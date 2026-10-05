"""The ingest job: git + GitHub -> chunks -> rag service.

Stages: clone/fetch -> github -> links -> commits -> code/docs -> issues/PRs.
Every chunk's text passes through secret redaction (G6) before indexing.
"""
import os
from datetime import datetime, timezone

import httpx

from . import git_ops, parsers
from .github_api import GitHubClient, load_fixture
from .links import build_graph, short_sha
from .secrets_redact import redact

BATCH = 64


class RagClient:
    def __init__(self, base_url, timeout=120.0):
        self.base = base_url.rstrip("/")
        self.http = httpx.Client(timeout=timeout)

    def index(self, repo, chunks):
        r = self.http.post(f"{self.base}/index", json={"repo": repo, "chunks": chunks})
        r.raise_for_status()
        return r.json()

    def stats(self, repo):
        r = self.http.get(f"{self.base}/stats", params={"repo": repo})
        r.raise_for_status()
        return r.json()

    def delete(self, repo, source_types=None):
        params = {"source_types": ",".join(source_types)} if source_types else None
        r = self.http.delete(f"{self.base}/repos/{repo}", params=params)
        r.raise_for_status()
        return r.json()


class Pusher:
    """Batches chunks to the rag service, redacting secrets on the way."""

    def __init__(self, rag, repo, on_flush=None):
        self.rag, self.repo, self.on_flush = rag, repo, on_flush
        self.buf, self.counts, self.redactions = [], {}, 0

    def add(self, chunks):
        for c in chunks:
            c["text"], n = redact(c["text"])
            self.redactions += n
            self.buf.append(c)
            self.counts[c["source_type"]] = self.counts.get(c["source_type"], 0) + 1
            if len(self.buf) >= BATCH:
                self.flush()

    def flush(self):
        if self.buf:
            samples = [{"ref": c["ref"], "type": c["source_type"], "preview": " ".join(c["text"][:90].split())}
                       for c in self.buf[:: max(1, len(self.buf) // 3)][:3]]
            batch = len(self.buf)
            self.rag.index(self.repo, self.buf)
            self.buf = []
            if self.on_flush:
                self.on_flush({"kind": "chunks", "batch": batch, "counts": dict(self.counts),
                               "redactions": self.redactions, "samples": samples})


def _iso_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_ingest(store, rag, cfg, repo_id, job_id, incremental=False, github_factory=None):
    """Runs one ingest/sync job. Never raises: failures are recorded on the job."""
    repo = store.get_repo(repo_id)
    opts = repo["options"]
    max_commits = int(opts.get("max_commits") or cfg["max_commits"])
    token = cfg.get("github_token") or None

    def step(stage, msg, pct=None, data=None):
        store.progress(job_id, stage, msg, pct, data)

    try:
        store.update_repo(repo_id, status="ingesting", error=None)
        full = not incremental or not repo.get("last_sha")
        dest = os.path.join(cfg["repos_dir"], repo_id)
        base_url = f"https://github.com/{repo['owner']}/{repo['name']}" if repo["kind"] == "github" else ""
        remote = f"https://github.com/{repo['owner']}/{repo['name']}.git" if repo["kind"] == "github" else repo["source"]

        step("clone", "fetching repository" if not full else "cloning repository", 5)
        head = git_ops.sync_repo(remote, dest, ref=repo.get("ref"), token=token)

        if full:
            rag.delete(repo_id)
        else:
            rag.delete(repo_id, ["code", "doc"])

        # ---- issues / PRs / releases (GitHub API, or offline fixture)
        step("github", "reading issues and pull requests", 15)
        since = None if full else repo.get("last_issue_sync")
        issues, prs, releases = [], [], []
        gh = None
        if opts.get("issues_file"):
            fx = load_fixture(opts["issues_file"])
            issues, prs, releases = fx["issues"], fx["pulls"], fx["releases"]
        elif repo["kind"] == "github" and opts.get("include_history", True):
            gh = (github_factory or GitHubClient)(token=token)
            try:
                issues = gh.issues(repo["owner"], repo["name"], since=since, limit=cfg["max_issues"])
                prs = gh.pulls(repo["owner"], repo["name"], since=since, limit=cfg["max_prs"])
                releases = gh.releases(repo["owner"], repo["name"])
            finally:
                gh.close()
        sync_started = _iso_now()
        if issues or prs or releases:
            step("github", f"{len(issues)} issues, {len(prs)} pull requests, {len(releases)} releases", 22,
                 {"kind": "github", "issues": len(issues), "prs": len(prs), "releases": len(releases)})

        # ---- commits
        step("commits", "reading commit history", 30)
        commits = git_ops.list_commits(dest, since_sha=None if full else repo["last_sha"], max_count=max_commits)
        graph = build_graph(commits, issues, prs)
        step("links", f"{graph.edge_count()} issue/PR/commit links", 34,
             {"kind": "links", "edges": graph.edge_count(), "commits": len(commits), "issues": len(issues), "prs": len(prs)})

        pusher = Pusher(rag, repo_id, on_flush=lambda d: step("index", f"{sum(d['counts'].values())} chunks indexed", None, d))
        total = max(len(commits), 1)
        every = max(1, len(commits) // 60)   # at most ~60 commit events, however long the history
        for i, c in enumerate(commits):
            ref = f"commit:{short_sha(c['sha'])}"
            links = graph.links(ref)
            files = git_ops.commit_numstat(dest, c["sha"])
            pusher.add([parsers.commit_chunk(repo_id, base_url, c, files, links)])
            n_diff = 0
            if opts.get("include_diffs", True):
                diffs = parsers.diff_chunks(repo_id, base_url, c, git_ops.commit_diff_sections(dest, c["sha"]), links)
                n_diff = len(diffs)
                pusher.add(diffs)
            if i % every == 0 or i == len(commits) - 1:
                step("commits", f"commit {i + 1}/{len(commits)}", 36 + int(30 * (i + 1) / total),
                     {"kind": "commit", "index": i + 1, "total": len(commits), "sha": short_sha(c["sha"]), "subject": c["subject"],
                      "author": c["author"], "date": c["date"][:10], "files": len(files), "diff_chunks": n_diff,
                      "links": links})

        # ---- code & docs at HEAD
        step("code", "chunking source and docs", 70)
        ref_name = repo.get("ref") or "HEAD"
        files_list = list(git_ops.iter_files(dest))
        every_f = max(1, len(files_list) // 80)
        for fi, (rel, text) in enumerate(files_list):
            is_doc = git_ops.is_doc(rel)
            made = (parsers.doc_chunks if is_doc else parsers.code_chunks)(repo_id, base_url, rel, text, ref_name)
            pusher.add(made)
            if fi % every_f == 0 or fi == len(files_list) - 1:
                step("code", f"{rel}", 68 + int(18 * (fi + 1) / max(len(files_list), 1)),
                     {"kind": "file", "path": rel, "type": "doc" if is_doc else "code", "chunks": len(made),
                      "index": fi + 1, "total": len(files_list)})

        # ---- issues / PRs / reviews / releases
        step("issues", "indexing issues, PRs and reviews", 88)
        for it in issues:
            pusher.add(parsers.issue_chunks(repo_id, base_url, it, graph.links(f"issue:#{it['number']}")))
        for pr in prs:
            pusher.add(parsers.pr_chunks(repo_id, base_url, pr, graph.links(f"pr:#{pr['number']}")))
        for rel in releases:
            pusher.add([parsers.release_chunk(repo_id, base_url, rel)])
        pusher.flush()

        counts = dict(rag.stats(repo_id).get("counts", {}))
        prior = 0 if full else int((repo.get("counts") or {}).get("_redactions", 0))
        counts["_redactions"] = prior + pusher.redactions
        store.update_repo(repo_id, status="ready", last_sha=head, last_issue_sync=sync_started, counts=counts, error=None)
        store.finish_job(job_id, "done", f"indexed {sum(pusher.counts.values())} chunks from {len(commits)} commits")
    except Exception as exc:  # noqa: BLE001 - job runner must record every failure
        msg = f"{type(exc).__name__}: {exc}"[:500]
        store.update_repo(repo_id, status="failed", error=msg)
        store.finish_job(job_id, "failed", msg)
