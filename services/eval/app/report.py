"""Aggregate results per model x mode x category and render the report.

Findings are always reported per category with confidence intervals; there is
deliberately no single blended score. The decision rule is fixed in advance.
"""
from collections import Counter, defaultdict

from . import stats
from .dataset import CATEGORIES

MODE_ORDER = ["no_context", "code_only", "code_history", "oracle"]
NUMERIC = ["correctness", "evidence_recall", "evidence_precision", "gold_cited", "citation_validity",
           "unsupported_ratio", "hallucinated", "refusal_correct", "latency_ms", "tokens_in", "tokens_out",
           "invalid_citations"]

# pre-registered decision rule (docs/EVALUATION.md)
MIN_EFFECT = 0.10          # history must beat code_only by >= 0.10 correctness on history categories
MAX_CONTROL_LOSS = 0.05    # and not lose more than 0.05 on the control category


def _group_mean(rows, key):
    return stats.mean([r["metrics"].get(key) for r in rows])


def _cell(rows):
    cell = {"n": len(rows)}
    for k in NUMERIC:
        v = _group_mean(rows, k)
        cell[k] = None if v is None else round(v, 3)
    lo, hi = stats.bootstrap_ci([r["metrics"].get("correctness") for r in rows])
    cell["correctness_ci"] = [None if lo is None else round(lo, 3), None if hi is None else round(hi, 3)]
    j = [r["jury"]["correctness"] / 2 for r in rows if r.get("jury")]
    cell["jury_correctness"] = round(stats.mean(j), 3) if j else None
    return cell


def build(run, results):
    ok = [r for r in results if not r.get("error")]
    errors = [r for r in results if r.get("error")]
    models = sorted({r["model"] for r in ok})
    modes = [m for m in MODE_ORDER if m in {r["mode"] for r in ok}]
    cats = sorted({r["category"] for r in ok}, key=lambda c: (list(CATEGORIES).index(c)))

    by = defaultdict(list)
    for r in ok:
        by[(r["model"], r["mode"], r["category"])].append(r)
    cells = {f"{m}|{mo}|{c}": _cell(rows) for (m, mo, c), rows in by.items()}

    overall = defaultdict(list)
    for r in ok:
        overall[(r["model"], r["mode"])].append(r)
    totals = {f"{m}|{mo}": _cell(rows) for (m, mo), rows in overall.items()}

    # paired comparisons per model: code_history vs code_only (and vs no_context)
    def correctness_by_item(model, mode, group):
        return {r["item_id"]: r["metrics"]["correctness"] for r in ok
                if r["model"] == model and r["mode"] == mode and CATEGORIES[r["category"]] == group}

    comparisons, decisions = [], []
    for model in models:
        for group in ("history", "control", "guardrail"):
            for base in ("code_only", "no_context"):
                if "code_history" not in modes or base not in modes:
                    continue
                cmp_ = stats.paired_compare(correctness_by_item(model, base, group),
                                            correctness_by_item(model, "code_history", group))
                if cmp_:
                    comparisons.append({"model": model, "group": group, "baseline": base, "treatment": "code_history", **cmp_})
        hist = next((c for c in comparisons if c["model"] == model and c["group"] == "history" and c["baseline"] == "code_only"), None)
        ctrl = next((c for c in comparisons if c["model"] == model and c["group"] == "control" and c["baseline"] == "code_only"), None)
        if hist:
            helps = hist["ci_low"] > 0 and hist["mean_diff"] >= MIN_EFFECT
            harms = bool(ctrl) and ctrl["ci_high"] < -MAX_CONTROL_LOSS
            decisions.append({
                "model": model, "history_helps": helps, "control_harmed": harms,
                "verdict": ("history is useful" if helps and not harms else
                            "history helps but hurts the control category" if helps else
                            "inconclusive" if hist["ci_low"] <= 0 <= hist["ci_high"] else "history does not help"),
                "history_diff": hist["mean_diff"], "history_ci": [hist["ci_low"], hist["ci_high"]],
            })

    failures = defaultdict(Counter)
    for r in ok:
        failures[f"{r['model']}|{r['mode']}"][r["metrics"]["failure"]] += 1

    return {
        "run": {k: run.get(k) for k in ("id", "name", "dataset_name", "dataset_hash", "status", "created_at", "config")},
        "models": models, "modes": modes, "categories": cats,
        "cells": cells, "totals": totals, "comparisons": comparisons, "decisions": decisions,
        "failures": {k: dict(v) for k, v in failures.items()},
        "n_results": len(ok), "n_errors": len(errors),
        "errors": [{"item_id": e["item_id"], "model": e["model"], "mode": e["mode"], "error": e["error"]} for e in errors[:20]],
    }


def _fmt(v, pct=False):
    if v is None:
        return "-"
    return f"{v * 100:.0f}%" if pct else f"{v:.2f}"


def to_markdown(rep):
    run = rep["run"]
    cfg = run.get("config") or {}
    lines = ["# CodeOrigin evaluation report", "",
             f"- Dataset: `{run.get('dataset_name')}` (hash `{run.get('dataset_hash')}`)",
             f"- Models: {', '.join(rep['models'])}; modes: {', '.join(rep['modes'])}",
             f"- Items scored: {rep['n_results']} ({rep['n_errors']} errors); split: {cfg.get('split', 'all')}",
             "- Temperature 0, fixed seed; identical context budget across modes.", ""]

    lines += ["## Verdict (pre-registered rule)", "",
              f"History is *useful* if code_history beats code_only on history categories by >= {MIN_EFFECT:.2f} "
              f"correctness with a 95% CI excluding 0, without losing more than {MAX_CONTROL_LOSS:.2f} on the control category.", ""]
    if rep["decisions"]:
        lines += ["| Model | Verdict | history diff (95% CI) |", "|---|---|---|"]
        for d in rep["decisions"]:
            lines.append(f"| {d['model']} | **{d['verdict']}** | {d['history_diff']:+.2f} [{d['history_ci'][0]:+.2f}, {d['history_ci'][1]:+.2f}] |")
    else:
        lines.append("_Need both code_only and code_history modes to apply the rule._")
    lines.append("")

    for model in rep["models"]:
        lines += [f"## {model}: correctness by category", "",
                  "| Category | " + " | ".join(rep["modes"]) + " |", "|---|" + "---|" * len(rep["modes"])]
        for c in rep["categories"]:
            row = []
            for mo in rep["modes"]:
                cell = rep["cells"].get(f"{model}|{mo}|{c}")
                if not cell:
                    row.append("-")
                    continue
                lo, hi = cell["correctness_ci"]
                row.append(f"{_fmt(cell['correctness'])} [{_fmt(lo)}-{_fmt(hi)}] n={cell['n']}")
            lines.append(f"| {c} | " + " | ".join(row) + " |")
        lines.append("")

    lines += ["## Retrieval, citations, hallucination and cost (all categories pooled)", "",
              "| Model | Mode | evidence recall | evidence precision | gold cited | citation validity | unsupported claims | refusal correct | p50-ish latency ms | tokens in/out |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for model in rep["models"]:
        for mo in rep["modes"]:
            t = rep["totals"].get(f"{model}|{mo}")
            if t:
                lines.append(f"| {model} | {mo} | {_fmt(t['evidence_recall'])} | {_fmt(t['evidence_precision'])} | {_fmt(t['gold_cited'])} | "
                             f"{_fmt(t['citation_validity'])} | {_fmt(t['unsupported_ratio'])} | {_fmt(t['refusal_correct'])} | "
                             f"{t['latency_ms'] if t['latency_ms'] is not None else '-'} | {t['tokens_in']}/{t['tokens_out']} |")
    lines.append("")

    if rep["comparisons"]:
        lines += ["## Paired comparisons (treatment - baseline, correctness)", "",
                  "| Model | Items | Baseline -> code_history | n | mean diff | 95% CI | p (sign-flip) | d_z |", "|---|---|---|---|---|---|---|---|"]
        for c in rep["comparisons"]:
            lines.append(f"| {c['model']} | {c['group']} | {c['baseline']} | {c['n']} | {c['mean_diff']:+.2f} | "
                         f"[{c['ci_low']:+.2f}, {c['ci_high']:+.2f}] | {c['p_value']} | {c['effect_size_dz']} |")
        lines.append("")

    lines += ["## Failure analysis (why answers were wrong)", "",
              "| Model | Mode | " + " | ".join(["ok", "retrieval_miss", "model_ignored_evidence", "hallucinated", "over_refused", "under_refused", "no_evidence_given"]) + " |",
              "|---|---|" + "---|" * 7]
    for key, counts in sorted(rep["failures"].items()):
        model, mo = key.split("|")
        lines.append(f"| {model} | {mo} | " + " | ".join(str(counts.get(k, 0)) for k in
                     ["ok", "retrieval_miss", "model_ignored_evidence", "hallucinated", "over_refused", "under_refused", "no_evidence_given"]) + " |")
    lines.append("")
    if rep["n_errors"]:
        lines += ["## Errors", ""] + [f"- {e['item_id']} / {e['model']} / {e['mode']}: {e['error']}" for e in rep["errors"]] + [""]
    lines.append("_Limits: small samples give wide intervals; automatic correctness is key-fact matching, calibrated against "
                 "human grades (see calibration)._")
    return "\n".join(lines)
