#!/usr/bin/env python3
"""Re-run the pre-registered history comparison using an LLM judge's scores instead of the automatic key-fact score.

    python scripts/judge_effect.py reports/deepseek_judge.csv [--exclude it06,it35]

Judge score 0/1/2 is rescaled to 0/0.5/1 so effects are comparable to the automatic correctness (0-1). For each model:
mean(code_history) - mean(code_only) over the history questions, paired by question, with the same bootstrap 95% CI and
sign-flip permutation test as the eval service. Also the control-category difference. This tests whether the headline
conclusion depends on the automatic scoring method.
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "eval"))
from app import stats  # noqa: E402

HISTORY = {"design_rationale", "bug_origin", "change_attribution", "issue_linkage", "evolution"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("judge_csv")
    ap.add_argument("--exclude", default="")
    a = ap.parse_args()
    drop = {x for x in a.exclude.split(",") if x}
    d = {}
    for r in csv.DictReader(open(a.judge_csv, encoding="utf-8")):
        if r["item_id"] not in drop:
            d[(r["model"], r["mode"], r["item_id"])] = (r["category"], int(r["score"]) / 2)
    print(f"judge scores rescaled to 0-1; excluded: {sorted(drop) or 'none'}")
    for model in sorted({k[0] for k in d}):
        for group, cats in (("history", HISTORY), ("control", {"current_state"})):
            ids = sorted(i for (m, mo, i), (c, _) in d.items() if m == model and mo == "code_history" and c in cats)
            diffs = [d[(model, "code_history", i)][1] - d[(model, "code_only", i)][1] for i in ids]
            lo, hi = stats.bootstrap_ci(diffs)
            p = stats.permutation_pvalue(diffs)
            print(f"{model:<15} {group:<8} n={len(diffs):<3} code_history - code_only = {sum(diffs) / len(diffs):+.2f}  95% CI [{lo:+.2f}, {hi:+.2f}]  p={p:.4f}")


if __name__ == "__main__":
    main()
