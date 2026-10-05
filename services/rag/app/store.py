"""Vector stores: in-memory (tests / small runs) and ChromaDB (compose stack).

A chunk is a dict: {id, ref, source_type, text, metadata}. `metadata` carries
path/author/date/url/title/links/... and is returned verbatim on retrieval.
"""
import hashlib
import json
import re
from collections import defaultdict

from .embeddings import cosine
from .refs import normalize_ref


class MemoryStore:
    name = "memory"

    def __init__(self):
        self._data = defaultdict(dict)  # repo -> {chunk_id: (chunk, embedding)}

    def upsert(self, repo, chunks, embeddings):
        for c, e in zip(chunks, embeddings):
            self._data[repo][c["id"]] = (c, e)

    def delete(self, repo, source_types=None):
        if repo not in self._data:
            return 0
        if not source_types:
            n = len(self._data[repo])
            del self._data[repo]
            return n
        doomed = [i for i, (c, _) in self._data[repo].items() if c["source_type"] in source_types]
        for i in doomed:
            del self._data[repo][i]
        return len(doomed)

    def counts(self, repo):
        out = defaultdict(int)
        for c, _ in self._data.get(repo, {}).values():
            out[c["source_type"]] += 1
        return dict(out)

    def repos(self):
        return [r for r, d in self._data.items() if d]

    def all_docs(self, repo, types=None):
        return [c for c, _ in self._data.get(repo, {}).values() if not types or c["source_type"] in types]

    def vector_search(self, repo, emb, k, types=None):
        scored = []
        for c, e in self._data.get(repo, {}).values():
            if types and c["source_type"] not in types:
                continue
            scored.append((c, max(0.0, cosine(emb, e))))
        scored.sort(key=lambda x: -x[1])
        return scored[:k]

    def get_by_refs(self, repo, refs):
        wanted = {normalize_ref(r) for r in refs}
        return [c for c, _ in self._data.get(repo, {}).values() if normalize_ref(c["ref"]) in wanted]

    def ping(self):
        return True


def _collection_name(repo):
    clean = re.sub(r"[^A-Za-z0-9._-]", "_", repo).strip("._-") or "repo"
    name = f"co_{clean}"
    if len(name) > 60:
        name = f"co_{clean[:40]}_{hashlib.sha1(repo.encode()).hexdigest()[:10]}"
    return name


class ChromaStore:
    name = "chroma"
    BATCH = 256

    def __init__(self, host=None, port=8000):
        import chromadb

        self.client = chromadb.HttpClient(host=host, port=port) if host else chromadb.EphemeralClient()

    def _col(self, repo, create=True):
        name = _collection_name(repo)
        if create:
            return self.client.get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})
        try:
            return self.client.get_collection(name=name)
        except Exception:
            return None

    @staticmethod
    def _flat_meta(c):
        m = c.get("metadata") or {}
        return {
            "ref": c["ref"],
            "ref_norm": normalize_ref(c["ref"]),
            "source_type": c["source_type"],
            "meta_json": json.dumps(m, default=str),
        }

    @staticmethod
    def _unflat(cid, doc, meta):
        return {
            "id": cid,
            "ref": meta.get("ref", ""),
            "source_type": meta.get("source_type", ""),
            "text": doc,
            "metadata": json.loads(meta.get("meta_json") or "{}"),
        }

    def upsert(self, repo, chunks, embeddings):
        col = self._col(repo)
        for i in range(0, len(chunks), self.BATCH):
            part = chunks[i : i + self.BATCH]
            col.upsert(
                ids=[c["id"] for c in part],
                documents=[c["text"] for c in part],
                embeddings=embeddings[i : i + self.BATCH],
                metadatas=[self._flat_meta(c) for c in part],
            )

    def delete(self, repo, source_types=None):
        col = self._col(repo, create=False)
        if col is None:
            return 0
        before = col.count()
        if not source_types:
            self.client.delete_collection(_collection_name(repo))
            return before
        col.delete(where={"source_type": {"$in": list(source_types)}})
        return before - col.count()

    def _get_all(self, col, where=None):
        out, offset, page = [], 0, 500
        while True:
            res = col.get(where=where, include=["documents", "metadatas"], limit=page, offset=offset)
            ids = res["ids"]
            if not ids:
                break
            for cid, doc, meta in zip(ids, res["documents"], res["metadatas"]):
                out.append(self._unflat(cid, doc, meta))
            if len(ids) < page:
                break
            offset += page
        return out

    def counts(self, repo):
        col = self._col(repo, create=False)
        out = defaultdict(int)
        if col is None:
            return {}
        offset, page = 0, 1000
        while True:
            res = col.get(include=["metadatas"], limit=page, offset=offset)
            for meta in res["metadatas"]:
                out[meta.get("source_type", "")] += 1
            if len(res["ids"]) < page:
                break
            offset += page
        return dict(out)

    def repos(self):
        return [c.name[3:] for c in self.client.list_collections() if c.name.startswith("co_")]

    def all_docs(self, repo, types=None):
        col = self._col(repo, create=False)
        if col is None:
            return []
        where = {"source_type": {"$in": list(types)}} if types else None
        return self._get_all(col, where)

    def vector_search(self, repo, emb, k, types=None):
        col = self._col(repo, create=False)
        if col is None or col.count() == 0:
            return []
        where = {"source_type": {"$in": list(types)}} if types else None
        res = col.query(
            query_embeddings=[emb],
            n_results=min(k, col.count()),
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        out = []
        for cid, doc, meta, dist in zip(res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]):
            out.append((self._unflat(cid, doc, meta), max(0.0, 1.0 - dist)))
        return out

    def get_by_refs(self, repo, refs):
        col = self._col(repo, create=False)
        if col is None:
            return []
        wanted = list({normalize_ref(r) for r in refs})
        if not wanted:
            return []
        return self._get_all(col, {"ref_norm": {"$in": wanted}})

    def ping(self):
        self.client.heartbeat()
        return True
