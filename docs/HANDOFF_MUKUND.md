# Handoff: taking over CodeOrigin (for Mukund)

Read this first, then `CODEORIGIN_CONTINUATION.md` (status and decisions), then `README.md`. About 20 minutes of reading gets you productive.

## 1. What this project is
CodeOrigin is a RAG system that answers *"why was it built this way?"* about a GitHub repo, using the code **and** its history (commits, diffs, issues, PRs, reviews), with every claim cited. It also has an evaluation harness that tests the research question: **does adding repository history to the prompt improve answers?** The experiment design is fixed (see section 8), so don't change it.

## 2. Where everything is
- Code: `C:\Users\ASUS\Desktop\IDT_FULL\CodeOrigin` (a copy is committed on the git branch `claude/codeorigin-continuation-docs-d58388` under `CodeOrigin/`). Get the folder from Deepu as a zip or via the branch.
- Results so far: `CodeOrigin/reports/dev_full_3models.md` and `.json` (dev-split run, 3 models), `grading_run5.csv` (blind sheet for human grading).

## 3. What to install (Windows 11, NVIDIA GPU recommended)
| Tool | Version | Why |
|---|---|---|
| Docker Desktop | recent (Compose v2) | runs all services, ChromaDB, the website |
| Ollama | 0.35+ | runs the LLMs on the host GPU |
| Python | 3.10 or 3.11 | running tests and scripts on the host |
| Node.js | 20+ | frontend lint/tests (`npm`) |
| Git | any | clone, and Git Bash is what the scripts were tested in |
| (optional) GPU driver | current NVIDIA | the demo machine is an RTX 3060 6 GB |

Python packages for host-side tests and scripts:
```bash
pip install httpx pytest pytest-cov ruff pyyaml prometheus-client==0.21.0 fastapi==0.115.9 uvicorn==0.30.6 pydantic==2.9.2
# or per service:  pip install -r services/<svc>/requirements-dev.txt   (rag, llm, ingest, orchestrator, eval, gateway)
```
Frontend: `cd services/frontend && npm install`.

Ollama models (about 12 GB total; `ollama pull <name>`): `llama2`, `codellama:7b`, `starcoder2:3b`, `gemma:2b` (the jury). `deepseek-coder:6.7b` is optional (exploratory only).

## 4. First-time setup
```bash
cd CodeOrigin
cp .env.example .env            # the defaults work; never commit .env
python scripts/sync_shared.py --check     # should print "shared modules in sync"
```
**Start Ollama with the GPU-fit settings** (quit the Ollama tray app first, otherwise it restarts without them):
```powershell
$env:OLLAMA_FLASH_ATTENTION="1"; $env:OLLAMA_KV_CACHE_TYPE="q8_0"; ollama serve
```
These plus `OLLAMA_NUM_CTX=3072` (already in `.env`) fit a 7B model in 6 GB of VRAM and roughly double the speed. They are a recorded run setting: **keep them identical for every result you want to compare**, and state them in any write-up. If you have more VRAM you can drop them (set `OLLAMA_NUM_CTX=0`), but then re-run everything that you compare.

Start the stack (real embeddings + ChromaDB + your Ollama):
```bash
docker compose -f docker-compose.yml -f docker-compose.demo.yml -f docker-compose.ports.yml up -d --build
python scripts/compose_health.py          # waits until everything is healthy
MSYS_NO_PATHCONV=1 python scripts/make_demo_repo.py demo-data
MSYS_NO_PATHCONV=1 python scripts/seed_demo.py --container-path /demo   # indexes the demo repo "Ledgerly"
```
Website: http://localhost:5180 (Ask, Repositories, Evaluation). The first build of the `rag` image downloads PyTorch and the embedding model, so allow about 10 minutes.

Stop everything: `docker compose -f docker-compose.yml -f docker-compose.demo.yml -f docker-compose.ports.yml stop`.

## 5. Checking it works (do this before changing anything)
```bash
make test          # 142 backend tests, no GPU needed (or run pytest in each services/<svc>)
make check         # shared-module drift + dataset check
cd services/frontend && npm run lint && npm test     # 10 tests
python scripts/smoke_local.py                          # end-to-end with MOCK LLM, about 20 s (plumbing only)
```
Then open the Evaluation page: the previous runs are in a Docker volume on Deepu's machine, so on a fresh machine the list is empty until you run one.

## 6. Running an evaluation
```bash
python scripts/run_eval.py --live --repo local__repo --split dev --models llama2 --limit 8 --out reports/mytry
```
`--live` prints every answer as it completes with progress and an ETA; `--attach <run_id>` follows a run already started (for example from the website). A 3-model dev run (255 answers) took about 21 minutes on the RTX 3060 once the GPU settings were in place.
Results land in `reports/<name>.md` and `.json`, and in the website's Evaluation page ("Which model is best where").
**Do not run two heavy things at once** (an eval plus Wan2.1, games, etc.): the laptop has 15 GB RAM and 6 GB VRAM, and it thrashes. If free RAM drops under about 0.5 GB, stop the run.

## 7. What is left (your work, in order)
1. **Make the real test repo.** A GitHub repo with real history: 30+ commits, 15+ issues, 15+ PRs with review discussion, at least one revert and one security/bug fix. Do the work in separate PRs; write real descriptions ("Fixes #12"). Do not mention CodeOrigin in it.
2. **Token.** Put your own `GITHUB_TOKEN=...` in `.env` (never commit it, never paste it in chat). Without a token GitHub allows only 60 API calls per hour.
3. **Ingest it** (Repositories page or `POST /api/repos`), then **mine candidate questions:** `python scripts/mine_questions.py <owner>/<repo> --out reports/candidates.json`.
4. **Verify 40+ questions by hand** (this is the real research work): for each, read the PR/issue/commits, write `gold_answer` and `key_facts` (alternative phrasings per fact), correct `gold_evidence`, add unanswerable / off-topic / adversarial / current-state items. Assign `split` (dev/test) **before running any model on them**. Full guide: `docs/OWN_REPO_TEST.md`.
5. **Recalibrate thresholds on the dev split only**, then freeze: `python scripts/calibrate_thresholds.py --dataset <yours> --split dev`; put the printed values in `.env`.
6. **One** held-out test run: `--split test --models llama2,codellama:7b,starcoder2:3b`. Never tune on it, never re-run it to "improve" results.
7. **Human grading, about 60 answers:** `python scripts/grading_sheet.py export --run <id> --n 60`, fill `human_score` (0 wrong, 1 partly, 2 right), then `import` and `kappa`. (You can also grade the existing `reports/grading_run5.csv` to get a first agreement number.)
8. **Failure analysis and write-up:** per-category tables with confidence intervals, effect sizes, the verdict from the pre-registered rule, failure taxonomy, and honest limitations.
9. **Push to GitHub and confirm CI passes.** The workflows in `.github/workflows/` have never run on GitHub; expect to fix small things (paths, secrets, Trivy findings).

## 8. Rules that must not change (research validity)
- Four modes: `no_context`, `code_only`, `code_history`, `oracle`. Same context budget, temperature 0, fixed seed.
- Decision rule (set in advance): history is useful only if `code_history` beats `code_only` on history categories by at least 0.10 correctness, the 95% CI excludes 0, and the control category loses no more than 0.05.
- Report per category with CIs; no single blended score.
- Thresholds tuned on **dev** only; **test** run once.
- The jury model (`gemma:2b`) must not be one of the compared models.
- Mock LLM results are for CI plumbing only and are never evidence. "No mock" for any real run (`MOCK_LLM=0`).

## 9. Things that will bite you
- **The jury is too lenient right now.** It gave 100% to every model, even `starcoder2:3b` (46% by automatic score). Do not report jury scores as results until human agreement (kappa >= 0.6) is shown.
- **Current numbers are not research evidence.** They are dev-split, 13 history questions, automatic key-fact scoring, no human grades. Verdict so far: `llama2` "history is useful"; `codellama:7b` and `starcoder2:3b` "inconclusive".
- `llama2` rarely writes `[ref]` citations; `starcoder2:3b` often just repeats the prompt or hallucinates. That is a model-use failure, not a bug in the pipeline.
- **Guardrail thresholds depend on the embedder.** Current values (G1 0.36, G2 0.44) came from only 2 negative examples each. Recalibrate on the new repo.
- Git Bash turns `/demo` into `C:/Program Files/Git/demo`: prefix with `MSYS_NO_PATHCONV=1`.
- `docker compose up -d --build` sometimes keeps the old container. Use `docker compose build <svc>` then `docker compose ... up -d --force-recreate --no-deps <svc>`.
- Never edit the copies of shared modules under `services/*/app/` (`textutil.py`, `refs.py`, `secrets_redact.py`). Edit `shared/` and run `python scripts/sync_shared.py`.
- Don't write files from Python heredocs on Windows (cp1252 can truncate them). Use an editor.
- The Ollama tray app restarts `ollama serve` without the GPU settings. Quit it before starting your own.
- `.env` must not have trailing `# comments` on value lines.
- The seeded demo repo contains a fake leaked API key and a prompt-injection commit **on purpose** (to test redaction and G5). They are not real secrets.

## 10. Optional pieces (not needed for the research)
- Monitoring: `docker compose -f docker-compose.yml -f docker-compose.demo.yml -f docker-compose.ports.yml -f docker-compose.monitoring.yml up -d` gives Prometheus :9090 and Grafana :3000 (anonymous read-only; admin password `change-me` in `.env`). It uses a few hundred MB of RAM; keep it off during real runs.
- Not started: Discord bot, Kubernetes manifests. Do not start them before the real experiment is finished.

## 11. Who to ask / where to look
- Architecture: `docs/ARCHITECTURE.md`; guardrails: `docs/GUARDRAILS.md`; operations and GPU notes: `docs/OPERATIONS.md`; demo script: `docs/DEMO_SCRIPT.md`; full status and decisions: `CODEORIGIN_CONTINUATION.md`.
- Service ports: gateway 8200, ingest 8201, rag 8202, llm 8203, orchestrator 8204, eval 8205, ChromaDB 8206, website 5180.
