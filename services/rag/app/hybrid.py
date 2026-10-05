"""Hybrid retrieval: embedding similarity + BM25, fused with reciprocal rank
fusion (RRF). Each hit also carries a `relevance` in [0, 1] that the
orchestrator's off-topic / no-evidence guardrails threshold on."""
import threading
import time

from .bm25 import BM25

RRF_K = 60


class Retriever:
    def __init__(self, store, embedder):
        self.store = store
        self.embedder = embedder
        self._bm25 = {}  # repo -> BM25
        self._lock = threading.Lock()

    def invalidate(self, repo):
        with self._lock:
            self._bm25.pop(repo, None)

    def _bm25_for(self, repo):
        with self._lock:
            idx = self._bm25.get(repo)
        if idx is None:
            docs = self.store.all_docs(repo)
            idx = BM25([(d["id"], d["text"]) for d in docs])
            idx.by_id = {d["id"]: d for d in docs}
            with self._lock:
                self._bm25[repo] = idx
        return idx

    @staticmethod
    def _passes(chunk, flt):
        if not flt:
            return True
        m = chunk.get("metadata") or {}
        if flt.get("path_prefix") and not str(m.get("path", "")).startswith(flt["path_prefix"]):
            return False
        if flt.get("author") and flt["author"].lower() not in str(m.get("author", "")).lower():
            return False
        date = str(m.get("date", ""))[:10]
        if flt.get("since") and (not date or date < flt["since"][:10]):
            return False
        if flt.get("until") and (not date or date > flt["until"][:10]):
            return False
        return True

    def search(self, repo, query, types=None, top_k=8, flt=None):
        t0 = time.perf_counter()
        types = list(types) if types else None
        pool = max(top_k * 4, 20)
        emb = self.embedder.embed([query])[0]
        vec_hits = [(c, s) for c, s in self.store.vector_search(repo, emb, pool, types) if self._passes(c, flt)]

        bm = self._bm25_for(repo)
        norm = bm.max_score(query) or 1.0
        bm_hits = []
        for cid, score in bm.scores(query):
            c = bm.by_id[cid]
            if types and c["source_type"] not in types:
                continue
            if not self._passes(c, flt):
                continue
            bm_hits.append((c, score))
            if len(bm_hits) >= pool:
                break

        fused = {}
        for rank, (c, s) in enumerate(vec_hits, 1):
            e = fused.setdefault(c["id"], {"chunk": c, "vec": 0.0, "bm": 0.0, "rrf": 0.0})
            e["vec"] = s
            e["rrf"] += 1.0 / (RRF_K + rank)
        for rank, (c, s) in enumerate(bm_hits, 1):
            e = fused.setdefault(c["id"], {"chunk": c, "vec": 0.0, "bm": 0.0, "rrf": 0.0})
            e["bm"] = s
            e["rrf"] += 1.0 / (RRF_K + rank)

        ranked = sorted(fused.values(), key=lambda e: -e["rrf"])[:top_k]
        hits = []
        for e in ranked:
            bm_norm = min(1.0, e["bm"] / norm) if e["bm"] else 0.0
            c = e["chunk"]
            hits.append(
                {
                    "id": c["id"],
                    "ref": c["ref"],
                    "source_type": c["source_type"],
                    "text": c["text"],
                    "metadata": c.get("metadata") or {},
                    "vector_score": round(e["vec"], 4),
                    "bm25_score": round(bm_norm, 4),
                    "relevance": round(max(e["vec"], bm_norm), 4),
                    "rank_score": round(e["rrf"], 5),
                }
            )
        return {
            "hits": hits,
            "top_relevance": max((h["relevance"] for h in hits), default=0.0),
            "query_coverage": round(bm.query_coverage(query), 3),
            "took_ms": round((time.perf_counter() - t0) * 1000, 1),
            "embedder": self.embedder.name,
        }
