# Testing on your own repository (the held-out experiment)

Goal: a repo with **real history you did not write for the experiment** (issues, PRs with review discussion, reverts, bug fixes), so the test is not about a seeded fiction. Everything below keeps the experiment valid.

## 1. Make the repo worth asking about
- Push it to GitHub (public, or private with a token). Aim for 30+ commits, 15+ issues, 15+ PRs, a few reviews and at least one revert and one security/bug fix.
- Write real issue and PR descriptions ("Fixes #12", reasons for the change). If it is a staged repo, do the work in separate PRs with discussion, not one big commit. Do not mention CodeOrigin or the questions in it.
- Put `GITHUB_TOKEN=<token>` in `.env` (git-ignored; never paste it into chat or commit it).

## 2. Ingest
```bash
docker compose -f docker-compose.yml -f docker-compose.ports.yml up -d
python scripts/compose_health.py
curl -X POST localhost:8200/api/repos -H 'content-type: application/json' -d '{"source":"https://github.com/<owner>/<repo>"}'
```

## 3. Mine and verify questions (human step)
```bash
python scripts/mine_questions.py <owner>/<repo> --out reports/candidates.json
```
For **each** candidate: read the PR/issue/commits, write `gold_answer` and `key_facts` (alternative phrasings per fact), correct `gold_evidence`, set `verified: true`. Add `unanswerable`, `off_topic`, `adversarial` and `current_state` (control) items by hand. Target 40+ verified items across all categories.
- Assign `split` (`dev` / `test`) **before** running any model on the new items. Roughly half and half; never tune on `test`.
- Convert to the dataset format in `services/eval/datasets/` (same fields as `demo.json`; `repo` = the new repo id) and re-run `python scripts/build_demo_dataset.py --check` style validation via the eval service.

## 4. Calibrate on dev only, then freeze
`python scripts/calibrate_thresholds.py --dataset <your dataset> --split dev`; set the printed thresholds in `.env`; do not change them after this point.

## 5. One test run
```bash
python scripts/run_eval.py --live --dataset <name> --repo <repo_id> --split test --models llama2,codellama:7b,starcoder2:3b --out reports/test_final
```
Host Ollama must run with the same settings as every other result set (see `docs/OPERATIONS.md`). Run this **once**.

## 6. Human grading and agreement
```bash
python scripts/grading_sheet.py export --run <id> --n 60 --out reports/grading_test.csv   # blind
# fill human_score: 0 = wrong, 1 = partly right, 2 = right
python scripts/grading_sheet.py import --run <id> --file reports/grading_test.csv
python scripts/grading_sheet.py kappa --run <id>
```
Report kappa for the automatic score and the jury; the jury is a headline metric only at kappa >= 0.6. Check G4 grounding by hand on the same sample (is each flagged-unsupported sentence really unsupported?).

## 7. Write-up
Per-category tables with CIs, effect sizes, the verdict from the pre-registered rule, the failure taxonomy, and limitations (sample size, one repo, small local models, key-fact scoring). State every run setting.
