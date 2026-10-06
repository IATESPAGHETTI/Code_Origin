# CodeOrigin — continuation brief

Hand-off document so another agent can continue without losing context. Companion to `PROJECT.md` (long-form overview). Last updated 2026-10-04. Sections 7 and 13 change most; check them first.

## 1. Project overview
CodeOrigin is a repository-aware RAG system that answers *"why was it built this way?"* from current code **and** development history (commits, diffs, issues, PRs, review comments, releases). Every claim must be cited (`commit:69e7bbd`, `issue:#7`, `pr:#8`). If the history does not say, the system abstains.

## 2. Research question
> Does incorporating repository history (commits, issues, PRs, code changes) into an LLM-RAG pipeline improve the accuracy and usefulness of software-development answers?

## 3. Experimental design (fixed — do not change casually)
| Mode | LLM sees |
|---|---|
| `no_context` | question only |
| `code_only` | question + retrieved current code/docs |
| `code_history` | question + code + commits/diffs/issues/PRs/reviews (cross-linked) |
| `oracle` | question + gold evidence, no retrieval (diagnostic: retrieval failure vs model-use failure) |

- Same prompt shape and **same context character budget** (`CONTEXT_CHAR_BUDGET`) in every mode; temperature 0, fixed seed.
- **Decision rule (pre-registered):** history is useful only if `code_history` beats `code_only` on the history categories by **>= 0.10 correctness**, the 95% bootstrap CI **excludes 0**, and the control category (`current_state`) loses **<= 0.05**.
- Paired sign-flip permutation test, Cohen's d_z, bootstrap CIs per category. No single blended score.
- Failure taxonomy per wrong answer: `retrieval_miss`, `model_ignored_evidence`, `hallucinated`, `over_refused`, `under_refused`, `no_evidence_given`.
- Models compared: `llama2`, `codellama:7b`, `starcoder2:3b`. Jury: `gemma:2b` (deliberately not a compared model).
- `dev` split is for threshold calibration/debugging; `test` split is **held out and run once** after thresholds are frozen.

## 4. Architecture
Browser -> web (React/Tailwind, nginx) -> gateway -> orchestrator -> RAG / LLM; gateway also fronts ingest and eval. SQLite for state (ingest, eval). Chroma or in-memory vectors. External: git remotes, GitHub REST API, Ollama.

## 5. Service map
| Service | Port | Role |
|---|---|---|
| gateway | 8200 | single entry: input limits (G7), rate limit, request IDs, API key, `/metrics`, webhook passthrough, SSE proxy |
| ingest | 8201 | clone/fetch, commits+diffs, GitHub issues/PRs/reviews/releases, link graph, chunk, redact, push to rag; full+incremental sync; HMAC webhooks |
| rag | 8202 | hybrid retrieval (vector + BM25, RRF), filters, link expansion; backends memory/Chroma; embedders hash/sentence-transformers |
| llm | 8203 | Ollama client + token accounting + `/judge`; `MOCK_LLM=1` for CI only |
| orchestrator | 8204 | pipeline per mode, guardrails G1-G10, cited prompt, citation validation, grounding |
| eval | 8205 | datasets, runs, metrics, stats, verdict, failure analysis, human-grade calibration, report |
| chromadb | 8206 (host) | vector store (container port 8000) |
| web | 5180 | UI: Home, Ask, Repositories, Evaluation |

`shared/` (textutil, refs, secrets_redact) is the single source of truth; `scripts/sync_shared.py` copies it into services; `--check` fails CI on drift. **Never edit the copies under `services/*/app/`.**

## 6. Current implementation
Complete and tested: ingestion (full/incremental/idempotent, deterministic chunk IDs, redaction, link graph, offline fixture mode, rate-limit handling), hybrid retrieval, citation tracking/validation, grounding, injection filtering, guardrails G1-G10, SSE streaming, evaluation harness (four modes, stats, failure taxonomy, jury, calibration), React UI. Seeded repo **Ledgerly** (13 commits, deterministic SHAs) + 43-question dataset with symbolic gold evidence (`commit@jwt` -> real SHA; `build_demo_dataset.py --check`).

Added in the continuation: `docker-compose.yml` + `dev`/`prod`/`monitoring`/`demo`/`ports` overrides, `.env.example`, `Makefile`, `monitoring/` (Prometheus, alerts, Loki, Promtail, Grafana provisioning + dashboard), `.github/workflows/{ci,release,nightly-eval}.yml`, `.gitleaks.toml`, `scripts/{compose_health,run_eval,mine_questions,grading_sheet}.py`, ruff config, frontend unit tests, README + `docs/`. Fixes: eval Dockerfile lacked `COPY datasets` and a writable `/data`; eval runner now runs the jury **after** all answers are generated (alternating answer/jury models thrashed a 6 GB GPU); new `OLLAMA_NUM_CTX` option in the llm service.

## 7. Test status
- 142 backend tests pass (rag 9, llm 12, ingest 32, orchestrator 46, eval 18, gateway 25) + 6 frontend (vitest). `ruff`, `sync_shared --check`, `build_demo_dataset --check` clean.
- Docker: all 7 images build; dev stack (mock) and real stack both reach healthy; monitoring stack verified (Prometheus scrapes gateway, Grafana dashboard provisioned, Loki receives container logs). GitHub Actions workflows are YAML-valid but **have not run on GitHub**.
- Real stack verified 2026-10-04: sentence-transformers `all-MiniLM-L6-v2` + ChromaDB 1.0 (container) + real `llama2` via host Ollama. ChromaStore is now exercised.
- Real GitHub ingest of `pallets/itsdangerous` (unauthenticated, capped): 150 commits, 9 issues, 8 PRs, 7 releases; idempotent re-sync; no response-shape problems.
- Calibration (real embedder, dev split): G1 = 0.36, G2 = 0.44 (on-topic min 0.597 vs off-topic max 0.124; answerable min 0.678 vs unanswerable max 0.205). Only 2 negatives each, so **provisional**.
- Real-model pilot (`reports/pilot_llama2_limit8.*`): llama2, dev split, first 8 items (history categories only), 4 modes, 32 answers in ~6 min, 0 errors. code_history minus code_only = +0.44 [+0.25, +0.62], n=8. **Not research evidence** (tiny n, one model, key-fact auto-scoring, no human grades, thresholds tuned on the same split). Observation: llama2 rarely writes `[ref]` citations (gold cited 0.06).
- Full DEV-split run (run 5, `reports/dev_full_3models.md/.json`): llama2, codellama:7b, starcoder2:3b x 4 modes x 23 dev items = 255 answers, 0 errors, ~21 min, real models + real embedder + Chroma, jury gemma:2b graded 191 answers. Verdicts by the pre-registered rule: llama2 "history is useful" (+0.42 [+0.15, +0.69], n=13 history items); codellama:7b inconclusive (+0.42 [+0.00, +0.73]); starcoder2:3b inconclusive (+0.08 [+0.00, +0.19], mostly hallucinated/under-instructed). Control category loses 0 for all (n=3). **Still dev-only, n=13, auto key-fact scoring, no human grades; thresholds were tuned on this split - treat as a pipeline check, not a research result.** The held-out test split has not been run.
- Run settings used for real runs (record with every result; see `docs/OPERATIONS.md`): host Ollama with `OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`, `OLLAMA_NUM_CTX=3072`. This fits llama2-7B in ~4.8 GB VRAM (~2x faster than the spilled default). The Ollama tray app restarts its own server without these variables; quit it and run `ollama serve` with them.

## 8. Evaluation framework
Dataset JSON per item: `category`, `question`, `expect` (answer|refuse), `key_facts` (alternatives per fact), `gold_evidence`, `split`. Categories: history = design_rationale, bug_origin, change_attribution, issue_linkage, evolution; control = current_state; guardrail = unanswerable, off_topic, adversarial. Per-answer metrics: correctness, evidence recall/precision, gold cited, citation validity, unsupported-claim ratio, refusal correctness, latency, tokens. Jury grading via `/judge`. Calibration: quadratic-weighted kappa + Spearman between human grades and (a) auto score, (b) jury; jury usable as headline only at kappa >= 0.6. Run: `python scripts/run_eval.py`. Human grading: `scripts/grading_sheet.py export|import|kappa` (blind, stratified sample; scores 0/1/2).

## 9. Dataset status
43 dev/test questions on Ledgerly (dev 23, test 20; 4-9 per category) — enough for development, **not** enough for a conclusion. Needed: 40+ additional questions from a **real** GitHub repo, each with human-verified gold evidence. `scripts/mine_questions.py owner/repo` drafts candidates (unverified); a human writes `gold_answer`/`key_facts`, checks `gold_evidence`, assigns the split **before** any model sees them.

## 10. Security / guardrails
G1 off-topic (no LLM call), G2 insufficient history, G3 citation enforcement, G4 lexical claim grounding, G5 prompt-injection neutralisation, G6 secret redaction (ingest + output), G7 input limits/allow-list/rate limit/API key, G8 repo isolation, G9 webhook HMAC, G10 unsafe-request refusal. Containers: non-root uid 10001, `cap_drop: ALL`, `read_only`, `no-new-privileges`. Repository content is only read, never executed. No secrets in git (`.env` ignored; gitleaks + trivy in CI).

## 11. Frontend status
React + Tailwind, Apple-style glass UI; builds and lints clean; 6 unit tests for the API/SSE client; rendered against the live stack.

## 12. Known limitations
1. No valid real-model research result exists yet (see section 7 pilot caveats). Mock-LLM results must never be cited as evidence about the hypothesis (mock is for CI only).
2. G1/G2 thresholds rest on 2 negative examples each.
3. GitHub client tested for real only unauthenticated on a small repo.
4. G4 grounding is lexical and unvalidated against humans; jury-human agreement unmeasured.
5. 43 questions -> wide CIs.
6. Speed: ~11-30 s per answer on the 6 GB GPU; a full dev run of 3 models is ~1 h, the test run similar.
7. Machine RAM is tight during runs (free RAM dips to ~0.3 GB); close heavy apps first.
8. BM25 rebuilt in memory per repo; SQLite instead of Postgres.

## 13. Remaining work
1. [x] Compose/overrides/.env.example/Makefile; images built and health-checked; CI/CD workflows written; Prometheus/Grafana/Loki verified; README/docs.
2. [x] Real embedder + Chroma + Ollama; thresholds recalibrated (provisional). [ ] Full dev run for all three models.
3. [x] Real GitHub ingest (small repo). [ ] Larger repo with a user-supplied `GITHUB_TOKEN` in `.env` (never committed) for question mining.
4. [ ] 40+ human-verified questions; held-out test run (once).
5. [ ] ~60 human-graded answers; jury-human kappa; G4 validation.
6. [ ] Failure-mode analysis; final report.
7. [ ] Push to GitHub and confirm the workflows pass (not yet run).

## 14. Priority order
Research validity > required DevOps > robustness > UI polish > optional (Discord, Kubernetes: not started).

## 15. Definition of done
- Real stack healthy; CI green on GitHub.
- Thresholds recalibrated on dev split with the real embedder and recorded (done, provisional).
- Real GitHub repo ingested; >= 40 new verified held-out questions.
- One test-split run for all three models x four modes; report with per-category CIs, effect sizes, verdict by the pre-registered rule, failure taxonomy.
- >= ~60 human-graded answers; kappa for jury and automatic score; G4 checked against human labels.
- Docs complete; limitations stated honestly, including the run settings.

## 16. Commands
```bash
python scripts/sync_shared.py --check && python scripts/build_demo_dataset.py --check
make test                                    # or: cd services/<svc> && python -m pytest -q
cp .env.example .env
# host Ollama with the run settings (quit the Ollama tray app first):
#   OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0 ollama serve
docker compose -f docker-compose.yml -f docker-compose.demo.yml -f docker-compose.ports.yml up -d
python scripts/compose_health.py
MSYS_NO_PATHCONV=1 python scripts/seed_demo.py --container-path /demo   # Git Bash needs the env var
python scripts/calibrate_thresholds.py                                   # dev split only
python scripts/run_eval.py --repo local__repo --split dev --models llama2 --limit 8 --out reports/pilot
python scripts/grading_sheet.py export --run <id> --n 60
```
Environment notes: Windows + Git Bash (set `MSYS_NO_PATHCONV=1` for container paths; write files with the file tools, not Python heredocs, because cp1252 encoding can truncate files). `docker compose up -d --build` sometimes keeps the old container: use `build` then `up -d --force-recreate --no-deps <svc>`. Host Ollama has llama2, codellama:7b, starcoder2:3b, gemma:2b, deepseek-coder:6.7b; RTX 3060 6 GB (one 7B model at a time). Monitoring containers stay off during runs to save RAM.

## 17. Decisions that must NOT be changed casually
- The four modes, equal context budget, temperature 0/fixed seed, and the pre-registered decision rule.
- Per-category reporting with bootstrap CIs; no blended headline score.
- `dev`/`test` split discipline: thresholds tuned on dev only; test run once.
- Jury model must not be one of the compared models.
- Guardrails enforced in code, not by prompting.
- Redaction before indexing; repo isolation; no execution of repository content.
- Deterministic chunk IDs and the symbolic-gold -> SHA resolution.
- `shared/` as the only source for shared modules.
- Ports (8200-8206, 5180).
- Run settings (context size, KV-cache type) must be recorded and identical across all modes and models within a result set.

## 18. GitHub and CI status (2026-10-05)
- Repository: https://github.com/IATESPAGHETTI/Code_Origin (branch `main`). It contains only the CodeOrigin folder, so `.github/workflows` is at the repo root.
- CI (`.github/workflows/ci.yml`) was run on GitHub and is green: lint + drift checks (ruff pinned to 0.15.9), 6 per-service test jobs, frontend lint/test/build, gitleaks, Trivy (HIGH/CRITICAL, fixable only), compose smoke (dev stack, seeded repo, an `/api/ask` with citations), and the end-to-end smoke test.
- Problems found and fixed by running it for real: wrong Trivy action tag, ruff default rules changing between versions, a wrong `make_demo_repo.py` invocation, a HIGH CVE in `react-router-dom` (now 6.30.6), and frontend Dockerfiles running as root (now non-root).
- Known quirk: after a force-push, the gitleaks action fails once ("unknown revision") because the push's `before` commit no longer exists. Any normal commit on top fixes it.
- Not yet run: `release.yml` (publishes images to GHCR on a `v*` tag) and the nightly workflow's real-model job (needs a self-hosted GPU runner).
- Commit identity: commits in this repo use the account's GitHub noreply identity. Do not author commits with a personal email.

## 19. Citation parsing fix and a caveat on earlier numbers (2026-10-06)
- Found while demoing: `llama2` often copies the evidence wrapper (`[evidence ref="doc:x" type="doc"]`) instead of the bare `[doc:x]` the prompt asks for. G3 did not recognise that form, so such answers counted as having **no citations** and showed raw wrapper text. `app/guardrails/citations.py` now converts the wrapper form to a normal citation; the ref is still validated against what was retrieved and invented refs are still stripped (2 new tests).
- **Measured effect on earlier results:** `python scripts/rescore_citations.py reports/dev_full_3models.json` re-applies the fixed parsing to the stored answers. It changes the citation count of only 4 of 186 answers (2 llama2, 2 starcoder2:3b); llama2 `code_history` stays at 3 of 23 answers citing. So the low citation rates in the dev run are real, and correctness (key-fact matching) is unaffected.
- G4 (lexical grounding) flags padded paraphrase: a sentence that restates a supported bullet with extra words can fall below `GROUNDING_MIN_SUPPORT` (0.50). That is the known limitation of a lexical check that has not been validated against human labels; the threshold was deliberately not tuned to hide it.
- Demo guidance: for questions about the Nexus repo `codellama:7b` stays closer to the evidence than `llama2`.
