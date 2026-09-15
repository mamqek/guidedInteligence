# Current-checkpoint four-case rerun (2026-09-15)

User-requested verification: two fresh actual workspace runs each on TypeScript
35468, Vue 10519, and two contrasting cases with prior nonzero oracle overlap.
Runtime remains checkpoint `803f5e2`; neither rejected unresolved-source variant
is enabled. No runtime or thesis changes are part of this measurement.

## Fixed configuration

Use `npm run coderepoqa:evaluate:workspace -- --issue-json <case> --skip-response-generation`.
TypeScript also retains its existing `--exclude-path openwiki` override. Final evidence
selection is enabled. Model: `gpt-5.6-luna`, temperature zero, continuity disabled.
These are fresh pipeline executions, not saved-input replays or smoke runs.

TypeScript/Vue reuse complete existing Qdrant collections (83408/4350 chunks).
The two missing pandas collections were restored using their existing snapshots,
scope and embedding cache, to 14707/6677 chunks respectively. The second run of
each pandas case was started only after its collection reached the complete count.
No index-scope change or rebuild of the existing TypeScript/Vue indexes was made.

## Additional-case selection

- `pandas-dev-pandas-14942`: categorical groupby memory growth. Saved workspace
  runs 20260905T002456Z/002648Z/002849Z/003048Z recorded 2/15, 2/15, 3/15, 2/15
  oracle overlap. Exercises Python data-processing internals.
- `pandas-dev-pandas-4542`: adding the XlsxWriter Excel backend. Saved workspace
  runs 20260904T233514Z/233719Z/233914Z/234054Z recorded 2/13, 3/13, 2/13, 2/13.
  Exercises a Python I/O extension point.

Those older pandas runs were graphless and used island-packet final selection.
They establish nonzero retrieval potential, not controlled baselines for this runtime.
The pandas denominators are the complete reference oracle sets, unlike the explicit
four authored focal files reported for TypeScript (whose full PR oracle has 46 files).

## Results

All eight runs completed successfully. Retrieval tokens are summed once from provider
usage on `llm_response_received` events, excluding request analysis and embeddings.

| Case | Run (UTC) | Oracle overlap | Retrieval tokens | Coverage / sufficient |
| --- | --- | --- | ---: | --- |
| TypeScript 35468 | run-20260915T022328Z | 4/4 focal | 102293 | partial / false |
| TypeScript 35468 | run-20260915T022339Z | 3/4 focal | 103095 | partial / false |
| Vue 10519 | run-20260915T022309Z | 1/2 | 52929 | partial / false |
| Vue 10519 | run-20260915T022319Z | 1/2 | 55553 | partial / false |
| pandas groupby 14942 | run-20260915T022739Z | 3/15 | 130301 | partial / false |
| pandas groupby 14942 | run-20260915T023200Z | 3/15 | 92162 | partial / false |
| pandas Excel 4542 | run-20260915T022747Z | 2/13 | 72343 | partial / false |
| pandas Excel 4542 | run-20260915T023027Z | 3/13 | 69710 | partial / false |

Groupby implementation overlap is 2 in both runs; Excel implementation overlap is
1 then 2. Total measured retrieval usage is **678386 tokens**. All eight retain
partial/false status: file overlap is not proof of complete behavioral evidence.
TypeScript's 4/4 result is not stable across these repeats. Vue repeats the one-file
final result. Both additional cases produce nonzero results in both executions.

The second TypeScript final set lacks Helpers; both Vue final sets contain props.js
but not props.spec.js. These statements describe final selection only, not a claim
that the missing final files never appeared earlier in retrieval.

Full scorecards, run metadata and traces live under
`C:/Programming/guidedInteligence_testcases/<case>/runs/<run>/`.
