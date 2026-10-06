# Evaluation: question, method, results, limits

This is the methodology and results document. Everything here is reproducible from the repository; section 8 lists the exact settings and commands.

## 1. Research question
> Does incorporating repository history (commits, diffs, issues, pull requests, review comments) into an LLM-RAG pipeline improve the accuracy and usefulness of answers to *"why was it built this way?"* questions?

**Hypothesis.** Answers to history-dependent questions are more correct when the model is given the repository's history in addition to its current code. **Null.** History adds nothing (or hurts) beyond current code and docs.

## 2. Design (fixed before running)
| Mode | What the model sees | Role |
|---|---|---|
| `no_context` | the question only | baseline: what the model guesses by itself |
| `code_only` | question + retrieved current code and docs | the realistic baseline (how most assistants work) |
| `code_history` | code + commits, diffs, issues, PRs, reviews, cross-linked | the treatment |
| `oracle` | question + the gold evidence, no retrieval | diagnostic: separates "retrieval failed" from "the model cannot use evidence" |

Held constant across modes: prompt shape, context budget (6000 characters), temperature 0, fixed seed (42), maximum answer length (300 tokens), top-k (8). Differences between modes therefore come from *which evidence is shown*, not from more text or randomness.

**Question categories.** History (design_rationale, bug_origin, change_attribution, issue_linkage, evolution), a **control** category (current_state: history should not be needed), and guardrail behaviour (unanswerable, off_topic, adversarial).

**Decision rule, set before any model ran.** History is "useful" only if `code_history` beats `code_only` on the history categories by **at least 0.10 correctness**, the 95% bootstrap confidence interval **excludes 0**, **and** the control category loses no more than **0.05**. Anything else is "inconclusive" or "does not help". There is deliberately no single blended score; results are reported per category.

## 3. Data
- **Repository under test: "Ledgerly"**, a small fictional payments/auth app whose 13-commit history is generated deterministically (`scripts/make_demo_repo.py`; fixed authors and dates, so SHAs are reproducible). Its history contains real kinds of engineering events: a session-fixation security fix, cookie-to-JWT migration with a review debate, a rate limiter, Decimal money handling, a cache that was added and reverted, an API key that was leaked and later moved to an environment variable, and a commit whose message tries to hijack an assistant (prompt injection). Matching issues, PRs and reviews come from an offline fixture in GitHub-API shape.
- **Dataset: 43 questions** (`services/eval/datasets/demo.json`, content hash `b96ac1b512bac60f`): 23 `dev`, 20 `test`. Each has `key_facts` (alternative phrasings per fact), `gold_evidence` (symbolic references resolved to real commit SHAs), and an expected behaviour (answer or refuse). `build_demo_dataset.py --check` fails CI if labels drift.
- **Split discipline.** Guardrail thresholds were calibrated on `dev` only. The `test` split is for one final run. *Exception:* an exploratory run of a fourth model (`deepseek-coder:6.7b`, run #6) used `split=all` and so touched the test items; it is excluded from the headline results.
- **Real repository ingestion** was verified (`pallets/itsdangerous`: 150 commits, 9 issues, 8 PRs, 7 releases; and a 3-commit personal repo), but no verified question set exists for them yet (see limits).

## 4. Metrics
Per answer (`services/eval/app/metrics.py`, deterministic and recomputable from stored responses):
- **correctness**: fraction of `key_facts` found in the answer (any acceptable phrasing, case-insensitive substring match); for questions that should be refused, 1 if the system refused or abstained, else 0.
- **evidence recall / precision**: how much of the gold evidence was among the chunks shown to the model, and how much of what was shown was gold.
- **gold cited, citation validity**: whether the model cited the gold refs, and the share of cited refs that were really retrieved.
- **unsupported ratio, hallucinated**: share of answer sentences that fail a lexical grounding check (G4); `hallucinated` = ratio >= 0.5.
- **refusal correct**, **latency**, **tokens**.
- **Failure tag** for each wrong answer: `retrieval_miss`, `model_ignored_evidence`, `hallucinated`, `over_refused`, `under_refused`, `no_evidence_given`.

**Statistics.** Per category: mean with a 95% bootstrap CI (2000 resamples). Paired comparisons (same question under two modes): mean difference with bootstrap CI, a paired sign-flip permutation test, and Cohen's d_z. **Agreement with humans:** quadratic-weighted Cohen's kappa and Spearman correlation (`scripts/grading_sheet.py`); an LLM jury (`gemma:2b`, deliberately not one of the compared models) is only to be used as a headline metric if kappa >= 0.6.

## 5. Results so far (run #5: dev split, 3 models x 4 modes, 255 answers, 0 errors)
Models: `llama2`, `codellama:7b`, `starcoder2:3b`, all local via Ollama.

**Overall correctness by mode** (all categories pooled)
| Model | no_context | code_only | code_history |
|---|---|---|---|
| llama2 | 26% | 67% | **91%** |
| codellama:7b | 30% | 67% | **91%** |
| starcoder2:3b | 17% | 41% | 46% |

**Pre-registered test: `code_history` minus `code_only`, history categories (n = 13 questions)**
| Model | Difference | 95% CI | p (permutation) | d_z | Verdict by the rule |
|---|---|---|---|---|---|
| llama2 | +0.42 | [+0.15, +0.69] | 0.023 | 0.86 | history is useful |
| codellama:7b | +0.42 | [+0.00, +0.73] | 0.087 | 0.60 | inconclusive (CI touches 0) |
| starcoder2:3b | +0.08 | [+0.00, +0.19] | 0.50 | 0.41 | inconclusive |

Control category (current_state, n = 3): `code_history` minus `code_only` = 0.00 for every model, i.e. no loss.

**Retrieval diagnostics (all categories pooled)**
| Mode | Evidence recall | Evidence precision |
|---|---|---|
| code_only | 0.19 | 0.04 |
| code_history | 1.00 | 0.36 |
| oracle | 1.00 | 1.00 |

`code_only` almost never retrieves the gold evidence (those refs are history objects), which is the mechanism behind its lower correctness.

**Failure taxonomy (answers that were not "ok")**
| Model | Mode | Main failures |
|---|---|---|
| llama2 | code_only | 5 retrieval_miss |
| llama2 | code_history | 1 model_ignored_evidence |
| codellama:7b | code_history | 2 model_ignored_evidence |
| starcoder2:3b | code_history | 8 hallucinated, 1 model_ignored_evidence |
| starcoder2:3b | oracle | 11 hallucinated, even when handed the gold evidence |
| all | no_context | 5 under_refused (answers questions it should refuse), 8-12 no_evidence_given |

**Other observations.** `llama2`/`codellama:7b` write citations in the requested format in only about 13% / 22% of `code_history` answers (`starcoder2:3b`: 0%). Unsupported-claim ratio in `code_history`: 0.29 / 0.31 / 0.57 (codellama / llama2 / starcoder2). Median latency: 9.1 s / 7.7 s / 0.9 s. The guardrail categories (unanswerable, off_topic, adversarial) are handled correctly in `code_only` and `code_history` for every model, because the refusal gates are enforced in code. `no_context` has no retrieval gates, so it answers unanswerable and off-topic questions.

## 6. Interpretation
1. **Where history helps.** For both 7B models, adding history raises correctness on history questions from roughly 0.5 to roughly 0.9, with no loss on the control question. The mechanism is visible in the diagnostics: `code_only` does not retrieve the history that holds the answer (recall 0.19), `code_history` does (1.00), and with the gold evidence handed over directly (`oracle`, answerable questions, n = 16) `llama2` scores 100% and `codellama:7b` 88%, so for these models the bottleneck is retrieval, not reasoning.
2. **What the pre-registered rule concludes.** Only `llama2` satisfies the rule. `codellama:7b` has the same effect size but a wider interval, so by the rule it is "inconclusive", not "no effect".
3. **The 3B model does not benefit.** `starcoder2:3b` is a code-completion model; given evidence it often copies or invents instead of answering (11 hallucinations out of 16 oracle answers). The failure is in model use of evidence, not retrieval.
4. **Do not over-read.** This is 13 history questions on one fictional repository, scored automatically. It shows the pipeline works and the effect is plausible and large for capable models. It is not yet a conclusion about real software projects.

## 7. Limitations, failure cases and sources of bias
- **Circularity.** The repository, its history and the questions' gold labels were all authored together. History questions are answerable from history *by construction*, which favours `code_history`. A real repository with independently written issues and PRs is needed for an unbiased test.
- **Sample size.** 4-9 questions per category; 13 history questions in the dev run. Confidence intervals are wide and several verdicts are "inconclusive" for that reason. The control category has 3 questions, so "no loss" is weak evidence.
- **Scoring is automatic and unvalidated.** Correctness is substring matching of key facts. It can miss correct paraphrases and can reward long answers that happen to mention a fact. No human grades exist yet, so agreement (kappa) is unmeasured.
- **The LLM jury is not trustworthy.** It scored every model 100% on the answers it graded, including `starcoder2:3b`, whose automatic score is 46%. It is not used in any conclusion.
- **Grounding check (G4) is lexical.** It flags padded paraphrase as unsupported (visible in the Ask page as red highlighting) and has not been checked against human labels.
- **Thresholds.** G1/G2 (0.36 / 0.44) were calibrated on `dev` with the real embedder, but with only 2 negative examples each. They may refuse some on-topic questions on a different repository (for example a very generic question such as "tell me about all 3 commits" retrieved no commit chunks and the model invented commits; the guardrails stripped the invented citations and flagged the answer).
- **Retrieval limitation.** Vague questions do not pull commit chunks when a repo has many code and doc chunks. Retrieval is a single hybrid search (vector + BM25), with no query rewriting.
- **Citations.** Models rarely cite in the requested format; a parser fix now also accepts the evidence-wrapper form some models copy (it changes 4 of 186 answers in run #5, see `scripts/rescore_citations.py`).
- **Model and hardware.** Small local models on one 6 GB GPU. Answers are limited to 300 tokens and the context window to 3072 tokens with an 8-bit KV cache (see section 8); results may differ with larger models or settings.
- **Test split.** The held-out run has not been done; the exploratory deepseek run touched it.

## 8. Reproducibility
**Environment.** Docker Compose stack (gateway, ingest, rag, llm, orchestrator, eval, ChromaDB 1.0.0, web) with host Ollama. Embeddings `all-MiniLM-L6-v2` (sentence-transformers), cosine similarity in ChromaDB, hybrid with BM25 and reciprocal-rank fusion.
**Models (Ollama tags and digests).** `llama2:latest` (78e26419b446), `codellama:7b` (8fdf8f752f6e), `starcoder2:3b` (9f4ae0aff61e), jury `gemma:2b` (b50d6c999e59).
**Fixed settings.** temperature 0, seed 42, max answer 300 tokens, context budget 6000 characters, top-k 8, G1 = 0.36, G2 = 0.44, G4 support >= 0.50. Host Ollama started with `OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0` and `OLLAMA_NUM_CTX=3072`; these were identical for every result in section 5 and are needed to reproduce the speed (and, in principle, small output differences).
**Commands.**
```bash
cp .env.example .env
docker compose -f docker-compose.yml -f docker-compose.demo.yml -f docker-compose.ports.yml up -d --build
python scripts/compose_health.py
MSYS_NO_PATHCONV=1 python scripts/seed_demo.py --container-path /demo       # indexes Ledgerly
python scripts/calibrate_thresholds.py                                        # dev split only
python scripts/run_eval.py --live --repo local__repo --split dev --models llama2,codellama:7b,starcoder2:3b --out reports/dev_full_3models
python scripts/rescore_citations.py reports/dev_full_3models.json
```
**Artefacts.** `reports/dev_full_3models.md` and `.json` (every stored answer, metrics, guardrail trace); `reports/grading_run5.csv` (blind sheet for human grading). The same results are browsable on the website's Evaluation page. Offline CI (`.github/workflows/ci.yml`) runs the unit tests, drift checks and a mock-LLM end-to-end test; mock results are for plumbing only and are never evidence.

## 9. What would make this stronger (next steps, in order of value)
1. A held-out run on a **real repository** with independently written issues and PRs, with 40+ questions whose gold evidence is verified by a human (`docs/OWN_REPO_TEST.md`).
2. **Human grading** of about 60 answers and reporting kappa for the automatic score and the jury; check G4 flags against the same labels.
3. Re-run on the real repository with more models and, if possible, one larger model to test whether the effect depends on model size.
4. Improve retrieval for vague history questions (route "commit/PR/issue" questions to those chunk types) and re-run, keeping the comparison fair by applying it to all runs.
