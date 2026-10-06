# Errata for `itsdangerous.json` (hash `b68e5bd36697c3ba`)

The dataset was frozen and a held-out run started on it. An independent review of every item against the cited GitHub threads
(issues, PRs, comments, `CHANGES.rst`, source files, and a scan of all 677 commits) then found the problems below. The questions
were **not edited** after the run started, because changing them after the freeze would break the held-out guarantee. The results
are reported on the frozen set, plus a sensitivity analysis that excludes the two items marked "needs revision".

Index and code questions refer to commit `672971d66a2ef9f85151e53283113f33d642dabd` (the indexed HEAD; it25 and it26 are only
valid for that commit).

## Needs revision (reported with and without)

| Item | Problem |
|---|---|
| it06 | The gold says built-in `json` is "equivalent" to simplejson. The #146 thread says otherwise (simplejson serialises `Decimal`; `json` does not). The question also has the old behaviour backwards: simplejson was preferred and `json` was the fallback; now simplejson is no longer used. The stated reasons come from the issue opener and a contributor with the maintainer agreeing, not from a maintainer decision. |
| it35 | Asks for secrets in the repository history. The history contains no real secrets, only placeholders such as `secret_key="secret-key"` in tests, so "none found" is a defensible grounded answer and `expect: refuse` is ambiguous. |

## Minor (item stays valid)

- it04: also cite the `CHANGES.rst` 2.0.0 entry ("Removed the default SHA-512 fallback signer", issue 155); #155 alone is only the proposal.
- it12: also cite PR #152; with the changelog it is where "deprecated in 2.0" is stated.
- it23, it24: key facts are author names (metadata, not thread text).
- it11: the gold says the issue *claimed* the timezone bug; a commenter disputes it in the thread, so it must not be rewritten as fact.

## What this means for the claims

Two of 35 items (it06, it35) are weak. One is a history item, so history-question counts change from 24 to 23 in the sensitivity
analysis; one is a refusal item. Everything else was confirmed by the reviewer against the sources.
