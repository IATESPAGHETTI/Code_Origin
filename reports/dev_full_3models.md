# CodeOrigin evaluation report

- Dataset: `demo` (hash `b96ac1b512bac60f`)
- Models: codellama:7b, llama2, starcoder2:3b; modes: no_context, code_only, code_history, oracle
- Items scored: 255 (0 errors); split: dev
- Temperature 0, fixed seed; identical context budget across modes.

## Verdict (pre-registered rule)

History is *useful* if code_history beats code_only on history categories by >= 0.10 correctness with a 95% CI excluding 0, without losing more than 0.05 on the control category.

| Model | Verdict | history diff (95% CI) |
|---|---|---|
| codellama:7b | **inconclusive** | +0.42 [+0.00, +0.73] |
| llama2 | **history is useful** | +0.42 [+0.15, +0.69] |
| starcoder2:3b | **inconclusive** | +0.08 [+0.00, +0.19] |

## codellama:7b: correctness by category

| Category | no_context | code_only | code_history | oracle |
|---|---|---|---|---|
| design_rationale | 0.50 [0.12-0.88] n=4 | 0.75 [0.50-1.00] n=4 | 0.50 [0.00-1.00] n=4 | 0.50 [0.00-1.00] n=4 |
| bug_origin | 0.75 [0.50-1.00] n=2 | 0.75 [0.50-1.00] n=2 | 1.00 [1.00-1.00] n=2 | 1.00 [1.00-1.00] n=2 |
| change_attribution | 0.00 [0.00-0.00] n=3 | 0.00 [0.00-0.00] n=3 | 1.00 [1.00-1.00] n=3 | 1.00 [1.00-1.00] n=3 |
| issue_linkage | 0.00 [0.00-0.00] n=2 | 0.00 [0.00-0.00] n=2 | 1.00 [1.00-1.00] n=2 | 1.00 [1.00-1.00] n=2 |
| evolution | 0.25 [0.00-0.50] n=2 | 0.50 [0.50-0.50] n=2 | 1.00 [1.00-1.00] n=2 | 1.00 [1.00-1.00] n=2 |
| current_state | 0.33 [0.00-0.50] n=3 | 1.00 [1.00-1.00] n=3 | 1.00 [1.00-1.00] n=3 | 1.00 [1.00-1.00] n=3 |
| unanswerable | 0.00 [0.00-0.00] n=3 | 1.00 [1.00-1.00] n=3 | 1.00 [1.00-1.00] n=3 | - |
| off_topic | 0.00 [0.00-0.00] n=2 | 1.00 [1.00-1.00] n=2 | 1.00 [1.00-1.00] n=2 | - |
| adversarial | 1.00 [1.00-1.00] n=2 | 1.00 [1.00-1.00] n=2 | 1.00 [1.00-1.00] n=2 | - |

## llama2: correctness by category

| Category | no_context | code_only | code_history | oracle |
|---|---|---|---|---|
| design_rationale | 0.50 [0.50-0.50] n=4 | 0.62 [0.50-0.88] n=4 | 0.75 [0.50-1.00] n=4 | 1.00 [1.00-1.00] n=4 |
| bug_origin | 0.50 [0.50-0.50] n=2 | 0.75 [0.50-1.00] n=2 | 1.00 [1.00-1.00] n=2 | 1.00 [1.00-1.00] n=2 |
| change_attribution | 0.00 [0.00-0.00] n=3 | 0.00 [0.00-0.00] n=3 | 0.67 [0.00-1.00] n=3 | 1.00 [1.00-1.00] n=3 |
| issue_linkage | 0.00 [0.00-0.00] n=2 | 0.00 [0.00-0.00] n=2 | 1.00 [1.00-1.00] n=2 | 1.00 [1.00-1.00] n=2 |
| evolution | 0.00 [0.00-0.00] n=2 | 0.75 [0.50-1.00] n=2 | 1.00 [1.00-1.00] n=2 | 1.00 [1.00-1.00] n=2 |
| current_state | 0.33 [0.00-0.50] n=3 | 1.00 [1.00-1.00] n=3 | 1.00 [1.00-1.00] n=3 | 1.00 [1.00-1.00] n=3 |
| unanswerable | 0.00 [0.00-0.00] n=3 | 1.00 [1.00-1.00] n=3 | 1.00 [1.00-1.00] n=3 | - |
| off_topic | 0.00 [0.00-0.00] n=2 | 1.00 [1.00-1.00] n=2 | 1.00 [1.00-1.00] n=2 | - |
| adversarial | 1.00 [1.00-1.00] n=2 | 1.00 [1.00-1.00] n=2 | 1.00 [1.00-1.00] n=2 | - |

## starcoder2:3b: correctness by category

| Category | no_context | code_only | code_history | oracle |
|---|---|---|---|---|
| design_rationale | 0.12 [0.00-0.38] n=4 | 0.12 [0.00-0.38] n=4 | 0.25 [0.00-0.50] n=4 | 0.12 [0.00-0.38] n=4 |
| bug_origin | 0.25 [0.00-0.50] n=2 | 0.50 [0.50-0.50] n=2 | 0.50 [0.50-0.50] n=2 | 0.75 [0.50-1.00] n=2 |
| change_attribution | 0.00 [0.00-0.00] n=3 | 0.00 [0.00-0.00] n=3 | 0.00 [0.00-0.00] n=3 | 0.00 [0.00-0.00] n=3 |
| issue_linkage | 0.00 [0.00-0.00] n=2 | 0.00 [0.00-0.00] n=2 | 0.00 [0.00-0.00] n=2 | 0.00 [0.00-0.00] n=2 |
| evolution | 0.00 [0.00-0.00] n=2 | 0.00 [0.00-0.00] n=2 | 0.25 [0.00-0.50] n=2 | 0.00 [0.00-0.00] n=2 |
| current_state | 0.33 [0.00-0.50] n=3 | 0.33 [0.00-0.50] n=3 | 0.33 [0.00-0.50] n=3 | 0.33 [0.00-0.50] n=3 |
| unanswerable | 0.00 [0.00-0.00] n=3 | 1.00 [1.00-1.00] n=3 | 1.00 [1.00-1.00] n=3 | - |
| off_topic | 0.00 [0.00-0.00] n=2 | 1.00 [1.00-1.00] n=2 | 1.00 [1.00-1.00] n=2 | - |
| adversarial | 1.00 [1.00-1.00] n=2 | 1.00 [1.00-1.00] n=2 | 1.00 [1.00-1.00] n=2 | - |

## Retrieval, citations, hallucination and cost (all categories pooled)

| Model | Mode | evidence recall | evidence precision | gold cited | citation validity | unsupported claims | refusal correct | p50-ish latency ms | tokens in/out |
|---|---|---|---|---|---|---|---|---|---|
| codellama:7b | no_context | - | - | - | - | - | 0.78 | 3238.191 | 65.696/92.174 |
| codellama:7b | code_only | 0.19 | 0.04 | 0.00 | 0.50 | 0.77 | 1.00 | 9413.209 | 924.087/173.0 |
| codellama:7b | code_history | 1.00 | 0.36 | 0.28 | 1.00 | 0.29 | 1.00 | 9137.809 | 1170.87/118.261 |
| codellama:7b | oracle | 1.00 | 1.00 | 0.22 | 1.00 | 0.19 | 1.00 | 6675.631 | 973.688/109.125 |
| llama2 | no_context | - | - | - | - | - | 0.78 | 2307.791 | 65.696/54.13 |
| llama2 | code_only | 0.19 | 0.04 | 0.00 | 0.00 | 0.80 | 1.00 | 9435.143 | 924.087/151.652 |
| llama2 | code_history | 1.00 | 0.36 | 0.09 | 1.00 | 0.31 | 1.00 | 7682.543 | 1170.87/84.087 |
| llama2 | oracle | 1.00 | 1.00 | 0.21 | 1.00 | 0.32 | 1.00 | 6938.994 | 973.688/115.562 |
| starcoder2:3b | no_context | - | - | - | - | - | 0.78 | 2179.191 | 23.957/167.609 |
| starcoder2:3b | code_only | 0.19 | 0.04 | 0.00 | - | 0.78 | 1.00 | 638.43 | 753.913/23.565 |
| starcoder2:3b | code_history | 1.00 | 0.36 | 0.00 | - | 0.57 | 1.00 | 852.291 | 1005.304/34.522 |
| starcoder2:3b | oracle | 1.00 | 1.00 | 0.00 | - | 0.62 | 1.00 | 856.725 | 782.812/53.188 |

## Paired comparisons (treatment - baseline, correctness)

| Model | Items | Baseline -> code_history | n | mean diff | 95% CI | p (sign-flip) | d_z |
|---|---|---|---|---|---|---|---|
| codellama:7b | history | code_only | 13 | +0.42 | [+0.00, +0.73] | 0.087 | 0.602 |
| codellama:7b | history | no_context | 13 | +0.54 | [+0.15, +0.85] | 0.0274 | 0.816 |
| codellama:7b | control | code_only | 3 | +0.00 | [+0.00, +0.00] | 1.0 | 0.0 |
| codellama:7b | control | no_context | 3 | +0.67 | [+0.50, +1.00] | 0.25 | 2.309 |
| codellama:7b | guardrail | code_only | 7 | +0.00 | [+0.00, +0.00] | 1.0 | 0.0 |
| codellama:7b | guardrail | no_context | 7 | +0.71 | [+0.43, +1.00] | 0.0625 | 1.464 |
| llama2 | history | code_only | 13 | +0.42 | [+0.15, +0.69] | 0.0232 | 0.857 |
| llama2 | history | no_context | 13 | +0.61 | [+0.39, +0.81] | 0.0006 | 1.479 |
| llama2 | control | code_only | 3 | +0.00 | [+0.00, +0.00] | 1.0 | 0.0 |
| llama2 | control | no_context | 3 | +0.67 | [+0.50, +1.00] | 0.25 | 2.309 |
| llama2 | guardrail | code_only | 7 | +0.00 | [+0.00, +0.00] | 1.0 | 0.0 |
| llama2 | guardrail | no_context | 7 | +0.71 | [+0.43, +1.00] | 0.0625 | 1.464 |
| starcoder2:3b | history | code_only | 13 | +0.08 | [+0.00, +0.19] | 0.4961 | 0.41 |
| starcoder2:3b | history | no_context | 13 | +0.12 | [-0.04, +0.27] | 0.3741 | 0.385 |
| starcoder2:3b | control | code_only | 3 | +0.00 | [+0.00, +0.00] | 1.0 | 0.0 |
| starcoder2:3b | control | no_context | 3 | +0.00 | [+0.00, +0.00] | 1.0 | 0.0 |
| starcoder2:3b | guardrail | code_only | 7 | +0.00 | [+0.00, +0.00] | 1.0 | 0.0 |
| starcoder2:3b | guardrail | no_context | 7 | +0.71 | [+0.43, +1.00] | 0.0625 | 1.464 |

## Failure analysis (why answers were wrong)

| Model | Mode | ok | retrieval_miss | model_ignored_evidence | hallucinated | over_refused | under_refused | no_evidence_given |
|---|---|---|---|---|---|---|---|---|
| codellama:7b | code_history | 21 | 0 | 2 | 0 | 0 | 0 | 0 |
| codellama:7b | code_only | 18 | 5 | 0 | 0 | 0 | 0 | 0 |
| codellama:7b | no_context | 10 | 0 | 0 | 0 | 0 | 5 | 8 |
| codellama:7b | oracle | 14 | 0 | 2 | 0 | 0 | 0 | 0 |
| llama2 | code_history | 22 | 0 | 1 | 0 | 0 | 0 | 0 |
| llama2 | code_only | 18 | 5 | 0 | 0 | 0 | 0 | 0 |
| llama2 | no_context | 10 | 0 | 0 | 0 | 0 | 5 | 8 |
| llama2 | oracle | 16 | 0 | 0 | 0 | 0 | 0 | 0 |
| starcoder2:3b | code_history | 14 | 0 | 1 | 8 | 0 | 0 | 0 |
| starcoder2:3b | code_only | 12 | 10 | 0 | 1 | 0 | 0 | 0 |
| starcoder2:3b | no_context | 6 | 0 | 0 | 0 | 0 | 5 | 12 |
| starcoder2:3b | oracle | 5 | 0 | 0 | 11 | 0 | 0 | 0 |

_Limits: small samples give wide intervals; automatic correctness is key-fact matching, calibrated against human grades (see calibration)._