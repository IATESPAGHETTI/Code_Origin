"""Turn repository artifacts into retrieval chunks.

chunk = {id, ref, source_type, text, metadata}
ids are deterministic so re-ingesting is idempotent (upsert, no duplicates).
"""
import ast
import re

from .links import short_sha

MAX_CHUNK = 1800


def _split_text(text, limit=MAX_CHUNK):
    """Split on paragraph boundaries, hard-wrapping oversize paragraphs."""
    parts, cur = [], ""
    for para in re.split(r"\n\s*\n", text.strip()):
        while len(para) > limit:
            if cur:
                parts.append(cur)
                cur = ""
            parts.append(para[:limit])
            para = para[limit:]
        if len(cur) + len(para) + 2 > limit and cur:
            parts.append(cur)
            cur = para
        else:
            cur = f"{cur}\n\n{para}" if cur else para
    if cur.strip():
        parts.append(cur)
    return parts or [""]


def _meta(repo, source_type, ref, links, **kw):
    m = {"repo": repo, "source_type": source_type, "ref": ref, "links": list(links or [])}
    m.update({k: v for k, v in kw.items() if v is not None})
    return m


def _web(base, kind, ident):
    if not base:
        return ""
    return f"{base}/{kind}/{ident}"


# ------------------------------------------------------------------ commits
def commit_chunk(repo, base_url, c, files, links):
    short = short_sha(c["sha"])
    ref = f"commit:{short}"
    flist = ", ".join(f"{f['path']} (+{f['added']}/-{f['deleted']})" for f in files[:25])
    more = f", ... and {len(files) - 25} more files" if len(files) > 25 else ""
    text = (
        f"Commit {short} by {c['author']} on {c['date'][:10]}\n"
        f"{c['subject']}\n\n{c['body']}\n\nFiles changed: {flist}{more}"
    ).strip()
    return {
        "id": f"{ref}#msg", "ref": ref, "source_type": "commit", "text": text,
        "metadata": _meta(repo, "commit", ref, links, sha=c["sha"], author=c["author"], date=c["date"],
                          title=c["subject"], url=_web(base_url, "commit", c["sha"]),
                          path=files[0]["path"] if len(files) == 1 else None),
    }


def _hunk_parts(diff_text, limit=MAX_CHUNK):
    """Split a file diff on hunk boundaries into <= limit-sized parts."""
    head, *hunks = re.split(r"(?m)^(?=@@ )", diff_text)
    parts, cur = [], head
    for h in hunks:
        if len(cur) + len(h) > limit and cur.strip() != head.strip():
            parts.append(cur)
            cur = head + h
        else:
            cur += h
    parts.append(cur)
    out = []
    for p in parts:
        out.extend([p[i:i + limit] for i in range(0, len(p), limit)] or [p])
    return out


def diff_chunks(repo, base_url, c, sections, links, max_files=12, max_parts=4):
    short = short_sha(c["sha"])
    ref = f"commit:{short}"
    chunks = []
    for name, diff in sections[:max_files]:
        for i, part in enumerate(_hunk_parts(diff)[:max_parts]):
            chunks.append({
                "id": f"{ref}#diff:{name}:{i}", "ref": ref, "source_type": "diff",
                "text": f"Diff for commit {short} ({c['subject']}) in {name}:\n{part}",
                "metadata": _meta(repo, "diff", ref, links, sha=c["sha"], author=c["author"], date=c["date"],
                                  title=c["subject"], path=name, url=_web(base_url, "commit", c["sha"])),
            })
    return chunks


# ------------------------------------------------------------- issues / PRs
def _comments_block(comments):
    return "\n".join(f"- {c.get('author', '?')}: {c.get('body', '').strip()}" for c in comments if c.get("body"))


def issue_chunks(repo, base_url, issue, links):
    ref = f"issue:#{issue['number']}"
    labels = ", ".join(issue.get("labels") or []) or "none"
    body = (
        f"Issue #{issue['number']}: {issue['title']}\n"
        f"State: {issue.get('state', '?')}; labels: {labels}; opened by {issue.get('author', '?')} "
        f"on {str(issue.get('created_at', ''))[:10]}\n\n{issue.get('body') or ''}"
    )
    cm = _comments_block(issue.get("comments") or [])
    if cm:
        body += f"\n\nDiscussion:\n{cm}"
    return [
        {"id": f"{ref}#{i}", "ref": ref, "source_type": "issue", "text": part,
         "metadata": _meta(repo, "issue", ref, links, number=issue["number"], author=issue.get("author"),
                           date=issue.get("created_at"), title=issue["title"],
                           url=issue.get("url") or _web(base_url, "issues", issue["number"]))}
        for i, part in enumerate(_split_text(body))
    ]


def pr_chunks(repo, base_url, pr, links):
    ref = f"pr:#{pr['number']}"
    state = "merged" if pr.get("merged") else pr.get("state", "?")
    body = (
        f"Pull request #{pr['number']}: {pr['title']}\n"
        f"State: {state}; opened by {pr.get('author', '?')} on {str(pr.get('created_at', ''))[:10]}\n\n"
        f"{pr.get('body') or ''}"
    )
    cm = _comments_block(pr.get("comments") or [])
    if cm:
        body += f"\n\nDiscussion:\n{cm}"
    url = pr.get("url") or _web(base_url, "pull", pr["number"])
    chunks = [
        {"id": f"{ref}#{i}", "ref": ref, "source_type": "pr", "text": part,
         "metadata": _meta(repo, "pr", ref, links, number=pr["number"], author=pr.get("author"),
                           date=pr.get("created_at"), title=pr["title"], url=url)}
        for i, part in enumerate(_split_text(body))
    ]
    review_lines = [f"- {r.get('author', '?')} ({r.get('state', 'COMMENTED')}): {r.get('body', '').strip()}"
                    for r in pr.get("reviews") or [] if r.get("body")]
    review_lines += [f"- {r.get('author', '?')} on {r.get('path', '?')}: {r.get('body', '').strip()}"
                     for r in pr.get("review_comments") or [] if r.get("body")]
    if review_lines:
        text = f"Code review of PR #{pr['number']} ({pr['title']}):\n" + "\n".join(review_lines)
        for i, part in enumerate(_split_text(text)):
            chunks.append({
                "id": f"{ref}#review{i}", "ref": ref, "source_type": "review", "text": part,
                "metadata": _meta(repo, "review", ref, links, number=pr["number"], title=pr["title"],
                                  date=pr.get("created_at"), url=url)})
    return chunks


def release_chunk(repo, base_url, rel):
    ref = f"release:{rel['tag']}"
    text = f"Release {rel['tag']} ({rel.get('name') or ''}) published {str(rel.get('date', ''))[:10]}\n\n{rel.get('body') or ''}"
    return {"id": f"{ref}#0", "ref": ref, "source_type": "release", "text": text.strip(),
            "metadata": _meta(repo, "release", ref, [], title=rel.get("name") or rel["tag"],
                              date=rel.get("date"), url=rel.get("url") or "")}


# ------------------------------------------------------------- code & docs
def _py_chunks(rel, text):
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return None
    lines = text.splitlines()
    spans = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            spans.append((start, node.end_lineno, node.name))
    if not spans:
        return None
    out, covered = [], set()
    for start, end, name in spans:
        covered.update(range(start, end + 1))
        out.append((start, end, name))
    rest = [i for i in range(1, len(lines) + 1) if i not in covered and lines[i - 1].strip()]
    if rest:
        out.append((rest[0], rest[-1], "module"))
    return sorted(out), lines


def _windows(n_lines, size=60, overlap=10):
    start = 1
    while start <= n_lines:
        end = min(n_lines, start + size - 1)
        yield start, end, None
        if end == n_lines:
            break
        start = end - overlap + 1


def code_chunks(repo, base_url, rel, text, ref_name=None):
    ref = f"code:{rel}"
    spans = None
    lines = text.splitlines()
    if rel.endswith(".py"):
        parsed = _py_chunks(rel, text)
        if parsed:
            spans, lines = parsed
    if spans is None:
        spans = list(_windows(len(lines)))
    chunks = []
    for start, end, name in spans:
        if name == "module" or (end - start) > 120:
            pieces = [(s + start - 1, min(e + start - 1, end), name) for s, e, _ in _windows(end - start + 1)]
        else:
            pieces = [(start, end, name)]
        for s, e, n in pieces:
            body = "\n".join(lines[s - 1:e])
            if not body.strip():
                continue
            label = f" ({n})" if n else ""
            chunks.append({
                "id": f"{ref}#L{s}-{e}", "ref": ref, "source_type": "code",
                "text": f"File {rel}{label} lines {s}-{e}:\n{body}",
                "metadata": _meta(repo, "code", ref, [], path=rel, start_line=s, end_line=e, symbol=n,
                                  url=_web(base_url, f"blob/{ref_name}" if ref_name else "blob/HEAD", rel)),
            })
    return chunks


def doc_chunks(repo, base_url, rel, text, ref_name=None):
    ref = f"doc:{rel}"
    sections = re.split(r"(?m)^(?=#{1,3} )", text) if rel.lower().endswith(".md") else [text]
    chunks, n = [], 0
    for sec in sections:
        if not sec.strip():
            continue
        title = sec.strip().splitlines()[0].lstrip("# ").strip()[:120]
        for part in _split_text(sec):
            chunks.append({
                "id": f"{ref}#{n}", "ref": ref, "source_type": "doc", "text": f"{rel} - {title}\n{part}",
                "metadata": _meta(repo, "doc", ref, [], path=rel, title=title,
                                  url=_web(base_url, f"blob/{ref_name}" if ref_name else "blob/HEAD", rel)),
            })
            n += 1
    return chunks
