import json

import pytest
from fastapi.testclient import TestClient

from app import dataset as ds
from app import main, metrics, report, runner, stats
from app.store import Store


# ---------------------------------------------------------------------- stats
def test_bootstrap_ci_brackets_the_mean_and_is_deterministic():
    xs = [0, 1, 1, 1, 0, 1, 1, 0, 1, 1]
    lo, hi = stats.bootstrap_ci(xs, seed=1)
    assert lo <= 0.7 <= hi and stats.bootstrap_ci(xs, seed=1) == (lo, hi)
    assert stats.bootstrap_ci([0.5]) == (0.5, 0.5) and stats.bootstrap_ci([]) == (None, None)


def test_permutation_pvalue_exact_small_n():
    assert stats.permutation_pvalue([1, 1, 1, 1, 1, 1]) == pytest.approx(2 / 64)
    assert stats.permutation_pvalue([0, 0, 0]) == 1.0
    assert stats.permutation_pvalue([1, -1, 1, -1]) == 1.0


def test_paired_compare_only_uses_common_items():
    a = {"q1": 0.0, "q2": 0.0, "q3": 1.0, "only_a": 1.0}
    b = {"q1": 1.0, "q2": 1.0, "q3": 1.0, "only_b": 0.0}
    r = stats.paired_compare(a, b)
    assert r["n"] == 3 and r["mean_diff"] == pytest.approx(0.667, abs=1e-3)
    assert stats.paired_compare({"x": 1}, {"y": 1}) is None


def test_weighted_kappa_perfect_none_and_partial():
    assert stats.weighted_kappa([0, 1, 2, 2, 1], [0, 1, 2, 2, 1]) == 1.0
    assert stats.weighted_kappa([0, 0, 2, 2], [2, 2, 0, 0]) < 0
    assert 0 < stats.weighted_kappa([0, 1, 2, 2, 1, 0], [0, 1, 2, 1, 1, 0]) < 1


def test_spearman_handles_ties_and_monotone():
    assert stats.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == 1.0
    assert stats.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == -1.0
    assert stats.spearman([1, 1, 1], [1, 2, 3]) is None


# -------------------------------------------------------------------- dataset
def good_dataset(**over):
    d = {"name": "t", "repo": "r", "items": [
        {"id": "a", "category": "design_rationale", "question": "Why?", "expect": "answer",
         "key_facts": [["jwt"]], "gold_evidence": ["commit:abc1234"]}]}
    d.update(over)
    return d


def test_dataset_validation_rules():
    assert ds.validate(good_dataset())["items"][0]["split"] == "dev"
    bad = good_dataset()
    bad["items"][0]["category"] = "nope"
    with pytest.raises(ds.DatasetError):
        ds.validate(bad)
    nofacts = good_dataset()
    nofacts["items"][0]["key_facts"] = []
    with pytest.raises(ds.DatasetError):
        ds.validate(nofacts)
    dup = good_dataset()
    dup["items"].append(dict(dup["items"][0]))
    with pytest.raises(ds.DatasetError):
        ds.validate(dup)


def test_dataset_hash_changes_with_content():
    a, b = good_dataset(), good_dataset()
    b["items"][0]["question"] = "Different?"
    assert ds.content_hash(ds.validate(a)) != ds.content_hash(ds.validate(b))


# -------------------------------------------------------------------- metrics
ITEM = {"id": "a", "category": "design_rationale", "question": "Why JWT?", "expect": "answer",
        "key_facts": [["jwt", "json web token"], ["session fixation"]], "gold_evidence": ["commit:69e7bbd", "issue:#7"]}


def resp(**kw):
    base = {"mode": "code_history", "answer": "Moved to JWT because of session fixation.", "refused": False,
            "sources": [{"ref": "commit:69e7bbd0aaa", "used": True}, {"ref": "code:src/auth.py", "used": True},
                        {"ref": "issue:#7", "used": False}],
            "citations": [{"ref": "commit:69e7bbd"}], "invalid_citations": ["commit:0000000"],
            "grounding": {"unsupported_ratio": 0.0}, "tokens": {"in": 100, "out": 20}, "timings": {"total_ms": 50.0}}
    base.update(kw)
    return base


def test_metrics_for_good_answer():
    m = metrics.compute(ITEM, resp())
    assert m["correctness"] == 1.0
    assert m["evidence_recall"] == 0.5 and m["evidence_recall_offered"] == 1.0
    assert m["evidence_precision"] == 0.5 and m["gold_cited"] == 0.5
    assert m["citation_validity"] == 0.5 and m["failure"] == "ok" and m["hallucinated"] == 0.0


def test_failure_taxonomy():
    wrong = resp(answer="Because of reasons.", sources=[{"ref": "code:x", "used": True}])
    assert metrics.compute(ITEM, wrong)["failure"] == "retrieval_miss"
    ignored = resp(answer="Because of reasons.")
    assert metrics.compute(ITEM, ignored)["failure"] == "model_ignored_evidence"
    halluc = resp(answer="Because of reasons.", grounding={"unsupported_ratio": 0.9})
    assert metrics.compute(ITEM, halluc)["failure"] == "hallucinated"
    assert metrics.compute(ITEM, resp(refused=True, answer="no"))["failure"] == "over_refused"
    assert metrics.compute(ITEM, resp(mode="no_context", answer="dunno", sources=[]))["failure"] == "no_evidence_given"


def test_refusal_items_score_abstention():
    item = {"id": "u", "category": "unanswerable", "question": "Why Rust?", "expect": "refuse", "gold_evidence": []}
    assert metrics.compute(item, resp(refused=True))["correctness"] == 1.0
    assert metrics.compute(item, resp(answer="The repository evidence does not say."))["correctness"] == 1.0
    m = metrics.compute(item, resp(answer="They chose Rust for speed."))
    assert m["correctness"] == 0.0 and m["failure"] == "under_refused"


def test_no_context_mode_has_no_retrieval_metrics():
    m = metrics.compute(ITEM, resp(mode="no_context", sources=[], citations=[], invalid_citations=[], grounding=None))
    assert m["evidence_recall"] is None and m["hallucinated"] is None and m["citation_validity"] is None


# --------------------------------------------------------------- run + report
class FakeBackends:
    """history mode answers correctly, code_only does not, no_context abstains."""

    def __init__(self):
        self.asked = []

    def ask(self, repo, item, model, mode):
        self.asked.append((item["id"], model, mode))
        good = mode == "code_history" or item["category"] == "current_state"
        answer = "Moved to JWT because of session fixation." if good else "I am not sure."
        if item["expect"] == "refuse":
            answer = "The repository evidence does not say."
        return resp(mode=mode, answer=answer, question=item["question"])

    def judge(self, item, r, jury_model):
        return {"parsed": {"correctness": 2, "completeness": 2, "hallucination": False, "rationale": "ok"}}


def make_items():
    items = []
    for i in range(6):
        items.append({**ITEM, "id": f"h{i}", "split": "dev"})
    items.append({**ITEM, "id": "c0", "category": "current_state", "split": "test"})
    items.append({"id": "u0", "category": "unanswerable", "question": "Why Rust?", "expect": "refuse",
                  "gold_evidence": [], "key_facts": None, "split": "dev"})
    return items


def test_execute_stores_results_and_report_applies_decision_rule():
    store = Store(":memory:")
    items = make_items()
    run_id = store.create_run("t", "t", "hash", {"split": "all"}, len(items) * 2 * 2)
    fb = FakeBackends()
    runner.execute(store, run_id, "repo", items, ["m1", "m2"], ["code_only", "code_history"], fb, jury_model="judge")
    run = store.get_run(run_id)
    assert run["status"] == "done" and run["done"] == len(items) * 4
    results = store.results(run_id)
    assert all(r["metrics"] and not r["error"] for r in results)
    assert any(r["jury"] for r in results)

    rep = report.build(run, results)
    assert rep["models"] == ["m1", "m2"] and rep["n_errors"] == 0
    dec = {d["model"]: d for d in rep["decisions"]}
    assert dec["m1"]["history_helps"] and dec["m1"]["verdict"] == "history is useful"
    cell = rep["cells"]["m1|code_history|design_rationale"]
    assert cell["correctness"] == 1.0 and cell["jury_correctness"] == 1.0
    assert rep["cells"]["m1|code_only|design_rationale"]["correctness"] == 0.0
    md = report.to_markdown(rep)
    assert "history is useful" in md and "design_rationale" in md and "Failure analysis" in md


def test_one_failing_item_does_not_kill_the_run():
    class Flaky(FakeBackends):
        def ask(self, repo, item, model, mode):
            if item["id"] == "h1":
                raise RuntimeError("orchestrator exploded")
            return super().ask(repo, item, model, mode)

    store = Store(":memory:")
    items = make_items()
    run_id = store.create_run("t", "t", "h", {}, 8)
    runner.execute(store, run_id, "repo", items, ["m"], ["code_history"], Flaky(), retries=0, sleep=lambda s: None)
    rep = report.build(store.get_run(run_id), store.results(run_id))
    assert store.get_run(run_id)["status"] == "done" and rep["n_errors"] == 1 and "orchestrator exploded" in rep["errors"][0]["error"]


def test_decision_inconclusive_with_tiny_sample():
    store = Store(":memory:")
    items = make_items()[:1]
    run_id = store.create_run("t", "t", "h", {}, 2)
    runner.execute(store, run_id, "repo", items, ["m"], ["code_only", "code_history"], FakeBackends())
    rep = report.build(store.get_run(run_id), store.results(run_id))
    assert rep["decisions"][0]["verdict"] in ("history is useful", "inconclusive")


# ------------------------------------------------------------------------ API
@pytest.fixture()
def api(tmp_path, monkeypatch):
    (tmp_path / "ds").mkdir()
    (tmp_path / "ds" / "t.json").write_text(json.dumps({"name": "t", "repo": "repo", "items": make_items()}), encoding="utf-8")
    monkeypatch.setenv("DATASETS_DIR", str(tmp_path / "ds"))
    monkeypatch.setenv("DATA_DIR", ":memory:")
    main._state.clear()
    main._state["backends"] = FakeBackends()
    monkeypatch.setattr(main, "run_in_background", lambda fn, *a: fn(*a))
    return TestClient(main.app)


def test_api_run_lifecycle_and_calibration(api):
    assert api.get("/datasets").json()["datasets"][0]["items"] == 8
    r = api.post("/runs", json={"dataset": "t", "models": ["m"], "modes": ["code_only", "code_history"], "jury_model": "j"})
    assert r.status_code == 202
    run_id = r.json()["run_id"]
    body = api.get(f"/runs/{run_id}").json()
    assert body["run"]["status"] == "done" and body["report"]["decisions"][0]["history_helps"]
    assert "history is useful" in api.get(f"/runs/{run_id}/report").text
    sheet = api.get(f"/runs/{run_id}/worksheet").json()["rows"]
    assert len(sheet) == 16 and sheet[0]["gold_answer"] == "" or sheet[0]["question"]

    grades = [{"item_id": s["item_id"], "model": s["model"], "mode": s["mode"], "score": 2 if s["mode"] == "code_history" else 0}
              for s in sheet if s["category"] == "design_rationale"]
    assert api.post(f"/runs/{run_id}/human-grades", json=grades).json()["saved"] == len(grades)
    cal = api.get(f"/runs/{run_id}/calibration").json()
    assert cal["auto_vs_human"]["weighted_kappa"] == 1.0 and cal["jury_vs_human"]["n"] >= 3


def test_api_rejects_bad_requests(api):
    assert api.post("/runs", json={"dataset": "missing", "models": ["m"]}).status_code == 404
    assert api.post("/runs", json={"dataset": "t", "models": ["m"], "modes": ["bogus"]}).status_code == 422
    assert api.post("/runs", json={"dataset": "t", "models": []}).status_code == 422
    assert api.post("/runs", json={"dataset": "t", "models": ["m"], "split": "nonexistent"}).status_code == 422
    assert api.get("/runs/999").status_code == 404


def test_plan_skips_oracle_for_items_without_gold_evidence():
    items = make_items()
    triples = runner.plan(items, ["m"], ["code_history", "oracle"])
    assert len([t for t in triples if t[1] == "oracle"]) == len([i for i in items if i["gold_evidence"]])
    assert len([t for t in triples if t[1] == "code_history"]) == len(items)


def test_jury_runs_after_all_answers_are_generated():
    """One small GPU: answering model and jury model must not alternate per item."""
    events = []

    class Ordered(FakeBackends):
        def ask(self, repo, item, model, mode):
            events.append("ask")
            return super().ask(repo, item, model, mode)

        def judge(self, item, r, jury_model):
            events.append("judge")
            return super().judge(item, r, jury_model)

    store = Store(":memory:")
    items = make_items()
    run_id = store.create_run("t", "t", "hash", {}, len(items))
    runner.execute(store, run_id, "repo", items, ["m"], ["code_history"], Ordered(), jury_model="judge")
    assert "judge" in events and events.index("judge") > max(i for i, e in enumerate(events) if e == "ask")
    assert any(r["jury"] for r in store.results(run_id))


def test_metrics_endpoint_exports_scores_and_verdicts():
    from fastapi.testclient import TestClient

    store = Store(":memory:")
    items = make_items()
    run_id = store.create_run("t", "t", "hash", {"split": "all"}, len(items) * 2)
    runner.execute(store, run_id, "repo", items, ["m1"], ["code_only", "code_history"], FakeBackends(), jury_model="judge")
    main._state["store"] = store
    text = TestClient(main.app).get("/metrics").text
    assert f'codeorigin_eval_correctness{{category="design_rationale",mode="code_history",model="m1",run="{run_id}"}} 1.0' in text
    assert f'codeorigin_eval_run_progress{{name="t",run="{run_id}",status="done"}} 1.0' in text
    assert 'verdict="history is useful"' in text and "codeorigin_eval_history_effect" in text
    assert "codeorigin_eval_quality" in text and 'metric="evidence_recall"' in text and "codeorigin_eval_latency_seconds" in text
    assert 'direction="out"' in text


def test_metrics_endpoint_skips_failed_runs():
    from fastapi.testclient import TestClient

    store = Store(":memory:")
    items = make_items()
    run_id = store.create_run("bad", "t", "hash", {"split": "all"}, len(items))
    runner.execute(store, run_id, "repo", items, ["m1"], ["code_history"], FakeBackends(), jury_model=None)
    store.finish_run(run_id, "failed", "interrupted")
    main._state["store"] = store
    assert f'run="{run_id}"' not in TestClient(main.app).get("/metrics").text
