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
| Full Workspace | 0.386 | 0.167 | 0.455 | 0.462 | 0.402 | 0.378 | 0.629 | 0.357 |
| Without CodeGraph | 0.379 | 0.186 | 0.445 | 0.451 | 0.411 | 0.381 | 0.607 | 0.336 |
| Without adaptive controller | 0.350 | 0.176 | 0.454 | 0.455 | 0.401 | 0.377 | 0.586 | 0.350 |
| Without either capability | 0.379 | 0.154 | 0.345 | 0.347 | 0.339 | 0.308 | 0.550 | 0.236 |
| Codex | 0.386 | 0.260 | 0.677 | 0.709 | 0.511 | 0.502 | 0.893 | 0.579 |

## Change from the previous overview

Positive values mean the replacement result is higher.

| Condition | ΔP@1 | ΔP@5 | ΔR@5 | ΔR@10 | ΔNDCG@5 | ΔNDCG@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Full Workspace | +0.057 | -0.024 | -0.053 | -0.055 | +0.001 | +0.005 |
| Without CodeGraph | -0.114 | -0.014 | -0.060 | -0.057 | -0.052 | -0.046 |
| Without adaptive controller | +0.029 | -0.010 | -0.011 | -0.018 | +0.012 | +0.017 |
| Without either capability | -0.085 | -0.032 | -0.134 | -0.134 | -0.094 | -0.093 |
| Codex | -0.000 | +0.000 | -0.000 | -0.000 | +0.000 | +0.000 |

## Development and held-out partitions

| Partition | Condition | P@5 | R@5 | NDCG@5 | Any hit | Full recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Development | Full Workspace | 0.175 | 0.458 | 0.411 | 0.661 | 0.348 |
| Development | Without CodeGraph | 0.184 | 0.392 | 0.386 | 0.589 | 0.259 |
| Development | Without adaptive controller | 0.164 | 0.393 | 0.375 | 0.554 | 0.268 |
| Development | Without either capability | 0.170 | 0.360 | 0.369 | 0.607 | 0.232 |
| Development | Codex | 0.246 | 0.596 | 0.464 | 0.866 | 0.473 |
| Held-out | Full Workspace | 0.136 | 0.446 | 0.363 | 0.500 | 0.393 |
| Held-out | Without CodeGraph | 0.193 | 0.661 | 0.509 | 0.679 | 0.643 |
| Held-out | Without adaptive controller | 0.221 | 0.696 | 0.504 | 0.714 | 0.679 |
| Held-out | Without either capability | 0.093 | 0.286 | 0.222 | 0.321 | 0.250 |
| Held-out | Codex | 0.314 | 1.000 | 0.700 | 1.000 | 1.000 |

## Native factorial contrasts

Positive values mean enabling the named capability increased the measure.

| Contrast | ΔP@1 | ΔR@5 | ΔNDCG@5 | ΔAny hit | ΔFull recall | ΔMean tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Adaptive controller, with CodeGraph | +0.036 | +0.002 | +0.001 | +0.043 | +0.007 | +24,929 |
| Adaptive controller, without CodeGraph | +0.000 | +0.100 | +0.071 | +0.057 | +0.100 | +25,995 |
| CodeGraph, with adaptive controller | +0.007 | +0.010 | -0.009 | +0.021 | +0.021 | +4,734 |
| CodeGraph, without adaptive controller | -0.029 | +0.109 | +0.062 | +0.036 | +0.114 | +5,800 |

## Efficiency and stability

Tokens are provider-reported retrieval-flow tokens; Codex total is input plus output, with reasoning already included in output. Index-build tokens are unavailable and excluded. Runtime excludes campaign queue time.

| Condition | Mean files | Mean flow tokens | Mean seconds | File-set Jaccard | Mean SD of R@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Full Workspace | 3.24 | 68,035 | 216.3 | 0.618 | 0.096 |
| Without CodeGraph | 3.20 | 63,301 | 190.7 | 0.606 | 0.065 |
| Without adaptive controller | 2.99 | 43,106 | 158.5 | 0.628 | 0.073 |
| Without either capability | 2.49 | 37,306 | 127.3 | 0.636 | 0.071 |
| Codex | 6.49 | 283,913 | 104.2 | 0.685 | 0.033 |

## Selector coverage states

These are system self-assessments, not independent causal-completeness labels.

| Condition | Coverage statuses | Sufficient |
| --- | --- | ---: |
| Full Workspace | `{"failed": 20, "missing": 1, "partial": 119}` | 0/140 |
| Without CodeGraph | `{"failed": 23, "missing": 2, "partial": 115}` | 0/140 |
| Without adaptive controller | `{"failed": 12, "missing": 3, "partial": 125}` | 0/140 |
| Without either capability | `{"failed": 26, "partial": 114}` | 0/140 |
| Codex | `{"strong": 140}` | 140/140 |

## Repository breakdown

| Group | Condition | Cases | P@1 | R@5 | NDCG@5 |
| --- | --- | ---: | ---: | ---: | ---: |
| microsoft/TypeScript | Full Workspace | 11 | 0.250 | 0.376 | 0.257 |
| microsoft/TypeScript | Without CodeGraph | 11 | 0.341 | 0.507 | 0.403 |
| microsoft/TypeScript | Without adaptive controller | 11 | 0.386 | 0.475 | 0.394 |
| microsoft/TypeScript | Without either capability | 11 | 0.386 | 0.420 | 0.358 |
| microsoft/TypeScript | Codex | 11 | 0.364 | 0.701 | 0.516 |
| pandas-dev/pandas | Full Workspace | 12 | 0.438 | 0.363 | 0.416 |
| pandas-dev/pandas | Without CodeGraph | 12 | 0.250 | 0.155 | 0.226 |
| pandas-dev/pandas | Without adaptive controller | 12 | 0.271 | 0.233 | 0.299 |
| pandas-dev/pandas | Without either capability | 12 | 0.396 | 0.261 | 0.328 |
| pandas-dev/pandas | Codex | 12 | 0.375 | 0.603 | 0.472 |
| vuejs/vue | Full Workspace | 12 | 0.458 | 0.620 | 0.519 |
| vuejs/vue | Without CodeGraph | 12 | 0.542 | 0.679 | 0.602 |
| vuejs/vue | Without adaptive controller | 12 | 0.396 | 0.655 | 0.509 |
| vuejs/vue | Without either capability | 12 | 0.354 | 0.360 | 0.334 |
| vuejs/vue | Codex | 12 | 0.417 | 0.728 | 0.547 |

## Issue-category breakdown

| Group | Condition | Cases | P@1 | R@5 | NDCG@5 |
| --- | --- | ---: | ---: | ---: | ---: |
| api_behavior_design | Full Workspace | 5 | 0.350 | 0.600 | 0.442 |
| api_behavior_design | Without CodeGraph | 5 | 0.400 | 0.525 | 0.485 |
| api_behavior_design | Without adaptive controller | 5 | 0.450 | 0.700 | 0.593 |
| api_behavior_design | Without either capability | 5 | 0.600 | 0.650 | 0.593 |
| api_behavior_design | Codex | 5 | 0.250 | 0.925 | 0.555 |
| bug_regression | Full Workspace | 5 | 0.400 | 0.500 | 0.431 |
| bug_regression | Without CodeGraph | 5 | 0.550 | 0.600 | 0.555 |
| bug_regression | Without adaptive controller | 5 | 0.600 | 0.600 | 0.568 |
| bug_regression | Without either capability | 5 | 0.450 | 0.500 | 0.443 |
| bug_regression | Codex | 5 | 0.200 | 0.850 | 0.518 |
| compatibility_versioning | Full Workspace | 5 | 0.100 | 0.400 | 0.176 |
| compatibility_versioning | Without CodeGraph | 5 | 0.100 | 0.400 | 0.198 |
| compatibility_versioning | Without adaptive controller | 5 | 0.100 | 0.400 | 0.175 |
| compatibility_versioning | Without either capability | 5 | 0.100 | 0.200 | 0.095 |
| compatibility_versioning | Codex | 5 | 0.000 | 0.600 | 0.212 |
| feature_enhancement | Full Workspace | 5 | 0.500 | 0.458 | 0.488 |
| feature_enhancement | Without CodeGraph | 5 | 0.650 | 0.526 | 0.591 |
| feature_enhancement | Without adaptive controller | 5 | 0.500 | 0.501 | 0.527 |
| feature_enhancement | Without either capability | 5 | 0.450 | 0.271 | 0.336 |
| feature_enhancement | Codex | 5 | 0.650 | 0.547 | 0.547 |
| maintenance_refactor | Full Workspace | 5 | 0.500 | 0.315 | 0.342 |
| maintenance_refactor | Without CodeGraph | 5 | 0.550 | 0.390 | 0.398 |
| maintenance_refactor | Without adaptive controller | 5 | 0.150 | 0.200 | 0.216 |
| maintenance_refactor | Without either capability | 5 | 0.300 | 0.115 | 0.156 |
| maintenance_refactor | Codex | 5 | 0.800 | 0.631 | 0.738 |
| performance_memory | Full Workspace | 5 | 0.450 | 0.339 | 0.397 |
| performance_memory | Without CodeGraph | 5 | 0.100 | 0.273 | 0.245 |
| performance_memory | Without adaptive controller | 5 | 0.300 | 0.292 | 0.283 |
| performance_memory | Without either capability | 5 | 0.350 | 0.128 | 0.204 |
| performance_memory | Codex | 5 | 0.400 | 0.350 | 0.343 |
| testing_build_tooling | Full Workspace | 5 | 0.400 | 0.575 | 0.535 |
| testing_build_tooling | Without CodeGraph | 5 | 0.300 | 0.404 | 0.401 |
| testing_build_tooling | Without adaptive controller | 5 | 0.350 | 0.483 | 0.443 |
| testing_build_tooling | Without either capability | 5 | 0.400 | 0.550 | 0.548 |
| testing_build_tooling | Codex | 5 | 0.400 | 0.833 | 0.667 |

## Interpretation boundary

This is a file-ranking evaluation against frozen implementation Oracles. It measures recovery, ordering, stability, runtime, and provider tokens; it does not independently prove that selected snippets explain every causal transition. Codex remains a complete-system comparison rather than a factorial component.

## Reproduction

The complete 700-row run inventory, per-case results, breakdowns, exact run directories, token records, and selection provenance are stored in `C:\Programming\guidedInteligence\testing\codeRepoQA\statistics\runs\2026-09-16-five-mode-four-runs.json`.
