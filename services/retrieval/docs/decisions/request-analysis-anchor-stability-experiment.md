# Request-analysis anchor stability experiment

## Problem and baseline

Two otherwise unchanged TypeScript 35468 runs produced materially different request analyses before retrieval:

- `run-20260826T080457Z` classified conceptual phrases such as `project references` as identifiers, split the command into weak literals, omitted `type error`, and attached generic anchors to `explain_state_changes`.
- `run-20260826T080907Z` retained the complete command and error phrase and produced a more useful state-change proposition. That later moved `builderState.ts` from global file position 36 to position 10.

The first LLM call currently invents the anchor categories and search terms. Deterministic normalization only replaces paths and partially validates symbols. The second LLM call independently chooses stage propositions and anchor references. The experiment therefore judges both the anchor inventory and its use in evidence obligations.

## Fixed boundary

- Case: `microsoft-TypeScript-35468` at snapshot `f7860b048037bd74021ec0557a62688ec57e33c1`.
- Input: the same title/body and repository facts used by the measured runs.
- Executed code: `classify_intent` only.
- Not executed: retrieval planning, Qdrant, CodeGraph, qualification, controller rounds, final evidence selection, or explanation generation.
- Model/configuration: the current workspace request-analysis LLM configuration.
- Each variant is independently executed twice.
- At most five variants may be attempted, as explicitly requested for this experiment.

## Quality and stability criteria

A variant passes only when both repetitions satisfy all of the following without case-specific names or rules:

1. Concept phrases such as project references, wildcard re-exports, and watch mode are search terms rather than identifiers.
2. Identifiers contain only source-level identifier or qualified-member syntax; prose, paths, versions, and command fragments are excluded.
3. Exact paths remain prompt-grounded and stable.
4. A complete command remains one literal instead of becoming separate flags and path fragments.
5. The reported error phrase remains available as error evidence.
6. The reproduction symbol remains available as a supporting symbol without being promoted to the repository's primary mechanism.
7. Evidence-obligation propositions preserve the project-reference/re-export/watch contrast and do not assume a root cause.
8. The two runs have the same anchor inventory by category and materially equivalent obligation anchor assignments. Exact wording may differ when it preserves the same retrieval concepts.

## Attempt sequence

Only the smallest failed boundary is changed between attempts.

1. **Typed extraction instructions.** Define identifiers, literals, errors, and search terms precisely in the existing request-analysis prompt.
2. **Prompt-grounded category normalization.** If attempt 1 remains unstable, introduce generic validation and normalization of LLM-produced categories.
3. **Deterministic explicit-anchor extraction.** If category normalization remains unstable, extract explicit paths, inline commands/literals, named symbols, error phrases, and declared search terms through language-neutral rules; the LLM continues producing intent and conceptual analysis.
4. **Stable stage-anchor assignment.** If the inventory is stable but obligation anchor use is not, separate deterministic anchor relevance from generated proposition wording.
5. **Bounded final refinement.** Address only the specific remaining measured failure. If it still does not pass twice, retain the best of attempts 1–5 and document the instability.

## Expected effects and risks

- Quality: fewer generic anchors and more repeatable retrieval propositions.
- Token/runtime: unchanged number of LLM calls; prompt-only attempts add negligible input text. Deterministic attempts add no model calls.
- Candidate volume: not measured in this stage-only experiment and not changed directly.
- Risks: over-filtering useful repository names, misclassifying prose as literals, or making every stage use the same broad anchors.
- Rollback: a variant is reverted when either repetition loses an explicit useful anchor, produces noisier categories, assumes the cause, or is less stable than the preceding best variant.

## Result ledger

| Attempt | Change | Run A | Run B | Quality | Stability | Decision |
|---|---|---|---|---|---|---|
| Baseline | Current `request_analysis_v2` behavior | `run-20260826T080457Z` | `run-20260826T080907Z` | Mixed | Failed | Replace |
| 1 | Typed extraction instructions | `attempt-1-run-1.json` | `attempt-1-run-2.json` | Failed: generic/file/command fragments remained identifiers and the error was omitted | Failed | Reverted |
| 2 | Prompt-grounded category normalization | `attempt-2-run-1.json` | `attempt-2-run-2.json` | Major improvement; exact categories matched, but `the error` was retained and versions entered repository anchor refs | Passed for inventory only | Refine |
| 3 | Error filtering and anchor-reference guidance | `attempt-3-run-1.json` | `attempt-3-run-2.json` | Strong propositions and clean exact categories | Failed symbol role: `Session` alternated primary/supporting | Refine |
| 4 | Reproduction-type role normalization | `attempt-4-run-1.json` | `attempt-4-run-2.json` | `Session` stable and propositions strong | Failed symbol inventory: model-added `index` appeared once | Refine |
| 5 | Deterministic syntactic symbol inventory | `attempt-5-accepted-run-1.json` | `attempt-5-accepted-run-2.json` | Passed after excluding filename/URL member-like spans | Passed | Retained |

All focused artifacts are stored in [`testing/codeRepoQA/request-analysis-runs`](../../../../testing/codeRepoQA/request-analysis-runs).
The preliminary attempt-5 artifacts record the filename-member parser defect and pre-version-label verification; they
are not acceptance artifacts.

## Retained result

Both accepted repetitions produced exactly:

- paths: `pure/index.ts`, `src/pure/session.ts`, `src/main/index.ts`;
- primary symbols: none;
- supporting symbols: `Session`;
- errors: `type error`;
- literals: `./node_modules/.bin/tsc --build src --watch`, `3.7.2`, `3.8.0-dev.20191203`;
- identifiers: none.

Both retained the declared search terms `project references` and `reexports`, plus the core inferred concepts
`wildcard re-exports` and `watch mode`. Additional conceptual terms still vary because conceptual query formulation
remains an LLM responsibility. The evidence-obligation wording and exact `anchor_refs` also vary, but both accepted
plans preserve the same mechanism boundaries and contrast. This experiment does not claim downstream retrieval
improvement because retrieval was deliberately not run.

The LLM still varies additional conceptual search terms, proposition wording, exact per-stage `anchor_refs`, and
non-retrieval `explicit_targets`. The last item is not consumed by the current retrieval pipeline. These remaining
variations do not change the exact anchor inventory, but downstream stability remains an open acceptance question.
