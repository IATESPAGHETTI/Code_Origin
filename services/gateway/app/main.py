"""CodeOrigin gateway: single entrypoint, input limits (G7), rate limiting,
request ids, metrics, and passthrough to the internal services."""
import json
import os
import re
import threading
import time
import uuid
from collections import defaultdict, deque
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field

app = FastAPI(title="CodeOrigin gateway", version="0.1.0")

SERVICES = {
    "ingest": os.getenv("INGEST_SERVICE_URL", "http://codeorigin-ingest:8201"),
    "rag": os.getenv("RAG_SERVICE_URL", "http://codeorigin-rag:8202"),
    "llm": os.getenv("LLM_SERVICE_URL", "http://codeorigin-llm:8203"),
    "orchestrator": os.getenv("ORCHESTRATOR_URL", "http://codeorigin-orchestrator:8204"),
    "eval": os.getenv("EVAL_SERVICE_URL", "http://codeorigin-eval:8205"),
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5180,http://127.0.0.1:5180").split(",") if o.strip()],
    allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Request-ID"],
)

REQS = Counter("codeorigin_requests_total", "Gateway requests", ["route", "method", "status"])
LATENCY = Histogram("codeorigin_request_seconds", "Gateway request latency", ["route"],
                    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300))
GUARD = Counter("codeorigin_guardrail_triggers_total", "Guardrail activations", ["guardrail", "action"])
TOKENS = Counter("codeorigin_llm_tokens_total", "LLM tokens", ["direction", "mode"])
REFUSALS = Counter("codeorigin_refusals_total", "Refused questions", ["type"])

GITHUB_SOURCE = re.compile(r"^(?:https://github\.com/)?[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?(?:\.git)?/?$")
MAX_QUESTION = 1000


def cfg():
    return {
        "allow_local": os.getenv("ALLOW_LOCAL_REPOS", "0") == "1",
        "api_key": os.getenv("API_KEY", ""),
        "rate_ask": int(os.getenv("RATE_LIMIT_ASK_PER_MIN", "30")),
        "rate_other": int(os.getenv("RATE_LIMIT_OTHER_PER_MIN", "240")),
        "timeout": float(os.getenv("GATEWAY_TIMEOUT_SECONDS", "300")),
    }


# ------------------------------------------------------------------ rate limit
class SlidingWindow:
    def __init__(self):
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key, limit, window=60.0, now=None):
        now = time.monotonic() if now is None else now
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                return False, max(1, int(window - (now - q[0])))
            q.append(now)
            return True, 0


limiter = SlidingWindow()
_http = {}


def http():
    if "c" not in _http:
        _http["c"] = httpx.Client(timeout=cfg()["timeout"])
    return _http["c"]


@app.middleware("http")
async def guard_and_observe(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    request.state.rid = rid
    path = request.url.path
    route = re.sub(r"/\d+", "/{id}", path)
    t0 = time.perf_counter()
    c = cfg()

    if path.startswith("/api/") and path != "/api/webhooks/github" and c["api_key"]:
        if request.headers.get("x-api-key") != c["api_key"]:
            resp = JSONResponse({"detail": "invalid or missing API key"}, status_code=401)
            resp.headers["X-Request-ID"] = rid
            return resp
    if path.startswith("/api/") and request.method != "OPTIONS":
        client = request.client.host if request.client else "?"
        bucket, limit = ("ask", c["rate_ask"]) if path in ("/api/ask", "/api/ask/stream") else ("other", c["rate_other"])
        ok, retry = limiter.allow((client, bucket), limit)
        if not ok:
            resp = JSONResponse({"detail": "rate limit exceeded"}, status_code=429, headers={"Retry-After": str(retry)})
            resp.headers["X-Request-ID"] = rid
            REQS.labels(route, request.method, "429").inc()
            return resp

    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    if path != "/metrics":
        REQS.labels(route, request.method, str(response.status_code)).inc()
        LATENCY.labels(route).observe(time.perf_counter() - t0)
    return response


# --------------------------------------------------------------------- helpers
def forward(method, service, path, rid, **kw):
    headers = {"x-request-id": rid, **kw.pop("headers", {})}
    try:
        r = http().request(method, f"{SERVICES[service]}{path}", headers=headers, **kw)
    except httpx.HTTPError as exc:
        raise HTTPException(503, f"{service} unreachable: {exc}")
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail", r.text)
        except ValueError:
            detail = r.text
        raise HTTPException(r.status_code, detail)
    ctype = r.headers.get("content-type", "")
    if "application/json" in ctype:
        return r.json()
    return Response(content=r.content, media_type=ctype or "text/plain")


def rid_of(request: Request):
    return request.state.rid


# ---------------------------------------------------------------------- models
class RepoIn(BaseModel):
    source: str = Field(min_length=3, max_length=300)
    ref: Optional[str] = Field(default=None, max_length=200)
    max_commits: Optional[int] = Field(default=None, ge=1, le=20000)
    include_history: bool = True
    include_diffs: bool = True
    issues_file: Optional[str] = None


class AskIn(BaseModel):
    repo: str = Field(min_length=1, max_length=200)
    question: str = Field(min_length=3, max_length=MAX_QUESTION)
    mode: str = "code_history"
    model: Optional[str] = Field(default=None, max_length=100)
    top_k: Optional[int] = Field(default=None, ge=1, le=30)


# ---------------------------------------------------------------------- routes
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/health/all")
def health_all():
    out = {}
    for name, url in SERVICES.items():
        try:
            out[name] = http().get(f"{url}/health", timeout=5).status_code == 200
        except httpx.HTTPError:
            out[name] = False
    return {"status": "ok" if all(out.values()) else "degraded", "services": out}


@app.post("/api/repos", status_code=202)
def add_repo(body: RepoIn, request: Request):
    c = cfg()
    src = body.source.strip()
    if not c["allow_local"]:
        if not GITHUB_SOURCE.match(src):
            raise HTTPException(400, "source must be a github.com URL or 'owner/repo'")
        if body.issues_file:
            raise HTTPException(400, "issues_file is not allowed")
    return forward("POST", "ingest", "/repos", rid_of(request), json=body.model_dump(exclude_none=True))


@app.get("/api/repos")
def list_repos(request: Request):
    return forward("GET", "ingest", "/repos", rid_of(request))


@app.get("/api/repos/{repo_id}")
def get_repo(repo_id: str, request: Request):
    return forward("GET", "ingest", f"/repos/{repo_id}", rid_of(request))


@app.delete("/api/repos/{repo_id}")
def delete_repo(repo_id: str, request: Request):
    return forward("DELETE", "ingest", f"/repos/{repo_id}", rid_of(request))


@app.post("/api/repos/{repo_id}/sync", status_code=202)
def sync_repo(repo_id: str, request: Request):
    return forward("POST", "ingest", f"/repos/{repo_id}/sync", rid_of(request))


@app.get("/api/jobs/{job_id}")
def get_job(job_id: int, request: Request):
    return forward("GET", "ingest", f"/jobs/{job_id}", rid_of(request))


@app.get("/api/jobs/{job_id}/events")
def job_events(job_id: int, request: Request):
    url = f"{SERVICES['ingest']}/jobs/{job_id}/events"

    def gen():
        try:
            with httpx.stream("GET", url, timeout=None, headers={"x-request-id": rid_of(request)}) as r:
                if r.status_code >= 400:
                    yield f"event: error\ndata: {r.status_code}\n\n"
                    return
                for chunk in r.iter_text():
                    yield chunk
        except httpx.HTTPError as exc:
            yield f"event: error\ndata: {exc}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


def record_ask_metrics(res):
    for g in res.get("guardrails", []):
        if g.get("triggered"):
            GUARD.labels(g["id"], g.get("action", "")).inc()
    if res.get("refused"):
        REFUSALS.labels(res.get("refusal_type") or "unknown").inc()
    tok = res.get("tokens", {})
    TOKENS.labels("in", res["mode"]).inc(tok.get("in", 0))
    TOKENS.labels("out", res["mode"]).inc(tok.get("out", 0))


def check_mode(body):
    if body.mode not in ("no_context", "code_only", "code_history"):
        raise HTTPException(422, "mode must be no_context, code_only or code_history")


@app.post("/api/ask")
def ask(body: AskIn, request: Request):
    check_mode(body)
    res = forward("POST", "orchestrator", "/ask", rid_of(request), json=body.model_dump(exclude_none=True))
    record_ask_metrics(res)
    return res


@app.post("/api/ask/stream")
def ask_stream(body: AskIn, request: Request):
    """Live pipeline: Server-Sent Events, one event per stage, then the final result."""
    check_mode(body)
    url = f"{SERVICES['orchestrator']}/ask/stream"
    payload = body.model_dump(exclude_none=True)
    rid = rid_of(request)

    def gen():
        buf = ""
        try:
            with httpx.stream("POST", url, json=payload, timeout=None, headers={"x-request-id": rid}) as r:
                if r.status_code >= 400:
                    r.read()
                    yield "data: " + json.dumps({"type": "error", "status": r.status_code, "detail": r.text[:300]}) + "\n\n"
                    return
                for chunk in r.iter_text():
                    yield chunk
                    buf += chunk
                    *blocks, buf = buf.split("\n\n")
                    for block in blocks:
                        if block.startswith("data: "):
                            try:
                                event = json.loads(block[6:])
                            except ValueError:
                                continue
                            if event.get("type") == "result":
                                record_ask_metrics(event["result"])
        except httpx.HTTPError as exc:
            yield "data: " + json.dumps({"type": "error", "status": 503, "detail": f"orchestrator unreachable: {exc}"}) + "\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/config")
def config(request: Request):
    out = forward("GET", "orchestrator", "/config", rid_of(request))
    try:
        out["models"] = forward("GET", "llm", "/models", rid_of(request))["models"]
    except HTTPException:
        out["models"] = []
    return out


@app.get("/api/evidence/{repo_id}/{ref:path}")
def evidence(repo_id: str, ref: str, request: Request):
    res = forward("POST", "rag", "/expand", rid_of(request), json={"repo": repo_id, "refs": [ref], "limit": 20})
    if not res["chunks"]:
        raise HTTPException(404, "no such evidence")
    return res


# --- evaluation passthrough
@app.get("/api/eval/datasets")
def eval_datasets(request: Request):
    return forward("GET", "eval", "/datasets", rid_of(request))


@app.get("/api/eval/datasets/{name}")
def eval_dataset(name: str, request: Request):
    return forward("GET", "eval", f"/datasets/{name}", rid_of(request))


@app.post("/api/eval/runs", status_code=202)
async def eval_start(request: Request):
    return forward("POST", "eval", "/runs", rid_of(request), json=await request.json())


@app.get("/api/eval/runs")
def eval_runs(request: Request):
    return forward("GET", "eval", "/runs", rid_of(request))


@app.get("/api/eval/runs/{run_id}")
def eval_run(run_id: int, request: Request):
    return forward("GET", "eval", f"/runs/{run_id}", rid_of(request))


@app.get("/api/eval/runs/{run_id}/report")
def eval_report(run_id: int, request: Request):
    return forward("GET", "eval", f"/runs/{run_id}/report", rid_of(request))


@app.get("/api/eval/runs/{run_id}/results")
def eval_results(run_id: int, request: Request, with_response: bool = False):
    return forward("GET", "eval", f"/runs/{run_id}/results?with_response={'true' if with_response else 'false'}", rid_of(request))


@app.get("/api/eval/runs/{run_id}/worksheet")
def eval_worksheet(run_id: int, request: Request):
    return forward("GET", "eval", f"/runs/{run_id}/worksheet", rid_of(request))


@app.post("/api/eval/runs/{run_id}/human-grades")
async def eval_grades(run_id: int, request: Request):
    return forward("POST", "eval", f"/runs/{run_id}/human-grades", rid_of(request), json=await request.json())


@app.get("/api/eval/runs/{run_id}/calibration")
def eval_calibration(run_id: int, request: Request):
    return forward("GET", "eval", f"/runs/{run_id}/calibration", rid_of(request))


# --- GitHub webhooks: raw body and signature headers pass through untouched
@app.post("/api/webhooks/github")
async def webhook(request: Request):
    body = await request.body()
    headers = {k: v for k, v in request.headers.items() if k.lower() in ("x-hub-signature-256", "x-github-event", "content-type")}
    return forward("POST", "ingest", "/webhooks/github", rid_of(request), content=body, headers=headers)
