"""Prometheus exposition of evaluation results, computed from the stored runs at scrape time.

Only the newest RUNS_EXPORTED runs are exported to keep label cardinality small, and failed (interrupted) runs are skipped. Scores are the same
numbers as the report (key-fact correctness, bootstrap CI, jury, verdict); nothing is recomputed differently.
"""
from prometheus_client.core import GaugeMetricFamily

from . import report

RUNS_EXPORTED = 10
# (metric label, field in the report cell); 'hallucinated' is the share of answers flagged hallucinated
QUALITY_FIELDS = [("hallucination_rate", "hallucinated"), ("unsupported_ratio", "unsupported_ratio"), ("evidence_recall", "evidence_recall"),
                  ("evidence_precision", "evidence_precision"), ("gold_cited", "gold_cited"), ("citation_validity", "citation_validity"),
                  ("refusal_correct", "refusal_correct")]


class EvalCollector:
    def __init__(self, get_store):
        self.get_store = get_store

    def collect(self):
        store = self.get_store()
        progress = GaugeMetricFamily("codeorigin_eval_run_progress", "Answers done / total for a run",
                                     labels=["run", "name", "status"])
        correct = GaugeMetricFamily("codeorigin_eval_correctness", "Mean correctness per model, mode and category",
                                    labels=["run", "model", "mode", "category"])
        total = GaugeMetricFamily("codeorigin_eval_correctness_overall", "Mean correctness per model and mode (all categories)",
                                  labels=["run", "model", "mode"])
        ci = GaugeMetricFamily("codeorigin_eval_correctness_overall_ci", "95% bootstrap CI bound of overall correctness",
                               labels=["run", "model", "mode", "bound"])
        jury = GaugeMetricFamily("codeorigin_eval_jury_correctness", "Mean jury correctness (0-1) per model and mode",
                                 labels=["run", "model", "mode"])
        effect = GaugeMetricFamily("codeorigin_eval_history_effect", "code_history minus code_only correctness on history categories",
                                   labels=["run", "model", "bound"])
        verdict = GaugeMetricFamily("codeorigin_eval_verdict", "Pre-registered decision rule verdict (1 = current)",
                                    labels=["run", "model", "verdict"])
        fails = GaugeMetricFamily("codeorigin_eval_failures", "Answers by failure category",
                                  labels=["run", "model", "mode", "failure"])
        quality = GaugeMetricFamily("codeorigin_eval_quality", "Mean answer-quality and retrieval metrics per model and mode",
                                    labels=["run", "model", "mode", "metric"])
        latency = GaugeMetricFamily("codeorigin_eval_latency_seconds", "Mean end-to-end response latency per model and mode",
                                    labels=["run", "model", "mode"])
        tokens = GaugeMetricFamily("codeorigin_eval_tokens", "Mean tokens per answer, by direction",
                                   labels=["run", "model", "mode", "direction"])
        for run in store.list_runs()[:RUNS_EXPORTED]:
            if run["status"] == "failed":
                continue
            rid = str(run["id"])
            frac = (run.get("done") or 0) / run["total"] if run.get("total") else 0.0
            progress.add_metric([rid, run.get("name") or "", run["status"]], frac)
            if not run.get("done"):
                continue
            rep = report.build(run, store.results(run["id"]))
            for key, cell in rep["cells"].items():
                model, mode, cat = key.split("|")
                if cell["correctness"] is not None:
                    correct.add_metric([rid, model, mode, cat], cell["correctness"])
            for key, cell in rep["totals"].items():
                model, mode = key.split("|")
                if cell["correctness"] is not None:
                    total.add_metric([rid, model, mode], cell["correctness"])
                    lo, hi = cell["correctness_ci"]
                    if lo is not None:
                        ci.add_metric([rid, model, mode, "low"], lo)
                        ci.add_metric([rid, model, mode, "high"], hi)
                if cell["jury_correctness"] is not None:
                    jury.add_metric([rid, model, mode], cell["jury_correctness"])
                for metric, field in QUALITY_FIELDS:
                    if cell.get(field) is not None:
                        quality.add_metric([rid, model, mode, metric], cell[field])
                if cell.get("latency_ms") is not None:
                    latency.add_metric([rid, model, mode], cell["latency_ms"] / 1000.0)
                for direction, field in (("in", "tokens_in"), ("out", "tokens_out")):
                    if cell.get(field) is not None:
                        tokens.add_metric([rid, model, mode, direction], cell[field])
            for d in rep["decisions"]:
                effect.add_metric([rid, d["model"], "mean"], d["history_diff"])
                effect.add_metric([rid, d["model"], "low"], d["history_ci"][0])
                effect.add_metric([rid, d["model"], "high"], d["history_ci"][1])
                verdict.add_metric([rid, d["model"], d["verdict"]], 1)
            for key, counts in rep["failures"].items():
                model, mode = key.split("|")
                for failure, n in counts.items():
                    fails.add_metric([rid, model, mode, failure], n)
        yield from (progress, correct, total, ci, jury, effect, verdict, fails, quality, latency, tokens)
