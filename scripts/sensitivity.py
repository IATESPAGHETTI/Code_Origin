#!/usr/bin/env python3
"""Re-compute the history effect (code_history minus code_only) with some items excluded, from a finished run's results JSON.

    python scripts/sensitivity.py reports/itsdangerous_heldout.json --exclude it06,it35

Uses the same statistics as the eval service (paired bootstrap 95% CI, sign-flip permutation test), applied to per-item
correctness. Used to show that conclusions do not depend on items an independent review flagged as weak.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "eval"))
from app import stats  # noqa: E402

HISTORY = {"design_rationale", "bug_origin", "change_attribution", "issue_linkage", "evolution"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--exclude", default="")
    a = ap.parse_args()
    drop = {x for x in a.exclude.split(",") if x}
    rows = json.load(open(a.results, encoding="utf-8"))["results"]
    by = {}
    for r in rows:
        if r["item_id"] in drop or r["error"]:
            continue
        by[(r["model"], r["mode"], r["item_id"])] = (r["category"], r["metrics"]["correctness"])
    print(f"excluded: {sorted(drop) or 'none'}")
    for model in sorted({k[0] for k in by}):
        ids = sorted(i for (m, mo, i), (c, _) in by.items() if m == model and mo == "code_history" and c in HISTORY)
        diffs = [by[(model, "code_history", i)][1] - by[(model, "code_only", i)][1] for i in ids]
        lo, hi = stats.bootstrap_ci(diffs)
        p = stats.permutation_pvalue(diffs)
        print(f"{model:<16} n={len(diffs):<3} mean diff {sum(diffs) / len(diffs):+.2f}  95% CI [{lo:+.2f}, {hi:+.2f}]  p={p:.4f}")


if __name__ == "__main__":
    main()
