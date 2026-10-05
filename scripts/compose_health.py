#!/usr/bin/env python3
"""Wait until every codeorigin-* container reports healthy; exit 1 on timeout/unhealthy.

    python scripts/compose_health.py [--timeout 300] [--require gateway,ingest,...]
"""
import argparse
import json
import subprocess
import sys
import time

CORE = ["web", "gateway", "ingest", "rag", "llm", "orchestrator", "eval", "chromadb"]


def states():
    out = subprocess.run(["docker", "ps", "-a", "--filter", "name=codeorigin-", "--format", "{{json .}}"],
                         capture_output=True, text=True, check=True).stdout
    res = {}
    for line in out.splitlines():
        row = json.loads(line)
        res[row["Names"].removeprefix("codeorigin-")] = row["Status"]
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--require", default=",".join(CORE))
    args = ap.parse_args()
    need = [s for s in args.require.split(",") if s]
    deadline = time.time() + args.timeout
    while True:
        st = states()
        bad = {n: st.get(n, "missing") for n in need if "(healthy)" not in st.get(n, "")}
        if not bad:
            print("all healthy:", ", ".join(need))
            return 0
        if any("unhealthy" in s or s.startswith("Exited") for s in bad.values()) or time.time() > deadline:
            print("NOT healthy:", bad)
            return 1
        time.sleep(3)


if __name__ == "__main__":
    sys.exit(main())
