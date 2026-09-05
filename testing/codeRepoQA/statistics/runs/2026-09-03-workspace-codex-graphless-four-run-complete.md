# Workspace, Codex Luna Efficient, and Workspace without CodeGraph — 35-Case Four-Run Comparison

## Status and scope

All three conditions contain 35 cases and four valid retrieval runs per case. Graphless is a controlled Workspace ablation: it reuses lexical/vector indexes but disables CodeGraph.

## Conditions

- Workspace: `gpt-5.6-luna`, qualification-first controller.
- Codex: `gpt-5.6-luna`, `efficient` profile.
- Graphless: the Workspace condition with `structural_graph_enabled: false`.
- Response generation was skipped and final evidence selection remained enabled in every accepted run.
- Aggregation: average four repetitions within each case, then macro-average 35 case means.

## Metric glossary

All metrics inspect the first **k ordered, unique repository files** returned by a system. `@1`, `@2`, `@5`, and `@10` mean that k is respectively 1, 2, 5, or 10.

- **P@k (precision):** implementation-Oracle files among the first k, divided by k. A short list still uses k as the denominator.
- **R@k (recall):** implementation-Oracle files among the first k, divided by all implementation-Oracle files for that testcase.
- **NDCG@k:** a rank-sensitive quality score from 0 to 1 for the first k files. Implementation-Oracle files receive relevance 2, supporting test/validation or documentation files relevance 1, and earlier ranks count more.

## Four-run descriptive metrics

| System | Cases | Runs | P@1 | P@2 | P@5 | P@10 | R@1 | R@2 | R@5 | R@10 | NDCG@1 | NDCG@2 | NDCG@5 | NDCG@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Workspace | 35 | 140 | 0.329 | 0.304 | 0.191 | 0.098 | 0.169 | 0.332 | 0.508 | 0.517 | 0.350 | 0.384 | 0.401 | 0.373 |
| Codex Luna Efficient | 35 | 140 | 0.386 | 0.382 | 0.260 | 0.144 | 0.207 | 0.425 | 0.677 | 0.709 | 0.407 | 0.469 | 0.511 | 0.502 |
| Workspace without CodeGraph | 35 | 140 | 0.493 | 0.379 | 0.200 | 0.101 | 0.300 | 0.417 | 0.505 | 0.508 | 0.512 | 0.496 | 0.463 | 0.427 |

## Operational summary

| System | Sufficient rate | Mean files | Any Oracle | Full Oracle | Mean flow tokens | Mean seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Workspace | 0.007 | 2.964 | 0.679 | 0.407 | 95315 | 227.5 |
| Codex Luna Efficient | 1.000 | 6.493 | 0.893 | 0.579 | 283913 | 121.7 |
| Workspace without CodeGraph | 0.000 | 2.814 | 0.686 | 0.379 | 82177 | 268.9 |

## Partition breakdown

| Group | System | Cases | Runs | P@5 | R@5 | NDCG@5 | Any hit | Full recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `development` | Workspace | 28 | 112 | 0.188 | 0.474 | 0.392 | 0.670 | 0.366 |
|  | Codex Luna Efficient | 28 | 112 | 0.246 | 0.596 | 0.464 | 0.866 | 0.473 |
|  | Workspace without CodeGraph | 28 | 112 | 0.195 | 0.453 | 0.439 | 0.661 | 0.312 |
| `final` | Workspace | 7 | 28 | 0.207 | 0.643 | 0.437 | 0.714 | 0.571 |
|  | Codex Luna Efficient | 7 | 28 | 0.314 | 1.000 | 0.700 | 1.000 | 1.000 |
|  | Workspace without CodeGraph | 7 | 28 | 0.221 | 0.714 | 0.560 | 0.786 | 0.643 |

## Issue-category breakdown

| Group | System | Cases | Runs | P@5 | R@5 | NDCG@5 | Any hit | Full recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `api_behavior_design` | Workspace | 5 | 20 | 0.300 | 0.625 | 0.515 | 0.800 | 0.550 |
|  | Codex Luna Efficient | 5 | 20 | 0.400 | 0.925 | 0.555 | 1.000 | 0.800 |
|  | Workspace without CodeGraph | 5 | 20 | 0.320 | 0.644 | 0.614 | 0.800 | 0.450 |
| `bug_regression` | Workspace | 5 | 20 | 0.200 | 0.800 | 0.525 | 0.800 | 0.800 |
|  | Codex Luna Efficient | 5 | 20 | 0.210 | 0.850 | 0.518 | 0.850 | 0.850 |
|  | Workspace without CodeGraph | 5 | 20 | 0.170 | 0.650 | 0.522 | 0.650 | 0.650 |
| `compatibility_versioning` | Workspace | 5 | 20 | 0.100 | 0.500 | 0.225 | 0.500 | 0.500 |
|  | Codex Luna Efficient | 5 | 20 | 0.120 | 0.600 | 0.212 | 0.600 | 0.600 |
|  | Workspace without CodeGraph | 5 | 20 | 0.090 | 0.450 | 0.233 | 0.450 | 0.450 |
| `feature_enhancement` | Workspace | 5 | 20 | 0.240 | 0.426 | 0.403 | 0.800 | 0.100 |
|  | Codex Luna Efficient | 5 | 20 | 0.370 | 0.547 | 0.547 | 1.000 | 0.200 |
|  | Workspace without CodeGraph | 5 | 20 | 0.310 | 0.509 | 0.532 | 0.850 | 0.200 |
| `maintenance_refactor` | Workspace | 5 | 20 | 0.120 | 0.390 | 0.344 | 0.600 | 0.350 |
|  | Codex Luna Efficient | 5 | 20 | 0.240 | 0.631 | 0.738 | 0.800 | 0.600 |
|  | Workspace without CodeGraph | 5 | 20 | 0.130 | 0.440 | 0.444 | 0.650 | 0.400 |
| `performance_memory` | Workspace | 5 | 20 | 0.170 | 0.336 | 0.290 | 0.650 | 0.200 |
|  | Codex Luna Efficient | 5 | 20 | 0.200 | 0.350 | 0.343 | 1.000 | 0.400 |
|  | Workspace without CodeGraph | 5 | 20 | 0.160 | 0.317 | 0.351 | 0.750 | 0.200 |
| `testing_build_tooling` | Workspace | 5 | 20 | 0.210 | 0.475 | 0.504 | 0.600 | 0.350 |
|  | Codex Luna Efficient | 5 | 20 | 0.280 | 0.833 | 0.667 | 1.000 | 0.600 |
|  | Workspace without CodeGraph | 5 | 20 | 0.220 | 0.525 | 0.545 | 0.650 | 0.300 |

## Retrieval-topology breakdown

| Group | System | Cases | Runs | P@5 | R@5 | NDCG@5 | Any hit | Full recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `broad_cross_cutting` | Workspace | 2 | 8 | 0.125 | 0.046 | 0.191 | 0.625 | 0.000 |
|  | Codex Luna Efficient | 2 | 8 | 0.275 | 0.099 | 0.323 | 1.000 | 0.000 |
|  | Workspace without CodeGraph | 2 | 8 | 0.175 | 0.061 | 0.244 | 0.875 | 0.000 |
| `connected_mechanism` | Workspace | 13 | 52 | 0.338 | 0.571 | 0.526 | 0.923 | 0.288 |
|  | Codex Luna Efficient | 13 | 52 | 0.427 | 0.705 | 0.620 | 1.000 | 0.385 |
|  | Workspace without CodeGraph | 13 | 52 | 0.350 | 0.560 | 0.568 | 0.904 | 0.231 |
| `localized_declarative` | Workspace | 6 | 24 | 0.033 | 0.167 | 0.115 | 0.167 | 0.167 |
|  | Codex Luna Efficient | 6 | 24 | 0.100 | 0.386 | 0.401 | 0.542 | 0.375 |
|  | Workspace without CodeGraph | 6 | 24 | 0.058 | 0.254 | 0.173 | 0.292 | 0.250 |
| `localized_implementation` | Workspace | 14 | 56 | 0.132 | 0.661 | 0.438 | 0.679 | 0.679 |
|  | Codex Luna Efficient | 14 | 56 | 0.171 | 0.857 | 0.484 | 0.929 | 0.929 |
|  | Workspace without CodeGraph | 14 | 56 | 0.125 | 0.625 | 0.521 | 0.625 | 0.625 |

## Repository breakdown

| Group | System | Cases | Runs | P@5 | R@5 | NDCG@5 | Any hit | Full recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `microsoft/TypeScript` | Workspace | 11 | 44 | 0.268 | 0.527 | 0.403 | 0.795 | 0.364 |
|  | Codex Luna Efficient | 11 | 44 | 0.359 | 0.701 | 0.516 | 0.932 | 0.477 |
|  | Workspace without CodeGraph | 11 | 44 | 0.300 | 0.549 | 0.478 | 0.795 | 0.318 |
| `pandas-dev/pandas` | Workspace | 12 | 48 | 0.163 | 0.393 | 0.365 | 0.583 | 0.292 |
|  | Codex Luna Efficient | 12 | 48 | 0.233 | 0.603 | 0.472 | 0.833 | 0.500 |
|  | Workspace without CodeGraph | 12 | 48 | 0.142 | 0.323 | 0.365 | 0.583 | 0.208 |
| `vuejs/vue` | Workspace | 12 | 48 | 0.150 | 0.604 | 0.436 | 0.667 | 0.562 |
|  | Codex Luna Efficient | 12 | 48 | 0.196 | 0.728 | 0.547 | 0.917 | 0.750 |
|  | Workspace without CodeGraph | 12 | 48 | 0.167 | 0.648 | 0.547 | 0.688 | 0.604 |

## Per-case results

| Case | Partition | Topology | System | P@5 | R@5 | NDCG@5 | Any-hit runs | Full-recall runs | Mean files | Mean tokens | Mean seconds |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `microsoft-TypeScript-10020` | `development` | `connected_mechanism` | Workspace | 0.200 | 0.500 | 0.273 | 4/4 | 0/4 | 3.00 | 108624 | 250.7 |
|  |  |  | Codex Luna Efficient | 0.200 | 0.500 | 0.445 | 4/4 | 0/4 | 5.25 | 203872 | 98.3 |
|  |  |  | Workspace without CodeGraph | 0.200 | 0.500 | 0.438 | 4/4 | 0/4 | 2.50 | 95172 | 197.0 |
| `microsoft-TypeScript-10041` | `final` | `localized_implementation` | Workspace | 0.100 | 0.500 | 0.191 | 2/4 | 2/4 | 1.75 | 76983 | 278.7 |
|  |  |  | Codex Luna Efficient | 0.200 | 1.000 | 0.363 | 4/4 | 4/4 | 4.00 | 849162 | 199.3 |
|  |  |  | Workspace without CodeGraph | 0.150 | 0.750 | 0.455 | 3/4 | 3/4 | 1.50 | 59397 | 167.4 |
| `microsoft-TypeScript-10473` | `final` | `connected_mechanism` | Workspace | 0.400 | 1.000 | 0.629 | 4/4 | 4/4 | 3.00 | 110861 | 281.2 |
|  |  |  | Codex Luna Efficient | 0.400 | 1.000 | 0.600 | 4/4 | 4/4 | 4.50 | 224604 | 115.3 |
|  |  |  | Workspace without CodeGraph | 0.400 | 1.000 | 0.643 | 4/4 | 4/4 | 3.50 | 87216 | 185.2 |
| `microsoft-TypeScript-16278` | `development` | `connected_mechanism` | Workspace | 0.800 | 0.500 | 0.888 | 4/4 | 0/4 | 5.00 | 121339 | 326.1 |
|  |  |  | Codex Luna Efficient | 1.000 | 0.625 | 1.000 | 4/4 | 0/4 | 6.25 | 200626 | 120.0 |
|  |  |  | Workspace without CodeGraph | 0.950 | 0.594 | 0.967 | 4/4 | 0/4 | 5.00 | 96722 | 201.8 |
| `microsoft-TypeScript-19074` | `final` | `connected_mechanism` | Workspace | 0.050 | 0.125 | 0.161 | 1/4 | 0/4 | 1.25 | 75507 | 242.6 |
|  |  |  | Codex Luna Efficient | 0.400 | 1.000 | 0.980 | 4/4 | 4/4 | 7.25 | 73227 | 89.1 |
|  |  |  | Workspace without CodeGraph | 0.050 | 0.125 | 0.146 | 1/4 | 0/4 | 1.25 | 60534 | 165.0 |
| `microsoft-TypeScript-24625` | `development` | `localized_implementation` | Workspace | 0.200 | 1.000 | 0.419 | 4/4 | 4/4 | 2.75 | 101704 | 239.5 |
|  |  |  | Codex Luna Efficient | 0.200 | 1.000 | 0.383 | 4/4 | 4/4 | 4.75 | 175100 | 123.4 |
|  |  |  | Workspace without CodeGraph | 0.200 | 1.000 | 0.606 | 4/4 | 4/4 | 2.00 | 76690 | 184.5 |
| `microsoft-TypeScript-2953` | `development` | `localized_declarative` | Workspace | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 1.25 | 63998 | 165.7 |
|  |  |  | Codex Luna Efficient | 0.050 | 0.250 | 0.125 | 1/4 | 1/4 | 6.75 | 297974 | 152.6 |
|  |  |  | Workspace without CodeGraph | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 1.50 | 66906 | 264.6 |
| `microsoft-TypeScript-35468` | `development` | `connected_mechanism` | Workspace | 0.500 | 0.625 | 0.567 | 4/4 | 2/4 | 4.75 | 130336 | 295.2 |
|  |  |  | Codex Luna Efficient | 0.400 | 0.500 | 0.360 | 4/4 | 0/4 | 6.50 | 968002 | 134.6 |
|  |  |  | Workspace without CodeGraph | 0.500 | 0.625 | 0.682 | 4/4 | 0/4 | 5.50 | 108560 | 0.0 |
| `microsoft-TypeScript-45713` | `development` | `connected_mechanism` | Workspace | 0.300 | 0.214 | 0.446 | 4/4 | 0/4 | 2.50 | 108377 | 261.3 |
|  |  |  | Codex Luna Efficient | 0.700 | 0.500 | 0.786 | 4/4 | 0/4 | 5.50 | 310299 | 127.8 |
|  |  |  | Workspace without CodeGraph | 0.500 | 0.357 | 0.621 | 4/4 | 0/4 | 2.75 | 83090 | 210.0 |
| `microsoft-TypeScript-46770` | `development` | `connected_mechanism` | Workspace | 0.200 | 1.000 | 0.438 | 4/4 | 4/4 | 2.75 | 124925 | 326.2 |
|  |  |  | Codex Luna Efficient | 0.200 | 1.000 | 0.343 | 4/4 | 4/4 | 5.25 | 646619 | 181.3 |
|  |  |  | Workspace without CodeGraph | 0.150 | 0.750 | 0.287 | 3/4 | 3/4 | 5.25 | 96716 | 226.6 |
| `microsoft-TypeScript-52695` | `development` | `connected_mechanism` | Workspace | 0.200 | 0.333 | 0.416 | 4/4 | 0/4 | 3.00 | 127062 | 314.8 |
|  |  |  | Codex Luna Efficient | 0.200 | 0.333 | 0.287 | 4/4 | 0/4 | 4.50 | 315889 | 140.7 |
|  |  |  | Workspace without CodeGraph | 0.200 | 0.333 | 0.416 | 4/4 | 0/4 | 2.75 | 87417 | 223.4 |
| `pandas-dev-pandas-10068` | `development` | `localized_implementation` | Workspace | 0.200 | 1.000 | 0.475 | 4/4 | 4/4 | 4.50 | 95499 | 207.9 |
|  |  |  | Codex Luna Efficient | 0.200 | 1.000 | 0.501 | 4/4 | 4/4 | 6.00 | 278654 | 131.5 |
|  |  |  | Workspace without CodeGraph | 0.050 | 0.250 | 0.183 | 1/4 | 1/4 | 1.75 | 71563 | 0.0 |
| `pandas-dev-pandas-10150` | `final` | `connected_mechanism` | Workspace | 0.350 | 0.875 | 0.709 | 4/4 | 3/4 | 3.75 | 95908 | 204.8 |
|  |  |  | Codex Luna Efficient | 0.400 | 1.000 | 0.510 | 4/4 | 4/4 | 4.50 | 262136 | 123.8 |
|  |  |  | Workspace without CodeGraph | 0.250 | 0.625 | 0.650 | 4/4 | 1/4 | 3.25 | 93077 | 193.2 |
| `pandas-dev-pandas-14942` | `development` | `connected_mechanism` | Workspace | 0.400 | 0.333 | 0.463 | 4/4 | 0/4 | 3.75 | 129212 | 240.7 |
|  |  |  | Codex Luna Efficient | 0.450 | 0.375 | 0.597 | 4/4 | 0/4 | 6.00 | 487512 | 164.7 |
|  |  |  | Workspace without CodeGraph | 0.250 | 0.208 | 0.415 | 4/4 | 0/4 | 3.75 | 130318 | 197.5 |
| `pandas-dev-pandas-16499` | `development` | `localized_implementation` | Workspace | 0.200 | 1.000 | 1.000 | 4/4 | 4/4 | 1.00 | 88571 | 184.4 |
|  |  |  | Codex Luna Efficient | 0.200 | 1.000 | 0.631 | 4/4 | 4/4 | 2.50 | 91718 | 81.5 |
|  |  |  | Workspace without CodeGraph | 0.200 | 1.000 | 1.000 | 4/4 | 4/4 | 1.25 | 67748 | 138.0 |
| `pandas-dev-pandas-16764` | `development` | `broad_cross_cutting` | Workspace | 0.050 | 0.015 | 0.042 | 1/4 | 0/4 | 1.75 | 84468 | 221.4 |
|  |  |  | Codex Luna Efficient | 0.150 | 0.044 | 0.106 | 4/4 | 0/4 | 18.50 | 287425 | 134.8 |
|  |  |  | Workspace without CodeGraph | 0.150 | 0.044 | 0.149 | 3/4 | 0/4 | 2.00 | 81805 | 183.5 |
| `pandas-dev-pandas-22698` | `development` | `localized_implementation` | Workspace | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 2.75 | 97283 | 225.5 |
|  |  |  | Codex Luna Efficient | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 4.00 | 180673 | 113.9 |
|  |  |  | Workspace without CodeGraph | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 2.25 | 69336 | 163.2 |
| `pandas-dev-pandas-22872` | `development` | `localized_declarative` | Workspace | 0.000 | 0.000 | 0.040 | 0/4 | 0/4 | 1.00 | 100792 | 234.7 |
|  |  |  | Codex Luna Efficient | 0.000 | 0.000 | 0.475 | 0/4 | 0/4 | 8.00 | 136366 | 121.3 |
|  |  |  | Workspace without CodeGraph | 0.000 | 0.000 | 0.126 | 0/4 | 0/4 | 3.50 | 100269 | 236.0 |
| `pandas-dev-pandas-25183` | `development` | `localized_implementation` | Workspace | 0.000 | 0.000 | 0.099 | 0/4 | 0/4 | 2.25 | 125116 | 257.5 |
|  |  |  | Codex Luna Efficient | 0.200 | 1.000 | 0.363 | 4/4 | 4/4 | 6.75 | 418598 | 152.8 |
|  |  |  | Workspace without CodeGraph | 0.000 | 0.000 | 0.145 | 0/4 | 0/4 | 2.25 | 98820 | 201.1 |
| `pandas-dev-pandas-32289` | `development` | `localized_implementation` | Workspace | 0.000 | 0.000 | 0.159 | 0/4 | 0/4 | 1.00 | 62958 | 176.6 |
|  |  |  | Codex Luna Efficient | 0.200 | 1.000 | 0.580 | 4/4 | 4/4 | 4.50 | 254060 | 119.2 |
|  |  |  | Workspace without CodeGraph | 0.000 | 0.000 | 0.220 | 0/4 | 0/4 | 1.75 | 56003 | 131.8 |
| `pandas-dev-pandas-35925` | `development` | `broad_cross_cutting` | Workspace | 0.200 | 0.077 | 0.339 | 4/4 | 0/4 | 1.00 | 42513 | 120.9 |
|  |  |  | Codex Luna Efficient | 0.400 | 0.154 | 0.539 | 4/4 | 0/4 | 4.75 | 86356 | 76.4 |
|  |  |  | Workspace without CodeGraph | 0.200 | 0.077 | 0.339 | 4/4 | 0/4 | 1.25 | 58069 | 162.7 |
| `pandas-dev-pandas-36617` | `development` | `localized_declarative` | Workspace | 0.150 | 0.750 | 0.399 | 3/4 | 3/4 | 1.50 | 74026 | 188.0 |
|  |  |  | Codex Luna Efficient | 0.200 | 1.000 | 0.695 | 4/4 | 4/4 | 13.75 | 307547 | 169.2 |
|  |  |  | Workspace without CodeGraph | 0.200 | 1.000 | 0.606 | 4/4 | 4/4 | 1.75 | 73001 | 163.9 |
| `pandas-dev-pandas-4542` | `development` | `connected_mechanism` | Workspace | 0.400 | 0.667 | 0.650 | 4/4 | 0/4 | 2.75 | 103909 | 204.7 |
|  |  |  | Codex Luna Efficient | 0.400 | 0.667 | 0.665 | 4/4 | 0/4 | 7.25 | 217524 | 115.6 |
|  |  |  | Workspace without CodeGraph | 0.400 | 0.667 | 0.549 | 4/4 | 0/4 | 3.75 | 95099 | 222.2 |
| `vuejs-vue-10004` | `development` | `localized_implementation` | Workspace | 0.000 | 0.000 | 0.056 | 0/4 | 0/4 | 7.00 | 132152 | 252.8 |
|  |  |  | Codex Luna Efficient | 0.000 | 0.000 | 0.000 | 4/4 | 4/4 | 13.50 | 441284 | 157.8 |
|  |  |  | Workspace without CodeGraph | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 7.25 | 127342 | 218.6 |
| `vuejs-vue-10519` | `development` | `localized_implementation` | Workspace | 0.200 | 1.000 | 0.521 | 4/4 | 4/4 | 3.00 | 77737 | 203.8 |
|  |  |  | Codex Luna Efficient | 0.200 | 1.000 | 0.803 | 4/4 | 4/4 | 5.75 | 198564 | 98.0 |
|  |  |  | Workspace without CodeGraph | 0.200 | 1.000 | 0.826 | 4/4 | 4/4 | 1.00 | 54695 | 121.0 |
| `vuejs-vue-10803` | `development` | `localized_implementation` | Workspace | 0.200 | 1.000 | 1.000 | 4/4 | 4/4 | 2.75 | 79862 | 201.2 |
|  |  |  | Codex Luna Efficient | 0.200 | 1.000 | 0.562 | 4/4 | 4/4 | 5.75 | 304026 | 123.0 |
|  |  |  | Workspace without CodeGraph | 0.200 | 1.000 | 0.957 | 4/4 | 4/4 | 1.75 | 70612 | 0.0 |
| `vuejs-vue-11718` | `development` | `connected_mechanism` | Workspace | 0.300 | 0.500 | 0.543 | 3/4 | 0/4 | 2.25 | 58299 | 177.0 |
|  |  |  | Codex Luna Efficient | 0.400 | 0.667 | 0.765 | 4/4 | 0/4 | 5.00 | 138336 | 92.3 |
|  |  |  | Workspace without CodeGraph | 0.300 | 0.500 | 0.574 | 3/4 | 0/4 | 1.75 | 45531 | 121.1 |
| `vuejs-vue-11782` | `final` | `localized_declarative` | Workspace | 0.050 | 0.250 | 0.250 | 1/4 | 1/4 | 3.25 | 71765 | 202.9 |
|  |  |  | Codex Luna Efficient | 0.200 | 1.000 | 1.000 | 4/4 | 4/4 | 7.25 | 145754 | 93.9 |
|  |  |  | Workspace without CodeGraph | 0.100 | 0.500 | 0.250 | 2/4 | 2/4 | 4.25 | 71042 | 3769.8 |
| `vuejs-vue-13052` | `development` | `localized_declarative` | Workspace | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 1.25 | 65717 | 178.9 |
|  |  |  | Codex Luna Efficient | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 2.25 | 78695 | 70.5 |
|  |  |  | Workspace without CodeGraph | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 1.25 | 55350 | 154.4 |
| `vuejs-vue-5884` | `development` | `localized_implementation` | Workspace | 0.150 | 0.750 | 0.461 | 4/4 | 4/4 | 4.75 | 99086 | 219.5 |
|  |  |  | Codex Luna Efficient | 0.200 | 1.000 | 0.521 | 4/4 | 4/4 | 6.75 | 216048 | 102.4 |
|  |  |  | Workspace without CodeGraph | 0.200 | 1.000 | 0.701 | 4/4 | 4/4 | 3.00 | 74416 | 178.8 |
| `vuejs-vue-6097` | `final` | `connected_mechanism` | Workspace | 0.300 | 0.750 | 0.648 | 4/4 | 2/4 | 4.75 | 100008 | 223.9 |
|  |  |  | Codex Luna Efficient | 0.400 | 1.000 | 0.724 | 4/4 | 4/4 | 6.50 | 118720 | 88.4 |
|  |  |  | Workspace without CodeGraph | 0.400 | 1.000 | 1.000 | 4/4 | 4/4 | 3.00 | 77232 | 176.1 |
| `vuejs-vue-6301` | `development` | `localized_declarative` | Workspace | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 3.75 | 81375 | 183.0 |
|  |  |  | Codex Luna Efficient | 0.150 | 0.068 | 0.112 | 4/4 | 0/4 | 8.50 | 139554 | 107.6 |
|  |  |  | Workspace without CodeGraph | 0.050 | 0.023 | 0.053 | 1/4 | 0/4 | 2.00 | 83058 | 0.0 |
| `vuejs-vue-8528` | `development` | `localized_implementation` | Workspace | 0.200 | 1.000 | 0.783 | 4/4 | 4/4 | 2.00 | 65312 | 174.8 |
|  |  |  | Codex Luna Efficient | 0.200 | 1.000 | 1.000 | 4/4 | 4/4 | 2.25 | 81530 | 76.0 |
|  |  |  | Workspace without CodeGraph | 0.200 | 1.000 | 1.000 | 4/4 | 4/4 | 1.00 | 51414 | 132.6 |
| `vuejs-vue-9042` | `development` | `localized_implementation` | Workspace | 0.200 | 1.000 | 0.497 | 4/4 | 4/4 | 5.50 | 134786 | 256.7 |
|  |  |  | Codex Luna Efficient | 0.200 | 1.000 | 0.352 | 4/4 | 4/4 | 9.50 | 418258 | 157.9 |
|  |  |  | Workspace without CodeGraph | 0.150 | 0.750 | 0.425 | 3/4 | 3/4 | 4.25 | 118649 | 245.3 |
| `vuejs-vue-9842` | `final` | `localized_implementation` | Workspace | 0.200 | 1.000 | 0.474 | 4/4 | 4/4 | 5.50 | 119941 | 240.3 |
|  |  |  | Codex Luna Efficient | 0.200 | 1.000 | 0.723 | 4/4 | 4/4 | 7.25 | 382230 | 106.2 |
|  |  |  | Workspace without CodeGraph | 0.200 | 1.000 | 0.777 | 4/4 | 4/4 | 6.00 | 133331 | 275.7 |

## Run inventory

| Case | System | Rep | Run | Coverage | Sufficient | Evidence | Files | Flow tokens | Seconds |
| --- | --- | ---: | --- | --- | --- | ---: | ---: | ---: | ---: |
| `microsoft-TypeScript-10020` | codex | 1 | `run-20260902T133446Z` | `strong` | true | 10 | 5 | 166157 | 99.0 |
|  |  | 2 | `run-20260902T133625Z` | `strong` | true | 10 | 5 | 114038 | 79.5 |
|  |  | 3 | `run-20260902T133744Z` | `strong` | true | 13 | 6 | 217318 | 101.5 |
|  |  | 4 | `run-20260902T133926Z` | `strong` | true | 11 | 5 | 317976 | 113.1 |
|  | graphless | 1 | `run-20260902T214230Z` | `partial` | false | 5 | 1 | 104308 | 201.9 |
|  |  | 2 | `run-20260902T214552Z` | `partial` | false | 8 | 3 | 97810 | 210.0 |
|  |  | 3 | `run-20260902T214922Z` | `partial` | false | 7 | 3 | 88697 | 196.9 |
|  |  | 4 | `run-20260902T215239Z` | `partial` | false | 7 | 3 | 89873 | 179.3 |
|  | workspace | 1 | `run-20260902T045151Z` | `partial` | false | 9 | 4 | 105662 | 258.4 |
|  |  | 2 | `run-20260902T045610Z` | `partial` | false | 5 | 2 | 116482 | 254.3 |
|  |  | 3 | `run-20260902T050023Z` | `partial` | false | 7 | 3 | 104348 | 236.7 |
|  |  | 4 | `run-20260902T050604Z` | `partial` | false | 9 | 3 | 108006 | 253.6 |
| `microsoft-TypeScript-10041` | codex | 1 | `run-20260902T134119Z` | `strong` | true | 10 | 2 | 868889 | 207.3 |
|  |  | 2 | `run-20260902T134446Z` | `strong` | true | 15 | 4 | 943558 | 203.1 |
|  |  | 3 | `run-20260902T134809Z` | `strong` | true | 13 | 5 | 807349 | 197.0 |
|  |  | 4 | `run-20260902T135126Z` | `strong` | true | 14 | 5 | 776853 | 189.9 |
|  | graphless | 1 | `run-20260902T215538Z` | `partial` | false | 3 | 2 | 60705 | 215.6 |
|  |  | 2 | `run-20260902T215914Z` | `partial` | false | 3 | 2 | 57145 | 147.3 |
|  |  | 3 | `run-20260902T220141Z` | `partial` | false | 2 | 1 | 53046 | 144.5 |
|  |  | 4 | `run-20260902T220626Z` | `partial` | false | 3 | 1 | 66691 | 162.4 |
|  | workspace | 1 | `run-20260902T051018Z` | `partial` | false | 1 | 1 | 76445 | 484.4 |
|  |  | 2 | `run-20260902T051822Z` | `partial` | false | 3 | 2 | 80865 | 225.4 |
|  |  | 3 | `run-20260902T052207Z` | `partial` | false | 2 | 1 | 71910 | 203.3 |
|  |  | 4 | `run-20260902T052530Z` | `partial` | false | 3 | 3 | 78711 | 201.5 |
| `microsoft-TypeScript-10473` | codex | 1 | `run-20260902T135436Z` | `strong` | true | 12 | 4 | 116046 | 126.3 |
|  |  | 2 | `run-20260902T135642Z` | `strong` | true | 10 | 4 | 404065 | 123.6 |
|  |  | 3 | `run-20260902T135846Z` | `strong` | true | 13 | 6 | 130282 | 104.6 |
|  |  | 4 | `run-20260902T140031Z` | `strong` | true | 9 | 4 | 248024 | 106.7 |
|  | graphless | 1 | `run-20260902T220908Z` | `partial` | false | 8 | 4 | 94037 | 243.6 |
|  |  | 2 | `run-20260902T221312Z` | `partial` | false | 8 | 4 | 90811 | 167.7 |
|  |  | 3 | `run-20260902T221600Z` | `partial` | false | 6 | 3 | 69814 | 153.9 |
|  |  | 4 | `run-20260902T221834Z` | `partial` | false | 8 | 3 | 94203 | 175.5 |
|  | workspace | 1 | `run-20260902T052852Z` | `partial` | false | 9 | 3 | 110147 | 423.9 |
|  |  | 2 | `run-20260902T053556Z` | `partial` | false | 8 | 3 | 109464 | 227.3 |
|  |  | 3 | `run-20260902T053943Z` | `partial` | false | 6 | 3 | 104498 | 222.1 |
|  |  | 4 | `run-20260902T054325Z` | `partial` | false | 8 | 3 | 119336 | 251.6 |
| `microsoft-TypeScript-16278` | codex | 1 | `run-20260902T140217Z` | `strong` | true | 10 | 6 | 230946 | 133.8 |
|  |  | 2 | `run-20260902T140431Z` | `strong` | true | 15 | 7 | 213036 | 127.3 |
|  |  | 3 | `run-20260902T140638Z` | `strong` | true | 13 | 6 | 178951 | 121.6 |
|  |  | 4 | `run-20260902T140840Z` | `strong` | true | 14 | 6 | 179573 | 97.3 |
|  | graphless | 1 | `run-20260902T222129Z` | `partial` | false | 12 | 6 | 103588 | 274.2 |
|  |  | 2 | `run-20260902T222603Z` | `partial` | false | 11 | 5 | 89285 | 167.8 |
|  |  | 3 | `run-20260902T222851Z` | `partial` | false | 13 | 5 | 97643 | 180.7 |
|  |  | 4 | `run-20260902T223152Z` | `partial` | false | 9 | 4 | 96373 | 184.7 |
|  | workspace | 1 | `run-20260902T054834Z` | `partial` | false | 14 | 4 | 114893 | 552.7 |
|  |  | 2 | `run-20260902T061222Z` | `partial` | false | 13 | 4 | 115333 | 254.5 |
|  |  | 3 | `run-20260902T061637Z` | `partial` | false | 13 | 7 | 132601 | 267.7 |
|  |  | 4 | `run-20260902T062104Z` | `partial` | false | 14 | 5 | 122529 | 229.6 |
| `microsoft-TypeScript-19074` | codex | 1 | `run-20260902T141017Z` | `strong` | true | 9 | 8 | 107805 | 103.5 |
|  |  | 2 | `run-20260902T141201Z` | `strong` | true | 7 | 7 | 46986 | 73.9 |
|  |  | 3 | `run-20260902T141315Z` | `strong` | true | 7 | 7 | 59783 | 83.9 |
|  |  | 4 | `run-20260902T141439Z` | `strong` | true | 9 | 7 | 78333 | 95.1 |
|  | graphless | 1 | `run-20260902T223456Z` | `partial` | false | 2 | 1 | 45356 | 188.3 |
|  |  | 2 | `run-20260902T223805Z` | `partial` | false | 1 | 1 | 52718 | 117.8 |
|  |  | 3 | `run-20260902T224002Z` | `partial` | false | 1 | 1 | 67516 | 176.9 |
|  |  | 4 | `run-20260902T224259Z` | `partial` | false | 2 | 2 | 76544 | 177.0 |
|  | workspace | 1 | `run-20260902T055724Z` | `partial` | false | 3 | 1 | 89067 | 287.7 |
|  |  | 2 | `run-20260902T060211Z` | `partial` | false | 1 | 1 | 79475 | 246.1 |
|  |  | 3 | `run-20260902T060617Z` | `partial` | false | 1 | 1 | 57329 | 206.9 |
|  |  | 4 | `run-20260902T061059Z` | `partial` | false | 2 | 2 | 76157 | 229.6 |
| `microsoft-TypeScript-24625` | codex | 1 | `run-20260902T141614Z` | `strong` | true | 10 | 5 | 189145 | 137.5 |
|  |  | 2 | `run-20260902T141831Z` | `strong` | true | 10 | 5 | 166367 | 111.2 |
|  |  | 3 | `run-20260902T142022Z` | `strong` | true | 10 | 3 | 239761 | 147.3 |
|  |  | 4 | `run-20260902T142250Z` | `strong` | true | 11 | 6 | 105127 | 97.5 |
|  | graphless | 1 | `run-20260902T224556Z` | `partial` | false | 4 | 2 | 75351 | 241.8 |
|  |  | 2 | `run-20260902T224958Z` | `partial` | false | 6 | 2 | 75644 | 148.2 |
|  |  | 3 | `run-20260902T225226Z` | `partial` | false | 4 | 2 | 70409 | 159.7 |
|  |  | 4 | `run-20260902T225506Z` | `partial` | false | 5 | 2 | 85356 | 188.1 |
|  | workspace | 1 | `run-20260902T062454Z` | `partial` | false | 6 | 2 | 99261 | 309.6 |
|  |  | 2 | `run-20260902T063004Z` | `partial` | false | 6 | 4 | 113447 | 209.1 |
|  |  | 3 | `run-20260902T063333Z` | `partial` | false | 5 | 2 | 90658 | 216.9 |
|  |  | 4 | `run-20260902T063710Z` | `partial` | false | 4 | 3 | 103451 | 222.3 |
| `microsoft-TypeScript-2953` | codex | 1 | `run-20260902T142427Z` | `strong` | true | 8 | 6 | 241545 | 180.8 |
|  |  | 2 | `run-20260902T142728Z` | `strong` | true | 8 | 5 | 353710 | 162.9 |
|  |  | 3 | `run-20260902T143011Z` | `strong` | true | 10 | 9 | 333006 | 136.6 |
|  |  | 4 | `run-20260902T143228Z` | `strong` | true | 9 | 7 | 263635 | 130.1 |
|  | graphless | 1 | `run-20260902T225814Z` | `partial` | false | 2 | 1 | 67384 | 619.1 |
|  |  | 2 | `run-20260902T230833Z` | `partial` | false | 4 | 2 | 74680 | 168.1 |
|  |  | 3 | `run-20260902T231351Z` | `partial` | false | 2 | 1 | 54555 | 116.1 |
|  |  | 4 | `run-20260902T231547Z` | `partial` | false | 5 | 2 | 71005 | 155.0 |
|  | workspace | 1 | `run-20260902T061916Z` | `partial` | false | 2 | 1 | 55916 | 160.0 |
|  |  | 2 | `run-20260902T062156Z` | `partial` | false | 3 | 1 | 74834 | 180.6 |
|  |  | 3 | `run-20260902T062456Z` | `partial` | false | 1 | 1 | 60806 | 155.1 |
|  |  | 4 | `run-20260902T062731Z` | `partial` | false | 3 | 2 | 64437 | 167.1 |
| `microsoft-TypeScript-35468` | codex | 1 | `run-20260902T132352Z` | `strong` | true | 21 | 6 | 1136609 | 0.0 |
|  |  | 2 | `run-20260902T143438Z` | `strong` | true | 26 | 8 | 735124 | 178.7 |
|  |  | 3 | `run-20260902T143736Z` | `strong` | true | 20 | 6 | 649424 | 164.2 |
|  |  | 4 | `run-20260902T144021Z` | `strong` | true | 12 | 6 | 1350852 | 195.4 |
|  | graphless | 1 | `run-20260902T201743Z` | `partial` | false | 6 | 6 | 98260 | 0.0 |
|  |  | 2 | `run-20260902T202325Z` | `partial` | false | 7 | 5 | 118487 | 0.0 |
|  |  | 3 | `run-20260902T202746Z` | `partial` | false | 8 | 6 | 113623 | 0.0 |
|  |  | 4 | `run-20260902T203109Z` | `partial` | false | 8 | 5 | 103871 | 0.0 |
|  | workspace | 1 | `run-20260902T064052Z` | `partial` | false | 14 | 5 | 135996 | 371.7 |
|  |  | 2 | `run-20260902T064704Z` | `partial` | false | 10 | 5 | 120869 | 259.3 |
|  |  | 3 | `run-20260902T065123Z` | `partial` | false | 10 | 2 | 130111 | 254.6 |
|  |  | 4 | `run-20260902T065537Z` | `partial` | false | 14 | 7 | 134366 | 295.3 |
| `microsoft-TypeScript-45713` | codex | 1 | `run-20260902T144336Z` | `strong` | true | 12 | 6 | 346975 | 143.1 |
|  |  | 2 | `run-20260902T144559Z` | `strong` | true | 8 | 5 | 382177 | 131.3 |
|  |  | 3 | `run-20260902T144810Z` | `strong` | true | 12 | 6 | 332477 | 133.2 |
|  |  | 4 | `run-20260902T145024Z` | `strong` | true | 10 | 5 | 179567 | 103.6 |
|  | graphless | 1 | `run-20260902T231822Z` | `partial` | false | 5 | 3 | 94953 | 296.4 |
|  |  | 2 | `run-20260902T232319Z` | `partial` | false | 8 | 4 | 85482 | 249.4 |
|  |  | 3 | `run-20260902T232728Z` | `partial` | false | 4 | 2 | 76738 | 144.4 |
|  |  | 4 | `run-20260902T232952Z` | `partial` | false | 7 | 2 | 75187 | 149.9 |
|  | workspace | 1 | `run-20260902T063019Z` | `partial` | false | 5 | 2 | 104432 | 334.5 |
|  |  | 2 | `run-20260902T063553Z` | `partial` | false | 6 | 2 | 109488 | 235.0 |
|  |  | 3 | `run-20260902T063948Z` | `partial` | false | 7 | 4 | 105211 | 219.7 |
|  |  | 4 | `run-20260902T064328Z` | `partial` | false | 6 | 2 | 114376 | 256.1 |
| `microsoft-TypeScript-46770` | codex | 1 | `run-20260902T145207Z` | `strong` | true | 16 | 5 | 758315 | 209.1 |
|  |  | 2 | `run-20260902T145537Z` | `strong` | true | 23 | 5 | 578148 | 165.9 |
|  |  | 3 | `run-20260902T145822Z` | `strong` | true | 15 | 4 | 583659 | 159.3 |
|  |  | 4 | `run-20260902T150102Z` | `strong` | true | 20 | 7 | 666353 | 190.8 |
|  | graphless | 1 | `run-20260902T233222Z` | `partial` | false | 10 | 7 | 102857 | 310.5 |
|  |  | 2 | `run-20260902T233820Z` | `partial` | false | 5 | 5 | 77617 | 166.6 |
|  |  | 3 | `run-20260902T234107Z` | `partial` | false | 4 | 3 | 101624 | 218.2 |
|  |  | 4 | `run-20260902T234445Z` | `partial` | false | 8 | 6 | 104764 | 211.0 |
|  | workspace | 1 | `run-20260902T070033Z` | `partial` | false | 7 | 3 | 133259 | 444.4 |
|  |  | 2 | `run-20260902T070757Z` | `partial` | false | 10 | 3 | 123963 | 323.1 |
|  |  | 3 | `run-20260902T071320Z` | `partial` | false | 7 | 1 | 118312 | 270.3 |
|  |  | 4 | `run-20260902T071750Z` | `partial` | false | 10 | 4 | 124166 | 267.2 |
| `microsoft-TypeScript-52695` | codex | 1 | `run-20260902T150412Z` | `strong` | true | 15 | 4 | 358286 | 149.4 |
|  |  | 2 | `run-20260902T150642Z` | `strong` | true | 12 | 5 | 367539 | 127.7 |
|  |  | 3 | `run-20260902T150850Z` | `strong` | true | 17 | 5 | 308568 | 151.4 |
|  |  | 4 | `run-20260902T151121Z` | `strong` | true | 14 | 4 | 229162 | 134.0 |
|  | graphless | 1 | `run-20260902T234816Z` | `partial` | false | 3 | 2 | 74890 | 288.8 |
|  |  | 2 | `run-20260902T235305Z` | `partial` | false | 5 | 3 | 93185 | 210.7 |
|  |  | 3 | `run-20260902T235635Z` | `partial` | false | 7 | 4 | 95168 | 194.2 |
|  |  | 4 | `run-20260903T000319Z` | `partial` | false | 3 | 2 | 86425 | 199.9 |
|  | workspace | 1 | `run-20260902T064744Z` | `partial` | false | 7 | 3 | 125342 | 411.9 |
|  |  | 2 | `run-20260902T065436Z` | `partial` | false | 8 | 2 | 118981 | 272.7 |
|  |  | 3 | `run-20260902T070353Z` | `partial` | false | 9 | 4 | 121797 | 289.7 |
|  |  | 4 | `run-20260902T071628Z` | `partial` | false | 11 | 3 | 142129 | 284.9 |
| `pandas-dev-pandas-10068` | codex | 1 | `run-20260902T151336Z` | `strong` | true | 12 | 6 | 322678 | 126.5 |
|  |  | 2 | `run-20260902T151542Z` | `strong` | true | 11 | 7 | 333192 | 153.1 |
|  |  | 3 | `run-20260902T151815Z` | `strong` | true | 10 | 5 | 209269 | 128.9 |
|  |  | 4 | `run-20260902T152024Z` | `strong` | true | 9 | 6 | 249476 | 117.7 |
|  | graphless | 1 | `run-20260902T203440Z` | `partial` | false | 3 | 2 | 72327 | 0.0 |
|  |  | 2 | `run-20260902T203710Z` | `partial` | false | 4 | 1 | 89958 | 0.0 |
|  |  | 3 | `run-20260902T204002Z` | `partial` | false | 2 | 1 | 50726 | 0.0 |
|  |  | 4 | `run-20260902T204147Z` | `partial` | false | 3 | 3 | 73242 | 0.0 |
|  | workspace | 1 | `run-20260902T072929Z` | `partial` | false | 5 | 4 | 78239 | 183.5 |
|  |  | 2 | `run-20260902T074521Z` | `partial` | false | 8 | 4 | 97066 | 202.4 |
|  |  | 3 | `run-20260902T074843Z` | `partial` | false | 9 | 5 | 119475 | 238.4 |
|  |  | 4 | `run-20260902T075242Z` | `partial` | false | 6 | 5 | 87215 | 207.1 |
| `pandas-dev-pandas-10150` | codex | 1 | `run-20260902T152222Z` | `strong` | true | 8 | 4 | 174091 | 113.0 |
|  |  | 2 | `run-20260902T152415Z` | `strong` | true | 11 | 5 | 429097 | 151.3 |
|  |  | 3 | `run-20260902T152646Z` | `strong` | true | 8 | 5 | 136337 | 104.8 |
|  |  | 4 | `run-20260902T152831Z` | `strong` | true | 9 | 4 | 309017 | 126.2 |
|  | graphless | 1 | `run-20260903T000640Z` | `partial` | false | 6 | 4 | 105839 | 230.3 |
|  |  | 2 | `run-20260903T001029Z` | `partial` | false | 4 | 3 | 84125 | 191.4 |
|  |  | 3 | `run-20260903T001341Z` | `partial` | false | 5 | 4 | 93219 | 188.4 |
|  |  | 4 | `run-20260903T001649Z` | `partial` | false | 3 | 2 | 89126 | 162.5 |
|  | workspace | 1 | `run-20260902T072114Z` | `partial` | false | 4 | 4 | 112721 | 226.6 |
|  |  | 2 | `run-20260902T072500Z` | `partial` | false | 4 | 4 | 101278 | 222.0 |
|  |  | 3 | `run-20260902T072842Z` | `partial` | false | 4 | 4 | 90388 | 193.7 |
|  |  | 4 | `run-20260902T073156Z` | `partial` | false | 3 | 3 | 79247 | 177.0 |
| `pandas-dev-pandas-14942` | codex | 1 | `run-20260902T153037Z` | `strong` | true | 11 | 4 | 423592 | 158.6 |
|  |  | 2 | `run-20260902T153316Z` | `strong` | true | 13 | 8 | 542912 | 169.6 |
|  |  | 3 | `run-20260902T153605Z` | `strong` | true | 16 | 7 | 568658 | 190.4 |
|  |  | 4 | `run-20260902T153916Z` | `strong` | true | 11 | 5 | 414884 | 140.1 |
|  | graphless | 1 | `run-20260903T001932Z` | `partial` | false | 6 | 3 | 129837 | 195.4 |
|  |  | 2 | `run-20260903T002247Z` | `partial` | false | 7 | 4 | 130248 | 193.3 |
|  |  | 3 | `run-20260903T081232Z` | `partial` | false | 8 | 4 | 136195 | 218.3 |
|  |  | 4 | `run-20260903T081759Z` | `partial` | false | 8 | 4 | 124991 | 182.9 |
|  | workspace | 1 | `run-20260902T080000Z` | `partial` | false | 8 | 3 | 130285 | 246.6 |
|  |  | 2 | `run-20260902T081246Z` | `partial` | false | 9 | 4 | 127754 | 230.3 |
|  |  | 3 | `run-20260902T081637Z` | `partial` | false | 7 | 4 | 147830 | 250.9 |
|  |  | 4 | `run-20260902T082047Z` | `partial` | false | 5 | 4 | 110980 | 234.9 |
| `pandas-dev-pandas-16499` | codex | 1 | `run-20260902T154136Z` | `strong` | true | 6 | 2 | 83344 | 73.8 |
|  |  | 2 | `run-20260902T154250Z` | `strong` | true | 7 | 4 | 107172 | 86.7 |
|  |  | 3 | `run-20260902T154416Z` | `strong` | true | 5 | 2 | 74213 | 70.1 |
|  |  | 4 | `run-20260902T154527Z` | `strong` | true | 7 | 2 | 102141 | 95.2 |
|  | graphless | 1 | `run-20260903T082102Z` | `partial` | false | 4 | 1 | 86795 | 189.4 |
|  |  | 2 | `run-20260903T082411Z` | `partial` | false | 2 | 1 | 53747 | 100.5 |
|  |  | 3 | `run-20260903T082552Z` | `partial` | false | 2 | 2 | 68630 | 133.1 |
|  |  | 4 | `run-20260903T082805Z` | `partial` | false | 2 | 1 | 61820 | 129.0 |
|  | workspace | 1 | `run-20260902T073453Z` | `partial` | false | 3 | 1 | 81258 | 172.7 |
|  |  | 2 | `run-20260902T073745Z` | `partial` | false | 3 | 1 | 102037 | 215.0 |
|  |  | 3 | `run-20260902T074121Z` | `partial` | false | 3 | 1 | 78502 | 154.5 |
|  |  | 4 | `run-20260902T074355Z` | `partial` | false | 3 | 1 | 92486 | 195.4 |
| `pandas-dev-pandas-16764` | codex | 1 | `run-20260902T154702Z` | `strong` | true | 33 | 32 | 160180 | 130.4 |
|  |  | 2 | `run-20260902T154912Z` | `strong` | true | 21 | 19 | 415519 | 138.9 |
|  |  | 3 | `run-20260902T155131Z` | `strong` | true | 22 | 14 | 252565 | 132.7 |
|  |  | 4 | `run-20260902T155344Z` | `strong` | true | 15 | 9 | 321437 | 137.1 |
|  | graphless | 1 | `run-20260903T083014Z` | `partial` | false | 5 | 3 | 91950 | 178.9 |
|  |  | 2 | `run-20260903T083313Z` | `partial` | false | 3 | 1 | 90001 | 201.6 |
|  |  | 3 | `run-20260903T083634Z` | `partial` | false | 4 | 2 | 92643 | 213.5 |
|  |  | 4 | `run-20260903T084008Z` | `partial` | false | 3 | 2 | 52626 | 139.9 |
|  | workspace | 1 | `run-20260902T082442Z` | `partial` | false | 4 | 1 | 73630 | 212.1 |
|  |  | 2 | `run-20260902T082814Z` | `partial` | false | 6 | 3 | 88581 | 221.9 |
|  |  | 3 | `run-20260902T083156Z` | `partial` | false | 2 | 1 | 91398 | 226.9 |
|  |  | 4 | `run-20260902T083543Z` | `partial` | false | 2 | 2 | 84265 | 224.9 |
| `pandas-dev-pandas-22698` | codex | 1 | `run-20260902T155601Z` | `strong` | true | 8 | 4 | 209424 | 113.0 |
|  |  | 2 | `run-20260902T155754Z` | `strong` | true | 8 | 5 | 192832 | 126.6 |
|  |  | 3 | `run-20260902T160001Z` | `strong` | true | 6 | 4 | 183500 | 116.1 |
|  |  | 4 | `run-20260902T160157Z` | `strong` | true | 4 | 3 | 136936 | 99.9 |
|  | graphless | 1 | `run-20260903T084228Z` | `partial` | false | 5 | 3 | 83630 | 223.9 |
|  |  | 2 | `run-20260903T084612Z` | `partial` | false | 3 | 2 | 70298 | 166.9 |
|  |  | 3 | `run-20260903T084858Z` | `partial` | false | 1 | 1 | 41981 | 79.9 |
|  |  | 4 | `run-20260903T085018Z` | `partial` | false | 5 | 3 | 81437 | 182.0 |
|  | workspace | 1 | `run-20260902T074710Z` | `partial` | false | 5 | 3 | 93395 | 219.5 |
|  |  | 2 | `run-20260902T075050Z` | `partial` | false | 3 | 2 | 100113 | 208.5 |
|  |  | 3 | `run-20260902T075419Z` | `partial` | false | 5 | 4 | 109879 | 250.1 |
|  |  | 4 | `run-20260902T075829Z` | `partial` | false | 4 | 2 | 85745 | 224.0 |
| `pandas-dev-pandas-22872` | codex | 1 | `run-20260902T160337Z` | `strong` | true | 17 | 8 | 161389 | 135.4 |
|  |  | 2 | `run-20260902T160553Z` | `strong` | true | 18 | 8 | 72989 | 104.6 |
|  |  | 3 | `run-20260902T160737Z` | `strong` | true | 16 | 8 | 237646 | 141.7 |
|  |  | 4 | `run-20260902T160958Z` | `strong` | true | 17 | 8 | 73441 | 103.4 |
|  | graphless | 1 | `run-20260903T125232Z` | `partial` | false | 4 | 4 | 120561 | 271.7 |
|  |  | 2 | `run-20260903T125807Z` | `partial` | false | 2 | 1 | 66618 | 180.1 |
|  |  | 3 | `run-20260903T130428Z` | `partial` | false | 2 | 2 | 103123 | 242.0 |
|  |  | 4 | `run-20260903T130830Z` | `partial` | false | 8 | 7 | 110774 | 250.2 |
|  | workspace | 1 | `run-20260902T083928Z` | `partial` | false | 3 | 3 | 119458 | 245.9 |
|  |  | 2 | `run-20260902T084334Z` | `missing` | false | 0 | 0 | 96226 | 251.0 |
|  |  | 3 | `run-20260902T084745Z` | `partial` | false | 1 | 1 | 104800 | 257.3 |
|  |  | 4 | `run-20260902T085202Z` | `missing` | false | 0 | 0 | 82683 | 184.8 |
| `pandas-dev-pandas-25183` | codex | 1 | `run-20260902T161142Z` | `strong` | true | 11 | 6 | 575756 | 162.9 |
|  |  | 2 | `run-20260902T161425Z` | `strong` | true | 12 | 6 | 318868 | 130.1 |
|  |  | 3 | `run-20260902T161634Z` | `strong` | true | 14 | 8 | 360592 | 153.2 |
|  |  | 4 | `run-20260902T161908Z` | `strong` | true | 13 | 7 | 419178 | 164.9 |
|  | graphless | 1 | `run-20260903T131240Z` | `partial` | false | 3 | 2 | 76342 | 199.3 |
|  |  | 2 | `run-20260903T131559Z` | `partial` | false | 3 | 2 | 107134 | 190.9 |
|  |  | 3 | `run-20260903T131910Z` | `partial` | false | 4 | 3 | 102679 | 186.5 |
|  |  | 4 | `run-20260903T132217Z` | `partial` | false | 2 | 2 | 109126 | 227.8 |
|  | workspace | 1 | `run-20260902T080213Z` | `partial` | false | 6 | 2 | 142769 | 317.8 |
|  |  | 2 | `run-20260902T080730Z` | `partial` | false | 5 | 1 | 100663 | 223.7 |
|  |  | 3 | `run-20260902T081114Z` | `partial` | false | 8 | 3 | 123037 | 240.5 |
|  |  | 4 | `run-20260902T081514Z` | `partial` | false | 7 | 3 | 133996 | 247.9 |
| `pandas-dev-pandas-32289` | codex | 1 | `run-20260902T162153Z` | `strong` | true | 7 | 5 | 236323 | 115.0 |
|  |  | 2 | `run-20260902T162348Z` | `strong` | true | 9 | 5 | 290837 | 130.5 |
|  |  | 3 | `run-20260902T162558Z` | `strong` | true | 8 | 4 | 272925 | 131.6 |
|  |  | 4 | `run-20260902T162810Z` | `strong` | true | 6 | 4 | 216157 | 99.6 |
|  | graphless | 1 | `run-20260903T132605Z` | `partial` | false | 3 | 2 | 56010 | 134.8 |
|  |  | 2 | `run-20260903T132819Z` | `partial` | false | 4 | 3 | 73269 | 164.9 |
|  |  | 3 | `run-20260903T133104Z` | `partial` | false | 1 | 1 | 40023 | 97.8 |
|  |  | 4 | `run-20260903T133242Z` | `partial` | false | 1 | 1 | 54709 | 129.6 |
|  | workspace | 1 | `run-20260902T085507Z` | `missing` | false | 0 | 0 | 71422 | 202.7 |
|  |  | 2 | `run-20260902T085830Z` | `partial` | false | 2 | 2 | 62268 | 174.4 |
|  |  | 3 | `run-20260902T090124Z` | `partial` | false | 1 | 1 | 58686 | 171.6 |
|  |  | 4 | `run-20260902T090416Z` | `partial` | false | 1 | 1 | 59457 | 157.9 |
| `pandas-dev-pandas-35925` | codex | 1 | `run-20260902T162949Z` | `strong` | true | 4 | 3 | 38004 | 63.3 |
|  |  | 2 | `run-20260902T163053Z` | `strong` | true | 7 | 4 | 97447 | 74.1 |
|  |  | 3 | `run-20260902T163207Z` | `strong` | true | 6 | 4 | 77573 | 80.4 |
|  |  | 4 | `run-20260902T163327Z` | `strong` | true | 10 | 8 | 132402 | 87.9 |
|  | graphless | 1 | `run-20260903T133452Z` | `partial` | false | 1 | 1 | 50155 | 162.1 |
|  |  | 2 | `run-20260903T133734Z` | `partial` | false | 1 | 1 | 59446 | 156.3 |
|  |  | 3 | `run-20260903T134317Z` | `partial` | false | 2 | 1 | 62111 | 174.7 |
|  |  | 4 | `run-20260903T134611Z` | `partial` | false | 2 | 2 | 60563 | 157.6 |
|  | workspace | 1 | `run-20260902T081923Z` | `partial` | false | 1 | 1 | 46005 | 133.2 |
|  |  | 2 | `run-20260902T082136Z` | `partial` | false | 1 | 1 | 30244 | 103.4 |
|  |  | 3 | `run-20260902T082319Z` | `partial` | false | 1 | 1 | 46884 | 144.3 |
|  |  | 4 | `run-20260902T082543Z` | `partial` | false | 1 | 1 | 46919 | 102.6 |
| `pandas-dev-pandas-36617` | codex | 1 | `run-20260902T163455Z` | `strong` | true | 18 | 14 | 351734 | 172.1 |
|  |  | 2 | `run-20260902T163747Z` | `strong` | true | 16 | 13 | 162822 | 152.8 |
|  |  | 3 | `run-20260902T164020Z` | `strong` | true | 13 | 13 | 262373 | 165.8 |
|  |  | 4 | `run-20260902T164307Z` | `strong` | true | 16 | 15 | 453260 | 186.1 |
|  | graphless | 1 | `run-20260903T134849Z` | `partial` | false | 3 | 2 | 82407 | 189.2 |
|  |  | 2 | `run-20260903T135158Z` | `partial` | false | 1 | 1 | 44535 | 98.6 |
|  |  | 3 | `run-20260903T135337Z` | `partial` | false | 4 | 3 | 85517 | 188.9 |
|  |  | 4 | `run-20260903T135646Z` | `partial` | false | 1 | 1 | 79545 | 179.0 |
|  | workspace | 1 | `run-20260902T090812Z` | `partial` | false | 1 | 1 | 67770 | 185.4 |
|  |  | 2 | `run-20260902T091117Z` | `partial` | false | 3 | 2 | 94357 | 235.0 |
|  |  | 3 | `run-20260902T091512Z` | `partial` | false | 4 | 2 | 64554 | 178.7 |
|  |  | 4 | `run-20260902T091811Z` | `partial` | false | 1 | 1 | 69422 | 152.7 |
| `pandas-dev-pandas-4542` | codex | 1 | `run-20260902T164612Z` | `strong` | true | 12 | 6 | 212340 | 110.7 |
|  |  | 2 | `run-20260902T164803Z` | `strong` | true | 16 | 8 | 192508 | 122.8 |
|  |  | 3 | `run-20260902T165006Z` | `strong` | true | 10 | 6 | 222856 | 115.9 |
|  |  | 4 | `run-20260902T165201Z` | `strong` | true | 16 | 9 | 242391 | 112.9 |
|  | graphless | 1 | `run-20260903T135945Z` | `partial` | false | 8 | 3 | 106717 | 231.9 |
|  |  | 2 | `run-20260903T140337Z` | `partial` | false | 8 | 4 | 72287 | 156.8 |
|  |  | 3 | `run-20260903T140614Z` | `partial` | false | 6 | 4 | 98104 | 254.2 |
|  |  | 4 | `run-20260903T141028Z` | `partial` | false | 5 | 4 | 103287 | 245.8 |
|  | workspace | 1 | `run-20260902T082726Z` | `partial` | false | 6 | 2 | 52825 | 108.0 |
|  |  | 2 | `run-20260902T082914Z` | `partial` | false | 6 | 3 | 128922 | 247.8 |
|  |  | 3 | `run-20260902T083322Z` | `partial` | false | 8 | 4 | 137940 | 265.5 |
|  |  | 4 | `run-20260902T083747Z` | `partial` | false | 7 | 2 | 95949 | 197.4 |
| `vuejs-vue-10004` | codex | 1 | `run-20260902T165354Z` | `strong` | true | 14 | 11 | 483342 | 140.0 |
|  |  | 2 | `run-20260902T165614Z` | `strong` | true | 20 | 16 | 329703 | 141.6 |
|  |  | 3 | `run-20260902T165836Z` | `strong` | true | 19 | 13 | 431851 | 153.6 |
|  |  | 4 | `run-20260902T170109Z` | `strong` | true | 20 | 14 | 520242 | 195.8 |
|  | graphless | 1 | `run-20260903T081759Z` | `partial` | false | 10 | 6 | 131852 | 214.5 |
|  |  | 2 | `run-20260903T082133Z` | `partial` | false | 10 | 8 | 132904 | 216.3 |
|  |  | 3 | `run-20260903T082837Z` | `partial` | false | 10 | 6 | 114244 | 200.7 |
|  |  | 4 | `run-20260903T083158Z` | `partial` | false | 13 | 9 | 130370 | 242.9 |
|  | workspace | 1 | `run-20260902T092201Z` | `partial` | false | 10 | 7 | 135688 | 250.8 |
|  |  | 2 | `run-20260902T092612Z` | `partial` | false | 10 | 7 | 134299 | 247.4 |
|  |  | 3 | `run-20260902T093019Z` | `partial` | false | 10 | 7 | 133112 | 256.6 |
|  |  | 4 | `run-20260902T093436Z` | `partial` | false | 11 | 7 | 125510 | 256.4 |
| `vuejs-vue-10519` | codex | 1 | `run-20260902T170425Z` | `strong` | true | 11 | 6 | 154389 | 88.0 |
|  |  | 2 | `run-20260902T170553Z` | `strong` | true | 10 | 6 | 195516 | 96.1 |
|  |  | 3 | `run-20260902T170729Z` | `strong` | true | 11 | 6 | 237105 | 110.6 |
|  |  | 4 | `run-20260902T170920Z` | `strong` | true | 10 | 5 | 207248 | 97.3 |
|  | graphless | 1 | `run-20260903T083601Z` | `partial` | false | 4 | 1 | 46707 | 98.9 |
|  |  | 2 | `run-20260903T083740Z` | `partial` | false | 5 | 1 | 57629 | 129.5 |
|  |  | 3 | `run-20260903T083949Z` | `partial` | false | 5 | 1 | 57529 | 125.1 |
|  |  | 4 | `run-20260903T084154Z` | `partial` | false | 3 | 1 | 56916 | 130.5 |
|  | workspace | 1 | `run-20260902T084105Z` | `partial` | false | 5 | 3 | 87332 | 233.7 |
|  |  | 2 | `run-20260902T084458Z` | `partial` | false | 5 | 3 | 72056 | 207.5 |
|  |  | 3 | `run-20260902T084826Z` | `partial` | false | 5 | 3 | 73199 | 187.7 |
|  |  | 4 | `run-20260902T085134Z` | `partial` | false | 5 | 3 | 78360 | 186.2 |
| `vuejs-vue-10803` | codex | 1 | `run-20260902T171057Z` | `strong` | true | 11 | 5 | 278425 | 111.9 |
|  |  | 2 | `run-20260902T173511Z` | `strong` | true | 13 | 7 | 439410 | 152.9 |
|  |  | 3 | `run-20260902T173744Z` | `strong` | true | 8 | 5 | 281719 | 123.4 |
|  |  | 4 | `run-20260902T174007Z` | `strong` | true | 10 | 6 | 216548 | 103.7 |
|  | graphless | 1 | `run-20260902T204415Z` | `partial` | false | 3 | 2 | 76661 | 0.0 |
|  |  | 2 | `run-20260902T204707Z` | `partial` | false | 3 | 2 | 74038 | 0.0 |
|  |  | 3 | `run-20260902T204953Z` | `partial` | false | 3 | 2 | 72308 | 0.0 |
|  |  | 4 | `run-20260902T205238Z` | `partial` | false | 2 | 1 | 59441 | 0.0 |
|  | workspace | 1 | `run-20260902T093853Z` | `partial` | false | 5 | 3 | 82551 | 206.5 |
|  |  | 2 | `run-20260902T094219Z` | `partial` | false | 3 | 2 | 77675 | 183.4 |
|  |  | 3 | `run-20260902T094522Z` | `partial` | false | 5 | 3 | 76434 | 196.2 |
|  |  | 4 | `run-20260902T094838Z` | `partial` | false | 5 | 3 | 82790 | 218.6 |
| `vuejs-vue-11718` | codex | 1 | `run-20260902T174151Z` | `strong` | true | 7 | 5 | 175487 | 99.1 |
|  |  | 2 | `run-20260902T174330Z` | `strong` | true | 9 | 5 | 84899 | 77.1 |
|  |  | 3 | `run-20260902T174447Z` | `strong` | true | 6 | 4 | 87267 | 92.5 |
|  |  | 4 | `run-20260902T174620Z` | `strong` | true | 7 | 6 | 205690 | 100.6 |
|  | graphless | 1 | `run-20260903T084405Z` | `partial` | false | 2 | 1 | 44462 | 104.0 |
|  |  | 2 | `run-20260903T084626Z` | `partial` | false | 2 | 2 | 49889 | 157.6 |
|  |  | 3 | `run-20260903T084903Z` | `partial` | false | 2 | 2 | 42023 | 106.5 |
|  |  | 4 | `run-20260903T085050Z` | `partial` | false | 2 | 2 | 45749 | 116.2 |
|  | workspace | 1 | `run-20260902T085440Z` | `partial` | false | 5 | 3 | 66747 | 192.6 |
|  |  | 2 | `run-20260902T085752Z` | `partial` | false | 4 | 3 | 72170 | 218.2 |
|  |  | 3 | `run-20260902T090131Z` | `partial` | false | 4 | 3 | 65255 | 197.4 |
|  |  | 4 | `run-20260902T090448Z` | `missing` | false | 0 | 0 | 29025 | 99.6 |
| `vuejs-vue-11782` | codex | 1 | `run-20260902T174800Z` | `strong` | true | 8 | 7 | 96319 | 80.4 |
|  |  | 2 | `run-20260902T174920Z` | `strong` | true | 8 | 7 | 116833 | 106.8 |
|  |  | 3 | `run-20260902T175107Z` | `strong` | true | 9 | 8 | 213333 | 97.9 |
|  |  | 4 | `run-20260902T175245Z` | `strong` | true | 10 | 7 | 156530 | 90.4 |
|  | graphless | 1 | `run-20260903T125229Z` | `partial` | false | 6 | 5 | 71008 | 14517.6 |
|  |  | 2 | `run-20260903T125520Z` | `partial` | false | 6 | 5 | 80093 | 194.6 |
|  |  | 3 | `run-20260903T125834Z` | `partial` | false | 4 | 3 | 59575 | 158.6 |
|  |  | 4 | `run-20260903T130113Z` | `partial` | false | 5 | 4 | 73494 | 208.5 |
|  | workspace | 1 | `run-20260902T095217Z` | `partial` | false | 2 | 2 | 65379 | 205.1 |
|  |  | 2 | `run-20260902T095654Z` | `partial` | false | 6 | 4 | 73344 | 187.4 |
|  |  | 3 | `run-20260902T100001Z` | `partial` | false | 4 | 3 | 75061 | 225.5 |
|  |  | 4 | `run-20260902T100347Z` | `partial` | false | 6 | 4 | 73277 | 193.6 |
| `vuejs-vue-13052` | codex | 1 | `run-20260902T175415Z` | `strong` | true | 6 | 3 | 100990 | 65.9 |
|  |  | 2 | `run-20260902T175521Z` | `strong` | true | 6 | 2 | 68712 | 64.4 |
|  |  | 3 | `run-20260902T175626Z` | `strong` | true | 8 | 3 | 95785 | 89.2 |
|  |  | 4 | `run-20260902T175755Z` | `strong` | true | 6 | 1 | 49294 | 62.4 |
|  | graphless | 1 | `run-20260903T130441Z` | `partial` | false | 2 | 1 | 52032 | 149.1 |
|  |  | 2 | `run-20260903T130710Z` | `partial` | false | 4 | 2 | 60530 | 161.4 |
|  |  | 3 | `run-20260903T130952Z` | `partial` | false | 2 | 1 | 46365 | 133.3 |
|  |  | 4 | `run-20260903T131205Z` | `partial` | false | 3 | 1 | 62473 | 173.9 |
|  | workspace | 1 | `run-20260902T090628Z` | `partial` | false | 2 | 1 | 62611 | 184.9 |
|  |  | 2 | `run-20260902T090932Z` | `partial` | false | 1 | 1 | 58651 | 161.3 |
|  |  | 3 | `run-20260902T091214Z` | `partial` | false | 5 | 2 | 78088 | 195.0 |
|  |  | 4 | `run-20260902T091529Z` | `partial` | false | 3 | 1 | 63519 | 174.5 |
| `vuejs-vue-5884` | codex | 1 | `run-20260902T175857Z` | `strong` | true | 10 | 6 | 285613 | 109.4 |
|  |  | 2 | `run-20260902T180047Z` | `strong` | true | 10 | 6 | 158912 | 94.1 |
|  |  | 3 | `run-20260902T180221Z` | `strong` | true | 12 | 7 | 129467 | 92.1 |
|  |  | 4 | `run-20260902T180353Z` | `strong` | true | 12 | 8 | 290199 | 114.3 |
|  | graphless | 1 | `run-20260903T131459Z` | `partial` | false | 3 | 3 | 80642 | 199.9 |
|  |  | 2 | `run-20260903T131819Z` | `partial` | false | 3 | 3 | 78991 | 175.9 |
|  |  | 3 | `run-20260903T132115Z` | `partial` | false | 3 | 3 | 76427 | 170.1 |
|  |  | 4 | `run-20260903T132405Z` | `partial` | false | 3 | 3 | 61603 | 169.3 |
|  | workspace | 1 | `run-20260902T100700Z` | `partial` | false | 5 | 4 | 90320 | 222.4 |
|  |  | 2 | `run-20260902T101043Z` | `strong` | true | 7 | 6 | 105793 | 236.9 |
|  |  | 3 | `run-20260902T101440Z` | `partial` | false | 6 | 6 | 117924 | 228.7 |
|  |  | 4 | `run-20260902T101829Z` | `partial` | false | 3 | 3 | 82307 | 190.1 |
| `vuejs-vue-6097` | codex | 1 | `run-20260902T180547Z` | `strong` | true | 11 | 6 | 108465 | 94.8 |
|  |  | 2 | `run-20260902T180722Z` | `strong` | true | 9 | 6 | 128130 | 82.9 |
|  |  | 3 | `run-20260902T180845Z` | `strong` | true | 10 | 7 | 97735 | 81.8 |
|  |  | 4 | `run-20260902T181006Z` | `strong` | true | 13 | 7 | 140549 | 94.0 |
|  | graphless | 1 | `run-20260903T132654Z` | `partial` | false | 6 | 3 | 80165 | 193.3 |
|  |  | 2 | `run-20260903T133007Z` | `partial` | false | 8 | 3 | 89744 | 185.5 |
|  |  | 3 | `run-20260903T133313Z` | `partial` | false | 5 | 3 | 74740 | 172.2 |
|  |  | 4 | `run-20260903T133605Z` | `partial` | false | 6 | 3 | 64277 | 153.4 |
|  | workspace | 1 | `run-20260902T091823Z` | `partial` | false | 6 | 6 | 102384 | 250.2 |
|  |  | 2 | `run-20260902T092233Z` | `partial` | false | 6 | 3 | 103600 | 228.7 |
|  |  | 3 | `run-20260902T092622Z` | `partial` | false | 8 | 6 | 93457 | 209.1 |
|  |  | 4 | `run-20260902T092951Z` | `partial` | false | 6 | 4 | 100589 | 207.8 |
| `vuejs-vue-6301` | codex | 1 | `run-20260902T181141Z` | `strong` | true | 22 | 11 | 191612 | 109.5 |
|  |  | 2 | `run-20260902T181330Z` | `strong` | true | 12 | 8 | 100190 | 100.4 |
|  |  | 3 | `run-20260902T181511Z` | `strong` | true | 14 | 6 | 148756 | 122.3 |
|  |  | 4 | `run-20260902T181713Z` | `strong` | true | 12 | 9 | 117656 | 98.3 |
|  | graphless | 1 | `run-20260902T205457Z` | `partial` | false | 5 | 3 | 95141 | 0.0 |
|  |  | 2 | `run-20260902T205806Z` | `partial` | false | 3 | 1 | 79734 | 0.0 |
|  |  | 3 | `run-20260902T210126Z` | `partial` | false | 5 | 2 | 97758 | 0.0 |
|  |  | 4 | `run-20260902T210506Z` | `partial` | false | 5 | 2 | 59599 | 0.0 |
|  | workspace | 1 | `run-20260902T102139Z` | `partial` | false | 6 | 4 | 80822 | 183.7 |
|  |  | 2 | `run-20260902T102442Z` | `partial` | false | 6 | 4 | 83874 | 191.4 |
|  |  | 3 | `run-20260902T103033Z` | `partial` | false | 4 | 3 | 78232 | 170.1 |
|  |  | 4 | `run-20260902T103323Z` | `partial` | false | 5 | 4 | 82572 | 186.8 |
| `vuejs-vue-8528` | codex | 1 | `run-20260902T181851Z` | `strong` | true | 12 | 6 | 119435 | 101.9 |
|  |  | 2 | `run-20260902T182033Z` | `strong` | true | 4 | 1 | 56479 | 60.2 |
|  |  | 3 | `run-20260902T182133Z` | `strong` | true | 6 | 1 | 63520 | 65.4 |
|  |  | 4 | `run-20260902T182239Z` | `strong` | true | 8 | 1 | 86685 | 76.4 |
|  | graphless | 1 | `run-20260903T133839Z` | `partial` | false | 2 | 1 | 46540 | 117.5 |
|  |  | 2 | `run-20260903T134036Z` | `partial` | false | 3 | 1 | 47914 | 122.3 |
|  |  | 3 | `run-20260903T134238Z` | `partial` | false | 4 | 1 | 51367 | 127.8 |
|  |  | 4 | `run-20260903T134446Z` | `partial` | false | 4 | 1 | 59836 | 163.0 |
|  | workspace | 1 | `run-20260902T093319Z` | `partial` | false | 4 | 2 | 68797 | 215.4 |
|  |  | 2 | `run-20260902T093654Z` | `partial` | false | 3 | 1 | 61749 | 162.3 |
|  |  | 3 | `run-20260902T093937Z` | `partial` | false | 2 | 2 | 65770 | 160.8 |
|  |  | 4 | `run-20260902T094218Z` | `partial` | false | 3 | 3 | 64930 | 160.8 |
| `vuejs-vue-9042` | codex | 1 | `run-20260902T182355Z` | `strong` | true | 9 | 7 | 253810 | 139.1 |
|  |  | 2 | `run-20260902T182614Z` | `strong` | true | 10 | 10 | 497959 | 159.2 |
|  |  | 3 | `run-20260902T182854Z` | `strong` | true | 15 | 10 | 443448 | 164.9 |
|  |  | 4 | `run-20260902T183138Z` | `strong` | true | 15 | 11 | 477813 | 168.6 |
|  | graphless | 1 | `run-20260903T134729Z` | `partial` | false | 8 | 4 | 93417 | 204.0 |
|  |  | 2 | `run-20260903T135053Z` | `partial` | false | 6 | 4 | 130176 | 263.0 |
|  |  | 3 | `run-20260903T135516Z` | `partial` | false | 8 | 4 | 127736 | 254.9 |
|  |  | 4 | `run-20260903T135931Z` | `partial` | false | 9 | 5 | 123268 | 259.2 |
|  | workspace | 1 | `run-20260902T103630Z` | `partial` | false | 9 | 5 | 143044 | 265.5 |
|  |  | 2 | `run-20260902T104055Z` | `partial` | false | 7 | 6 | 109787 | 219.1 |
|  |  | 3 | `run-20260902T104434Z` | `partial` | false | 8 | 5 | 144148 | 268.3 |
|  |  | 4 | `run-20260902T104903Z` | `partial` | false | 9 | 6 | 142166 | 274.0 |
| `vuejs-vue-9842` | codex | 1 | `run-20260902T183427Z` | `strong` | true | 11 | 7 | 258736 | 113.5 |
|  |  | 2 | `run-20260902T183620Z` | `strong` | true | 11 | 7 | 314510 | 0.0 |
|  |  | 3 | `run-20260902T184607Z` | `strong` | true | 15 | 7 | 507342 | 162.7 |
|  |  | 4 | `run-20260902T184850Z` | `strong` | true | 20 | 8 | 448333 | 148.7 |
|  | graphless | 1 | `run-20260903T140351Z` | `partial` | false | 12 | 6 | 124637 | 281.8 |
|  |  | 2 | `run-20260903T140930Z` | `partial` | false | 7 | 5 | 118837 | 244.5 |
|  |  | 3 | `run-20260903T141334Z` | `partial` | false | 9 | 6 | 138203 | 263.3 |
|  |  | 4 | `run-20260903T141757Z` | `partial` | false | 11 | 7 | 151648 | 313.3 |
|  | workspace | 1 | `run-20260902T094458Z` | `partial` | false | 9 | 6 | 123346 | 226.4 |
|  |  | 2 | `run-20260902T094845Z` | `partial` | false | 8 | 5 | 110663 | 218.5 |
|  |  | 3 | `run-20260902T095224Z` | `partial` | false | 7 | 5 | 119261 | 245.8 |
|  |  | 4 | `run-20260902T095629Z` | `partial` | false | 12 | 6 | 126494 | 270.7 |

## Limitations

- Graphless is an ablation of Workspace: Qdrant/BM25 indexes are reused and CodeGraph is disabled.
- Flow-token counts exclude indexing and response generation was skipped.
- Invalid attempts remain in campaign ledgers but do not enter four-run metrics.

## Reproduction

- Script: `testing/codeRepoQA/aggregate_three_system_comparison.py`
- workspace: `2026-09-02-workspace-four-runs-complete.json`
- codex: `2026-09-02-codex-efficient-luna-four-runs.json`
- graphless: `2026-09-03-graphless-four-runs-complete.json`
