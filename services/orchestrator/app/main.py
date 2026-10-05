"""CodeOrigin orchestrator: runs the three experimental modes behind the guardrails."""
import json
import os
import queue
import threading
from typing import Literal, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .config import settings
from .pipeline import AskError, MODES, ask, probe

app = FastAPI(title="CodeOrigin orchestrator", version="0.1.0")


class Clients:
    """HTTP clients for rag and llm. Swappable in tests."""

    def __init__(self):
        self.rag = os.getenv("RAG_SERVICE_URL", "http://codeorigin-rag:8202").rstrip("/")
        self.llm = os.getenv("LLM_SERVICE_URL", "http://codeorigin-llm:8203").rstrip("/")
        self.http = httpx.Client(timeout=float(os.getenv("DOWNSTREAM_TIMEOUT_SECONDS", "300")))

    def _post(self, url, payload, what):
        try:
            r = self.http.post(url, json=payload)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as exc:
            raise AskError(502, f"{what} returned {exc.response.status_code}: {exc.response.text[:200]}")
        except httpx.HTTPError as exc:
            raise AskError(503, f"{what} unreachable: {exc}")

    def query(self, repo, question, types, top_k):
        return self._post(f"{self.rag}/query", {"repo": repo, "query": question, "source_types": types, "top_k": top_k}, "rag")

    def expand(self, repo, refs, limit):
        return self._post(f"{self.rag}/expand", {"repo": repo, "refs": refs, "limit": limit}, "rag")["chunks"]

    def generate(self, prompt, system, model, max_tokens):
        return self._post(f"{self.llm}/generate", {"prompt": prompt, "system": system, "model": model,
                                                   "temperature": 0.0, "seed": 42, "max_tokens": max_tokens}, "llm")

    def ready(self):
        out = {}
        for name, url in (("rag", self.rag), ("llm", self.llm)):
            try:
                out[name] = self.http.get(f"{url}/health", timeout=5).status_code == 200
            except httpx.HTTPError:
                out[name] = False
        return out


_clients = {}


def get_clients():
    if "c" not in _clients:
        _clients["c"] = Clients()
    return _clients["c"]


class AskRequest(BaseModel):
    repo: str = Field(min_length=1, max_length=200)
    question: str = Field(min_length=3, max_length=1000)
    mode: Literal["no_context", "code_only", "code_history", "oracle"] = "code_history"
    model: Optional[str] = Field(default=None, max_length=100)
    top_k: Optional[int] = Field(default=None, ge=1, le=30)
    oracle_refs: Optional[list[str]] = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    r = get_clients().ready()
    if not all(r.values()):
        raise HTTPException(503, detail=r)
    return {"status": "ready", **r}


@app.get("/config")
def config():
    return {"modes": list(MODES), "settings": settings()}


@app.post("/ask")
def ask_endpoint(req: AskRequest):
    try:
        return ask(req.model_dump(), get_clients())
    except AskError as exc:
        raise HTTPException(exc.status, exc.detail)


class ProbeRequest(BaseModel):
    repo: str = Field(min_length=1, max_length=200)
    question: str = Field(min_length=3, max_length=1000)
    top_k: Optional[int] = Field(default=None, ge=1, le=30)


@app.post("/retrieve")
def retrieve_probe(req: ProbeRequest):
    """Retrieval scores only (no LLM). Calibration / debugging aid."""
    try:
        return probe(req.model_dump(), get_clients())
    except AskError as exc:
        raise HTTPException(exc.status, exc.detail)


@app.post("/ask/stream")
def ask_stream(req: AskRequest):
    """Server-Sent Events: one `stage` event per pipeline step as it happens, then a final `result`."""
    q = queue.Queue()
    clients = get_clients()

    def work():
        try:
            result = ask(req.model_dump(), clients, emit=q.put)
            q.put({"type": "result", "result": result})
        except AskError as exc:
            q.put({"type": "error", "status": exc.status, "detail": exc.detail})
        except Exception as exc:  # noqa: BLE001 - the stream must always terminate cleanly
            q.put({"type": "error", "status": 500, "detail": f"{type(exc).__name__}: {exc}"})
        finally:
            q.put(None)

    threading.Thread(target=work, daemon=True).start()

    def gen():
        while True:
            item = q.get()
            if item is None:
                return
            yield "data: " + json.dumps(item) + "\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
