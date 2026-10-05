from app import git_ops, parsers
from app.links import build_graph, mentioned_numbers, short_sha
from app.secrets_redact import redact


def test_mentioned_numbers_ignores_urls_and_words():
    assert mentioned_numbers("fixes #7 and refs #22, see http://x/y#12 and a#3b") == {7, 22}


def test_graph_links_commit_pr_issue_both_directions():
    commits = [{"sha": "69e7bbd0" * 5, "subject": "Replace cookies (fixes #7)", "body": ""}]
    issues = [{"number": 7, "title": "t", "body": ""}]
    prs = [{"number": 8, "title": "JWT", "body": "Fixes #7", "merge_commit_sha": "69e7bbd0" * 5}]
    g = build_graph(commits, issues, prs)
    assert set(g.links("commit:69e7bbd")) == {"issue:#7", "pr:#8"}
    assert set(g.links("issue:#7")) == {"commit:69e7bbd", "pr:#8"}
    assert "pr:#8" in g.links("commit:69e7bbd")


def test_unknown_numbers_are_dropped():
    g = build_graph([{"sha": "a" * 40, "subject": "see #99", "body": ""}], [], [])
    assert g.links("commit:aaaaaaa") == []


def test_python_code_chunked_by_function(tmp_path):
    src = "import os\n\n\ndef a():\n    return 1\n\n\nclass B:\n    def m(self):\n        return 2\n"
    chunks = parsers.code_chunks("r", "", "pkg/mod.py", src)
    symbols = {c["metadata"]["symbol"] for c in chunks}
    assert symbols == {"a", "B", "module"}
    assert all(c["ref"] == "code:pkg/mod.py" and c["id"].startswith("code:pkg/mod.py#L") for c in chunks)


def test_non_python_code_uses_windows():
    text = "\n".join(f"line {i}" for i in range(150))
    chunks = parsers.code_chunks("r", "", "a.js", text)
    assert len(chunks) >= 3 and chunks[0]["metadata"]["start_line"] == 1


def test_syntax_error_python_falls_back_to_windows():
    assert parsers.code_chunks("r", "", "bad.py", "def (:\n  nope\n" * 5)


def test_doc_chunks_split_on_headings():
    md = "# Title\nintro\n\n## Part A\nalpha text\n\n## Part B\nbeta text\n"
    chunks = parsers.doc_chunks("r", "", "docs/x.md", md)
    assert len(chunks) == 3 and chunks[1]["metadata"]["title"] == "Part A"


def test_long_issue_is_split_with_stable_ids():
    issue = {"number": 5, "title": "T", "body": "word " * 1500, "state": "open", "author": "a",
             "created_at": "2024-01-01T00:00:00Z", "comments": [{"author": "b", "body": "hi"}]}
    chunks = parsers.issue_chunks("r", "", issue, ["pr:#6"])
    assert len(chunks) > 1 and chunks[0]["id"] == "issue:#5#0" and all(c["ref"] == "issue:#5" for c in chunks)
    assert chunks[0]["metadata"]["links"] == ["pr:#6"]


def test_pr_produces_pr_and_review_chunks():
    pr = {"number": 8, "title": "JWT", "body": "b", "state": "closed", "merged": True, "author": "a",
          "created_at": "2023-04-18T00:00:00Z", "reviews": [{"author": "bob", "state": "COMMENTED", "body": "why HS256?"}],
          "review_comments": [{"author": "alice", "path": "src/auth.py", "body": "single service"}]}
    chunks = parsers.pr_chunks("r", "", pr, [])
    kinds = {c["source_type"] for c in chunks}
    assert kinds == {"pr", "review"} and all(c["ref"] == "pr:#8" for c in chunks)
    assert "single service" in next(c for c in chunks if c["source_type"] == "review")["text"]


def test_demo_history_is_readable(demo):
    commits = git_ops.list_commits(demo["repo"])
    assert len(commits) == 13 and commits[-1]["subject"] == "Initial project skeleton"
    jwt = next(c for c in commits if c["sha"] == demo["shas"]["jwt"])
    assert "Session fixation" in jwt["body"] and jwt["author"] == "Alice Moreau"
    assert [c["sha"] for c in git_ops.list_commits(demo["repo"], since_sha=demo["shas"]["env"])] == [demo["shas"]["poison"], demo["shas"]["ttl"]]


def test_numstat_and_diff_sections(demo):
    files = git_ops.commit_numstat(demo["repo"], demo["shas"]["ratelimit"])
    assert {f["path"] for f in files} == {"src/ratelimit.py", "src/auth.py"}
    sections = git_ops.commit_diff_sections(demo["repo"], demo["shas"]["ratelimit"])
    assert {n for n, _ in sections} == {"src/ratelimit.py", "src/auth.py"}
    chunks = parsers.diff_chunks("r", "", {"sha": demo["shas"]["ratelimit"], "subject": "s", "author": "a", "date": "d"}, sections, [])
    assert chunks and all(c["ref"] == f"commit:{short_sha(demo['shas']['ratelimit'])}" for c in chunks)


def test_iter_files_skips_noise(demo):
    names = {rel for rel, _ in git_ops.iter_files(demo["repo"])}
    assert "src/auth.py" in names and "README.md" in names and not any(n.endswith(".lock") for n in names)


def test_leaked_key_is_in_history_but_redacted():
    sections = [("src/config.py", '+GATEWAY_API_KEY = "pk_live_51HqXzTzabcdefghijklmnop"\n')]
    text, n = redact(sections[0][1])
    assert n == 1 and "pk_live" not in text


def test_token_never_leaks_into_git_errors(tmp_path):
    import pytest
    with pytest.raises(git_ops.GitError) as e:
        git_ops.run_git(["clone", "--quiet", str(tmp_path / "does-not-exist"), str(tmp_path / "x")], token="ghp_SECRETSECRET")
    assert "SECRETSECRET" not in str(e.value)
