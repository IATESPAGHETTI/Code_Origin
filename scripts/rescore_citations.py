#!/usr/bin/env python3
"""Offline check of how much the evidence-wrapper citation fix changes a finished run (no LLM, no services).

    python scripts/rescore_citations.py reports/dev_full_3models.json

Old runs stored the answers the models wrote. Some models copy the evidence wrapper (`[evidence ref="doc:x" type="doc"]`)
instead of `[doc:x]`; before the fix the citation check ignored that form. This re-applies the fixed parsing to the stored
answers (validating refs against the sources that were actually offered) and reports citation counts before and after,
per model and mode. Correctness (key-fact matching) does not depend on citations and is not touched.
"""
import collections
import json
import re
import sys

WRAPPER = re.compile(r"""[\[<]\s*evidence\s+ref\s*=\s*["']([^"']+)["'][^\]>]*[\]>]""", re.I)


def norm(ref):
    return ref.strip().lower().replace("#", "")


def main(path):
    results = json.load(open(path, encoding="utf-8"))["results"]
    before = collections.Counter()
    after = collections.Counter()
    n = collections.Counter()
    changed = []
    for r in results:
        resp = r.get("response")
        if not resp or r["mode"] == "no_context":
            continue
        key = (r["model"], r["mode"])
        n[key] += 1
        offered = {norm(s["ref"]) for s in resp.get("sources", [])}
        old = len(resp.get("citations", []))
        found = {norm(m) for m in WRAPPER.findall(resp.get("answer") or "")}
        new = old + len([f for f in found if f in offered and f not in {norm(c["ref"]) for c in resp.get("citations", [])}])
        before[key] += old > 0
        after[key] += new > 0
        if new != old:
            changed.append((r["item_id"], r["model"], r["mode"], old, new))
    print(f"{'model':<16}{'mode':<14}{'answers':>8}{'cited before':>14}{'cited after':>13}")
    for key in sorted(n):
        print(f"{key[0]:<16}{key[1]:<14}{n[key]:>8}{before[key]:>14}{after[key]:>13}")
    print(f"\nanswers whose citation count changed: {len(changed)} of {sum(n.values())}")
    for c in changed:
        print("  ", c)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "reports/dev_full_3models.json")
