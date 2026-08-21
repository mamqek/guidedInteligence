# Native Retrieval vs Codex Retrieval — Example Statistics Report

> **Status:** format example using saved pilot runs, not the 35-case benchmark result.

## What This Report Covers

This example compares final native/workspace retrieval with historical Codex retrieval on three previously exercised development cases. It demonstrates the required report format using real saved outputs. The sample is too small and too narrow for a general quality conclusion: it contains three cases from only two categories.

| Scope item | Value |
| --- | --- |
| Partition | Development pilot |
| Testcases | 3 |
| Repositories | TypeScript, pandas, Vue |
| Categories represented | Bug/regression; testing/build/tooling |
| Cutoff | Saved runs selected through 2026-08-14 |
| Ranking unit | Ordered unique repository-relative files |
| Reported cutoffs | 1, 2, 5, 10 |

## Conditions And Run Selection

- **Native retrieval:** final native `workspace` retrieval runs, using `gpt-5.6-luna` for LLM-backed stages. The first valid run in the declared pilot window is selected for each testcase.
- **Codex retrieval:** the latest valid saved `efficient` profile run selected for each case, using `gpt-5.4-mini`. One saved run per case is available in this example.

Exactly one valid run per testcase and system enters the headline metrics. Extra valid executions are not averaged into this report. A run remains eligible when its retrieval version and configuration match the declared condition, even if it was originally started for an indexing or diagnostic check.

The model difference is intentional historical provenance, not something hidden inside a generic “Codex” label. Future Codex cases expected to use `gpt-5.6-luna` must be reported as a separate model stratum or rerun under one common configuration before forming a homogeneous headline Codex average.

### Run inventory

Each selected testcase/system pair must record its end-to-end elapsed wall-clock time (from pipeline start through final artifact creation) and token accounting. Token accounting separates the tokens spent to build or rebuild an index from the tokens spent by the rest of the flow; the total is their sum. When an index is reused, do not rerun indexing: take the indexing-token count from the logged original build with the same index signature, cite that build run, and add it to the reused run's rest-of-flow tokens. Codex rows additionally separate cached and uncached input tokens from output tokens; reasoning output tokens, when available, are a subset of output tokens and must not be added again.

The saved pilot artifacts used by this legacy example do not retain these values, so they are explicitly marked unavailable rather than reconstructed from run IDs or fabricated. A newly generated statistics report must contain measured values in each applicable column.

| Testcase | Category | System | Model / profile | Selected run ID | Selection rule | Elapsed time | Indexing tokens | Rest-of-flow tokens | Total tokens | Cached input (Codex) | Uncached input (Codex) | Output (Codex) |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `microsoft-TypeScript-35468` | Testing/build/tooling | Native | `gpt-5.6-luna`; workspace final | `run-20260814T060345Z` | First valid in pilot window | Unavailable (not retained) | Unavailable (not retained) | Unavailable (not retained) | Unavailable (not retained) | N/A | N/A | N/A |
| `microsoft-TypeScript-35468` | Testing/build/tooling | Codex | `gpt-5.4-mini`; `efficient` | `run-20260729T205015Z` | Latest valid before cutoff | Unavailable (not retained) | Unavailable (not retained) | Unavailable (not retained) | Unavailable (not retained) | Unavailable (not retained) | Unavailable (not retained) | Unavailable (not retained) |
| `pandas-dev-pandas-10068` | Bug/regression | Native | `gpt-5.6-luna`; workspace final | `run-20260814T061200Z` | First valid in pilot window | Unavailable (not retained) | Unavailable (not retained) | Unavailable (not retained) | Unavailable (not retained) | N/A | N/A | N/A |
| `pandas-dev-pandas-10068` | Bug/regression | Codex | `gpt-5.4-mini`; `efficient` | `run-20260729T204029Z` | Latest valid before cutoff | Unavailable (not retained) | Unavailable (not retained) | Unavailable (not retained) | Unavailable (not retained) | Unavailable (not retained) | Unavailable (not retained) | Unavailable (not retained) |
| `vuejs-vue-10803` | Bug/regression | Native | `gpt-5.6-luna`; workspace final | `run-20260814T061744Z` | First valid in pilot window | Unavailable (not retained) | Unavailable (not retained) | Unavailable (not retained) | Unavailable (not retained) | N/A | N/A | N/A |
| `vuejs-vue-10803` | Bug/regression | Codex | `gpt-5.4-mini`; `efficient` | `run-20260805T213915Z` | Latest valid before cutoff | Unavailable (not retained) | Unavailable (not retained) | Unavailable (not retained) | Unavailable (not retained) | Unavailable (not retained) | Unavailable (not retained) | Unavailable (not retained) |

### Fair cost presentation

A production report reuses the logged indexing-token count from the matching original index-build run whenever an index is reused; it does not rerun the index just to reproduce that measurement. The report cites that source run and index signature, and compares `recorded original index tokens + current rest-of-flow tokens`. An amortized view is optional and must state the exact matching signature and divisor: `recorded original index cost / named shared requests + rest-of-flow cost`.

For Codex, a currency estimate must separately price cached input, uncached input, and output tokens at the rates for the selected model and dated pricing snapshot. Cached tokens reduce cost; they are not zero-cost and must not be merged into uncached input. This saved-artifact example has no reproducible usage or pricing snapshot, so it makes no cost comparison.

## How To Read The Metrics

The systems rank **files**, not snippets. If several snippets come from one file, only that file's first position counts.

- **P@k** is the number of implementation Oracle files in the first k ranks divided by k. The denominator remains k when fewer files are returned. For example, two correct files in a four-file result give P@10 = 2/10 = 0.20 because ranks 5–10 are empty and nonrelevant.
- **R@k** is the fraction of all known implementation Oracle files found by rank k.
- **NDCG@k** also recognizes supporting Oracle files and rewards earlier ranks. Implementation Oracle files have relevance 2, test/validation or documentation Oracle files have relevance 1, and all other files have relevance 0.

“Implementation Oracle” means the frozen files recorded as owning the implementation involved in the selected fix. It does not include every file that merely seems related to the issue. Tests and documentation support the result through NDCG but do not inflate the primary precision or recall.

All displayed values range from 0 to 1. They are calculated at full precision and rounded to three decimals here.

## Headline Pilot Metrics

Each row is a macro-average over three testcase scores, using one selected valid run per testcase and system.

### Precision

| System | Cases | P@1 | P@2 | P@5 | P@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Native | 3 | 0.667 | 0.333 | 0.267 | 0.167 |
| Codex (`gpt-5.4-mini`) | 3 | 0.333 | 0.333 | 0.267 | 0.133 |

### Recall

| System | Cases | R@1 | R@2 | R@5 | R@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Native | 3 | 0.667 | 0.667 | 0.833 | 0.917 |
| Codex (`gpt-5.4-mini`) | 3 | 0.333 | 0.417 | 0.833 | 0.833 |

### Graded ranking quality

| System | Cases | NDCG@1 | NDCG@2 | NDCG@5 | NDCG@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Native | 3 | 0.667 | 0.609 | 0.720 | 0.735 |
| Codex (`gpt-5.4-mini`) | 3 | 0.333 | 0.404 | 0.528 | 0.539 |

## Per-case Audit View

This compact view shows the rank-5 values behind the pilot average. A full production report should retain machine-readable results for every requested cutoff.

| Testcase | System | P@5 | R@5 | NDCG@5 |
| --- | --- | ---: | ---: | ---: |
| `microsoft-TypeScript-35468` | Native | 0.400 | 0.500 | 0.330 |
| `microsoft-TypeScript-35468` | Codex (`gpt-5.4-mini`) | 0.400 | 0.500 | 0.395 |
| `pandas-dev-pandas-10068` | Native | 0.200 | 1.000 | 0.830 |
| `pandas-dev-pandas-10068` | Codex (`gpt-5.4-mini`) | 0.200 | 1.000 | 0.363 |
| `vuejs-vue-10803` | Native | 0.200 | 1.000 | 1.000 |
| `vuejs-vue-10803` | Codex (`gpt-5.4-mini`) | 0.200 | 1.000 | 0.826 |

## Breakdown Context

No category or repository aggregate is presented as evidence here because each repository has only one case and one category has only one case. In the complete 35-case report, include category rows with five cases each for the combined corpus, development rows with four cases each, final rows with one case each, and repository rows with their case counts.

## Limitations

- This is a three-case formatting example, not a complete development or final evaluation.
- Only two of seven retrieval categories are represented.
- Exactly one valid run per testcase and system is used. This descriptive report therefore does not estimate run-to-run stochastic variability.
- The saved pilot artifacts lack end-to-end elapsed-time and the required token breakdown. This legacy example flags them as unavailable; future statistics reports must report those values for every testcase/system pair.
- The Codex condition is historical `gpt-5.4-mini`, whereas new Codex runs are expected to use `gpt-5.6-luna`. These must not be silently pooled in a future headline aggregate.
- @20 is omitted because the saved systems did not consistently provide comparable 20-file rankings.
- These are descriptive retrieval metrics; no confidence interval or significance claim is made from three cases.

## Reproduction Note

The source values are the listed runs' `evaluator-comparison.json` files. Paths are deduplicated in ranked order. P/R use `oracle_implementation_files`; graded NDCG uses implementation = 2, test/validation or documentation = 1, other = 0, with gain `(2^grade - 1) / log2(rank + 1)`. One selected run supplies each testcase score, and testcase scores are macro-averaged.

The governing calculation and publication rules are in [RETRIEVAL_STATISTICS_PROTOCOL.md](RETRIEVAL_STATISTICS_PROTOCOL.md). Completed evaluations belong under [runs/](runs/).
