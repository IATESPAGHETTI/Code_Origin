"""Thin, safe wrapper around the git CLI. Repository code is only ever *read*;
nothing from a repo is executed."""
import base64
import os
import re
import subprocess

FS, RS = "\x1f", "\x1e"
LOG_FORMAT = FS.join(["%H", "%an", "%ae", "%aI", "%P", "%s", "%b"]) + RS

SKIP_DIRS = {".git", "node_modules", "vendor", "dist", "build", "__pycache__", ".venv", "venv", ".next", "target", "site-packages"}
SKIP_SUFFIX = (".lock", ".min.js", ".min.css", ".map", ".svg", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf",
               ".zip", ".gz", ".tar", ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".mp3", ".class", ".jar", ".exe",
               ".dll", ".so", ".pyc", ".bin", ".lockb")
SKIP_NAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "Cargo.lock", "go.sum"}
DOC_SUFFIX = (".md", ".rst", ".txt", ".adoc")
MAX_FILE_BYTES = 200_000


class GitError(RuntimeError):
    pass


def _scrub(text, token):
    if token:
        text = text.replace(token, "***")
        text = text.replace(base64.b64encode(f"x-access-token:{token}".encode()).decode(), "***")
    return text


def run_git(args, cwd=None, token=None, timeout=600):
    cmd = ["git"]
    if token:
        b64 = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        cmd += ["-c", f"http.extraheader=AUTHORIZATION: basic {b64}"]
    cmd += list(args)
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"}
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        raise GitError(f"git {args[0]} timed out after {timeout}s")
    if p.returncode != 0:
        raise GitError(_scrub(f"git {' '.join(args[:2])} failed: {p.stderr.strip()[:500]}", token))
    return p.stdout


def sync_repo(source, dest, ref=None, token=None):
    """Clone if absent, otherwise fetch and fast-forward. Returns HEAD sha."""
    if os.path.isdir(os.path.join(dest, ".git")):
        run_git(["fetch", "--tags", "--prune", "origin"], cwd=dest, token=token)
        if ref:
            try:
                run_git(["checkout", "--force", "--detach", f"origin/{ref}"], cwd=dest)
            except GitError:
                run_git(["checkout", "--force", "--detach", ref], cwd=dest)
        else:
            try:
                run_git(["reset", "--hard", "origin/HEAD"], cwd=dest)
            except GitError:
                run_git(["reset", "--hard", "FETCH_HEAD"], cwd=dest)
    else:
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        run_git(["clone", "--quiet", source, dest], token=token)
        if ref:
            run_git(["checkout", "--force", "--detach", ref], cwd=dest)
    return head_sha(dest)


def head_sha(path):
    return run_git(["rev-parse", "HEAD"], cwd=path).strip()


def sha_exists(path, sha):
    try:
        run_git(["cat-file", "-e", f"{sha}^{{commit}}"], cwd=path)
        return True
    except GitError:
        return False


def list_commits(path, since_sha=None, max_count=2000):
    args = ["log", f"--format={LOG_FORMAT}", f"--max-count={max_count}"]
    if since_sha and sha_exists(path, since_sha):
        args.append(f"{since_sha}..HEAD")
    out = run_git(args, cwd=path)
    commits = []
    for rec in out.split(RS):
        rec = rec.strip("\n")
        if not rec.strip():
            continue
        parts = rec.split(FS)
        if len(parts) < 7:
            continue
        sha, an, ae, date, parents, subject, body = parts[:7]
        commits.append({
            "sha": sha.strip(), "author": an, "email": ae, "date": date,
            "parents": parents.split(), "subject": subject, "body": body.strip(),
        })
    return commits


def commit_numstat(path, sha):
    out = run_git(["show", "--format=", "--numstat", "-m", "--first-parent", sha], cwd=path)
    files = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            add, dele, name = parts
            files.append({"path": name, "added": int(add) if add.isdigit() else 0,
                          "deleted": int(dele) if dele.isdigit() else 0})
    return files


_DIFF_SPLIT = re.compile(r"^diff --git a/(.*?) b/(.*)$", re.M)


def commit_diff_sections(path, sha, max_total=60_000):
    """[(file_path, diff_text)] for a commit, skipping binary/noise files."""
    out = run_git(["show", "--format=", "-U3", "--no-color", "-m", "--first-parent", sha], cwd=path)
    out = out[:max_total]
    matches = list(_DIFF_SPLIT.finditer(out))
    sections = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(out)
        name = m.group(2)
        body = out[m.start():end]
        if "Binary files" in body[:400] or is_noise(name):
            continue
        sections.append((name, body))
    return sections


def is_noise(name):
    base = os.path.basename(name)
    return base in SKIP_NAMES or name.endswith(SKIP_SUFFIX)


def iter_files(path):
    """Yield (relative_path, text) for text files tracked at HEAD."""
    out = run_git(["ls-files", "-z"], cwd=path)
    for rel in filter(None, out.split("\0")):
        parts = rel.replace("\\", "/").split("/")
        if any(p in SKIP_DIRS for p in parts[:-1]) or is_noise(rel):
            continue
        full = os.path.join(path, rel)
        try:
            if os.path.getsize(full) > MAX_FILE_BYTES:
                continue
            with open(full, "rb") as fh:
                raw = fh.read()
        except OSError:
            continue
        if b"\0" in raw[:2048]:
            continue
        yield rel.replace("\\", "/"), raw.decode("utf-8", errors="replace")


def is_doc(rel):
    return rel.lower().endswith(DOC_SUFFIX)
