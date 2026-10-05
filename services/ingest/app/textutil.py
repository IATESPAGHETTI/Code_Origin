"""Tokenisation shared by retrieval (BM25), grounding checks and evaluation.

Source of truth lives in /shared; scripts/sync_shared.py copies it into each
service so every container stays self-contained.
"""
import re

STOPWORDS = frozenset(
    """a about above after again all also am an and any are as at be because been
    before being below between both but by can could did do does doing down during
    each few for from further had has have having he her here hers him his how i if
    in into is it its itself just me more most my no nor not of off on once only or
    other our out over own same she should so some such than that the their theirs
    them then there these they this those through to too under until up very was we
    were what when where which while who whom why will with would you your yours
    please tell explain""".split()
)

_WORD = re.compile(r"[A-Za-z0-9_]+")
_CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")
_HEX = re.compile(r"^[0-9a-f]{7,40}$")


def _parts(word: str):
    pieces = []
    for chunk in word.split("_"):
        if not chunk:
            continue
        pieces.extend(m.group(0).lower() for m in _CAMEL.finditer(chunk))
    return pieces


def tokenize(text: str, keep_stop: bool = False):
    """Lower-cased tokens; identifiers are split (snake_case/camelCase) while
    the whole identifier and commit-like hex strings are kept too."""
    out = []
    for m in _WORD.finditer(text or ""):
        word = m.group(0)
        low = word.lower()
        if _HEX.match(low) and any(c.isdigit() for c in low) and any(c.isalpha() for c in low):
            out.append(low[:7])
            continue
        parts = _parts(word)
        if len(parts) > 1:
            out.append(low)
        out.extend(parts)
    if keep_stop:
        return [t for t in out if len(t) >= 2]
    return [t for t in out if len(t) >= 2 and t not in STOPWORDS]


def content_tokens(text: str):
    """Distinct content tokens (no stopwords, length >= 3)."""
    return {t for t in tokenize(text) if len(t) >= 3}


_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def split_sentences(text: str):
    return [s.strip() for s in _SENT_SPLIT.split(text or "") if s and s.strip()]
