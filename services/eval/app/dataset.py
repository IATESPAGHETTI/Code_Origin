"""Evaluation datasets: validated JSON with a content hash recorded in every run."""
import hashlib
import json
import os

CATEGORIES = {
    "design_rationale": "history", "bug_origin": "history", "change_attribution": "history",
    "issue_linkage": "history", "evolution": "history",
    "current_state": "control",
    "unanswerable": "guardrail", "off_topic": "guardrail", "adversarial": "guardrail",
}
EXPECT = ("answer", "refuse")


class DatasetError(ValueError):
    pass


def validate(data):
    for key in ("name", "repo", "items"):
        if key not in data:
            raise DatasetError(f"dataset missing '{key}'")
    seen = set()
    for it in data["items"]:
        for key in ("id", "category", "question", "expect"):
            if key not in it:
                raise DatasetError(f"item {it.get('id', '?')} missing '{key}'")
        if it["id"] in seen:
            raise DatasetError(f"duplicate item id {it['id']}")
        seen.add(it["id"])
        if it["category"] not in CATEGORIES:
            raise DatasetError(f"item {it['id']}: unknown category {it['category']}")
        if it["expect"] not in EXPECT:
            raise DatasetError(f"item {it['id']}: expect must be one of {EXPECT}")
        if it["expect"] == "answer" and not it.get("key_facts"):
            raise DatasetError(f"item {it['id']}: answerable items need key_facts")
        it.setdefault("split", "dev")
        it.setdefault("gold_evidence", [])
        it.setdefault("gold_answer", "")
    return data


def content_hash(data):
    canonical = json.dumps(data["items"], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def load(path):
    with open(path, encoding="utf-8") as fh:
        data = validate(json.load(fh))
    data["hash"] = content_hash(data)
    return data


def list_datasets(directory):
    out = []
    if not os.path.isdir(directory):
        return out
    for name in sorted(os.listdir(directory)):
        if name.endswith(".json") and not name.endswith(".shas.json"):
            try:
                d = load(os.path.join(directory, name))
            except (DatasetError, ValueError, KeyError):
                continue
            out.append({"file": name, "name": d["name"], "repo": d["repo"], "items": len(d["items"]), "hash": d["hash"]})
    return out


def select(data, split=None, limit=None, categories=None):
    items = [i for i in data["items"] if (not split or split == "all" or i["split"] == split)
             and (not categories or i["category"] in categories)]
    return items[:limit] if limit else items
