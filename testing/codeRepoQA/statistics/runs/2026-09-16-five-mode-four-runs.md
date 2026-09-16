# Five-Mode Retrieval Statistics — 35 Cases, Four Repetitions

## Status and audit

Complete replacement evaluation: 35 cases, five modes, and four valid repetitions per case-mode cell (700 accepted runs). All conditions use `gpt-5.6-luna`; Workspace response generation was skipped while final evidence selection remained enabled. Codex uses the frozen `efficient` profile. The policy-blocked August 26 Codex attempts are excluded; Codex rows come from the policy-corrected September 2 cohort.

- Development cases: 28
- Held-out cases: 7
- TypeScript: 11; pandas: 12; Vue: 12
- Every one of the 175 case-mode cells contains exactly four accepted runs.

## Headline ranking metrics

Metrics macro-average four-run case means. Precision and recall use implementation Oracle files; NDCG grades implementation files 2, supporting tests/docs 1, and other files 0.

| Condition | P@1 | P@5 | R@5 | R@10 | NDCG@5 | NDCG@10 | Any hit | Full recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Full Workspace | 0.450 | 0.207 | 0.517 | 0.526 | 0.461 | 0.430 | 0.707 | 0.400 |
| Without CodeGraph | 0.464 | 0.207 | 0.508 | 0.514 | 0.476 | 0.444 | 0.693 | 0.386 |
| Without adaptive controller | 0.407 | 0.187 | 0.484 | 0.486 | 0.429 | 0.397 | 0.643 | 0.379 |
| Without either capability | 0.443 | 0.187 | 0.470 | 0.486 | 0.430 | 0.402 | 0.693 | 0.371 |
| Codex | 0.386 | 0.260 | 0.677 | 0.709 | 0.511 | 0.502 | 0.893 | 0.579 |

## Change from the previous overview

Positive values mean the replacement result is higher.

| Condition | ΔP@1 | ΔP@5 | ΔR@5 | ΔR@10 | ΔNDCG@5 | ΔNDCG@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Full Workspace | +0.121 | +0.016 | +0.009 | +0.009 | +0.060 | +0.057 |
| Without CodeGraph | -0.029 | +0.007 | +0.003 | +0.006 | +0.013 | +0.017 |
| Without adaptive controller | +0.086 | +0.001 | +0.019 | +0.013 | +0.040 | +0.037 |
| Without either capability | -0.021 | +0.001 | -0.009 | +0.005 | -0.003 | +0.001 |
| Codex | -0.000 | +0.000 | -0.000 | -0.000 | +0.000 | +0.000 |

## Development and held-out partitions

| Partition | Condition | P@5 | R@5 | NDCG@5 | Any hit | Full recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Development | Full Workspace | 0.205 | 0.477 | 0.445 | 0.696 | 0.348 |
| Development | Without CodeGraph | 0.198 | 0.439 | 0.439 | 0.661 | 0.295 |
| Development | Without adaptive controller | 0.179 | 0.431 | 0.410 | 0.625 | 0.304 |
| Development | Without either capability | 0.182 | 0.422 | 0.415 | 0.670 | 0.295 |
| Development | Codex | 0.246 | 0.596 | 0.464 | 0.866 | 0.473 |
| Held-out | Full Workspace | 0.214 | 0.679 | 0.527 | 0.750 | 0.607 |
| Held-out | Without CodeGraph | 0.243 | 0.786 | 0.620 | 0.821 | 0.750 |
| Held-out | Without adaptive controller | 0.221 | 0.696 | 0.504 | 0.714 | 0.679 |
| Held-out | Without either capability | 0.207 | 0.661 | 0.486 | 0.786 | 0.679 |
| Held-out | Codex | 0.314 | 1.000 | 0.700 | 1.000 | 1.000 |

## Native factorial contrasts

Positive values mean enabling the named capability increased the measure.

| Contrast | ΔP@1 | ΔR@5 | ΔNDCG@5 | ΔAny hit | ΔFull recall | ΔMean tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Adaptive controller, with CodeGraph | +0.043 | +0.033 | +0.032 | +0.064 | +0.021 | +33,494 |
| Adaptive controller, without CodeGraph | +0.021 | +0.039 | +0.046 | +0.000 | +0.014 | +29,944 |
| CodeGraph, with adaptive controller | -0.014 | +0.008 | -0.015 | +0.014 | +0.014 | +3,845 |
| CodeGraph, without adaptive controller | -0.036 | +0.014 | -0.001 | -0.050 | +0.007 | +295 |

## Efficiency and stability

Tokens are provider-reported retrieval-flow tokens; Codex total is input plus output, with reasoning already included in output. Index-build tokens are unavailable and excluded. Runtime excludes campaign queue time.

| Condition | Mean files | Mean flow tokens | Mean seconds | File-set Jaccard | Mean SD of R@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Full Workspace | 3.89 | 79,407 | 206.5 | 0.555 | 0.118 |
| Without CodeGraph | 3.81 | 75,562 | 182.4 | 0.519 | 0.071 |
| Without adaptive controller | 3.24 | 45,913 | 146.8 | 0.608 | 0.073 |
| Without either capability | 3.25 | 45,618 | 115.0 | 0.564 | 0.102 |
| Codex | 6.49 | 283,913 | 104.2 | 0.685 | 0.033 |

## Selector coverage states

These are system self-assessments, not independent causal-completeness labels.

| Condition | Coverage statuses | Sufficient |
| --- | --- | ---: |
| Full Workspace | `{"missing": 3, "partial": 137}` | 0/140 |
| Without CodeGraph | `{"missing": 2, "partial": 137, "strong": 1}` | 1/140 |
| Without adaptive controller | `{"missing": 3, "partial": 137}` | 0/140 |
| Without either capability | `{"partial": 140}` | 0/140 |
| Codex | `{"strong": 140}` | 140/140 |

## Repository breakdown

| Group | Condition | Cases | P@1 | R@5 | NDCG@5 |
| --- | --- | ---: | ---: | ---: | ---: |
| microsoft/TypeScript | Full Workspace | 11 | 0.455 | 0.572 | 0.446 |
| microsoft/TypeScript | Without CodeGraph | 11 | 0.432 | 0.538 | 0.441 |
| microsoft/TypeScript | Without adaptive controller | 11 | 0.386 | 0.475 | 0.394 |
| microsoft/TypeScript | Without either capability | 11 | 0.409 | 0.534 | 0.414 |
| microsoft/TypeScript | Codex | 11 | 0.364 | 0.701 | 0.516 |
| pandas-dev/pandas | Full Workspace | 12 | 0.438 | 0.363 | 0.416 |
| pandas-dev/pandas | Without CodeGraph | 12 | 0.417 | 0.311 | 0.381 |
| pandas-dev/pandas | Without adaptive controller | 12 | 0.438 | 0.322 | 0.377 |
| pandas-dev/pandas | Without either capability | 12 | 0.396 | 0.261 | 0.328 |
| pandas-dev/pandas | Codex | 12 | 0.375 | 0.603 | 0.472 |
| vuejs/vue | Full Workspace | 12 | 0.458 | 0.620 | 0.519 |
| vuejs/vue | Without CodeGraph | 12 | 0.542 | 0.679 | 0.602 |
| vuejs/vue | Without adaptive controller | 12 | 0.396 | 0.655 | 0.512 |
| vuejs/vue | Without either capability | 12 | 0.521 | 0.620 | 0.546 |
| vuejs/vue | Codex | 12 | 0.417 | 0.728 | 0.547 |

## Issue-category breakdown

| Group | Condition | Cases | P@1 | R@5 | NDCG@5 |
| --- | --- | ---: | ---: | ---: | ---: |
| api_behavior_design | Full Workspace | 5 | 0.550 | 0.706 | 0.629 |
| api_behavior_design | Without CodeGraph | 5 | 0.600 | 0.700 | 0.641 |
| api_behavior_design | Without adaptive controller | 5 | 0.450 | 0.700 | 0.593 |
| api_behavior_design | Without either capability | 5 | 0.600 | 0.650 | 0.593 |
| api_behavior_design | Codex | 5 | 0.250 | 0.925 | 0.555 |
| bug_regression | Full Workspace | 5 | 0.600 | 0.700 | 0.606 |
| bug_regression | Without CodeGraph | 5 | 0.550 | 0.600 | 0.555 |
| bug_regression | Without adaptive controller | 5 | 0.600 | 0.600 | 0.568 |
| bug_regression | Without either capability | 5 | 0.500 | 0.600 | 0.516 |
| bug_regression | Codex | 5 | 0.200 | 0.850 | 0.518 |
| compatibility_versioning | Full Workspace | 5 | 0.100 | 0.500 | 0.206 |
| compatibility_versioning | Without CodeGraph | 5 | 0.100 | 0.400 | 0.198 |
| compatibility_versioning | Without adaptive controller | 5 | 0.100 | 0.400 | 0.175 |
| compatibility_versioning | Without either capability | 5 | 0.100 | 0.400 | 0.162 |
| compatibility_versioning | Codex | 5 | 0.000 | 0.600 | 0.212 |
| feature_enhancement | Full Workspace | 5 | 0.500 | 0.458 | 0.488 |
| feature_enhancement | Without CodeGraph | 5 | 0.650 | 0.526 | 0.591 |
| feature_enhancement | Without adaptive controller | 5 | 0.500 | 0.501 | 0.527 |
| feature_enhancement | Without either capability | 5 | 0.600 | 0.446 | 0.500 |
| feature_enhancement | Codex | 5 | 0.650 | 0.547 | 0.547 |
| maintenance_refactor | Full Workspace | 5 | 0.550 | 0.340 | 0.366 |
| maintenance_refactor | Without CodeGraph | 5 | 0.550 | 0.390 | 0.415 |
| maintenance_refactor | Without adaptive controller | 5 | 0.550 | 0.415 | 0.405 |
| maintenance_refactor | Without either capability | 5 | 0.500 | 0.315 | 0.356 |
| maintenance_refactor | Codex | 5 | 0.800 | 0.631 | 0.738 |
| performance_memory | Full Workspace | 5 | 0.450 | 0.339 | 0.397 |
| performance_memory | Without CodeGraph | 5 | 0.300 | 0.339 | 0.328 |
| performance_memory | Without adaptive controller | 5 | 0.300 | 0.292 | 0.288 |
| performance_memory | Without either capability | 5 | 0.400 | 0.328 | 0.331 |
| performance_memory | Codex | 5 | 0.400 | 0.350 | 0.343 |
| testing_build_tooling | Full Workspace | 5 | 0.400 | 0.575 | 0.535 |
| testing_build_tooling | Without CodeGraph | 5 | 0.500 | 0.604 | 0.601 |
| testing_build_tooling | Without adaptive controller | 5 | 0.350 | 0.483 | 0.443 |
| testing_build_tooling | Without either capability | 5 | 0.400 | 0.550 | 0.548 |
| testing_build_tooling | Codex | 5 | 0.400 | 0.833 | 0.667 |

## Interpretation boundary

This is a file-ranking evaluation against frozen implementation Oracles. It measures recovery, ordering, stability, runtime, and provider tokens; it does not independently prove that selected snippets explain every causal transition. Codex remains a complete-system comparison rather than a factorial component.

## Reproduction

The complete 700-row run inventory, per-case results, breakdowns, exact run directories, token records, and selection provenance are stored in `C:\Programming\guidedInteligence\testing\codeRepoQA\statistics\runs\2026-09-16-five-mode-four-runs.json`.
