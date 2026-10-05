# Guardrails

All guardrails are enforced in code, never by asking a small model to behave.

| ID | Name | Behaviour | Where |
|---|---|---|---|
| G1 | Off-topic | best retrieval relevance < `OFF_TOPIC_MIN_RELEVANCE` → refuse, no LLM call | orchestrator/guardrails/evidence.py |
| G2 | Insufficient history | history-seeking question with no history chunk ≥ `HISTORY_MIN_RELEVANCE` → "the history doesn't say why" | same |
| G3 | Citation enforcement | every `[ref]` in the answer must have been retrieved; invented refs are stripped and reported | guardrails/citations.py |
| G4 | Claim grounding | each sentence must be lexically supported (≥ `GROUNDING_MIN_SUPPORT`); unsupported sentences flagged | guardrails/grounding.py |
| G5 | Prompt-injection defence | commit messages/issues/comments are untrusted data: instruction-like text neutralised, evidence wrapper escaped | guardrails/injection.py |
| G6 | Secret redaction | at ingest and on model output | shared/secrets_redact.py |
| G7 | Input limits | github.com allow-list, question length, rate limit, optional API key | gateway |
| G8 | Repo isolation | queries scoped to one repo; per-repo store | rag |
| G9 | Webhook authenticity | HMAC-SHA256 over raw body; disabled with no secret | ingest/gateway |
| G10 | Request safety | refuse secret-exfiltration, command-execution and prompt-override requests before any retrieval | guardrails/safety.py |

## Calibration
G1/G2 are picked by `scripts/calibrate_thresholds.py` on the **dev** split only, so the held-out **test** split stays untouched. Re-run it whenever `EMBEDDING_BACKEND`/`EMBEDDING_MODEL` changes and record the result in `docs/EVALUATION.md`.

## Known weaknesses
G4 is a lexical heuristic that has not yet been validated against human labels. G10 uses deliberately narrow patterns (legitimate questions like "why was the API key moved?" must pass), so it is not a complete defence on its own — G5/G6 are the backstops.
