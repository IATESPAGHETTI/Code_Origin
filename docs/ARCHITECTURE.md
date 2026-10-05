# Architecture

## Services
| Service | Port | Responsibility |
|---|---|---|
| web | 5180 | React/Tailwind UI served by nginx; `/api/` proxied to the gateway with SSE buffering off |
| gateway | 8200 | only public API: validation (G7), rate limiting, request IDs, optional API key, `/metrics`, webhook passthrough |
| ingest | 8201 | repository → chunks. Git history via `git`, issues/PRs/reviews/releases via GitHub REST; SQLite state; HMAC webhooks |
| rag | 8202 | hybrid retrieval (vector + BM25, reciprocal-rank fusion), metadata filters, link expansion |
| llm | 8203 | Ollama client, token accounting, `/judge`, `MOCK_LLM=1` |
| orchestrator | 8204 | per-mode pipeline + guardrails + cited prompt + citation/grounding checks |
| eval | 8205 | datasets, runs, metrics, statistics, report, human-grade calibration |
| chromadb | 8206→8000 | vector store; one collection per repository |

## Data flow: ingestion
`register repo → clone/fetch → read commits+diffs → GitHub issues/PRs/reviews/releases → build issue↔PR↔commit link graph → chunk (AST for Python, headings for docs, line windows otherwise) → redact secrets → embed → store`. Chunk IDs are deterministic (re-ingest never duplicates); incremental sync fetches only new commits and items updated since the last sync.

## Data flow: a question
```
safety (G10) → retrieve → on-topic gate (G1) → history gate (G2) → link expansion
  → context build (G5 injection filter, fixed char budget) → generate → citation check (G3)
  → grounding (G4) → output redaction (G6)
```
`code_only` runs the same pipeline but retrieves only code/docs; G1 topicality is judged against the whole repo so the baseline is not handicapped. `oracle` skips retrieval and supplies the gold evidence.

## Retrieval
Vector similarity (cosine) + BM25 so exact SHAs, issue numbers and identifiers still match, fused with RRF. Each hit carries `vector_score`, `bm25_score` and a `relevance` ∈ [0,1] used by the gates. Embedders: `hash` (deterministic, tests only) or `sentence` (`all-MiniLM-L6-v2`). Thresholds depend on the embedder → recalibrate when it changes.

## Deployment
`docker-compose.yml` is the core stack; overrides: `dev` (mock LLM, hash embedder, hot reload, ports published), `prod` (registry images, limits, mandatory API key), `monitoring` (Prometheus/Grafana/Loki/Promtail), `demo` (mounts the seeded repo). Ollama runs on the host by default; `--profile ollama` runs it in a container with NVIDIA GPU access and reuses the host model folder.

## Deviations from the original design
SQLite instead of Postgres; one Chroma collection per repo with a `source_type` filter; no ETag caching in the GitHub client; BM25 rebuilt in memory per repo.
