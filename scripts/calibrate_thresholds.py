#!/usr/bin/env python3
"""Pick the G1 (off-topic) and G2 (insufficient history) thresholds from data.

Uses the DEV split only, so the held-out TEST split stays untouched for the
final evaluation. Thresholds depend on the embedding backend, so re-run this
whenever EMBEDDING_BACKEND / EMBEDDING_MODEL changes.

    python scripts/calibrate_thresholds.py --orchestrator http://localhost:8204 \
        --dataset services/eval/datasets/demo.json [--split dev]

Prints suggested OFF_TOPIC_MIN_RELEVANCE and HISTORY_MIN_RELEVANCE.
"""
import argparse
import json
import sys

import httpx


def best_threshold(positives, negatives):
    """Threshold t (flag when score < t) maximising balanced accuracy where
    `negatives` should be flagged and `positives` should pass. Ties prefer the
    larger margin (midpoint between neighbouring scores)."""
    cands = sorted(set(positives) | set(negatives))
    if not cands:
        return None
    points = [cands[0] - 0.01] + [(a + b) / 2 for a, b in zip(cands, cands[1:])] + [cands[-1] + 0.01]
    best = None
    for t in points:
        tpr = sum(p >= t for p in positives) / len(positives) if positives else 1.0   # kept
        tnr = sum(n < t for n in negatives) / len(negatives) if negatives else 1.0    # flagged
        score = (tpr + tnr) / 2
        if best is None or score > best[0] + 1e-9:
            best = (score, t, tpr, tnr)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--orchestrator", default="http://localhost:8204")
    ap.add_argument("--dataset", default="services/eval/datasets/demo.json")
    ap.add_argument("--split", default="dev")
    args = ap.parse_args()

    data = json.load(open(args.dataset, encoding="utf-8"))
    rows = []
    with httpx.Client(timeout=120) as c:
        for it in data["items"]:
            if it["split"] != args.split or it["category"] == "adversarial":  # adversarial is G10's job
                continue
            r = c.post(f"{args.orchestrator}/retrieve", json={"repo": data["repo"], "question": it["question"]})
            r.raise_for_status()
            rows.append({**it, **r.json()})

    # only answerable questions must pass G1; unanswerable ones may legitimately be stopped by either gate
    on_topic = [r["top_relevance"] for r in rows if r["expect"] == "answer"]
    off_topic = [r["top_relevance"] for r in rows if r["category"] == "off_topic"]
    print(f"G1 off-topic: {len(on_topic)} on-topic vs {len(off_topic)} off-topic questions ({args.split} split)")
    print(f"   on-topic  top relevance: min={min(on_topic):.3f}  median={sorted(on_topic)[len(on_topic)//2]:.3f}")
    print(f"   off-topic top relevance: max={max(off_topic):.3f}")
    g1 = best_threshold(on_topic, off_topic)
    print(f"   -> OFF_TOPIC_MIN_RELEVANCE={g1[1]:.3f}  (keeps {g1[2]:.0%} of on-topic, blocks {g1[3]:.0%} of off-topic)")

    hist_ok = [r["top_history_relevance"] for r in rows if r["history_intent"] and r["expect"] == "answer"]
    hist_no = [r["top_history_relevance"] for r in rows if r["history_intent"] and r["category"] == "unanswerable"]
    if hist_ok and hist_no:
        print(f"G2 insufficient history: {len(hist_ok)} answerable vs {len(hist_no)} unanswerable history questions")
        print(f"   answerable   top history relevance: min={min(hist_ok):.3f}")
        print(f"   unanswerable top history relevance: max={max(hist_no):.3f}")
        g2 = best_threshold(hist_ok, hist_no)
        print(f"   -> HISTORY_MIN_RELEVANCE={g2[1]:.3f}  (keeps {g2[2]:.0%} of answerable, refuses {g2[3]:.0%} of unanswerable)")
    else:
        print("G2: not enough history-intent questions to calibrate")
    print("\nSet these in .env (they depend on the embedding backend).")


if __name__ == "__main__":
    sys.exit(main())
