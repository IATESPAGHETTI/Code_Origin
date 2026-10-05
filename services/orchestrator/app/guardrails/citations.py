"""G3 - citation enforcement. The model is asked to cite refs; code checks each
cited ref against what was actually retrieved. Invented refs are stripped."""
import re

from ..refs import CITE_RE, normalize_ref


def validate(answer: str, allowed_refs):
    """-> (clean_answer, valid_refs, invalid_refs)"""
    allowed = {normalize_ref(r): r for r in allowed_refs}
    valid, invalid, seen = [], [], set()

    def _sub(m):
        ref = m.group(1)
        key = normalize_ref(ref)
        if key in allowed:
            if key not in seen:
                seen.add(key)
                valid.append(allowed[key])
            return f"[{allowed[key]}]"
        if ref not in invalid:
            invalid.append(ref)
        return ""

    clean = CITE_RE.sub(_sub, answer or "")
    clean = re.sub(r"[ \t]{2,}", " ", clean)
    clean = re.sub(r"\s+([.,;:!?])", r"\1", clean).strip()
    return clean, valid, invalid
