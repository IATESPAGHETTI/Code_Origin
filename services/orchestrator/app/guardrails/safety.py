"""G10 - request safety and prompt-override attempts in the *question*.

The system never executes repository code and never reveals secrets, so
requests to do either are refused before any retrieval or LLM call.
Patterns are deliberately narrow: "why was the API key moved to the
environment?" and "why did tokens get a 15 minute TTL?" are legitimate.
"""
import re

_UNSAFE = [
    # asking for secret *values* ("print the live API key")
    ("secret_exfiltration", re.compile(
        r"(?i)\b(show|print|reveal|leak|dump|display|expose)\b[^.?!]{0,25}\b(password|passwd|api[ _-]?key|secret|private key|credentials?)s?\b")),
    ("secret_exfiltration", re.compile(
        r"(?i)\bwhat(?:'s| is| was) the (?:actual |real |live |full |exact )?(?:password|api[ _-]?key|secret|private key)\b"
        r"(?! (?:rotation|policy|handling|storage|management))")),
    # imperative requests to execute things; "why does the script run nightly" is fine
    ("code_execution", re.compile(r"(?i)^\s*(?:please\s+)?(?:(?:can|could|would) you\s+)?(?:run|execute|exec|eval)\b")),
    ("shell_command", re.compile(r"(?i)(\brm\s+-rf\b|\bcurl\s+https?://|\bwget\s+https?://|\bpowershell\b|\bcmd\.exe\b|\bsudo\s)")),
    ("prompt_override", re.compile(
        r"(?i)\b(ignore|disregard|forget|override)\b.{0,30}\b(previous|prior|above|all|system|your)\b.{0,20}\b(instructions?|prompt|rules?|guidelines?)\b")),
    ("prompt_leak", re.compile(
        r"(?i)\b(reveal|print|show|repeat|output)\b.{0,30}\b(system prompt|your instructions|hidden prompt)\b")),
]


def check(question: str):
    """-> (is_unsafe, category or None)"""
    for name, pat in _UNSAFE:
        if pat.search(question or ""):
            return True, name
    return False, None
