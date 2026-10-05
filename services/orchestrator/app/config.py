import os


def _f(name, default):
    return float(os.getenv(name, default))


def _i(name, default):
    return int(os.getenv(name, default))


def settings():
    """Read at call time so tests / ops can change thresholds without a rebuild."""
    return {
        "off_topic_min_relevance": _f("OFF_TOPIC_MIN_RELEVANCE", 0.25),
        "history_min_relevance": _f("HISTORY_MIN_RELEVANCE", 0.30),
        "grounding_min_support": _f("GROUNDING_MIN_SUPPORT", 0.50),
        "context_char_budget": _i("CONTEXT_CHAR_BUDGET", 6000),
        "chunk_char_limit": _i("CHUNK_CHAR_LIMIT", 1200),
        "default_top_k": _i("DEFAULT_TOP_K", 8),
        "expand_k": _i("EXPAND_K", 4),
        "max_answer_tokens": _i("MAX_ANSWER_TOKENS", 300),
        "default_model": os.getenv("LLM_MODEL", "llama2"),
    }
