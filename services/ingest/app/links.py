"""Cross-reference graph: issue <-> PR <-> commit.

Edges come from `#123` mentions in commit messages / PR and issue bodies and
from a PR's merge commit. A retrieved commit can then pull in the issue and PR
that explain it (and vice versa), giving the LLM the full chain.
"""
import re
from collections import defaultdict

_NUM = re.compile(r"(?<![\w/&])#(\d+)\b")


def mentioned_numbers(*texts):
    out = set()
    for t in texts:
        out.update(int(n) for n in _NUM.findall(t or ""))
    return out


class LinkGraph:
    def __init__(self):
        self._edges = defaultdict(set)

    def add(self, a, b):
        if a and b and a != b:
            self._edges[a].add(b)
            self._edges[b].add(a)

    def links(self, ref):
        return sorted(self._edges.get(ref, ()))

    def edge_count(self):
        return sum(len(v) for v in self._edges.values()) // 2


def short_sha(sha):
    return (sha or "")[:7]


def build_graph(commits, issues, prs):
    """commits: [{sha, subject, body}], issues/prs: normalised dicts."""
    pr_nums = {p["number"] for p in prs}
    issue_nums = {i["number"] for i in issues}

    def resolve(n):
        if n in pr_nums:
            return f"pr:#{n}"
        if n in issue_nums:
            return f"issue:#{n}"
        return None

    g = LinkGraph()
    for c in commits:
        ref = f"commit:{short_sha(c['sha'])}"
        for n in mentioned_numbers(c.get("subject"), c.get("body")):
            g.add(ref, resolve(n))
    for p in prs:
        ref = f"pr:#{p['number']}"
        for n in mentioned_numbers(p.get("title"), p.get("body")):
            if n != p["number"]:
                g.add(ref, resolve(n))
        if p.get("merge_commit_sha"):
            g.add(ref, f"commit:{short_sha(p['merge_commit_sha'])}")
    for i in issues:
        ref = f"issue:#{i['number']}"
        for n in mentioned_numbers(i.get("body")):
            if n != i["number"]:
                g.add(ref, resolve(n))
    return g
