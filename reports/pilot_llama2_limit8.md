# CodeOrigin evaluation report

- Dataset: `demo` (hash `b96ac1b512bac60f`)
- Models: llama2; modes: no_context, code_only, code_history, oracle
- Items scored: 32 (0 errors); split: dev
- Temperature 0, fixed seed; identical context budget across modes.

## Verdict (pre-registered rule)

History is *useful* if code_history beats code_only on history categories by >= 0.10 correctness with a 95% CI excluding 0, without losing more than 0.05 on the control category.

| Model | Verdict | history diff (95% CI) |
|---|---|---|
| llama2 | **history is useful** | +0.44 [+0.25, +0.62] |

## llama2: correctness by category

| Category | no_context | code_only | code_history | oracle |
|---|---|---|---|---|
| design_rationale | 0.50 [0.50-0.50] n=4 | 0.50 [0.50-0.50] n=4 | 0.88 [0.62-1.00] n=4 | 0.88 [0.62-1.00] n=4 |
| bug_origin | 0.50 [0.50-0.50] n=2 | 0.50 [0.50-0.50] n=2 | 1.00 [1.00-1.00] n=2 | 1.00 [1.00-1.00] n=2 |
| change_attribution | 0.00 [0.00-0.00] n=2 | 0.00 [0.00-0.00] n=2 | 0.50 [0.00-1.00] n=2 | 1.00 [1.00-1.00] n=2 |

## Retrieval, citations, hallucination and cost (all categories pooled)

| Model | Mode | evidence recall | evidence precision | gold cited | citation validity | unsupported claims | refusal correct | p50-ish latency ms | tokens in/out |
|---|---|---|---|---|---|---|---|---|---|
| llama2 | no_context | - | - | - | - | - | 1.00 | 4163.225 | 73.0/75.125 |
| llama2 | code_only | 0.00 | 0.00 | 0.00 | 0.00 | 0.84 | 1.00 | 17612.025 | 1292.0/238.125 |
| llama2 | code_history | 1.00 | 0.43 | 0.06 | 1.00 | 0.34 | 1.00 | 10468.2 | 1630.625/121.125 |
| llama2 | oracle | 1.00 | 1.00 | 0.12 | 1.00 | 0.23 | 1.00 | 8144.175 | 970.625/107.625 |

## Paired comparisons (treatment - baseline, correctness)

| Model | Items | Baseline -> code_history | n | mean diff | 95% CI | p (sign-flip) | d_z |
|---|---|---|---|---|---|---|---|
| llama2 | history | code_only | 8 | +0.44 | [+0.25, +0.62] | 0.0312 | 1.365 |
| llama2 | history | no_context | 8 | +0.44 | [+0.25, +0.62] | 0.0312 | 1.365 |

## Failure analysis (why answers were wrong)

| Model | Mode | ok | retrieval_miss | model_ignored_evidence | hallucinated | over_refused | under_refused | no_evidence_given |
|---|---|---|---|---|---|---|---|---|
| llama2 | code_history | 7 | 0 | 1 | 0 | 0 | 0 | 0 |
| llama2 | code_only | 6 | 2 | 0 | 0 | 0 | 0 | 0 |
| llama2 | no_context | 6 | 0 | 0 | 0 | 0 | 0 | 2 |
| llama2 | oracle | 8 | 0 | 0 | 0 | 0 | 0 | 0 |

_Limits: small samples give wide intervals; automatic correctness is key-fact matching, calibrated against human grades (see calibration)._