#!/usr/bin/env python3
"""Machine check of a real-repo evaluation dataset against the GitHub snapshot it was drafted from.

    python scripts/check_dataset.py services/eval/datasets/itsdangerous.json demo-data/itsdangerous_fixtures.json

For every answerable item it checks (1) each gold_evidence ref exists in the snapshot (issues, PRs, releases; code files are
fetched with `gh` from the repo's default branch), and (2) every key-fact group has at least one phrasing that occurs in the
text of the cited evidence. (2) proves the answer is *available* in the evidence; it does not prove the gold answer is the
best reading of it, so a human still has to read the threads. Items that fail are listed and the exit code is 1.
"""
import json
import subprocess
import sys


def evidence_text(ref, fx, repo):
    kind, _, ident = ref.partition(":")
    if kind in ("issue", "pr"):
        n = int(ident.lstrip("#"))
        pool = fx["issues"] if kind == "issue" else fx["pulls"]
        x = next((i for i in pool if i["number"] == n), None)
        if not x:
            return None
        parts = [x["title"], x["body"], x["author"]] + [c["body"] for c in x["comments"]]
        parts += [r["body"] for r in x.get("reviews", [])] + [c["body"] for c in x.get("review_comments", [])]
        return "\n".join(p or "" for p in parts)
    if kind == "release":
        r = next((r for r in fx["releases"] if r["tag"] == ident), None)
        return None if not r else f"{r['name']}\n{r['body']}"
    if kind == "code":
        try:
            return subprocess.run(["gh", "api", f"repos/{repo}/contents/{ident}", "-H", "Accept: application/vnd.github.raw"],
                                  capture_output=True, text=True, check=True, encoding="utf-8").stdout
        except subprocess.CalledProcessError:
            return None
    return None


def main(dataset_path, fixture_path):
    ds = json.load(open(dataset_path, encoding="utf-8"))
    fx = json.load(open(fixture_path, encoding="utf-8"))
    repo = fx["repo"]
    problems, ok = [], 0
    for it in ds["items"]:
        if it["expect"] != "answer":
            continue
        texts = {}
        for ref in it["gold_evidence"]:
            t = evidence_text(ref, fx, repo)
            if t is None:
                problems.append((it["id"], f"evidence {ref} not found in snapshot"))
            else:
                texts[ref] = t.lower()
        blob = "\n".join(texts.values())
        bad = [g for g in it["key_facts"] if not any(alt.lower() in blob for alt in g)]
        # attribution/linkage facts must appear in the evidence text too (authors are included above)
        for g in bad:
            problems.append((it["id"], f"no phrasing of {g} occurs in the cited evidence"))
        ok += not any(p[0] == it["id"] for p in problems)
    n = sum(1 for i in ds["items"] if i["expect"] == "answer")
    print(f"{ok}/{n} answerable items pass (evidence exists, every key fact is present in it)")
    for p in problems:
        print("  FAIL", *p)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
