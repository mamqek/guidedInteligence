# Owner-comparison shortlist experiment (rejected)

## Historical audit

The audit parsed 95 grouped owner-comparison calls from August 25–26. Among 310 file groups from which the LLM
selected at least one owner, 585 owners were selected. A hard first-ten prefix retained 443 selections (75.7%) and
retained every selected owner in only 195 groups (62.9%). There were 142 selected owners below position ten.

Reordering the same candidates using only currently serialized navigation signals did not solve the loss:

| Ten-item policy | Selected owners retained | Groups retaining every selection |
|---|---:|---:|
| Existing order prefix | 443 / 585 | 195 / 310 |
| Best retrieval rank, then support | 434 / 585 | 187 / 310 |
| Dense/sparse and obligation agreement, then rank | 437 / 585 | 186 / 310 |
| Four rank leaders + four agreement leaders + ordered fill | 444 / 585 | 194 / 310 |

Deep selections included `invalidateProjectAndScheduleBuilds`, `queueReferencingProjects`,
`forEachReferencingModulesOfExportOfAffectedFile`, `Project::updateGraph`, and issue-relevant test scenarios. In the
measured TypeScript run `run-20260826T141453Z`, `builderState.ts` owners `updateShapeSignature` and
`updateExportedModules` occupied positions 11 and 12 and both became qualified final evidence. A deterministic
ten-item prefix would therefore have removed the second implementation Oracle from that run.

## Proposed isolated experiment

Construct at most ten candidates per file from explicit, auditable strata rather than a single scalar sort:

- best retrieval-supported owners;
- owners supported by both dense and sparse channels;
- distinct retrieved source regions;
- distinct callable, state, diagnostic, and test-scenario responsibilities;
- exact request anchors and exact structural target hints;
- at most one candidate from a substantially redundant structural-owner family.

The experiment must replay saved comparison payloads before any actual pipeline run and report retention of prior
semantic selections, payload characters, per-file candidate concentration, and every previously final owner omitted
by the shortlist. Simple rank/support-only variants are rejected by the historical audit and must not be retried as
the proposed semantic-diversity shortlist.

## Fixed implementation boundary

- The shortlist runs after the existing ranked file-prefix admission decision. Payload savings do not admit more
  files or change Qdrant, CodeGraph resolution, canonicalization, or file ranking.
- Each admitted file keeps at most ten owners in the initial owner-comparison request.
- Owners omitted by deterministic shortlisting become deferred. They are not recorded as LLM-rejected dormant
  owners and remain eligible for ordinary deferred inspection.
- The global owner-comparison LLM, 24-owner ceiling, qualification, controller, and final selection remain unchanged.
- The shortlist belongs in one cohesive initial-owner shortlist module and emits per-owner selection strata and
  lifecycle counts to the trace.

## Attempt sequence and acceptance

At most three implementation variants are allowed.

1. Morphology-aware semantic/diversity strata using obligation overlap, exact anchors, dense/sparse agreement,
   retrieval rank, source-region diversity, responsibility diversity, and nested-owner family suppression.
2. If attempt 1 loses a central mechanism in focused LLM replay, adjust only the measured missing stratum or family
   rule; do not add testcase paths or symbols.
3. A final bounded refinement is permitted only for a remaining generalizable failure.

Focused acceptance requires deterministic repeatability, no group above ten owners, retention of the measured
BuilderState `updateShapeSignature`/`updateExportedModules` pair and Pandas `Series::_binop`, complete deferred
lifecycle accounting for shortlist omissions, a materially smaller request, and two real shortlisted comparison
calls that retain coherent Builder, BuilderState, watch, and solution-build mechanisms without one-file takeover.

Only after focused acceptance may two actual TypeScript pipelines run with final evidence selection enabled and
explanation generation skipped. Revert if both actual runs regress implementation-Oracle retention or the omitted
owners are required but unreachable.

## Offline design screening

The strongest pre-implementation policy retained 591 of 669 historical LLM-selected owners across 346 selected file
groups (88.3%) while preserving the measured BuilderState pair and Pandas `_binop`. It still omitted 26 selected
owners that later appeared in final evidence. These included deep watch test helpers, builder/tsbuild functions, one
Pandas flex factory, and structurally unresolved Vue ranges. This is a warning boundary rather than acceptance:
attempt 1 must show that the fresh LLM can choose coherent alternatives from the shortlist and that deferred recovery
preserves the omitted lifecycle.

## Result ledger

| Step | Attempt | Focused run 1 | Focused run 2 | Cost change | Decision | Remaining issue |
|---|---:|---|---|---|---|---|
| Ten-owner semantic/diversity shortlist | 1 | 13/14 prior selections retained; coherent fresh selection | 20/21 retained; coherent fresh selection | Comparison tokens reduced | Rejected after actual-pipeline comparison | Final Oracle retention 2/3 versus baseline 3/4 |

## Measured results — 2026-08-27

### Focused replays

| Saved run | Owners before / after | Serialized characters before / after | New selections | Comparison tokens before / after |
|---|---:|---:|---:|---:|
| `run-20260827T023945Z` | 168 / 127 | 53,190 / 42,218 | 15 | 23,543 / 17,939 |
| `run-20260827T024536Z` | 173 / 110 | 53,138 / 36,993 | 19 | 23,033 / 15,919 |

The first shortlist retained 13/14 previous selections, excluding `builderState.ts::updateSignaturesFromCache`.
The second retained 20/21, excluding `watchPublic.ts::createWatchProgram::createNewProgram`. Both excluded owners
had appeared in the corresponding previous final evidence. The fresh LLM selected coherent alternatives, including
Builder/BuilderState state propagation and watch/solution-build owners. Largest selected-file shares were 4/15 and
3/19. Artifacts are in `testing/codeRepoQA/owner-shortlist-replays/`.

Replay limitation: these inputs reconstruct the saved compact owner/source payload, including synthetic provenance
from aggregate support counts. They are not an exact replay of the full original source views and provenance used
by runtime shortlisting. They establish comparison feasibility, not pipeline acceptance.

### Integration correction and excluded diagnostics

The initial implementation left shortlist omissions in deferred state but omitted the `same_path_alternative`
reason needed by the existing deferred **same-file search-seed** route. Ordinary `InspectDeferredObservation` was
already possible; this was not total loss of deferred access. The reason was added without broadening existing
relevance checks, and an exact-anchor edge case was fixed so later strata cannot exceed ten after anchors fill it.
The corrected implementation passed 100 focused tests, including lifecycle and hard-limit tests.

Pre-correction runs are retained as diagnostics, not acceptance of the corrected implementation:

| Run | Coverage / sufficient | Final items | Implementation Oracles | Retrieval tokens |
|---|---|---:|---:|---:|
| `run-20260827T032635Z` | partial / false | 10 | 3 | 93,277 |
| `run-20260827T033121Z` | partial / false | 10 | 2 | 84,855 |

### Corrected actual-pipeline comparison

All runs used the existing TypeScript index (`index_rebuilt=false`), GPT-5.6 Luna, dormant completion disabled,
unchanged query/file-admission/controller settings, final selection enabled, and explanation generation skipped.

| Run | Compared owners | Comparison tokens | All retrieval tokens | Final items | Implementation Oracles | Coverage / sufficient |
|---|---:|---:|---:|---:|---:|---|
| Baseline `run-20260827T023945Z` | 168 | 23,543 | 102,546 | 12 | 3 | partial / false |
| Baseline `run-20260827T024536Z` | 173 | 23,033 | 146,101 | 12 | 4 | partial / false |
| Shortlist `run-20260827T033557Z` | 114 | 16,312 | 102,103 | 11 | 2 | partial / false |
| Shortlist `run-20260827T034005Z` | 96 | 15,125 | 90,571 | 12 | 3 | partial / false |

Same-run admission and shortlist measurements isolate the actual size change:

- `033557Z`: 17 admitted files; 171 -> 114 owners; 57 deferred omissions; complete comparison input
  59,369 -> 43,492 characters (38,210 serialized payload). Round-zero partition:
  `327 = 15 selected + 213 deferred + 99 dormant`.
- `034005Z`: 14 admitted files; 166 -> 96 owners; 70 deferred omissions; complete comparison input
  58,589 -> 38,832 characters (33,853 serialized payload). Round-zero partition:
  `376 = 19 selected + 280 deferred + 77 dormant`.
- Maximum group size was ten in both; the shortlist did not alter the already-admitted file set or backfill files.
  The 17/14 admitted-file difference is upstream variation, not an effect of shortlisting.
- Comparison-token savings are measured, but the entire end-to-end saving is not attributable to shortlisting:
  the second baseline had a conditional fourth round and a malformed-response retry, while both variants had three
  rounds. Final quality did not improve.

Proof: [033557Z admission](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260827T033557Z/retrieval-trace.jsonl:53),
[shortlist](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260827T033557Z/retrieval-trace.jsonl:54),
[comparison](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260827T033557Z/retrieval-trace.jsonl:59),
[lifecycle](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260827T033557Z/retrieval-trace.jsonl:61);
[034005Z admission](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260827T034005Z/retrieval-trace.jsonl:53),
[shortlist](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260827T034005Z/retrieval-trace.jsonl:54),
[comparison](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260827T034005Z/retrieval-trace.jsonl:59),
[lifecycle](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260827T034005Z/retrieval-trace.jsonl:61).

### Specific behavior and loss boundaries

- In `033557Z`, `updateShapeSignature`, `updateExportedModules`, `forEachReferencingModulesOfExportOfAffectedFile`,
  `verifyTransitiveReferences`, and its `verifyScenario` helper survived shortlisting. Owner comparison selected the
  main transitive-reference owner and `verifyProjectChanges`. Qualification saw a configuration-deletion scenario,
  assigned navigation-only support, and requested the missing wildcard/interface-edit scenario. The missing final
  watch Oracle therefore was not caused by those owners being removed by the shortlist. See
  [qualification](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260827T033557Z/retrieval-trace.jsonl:87).
- All 57 omissions reached deferred auditing. A shortlisted-out `FileInfo` seeded a round-1 `ExpandWithinFileHandoff`
  returning three snippets. The also-omitted `getNextInvalidatedProject` was inspected only in round 3 and eventually
  reached final rank 2. This demonstrates real recovery, but also delayed access to a useful mechanism owner. See
  [seed execution](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260827T033557Z/retrieval-trace.jsonl:456),
  [round-3 inspection](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260827T033557Z/retrieval-trace.jsonl:1256),
  and [final ledger](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260827T033557Z/retrieval-trace.jsonl:1654).
- In `034005Z`, all 70 omissions reached deferred auditing. `introduceError` and `verifyDependencies` were omitted
  by shortlisting, inspected through ordinary deferred actions in rounds 2/3, and selected finally at ranks 10/12.
  Both were navigation-only with no supported obligations; each still requested the surrounding scenario and its
  assertions. Recovering the file therefore did not complete the missing behavior chain. See
  [introduceError inspection](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260827T034005Z/retrieval-trace.jsonl:727),
  [qualification](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260827T034005Z/retrieval-trace.jsonl:740),
  [verifyDependencies inspection](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260827T034005Z/retrieval-trace.jsonl:1084),
  and [qualification](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260827T034005Z/retrieval-trace.jsonl:1093).

## Decision and retained artifacts

Rejected and runtime reverted. The policy materially reduced comparison size but did not show non-regressing final
quality: implementation-Oracle retention was 2/3 versus 3/4 in the immediate baseline pair. Stochastic upstream
inventories and LLM decisions prevent assigning the whole quality difference to shortlisting, but they do not provide
evidence for retaining it either. No testcase-specific tuning or additional ranking variant was added to chase these
outcomes.

The [reproducible implementation patch](artifacts/owner-comparison-shortlist-attempt-1.patch) includes the corrected
runtime, focused tests, and replay utility. It passes `git apply --check` against the restored baseline. All 95 baseline
owner-comparison/qualification-first tests pass after rollback. Replay artifacts and actual run directories remain.

## Status

Rejected; no shortlist behavior remains enabled. IOC-1 remains open.
