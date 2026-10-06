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
- **Real repository (held-out):** `pallets/itsdangerous`, 35 questions, results in section 5b. A 3-commit personal repo was also ingested for demonstration only (too little history to test).

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

## 5b. Held-out run on a real repository (run #8: `pallets/itsdangerous`, 399 answers, 0 errors)
This is the test the demo results could not give: a repository whose history was written by other people, for other purposes, and questions that no model or threshold was tuned on.

**Data.** `services/eval/datasets/itsdangerous.json` (hash `b68e5bd36697c3ba`), 35 questions, all `split=test`: 24 history, 4 control (current code), 7 guardrail (3 unanswerable, 2 off-topic, 2 adversarial). Indexed from commit `672971d`: 677 commits, 125 issues, 311 PRs, 7 releases (a snapshot taken with `scripts/fetch_gh_fixture.py`, so the evidence cannot change). Questions were drafted from real issue and PR threads; `scripts/check_dataset.py` confirms every gold reference exists and every key fact occurs in the cited text (28/28 answerable items). The set was committed (`50bdc9e`) before any result was seen. Settings are identical to run #5. A first attempt (run #7) was lost when Docker Desktop stopped at about 70/399 answers; it was discarded unseen and rerun from scratch with no change.

**Pre-registered test: `code_history` minus `code_only`, history categories (n = 24 questions)**
| Model | Difference | 95% CI | p (permutation) | d_z | Verdict by the rule |
|---|---|---|---|---|---|
| llama2 | +0.32 | [+0.07, +0.55] | 0.022 | 0.52 | **history is useful** |
| codellama:7b | +0.28 | [+0.05, +0.49] | 0.033 | 0.48 | **history is useful** |
| starcoder2:3b | -0.02 | [-0.21, +0.17] | 1.00 | -0.04 | inconclusive (no effect) |

Control category (n = 4): `code_history` minus `code_only` = 0.00 for llama2 and codellama by the automatic score (the interval is very wide with 4 questions); a judge-based re-score shows a drop (see the validation paragraph below). Versus `no_context` the history effect is +0.55 (codellama) and +0.57 (llama2), both p = 0.0002.

**Sensitivity to the two weak items.** An independent review after the freeze found it06 and it35 weak (see `services/eval/datasets/itsdangerous.errata.md`). The questions were not edited. Excluding them (`scripts/sensitivity.py`): llama2 +0.33 [+0.09, +0.57], codellama +0.27 [+0.04, +0.51], starcoder2 -0.02 [-0.22, +0.17]. The conclusions do not change.

**Retrieval and citations (all categories pooled).** Evidence recall: `code_only` 0.14, `code_history` 0.70, `oracle` 1.00 (on the demo repository `code_history` reached 1.00). Citation validity in `code_history`: 0.93 (codellama), 1.00 (llama2), 0.89 (starcoder2). The gold evidence was cited in only 1-2% of `code_history` answers, so models mostly state the right fact without citing the exact source.

**Failure analysis (what went wrong, with the actual cases).**
- **Retrieval misses (llama2 3, codellama 2).** For it17 ("Why was 1.0.0 removed from PyPI?") `code_history` retrieved unrelated issues (#92, #47) and commits; recall was 0, and both 7B models then invented a reason ("it was deprecated ... drop Python 2.6"). `code_only` happened to score 1.00 on it17, which is why the *evolution* category (n = 2) is worse with history for codellama (0.00 vs 0.75). It13 (PR #296) is another miss.
- **Refusal gate does not transfer (the clearest negative result).** The three unanswerable questions mention "itsdangerous", so they are topically close to the repository and pass the relevance gates calibrated on the demo repository. The relevance gate never fired on any of them, for any model. `codellama:7b` and `starcoder2:3b` gave invented or speculative answers to all three (for example "Tristan Escalada paid for the library in 2014" for it31 and "rewritten in Rust for memory safety" for it29), scoring 0 in every mode. `llama2` scored 3/3 in `code_history`, but only because the model itself wrote that the evidence did not mention it (an abstention), not because a guardrail stopped it. The gate did fire for the off-topic and prompt-injection questions (it32-it34), so G1 transfers but G2 does not.
- **Model ignored evidence (codellama 3, llama2 1).** For example it18 ("what changed in 1.1.0"): the evidence was retrieved (#111, #112) but codellama still said the default changed from HS256 to HS512 (that was 1.0).
- **starcoder2:3b.** Of its wrong answers, 10 in `code_history` and 18 in `oracle` are tagged hallucinated (the oracle ones even with the gold evidence supplied). It does not benefit from history, as in run #5.
- **Oracle is not an upper bound everywhere.** For design rationale, `oracle` (0.70 / 0.65) was not above `code_history` (0.70 / 0.75): with the gold threads supplied the 7B models still miss key facts, so part of the remaining error is model comprehension, not retrieval.

**Validation of the automatic score (LLM judges; not human grading).** The automatic correctness score is key-fact substring matching, so it was checked against two independent LLM judges, both blind to model and mode (the judge sees only question, gold answer and answer):
- **DeepSeek (`deepseek-chat`), all 399 answers** (`scripts/llm_judge.py`, `reports/deepseek_judge.csv`): quadratic-weighted kappa **0.749**, Spearman 0.757, exact agreement 75%. Where the two differ, the automatic score is mostly too generous: of the 143 answers it scored fully correct, the judge rated 42 (29%) as only partly right or wrong (typically a right fact plus an invented or wrong extra claim, or a missing second fact); of 204 it scored 0, the judge gave credit to 24 (12%). It is weakest on partial-credit answers (17 of 52 agree).
- **GPT, 36 sampled answers** (`reports/gpt_grades.csv`, graded with `reports/GPT_GRADING_PROMPT.md`): kappa **0.939**, exact agreement 89%, no 2-point disagreements. The sample contained only automatic scores of exactly 0 or 1, so this is the easy case; the DeepSeek figure on all 399 answers is the more reliable one.
- **Gemini 3.1 Pro, the same 36 answers** (`reports/gemini_grades.csv`): kappa **0.691**, exact agreement 78%; it is the strictest judge (for example it scored 0 an answer that GPT and DeepSeek accepted because the answer added an invented "closed without action" claim).
- **Human spot check (the project author, 18 rows).** The author, who is not a Python-security expert, graded only the 18 of the 36 sampled answers that can be checked by comparing text with the gold answer (issue numbers, names, a single default value, refusals; `reports/human_grades_easy.csv`, blind to model and mode). Agreement with the automatic score: 18/18 (kappa 1.0). Against the judges: GPT 17/18 (kappa 0.97), DeepSeek 16/18 (0.84), Gemini 16/18 (0.75). The disagreements are row 10 (an empty answer to an unanswerable question: the author and GPT scored it wrong, Gemini and DeepSeek right) and row 24 (a reply that names the right person but also another one, repeated). Two corrections were made after the first pass because some replies contradicted the text, and the final grades are the corrected ones. **Limits:** 18 easy rows by the person who built the system, not an independent expert, and none of the 16 technical "why" answers were human-graded, so this supports the scoring on factual look-ups and refusals only.
- **Judges against each other** (same 36 answers, weighted kappa): GPT-DeepSeek 0.86, GPT-Gemini 0.80, DeepSeek-Gemini 0.83, and each against the automatic score 0.94 (GPT), 0.84 (DeepSeek), 0.69 (Gemini). So the automatic score disagrees with a given LLM judge about as much as the LLM judges disagree with one another (kappa 0.69-0.94 vs 0.80-0.86). They differ mainly on borderline answers (a right fact plus an invented extra, or an empty answer to an unanswerable question).
- These are LLM judges. No human has graded the 36-row sheet yet, so human agreement is still unmeasured.

**Does the headline survive a different scoring method? (`scripts/judge_effect.py`)** Using DeepSeek's scores (rescaled to 0-1) instead of key-fact matching, the history effect (`code_history` minus `code_only`, 24 history questions) is llama2 **+0.35 [+0.15, +0.54]** p 0.006, codellama **+0.35 [+0.12, +0.58]** p 0.016, starcoder2 +0.06 [-0.08, +0.23] (inconclusive). Same conclusions, slightly larger effects. Mean judge score per mode confirms the ordering `no_context` < `code_only` < `code_history` for both 7B models (llama2 0.49 / 0.86 / 1.34, codellama 0.26 / 0.80 / 1.20 out of 2) and a flat picture for starcoder2 (0.29 / 0.46 / 0.51, oracle 0.21).

**New caveat on the control category.** The automatic score shows no loss on the 4 control questions, but the judge does: `code_history` minus `code_only` is **-0.25** (llama2, CI [-0.88, +0.62]) and **-0.12** (codellama, CI [-0.38, 0.00]). The cause is visible in the answers: with history in the prompt, llama2 said the default key derivation is "hmac" and cited an unrelated commit (the code says django-concat), and both models added wrong details to the zlib-compression answer. So history can distract a model on questions that only need the current code. With 4 questions the intervals include 0, so this is a warning sign, not a proven loss, but it means the pre-registered "control loses at most 0.05" condition is **not clearly satisfied** under the judge's scores. We therefore do not claim "no loss on the control".

**Two small notes on scoring.** codellama's answer to it30 begins "the budget was not explicitly mentioned" and then speculates; the automatic score is 0, but a human may judge it differently. This is exactly why human grading is needed (`reports/grading_itsdangerous.csv`, 36 blind rows, not yet graded).

## 6. Interpretation
0. **The headline result now holds on a real repository.** On independent history (run #8), both 7B models pass the pre-registered rule: +0.32 and +0.28 correctness on 24 history questions, intervals excluding 0; the control category (4 questions) shows no loss by the automatic score but a possible drop by an LLM judge, so "no loss" is not claimed. The effect is smaller than on the demo repository (+0.42), as expected when the history is written by strangers and retrieval is harder (recall 0.70 not 1.00). The small model shows no effect on either repository. The remaining weaknesses are retrieval of vague or unusual phrasings and refusal of unanswerable questions about a real repository.
1. **Where history helps.** For both 7B models, adding history raises correctness on history questions from roughly 0.5 to roughly 0.9, with no measured loss on the control question by the automatic score (a judge disagrees, see section 5b). The mechanism is visible in the diagnostics: `code_only` does not retrieve the history that holds the answer (recall 0.19), `code_history` does (1.00), and with the gold evidence handed over directly (`oracle`, answerable questions, n = 16) `llama2` scores 100% and `codellama:7b` 88%, so for these models the bottleneck is retrieval, not reasoning.
2. **What the pre-registered rule concludes.** Only `llama2` satisfies the rule. `codellama:7b` has the same effect size but a wider interval, so by the rule it is "inconclusive", not "no effect".
3. **The 3B model does not benefit.** `starcoder2:3b` is a code-completion model; given evidence it often copies or invents instead of answering (11 hallucinations out of 16 oracle answers). The failure is in model use of evidence, not retrieval.
4. **Do not over-read.** This is 13 history questions on one fictional repository, scored automatically. It shows the pipeline works and the effect is plausible and large for capable models. It is not yet a conclusion about real software projects.

## 7. Limitations, failure cases and sources of bias
- **Circularity (demo repository, partly addressed).** On the demo repository the history, the repository and the gold labels were authored together, so history questions are answerable from history by construction. Run #8 on `pallets/itsdangerous` removes that circularity for the repository and its history, but the questions and gold answers were still drafted by the project team from the same threads (checked by script and by one independent review, not by a second domain expert), so some residual bias towards history-answerable questions remains.
- **Sample size.** 2-10 questions per category; 13 history questions in the dev run, 24 in the held-out run. Confidence intervals are wide. The control category has 3-4 questions, so "no loss" is weak evidence and an LLM judge disagrees (section 5b); the evolution category has 2 and shows a regression with history that cannot be interpreted statistically.
- **Scoring is automatic and unvalidated.** Correctness is substring matching of key facts. It can miss correct paraphrases and can reward long answers that happen to mention a fact. No human grades exist yet, so agreement (kappa) is unmeasured.
- **The LLM jury is not trustworthy.** It scored every model 100% on the answers it graded, including `starcoder2:3b`, whose automatic score is 46%. It is not used in any conclusion.
- **Grounding check (G4) is lexical.** It flags padded paraphrase as unsupported (visible in the Ask page as red highlighting) and has not been checked against human labels.
- **Thresholds.** G1/G2 (0.36 / 0.44) were calibrated on `dev` with the real embedder, but with only 2 negative examples each. They may refuse some on-topic questions on a different repository (for example a very generic question such as "tell me about all 3 commits" retrieved no commit chunks and the model invented commits; the guardrails stripped the invented citations and flagged the answer).
- **Retrieval limitation.** Vague questions do not pull commit chunks when a repo has many code and doc chunks. Retrieval is a single hybrid search (vector + BM25), with no query rewriting.
- **Citations.** Models rarely cite in the requested format; a parser fix now also accepts the evidence-wrapper form some models copy (it changes 4 of 186 answers in run #5, see `scripts/rescore_citations.py`).
- **Model and hardware.** Small local models on one 6 GB GPU. Answers are limited to 300 tokens and the context window to 3072 tokens with an 8-bit KV cache (see section 8); results may differ with larger models or settings.
- **Test split.** The demo repository's `test` split was not run (the exploratory deepseek run touched it); the held-out evidence is the separate itsdangerous set (section 5b). One model-comparison caveat: all three models see the same questions, so the comparison between models is paired, but one repository and 35 questions do not support general claims about model rankings.
- **Guardrail G2 does not transfer** to a real repository (section 5b): refusal of unanswerable but on-topic questions depends on the model, not the gate.
- **Human validation is partial.** A spot check of 18 objectively checkable rows by the project author agreed 18/18 with the automatic score; the 16 technical rationale rows were not human-graded. Automatic scores also agree with LLM judges (DeepSeek kappa 0.75 on 399 answers; GPT 0.94 and Gemini 0.69 on 36), but the 36-row blind sheet has not been graded by a human, so agreement with human judgement is unmeasured. The automatic score over-credits about 29% of its full-credit answers.

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
# held-out real-repository run (section 5b)
python scripts/fetch_gh_fixture.py pallets/itsdangerous demo-data/itsdangerous_fixtures.json
# then index it: POST /api/repos {source: https://github.com/pallets/itsdangerous, issues_file: /demo/itsdangerous_fixtures.json}
python scripts/check_dataset.py services/eval/datasets/itsdangerous.json demo-data/itsdangerous_fixtures.json
python scripts/run_eval.py --live --dataset itsdangerous --repo pallets__itsdangerous --split test --models llama2,codellama:7b,starcoder2:3b --out reports/itsdangerous_heldout
python scripts/sensitivity.py reports/itsdangerous_heldout.json --exclude it06,it35
```
**Artefacts.** `reports/dev_full_3models.md` and `.json` (every stored answer, metrics, guardrail trace); `reports/itsdangerous_heldout.md` and `.json` (run #8), `reports/grading_itsdangerous.csv` (blind sheet for human grading). The same results are browsable on the website's Evaluation page. Offline CI (`.github/workflows/ci.yml`) runs the unit tests, drift checks and a mock-LLM end-to-end test; mock results are for plumbing only and are never evidence.

## 9. What would make this stronger (next steps, in order of value)
1. Done in part: a held-out run on a real repository (section 5b). Still needed: a second human to verify the 35 gold answers, and more questions (40+) from a second real repository.
2. **Human grading** of the 36 blind rows (`reports/grading_itsdangerous.csv`): a human grades about 10-36 and we report agreement with the LLM judges and the automatic score; check G4 flags against the same labels.
3. Re-run on the real repository with more models and, if possible, one larger model to test whether the effect depends on model size.
4. Fix the two failures section 5b exposed: retrieval misses on unusual phrasings (it17, it13) and a refusal gate that works for unanswerable-but-on-topic questions (recalibrate G2 on negatives from several repositories). Improve retrieval for vague history questions (route "commit/PR/issue" questions to those chunk types) and re-run, keeping the comparison fair by applying it to all runs.
