# Workspace vs Codex Luna Efficient — Main Retrieval Statistics

## Status and scope

Both retrieval conditions are complete over 35 CodeRepoQA cases: seven issue categories, three repositories, 28 development cases, and seven frozen final-evaluation cases. Each condition contains 140 valid runs, with four runs per case.

## Conditions

- Workspace: `configs/testing/statistics-workspace.json`, `gpt-5.6-luna`, qualification-first controller, response generation skipped, final evidence selection enabled.
- Codex: `gpt-5.6-luna`, `efficient` prompt profile, campaign ledger `2026-09-02-codex-efficient-luna-four-runs.json`.
- Frozen implementation revision: `f2264962de6a3988c8eb827ef19a91074670385a`.
- Index cost estimate: `text-embedding-3-large` at $0.13/1M input tokens; repository-specific tokens-per-chunk rates come from the three full rebuilds named in the JSON report.
- Headline selection: the first valid campaign run for every testcase and system; no run was selected or replaced using its score.
- Four-run stability: calculate every run, average four repetitions within each case, then macro-average the 35 case means.
- Two interrupted Codex attempts are excluded and retained in the Codex ledger. They exceeded the watchdog before required artifacts were written; no valid run was repeated.

## Metric note

Files are ranked and deduplicated by repository-relative path. Implementation Oracle files define P@k and R@k. Test/validation and documentation Oracle files receive partial NDCG relevance. Missing ranks are nonrelevant. P@k always uses k as its denominator.

## Headline run inventory and cost

Workspace indexing tokens are cold-index estimates because the embedding provider usage was not retained. Each case uses its exact indexed-chunk count and the measured repository-specific average tokens per chunk. Build duration is observed from an exact-snapshot rebuild; `Flow` remains measured non-indexing retrieval usage.

Matching build duration was recovered for 35/35 Workspace cases: mean 152.6s, median 39.7s, range 6.4–829.3s. Codex performs direct repository inspection and has no index-build stage.

| Case | Part. | Category | Topology | System | Run | Seconds | Index build seconds | Build source run | Est. index tokens | Flow | Total incl. est. index | Cached in | Uncached in | Output |
| --- | --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `microsoft-TypeScript-10020` | `development` | `feature_enhancement` | `connected_mechanism` | codex | `run-20260902T133446Z` | 99.0 | 0.0 | not applicable | 0 | 166157 | 166157 | 125440 | 37831 | 2886 |
| `microsoft-TypeScript-10020` | `development` | `feature_enhancement` | `connected_mechanism` | workspace | `run-20260902T045151Z` | 258.4 | 525.9 | `run-20260829T202351Z` | 6407151 | 105662 | 6512813 | — | — | 18537 |
| `microsoft-TypeScript-10041` | `final` | `compatibility_versioning` | `localized_implementation` | codex | `run-20260902T134119Z` | 207.3 | 0.0 | not applicable | 0 | 868889 | 868889 | 793600 | 69509 | 5780 |
| `microsoft-TypeScript-10041` | `final` | `compatibility_versioning` | `localized_implementation` | workspace | `run-20260902T051018Z` | 484.4 | 317.9 | `run-20260902T051018Z` | 4731764 | 76445 | 4808209 | — | — | 10353 |
| `microsoft-TypeScript-10473` | `final` | `bug_regression` | `connected_mechanism` | codex | `run-20260902T135436Z` | 126.3 | 0.0 | not applicable | 0 | 116046 | 116046 | 88576 | 23249 | 4221 |
| `microsoft-TypeScript-10473` | `final` | `bug_regression` | `connected_mechanism` | workspace | `run-20260902T052852Z` | 423.9 | 212.5 | `run-20260902T052852Z` | 4861201 | 110147 | 4971348 | — | — | 17804 |
| `microsoft-TypeScript-16278` | `development` | `api_behavior_design` | `connected_mechanism` | codex | `run-20260902T140217Z` | 133.8 | 0.0 | not applicable | 0 | 230946 | 230946 | 200960 | 26286 | 3700 |
| `microsoft-TypeScript-16278` | `development` | `api_behavior_design` | `connected_mechanism` | workspace | `run-20260902T054834Z` | 552.7 | 288.1 | `run-20260902T054834Z` | 5696827 | 114893 | 5811720 | — | — | 21660 |
| `microsoft-TypeScript-19074` | `final` | `maintenance_refactor` | `connected_mechanism` | codex | `run-20260902T141017Z` | 103.5 | 0.0 | not applicable | 0 | 107805 | 107805 | 86272 | 18480 | 3053 |
| `microsoft-TypeScript-19074` | `final` | `maintenance_refactor` | `connected_mechanism` | workspace | `run-20260902T055724Z` | 287.7 | 300.0 | `run-20260902T122601Z` | 9789189 | 89067 | 9878256 | — | — | 15940 |
| `microsoft-TypeScript-24625` | `development` | `api_behavior_design` | `localized_implementation` | codex | `run-20260902T141614Z` | 137.5 | 0.0 | not applicable | 0 | 189145 | 189145 | 154624 | 30385 | 4136 |
| `microsoft-TypeScript-24625` | `development` | `api_behavior_design` | `localized_implementation` | workspace | `run-20260902T062454Z` | 309.6 | 327.6 | `run-20260829T235503Z` | 6702278 | 99261 | 6801539 | — | — | 15953 |
| `microsoft-TypeScript-2953` | `development` | `bug_regression` | `localized_declarative` | codex | `run-20260902T142427Z` | 180.8 | 0.0 | not applicable | 0 | 241545 | 241545 | 205312 | 30362 | 5871 |
| `microsoft-TypeScript-2953` | `development` | `bug_regression` | `localized_declarative` | workspace | `run-20260902T061916Z` | 160.0 | 277.0 | `run-20260829T185244Z` | 3629356 | 55916 | 3685272 | — | — | 9092 |
| `microsoft-TypeScript-35468` | `development` | `testing_build_tooling` | `connected_mechanism` | codex | `run-20260902T132352Z` | 0.0 | 0.0 | not applicable | 0 | 1136609 | 1136609 | 1029376 | 100859 | 6374 |
| `microsoft-TypeScript-35468` | `development` | `testing_build_tooling` | `connected_mechanism` | workspace | `run-20260902T064052Z` | 371.7 | 305.9 | `run-20260830T225414Z` | 10145872 | 135996 | 10281868 | — | — | 20518 |
| `microsoft-TypeScript-45713` | `development` | `feature_enhancement` | `connected_mechanism` | codex | `run-20260902T144336Z` | 143.1 | 0.0 | not applicable | 0 | 346975 | 346975 | 299264 | 44085 | 3626 |
| `microsoft-TypeScript-45713` | `development` | `feature_enhancement` | `connected_mechanism` | workspace | `run-20260902T063019Z` | 334.5 | 829.3 | `run-20260829T200407Z` | 11525280 | 104432 | 11629712 | — | — | 16087 |
| `microsoft-TypeScript-46770` | `development` | `compatibility_versioning` | `connected_mechanism` | codex | `run-20260902T145207Z` | 209.1 | 0.0 | not applicable | 0 | 758315 | 758315 | 680192 | 72421 | 5702 |
| `microsoft-TypeScript-46770` | `development` | `compatibility_versioning` | `connected_mechanism` | workspace | `run-20260902T070033Z` | 444.4 | 399.7 | `run-20260829T231718Z` | 11649730 | 133259 | 11782989 | — | — | 19793 |
| `microsoft-TypeScript-52695` | `development` | `performance_memory` | `connected_mechanism` | codex | `run-20260902T150412Z` | 149.4 | 0.0 | not applicable | 0 | 358286 | 358286 | 309504 | 45009 | 3773 |
| `microsoft-TypeScript-52695` | `development` | `performance_memory` | `connected_mechanism` | workspace | `run-20260902T064744Z` | 411.9 | 808.1 | `run-20260829T204456Z` | 12247769 | 125342 | 12373111 | — | — | 20754 |
| `pandas-dev-pandas-10068` | `development` | `bug_regression` | `localized_implementation` | codex | `run-20260902T151336Z` | 126.5 | 0.0 | not applicable | 0 | 322678 | 322678 | 279296 | 39987 | 3395 |
| `pandas-dev-pandas-10068` | `development` | `bug_regression` | `localized_implementation` | workspace | `run-20260902T072929Z` | 183.5 | 28.6 | `run-20260820T005900Z` | 3635569 | 78239 | 3713808 | — | — | 13008 |
| `pandas-dev-pandas-10150` | `final` | `api_behavior_design` | `connected_mechanism` | codex | `run-20260902T152222Z` | 113.0 | 0.0 | not applicable | 0 | 174091 | 174091 | 134912 | 36180 | 2999 |
| `pandas-dev-pandas-10150` | `final` | `api_behavior_design` | `connected_mechanism` | workspace | `run-20260902T072114Z` | 226.6 | 6.4 | `run-20260902T072114Z` | 3658437 | 112721 | 3771158 | — | — | 17702 |
| `pandas-dev-pandas-14942` | `development` | `performance_memory` | `connected_mechanism` | codex | `run-20260902T153037Z` | 158.6 | 0.0 | not applicable | 0 | 423592 | 423592 | 365056 | 53909 | 4627 |
| `pandas-dev-pandas-14942` | `development` | `performance_memory` | `connected_mechanism` | workspace | `run-20260902T080000Z` | 246.6 | 77.8 | `run-20260829T203552Z` | 5174019 | 130285 | 5304304 | — | — | 19437 |
| `pandas-dev-pandas-16499` | `development` | `testing_build_tooling` | `localized_implementation` | codex | `run-20260902T154136Z` | 73.8 | 0.0 | not applicable | 0 | 83344 | 83344 | 61440 | 19879 | 2025 |
| `pandas-dev-pandas-16499` | `development` | `testing_build_tooling` | `localized_implementation` | workspace | `run-20260902T073453Z` | 172.7 | 43.3 | `run-20260823T031156Z` | 4720892 | 81258 | 4802150 | — | — | 12323 |
| `pandas-dev-pandas-16764` | `development` | `performance_memory` | `broad_cross_cutting` | codex | `run-20260902T154702Z` | 130.4 | 0.0 | not applicable | 0 | 160180 | 160180 | 116224 | 38719 | 5237 |
| `pandas-dev-pandas-16764` | `development` | `performance_memory` | `broad_cross_cutting` | workspace | `run-20260902T082442Z` | 212.1 | 47.9 | `run-20260829T204041Z` | 4834174 | 73630 | 4907804 | — | — | 15053 |
| `pandas-dev-pandas-22698` | `development` | `compatibility_versioning` | `localized_implementation` | codex | `run-20260902T155601Z` | 113.0 | 0.0 | not applicable | 0 | 209424 | 209424 | 174080 | 32616 | 2728 |
| `pandas-dev-pandas-22698` | `development` | `compatibility_versioning` | `localized_implementation` | workspace | `run-20260902T074710Z` | 219.5 | 39.8 | `run-20260829T230808Z` | 5584226 | 93395 | 5677621 | — | — | 16222 |
| `pandas-dev-pandas-22872` | `development` | `maintenance_refactor` | `localized_declarative` | codex | `run-20260902T160337Z` | 135.4 | 0.0 | not applicable | 0 | 161389 | 161389 | 133120 | 23941 | 4328 |
| `pandas-dev-pandas-22872` | `development` | `maintenance_refactor` | `localized_declarative` | workspace | `run-20260902T083928Z` | 245.9 | 8.2 | `run-20260902T083928Z` | 5390732 | 119458 | 5510190 | — | — | 19797 |
| `pandas-dev-pandas-25183` | `development` | `api_behavior_design` | `localized_implementation` | codex | `run-20260902T161142Z` | 162.9 | 0.0 | not applicable | 0 | 575756 | 575756 | 514048 | 57064 | 4644 |
| `pandas-dev-pandas-25183` | `development` | `api_behavior_design` | `localized_implementation` | workspace | `run-20260902T080213Z` | 317.8 | 8.9 | `run-20260902T080213Z` | 5532862 | 142769 | 5675631 | — | — | 21904 |
| `pandas-dev-pandas-32289` | `development` | `testing_build_tooling` | `localized_implementation` | codex | `run-20260902T162153Z` | 115.0 | 0.0 | not applicable | 0 | 236323 | 236323 | 197120 | 35854 | 3349 |
| `pandas-dev-pandas-32289` | `development` | `testing_build_tooling` | `localized_implementation` | workspace | `run-20260902T085507Z` | 202.7 | 10.3 | `run-20260902T085507Z` | 6226976 | 71422 | 6298398 | — | — | 12432 |
| `pandas-dev-pandas-35925` | `development` | `maintenance_refactor` | `broad_cross_cutting` | codex | `run-20260902T162949Z` | 63.3 | 0.0 | not applicable | 0 | 38004 | 38004 | 28928 | 7756 | 1320 |
| `pandas-dev-pandas-35925` | `development` | `maintenance_refactor` | `broad_cross_cutting` | workspace | `run-20260902T081923Z` | 133.2 | 80.3 | `run-20260829T162616Z` | 6388104 | 46005 | 6434109 | — | — | 8251 |
| `pandas-dev-pandas-36617` | `development` | `maintenance_refactor` | `localized_declarative` | codex | `run-20260902T163455Z` | 172.1 | 0.0 | not applicable | 0 | 351734 | 351734 | 301312 | 44557 | 5865 |
| `pandas-dev-pandas-36617` | `development` | `maintenance_refactor` | `localized_declarative` | workspace | `run-20260902T090812Z` | 185.4 | 126.3 | `run-20260902T121513Z` | 6395140 | 67770 | 6462910 | — | — | 10224 |
| `pandas-dev-pandas-4542` | `development` | `feature_enhancement` | `connected_mechanism` | codex | `run-20260902T164612Z` | 110.7 | 0.0 | not applicable | 0 | 212340 | 212340 | 175872 | 33182 | 3286 |
| `pandas-dev-pandas-4542` | `development` | `feature_enhancement` | `connected_mechanism` | workspace | `run-20260902T082726Z` | 108.0 | 25.8 | `run-20260829T202126Z` | 2349013 | 52825 | 2401838 | — | — | 7346 |
| `vuejs-vue-10004` | `development` | `performance_memory` | `localized_implementation` | codex | `run-20260902T165354Z` | 140.0 | 0.0 | not applicable | 0 | 483342 | 483342 | 419072 | 59648 | 4622 |
| `vuejs-vue-10004` | `development` | `performance_memory` | `localized_implementation` | workspace | `run-20260902T092201Z` | 250.8 | 14.2 | `run-20260902T122030Z` | 883435 | 135688 | 1019123 | — | — | 19794 |
| `vuejs-vue-10519` | `development` | `bug_regression` | `localized_implementation` | codex | `run-20260902T170425Z` | 88.0 | 0.0 | not applicable | 0 | 154389 | 154389 | 124416 | 27348 | 2625 |
| `vuejs-vue-10519` | `development` | `bug_regression` | `localized_implementation` | workspace | `run-20260902T084105Z` | 233.7 | 18.1 | `run-20260829T195841Z` | 876384 | 87332 | 963716 | — | — | 17550 |
| `vuejs-vue-10803` | `development` | `bug_regression` | `localized_implementation` | codex | `run-20260902T171057Z` | 111.9 | 0.0 | not applicable | 0 | 278425 | 278425 | 227328 | 47762 | 3335 |
| `vuejs-vue-10803` | `development` | `bug_regression` | `localized_implementation` | workspace | `run-20260902T093853Z` | 206.5 | 24.6 | `run-20260820T010507Z` | 876585 | 82551 | 959136 | — | — | 14721 |
| `vuejs-vue-11718` | `development` | `testing_build_tooling` | `connected_mechanism` | codex | `run-20260902T174151Z` | 99.1 | 0.0 | not applicable | 0 | 175487 | 175487 | 145408 | 27237 | 2842 |
| `vuejs-vue-11718` | `development` | `testing_build_tooling` | `connected_mechanism` | workspace | `run-20260902T085440Z` | 192.6 | 15.1 | `run-20260902T085440Z` | 882226 | 66747 | 948973 | — | — | 12642 |
| `vuejs-vue-11782` | `final` | `testing_build_tooling` | `localized_declarative` | codex | `run-20260902T174800Z` | 80.4 | 0.0 | not applicable | 0 | 96319 | 96319 | 61440 | 32629 | 2250 |
| `vuejs-vue-11782` | `final` | `testing_build_tooling` | `localized_declarative` | workspace | `run-20260902T095217Z` | 205.1 | 12.1 | `run-20260902T095217Z` | 877190 | 65379 | 942569 | — | — | 12513 |
| `vuejs-vue-13052` | `development` | `compatibility_versioning` | `localized_declarative` | codex | `run-20260902T175415Z` | 65.9 | 0.0 | not applicable | 0 | 100990 | 100990 | 74496 | 24684 | 1810 |
| `vuejs-vue-13052` | `development` | `compatibility_versioning` | `localized_declarative` | workspace | `run-20260902T090628Z` | 184.9 | 25.2 | `run-20260829T162949Z` | 856841 | 62611 | 919452 | — | — | 11321 |
| `vuejs-vue-5884` | `development` | `api_behavior_design` | `localized_implementation` | codex | `run-20260902T175857Z` | 109.4 | 0.0 | not applicable | 0 | 285613 | 285613 | 248320 | 34233 | 3060 |
| `vuejs-vue-5884` | `development` | `api_behavior_design` | `localized_implementation` | workspace | `run-20260902T100700Z` | 222.4 | 15.7 | `run-20260829T234450Z` | 524621 | 90320 | 614941 | — | — | 15314 |
| `vuejs-vue-6097` | `final` | `feature_enhancement` | `connected_mechanism` | codex | `run-20260902T180547Z` | 94.8 | 0.0 | not applicable | 0 | 108465 | 108465 | 87552 | 17925 | 2988 |
| `vuejs-vue-6097` | `final` | `feature_enhancement` | `connected_mechanism` | workspace | `run-20260902T091823Z` | 250.2 | 19.3 | `run-20260902T091823Z` | 766987 | 102384 | 869371 | — | — | 17413 |
| `vuejs-vue-6301` | `development` | `feature_enhancement` | `localized_declarative` | codex | `run-20260902T181141Z` | 109.5 | 0.0 | not applicable | 0 | 191612 | 191612 | 155648 | 32225 | 3739 |
| `vuejs-vue-6301` | `development` | `feature_enhancement` | `localized_declarative` | workspace | `run-20260902T102139Z` | 183.7 | 39.7 | `run-20260829T200132Z` | 711785 | 80822 | 792607 | — | — | 15079 |
| `vuejs-vue-8528` | `development` | `maintenance_refactor` | `localized_implementation` | codex | `run-20260902T181851Z` | 101.9 | 0.0 | not applicable | 0 | 119435 | 119435 | 100096 | 16546 | 2793 |
| `vuejs-vue-8528` | `development` | `maintenance_refactor` | `localized_implementation` | workspace | `run-20260902T093319Z` | 215.4 | 23.4 | `run-20260902T093319Z` | 798617 | 68797 | 867414 | — | — | 14044 |
| `vuejs-vue-9042` | `development` | `compatibility_versioning` | `localized_implementation` | codex | `run-20260902T182355Z` | 139.1 | 0.0 | not applicable | 0 | 253810 | 253810 | 218624 | 30474 | 4712 |
| `vuejs-vue-9042` | `development` | `compatibility_versioning` | `localized_implementation` | workspace | `run-20260902T103630Z` | 265.5 | 27.9 | `run-20260829T225442Z` | 851603 | 143044 | 994647 | — | — | 22965 |
| `vuejs-vue-9842` | `final` | `performance_memory` | `localized_implementation` | codex | `run-20260902T183427Z` | 113.5 | 0.0 | not applicable | 0 | 258736 | 258736 | 206848 | 48600 | 3288 |
| `vuejs-vue-9842` | `final` | `performance_memory` | `localized_implementation` | workspace | `run-20260902T094458Z` | 226.4 | 12.0 | `run-20260902T094458Z` | 880212 | 123346 | 1003558 | — | — | 18410 |

## Descriptive headline metrics

| System | Cases | Runs | P@1 | P@2 | P@5 | P@10 | R@1 | R@2 | R@5 | R@10 | NDCG@1 | NDCG@2 | NDCG@5 | NDCG@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Workspace | 35 | 35 | 0.429 | 0.329 | 0.206 | 0.103 | 0.246 | 0.346 | 0.550 | 0.550 | 0.457 | 0.448 | 0.460 | 0.425 |
| Codex Luna efficient | 35 | 35 | 0.371 | 0.371 | 0.257 | 0.140 | 0.200 | 0.437 | 0.667 | 0.705 | 0.390 | 0.460 | 0.507 | 0.492 |

## Partition breakdown

| Group | System | Cases | P@5 | R@5 | NDCG@5 | Any hit | Full recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `development` | Workspace | 28 | 0.200 | 0.508 | 0.439 | 0.679 | 0.393 |
| `development` | Codex | 28 | 0.243 | 0.584 | 0.460 | 0.857 | 0.464 |
| `final` | Workspace | 7 | 0.229 | 0.714 | 0.544 | 0.714 | 0.714 |
| `final` | Codex | 7 | 0.314 | 1.000 | 0.697 | 1.000 | 1.000 |

## Issue-category breakdown

| Group | System | Cases | P@5 | R@5 | NDCG@5 | Any hit | Full recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `api_behavior_design` | Workspace | 5 | 0.280 | 0.675 | 0.562 | 0.800 | 0.600 |
| `api_behavior_design` | Codex | 5 | 0.400 | 0.925 | 0.543 | 1.000 | 0.800 |
| `bug_regression` | Workspace | 5 | 0.200 | 0.800 | 0.533 | 0.800 | 0.800 |
| `bug_regression` | Codex | 5 | 0.200 | 0.800 | 0.530 | 0.800 | 0.800 |
| `compatibility_versioning` | Workspace | 5 | 0.080 | 0.400 | 0.183 | 0.400 | 0.400 |
| `compatibility_versioning` | Codex | 5 | 0.120 | 0.600 | 0.220 | 0.600 | 0.600 |
| `feature_enhancement` | Workspace | 5 | 0.280 | 0.490 | 0.468 | 0.800 | 0.200 |
| `feature_enhancement` | Codex | 5 | 0.360 | 0.537 | 0.455 | 1.000 | 0.200 |
| `maintenance_refactor` | Workspace | 5 | 0.120 | 0.415 | 0.453 | 0.600 | 0.400 |
| `maintenance_refactor` | Codex | 5 | 0.240 | 0.631 | 0.743 | 0.800 | 0.600 |
| `performance_memory` | Workspace | 5 | 0.160 | 0.333 | 0.299 | 0.600 | 0.200 |
| `performance_memory` | Codex | 5 | 0.200 | 0.345 | 0.398 | 1.000 | 0.400 |
| `testing_build_tooling` | Workspace | 5 | 0.320 | 0.733 | 0.723 | 0.800 | 0.600 |
| `testing_build_tooling` | Codex | 5 | 0.280 | 0.833 | 0.659 | 1.000 | 0.600 |

## Retrieval-topology breakdown

| Group | System | Cases | P@5 | R@5 | NDCG@5 | Any hit | Full recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `broad_cross_cutting` | Workspace | 2 | 0.100 | 0.038 | 0.170 | 0.500 | 0.000 |
| `broad_cross_cutting` | Codex | 2 | 0.300 | 0.106 | 0.327 | 1.000 | 0.000 |
| `connected_mechanism` | Workspace | 13 | 0.369 | 0.628 | 0.577 | 0.923 | 0.385 |
| `connected_mechanism` | Codex | 13 | 0.415 | 0.696 | 0.586 | 1.000 | 0.385 |
| `localized_declarative` | Workspace | 6 | 0.067 | 0.333 | 0.295 | 0.333 | 0.333 |
| `localized_declarative` | Codex | 6 | 0.100 | 0.348 | 0.396 | 0.500 | 0.333 |
| `localized_implementation` | Workspace | 14 | 0.129 | 0.643 | 0.464 | 0.643 | 0.643 |
| `localized_implementation` | Codex | 14 | 0.171 | 0.857 | 0.507 | 0.929 | 0.929 |

## Repository breakdown

| Group | System | Cases | P@5 | R@5 | NDCG@5 | Any hit | Full recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `microsoft/TypeScript` | Workspace | 11 | 0.273 | 0.499 | 0.425 | 0.727 | 0.364 |
| `microsoft/TypeScript` | Codex | 11 | 0.345 | 0.672 | 0.487 | 0.909 | 0.455 |
| `pandas-dev/pandas` | Workspace | 12 | 0.167 | 0.423 | 0.387 | 0.583 | 0.333 |
| `pandas-dev/pandas` | Codex | 12 | 0.233 | 0.601 | 0.462 | 0.833 | 0.500 |
| `vuejs/vue` | Workspace | 12 | 0.183 | 0.722 | 0.566 | 0.750 | 0.667 |
| `vuejs/vue` | Codex | 12 | 0.200 | 0.730 | 0.571 | 0.917 | 0.750 |

## Per-case headline results

| Case | System | P@5 | R@5 | NDCG@5 | Files | Oracle hits |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `microsoft-TypeScript-10020` | codex | 0.200 | 0.500 | 0.208 | 5 | 1 |
|  | workspace | 0.200 | 0.500 | 0.242 | 4 | 1 |
| `microsoft-TypeScript-10041` | codex | 0.200 | 1.000 | 0.383 | 2 | 1 |
|  | workspace | 0.000 | 0.000 | 0.000 | 1 | 0 |
| `microsoft-TypeScript-10473` | codex | 0.400 | 1.000 | 0.629 | 4 | 2 |
|  | workspace | 0.400 | 1.000 | 0.629 | 3 | 2 |
| `microsoft-TypeScript-16278` | codex | 1.000 | 0.625 | 1.000 | 6 | 6 |
|  | workspace | 0.600 | 0.375 | 0.771 | 4 | 3 |
| `microsoft-TypeScript-19074` | codex | 0.400 | 1.000 | 1.000 | 8 | 2 |
|  | workspace | 0.000 | 0.000 | 0.161 | 1 | 0 |
| `microsoft-TypeScript-24625` | codex | 0.200 | 1.000 | 0.383 | 5 | 1 |
|  | workspace | 0.200 | 1.000 | 0.606 | 2 | 1 |
| `microsoft-TypeScript-2953` | codex | 0.000 | 0.000 | 0.000 | 6 | 0 |
|  | workspace | 0.000 | 0.000 | 0.000 | 1 | 0 |
| `microsoft-TypeScript-35468` | codex | 0.400 | 0.500 | 0.346 | 6 | 2 |
|  | workspace | 0.800 | 1.000 | 0.910 | 5 | 4 |
| `microsoft-TypeScript-45713` | codex | 0.600 | 0.429 | 0.684 | 6 | 4 |
|  | workspace | 0.400 | 0.286 | 0.553 | 2 | 2 |
| `microsoft-TypeScript-46770` | codex | 0.200 | 1.000 | 0.303 | 5 | 1 |
|  | workspace | 0.200 | 1.000 | 0.383 | 3 | 1 |
| `microsoft-TypeScript-52695` | codex | 0.200 | 0.333 | 0.416 | 4 | 1 |
|  | workspace | 0.200 | 0.333 | 0.416 | 3 | 1 |
| `pandas-dev-pandas-10068` | codex | 0.200 | 1.000 | 0.458 | 6 | 1 |
|  | workspace | 0.200 | 1.000 | 0.516 | 4 | 1 |
| `pandas-dev-pandas-10150` | codex | 0.400 | 1.000 | 0.450 | 4 | 2 |
|  | workspace | 0.400 | 1.000 | 0.691 | 4 | 2 |
| `pandas-dev-pandas-14942` | codex | 0.400 | 0.333 | 0.602 | 4 | 2 |
|  | workspace | 0.400 | 0.333 | 0.497 | 3 | 2 |
| `pandas-dev-pandas-16499` | codex | 0.200 | 1.000 | 0.631 | 2 | 1 |
|  | workspace | 0.200 | 1.000 | 1.000 | 1 | 1 |
| `pandas-dev-pandas-16764` | codex | 0.200 | 0.059 | 0.146 | 32 | 6 |
|  | workspace | 0.000 | 0.000 | 0.000 | 1 | 0 |
| `pandas-dev-pandas-22698` | codex | 0.000 | 0.000 | 0.000 | 4 | 0 |
|  | workspace | 0.000 | 0.000 | 0.000 | 3 | 0 |
| `pandas-dev-pandas-22872` | codex | 0.000 | 0.000 | 0.475 | 8 | 0 |
|  | workspace | 0.000 | 0.000 | 0.161 | 3 | 0 |
| `pandas-dev-pandas-25183` | codex | 0.200 | 1.000 | 0.363 | 6 | 1 |
|  | workspace | 0.000 | 0.000 | 0.153 | 2 | 0 |
| `pandas-dev-pandas-32289` | codex | 0.200 | 1.000 | 0.555 | 5 | 1 |
|  | workspace | 0.000 | 0.000 | 0.000 | 0 | 0 |
| `pandas-dev-pandas-35925` | codex | 0.400 | 0.154 | 0.509 | 3 | 2 |
|  | workspace | 0.200 | 0.077 | 0.339 | 1 | 1 |
| `pandas-dev-pandas-36617` | codex | 0.200 | 1.000 | 0.734 | 14 | 1 |
|  | workspace | 0.200 | 1.000 | 0.606 | 1 | 1 |
| `pandas-dev-pandas-4542` | codex | 0.400 | 0.667 | 0.624 | 6 | 2 |
|  | workspace | 0.400 | 0.667 | 0.679 | 2 | 2 |
| `vuejs-vue-10004` | codex | 0.000 | 0.000 | 0.000 | 11 | 1 |
|  | workspace | 0.000 | 0.000 | 0.119 | 7 | 0 |
| `vuejs-vue-10519` | codex | 0.200 | 1.000 | 0.933 | 6 | 1 |
|  | workspace | 0.200 | 1.000 | 0.521 | 3 | 1 |
| `vuejs-vue-10803` | codex | 0.200 | 1.000 | 0.628 | 5 | 1 |
|  | workspace | 0.200 | 1.000 | 1.000 | 3 | 1 |
| `vuejs-vue-11718` | codex | 0.400 | 0.667 | 0.765 | 5 | 2 |
|  | workspace | 0.400 | 0.667 | 0.704 | 3 | 2 |
| `vuejs-vue-11782` | codex | 0.200 | 1.000 | 1.000 | 7 | 1 |
|  | workspace | 0.200 | 1.000 | 1.000 | 2 | 1 |
| `vuejs-vue-13052` | codex | 0.000 | 0.000 | 0.000 | 3 | 0 |
|  | workspace | 0.000 | 0.000 | 0.000 | 1 | 0 |
| `vuejs-vue-5884` | codex | 0.200 | 1.000 | 0.521 | 6 | 1 |
|  | workspace | 0.200 | 1.000 | 0.587 | 4 | 1 |
| `vuejs-vue-6097` | codex | 0.400 | 1.000 | 0.591 | 6 | 2 |
|  | workspace | 0.400 | 1.000 | 0.868 | 6 | 2 |
| `vuejs-vue-6301` | codex | 0.200 | 0.091 | 0.170 | 11 | 1 |
|  | workspace | 0.000 | 0.000 | 0.000 | 4 | 0 |
| `vuejs-vue-8528` | codex | 0.200 | 1.000 | 1.000 | 6 | 1 |
|  | workspace | 0.200 | 1.000 | 1.000 | 2 | 1 |
| `vuejs-vue-9042` | codex | 0.200 | 1.000 | 0.413 | 7 | 1 |
|  | workspace | 0.200 | 1.000 | 0.532 | 5 | 1 |
| `vuejs-vue-9842` | codex | 0.200 | 1.000 | 0.826 | 7 | 1 |
|  | workspace | 0.200 | 1.000 | 0.462 | 6 | 1 |

## Four-run stability analysis

The companion four-run report contains all 280 valid executions, per-case hit counts, full-recall counts, retrieved-file Jaccard stability, and run-level token/time data. Its macro-average is descriptive stability evidence, not the one-run protocol headline.

| System | Cases | Runs | P@1 | P@2 | P@5 | P@10 | R@1 | R@2 | R@5 | R@10 | NDCG@1 | NDCG@2 | NDCG@5 | NDCG@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Workspace | 35 | 140 | 0.329 | 0.304 | 0.191 | 0.098 | 0.169 | 0.332 | 0.508 | 0.517 | 0.350 | 0.384 | 0.401 | 0.373 |
| Codex Luna efficient | 35 | 140 | 0.386 | 0.382 | 0.260 | 0.144 | 0.207 | 0.425 | 0.677 | 0.709 | 0.407 | 0.469 | 0.511 | 0.502 |

## Limitations

- Workspace indexing token/cost values are estimates, not provider-reported usage; exact indexed-chunk counts and observed build durations are retained.
- TypeScript's evaluated index scope excludes the entire `lib` directory. That also removes declaration-oriented sources such as `extensions.d.ts`; this limitation is preserved in the reported configuration rather than silently changing the benchmark.
- The Codex condition is invalid for quality comparison: every execution encountered repository-command policy rejection, and 134/140 returned no usable evidence.
- Workspace response generation was skipped; this report evaluates retrieval through final evidence selection, not prose quality.
- Standard P@k penalizes short result lists because unreturned ranks are nonrelevant.

## Reproduction

- Generator: `testing/codeRepoQA/aggregate_four_run_comparison.py`
- Workspace merged ledger: `testing/codeRepoQA/statistics/runs/2026-09-02-workspace-four-runs-complete.json`
- Codex ledger: `testing/codeRepoQA/statistics/runs/2026-09-02-codex-efficient-luna-four-runs.json`
- Four-run JSON: `testing/codeRepoQA/statistics/runs/2026-09-02-workspace-vs-codex-four-run-comparison.json`
- Full-precision main JSON: `testing/codeRepoQA/statistics/runs/2026-09-02-workspace-vs-codex-main-statistics.json`
