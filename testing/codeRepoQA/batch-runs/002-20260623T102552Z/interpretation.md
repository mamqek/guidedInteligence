# Batch 002 Interpretation

Source artifacts:
- `summary.json`
- `summary.md`
- per-run `scorecard.json`
- per-run `evaluator-comparison.md`
- per-run `orchestration-result.json`

## Headline

| Metric | Result |
| --- | --- |
| Cases | 5 |
| Attempts | 10 |
| Completed attempts | 9 |
| Setup/runtime errors | 1 |
| Avg completed workspace runtime | 587.334s |
| Avg completed codex runtime | 288.022s |
| Codex speedup vs workspace | 2.04x |

## Case Table

| Case | Workspace outcome | Codex outcome | Winner | Why |
| --- | --- | --- | --- | --- |
| `microsoft-TypeScript-45713` | Completed, but retrieval failed in practice: `coverage_status=failed`, `sufficient=false`, `overlap_count=0`, no retrieved source files. | Strong result: `coverage_status=strong`, `sufficient=true`, implementation overlap `2`; found `src/executeCommandLine/executeCommandLine.ts` and `src/compiler/watch.ts` at ranks 1 and 2. | `codex` | Workspace returned no useful implementation evidence; Codex found the two core owner files immediately. |
| `microsoft-TypeScript-46770` | Completed, but retrieval failed in practice: `coverage_status=failed`, `sufficient=false`, `overlap_count=0`, no retrieved source files. | Strong result: `coverage_status=strong`, `sufficient=true`, implementation overlap `1`; found `src/compiler/moduleNameResolver.ts` at rank 3. | `codex` | Codex hit the main implementation file; workspace found nothing useful. |
| `pandas-dev-pandas-10068` | Completed, but retrieval failed in practice: `coverage_status=failed`, `sufficient=false`, `overlap_count=0`, no retrieved source files. | Strong result: `coverage_status=strong`, `sufficient=true`, implementation overlap `1`; found `pandas/core/series.py` at rank 3 with nearby supporting files. | `codex` | Codex found the real implementation surface for the bug; workspace did not. |
| `pandas-dev-pandas-14942` | Did not run successfully: setup failed during detached checkout with `update_ref failed for ref 'HEAD'`. | Completed, but retrieval missed: `coverage_status=missing`, `sufficient=false`, `selected_count=0`; explanation generation failed because no valid understanding checks were produced. | none | Workspace died before retrieval; Codex ran but returned no usable evidence, so neither mode produced a good testcase result. |
| `vuejs-vue-10803` | Best workspace case, but still incomplete: `coverage_status=partial`, `sufficient=false`, implementation overlap `1`; found `src/platforms/web/server/modules/dom-props.js` at rank 2 with several noisy files. | Strong result: `coverage_status=strong`, `sufficient=true`, implementation overlap `1`; found `src/platforms/web/server/modules/dom-props.js` at rank 3 with a cleaner SSR-focused file set. | `codex` | Both modes touched the right file, but only Codex reached strong/sufficient coverage and stayed more focused. |

## Pattern Summary

| Mode | Result pattern |
| --- | --- |
| `workspace` | 3 runs were `failed/false`, 1 run was `partial/false`, and 1 run failed before retrieval started. |
| `codex` | 4 runs were `strong/true`; 1 run was `missing/false`. |

## Takeaway

Batch 002 shows that the old `workspace` retriever was operationally capable of finishing most runs, but usually failed to produce sufficient implementation evidence. The `codex` retriever was both faster on average and far more effective on this batch, with 4 of 5 cases reaching strong and sufficient retrieval quality.
