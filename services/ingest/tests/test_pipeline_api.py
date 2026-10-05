import hashlib
import hmac
import json
import shutil

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.github_api import GitHubClient, RateLimited
from app.pipeline import run_ingest
from app.store import Store

from conftest import git


def make_cfg(tmp_path):
    return {"repos_dir": str(tmp_path / "repos"), "max_commits": 500, "max_issues": 100, "max_prs": 100, "github_token": ""}


def register(store, demo, repo_id="local__demo"):
    store.upsert_repo(repo_id, kind="local", source=demo["repo"], owner="local", name="demo", ref=None,
                      status="queued", options={"issues_file": demo["fixtures"]})
    return repo_id


def test_full_ingest_builds_chain_of_evidence(tmp_path, demo, fake_rag):
    store = Store(":memory:")
    rid = register(store, demo)
    job = store.create_job(rid, "full")
    run_ingest(store, fake_rag, make_cfg(tmp_path), rid, job)

    assert store.get_job(job)["status"] == "done", store.get_job(job)
    repo = store.get_repo(rid)
    assert repo["status"] == "ready" and repo["last_sha"] == demo["shas"]["poison"]
    counts = fake_rag.stats(rid)["counts"]
    assert counts["commit"] == 13 and counts["issue"] >= 8 and counts["pr"] >= 8 and counts["review"] >= 4
    assert counts["code"] > 0 and counts["doc"] > 0 and counts["diff"] > 0

    jwt = next(c for c in fake_rag.of_type("commit") if c["ref"] == f"commit:{demo['shas']['jwt'][:7]}")
    assert {"issue:#7", "pr:#8"} <= set(jwt["metadata"]["links"])
    review = next(c for c in fake_rag.of_type("review") if c["ref"] == "pr:#8")
    assert "HS256" in review["text"]


def test_leaked_key_never_reaches_the_index(tmp_path, demo, fake_rag):
    store = Store(":memory:")
    rid = register(store, demo)
    run_ingest(store, fake_rag, make_cfg(tmp_path), rid, store.create_job(rid, "full"))
    assert all("pk_live_51Hq" not in c["text"] for c in fake_rag.chunks.values())
    assert any("[REDACTED:assignment]" in c["text"] for c in fake_rag.of_type("diff"))
    assert store.get_repo(rid)["counts"]["_redactions"] >= 1


def test_reingest_is_idempotent(tmp_path, demo, fake_rag):
    store = Store(":memory:")
    rid = register(store, demo)
    run_ingest(store, fake_rag, make_cfg(tmp_path), rid, store.create_job(rid, "full"))
    first = dict(fake_rag.chunks)
    run_ingest(store, fake_rag, make_cfg(tmp_path), rid, store.create_job(rid, "full"))
    assert set(fake_rag.chunks) == set(first)


def test_incremental_sync_only_adds_new_commits(tmp_path, demo, fake_rag):
    origin = tmp_path / "origin"
    shutil.copytree(demo["repo"], origin)
    store = Store(":memory:")
    rid = "local__origin"
    store.upsert_repo(rid, kind="local", source=str(origin), owner="local", name="origin", ref=None,
                      status="queued", options={"issues_file": demo["fixtures"]})
    cfg = make_cfg(tmp_path)
    run_ingest(store, fake_rag, cfg, rid, store.create_job(rid, "full"))
    before = fake_rag.stats(rid)["counts"]["commit"]

    (origin / "src" / "new.py").write_text("def added():\n    return 1\n", encoding="utf-8")
    git(origin, "add", "-A")
    git(origin, "-c", "user.name=T", "-c", "user.email=t@t", "commit", "-q", "-m", "Add new helper (refs #22)")
    new_sha = git(origin, "rev-parse", "HEAD").strip()

    job = store.create_job(rid, "incremental")
    run_ingest(store, fake_rag, cfg, rid, job, incremental=True)
    assert store.get_job(job)["status"] == "done", store.get_job(job)
    assert fake_rag.stats(rid)["counts"]["commit"] == before + 1
    assert store.get_repo(rid)["last_sha"] == new_sha
    assert any(c["ref"] == f"commit:{new_sha[:7]}" for c in fake_rag.of_type("commit"))
    assert any(c["metadata"].get("path") == "src/new.py" for c in fake_rag.of_type("code"))


def test_failure_is_recorded_not_raised(tmp_path, fake_rag):
    store = Store(":memory:")
    store.upsert_repo("local__nope", kind="local", source=str(tmp_path / "missing"), owner="local", name="nope",
                      ref=None, status="queued", options={})
    job = store.create_job("local__nope", "full")
    run_ingest(store, fake_rag, make_cfg(tmp_path), "local__nope", job)
    assert store.get_job(job)["status"] == "failed"
    assert store.get_repo("local__nope")["status"] == "failed"


# ------------------------------------------------------------------ GitHub API
def gh_client(handler, **kw):
    return GitHubClient(token="t", base="https://api.test", transport=httpx.MockTransport(handler), **kw)


def test_github_pagination_follows_link_header():
    def handler(req):
        if req.url.params.get("page") == "2":
            return httpx.Response(200, json=[{"number": 2, "title": "b", "comments": 0, "labels": []}])
        return httpx.Response(200, json=[{"number": 1, "title": "a", "comments": 0, "labels": []}],
                              headers={"Link": '<https://api.test/repos/o/r/issues?page=2>; rel="next"'})

    issues = gh_client(handler).issues("o", "r")
    assert [i["number"] for i in issues] == [1, 2]


def test_github_skips_prs_in_issue_list_and_reads_comments():
    def handler(req):
        if req.url.path.endswith("/issues"):
            return httpx.Response(200, json=[
                {"number": 1, "title": "i", "comments": 1, "comments_url": "https://api.test/c/1", "labels": [{"name": "bug"}],
                 "user": {"login": "u"}},
                {"number": 2, "title": "pr", "pull_request": {}, "labels": []}])
        return httpx.Response(200, json=[{"user": {"login": "v"}, "body": "hello"}])

    issues = gh_client(handler).issues("o", "r")
    assert len(issues) == 1 and issues[0]["labels"] == ["bug"] and issues[0]["comments"][0]["body"] == "hello"


def test_github_rate_limit_waits_then_retries():
    calls, slept = [], []

    def handler(req):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(403, headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1005"})
        return httpx.Response(200, json=[])

    gh_client(handler, sleep=slept.append, clock=lambda: 1000.0).issues("o", "r")
    assert len(calls) == 2 and slept == [6.0]


def test_github_rate_limit_too_long_raises():
    def handler(req):
        return httpx.Response(403, headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "999999"})

    with pytest.raises(RateLimited):
        gh_client(handler, sleep=lambda s: None, clock=lambda: 0.0, max_wait=30).issues("o", "r")


def test_github_404_returns_empty():
    assert gh_client(lambda req: httpx.Response(404)).issues("o", "r") == []


# ------------------------------------------------------------------------ API
@pytest.fixture()
def client(tmp_path, monkeypatch, fake_rag):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("ALLOW_LOCAL_REPOS", "1")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "s3cret")
    main._state.clear()
    main._state["rag"] = fake_rag
    return TestClient(main.app)


def test_parse_source_forms():
    ps = main.parse_source
    assert ps("https://github.com/Owner/Repo.git", False)[3] == "owner__repo"
    assert ps("owner/repo", False)[:3] == ("github", "owner", "repo")
    with pytest.raises(Exception):
        ps("not a repo", False)
    with pytest.raises(Exception):
        ps("https://gitlab.com/a/b", False)


def test_register_runs_job_and_reports_progress(client, demo, fake_rag):
    r = client.post("/repos", json={"source": demo["repo"], "issues_file": demo["fixtures"]})
    assert r.status_code == 202
    body = r.json()
    job = client.get(f"/jobs/{body['job_id']}").json()
    assert job["status"] == "done"
    repo = client.get(f"/repos/{body['repo_id']}").json()
    assert repo["status"] == "ready" and repo["counts"]["commit"] == 13
    events = client.get(f"/jobs/{body['job_id']}/events").text
    assert "event: end" in events and '"stage": "commits"' in events
    assert client.post(f"/repos/{body['repo_id']}/sync").status_code == 202
    assert client.delete(f"/repos/{body['repo_id']}").json()["deleted"] == body["repo_id"]
    assert client.get(f"/repos/{body['repo_id']}").status_code == 404


def test_local_paths_rejected_when_disabled(client, monkeypatch, demo):
    monkeypatch.setenv("ALLOW_LOCAL_REPOS", "0")
    assert client.post("/repos", json={"source": demo["repo"]}).status_code == 400


def sign(body, secret="s3cret"):
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_webhook_requires_valid_signature(client):
    body = json.dumps({"repository": {"full_name": "o/r"}}).encode()
    h = {"x-github-event": "push", "content-type": "application/json"}
    assert client.post("/webhooks/github", content=body, headers=h).status_code == 401
    assert client.post("/webhooks/github", content=body, headers={**h, "x-hub-signature-256": sign(body, "wrong")}).status_code == 401
    ok = client.post("/webhooks/github", content=body, headers={**h, "x-hub-signature-256": sign(body)})
    assert ok.status_code == 200 and ok.json()["ignored"] == "repository not registered"


def test_webhook_ping_and_disabled_without_secret(client, monkeypatch):
    body = b"{}"
    ping = client.post("/webhooks/github", content=body, headers={"x-github-event": "ping", "x-hub-signature-256": sign(body)})
    assert ping.json()["pong"] is True
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "")
    assert client.post("/webhooks/github", content=body, headers={"x-github-event": "ping"}).status_code == 503


def test_webhook_triggers_incremental_sync(client, demo):
    rid = client.post("/repos", json={"source": demo["repo"], "issues_file": demo["fixtures"]}).json()["repo_id"]
    get = main.get_store()
    get.upsert_repo("o__r", kind="local", source=demo["repo"], owner="o", name="r", ref=None, status="ready",
                    options={"issues_file": demo["fixtures"]})
    body = json.dumps({"repository": {"full_name": "O/R"}}).encode()
    resp = client.post("/webhooks/github", content=body,
                       headers={"x-github-event": "push", "x-hub-signature-256": sign(body)})
    assert resp.json()["queued"] is True
    assert get.get_job(resp.json()["job_id"])["status"] in ("done", "failed")
    assert rid


def test_ingest_emits_structured_live_events(tmp_path, demo, fake_rag):
    store = Store(":memory:")
    rid = register(store, demo)
    job = store.create_job(rid, "full")
    run_ingest(store, fake_rag, make_cfg(tmp_path), rid, job)
    events = store.job_events(job)
    kinds = [e["data"]["kind"] for e in events if e["data"]]
    assert {"github", "links", "commit", "chunks", "file"} <= set(kinds)

    commits = [e["data"] for e in events if e["data"] and e["data"]["kind"] == "commit"]
    assert len(commits) == 13 and commits[0]["total"] == 13 and commits[-1]["index"] == 13
    jwt = next(c for c in commits if c["sha"] == demo["shas"]["jwt"][:7])
    assert jwt["subject"].startswith("Replace session cookies") and {"issue:#7", "pr:#8"} <= set(jwt["links"])

    chunk_events = [e["data"] for e in events if e["data"] and e["data"]["kind"] == "chunks"]
    assert chunk_events[-1]["counts"]["commit"] == 13 and chunk_events[0]["samples"]
    totals = [sum(c["counts"].values()) for c in chunk_events]
    assert totals == sorted(totals)                              # counters only ever grow
    assert all(e["progress"] is None or 0 <= e["progress"] <= 100 for e in events)
    assert store.get_job(job)["progress"] == 100


def test_sse_stream_carries_structured_data(client, demo):
    body = client.post("/repos", json={"source": demo["repo"], "issues_file": demo["fixtures"]}).json()
    stream = client.get(f"/jobs/{body['job_id']}/events").text
    assert '"kind": "commit"' in stream and '"kind": "chunks"' in stream and "event: end" in stream
