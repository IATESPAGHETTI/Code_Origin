# Operations

## Compose files
| File | Purpose |
|---|---|
| `docker-compose.yml` | core stack: web, gateway, ingest, rag, llm, orchestrator, eval, chromadb; optional `ollama` profile |
| `docker-compose.dev.yml` | mock LLM, hash embedder, in-memory store, Vite hot reload, all ports published |
| `docker-compose.prod.yml` | GHCR images by `TAG`, CPU/memory limits, `API_KEY` mandatory |
| `docker-compose.monitoring.yml` | Prometheus :9090, Grafana :3000, Loki, Promtail |
| `docker-compose.demo.yml` | mounts `demo-data/` into ingest at `/demo` and enables local repos |

Typical combinations: `make dev`, `make up`, `make monitoring`, `make prod`.

## Ollama
Default is the **host** Ollama (`OLLAMA_HOST=http://host.docker.internal:11434`), which already has the models and the GPU. To run it in compose: `docker compose --profile ollama up -d`, set `OLLAMA_HOST=http://codeorigin-ollama:11434` and `OLLAMA_MODELS_DIR=C:/Users/<you>/.ollama`; stop the host Ollama first (one 6 GB GPU cannot serve both). Run one 7B model at a time.

## Health and metrics
`python scripts/compose_health.py` waits for every `codeorigin-*` container to be healthy. The gateway exposes `/metrics`: `codeorigin_requests_total`, `codeorigin_request_seconds`, `codeorigin_guardrail_triggers_total`, `codeorigin_llm_tokens_total`, `codeorigin_refusals_total`. Alerts in `monitoring/alerts.yml`.

## CI/CD
- `ci.yml`: ruff, shared-module and dataset drift checks, per-service tests, frontend lint+build, gitleaks, Trivy fs scan, compose smoke (dev stack + seeded repo + an `/api/ask`), eval gate (`smoke_local.py`, mock LLM — plumbing only).
- `release.yml`: on `v*` tags, builds each image, Trivy-scans it, pushes to `ghcr.io/<owner>/codeorigin-<svc>:<version>`, creates a GitHub release.
- `nightly-eval.yml`: mock regression on hosted runners; real-model dev-split run only on a self-hosted GPU runner (repo variable `HAS_GPU_RUNNER=true`).

## Gotchas
- Git Bash rewrites `/demo` into a Windows path; use `MSYS_NO_PATHCONV=1`.
- Named volumes keep old ownership: if you change a Dockerfile's `/data` permissions, `docker volume rm` the volume.
- In `.env`, do not put trailing `# comments` on a value line; Compose treats them inconsistently.

## Fitting a 7B model on a 6 GB GPU
Default `llama2` (4096 ctx, fp16 KV cache) needs ~6.1 GB and spills ~30% to the CPU (≈7 tok/s). Measured on an RTX 3060 Laptop 6 GB: with
`OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0` on the host Ollama and `OLLAMA_NUM_CTX=3072`, it runs 89% on GPU (4.8 GB) at ≈40 tok/s.
Start the host server for the session with those variables (quit the Ollama tray app first): `ollama serve`. The q8 KV cache and the context size
are recorded run settings and apply identically to all modes. Prompts are ≈2,000 tokens + up to 300 generated, so 3072 does not truncate.

## Evaluation scores in Grafana
The eval service exposes `/metrics` (internal only; Prometheus scrapes `codeorigin-eval:8205` every 30 s). It exports the newest 10 runs: per-category and overall correctness (with CI bounds), jury correctness, history effect (`code_history` minus `code_only`) with its CI, the pre-registered verdict, failure counts and run progress. The dashboard row "Evaluation results" has run and model selectors. These are the same numbers as the markdown report: automatic key-fact scoring, not human-graded, and per-category n is small on the demo dataset.
