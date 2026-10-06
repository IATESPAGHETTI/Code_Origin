# Viva preparation: be able to explain and defend every part

Read `docs/EVALUATION.md` first; this sheet is the short version plus likely questions. If you cannot answer a question below in your own words, that is the part to study.

## The 60-second pitch
Code shows *what* exists; the reason it exists is in the history around it (commits, issues, PRs, reviews). CodeOrigin is a RAG system that indexes both, answers "why was it built this way?" with citations, and refuses when the evidence does not say. We test the research question *does adding repository history improve answers?* by asking the same questions in four modes (no context, code only, code + history, oracle) with everything else held constant, and judging the result with a rule we fixed beforehand. On a seeded demo repository history raised correctness from about 0.5 to about 0.9 for two 7B models. We then ran a held-out test on a real repository, pallets/itsdangerous (677 commits, 125 issues, 311 PRs, history written by strangers): both 7B models pass the rule (+0.32 and +0.28 correctness, intervals excluding 0; an LLM judge confirms the effect, though it also hints that history can slightly hurt questions that only need the code) and the 3B model shows no effect. It is the first real evidence for the research question, still limited by 24 history questions and automatic scoring.

## Numbers worth remembering
**Held-out real repository (run #8, pallets/itsdangerous, 35 questions, 399 answers):** history effect (`code_history` minus `code_only`, 24 history questions): llama2 +0.32 [+0.07, +0.55] p 0.022; codellama:7b +0.28 [+0.05, +0.49] p 0.033; starcoder2:3b -0.02 [-0.21, +0.17]. Both 7B models pass the rule. Evidence recall 0.14 (`code_only`) vs 0.70 (`code_history`). Excluding the two items an independent review flagged (it06, it35): +0.33 and +0.27, same conclusions. Scoring validated against LLM judges: DeepSeek kappa 0.75 (399 answers), GPT kappa 0.94 (36); judge-scored history effect +0.35 / +0.35 (llama2 / codellama). Control category under the judge: -0.25 / -0.12 (n=4, CIs include 0). Dataset hash `b68e5bd36697c3ba`, committed before the run.

**Demo repository (run #5, dev split):**
- 43 questions in the dataset (23 dev, 20 test); 13 history questions in the dev comparison; control category 3.
- Overall correctness `no_context` / `code_only` / `code_history`: llama2 26% / 67% / 91%; codellama:7b 30% / 67% / 91%; starcoder2:3b 17% / 41% / 46%.
- History effect (`code_history` minus `code_only`): llama2 +0.42 [+0.15, +0.69] (passes the rule); codellama +0.42 [0.00, +0.73] (inconclusive); starcoder2 +0.08 [0.00, +0.19] (inconclusive).
- Evidence recall: `code_only` 0.19 vs `code_history` 1.00. Oracle correctness on answerable questions: llama2 100%, codellama 88%, starcoder2 19%.
- Decision rule: at least +0.10, CI excludes 0, control loses at most 0.05.
- 142 backend + 20 frontend tests; CI has 11 jobs, all green; 7 containers; 10 guardrails (G1 to G10).

## Research and method
**What is the research question and why is it meaningful?** Does repository history improve answers about *why*? It matters because current assistants only see current code, so rationale questions become guesses.

**Why four modes?** `no_context` shows what the model already "knows" or guesses. `code_only` is the realistic baseline (what most tools do). `code_history` is the treatment. `oracle` gives the model the gold evidence with no retrieval, so if a model still fails there, the problem is model use of evidence, not retrieval.

**How do you make the comparison fair?** Same prompt shape, same context budget (6000 characters), temperature 0, fixed seed, same questions in every mode. So a difference can only come from which evidence is shown.

**Why fix a decision rule in advance?** To stop us choosing a favourable reading after seeing results. +0.10 is the smallest improvement we would call practically useful; requiring the CI to exclude 0 guards against noise; the control category guards against history making simple questions worse.

**What is a bootstrap confidence interval? A permutation test? Cohen's d_z?** Bootstrap: resample the per-question scores with replacement many times; the middle 95% of the resampled means is the interval. Paired permutation (sign-flip) test: if history made no difference, the sign of each question's difference is arbitrary, so we flip signs at random and see how often we get a difference as large as observed (the p-value). d_z: the mean paired difference divided by its standard deviation, a standardised effect size.

**Why is only llama2 "useful" when codellama has the same effect?** Same mean difference (+0.42), but codellama's interval touches 0 (its per-question differences vary more), so by the rule it is "inconclusive". It means "not enough evidence", not "no effect".

**How is correctness computed, and what is its weakness?** The fraction of expected key facts that appear in the answer (any accepted phrasing, substring match); for questions that should be refused, 1 if the system refused or abstained. Weaknesses: it misses correct paraphrases and can reward long answers that mention a fact in passing. That is why human grading is the next step.

**Why not use the LLM jury?** We built one (`gemma:2b`, not a compared model, to avoid self-preference) but it gave 100% to every model, even the weakest, so it is too lenient. A judge is only trustworthy once it agrees with humans (kappa >= 0.6); we have not measured that.

**What are the biggest threats to validity?** Circularity (on the demo repository we wrote everything together; on the real repository we drafted the questions from its threads), tiny sample, automatic scoring, one repository, small local models, and dev/test discipline (thresholds tuned on dev only; an exploratory fourth-model run touched the test items and is excluded).

**What would you do with more time?** Human grading of the blind sheet to measure kappa for the automatic score, a second person verifying the gold answers, a second real repository with 40+ questions, a fix for the two weaknesses found (retrieval of unusual phrasings, refusal of on-topic unanswerable questions), and a larger model to see whether the effect depends on size.

## Implementation
**How does retrieval work?** Hybrid: vector similarity (all-MiniLM-L6-v2 embeddings in ChromaDB) plus BM25 keyword search (so exact SHAs, issue numbers and identifiers still match), fused with reciprocal-rank fusion. Commits, diffs, issues, PRs and reviews are cross-linked (`#123` mentions, PR merge commits), so retrieving one pulls in the others that explain it.

**What does "ingestion" do?** Clones the repo, reads commits and diffs, pulls issues/PRs/reviews/releases from the GitHub API, builds the link graph, chunks everything (functions for Python, headings for docs), redacts secrets *before* indexing, and stores deterministic chunk IDs so re-ingesting never duplicates.

**Name the guardrails.** G1 off-topic refusal (no model call); G2 insufficient-history ("the history doesn't say"); G3 citation check (invented citations stripped); G4 grounding (each sentence must be supported); G5 prompt-injection defence (commit text treated as untrusted data); G6 secret redaction (at ingest and in output); G7 input limits, rate limit, API key; G8 repository isolation; G9 webhook signature check; G10 refuse requests for secrets or commands. They are enforced in code, not by asking the model to behave.

**What happens on a vague question like "tell me about all 3 commits"?** Retrieval may return no commit chunks (code and docs outscore them), and the model can invent commits. The guardrails catch it (invented citations stripped, answer flagged), but the underlying retrieval limitation remains; asking about specifics works.

**Why do answers sometimes show red highlighting?** That is G4 flagging sentences with weak lexical support, often padded paraphrase. It is a heuristic that has not been validated against humans; we deliberately did not loosen the threshold to make output look cleaner.

**Why does `starcoder2:3b` do so badly?** It is a code-completion model: given evidence it often copies or invents instead of answering (11 of 16 oracle answers hallucinated). Retrieval was not its problem.

## DevOps
**What is the pipeline?** 7 multi-stage, non-root containers with health checks; Docker Compose with dev/prod/monitoring/demo overrides; GitHub Actions CI (lint, drift checks, 6 test jobs, frontend build, security scan with gitleaks and Trivy, compose smoke test, end-to-end eval gate); a release workflow that scans and publishes images to GHCR on a version tag; Prometheus, Grafana and Loki for monitoring.

**What did running CI for real find?** A HIGH-severity vulnerability in a frontend dependency, Dockerfiles running as root, linter-version drift, a wrong script call in the smoke test, and a wrong action version. All fixed; the pipeline is green.

**What does "reproducible" mean here?** One command brings up the stack; settings, model digests and dataset hash are recorded (`docs/EVALUATION.md` section 8); results are stored and browsable; deterministic demo repository so SHAs and gold labels do not drift.

## Which model is best for what? (see docs/EVALUATION.md section 5c)
- **Explanation, bug analysis, dependency links (issue/PR/commit relations):** llama2 and codellama:7b tie (differences under 0.10 on 4-10 questions each); starcoder2:3b is far behind (0.15-0.50).
- **Code retrieval (lookups in current code):** codellama:7b best (1.00 vs llama2 0.75), only 4 questions.
- **RAG overall:** llama2 and codellama tie on accuracy (0.77 vs 0.74 on answerable questions); llama2 is about twice as fast (8.3 s vs 16.1 s median), codellama hallucinated less (20% vs 29%).
- **Code generation, refactoring, test-pass rate:** not evaluated; the system answers questions, it does not write code. Say so plainly; do not invent numbers.
- **Metrics measured:** correctness, hallucination rate, retrieval recall/precision, latency, tokens; relevance is not scored separately.

## Honest answers to hard questions
- *"Does history really help?"* On this dataset, for capable models, yes and by a large margin; but the repository is fictional and the sample small, so we claim it is promising, not proven.
- *"Isn't the test biased towards history?"* On the demo repository, yes, by construction. That is why we ran a held-out test on a real repository whose history we did not write. Some bias remains because we drafted the questions from its threads (script-checked, one independent review found 2 weak items out of 35; we did not edit them and report results with and without).
- *"What went wrong on the real repository?"* Retrieval missed on some phrasings (recall 0.70, not 1.00; for "why was 1.0.0 removed from PyPI" it fetched unrelated issues and both models invented a reason). And the refusal gate for unanswerable questions did not transfer: codellama invented a customer name for "who was the first paying customer" because the question is topically close to the repo. Only the model itself abstained for llama2.
- *"Did you cherry-pick or change the test?"* No. The 35 questions were committed before the run (commit 50bdc9e); a first run crashed (Docker stopped) and was rerun unchanged; a review after the freeze led to errata, not edits.
- *"Why trust your scoring?"* Correctness is automatic key-fact matching, so we checked it against two blind LLM judges: DeepSeek on all 399 answers (kappa 0.75, good) and, on a 36-answer sample, GPT (0.94) and Gemini (0.69); the judges agree with each other at 0.80-0.86, so the automatic score disagrees with a judge about as much as judges disagree among themselves. The automatic score is somewhat generous (it gave full credit to 143 answers; DeepSeek rated 42 of them as only partly right or wrong). Re-scoring the whole comparison with DeepSeek gives the same conclusion (+0.35 for both 7B models). I also graded by hand the 18 of the 36 sampled answers that can be checked by comparing text (issue numbers, names, refusals) and agreed with the automatic score on all 18; I did not grade the 16 technical "why" answers because I cannot judge those, so human validation covers factual look-ups only.
- *"Does history ever hurt?"* Possibly. On the 4 questions that only need the current code, an LLM judge scores `code_history` lower than `code_only` (-0.25 llama2, -0.12 codellama; intervals include 0). Example: with history in the prompt llama2 said the default key derivation is "hmac" and cited an unrelated commit. With only 4 questions it is a warning sign, not a proven loss, and the automatic score did not show it.
- *"What is not done?"* Human grading (the 36-row blind sheet is ready; so far a hand check of 18 factual rows plus LLM judges have been compared with the automatic score; the 16 technical rows need a Python-savvy human), a second human check of the gold answers, a second real repository, and fixing the two weaknesses above.
