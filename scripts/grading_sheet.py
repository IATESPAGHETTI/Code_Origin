#!/usr/bin/env python3
"""Human grading workflow for an evaluation run (feeds jury/automatic-score agreement).

    python scripts/grading_sheet.py export --run 1 --n 60 --out reports/grading_run1.csv [--seed 7]
    # a human fills the `human_score` column: 0 = wrong, 1 = partly right, 2 = right (see docs/EVALUATION.md)
    python scripts/grading_sheet.py import --run 1 --file reports/grading_run1.csv
    python scripts/grading_sheet.py kappa  --run 1       # prints weighted kappa for jury and automatic score

The export is BLIND: the mode and model columns are withheld (kept in a separate key file) and rows are
shuffled, so the grader cannot favour code_history. Rows are a stratified random sample over categories.
"""
import argparse
import csv
import json
import random
import sys

import httpx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["export", "import", "kappa"])
    ap.add_argument("--gateway", default="http://localhost:8200")
    ap.add_argument("--run", type=int, required=True)
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=None)
    ap.add_argument("--file", default=None)
    ap.add_argument("--api-key", default=None)
    a = ap.parse_args()
    headers = {"X-API-Key": a.api_key} if a.api_key else {}
    with httpx.Client(base_url=a.gateway, timeout=60, headers=headers) as c:
        if a.cmd == "export":
            rows = [r for r in c.get(f"/api/eval/runs/{a.run}/worksheet").json()["rows"] if r["category"] not in ("off_topic", "adversarial")]
            rng = random.Random(a.seed)
            by = {}
            for r in rows:
                by.setdefault(r["category"], []).append(r)
            for v in by.values():
                rng.shuffle(v)
            sample, i = [], 0
            while len(sample) < min(a.n, len(rows)):  # round-robin across categories
                for cat in sorted(by):
                    if i < len(by[cat]) and len(sample) < a.n:
                        sample.append(by[cat][i])
                i += 1
            rng.shuffle(sample)
            out = a.out or f"reports/grading_run{a.run}.csv"
            with open(out, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["row_id", "category", "question", "gold_answer", "answer", "human_score"])
                for n, r in enumerate(sample, 1):
                    w.writerow([n, r["category"], r["question"], r["gold_answer"], r["answer"], ""])
            json.dump([{"row_id": n, "item_id": r["item_id"], "model": r["model"], "mode": r["mode"]} for n, r in enumerate(sample, 1)],
                      open(out.replace(".csv", ".key.json"), "w"), indent=1)
            print(f"{len(sample)} rows -> {out} (blind); key -> {out.replace('.csv', '.key.json')}")
        elif a.cmd == "import":
            key = {k["row_id"]: k for k in json.load(open(a.file.replace(".csv", ".key.json")))}
            grades = []
            for row in csv.DictReader(open(a.file, encoding="utf-8")):
                if row["human_score"].strip() != "":
                    k = key[int(row["row_id"])]
                    grades.append({"item_id": k["item_id"], "model": k["model"], "mode": k["mode"], "score": int(row["human_score"])})
            r = c.post(f"/api/eval/runs/{a.run}/human-grades", json=grades)
            r.raise_for_status()
            print(f"saved {r.json()['saved']} human grades")
        else:
            print(json.dumps(c.get(f"/api/eval/runs/{a.run}/calibration").json(), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
