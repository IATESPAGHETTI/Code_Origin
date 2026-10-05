#!/usr/bin/env python3
"""Build the seeded demo repo and register it through the gateway.

    python scripts/seed_demo.py [--gateway http://localhost:8200] [--out demo-data] [--container-path /demo]

With docker compose the ingest container sees the demo data at /demo
(see docker-compose.demo.yml), hence --container-path.
"""
import argparse
import pathlib
import sys
import time

import httpx

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import make_demo_repo  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gateway", default="http://localhost:8200")
    ap.add_argument("--out", default="demo-data")
    ap.add_argument("--container-path", default=None, help="where ingest sees --out (default: same path)")
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args()

    out = pathlib.Path(args.out).resolve()
    shas = make_demo_repo.build(out)
    base = args.container_path or str(out)
    base = base.rstrip("/\\")
    sep = "/" if "/" in base or not base[1:2] == ":" else "\\"
    print(f"demo repo built: {len(shas)} commits in {out}")

    with httpx.Client(base_url=args.gateway, timeout=60) as c:
        r = c.post("/api/repos", json={"source": f"{base}{sep}repo", "issues_file": f"{base}{sep}fixtures.json"})
        if r.status_code >= 400:
            sys.exit(f"register failed: {r.status_code} {r.text}")
        body = r.json()
        job = body["job_id"]
        deadline = time.time() + args.timeout
        while time.time() < deadline:
            j = c.get(f"/api/jobs/{job}").json()
            print(f"  [{j['progress'] or 0:3d}%] {j['stage']}: {j['message']}")
            if j["status"] != "running":
                break
            time.sleep(1)
        if j["status"] != "done":
            sys.exit(f"ingest {j['status']}: {j['message']}")
        repo = c.get(f"/api/repos/{body['repo_id']}").json()
        print("ready:", body["repo_id"], repo["counts"])


if __name__ == "__main__":
    main()
