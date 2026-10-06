#!/usr/bin/env python3
"""Which model is best for which kind of task? Computed from a finished run (and optionally the LLM-judge scores).

    python scripts/task_analysis.py reports/itsdangerous_heldout.json [--judge reports/deepseek_judge.csv] [--mode code_history]

Maps the dataset's question categories onto task types and reports, per model: correctness (automatic and, if given, judge),
hallucination rate, latency and tokens. Task mapping (what each task means in this project):
  Explanation              -> design_rationale  (why was it built this way)
  Bug analysis             -> bug_origin        (what bug / what broke / why)
  Dependency understanding -> issue_linkage     (which issue a PR fixed; links between issues, PRs, commits)
  Attribution              -> change_attribution (who did it)
  Code retrieval           -> current_state     (look up a fact in the current code)
  RAG (whole pipeline)     -> all answerable categories, with and without history, plus the oracle gap
  Code generation, refactoring, test-pass rate: NOT evaluated (the dataset has no such questions).
With n of 2 to 10 questions per task the differences are small; a 'tie' is declared when the gap is under 0.10.
"""
import argparse
import csv
import json
import statistics as st

TASKS = [("Explanation", {"design_rationale"}), ("Bug analysis", {"bug_origin"}), ("Dependency understanding", {"issue_linkage"}),
         ("Attribution", {"change_attribution"}), ("Code retrieval (current code)", {"current_state"})]
ANSWERABLE = {"design_rationale", "bug_origin", "issue_linkage", "change_attribution", "evolution", "current_state"}


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--judge", default=None)
    ap.add_argument("--mode", default="code_history")
    a = ap.parse_args()
    rows = [r for r in json.load(open(a.results, encoding="utf-8"))["results"] if r.get("response") and not r.get("error")]
    models = sorted({r["model"] for r in rows})
    judge = {}
    if a.judge:
        for r in csv.DictReader(open(a.judge, encoding="utf-8")):
            judge[(r["item_id"], r["model"], r["mode"])] = int(r["score"]) / 2

    def pick(model, mode, cats):
        return [r for r in rows if r["model"] == model and r["mode"] == mode and r["category"] in cats]

    print(f"mode = {a.mode}\n")
    print("Per task: correctness (automatic | judge), n questions")
    for name, cats in TASKS:
        cells, vals = [], {}
        for m in models:
            rs = pick(m, a.mode, cats)
            auto = mean([r["metrics"]["correctness"] for r in rs])
            jd = mean([judge[(r["item_id"], m, a.mode)] for r in rs if (r["item_id"], m, a.mode) in judge]) if judge else float("nan")
            vals[m] = (auto, jd)
            cells.append(f"{m} {auto:.2f}" + (f"|{jd:.2f}" if judge else ""))
        n = len(pick(models[0], a.mode, cats))
        best = max(vals, key=lambda k: vals[k][0]); gap = vals[best][0] - sorted(v[0] for v in vals.values())[-2]
        verdict = best if gap >= 0.10 else "tie (" + ", ".join(k for k in vals if vals[best][0] - vals[k][0] < 0.10) + ")"
        print(f"  {name:<32} n={n:<3} " + "  ".join(cells) + f"   -> {verdict}")

    print("\nRAG (whole pipeline), answerable categories pooled: correctness by mode, history effect, oracle")
    for m in models:
        g = lambda mode: mean([r["metrics"]["correctness"] for r in rows if r["model"] == m and r["mode"] == mode and r["category"] in ANSWERABLE])
        print(f"  {m:<14} no_context {g('no_context'):.2f}  code_only {g('code_only'):.2f}  code_history {g('code_history'):.2f}  oracle {g('oracle'):.2f}")

    print("\nHallucination, latency, tokens (all categories pooled, mode = " + a.mode + ")")
    for m in models:
        rs = [r for r in rows if r["model"] == m and r["mode"] == a.mode]
        hall = mean([1.0 if r["metrics"].get("hallucinated") else 0.0 for r in rs])
        uns = mean([r["metrics"]["unsupported_ratio"] for r in rs if r["metrics"].get("unsupported_ratio") is not None])
        lat = st.median([r["metrics"]["latency_ms"] for r in rs]) / 1000
        tin = st.median([r["metrics"]["tokens_in"] for r in rs if r["metrics"].get("tokens_in") is not None])
        tout = st.median([r["metrics"]["tokens_out"] for r in rs if r["metrics"].get("tokens_out") is not None])
        print(f"  {m:<14} hallucinated {hall:.0%}  unsupported-sentence ratio {uns:.2f}  median latency {lat:.1f}s  tokens in/out {tin:.0f}/{tout:.0f}")

    print("\nRetrieval quality (property of the retriever, identical for every model): evidence recall / precision by mode")
    for mode in ("code_only", "code_history", "oracle"):
        rs = [r for r in rows if r["mode"] == mode and r["metrics"].get("evidence_recall") is not None and r["model"] == models[0]]
        print(f"  {mode:<13} recall {mean([r['metrics']['evidence_recall'] for r in rs]):.2f}  precision {mean([r['metrics']['evidence_precision'] for r in rs]):.2f}")


if __name__ == "__main__":
    main()
