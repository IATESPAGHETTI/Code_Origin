"""Evidence references and citation parsing.

A *ref* identifies a piece of repository evidence and is what the LLM must cite:
    commit:ab12cd3   issue:#12   pr:#5   code:src/auth.py   doc:README.md   release:v1.2
"""
import re

REF_TYPES = ("commit", "issue", "pr", "code", "doc", "release")
CITE_RE = re.compile(r"\[((?:commit|issue|pr|code|doc|release):[^\]\s]+)\]", re.IGNORECASE)
REF_RE = re.compile(r"^(commit|issue|pr|code|doc|release):(\S+)$", re.IGNORECASE)


def normalize_ref(ref: str) -> str:
    """Canonical form used for comparing refs (case/short-sha insensitive)."""
    ref = (ref or "").strip()
    m = REF_RE.match(ref)
    if not m:
        return ref.lower()
    kind, ident = m.group(1).lower(), m.group(2)
    if kind == "commit":
        return f"commit:{ident.lower()[:7]}"
    if kind in ("issue", "pr"):
        ident = ident.lstrip("#")
        return f"{kind}:#{ident}"
    return f"{kind}:{ident.lower()}"


def ref_matches(a: str, b: str) -> bool:
    return normalize_ref(a) == normalize_ref(b)


def extract_citations(text: str):
    """Return citation refs in order of appearance (duplicates removed)."""
    seen, out = set(), []
    for m in CITE_RE.finditer(text or ""):
        ref = m.group(1)
        key = normalize_ref(ref)
        if key not in seen:
            seen.add(key)
            out.append(ref)
    return out


def ref_type(ref: str) -> str:
    m = REF_RE.match((ref or "").strip())
    return m.group(1).lower() if m else ""


# chunk source types (what is stored) -> grouped by experiment condition
HISTORY_TYPES = ("commit", "diff", "issue", "pr", "review", "release")
CODE_TYPES = ("code", "doc")
