# CodeOrigin task runner. `make help` lists targets.
SERVICES := rag llm ingest orchestrator eval gateway
PY ?= python
BASE := -f docker-compose.yml
DEV := $(BASE) -f docker-compose.dev.yml
PROD := $(BASE) -f docker-compose.prod.yml
MON := $(BASE) -f docker-compose.monitoring.yml

.PHONY: help sync test lint check smoke up down dev prod monitoring build health logs eval calibrate clean $(addprefix test-,$(SERVICES))

help:
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/'

sync: ## copy shared/ modules into services
	$(PY) scripts/sync_shared.py

check: ## drift checks (shared modules, dataset gold evidence)
	$(PY) scripts/sync_shared.py --check
	$(PY) scripts/build_demo_dataset.py --check

lint: ## ruff (python) + eslint (frontend)
	$(PY) -m ruff check services shared scripts
	cd services/frontend && npm run lint

test: $(addprefix test-,$(SERVICES)) ## all backend tests (mock LLM, hash embedder)
test-%:
	cd services/$* && $(PY) -m pytest -q

smoke: ## 6 real processes, full end-to-end check (no Docker)
	$(PY) scripts/smoke_local.py

build: ## build every image
	docker compose $(BASE) --profile ollama build

up: ## core stack (real embeddings + Chroma, host Ollama)
	docker compose $(BASE) up -d --build
dev: ## mock LLM, hash embedder, hot-reload UI, all ports published
	docker compose $(DEV) up -d --build
prod: ## pinned registry images + limits (needs TAG and API_KEY)
	docker compose $(PROD) up -d
monitoring: ## core stack + Prometheus/Grafana/Loki
	docker compose $(MON) up -d --build
down:
	docker compose $(MON) --profile ollama down
health: ## probe every service through its container healthcheck
	$(PY) scripts/compose_health.py
logs:
	docker compose $(BASE) logs -f --tail=100

eval: ## run the evaluation through the gateway (real models; see docs/EVALUATION.md)
	$(PY) scripts/run_eval.py
calibrate: ## recalibrate G1/G2 on the dev split against the running stack
	$(PY) scripts/calibrate_thresholds.py

clean:
	docker compose $(MON) --profile ollama down -v
