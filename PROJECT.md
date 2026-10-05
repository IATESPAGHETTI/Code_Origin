# CodeOrigin — project overview and status

> **One line:** a repository-aware RAG system that answers *"why was it built this way?"* from source code **and** development history (commits, diffs, issues, pull requests, review comments), with every claim cited, and an evaluation harness that measures whether the history actually helps.

Status snapshot: **core system built and verified end to end locally; Docker/CI/monitoring/docs still to do.** Details in [section 9](#9-what-is-done-and-what-is-not).

Location: `CodeOrigin/` inside the worktree `devops-new-project-3b6ce0` (branch `claude/devops-new-project-3b6ce0`). It was built there, not in the base `IDT_FULL` checkout, because the session is sandboxed to the worktree. Nothing is committed yet.

---

## 1. The problem

A developer finds an odd authentication flow and asks *"why was it done this way?"* The current code cannot answer. The answer lives in:

```
code → commit history → pull requests → issues → review comments → docs
```

Ordinary code assistants look only at the current state of the code. CodeOrigin indexes the history too, retrieves the relevant pieces for a question, and has an LLM answer **only from that evidence**, citing it (`commit:69e7bbd`, `issue:#7`, `pr:#8`). If the history does not contain the answer, it says so instead of inventing a story.

## 2. The research question

> Does incorporating repository history (commits, issues, pull requests, code changes) into an LLM-RAG pipeline improve the accuracy and usefulness of software-development answers?

(This is "Idea #2" of the assignment brief. It was chosen over "change-impact analysis" because the earlier ChangeGuard project already covered that.)

### The experiment

Every question is answered in three conditions, plus a diagnostic fourth:

| Mode | What the LLM sees | Purpose |
|---|---|---|
| `no_context` | the question only | baseline: what the model guesses by itself |
| `code_only` | question + retrieved **source code and docs** | how most code assistants work today |
| `code_history` | question + code + **commits, diffs, issues, PRs, reviews** (cross-linked) | the hypothesis |
| `oracle` | question + the **gold** evidence, no retrieval | diagnosis: separates "retrieval missed it" from "the model cannot use it" |

All modes share the same prompt shape, the same character budget for context, temperature 0 and a fixed seed, so any gain cannot be explained by "more text" or randomness.

### How the result is judged (fixed before running)

- Results are reported **per question category with 95% bootstrap confidence intervals**. There is deliberately no single blended score.
- Decision rule: *history is "useful" if `code_history` beats `code_only` on the history categories by ≥ 0.10 correctness with the CI excluding 0, **and** does not lose more than 0.05 on the control category.* Otherwise the verdict is "inconclusive" or "does not help".
- Paired sign-flip permutation test and Cohen's d_z for each comparison.
- A **failure taxonomy** tags every wrong answer: `retrieval_miss`, `model_ignored_evidence`, `hallucinated`, `over_refused`, `under_refused`, `no_evidence_given`.

---

## 3. Architecture

```
Browser ──► web (React, nginx in prod)
                │  /api (SSE for live pipeline + ingestion)
                ▼
          gateway :8200   input limits, rate limit, request ids, metrics, webhook passthrough
   ┌────────┬───┴────┬─────────────┐
   ▼        ▼        ▼             ▼
 ingest   eval   orchestrator    (rag / llm read-only passthroughs)
 :8201    :8205  :8204
   │        │      │     │
   │        └──────┘     ▼
   │   (runs questions)  rag :8202 ◄── hybrid retrieval (embeddings + BM25) ── ChromaDB / in-memory
   ▼                     llm :8203 ◄── Ollama (llama2, codellama, starcoder2) + jury (gemma:2b)
 git + GitHub API
 SQLite state
```

| Service | Port | Responsibility |
|---|---|---|
| `gateway` | 8200 | Single entrypoint. Validates input (G7), rate-limits, propagates `X-Request-ID`, optional API key, Prometheus `/metrics`, forwards GitHub webhooks untouched, proxies the SSE streams. |
| `ingest` | 8201 | Registers a repo (GitHub URL or `owner/repo`), clones/fetches with git, reads commits + diffs, pulls issues/PRs/reviews/releases from the GitHub API, builds the issue↔PR↔commit link graph, chunks everything, redacts secrets, pushes chunks to `rag`. Full + incremental sync, webhook receiver (HMAC-verified). |
| `rag` | 8202 | Stores chunks and embeddings; hybrid retrieval (vector + BM25 fused with reciprocal-rank fusion); metadata filters; link expansion (`/expand`). Backends: in-memory (tests/CI) or ChromaDB (compose). Embedders: deterministic `hash` (tests) or `sentence-transformers` (real). |
| `llm` | 8203 | Ollama client with token accounting, `/judge` (LLM jury), and a deterministic `MOCK_LLM=1` mode so CI never needs a GPU. |
| `orchestrator` | 8204 | Runs the pipeline for a mode, applies the guardrails, builds the cited prompt, validates citations, checks grounding. Exposes `/ask`, `/ask/stream` (live stage events), `/retrieve` (scores only, for calibration). |
| `eval` | 8205 | Dataset loading/validation, runs the models × modes × questions matrix, computes metrics, statistics, the verdict, failure analysis, human-grade calibration of the jury, markdown report. |
| `frontend` | 5180 | React + Tailwind UI (Home, Ask, Repositories, Evaluation). |
| `chromadb`, `ollama` | – | Infrastructure (compose, not yet written). |

Shared code (`shared/`) is the single source of truth for tokenisation, evidence-ref parsing and secret redaction; `scripts/sync_shared.py` copies it into each service so every container is self-contained, and `--check` fails CI on drift.

---

## 4. How it works

### 4.1 Ingestion (what is read from a repository)

| Source | Method | Stored as |
|---|---|---|
| Source files at HEAD | `git ls-files`, Python split by function/class (AST), other languages by line windows | `code` |
| Docs (`.md/.rst/.txt`) | split on headings | `doc` |
| Commits (SHA, author, date, message, files changed) | `git log` | `commit` |
| Per-commit diffs (size-capped, noise/binary skipped) | `git show` | `diff` |
| Issues + comments | GitHub REST API, paginated | `issue` |
| Pull requests + comments | GitHub REST API | `pr` |
| Reviews + review comments | GitHub REST API | `review` |
| Releases | GitHub REST API | `release` |

- **Cross-links.** `#123` mentions in commits/PRs/issues and each PR's merge commit become edges in an issue↔PR↔commit graph, stored on every chunk. Retrieving one pulls in the others that explain it.
- **Idempotent.** Chunk ids are deterministic, so re-ingesting never duplicates.
- **Incremental.** Re-sync fetches only new commits and issues/PRs updated since the last sync; code/docs are re-chunked.
- **Rate limits.** Honours `Retry-After` and `X-RateLimit-*` (waits up to a cap, else fails with a clear message). A `GITHUB_TOKEN` raises the limit and enables private repos; it is passed to git via an HTTP header and scrubbed from any error text.
- **Secrets.** Every chunk is redacted (AWS keys, GitHub/Slack tokens, JWTs, private keys, `KEY = "literal"` assignments) **before** indexing, so a key leaked in 2023 never reaches the index.
- **Offline mode.** A local path plus a JSON fixture (GitHub-API shape) runs the identical pipeline without network. Used by tests, CI and the seeded demo repo.

### 4.2 Retrieval

Embedding similarity plus BM25 (so exact SHAs, issue numbers and identifiers still match), fused by reciprocal-rank fusion. Each hit carries `vector_score`, `bm25_score` and a `relevance` in [0, 1] that the gates threshold on. Filters: path prefix, author, date range. Repositories are isolated: a query must name a repo.

### 4.3 The answer pipeline (per question)

```
safety (G10) → retrieve → on-topic gate (G1) → history-evidence gate (G2) → follow cross-links
   → build context (G5 injection filter, fixed budget) → generate → verify citations (G3)
   → check grounding (G4) → redact secrets (G6)
```

For `code_only`, topicality (G1) is judged against the **whole repository**, not just code chunks. (This was a real bug found in the live UI: judging on code only refused on-topic history questions and handicapped the baseline. It now has a regression test.)

---

## 5. Guardrails

All enforced **in code**, never by asking a small model to behave.

| ID | Guardrail | Behaviour | Status |
|---|---|---|---|
| G1 | Off-topic | best retrieval relevance below threshold → refuse, **no LLM call** | ✅ built, tested, calibrated on dev split |
| G2 | Insufficient history | history-seeking question with no history chunk above threshold → "the history doesn't say why" | ✅ |
| G3 | Citation enforcement | every `[ref]` the model writes is checked against what was retrieved; invented ones are stripped and reported | ✅ |
| G4 | Claim grounding | each answer sentence must be lexically supported by the evidence; unsupported ones flagged (counted as hallucination) | ✅ lexical, not yet validated against human labels |
| G5 | Prompt-injection defence | commit messages/issues/code comments are untrusted data: instruction-like text neutralised, evidence wrapper escaped | ✅ tested incl. a deliberately poisoned commit in the demo repo |
| G6 | Secret redaction | at ingest **and** on model output | ✅ |
| G7 | Input limits | github.com-only allow-list, question length, rate limit, optional API key | ✅ (gateway) |
| G8 | Repo isolation | queries are scoped to one repo | ✅ by construction (per-repo store) |
| G9 | Webhook authenticity | HMAC-SHA256 on the raw body; disabled when no secret is set | ✅ |
| G10 | Request safety | refuse secret-exfiltration, command-execution and prompt-override requests before any retrieval | ✅ narrow patterns; legit questions like "why was the API key moved?" are not blocked |

Thresholds are **calibrated from data**: `scripts/calibrate_thresholds.py` picks G1/G2 on the **dev** split only, leaving the **test** split untouched for the final run. They depend on the embedding backend, so they must be recalibrated when the embedder changes.

---

## 6. Evaluation system

- **Dataset format** (`services/eval/datasets/*.json`): per item a category, question, `expect` (`answer` or `refuse`), `key_facts` (alternative phrasings per fact), `gold_evidence` refs, and a `dev`/`test` split. A content hash is recorded in every run.
- **Categories (9):** `design_rationale`, `bug_origin`, `change_attribution`, `issue_linkage`, `evolution` (history); `current_state` (control, where history should not be needed); `unanswerable`, `off_topic`, `adversarial` (guardrail behaviour).
- **Metrics per answer:** correctness (key-fact match, or correct abstention), evidence recall/precision, whether gold evidence was cited, citation validity, unsupported-claim ratio, refusal correctness, latency, tokens.
- **LLM jury:** a separate model (`gemma:2b`, deliberately not one of the compared models) grades answers via `/judge`; unparseable output is kept raw rather than dropped.
- **Calibration:** `/runs/{id}/calibration` computes quadratic-weighted κ and Spearman between human grades and (a) the automatic score and (b) the jury; the jury is only flagged "usable as headline" at κ ≥ 0.6.
- **Models compared:** `llama2`, `codellama:7b`, `starcoder2:3b` (configurable).
- **Report:** per-category tables with CIs, pooled retrieval/cost table, paired comparisons, the verdict, failure analysis, errors.

### The demo repo and dataset

`scripts/make_demo_repo.py` builds a deterministic fictional repo, **Ledgerly** (fixed authors/dates → reproducible SHAs, verified identical across runs), with a seeded 13-commit history that contains real engineering decisions: a session-fixation fix (cookies → JWT, HS256 vs RS256 debated in review), a login rate limiter, a Decimal money type, a CSV export, a **cache that was added then reverted**, a **leaked API key later moved to the environment**, a TTL change, and a **commit whose message tries to hijack an assistant** (prompt injection). Matching issues, PRs and reviews come from an offline fixture.

`scripts/build_demo_dataset.py` generates a **43-question** dataset from that history; gold evidence is written symbolically (`commit@jwt`) and resolved to real SHAs, so labels cannot drift (CI-checkable with `--check`).

> The demo repo exists so there is guaranteed ground truth. The real test is running it against a real GitHub repository with real issues and PRs (see next steps).

---

## 7. Frontend

Light, Apple-inspired design: `#f5f5f7` canvas, near-black type, one blue accent, translucent **liquid-glass** panels (frosted blur, bright specular rim, a spotlight that follows the pointer) over a restrained backdrop (soft pastel light, hairline grid, thin rings). Where the browser supports it (Chromium), an SVG displacement filter used as `backdrop-filter` makes glass edges genuinely **refract** the backdrop; other browsers fall back to plain frost. Motion respects `prefers-reduced-motion`.

| Page | What it does |
|---|---|
| **Home** | Hero with a self-playing demo of the pipeline (steps light up, retrieval bars grow), the word "why" in an animated Apple-colour gradient, evidence-ticker, bento feature grid, an evidence-chain diagram that draws itself on scroll, guardrail cards, count-up stats. |
| **Ask** | Pick repo/model; ask in one mode or **compare all three side by side**. Each card streams the **live pipeline** from real backend events: safety → retrieval (per-chunk vector and BM25 bars) → gate gauges (value vs threshold, pass/blocked) → link expansion → context built (used vs cut chunks, budget meter, neutralised-injection count) → generation → citation check (valid ticks, invented struck through) → grounding (per-sentence support bars, unsupported sentences underlined) → redaction. Then the answer types out with clickable citations that open the evidence. A **Slow motion** toggle dwells on each stage so it can be followed. |
| **Repositories** | Add a GitHub URL; watch **live ingestion**: stage stepper, commits streaming in with their issue/PR links, files being chunked, chunk counters by type ticking up, sample chunks flowing into the index, redaction counter. Sync / delete. |
| **Evaluation** | Choose dataset, split, models, modes, jury; start a run; watch progress; read the verdict, correctness heat-table per category, pooled metrics, failure analysis; show the markdown report. |

---

## 8. Repository layout

```
CodeOrigin/
├── PROJECT.md                     # this file
├── shared/                        # single source of truth for textutil, refs, secret redaction
├── scripts/
│   ├── sync_shared.py             # copy/check shared modules into services
│   ├── make_demo_repo.py          # deterministic seeded 'ledgerly' repo + offline fixtures
│   ├── build_demo_dataset.py      # 43-question dataset (--check for CI)
│   ├── seed_demo.py               # build demo repo and register it through the gateway
│   ├── calibrate_thresholds.py    # pick G1/G2 on the dev split
│   └── smoke_local.py             # start all 6 services as processes, run end-to-end checks (--serve keeps them up)
└── services/
    ├── gateway/        app/main.py                              tests/
    ├── ingest/         app/{git_ops,github_api,parsers,links,pipeline,store,main}.py   tests/
    ├── rag/            app/{embeddings,bm25,store,hybrid,main}.py                      tests/
    ├── llm/            app/main.py                              tests/
    ├── orchestrator/   app/{pipeline,config,main}.py + guardrails/{safety,evidence,injection,citations,grounding}.py   tests/
    ├── eval/           app/{dataset,metrics,stats,report,runner,store,main}.py + datasets/demo.json   tests/
    └── frontend/       src/{pages,components,api.js} + Dockerfile + nginx.conf
```

Each Python service has a multi-stage, non-root `Dockerfile` with a healthcheck; `rag` takes a build arg to choose real embeddings (CPU torch) or the tiny deterministic one.

---

## 9. What is done and what is not

### Done and verified

| Area | Evidence |
|---|---|
| **141 automated tests, all passing** | rag 9 · llm 12 · ingest 32 · orchestrator 46 · eval 17 · gateway 25 (run locally; ingest uses real git against the demo repo) |
| **End-to-end smoke test passes** (`scripts/smoke_local.py`) | 6 real service processes: health, seed + ingest, all modes, every guardrail path, the eval run, report generation |
| **Ingestion** | full + incremental sync, idempotent re-ingest, secret redaction (leaked key never indexed), link graph, GitHub client with pagination/rate-limit tests (mocked), webhook HMAC |
| **Guardrails G1–G10** | unit tests for each, pipeline tests, plus regression for the code-only over-refusal bug |
| **Evaluation** | metrics, stats (bootstrap CI, permutation test, κ, Spearman), decision rule, failure analysis, oracle mode, calibration |
| **Live streaming** | ingest events, `/ask/stream`, gateway SSE passthrough with metrics; tested at each layer and confirmed in the browser (pipeline steps lighting progressively across the three cards) |
| **Frontend** | builds and lints clean; Home/Ask/Repositories/Evaluation rendered against the live stack; evaluation run of 129 answers driven from the UI |

### Not done yet

| Item | Notes |
|---|---|
| `docker-compose.yml` (+ dev/prod/monitoring overrides), `.env.example`, Makefile | **not written**. The Dockerfiles exist but **have never been built**: the Docker daemon was off during this session. |
| CI/CD (GitHub Actions: lint, test, build, scan, smoke, eval gate, release, nightly eval) | not written. `smoke_local.py` and `sync_shared.py --check` are ready to be called from it. |
| Prometheus/Grafana/Loki | the gateway already exposes `/metrics`; nothing scrapes it yet. |
| `README.md` and `docs/` pages (architecture, guardrails, evaluation, demo script) | this file is the only prose so far. |
| Discord bot, Kubernetes manifests | optional, not started. |
| Frontend Dockerfile/nginx | written, not built. Frontend unit tests: none yet (only lint + build). |

### Not yet validated (be careful what you claim)

- **No real-model results exist.** Every evaluation run so far used the **mock LLM** (it just quotes the first evidence block) and the **hash embedder**. The "inconclusive" verdict in those runs says nothing about the research question. Real numbers need Ollama models and the sentence embedder.
- **G1/G2 thresholds** were calibrated on the hash embedder (G1 ≈ 0.27, G2 ≈ 0.37 → defaults 0.25 / 0.30). They **must be recalibrated** for sentence-transformers.
- **ChromaDB backend** (`ChromaStore`) is written but has **never been run**; tests use the in-memory store.
- **GitHub API client** is tested only against mocked responses, never against real GitHub. A first real run may surface response-shape surprises.
- **G4 grounding** is a lexical heuristic; it has not been checked against human labels (the plan's spike S3).
- **Jury agreement** with humans is unmeasured (needs human-graded answers via the calibration endpoint).
- **Sample size:** 43 questions, with 4–9 per category, gives wide confidence intervals. That is a limit to state, not hide.
- Visual refraction was confirmed in Chromium only.

### Deviations from `DESIGN.md`

- **SQLite** instead of Postgres for ingest/eval state (simpler; no extra container).
- **One Chroma collection per repo** with a `source_type` filter, instead of one per source type.
- **No ETag caching** in the GitHub client (relies on `since` for incremental sync).
- BM25 is rebuilt in memory per repo (fine at this scale; not for very large repos).
- Ports: gateway 8200, ingest 8201, rag 8202, llm 8203, orchestrator 8204, eval 8205, web 5180 (Chroma will use 8206 to avoid the clash noted in the design).

---

## 10. How to run it today (no Docker needed)

```bash
# one-time: Python 3.10+ with fastapi, uvicorn, httpx, pydantic, prometheus-client, pytest; Node 20 for the UI
cd CodeOrigin
python scripts/sync_shared.py                          # copy shared modules into services
python scripts/smoke_local.py                          # start 6 services, run every check, print the eval report
python scripts/smoke_local.py --serve --base-port 8200 # keep the seeded stack running on 8200-8205
cd services/frontend && npm install && npm run dev     # UI on http://localhost:5180 (proxies /api to :8200)
```

Per-service tests: `cd services/<name> && python -m pytest -q`.

To use a real model: run Ollama with `llama2`, `codellama:7b`, `starcoder2:3b`, `gemma:2b`; start `llm` **without** `MOCK_LLM`, start `rag` with `EMBEDDING_BACKEND=sentence` and `STORE_BACKEND=chroma`, then re-run `calibrate_thresholds.py` and set the printed `OFF_TOPIC_MIN_RELEVANCE` / `HISTORY_MIN_RELEVANCE`.

---

## 11. Next steps (in order)

1. `docker-compose.yml` + overrides, `.env.example`, Makefile; **build every image** and run the compose smoke test (start Docker Desktop first).
2. GitHub Actions: lint/test/build, `sync_shared --check`, dataset `--check`, Trivy + gitleaks, compose smoke, eval gate; release + nightly eval.
3. Pull the Ollama models; re-run the smoke and the evaluation with **real models and the sentence embedder**; recalibrate G1/G2; run ChromaDB for real.
4. Index a **real GitHub repo** with rich issue/PR history; mine and hand-verify 40+ questions (the 'question mining' step in the design); run the held-out test split once.
5. Human-grade ~60 answers; compute jury/automatic agreement; publish the report with the failure analysis.
6. Monitoring (Prometheus/Grafana), README + docs, then optional Discord bot and Kubernetes.
