#!/usr/bin/env python3
"""Grade every stored answer of a finished run with an external LLM judge (DeepSeek API by default), blind to model and mode.

    # the key stays in YOUR shell; this script only reads the environment variable and never prints it
    #   PowerShell:  $env:DEEPSEEK_API_KEY = "sk-..."
    #   bash:        export DEEPSEEK_API_KEY=sk-...
    python scripts/llm_judge.py reports/itsdangerous_heldout.json services/eval/datasets/itsdangerous.json \
        --out reports/deepseek_judge.csv [--model deepseek-chat] [--limit 10]

The judge sees only: question, gold answer, and the system's answer (no model name, no mode, no retrieved evidence), and scores
0 = wrong, 1 = partly right, 2 = right (same rubric as reports/GPT_GRADING_PROMPT.md). Temperature 0. It then prints the
agreement between the automatic key-fact score and the judge over every graded answer (quadratic-weighted kappa, Spearman,
exact agreement), and the mean judge score per model and mode. An LLM judge's agreement must be reported as "LLM judge", never
as human agreement. Data sent to the API: public repository text and model answers only.
"""
import argparse
import csv
import json
import os
import re
import sys
import time

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "eval"))
from app import stats  # noqa: E402

SYSTEM = """You grade answers produced by an AI system that explains why a Python library was built a certain way.
You get a question, a gold_answer (the reference, written from the project's real GitHub issues and pull requests), and the system's answer.
Score with exactly one of: 2 = right (states the key facts of the gold answer, no contradiction or meaning-changing invention);
1 = partly right (some key facts, but misses an important one or mixes a correct fact with a wrong or invented one);
0 = wrong (misses the key facts, contradicts the gold answer, or invents an answer).
If gold_answer is empty the question cannot be answered from the repository (or is off-topic or an attack): score 2 only if the answer clearly refuses or says the information is not available without inventing details; 0 if it invents an answer; 1 if it says the information is missing but then speculates.
Judge by meaning, not wording. Ignore citation formatting, length and style. Do not reward claims the gold answer does not support. Be strict and consistent.
Reply with JSON only: {"score": 0|1|2, "reason": "<under 20 words>"}"""


def bucket(x):
    return 0 if x < 0.34 else 1 if x < 0.67 else 2


def judge(client, base, key, model, question, gold, answer):
    body = {"model": model, "temperature": 0, "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": json.dumps({"question": question, "gold_answer": gold, "answer": answer}, ensure_ascii=False)}]}
    for attempt in range(4):
        r = client.post(f"{base}/chat/completions", headers={"Authorization": f"Bearer {key}"}, json=body)
        if r.status_code in (429, 500, 502, 503):
            time.sleep(2 ** attempt)
            continue
        if r.status_code >= 400:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
        txt = r.json()["choices"][0]["message"]["content"]
        m = re.search(r"\{.*\}", txt, re.S)
        d = json.loads(m.group(0)) if m else {}
        s = int(d.get("score"))
        if s in (0, 1, 2):
            return s, str(d.get("reason", ""))[:200]
        break
    raise RuntimeError("judge returned no usable score")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("dataset")
    ap.add_argument("--out", default="reports/deepseek_judge.csv")
    ap.add_argument("--model", default="deepseek-chat")
    ap.add_argument("--base", default="https://api.deepseek.com")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    key = (os.environ.get("DEEPSEEK_API_KEY") or "").strip().strip("\"'")
    if not key:
        sys.exit("set DEEPSEEK_API_KEY in your shell first (never paste it into chat or commit it)")
    items = {i["id"]: i for i in json.load(open(a.dataset, encoding="utf-8"))["items"]}
    rows = [r for r in json.load(open(a.results, encoding="utf-8"))["results"] if r.get("response") and not r.get("error")]
    if a.limit:
        rows = rows[: a.limit]
    out, auto_s, jud_s, by, fails = [], [], [], {}, 0
    with httpx.Client(timeout=90) as client:
        for n, r in enumerate(rows, 1):
            it = items[r["item_id"]]
            ans = (r["response"].get("answer") or "").strip() or "(no answer)"
            try:
                score, reason = judge(client, a.base, key, a.model, it["question"], it.get("gold_answer", ""), ans)
            except Exception as e:  # keep going, but stop early if the API keeps failing
                msg = str(e).replace(key, "<key redacted>")[:200]
                print(f"  {r['item_id']} {r['model']} {r['mode']}: judge failed: {type(e).__name__}: {msg}", file=sys.stderr)
                fails += 1
                if fails >= 3 and not out:
                    sys.exit("first 3 calls all failed; fix the error above (key, balance, network) and retry")
                continue
            out.append({"item_id": r["item_id"], "model": r["model"], "mode": r["mode"], "category": r["category"], "auto": bucket(r["metrics"]["correctness"]), "score": score, "reason": reason})
            auto_s.append(bucket(r["metrics"]["correctness"]))
            jud_s.append(score)
            by.setdefault((r["model"], r["mode"]), []).append(score)
            if n % 20 == 0:
                print(f"  graded {n}/{len(rows)}", flush=True)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["item_id", "model", "mode", "category", "auto", "score", "reason"])
        w.writeheader()
        w.writerows(out)
    n = len(out)
    if not n:
        sys.exit("nothing was graded")
    rho = stats.spearman(auto_s, jud_s)
    print(f"\njudge: {a.model}   answers graded: {n}")
    print(f"quadratic-weighted kappa (automatic vs judge): {stats.weighted_kappa(auto_s, jud_s)}")
    print(f"Spearman: {None if rho is None else round(rho, 3)}   exact agreement: {sum(x == y for x, y in zip(auto_s, jud_s)) / n:.0%}")
    print("confusion (rows = automatic 0/1/2, cols = judge 0/1/2):")
    for i in range(3):
        print("  ", [sum(1 for x, y in zip(auto_s, jud_s) if x == i and y == j) for j in range(3)])
    print("\nmean judge score (0-2) per model and mode:")
    for (m, mo), v in sorted(by.items()):
        print(f"  {m:<15} {mo:<13} {sum(v) / len(v):.2f}  (n={len(v)})")
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
