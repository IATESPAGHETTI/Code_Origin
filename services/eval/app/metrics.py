"""Per-answer metrics. Everything here is deterministic and re-computable from
the stored orchestrator response, so metric definitions can evolve without
re-running the LLM."""
import re

from .refs import normalize_ref

_ABSTAIN = re.compile(r"(?i)(does not say|do not have enough|don't have enough|cannot determine|can't determine|"
                      r"not enough information|doesn't say|no evidence|i do not know|i don't know)")


def _unique_refs(sources, only_used=True):
    seen, out = set(), []
    for s in sources:
        if only_used and not s.get("used"):
            continue
        key = normalize_ref(s["ref"])
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def key_fact_score(answer, key_facts):
    """Fraction of key facts present. Each fact is a list of acceptable phrasings."""
    if not key_facts:
        return None
    low = (answer or "").lower()
    hit = sum(1 for alts in key_facts if any(a.lower() in low for a in alts))
    return hit / len(key_facts)


def abstained(resp):
    return bool(resp.get("refused")) or bool(_ABSTAIN.search(resp.get("answer") or ""))


def compute(item, resp):
    """-> flat metrics dict for one (item, model, mode) answer."""
    gold = [normalize_ref(g) for g in item.get("gold_evidence", [])]
    retrieved = _unique_refs(resp.get("sources", []), only_used=True)
    offered = _unique_refs(resp.get("sources", []), only_used=False)
    cited = [normalize_ref(c["ref"]) for c in resp.get("citations", [])]
    n_valid, n_invalid = len(cited), len(resp.get("invalid_citations", []))

    recall = precision = gold_cited = recall_offered = None
    if gold and resp.get("mode") != "no_context":
        hit = [g for g in gold if g in retrieved]
        recall = len(hit) / len(gold)
        precision = (len([r for r in retrieved if r in gold]) / len(retrieved)) if retrieved else 0.0
        recall_offered = len([g for g in gold if g in offered]) / len(gold)
        gold_cited = len([g for g in gold if g in cited]) / len(gold)

    did_abstain = abstained(resp)
    if item["expect"] == "answer":
        correctness = 0.0 if resp.get("refused") else key_fact_score(resp.get("answer"), item.get("key_facts"))
        refusal_correct = not resp.get("refused")
    else:
        correctness = 1.0 if did_abstain else 0.0
        refusal_correct = did_abstain

    grounding = resp.get("grounding")
    unsupported = grounding["unsupported_ratio"] if grounding else None
    tok = resp.get("tokens", {})
    tim = resp.get("timings", {})
    m = {
        "correctness": correctness,
        "refusal_correct": float(refusal_correct),
        "abstained": float(did_abstain),
        "refused": float(bool(resp.get("refused"))),
        "evidence_recall": recall,
        "evidence_precision": precision,
        "evidence_recall_offered": recall_offered,
        "gold_cited": gold_cited,
        "citation_validity": (n_valid / (n_valid + n_invalid)) if (n_valid + n_invalid) else None,
        "invalid_citations": float(n_invalid),
        "unsupported_ratio": unsupported,
        "hallucinated": (float(unsupported >= 0.5) if unsupported is not None else None),
        "latency_ms": tim.get("total_ms"),
        "retrieve_ms": tim.get("retrieve_ms"),
        "generate_ms": tim.get("generate_ms"),
        "tokens_in": tok.get("in"),
        "tokens_out": tok.get("out"),
    }
    m["failure"] = failure_tag(item, resp, m)
    return m


def failure_tag(item, resp, m):
    """Why a wrong answer was wrong (the table that makes findings actionable)."""
    if item["expect"] == "refuse":
        return "ok" if m["abstained"] else "under_refused"
    if resp.get("refused"):
        return "over_refused"
    if (m["correctness"] or 0) >= 0.5:
        return "ok"
    if resp.get("mode") == "no_context":
        return "no_evidence_given"
    if item.get("gold_evidence") and (m["evidence_recall"] or 0) == 0:
        return "retrieval_miss"
    if (m["unsupported_ratio"] or 0) >= 0.5:
        return "hallucinated"
    return "model_ignored_evidence"
