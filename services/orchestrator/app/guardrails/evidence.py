"""G1 (off-topic) and G2 (insufficient history) - decided from retrieval scores,
never by asking the model to refuse (small models cannot be trusted to)."""
import re

from ..refs import HISTORY_TYPES

OFF_TOPIC_REFUSAL = (
    "I can only answer questions about this repository's code, documentation and development history. "
    "That question doesn't relate to the repository, so I can't answer it."
)
NO_HISTORY_REFUSAL = (
    "The repository history I have access to doesn't say why. I found related code but no commit, issue or "
    "pull request that explains the reason, so I won't guess."
)
UNSAFE_REFUSAL = "I can't help with that request. I only explain a repository's code and history from evidence."

_HISTORY_INTENT = re.compile(
    r"(?i)\b(why|reason|rationale|because|motivat\w*|introduc\w*|origin\w*|history|histor\w+|previous\w*|"
    r"used to|replac\w*|remov\w*|revert\w*|decid\w*|evolv\w*|caused?|led to|when (was|did|were)|"
    r"who (changed|added|wrote|introduced|removed|fixed|reverted)|since when|how has|changed|chose|choose)\b"
)


def history_intent(question: str) -> bool:
    return bool(_HISTORY_INTENT.search(question or ""))


def off_topic(top_relevance: float, threshold: float):
    """G1: -> (triggered, detail)"""
    return top_relevance < threshold, {"top_relevance": round(top_relevance, 4), "threshold": threshold}


def insufficient_history(hits, question: str, threshold: float):
    """G2: only for history-seeking questions in code_history mode."""
    if not history_intent(question):
        return False, {"history_intent": False}
    good = [h for h in hits if h["source_type"] in HISTORY_TYPES and h["relevance"] >= threshold]
    return not good, {"history_intent": True, "history_hits": len(good), "threshold": threshold}
