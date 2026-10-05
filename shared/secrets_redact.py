"""Secret redaction (guardrail G6). Pattern based; applied at ingest time and
again on model output."""
import re

_PATTERNS = [
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S)),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    ("bearer", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{20,}")),
    (
        "assignment",
        # NAME = "quoted literal"  (>= 8 chars)   or   NAME = 20+ chars of hex/base64-ish
        # Unquoted identifiers/calls (password = hash_password(pw)) are code, not secrets.
        re.compile(
            r"""(?ix)
            (?<![A-Za-z0-9])
            ((?:[a-z0-9]+[_-])*(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|private[_-]?key))
            (\s*[:=]\s*)
            (?: (["'])([^"'\s]{8,})\3 | ([A-Za-z0-9+/=\-]{20,}) )
            """
        ),
    ),
]

PLACEHOLDER = "[REDACTED:{kind}]"


def redact(text: str):
    """Return (redacted_text, count)."""
    if not text:
        return text, 0
    count = 0
    for kind, pat in _PATTERNS:
        if kind == "assignment":

            def _sub(m, kind=kind):
                nonlocal count
                count += 1
                quote = m.group(3) or ""
                return f"{m.group(1)}{m.group(2)}{quote}{PLACEHOLDER.format(kind=kind)}{quote}"

            text = pat.sub(_sub, text)
        else:
            text, n = pat.subn(PLACEHOLDER.format(kind=kind), text)
            count += n
    return text, count
