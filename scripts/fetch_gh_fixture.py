#!/usr/bin/env python3
"""Snapshot a GitHub repo's issues, PRs, reviews and releases into the ingest fixture format, using the `gh` CLI.

    python scripts/fetch_gh_fixture.py pallets/itsdangerous demo-data/itsdangerous_fixtures.json

Why: unauthenticated GitHub API access is limited to 60 requests/hour, which cuts a real ingest short. `gh` is
already authenticated on this machine (this script never reads or prints the token). The output is the same normalised
shape `services/ingest/app/github_api.py` produces, so ingest can load it with `issues_file`. A snapshot also makes
the evaluation reproducible: the evidence cannot change between runs.

Pull requests that are pure noise (bot version bumps, pre-commit autoupdates, spam) are kept as records but their
comments and reviews are not fetched, to save API calls.
"""
import json
import re
import subprocess
import sys

NOISE = re.compile(r"^(bump |\[pre-commit\.ci\]|ai junk|ai spam|reject|<spam>)", re.I)


def gh(path, paginate=True):
    cmd = ["gh", "api", path] + (["--paginate"] if paginate else [])
    out = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding="utf-8").stdout
    # --paginate concatenates JSON arrays: ][ -> ,
    return json.loads(re.sub(r"\]\s*\[", ",", out)) if out.strip() else []


def user(u):
    return (u or {}).get("login", "ghost")


def comments(repo, n):
    return [{"author": user(c.get("user")), "body": c.get("body") or "", "created_at": c.get("created_at")}
            for c in gh(f"repos/{repo}/issues/{n}/comments?per_page=100")]


def main(repo, out):
    issues, pulls = [], []
    for it in gh(f"repos/{repo}/issues?state=all&per_page=100"):
        if "pull_request" in it:
            continue
        issues.append({
            "number": it["number"], "title": it.get("title") or "", "body": it.get("body") or "", "state": it.get("state"),
            "author": user(it.get("user")), "labels": [lb["name"] for lb in it.get("labels", [])],
            "created_at": it.get("created_at"), "updated_at": it.get("updated_at"), "url": it.get("html_url"),
            "comments": comments(repo, it["number"]) if it.get("comments") else [],
        })
    for pr in gh(f"repos/{repo}/pulls?state=all&per_page=100"):
        n = pr["number"]
        noisy = bool(NOISE.match(pr.get("title") or "")) or user(pr.get("user")).endswith("[bot]")
        pulls.append({
            "number": n, "title": pr.get("title") or "", "body": pr.get("body") or "", "state": pr.get("state"),
            "merged": bool(pr.get("merged_at")), "author": user(pr.get("user")),
            "labels": [lb["name"] for lb in pr.get("labels", [])],
            "created_at": pr.get("created_at"), "updated_at": pr.get("updated_at"),
            "merge_commit_sha": pr.get("merge_commit_sha"), "url": pr.get("html_url"),
            "comments": [] if noisy else comments(repo, n),
            "review_comments": [] if noisy else [{"author": user(c.get("user")), "path": c.get("path"), "body": c.get("body") or ""}
                                                 for c in gh(f"repos/{repo}/pulls/{n}/comments?per_page=100")],
            "reviews": [] if noisy else [{"author": user(r.get("user")), "state": r.get("state"), "body": r.get("body") or ""}
                                         for r in gh(f"repos/{repo}/pulls/{n}/reviews?per_page=100")],
        })
    releases = [{"tag": r["tag_name"], "name": r.get("name"), "body": r.get("body") or "", "date": r.get("published_at"), "url": r.get("html_url")}
                for r in gh(f"repos/{repo}/releases?per_page=100")]
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"repo": repo, "issues": issues, "pulls": pulls, "releases": releases}, fh, indent=1, ensure_ascii=False)
    print(f"{repo}: {len(issues)} issues, {len(pulls)} pulls, {len(releases)} releases -> {out}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
