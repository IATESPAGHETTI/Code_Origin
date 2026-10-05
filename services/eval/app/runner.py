"""Runs the dataset x models x modes matrix against the orchestrator."""
import time

import httpx

from . import metrics


class Backends:
    """HTTP access to orchestrator and llm (jury). Swappable in tests."""

    def __init__(self, orchestrator_url, llm_url, timeout=600.0):
        self.orch = orchestrator_url.rstrip("/")
        self.llm = llm_url.rstrip("/")
        self.http = httpx.Client(timeout=timeout)

    def ask(self, repo, item, model, mode):
        payload = {"repo": repo, "question": item["question"], "mode": mode, "model": model}
        if mode == "oracle":
            payload["oracle_refs"] = item.get("gold_evidence") or []
        r = self.http.post(f"{self.orch}/ask", json=payload)
        r.raise_for_status()
        return r.json()

    def judge(self, item, resp, jury_model):
        evidence = "\n".join(s["snippet"] for s in resp.get("sources", []) if s.get("used"))[:1500]
        r = self.http.post(f"{self.llm}/judge", json={
            "question": item["question"], "answer": resp.get("answer", ""), "gold_answer": item.get("gold_answer", ""),
            "evidence": evidence or None, "model": jury_model})
        r.raise_for_status()
        return r.json()


def plan(items, models, modes):
    """(model, mode, item) triples to run. Oracle mode needs gold evidence, so items
    without any (refusal categories) are skipped for it."""
    return [(m, mo, it) for m in models for mo in modes for it in items
            if not (mo == "oracle" and not it.get("gold_evidence"))]


def _judge(backends, item, resp, jury_model):
    """Jury grade, or None if unavailable / unparseable (the automatic metric still stands)."""
    if not (resp and jury_model) or resp.get("refused") or item["expect"] != "answer":
        return None
    try:
        out = backends.judge(item, resp, jury_model)
    except Exception:  # noqa: BLE001 - jury is optional
        return None
    parsed = out.get("parsed")
    if not parsed or "correctness" not in parsed:
        return None
    return {**parsed, "raw": out.get("raw")}


def execute(store, run_id, repo, items, models, modes, backends, jury_model=None, retries=1, sleep=time.sleep):
    """Sequential on purpose: one local GPU, and latency numbers must not be contaminated by parallel load.

    Two passes: generate every answer first, then run the jury. Interleaving them makes a small GPU
    swap the answering model and the jury model in and out for every single item."""
    try:
        to_judge = []
        for model, mode, item in plan(items, models, modes):
            resp = metrics_ = err = None
            for attempt in range(retries + 1):
                try:
                    resp = backends.ask(repo, item, model, mode)
                    metrics_ = metrics.compute(item, resp)
                    err = None
                    break
                except Exception as exc:  # noqa: BLE001 - one bad item must not kill the run
                    err = f"{type(exc).__name__}: {exc}"[:300]
                    resp = None
                    if attempt < retries:
                        sleep(1.0)
            row_id = store.add_result(run_id, item["id"], model, mode, item["category"], resp, metrics_, None, err)
            if jury_model and resp:
                to_judge.append((row_id, item, resp))
        for row_id, item, resp in to_judge:
            jury = _judge(backends, item, resp, jury_model)
            if jury:
                store.set_jury(row_id, jury)
        store.finish_run(run_id, "done")
    except Exception as exc:  # noqa: BLE001
        store.finish_run(run_id, "failed", f"{type(exc).__name__}: {exc}"[:300])
