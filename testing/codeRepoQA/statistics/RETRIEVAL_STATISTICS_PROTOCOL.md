# Retrieval Statistics Protocol

## Purpose

This is the authoritative procedure for comparing the final native retrieval pipeline with Codex retrieval on CodeRepoQA cases. A statistics report must be understandable without this document, so every report must repeat the short metric definitions and configuration disclosures listed in the report checklist below.

The comparison is retrieval-only. It measures whether each system ranks the correct files near the top; it does not score the final prose answer.

## Benchmark Population And Split

Use only the seven retrieval-grounded categories:

1. `bug_regression`
2. `feature_enhancement`
3. `performance_memory`
4. `compatibility_versioning`
5. `api_behavior_design`
6. `testing_build_tooling`
7. `maintenance_refactor`

Do not include `question_usage` or any other explanation-grounded case in these ranking statistics.

The target corpus has 35 retrieval-grounded cases, five in each category:

| Partition | Cases per category | Total | Share |
| --- | ---: | ---: | ---: |
| Development | 4 | 28 | 80% |
| Final evaluation | 1 | 7 | 20% |
| Total | 5 | 35 | 100% |

All seven final cases must be frozen before system-level evaluation. Eligibility screening—checking issue quality, resolution availability, and snapshot feasibility—is allowed. Retrieval runs, tuning against outputs, and manual inspection of system results are not allowed until final evaluation begins. The selected expansion and split are recorded in [RETRIEVAL_STATISTICS_CORPUS_SPLIT.md](RETRIEVAL_STATISTICS_CORPUS_SPLIT.md).

## Compared Conditions

The two conditions are:

- **Native retrieval:** the final native/workspace retrieval version being evaluated.
- **Codex retrieval:** the declared Codex prompt profile and model.

Every report must name the exact profile, model, configuration or configuration hash, and run IDs for both conditions. “Codex retrieval” by itself is not a reproducible condition.

The reusable historical Codex `efficient` runs use `gpt-5.4-mini`. New Codex runs are expected to use `gpt-5.6-luna`. Never silently average those into a single homogeneous Codex result. Use one of these options:

1. rerun a case with the declared current configuration; or
2. retain the historical result, show its model on the run row, and report model-stratified aggregates.

A mixed-model combined average may be shown only as an explicitly labelled exploratory number. It must not be presented as the headline result for one Codex configuration.

Do not average arbitrary historical executions. Every evaluation campaign uses exactly one valid run per testcase and system. Select that run by a written rule fixed before looking at metric values. For newly executed campaign runs, use the first valid run at or after the declared campaign start. For reused historical results, a rule such as the latest valid run of the declared profile before a fixed cutoff is acceptable. Record the selected run ID. Never choose the best-looking run.

A run is eligible based on its retrieval version, model/profile, configuration, testcase snapshot, and declared time window—not on why somebody originally started it. A run made while testing indexing reuse may therefore be reused when its retrieval condition is identical to the frozen campaign condition.

## Ranking Unit

Rank **ordered unique repository-relative file paths**, not snippets.

The pipeline may retrieve several snippets from one file. Keep only the first occurrence of that file. Otherwise a system could receive repeated credit for returning multiple snippets from the same correct file.

Use `retrieved_source_files` from `evaluator-comparison.json` when it is available. Normalize path separators and repository-relative spelling before matching. File matching is exact after normalization.

## Relevance Rules

### Primary binary oracle for precision and recall

For P@k and R@k, a file is relevant only when it appears in `oracle_implementation_files` for that case.

“Implementation Oracle” means the file set recorded in the case verification data as owning the implementation involved in the selected resolution. It can contain more than one file. It does not mean every file that appears semantically related to the issue. A plausible nearby file that is absent from the frozen oracle receives no deterministic credit, but it may be discussed in a qualitative error analysis.

Tests, generated baselines, documentation, and configuration are not counted as correct files for primary P@k or R@k unless the case verification explicitly classifies one as an implementation file.

### Secondary graded oracle for NDCG

Use these grades:

| File class | Relevance grade |
| --- | ---: |
| Implementation Oracle | 2 |
| Supporting Oracle: test/validation or documentation | 1 |
| All other files | 0 |

If a file occurs in more than one oracle list, use the highest grade. This makes NDCG reward implementation owners most strongly while still recognizing useful supporting evidence. Do not mix this graded definition into the binary precision and recall calculations.

## Metrics

Report P@1, P@2, P@5, P@10; R@1, R@2, R@5, R@10; and NDCG@1, NDCG@2, NDCG@5, NDCG@10.

### Precision at k

`P@k = relevant implementation files in the first k ranks / k`

The denominator is always `k`. If a system returns only four unique files, ranks 5–10 are empty and nonrelevant, so two correct returned files produce P@10 = 2/10 = 0.20. This is standard P@k and intentionally measures both ranking accuracy and whether the system supplies a complete top-k list.

### Recall at k

`R@k = relevant implementation files in the first k ranks / total implementation Oracle files for the case`

Recall answers how much of the known implementation set has been found by rank k. A case must have at least one frozen implementation Oracle file to enter the benchmark.

### NDCG at k

For rank `i` starting at 1:

`DCG@k = sum((2^grade - 1) / log2(i + 1))`

`NDCG@k = DCG@k / IDCG@k`

`IDCG@k` is the DCG of the same case's known graded Oracle files ordered ideally, with grade 2 files before grade 1 files. Empty/unreturned ranks have grade 0. NDCG is therefore between 0 and 1 and gives more credit when highly relevant files appear earlier.

### Why @20 is not a default

Do not report @20 in the headline comparison unless both systems were configured to return at least 20 unique files for every included run. Otherwise P@20 mostly measures different output limits. If the condition is met, @20 may be added using exactly the same rules.

## Runs And Repetitions

The headline evaluation uses **exactly one valid run per testcase and system per campaign**. This keeps every case equally measured and makes the result easy to audit. Infrastructure failures—such as API rate limits, unavailable Qdrant, or an incomplete artifact—do not count as runs; retry until one valid run is obtained. Once a valid run has been selected, do not replace it because another valid run scores better.

Additional valid executions under the same condition are not pooled into the headline result. They may be retained as a separately labelled indexing check, diagnostic run, or stability analysis. Their original purpose does not make them invalid; the one-run campaign selection rule alone determines whether they enter headline metrics.

A future rerun of the full benchmark is a new evaluation campaign with its own start time, configuration declaration, and one selected valid run per testcase. Do not pool the new campaign with an older campaign unless the explicit research objective is run-to-run stability.

If stochastic variability is studied, predeclare the same repetition count for every testcase and condition, keep configurations fixed, and report that analysis separately. Never repeat only weak cases or stop when a favorable result appears.

Headline aggregation order is:

1. calculate every metric from the single selected run for each testcase and system;
2. macro-average those testcase scores across cases.

## Aggregate Views

The required headline value for every metric is the macro-average across case-level scores. Also report:

- one row per category;
- one row per repository;
- the development and final partitions separately;
- the number of cases and individual runs behind every aggregate.

Do not merge development and final results until after the final result has been reported separately. Do not use the final partition to tune retrieval behavior.

With the complete 35-case corpus, a paired uncertainty interval may be added by bootstrapping testcase pairs. If used, record the method, seed, number of resamples, and confidence level. It is optional and does not replace the required per-category and per-repository breakdowns.

## Case Eligibility

Before a candidate enters the manifest, verify all of the following:

- the local source JSON is a real issue with enough problem detail;
- the issue belongs to exactly one of the seven retrieval categories;
- a fixing PR/commit or other resolution artifact is identifiable;
- the pre-fix commit is unambiguous and available;
- a pre-fix snapshot can be derived without resolution leakage;
- implementation and supporting Oracle files can be recorded from the resolution;
- the issue text shown to retrieval does not expose the hidden resolution;
- the case does not duplicate an existing case's exact responsibility.

Candidate screening does not create a runnable testcase. Add a case to `selection_manifest.json` only after its issue and verification files, snapshot reference, and Oracle are materialized and validated.

## Required Report Structure

Each statistics report must contain, in this order:

1. **Status and scope:** pilot/development/final, case count, categories, repositories, and cutoff date.
2. **Conditions:** retrieval mode, prompt/profile, model, configuration identifier, and run selection rule.
3. **Plain-language metric note:** files are ranked; implementation files define P/R; supporting files receive partial NDCG relevance; missing ranks are nonrelevant.
4. **Run inventory:** case, partition, category, system, selected run ID, model/profile, campaign selection rule, and validity notes.
5. **Headline metrics:** the complete P/R/NDCG table at 1, 2, 5, and 10.
6. **Breakdowns:** per category and per repository, with counts.
7. **Per-case results:** enough detail to audit the averages.
8. **Limitations:** missing cases, mixed models, single-run stochasticity, output limits, failed attempts, or Oracle concerns.
9. **Reproduction note:** source files and calculation version/script or exact formula.

Use decimal values from 0 to 1 and display three decimal places. Calculate with full precision and round only for presentation. A clean reader-facing example is [EXAMPLE_RETRIEVAL_STATISTICS.md](EXAMPLE_RETRIEVAL_STATISTICS.md). Actual result reports belong under [runs/](runs/).

## Pre-publication Checklist

- [ ] Only retrieval-grounded cases are included.
- [ ] Development and final partitions are not accidentally pooled.
- [ ] Each case has at least one implementation Oracle file.
- [ ] Ranked paths are unique, normalized files.
- [ ] P@k uses denominator k even for short result lists.
- [ ] P/R use only implementation Oracle files.
- [ ] NDCG uses grades 2/1/0 and the documented gain formula.
- [ ] Exactly one valid run is selected per case/system for the headline campaign.
- [ ] Failed infrastructure attempts are excluded, and no successful run was replaced based on its score.
- [ ] Model/profile and run selection are explicit; mixed Codex models are stratified.
- [ ] Counts accompany all aggregates.
- [ ] The report itself repeats the definitions needed by a reader.
- [ ] Final cases remained untouched until the declared final evaluation.
