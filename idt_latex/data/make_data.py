"""
Builds idt_latex/data/derived.json, the only input of make_figures.py and
make_tables.py, from the projects' own stored results. No model is run.

CodeOrigin numbers are recomputed from every stored answer with CodeOrigin's
own statistics module (services/eval/app/stats.py: 2000 bootstrap resamples,
sign-flip permutation test, seed 0), so they match CodeOrigin's reports.

Usage (paths default to the IDT_FULL checkout layout):
    python idt_latex/data/make_data.py --codeorigin <CodeOrigin dir> \
        --changeguard <endsem dir> --platform-eval <merged eval dir>
"""
import argparse
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HISTORY = ["design_rationale", "bug_origin", "change_attribution", "issue_linkage", "evolution"]
CONTROL = ["current_state"]
GUARD = ["unanswerable", "off_topic", "adversarial"]
MODES = ["no_context", "code_only", "code_history", "oracle"]
MODELS = ["llama2", "codellama:7b", "starcoder2:3b"]
CG_CATS = ["code_explanation", "code_retrieval", "dependency_understanding", "bug_analysis",
           "rag_documentation", "code_generation", "refactoring", "repo_level_understanding"]


def codeorigin_run(path, stats):
    rows = json.load(open(path, encoding="utf-8"))["results"]
    rows = [r for r in rows if not r.get("error")]
    out = {"n_answers": len(rows), "models": {}}
    for m in MODELS:
        mr = [r for r in rows if r["model"] == m]
        if not mr:
            continue
        res = {"modes": {}, "categories": {}, "paired": {}}
        by = {}
        for r in mr:
            by.setdefault(r["mode"], {})[r["item_id"]] = r
        for mode in MODES:
            items = list(by.get(mode, {}).values())
            if not items:
                continue
            def sel(cats):
                return [r["metrics"]["correctness"] for r in items if r["category"] in cats]
            hist = sel(HISTORY)
            lo, hi = stats.bootstrap_ci(hist)
            mm = [r["metrics"] for r in items]
            hall = [x["hallucinated"] for x in mm if x.get("hallucinated") is not None and not x.get("refused")]
            res["modes"][mode] = {
                "history_mean": stats.mean(hist), "history_ci": [lo, hi], "history_n": len(hist),
                "control_mean": stats.mean(sel(CONTROL)), "guard_mean": stats.mean(sel(GUARD)) if sel(GUARD) else None,
                "answerable_mean": stats.mean(sel(HISTORY + CONTROL)),
                "evidence_recall": stats.mean([x.get("evidence_recall") for x in mm]),
                "evidence_precision": stats.mean([x.get("evidence_precision") for x in mm]),
                "citation_validity": stats.mean([x.get("citation_validity") for x in mm]),
                "unsupported_ratio": stats.mean([x.get("unsupported_ratio") for x in mm]),
                "hallucination_rate": stats.mean([1.0 if h else 0.0 for h in hall]) if hall else None,
                "latency_median_s": statistics.median([x["latency_ms"] for x in mm]) / 1000,
                "latency_mean_s": statistics.mean([x["latency_ms"] for x in mm]) / 1000,
                "failures": {},
            }
            for x in mm:
                f = x.get("failure") or "ok"
                res["modes"][mode]["failures"][f] = res["modes"][mode]["failures"].get(f, 0) + 1
        for cat in HISTORY + CONTROL + GUARD:
            res["categories"][cat] = {mode: stats.mean([r["metrics"]["correctness"] for r in by.get(mode, {}).values()
                                                        if r["category"] == cat]) for mode in MODES}
        for group, cats in (("history", HISTORY), ("control", CONTROL)):
            for base in ("code_only", "no_context"):
                a = {k: r["metrics"]["correctness"] for k, r in by.get(base, {}).items() if r["category"] in cats}
                b = {k: r["metrics"]["correctness"] for k, r in by.get("code_history", {}).items() if r["category"] in cats}
                res["paired"][f"{group}|{base}"] = stats.paired_compare(a, b)
        out["models"][m] = res
    return out


def parse_category_md(path):
    """Hand grades per category from CATEGORY_COMPARISON.md (the only place they are stored)."""
    text = open(path, encoding="utf-8").read()
    out = {}
    for block in re.split(r"\n## \d+\. ", text)[1:]:
        cat = re.match(r"`([a-z_]+)`", block).group(1)
        out[cat] = {}
        for m in MODELS:
            row = re.search(r"\| " + re.escape(m) + r" \| ([0-9.]+) \|", block)
            if row:
                out[cat][m] = float(row.group(1))
    return out


def main():
    root = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
    ap = argparse.ArgumentParser()
    ap.add_argument("--codeorigin", default=os.path.join(root, "CodeOrigin"))
    ap.add_argument("--changeguard", default=os.path.join(root, "endsem"))
    ap.add_argument("--platform-eval", default=os.path.join(root, "eval"))
    a = ap.parse_args()
    sys.path.insert(0, os.path.join(a.codeorigin, "services", "eval", "app"))
    import stats  # CodeOrigin's own module

    d = {"codeorigin": {}, "changeguard": {}}
    d["codeorigin"]["heldout"] = codeorigin_run(os.path.join(a.codeorigin, "reports", "itsdangerous_heldout.json"), stats)
    d["codeorigin"]["demo_dev"] = codeorigin_run(os.path.join(a.codeorigin, "reports", "dev_full_3models.json"), stats)
    pe = a.platform_eval
    ds = json.load(open(os.path.join(pe, "results", "deepseek_run10_metrics.json"), encoding="utf-8"))
    d["codeorigin"]["deepseek_run10"] = ds
    # Run 10 (hosted DeepSeek, same held-out set): per-category means are stored per mode with their n,
    # so the history-question mean is the n-weighted mean over the five history categories.
    cmp_ = json.load(open(os.path.join(pe, "results", "deepseek_comparison.json"), encoding="utf-8"))
    cats = cmp_["codeorigin"]["deepseek"]["models"]["deepseek-flash"]["categories"]
    hm = {}
    for mode in MODES:
        num = sum(cats[c][mode][0] * cats[c][mode][1] for c in HISTORY)
        den = sum(cats[c][mode][1] for c in HISTORY)
        hm[mode] = num / den
    eff = {e["bound"]: e["v"] for e in ds["history_effect"]}
    d["codeorigin"]["deepseek_run10_summary"] = {"history_means": hm, "effect": eff, "categories": cats,
                                                "cost": cmp_["cost"], "wall_seconds": cmp_["codeorigin"]["wall_seconds"]}

    ev = os.path.join(a.changeguard, "evaluation")
    res = json.load(open(os.path.join(ev, "results.json"), encoding="utf-8"))
    p5 = {}
    for it in res["items"]:
        p5.setdefault(it["category"], []).append(it["retrieval"]["precision_at_5"])
    d["changeguard"]["n_questions"] = len(res["items"])
    d["changeguard"]["category_n"] = {c: len(v) for c, v in p5.items()}
    d["changeguard"]["precision_at_5"] = {c: statistics.mean(v) for c, v in p5.items()}
    d["changeguard"]["precision_at_5_all"] = statistics.mean([x for v in p5.values() for x in v])
    d["changeguard"]["hand_grades"] = parse_category_md(os.path.join(ev, "CATEGORY_COMPARISON.md"))
    for name in ("changeguard_metrics", "changeguard_keyfacts", "codegen_rescore", "codegen_grounded_deepseek_rescore",
                 "changeguard_deepseek_codegen_rescore"):
        d["changeguard"][name] = json.load(open(os.path.join(pe, "results", name + ".json"), encoding="utf-8"))
    for name in ("codegen_rescore", "codegen_grounded_deepseek_rescore", "changeguard_deepseek_codegen_rescore"):
        d["changeguard"][name] = d["changeguard"][name].get("summary", d["changeguard"][name])
    # Chunking and retrieval comparisons are stored only in endsem/EVALUATION.md (5 questions, run 2026-08-23).
    d["changeguard"]["chunking"] = {"fixed": {"p5": 1.00, "chars": 722, "latency_s": 0.032},
                                    "structure": {"p5": 0.90, "chars": 350, "latency_s": 0.027},
                                    "source": "endsem/EVALUATION.md"}
    d["changeguard"]["retrieval"] = {"vector_similarity": {"p5": 0.90, "latency_s": 0.052},
                                     "metadata_filtered_source_code": {"p5": 0.60, "latency_s": 0.029},
                                     "source": "endsem/EVALUATION.md"}
    with open(os.path.join(HERE, "derived.json"), "w", encoding="utf-8") as fh:
        json.dump(d, fh, indent=1)
    h = d["codeorigin"]["heldout"]["models"]
    for m in h:
        p = h[m]["paired"]["history|code_only"]
        print(m, {k: round(v["history_mean"], 3) for k, v in h[m]["modes"].items()}, p)


if __name__ == "__main__":
    main()
