"""G5 - prompt-injection defence for retrieved evidence.

Commit messages, issue bodies, PR comments and code comments are written by
arbitrary third parties, so they are untrusted *data*. Before they reach the
model we (1) neutralise instruction-like text, (2) prevent breaking out of the
evidence wrapper, and (3) the system prompt states that evidence is data.
"""
import re

REMOVED = "[removed: instruction-like text]"

_PATTERNS = [
    re.compile(r"(?i)\b(ignore|disregard|forget|override|bypass)\b[^.\n]{0,40}\b(previous|prior|above|earlier|all|any|the|your|system)\b[^.\n]{0,30}\b(instructions?|prompts?|rules?|guidelines?|context|constraints?)\b[^.\n]*"),
    re.compile(r"(?i)\byou are (now|no longer)\b[^.\n]*"),
    re.compile(r"(?i)\b(new|updated|real) (system )?(instructions?|prompt|task)\s*:[^\n]*"),
    re.compile(r"(?i)\b(reveal|print|show|output|repeat)\b[^.\n]{0,30}\b(system prompt|your instructions|hidden prompt)\b[^.\n]*"),
    re.compile(r"(?im)^\s*(system|assistant|developer)\s*:\s*[^\n]*"),
    re.compile(r"<\|[^|>]{1,30}\|>"),
    re.compile(r"(?i)\[/?(INST|SYS)\]|<</?SYS>>"),
    re.compile(r"(?im)^#{2,}\s*(system|instructions?)\b[^\n]*"),
    re.compile(r"(?i)\bdo not (cite|mention|follow|use)\b[^.\n]*"),
]
_WRAPPER = re.compile(r"(?i)</?\s*evidence\b[^>]*>")


def sanitize(text: str):
    """-> (clean_text, number_of_neutralised_spans)"""
    flagged = 0
    for pat in _PATTERNS:
        text, n = pat.subn(REMOVED, text)
        flagged += n
    text, n = _WRAPPER.subn("[evidence-tag removed]", text)
    return text, flagged + n
