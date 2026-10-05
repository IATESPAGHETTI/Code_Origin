"""CodeOrigin rag service: chunk storage, embeddings, hybrid retrieval."""
import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from .embeddings import get_embedder
from .hybrid import Retriever
from .store import ChromaStore, MemoryStore

app = FastAPI(title="CodeOrigin rag", version="0.1.0")

_state = {}


def get_retriever() -> Retriever:
    if "retriever" not in _state:
        backend = os.getenv("STORE_BACKEND", "memory").lower()
        if backend == "chroma":
            store = ChromaStore(host=os.getenv("CHROMA_HOST", "codeorigin-chromadb"), port=int(os.getenv("CHROMA_PORT", "8000")))
        else:
            store = MemoryStore()
        _state["retriever"] = Retriever(store, get_embedder())
    return _state["retriever"]


class ChunkIn(BaseModel):
    id: str
    ref: str
    source_type: str
    text: str
    metadata: dict = Field(default_factory=dict)


class IndexRequest(BaseModel):
    repo: str
    chunks: list[ChunkIn]


class Filters(BaseModel):
    path_prefix: Optional[str] = None
    author: Optional[str] = None
    since: Optional[str] = None
    until: Optional[str] = None


class QueryRequest(BaseModel):
    repo: str
    query: str = Field(min_length=1, max_length=2000)
    source_types: Optional[list[str]] = None
    top_k: int = Field(default=8, ge=1, le=50)
    filters: Optional[Filters] = None


class ExpandRequest(BaseModel):
    repo: str
    refs: list[str]
    limit: int = Field(default=10, ge=1, le=50)


@app.get("/health")
def health():
    r = get_retriever()
    try:
        ok = r.store.ping()
    except Exception as exc:  # store unreachable
        raise HTTPException(status_code=503, detail=f"store unreachable: {exc}")
    return {"status": "ok", "store": r.store.name, "embedder": r.embedder.name, "store_reachable": ok}


@app.post("/index")
def index(req: IndexRequest):
    r = get_retriever()
    if not req.chunks:
        return {"indexed": 0}
    chunks = [c.model_dump() for c in req.chunks]
    embeddings = r.embedder.embed([c["text"] for c in chunks])
    r.store.upsert(req.repo, chunks, embeddings)
    r.invalidate(req.repo)
    return {"indexed": len(chunks), "embedder": r.embedder.name}


@app.post("/query")
def query(req: QueryRequest):
    r = get_retriever()
    flt = req.filters.model_dump(exclude_none=True) if req.filters else None
    return r.search(req.repo, req.query, req.source_types, req.top_k, flt)


@app.post("/expand")
def expand(req: ExpandRequest):
    r = get_retriever()
    chunks = r.store.get_by_refs(req.repo, req.refs)
    return {"chunks": chunks[: req.limit]}


@app.delete("/repos/{repo}")
def delete_repo(repo: str, source_types: Optional[str] = Query(default=None, description="comma separated")):
    r = get_retriever()
    types = [t for t in (source_types or "").split(",") if t] or None
    n = r.store.delete(repo, types)
    r.invalidate(repo)
    return {"deleted": n}


@app.get("/stats")
def stats(repo: Optional[str] = None):
    r = get_retriever()
    if repo:
        counts = r.store.counts(repo)
        return {"repo": repo, "counts": counts, "total": sum(counts.values())}
    return {"repos": r.store.repos()}
