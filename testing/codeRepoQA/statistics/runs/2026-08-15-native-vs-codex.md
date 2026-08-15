# Native Retrieval vs Codex Retrieval — 35-Case Evaluation

> **Run date:** 2026-08-15  
> **Status:** completed evaluation; 35 paired retrieval-grounded cases.

## Executive Summary

This campaign currently has one selected valid native run for 35 cases, using `gpt-5.6-luna`. Additional valid executions do not replace or get averaged with those selections. Codex retrieval is available for all 35 planned cases: 21 reusable historical `efficient` runs made with `gpt-5.4-mini` and 14 new `efficient` runs made with `gpt-5.6-luna`. Only the 35 cases with a selected native run enter paired metrics in this report.

Because the Codex model differs across cohorts, any combined table is a **coverage summary**, not a homogeneous single-model Codex benchmark. Model-specific cohorts are reported separately and should be used for configuration-specific conclusions.

No Codex usage-limit or token-exhaustion event occurred. All 14 requested new Codex runs completed.

## How The Metrics Are Calculated

The ranking unit is an ordered unique file path. Multiple snippets from the same file count once, at the file's first position.

- **P@k:** implementation Oracle files found in the first k ranks divided by k. If fewer than k files are returned, empty ranks are nonrelevant.
- **R@k:** implementation Oracle files found in the first k ranks divided by all implementation Oracle files for that case.
- **NDCG@k:** position-sensitive graded ranking quality. Implementation Oracle files have relevance 2, test/validation or documentation Oracle files have relevance 1, and all other files have relevance 0.

Exactly one valid run per testcase and system enters headline metrics. Failed infrastructure attempts do not count. Extra successful runs are retained separately rather than averaged or selected by score. Testcase scores are macro-averaged and rounded to three decimals only for display.

## Configuration And Validity

| Condition | Cases | Model | Profile | Run selection |
| --- | ---: | --- | --- | --- |
| Native final | 35 valid paired | `gpt-5.6-luna` | workspace final | First valid run at/after `run-20260815T011600Z` |
| Codex historical | 21 | `gpt-5.4-mini` | `efficient` | Latest valid reusable run |
| Codex current | 14 | `gpt-5.6-luna` | `efficient` | New run from this evaluation |

Native runs are valid only when infrastructure completed, `coverage_status` is not `failed`, evidence is nonempty, and evaluator comparison artifacts exist. Earlier attempts from this date that failed because Node lacked `node:sqlite` or Qdrant was unavailable are explicitly excluded.

Native coverage statuses: {'partial': 35}; sufficient: 0/35.  
Codex coverage statuses within the paired subset: {'strong': 35}; sufficient: 35/35.  
Codex coverage statuses across all 35: {'strong': 35}; sufficient: 35/35.

## Aggregate Results

### Paired coverage summary — 35 cases

Codex model composition: historical Mini=21; current Luna=14.

Cases: **35**

| System | P@1 | P@2 | P@5 | P@10 | R@1 | R@2 | R@5 | R@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Native | 0.457 | 0.371 | 0.246 | 0.129 | 0.236 | 0.363 | 0.575 | 0.593 |
| Codex | 0.543 | 0.400 | 0.269 | 0.140 | 0.361 | 0.456 | 0.674 | 0.681 |

| System | NDCG@1 | NDCG@2 | NDCG@5 | NDCG@10 |
| --- | ---: | ---: | ---: | ---: |
| Native | 0.476 | 0.458 | 0.506 | 0.471 |
| Codex | 0.562 | 0.538 | 0.576 | 0.542 |

### Historical reusable cohort — paired cases: 21

Paired native final runs versus Codex `gpt-5.4-mini` / `efficient`.

Cases: **21**

| System | P@1 | P@2 | P@5 | P@10 | R@1 | R@2 | R@5 | R@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Native | 0.429 | 0.357 | 0.248 | 0.124 | 0.205 | 0.340 | 0.556 | 0.556 |
| Codex | 0.476 | 0.357 | 0.248 | 0.124 | 0.318 | 0.408 | 0.609 | 0.609 |

| System | NDCG@1 | NDCG@2 | NDCG@5 | NDCG@10 |
| --- | ---: | ---: | ---: | ---: |
| Native | 0.460 | 0.456 | 0.487 | 0.430 |
| Codex | 0.508 | 0.503 | 0.524 | 0.471 |

### Current homogeneous cohort — paired cases: 14

Paired native final runs versus Codex `gpt-5.6-luna` / `efficient`.

Cases: **14**

| System | P@1 | P@2 | P@5 | P@10 | R@1 | R@2 | R@5 | R@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Native | 0.500 | 0.393 | 0.243 | 0.136 | 0.283 | 0.399 | 0.604 | 0.649 |
| Codex | 0.643 | 0.464 | 0.300 | 0.164 | 0.426 | 0.530 | 0.771 | 0.789 |

| System | NDCG@1 | NDCG@2 | NDCG@5 | NDCG@10 |
| --- | ---: | ---: | ---: | ---: |
| Native | 0.500 | 0.460 | 0.533 | 0.532 |
| Codex | 0.643 | 0.590 | 0.655 | 0.647 |

### Development partition — 28 paired cases

All 28 planned development cases are included.

Cases: **28**

| System | P@1 | P@2 | P@5 | P@10 | R@1 | R@2 | R@5 | R@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Native | 0.429 | 0.339 | 0.250 | 0.129 | 0.188 | 0.293 | 0.540 | 0.545 |
| Codex | 0.536 | 0.393 | 0.257 | 0.136 | 0.344 | 0.428 | 0.593 | 0.601 |

| System | NDCG@1 | NDCG@2 | NDCG@5 | NDCG@10 |
| --- | ---: | ---: | ---: | ---: |
| Native | 0.452 | 0.421 | 0.468 | 0.419 |
| Codex | 0.560 | 0.536 | 0.543 | 0.499 |

### Final partition — 7 paired cases

Both conditions use `gpt-5.6-luna`.

Cases: **7**

| System | P@1 | P@2 | P@5 | P@10 | R@1 | R@2 | R@5 | R@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Native | 0.571 | 0.500 | 0.229 | 0.129 | 0.429 | 0.643 | 0.714 | 0.786 |
| Codex | 0.571 | 0.429 | 0.314 | 0.157 | 0.429 | 0.571 | 1.000 | 1.000 |

| System | NDCG@1 | NDCG@2 | NDCG@5 | NDCG@10 |
| --- | ---: | ---: | ---: | ---: |
| Native | 0.571 | 0.602 | 0.656 | 0.681 |
| Codex | 0.571 | 0.547 | 0.711 | 0.713 |

## Codex-Only Results Across All 35 Cases

These supplemental tables show Codex results without the adjacent native columns. The mixed-model total is a coverage summary; use the model-specific cohorts for configuration conclusions.

### All Codex cases — mixed-model coverage

This combines 21 historical Mini and 14 current Luna cases; use the model-specific tables below for configuration conclusions.

Cases: **35**

| P@1 | P@2 | P@5 | P@10 | R@1 | R@2 | R@5 | R@10 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.543 | 0.400 | 0.269 | 0.140 | 0.361 | 0.456 | 0.674 | 0.681 |

| NDCG@1 | NDCG@2 | NDCG@5 | NDCG@10 |
| ---: | ---: | ---: | ---: |
| 0.562 | 0.538 | 0.576 | 0.542 |

### Historical Codex cohort — 21 cases

`gpt-5.4-mini` with the `efficient` profile.

Cases: **21**

| P@1 | P@2 | P@5 | P@10 | R@1 | R@2 | R@5 | R@10 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.476 | 0.357 | 0.248 | 0.124 | 0.318 | 0.408 | 0.609 | 0.609 |

| NDCG@1 | NDCG@2 | NDCG@5 | NDCG@10 |
| ---: | ---: | ---: | ---: |
| 0.508 | 0.503 | 0.524 | 0.471 |

### Current Codex cohort — 14 cases

`gpt-5.6-luna` with the `efficient` profile.

Cases: **14**

| P@1 | P@2 | P@5 | P@10 | R@1 | R@2 | R@5 | R@10 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.643 | 0.464 | 0.300 | 0.164 | 0.426 | 0.530 | 0.771 | 0.789 |

| NDCG@1 | NDCG@2 | NDCG@5 | NDCG@10 |
| ---: | ---: | ---: | ---: |
| 0.643 | 0.590 | 0.655 | 0.647 |

### Codex development partition — 28 cases

Mixed-model: 21 Mini and 7 Luna cases.

Cases: **28**

| P@1 | P@2 | P@5 | P@10 | R@1 | R@2 | R@5 | R@10 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.536 | 0.393 | 0.257 | 0.136 | 0.344 | 0.428 | 0.593 | 0.601 |

| NDCG@1 | NDCG@2 | NDCG@5 | NDCG@10 |
| ---: | ---: | ---: | ---: |
| 0.560 | 0.536 | 0.543 | 0.499 |

### Codex final partition — 7 cases

All seven held-out categories use `gpt-5.6-luna`.

Cases: **7**

| P@1 | P@2 | P@5 | P@10 | R@1 | R@2 | R@5 | R@10 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.571 | 0.429 | 0.314 | 0.157 | 0.429 | 0.571 | 1.000 | 1.000 |

| NDCG@1 | NDCG@2 | NDCG@5 | NDCG@10 |
| ---: | ---: | ---: | ---: |
| 0.571 | 0.547 | 0.711 | 0.713 |

## Category Breakdown At Rank 5

| Group | Cases | Codex models | Native P@5 | Codex P@5 | Native R@5 | Codex R@5 | Native NDCG@5 | Codex NDCG@5 |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `api_behavior_design` | 5 | gpt-5.4-mini: 3, gpt-5.6-luna: 2 | 0.320 | 0.400 | 0.525 | 0.925 | 0.526 | 0.612 |
| `bug_regression` | 5 | gpt-5.4-mini: 3, gpt-5.6-luna: 2 | 0.240 | 0.200 | 1.000 | 0.800 | 0.686 | 0.594 |
| `compatibility_versioning` | 5 | gpt-5.4-mini: 3, gpt-5.6-luna: 2 | 0.080 | 0.120 | 0.400 | 0.600 | 0.183 | 0.355 |
| `feature_enhancement` | 5 | gpt-5.4-mini: 3, gpt-5.6-luna: 2 | 0.320 | 0.440 | 0.509 | 0.584 | 0.514 | 0.596 |
| `maintenance_refactor` | 5 | gpt-5.4-mini: 3, gpt-5.6-luna: 2 | 0.240 | 0.240 | 0.546 | 0.631 | 0.439 | 0.795 |
| `performance_memory` | 5 | gpt-5.4-mini: 3, gpt-5.6-luna: 2 | 0.240 | 0.200 | 0.378 | 0.345 | 0.467 | 0.338 |
| `testing_build_tooling` | 5 | gpt-5.4-mini: 3, gpt-5.6-luna: 2 | 0.280 | 0.280 | 0.667 | 0.833 | 0.724 | 0.743 |

## Repository Breakdown At Rank 5

| Group | Cases | Codex models | Native P@5 | Codex P@5 | Native R@5 | Codex R@5 | Native NDCG@5 | Codex NDCG@5 |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `microsoft/TypeScript` | 11 | gpt-5.4-mini: 6, gpt-5.6-luna: 5 | 0.309 | 0.364 | 0.522 | 0.685 | 0.487 | 0.545 |
| `pandas-dev/pandas` | 12 | gpt-5.4-mini: 11, gpt-5.6-luna: 1 | 0.250 | 0.233 | 0.496 | 0.601 | 0.509 | 0.511 |
| `vuejs/vue` | 12 | gpt-5.4-mini: 4, gpt-5.6-luna: 8 | 0.183 | 0.217 | 0.702 | 0.737 | 0.519 | 0.670 |

## Per-case Audit At Rank 5

| Testcase | Selected native run | Partition | Category | Codex model | Native P@5 | Codex P@5 | Native R@5 | Codex R@5 | Native NDCG@5 | Codex NDCG@5 |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `microsoft-TypeScript-16278` | `run-20260815T182050Z` | development | `api_behavior_design` | `gpt-5.6-luna` | 1.000 | 1.000 | 0.625 | 0.625 | 1.000 | 1.000 |
| `microsoft-TypeScript-24625` | `run-20260815T174619Z` | development | `api_behavior_design` | `gpt-5.4-mini` | 0.000 | 0.200 | 0.000 | 1.000 | 0.000 | 0.606 |
| `pandas-dev-pandas-25183` | `run-20260815T175808Z` | development | `api_behavior_design` | `gpt-5.4-mini` | 0.000 | 0.200 | 0.000 | 1.000 | 0.121 | 0.363 |
| `vuejs-vue-5884` | `run-20260815T174348Z` | development | `api_behavior_design` | `gpt-5.4-mini` | 0.200 | 0.200 | 1.000 | 1.000 | 0.640 | 0.640 |
| `microsoft-TypeScript-2953` | `run-20260815T011910Z` | development | `bug_regression` | `gpt-5.4-mini` | 0.200 | 0.000 | 1.000 | 0.000 | 0.500 | 0.000 |
| `pandas-dev-pandas-10068` | `run-20260815T012526Z` | development | `bug_regression` | `gpt-5.4-mini` | 0.200 | 0.200 | 1.000 | 1.000 | 0.467 | 0.363 |
| `vuejs-vue-10519` | `run-20260815T012802Z` | development | `bug_regression` | `gpt-5.6-luna` | 0.200 | 0.200 | 1.000 | 1.000 | 0.462 | 0.945 |
| `vuejs-vue-10803` | `run-20260815T011658Z` | development | `bug_regression` | `gpt-5.4-mini` | 0.200 | 0.200 | 1.000 | 1.000 | 1.000 | 0.826 |
| `microsoft-TypeScript-46770` | `run-20260815T173128Z` | development | `compatibility_versioning` | `gpt-5.4-mini` | 0.200 | 0.200 | 1.000 | 1.000 | 0.383 | 0.606 |
| `pandas-dev-pandas-22698` | `run-20260815T164456Z` | development | `compatibility_versioning` | `gpt-5.4-mini` | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| `vuejs-vue-13052` | `run-20260815T174046Z` | development | `compatibility_versioning` | `gpt-5.6-luna` | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| `vuejs-vue-9042` | `run-20260815T164218Z` | development | `compatibility_versioning` | `gpt-5.4-mini` | 0.200 | 0.200 | 1.000 | 1.000 | 0.532 | 0.933 |
| `microsoft-TypeScript-10020` | `run-20260815T155518Z` | development | `feature_enhancement` | `gpt-5.6-luna` | 0.200 | 0.200 | 0.500 | 0.500 | 0.545 | 0.483 |
| `microsoft-TypeScript-45713` | `run-20260815T140948Z` | development | `feature_enhancement` | `gpt-5.4-mini` | 0.400 | 0.800 | 0.286 | 0.571 | 0.470 | 0.661 |
| `pandas-dev-pandas-4542` | `run-20260815T142524Z` | development | `feature_enhancement` | `gpt-5.4-mini` | 0.400 | 0.400 | 0.667 | 0.667 | 0.748 | 0.738 |
| `vuejs-vue-6301` | `run-20260815T013026Z` | development | `feature_enhancement` | `gpt-5.4-mini` | 0.200 | 0.400 | 0.091 | 0.182 | 0.146 | 0.470 |
| `pandas-dev-pandas-22872` | `run-20260815T184856Z` | development | `maintenance_refactor` | `gpt-5.4-mini` | 0.200 | 0.000 | 0.500 | 0.000 | 0.348 | 0.475 |
| `pandas-dev-pandas-35925` | `run-20260815T184419Z` | development | `maintenance_refactor` | `gpt-5.4-mini` | 0.600 | 0.400 | 0.231 | 0.154 | 0.723 | 0.580 |
| `pandas-dev-pandas-36617` | `run-20260815T185318Z` | development | `maintenance_refactor` | `gpt-5.4-mini` | 0.200 | 0.200 | 1.000 | 1.000 | 0.606 | 0.922 |
| `vuejs-vue-8528` | `run-20260815T185612Z` | development | `maintenance_refactor` | `gpt-5.6-luna` | 0.200 | 0.200 | 1.000 | 1.000 | 0.387 | 1.000 |
| `microsoft-TypeScript-52695` | `run-20260815T171510Z` | development | `performance_memory` | `gpt-5.4-mini` | 0.200 | 0.200 | 0.333 | 0.333 | 0.416 | 0.179 |
| `pandas-dev-pandas-14942` | `run-20260815T154547Z` | development | `performance_memory` | `gpt-5.4-mini` | 0.600 | 0.400 | 0.500 | 0.333 | 0.815 | 0.553 |
| `pandas-dev-pandas-16764` | `run-20260815T161202Z` | development | `performance_memory` | `gpt-5.4-mini` | 0.200 | 0.200 | 0.059 | 0.059 | 0.170 | 0.131 |
| `vuejs-vue-10004` | `run-20260815T163904Z` | development | `performance_memory` | `gpt-5.6-luna` | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| `microsoft-TypeScript-35468` | `run-20260815T183615Z` | development | `testing_build_tooling` | `gpt-5.4-mini` | 0.800 | 0.400 | 1.000 | 0.500 | 0.910 | 0.395 |
| `pandas-dev-pandas-16499` | `run-20260815T182704Z` | development | `testing_build_tooling` | `gpt-5.4-mini` | 0.200 | 0.200 | 1.000 | 1.000 | 1.000 | 1.000 |
| `pandas-dev-pandas-32289` | `run-20260815T182926Z` | development | `testing_build_tooling` | `gpt-5.4-mini` | 0.000 | 0.200 | 0.000 | 1.000 | 0.242 | 0.555 |
| `vuejs-vue-11718` | `run-20260815T125621Z` | development | `testing_build_tooling` | `gpt-5.6-luna` | 0.200 | 0.400 | 0.333 | 0.667 | 0.469 | 0.765 |
| `pandas-dev-pandas-10150` | `run-20260815T191410Z` | final | `api_behavior_design` | `gpt-5.6-luna` | 0.400 | 0.400 | 1.000 | 1.000 | 0.868 | 0.450 |
| `microsoft-TypeScript-10473` | `run-20260815T185819Z` | final | `bug_regression` | `gpt-5.6-luna` | 0.400 | 0.400 | 1.000 | 1.000 | 1.000 | 0.834 |
| `microsoft-TypeScript-10041` | `run-20260815T190953Z` | final | `compatibility_versioning` | `gpt-5.6-luna` | 0.000 | 0.200 | 0.000 | 1.000 | 0.000 | 0.235 |
| `vuejs-vue-6097` | `run-20260815T190450Z` | final | `feature_enhancement` | `gpt-5.6-luna` | 0.400 | 0.400 | 1.000 | 1.000 | 0.662 | 0.629 |
| `microsoft-TypeScript-19074` | `run-20260815T191854Z` | final | `maintenance_refactor` | `gpt-5.6-luna` | 0.000 | 0.400 | 0.000 | 1.000 | 0.132 | 1.000 |
| `vuejs-vue-9842` | `run-20260815T190715Z` | final | `performance_memory` | `gpt-5.6-luna` | 0.200 | 0.200 | 1.000 | 1.000 | 0.933 | 0.826 |
| `vuejs-vue-11782` | `run-20260815T191653Z` | final | `testing_build_tooling` | `gpt-5.6-luna` | 0.200 | 0.200 | 1.000 | 1.000 | 1.000 | 1.000 |

## Run Inventory

| Testcase | Native run | Native status | Codex run | Codex model | Codex status |
| --- | --- | --- | --- | --- | --- |
| `microsoft-TypeScript-10020` | `run-20260815T155518Z` | partial; sufficient=false | `run-20260815T005105Z` | `gpt-5.6-luna` | strong; sufficient=true |
| `microsoft-TypeScript-10041` | `run-20260815T190953Z` | partial; sufficient=false | `run-20260815T010234Z` | `gpt-5.6-luna` | strong; sufficient=true |
| `microsoft-TypeScript-10473` | `run-20260815T185819Z` | partial; sufficient=false | `run-20260815T005839Z` | `gpt-5.6-luna` | strong; sufficient=true |
| `microsoft-TypeScript-16278` | `run-20260815T182050Z` | partial; sufficient=false | `run-20260815T005500Z` | `gpt-5.6-luna` | strong; sufficient=true |
| `microsoft-TypeScript-19074` | `run-20260815T191854Z` | partial; sufficient=false | `run-20260815T010953Z` | `gpt-5.6-luna` | strong; sufficient=true |
| `microsoft-TypeScript-24625` | `run-20260815T174619Z` | partial; sufficient=false | `run-20260729T204029Z` | `gpt-5.4-mini` | strong; sufficient=true |
| `microsoft-TypeScript-2953` | `run-20260815T011910Z` | partial; sufficient=false | `run-20260729T204600Z` | `gpt-5.4-mini` | strong; sufficient=true |
| `microsoft-TypeScript-35468` | `run-20260815T183615Z` | partial; sufficient=false | `run-20260729T205015Z` | `gpt-5.4-mini` | strong; sufficient=true |
| `microsoft-TypeScript-45713` | `run-20260815T140948Z` | partial; sufficient=false | `run-20260729T205347Z` | `gpt-5.4-mini` | strong; sufficient=true |
| `microsoft-TypeScript-46770` | `run-20260815T173128Z` | partial; sufficient=false | `run-20260729T205636Z` | `gpt-5.4-mini` | strong; sufficient=true |
| `microsoft-TypeScript-52695` | `run-20260815T171510Z` | partial; sufficient=false | `run-20260807T211734Z` | `gpt-5.4-mini` | strong; sufficient=true |
| `pandas-dev-pandas-10068` | `run-20260815T012526Z` | partial; sufficient=false | `run-20260729T204029Z` | `gpt-5.4-mini` | strong; sufficient=true |
| `pandas-dev-pandas-10150` | `run-20260815T191410Z` | partial; sufficient=false | `run-20260815T010631Z` | `gpt-5.6-luna` | strong; sufficient=true |
| `pandas-dev-pandas-14942` | `run-20260815T154547Z` | partial; sufficient=false | `run-20260729T204601Z` | `gpt-5.4-mini` | strong; sufficient=true |
| `pandas-dev-pandas-16499` | `run-20260815T182704Z` | partial; sufficient=false | `run-20260729T205016Z` | `gpt-5.4-mini` | strong; sufficient=true |
| `pandas-dev-pandas-16764` | `run-20260815T161202Z` | partial; sufficient=false | `run-20260729T205347Z` | `gpt-5.4-mini` | strong; sufficient=true |
| `pandas-dev-pandas-22698` | `run-20260815T164456Z` | partial; sufficient=false | `run-20260729T205637Z` | `gpt-5.4-mini` | strong; sufficient=true |
| `pandas-dev-pandas-22872` | `run-20260815T184856Z` | partial; sufficient=false | `run-20260729T210215Z` | `gpt-5.4-mini` | strong; sufficient=true |
| `pandas-dev-pandas-25183` | `run-20260815T175808Z` | partial; sufficient=false | `run-20260729T210512Z` | `gpt-5.4-mini` | strong; sufficient=true |
| `pandas-dev-pandas-32289` | `run-20260815T182926Z` | partial; sufficient=false | `run-20260729T210832Z` | `gpt-5.4-mini` | strong; sufficient=true |
| `pandas-dev-pandas-35925` | `run-20260815T184419Z` | partial; sufficient=false | `run-20260729T211142Z` | `gpt-5.4-mini` | strong; sufficient=true |
| `pandas-dev-pandas-36617` | `run-20260815T185318Z` | partial; sufficient=false | `run-20260729T211408Z` | `gpt-5.4-mini` | strong; sufficient=true |
| `pandas-dev-pandas-4542` | `run-20260815T142524Z` | partial; sufficient=false | `run-20260729T211545Z` | `gpt-5.4-mini` | strong; sufficient=true |
| `vuejs-vue-10004` | `run-20260815T163904Z` | partial; sufficient=false | `run-20260815T005220Z` | `gpt-5.6-luna` | strong; sufficient=true |
| `vuejs-vue-10519` | `run-20260815T012802Z` | partial; sufficient=false | `run-20260815T004953Z` | `gpt-5.6-luna` | strong; sufficient=true |
| `vuejs-vue-10803` | `run-20260815T011658Z` | partial; sufficient=false | `run-20260805T213915Z` | `gpt-5.4-mini` | strong; sufficient=true |
| `vuejs-vue-11718` | `run-20260815T125621Z` | partial; sufficient=false | `run-20260815T005631Z` | `gpt-5.6-luna` | strong; sufficient=true |
| `vuejs-vue-11782` | `run-20260815T191653Z` | partial; sufficient=false | `run-20260815T010829Z` | `gpt-5.6-luna` | strong; sufficient=true |
| `vuejs-vue-13052` | `run-20260815T174046Z` | partial; sufficient=false | `run-20260815T005357Z` | `gpt-5.6-luna` | strong; sufficient=true |
| `vuejs-vue-5884` | `run-20260815T174348Z` | partial; sufficient=false | `run-20260729T213116Z` | `gpt-5.4-mini` | strong; sufficient=true |
| `vuejs-vue-6097` | `run-20260815T190450Z` | partial; sufficient=false | `run-20260815T005939Z` | `gpt-5.6-luna` | strong; sufficient=true |
| `vuejs-vue-6301` | `run-20260815T013026Z` | partial; sufficient=false | `run-20260729T205016Z` | `gpt-5.4-mini` | strong; sufficient=true |
| `vuejs-vue-8528` | `run-20260815T185612Z` | partial; sufficient=false | `run-20260815T005738Z` | `gpt-5.6-luna` | strong; sufficient=true |
| `vuejs-vue-9042` | `run-20260815T164218Z` | partial; sufficient=false | `run-20260729T205347Z` | `gpt-5.4-mini` | strong; sufficient=true |
| `vuejs-vue-9842` | `run-20260815T190715Z` | partial; sufficient=false | `run-20260815T010104Z` | `gpt-5.6-luna` | strong; sufficient=true |

## Interpretation Limits

- Do not interpret the combined Codex value as one model configuration; use the model-specific cohort tables.
- The seven-case final set is category-balanced but has one case per category, so category-level final estimates are individually fragile.
- One selected valid run per case/system is used in this report. Extra successful executions—including indexing or diagnostic checks—do not replace the selected run and are not averaged into headline metrics. This does not estimate run-to-run variance.
- Standard P@k penalizes deliberately short lists because missing ranks count as nonrelevant.
- These metrics evaluate frozen file Oracles. Semantically plausible non-Oracle files receive no deterministic credit and should be assessed separately in qualitative error analysis.

## Reproduction

This report was generated by `testing/codeRepoQA/generate_retrieval_statistics.py` from the selected runs' `evaluator-comparison.json`, `run-metadata.json`, and `orchestration-result.json` artifacts. Full-precision per-case values and run selections are stored in the adjacent JSON file.

The governing definitions are in [../RETRIEVAL_STATISTICS_PROTOCOL.md](../RETRIEVAL_STATISTICS_PROTOCOL.md).
