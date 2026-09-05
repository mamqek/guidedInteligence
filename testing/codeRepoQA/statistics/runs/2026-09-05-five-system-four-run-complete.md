# Five-System CodeRepoQA — 35-Case Four-Run Comparison

## Status and scope

All five conditions contain 35 cases and four valid retrieval runs per case. The three Workspace ablations reuse the same lexical/vector indexes and disable CodeGraph, the adaptive controller, or both.

## Conditions

- Workspace: `gpt-5.6-luna`, qualification-first controller.
- Codex: `gpt-5.6-luna`, `efficient` profile.
- Without CodeGraph: `structural_graph_enabled: false`.
- Without adaptive controller: `adaptive_controller_enabled: false`.
- Without either: both flags are `false`.
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
| Workspace without adaptive controller | 35 | 140 | 0.321 | 0.293 | 0.186 | 0.094 | 0.176 | 0.296 | 0.465 | 0.473 | 0.348 | 0.378 | 0.389 | 0.360 |
| Workspace without CodeGraph or adaptive controller | 35 | 140 | 0.464 | 0.357 | 0.186 | 0.094 | 0.292 | 0.399 | 0.479 | 0.481 | 0.493 | 0.471 | 0.433 | 0.401 |

## Operational summary

| System | Sufficient rate | Mean files | Any Oracle | Full Oracle | Mean flow tokens | Mean seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Workspace | 0.007 | 2.964 | 0.679 | 0.407 | 95315 | 227.5 |
| Codex Luna Efficient | 1.000 | 6.493 | 0.893 | 0.579 | 283913 | 121.7 |
| Workspace without CodeGraph | 0.000 | 2.814 | 0.686 | 0.379 | 82177 | 268.9 |
| Workspace without adaptive controller | 0.000 | 2.664 | 0.629 | 0.350 | 47566 | 127.4 |
| Workspace without CodeGraph or adaptive controller | 0.000 | 2.500 | 0.657 | 0.364 | 46176 | 115.8 |

## Partition breakdown

| Group | System | Cases | Runs | P@5 | R@5 | NDCG@5 | Any hit | Full recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `development` | Workspace | 28 | 112 | 0.188 | 0.474 | 0.392 | 0.670 | 0.366 |
|  | Codex Luna Efficient | 28 | 112 | 0.246 | 0.596 | 0.464 | 0.866 | 0.473 |
|  | Workspace without CodeGraph | 28 | 112 | 0.195 | 0.453 | 0.439 | 0.661 | 0.312 |
|  | Workspace without adaptive controller | 28 | 112 | 0.184 | 0.434 | 0.391 | 0.616 | 0.295 |
|  | Workspace without CodeGraph or adaptive controller | 28 | 112 | 0.173 | 0.398 | 0.385 | 0.607 | 0.268 |
| `final` | Workspace | 7 | 28 | 0.207 | 0.643 | 0.437 | 0.714 | 0.571 |
|  | Codex Luna Efficient | 7 | 28 | 0.314 | 1.000 | 0.700 | 1.000 | 1.000 |
|  | Workspace without CodeGraph | 7 | 28 | 0.221 | 0.714 | 0.560 | 0.786 | 0.643 |
|  | Workspace without adaptive controller | 7 | 28 | 0.193 | 0.589 | 0.382 | 0.679 | 0.571 |
|  | Workspace without CodeGraph or adaptive controller | 7 | 28 | 0.236 | 0.804 | 0.626 | 0.857 | 0.750 |

## Issue-category breakdown

| Group | System | Cases | Runs | P@5 | R@5 | NDCG@5 | Any hit | Full recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `api_behavior_design` | Workspace | 5 | 20 | 0.300 | 0.625 | 0.515 | 0.800 | 0.550 |
|  | Codex Luna Efficient | 5 | 20 | 0.400 | 0.925 | 0.555 | 1.000 | 0.800 |
|  | Workspace without CodeGraph | 5 | 20 | 0.320 | 0.644 | 0.614 | 0.800 | 0.450 |
|  | Workspace without adaptive controller | 5 | 20 | 0.340 | 0.713 | 0.582 | 0.800 | 0.600 |
|  | Workspace without CodeGraph or adaptive controller | 5 | 20 | 0.290 | 0.581 | 0.521 | 0.750 | 0.400 |
| `bug_regression` | Workspace | 5 | 20 | 0.200 | 0.800 | 0.525 | 0.800 | 0.800 |
|  | Codex Luna Efficient | 5 | 20 | 0.210 | 0.850 | 0.518 | 0.850 | 0.850 |
|  | Workspace without CodeGraph | 5 | 20 | 0.170 | 0.650 | 0.522 | 0.650 | 0.650 |
|  | Workspace without adaptive controller | 5 | 20 | 0.140 | 0.500 | 0.387 | 0.500 | 0.500 |
|  | Workspace without CodeGraph or adaptive controller | 5 | 20 | 0.150 | 0.550 | 0.482 | 0.550 | 0.550 |
| `compatibility_versioning` | Workspace | 5 | 20 | 0.100 | 0.500 | 0.225 | 0.500 | 0.500 |
|  | Codex Luna Efficient | 5 | 20 | 0.120 | 0.600 | 0.212 | 0.600 | 0.600 |
|  | Workspace without CodeGraph | 5 | 20 | 0.090 | 0.450 | 0.233 | 0.450 | 0.450 |
|  | Workspace without adaptive controller | 5 | 20 | 0.090 | 0.450 | 0.183 | 0.450 | 0.450 |
|  | Workspace without CodeGraph or adaptive controller | 5 | 20 | 0.090 | 0.450 | 0.266 | 0.450 | 0.450 |
| `feature_enhancement` | Workspace | 5 | 20 | 0.240 | 0.426 | 0.403 | 0.800 | 0.100 |
|  | Codex Luna Efficient | 5 | 20 | 0.370 | 0.547 | 0.547 | 1.000 | 0.200 |
|  | Workspace without CodeGraph | 5 | 20 | 0.310 | 0.509 | 0.532 | 0.850 | 0.200 |
|  | Workspace without adaptive controller | 5 | 20 | 0.240 | 0.408 | 0.404 | 0.800 | 0.050 |
|  | Workspace without CodeGraph or adaptive controller | 5 | 20 | 0.270 | 0.483 | 0.446 | 0.800 | 0.200 |
| `maintenance_refactor` | Workspace | 5 | 20 | 0.120 | 0.390 | 0.344 | 0.600 | 0.350 |
|  | Codex Luna Efficient | 5 | 20 | 0.240 | 0.631 | 0.738 | 0.800 | 0.600 |
|  | Workspace without CodeGraph | 5 | 20 | 0.130 | 0.440 | 0.444 | 0.650 | 0.400 |
|  | Workspace without adaptive controller | 5 | 20 | 0.120 | 0.369 | 0.380 | 0.550 | 0.350 |
|  | Workspace without CodeGraph or adaptive controller | 5 | 20 | 0.110 | 0.365 | 0.349 | 0.550 | 0.350 |
| `performance_memory` | Workspace | 5 | 20 | 0.170 | 0.336 | 0.290 | 0.650 | 0.200 |
|  | Codex Luna Efficient | 5 | 20 | 0.200 | 0.350 | 0.343 | 1.000 | 0.400 |
|  | Workspace without CodeGraph | 5 | 20 | 0.160 | 0.317 | 0.351 | 0.750 | 0.200 |
|  | Workspace without adaptive controller | 5 | 20 | 0.140 | 0.233 | 0.235 | 0.550 | 0.150 |
|  | Workspace without CodeGraph or adaptive controller | 5 | 20 | 0.170 | 0.325 | 0.378 | 0.750 | 0.200 |
| `testing_build_tooling` | Workspace | 5 | 20 | 0.210 | 0.475 | 0.504 | 0.600 | 0.350 |
|  | Codex Luna Efficient | 5 | 20 | 0.280 | 0.833 | 0.667 | 1.000 | 0.600 |
|  | Workspace without CodeGraph | 5 | 20 | 0.220 | 0.525 | 0.545 | 0.650 | 0.300 |
|  | Workspace without adaptive controller | 5 | 20 | 0.230 | 0.583 | 0.551 | 0.750 | 0.350 |
|  | Workspace without CodeGraph or adaptive controller | 5 | 20 | 0.220 | 0.600 | 0.590 | 0.750 | 0.400 |

## Retrieval-topology breakdown

| Group | System | Cases | Runs | P@5 | R@5 | NDCG@5 | Any hit | Full recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `broad_cross_cutting` | Workspace | 2 | 8 | 0.125 | 0.046 | 0.191 | 0.625 | 0.000 |
|  | Codex Luna Efficient | 2 | 8 | 0.275 | 0.099 | 0.323 | 1.000 | 0.000 |
|  | Workspace without CodeGraph | 2 | 8 | 0.175 | 0.061 | 0.244 | 0.875 | 0.000 |
|  | Workspace without adaptive controller | 2 | 8 | 0.125 | 0.048 | 0.196 | 0.500 | 0.000 |
|  | Workspace without CodeGraph or adaptive controller | 2 | 8 | 0.175 | 0.061 | 0.250 | 0.875 | 0.000 |
| `connected_mechanism` | Workspace | 13 | 52 | 0.338 | 0.571 | 0.526 | 0.923 | 0.288 |
|  | Codex Luna Efficient | 13 | 52 | 0.427 | 0.705 | 0.620 | 1.000 | 0.385 |
|  | Workspace without CodeGraph | 13 | 52 | 0.350 | 0.560 | 0.568 | 0.904 | 0.231 |
|  | Workspace without adaptive controller | 13 | 52 | 0.346 | 0.572 | 0.526 | 0.923 | 0.250 |
|  | Workspace without CodeGraph or adaptive controller | 13 | 52 | 0.323 | 0.531 | 0.531 | 0.885 | 0.231 |
| `localized_declarative` | Workspace | 6 | 24 | 0.033 | 0.167 | 0.115 | 0.167 | 0.167 |
|  | Codex Luna Efficient | 6 | 24 | 0.100 | 0.386 | 0.401 | 0.542 | 0.375 |
|  | Workspace without CodeGraph | 6 | 24 | 0.058 | 0.254 | 0.173 | 0.292 | 0.250 |
|  | Workspace without adaptive controller | 6 | 24 | 0.050 | 0.250 | 0.160 | 0.250 | 0.250 |
|  | Workspace without CodeGraph or adaptive controller | 6 | 24 | 0.067 | 0.333 | 0.218 | 0.333 | 0.333 |
| `localized_implementation` | Workspace | 14 | 56 | 0.132 | 0.661 | 0.438 | 0.679 | 0.679 |
|  | Codex Luna Efficient | 14 | 56 | 0.171 | 0.857 | 0.484 | 0.929 | 0.929 |
|  | Workspace without CodeGraph | 14 | 56 | 0.125 | 0.625 | 0.521 | 0.625 | 0.625 |
|  | Workspace without adaptive controller | 14 | 56 | 0.104 | 0.518 | 0.388 | 0.536 | 0.536 |
|  | Workspace without CodeGraph or adaptive controller | 14 | 56 | 0.111 | 0.554 | 0.461 | 0.554 | 0.554 |

## Repository breakdown

| Group | System | Cases | Runs | P@5 | R@5 | NDCG@5 | Any hit | Full recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `microsoft/TypeScript` | Workspace | 11 | 44 | 0.268 | 0.527 | 0.403 | 0.795 | 0.364 |
|  | Codex Luna Efficient | 11 | 44 | 0.359 | 0.701 | 0.516 | 0.932 | 0.477 |
|  | Workspace without CodeGraph | 11 | 44 | 0.300 | 0.549 | 0.478 | 0.795 | 0.318 |
|  | Workspace without adaptive controller | 11 | 44 | 0.264 | 0.491 | 0.370 | 0.750 | 0.295 |
|  | Workspace without CodeGraph or adaptive controller | 11 | 44 | 0.264 | 0.510 | 0.444 | 0.773 | 0.318 |
| `pandas-dev/pandas` | Workspace | 12 | 48 | 0.163 | 0.393 | 0.365 | 0.583 | 0.292 |
|  | Codex Luna Efficient | 12 | 48 | 0.233 | 0.603 | 0.472 | 0.833 | 0.500 |
|  | Workspace without CodeGraph | 12 | 48 | 0.142 | 0.323 | 0.365 | 0.583 | 0.208 |
|  | Workspace without adaptive controller | 12 | 48 | 0.158 | 0.362 | 0.392 | 0.521 | 0.271 |
|  | Workspace without CodeGraph or adaptive controller | 12 | 48 | 0.142 | 0.305 | 0.333 | 0.562 | 0.188 |
| `vuejs/vue` | Workspace | 12 | 48 | 0.150 | 0.604 | 0.436 | 0.667 | 0.562 |
|  | Codex Luna Efficient | 12 | 48 | 0.196 | 0.728 | 0.547 | 0.917 | 0.750 |
|  | Workspace without CodeGraph | 12 | 48 | 0.167 | 0.648 | 0.547 | 0.688 | 0.604 |
|  | Workspace without adaptive controller | 12 | 48 | 0.142 | 0.545 | 0.403 | 0.625 | 0.479 |
|  | Workspace without CodeGraph or adaptive controller | 12 | 48 | 0.158 | 0.625 | 0.524 | 0.646 | 0.583 |

## Per-case results

| Case | Partition | Topology | System | P@5 | R@5 | NDCG@5 | Any-hit runs | Full-recall runs | Mean files | Mean tokens | Mean seconds |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `microsoft-TypeScript-10020` | `development` | `connected_mechanism` | Workspace | 0.200 | 0.500 | 0.273 | 4/4 | 0/4 | 3.00 | 108624 | 250.7 |
|  |  |  | Codex Luna Efficient | 0.200 | 0.500 | 0.445 | 4/4 | 0/4 | 5.25 | 203872 | 98.3 |
|  |  |  | Workspace without CodeGraph | 0.200 | 0.500 | 0.438 | 4/4 | 0/4 | 2.50 | 95172 | 197.0 |
|  |  |  | Workspace without adaptive controller | 0.200 | 0.500 | 0.326 | 4/4 | 0/4 | 3.00 | 53616 | 139.8 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.200 | 0.500 | 0.459 | 4/4 | 0/4 | 1.75 | 54273 | 120.9 |
| `microsoft-TypeScript-10041` | `final` | `localized_implementation` | Workspace | 0.100 | 0.500 | 0.191 | 2/4 | 2/4 | 1.75 | 76983 | 278.7 |
|  |  |  | Codex Luna Efficient | 0.200 | 1.000 | 0.363 | 4/4 | 4/4 | 4.00 | 849162 | 199.3 |
|  |  |  | Workspace without CodeGraph | 0.150 | 0.750 | 0.455 | 3/4 | 3/4 | 1.50 | 59397 | 167.4 |
|  |  |  | Workspace without adaptive controller | 0.050 | 0.250 | 0.096 | 1/4 | 1/4 | 1.50 | 40996 | 130.5 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.200 | 1.000 | 0.606 | 4/4 | 4/4 | 1.50 | 43280 | 128.0 |
| `microsoft-TypeScript-10473` | `final` | `connected_mechanism` | Workspace | 0.400 | 1.000 | 0.629 | 4/4 | 4/4 | 3.00 | 110861 | 281.2 |
|  |  |  | Codex Luna Efficient | 0.400 | 1.000 | 0.600 | 4/4 | 4/4 | 4.50 | 224604 | 115.3 |
|  |  |  | Workspace without CodeGraph | 0.400 | 1.000 | 0.643 | 4/4 | 4/4 | 3.50 | 87216 | 185.2 |
|  |  |  | Workspace without adaptive controller | 0.400 | 1.000 | 0.601 | 4/4 | 4/4 | 3.25 | 55003 | 138.2 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.400 | 1.000 | 0.764 | 4/4 | 4/4 | 3.25 | 53214 | 125.6 |
| `microsoft-TypeScript-16278` | `development` | `connected_mechanism` | Workspace | 0.800 | 0.500 | 0.888 | 4/4 | 0/4 | 5.00 | 121339 | 326.1 |
|  |  |  | Codex Luna Efficient | 1.000 | 0.625 | 1.000 | 4/4 | 0/4 | 6.25 | 200626 | 120.0 |
|  |  |  | Workspace without CodeGraph | 0.950 | 0.594 | 0.967 | 4/4 | 0/4 | 5.00 | 96722 | 201.8 |
|  |  |  | Workspace without adaptive controller | 0.900 | 0.562 | 0.945 | 4/4 | 0/4 | 5.25 | 69018 | 175.1 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.850 | 0.531 | 0.898 | 4/4 | 0/4 | 4.25 | 56742 | 154.5 |
| `microsoft-TypeScript-19074` | `final` | `connected_mechanism` | Workspace | 0.050 | 0.125 | 0.161 | 1/4 | 0/4 | 1.25 | 75507 | 242.6 |
|  |  |  | Codex Luna Efficient | 0.400 | 1.000 | 0.980 | 4/4 | 4/4 | 7.25 | 73227 | 89.1 |
|  |  |  | Workspace without CodeGraph | 0.050 | 0.125 | 0.146 | 1/4 | 0/4 | 1.25 | 60534 | 165.0 |
|  |  |  | Workspace without adaptive controller | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 1.00 | 30380 | 110.2 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.000 | 0.000 | 0.081 | 0/4 | 0/4 | 1.00 | 38970 | 152.9 |
| `microsoft-TypeScript-24625` | `development` | `localized_implementation` | Workspace | 0.200 | 1.000 | 0.419 | 4/4 | 4/4 | 2.75 | 101704 | 239.5 |
|  |  |  | Codex Luna Efficient | 0.200 | 1.000 | 0.383 | 4/4 | 4/4 | 4.75 | 175100 | 123.4 |
|  |  |  | Workspace without CodeGraph | 0.200 | 1.000 | 0.606 | 4/4 | 4/4 | 2.00 | 76690 | 184.5 |
|  |  |  | Workspace without adaptive controller | 0.200 | 1.000 | 0.399 | 4/4 | 4/4 | 3.25 | 46952 | 148.5 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.150 | 0.750 | 0.343 | 3/4 | 3/4 | 2.25 | 43672 | 155.5 |
| `microsoft-TypeScript-2953` | `development` | `localized_declarative` | Workspace | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 1.25 | 63998 | 165.7 |
|  |  |  | Codex Luna Efficient | 0.050 | 0.250 | 0.125 | 1/4 | 1/4 | 6.75 | 297974 | 152.6 |
|  |  |  | Workspace without CodeGraph | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 1.50 | 66906 | 264.6 |
|  |  |  | Workspace without adaptive controller | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 2.25 | 34996 | 110.9 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 1.00 | 36768 | 95.1 |
| `microsoft-TypeScript-35468` | `development` | `connected_mechanism` | Workspace | 0.500 | 0.625 | 0.567 | 4/4 | 2/4 | 4.75 | 130336 | 295.2 |
|  |  |  | Codex Luna Efficient | 0.400 | 0.500 | 0.360 | 4/4 | 0/4 | 6.50 | 968002 | 134.6 |
|  |  |  | Workspace without CodeGraph | 0.500 | 0.625 | 0.682 | 4/4 | 0/4 | 5.50 | 108560 | 0.0 |
|  |  |  | Workspace without adaptive controller | 0.400 | 0.500 | 0.444 | 4/4 | 0/4 | 4.25 | 59500 | 120.6 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.400 | 0.500 | 0.496 | 4/4 | 0/4 | 5.25 | 59704 | 170.0 |
| `microsoft-TypeScript-45713` | `development` | `connected_mechanism` | Workspace | 0.300 | 0.214 | 0.446 | 4/4 | 0/4 | 2.50 | 108377 | 261.3 |
|  |  |  | Codex Luna Efficient | 0.700 | 0.500 | 0.786 | 4/4 | 0/4 | 5.50 | 310299 | 127.8 |
|  |  |  | Workspace without CodeGraph | 0.500 | 0.357 | 0.621 | 4/4 | 0/4 | 2.75 | 83090 | 210.0 |
|  |  |  | Workspace without adaptive controller | 0.350 | 0.250 | 0.457 | 4/4 | 0/4 | 2.50 | 50087 | 205.0 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.350 | 0.250 | 0.426 | 4/4 | 0/4 | 2.50 | 45095 | 157.9 |
| `microsoft-TypeScript-46770` | `development` | `connected_mechanism` | Workspace | 0.200 | 1.000 | 0.438 | 4/4 | 4/4 | 2.75 | 124925 | 326.2 |
|  |  |  | Codex Luna Efficient | 0.200 | 1.000 | 0.343 | 4/4 | 4/4 | 5.25 | 646619 | 181.3 |
|  |  |  | Workspace without CodeGraph | 0.150 | 0.750 | 0.287 | 3/4 | 3/4 | 5.25 | 96716 | 226.6 |
|  |  |  | Workspace without adaptive controller | 0.200 | 1.000 | 0.419 | 4/4 | 4/4 | 3.75 | 56768 | 201.7 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.150 | 0.750 | 0.399 | 3/4 | 3/4 | 4.25 | 59492 | 210.9 |
| `microsoft-TypeScript-52695` | `development` | `connected_mechanism` | Workspace | 0.200 | 0.333 | 0.416 | 4/4 | 0/4 | 3.00 | 127062 | 314.8 |
|  |  |  | Codex Luna Efficient | 0.200 | 0.333 | 0.287 | 4/4 | 0/4 | 4.50 | 315889 | 140.7 |
|  |  |  | Workspace without CodeGraph | 0.200 | 0.333 | 0.416 | 4/4 | 0/4 | 2.75 | 87417 | 223.4 |
|  |  |  | Workspace without adaptive controller | 0.200 | 0.333 | 0.378 | 4/4 | 0/4 | 3.25 | 58090 | 182.4 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.200 | 0.333 | 0.416 | 4/4 | 0/4 | 1.50 | 48019 | 184.1 |
| `pandas-dev-pandas-10068` | `development` | `localized_implementation` | Workspace | 0.200 | 1.000 | 0.475 | 4/4 | 4/4 | 4.50 | 95499 | 207.9 |
|  |  |  | Codex Luna Efficient | 0.200 | 1.000 | 0.501 | 4/4 | 4/4 | 6.00 | 278654 | 131.5 |
|  |  |  | Workspace without CodeGraph | 0.050 | 0.250 | 0.183 | 1/4 | 1/4 | 1.75 | 71563 | 0.0 |
|  |  |  | Workspace without adaptive controller | 0.100 | 0.500 | 0.334 | 2/4 | 2/4 | 2.50 | 39908 | 102.5 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 1.00 | 38887 | 87.8 |
| `pandas-dev-pandas-10150` | `final` | `connected_mechanism` | Workspace | 0.350 | 0.875 | 0.709 | 4/4 | 3/4 | 3.75 | 95908 | 204.8 |
|  |  |  | Codex Luna Efficient | 0.400 | 1.000 | 0.510 | 4/4 | 4/4 | 4.50 | 262136 | 123.8 |
|  |  |  | Workspace without CodeGraph | 0.250 | 0.625 | 0.650 | 4/4 | 1/4 | 3.25 | 93077 | 193.2 |
|  |  |  | Workspace without adaptive controller | 0.400 | 1.000 | 0.793 | 4/4 | 4/4 | 3.25 | 45163 | 114.3 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.250 | 0.625 | 0.559 | 4/4 | 1/4 | 2.50 | 44421 | 100.4 |
| `pandas-dev-pandas-14942` | `development` | `connected_mechanism` | Workspace | 0.400 | 0.333 | 0.463 | 4/4 | 0/4 | 3.75 | 129212 | 240.7 |
|  |  |  | Codex Luna Efficient | 0.450 | 0.375 | 0.597 | 4/4 | 0/4 | 6.00 | 487512 | 164.7 |
|  |  |  | Workspace without CodeGraph | 0.250 | 0.208 | 0.415 | 4/4 | 0/4 | 3.75 | 130318 | 197.5 |
|  |  |  | Workspace without adaptive controller | 0.400 | 0.333 | 0.497 | 4/4 | 0/4 | 3.00 | 57764 | 120.6 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.300 | 0.250 | 0.487 | 4/4 | 0/4 | 3.25 | 70776 | 119.0 |
| `pandas-dev-pandas-16499` | `development` | `localized_implementation` | Workspace | 0.200 | 1.000 | 1.000 | 4/4 | 4/4 | 1.00 | 88571 | 184.4 |
|  |  |  | Codex Luna Efficient | 0.200 | 1.000 | 0.631 | 4/4 | 4/4 | 2.50 | 91718 | 81.5 |
|  |  |  | Workspace without CodeGraph | 0.200 | 1.000 | 1.000 | 4/4 | 4/4 | 1.25 | 67748 | 138.0 |
|  |  |  | Workspace without adaptive controller | 0.200 | 1.000 | 1.000 | 4/4 | 4/4 | 1.00 | 39202 | 102.9 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.200 | 1.000 | 1.000 | 4/4 | 4/4 | 1.00 | 36161 | 86.3 |
| `pandas-dev-pandas-16764` | `development` | `broad_cross_cutting` | Workspace | 0.050 | 0.015 | 0.042 | 1/4 | 0/4 | 1.75 | 84468 | 221.4 |
|  |  |  | Codex Luna Efficient | 0.150 | 0.044 | 0.106 | 4/4 | 0/4 | 18.50 | 287425 | 134.8 |
|  |  |  | Workspace without CodeGraph | 0.150 | 0.044 | 0.149 | 3/4 | 0/4 | 2.00 | 81805 | 183.5 |
|  |  |  | Workspace without adaptive controller | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 1.00 | 42691 | 118.6 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.150 | 0.044 | 0.160 | 3/4 | 0/4 | 1.75 | 40970 | 90.9 |
| `pandas-dev-pandas-22698` | `development` | `localized_implementation` | Workspace | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 2.75 | 97283 | 225.5 |
|  |  |  | Codex Luna Efficient | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 4.00 | 180673 | 113.9 |
|  |  |  | Workspace without CodeGraph | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 2.25 | 69336 | 163.2 |
|  |  |  | Workspace without adaptive controller | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 2.25 | 49018 | 127.6 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 2.00 | 37374 | 89.0 |
| `pandas-dev-pandas-22872` | `development` | `localized_declarative` | Workspace | 0.000 | 0.000 | 0.040 | 0/4 | 0/4 | 1.00 | 100792 | 234.7 |
|  |  |  | Codex Luna Efficient | 0.000 | 0.000 | 0.475 | 0/4 | 0/4 | 8.00 | 136366 | 121.3 |
|  |  |  | Workspace without CodeGraph | 0.000 | 0.000 | 0.126 | 0/4 | 0/4 | 3.50 | 100269 | 236.0 |
|  |  |  | Workspace without adaptive controller | 0.000 | 0.000 | 0.146 | 0/4 | 0/4 | 1.50 | 50620 | 142.2 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.000 | 0.000 | 0.060 | 0/4 | 0/4 | 2.00 | 48680 | 112.4 |
| `pandas-dev-pandas-25183` | `development` | `localized_implementation` | Workspace | 0.000 | 0.000 | 0.099 | 0/4 | 0/4 | 2.25 | 125116 | 257.5 |
|  |  |  | Codex Luna Efficient | 0.200 | 1.000 | 0.363 | 4/4 | 4/4 | 6.75 | 418598 | 152.8 |
|  |  |  | Workspace without CodeGraph | 0.000 | 0.000 | 0.145 | 0/4 | 0/4 | 2.25 | 98820 | 201.1 |
|  |  |  | Workspace without adaptive controller | 0.000 | 0.000 | 0.159 | 0/4 | 0/4 | 2.50 | 50166 | 110.7 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.000 | 0.000 | 0.099 | 0/4 | 0/4 | 2.25 | 50913 | 102.5 |
| `pandas-dev-pandas-32289` | `development` | `localized_implementation` | Workspace | 0.000 | 0.000 | 0.159 | 0/4 | 0/4 | 1.00 | 62958 | 176.6 |
|  |  |  | Codex Luna Efficient | 0.200 | 1.000 | 0.580 | 4/4 | 4/4 | 4.50 | 254060 | 119.2 |
|  |  |  | Workspace without CodeGraph | 0.000 | 0.000 | 0.220 | 0/4 | 0/4 | 1.75 | 56003 | 131.8 |
|  |  |  | Workspace without adaptive controller | 0.000 | 0.000 | 0.220 | 0/4 | 0/4 | 1.25 | 32136 | 90.6 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.000 | 0.000 | 0.242 | 0/4 | 0/4 | 1.50 | 36022 | 80.6 |
| `pandas-dev-pandas-35925` | `development` | `broad_cross_cutting` | Workspace | 0.200 | 0.077 | 0.339 | 4/4 | 0/4 | 1.00 | 42513 | 120.9 |
|  |  |  | Codex Luna Efficient | 0.400 | 0.154 | 0.539 | 4/4 | 0/4 | 4.75 | 86356 | 76.4 |
|  |  |  | Workspace without CodeGraph | 0.200 | 0.077 | 0.339 | 4/4 | 0/4 | 1.25 | 58069 | 162.7 |
|  |  |  | Workspace without adaptive controller | 0.250 | 0.096 | 0.393 | 4/4 | 0/4 | 1.25 | 28592 | 81.7 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.200 | 0.077 | 0.339 | 4/4 | 0/4 | 1.00 | 21226 | 72.8 |
| `pandas-dev-pandas-36617` | `development` | `localized_declarative` | Workspace | 0.150 | 0.750 | 0.399 | 3/4 | 3/4 | 1.50 | 74026 | 188.0 |
|  |  |  | Codex Luna Efficient | 0.200 | 1.000 | 0.695 | 4/4 | 4/4 | 13.75 | 307547 | 169.2 |
|  |  |  | Workspace without CodeGraph | 0.200 | 1.000 | 0.606 | 4/4 | 4/4 | 1.75 | 73001 | 163.9 |
|  |  |  | Workspace without adaptive controller | 0.150 | 0.750 | 0.455 | 3/4 | 3/4 | 1.00 | 39228 | 106.8 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.200 | 1.000 | 0.606 | 4/4 | 4/4 | 1.00 | 38576 | 86.8 |
| `pandas-dev-pandas-4542` | `development` | `connected_mechanism` | Workspace | 0.400 | 0.667 | 0.650 | 4/4 | 0/4 | 2.75 | 103909 | 204.7 |
|  |  |  | Codex Luna Efficient | 0.400 | 0.667 | 0.665 | 4/4 | 0/4 | 7.25 | 217524 | 115.6 |
|  |  |  | Workspace without CodeGraph | 0.400 | 0.667 | 0.549 | 4/4 | 0/4 | 3.75 | 95099 | 222.2 |
|  |  |  | Workspace without adaptive controller | 0.400 | 0.667 | 0.709 | 4/4 | 0/4 | 3.25 | 60386 | 120.4 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.400 | 0.667 | 0.444 | 4/4 | 0/4 | 3.75 | 51906 | 109.6 |
| `vuejs-vue-10004` | `development` | `localized_implementation` | Workspace | 0.000 | 0.000 | 0.056 | 0/4 | 0/4 | 7.00 | 132152 | 252.8 |
|  |  |  | Codex Luna Efficient | 0.000 | 0.000 | 0.000 | 4/4 | 4/4 | 13.50 | 441284 | 157.8 |
|  |  |  | Workspace without CodeGraph | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 7.25 | 127342 | 218.6 |
|  |  |  | Workspace without adaptive controller | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 5.75 | 66626 | 152.8 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 5.75 | 65250 | 133.8 |
| `vuejs-vue-10519` | `development` | `localized_implementation` | Workspace | 0.200 | 1.000 | 0.521 | 4/4 | 4/4 | 3.00 | 77737 | 203.8 |
|  |  |  | Codex Luna Efficient | 0.200 | 1.000 | 0.803 | 4/4 | 4/4 | 5.75 | 198564 | 98.0 |
|  |  |  | Workspace without CodeGraph | 0.200 | 1.000 | 0.826 | 4/4 | 4/4 | 1.00 | 54695 | 121.0 |
|  |  |  | Workspace without adaptive controller | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 1.00 | 42989 | 114.7 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.200 | 1.000 | 0.826 | 4/4 | 4/4 | 1.00 | 39742 | 86.3 |
| `vuejs-vue-10803` | `development` | `localized_implementation` | Workspace | 0.200 | 1.000 | 1.000 | 4/4 | 4/4 | 2.75 | 79862 | 201.2 |
|  |  |  | Codex Luna Efficient | 0.200 | 1.000 | 0.562 | 4/4 | 4/4 | 5.75 | 304026 | 123.0 |
|  |  |  | Workspace without CodeGraph | 0.200 | 1.000 | 0.957 | 4/4 | 4/4 | 1.75 | 70612 | 0.0 |
|  |  |  | Workspace without adaptive controller | 0.200 | 1.000 | 1.000 | 4/4 | 4/4 | 2.00 | 37818 | 109.8 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.150 | 0.750 | 0.819 | 3/4 | 3/4 | 1.75 | 41751 | 96.4 |
| `vuejs-vue-11718` | `development` | `connected_mechanism` | Workspace | 0.300 | 0.500 | 0.543 | 3/4 | 0/4 | 2.25 | 58299 | 177.0 |
|  |  |  | Codex Luna Efficient | 0.400 | 0.667 | 0.765 | 4/4 | 0/4 | 5.00 | 138336 | 92.3 |
|  |  |  | Workspace without CodeGraph | 0.300 | 0.500 | 0.574 | 3/4 | 0/4 | 1.75 | 45531 | 121.1 |
|  |  |  | Workspace without adaptive controller | 0.400 | 0.667 | 0.735 | 4/4 | 0/4 | 2.75 | 41386 | 107.3 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.300 | 0.500 | 0.574 | 3/4 | 0/4 | 2.00 | 38720 | 104.1 |
| `vuejs-vue-11782` | `final` | `localized_declarative` | Workspace | 0.050 | 0.250 | 0.250 | 1/4 | 1/4 | 3.25 | 71765 | 202.9 |
|  |  |  | Codex Luna Efficient | 0.200 | 1.000 | 1.000 | 4/4 | 4/4 | 7.25 | 145754 | 93.9 |
|  |  |  | Workspace without CodeGraph | 0.100 | 0.500 | 0.250 | 2/4 | 2/4 | 4.25 | 71042 | 3769.8 |
|  |  |  | Workspace without adaptive controller | 0.150 | 0.750 | 0.358 | 3/4 | 3/4 | 4.50 | 43134 | 123.6 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.200 | 1.000 | 0.640 | 4/4 | 4/4 | 4.50 | 45810 | 97.9 |
| `vuejs-vue-13052` | `development` | `localized_declarative` | Workspace | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 1.25 | 65717 | 178.9 |
|  |  |  | Codex Luna Efficient | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 2.25 | 78695 | 70.5 |
|  |  |  | Workspace without CodeGraph | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 1.25 | 55350 | 154.4 |
|  |  |  | Workspace without adaptive controller | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 1.00 | 35304 | 96.0 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 1.25 | 36799 | 83.9 |
| `vuejs-vue-5884` | `development` | `localized_implementation` | Workspace | 0.150 | 0.750 | 0.461 | 4/4 | 4/4 | 4.75 | 99086 | 219.5 |
|  |  |  | Codex Luna Efficient | 0.200 | 1.000 | 0.521 | 4/4 | 4/4 | 6.75 | 216048 | 102.4 |
|  |  |  | Workspace without CodeGraph | 0.200 | 1.000 | 0.701 | 4/4 | 4/4 | 3.00 | 74416 | 178.8 |
|  |  |  | Workspace without adaptive controller | 0.200 | 1.000 | 0.614 | 4/4 | 4/4 | 2.75 | 50240 | 135.3 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.200 | 1.000 | 0.708 | 4/4 | 4/4 | 2.75 | 43784 | 100.8 |
| `vuejs-vue-6097` | `final` | `connected_mechanism` | Workspace | 0.300 | 0.750 | 0.648 | 4/4 | 2/4 | 4.75 | 100008 | 223.9 |
|  |  |  | Codex Luna Efficient | 0.400 | 1.000 | 0.724 | 4/4 | 4/4 | 6.50 | 118720 | 88.4 |
|  |  |  | Workspace without CodeGraph | 0.400 | 1.000 | 1.000 | 4/4 | 4/4 | 3.00 | 77232 | 176.1 |
|  |  |  | Workspace without adaptive controller | 0.250 | 0.625 | 0.528 | 4/4 | 1/4 | 3.75 | 54870 | 127.7 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.400 | 1.000 | 0.904 | 4/4 | 4/4 | 3.00 | 45748 | 100.7 |
| `vuejs-vue-6301` | `development` | `localized_declarative` | Workspace | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 3.75 | 81375 | 183.0 |
|  |  |  | Codex Luna Efficient | 0.150 | 0.068 | 0.112 | 4/4 | 0/4 | 8.50 | 139554 | 107.6 |
|  |  |  | Workspace without CodeGraph | 0.050 | 0.023 | 0.053 | 1/4 | 0/4 | 2.00 | 83058 | 0.0 |
|  |  |  | Workspace without adaptive controller | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 2.25 | 49069 | 120.1 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.000 | 0.000 | 0.000 | 0/4 | 0/4 | 2.50 | 49139 | 107.0 |
| `vuejs-vue-8528` | `development` | `localized_implementation` | Workspace | 0.200 | 1.000 | 0.783 | 4/4 | 4/4 | 2.00 | 65312 | 174.8 |
|  |  |  | Codex Luna Efficient | 0.200 | 1.000 | 1.000 | 4/4 | 4/4 | 2.25 | 81530 | 76.0 |
|  |  |  | Workspace without CodeGraph | 0.200 | 1.000 | 1.000 | 4/4 | 4/4 | 1.00 | 51414 | 132.6 |
|  |  |  | Workspace without adaptive controller | 0.200 | 1.000 | 0.908 | 4/4 | 4/4 | 1.25 | 35285 | 101.0 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.150 | 0.750 | 0.658 | 3/4 | 3/4 | 1.25 | 35031 | 91.0 |
| `vuejs-vue-9042` | `development` | `localized_implementation` | Workspace | 0.200 | 1.000 | 0.497 | 4/4 | 4/4 | 5.50 | 134786 | 256.7 |
|  |  |  | Codex Luna Efficient | 0.200 | 1.000 | 0.352 | 4/4 | 4/4 | 9.50 | 418258 | 157.9 |
|  |  |  | Workspace without CodeGraph | 0.150 | 0.750 | 0.425 | 3/4 | 3/4 | 4.25 | 118649 | 245.3 |
|  |  |  | Workspace without adaptive controller | 0.200 | 1.000 | 0.399 | 4/4 | 4/4 | 3.75 | 52450 | 125.8 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.100 | 0.500 | 0.327 | 2/4 | 2/4 | 4.00 | 57122 | 122.6 |
| `vuejs-vue-9842` | `final` | `localized_implementation` | Workspace | 0.200 | 1.000 | 0.474 | 4/4 | 4/4 | 5.50 | 119941 | 240.3 |
|  |  |  | Codex Luna Efficient | 0.200 | 1.000 | 0.723 | 4/4 | 4/4 | 7.25 | 382230 | 106.2 |
|  |  |  | Workspace without CodeGraph | 0.200 | 1.000 | 0.777 | 4/4 | 4/4 | 6.00 | 133331 | 275.7 |
|  |  |  | Workspace without adaptive controller | 0.100 | 0.500 | 0.301 | 3/4 | 3/4 | 5.50 | 65357 | 144.5 |
|  |  |  | Workspace without CodeGraph or adaptive controller | 0.200 | 1.000 | 0.826 | 4/4 | 4/4 | 6.25 | 62107 | 135.2 |

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
|  | graphless_no_controller | 1 | `run-20260904T231103Z` | `partial` | false | 3 | 1 | 62075 | 164.1 |
|  |  | 2 | `run-20260904T231347Z` | `partial` | false | 5 | 2 | 46096 | 98.0 |
|  |  | 3 | `run-20260904T231613Z` | `partial` | false | 7 | 3 | 63458 | 117.0 |
|  |  | 4 | `run-20260904T231810Z` | `partial` | false | 3 | 1 | 45463 | 104.4 |
|  | no_controller | 1 | `run-20260904T142154Z` | `partial` | false | 7 | 3 | 55258 | 130.9 |
|  |  | 2 | `run-20260904T142405Z` | `partial` | false | 6 | 3 | 48195 | 126.1 |
|  |  | 3 | `run-20260904T142611Z` | `partial` | false | 8 | 4 | 58089 | 162.8 |
|  |  | 4 | `run-20260904T142854Z` | `partial` | false | 5 | 2 | 52920 | 139.2 |
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
|  | graphless_no_controller | 1 | `run-20260904T231954Z` | `partial` | false | 1 | 1 | 38030 | 158.0 |
|  |  | 2 | `run-20260904T232232Z` | `partial` | false | 1 | 1 | 40302 | 92.0 |
|  |  | 3 | `run-20260904T232404Z` | `partial` | false | 3 | 2 | 42395 | 106.4 |
|  |  | 4 | `run-20260904T232551Z` | `partial` | false | 3 | 2 | 52391 | 155.7 |
|  | no_controller | 1 | `run-20260904T143113Z` | `partial` | false | 1 | 1 | 38339 | 157.3 |
|  |  | 2 | `run-20260904T143546Z` | `partial` | false | 1 | 1 | 41072 | 116.2 |
|  |  | 3 | `run-20260904T143742Z` | `partial` | false | 2 | 2 | 41500 | 119.2 |
|  |  | 4 | `run-20260904T143941Z` | `partial` | false | 2 | 2 | 43073 | 129.2 |
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
|  | graphless_no_controller | 1 | `run-20260904T233013Z` | `partial` | false | 5 | 4 | 51645 | 114.6 |
|  |  | 2 | `run-20260904T233207Z` | `partial` | false | 4 | 3 | 49603 | 108.6 |
|  |  | 3 | `run-20260904T233356Z` | `partial` | false | 5 | 3 | 59199 | 117.1 |
|  |  | 4 | `run-20260904T233553Z` | `partial` | false | 6 | 3 | 52410 | 162.0 |
|  | no_controller | 1 | `run-20260904T144150Z` | `partial` | false | 5 | 3 | 46617 | 172.4 |
|  |  | 2 | `run-20260904T144442Z` | `partial` | false | 7 | 3 | 57753 | 119.2 |
|  |  | 3 | `run-20260904T144642Z` | `partial` | false | 7 | 3 | 57252 | 127.4 |
|  |  | 4 | `run-20260904T144849Z` | `partial` | false | 9 | 4 | 58391 | 133.7 |
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
|  | graphless_no_controller | 1 | `run-20260904T233835Z` | `partial` | false | 9 | 5 | 56993 | 187.9 |
|  |  | 2 | `run-20260904T234143Z` | `partial` | false | 8 | 4 | 60318 | 123.1 |
|  |  | 3 | `run-20260904T234346Z` | `partial` | false | 9 | 5 | 56797 | 104.4 |
|  |  | 4 | `run-20260904T234531Z` | `partial` | false | 6 | 3 | 52861 | 202.5 |
|  | no_controller | 1 | `run-20260904T145103Z` | `partial` | false | 14 | 6 | 66131 | 206.6 |
|  |  | 2 | `run-20260904T145631Z` | `partial` | false | 13 | 4 | 68096 | 165.8 |
|  |  | 3 | `run-20260904T145917Z` | `partial` | false | 14 | 5 | 72271 | 143.3 |
|  |  | 4 | `run-20260904T150141Z` | `partial` | false | 14 | 6 | 69575 | 184.9 |
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
|  | graphless_no_controller | 1 | `run-20260904T234854Z` | `partial` | false | 1 | 1 | 36448 | 247.9 |
|  |  | 2 | `run-20260904T235557Z` | `partial` | false | 1 | 1 | 31401 | 87.7 |
|  |  | 3 | `run-20260904T235725Z` | `partial` | false | 1 | 1 | 44663 | 136.4 |
|  |  | 4 | `run-20260904T235942Z` | `partial` | false | 1 | 1 | 43367 | 139.8 |
|  | no_controller | 1 | `run-20260904T150806Z` | `partial` | false | 1 | 1 | 29456 | 108.6 |
|  |  | 2 | `run-20260904T151105Z` | `partial` | false | 1 | 1 | 26863 | 98.8 |
|  |  | 3 | `run-20260904T151243Z` | `partial` | false | 1 | 1 | 34915 | 128.6 |
|  |  | 4 | `run-20260904T151452Z` | `partial` | false | 1 | 1 | 30286 | 104.8 |
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
|  | graphless_no_controller | 1 | `run-20260905T000201Z` | `partial` | false | 2 | 1 | 39097 | 239.5 |
|  |  | 2 | `run-20260905T000601Z` | `partial` | false | 3 | 3 | 47910 | 128.7 |
|  |  | 3 | `run-20260905T000809Z` | `partial` | false | 3 | 3 | 42384 | 129.9 |
|  |  | 4 | `run-20260905T001019Z` | `partial` | false | 3 | 2 | 45299 | 123.9 |
|  | no_controller | 1 | `run-20260904T151637Z` | `partial` | false | 5 | 3 | 52570 | 197.1 |
|  |  | 2 | `run-20260904T151954Z` | `partial` | false | 4 | 4 | 42232 | 113.5 |
|  |  | 3 | `run-20260904T152149Z` | `partial` | false | 4 | 3 | 46205 | 164.8 |
|  |  | 4 | `run-20260904T152433Z` | `partial` | false | 4 | 3 | 46801 | 118.4 |
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
|  | graphless_no_controller | 1 | `run-20260904T231103Z` | `partial` | false | 1 | 1 | 36648 | 126.9 |
|  |  | 2 | `run-20260904T231310Z` | `partial` | false | 1 | 1 | 35719 | 77.5 |
|  |  | 3 | `run-20260904T231550Z` | `partial` | false | 1 | 1 | 36069 | 88.9 |
|  |  | 4 | `run-20260904T231720Z` | `partial` | false | 1 | 1 | 38638 | 87.2 |
|  | no_controller | 1 | `run-20260904T153036Z` | `partial` | false | 1 | 1 | 33797 | 101.2 |
|  |  | 2 | `run-20260904T153419Z` | `partial` | false | 4 | 4 | 37139 | 127.4 |
|  |  | 3 | `run-20260904T153626Z` | `partial` | false | 1 | 1 | 32860 | 103.5 |
|  |  | 4 | `run-20260904T153810Z` | `partial` | false | 3 | 3 | 36186 | 111.6 |
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
|  | graphless_no_controller | 1 | `run-20260904T231846Z` | `partial` | false | 8 | 5 | 57501 | 203.0 |
|  |  | 2 | `run-20260904T232306Z` | `partial` | false | 9 | 7 | 64425 | 139.3 |
|  |  | 3 | `run-20260904T232526Z` | `partial` | false | 7 | 5 | 58530 | 215.0 |
|  |  | 4 | `run-20260904T232900Z` | `partial` | false | 5 | 4 | 58362 | 122.6 |
|  | no_controller | 1 | `run-20260904T134949Z` | `partial` | false | 7 | 6 | 61611 | 0.0 |
|  |  | 2 | `run-20260904T135451Z` | `partial` | false | 7 | 5 | 58249 | 0.0 |
|  |  | 3 | `run-20260904T154002Z` | `partial` | false | 5 | 3 | 61254 | 303.6 |
|  |  | 4 | `run-20260904T154505Z` | `partial` | false | 5 | 3 | 56887 | 178.9 |
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
|  | graphless_no_controller | 1 | `run-20260904T233103Z` | `partial` | false | 4 | 3 | 46867 | 221.6 |
|  |  | 2 | `run-20260904T233445Z` | `partial` | false | 4 | 3 | 46241 | 130.8 |
|  |  | 3 | `run-20260904T233656Z` | `partial` | false | 2 | 2 | 38301 | 164.6 |
|  |  | 4 | `run-20260904T233941Z` | `partial` | false | 2 | 2 | 48972 | 114.5 |
|  | no_controller | 1 | `run-20260904T154804Z` | `partial` | false | 5 | 3 | 55683 | 332.5 |
|  |  | 2 | `run-20260904T155337Z` | `partial` | false | 6 | 2 | 50820 | 158.0 |
|  |  | 3 | `run-20260904T155615Z` | `partial` | false | 4 | 2 | 38215 | 143.8 |
|  |  | 4 | `run-20260904T155838Z` | `partial` | false | 6 | 3 | 55631 | 185.8 |
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
|  | graphless_no_controller | 1 | `run-20260904T234135Z` | `partial` | false | 6 | 5 | 62152 | 259.7 |
|  |  | 2 | `run-20260904T234555Z` | `partial` | false | 3 | 3 | 55407 | 272.1 |
|  |  | 3 | `run-20260904T235028Z` | `partial` | false | 5 | 4 | 58216 | 152.5 |
|  |  | 4 | `run-20260904T235300Z` | `partial` | false | 8 | 5 | 62193 | 159.3 |
|  | no_controller | 1 | `run-20260904T160145Z` | `partial` | false | 9 | 4 | 62707 | 338.7 |
|  |  | 2 | `run-20260904T185535Z` | `partial` | false | 4 | 4 | 45802 | 132.9 |
|  |  | 3 | `run-20260904T185748Z` | `partial` | false | 4 | 1 | 56559 | 163.4 |
|  |  | 4 | `run-20260904T190032Z` | `partial` | false | 8 | 6 | 62006 | 172.0 |
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
|  | graphless_no_controller | 1 | `run-20260904T235539Z` | `partial` | false | 4 | 2 | 52269 | 322.2 |
|  |  | 2 | `run-20260905T000101Z` | `partial` | false | 6 | 2 | 54058 | 162.2 |
|  |  | 3 | `run-20260905T000510Z` | `partial` | false | 3 | 1 | 41972 | 124.3 |
|  |  | 4 | `run-20260905T000821Z` | `partial` | false | 3 | 1 | 43777 | 127.7 |
|  | no_controller | 1 | `run-20260904T190443Z` | `partial` | false | 5 | 2 | 49563 | 211.7 |
|  |  | 2 | `run-20260904T190815Z` | `partial` | false | 7 | 4 | 59686 | 185.3 |
|  |  | 3 | `run-20260904T191120Z` | `partial` | false | 7 | 4 | 57315 | 160.3 |
|  |  | 4 | `run-20260904T191400Z` | `partial` | false | 10 | 3 | 65796 | 172.3 |
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
|  | graphless_no_controller | 1 | `run-20260905T001224Z` | `partial` | false | 1 | 1 | 35133 | 89.1 |
|  |  | 2 | `run-20260905T001354Z` | `partial` | false | 2 | 1 | 38235 | 89.4 |
|  |  | 3 | `run-20260905T001522Z` | `partial` | false | 2 | 1 | 40766 | 93.1 |
|  |  | 4 | `run-20260905T001655Z` | `partial` | false | 3 | 1 | 41415 | 79.5 |
|  | no_controller | 1 | `run-20260904T191654Z` | `partial` | false | 3 | 3 | 39632 | 102.3 |
|  |  | 2 | `run-20260904T191836Z` | `partial` | false | 4 | 3 | 42108 | 105.3 |
|  |  | 3 | `run-20260904T221251Z` | `partial` | false | 3 | 2 | 39185 | 103.9 |
|  |  | 4 | `run-20260904T221434Z` | `partial` | false | 3 | 2 | 38705 | 98.5 |
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
|  | graphless_no_controller | 1 | `run-20260905T001815Z` | `partial` | false | 2 | 2 | 41681 | 97.7 |
|  |  | 2 | `run-20260905T001952Z` | `partial` | false | 3 | 3 | 48449 | 108.3 |
|  |  | 3 | `run-20260905T002140Z` | `partial` | false | 2 | 2 | 39768 | 85.4 |
|  |  | 4 | `run-20260905T002306Z` | `partial` | false | 4 | 3 | 47785 | 110.1 |
|  | no_controller | 1 | `run-20260904T190445Z` | `partial` | false | 4 | 4 | 50454 | 121.6 |
|  |  | 2 | `run-20260904T190645Z` | `partial` | false | 3 | 3 | 42047 | 113.6 |
|  |  | 3 | `run-20260904T190839Z` | `partial` | false | 2 | 2 | 40221 | 108.6 |
|  |  | 4 | `run-20260904T191028Z` | `partial` | false | 4 | 4 | 47929 | 113.3 |
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
|  | graphless_no_controller | 1 | `run-20260905T002456Z` | `partial` | false | 6 | 3 | 72683 | 112.2 |
|  |  | 2 | `run-20260905T002648Z` | `partial` | false | 7 | 3 | 69006 | 120.6 |
|  |  | 3 | `run-20260905T002849Z` | `partial` | false | 7 | 4 | 69317 | 119.0 |
|  |  | 4 | `run-20260905T003048Z` | `partial` | false | 6 | 3 | 72096 | 124.1 |
|  | no_controller | 1 | `run-20260904T221613Z` | `partial` | false | 4 | 3 | 57121 | 130.0 |
|  |  | 2 | `run-20260904T221823Z` | `partial` | false | 4 | 3 | 54132 | 116.3 |
|  |  | 3 | `run-20260904T222019Z` | `partial` | false | 4 | 3 | 53572 | 116.9 |
|  |  | 4 | `run-20260904T222216Z` | `partial` | false | 7 | 3 | 66229 | 119.4 |
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
|  | graphless_no_controller | 1 | `run-20260905T001030Z` | `partial` | false | 1 | 1 | 37772 | 103.7 |
|  |  | 2 | `run-20260905T001214Z` | `partial` | false | 1 | 1 | 33617 | 74.7 |
|  |  | 3 | `run-20260905T001328Z` | `partial` | false | 1 | 1 | 36112 | 80.3 |
|  |  | 4 | `run-20260905T001448Z` | `partial` | false | 2 | 1 | 37142 | 86.5 |
|  | no_controller | 1 | `run-20260904T191221Z` | `partial` | false | 2 | 1 | 37960 | 92.3 |
|  |  | 2 | `run-20260904T191353Z` | `partial` | false | 3 | 1 | 40159 | 113.9 |
|  |  | 3 | `run-20260904T191548Z` | `partial` | false | 3 | 1 | 39370 | 87.9 |
|  |  | 4 | `run-20260904T191716Z` | `partial` | false | 1 | 1 | 39317 | 117.6 |
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
|  | graphless_no_controller | 1 | `run-20260905T001615Z` | `partial` | false | 4 | 2 | 40303 | 90.7 |
|  |  | 2 | `run-20260905T001746Z` | `partial` | false | 2 | 1 | 34545 | 83.1 |
|  |  | 3 | `run-20260905T001908Z` | `partial` | false | 4 | 2 | 41800 | 91.9 |
|  |  | 4 | `run-20260905T002040Z` | `partial` | false | 4 | 2 | 47232 | 97.7 |
|  | no_controller | 1 | `run-20260904T221254Z` | `partial` | false | 4 | 1 | 37798 | 118.0 |
|  |  | 2 | `run-20260904T221452Z` | `partial` | false | 5 | 1 | 58340 | 144.3 |
|  |  | 3 | `run-20260904T221716Z` | `partial` | false | 4 | 1 | 37832 | 111.0 |
|  |  | 4 | `run-20260904T221908Z` | `partial` | false | 2 | 1 | 36794 | 101.1 |
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
|  | graphless_no_controller | 1 | `run-20260905T002218Z` | `partial` | false | 2 | 2 | 36746 | 96.3 |
|  |  | 2 | `run-20260905T002355Z` | `partial` | false | 2 | 2 | 38893 | 87.4 |
|  |  | 3 | `run-20260905T002522Z` | `partial` | false | 2 | 2 | 37084 | 88.9 |
|  |  | 4 | `run-20260905T002651Z` | `partial` | false | 2 | 2 | 36771 | 83.4 |
|  | no_controller | 1 | `run-20260904T222415Z` | `partial` | false | 4 | 3 | 50346 | 144.3 |
|  |  | 2 | `run-20260904T222639Z` | `partial` | false | 4 | 3 | 50826 | 118.9 |
|  |  | 3 | `run-20260904T222838Z` | `partial` | false | 2 | 1 | 46353 | 132.3 |
|  |  | 4 | `run-20260904T223051Z` | `partial` | false | 3 | 2 | 48549 | 114.9 |
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
|  | graphless_no_controller | 1 | `run-20260905T002814Z` | `partial` | false | 1 | 1 | 38542 | 94.5 |
|  |  | 2 | `run-20260905T003125Z` | `partial` | false | 3 | 3 | 52428 | 124.9 |
|  |  | 3 | `run-20260905T003330Z` | `partial` | false | 1 | 1 | 48630 | 115.9 |
|  |  | 4 | `run-20260905T003526Z` | `partial` | false | 3 | 3 | 55119 | 114.5 |
|  | no_controller | 1 | `run-20260904T222048Z` | `partial` | false | 1 | 1 | 50441 | 148.4 |
|  |  | 2 | `run-20260904T222529Z` | `partial` | false | 2 | 2 | 57972 | 161.0 |
|  |  | 3 | `run-20260904T223000Z` | `partial` | false | 2 | 2 | 49900 | 132.7 |
|  |  | 4 | `run-20260904T223213Z` | `partial` | false | 1 | 1 | 44165 | 126.6 |
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
|  | graphless_no_controller | 1 | `run-20260904T231104Z` | `partial` | false | 4 | 3 | 53701 | 110.7 |
|  |  | 2 | `run-20260904T231255Z` | `partial` | false | 4 | 2 | 49741 | 101.1 |
|  |  | 3 | `run-20260904T231436Z` | `partial` | false | 4 | 3 | 52426 | 102.6 |
|  |  | 4 | `run-20260904T231618Z` | `partial` | false | 3 | 1 | 47784 | 95.7 |
|  | no_controller | 1 | `run-20260904T223419Z` | `partial` | false | 2 | 2 | 54950 | 113.8 |
|  |  | 2 | `run-20260904T223613Z` | `partial` | false | 2 | 2 | 39995 | 96.6 |
|  |  | 3 | `run-20260904T223750Z` | `partial` | false | 5 | 3 | 48864 | 102.4 |
|  |  | 4 | `run-20260904T223932Z` | `partial` | false | 5 | 3 | 56854 | 130.0 |
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
|  | graphless_no_controller | 1 | `run-20260904T231754Z` | `partial` | false | 1 | 1 | 34817 | 83.8 |
|  |  | 2 | `run-20260904T231918Z` | `partial` | false | 2 | 2 | 37595 | 84.7 |
|  |  | 3 | `run-20260904T232042Z` | `partial` | false | 1 | 1 | 35162 | 80.6 |
|  |  | 4 | `run-20260904T232203Z` | `partial` | false | 2 | 2 | 36516 | 73.5 |
|  | no_controller | 1 | `run-20260904T223246Z` | `partial` | false | 2 | 2 | 36863 | 115.7 |
|  |  | 2 | `run-20260904T223441Z` | `partial` | false | 1 | 1 | 30502 | 78.5 |
|  |  | 3 | `run-20260904T223600Z` | `partial` | false | 1 | 1 | 29870 | 82.9 |
|  |  | 4 | `run-20260904T223723Z` | `partial` | false | 1 | 1 | 31307 | 85.2 |
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
|  | graphless_no_controller | 1 | `run-20260904T232316Z` | `partial` | false | 1 | 1 | 16475 | 70.0 |
|  |  | 2 | `run-20260904T232426Z` | `partial` | false | 1 | 1 | 16588 | 73.6 |
|  |  | 3 | `run-20260904T232540Z` | `partial` | false | 1 | 1 | 34336 | 78.6 |
|  |  | 4 | `run-20260904T232659Z` | `partial` | false | 1 | 1 | 17503 | 69.2 |
|  | no_controller | 1 | `run-20260904T224142Z` | `partial` | false | 2 | 2 | 38767 | 99.8 |
|  |  | 2 | `run-20260904T224322Z` | `partial` | false | 1 | 1 | 20486 | 79.2 |
|  |  | 3 | `run-20260904T224441Z` | `partial` | false | 1 | 1 | 35432 | 80.4 |
|  |  | 4 | `run-20260904T224601Z` | `partial` | false | 1 | 1 | 19683 | 67.5 |
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
|  | graphless_no_controller | 1 | `run-20260904T232808Z` | `partial` | false | 1 | 1 | 38889 | 87.4 |
|  |  | 2 | `run-20260904T233054Z` | `partial` | false | 1 | 1 | 37637 | 83.5 |
|  |  | 3 | `run-20260904T233217Z` | `partial` | false | 1 | 1 | 35408 | 71.4 |
|  |  | 4 | `run-20260904T233329Z` | `partial` | false | 1 | 1 | 42372 | 104.8 |
|  | no_controller | 1 | `run-20260904T224709Z` | `partial` | false | 1 | 1 | 34865 | 98.0 |
|  |  | 2 | `run-20260904T224847Z` | `partial` | false | 1 | 1 | 37288 | 98.9 |
|  |  | 3 | `run-20260904T225026Z` | `partial` | false | 1 | 1 | 47054 | 131.2 |
|  |  | 4 | `run-20260904T225237Z` | `partial` | false | 1 | 1 | 37706 | 99.3 |
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
|  | graphless_no_controller | 1 | `run-20260904T233514Z` | `partial` | false | 7 | 4 | 56129 | 125.2 |
|  |  | 2 | `run-20260904T233719Z` | `partial` | false | 7 | 4 | 52496 | 114.9 |
|  |  | 3 | `run-20260904T233914Z` | `partial` | false | 6 | 3 | 45633 | 100.6 |
|  |  | 4 | `run-20260904T234054Z` | `partial` | false | 8 | 4 | 53367 | 97.7 |
|  | no_controller | 1 | `run-20260904T223848Z` | `partial` | false | 9 | 4 | 60336 | 125.1 |
|  |  | 2 | `run-20260904T224053Z` | `partial` | false | 8 | 3 | 67079 | 126.0 |
|  |  | 3 | `run-20260904T224259Z` | `partial` | false | 6 | 3 | 53721 | 105.3 |
|  |  | 4 | `run-20260904T224444Z` | `partial` | false | 8 | 3 | 60410 | 125.3 |
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
|  | graphless_no_controller | 1 | `run-20260904T234232Z` | `partial` | false | 9 | 7 | 63578 | 113.9 |
|  |  | 2 | `run-20260904T234426Z` | `partial` | false | 6 | 5 | 62675 | 115.9 |
|  |  | 3 | `run-20260904T234623Z` | `partial` | false | 7 | 5 | 66191 | 150.9 |
|  |  | 4 | `run-20260904T234854Z` | `partial` | false | 8 | 6 | 68554 | 154.5 |
|  | no_controller | 1 | `run-20260904T185536Z` | `partial` | false | 8 | 6 | 71861 | 161.0 |
|  |  | 2 | `run-20260904T185817Z` | `partial` | false | 6 | 6 | 73496 | 152.6 |
|  |  | 3 | `run-20260904T190049Z` | `partial` | false | 7 | 6 | 64708 | 166.0 |
|  |  | 4 | `run-20260904T190444Z` | `partial` | false | 6 | 5 | 56437 | 131.5 |
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
|  | graphless_no_controller | 1 | `run-20260904T235128Z` | `partial` | false | 4 | 1 | 42044 | 110.7 |
|  |  | 2 | `run-20260904T235319Z` | `partial` | false | 3 | 1 | 38389 | 78.1 |
|  |  | 3 | `run-20260904T235437Z` | `partial` | false | 3 | 1 | 37967 | 70.1 |
|  |  | 4 | `run-20260904T235547Z` | `partial` | false | 4 | 1 | 40566 | 86.4 |
|  | no_controller | 1 | `run-20260904T190655Z` | `partial` | false | 3 | 1 | 44496 | 115.9 |
|  |  | 2 | `run-20260904T190851Z` | `partial` | false | 3 | 1 | 42996 | 121.9 |
|  |  | 3 | `run-20260904T191053Z` | `partial` | false | 3 | 1 | 43726 | 115.9 |
|  |  | 4 | `run-20260904T191249Z` | `partial` | false | 2 | 1 | 40737 | 105.2 |
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
|  | graphless_no_controller | 1 | `run-20260904T235714Z` | `partial` | false | 1 | 1 | 46796 | 122.9 |
|  |  | 2 | `run-20260904T235916Z` | `partial` | false | 2 | 2 | 38425 | 74.2 |
|  |  | 3 | `run-20260905T000030Z` | `partial` | false | 2 | 2 | 38239 | 87.6 |
|  |  | 4 | `run-20260905T000158Z` | `partial` | false | 3 | 2 | 43545 | 101.1 |
|  | no_controller | 1 | `run-20260904T191435Z` | `partial` | false | 2 | 2 | 36202 | 96.0 |
|  |  | 2 | `run-20260904T191611Z` | `partial` | false | 2 | 2 | 37118 | 106.0 |
|  |  | 3 | `run-20260904T191757Z` | `partial` | false | 3 | 2 | 39931 | 113.5 |
|  |  | 4 | `run-20260904T221251Z` | `partial` | false | 2 | 2 | 38021 | 123.7 |
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
|  | graphless_no_controller | 1 | `run-20260905T000339Z` | `partial` | false | 2 | 2 | 37002 | 116.5 |
|  |  | 2 | `run-20260905T000536Z` | `partial` | false | 2 | 2 | 39477 | 95.0 |
|  |  | 3 | `run-20260905T000711Z` | `partial` | false | 2 | 2 | 36890 | 100.7 |
|  |  | 4 | `run-20260905T000852Z` | `partial` | false | 3 | 2 | 41510 | 104.3 |
|  | no_controller | 1 | `run-20260904T221454Z` | `partial` | false | 4 | 3 | 41525 | 109.3 |
|  |  | 2 | `run-20260904T221643Z` | `partial` | false | 2 | 2 | 39547 | 105.7 |
|  |  | 3 | `run-20260904T221829Z` | `partial` | false | 3 | 3 | 44097 | 106.0 |
|  |  | 4 | `run-20260904T222015Z` | `partial` | false | 3 | 3 | 40373 | 108.2 |
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
|  | graphless_no_controller | 1 | `run-20260904T231104Z` | `partial` | false | 5 | 5 | 46126 | 94.7 |
|  |  | 2 | `run-20260904T231239Z` | `partial` | false | 3 | 3 | 42086 | 93.4 |
|  |  | 3 | `run-20260904T231412Z` | `partial` | false | 5 | 5 | 48401 | 102.8 |
|  |  | 4 | `run-20260904T231555Z` | `partial` | false | 5 | 5 | 46629 | 100.9 |
|  | no_controller | 1 | `run-20260904T222203Z` | `partial` | false | 7 | 6 | 45777 | 129.0 |
|  |  | 2 | `run-20260904T222412Z` | `partial` | false | 4 | 4 | 41267 | 114.6 |
|  |  | 3 | `run-20260904T222607Z` | `partial` | false | 4 | 4 | 41292 | 127.4 |
|  |  | 4 | `run-20260904T222814Z` | `partial` | false | 5 | 4 | 44200 | 123.5 |
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
|  | graphless_no_controller | 1 | `run-20260904T231736Z` | `partial` | false | 4 | 2 | 43388 | 92.6 |
|  |  | 2 | `run-20260904T231908Z` | `partial` | false | 2 | 1 | 34666 | 83.4 |
|  |  | 3 | `run-20260904T232032Z` | `partial` | false | 2 | 1 | 37262 | 90.5 |
|  |  | 4 | `run-20260904T232203Z` | `partial` | false | 1 | 1 | 31881 | 69.0 |
|  | no_controller | 1 | `run-20260904T223018Z` | `partial` | false | 3 | 1 | 37351 | 107.4 |
|  |  | 2 | `run-20260904T223205Z` | `partial` | false | 2 | 1 | 34091 | 98.5 |
|  |  | 3 | `run-20260904T223344Z` | `partial` | false | 1 | 1 | 32562 | 80.0 |
|  |  | 4 | `run-20260904T223504Z` | `partial` | false | 1 | 1 | 37213 | 98.1 |
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
|  | graphless_no_controller | 1 | `run-20260904T232311Z` | `partial` | false | 3 | 3 | 43327 | 100.3 |
|  |  | 2 | `run-20260904T232452Z` | `partial` | false | 3 | 3 | 45894 | 105.5 |
|  |  | 3 | `run-20260904T232637Z` | `partial` | false | 4 | 4 | 47775 | 104.8 |
|  |  | 4 | `run-20260904T232822Z` | `partial` | false | 1 | 1 | 38141 | 92.5 |
|  | no_controller | 1 | `run-20260904T190444Z` | `partial` | false | 4 | 4 | 47346 | 148.8 |
|  |  | 2 | `run-20260904T190713Z` | `partial` | false | 2 | 2 | 54853 | 158.7 |
|  |  | 3 | `run-20260904T190951Z` | `partial` | false | 3 | 3 | 43706 | 117.7 |
|  |  | 4 | `run-20260904T191149Z` | `partial` | false | 3 | 2 | 55055 | 116.1 |
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
|  | graphless_no_controller | 1 | `run-20260904T232954Z` | `partial` | false | 6 | 3 | 53942 | 127.2 |
|  |  | 2 | `run-20260904T233202Z` | `partial` | false | 5 | 4 | 46779 | 90.0 |
|  |  | 3 | `run-20260904T233332Z` | `partial` | false | 3 | 2 | 37972 | 94.4 |
|  |  | 4 | `run-20260904T233506Z` | `partial` | false | 5 | 3 | 44297 | 91.1 |
|  | no_controller | 1 | `run-20260904T191345Z` | `partial` | false | 7 | 5 | 55178 | 129.9 |
|  |  | 2 | `run-20260904T191555Z` | `partial` | false | 5 | 3 | 57406 | 142.8 |
|  |  | 3 | `run-20260904T191818Z` | `partial` | false | 5 | 3 | 60257 | 141.0 |
|  |  | 4 | `run-20260904T221251Z` | `partial` | false | 5 | 4 | 46638 | 97.1 |
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
|  | graphless_no_controller | 1 | `run-20260904T233637Z` | `partial` | false | 5 | 4 | 55116 | 132.7 |
|  |  | 2 | `run-20260904T233850Z` | `partial` | false | 3 | 1 | 44451 | 98.0 |
|  |  | 3 | `run-20260904T234028Z` | `partial` | false | 1 | 1 | 42222 | 92.6 |
|  |  | 4 | `run-20260904T234201Z` | `partial` | false | 8 | 4 | 54768 | 104.7 |
|  | no_controller | 1 | `run-20260904T221428Z` | `partial` | false | 4 | 3 | 55330 | 128.2 |
|  |  | 2 | `run-20260904T221636Z` | `partial` | false | 2 | 1 | 38629 | 101.3 |
|  |  | 3 | `run-20260904T221818Z` | `partial` | false | 1 | 1 | 46596 | 116.6 |
|  |  | 4 | `run-20260904T222014Z` | `partial` | false | 5 | 4 | 55720 | 134.4 |
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
|  | graphless_no_controller | 1 | `run-20260904T234345Z` | `partial` | false | 2 | 2 | 37618 | 94.2 |
|  |  | 2 | `run-20260904T234520Z` | `partial` | false | 1 | 1 | 32498 | 73.7 |
|  |  | 3 | `run-20260904T234634Z` | `partial` | false | 2 | 1 | 35706 | 87.1 |
|  |  | 4 | `run-20260904T234801Z` | `partial` | false | 1 | 1 | 34301 | 109.0 |
|  | no_controller | 1 | `run-20260904T222229Z` | `partial` | false | 1 | 1 | 34372 | 91.3 |
|  |  | 2 | `run-20260904T222400Z` | `partial` | false | 2 | 1 | 35260 | 98.2 |
|  |  | 3 | `run-20260904T222538Z` | `partial` | false | 2 | 1 | 35842 | 100.9 |
|  |  | 4 | `run-20260904T222719Z` | `partial` | false | 2 | 2 | 35667 | 113.4 |
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
|  | graphless_no_controller | 1 | `run-20260904T234950Z` | `partial` | false | 5 | 4 | 61020 | 133.3 |
|  |  | 2 | `run-20260904T235203Z` | `partial` | false | 4 | 3 | 51593 | 108.0 |
|  |  | 3 | `run-20260904T235351Z` | `partial` | false | 5 | 5 | 52193 | 116.6 |
|  |  | 4 | `run-20260904T235548Z` | `partial` | false | 5 | 4 | 63684 | 132.2 |
|  | no_controller | 1 | `run-20260904T222913Z` | `partial` | false | 6 | 4 | 63350 | 138.5 |
|  |  | 2 | `run-20260904T223131Z` | `partial` | false | 5 | 4 | 48905 | 112.4 |
|  |  | 3 | `run-20260904T223323Z` | `partial` | false | 4 | 3 | 51193 | 140.4 |
|  |  | 4 | `run-20260904T223544Z` | `partial` | false | 6 | 4 | 46350 | 111.8 |
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
|  | graphless_no_controller | 1 | `run-20260904T235800Z` | `partial` | false | 7 | 6 | 58289 | 134.1 |
|  |  | 2 | `run-20260905T000111Z` | `partial` | false | 8 | 6 | 67654 | 131.3 |
|  |  | 3 | `run-20260905T000323Z` | `partial` | false | 11 | 7 | 64737 | 147.2 |
|  |  | 4 | `run-20260905T000550Z` | `partial` | false | 8 | 6 | 57747 | 128.4 |
|  | no_controller | 1 | `run-20260904T223736Z` | `partial` | false | 5 | 4 | 61499 | 158.9 |
|  |  | 2 | `run-20260904T224014Z` | `partial` | false | 10 | 7 | 70370 | 146.7 |
|  |  | 3 | `run-20260904T224241Z` | `partial` | false | 8 | 6 | 67497 | 135.0 |
|  |  | 4 | `run-20260904T224456Z` | `partial` | false | 7 | 5 | 62061 | 137.2 |
|  | workspace | 1 | `run-20260902T094458Z` | `partial` | false | 9 | 6 | 123346 | 226.4 |
|  |  | 2 | `run-20260902T094845Z` | `partial` | false | 8 | 5 | 110663 | 218.5 |
|  |  | 3 | `run-20260902T095224Z` | `partial` | false | 7 | 5 | 119261 | 245.8 |
|  |  | 4 | `run-20260902T095629Z` | `partial` | false | 12 | 6 | 126494 | 270.7 |

## Limitations

- The three Workspace ablations reuse the same Qdrant/BM25 indexes; they disable CodeGraph, the adaptive controller, or both.
- Flow-token counts exclude indexing and response generation was skipped.
- Invalid attempts remain in campaign ledgers but do not enter four-run metrics.

## Reproduction

- Script: `testing/codeRepoQA/aggregate_three_system_comparison.py`
- workspace: `2026-09-02-workspace-four-runs-complete.json`
- codex: `2026-09-02-codex-efficient-luna-four-runs.json`
- graphless: `2026-09-03-graphless-four-runs-complete.json`
- no_controller: `2026-09-05-workspace-no-controller-four-runs-complete.json`
- graphless_no_controller: `2026-09-05-workspace-graphless-no-controller-four-runs-complete.json`
