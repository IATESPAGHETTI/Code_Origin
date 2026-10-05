"""Small dependency-free Okapi BM25 used for the keyword half of hybrid search.

Keyword matching matters for history questions: commit SHAs, issue numbers and
identifiers are exact strings that embeddings blur.
"""
import math
from collections import Counter

from .textutil import tokenize


class BM25:
    def __init__(self, docs, k1=1.5, b=0.75):
        """docs: list of (doc_id, text)."""
        self.k1, self.b = k1, b
        self.ids = [d[0] for d in docs]
        self.tfs = [Counter(tokenize(d[1])) for d in docs]
        self.lens = [sum(tf.values()) for tf in self.tfs]
        self.n = len(docs)
        self.avgdl = (sum(self.lens) / self.n) if self.n else 0.0
        df = Counter()
        for tf in self.tfs:
            df.update(tf.keys())
        self.idf = {t: math.log(1 + (self.n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def _qterms(self, query):
        return [t for t in dict.fromkeys(tokenize(query)) if t in self.idf]

    def max_score(self, query):
        """Normaliser: total idf mass of the query's terms (terms the corpus has
        never seen count at the maximum idf). A document matching every term
        once scores about this value, so score/max_score lands in ~[0, 1] and
        goes to 0 for queries about things the corpus does not contain."""
        terms = list(dict.fromkeys(tokenize(query)))
        max_idf = math.log(1 + (self.n + 0.5) / 0.5) if self.n else 0.0
        return sum(self.idf.get(t, max_idf) for t in terms)

    def scores(self, query):
        terms = self._qterms(query)
        if not terms or not self.n:
            return []
        out = []
        for i, tf in enumerate(self.tfs):
            s = 0.0
            dl = self.lens[i] or 1
            for t in terms:
                f = tf.get(t, 0)
                if not f:
                    continue
                denom = f + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1))
                s += self.idf[t] * f * (self.k1 + 1) / denom
            if s > 0:
                out.append((self.ids[i], s))
        out.sort(key=lambda x: -x[1])
        return out

    def query_coverage(self, query):
        """Fraction of the query's content terms that exist anywhere in the corpus."""
        all_terms = list(dict.fromkeys(tokenize(query)))
        if not all_terms:
            return 0.0
        return sum(1 for t in all_terms if t in self.idf) / len(all_terms)
