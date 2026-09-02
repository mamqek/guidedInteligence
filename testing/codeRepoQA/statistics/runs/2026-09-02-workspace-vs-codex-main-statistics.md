# Workspace vs Codex Luna Efficient — Main Retrieval Statistics

## Status and scope

Workspace retrieval is complete over 35 CodeRepoQA cases: seven issue categories, three repositories, 28 development cases, and seven frozen final-evaluation cases. The Codex campaign is not a valid comparison condition: all 140 executions had repository shell commands rejected by policy, and 134 returned no usable evidence. Its rows are retained below only to audit that failure.

## Conditions

- Workspace: `configs/testing/statistics-workspace.json`, `gpt-5.6-luna`, qualification-first controller, response generation skipped, final evidence selection enabled.
- Codex: `gpt-5.6-luna`, `efficient` prompt profile, frozen campaign ledger `2026-08-26-codex-luna-four-runs.json`.
- Headline selection: the first valid campaign run for every testcase and system; no run was selected or replaced using its score.
- Four-run stability: calculate every run, average four repetitions within each case, then macro-average the 35 case means.
- Twenty-one Workspace attempts exited with code 1 before producing required artifacts. They are excluded and remain auditable in the source ledgers; the ledger does not preserve a precise cause for every attempt.

## Metric note

Files are ranked and deduplicated by repository-relative path. Implementation Oracle files define P@k and R@k. Test/validation and documentation Oracle files receive partial NDCG relevance. Missing ranks are nonrelevant. P@k always uses k as its denominator.

## Headline run inventory and cost

Indexing-token totals for Workspace are unavailable because the reused-index build usage was not provider-logged. They are not estimated. Observed build duration is recovered only from an earlier trace with the same case snapshot and exact Qdrant collection identity. `Flow` is the recorded non-indexing retrieval usage.

Matching build duration was recovered for 32/35 Workspace cases: mean 153.2s, median 34.2s, range 6.4–829.3s. Codex performs direct repository inspection and has no index-build stage.

| Case | Part. | Category | Topology | System | Run | Seconds | Index build seconds | Build source run | Index tokens | Flow | Cached in | Uncached in | Output |
| --- | --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| `microsoft-TypeScript-10020` | `development` | `feature_enhancement` | `connected_mechanism` | codex | `run-20260826T142635Z` | 58.4 | 0.0 | not applicable | 0 | 190909 | 154368 | 35149 | 1392 |
| `microsoft-TypeScript-10020` | `development` | `feature_enhancement` | `connected_mechanism` | workspace | `run-20260902T045151Z` | 258.4 | 525.9 | `run-20260829T202351Z` | unavailable | 105662 | — | — | 18537 |
| `microsoft-TypeScript-10041` | `final` | `compatibility_versioning` | `localized_implementation` | codex | `run-20260826T143004Z` | 56.7 | 0.0 | not applicable | 0 | 167635 | 131072 | 35289 | 1274 |
| `microsoft-TypeScript-10041` | `final` | `compatibility_versioning` | `localized_implementation` | workspace | `run-20260902T051018Z` | 484.4 | 317.9 | `run-20260902T051018Z` | unavailable | 76445 | — | — | 10353 |
| `microsoft-TypeScript-10473` | `final` | `bug_regression` | `connected_mechanism` | codex | `run-20260826T143350Z` | 51.6 | 0.0 | not applicable | 0 | 102883 | 83200 | 18729 | 954 |
| `microsoft-TypeScript-10473` | `final` | `bug_regression` | `connected_mechanism` | workspace | `run-20260902T052852Z` | 423.9 | 212.5 | `run-20260902T052852Z` | unavailable | 110147 | — | — | 17804 |
| `microsoft-TypeScript-16278` | `development` | `api_behavior_design` | `connected_mechanism` | codex | `run-20260826T143724Z` | 63.9 | 0.0 | not applicable | 0 | 192556 | 154368 | 36123 | 2065 |
| `microsoft-TypeScript-16278` | `development` | `api_behavior_design` | `connected_mechanism` | workspace | `run-20260902T054834Z` | 552.7 | 288.1 | `run-20260902T054834Z` | unavailable | 114893 | — | — | 21660 |
| `microsoft-TypeScript-19074` | `final` | `maintenance_refactor` | `connected_mechanism` | codex | `run-20260826T144120Z` | 58.3 | 0.0 | not applicable | 0 | 235477 | 188928 | 44926 | 1623 |
| `microsoft-TypeScript-19074` | `final` | `maintenance_refactor` | `connected_mechanism` | workspace | `run-20260902T055724Z` | 287.7 | unavailable | unavailable | unavailable | 89067 | — | — | 15940 |
| `microsoft-TypeScript-24625` | `development` | `api_behavior_design` | `localized_implementation` | codex | `run-20260826T144441Z` | 56.1 | 0.0 | not applicable | 0 | 124300 | 103680 | 19331 | 1289 |
| `microsoft-TypeScript-24625` | `development` | `api_behavior_design` | `localized_implementation` | workspace | `run-20260902T062454Z` | 309.6 | 327.6 | `run-20260829T235503Z` | unavailable | 99261 | — | — | 15953 |
| `microsoft-TypeScript-2953` | `development` | `bug_regression` | `localized_declarative` | codex | `run-20260826T144827Z` | 69.8 | 0.0 | not applicable | 0 | 174735 | 137984 | 35410 | 1341 |
| `microsoft-TypeScript-2953` | `development` | `bug_regression` | `localized_declarative` | workspace | `run-20260902T061916Z` | 160.0 | 277.0 | `run-20260829T185244Z` | unavailable | 55916 | — | — | 9092 |
| `microsoft-TypeScript-35468` | `development` | `testing_build_tooling` | `connected_mechanism` | codex | `run-20260827T040705Z` | 57.7 | 0.0 | not applicable | 0 | 169984 | 135168 | 33490 | 1326 |
| `microsoft-TypeScript-35468` | `development` | `testing_build_tooling` | `connected_mechanism` | workspace | `run-20260902T064052Z` | 371.7 | 305.9 | `run-20260830T225414Z` | unavailable | 135996 | — | — | 20518 |
| `microsoft-TypeScript-45713` | `development` | `feature_enhancement` | `connected_mechanism` | codex | `run-20260827T041035Z` | 69.0 | 0.0 | not applicable | 0 | 141841 | 109568 | 30131 | 2142 |
| `microsoft-TypeScript-45713` | `development` | `feature_enhancement` | `connected_mechanism` | workspace | `run-20260902T063019Z` | 334.5 | 829.3 | `run-20260829T200407Z` | unavailable | 104432 | — | — | 16087 |
| `microsoft-TypeScript-46770` | `development` | `compatibility_versioning` | `connected_mechanism` | codex | `run-20260827T041447Z` | 54.4 | 0.0 | not applicable | 0 | 151589 | 114944 | 35537 | 1108 |
| `microsoft-TypeScript-46770` | `development` | `compatibility_versioning` | `connected_mechanism` | workspace | `run-20260902T070033Z` | 444.4 | 399.7 | `run-20260829T231718Z` | unavailable | 133259 | — | — | 19793 |
| `microsoft-TypeScript-52695` | `development` | `performance_memory` | `connected_mechanism` | codex | `run-20260827T041835Z` | 54.2 | 0.0 | not applicable | 0 | 150515 | 119808 | 29253 | 1454 |
| `microsoft-TypeScript-52695` | `development` | `performance_memory` | `connected_mechanism` | workspace | `run-20260902T064744Z` | 411.9 | 808.1 | `run-20260829T204456Z` | unavailable | 125342 | — | — | 20754 |
| `pandas-dev-pandas-10068` | `development` | `bug_regression` | `localized_implementation` | codex | `run-20260827T042220Z` | 66.7 | 0.0 | not applicable | 0 | 121099 | 74240 | 44810 | 2049 |
| `pandas-dev-pandas-10068` | `development` | `bug_regression` | `localized_implementation` | workspace | `run-20260902T072929Z` | 183.5 | 28.6 | `run-20260820T005900Z` | unavailable | 78239 | — | — | 13008 |
| `pandas-dev-pandas-10150` | `final` | `api_behavior_design` | `connected_mechanism` | codex | `run-20260827T042633Z` | 64.0 | 0.0 | not applicable | 0 | 142179 | 106752 | 33566 | 1861 |
| `pandas-dev-pandas-10150` | `final` | `api_behavior_design` | `connected_mechanism` | workspace | `run-20260902T072114Z` | 226.6 | 6.4 | `run-20260902T072114Z` | unavailable | 112721 | — | — | 17702 |
| `pandas-dev-pandas-14942` | `development` | `performance_memory` | `connected_mechanism` | codex | `run-20260827T043249Z` | 65.6 | 0.0 | not applicable | 0 | 164470 | 134144 | 28705 | 1621 |
| `pandas-dev-pandas-14942` | `development` | `performance_memory` | `connected_mechanism` | workspace | `run-20260902T080000Z` | 246.6 | 77.8 | `run-20260829T203552Z` | unavailable | 130285 | — | — | 19437 |
| `pandas-dev-pandas-16499` | `development` | `testing_build_tooling` | `localized_implementation` | codex | `run-20260827T043942Z` | 75.6 | 0.0 | not applicable | 0 | 204944 | 176896 | 25842 | 2206 |
| `pandas-dev-pandas-16499` | `development` | `testing_build_tooling` | `localized_implementation` | workspace | `run-20260902T073453Z` | 172.7 | 43.3 | `run-20260823T031156Z` | unavailable | 81258 | — | — | 12323 |
| `pandas-dev-pandas-16764` | `development` | `performance_memory` | `broad_cross_cutting` | codex | `run-20260827T044409Z` | 59.3 | 0.0 | not applicable | 0 | 161117 | 138752 | 20785 | 1580 |
| `pandas-dev-pandas-16764` | `development` | `performance_memory` | `broad_cross_cutting` | workspace | `run-20260902T082442Z` | 212.1 | 47.9 | `run-20260829T204041Z` | unavailable | 73630 | — | — | 15053 |
| `pandas-dev-pandas-22698` | `development` | `compatibility_versioning` | `localized_implementation` | codex | `run-20260827T044804Z` | 59.8 | 0.0 | not applicable | 0 | 153985 | 122880 | 29547 | 1558 |
| `pandas-dev-pandas-22698` | `development` | `compatibility_versioning` | `localized_implementation` | workspace | `run-20260902T074710Z` | 219.5 | 39.8 | `run-20260829T230808Z` | unavailable | 93395 | — | — | 16222 |
| `pandas-dev-pandas-22872` | `development` | `maintenance_refactor` | `localized_declarative` | codex | `run-20260827T045311Z` | 59.1 | 0.0 | not applicable | 0 | 156376 | 125952 | 29168 | 1256 |
| `pandas-dev-pandas-22872` | `development` | `maintenance_refactor` | `localized_declarative` | workspace | `run-20260902T083928Z` | 245.9 | 8.2 | `run-20260902T083928Z` | unavailable | 119458 | — | — | 19797 |
| `pandas-dev-pandas-25183` | `development` | `api_behavior_design` | `localized_implementation` | codex | `run-20260827T045922Z` | 60.7 | 0.0 | not applicable | 0 | 154505 | 122880 | 30210 | 1415 |
| `pandas-dev-pandas-25183` | `development` | `api_behavior_design` | `localized_implementation` | workspace | `run-20260902T080213Z` | 317.8 | 8.9 | `run-20260902T080213Z` | unavailable | 142769 | — | — | 21904 |
| `pandas-dev-pandas-32289` | `development` | `testing_build_tooling` | `localized_implementation` | codex | `run-20260827T050312Z` | 47.4 | 0.0 | not applicable | 0 | 155878 | 123648 | 30886 | 1344 |
| `pandas-dev-pandas-32289` | `development` | `testing_build_tooling` | `localized_implementation` | workspace | `run-20260902T085507Z` | 202.7 | 10.3 | `run-20260902T085507Z` | unavailable | 71422 | — | — | 12432 |
| `pandas-dev-pandas-35925` | `development` | `maintenance_refactor` | `broad_cross_cutting` | codex | `run-20260827T050627Z` | 45.0 | 0.0 | not applicable | 0 | 83844 | 66048 | 16956 | 840 |
| `pandas-dev-pandas-35925` | `development` | `maintenance_refactor` | `broad_cross_cutting` | workspace | `run-20260902T081923Z` | 133.2 | 80.3 | `run-20260829T162616Z` | unavailable | 46005 | — | — | 8251 |
| `pandas-dev-pandas-36617` | `development` | `maintenance_refactor` | `localized_declarative` | codex | `run-20260827T050948Z` | 72.5 | 0.0 | not applicable | 0 | 134562 | 103424 | 29415 | 1723 |
| `pandas-dev-pandas-36617` | `development` | `maintenance_refactor` | `localized_declarative` | workspace | `run-20260902T090812Z` | 185.4 | unavailable | unavailable | unavailable | 67770 | — | — | 10224 |
| `pandas-dev-pandas-4542` | `development` | `feature_enhancement` | `connected_mechanism` | codex | `run-20260827T051413Z` | 44.0 | 0.0 | not applicable | 0 | 123540 | 103424 | 19153 | 963 |
| `pandas-dev-pandas-4542` | `development` | `feature_enhancement` | `connected_mechanism` | workspace | `run-20260902T082726Z` | 108.0 | 25.8 | `run-20260829T202126Z` | unavailable | 52825 | — | — | 7346 |
| `vuejs-vue-10004` | `development` | `performance_memory` | `localized_implementation` | codex | `run-20260827T051726Z` | 62.5 | 0.0 | not applicable | 0 | 170474 | 131840 | 37179 | 1455 |
| `vuejs-vue-10004` | `development` | `performance_memory` | `localized_implementation` | workspace | `run-20260902T092201Z` | 250.8 | unavailable | unavailable | unavailable | 135688 | — | — | 19794 |
| `vuejs-vue-10519` | `development` | `bug_regression` | `localized_implementation` | codex | `run-20260827T052132Z` | 98.6 | 0.0 | not applicable | 0 | 276440 | 238592 | 33874 | 3974 |
| `vuejs-vue-10519` | `development` | `bug_regression` | `localized_implementation` | workspace | `run-20260902T084105Z` | 233.7 | 18.1 | `run-20260829T195841Z` | unavailable | 87332 | — | — | 17550 |
| `vuejs-vue-10803` | `development` | `bug_regression` | `localized_implementation` | codex | `run-20260827T052628Z` | 50.4 | 0.0 | not applicable | 0 | 114756 | 94208 | 19336 | 1212 |
| `vuejs-vue-10803` | `development` | `bug_regression` | `localized_implementation` | workspace | `run-20260902T093853Z` | 206.5 | 24.6 | `run-20260820T010507Z` | unavailable | 82551 | — | — | 14721 |
| `vuejs-vue-11718` | `development` | `testing_build_tooling` | `connected_mechanism` | codex | `run-20260827T053101Z` | 48.3 | 0.0 | not applicable | 0 | 87742 | 69120 | 17626 | 996 |
| `vuejs-vue-11718` | `development` | `testing_build_tooling` | `connected_mechanism` | workspace | `run-20260902T085440Z` | 192.6 | 15.1 | `run-20260902T085440Z` | unavailable | 66747 | — | — | 12642 |
| `vuejs-vue-11782` | `final` | `testing_build_tooling` | `localized_declarative` | codex | `run-20260827T053412Z` | 61.2 | 0.0 | not applicable | 0 | 185108 | 154112 | 29592 | 1404 |
| `vuejs-vue-11782` | `final` | `testing_build_tooling` | `localized_declarative` | workspace | `run-20260902T095217Z` | 205.1 | 12.1 | `run-20260902T095217Z` | unavailable | 65379 | — | — | 12513 |
| `vuejs-vue-13052` | `development` | `compatibility_versioning` | `localized_declarative` | codex | `run-20260827T053820Z` | 70.4 | 0.0 | not applicable | 0 | 173682 | 135936 | 35681 | 2065 |
| `vuejs-vue-13052` | `development` | `compatibility_versioning` | `localized_declarative` | workspace | `run-20260902T090628Z` | 184.9 | 25.2 | `run-20260829T162949Z` | unavailable | 62611 | — | — | 11321 |
| `vuejs-vue-5884` | `development` | `api_behavior_design` | `localized_implementation` | codex | `run-20260827T054153Z` | 53.2 | 0.0 | not applicable | 0 | 167165 | 126720 | 39048 | 1397 |
| `vuejs-vue-5884` | `development` | `api_behavior_design` | `localized_implementation` | workspace | `run-20260902T100700Z` | 222.4 | 15.7 | `run-20260829T234450Z` | unavailable | 90320 | — | — | 15314 |
| `vuejs-vue-6097` | `final` | `feature_enhancement` | `connected_mechanism` | codex | `run-20260827T054518Z` | 138.3 | 0.0 | not applicable | 0 | 603804 | 545280 | 53738 | 4786 |
| `vuejs-vue-6097` | `final` | `feature_enhancement` | `connected_mechanism` | workspace | `run-20260902T091823Z` | 250.2 | 19.3 | `run-20260902T091823Z` | unavailable | 102384 | — | — | 17413 |
| `vuejs-vue-6301` | `development` | `feature_enhancement` | `localized_declarative` | codex | `run-20260827T055110Z` | 44.9 | 0.0 | not applicable | 0 | 145665 | 122624 | 21896 | 1145 |
| `vuejs-vue-6301` | `development` | `feature_enhancement` | `localized_declarative` | workspace | `run-20260902T102139Z` | 183.7 | 39.7 | `run-20260829T200132Z` | unavailable | 80822 | — | — | 15079 |
| `vuejs-vue-8528` | `development` | `maintenance_refactor` | `localized_implementation` | codex | `run-20260827T055426Z` | 63.0 | 0.0 | not applicable | 0 | 114963 | 93440 | 19709 | 1814 |
| `vuejs-vue-8528` | `development` | `maintenance_refactor` | `localized_implementation` | workspace | `run-20260902T093319Z` | 215.4 | 23.4 | `run-20260902T093319Z` | unavailable | 68797 | — | — | 14044 |
| `vuejs-vue-9042` | `development` | `compatibility_versioning` | `localized_implementation` | codex | `run-20260827T055813Z` | 63.6 | 0.0 | not applicable | 0 | 113933 | 94208 | 18668 | 1057 |
| `vuejs-vue-9042` | `development` | `compatibility_versioning` | `localized_implementation` | workspace | `run-20260902T103630Z` | 265.5 | 27.9 | `run-20260829T225442Z` | unavailable | 143044 | — | — | 22965 |
| `vuejs-vue-9842` | `final` | `performance_memory` | `localized_implementation` | codex | `run-20260827T060223Z` | 47.8 | 0.0 | not applicable | 0 | 103214 | 83200 | 19101 | 913 |
| `vuejs-vue-9842` | `final` | `performance_memory` | `localized_implementation` | workspace | `run-20260902T094458Z` | 226.4 | 12.0 | `run-20260902T094458Z` | unavailable | 123346 | — | — | 18410 |

## Descriptive headline metrics — Codex condition invalid

| System | Cases | Runs | P@1 | P@2 | P@5 | P@10 | R@1 | R@2 | R@5 | R@10 | NDCG@1 | NDCG@2 | NDCG@5 | NDCG@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Workspace | 35 | 35 | 0.429 | 0.329 | 0.206 | 0.103 | 0.246 | 0.346 | 0.550 | 0.550 | 0.457 | 0.448 | 0.460 | 0.425 |
| Codex Luna efficient | 35 | 35 | 0.029 | 0.029 | 0.017 | 0.009 | 0.029 | 0.043 | 0.057 | 0.057 | 0.029 | 0.035 | 0.042 | 0.042 |

No Workspace-minus-Codex quality conclusion is valid from these values. The Codex condition must be rerun with working read-only repository inspection.

## Partition breakdown

| Group | System | Cases | P@5 | R@5 | NDCG@5 | Any hit | Full recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `development` | Workspace | 28 | 0.200 | 0.508 | 0.439 | 0.679 | 0.393 |
| `development` | Codex | 28 | 0.007 | 0.036 | 0.030 | 0.036 | 0.036 |
| `final` | Workspace | 7 | 0.229 | 0.714 | 0.544 | 0.714 | 0.714 |
| `final` | Codex | 7 | 0.057 | 0.143 | 0.090 | 0.143 | 0.143 |

## Issue-category breakdown

| Group | System | Cases | P@5 | R@5 | NDCG@5 | Any hit | Full recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `api_behavior_design` | Workspace | 5 | 0.280 | 0.675 | 0.562 | 0.800 | 0.600 |
| `api_behavior_design` | Codex | 5 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| `bug_regression` | Workspace | 5 | 0.200 | 0.800 | 0.533 | 0.800 | 0.800 |
| `bug_regression` | Codex | 5 | 0.040 | 0.200 | 0.165 | 0.200 | 0.200 |
| `compatibility_versioning` | Workspace | 5 | 0.080 | 0.400 | 0.183 | 0.400 | 0.400 |
| `compatibility_versioning` | Codex | 5 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| `feature_enhancement` | Workspace | 5 | 0.280 | 0.490 | 0.468 | 0.800 | 0.200 |
| `feature_enhancement` | Codex | 5 | 0.080 | 0.200 | 0.126 | 0.200 | 0.200 |
| `maintenance_refactor` | Workspace | 5 | 0.120 | 0.415 | 0.453 | 0.600 | 0.400 |
| `maintenance_refactor` | Codex | 5 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| `performance_memory` | Workspace | 5 | 0.160 | 0.333 | 0.299 | 0.600 | 0.200 |
| `performance_memory` | Codex | 5 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| `testing_build_tooling` | Workspace | 5 | 0.320 | 0.733 | 0.723 | 0.800 | 0.600 |
| `testing_build_tooling` | Codex | 5 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |

## Retrieval-topology breakdown

| Group | System | Cases | P@5 | R@5 | NDCG@5 | Any hit | Full recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `broad_cross_cutting` | Workspace | 2 | 0.100 | 0.038 | 0.170 | 0.500 | 0.000 |
| `broad_cross_cutting` | Codex | 2 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| `connected_mechanism` | Workspace | 13 | 0.369 | 0.628 | 0.577 | 0.923 | 0.385 |
| `connected_mechanism` | Codex | 13 | 0.031 | 0.077 | 0.048 | 0.077 | 0.077 |
| `localized_declarative` | Workspace | 6 | 0.067 | 0.333 | 0.295 | 0.333 | 0.333 |
| `localized_declarative` | Codex | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| `localized_implementation` | Workspace | 14 | 0.129 | 0.643 | 0.464 | 0.643 | 0.643 |
| `localized_implementation` | Codex | 14 | 0.014 | 0.071 | 0.059 | 0.071 | 0.071 |

## Repository breakdown

| Group | System | Cases | P@5 | R@5 | NDCG@5 | Any hit | Full recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `microsoft/TypeScript` | Workspace | 11 | 0.273 | 0.499 | 0.425 | 0.727 | 0.364 |
| `microsoft/TypeScript` | Codex | 11 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| `pandas-dev/pandas` | Workspace | 12 | 0.167 | 0.423 | 0.387 | 0.583 | 0.333 |
| `pandas-dev/pandas` | Codex | 12 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| `vuejs/vue` | Workspace | 12 | 0.183 | 0.722 | 0.566 | 0.750 | 0.667 |
| `vuejs/vue` | Codex | 12 | 0.050 | 0.167 | 0.121 | 0.167 | 0.167 |

## Per-case headline results

| Case | System | P@5 | R@5 | NDCG@5 | Files | Oracle hits |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `microsoft-TypeScript-10020` | codex | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `microsoft-TypeScript-10020` | workspace | 0.200 | 0.500 | 0.242 | 4 | 1 |
| `microsoft-TypeScript-10041` | codex | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `microsoft-TypeScript-10041` | workspace | 0.000 | 0.000 | 0.000 | 1 | 0 |
| `microsoft-TypeScript-10473` | codex | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `microsoft-TypeScript-10473` | workspace | 0.400 | 1.000 | 0.629 | 3 | 2 |
| `microsoft-TypeScript-16278` | codex | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `microsoft-TypeScript-16278` | workspace | 0.600 | 0.375 | 0.771 | 4 | 3 |
| `microsoft-TypeScript-19074` | codex | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `microsoft-TypeScript-19074` | workspace | 0.000 | 0.000 | 0.161 | 1 | 0 |
| `microsoft-TypeScript-24625` | codex | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `microsoft-TypeScript-24625` | workspace | 0.200 | 1.000 | 0.606 | 2 | 1 |
| `microsoft-TypeScript-2953` | codex | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `microsoft-TypeScript-2953` | workspace | 0.000 | 0.000 | 0.000 | 1 | 0 |
| `microsoft-TypeScript-35468` | codex | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `microsoft-TypeScript-35468` | workspace | 0.800 | 1.000 | 0.910 | 5 | 4 |
| `microsoft-TypeScript-45713` | codex | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `microsoft-TypeScript-45713` | workspace | 0.400 | 0.286 | 0.553 | 2 | 2 |
| `microsoft-TypeScript-46770` | codex | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `microsoft-TypeScript-46770` | workspace | 0.200 | 1.000 | 0.383 | 3 | 1 |
| `microsoft-TypeScript-52695` | codex | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `microsoft-TypeScript-52695` | workspace | 0.200 | 0.333 | 0.416 | 3 | 1 |
| `pandas-dev-pandas-10068` | codex | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `pandas-dev-pandas-10068` | workspace | 0.200 | 1.000 | 0.516 | 4 | 1 |
| `pandas-dev-pandas-10150` | codex | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `pandas-dev-pandas-10150` | workspace | 0.400 | 1.000 | 0.691 | 4 | 2 |
| `pandas-dev-pandas-14942` | codex | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `pandas-dev-pandas-14942` | workspace | 0.400 | 0.333 | 0.497 | 3 | 2 |
| `pandas-dev-pandas-16499` | codex | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `pandas-dev-pandas-16499` | workspace | 0.200 | 1.000 | 1.000 | 1 | 1 |
| `pandas-dev-pandas-16764` | codex | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `pandas-dev-pandas-16764` | workspace | 0.000 | 0.000 | 0.000 | 1 | 0 |
| `pandas-dev-pandas-22698` | codex | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `pandas-dev-pandas-22698` | workspace | 0.000 | 0.000 | 0.000 | 3 | 0 |
| `pandas-dev-pandas-22872` | codex | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `pandas-dev-pandas-22872` | workspace | 0.000 | 0.000 | 0.161 | 3 | 0 |
| `pandas-dev-pandas-25183` | codex | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `pandas-dev-pandas-25183` | workspace | 0.000 | 0.000 | 0.153 | 2 | 0 |
| `pandas-dev-pandas-32289` | codex | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `pandas-dev-pandas-32289` | workspace | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `pandas-dev-pandas-35925` | codex | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `pandas-dev-pandas-35925` | workspace | 0.200 | 0.077 | 0.339 | 1 | 1 |
| `pandas-dev-pandas-36617` | codex | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `pandas-dev-pandas-36617` | workspace | 0.200 | 1.000 | 0.606 | 1 | 1 |
| `pandas-dev-pandas-4542` | codex | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `pandas-dev-pandas-4542` | workspace | 0.400 | 0.667 | 0.679 | 2 | 2 |
| `vuejs-vue-10004` | codex | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `vuejs-vue-10004` | workspace | 0.000 | 0.000 | 0.119 | 7 | 0 |
| `vuejs-vue-10519` | codex | 0.200 | 1.000 | 0.826 | 1 | 1 |
| `vuejs-vue-10519` | workspace | 0.200 | 1.000 | 0.521 | 3 | 1 |
| `vuejs-vue-10803` | codex | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `vuejs-vue-10803` | workspace | 0.200 | 1.000 | 1.000 | 3 | 1 |
| `vuejs-vue-11718` | codex | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `vuejs-vue-11718` | workspace | 0.400 | 0.667 | 0.704 | 3 | 2 |
| `vuejs-vue-11782` | codex | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `vuejs-vue-11782` | workspace | 0.200 | 1.000 | 1.000 | 2 | 1 |
| `vuejs-vue-13052` | codex | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `vuejs-vue-13052` | workspace | 0.000 | 0.000 | 0.000 | 1 | 0 |
| `vuejs-vue-5884` | codex | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `vuejs-vue-5884` | workspace | 0.200 | 1.000 | 0.587 | 4 | 1 |
| `vuejs-vue-6097` | codex | 0.400 | 1.000 | 0.629 | 3 | 2 |
| `vuejs-vue-6097` | workspace | 0.400 | 1.000 | 0.868 | 6 | 2 |
| `vuejs-vue-6301` | codex | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `vuejs-vue-6301` | workspace | 0.000 | 0.000 | 0.000 | 4 | 0 |
| `vuejs-vue-8528` | codex | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `vuejs-vue-8528` | workspace | 0.200 | 1.000 | 1.000 | 2 | 1 |
| `vuejs-vue-9042` | codex | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `vuejs-vue-9042` | workspace | 0.200 | 1.000 | 0.532 | 5 | 1 |
| `vuejs-vue-9842` | codex | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `vuejs-vue-9842` | workspace | 0.200 | 1.000 | 0.462 | 6 | 1 |

## Four-run stability analysis

The companion four-run report contains all 280 valid executions, per-case hit counts, full-recall counts, retrieved-file Jaccard stability, and run-level token/time data. Its macro-average is descriptive stability evidence, not the one-run protocol headline.

| System | Cases | Runs | P@1 | P@2 | P@5 | P@10 | R@1 | R@2 | R@5 | R@10 | NDCG@1 | NDCG@2 | NDCG@5 | NDCG@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Workspace | 35 | 140 | 0.329 | 0.304 | 0.191 | 0.098 | 0.169 | 0.332 | 0.508 | 0.517 | 0.350 | 0.384 | 0.401 | 0.373 |
| Codex Luna efficient | 35 | 140 | 0.014 | 0.014 | 0.011 | 0.006 | 0.008 | 0.013 | 0.025 | 0.025 | 0.017 | 0.018 | 0.022 | 0.021 |

## Limitations

- Workspace indexing tokens and combined indexing-plus-flow totals are unavailable because no matching provider-logged build artifact was retained.
- The Codex condition is invalid for quality comparison: every execution encountered repository-command policy rejection, and 134/140 returned no usable evidence.
- Workspace response generation was skipped; this report evaluates retrieval through final evidence selection, not prose quality.
- The Workspace campaign contains a disclosed implementation boundary: final-selection contract handling and coverage-payload budgeting were repaired while the batch was running. Results are retained as the requested campaign, but they are not evidence from one immutable commit.
- Standard P@k penalizes short result lists because unreturned ranks are nonrelevant.

## Reproduction

- Generator: `testing/codeRepoQA/aggregate_four_run_comparison.py`
- Workspace merged ledger: `testing/codeRepoQA/statistics/runs/2026-09-02-workspace-four-runs-complete.json`
- Codex ledger: `testing/codeRepoQA/statistics/runs/2026-08-26-codex-luna-four-runs.json`
- Four-run JSON: `testing/codeRepoQA/statistics/runs/2026-09-02-workspace-vs-codex-four-run-comparison.json`
- Full-precision main JSON: `testing/codeRepoQA/statistics/runs/2026-09-02-workspace-vs-codex-main-statistics.json`
