#!/usr/bin/env python3
"""Mine CANDIDATE evaluation questions from a real GitHub repo's high-signal events.

    python scripts/mine_questions.py owner/repo --out reports/candidates_owner_repo.json [--limit 60]

Sources (merged PRs only): PRs that close an issue, reverts, security/bug fixes, PRs with review discussion.
Output is a draft. A HUMAN must, for every item: read the evidence, write `gold_answer` and `key_facts`
(alternative phrasings per fact), confirm/edit `gold_evidence`, then set `verified: true`. Unverified items
must never enter the evaluation dataset. Assign `split` (dev/test) BEFORE running any model on the items,
and do not tune prompts or thresholds on `test` items (contamination control).

Uses GITHUB_TOKEN from the environment if set (never printed); unauthenticated works for ~20 PRs/hour.
"""
import argparse
import json
import os
import re
import sys

import httpx

CLOSES = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+(?:[\w.-]+/[\w.-]+)?#(\d+)", re.I)
SECURITY = re.compile(r"\b(security|vulnerab|cve-|xss|csrf|injection|leak|secret|token)\b", re.I)
BUGFIX = re.compile(r"\b(fix|bug|regression|crash|error|incorrect|wrong)\b", re.I)


def classify(pr, closes):
    title = pr["title"]
    if title.lower().startswith("revert"):
        return "evolution", f"Why was '{title}' reverted, and what did it undo?"
    if SECURITY.search(title + " " + (pr.get("body") or "")):
        return "design_rationale", f"What problem motivated the change in PR #{pr['number']} ('{title}'), and why was it addressed this way?"
    if closes and BUGFIX.search(title):
        return "bug_origin", f"What bug did PR #{pr['number']} ('{title}') fix, and where was it reported?"
    if closes:
        return "issue_linkage", f"Which issue did PR #{pr['number']} ('{title}') close, and what was the reason for it?"
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", help="owner/repo")
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--pages", type=int, default=2)
    a = ap.parse_args()

    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    cands = []
    with httpx.Client(base_url="https://api.github.com", headers=headers, timeout=30) as c:
        for page in range(1, a.pages + 1):
            r = c.get(f"/repos/{a.repo}/pulls", params={"state": "closed", "per_page": 50, "page": page, "sort": "updated", "direction": "desc"})
            if r.status_code in (403, 429):
                print("rate limited; set GITHUB_TOKEN or retry later", file=sys.stderr)
                break
            r.raise_for_status()
            for pr in r.json():
                if not pr.get("merged_at"):
                    continue
                closes = sorted({int(n) for n in CLOSES.findall((pr.get("body") or "") + " " + pr["title"])})
                category, question = classify(pr, closes)
                if not category:
                    continue
                refs = [f"pr:#{pr['number']}"] + [f"issue:#{n}" for n in closes] + [f"commit:{pr['merge_commit_sha'][:7]}"] * bool(pr.get("merge_commit_sha"))
                cands.append({
                    "id": f"{a.repo.replace('/', '_')}_pr{pr['number']}", "category": category, "question": question, "expect": "answer",
                    "gold_evidence": refs, "gold_answer": "", "key_facts": [], "split": None, "verified": False,
                    "source_url": pr["html_url"], "needs_human": ["gold_answer", "key_facts", "verify gold_evidence", "split"],
                })
                if len(cands) >= a.limit:
                    break
            if len(cands) >= a.limit:
                break
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    json.dump({"repo": a.repo, "candidates": cands}, open(a.out, "w", encoding="utf-8"), indent=1)
    by = {}
    for x in cands:
        by[x["category"]] = by.get(x["category"], 0) + 1
    print(f"{len(cands)} candidates -> {a.out}  {by}")


if __name__ == "__main__":
    main()
