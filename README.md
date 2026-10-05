# CodeOrigin

A repository-aware RAG system that answers **"why was it built this way?"** from source code *and* development history — commits, diffs, issues, pull requests, review comments, releases — with every claim cited. It ships with an evaluation harness that measures whether the history actually helps.

> **Research question:** does incorporating repository history into an LLM-RAG pipeline improve the accuracy and usefulness of software-development answers?
> Status: pipeline, guardrails, evaluation harness and DevOps stack are built. See [docs/EVALUATION.md](docs/EVALUATION.md) for what has and has not been measured with real models — mock-LLM numbers are never evidence about the hypothesis.

## Architecture

```
Browser ─► web :5180 ─► gateway :8200 ─┬─► ingest :8201 ─► git + GitHub API, SQLite
                                       ├─► orchestrator :8204 ─► rag :8202 ─► ChromaDB :8206
                                       │                     └─► llm :8203 ─► Ollama
                                       └─► eval :8205 ─► orchestrator / llm (jury)
```
Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · guardrails G1–G10: [docs/GUARDRAILS.md](docs/GUARDRAILS.md) · demo: [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) · ops: [docs/OPERATIONS.md](docs/OPERATIONS.md) · own-repo experiment: [docs/OWN_REPO_TEST.md](docs/OWN_REPO_TEST.md) · hand-off: [docs/HANDOFF_MUKUND.md](docs/HANDOFF_MUKUND.md) · status: [CODEORIGIN_CONTINUATION.md](CODEORIGIN_CONTINUATION.md)

## Quick start

**No Docker (mock LLM, ~1 min):**
```bash
pip install -r services/gateway/requirements-dev.txt   # plus the other services' requirements
python scripts/sync_shared.py
python scripts/smoke_local.py --serve --base-port 8200 # 6 services + seeded demo repo
cd services/frontend && npm install && npm run dev      # http://localhost:5180
```

**Docker, dev (mock LLM, hash embedder, no GPU):**
```bash
cp .env.example .env
make dev        # docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

**Docker, real models (sentence-transformers + ChromaDB + your host Ollama):**
```bash
ollama pull llama2 && ollama pull codellama:7b && ollama pull starcoder2:3b && ollama pull gemma:2b
cp .env.example .env
make up         # add --profile ollama + OLLAMA_HOST=http://codeorigin-ollama:11434 to run Ollama in a container with the GPU
make health
```
Add `-f docker-compose.monitoring.yml` (`make monitoring`) for Prometheus :9090, Grafana :3000, Loki.

Seed the Ledgerly demo repo: `python scripts/make_demo_repo.py --out demo-data`, then (with `docker-compose.demo.yml`) `python scripts/seed_demo.py --container-path /demo`. Git Bash on Windows: prefix with `MSYS_NO_PATHCONV=1`.

## Layout
```
services/{gateway,ingest,rag,llm,orchestrator,eval,frontend}   one Dockerfile each (multi-stage, non-root, healthcheck)
shared/                 textutil, refs, secrets_redact (copied into services by scripts/sync_shared.py)
scripts/                demo repo/dataset builders, smoke test, calibration, eval runner, compose health
monitoring/             Prometheus, alerts, Loki, Promtail, Grafana dashboards
.github/workflows/      ci, release (GHCR), nightly-eval
```

## Testing
```bash
make check      # shared-module drift + dataset gold-evidence check
make test       # 142 backend tests across 6 services (+6 frontend) (mock LLM, hash embedder, in-memory store)
make lint       # ruff + eslint (frontend unit tests: cd services/frontend && npm test)
make smoke      # end-to-end with real processes
```

## Security notes
Secrets are redacted before indexing and on output; repository content is treated as untrusted data (prompt-injection neutralised) and never executed; containers run non-root with dropped capabilities; the gateway supports an API key, rate limits and HMAC-verified webhooks. Put `GITHUB_TOKEN`, `API_KEY` and `GITHUB_WEBHOOK_SECRET` only in `.env` (git-ignored).
