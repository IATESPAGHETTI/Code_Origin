import pytest
from fastapi.testclient import TestClient

from app import main
from app.bm25 import BM25
from app.embeddings import HashEmbedder, cosine
from app.hybrid import Retriever
from app.store import MemoryStore
from app.textutil import tokenize

CHUNKS = [
    {"id": "c1", "ref": "commit:abc1234", "source_type": "commit",
     "text": "Replace session cookies with JWT tokens after security issue CVE token theft",
     "metadata": {"author": "alice", "date": "2024-03-01T10:00:00+00:00", "path": ""}},
    {"id": "c2", "ref": "issue:#12", "source_type": "issue",
     "text": "Session fixation vulnerability allows account takeover in login flow",
     "metadata": {"author": "bob", "date": "2024-02-20T10:00:00+00:00"}},
    {"id": "c3", "ref": "code:src/auth.py", "source_type": "code",
     "text": "def issue_jwt(user): return jwt.encode({'sub': user.id}, SECRET)",
     "metadata": {"path": "src/auth.py"}},
    {"id": "c4", "ref": "doc:README.md", "source_type": "doc",
     "text": "CodeOrigin sample app: payments, ledger and invoice export module",
     "metadata": {"path": "README.md"}},
]


@pytest.fixture()
def retriever():
    emb = HashEmbedder()
    store = MemoryStore()
    store.upsert("r", CHUNKS, emb.embed([c["text"] for c in CHUNKS]))
    return Retriever(store, emb)


def test_tokenize_splits_identifiers_and_keeps_hex():
    toks = tokenize("calculateStudentCredits and issue_jwt fixed in a1b2c3d")
    assert {"calculate", "student", "credits", "calculatestudentcredits", "issue", "jwt", "a1b2c3d"} <= set(toks)
    assert "and" not in toks and "in" not in toks


def test_hash_embedder_is_deterministic_and_normalised():
    e = HashEmbedder()
    a, b = e.embed(["jwt token auth"])[0], e.embed(["jwt token auth"])[0]
    assert a == b
    assert abs(cosine(a, a) - 1.0) < 1e-9


def test_bm25_ranks_exact_terms_and_normaliser_zero_for_unknown():
    bm = BM25([(c["id"], c["text"]) for c in CHUNKS])
    ranked = bm.scores("session fixation")
    assert ranked[0][0] == "c2"
    assert bm.query_coverage("weather forecast tomorrow") == 0.0
    assert bm.scores("weather forecast tomorrow") == []


def test_search_finds_relevant_history_and_filters_types(retriever):
    res = retriever.search("r", "why did we replace session cookies with JWT", top_k=3)
    assert res["hits"][0]["ref"] in ("commit:abc1234", "issue:#12", "code:src/auth.py")
    assert res["top_relevance"] > 0.2
    only_code = retriever.search("r", "jwt session", types=["code", "doc"], top_k=5)
    assert {h["source_type"] for h in only_code["hits"]} <= {"code", "doc"}


def test_off_topic_query_has_low_relevance(retriever):
    res = retriever.search("r", "what is the weather in paris today", top_k=3)
    assert res["top_relevance"] < 0.2


def test_exact_commit_sha_lookup_works_via_bm25(retriever):
    res = retriever.search("r", "what changed in abc1234", top_k=3)
    assert res["hits"][0]["ref"] == "commit:abc1234"


def test_metadata_filters(retriever):
    res = retriever.search("r", "session jwt", top_k=5, flt={"author": "bob"})
    assert res["hits"] and all(h["metadata"].get("author") == "bob" for h in res["hits"])
    res = retriever.search("r", "session jwt", top_k=5, flt={"since": "2024-02-25"})
    assert all(h["metadata"].get("date", "") >= "2024-02-25" for h in res["hits"])


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("STORE_BACKEND", "memory")
    main._state.clear()
    return TestClient(main.app)


def test_api_index_query_expand_delete_stats(client):
    assert client.get("/health").json()["status"] == "ok"
    r = client.post("/index", json={"repo": "x", "chunks": CHUNKS})
    assert r.json()["indexed"] == 4
    assert client.get("/stats", params={"repo": "x"}).json()["counts"]["commit"] == 1
    q = client.post("/query", json={"repo": "x", "query": "jwt session cookies", "top_k": 3}).json()
    assert q["hits"]
    ex = client.post("/expand", json={"repo": "x", "refs": ["issue:12", "COMMIT:abc1234deadbeef"]}).json()
    assert {c["ref"] for c in ex["chunks"]} == {"issue:#12", "commit:abc1234"}
    assert client.delete("/repos/x", params={"source_types": "code,doc"}).json()["deleted"] == 2
    assert client.get("/stats", params={"repo": "x"}).json()["total"] == 2
    assert client.delete("/repos/x").json()["deleted"] == 2


def test_repo_isolation(client):
    client.post("/index", json={"repo": "a", "chunks": CHUNKS})
    q = client.post("/query", json={"repo": "b", "query": "jwt"}).json()
    assert q["hits"] == []
