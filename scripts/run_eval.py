#!/usr/bin/env python3
"""Start an evaluation run through the gateway, wait, and write the markdown report + results JSON.

    python scripts/run_eval.py --repo <repo_id> --dataset demo --split test \
        --models llama2,codellama:7b,starcoder2:3b --jury gemma:2b --out reports/run1

The held-out `test` split should be run ONCE, after thresholds are frozen (see docs/EVALUATION.md).
"""
import argparse
import json
import pathlib
import sys
import time

import httpx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gateway", default="http://localhost:8200")
    ap.add_argument("--dataset", default="demo")
    ap.add_argument("--repo", default=None)
    ap.add_argument("--split", default="all", choices=["dev", "test", "all"])
    ap.add_argument("--models", default="llama2")
    ap.add_argument("--modes", default="no_context,code_only,code_history,oracle")
    ap.add_argument("--jury", default="gemma:2b")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--name", default=None)
    ap.add_argument("--attach", type=int, default=None, help="follow an existing run id instead of starting one")
    ap.add_argument("--live", action="store_true", help="print each answer (score, latency) as it completes, with progress and ETA")
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--out", default="reports/run")
    ap.add_argument("--timeout", type=int, default=6 * 3600)
    a = ap.parse_args()

    headers = {"X-API-Key": a.api_key} if a.api_key else {}
    body = {"dataset": a.dataset, "models": a.models.split(","), "modes": a.modes.split(","), "split": a.split,
            "jury_model": a.jury or None, "repo": a.repo, "limit": a.limit, "name": a.name}
    with httpx.Client(base_url=a.gateway, timeout=60, headers=headers) as c:
        if a.attach:
            run_id, total = a.attach, c.get(f"/api/eval/runs/{a.attach}").json()["run"]["total"]
        else:
            r = c.post("/api/eval/runs", json={k: v for k, v in body.items() if v is not None})
            r.raise_for_status()
            run_id, total = r.json()["run_id"], r.json()["total"]
        print(f"run {run_id}: {total} answers", flush=True)
        end = time.time() + a.timeout
        t0, seen = time.time(), 0
        while time.time() < end:
            run = c.get(f"/api/eval/runs/{run_id}").json()["run"]
            done = run.get("done") or 0
            if a.live:
                rows = c.get(f"/api/eval/runs/{run_id}/results").json()["results"]
                for r in rows[seen:]:
                    m = r.get("metrics") or {}
                    cor = m.get("correctness")
                    err = f"  ERROR {r['error']}" if r.get("error") else ""
                    print(f"  {r['model']:<14} {r['mode']:<13} {r['item_id']:<26} {r['category']:<18} "
                          f"correct={'-' if cor is None else format(cor, '.2f')} lat={(m.get('latency_ms') or 0) / 1000:5.1f}s{err}", flush=True)
                seen = len(rows)
                el = time.time() - t0
                eta = f"{el / done * (total - done) / 60:.0f} min left" if done else "estimating"
                phase = "judging" if done >= total and run["status"] == "running" else run["status"]
                print(f"[{el / 60:5.1f} min] {phase} {done}/{total} ({100 * done // max(total, 1)}%) {eta}", flush=True)
            else:
                print(f"\r  {run['status']} {done}/{total}", end="", flush=True)
            if run["status"] != "running":
                break
            time.sleep(15 if a.live else 5)
        print()
        out = pathlib.Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.with_suffix(".md").write_text(c.get(f"/api/eval/runs/{run_id}/report").text, encoding="utf-8")
        out.with_suffix(".json").write_text(json.dumps(c.get(f"/api/eval/runs/{run_id}/results", params={"with_response": True}).json(),
                                                       indent=1), encoding="utf-8")
        print(f"wrote {out}.md / {out}.json  (status: {run['status']})")
        return 0 if run["status"] == "done" else 1


if __name__ == "__main__":
    sys.exit(main())
