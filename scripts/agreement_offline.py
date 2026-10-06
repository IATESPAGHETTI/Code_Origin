#!/usr/bin/env python3
"""Agreement between the automatic correctness score and an external grader, computed offline (no services needed).

    python scripts/agreement_offline.py reports/grading_itsdangerous.csv reports/grading_itsdangerous.key.json \
        reports/itsdangerous_heldout.json --column score --grader "GPT (LLM judge)"

The CSV must contain `row_id` and the grade column (0 = wrong, 1 = partly right, 2 = right). The automatic score is mapped to
the same 0/1/2 scale with the eval service's cut-offs (<0.34 -> 0, <0.67 -> 1, else 2). Prints quadratic-weighted kappa,
Spearman correlation, exact agreement, the confusion matrix and every disagreement of 2 points or more.
Use --grader to say honestly WHO graded: an LLM judge's agreement must never be reported as human agreement.
"""
import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "eval"))
from app import stats  # noqa: E402


def bucket(x):
    return 0 if x < 0.34 else 1 if x < 0.67 else 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("key")
    ap.add_argument("results")
    ap.add_argument("--column", default="human_score")
    ap.add_argument("--grader", default="human")
    a = ap.parse_args()
    key = {k["row_id"]: k for k in json.load(open(a.key, encoding="utf-8"))}
    auto = {(r["item_id"], r["model"], r["mode"]): r["metrics"]["correctness"] for r in json.load(open(a.results, encoding="utf-8"))["results"]}
    auto_s, ext_s, rows = [], [], []
    for row in csv.DictReader(open(a.csv, encoding="utf-8")):
        raw = (row.get(a.column) or "").strip()
        if raw == "":
            continue
        k = key[int(row["row_id"])]
        x = bucket(auto[(k["item_id"], k["model"], k["mode"])])
        y = int(float(raw))
        auto_s.append(x)
        ext_s.append(y)
        rows.append((row["row_id"], k["item_id"], k["model"], k["mode"], x, y))
    n = len(rows)
    if not n:
        sys.exit(f"no graded rows found in column '{a.column}'")
    kappa = stats.weighted_kappa(auto_s, ext_s)
    rho = stats.spearman(auto_s, ext_s)
    exact = sum(1 for x, y in zip(auto_s, ext_s) if x == y) / n
    print(f"grader: {a.grader}   rows graded: {n}")
    print(f"quadratic-weighted kappa (automatic vs grader): {kappa}")
    print(f"Spearman correlation: {rho if rho is None else round(rho, 3)}   exact agreement: {exact:.0%}")
    print("confusion (rows = automatic 0/1/2, cols = grader 0/1/2):")
    for i in range(3):
        print("  ", [sum(1 for x, y in zip(auto_s, ext_s) if x == i and y == j) for j in range(3)])
    big = [r for r in rows if abs(r[4] - r[5]) >= 2]
    print(f"disagreements of 2 points: {len(big)}")
    for r in big:
        print("  row", r[0], r[1], r[2], r[3], "auto", r[4], "grader", r[5])
    print("auto mean (0-2): %.2f   grader mean: %.2f  (grader higher = automatic scoring too strict)" % (sum(auto_s) / n, sum(ext_s) / n))


if __name__ == "__main__":
    main()
