# Initial File Admission Cost Experiment

## Status

Attempt 1 was initially reverted because the old two-per-file runtime invariant rejected both live responses. After
the separately tested grouped owner-selection contract removed that contradictory invariant, this exact admission
policy was replayed unchanged and is now retained through the TypeScript pre-qualification boundary.

This experiment changed only deterministic file admission before the
existing initial owner-comparison LLM call. It does not change Qdrant retrieval, CodeGraph resolution, canonical
snippet identity, within-file owner candidates, the comparison prompt/schema/model, the 24/two-per-file selection,
or round-zero qualification.

## Observed problem and baseline

TypeScript case `microsoft-TypeScript-35468` pre-qualification runs `run-20260824T223236Z` and
`run-20260824T223430Z` admitted 49/329 and 38/324 files/candidates by filling the literal owner-comparison request to
100,000 and 99,986 characters. They spent 37,960 and 37,847 comparison tokens. Admission currently reserves the first
file associated with each not-yet-covered obligation, then scans the complete ranking and skips any whole file that
does not fit. This lets later small, weak groups consume leftover budget after stronger large groups were rejected.

The isolated evidence-region attempt does not remain in runtime and is not part of this experiment.

## Attempt 1: quality-prefix admission under a preferred request size

### Boundary

- Rank the existing canonical snippet files with the existing exact-anchor, best file-group rank, best file-group
  score, obligation-count, and recurrence tuple.
- Remove binary obligation reservation. Obligation count remains a later ranking tie-breaker; no file can claim an
  obligation and move ahead merely because earlier reserved files did not carry that ID.
- Walk the quality ranking as one prefix. Admit complete file groups while the literal prompt + schema + payload stays
  within a 60,000-character preferred target. Keep 100,000 characters as the unchanged hard safety ceiling.
- Once the next ranked complete file would exceed the preferred target, stop. Do not scavenge later smaller files.
- Permit the first ranked file to exceed the preferred target only when it remains within the 100,000-character hard
  ceiling, so one unusually large best file cannot make the request empty.
- Every nonadmitted canonical snippet remains deferred through the existing lifecycle accounting.

This attempt deliberately introduces no file-role gate, weighted value formula, one-snippet-per-file rule, region
grouping, or additional LLM call. Those would be separately testable changes.

### Expected effects

- Quality: retain a deterministic strongest-file prefix and prevent weak small files from backfilling fragmented
  capacity; preserve every structurally resolved owner inside each admitted file.
- Cost: reduce comparison request size toward 60,000 characters and comparison tokens proportionally; reduce admitted
  candidate and file counts.
- Runtime: slightly reduce comparison serialization/model time; earlier retrieval and CodeGraph work are unchanged.

### Risks

- A high-ranked broad lexical file can still consume substantial capacity.
- A useful file just below the prefix can be deferred without semantic comparison.
- Removing coverage reservation can leave an obligation without an admitted file when retrieval quality ranks all of
  its candidates below the prefix.
- The 60,000-character target is an experimental operating point, not an accepted universal default.

### Verification and rollback

1. Focused tests must prove ranking has no reservation promotion, admission stops at the preferred boundary instead of
   backfilling, the first-file exception remains hard-budget safe, and lifecycle inputs remain complete.
2. Run the actual TypeScript pipeline twice with `--stop-before-round-zero-qualification` under otherwise unchanged
   settings.
3. Record admitted/deferred files and owners, literal comparison characters, comparison tokens, selected/dormant
   owners, obligation representation, and important Builder/BuilderState/watch/test paths.
4. Revert attempt 1 if either run loses central Builder/BuilderState/watch mechanism files before comparison, lifecycle
   accounting fails, request size does not materially fall, or selection becomes less stable/noisier than the saved
   baseline.

## Result ledger

| Step | Attempt | Focused run 1 | Focused run 2 | Cost change | Decision | Remaining issue |
|---|---:|---|---|---|---|---|
| Preferred-size quality-prefix file admission | 1 | 92 tests pass | 92 tests pass | 100K/99,986 chars and 37,960/37,847 tokens -> 53,179/55,334 chars and 20,099/21,509 tokens | Reverted | Both live responses violated the unchanged two-per-file invariant |
| Preferred-size prefix plus grouped selection | 2 | 93 tests pass | 93 tests pass | 59,457/59,956 chars and 22,307/23,756 tokens | Retained through pre-qualification | Downstream acceptance |

## Attempt 1 results

Focused verification passed twice with 92 tests. Configuration and CodeGraph integration checks passed 19 tests
under bundled Node 24.19; the ordinary shell's older Node reproduced the known missing-`node:sqlite` environment
failure and is not behavior evidence.

### Actual run 1 — `run-20260825T032456Z`

- 408 canonical snippets across 87 files entered ranking.
- The quality prefix admitted 159 owners across ten files at 53,179 characters and stopped before `Gulpfile.js`, whose
  marginal 7,632 characters would have produced a 60,811-character request.
- Comparison used 20,099 tokens and selected 13 owners. The selected set retained WatchMode, WatchPublic,
  TsBuildPublic, Builder, BuilderState, and watch diagnostics. One server-session owner remained tangential.
- The model selected four distinct `builder.ts` mechanisms:
  `forEachReferencingModulesOfExportOfAffectedFile`, `isChangedSignagure`, `handleDtsMayChangeOf`, and
  `createBuilderProgram::getSemanticDiagnostics`.
- Runtime rejected the response with `initial_owner_comparison_file_limit_exceeded:g8`; round-zero preparation did
  not execute.

### Actual run 2 — `run-20260825T032649Z`

- 406 canonical snippets across 91 files entered ranking.
- The quality prefix admitted 177 owners across ten files at 55,334 characters and stopped before
  `server/editorServices.ts`.
- Comparison used 21,509 tokens and selected 12 owners. The set retained WatchMode, TsBuildPublic, Builder,
  WatchPublic, BuilderState, and a TscWatch incremental scenario, with no diagnostic catalogue or broad server
  `Project`/`Session` selection.
- The response selected three `tsbuildPublic.ts` owners and three `builderState.ts` owners. All six are plausible
  mechanism evidence; runtime stopped at the first violation with
  `initial_owner_comparison_file_limit_exceeded:g4`.

### Decision

Attempt 1 is reverted because neither actual run completed the unchanged pre-qualification contract. The failure is
not evidence that the narrowed files or selected owners were poor. It shows that reducing comparison breadth made the
model concentrate on several distinct mechanisms in central files, exposing the independently unresolved IOC-1
two-per-file boundary in both repeats. Do not tune the preferred size or restore binary obligation reservation to
hide that conflict. A later authorized experiment should first replace the invalid split prompt/schema/runtime
contract with a semantically coherent global selection contract, then replay this exact admission policy unchanged.

## Attempt 2 results after grouped selection

Actual runs `run-20260825T035631Z` and `run-20260825T035754Z` admitted 172 owners across 14 files at 59,457
characters and 191 owners across 18 files at 59,956 characters. Owner comparison completed at 22,307 and 23,756
tokens. Both runs retained Builder, BuilderState, TsBuildPublic, and watch/project-reference mechanisms; the second
selected three distinct owners from both Builder and BuilderState without takeover. Lifecycle accounting was complete
and qualification preparation fit inside 40,000 characters. The exact 60K policy is retained; controller and final
selection acceptance remain out of scope for these diagnostic-stop runs.
