"""G4 - claim grounding. Each answer sentence must be lexically supported by
the evidence the model was given; unsupported sentences are flagged and counted
as hallucination. Lexical on purpose: cheap, deterministic, explainable."""
import re

from ..refs import CITE_RE
from ..textutil import content_tokens, split_sentences

_ABSTAIN = re.compile(r"(?i)(does not say|do not have enough|don't have enough|cannot determine|can't determine|not enough information|no evidence)")
MIN_TOKENS = 4


def check(answer: str, evidence_texts, min_support: float):
    ev_tokens = [content_tokens(t) for t in evidence_texts]
    rows = []
    for sent in split_sentences(answer):
        plain = CITE_RE.sub("", sent).strip()
        toks = content_tokens(plain)
        if _ABSTAIN.search(plain):
            rows.append({"text": sent, "support": 1.0, "supported": True, "checked": False, "abstention": True})
            continue
        if len(toks) < MIN_TOKENS:
            rows.append({"text": sent, "support": None, "supported": True, "checked": False, "abstention": False})
            continue
        support = max((len(toks & et) / len(toks) for et in ev_tokens), default=0.0)
        rows.append({"text": sent, "support": round(support, 3), "supported": support >= min_support,
                     "checked": True, "abstention": False})
    checked = [r for r in rows if r["checked"]]
    unsupported = [r for r in checked if not r["supported"]]
    return {
        "sentences": rows,
        "checked": len(checked),
        "unsupported": len(unsupported),
        "unsupported_ratio": round(len(unsupported) / len(checked), 3) if checked else 0.0,
    }
