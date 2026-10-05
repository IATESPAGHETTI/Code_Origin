"""GitHub REST client: paginated, rate-limit aware, and normalising.

Also supports an offline JSON fixture with the same normalised shape so the
whole pipeline can be exercised (tests, CI, seeded demo repo) without network.
"""
import json
import time

import httpx

API = "https://api.github.com"


class RateLimited(RuntimeError):
    pass


class GitHubClient:
    def __init__(self, token=None, base=API, transport=None, max_wait=90.0, sleep=time.sleep, clock=time.time):
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
                   "User-Agent": "codeorigin-ingest"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self.http = httpx.Client(base_url=base, headers=headers, timeout=30.0, transport=transport)
        self.max_wait, self.sleep, self.clock = max_wait, sleep, clock
        self.calls = 0
        self.rate_remaining = None

    # -------------------------------------------------------------- plumbing
    def _get(self, url, params=None):
        for attempt in range(4):
            resp = self.http.get(url, params=params)
            self.calls += 1
            remaining = resp.headers.get("X-RateLimit-Remaining")
            if remaining is not None:
                self.rate_remaining = int(remaining)
            limited = resp.status_code == 429 or (resp.status_code == 403 and remaining == "0")
            if not limited:
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp
            wait = None
            if resp.headers.get("Retry-After"):
                wait = float(resp.headers["Retry-After"])
            elif resp.headers.get("X-RateLimit-Reset"):
                wait = max(0.0, float(resp.headers["X-RateLimit-Reset"]) - self.clock()) + 1
            wait = 5.0 if wait is None else wait
            if wait > self.max_wait or attempt == 3:
                raise RateLimited(f"GitHub rate limit hit; resets in {wait:.0f}s (set GITHUB_TOKEN for a higher limit)")
            self.sleep(wait)
        raise RateLimited("GitHub rate limit retries exhausted")

    def paginate(self, url, params=None, limit=1000):
        params = dict(params or {})
        params.setdefault("per_page", 100)
        out = []
        while url and len(out) < limit:
            resp = self._get(url, params)
            if resp is None:
                break
            data = resp.json()
            out.extend(data if isinstance(data, list) else [])
            nxt = resp.links.get("next", {}).get("url")
            url, params = nxt, None
        return out[:limit]

    # ------------------------------------------------------------- normalisers
    @staticmethod
    def _user(obj):
        return (obj or {}).get("login") or "unknown"

    def _comments(self, url, limit=60):
        return [
            {"author": self._user(c.get("user")), "body": c.get("body") or "", "created_at": c.get("created_at")}
            for c in self.paginate(url, limit=limit)
        ]

    # ---------------------------------------------------------------- endpoints
    def issues(self, owner, repo, since=None, limit=300):
        params = {"state": "all", "sort": "updated", "direction": "desc"}
        if since:
            params["since"] = since
        out = []
        for it in self.paginate(f"/repos/{owner}/{repo}/issues", params, limit=limit * 2):
            if "pull_request" in it:
                continue
            comments = self._comments(it["comments_url"]) if it.get("comments") else []
            out.append({
                "number": it["number"], "title": it.get("title") or "", "body": it.get("body") or "",
                "state": it.get("state"), "author": self._user(it.get("user")),
                "labels": [lb["name"] for lb in it.get("labels", []) if isinstance(lb, dict)],
                "created_at": it.get("created_at"), "updated_at": it.get("updated_at"),
                "url": it.get("html_url"), "comments": comments,
            })
            if len(out) >= limit:
                break
        return out

    def pulls(self, owner, repo, since=None, limit=200):
        params = {"state": "all", "sort": "updated", "direction": "desc"}
        out = []
        for pr in self.paginate(f"/repos/{owner}/{repo}/pulls", params, limit=limit * 2):
            if since and (pr.get("updated_at") or "") < since:
                break
            n = pr["number"]
            out.append({
                "number": n, "title": pr.get("title") or "", "body": pr.get("body") or "",
                "state": pr.get("state"), "merged": bool(pr.get("merged_at")),
                "author": self._user(pr.get("user")),
                "labels": [lb["name"] for lb in pr.get("labels", []) if isinstance(lb, dict)],
                "created_at": pr.get("created_at"), "updated_at": pr.get("updated_at"),
                "merge_commit_sha": pr.get("merge_commit_sha"), "url": pr.get("html_url"),
                "comments": self._comments(f"/repos/{owner}/{repo}/issues/{n}/comments"),
                "review_comments": [
                    {"author": self._user(c.get("user")), "path": c.get("path"), "body": c.get("body") or ""}
                    for c in self.paginate(f"/repos/{owner}/{repo}/pulls/{n}/comments", limit=60)
                ],
                "reviews": [
                    {"author": self._user(r.get("user")), "state": r.get("state"), "body": r.get("body") or ""}
                    for r in self.paginate(f"/repos/{owner}/{repo}/pulls/{n}/reviews", limit=30)
                ],
            })
            if len(out) >= limit:
                break
        return out

    def releases(self, owner, repo, limit=50):
        return [
            {"tag": r["tag_name"], "name": r.get("name"), "body": r.get("body") or "",
             "date": r.get("published_at"), "url": r.get("html_url")}
            for r in self.paginate(f"/repos/{owner}/{repo}/releases", limit=limit)
        ]

    def close(self):
        self.http.close()


def load_fixture(path):
    """Offline stand-in for the API: {'issues': [...], 'pulls': [...], 'releases': [...]}
    in the same normalised shape the client above produces."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return {"issues": data.get("issues", []), "pulls": data.get("pulls", []), "releases": data.get("releases", [])}
