"""CodeOrigin eval service: datasets, runs, metrics, jury calibration, reports."""
import os
import threading
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest
from pydantic import BaseModel, Field

from . import dataset as ds
from . import exporter, report, runner, stats
from .store import Store

app = FastAPI(title="CodeOrigin eval", version="0.1.0")
_state = {}


def datasets_dir():
    return os.getenv("DATASETS_DIR", os.path.join(os.path.dirname(__file__), "..", "datasets"))


def get_store():
    if "store" not in _state:
        data = os.getenv("DATA_DIR", "/data")
        _state["store"] = Store(":memory:" if data == ":memory:" else os.path.join(data, "eval.db"))
        _state["store"].fail_stale()
    return _state["store"]


def get_backends():
    if "backends" not in _state:
        _state["backends"] = runner.Backends(os.getenv("ORCHESTRATOR_URL", "http://codeorigin-orchestrator:8204"),
                                             os.getenv("LLM_SERVICE_URL", "http://codeorigin-llm:8203"))
    return _state["backends"]


def run_in_background(fn, *args):
    """Indirection so tests can run synchronously."""
    threading.Thread(target=fn, args=args, daemon=True).start()


class RunRequest(BaseModel):
    dataset: str = Field(min_length=1)
    models: list[str] = Field(min_length=1)
    modes: list[str] = Field(default_factory=lambda: ["no_context", "code_only", "code_history"])
    split: Optional[str] = "all"
    limit: Optional[int] = Field(default=None, ge=1)
    categories: Optional[list[str]] = None
    jury_model: Optional[str] = None
    repo: Optional[str] = None
    name: Optional[str] = None


class HumanGrade(BaseModel):
    item_id: str
    model: str
    mode: str
    score: int = Field(ge=0, le=2)


@app.get("/metrics")
def metrics_endpoint():
    """Evaluation scores for Prometheus/Grafana (internal network only; the gateway does not proxy this)."""
    registry = CollectorRegistry()
    registry.register(exporter.EvalCollector(get_store))
    return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
def health():
    get_store()
    return {"status": "ok"}


@app.get("/datasets")
def list_datasets():
    return {"datasets": ds.list_datasets(datasets_dir())}


@app.get("/datasets/{name}")
def get_dataset(name: str):
    path = os.path.join(datasets_dir(), os.path.basename(name if name.endswith(".json") else f"{name}.json"))
    if not os.path.isfile(path):
        raise HTTPException(404, "unknown dataset")
    return ds.load(path)


@app.post("/runs", status_code=202)
def start_run(req: RunRequest):
    for mode in req.modes:
        if mode not in ("no_context", "code_only", "code_history", "oracle"):
            raise HTTPException(422, f"unknown mode {mode}")
    path = os.path.join(datasets_dir(), os.path.basename(req.dataset if req.dataset.endswith(".json") else f"{req.dataset}.json"))
    if not os.path.isfile(path):
        raise HTTPException(404, "unknown dataset")
    try:
        data = ds.load(path)
    except ds.DatasetError as exc:
        raise HTTPException(422, str(exc))
    items = ds.select(data, req.split, req.limit, req.categories)
    if not items:
        raise HTTPException(422, "no items selected")
    config = {"models": req.models, "modes": req.modes, "split": req.split, "limit": req.limit, "jury_model": req.jury_model,
              "git_sha": os.getenv("GIT_SHA", "unknown")}
    store = get_store()
    total = len(runner.plan(items, req.models, req.modes))
    run_id = store.create_run(req.name or f"{data['name']}-run", data["name"], data["hash"], config, total)
    run_in_background(runner.execute, store, run_id, req.repo or data["repo"], items, req.models, req.modes,
                      get_backends(), req.jury_model)
    return {"run_id": run_id, "total": total}


@app.get("/runs")
def list_runs():
    return {"runs": get_store().list_runs()}


def _run_or_404(run_id):
    run = get_store().get_run(run_id)
    if not run:
        raise HTTPException(404, "unknown run")
    return run


@app.get("/runs/{run_id}")
def get_run(run_id: int):
    run = _run_or_404(run_id)
    return {"run": run, "report": report.build(run, get_store().results(run_id))}


@app.get("/runs/{run_id}/report", response_class=PlainTextResponse)
def get_report(run_id: int):
    run = _run_or_404(run_id)
    return report.to_markdown(report.build(run, get_store().results(run_id)))


@app.get("/runs/{run_id}/results")
def get_results(run_id: int, with_response: bool = False):
    _run_or_404(run_id)
    return {"results": get_store().results(run_id, with_response)}


@app.get("/runs/{run_id}/worksheet")
def worksheet(run_id: int):
    """Blind-able sheet for human grading: question, gold answer, model answer."""
    run = _run_or_404(run_id)
    try:
        data = ds.load(os.path.join(datasets_dir(), f"{run['dataset_name']}.json"))
        items = {i["id"]: i for i in data["items"]}
    except (OSError, ds.DatasetError):
        items = {}
    rows = []
    for r in get_store().results(run_id, with_response=True):
        if r["response"]:
            it = items.get(r["item_id"], {})
            rows.append({"item_id": r["item_id"], "model": r["model"], "mode": r["mode"], "category": r["category"],
                         "question": it.get("question", r["response"].get("question")), "gold_answer": it.get("gold_answer", ""),
                         "answer": r["response"]["answer"]})
    return {"rows": rows}


@app.post("/runs/{run_id}/human-grades")
def post_human_grades(run_id: int, grades: list[HumanGrade]):
    _run_or_404(run_id)
    for g in grades:
        get_store().set_human_grade(run_id, g.item_id, g.model, g.mode, g.score)
    return {"saved": len(grades)}


@app.get("/runs/{run_id}/calibration")
def calibration(run_id: int):
    """Agreement of the LLM jury and the automatic key-fact score with human grades."""
    _run_or_404(run_id)
    human = {(g["item_id"], g["model"], g["mode"]): g["score"] for g in get_store().human_grades(run_id)}
    rows = [r for r in get_store().results(run_id) if (r["item_id"], r["model"], r["mode"]) in human and r["metrics"]]
    if len(rows) < 3:
        return {"n": len(rows), "note": "need at least 3 human-graded answers"}

    def to_ord(x):
        return 0 if x < 0.34 else 1 if x < 0.67 else 2

    h = [human[(r["item_id"], r["model"], r["mode"])] for r in rows]
    auto = [to_ord(r["metrics"]["correctness"] or 0) for r in rows]
    out = {"n": len(rows),
           "auto_vs_human": {"weighted_kappa": stats.weighted_kappa(auto, h), "spearman": stats.spearman(auto, h)}}
    jr = [(r, human[(r["item_id"], r["model"], r["mode"])]) for r in rows if r["jury"]]
    if len(jr) >= 3:
        jv = [int(r["jury"]["correctness"]) for r, _ in jr]
        hv = [s for _, s in jr]
        k = stats.weighted_kappa(jv, hv)
        out["jury_vs_human"] = {"n": len(jr), "weighted_kappa": k, "spearman": stats.spearman(jv, hv),
                                "usable_as_headline": bool(k is not None and k >= 0.6)}
    return out
