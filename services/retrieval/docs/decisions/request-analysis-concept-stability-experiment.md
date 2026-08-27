# Request-analysis conceptual-query stability experiment

## Problem and fixed boundary

The retained exact-anchor normalization stabilizes paths, source symbols, errors, commands, and versions, but the
LLM still supplies the conceptual `search_terms` used to enrich obligation-specific dense queries. Identical
TypeScript 35468 analyses have alternated between relational mechanism concepts and generic or reproduction-local
terms such as `Session`, `interface`, `pure`, `index`, `main`, `project`, and `error`.

- Case: `microsoft-TypeScript-35468` at snapshot `f7860b048037bd74021ec0557a62688ec57e33c1`.
- Executed code: `classify_intent` only.
- Not executed: Qdrant, CodeGraph, qualification, controller rounds, final selection, or explanation generation.
- Each attempt is executed twice with the current workspace request-analysis model and configuration.
- At most five attempts are allowed. Only the smallest measured failure changes between attempts.

## Intended behavior

1. Preserve a deterministic core from explicitly declared search terms and request-level relational concepts.
2. Keep reproduction entities, observable outcomes, and repository mechanism concepts distinct.
3. Do not turn reproduction path basenames into free-standing global search terms.
4. Exclude generic single-word additions unless their syntax makes them a distinctive repository identifier.
5. Prefer relational multiword concepts that express a mechanism or state transition.
6. Place bounded LLM-derived additions after the stable core rather than treating every addition equally.

## Acceptance criteria

Both repetitions must:

- begin with materially equivalent core concepts covering project references, wildcard re-exports, and watch mode;
- contain no free-standing `pure`, `index`, or `main` terms;
- contain no generic free-standing `type`, `interface`, `project`, or `error` terms;
- retain mechanism-oriented relational concepts rather than only reproduction vocabulary;
- preserve the existing exact-anchor inventory and the direct-import/non-watch/watch contrast;
- avoid asserting an unverified root cause.

## Expected effects and risks

- Expected quality: obligation dense queries receive a stable request-level core and fewer generic tails.
- Expected token impact: no additional LLM call; negligible prompt growth and a bounded search-term list.
- Known risk: aggressive filtering can remove a useful single-word domain concept or retain an apparently specific
  phrase whose semantics are still irrelevant.
- Comparison: exact search-term inventory, order, obligation propositions, and anchor references are compared across
  the two repetitions. This focused experiment does not claim downstream retrieval improvement.

## Attempt ledger

| Attempt | Change | Run A | Run B | Quality | Stability | Decision |
|---|---|---|---|---|---|---|
| 1 | Prompt separates stable core, mechanism terms, outcomes, and reproduction entities | `concept-attempt-1-run-1.json` | `concept-attempt-1-run-2.json` | Passed | Passed | Retained |

## Result

Both repetitions produced the same ordered core:

1. `project references`
2. `reexports`
3. `wildcard re-exports`
4. `watch mode`
5. `dependency invalidation`

Run 1 added one secondary mechanism phrase, `referenced-project rebuild state`; run 2 stopped after the shared five.
Neither run emitted a reproduction basename or a generic single-word term. Both preserved the previously accepted
exact-anchor inventory, the direct-import versus wildcard-re-export contrast, and the watch versus non-watch contrast.
The propositions differed in wording but retained the same six mechanism boundaries and did not assert a root cause.

Attempt 1 is retained, so attempts 2–5 were not executed. The result establishes focused request-analysis stability;
two subsequent actual-pipeline runs then evaluated its downstream behavior with final evidence selection enabled and
explanation generation skipped.

## Actual-pipeline follow-up

An initial invocation, `run-20260827T023849Z`, is invalid and excluded: the invoking shell selected an old Node
runtime without `node:sqlite`, so CodeGraph failed before retrieval. The same command was rerun with the bundled Node
runtime; no deterministic or sparse-only fallback was used.

| Run | Concepts after the shared core | Dense mechanism ranks (trigger / ordered / state) | Global file ranks (`watchMode` / `builder` / `builderState`) | Final implementation-Oracles | Coverage | Retrieval tokens |
|---|---|---|---|---:|---|---:|
| `run-20260827T023945Z` | `dependency invalidation`; `re-export dependency transition` | 1 / 2 / 1 | 1 / 10 / 3 | 3 | `partial/false` | 102,546 |
| `run-20260827T024536Z` | `re-exported interface type`; `project invalidation through re-export changes` | 1 / 2 / 1 | 1 / 9 / 3 | 4 | `partial/false` | 146,101 |

The three dense ranks refer to `watchMode.ts` for `explain_trigger`, `builder.ts` for
`explain_ordered_mechanism`, and `builderState.ts` for `explain_state_changes`. Before stabilization, comparable runs
`run-20260826T140738Z` and `run-20260826T141453Z` produced ranks `missing / 13 / 6` and `2 / 1 / 1`. The new pair is
therefore repeatable at the intended query boundary.

The complete pipeline remains variable. Canonical owner candidates were 408 and 316; owner comparison selected 14
and 21; global file admission retained 20 and 17 files. The second run executed four controller rounds instead of
three and retried one malformed structured response, accounting for most of its higher token total. Both runs remained
partial because controller/consolidation did not establish every requested handoff, despite retaining three and four
implementation-Oracles.

The second run nevertheless showed a materially stronger consolidation result: subject, trigger, ordered mechanism,
and state changes were jointly supported; only resulting effect and why remained partial because no selected source
proved the three-way diagnostic contrast or the final causal link. In the first run only state changes was jointly
supported, while why remained unresolved. This improvement is consistent with the better final Oracle set, but cannot
be attributed solely to conceptual terms because owner comparison and controller choices remain LLM-variable.

Decision: retain the conceptual-query prompt change. It improved repeatability at the targeted initial dense-query
boundary and did not regress final Oracle retention in this pair. It does not stabilize generated obligation wording,
secondary conceptual additions, owner-candidate volume, controller behavior, or sufficiency.
