"""Embedding backends.

`hash`      deterministic feature-hashing embedder: no model download, used by
            tests/CI and as a dependency-free fallback.
`sentence`  sentence-transformers (default all-MiniLM-L6-v2) for real runs.
"""
import hashlib
import math
import os

from .textutil import tokenize

DIM = 384
MAX_CHARS = 2000


class HashEmbedder:
    name = "hash"
    dim = DIM

    def embed(self, texts):
        return [self._one(t) for t in texts]

    def _one(self, text):
        toks = tokenize((text or "")[:MAX_CHARS])
        feats = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]
        vec = [0.0] * DIM
        for f in feats:
            h = int.from_bytes(hashlib.blake2b(f.encode(), digest_size=8).digest(), "big")
            vec[h % DIM] += 1.0 if (h >> 63) & 1 else -1.0
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]


class SentenceEmbedder:
    name = "sentence"

    def __init__(self, model_name=None):
        from sentence_transformers import SentenceTransformer  # lazy: heavy import

        self.model_name = model_name or os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        self.model = SentenceTransformer(self.model_name)
        self.dim = self.model.get_sentence_embedding_dimension()

    def embed(self, texts):
        vecs = self.model.encode(
            [(t or "")[:MAX_CHARS] for t in texts], normalize_embeddings=True, show_progress_bar=False
        )
        return [v.tolist() for v in vecs]


def get_embedder(backend=None):
    backend = (backend or os.getenv("EMBEDDING_BACKEND", "hash")).lower()
    if backend == "sentence":
        return SentenceEmbedder()
    return HashEmbedder()


def cosine(a, b):
    return sum(x * y for x, y in zip(a, b))
