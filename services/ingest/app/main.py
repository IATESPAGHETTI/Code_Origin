"""CodeOrigin ingest service: registers repositories and keeps them indexed."""
import asyncio
import hashlib
import hmac
import json
import os
import re
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .pipeline import RagClient, run_ingest
from .store import Store

app = FastAPI(title="CodeOrigin ingest", version="0.1.0")

_state = {}

GITHUB_RE = re.compile(r"^(?:https?://github\.com/)?([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")


def cfg():
    return {
        "data_dir": os.getenv("DATA_DIR", "/data"),
        "repos_dir": os.path.join(os.getenv("DATA_DIR", "/data"), "repos"),
        "rag_url": os.getenv("RAG_SERVICE_URL", "http://codeorigin-rag:8202"),
        "github_token": os.getenv("GITHUB_TOKEN", ""),
        "webhook_secret": os.getenv("GITHUB_WEBHOOK_SECRET", ""),
        "allow_local": os.getenv("ALLOW_LOCAL_REPOS", "0") == "1",
        "max_commits": int(os.getenv("MAX_COMMITS", "2000")),
        "max_issues": int(os.getenv("MAX_ISSUES", "300")),
        "max_prs": int(os.getenv("MAX_PRS", "200")),
    }


def get_store() -> Store:
    if "store" not in _state:
        path = os.path.join(cfg()["data_dir"], "ingest.db") if os.getenv("DATA_DIR", "/data") != ":memory:" else ":memory:"
        _state["store"] = Store(path)
        _state["store"].fail_stale_jobs()
    return _state["store"]


def get_rag():
    if "rag" not in _state:
        _state["rag"] = RagClient(cfg()["rag_url"])
    return _state["rag"]


def parse_source(source: str, allow_local: bool):
    """-> (kind, owner, name, repo_id, source)"""
    source = source.strip()
    if allow_local and os.path.isdir(source):
        path = os.path.abspath(source)
        name = re.sub(r"[^A-Za-z0-9_.-]", "_", os.path.basename(path.rstrip("/\\")) or "repo")
        return "local", "local", name, f"local__{name}", path
    m = GITHUB_RE.match(source)
    if not m:
        raise HTTPException(400, "source must be a github.com URL, 'owner/repo', or (when enabled) a local path")
    owner, name = m.group(1), m.group(2)
    return "github", owner, name, f"{owner}__{name}".lower(), f"https://github.com/{owner}/{name}"


class RepoCreate(BaseModel):
    source: str = Field(min_length=3, max_length=500)
    ref: Optional[str] = Field(default=None, max_length=200)
    issues_file: Optional[str] = None  # offline fixture (local repos / tests)
    max_commits: Optional[int] = Field(default=None, ge=1, le=20000)
    include_history: bool = True
    include_diffs: bool = True


def _start(background: BackgroundTasks, repo_id: str, kind: str, incremental: bool):
    store = get_store()
    if store.active_job(repo_id):
        raise HTTPException(409, "an ingest job is already running for this repository")
    job_id = store.create_job(repo_id, kind)
    background.add_task(run_ingest, store, get_rag(), cfg(), repo_id, job_id, incremental)
    return job_id


@app.get("/health")
def health():
    get_store()
    return {"status": "ok", "github_token": bool(cfg()["github_token"]), "webhooks": bool(cfg()["webhook_secret"])}


@app.post("/repos", status_code=202)
def register_repo(req: RepoCreate, background: BackgroundTasks):
    c = cfg()
    kind, owner, name, repo_id, source = parse_source(req.source, c["allow_local"])
    if req.issues_file and not c["allow_local"]:
        raise HTTPException(400, "issues_file is only allowed when local repositories are enabled")
    options = {"include_history": req.include_history, "include_diffs": req.include_diffs}
    if req.issues_file:
        options["issues_file"] = req.issues_file
    if req.max_commits:
        options["max_commits"] = req.max_commits
    get_store().upsert_repo(repo_id, kind=kind, source=source, owner=owner, name=name, ref=req.ref,
                            status="queued", options=options)
    job_id = _start(background, repo_id, "full", incremental=False)
    return {"repo_id": repo_id, "job_id": job_id}


@app.get("/repos")
def list_repos():
    return {"repos": get_store().list_repos()}


@app.get("/repos/{repo_id}")
def get_repo(repo_id: str):
    repo = get_store().get_repo(repo_id)
    if not repo:
        raise HTTPException(404, "unknown repository")
    return repo


@app.post("/repos/{repo_id}/sync", status_code=202)
def sync_repo(repo_id: str, background: BackgroundTasks):
    if not get_store().get_repo(repo_id):
        raise HTTPException(404, "unknown repository")
    return {"repo_id": repo_id, "job_id": _start(background, repo_id, "incremental", incremental=True)}


@app.delete("/repos/{repo_id}")
def delete_repo(repo_id: str):
    store = get_store()
    if not store.get_repo(repo_id):
        raise HTTPException(404, "unknown repository")
    if store.active_job(repo_id):
        raise HTTPException(409, "an ingest job is running for this repository")
    try:
        get_rag().delete(repo_id)
    except Exception as exc:  # rag down: keep the repo registered so the user can retry
        raise HTTPException(502, f"could not clear index: {exc}")
    store.delete_repo(repo_id)
    return {"deleted": repo_id}


@app.get("/jobs/{job_id}")
def get_job(job_id: int):
    job = get_store().get_job(job_id)
    if not job:
        raise HTTPException(404, "unknown job")
    return job


@app.get("/jobs/{job_id}/events")
async def job_events(job_id: int):
    store = get_store()
    if not store.get_job(job_id):
        raise HTTPException(404, "unknown job")

    async def gen():
        last = 0
        while True:
            for ev in store.job_events(job_id, last):
                last = ev["id"]
                yield f"data: {json.dumps(ev)}\n\n"
            job = store.get_job(job_id)
            if job["status"] != "running":
                for ev in store.job_events(job_id, last):
                    yield f"data: {json.dumps(ev)}\n\n"
                yield f"event: end\ndata: {json.dumps({'status': job['status']})}\n\n"
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(gen(), media_type="text/event-stream")


def verify_signature(secret: str, body: bytes, header: Optional[str]) -> bool:
    """GitHub signs the raw body: X-Hub-Signature-256: sha256=<hmac>."""
    if not secret or not header or not header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header)


@app.post("/webhooks/github")
async def github_webhook(request: Request, background: BackgroundTasks):
    c = cfg()
    if not c["webhook_secret"]:
        raise HTTPException(503, "webhooks disabled: GITHUB_WEBHOOK_SECRET is not set")
    body = await request.body()
    if not verify_signature(c["webhook_secret"], body, request.headers.get("x-hub-signature-256")):
        raise HTTPException(401, "invalid signature")
    event = request.headers.get("x-github-event", "")
    if event == "ping":
        return {"ok": True, "pong": True}
    try:
        payload = json.loads(body)
        full_name = payload["repository"]["full_name"]
    except (ValueError, KeyError, TypeError):
        raise HTTPException(400, "malformed payload")
    if event not in ("push", "issues", "issue_comment", "pull_request", "pull_request_review", "release"):
        return {"ok": True, "ignored": event}
    repo_id = full_name.replace("/", "__").lower()
    store = get_store()
    if not store.get_repo(repo_id):
        return {"ok": True, "ignored": "repository not registered"}
    if store.active_job(repo_id):
        return {"ok": True, "queued": False, "reason": "sync already running"}
    return {"ok": True, "queued": True, "job_id": _start(background, repo_id, "webhook", incremental=True)}
