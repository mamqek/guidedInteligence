# Shared snippet selection and initial admission experiment

## Baseline and scope

Branch: `codex/snippet-first-admission`, from `codex/dormant-island-reconnection` at `7c50ba2`.
The starting working tree includes the qualification-rationale experiment and its artifacts. Tracked baseline
snapshot: `ea8a285d79f1692f88d79c4b27d8b99007301796` (saved stash, not applied/removed). Existing untracked
artifacts remain untouched. Compare against `run-20260828T021522Z` and `run-20260828T021533Z`:
partial/false, two implementation Oracle files each, 87,747 / 107,062 tokens.

Observed boundary FPK-1/IOC-1: complete-file initial admission used 90,777 characters for four files/105 owners
in 021522Z; editorServices alone added 43 owners/40,613 characters, with zero LLM selections. In 021533Z,
four files/76 owners used 63,699 characters. Builder was excluded before comparison in both runs.

## Independently testable steps

1. A common read-only selection view, adapters for discovery and qualified candidates, and an admission engine
   with injected ranking and exact payload measurement. Unknown qualification/connections stay unknown; retrieval
   associations never become semantic support. Test identity, unknown versus empty state, source preservation,
   deterministic ordering, duplicate rejection, boundary equality, crossing-item retention and lifecycle accounting.
2. Initial owner-comparison admission uses global snippet priority: exact anchor, recurrence, rank, score,
   normalized path, line, ID tie-breaker. File groups only serialize admitted snippets. No per-file cap, cost
   penalty, binary coverage reservation, new prompt or source-format change. Whole-file ranking is removed from
   this active boundary. Unadmitted snippets remain deferred; same-file omissions keep the existing same-file
   deferred reason. Only LLM-unselected compared snippets become dormant.
3. Replay saved canonical inputs and prepared source cards twice; require exact reproduction of the recorded
   baseline request before trusting comparisons. Use real owner-comparison calls on two saved inputs, then run
   TypeScript twice with final selection on and explanation off. No indexing, model or configuration change.
4. Final-selection snippet admission is a separate later experiment, not activated here. The qualified adapter
   exposes a shared view but does not change final eligibility, flow scoring, rendering or connections.

## Expected impact and risks

Expected: more files compete without wholesale admission of weak same-file alternatives; smaller threshold
overshoot. Total tokens need not fall: admitting better evidence can cause additional controller work. Global
recurrence still favors highly repeated generic owners; no promise of semantic relevance or file diversity follows
from the shared interface. Source cards and qualification remain unchanged. Larger group/schema overhead and
omission of complementary same-file owners are explicit regression risks.

## Measurements and decision

Record ranking factors/positions, exact incremental request cost, per-file admitted/omitted counts, comparison
selections, deferred/dormant accounting, and previous semantic/final-owner retention. Audit Oracle and non-Oracle
sources through comparison, qualification, controller and final selection; do not equate Oracle overlap with proof
of a complete mechanism. Specifically audit Helpers file trace creation, exact-source acceptance, endpoint
qualification, file-trace LLM eligibility and later island preservation. Its absence cannot be attributed solely
to helper qualification.

At most three implementation variants. Retain only repeatable boundary improvement without demonstrated
end-to-end quality regression; revert a clearly regressing change, report questionable results for user review.
Save all runs and failures, including token totals and partial/sufficient outcomes. No deterministic LLM fallback.

| Step | Attempt | Focused 1 | Focused 2 | Cost | Decision | Remaining issue |
|---|---:|---|---|---|---|---|
| Shared view and initial snippet admission | 1 | Exact saved-input replay + valid LLM selection | Exact saved-input replay + valid LLM selection | Comparison tokens lower; total tokens higher | Retained as a measured initial-admission improvement | Recurrence bias and final-flow cutoff remain |

## Attempt 1 progress

221 focused/relevant unittest checks pass (pytest is not installed; no dependency added).
Saved-input artifacts: `testing/codeRepoQA/snippet-admission-replays/saved-021522-llm.json` and
`saved-021533-llm.json`, with literal requests/responses in adjacent JSONL. Both reproduce the complete original
comparison payload and measured baseline cost exactly, and repeat deterministic admission identically.

| Saved input | Files old/new | Snippets old/new | Request chars old/new | Prior selections still admitted | New comparison tokens |
|---|---:|---:|---:|---:|---:|
| 021522Z | 4 / 16 | 105 / 66 | 90,777 / 60,679 | 3 / 6 | 16,889 |
| 021533Z | 4 / 20 | 76 / 71 | 63,699 / 60,270 | 7 / 11 | 17,426 |

Builder's forEachReferencingModulesOfExportOfAffectedFile is admitted and LLM-selected in both replays. New
selections are 8/20 owners. The second comparison also selects questionable declaration-symlink test constants
and decorators; this is not accepted as semantic improvement. Unchanged recurrence-first ranking puts
updateShapeSignature at positions 185/120 (recurrence one), outside admission, even though its best retrieval
rank in the second saved input is one. This is the ranking tradeoff under examination, not a source-visibility
failure. No weights are tuned before the live comparison.

Actual TypeScript acceptance runs (same index/config/model, no explanation, final selection enabled):

| Repetition | Run | State |
|---|---|---|
| 1 | run-20260828T131737Z | Completed partial/false; 3 implementation Oracle files; 101,538 retrieval tokens |
| Diagnostic | run-20260828T131742Z | Failed before retrieval: structural sync lock contention, pending references 945 |
| 2 | run-20260828T132110Z | Completed partial/false; 3 implementation Oracle files; 112,414 retrieval tokens |

131737Z's ordinary structural synchronization removed 12,273 stale indexed file records (not source files).
It then reported zero pending references and exactly the baseline graph counts: 14,091 files, 97,250 nodes,
202,921 edges. The second simultaneous startup returned the dependency's lock-unavailable result
(filesChecked=0/durationMs=0) and observed the intermediate pending references; it is not an acceptance run.
No forced rebuild, index-scope change, health-check bypass or selector fix was used. The replacement starts
after the first synchronization completes. Graph counts alone are not a byte-for-byte graph identity proof;
the cleanup is disclosed as an environmental startup difference.

The qualified-candidate adapter is tested but not connected to final admission in this step. Controller and
final-flow eligibility/scoring are unchanged. Historical replay scripts for previous admission contracts are
archival; this experiment uses its dedicated exact-payload replay rather than a production compatibility branch.

## Completed live comparison

Both measured runs reused the existing Qdrant index (`rebuilt=false`) and unchanged configuration, used three
controller rounds, kept final selection enabled, and skipped explanation. All runs are tagged with
`experiment_annotation` and an adjacent `experiment-annotation.json`; the startup failure is explicitly excluded
from acceptance. Audits and literal replay payloads are in `testing/codeRepoQA/snippet-admission-replays/`.

| Measure | 131737Z | 132110Z |
|---|---:|---:|
| Canonical snippets | 476 | 317 |
| Compared snippets / files | 64 / 21 | 71 / 22 |
| Initial complete request characters | 60,111 | 60,654 |
| Owner-comparison selections / files | 16 / 10 | 20 / 13 |
| Owner-comparison tokens | 16,941 | 17,637 |
| Qualification tokens | 33,566 | 35,908 |
| Coverage tokens | 31,464 | 37,278 |
| Final-selection tokens | 17,653 | 19,781 |
| Connected-source-context tokens | 1,914 | 1,810 |
| All retrieval tokens | 101,538 | 112,414 |
| Final returned evidence | 12 | 14 |
| Implementation Oracle files | 3 | 3 |
| Coverage / sufficient | partial / false | partial / false |

Combined comparison tokens: 34,578 versus baseline 42,851 (-19.3%). Combined retrieval tokens: 213,952 versus
194,809 (+9.8%). The latter is not a controlled causal delta: query inventories and qualified candidate pools
differ. The changed initial admission has controlled counterfactual evidence below; final quality remains partial.

Evidence links (bare parenthesized line numbers below refer to the corresponding run's retrieval trace):

- Run 1: [admission](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260828T131737Z/retrieval-trace.jsonl:54),
  [comparison](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260828T131737Z/retrieval-trace.jsonl:59),
  [final flows](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260828T131737Z/retrieval-trace.jsonl:1722),
  [scorecard](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260828T131737Z/scorecard.json).
- Run 2: [admission](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260828T132110Z/retrieval-trace.jsonl:54),
  [comparison](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260828T132110Z/retrieval-trace.jsonl:59),
  [final flows](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260828T132110Z/retrieval-trace.jsonl:1702),
  [scorecard](C:/Programming/guidedInteligence_testcases/microsoft-TypeScript-35468/runs/run-20260828T132110Z/scorecard.json).
- Controlled replays: [run 1](C:/Programming/guidedInteligence/testing/codeRepoQA/snippet-admission-replays/live-131737-counterfactual.json),
  [run 2](C:/Programming/guidedInteligence/testing/codeRepoQA/snippet-admission-replays/live-132110-counterfactual.json).

### Same-input counterfactuals, not assumptions about upstream variation

The replay executes the whole-file policy from baseline snapshot `ea8a285d79f1692f88d79c4b27d8b99007301796`
on each live run's canonical pool and exact saved source cards. Reconstructed live request equals the literal
recorded request before computing the counterfactual. No new retrieval, graph operations, or simulated LLM result.

| Live input | Old whole-file files / snippets / chars | New snippet-first files / snippets / chars |
|---|---|---|
| 131737Z | 7 / 92 / 67,818 | 21 / 64 / 60,111 |
| 132110Z | 4 / 91 / 69,798 | 22 / 71 / 60,654 |

The first old prefix excludes Builder; the new prefix admits forEachReferencingModulesOfExportOfAffectedFile
(position 3) and getNextAffectedFile. Both qualify direct (100); getNextAffectedFile reaches final rank 4, and
the later-recovered getSemanticDiagnostics reaches rank 8. This is concrete compiler evidence gained through
admission rather than merely a larger file count. In run 2, forEachReferencingModulesOfExportOfAffectedFile
qualifies direct (107/514) and reaches final rank 9.

BuilderState enters comparison with two owners in run 1; updateShapeSignature qualifies direct and reaches
rank 7. In run 2, its initial three owners remain deferred (positions 187, 188, 243); the unchanged controller
subsequently qualifies getReferencedByPaths in round 2 (924) and getFilesAffectedByUpdatedShapeWhenModuleEmit in
round 3 (1306), finally selecting them at ranks 11/10. Do not attribute direct initial admission of BuilderState
to this second run: it did not happen.

### Ranking and unresolved loss boundaries

- Initial recurrence is still powerful: run 1 ranks the OutOfDateWithUpstream constant second with recurrence 5;
  ConfigFileExistenceInfo fifth with recurrence 5 despite best rank 7; trimString tenth with recurrence 4/best
  rank 9. These are navigation/retrieval signals, not proof of the reported compiler mechanism. No extra penalty
  or role heuristic was introduced. Builder's position 3 is supported by recurrence 5/best rank 2; the semantic
  check confirms its body shows exported-map and changed-signature gates.
- The same policy puts useful single-query owners below the boundary. In run 2, forEachFilesReferencingPath
  has best rank 1 but recurrence 1, placing it 152nd; it stays deferred and never qualifies. Its source at
  builder.ts:546-549 calls forEachFileAndExportsOfFile, connecting that helper to the upstream propagation function.
  forEachFileAndExportsOfFile itself starts deferred at position 90, is recovered and qualifies direct for four
  obligations (514), but final flow construction records zero outgoing transitions and labels it supporting;
  it is rejected as `rejected_no_new_causal_responsibility` (1702), before budgeting. The intermediate owner is
  missing from the final pool, so the qualified-helper exception cannot assume that connection. This is a
  concrete residual loss, not evidence that all useful snippets now rank highly.
- Run 2's verifyTransitiveExports is qualified direct (107), with a visible interface edit and queued watch
  callbacks. getSemanticDiagnostics also qualifies direct (514), visibly draining next-affected diagnostics.
  Both are absent from the final LLM input because their flows follow the unchanged 45K crossing boundary (1702).
  Their inventories contain visible calls but zero represented outgoing transitions; they receive no established
  outgoing connection from those calls alone. They remain relevant follow-ups, not proof of the exact issue.
- Run 1 final input is 48,554 serialized characters (1724); only the Session::updateErrorCheck flow is budget
  excluded (1722). Run 2 is 53,100 (1704), with 28 remaining flows excluded after crossing (1702). Many excluded
  flows reuse already-admitted candidates; this is not 28 unique snippet losses. Fourteen inventory candidates
  are absent from that request: thirteen encounter the budget boundary, while forEachFileAndExportsOfFile is
  excluded by the earlier responsibility gate. No explicit connections were budget-excluded in either run.
- The final LLM selects eight snippets in run 1 and eleven in run 2. Post-LLM island preservation appends four
  and three respectively. Run 1's appended Project::updateGraphWorker and Session::updateErrorCheck belong to
  tsserver rather than the requested tsc build-watch path; their recurrence/qualification made them eligible,
  but their returned ranks 10/12 are not an endorsement by final selection. WatchMode also survives via that
  preservation path, not because final selection established the exact reported test scenario.

### Helpers: a different boundary than the preceding two runs

Neither live run qualifies a tscWatch/helpers.ts snippet or creates a WatchMode-to-Helpers file trace. The old
`source_island_not_selected` loss therefore does not explain this pair: no such trace reaches that gate.

- 131737Z: no exact Helpers hit in initial dense/sparse results and no canonical Helpers snippet. Raw ranges in
  other files nevertheless contain verifyTscWatch calls: 51 channel occurrences / 27 distinct ranges, read from
  the logged ranges in the unchanged source snapshot. WatchMode's verifyTransitiveReferences is deferred as
  insufficient at round zero (100); the controller concentrates on compiler chains and never materializes an
  eligible Helpers trace. Final file-trace creation (1718) contains only BuilderState and server Project.
- 132110Z: four exact initial Helpers hits (dense/sparse trace lines 25/40) resolve into four canonical snippets:
  createWatchOfConfigFile, fileChangeDetected, HostOutputWatchDiagnostic, checkOutputErrorsIncremental.
  They rank 217, 218, 251, 252 and remain deferred (54); none is verifyTscWatch. Other raw ranges contain that
  call in 60 channel occurrences / 28 distinct ranges. No Helpers snippet qualifies later. File-trace creation
  (1698) contains only sys.ts and BuilderState, and final trace evaluation (1708) cannot select Helpers.

These counts distinguish exact helper-owner retrieval from source-grounded leads. More watch test snippets
alone do not guarantee an executed file-level handoff; no scheduling/eligibility change was made here.

## Decision

Keep the shared interface and initial snippet-first admission on this experiment branch. Both saved-input
replays and both live same-input counterfactuals show broader file access with less whole-group waste; both
actual runs preserve Builder plus BuilderState and WatchMode (3 Oracle files versus baseline 2). This is an
initial-boundary improvement, not a complete/reliably sufficient retriever. Final-input snippet admission has
not been implemented or claimed accepted. No further tuning or controller change is included. The remaining
recurrence bias, missing intermediate connections, Helpers discovery, and final-flow cuts are recorded for review.

Final verification: 221 focused/relevant checks pass. Optional full-owner bounds and source facts are exposed
by the adapters and tested; these metadata fields do not enter prompts, ranking or cost calculations. There is
no added third-party dependency, fallback LLM behavior, per-file cap, or production compatibility branch.

## 2026-08-29 restoration verification

After subsequent final-admission experiments were rejected, this version was restored from the pre-joint-selection
snapshot and committed as `3e68d44`. Two unchanged actual TypeScript repetitions again retain all three central
Oracle files:

| Run | Evidence | Oracle files | Retrieval tokens | Final request |
|---|---:|---:|---:|---:|
| run-20260829T003915Z | 13 | Builder, BuilderState, WatchMode | 89,424 | 10 candidates / 7 flows / 35,527 chars |
| run-20260829T004122Z | 12 | Builder, BuilderState, WatchMode | 102,356 | 13 candidates / 9 flows / 50,803 chars |

Both are partial/false and skip explanation generation. The first retains BuilderState module-emit propagation
and reverse-reference lookup. The second retains the reverse-reference lookup and signature-cache update. Both
retain WatchMode source. These are actual-pipeline results, not saved-input replays. Full measurements are also
recorded in the retrieval changelog.
