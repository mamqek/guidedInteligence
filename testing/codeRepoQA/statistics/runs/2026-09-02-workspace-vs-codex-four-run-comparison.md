# Workspace vs Codex Luna Efficient — 35-Case Four-Run Comparison

## Status and scope

Workspace complete: 35 cases and 140 valid retrieval runs. The frozen Codex ledger contains 140 artifact-complete executions, but it is not a valid retrieval condition: every run had repository shell commands rejected by execution policy and 134 returned no usable evidence. Codex values below are retained for failure audit only and must not be presented as a functioning Workspace-versus-Codex comparison.

## Conditions

- Workspace: `configs/testing/statistics-workspace.json`, `gpt-5.6-luna`, qualification-first controller, response generation skipped, final evidence selection enabled.
- Codex: frozen `2026-08-26-codex-luna-four-runs.json`, `gpt-5.6-luna`, `efficient` prompt profile.
- Aggregation: calculate each run, average four runs within each case, then macro-average the 35 case means.
- Workspace collection used two workers for the final 32 cases; elapsed time is compared directly as requested.

## Metric note

Files are ranked. Implementation Oracle files define precision and recall; test/validation and documentation Oracle files receive partial NDCG relevance. Missing ranks are nonrelevant. Values are calculated at 1, 2, 5, and 10.

## Descriptive metrics — Codex condition invalid

| System | Cases | Runs | P@1 | P@2 | P@5 | P@10 | R@1 | R@2 | R@5 | R@10 | NDCG@1 | NDCG@2 | NDCG@5 | NDCG@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Workspace | 35 | 140 | 0.329 | 0.304 | 0.191 | 0.098 | 0.169 | 0.332 | 0.508 | 0.517 | 0.350 | 0.384 | 0.401 | 0.373 |
| Codex Luna efficient | 35 | 140 | 0.014 | 0.014 | 0.011 | 0.006 | 0.008 | 0.013 | 0.025 | 0.025 | 0.017 | 0.018 | 0.022 | 0.021 |

No inferential Workspace-minus-Codex conclusion is valid from this campaign because the Codex repository-inspection condition failed.

## Operational summary

| System | Sufficient rate | Mean retrieved files | Any implementation hit | Full implementation recall | Mean flow tokens | Mean elapsed seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Workspace | 0.007 | 2.964 | 0.679 | 0.407 | 95315 | 227.5 |
| Codex Luna efficient | 0.043 | 0.171 | 0.029 | 0.021 | 176417 | 62.0 |

## Partition breakdown

| Group | System | Cases | Runs | P@5 | R@5 | NDCG@5 | Any hit | Full recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `development` | Workspace | 28 | 112 | 0.188 | 0.474 | 0.392 | 0.670 | 0.366 |
| `development` | Codex | 28 | 112 | 0.007 | 0.013 | 0.018 | 0.018 | 0.009 |
| `final` | Workspace | 7 | 28 | 0.207 | 0.643 | 0.437 | 0.714 | 0.571 |
| `final` | Codex | 7 | 28 | 0.029 | 0.071 | 0.039 | 0.071 | 0.071 |

## Issue-category breakdown

| Group | System | Cases | Runs | P@5 | R@5 | NDCG@5 | Any hit | Full recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `api_behavior_design` | Workspace | 5 | 20 | 0.300 | 0.625 | 0.515 | 0.800 | 0.550 |
| `api_behavior_design` | Codex | 5 | 20 | 0.020 | 0.050 | 0.022 | 0.050 | 0.050 |
| `bug_regression` | Workspace | 5 | 20 | 0.200 | 0.800 | 0.525 | 0.800 | 0.800 |
| `bug_regression` | Codex | 5 | 20 | 0.010 | 0.050 | 0.041 | 0.050 | 0.050 |
| `compatibility_versioning` | Workspace | 5 | 20 | 0.100 | 0.500 | 0.225 | 0.500 | 0.500 |
| `compatibility_versioning` | Codex | 5 | 20 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| `feature_enhancement` | Workspace | 5 | 20 | 0.240 | 0.426 | 0.403 | 0.800 | 0.100 |
| `feature_enhancement` | Codex | 5 | 20 | 0.020 | 0.050 | 0.031 | 0.050 | 0.050 |
| `maintenance_refactor` | Workspace | 5 | 20 | 0.120 | 0.390 | 0.344 | 0.600 | 0.350 |
| `maintenance_refactor` | Codex | 5 | 20 | 0.000 | 0.000 | 0.024 | 0.000 | 0.000 |
| `performance_memory` | Workspace | 5 | 20 | 0.170 | 0.336 | 0.290 | 0.650 | 0.200 |
| `performance_memory` | Codex | 5 | 20 | 0.030 | 0.025 | 0.036 | 0.050 | 0.000 |
| `testing_build_tooling` | Workspace | 5 | 20 | 0.210 | 0.475 | 0.504 | 0.600 | 0.350 |
| `testing_build_tooling` | Codex | 5 | 20 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |

## Retrieval-topology breakdown

| Group | System | Cases | Runs | P@5 | R@5 | NDCG@5 | Any hit | Full recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `broad_cross_cutting` | Workspace | 2 | 8 | 0.125 | 0.046 | 0.191 | 0.625 | 0.000 |
| `broad_cross_cutting` | Codex | 2 | 8 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| `connected_mechanism` | Workspace | 13 | 52 | 0.338 | 0.571 | 0.526 | 0.923 | 0.288 |
| `connected_mechanism` | Codex | 13 | 52 | 0.027 | 0.048 | 0.035 | 0.058 | 0.038 |
| `localized_declarative` | Workspace | 6 | 24 | 0.033 | 0.167 | 0.115 | 0.167 | 0.167 |
| `localized_declarative` | Codex | 6 | 24 | 0.000 | 0.000 | 0.020 | 0.000 | 0.000 |
| `localized_implementation` | Workspace | 14 | 56 | 0.132 | 0.661 | 0.438 | 0.679 | 0.679 |
| `localized_implementation` | Codex | 14 | 56 | 0.004 | 0.018 | 0.015 | 0.018 | 0.018 |

## Repository breakdown

| Group | System | Cases | Runs | P@5 | R@5 | NDCG@5 | Any hit | Full recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `microsoft/TypeScript` | Workspace | 11 | 44 | 0.268 | 0.527 | 0.403 | 0.795 | 0.364 |
| `microsoft/TypeScript` | Codex | 11 | 44 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| `pandas-dev/pandas` | Workspace | 12 | 48 | 0.163 | 0.393 | 0.365 | 0.583 | 0.292 |
| `pandas-dev/pandas` | Codex | 12 | 48 | 0.021 | 0.031 | 0.034 | 0.042 | 0.021 |
| `vuejs/vue` | Workspace | 12 | 48 | 0.150 | 0.604 | 0.436 | 0.667 | 0.562 |
| `vuejs/vue` | Codex | 12 | 48 | 0.013 | 0.042 | 0.030 | 0.042 | 0.042 |

## Per-case results

| Case | Partition | Topology | System | P@5 | R@5 | NDCG@5 | Any-hit runs | Full-recall runs | Mean files | Mean tokens | Mean seconds |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `microsoft-TypeScript-10020` | `development` | `connected_mechanism` | Workspace | 0.200 | 0.500 | 0.273 | 4/4 | 0/4 | 3.000 | 108624 | 250.7 |
| `microsoft-TypeScript-10020` | `development` | `connected_mechanism` | Codex | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 0.000 | 162100 | 52.1 |
| `microsoft-TypeScript-10041` | `final` | `localized_implementation` | Workspace | 0.100 | 0.500 | 0.191 | 2/4 | 2/4 | 1.750 | 76983 | 278.7 |
| `microsoft-TypeScript-10041` | `final` | `localized_implementation` | Codex | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 0.000 | 140616 | 56.6 |
| `microsoft-TypeScript-10473` | `final` | `connected_mechanism` | Workspace | 0.400 | 1.000 | 0.629 | 4/4 | 4/4 | 3.000 | 110861 | 281.2 |
| `microsoft-TypeScript-10473` | `final` | `connected_mechanism` | Codex | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 0.000 | 146730 | 53.4 |
| `microsoft-TypeScript-16278` | `development` | `connected_mechanism` | Workspace | 0.800 | 0.500 | 0.888 | 4/4 | 0/4 | 5.000 | 121339 | 326.1 |
| `microsoft-TypeScript-16278` | `development` | `connected_mechanism` | Codex | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 0.000 | 174152 | 59.1 |
| `microsoft-TypeScript-19074` | `final` | `connected_mechanism` | Workspace | 0.050 | 0.125 | 0.161 | 1/4 | 0/4 | 1.250 | 75507 | 242.6 |
| `microsoft-TypeScript-19074` | `final` | `connected_mechanism` | Codex | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 0.000 | 160383 | 50.2 |
| `microsoft-TypeScript-24625` | `development` | `localized_implementation` | Workspace | 0.200 | 1.000 | 0.419 | 4/4 | 4/4 | 2.750 | 101704 | 239.5 |
| `microsoft-TypeScript-24625` | `development` | `localized_implementation` | Codex | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 0.000 | 156313 | 56.4 |
| `microsoft-TypeScript-2953` | `development` | `localized_declarative` | Workspace | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 1.250 | 63998 | 165.7 |
| `microsoft-TypeScript-2953` | `development` | `localized_declarative` | Codex | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 0.000 | 165150 | 62.8 |
| `microsoft-TypeScript-35468` | `development` | `connected_mechanism` | Workspace | 0.500 | 0.625 | 0.567 | 4/4 | 2/4 | 4.750 | 130336 | 295.2 |
| `microsoft-TypeScript-35468` | `development` | `connected_mechanism` | Codex | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 0.000 | 136795 | 52.4 |
| `microsoft-TypeScript-45713` | `development` | `connected_mechanism` | Workspace | 0.300 | 0.214 | 0.446 | 4/4 | 0/4 | 2.500 | 108377 | 261.3 |
| `microsoft-TypeScript-45713` | `development` | `connected_mechanism` | Codex | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 0.000 | 162361 | 63.1 |
| `microsoft-TypeScript-46770` | `development` | `connected_mechanism` | Workspace | 0.200 | 1.000 | 0.438 | 4/4 | 4/4 | 2.750 | 124925 | 326.2 |
| `microsoft-TypeScript-46770` | `development` | `connected_mechanism` | Codex | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 0.000 | 155146 | 56.9 |
| `microsoft-TypeScript-52695` | `development` | `connected_mechanism` | Workspace | 0.200 | 0.333 | 0.416 | 4/4 | 0/4 | 3.000 | 127062 | 314.8 |
| `microsoft-TypeScript-52695` | `development` | `connected_mechanism` | Codex | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 0.000 | 140360 | 56.0 |
| `pandas-dev-pandas-10068` | `development` | `localized_implementation` | Workspace | 0.200 | 1.000 | 0.475 | 4/4 | 4/4 | 4.500 | 95499 | 207.9 |
| `pandas-dev-pandas-10068` | `development` | `localized_implementation` | Codex | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 0.000 | 143836 | 63.3 |
| `pandas-dev-pandas-10150` | `final` | `connected_mechanism` | Workspace | 0.350 | 0.875 | 0.709 | 4/4 | 3/4 | 3.750 | 95908 | 204.8 |
| `pandas-dev-pandas-10150` | `final` | `connected_mechanism` | Codex | 0.100 | 0.250 | 0.112 | 1/4 | 1/4 | 1.000 | 352272 | 94.0 |
| `pandas-dev-pandas-14942` | `development` | `connected_mechanism` | Workspace | 0.400 | 0.333 | 0.463 | 4/4 | 0/4 | 3.750 | 129212 | 240.7 |
| `pandas-dev-pandas-14942` | `development` | `connected_mechanism` | Codex | 0.150 | 0.125 | 0.181 | 1/4 | 0/4 | 1.250 | 563135 | 103.2 |
| `pandas-dev-pandas-16499` | `development` | `localized_implementation` | Workspace | 0.200 | 1.000 | 1.000 | 4/4 | 4/4 | 1.000 | 88571 | 184.4 |
| `pandas-dev-pandas-16499` | `development` | `localized_implementation` | Codex | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 0.000 | 161697 | 66.7 |
| `pandas-dev-pandas-16764` | `development` | `broad_cross_cutting` | Workspace | 0.050 | 0.015 | 0.042 | 1/4 | 0/4 | 1.750 | 84468 | 221.4 |
| `pandas-dev-pandas-16764` | `development` | `broad_cross_cutting` | Codex | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 0.000 | 149912 | 58.6 |
| `pandas-dev-pandas-22698` | `development` | `localized_implementation` | Workspace | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 2.750 | 97283 | 225.5 |
| `pandas-dev-pandas-22698` | `development` | `localized_implementation` | Codex | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 0.750 | 252733 | 76.9 |
| `pandas-dev-pandas-22872` | `development` | `localized_declarative` | Workspace | 0.000 | 0.000 | 0.040 | 0/4 | 0/4 | 1.000 | 100792 | 234.7 |
| `pandas-dev-pandas-22872` | `development` | `localized_declarative` | Codex | 0.000 | 0.000 | 0.119 | 0/4 | 0/4 | 2.000 | 320516 | 92.8 |
| `pandas-dev-pandas-25183` | `development` | `localized_implementation` | Workspace | 0.000 | 0.000 | 0.099 | 0/4 | 0/4 | 2.250 | 125116 | 257.5 |
| `pandas-dev-pandas-25183` | `development` | `localized_implementation` | Codex | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 0.000 | 138054 | 57.6 |
| `pandas-dev-pandas-32289` | `development` | `localized_implementation` | Workspace | 0.000 | 0.000 | 0.159 | 0/4 | 0/4 | 1.000 | 62958 | 176.6 |
| `pandas-dev-pandas-32289` | `development` | `localized_implementation` | Codex | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 0.000 | 146062 | 48.7 |
| `pandas-dev-pandas-35925` | `development` | `broad_cross_cutting` | Workspace | 0.200 | 0.077 | 0.339 | 4/4 | 0/4 | 1.000 | 42513 | 120.9 |
| `pandas-dev-pandas-35925` | `development` | `broad_cross_cutting` | Codex | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 0.000 | 121427 | 50.1 |
| `pandas-dev-pandas-36617` | `development` | `localized_declarative` | Workspace | 0.150 | 0.750 | 0.399 | 3/4 | 3/4 | 1.500 | 74026 | 188.0 |
| `pandas-dev-pandas-36617` | `development` | `localized_declarative` | Codex | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 0.000 | 144160 | 66.3 |
| `pandas-dev-pandas-4542` | `development` | `connected_mechanism` | Workspace | 0.400 | 0.667 | 0.650 | 4/4 | 0/4 | 2.750 | 103909 | 204.7 |
| `pandas-dev-pandas-4542` | `development` | `connected_mechanism` | Codex | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 0.000 | 108957 | 48.2 |
| `vuejs-vue-10004` | `development` | `localized_implementation` | Workspace | 0.000 | 0.000 | 0.056 | 0/4 | 0/4 | 7.000 | 132152 | 252.8 |
| `vuejs-vue-10004` | `development` | `localized_implementation` | Codex | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 0.000 | 163143 | 61.6 |
| `vuejs-vue-10519` | `development` | `localized_implementation` | Workspace | 0.200 | 1.000 | 0.521 | 4/4 | 4/4 | 3.000 | 77737 | 203.8 |
| `vuejs-vue-10519` | `development` | `localized_implementation` | Codex | 0.050 | 0.250 | 0.207 | 1/4 | 1/4 | 0.250 | 186346 | 73.9 |
| `vuejs-vue-10803` | `development` | `localized_implementation` | Workspace | 0.200 | 1.000 | 1.000 | 4/4 | 4/4 | 2.750 | 79862 | 201.2 |
| `vuejs-vue-10803` | `development` | `localized_implementation` | Codex | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 0.000 | 129655 | 68.2 |
| `vuejs-vue-11718` | `development` | `connected_mechanism` | Workspace | 0.300 | 0.500 | 0.543 | 3/4 | 0/4 | 2.250 | 58299 | 177.0 |
| `vuejs-vue-11718` | `development` | `connected_mechanism` | Codex | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 0.000 | 103414 | 47.7 |
| `vuejs-vue-11782` | `final` | `localized_declarative` | Workspace | 0.050 | 0.250 | 0.250 | 1/4 | 1/4 | 3.250 | 71765 | 202.9 |
| `vuejs-vue-11782` | `final` | `localized_declarative` | Codex | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 0.000 | 146739 | 62.1 |
| `vuejs-vue-13052` | `development` | `localized_declarative` | Workspace | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 1.250 | 65717 | 178.9 |
| `vuejs-vue-13052` | `development` | `localized_declarative` | Codex | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 0.000 | 126019 | 53.1 |
| `vuejs-vue-5884` | `development` | `localized_implementation` | Workspace | 0.150 | 0.750 | 0.461 | 4/4 | 4/4 | 4.750 | 99086 | 219.5 |
| `vuejs-vue-5884` | `development` | `localized_implementation` | Codex | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 0.000 | 144652 | 51.4 |
| `vuejs-vue-6097` | `final` | `connected_mechanism` | Workspace | 0.300 | 0.750 | 0.648 | 4/4 | 2/4 | 4.750 | 100008 | 223.9 |
| `vuejs-vue-6097` | `final` | `connected_mechanism` | Codex | 0.100 | 0.250 | 0.157 | 1/4 | 1/4 | 0.750 | 322408 | 88.0 |
| `vuejs-vue-6301` | `development` | `localized_declarative` | Workspace | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 3.750 | 81375 | 183.0 |
| `vuejs-vue-6301` | `development` | `localized_declarative` | Codex | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 0.000 | 149479 | 48.9 |
| `vuejs-vue-8528` | `development` | `localized_implementation` | Workspace | 0.200 | 1.000 | 0.783 | 4/4 | 4/4 | 2.000 | 65312 | 174.8 |
| `vuejs-vue-8528` | `development` | `localized_implementation` | Codex | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 0.000 | 102417 | 56.7 |
| `vuejs-vue-9042` | `development` | `localized_implementation` | Workspace | 0.200 | 1.000 | 0.497 | 4/4 | 4/4 | 5.500 | 134786 | 256.7 |
| `vuejs-vue-9042` | `development` | `localized_implementation` | Codex | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 0.000 | 160771 | 62.6 |
| `vuejs-vue-9842` | `final` | `localized_implementation` | Workspace | 0.200 | 1.000 | 0.474 | 4/4 | 4/4 | 5.500 | 119941 | 240.3 |
| `vuejs-vue-9842` | `final` | `localized_implementation` | Codex | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 0.000 | 136694 | 51.5 |

## Run inventory

The JSON companion contains normalized ranked files, Oracle overlap, all metric values, and token components for every row.

| Case | System | Rep | Run | Coverage | Sufficient | Evidence | Files | Flow tokens | Seconds |
| --- | --- | ---: | --- | --- | --- | ---: | ---: | ---: | ---: |
| `microsoft-TypeScript-10020` | codex | 1 | `run-20260826T142635Z` | `missing` | false | 0 | 0 | 190909 | 58.4 |
| `microsoft-TypeScript-10020` | codex | 2 | `run-20260826T142734Z` | `missing` | false | 0 | 0 | 149743 | 49.4 |
| `microsoft-TypeScript-10020` | codex | 3 | `run-20260826T142823Z` | `missing` | false | 0 | 0 | 145362 | 55.5 |
| `microsoft-TypeScript-10020` | codex | 4 | `run-20260826T142919Z` | `missing` | false | 0 | 0 | 162384 | 45.1 |
| `microsoft-TypeScript-10020` | workspace | 1 | `run-20260902T045151Z` | `partial` | false | 9 | 4 | 105662 | 258.4 |
| `microsoft-TypeScript-10020` | workspace | 2 | `run-20260902T045610Z` | `partial` | false | 5 | 2 | 116482 | 254.3 |
| `microsoft-TypeScript-10020` | workspace | 3 | `run-20260902T050023Z` | `partial` | false | 7 | 3 | 104348 | 236.7 |
| `microsoft-TypeScript-10020` | workspace | 4 | `run-20260902T050604Z` | `partial` | false | 9 | 3 | 108006 | 253.6 |
| `microsoft-TypeScript-10041` | codex | 1 | `run-20260826T143004Z` | `missing` | false | 0 | 0 | 167635 | 56.7 |
| `microsoft-TypeScript-10041` | codex | 2 | `run-20260826T143101Z` | `missing` | false | 0 | 0 | 124735 | 52.7 |
| `microsoft-TypeScript-10041` | codex | 3 | `run-20260826T143153Z` | `missing` | false | 0 | 0 | 124730 | 56.4 |
| `microsoft-TypeScript-10041` | codex | 4 | `run-20260826T143250Z` | `missing` | false | 0 | 0 | 145365 | 60.4 |
| `microsoft-TypeScript-10041` | workspace | 1 | `run-20260902T051018Z` | `partial` | false | 1 | 1 | 76445 | 484.4 |
| `microsoft-TypeScript-10041` | workspace | 2 | `run-20260902T051822Z` | `partial` | false | 3 | 2 | 80865 | 225.4 |
| `microsoft-TypeScript-10041` | workspace | 3 | `run-20260902T052207Z` | `partial` | false | 2 | 1 | 71910 | 203.3 |
| `microsoft-TypeScript-10041` | workspace | 4 | `run-20260902T052530Z` | `partial` | false | 3 | 3 | 78711 | 201.5 |
| `microsoft-TypeScript-10473` | codex | 1 | `run-20260826T143350Z` | `missing` | false | 0 | 0 | 102883 | 51.6 |
| `microsoft-TypeScript-10473` | codex | 2 | `run-20260826T143442Z` | `missing` | false | 0 | 0 | 148320 | 51.0 |
| `microsoft-TypeScript-10473` | codex | 3 | `run-20260826T143533Z` | `missing` | false | 0 | 0 | 161560 | 54.7 |
| `microsoft-TypeScript-10473` | codex | 4 | `run-20260826T143627Z` | `missing` | false | 0 | 0 | 174156 | 56.2 |
| `microsoft-TypeScript-10473` | workspace | 1 | `run-20260902T052852Z` | `partial` | false | 9 | 3 | 110147 | 423.9 |
| `microsoft-TypeScript-10473` | workspace | 2 | `run-20260902T053556Z` | `partial` | false | 8 | 3 | 109464 | 227.3 |
| `microsoft-TypeScript-10473` | workspace | 3 | `run-20260902T053943Z` | `partial` | false | 6 | 3 | 104498 | 222.1 |
| `microsoft-TypeScript-10473` | workspace | 4 | `run-20260902T054325Z` | `partial` | false | 8 | 3 | 119336 | 251.6 |
| `microsoft-TypeScript-16278` | codex | 1 | `run-20260826T143724Z` | `missing` | false | 0 | 0 | 192556 | 63.9 |
| `microsoft-TypeScript-16278` | codex | 2 | `run-20260826T143828Z` | `missing` | false | 0 | 0 | 149087 | 54.3 |
| `microsoft-TypeScript-16278` | codex | 3 | `run-20260826T143922Z` | `missing` | false | 0 | 0 | 169286 | 54.4 |
| `microsoft-TypeScript-16278` | codex | 4 | `run-20260826T144016Z` | `missing` | false | 0 | 0 | 185680 | 63.8 |
| `microsoft-TypeScript-16278` | workspace | 1 | `run-20260902T054834Z` | `partial` | false | 14 | 4 | 114893 | 552.7 |
| `microsoft-TypeScript-16278` | workspace | 2 | `run-20260902T061222Z` | `partial` | false | 13 | 4 | 115333 | 254.5 |
| `microsoft-TypeScript-16278` | workspace | 3 | `run-20260902T061637Z` | `partial` | false | 13 | 7 | 132601 | 267.7 |
| `microsoft-TypeScript-16278` | workspace | 4 | `run-20260902T062104Z` | `partial` | false | 14 | 5 | 122529 | 229.6 |
| `microsoft-TypeScript-19074` | codex | 1 | `run-20260826T144120Z` | `missing` | false | 0 | 0 | 235477 | 58.3 |
| `microsoft-TypeScript-19074` | codex | 2 | `run-20260826T144218Z` | `missing` | false | 0 | 0 | 157717 | 50.5 |
| `microsoft-TypeScript-19074` | codex | 3 | `run-20260826T144309Z` | `missing` | false | 0 | 0 | 88692 | 43.2 |
| `microsoft-TypeScript-19074` | codex | 4 | `run-20260826T144352Z` | `missing` | false | 0 | 0 | 159647 | 48.9 |
| `microsoft-TypeScript-19074` | workspace | 1 | `run-20260902T055724Z` | `partial` | false | 3 | 1 | 89067 | 287.7 |
| `microsoft-TypeScript-19074` | workspace | 2 | `run-20260902T060211Z` | `partial` | false | 1 | 1 | 79475 | 246.1 |
| `microsoft-TypeScript-19074` | workspace | 3 | `run-20260902T060617Z` | `partial` | false | 1 | 1 | 57329 | 206.9 |
| `microsoft-TypeScript-19074` | workspace | 4 | `run-20260902T061059Z` | `partial` | false | 2 | 2 | 76157 | 229.6 |
| `microsoft-TypeScript-24625` | codex | 1 | `run-20260826T144441Z` | `missing` | false | 0 | 0 | 124300 | 56.1 |
| `microsoft-TypeScript-24625` | codex | 2 | `run-20260826T144537Z` | `missing` | false | 0 | 0 | 245217 | 57.3 |
| `microsoft-TypeScript-24625` | codex | 3 | `run-20260826T144634Z` | `missing` | false | 0 | 0 | 104437 | 49.5 |
| `microsoft-TypeScript-24625` | codex | 4 | `run-20260826T144724Z` | `missing` | false | 0 | 0 | 151297 | 62.7 |
| `microsoft-TypeScript-24625` | workspace | 1 | `run-20260902T062454Z` | `partial` | false | 6 | 2 | 99261 | 309.6 |
| `microsoft-TypeScript-24625` | workspace | 2 | `run-20260902T063004Z` | `partial` | false | 6 | 4 | 113447 | 209.1 |
| `microsoft-TypeScript-24625` | workspace | 3 | `run-20260902T063333Z` | `partial` | false | 5 | 2 | 90658 | 216.9 |
| `microsoft-TypeScript-24625` | workspace | 4 | `run-20260902T063710Z` | `partial` | false | 4 | 3 | 103451 | 222.3 |
| `microsoft-TypeScript-2953` | codex | 1 | `run-20260826T144827Z` | `missing` | false | 0 | 0 | 174735 | 69.8 |
| `microsoft-TypeScript-2953` | codex | 2 | `run-20260826T144936Z` | `missing` | false | 0 | 0 | 144752 | 63.1 |
| `microsoft-TypeScript-2953` | codex | 3 | `run-20260827T040507Z` | `missing` | false | 0 | 0 | 158807 | 60.5 |
| `microsoft-TypeScript-2953` | codex | 4 | `run-20260827T040608Z` | `missing` | false | 0 | 0 | 182304 | 57.9 |
| `microsoft-TypeScript-2953` | workspace | 1 | `run-20260902T061916Z` | `partial` | false | 2 | 1 | 55916 | 160.0 |
| `microsoft-TypeScript-2953` | workspace | 2 | `run-20260902T062156Z` | `partial` | false | 3 | 1 | 74834 | 180.6 |
| `microsoft-TypeScript-2953` | workspace | 3 | `run-20260902T062456Z` | `partial` | false | 1 | 1 | 60806 | 155.1 |
| `microsoft-TypeScript-2953` | workspace | 4 | `run-20260902T062731Z` | `partial` | false | 3 | 2 | 64437 | 167.1 |
| `microsoft-TypeScript-35468` | codex | 1 | `run-20260827T040705Z` | `missing` | false | 0 | 0 | 169984 | 57.7 |
| `microsoft-TypeScript-35468` | codex | 2 | `run-20260827T040803Z` | `missing` | false | 0 | 0 | 114883 | 52.3 |
| `microsoft-TypeScript-35468` | codex | 3 | `run-20260827T040856Z` | `missing` | false | 0 | 0 | 147405 | 53.4 |
| `microsoft-TypeScript-35468` | codex | 4 | `run-20260827T040949Z` | `missing` | false | 0 | 0 | 114908 | 46.1 |
| `microsoft-TypeScript-35468` | workspace | 1 | `run-20260902T064052Z` | `partial` | false | 14 | 5 | 135996 | 371.7 |
| `microsoft-TypeScript-35468` | workspace | 2 | `run-20260902T064704Z` | `partial` | false | 10 | 5 | 120869 | 259.3 |
| `microsoft-TypeScript-35468` | workspace | 3 | `run-20260902T065123Z` | `partial` | false | 10 | 2 | 130111 | 254.6 |
| `microsoft-TypeScript-35468` | workspace | 4 | `run-20260902T065537Z` | `partial` | false | 14 | 7 | 134366 | 295.3 |
| `microsoft-TypeScript-45713` | codex | 1 | `run-20260827T041035Z` | `missing` | false | 0 | 0 | 141841 | 69.0 |
| `microsoft-TypeScript-45713` | codex | 2 | `run-20260827T041144Z` | `missing` | false | 0 | 0 | 188097 | 63.8 |
| `microsoft-TypeScript-45713` | codex | 3 | `run-20260827T041248Z` | `missing` | false | 0 | 0 | 156694 | 64.7 |
| `microsoft-TypeScript-45713` | codex | 4 | `run-20260827T041352Z` | `missing` | false | 0 | 0 | 162811 | 55.0 |
| `microsoft-TypeScript-45713` | workspace | 1 | `run-20260902T063019Z` | `partial` | false | 5 | 2 | 104432 | 334.5 |
| `microsoft-TypeScript-45713` | workspace | 2 | `run-20260902T063553Z` | `partial` | false | 6 | 2 | 109488 | 235.0 |
| `microsoft-TypeScript-45713` | workspace | 3 | `run-20260902T063948Z` | `partial` | false | 7 | 4 | 105211 | 219.7 |
| `microsoft-TypeScript-45713` | workspace | 4 | `run-20260902T064328Z` | `partial` | false | 6 | 2 | 114376 | 256.1 |
| `microsoft-TypeScript-46770` | codex | 1 | `run-20260827T041447Z` | `missing` | false | 0 | 0 | 151589 | 54.4 |
| `microsoft-TypeScript-46770` | codex | 2 | `run-20260827T041542Z` | `missing` | false | 0 | 0 | 217268 | 66.6 |
| `microsoft-TypeScript-46770` | codex | 3 | `run-20260827T041648Z` | `missing` | false | 0 | 0 | 118156 | 53.1 |
| `microsoft-TypeScript-46770` | codex | 4 | `run-20260827T041741Z` | `missing` | false | 0 | 0 | 133572 | 53.7 |
| `microsoft-TypeScript-46770` | workspace | 1 | `run-20260902T070033Z` | `partial` | false | 7 | 3 | 133259 | 444.4 |
| `microsoft-TypeScript-46770` | workspace | 2 | `run-20260902T070757Z` | `partial` | false | 10 | 3 | 123963 | 323.1 |
| `microsoft-TypeScript-46770` | workspace | 3 | `run-20260902T071320Z` | `partial` | false | 7 | 1 | 118312 | 270.3 |
| `microsoft-TypeScript-46770` | workspace | 4 | `run-20260902T071750Z` | `partial` | false | 10 | 4 | 124166 | 267.2 |
| `microsoft-TypeScript-52695` | codex | 1 | `run-20260827T041835Z` | `missing` | false | 0 | 0 | 150515 | 54.2 |
| `microsoft-TypeScript-52695` | codex | 2 | `run-20260827T041929Z` | `missing` | false | 0 | 0 | 172022 | 65.9 |
| `microsoft-TypeScript-52695` | codex | 3 | `run-20260827T042035Z` | `missing` | false | 0 | 0 | 93066 | 43.3 |
| `microsoft-TypeScript-52695` | codex | 4 | `run-20260827T042118Z` | `missing` | false | 0 | 0 | 145836 | 60.8 |
| `microsoft-TypeScript-52695` | workspace | 1 | `run-20260902T064744Z` | `partial` | false | 7 | 3 | 125342 | 411.9 |
| `microsoft-TypeScript-52695` | workspace | 2 | `run-20260902T065436Z` | `partial` | false | 8 | 2 | 118981 | 272.7 |
| `microsoft-TypeScript-52695` | workspace | 3 | `run-20260902T070353Z` | `partial` | false | 9 | 4 | 121797 | 289.7 |
| `microsoft-TypeScript-52695` | workspace | 4 | `run-20260902T071628Z` | `partial` | false | 11 | 3 | 142129 | 284.9 |
| `pandas-dev-pandas-10068` | codex | 1 | `run-20260827T042220Z` | `missing` | false | 0 | 0 | 121099 | 66.7 |
| `pandas-dev-pandas-10068` | codex | 2 | `run-20260827T042326Z` | `missing` | false | 0 | 0 | 112430 | 58.0 |
| `pandas-dev-pandas-10068` | codex | 3 | `run-20260827T042424Z` | `missing` | false | 0 | 0 | 143353 | 46.9 |
| `pandas-dev-pandas-10068` | codex | 4 | `run-20260827T042511Z` | `missing` | false | 0 | 0 | 198462 | 81.5 |
| `pandas-dev-pandas-10068` | workspace | 1 | `run-20260902T072929Z` | `partial` | false | 5 | 4 | 78239 | 183.5 |
| `pandas-dev-pandas-10068` | workspace | 2 | `run-20260902T074521Z` | `partial` | false | 8 | 4 | 97066 | 202.4 |
| `pandas-dev-pandas-10068` | workspace | 3 | `run-20260902T074843Z` | `partial` | false | 9 | 5 | 119475 | 238.4 |
| `pandas-dev-pandas-10068` | workspace | 4 | `run-20260902T075242Z` | `partial` | false | 6 | 5 | 87215 | 207.1 |
| `pandas-dev-pandas-10150` | codex | 1 | `run-20260827T042633Z` | `missing` | false | 0 | 0 | 142179 | 64.0 |
| `pandas-dev-pandas-10150` | codex | 2 | `run-20260827T042737Z` | `missing` | false | 0 | 0 | 199015 | 77.9 |
| `pandas-dev-pandas-10150` | codex | 3 | `run-20260827T042855Z` | `strong` | true | 8 | 4 | 912365 | 171.7 |
| `pandas-dev-pandas-10150` | codex | 4 | `run-20260827T043147Z` | `missing` | false | 0 | 0 | 155531 | 62.2 |
| `pandas-dev-pandas-10150` | workspace | 1 | `run-20260902T072114Z` | `partial` | false | 4 | 4 | 112721 | 226.6 |
| `pandas-dev-pandas-10150` | workspace | 2 | `run-20260902T072500Z` | `partial` | false | 4 | 4 | 101278 | 222.0 |
| `pandas-dev-pandas-10150` | workspace | 3 | `run-20260902T072842Z` | `partial` | false | 4 | 4 | 90388 | 193.7 |
| `pandas-dev-pandas-10150` | workspace | 4 | `run-20260902T073156Z` | `partial` | false | 3 | 3 | 79247 | 177.0 |
| `pandas-dev-pandas-14942` | codex | 1 | `run-20260827T043249Z` | `missing` | false | 0 | 0 | 164470 | 65.6 |
| `pandas-dev-pandas-14942` | codex | 2 | `run-20260827T043355Z` | `strong` | true | 14 | 5 | 1726888 | 201.5 |
| `pandas-dev-pandas-14942` | codex | 3 | `run-20260827T043716Z` | `missing` | false | 0 | 0 | 160256 | 86.0 |
| `pandas-dev-pandas-14942` | codex | 4 | `run-20260827T043842Z` | `missing` | false | 0 | 0 | 200925 | 59.9 |
| `pandas-dev-pandas-14942` | workspace | 1 | `run-20260902T080000Z` | `partial` | false | 8 | 3 | 130285 | 246.6 |
| `pandas-dev-pandas-14942` | workspace | 2 | `run-20260902T081246Z` | `partial` | false | 9 | 4 | 127754 | 230.3 |
| `pandas-dev-pandas-14942` | workspace | 3 | `run-20260902T081637Z` | `partial` | false | 7 | 4 | 147830 | 250.9 |
| `pandas-dev-pandas-14942` | workspace | 4 | `run-20260902T082047Z` | `partial` | false | 5 | 4 | 110980 | 234.9 |
| `pandas-dev-pandas-16499` | codex | 1 | `run-20260827T043942Z` | `missing` | false | 0 | 0 | 204944 | 75.6 |
| `pandas-dev-pandas-16499` | codex | 2 | `run-20260827T044058Z` | `missing` | false | 0 | 0 | 160519 | 75.3 |
| `pandas-dev-pandas-16499` | codex | 3 | `run-20260827T044214Z` | `missing` | false | 0 | 0 | 147681 | 61.7 |
| `pandas-dev-pandas-16499` | codex | 4 | `run-20260827T044315Z` | `missing` | false | 0 | 0 | 133643 | 54.1 |
| `pandas-dev-pandas-16499` | workspace | 1 | `run-20260902T073453Z` | `partial` | false | 3 | 1 | 81258 | 172.7 |
| `pandas-dev-pandas-16499` | workspace | 2 | `run-20260902T073745Z` | `partial` | false | 3 | 1 | 102037 | 215.0 |
| `pandas-dev-pandas-16499` | workspace | 3 | `run-20260902T074121Z` | `partial` | false | 3 | 1 | 78502 | 154.5 |
| `pandas-dev-pandas-16499` | workspace | 4 | `run-20260902T074355Z` | `partial` | false | 3 | 1 | 92486 | 195.4 |
| `pandas-dev-pandas-16764` | codex | 1 | `run-20260827T044409Z` | `missing` | false | 0 | 0 | 161117 | 59.3 |
| `pandas-dev-pandas-16764` | codex | 2 | `run-20260827T044508Z` | `missing` | false | 0 | 0 | 136619 | 64.8 |
| `pandas-dev-pandas-16764` | codex | 3 | `run-20260827T044613Z` | `missing` | false | 0 | 0 | 158718 | 52.9 |
| `pandas-dev-pandas-16764` | codex | 4 | `run-20260827T044706Z` | `missing` | false | 0 | 0 | 143193 | 57.5 |
| `pandas-dev-pandas-16764` | workspace | 1 | `run-20260902T082442Z` | `partial` | false | 4 | 1 | 73630 | 212.1 |
| `pandas-dev-pandas-16764` | workspace | 2 | `run-20260902T082814Z` | `partial` | false | 6 | 3 | 88581 | 221.9 |
| `pandas-dev-pandas-16764` | workspace | 3 | `run-20260902T083156Z` | `partial` | false | 2 | 1 | 91398 | 226.9 |
| `pandas-dev-pandas-16764` | workspace | 4 | `run-20260902T083543Z` | `partial` | false | 2 | 2 | 84265 | 224.9 |
| `pandas-dev-pandas-22698` | codex | 1 | `run-20260827T044804Z` | `missing` | false | 0 | 0 | 153985 | 59.8 |
| `pandas-dev-pandas-22698` | codex | 2 | `run-20260827T044903Z` | `missing` | false | 0 | 0 | 232711 | 69.9 |
| `pandas-dev-pandas-22698` | codex | 3 | `run-20260827T045013Z` | `missing` | false | 0 | 0 | 122820 | 56.0 |
| `pandas-dev-pandas-22698` | codex | 4 | `run-20260827T045109Z` | `strong` | true | 8 | 3 | 501415 | 121.8 |
| `pandas-dev-pandas-22698` | workspace | 1 | `run-20260902T074710Z` | `partial` | false | 5 | 3 | 93395 | 219.5 |
| `pandas-dev-pandas-22698` | workspace | 2 | `run-20260902T075050Z` | `partial` | false | 3 | 2 | 100113 | 208.5 |
| `pandas-dev-pandas-22698` | workspace | 3 | `run-20260902T075419Z` | `partial` | false | 5 | 4 | 109879 | 250.1 |
| `pandas-dev-pandas-22698` | workspace | 4 | `run-20260902T075829Z` | `partial` | false | 4 | 2 | 85745 | 224.0 |
| `pandas-dev-pandas-22872` | codex | 1 | `run-20260827T045311Z` | `missing` | false | 0 | 0 | 156376 | 59.1 |
| `pandas-dev-pandas-22872` | codex | 2 | `run-20260827T045410Z` | `missing` | false | 0 | 0 | 184103 | 68.8 |
| `pandas-dev-pandas-22872` | codex | 3 | `run-20260827T045519Z` | `strong` | true | 17 | 8 | 808256 | 188.8 |
| `pandas-dev-pandas-22872` | codex | 4 | `run-20260827T045828Z` | `missing` | false | 0 | 0 | 133330 | 54.4 |
| `pandas-dev-pandas-22872` | workspace | 1 | `run-20260902T083928Z` | `partial` | false | 3 | 3 | 119458 | 245.9 |
| `pandas-dev-pandas-22872` | workspace | 2 | `run-20260902T084334Z` | `missing` | false | 0 | 0 | 96226 | 251.0 |
| `pandas-dev-pandas-22872` | workspace | 3 | `run-20260902T084745Z` | `partial` | false | 1 | 1 | 104800 | 257.3 |
| `pandas-dev-pandas-22872` | workspace | 4 | `run-20260902T085202Z` | `missing` | false | 0 | 0 | 82683 | 184.8 |
| `pandas-dev-pandas-25183` | codex | 1 | `run-20260827T045922Z` | `missing` | false | 0 | 0 | 154505 | 60.7 |
| `pandas-dev-pandas-25183` | codex | 2 | `run-20260827T050023Z` | `missing` | false | 0 | 0 | 117278 | 51.3 |
| `pandas-dev-pandas-25183` | codex | 3 | `run-20260827T050114Z` | `missing` | false | 0 | 0 | 175217 | 61.1 |
| `pandas-dev-pandas-25183` | codex | 4 | `run-20260827T050215Z` | `missing` | false | 0 | 0 | 105218 | 57.2 |
| `pandas-dev-pandas-25183` | workspace | 1 | `run-20260902T080213Z` | `partial` | false | 6 | 2 | 142769 | 317.8 |
| `pandas-dev-pandas-25183` | workspace | 2 | `run-20260902T080730Z` | `partial` | false | 5 | 1 | 100663 | 223.7 |
| `pandas-dev-pandas-25183` | workspace | 3 | `run-20260902T081114Z` | `partial` | false | 8 | 3 | 123037 | 240.5 |
| `pandas-dev-pandas-25183` | workspace | 4 | `run-20260902T081514Z` | `partial` | false | 7 | 3 | 133996 | 247.9 |
| `pandas-dev-pandas-32289` | codex | 1 | `run-20260827T050312Z` | `missing` | false | 0 | 0 | 155878 | 47.4 |
| `pandas-dev-pandas-32289` | codex | 2 | `run-20260827T050400Z` | `missing` | false | 0 | 0 | 164229 | 52.2 |
| `pandas-dev-pandas-32289` | codex | 3 | `run-20260827T050452Z` | `missing` | false | 0 | 0 | 97864 | 44.7 |
| `pandas-dev-pandas-32289` | codex | 4 | `run-20260827T050537Z` | `missing` | false | 0 | 0 | 166277 | 50.6 |
| `pandas-dev-pandas-32289` | workspace | 1 | `run-20260902T085507Z` | `missing` | false | 0 | 0 | 71422 | 202.7 |
| `pandas-dev-pandas-32289` | workspace | 2 | `run-20260902T085830Z` | `partial` | false | 2 | 2 | 62268 | 174.4 |
| `pandas-dev-pandas-32289` | workspace | 3 | `run-20260902T090124Z` | `partial` | false | 1 | 1 | 58686 | 171.6 |
| `pandas-dev-pandas-32289` | workspace | 4 | `run-20260902T090416Z` | `partial` | false | 1 | 1 | 59457 | 157.9 |
| `pandas-dev-pandas-35925` | codex | 1 | `run-20260827T050627Z` | `missing` | false | 0 | 0 | 83844 | 45.0 |
| `pandas-dev-pandas-35925` | codex | 2 | `run-20260827T050712Z` | `missing` | false | 0 | 0 | 104035 | 57.4 |
| `pandas-dev-pandas-35925` | codex | 3 | `run-20260827T050810Z` | `missing` | false | 0 | 0 | 126347 | 46.3 |
| `pandas-dev-pandas-35925` | codex | 4 | `run-20260827T050856Z` | `missing` | false | 0 | 0 | 171483 | 51.8 |
| `pandas-dev-pandas-35925` | workspace | 1 | `run-20260902T081923Z` | `partial` | false | 1 | 1 | 46005 | 133.2 |
| `pandas-dev-pandas-35925` | workspace | 2 | `run-20260902T082136Z` | `partial` | false | 1 | 1 | 30244 | 103.4 |
| `pandas-dev-pandas-35925` | workspace | 3 | `run-20260902T082319Z` | `partial` | false | 1 | 1 | 46884 | 144.3 |
| `pandas-dev-pandas-35925` | workspace | 4 | `run-20260902T082543Z` | `partial` | false | 1 | 1 | 46919 | 102.6 |
| `pandas-dev-pandas-36617` | codex | 1 | `run-20260827T050948Z` | `missing` | false | 0 | 0 | 134562 | 72.5 |
| `pandas-dev-pandas-36617` | codex | 2 | `run-20260827T051100Z` | `missing` | false | 0 | 0 | 187771 | 62.2 |
| `pandas-dev-pandas-36617` | codex | 3 | `run-20260827T051203Z` | `missing` | false | 0 | 0 | 95723 | 65.2 |
| `pandas-dev-pandas-36617` | codex | 4 | `run-20260827T051308Z` | `missing` | false | 0 | 0 | 158582 | 65.3 |
| `pandas-dev-pandas-36617` | workspace | 1 | `run-20260902T090812Z` | `partial` | false | 1 | 1 | 67770 | 185.4 |
| `pandas-dev-pandas-36617` | workspace | 2 | `run-20260902T091117Z` | `partial` | false | 3 | 2 | 94357 | 235.0 |
| `pandas-dev-pandas-36617` | workspace | 3 | `run-20260902T091512Z` | `partial` | false | 4 | 2 | 64554 | 178.7 |
| `pandas-dev-pandas-36617` | workspace | 4 | `run-20260902T091811Z` | `partial` | false | 1 | 1 | 69422 | 152.7 |
| `pandas-dev-pandas-4542` | codex | 1 | `run-20260827T051413Z` | `missing` | false | 0 | 0 | 123540 | 44.0 |
| `pandas-dev-pandas-4542` | codex | 2 | `run-20260827T051457Z` | `missing` | false | 0 | 0 | 114264 | 51.8 |
| `pandas-dev-pandas-4542` | codex | 3 | `run-20260827T051549Z` | `missing` | false | 0 | 0 | 78571 | 40.1 |
| `pandas-dev-pandas-4542` | codex | 4 | `run-20260827T051629Z` | `missing` | false | 0 | 0 | 119453 | 56.8 |
| `pandas-dev-pandas-4542` | workspace | 1 | `run-20260902T082726Z` | `partial` | false | 6 | 2 | 52825 | 108.0 |
| `pandas-dev-pandas-4542` | workspace | 2 | `run-20260902T082914Z` | `partial` | false | 6 | 3 | 128922 | 247.8 |
| `pandas-dev-pandas-4542` | workspace | 3 | `run-20260902T083322Z` | `partial` | false | 8 | 4 | 137940 | 265.5 |
| `pandas-dev-pandas-4542` | workspace | 4 | `run-20260902T083747Z` | `partial` | false | 7 | 2 | 95949 | 197.4 |
| `vuejs-vue-10004` | codex | 1 | `run-20260827T051726Z` | `missing` | false | 0 | 0 | 170474 | 62.5 |
| `vuejs-vue-10004` | codex | 2 | `run-20260827T051828Z` | `missing` | false | 0 | 0 | 146683 | 56.4 |
| `vuejs-vue-10004` | codex | 3 | `run-20260827T051925Z` | `missing` | false | 0 | 0 | 188670 | 60.2 |
| `vuejs-vue-10004` | codex | 4 | `run-20260827T052025Z` | `missing` | false | 0 | 0 | 146744 | 67.4 |
| `vuejs-vue-10004` | workspace | 1 | `run-20260902T092201Z` | `partial` | false | 10 | 7 | 135688 | 250.8 |
| `vuejs-vue-10004` | workspace | 2 | `run-20260902T092612Z` | `partial` | false | 10 | 7 | 134299 | 247.4 |
| `vuejs-vue-10004` | workspace | 3 | `run-20260902T093019Z` | `partial` | false | 10 | 7 | 133112 | 256.6 |
| `vuejs-vue-10004` | workspace | 4 | `run-20260902T093436Z` | `partial` | false | 11 | 7 | 125510 | 256.4 |
| `vuejs-vue-10519` | codex | 1 | `run-20260827T052132Z` | `strong` | true | 5 | 1 | 276440 | 98.6 |
| `vuejs-vue-10519` | codex | 2 | `run-20260827T052311Z` | `missing` | false | 0 | 0 | 123799 | 67.3 |
| `vuejs-vue-10519` | codex | 3 | `run-20260827T052418Z` | `missing` | false | 0 | 0 | 185579 | 70.0 |
| `vuejs-vue-10519` | codex | 4 | `run-20260827T052528Z` | `missing` | false | 0 | 0 | 159566 | 59.7 |
| `vuejs-vue-10519` | workspace | 1 | `run-20260902T084105Z` | `partial` | false | 5 | 3 | 87332 | 233.7 |
| `vuejs-vue-10519` | workspace | 2 | `run-20260902T084458Z` | `partial` | false | 5 | 3 | 72056 | 207.5 |
| `vuejs-vue-10519` | workspace | 3 | `run-20260902T084826Z` | `partial` | false | 5 | 3 | 73199 | 187.7 |
| `vuejs-vue-10519` | workspace | 4 | `run-20260902T085134Z` | `partial` | false | 5 | 3 | 78360 | 186.2 |
| `vuejs-vue-10803` | codex | 1 | `run-20260827T052628Z` | `missing` | false | 0 | 0 | 114756 | 50.4 |
| `vuejs-vue-10803` | codex | 2 | `run-20260827T052718Z` | `missing` | false | 0 | 0 | 81375 | 81.8 |
| `vuejs-vue-10803` | codex | 3 | `run-20260827T052840Z` | `missing` | false | 0 | 0 | 135570 | 68.4 |
| `vuejs-vue-10803` | codex | 4 | `run-20260827T052949Z` | `missing` | false | 0 | 0 | 186920 | 72.3 |
| `vuejs-vue-10803` | workspace | 1 | `run-20260902T093853Z` | `partial` | false | 5 | 3 | 82551 | 206.5 |
| `vuejs-vue-10803` | workspace | 2 | `run-20260902T094219Z` | `partial` | false | 3 | 2 | 77675 | 183.4 |
| `vuejs-vue-10803` | workspace | 3 | `run-20260902T094522Z` | `partial` | false | 5 | 3 | 76434 | 196.2 |
| `vuejs-vue-10803` | workspace | 4 | `run-20260902T094838Z` | `partial` | false | 5 | 3 | 82790 | 218.6 |
| `vuejs-vue-11718` | codex | 1 | `run-20260827T053101Z` | `missing` | false | 0 | 0 | 87742 | 48.3 |
| `vuejs-vue-11718` | codex | 2 | `run-20260827T053149Z` | `missing` | false | 0 | 0 | 177382 | 52.3 |
| `vuejs-vue-11718` | codex | 3 | `run-20260827T053242Z` | `missing` | false | 0 | 0 | 70416 | 43.9 |
| `vuejs-vue-11718` | codex | 4 | `run-20260827T053326Z` | `missing` | false | 0 | 0 | 78118 | 46.2 |
| `vuejs-vue-11718` | workspace | 1 | `run-20260902T085440Z` | `partial` | false | 5 | 3 | 66747 | 192.6 |
| `vuejs-vue-11718` | workspace | 2 | `run-20260902T085752Z` | `partial` | false | 4 | 3 | 72170 | 218.2 |
| `vuejs-vue-11718` | workspace | 3 | `run-20260902T090131Z` | `partial` | false | 4 | 3 | 65255 | 197.4 |
| `vuejs-vue-11718` | workspace | 4 | `run-20260902T090448Z` | `missing` | false | 0 | 0 | 29025 | 99.6 |
| `vuejs-vue-11782` | codex | 1 | `run-20260827T053412Z` | `missing` | false | 0 | 0 | 185108 | 61.2 |
| `vuejs-vue-11782` | codex | 2 | `run-20260827T053513Z` | `missing` | false | 0 | 0 | 125275 | 66.0 |
| `vuejs-vue-11782` | codex | 3 | `run-20260827T053619Z` | `missing` | false | 0 | 0 | 144680 | 58.7 |
| `vuejs-vue-11782` | codex | 4 | `run-20260827T053718Z` | `missing` | false | 0 | 0 | 131894 | 62.6 |
| `vuejs-vue-11782` | workspace | 1 | `run-20260902T095217Z` | `partial` | false | 2 | 2 | 65379 | 205.1 |
| `vuejs-vue-11782` | workspace | 2 | `run-20260902T095654Z` | `partial` | false | 6 | 4 | 73344 | 187.4 |
| `vuejs-vue-11782` | workspace | 3 | `run-20260902T100001Z` | `partial` | false | 4 | 3 | 75061 | 225.5 |
| `vuejs-vue-11782` | workspace | 4 | `run-20260902T100347Z` | `partial` | false | 6 | 4 | 73277 | 193.6 |
| `vuejs-vue-13052` | codex | 1 | `run-20260827T053820Z` | `missing` | false | 0 | 0 | 173682 | 70.4 |
| `vuejs-vue-13052` | codex | 2 | `run-20260827T053931Z` | `missing` | false | 0 | 0 | 118504 | 46.4 |
| `vuejs-vue-13052` | codex | 3 | `run-20260827T054017Z` | `missing` | false | 0 | 0 | 97845 | 43.2 |
| `vuejs-vue-13052` | codex | 4 | `run-20260827T054100Z` | `missing` | false | 0 | 0 | 114044 | 52.4 |
| `vuejs-vue-13052` | workspace | 1 | `run-20260902T090628Z` | `partial` | false | 2 | 1 | 62611 | 184.9 |
| `vuejs-vue-13052` | workspace | 2 | `run-20260902T090932Z` | `partial` | false | 1 | 1 | 58651 | 161.3 |
| `vuejs-vue-13052` | workspace | 3 | `run-20260902T091214Z` | `partial` | false | 5 | 2 | 78088 | 195.0 |
| `vuejs-vue-13052` | workspace | 4 | `run-20260902T091529Z` | `partial` | false | 3 | 1 | 63519 | 174.5 |
| `vuejs-vue-5884` | codex | 1 | `run-20260827T054153Z` | `missing` | false | 0 | 0 | 167165 | 53.2 |
| `vuejs-vue-5884` | codex | 2 | `run-20260827T054246Z` | `missing` | false | 0 | 0 | 174560 | 54.1 |
| `vuejs-vue-5884` | codex | 3 | `run-20260827T054340Z` | `missing` | false | 0 | 0 | 69054 | 38.7 |
| `vuejs-vue-5884` | codex | 4 | `run-20260827T054419Z` | `missing` | false | 0 | 0 | 167827 | 59.7 |
| `vuejs-vue-5884` | workspace | 1 | `run-20260902T100700Z` | `partial` | false | 5 | 4 | 90320 | 222.4 |
| `vuejs-vue-5884` | workspace | 2 | `run-20260902T101043Z` | `strong` | true | 7 | 6 | 105793 | 236.9 |
| `vuejs-vue-5884` | workspace | 3 | `run-20260902T101440Z` | `partial` | false | 6 | 6 | 117924 | 228.7 |
| `vuejs-vue-5884` | workspace | 4 | `run-20260902T101829Z` | `partial` | false | 3 | 3 | 82307 | 190.1 |
| `vuejs-vue-6097` | codex | 1 | `run-20260827T054518Z` | `strong` | true | 6 | 3 | 603804 | 138.3 |
| `vuejs-vue-6097` | codex | 2 | `run-20260827T054737Z` | `missing` | false | 0 | 0 | 449427 | 116.3 |
| `vuejs-vue-6097` | codex | 3 | `run-20260827T054933Z` | `missing` | false | 0 | 0 | 68665 | 40.2 |
| `vuejs-vue-6097` | codex | 4 | `run-20260827T055013Z` | `missing` | false | 0 | 0 | 167735 | 57.1 |
| `vuejs-vue-6097` | workspace | 1 | `run-20260902T091823Z` | `partial` | false | 6 | 6 | 102384 | 250.2 |
| `vuejs-vue-6097` | workspace | 2 | `run-20260902T092233Z` | `partial` | false | 6 | 3 | 103600 | 228.7 |
| `vuejs-vue-6097` | workspace | 3 | `run-20260902T092622Z` | `partial` | false | 8 | 6 | 93457 | 209.1 |
| `vuejs-vue-6097` | workspace | 4 | `run-20260902T092951Z` | `partial` | false | 6 | 4 | 100589 | 207.8 |
| `vuejs-vue-6301` | codex | 1 | `run-20260827T055110Z` | `missing` | false | 0 | 0 | 145665 | 44.9 |
| `vuejs-vue-6301` | codex | 2 | `run-20260827T055155Z` | `missing` | false | 0 | 0 | 134914 | 42.7 |
| `vuejs-vue-6301` | codex | 3 | `run-20260827T055238Z` | `missing` | false | 0 | 0 | 137218 | 52.5 |
| `vuejs-vue-6301` | codex | 4 | `run-20260827T055330Z` | `missing` | false | 0 | 0 | 180120 | 55.3 |
| `vuejs-vue-6301` | workspace | 1 | `run-20260902T102139Z` | `partial` | false | 6 | 4 | 80822 | 183.7 |
| `vuejs-vue-6301` | workspace | 2 | `run-20260902T102442Z` | `partial` | false | 6 | 4 | 83874 | 191.4 |
| `vuejs-vue-6301` | workspace | 3 | `run-20260902T103033Z` | `partial` | false | 4 | 3 | 78232 | 170.1 |
| `vuejs-vue-6301` | workspace | 4 | `run-20260902T103323Z` | `partial` | false | 5 | 4 | 82572 | 186.8 |
| `vuejs-vue-8528` | codex | 1 | `run-20260827T055426Z` | `missing` | false | 0 | 0 | 114963 | 63.0 |
| `vuejs-vue-8528` | codex | 2 | `run-20260827T055529Z` | `missing` | false | 0 | 0 | 88871 | 57.9 |
| `vuejs-vue-8528` | codex | 3 | `run-20260827T055627Z` | `missing` | false | 0 | 0 | 147864 | 60.0 |
| `vuejs-vue-8528` | codex | 4 | `run-20260827T055727Z` | `missing` | false | 0 | 0 | 57971 | 46.0 |
| `vuejs-vue-8528` | workspace | 1 | `run-20260902T093319Z` | `partial` | false | 4 | 2 | 68797 | 215.4 |
| `vuejs-vue-8528` | workspace | 2 | `run-20260902T093654Z` | `partial` | false | 3 | 1 | 61749 | 162.3 |
| `vuejs-vue-8528` | workspace | 3 | `run-20260902T093937Z` | `partial` | false | 2 | 2 | 65770 | 160.8 |
| `vuejs-vue-8528` | workspace | 4 | `run-20260902T094218Z` | `partial` | false | 3 | 3 | 64930 | 160.8 |
| `vuejs-vue-9042` | codex | 1 | `run-20260827T055813Z` | `missing` | false | 0 | 0 | 113933 | 63.6 |
| `vuejs-vue-9042` | codex | 2 | `run-20260827T055916Z` | `missing` | false | 0 | 0 | 187684 | 62.6 |
| `vuejs-vue-9042` | codex | 3 | `run-20260827T060019Z` | `missing` | false | 0 | 0 | 146872 | 51.3 |
| `vuejs-vue-9042` | codex | 4 | `run-20260827T060110Z` | `missing` | false | 0 | 0 | 194594 | 72.9 |
| `vuejs-vue-9042` | workspace | 1 | `run-20260902T103630Z` | `partial` | false | 9 | 5 | 143044 | 265.5 |
| `vuejs-vue-9042` | workspace | 2 | `run-20260902T104055Z` | `partial` | false | 7 | 6 | 109787 | 219.1 |
| `vuejs-vue-9042` | workspace | 3 | `run-20260902T104434Z` | `partial` | false | 8 | 5 | 144148 | 268.3 |
| `vuejs-vue-9042` | workspace | 4 | `run-20260902T104903Z` | `partial` | false | 9 | 6 | 142166 | 274.0 |
| `vuejs-vue-9842` | codex | 1 | `run-20260827T060223Z` | `missing` | false | 0 | 0 | 103214 | 47.8 |
| `vuejs-vue-9842` | codex | 2 | `run-20260827T060311Z` | `missing` | false | 0 | 0 | 142999 | 50.2 |
| `vuejs-vue-9842` | codex | 3 | `run-20260827T060401Z` | `missing` | false | 0 | 0 | 174176 | 58.0 |
| `vuejs-vue-9842` | codex | 4 | `run-20260827T060459Z` | `missing` | false | 0 | 0 | 126385 | 50.0 |
| `vuejs-vue-9842` | workspace | 1 | `run-20260902T094458Z` | `partial` | false | 9 | 6 | 123346 | 226.4 |
| `vuejs-vue-9842` | workspace | 2 | `run-20260902T094845Z` | `partial` | false | 8 | 5 | 110663 | 218.5 |
| `vuejs-vue-9842` | workspace | 3 | `run-20260902T095224Z` | `partial` | false | 7 | 5 | 119261 | 245.8 |
| `vuejs-vue-9842` | workspace | 4 | `run-20260902T095629Z` | `partial` | false | 12 | 6 | 126494 | 270.7 |

## Limitations

- Workspace indexing-token usage is not provider-logged. The report compares recorded non-indexing retrieval-flow tokens and marks Workspace indexing totals unavailable.
- Response generation was skipped for Workspace; this is a retrieval and final-evidence comparison.
- Failed attempts are retained in the three source Workspace ledgers but excluded from the 140 valid-run inventory.
- The complete topology assignment file was finalized from frozen issue/Oracle structure without consulting retrieval output; the earlier documentation contained only five explicit examples.

## Reproduction

- Script: `testing/codeRepoQA/aggregate_four_run_comparison.py`
- Workspace ledger: `testing/codeRepoQA/statistics/runs/2026-09-02-workspace-four-runs-complete.json`
- Codex ledger: `testing/codeRepoQA/statistics/runs/2026-08-26-codex-luna-four-runs.json`
- JSON report: `testing/codeRepoQA/statistics/runs/2026-09-02-workspace-vs-codex-four-run-comparison.json`
