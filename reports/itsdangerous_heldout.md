# CodeOrigin evaluation report

- Dataset: `itsdangerous` (hash `b68e5bd36697c3ba`)
- Models: codellama:7b, llama2, starcoder2:3b; modes: no_context, code_only, code_history, oracle
- Items scored: 399 (0 errors); split: test
- Temperature 0, fixed seed; identical context budget across modes.

## Verdict (pre-registered rule)

History is *useful* if code_history beats code_only on history categories by >= 0.10 correctness with a 95% CI excluding 0, without losing more than 0.05 on the control category.

| Model | Verdict | history diff (95% CI) |
|---|---|---|
| codellama:7b | **history is useful** | +0.28 [+0.05, +0.49] |
| llama2 | **history is useful** | +0.32 [+0.07, +0.55] |
| starcoder2:3b | **inconclusive** | -0.02 [-0.21, +0.17] |

## codellama:7b: correctness by category

| Category | no_context | code_only | code_history | oracle |
|---|---|---|---|---|
| design_rationale | 0.20 [0.00-0.45] n=10 | 0.35 [0.10-0.60] n=10 | 0.70 [0.45-0.90] n=10 | 0.70 [0.50-0.90] n=10 |
| bug_origin | 0.25 [0.00-0.58] n=6 | 0.50 [0.25-0.75] n=6 | 0.61 [0.22-0.94] n=6 | 0.92 [0.75-1.00] n=6 |
| change_attribution | 0.00 [0.00-0.00] n=2 | 0.00 [0.00-0.00] n=2 | 1.00 [1.00-1.00] n=2 | 1.00 [1.00-1.00] n=2 |
| issue_linkage | 0.00 [0.00-0.00] n=4 | 0.50 [0.00-1.00] n=4 | 1.00 [1.00-1.00] n=4 | 1.00 [1.00-1.00] n=4 |
| evolution | 0.00 [0.00-0.00] n=2 | 0.75 [0.50-1.00] n=2 | 0.00 [0.00-0.00] n=2 | 0.75 [0.50-1.00] n=2 |
| current_state | 0.00 [0.00-0.00] n=4 | 1.00 [1.00-1.00] n=4 | 1.00 [1.00-1.00] n=4 | 0.50 [0.00-1.00] n=4 |
| unanswerable | 0.00 [0.00-0.00] n=3 | 0.00 [0.00-0.00] n=3 | 0.00 [0.00-0.00] n=3 | - |
| off_topic | 0.00 [0.00-0.00] n=2 | 1.00 [1.00-1.00] n=2 | 1.00 [1.00-1.00] n=2 | - |
| adversarial | 0.50 [0.00-1.00] n=2 | 0.50 [0.00-1.00] n=2 | 0.50 [0.00-1.00] n=2 | - |

## llama2: correctness by category

| Category | no_context | code_only | code_history | oracle |
|---|---|---|---|---|
| design_rationale | 0.25 [0.05-0.50] n=10 | 0.45 [0.15-0.70] n=10 | 0.75 [0.50-1.00] n=10 | 0.65 [0.40-0.90] n=10 |
| bug_origin | 0.42 [0.17-0.67] n=6 | 0.42 [0.17-0.67] n=6 | 0.69 [0.36-0.94] n=6 | 0.83 [0.67-1.00] n=6 |
| change_attribution | 0.00 [0.00-0.00] n=2 | 0.00 [0.00-0.00] n=2 | 1.00 [1.00-1.00] n=2 | 1.00 [1.00-1.00] n=2 |
| issue_linkage | 0.00 [0.00-0.00] n=4 | 0.50 [0.00-1.00] n=4 | 1.00 [1.00-1.00] n=4 | 1.00 [1.00-1.00] n=4 |
| evolution | 0.00 [0.00-0.00] n=2 | 1.00 [1.00-1.00] n=2 | 0.50 [0.00-1.00] n=2 | 0.75 [0.50-1.00] n=2 |
| current_state | 0.25 [0.00-0.75] n=4 | 0.75 [0.25-1.00] n=4 | 0.75 [0.25-1.00] n=4 | 0.25 [0.00-0.75] n=4 |
| unanswerable | 0.00 [0.00-0.00] n=3 | 0.67 [0.00-1.00] n=3 | 1.00 [1.00-1.00] n=3 | - |
| off_topic | 0.00 [0.00-0.00] n=2 | 1.00 [1.00-1.00] n=2 | 1.00 [1.00-1.00] n=2 | - |
| adversarial | 0.50 [0.00-1.00] n=2 | 0.50 [0.00-1.00] n=2 | 1.00 [1.00-1.00] n=2 | - |

## starcoder2:3b: correctness by category

| Category | no_context | code_only | code_history | oracle |
|---|---|---|---|---|
| design_rationale | 0.05 [0.00-0.15] n=10 | 0.25 [0.05-0.45] n=10 | 0.15 [0.00-0.35] n=10 | 0.15 [0.00-0.30] n=10 |
| bug_origin | 0.22 [0.00-0.56] n=6 | 0.17 [0.00-0.33] n=6 | 0.17 [0.00-0.33] n=6 | 0.22 [0.00-0.56] n=6 |
| change_attribution | 0.00 [0.00-0.00] n=2 | 0.00 [0.00-0.00] n=2 | 0.00 [0.00-0.00] n=2 | 0.50 [0.00-1.00] n=2 |
| issue_linkage | 0.00 [0.00-0.00] n=4 | 0.25 [0.00-0.75] n=4 | 0.50 [0.00-1.00] n=4 | 0.25 [0.00-0.75] n=4 |
| evolution | 0.00 [0.00-0.00] n=2 | 0.25 [0.00-0.50] n=2 | 0.00 [0.00-0.00] n=2 | 0.00 [0.00-0.00] n=2 |
| current_state | 0.50 [0.00-1.00] n=4 | 0.50 [0.00-1.00] n=4 | 0.25 [0.00-0.75] n=4 | 0.00 [0.00-0.00] n=4 |
| unanswerable | 0.00 [0.00-0.00] n=3 | 0.00 [0.00-0.00] n=3 | 0.00 [0.00-0.00] n=3 | - |
| off_topic | 0.00 [0.00-0.00] n=2 | 1.00 [1.00-1.00] n=2 | 1.00 [1.00-1.00] n=2 | - |
| adversarial | 0.50 [0.00-1.00] n=2 | 0.50 [0.00-1.00] n=2 | 0.50 [0.00-1.00] n=2 | - |

## Retrieval, citations, hallucination and cost (all categories pooled)

| Model | Mode | evidence recall | evidence precision | gold cited | citation validity | unsupported claims | refusal correct | p50-ish latency ms | tokens in/out |
|---|---|---|---|---|---|---|---|---|---|
| codellama:7b | no_context | - | - | - | - | - | 0.83 | 4928.991 | 81.286/99.057 |
| codellama:7b | code_only | 0.14 | 0.05 | 0.04 | 0.12 | 0.47 | 0.89 | 14311.077 | 1762.029/179.6 |
| codellama:7b | code_history | 0.70 | 0.25 | 0.02 | 0.93 | 0.26 | 0.89 | 14455.477 | 2031.829/173.429 |
| codellama:7b | oracle | 1.00 | 1.00 | 0.04 | 1.00 | 0.20 | 1.00 | 10698.807 | 1136.286/160.036 |
| llama2 | no_context | - | - | - | - | - | 0.83 | 4312.111 | 81.286/73.657 |
| llama2 | code_only | 0.14 | 0.05 | 0.04 | 0.75 | 0.55 | 0.94 | 16521.077 | 1762.029/183.229 |
| llama2 | code_history | 0.70 | 0.25 | 0.02 | 1.00 | 0.27 | 1.00 | 12035.063 | 2031.829/125.8 |
| llama2 | oracle | 1.00 | 1.00 | 0.09 | 1.00 | 0.27 | 1.00 | 10119.996 | 1136.286/140.357 |
| starcoder2:3b | no_context | - | - | - | - | - | 0.83 | 2260.543 | 36.8/238.171 |
| starcoder2:3b | code_only | 0.14 | 0.05 | 0.00 | - | 0.53 | 0.89 | 2193.757 | 1473.2/150.0 |
| starcoder2:3b | code_history | 0.70 | 0.25 | 0.01 | 0.89 | 0.37 | 0.89 | 2251.309 | 1780.6/147.286 |
| starcoder2:3b | oracle | 1.00 | 1.00 | 0.04 | 0.50 | 0.52 | 1.00 | 1356.718 | 931.464/106.536 |

## Paired comparisons (treatment - baseline, correctness)

| Model | Items | Baseline -> code_history | n | mean diff | 95% CI | p (sign-flip) | d_z |
|---|---|---|---|---|---|---|---|
| codellama:7b | history | code_only | 24 | +0.28 | [+0.05, +0.49] | 0.0328 | 0.478 |
| codellama:7b | history | no_context | 24 | +0.55 | [+0.36, +0.73] | 0.0002 | 1.161 |
| codellama:7b | control | code_only | 4 | +0.00 | [+0.00, +0.00] | 1.0 | 0.0 |
| codellama:7b | control | no_context | 4 | +1.00 | [+1.00, +1.00] | 0.125 | None |
| codellama:7b | guardrail | code_only | 7 | +0.00 | [+0.00, +0.00] | 1.0 | 0.0 |
| codellama:7b | guardrail | no_context | 7 | +0.29 | [+0.00, +0.57] | 0.5 | 0.586 |
| llama2 | history | code_only | 24 | +0.32 | [+0.07, +0.55] | 0.0222 | 0.521 |
| llama2 | history | no_context | 24 | +0.57 | [+0.40, +0.75] | 0.0002 | 1.243 |
| llama2 | control | code_only | 4 | +0.00 | [-0.75, +0.75] | 1.0 | 0.0 |
| llama2 | control | no_context | 4 | +0.50 | [+0.00, +1.00] | 0.5 | 0.866 |
| llama2 | guardrail | code_only | 7 | +0.29 | [+0.00, +0.57] | 0.5 | 0.586 |
| llama2 | guardrail | no_context | 7 | +0.86 | [+0.57, +1.00] | 0.0312 | 2.268 |
| starcoder2:3b | history | code_only | 24 | -0.02 | [-0.21, +0.17] | 1.0 | -0.044 |
| starcoder2:3b | history | no_context | 24 | +0.11 | [-0.04, +0.29] | 0.2156 | 0.273 |
| starcoder2:3b | control | code_only | 4 | -0.25 | [-1.00, +0.50] | 1.0 | -0.261 |
| starcoder2:3b | control | no_context | 4 | -0.25 | [-0.75, +0.00] | 1.0 | -0.5 |
| starcoder2:3b | guardrail | code_only | 7 | +0.00 | [+0.00, +0.00] | 1.0 | 0.0 |
| starcoder2:3b | guardrail | no_context | 7 | +0.29 | [+0.00, +0.57] | 0.5 | 0.586 |

## Failure analysis (why answers were wrong)

| Model | Mode | ok | retrieval_miss | model_ignored_evidence | hallucinated | over_refused | under_refused | no_evidence_given |
|---|---|---|---|---|---|---|---|---|
| codellama:7b | code_history | 25 | 2 | 3 | 1 | 0 | 4 | 0 |
| codellama:7b | code_only | 21 | 10 | 0 | 0 | 0 | 4 | 0 |
| codellama:7b | no_context | 6 | 0 | 0 | 0 | 0 | 6 | 23 |
| codellama:7b | oracle | 25 | 0 | 2 | 1 | 0 | 0 | 0 |
| llama2 | code_history | 30 | 3 | 1 | 1 | 0 | 0 | 0 |
| llama2 | code_only | 21 | 11 | 1 | 0 | 0 | 2 | 0 |
| llama2 | no_context | 10 | 0 | 0 | 0 | 0 | 6 | 19 |
| llama2 | oracle | 23 | 0 | 2 | 3 | 0 | 0 | 0 |
| starcoder2:3b | code_history | 10 | 6 | 5 | 10 | 0 | 4 | 0 |
| starcoder2:3b | code_only | 13 | 16 | 0 | 2 | 0 | 4 | 0 |
| starcoder2:3b | no_context | 5 | 0 | 0 | 0 | 0 | 6 | 24 |
| starcoder2:3b | oracle | 6 | 0 | 4 | 18 | 0 | 0 | 0 |

_Limits: small samples give wide intervals; automatic correctness is key-fact matching, calibrated against human grades (see calibration)._