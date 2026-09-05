# Workspace vs Codex Luna Efficient — 35-Case Four-Run Comparison

## Status and scope

Workspace and Codex are complete: 35 cases and 140 valid retrieval runs each. Two interrupted Codex attempts remain auditable in the ledger but are excluded from all metrics.

## Conditions

- Workspace: `configs/testing/statistics-workspace.json`, `gpt-5.6-luna`, qualification-first controller, response generation skipped, final evidence selection enabled.
- Codex: `2026-09-02-codex-efficient-luna-four-runs.json`, `gpt-5.6-luna`, `efficient` prompt profile.
- Aggregation: calculate each run, average four runs within each case, then macro-average the 35 case means.
- Workspace collection used two workers for the final 32 cases; elapsed time is compared directly as requested.

## Metric note

Files are ranked. Implementation Oracle files define precision and recall; test/validation and documentation Oracle files receive partial NDCG relevance. Missing ranks are nonrelevant. Values are calculated at 1, 2, 5, and 10.

## Descriptive metrics

| System | Cases | Runs | P@1 | P@2 | P@5 | P@10 | R@1 | R@2 | R@5 | R@10 | NDCG@1 | NDCG@2 | NDCG@5 | NDCG@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Workspace | 35 | 140 | 0.329 | 0.304 | 0.191 | 0.098 | 0.169 | 0.332 | 0.508 | 0.517 | 0.350 | 0.384 | 0.401 | 0.373 |
| Codex Luna efficient | 35 | 140 | 0.386 | 0.382 | 0.260 | 0.144 | 0.207 | 0.425 | 0.677 | 0.709 | 0.407 | 0.469 | 0.511 | 0.502 |

## Operational summary

| System | Sufficient rate | Mean retrieved files | Any implementation hit | Full implementation recall | Mean flow tokens | Mean elapsed seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Workspace | 0.007 | 2.964 | 0.679 | 0.407 | 95315 | 227.5 |
| Codex Luna efficient | 1.000 | 6.493 | 0.893 | 0.579 | 283913 | 121.7 |

## Partition breakdown

| Group | System | Cases | Runs | P@5 | R@5 | NDCG@5 | Any hit | Full recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `development` | Workspace | 28 | 112 | 0.188 | 0.474 | 0.392 | 0.670 | 0.366 |
| `development` | Codex | 28 | 112 | 0.246 | 0.596 | 0.464 | 0.866 | 0.473 |
| `final` | Workspace | 7 | 28 | 0.207 | 0.643 | 0.437 | 0.714 | 0.571 |
| `final` | Codex | 7 | 28 | 0.314 | 1.000 | 0.700 | 1.000 | 1.000 |

## Issue-category breakdown

| Group | System | Cases | Runs | P@5 | R@5 | NDCG@5 | Any hit | Full recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `api_behavior_design` | Workspace | 5 | 20 | 0.300 | 0.625 | 0.515 | 0.800 | 0.550 |
| `api_behavior_design` | Codex | 5 | 20 | 0.400 | 0.925 | 0.555 | 1.000 | 0.800 |
| `bug_regression` | Workspace | 5 | 20 | 0.200 | 0.800 | 0.525 | 0.800 | 0.800 |
| `bug_regression` | Codex | 5 | 20 | 0.210 | 0.850 | 0.518 | 0.850 | 0.850 |
| `compatibility_versioning` | Workspace | 5 | 20 | 0.100 | 0.500 | 0.225 | 0.500 | 0.500 |
| `compatibility_versioning` | Codex | 5 | 20 | 0.120 | 0.600 | 0.212 | 0.600 | 0.600 |
| `feature_enhancement` | Workspace | 5 | 20 | 0.240 | 0.426 | 0.403 | 0.800 | 0.100 |
| `feature_enhancement` | Codex | 5 | 20 | 0.370 | 0.547 | 0.547 | 1.000 | 0.200 |
| `maintenance_refactor` | Workspace | 5 | 20 | 0.120 | 0.390 | 0.344 | 0.600 | 0.350 |
| `maintenance_refactor` | Codex | 5 | 20 | 0.240 | 0.631 | 0.738 | 0.800 | 0.600 |
| `performance_memory` | Workspace | 5 | 20 | 0.170 | 0.336 | 0.290 | 0.650 | 0.200 |
| `performance_memory` | Codex | 5 | 20 | 0.200 | 0.350 | 0.343 | 1.000 | 0.400 |
| `testing_build_tooling` | Workspace | 5 | 20 | 0.210 | 0.475 | 0.504 | 0.600 | 0.350 |
| `testing_build_tooling` | Codex | 5 | 20 | 0.280 | 0.833 | 0.667 | 1.000 | 0.600 |

## Retrieval-topology breakdown

| Group | System | Cases | Runs | P@5 | R@5 | NDCG@5 | Any hit | Full recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `broad_cross_cutting` | Workspace | 2 | 8 | 0.125 | 0.046 | 0.191 | 0.625 | 0.000 |
| `broad_cross_cutting` | Codex | 2 | 8 | 0.275 | 0.099 | 0.323 | 1.000 | 0.000 |
| `connected_mechanism` | Workspace | 13 | 52 | 0.338 | 0.571 | 0.526 | 0.923 | 0.288 |
| `connected_mechanism` | Codex | 13 | 52 | 0.427 | 0.705 | 0.620 | 1.000 | 0.385 |
| `localized_declarative` | Workspace | 6 | 24 | 0.033 | 0.167 | 0.115 | 0.167 | 0.167 |
| `localized_declarative` | Codex | 6 | 24 | 0.100 | 0.386 | 0.401 | 0.542 | 0.375 |
| `localized_implementation` | Workspace | 14 | 56 | 0.132 | 0.661 | 0.438 | 0.679 | 0.679 |
| `localized_implementation` | Codex | 14 | 56 | 0.171 | 0.857 | 0.484 | 0.929 | 0.929 |

## Repository breakdown

| Group | System | Cases | Runs | P@5 | R@5 | NDCG@5 | Any hit | Full recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `microsoft/TypeScript` | Workspace | 11 | 44 | 0.268 | 0.527 | 0.403 | 0.795 | 0.364 |
| `microsoft/TypeScript` | Codex | 11 | 44 | 0.359 | 0.701 | 0.516 | 0.932 | 0.477 |
| `pandas-dev/pandas` | Workspace | 12 | 48 | 0.163 | 0.393 | 0.365 | 0.583 | 0.292 |
| `pandas-dev/pandas` | Codex | 12 | 48 | 0.233 | 0.603 | 0.472 | 0.833 | 0.500 |
| `vuejs/vue` | Workspace | 12 | 48 | 0.150 | 0.604 | 0.436 | 0.667 | 0.562 |
| `vuejs/vue` | Codex | 12 | 48 | 0.196 | 0.728 | 0.547 | 0.917 | 0.750 |

## Per-case results

| Case | Partition | Topology | System | P@5 | R@5 | NDCG@5 | Any-hit runs | Full-recall runs | Mean files | Mean tokens | Mean seconds |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `microsoft-TypeScript-10020` | `development` | `connected_mechanism` | Workspace | 0.200 | 0.500 | 0.273 | 4/4 | 0/4 | 3.000 | 108624 | 250.7 |
|  |  |  | Codex | 0.200 | 0.500 | 0.445 | 4/4 | 0/4 | 5.250 | 203872 | 98.3 |
| `microsoft-TypeScript-10041` | `final` | `localized_implementation` | Workspace | 0.100 | 0.500 | 0.191 | 2/4 | 2/4 | 1.750 | 76983 | 278.7 |
|  |  |  | Codex | 0.200 | 1.000 | 0.363 | 4/4 | 4/4 | 4.000 | 849162 | 199.3 |
| `microsoft-TypeScript-10473` | `final` | `connected_mechanism` | Workspace | 0.400 | 1.000 | 0.629 | 4/4 | 4/4 | 3.000 | 110861 | 281.2 |
|  |  |  | Codex | 0.400 | 1.000 | 0.600 | 4/4 | 4/4 | 4.500 | 224604 | 115.3 |
| `microsoft-TypeScript-16278` | `development` | `connected_mechanism` | Workspace | 0.800 | 0.500 | 0.888 | 4/4 | 0/4 | 5.000 | 121339 | 326.1 |
|  |  |  | Codex | 1.000 | 0.625 | 1.000 | 4/4 | 0/4 | 6.250 | 200626 | 120.0 |
| `microsoft-TypeScript-19074` | `final` | `connected_mechanism` | Workspace | 0.050 | 0.125 | 0.161 | 1/4 | 0/4 | 1.250 | 75507 | 242.6 |
|  |  |  | Codex | 0.400 | 1.000 | 0.980 | 4/4 | 4/4 | 7.250 | 73227 | 89.1 |
| `microsoft-TypeScript-24625` | `development` | `localized_implementation` | Workspace | 0.200 | 1.000 | 0.419 | 4/4 | 4/4 | 2.750 | 101704 | 239.5 |
|  |  |  | Codex | 0.200 | 1.000 | 0.383 | 4/4 | 4/4 | 4.750 | 175100 | 123.4 |
| `microsoft-TypeScript-2953` | `development` | `localized_declarative` | Workspace | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 1.250 | 63998 | 165.7 |
|  |  |  | Codex | 0.050 | 0.250 | 0.125 | 1/4 | 1/4 | 6.750 | 297974 | 152.6 |
| `microsoft-TypeScript-35468` | `development` | `connected_mechanism` | Workspace | 0.500 | 0.625 | 0.567 | 4/4 | 2/4 | 4.750 | 130336 | 295.2 |
|  |  |  | Codex | 0.400 | 0.500 | 0.360 | 4/4 | 0/4 | 6.500 | 968002 | 134.6 |
| `microsoft-TypeScript-45713` | `development` | `connected_mechanism` | Workspace | 0.300 | 0.214 | 0.446 | 4/4 | 0/4 | 2.500 | 108377 | 261.3 |
|  |  |  | Codex | 0.700 | 0.500 | 0.786 | 4/4 | 0/4 | 5.500 | 310299 | 127.8 |
| `microsoft-TypeScript-46770` | `development` | `connected_mechanism` | Workspace | 0.200 | 1.000 | 0.438 | 4/4 | 4/4 | 2.750 | 124925 | 326.2 |
|  |  |  | Codex | 0.200 | 1.000 | 0.343 | 4/4 | 4/4 | 5.250 | 646619 | 181.3 |
| `microsoft-TypeScript-52695` | `development` | `connected_mechanism` | Workspace | 0.200 | 0.333 | 0.416 | 4/4 | 0/4 | 3.000 | 127062 | 314.8 |
|  |  |  | Codex | 0.200 | 0.333 | 0.287 | 4/4 | 0/4 | 4.500 | 315889 | 140.7 |
| `pandas-dev-pandas-10068` | `development` | `localized_implementation` | Workspace | 0.200 | 1.000 | 0.475 | 4/4 | 4/4 | 4.500 | 95499 | 207.9 |
|  |  |  | Codex | 0.200 | 1.000 | 0.501 | 4/4 | 4/4 | 6.000 | 278654 | 131.5 |
| `pandas-dev-pandas-10150` | `final` | `connected_mechanism` | Workspace | 0.350 | 0.875 | 0.709 | 4/4 | 3/4 | 3.750 | 95908 | 204.8 |
|  |  |  | Codex | 0.400 | 1.000 | 0.510 | 4/4 | 4/4 | 4.500 | 262136 | 123.8 |
| `pandas-dev-pandas-14942` | `development` | `connected_mechanism` | Workspace | 0.400 | 0.333 | 0.463 | 4/4 | 0/4 | 3.750 | 129212 | 240.7 |
|  |  |  | Codex | 0.450 | 0.375 | 0.597 | 4/4 | 0/4 | 6.000 | 487512 | 164.7 |
| `pandas-dev-pandas-16499` | `development` | `localized_implementation` | Workspace | 0.200 | 1.000 | 1.000 | 4/4 | 4/4 | 1.000 | 88571 | 184.4 |
|  |  |  | Codex | 0.200 | 1.000 | 0.631 | 4/4 | 4/4 | 2.500 | 91718 | 81.5 |
| `pandas-dev-pandas-16764` | `development` | `broad_cross_cutting` | Workspace | 0.050 | 0.015 | 0.042 | 1/4 | 0/4 | 1.750 | 84468 | 221.4 |
|  |  |  | Codex | 0.150 | 0.044 | 0.106 | 4/4 | 0/4 | 18.500 | 287425 | 134.8 |
| `pandas-dev-pandas-22698` | `development` | `localized_implementation` | Workspace | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 2.750 | 97283 | 225.5 |
|  |  |  | Codex | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 4.000 | 180673 | 113.9 |
| `pandas-dev-pandas-22872` | `development` | `localized_declarative` | Workspace | 0.000 | 0.000 | 0.040 | 0/4 | 0/4 | 1.000 | 100792 | 234.7 |
|  |  |  | Codex | 0.000 | 0.000 | 0.475 | 0/4 | 0/4 | 8.000 | 136366 | 121.3 |
| `pandas-dev-pandas-25183` | `development` | `localized_implementation` | Workspace | 0.000 | 0.000 | 0.099 | 0/4 | 0/4 | 2.250 | 125116 | 257.5 |
|  |  |  | Codex | 0.200 | 1.000 | 0.363 | 4/4 | 4/4 | 6.750 | 418598 | 152.8 |
| `pandas-dev-pandas-32289` | `development` | `localized_implementation` | Workspace | 0.000 | 0.000 | 0.159 | 0/4 | 0/4 | 1.000 | 62958 | 176.6 |
|  |  |  | Codex | 0.200 | 1.000 | 0.580 | 4/4 | 4/4 | 4.500 | 254060 | 119.2 |
| `pandas-dev-pandas-35925` | `development` | `broad_cross_cutting` | Workspace | 0.200 | 0.077 | 0.339 | 4/4 | 0/4 | 1.000 | 42513 | 120.9 |
|  |  |  | Codex | 0.400 | 0.154 | 0.539 | 4/4 | 0/4 | 4.750 | 86356 | 76.4 |
| `pandas-dev-pandas-36617` | `development` | `localized_declarative` | Workspace | 0.150 | 0.750 | 0.399 | 3/4 | 3/4 | 1.500 | 74026 | 188.0 |
|  |  |  | Codex | 0.200 | 1.000 | 0.695 | 4/4 | 4/4 | 13.750 | 307547 | 169.2 |
| `pandas-dev-pandas-4542` | `development` | `connected_mechanism` | Workspace | 0.400 | 0.667 | 0.650 | 4/4 | 0/4 | 2.750 | 103909 | 204.7 |
|  |  |  | Codex | 0.400 | 0.667 | 0.665 | 4/4 | 0/4 | 7.250 | 217524 | 115.6 |
| `vuejs-vue-10004` | `development` | `localized_implementation` | Workspace | 0.000 | 0.000 | 0.056 | 0/4 | 0/4 | 7.000 | 132152 | 252.8 |
|  |  |  | Codex | 0.000 | 0.000 | 0.000 | 4/4 | 4/4 | 13.500 | 441284 | 157.8 |
| `vuejs-vue-10519` | `development` | `localized_implementation` | Workspace | 0.200 | 1.000 | 0.521 | 4/4 | 4/4 | 3.000 | 77737 | 203.8 |
|  |  |  | Codex | 0.200 | 1.000 | 0.803 | 4/4 | 4/4 | 5.750 | 198564 | 98.0 |
| `vuejs-vue-10803` | `development` | `localized_implementation` | Workspace | 0.200 | 1.000 | 1.000 | 4/4 | 4/4 | 2.750 | 79862 | 201.2 |
|  |  |  | Codex | 0.200 | 1.000 | 0.562 | 4/4 | 4/4 | 5.750 | 304026 | 123.0 |
| `vuejs-vue-11718` | `development` | `connected_mechanism` | Workspace | 0.300 | 0.500 | 0.543 | 3/4 | 0/4 | 2.250 | 58299 | 177.0 |
|  |  |  | Codex | 0.400 | 0.667 | 0.765 | 4/4 | 0/4 | 5.000 | 138336 | 92.3 |
| `vuejs-vue-11782` | `final` | `localized_declarative` | Workspace | 0.050 | 0.250 | 0.250 | 1/4 | 1/4 | 3.250 | 71765 | 202.9 |
|  |  |  | Codex | 0.200 | 1.000 | 1.000 | 4/4 | 4/4 | 7.250 | 145754 | 93.9 |
| `vuejs-vue-13052` | `development` | `localized_declarative` | Workspace | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 1.250 | 65717 | 178.9 |
|  |  |  | Codex | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 2.250 | 78695 | 70.5 |
| `vuejs-vue-5884` | `development` | `localized_implementation` | Workspace | 0.150 | 0.750 | 0.461 | 4/4 | 4/4 | 4.750 | 99086 | 219.5 |
|  |  |  | Codex | 0.200 | 1.000 | 0.521 | 4/4 | 4/4 | 6.750 | 216048 | 102.4 |
| `vuejs-vue-6097` | `final` | `connected_mechanism` | Workspace | 0.300 | 0.750 | 0.648 | 4/4 | 2/4 | 4.750 | 100008 | 223.9 |
|  |  |  | Codex | 0.400 | 1.000 | 0.724 | 4/4 | 4/4 | 6.500 | 118720 | 88.4 |
| `vuejs-vue-6301` | `development` | `localized_declarative` | Workspace | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 3.750 | 81375 | 183.0 |
|  |  |  | Codex | 0.150 | 0.068 | 0.112 | 4/4 | 0/4 | 8.500 | 139554 | 107.6 |
| `vuejs-vue-8528` | `development` | `localized_implementation` | Workspace | 0.200 | 1.000 | 0.783 | 4/4 | 4/4 | 2.000 | 65312 | 174.8 |
|  |  |  | Codex | 0.200 | 1.000 | 1.000 | 4/4 | 4/4 | 2.250 | 81530 | 76.0 |
| `vuejs-vue-9042` | `development` | `localized_implementation` | Workspace | 0.200 | 1.000 | 0.497 | 4/4 | 4/4 | 5.500 | 134786 | 256.7 |
|  |  |  | Codex | 0.200 | 1.000 | 0.352 | 4/4 | 4/4 | 9.500 | 418258 | 157.9 |
| `vuejs-vue-9842` | `final` | `localized_implementation` | Workspace | 0.200 | 1.000 | 0.474 | 4/4 | 4/4 | 5.500 | 119941 | 240.3 |
|  |  |  | Codex | 0.200 | 1.000 | 0.723 | 4/4 | 4/4 | 7.250 | 382230 | 106.2 |

## Run inventory

The JSON companion contains normalized ranked files, Oracle overlap, all metric values, and token components for every row.

| Case | System | Rep | Run | Coverage | Sufficient | Evidence | Files | Flow tokens | Seconds |
| --- | --- | ---: | --- | --- | --- | ---: | ---: | ---: | ---: |
| `microsoft-TypeScript-10020` | codex | 1 | `run-20260902T133446Z` | `strong` | true | 10 | 5 | 166157 | 99.0 |
| `microsoft-TypeScript-10020` | codex | 2 | `run-20260902T133625Z` | `strong` | true | 10 | 5 | 114038 | 79.5 |
| `microsoft-TypeScript-10020` | codex | 3 | `run-20260902T133744Z` | `strong` | true | 13 | 6 | 217318 | 101.5 |
| `microsoft-TypeScript-10020` | codex | 4 | `run-20260902T133926Z` | `strong` | true | 11 | 5 | 317976 | 113.1 |
| `microsoft-TypeScript-10020` | workspace | 1 | `run-20260902T045151Z` | `partial` | false | 9 | 4 | 105662 | 258.4 |
| `microsoft-TypeScript-10020` | workspace | 2 | `run-20260902T045610Z` | `partial` | false | 5 | 2 | 116482 | 254.3 |
| `microsoft-TypeScript-10020` | workspace | 3 | `run-20260902T050023Z` | `partial` | false | 7 | 3 | 104348 | 236.7 |
| `microsoft-TypeScript-10020` | workspace | 4 | `run-20260902T050604Z` | `partial` | false | 9 | 3 | 108006 | 253.6 |
| `microsoft-TypeScript-10041` | codex | 1 | `run-20260902T134119Z` | `strong` | true | 10 | 2 | 868889 | 207.3 |
| `microsoft-TypeScript-10041` | codex | 2 | `run-20260902T134446Z` | `strong` | true | 15 | 4 | 943558 | 203.1 |
| `microsoft-TypeScript-10041` | codex | 3 | `run-20260902T134809Z` | `strong` | true | 13 | 5 | 807349 | 197.0 |
| `microsoft-TypeScript-10041` | codex | 4 | `run-20260902T135126Z` | `strong` | true | 14 | 5 | 776853 | 189.9 |
| `microsoft-TypeScript-10041` | workspace | 1 | `run-20260902T051018Z` | `partial` | false | 1 | 1 | 76445 | 484.4 |
| `microsoft-TypeScript-10041` | workspace | 2 | `run-20260902T051822Z` | `partial` | false | 3 | 2 | 80865 | 225.4 |
| `microsoft-TypeScript-10041` | workspace | 3 | `run-20260902T052207Z` | `partial` | false | 2 | 1 | 71910 | 203.3 |
| `microsoft-TypeScript-10041` | workspace | 4 | `run-20260902T052530Z` | `partial` | false | 3 | 3 | 78711 | 201.5 |
| `microsoft-TypeScript-10473` | codex | 1 | `run-20260902T135436Z` | `strong` | true | 12 | 4 | 116046 | 126.3 |
| `microsoft-TypeScript-10473` | codex | 2 | `run-20260902T135642Z` | `strong` | true | 10 | 4 | 404065 | 123.6 |
| `microsoft-TypeScript-10473` | codex | 3 | `run-20260902T135846Z` | `strong` | true | 13 | 6 | 130282 | 104.6 |
| `microsoft-TypeScript-10473` | codex | 4 | `run-20260902T140031Z` | `strong` | true | 9 | 4 | 248024 | 106.7 |
| `microsoft-TypeScript-10473` | workspace | 1 | `run-20260902T052852Z` | `partial` | false | 9 | 3 | 110147 | 423.9 |
| `microsoft-TypeScript-10473` | workspace | 2 | `run-20260902T053556Z` | `partial` | false | 8 | 3 | 109464 | 227.3 |
| `microsoft-TypeScript-10473` | workspace | 3 | `run-20260902T053943Z` | `partial` | false | 6 | 3 | 104498 | 222.1 |
| `microsoft-TypeScript-10473` | workspace | 4 | `run-20260902T054325Z` | `partial` | false | 8 | 3 | 119336 | 251.6 |
| `microsoft-TypeScript-16278` | codex | 1 | `run-20260902T140217Z` | `strong` | true | 10 | 6 | 230946 | 133.8 |
| `microsoft-TypeScript-16278` | codex | 2 | `run-20260902T140431Z` | `strong` | true | 15 | 7 | 213036 | 127.3 |
| `microsoft-TypeScript-16278` | codex | 3 | `run-20260902T140638Z` | `strong` | true | 13 | 6 | 178951 | 121.6 |
| `microsoft-TypeScript-16278` | codex | 4 | `run-20260902T140840Z` | `strong` | true | 14 | 6 | 179573 | 97.3 |
| `microsoft-TypeScript-16278` | workspace | 1 | `run-20260902T054834Z` | `partial` | false | 14 | 4 | 114893 | 552.7 |
| `microsoft-TypeScript-16278` | workspace | 2 | `run-20260902T061222Z` | `partial` | false | 13 | 4 | 115333 | 254.5 |
| `microsoft-TypeScript-16278` | workspace | 3 | `run-20260902T061637Z` | `partial` | false | 13 | 7 | 132601 | 267.7 |
| `microsoft-TypeScript-16278` | workspace | 4 | `run-20260902T062104Z` | `partial` | false | 14 | 5 | 122529 | 229.6 |
| `microsoft-TypeScript-19074` | codex | 1 | `run-20260902T141017Z` | `strong` | true | 9 | 8 | 107805 | 103.5 |
| `microsoft-TypeScript-19074` | codex | 2 | `run-20260902T141201Z` | `strong` | true | 7 | 7 | 46986 | 73.9 |
| `microsoft-TypeScript-19074` | codex | 3 | `run-20260902T141315Z` | `strong` | true | 7 | 7 | 59783 | 83.9 |
| `microsoft-TypeScript-19074` | codex | 4 | `run-20260902T141439Z` | `strong` | true | 9 | 7 | 78333 | 95.1 |
| `microsoft-TypeScript-19074` | workspace | 1 | `run-20260902T055724Z` | `partial` | false | 3 | 1 | 89067 | 287.7 |
| `microsoft-TypeScript-19074` | workspace | 2 | `run-20260902T060211Z` | `partial` | false | 1 | 1 | 79475 | 246.1 |
| `microsoft-TypeScript-19074` | workspace | 3 | `run-20260902T060617Z` | `partial` | false | 1 | 1 | 57329 | 206.9 |
| `microsoft-TypeScript-19074` | workspace | 4 | `run-20260902T061059Z` | `partial` | false | 2 | 2 | 76157 | 229.6 |
| `microsoft-TypeScript-24625` | codex | 1 | `run-20260902T141614Z` | `strong` | true | 10 | 5 | 189145 | 137.5 |
| `microsoft-TypeScript-24625` | codex | 2 | `run-20260902T141831Z` | `strong` | true | 10 | 5 | 166367 | 111.2 |
| `microsoft-TypeScript-24625` | codex | 3 | `run-20260902T142022Z` | `strong` | true | 10 | 3 | 239761 | 147.3 |
| `microsoft-TypeScript-24625` | codex | 4 | `run-20260902T142250Z` | `strong` | true | 11 | 6 | 105127 | 97.5 |
| `microsoft-TypeScript-24625` | workspace | 1 | `run-20260902T062454Z` | `partial` | false | 6 | 2 | 99261 | 309.6 |
| `microsoft-TypeScript-24625` | workspace | 2 | `run-20260902T063004Z` | `partial` | false | 6 | 4 | 113447 | 209.1 |
| `microsoft-TypeScript-24625` | workspace | 3 | `run-20260902T063333Z` | `partial` | false | 5 | 2 | 90658 | 216.9 |
| `microsoft-TypeScript-24625` | workspace | 4 | `run-20260902T063710Z` | `partial` | false | 4 | 3 | 103451 | 222.3 |
| `microsoft-TypeScript-2953` | codex | 1 | `run-20260902T142427Z` | `strong` | true | 8 | 6 | 241545 | 180.8 |
| `microsoft-TypeScript-2953` | codex | 2 | `run-20260902T142728Z` | `strong` | true | 8 | 5 | 353710 | 162.9 |
| `microsoft-TypeScript-2953` | codex | 3 | `run-20260902T143011Z` | `strong` | true | 10 | 9 | 333006 | 136.6 |
| `microsoft-TypeScript-2953` | codex | 4 | `run-20260902T143228Z` | `strong` | true | 9 | 7 | 263635 | 130.1 |
| `microsoft-TypeScript-2953` | workspace | 1 | `run-20260902T061916Z` | `partial` | false | 2 | 1 | 55916 | 160.0 |
| `microsoft-TypeScript-2953` | workspace | 2 | `run-20260902T062156Z` | `partial` | false | 3 | 1 | 74834 | 180.6 |
| `microsoft-TypeScript-2953` | workspace | 3 | `run-20260902T062456Z` | `partial` | false | 1 | 1 | 60806 | 155.1 |
| `microsoft-TypeScript-2953` | workspace | 4 | `run-20260902T062731Z` | `partial` | false | 3 | 2 | 64437 | 167.1 |
| `microsoft-TypeScript-35468` | codex | 1 | `run-20260902T132352Z` | `strong` | true | 21 | 6 | 1136609 | 0.0 |
| `microsoft-TypeScript-35468` | codex | 2 | `run-20260902T143438Z` | `strong` | true | 26 | 8 | 735124 | 178.7 |
| `microsoft-TypeScript-35468` | codex | 3 | `run-20260902T143736Z` | `strong` | true | 20 | 6 | 649424 | 164.2 |
| `microsoft-TypeScript-35468` | codex | 4 | `run-20260902T144021Z` | `strong` | true | 12 | 6 | 1350852 | 195.4 |
| `microsoft-TypeScript-35468` | workspace | 1 | `run-20260902T064052Z` | `partial` | false | 14 | 5 | 135996 | 371.7 |
| `microsoft-TypeScript-35468` | workspace | 2 | `run-20260902T064704Z` | `partial` | false | 10 | 5 | 120869 | 259.3 |
| `microsoft-TypeScript-35468` | workspace | 3 | `run-20260902T065123Z` | `partial` | false | 10 | 2 | 130111 | 254.6 |
| `microsoft-TypeScript-35468` | workspace | 4 | `run-20260902T065537Z` | `partial` | false | 14 | 7 | 134366 | 295.3 |
| `microsoft-TypeScript-45713` | codex | 1 | `run-20260902T144336Z` | `strong` | true | 12 | 6 | 346975 | 143.1 |
| `microsoft-TypeScript-45713` | codex | 2 | `run-20260902T144559Z` | `strong` | true | 8 | 5 | 382177 | 131.3 |
| `microsoft-TypeScript-45713` | codex | 3 | `run-20260902T144810Z` | `strong` | true | 12 | 6 | 332477 | 133.2 |
| `microsoft-TypeScript-45713` | codex | 4 | `run-20260902T145024Z` | `strong` | true | 10 | 5 | 179567 | 103.6 |
| `microsoft-TypeScript-45713` | workspace | 1 | `run-20260902T063019Z` | `partial` | false | 5 | 2 | 104432 | 334.5 |
| `microsoft-TypeScript-45713` | workspace | 2 | `run-20260902T063553Z` | `partial` | false | 6 | 2 | 109488 | 235.0 |
| `microsoft-TypeScript-45713` | workspace | 3 | `run-20260902T063948Z` | `partial` | false | 7 | 4 | 105211 | 219.7 |
| `microsoft-TypeScript-45713` | workspace | 4 | `run-20260902T064328Z` | `partial` | false | 6 | 2 | 114376 | 256.1 |
| `microsoft-TypeScript-46770` | codex | 1 | `run-20260902T145207Z` | `strong` | true | 16 | 5 | 758315 | 209.1 |
| `microsoft-TypeScript-46770` | codex | 2 | `run-20260902T145537Z` | `strong` | true | 23 | 5 | 578148 | 165.9 |
| `microsoft-TypeScript-46770` | codex | 3 | `run-20260902T145822Z` | `strong` | true | 15 | 4 | 583659 | 159.3 |
| `microsoft-TypeScript-46770` | codex | 4 | `run-20260902T150102Z` | `strong` | true | 20 | 7 | 666353 | 190.8 |
| `microsoft-TypeScript-46770` | workspace | 1 | `run-20260902T070033Z` | `partial` | false | 7 | 3 | 133259 | 444.4 |
| `microsoft-TypeScript-46770` | workspace | 2 | `run-20260902T070757Z` | `partial` | false | 10 | 3 | 123963 | 323.1 |
| `microsoft-TypeScript-46770` | workspace | 3 | `run-20260902T071320Z` | `partial` | false | 7 | 1 | 118312 | 270.3 |
| `microsoft-TypeScript-46770` | workspace | 4 | `run-20260902T071750Z` | `partial` | false | 10 | 4 | 124166 | 267.2 |
| `microsoft-TypeScript-52695` | codex | 1 | `run-20260902T150412Z` | `strong` | true | 15 | 4 | 358286 | 149.4 |
| `microsoft-TypeScript-52695` | codex | 2 | `run-20260902T150642Z` | `strong` | true | 12 | 5 | 367539 | 127.7 |
| `microsoft-TypeScript-52695` | codex | 3 | `run-20260902T150850Z` | `strong` | true | 17 | 5 | 308568 | 151.4 |
| `microsoft-TypeScript-52695` | codex | 4 | `run-20260902T151121Z` | `strong` | true | 14 | 4 | 229162 | 134.0 |
| `microsoft-TypeScript-52695` | workspace | 1 | `run-20260902T064744Z` | `partial` | false | 7 | 3 | 125342 | 411.9 |
| `microsoft-TypeScript-52695` | workspace | 2 | `run-20260902T065436Z` | `partial` | false | 8 | 2 | 118981 | 272.7 |
| `microsoft-TypeScript-52695` | workspace | 3 | `run-20260902T070353Z` | `partial` | false | 9 | 4 | 121797 | 289.7 |
| `microsoft-TypeScript-52695` | workspace | 4 | `run-20260902T071628Z` | `partial` | false | 11 | 3 | 142129 | 284.9 |
| `pandas-dev-pandas-10068` | codex | 1 | `run-20260902T151336Z` | `strong` | true | 12 | 6 | 322678 | 126.5 |
| `pandas-dev-pandas-10068` | codex | 2 | `run-20260902T151542Z` | `strong` | true | 11 | 7 | 333192 | 153.1 |
| `pandas-dev-pandas-10068` | codex | 3 | `run-20260902T151815Z` | `strong` | true | 10 | 5 | 209269 | 128.9 |
| `pandas-dev-pandas-10068` | codex | 4 | `run-20260902T152024Z` | `strong` | true | 9 | 6 | 249476 | 117.7 |
| `pandas-dev-pandas-10068` | workspace | 1 | `run-20260902T072929Z` | `partial` | false | 5 | 4 | 78239 | 183.5 |
| `pandas-dev-pandas-10068` | workspace | 2 | `run-20260902T074521Z` | `partial` | false | 8 | 4 | 97066 | 202.4 |
| `pandas-dev-pandas-10068` | workspace | 3 | `run-20260902T074843Z` | `partial` | false | 9 | 5 | 119475 | 238.4 |
| `pandas-dev-pandas-10068` | workspace | 4 | `run-20260902T075242Z` | `partial` | false | 6 | 5 | 87215 | 207.1 |
| `pandas-dev-pandas-10150` | codex | 1 | `run-20260902T152222Z` | `strong` | true | 8 | 4 | 174091 | 113.0 |
| `pandas-dev-pandas-10150` | codex | 2 | `run-20260902T152415Z` | `strong` | true | 11 | 5 | 429097 | 151.3 |
| `pandas-dev-pandas-10150` | codex | 3 | `run-20260902T152646Z` | `strong` | true | 8 | 5 | 136337 | 104.8 |
| `pandas-dev-pandas-10150` | codex | 4 | `run-20260902T152831Z` | `strong` | true | 9 | 4 | 309017 | 126.2 |
| `pandas-dev-pandas-10150` | workspace | 1 | `run-20260902T072114Z` | `partial` | false | 4 | 4 | 112721 | 226.6 |
| `pandas-dev-pandas-10150` | workspace | 2 | `run-20260902T072500Z` | `partial` | false | 4 | 4 | 101278 | 222.0 |
| `pandas-dev-pandas-10150` | workspace | 3 | `run-20260902T072842Z` | `partial` | false | 4 | 4 | 90388 | 193.7 |
| `pandas-dev-pandas-10150` | workspace | 4 | `run-20260902T073156Z` | `partial` | false | 3 | 3 | 79247 | 177.0 |
| `pandas-dev-pandas-14942` | codex | 1 | `run-20260902T153037Z` | `strong` | true | 11 | 4 | 423592 | 158.6 |
| `pandas-dev-pandas-14942` | codex | 2 | `run-20260902T153316Z` | `strong` | true | 13 | 8 | 542912 | 169.6 |
| `pandas-dev-pandas-14942` | codex | 3 | `run-20260902T153605Z` | `strong` | true | 16 | 7 | 568658 | 190.4 |
| `pandas-dev-pandas-14942` | codex | 4 | `run-20260902T153916Z` | `strong` | true | 11 | 5 | 414884 | 140.1 |
| `pandas-dev-pandas-14942` | workspace | 1 | `run-20260902T080000Z` | `partial` | false | 8 | 3 | 130285 | 246.6 |
| `pandas-dev-pandas-14942` | workspace | 2 | `run-20260902T081246Z` | `partial` | false | 9 | 4 | 127754 | 230.3 |
| `pandas-dev-pandas-14942` | workspace | 3 | `run-20260902T081637Z` | `partial` | false | 7 | 4 | 147830 | 250.9 |
| `pandas-dev-pandas-14942` | workspace | 4 | `run-20260902T082047Z` | `partial` | false | 5 | 4 | 110980 | 234.9 |
| `pandas-dev-pandas-16499` | codex | 1 | `run-20260902T154136Z` | `strong` | true | 6 | 2 | 83344 | 73.8 |
| `pandas-dev-pandas-16499` | codex | 2 | `run-20260902T154250Z` | `strong` | true | 7 | 4 | 107172 | 86.7 |
| `pandas-dev-pandas-16499` | codex | 3 | `run-20260902T154416Z` | `strong` | true | 5 | 2 | 74213 | 70.1 |
| `pandas-dev-pandas-16499` | codex | 4 | `run-20260902T154527Z` | `strong` | true | 7 | 2 | 102141 | 95.2 |
| `pandas-dev-pandas-16499` | workspace | 1 | `run-20260902T073453Z` | `partial` | false | 3 | 1 | 81258 | 172.7 |
| `pandas-dev-pandas-16499` | workspace | 2 | `run-20260902T073745Z` | `partial` | false | 3 | 1 | 102037 | 215.0 |
| `pandas-dev-pandas-16499` | workspace | 3 | `run-20260902T074121Z` | `partial` | false | 3 | 1 | 78502 | 154.5 |
| `pandas-dev-pandas-16499` | workspace | 4 | `run-20260902T074355Z` | `partial` | false | 3 | 1 | 92486 | 195.4 |
| `pandas-dev-pandas-16764` | codex | 1 | `run-20260902T154702Z` | `strong` | true | 33 | 32 | 160180 | 130.4 |
| `pandas-dev-pandas-16764` | codex | 2 | `run-20260902T154912Z` | `strong` | true | 21 | 19 | 415519 | 138.9 |
| `pandas-dev-pandas-16764` | codex | 3 | `run-20260902T155131Z` | `strong` | true | 22 | 14 | 252565 | 132.7 |
| `pandas-dev-pandas-16764` | codex | 4 | `run-20260902T155344Z` | `strong` | true | 15 | 9 | 321437 | 137.1 |
| `pandas-dev-pandas-16764` | workspace | 1 | `run-20260902T082442Z` | `partial` | false | 4 | 1 | 73630 | 212.1 |
| `pandas-dev-pandas-16764` | workspace | 2 | `run-20260902T082814Z` | `partial` | false | 6 | 3 | 88581 | 221.9 |
| `pandas-dev-pandas-16764` | workspace | 3 | `run-20260902T083156Z` | `partial` | false | 2 | 1 | 91398 | 226.9 |
| `pandas-dev-pandas-16764` | workspace | 4 | `run-20260902T083543Z` | `partial` | false | 2 | 2 | 84265 | 224.9 |
| `pandas-dev-pandas-22698` | codex | 1 | `run-20260902T155601Z` | `strong` | true | 8 | 4 | 209424 | 113.0 |
| `pandas-dev-pandas-22698` | codex | 2 | `run-20260902T155754Z` | `strong` | true | 8 | 5 | 192832 | 126.6 |
| `pandas-dev-pandas-22698` | codex | 3 | `run-20260902T160001Z` | `strong` | true | 6 | 4 | 183500 | 116.1 |
| `pandas-dev-pandas-22698` | codex | 4 | `run-20260902T160157Z` | `strong` | true | 4 | 3 | 136936 | 99.9 |
| `pandas-dev-pandas-22698` | workspace | 1 | `run-20260902T074710Z` | `partial` | false | 5 | 3 | 93395 | 219.5 |
| `pandas-dev-pandas-22698` | workspace | 2 | `run-20260902T075050Z` | `partial` | false | 3 | 2 | 100113 | 208.5 |
| `pandas-dev-pandas-22698` | workspace | 3 | `run-20260902T075419Z` | `partial` | false | 5 | 4 | 109879 | 250.1 |
| `pandas-dev-pandas-22698` | workspace | 4 | `run-20260902T075829Z` | `partial` | false | 4 | 2 | 85745 | 224.0 |
| `pandas-dev-pandas-22872` | codex | 1 | `run-20260902T160337Z` | `strong` | true | 17 | 8 | 161389 | 135.4 |
| `pandas-dev-pandas-22872` | codex | 2 | `run-20260902T160553Z` | `strong` | true | 18 | 8 | 72989 | 104.6 |
| `pandas-dev-pandas-22872` | codex | 3 | `run-20260902T160737Z` | `strong` | true | 16 | 8 | 237646 | 141.7 |
| `pandas-dev-pandas-22872` | codex | 4 | `run-20260902T160958Z` | `strong` | true | 17 | 8 | 73441 | 103.4 |
| `pandas-dev-pandas-22872` | workspace | 1 | `run-20260902T083928Z` | `partial` | false | 3 | 3 | 119458 | 245.9 |
| `pandas-dev-pandas-22872` | workspace | 2 | `run-20260902T084334Z` | `missing` | false | 0 | 0 | 96226 | 251.0 |
| `pandas-dev-pandas-22872` | workspace | 3 | `run-20260902T084745Z` | `partial` | false | 1 | 1 | 104800 | 257.3 |
| `pandas-dev-pandas-22872` | workspace | 4 | `run-20260902T085202Z` | `missing` | false | 0 | 0 | 82683 | 184.8 |
| `pandas-dev-pandas-25183` | codex | 1 | `run-20260902T161142Z` | `strong` | true | 11 | 6 | 575756 | 162.9 |
| `pandas-dev-pandas-25183` | codex | 2 | `run-20260902T161425Z` | `strong` | true | 12 | 6 | 318868 | 130.1 |
| `pandas-dev-pandas-25183` | codex | 3 | `run-20260902T161634Z` | `strong` | true | 14 | 8 | 360592 | 153.2 |
| `pandas-dev-pandas-25183` | codex | 4 | `run-20260902T161908Z` | `strong` | true | 13 | 7 | 419178 | 164.9 |
| `pandas-dev-pandas-25183` | workspace | 1 | `run-20260902T080213Z` | `partial` | false | 6 | 2 | 142769 | 317.8 |
| `pandas-dev-pandas-25183` | workspace | 2 | `run-20260902T080730Z` | `partial` | false | 5 | 1 | 100663 | 223.7 |
| `pandas-dev-pandas-25183` | workspace | 3 | `run-20260902T081114Z` | `partial` | false | 8 | 3 | 123037 | 240.5 |
| `pandas-dev-pandas-25183` | workspace | 4 | `run-20260902T081514Z` | `partial` | false | 7 | 3 | 133996 | 247.9 |
| `pandas-dev-pandas-32289` | codex | 1 | `run-20260902T162153Z` | `strong` | true | 7 | 5 | 236323 | 115.0 |
| `pandas-dev-pandas-32289` | codex | 2 | `run-20260902T162348Z` | `strong` | true | 9 | 5 | 290837 | 130.5 |
| `pandas-dev-pandas-32289` | codex | 3 | `run-20260902T162558Z` | `strong` | true | 8 | 4 | 272925 | 131.6 |
| `pandas-dev-pandas-32289` | codex | 4 | `run-20260902T162810Z` | `strong` | true | 6 | 4 | 216157 | 99.6 |
| `pandas-dev-pandas-32289` | workspace | 1 | `run-20260902T085507Z` | `missing` | false | 0 | 0 | 71422 | 202.7 |
| `pandas-dev-pandas-32289` | workspace | 2 | `run-20260902T085830Z` | `partial` | false | 2 | 2 | 62268 | 174.4 |
| `pandas-dev-pandas-32289` | workspace | 3 | `run-20260902T090124Z` | `partial` | false | 1 | 1 | 58686 | 171.6 |
| `pandas-dev-pandas-32289` | workspace | 4 | `run-20260902T090416Z` | `partial` | false | 1 | 1 | 59457 | 157.9 |
| `pandas-dev-pandas-35925` | codex | 1 | `run-20260902T162949Z` | `strong` | true | 4 | 3 | 38004 | 63.3 |
| `pandas-dev-pandas-35925` | codex | 2 | `run-20260902T163053Z` | `strong` | true | 7 | 4 | 97447 | 74.1 |
| `pandas-dev-pandas-35925` | codex | 3 | `run-20260902T163207Z` | `strong` | true | 6 | 4 | 77573 | 80.4 |
| `pandas-dev-pandas-35925` | codex | 4 | `run-20260902T163327Z` | `strong` | true | 10 | 8 | 132402 | 87.9 |
| `pandas-dev-pandas-35925` | workspace | 1 | `run-20260902T081923Z` | `partial` | false | 1 | 1 | 46005 | 133.2 |
| `pandas-dev-pandas-35925` | workspace | 2 | `run-20260902T082136Z` | `partial` | false | 1 | 1 | 30244 | 103.4 |
| `pandas-dev-pandas-35925` | workspace | 3 | `run-20260902T082319Z` | `partial` | false | 1 | 1 | 46884 | 144.3 |
| `pandas-dev-pandas-35925` | workspace | 4 | `run-20260902T082543Z` | `partial` | false | 1 | 1 | 46919 | 102.6 |
| `pandas-dev-pandas-36617` | codex | 1 | `run-20260902T163455Z` | `strong` | true | 18 | 14 | 351734 | 172.1 |
| `pandas-dev-pandas-36617` | codex | 2 | `run-20260902T163747Z` | `strong` | true | 16 | 13 | 162822 | 152.8 |
| `pandas-dev-pandas-36617` | codex | 3 | `run-20260902T164020Z` | `strong` | true | 13 | 13 | 262373 | 165.8 |
| `pandas-dev-pandas-36617` | codex | 4 | `run-20260902T164307Z` | `strong` | true | 16 | 15 | 453260 | 186.1 |
| `pandas-dev-pandas-36617` | workspace | 1 | `run-20260902T090812Z` | `partial` | false | 1 | 1 | 67770 | 185.4 |
| `pandas-dev-pandas-36617` | workspace | 2 | `run-20260902T091117Z` | `partial` | false | 3 | 2 | 94357 | 235.0 |
| `pandas-dev-pandas-36617` | workspace | 3 | `run-20260902T091512Z` | `partial` | false | 4 | 2 | 64554 | 178.7 |
| `pandas-dev-pandas-36617` | workspace | 4 | `run-20260902T091811Z` | `partial` | false | 1 | 1 | 69422 | 152.7 |
| `pandas-dev-pandas-4542` | codex | 1 | `run-20260902T164612Z` | `strong` | true | 12 | 6 | 212340 | 110.7 |
| `pandas-dev-pandas-4542` | codex | 2 | `run-20260902T164803Z` | `strong` | true | 16 | 8 | 192508 | 122.8 |
| `pandas-dev-pandas-4542` | codex | 3 | `run-20260902T165006Z` | `strong` | true | 10 | 6 | 222856 | 115.9 |
| `pandas-dev-pandas-4542` | codex | 4 | `run-20260902T165201Z` | `strong` | true | 16 | 9 | 242391 | 112.9 |
| `pandas-dev-pandas-4542` | workspace | 1 | `run-20260902T082726Z` | `partial` | false | 6 | 2 | 52825 | 108.0 |
| `pandas-dev-pandas-4542` | workspace | 2 | `run-20260902T082914Z` | `partial` | false | 6 | 3 | 128922 | 247.8 |
| `pandas-dev-pandas-4542` | workspace | 3 | `run-20260902T083322Z` | `partial` | false | 8 | 4 | 137940 | 265.5 |
| `pandas-dev-pandas-4542` | workspace | 4 | `run-20260902T083747Z` | `partial` | false | 7 | 2 | 95949 | 197.4 |
| `vuejs-vue-10004` | codex | 1 | `run-20260902T165354Z` | `strong` | true | 14 | 11 | 483342 | 140.0 |
| `vuejs-vue-10004` | codex | 2 | `run-20260902T165614Z` | `strong` | true | 20 | 16 | 329703 | 141.6 |
| `vuejs-vue-10004` | codex | 3 | `run-20260902T165836Z` | `strong` | true | 19 | 13 | 431851 | 153.6 |
| `vuejs-vue-10004` | codex | 4 | `run-20260902T170109Z` | `strong` | true | 20 | 14 | 520242 | 195.8 |
| `vuejs-vue-10004` | workspace | 1 | `run-20260902T092201Z` | `partial` | false | 10 | 7 | 135688 | 250.8 |
| `vuejs-vue-10004` | workspace | 2 | `run-20260902T092612Z` | `partial` | false | 10 | 7 | 134299 | 247.4 |
| `vuejs-vue-10004` | workspace | 3 | `run-20260902T093019Z` | `partial` | false | 10 | 7 | 133112 | 256.6 |
| `vuejs-vue-10004` | workspace | 4 | `run-20260902T093436Z` | `partial` | false | 11 | 7 | 125510 | 256.4 |
| `vuejs-vue-10519` | codex | 1 | `run-20260902T170425Z` | `strong` | true | 11 | 6 | 154389 | 88.0 |
| `vuejs-vue-10519` | codex | 2 | `run-20260902T170553Z` | `strong` | true | 10 | 6 | 195516 | 96.1 |
| `vuejs-vue-10519` | codex | 3 | `run-20260902T170729Z` | `strong` | true | 11 | 6 | 237105 | 110.6 |
| `vuejs-vue-10519` | codex | 4 | `run-20260902T170920Z` | `strong` | true | 10 | 5 | 207248 | 97.3 |
| `vuejs-vue-10519` | workspace | 1 | `run-20260902T084105Z` | `partial` | false | 5 | 3 | 87332 | 233.7 |
| `vuejs-vue-10519` | workspace | 2 | `run-20260902T084458Z` | `partial` | false | 5 | 3 | 72056 | 207.5 |
| `vuejs-vue-10519` | workspace | 3 | `run-20260902T084826Z` | `partial` | false | 5 | 3 | 73199 | 187.7 |
| `vuejs-vue-10519` | workspace | 4 | `run-20260902T085134Z` | `partial` | false | 5 | 3 | 78360 | 186.2 |
| `vuejs-vue-10803` | codex | 1 | `run-20260902T171057Z` | `strong` | true | 11 | 5 | 278425 | 111.9 |
| `vuejs-vue-10803` | codex | 2 | `run-20260902T173511Z` | `strong` | true | 13 | 7 | 439410 | 152.9 |
| `vuejs-vue-10803` | codex | 3 | `run-20260902T173744Z` | `strong` | true | 8 | 5 | 281719 | 123.4 |
| `vuejs-vue-10803` | codex | 4 | `run-20260902T174007Z` | `strong` | true | 10 | 6 | 216548 | 103.7 |
| `vuejs-vue-10803` | workspace | 1 | `run-20260902T093853Z` | `partial` | false | 5 | 3 | 82551 | 206.5 |
| `vuejs-vue-10803` | workspace | 2 | `run-20260902T094219Z` | `partial` | false | 3 | 2 | 77675 | 183.4 |
| `vuejs-vue-10803` | workspace | 3 | `run-20260902T094522Z` | `partial` | false | 5 | 3 | 76434 | 196.2 |
| `vuejs-vue-10803` | workspace | 4 | `run-20260902T094838Z` | `partial` | false | 5 | 3 | 82790 | 218.6 |
| `vuejs-vue-11718` | codex | 1 | `run-20260902T174151Z` | `strong` | true | 7 | 5 | 175487 | 99.1 |
| `vuejs-vue-11718` | codex | 2 | `run-20260902T174330Z` | `strong` | true | 9 | 5 | 84899 | 77.1 |
| `vuejs-vue-11718` | codex | 3 | `run-20260902T174447Z` | `strong` | true | 6 | 4 | 87267 | 92.5 |
| `vuejs-vue-11718` | codex | 4 | `run-20260902T174620Z` | `strong` | true | 7 | 6 | 205690 | 100.6 |
| `vuejs-vue-11718` | workspace | 1 | `run-20260902T085440Z` | `partial` | false | 5 | 3 | 66747 | 192.6 |
| `vuejs-vue-11718` | workspace | 2 | `run-20260902T085752Z` | `partial` | false | 4 | 3 | 72170 | 218.2 |
| `vuejs-vue-11718` | workspace | 3 | `run-20260902T090131Z` | `partial` | false | 4 | 3 | 65255 | 197.4 |
| `vuejs-vue-11718` | workspace | 4 | `run-20260902T090448Z` | `missing` | false | 0 | 0 | 29025 | 99.6 |
| `vuejs-vue-11782` | codex | 1 | `run-20260902T174800Z` | `strong` | true | 8 | 7 | 96319 | 80.4 |
| `vuejs-vue-11782` | codex | 2 | `run-20260902T174920Z` | `strong` | true | 8 | 7 | 116833 | 106.8 |
| `vuejs-vue-11782` | codex | 3 | `run-20260902T175107Z` | `strong` | true | 9 | 8 | 213333 | 97.9 |
| `vuejs-vue-11782` | codex | 4 | `run-20260902T175245Z` | `strong` | true | 10 | 7 | 156530 | 90.4 |
| `vuejs-vue-11782` | workspace | 1 | `run-20260902T095217Z` | `partial` | false | 2 | 2 | 65379 | 205.1 |
| `vuejs-vue-11782` | workspace | 2 | `run-20260902T095654Z` | `partial` | false | 6 | 4 | 73344 | 187.4 |
| `vuejs-vue-11782` | workspace | 3 | `run-20260902T100001Z` | `partial` | false | 4 | 3 | 75061 | 225.5 |
| `vuejs-vue-11782` | workspace | 4 | `run-20260902T100347Z` | `partial` | false | 6 | 4 | 73277 | 193.6 |
| `vuejs-vue-13052` | codex | 1 | `run-20260902T175415Z` | `strong` | true | 6 | 3 | 100990 | 65.9 |
| `vuejs-vue-13052` | codex | 2 | `run-20260902T175521Z` | `strong` | true | 6 | 2 | 68712 | 64.4 |
| `vuejs-vue-13052` | codex | 3 | `run-20260902T175626Z` | `strong` | true | 8 | 3 | 95785 | 89.2 |
| `vuejs-vue-13052` | codex | 4 | `run-20260902T175755Z` | `strong` | true | 6 | 1 | 49294 | 62.4 |
| `vuejs-vue-13052` | workspace | 1 | `run-20260902T090628Z` | `partial` | false | 2 | 1 | 62611 | 184.9 |
| `vuejs-vue-13052` | workspace | 2 | `run-20260902T090932Z` | `partial` | false | 1 | 1 | 58651 | 161.3 |
| `vuejs-vue-13052` | workspace | 3 | `run-20260902T091214Z` | `partial` | false | 5 | 2 | 78088 | 195.0 |
| `vuejs-vue-13052` | workspace | 4 | `run-20260902T091529Z` | `partial` | false | 3 | 1 | 63519 | 174.5 |
| `vuejs-vue-5884` | codex | 1 | `run-20260902T175857Z` | `strong` | true | 10 | 6 | 285613 | 109.4 |
| `vuejs-vue-5884` | codex | 2 | `run-20260902T180047Z` | `strong` | true | 10 | 6 | 158912 | 94.1 |
| `vuejs-vue-5884` | codex | 3 | `run-20260902T180221Z` | `strong` | true | 12 | 7 | 129467 | 92.1 |
| `vuejs-vue-5884` | codex | 4 | `run-20260902T180353Z` | `strong` | true | 12 | 8 | 290199 | 114.3 |
| `vuejs-vue-5884` | workspace | 1 | `run-20260902T100700Z` | `partial` | false | 5 | 4 | 90320 | 222.4 |
| `vuejs-vue-5884` | workspace | 2 | `run-20260902T101043Z` | `strong` | true | 7 | 6 | 105793 | 236.9 |
| `vuejs-vue-5884` | workspace | 3 | `run-20260902T101440Z` | `partial` | false | 6 | 6 | 117924 | 228.7 |
| `vuejs-vue-5884` | workspace | 4 | `run-20260902T101829Z` | `partial` | false | 3 | 3 | 82307 | 190.1 |
| `vuejs-vue-6097` | codex | 1 | `run-20260902T180547Z` | `strong` | true | 11 | 6 | 108465 | 94.8 |
| `vuejs-vue-6097` | codex | 2 | `run-20260902T180722Z` | `strong` | true | 9 | 6 | 128130 | 82.9 |
| `vuejs-vue-6097` | codex | 3 | `run-20260902T180845Z` | `strong` | true | 10 | 7 | 97735 | 81.8 |
| `vuejs-vue-6097` | codex | 4 | `run-20260902T181006Z` | `strong` | true | 13 | 7 | 140549 | 94.0 |
| `vuejs-vue-6097` | workspace | 1 | `run-20260902T091823Z` | `partial` | false | 6 | 6 | 102384 | 250.2 |
| `vuejs-vue-6097` | workspace | 2 | `run-20260902T092233Z` | `partial` | false | 6 | 3 | 103600 | 228.7 |
| `vuejs-vue-6097` | workspace | 3 | `run-20260902T092622Z` | `partial` | false | 8 | 6 | 93457 | 209.1 |
| `vuejs-vue-6097` | workspace | 4 | `run-20260902T092951Z` | `partial` | false | 6 | 4 | 100589 | 207.8 |
| `vuejs-vue-6301` | codex | 1 | `run-20260902T181141Z` | `strong` | true | 22 | 11 | 191612 | 109.5 |
| `vuejs-vue-6301` | codex | 2 | `run-20260902T181330Z` | `strong` | true | 12 | 8 | 100190 | 100.4 |
| `vuejs-vue-6301` | codex | 3 | `run-20260902T181511Z` | `strong` | true | 14 | 6 | 148756 | 122.3 |
| `vuejs-vue-6301` | codex | 4 | `run-20260902T181713Z` | `strong` | true | 12 | 9 | 117656 | 98.3 |
| `vuejs-vue-6301` | workspace | 1 | `run-20260902T102139Z` | `partial` | false | 6 | 4 | 80822 | 183.7 |
| `vuejs-vue-6301` | workspace | 2 | `run-20260902T102442Z` | `partial` | false | 6 | 4 | 83874 | 191.4 |
| `vuejs-vue-6301` | workspace | 3 | `run-20260902T103033Z` | `partial` | false | 4 | 3 | 78232 | 170.1 |
| `vuejs-vue-6301` | workspace | 4 | `run-20260902T103323Z` | `partial` | false | 5 | 4 | 82572 | 186.8 |
| `vuejs-vue-8528` | codex | 1 | `run-20260902T181851Z` | `strong` | true | 12 | 6 | 119435 | 101.9 |
| `vuejs-vue-8528` | codex | 2 | `run-20260902T182033Z` | `strong` | true | 4 | 1 | 56479 | 60.2 |
| `vuejs-vue-8528` | codex | 3 | `run-20260902T182133Z` | `strong` | true | 6 | 1 | 63520 | 65.4 |
| `vuejs-vue-8528` | codex | 4 | `run-20260902T182239Z` | `strong` | true | 8 | 1 | 86685 | 76.4 |
| `vuejs-vue-8528` | workspace | 1 | `run-20260902T093319Z` | `partial` | false | 4 | 2 | 68797 | 215.4 |
| `vuejs-vue-8528` | workspace | 2 | `run-20260902T093654Z` | `partial` | false | 3 | 1 | 61749 | 162.3 |
| `vuejs-vue-8528` | workspace | 3 | `run-20260902T093937Z` | `partial` | false | 2 | 2 | 65770 | 160.8 |
| `vuejs-vue-8528` | workspace | 4 | `run-20260902T094218Z` | `partial` | false | 3 | 3 | 64930 | 160.8 |
| `vuejs-vue-9042` | codex | 1 | `run-20260902T182355Z` | `strong` | true | 9 | 7 | 253810 | 139.1 |
| `vuejs-vue-9042` | codex | 2 | `run-20260902T182614Z` | `strong` | true | 10 | 10 | 497959 | 159.2 |
| `vuejs-vue-9042` | codex | 3 | `run-20260902T182854Z` | `strong` | true | 15 | 10 | 443448 | 164.9 |
| `vuejs-vue-9042` | codex | 4 | `run-20260902T183138Z` | `strong` | true | 15 | 11 | 477813 | 168.6 |
| `vuejs-vue-9042` | workspace | 1 | `run-20260902T103630Z` | `partial` | false | 9 | 5 | 143044 | 265.5 |
| `vuejs-vue-9042` | workspace | 2 | `run-20260902T104055Z` | `partial` | false | 7 | 6 | 109787 | 219.1 |
| `vuejs-vue-9042` | workspace | 3 | `run-20260902T104434Z` | `partial` | false | 8 | 5 | 144148 | 268.3 |
| `vuejs-vue-9042` | workspace | 4 | `run-20260902T104903Z` | `partial` | false | 9 | 6 | 142166 | 274.0 |
| `vuejs-vue-9842` | codex | 1 | `run-20260902T183427Z` | `strong` | true | 11 | 7 | 258736 | 113.5 |
| `vuejs-vue-9842` | codex | 2 | `run-20260902T183620Z` | `strong` | true | 11 | 7 | 314510 | 0.0 |
| `vuejs-vue-9842` | codex | 3 | `run-20260902T184607Z` | `strong` | true | 15 | 7 | 507342 | 162.7 |
| `vuejs-vue-9842` | codex | 4 | `run-20260902T184850Z` | `strong` | true | 20 | 8 | 448333 | 148.7 |
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
- Codex ledger: `testing/codeRepoQA/statistics/runs/2026-09-02-codex-efficient-luna-four-runs.json`
- JSON report: `testing/codeRepoQA/statistics/runs/2026-09-02-workspace-vs-codex-four-run-comparison.json`
