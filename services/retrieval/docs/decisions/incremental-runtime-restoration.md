# Incremental restoration from the August 29 runtime

> Current checkpoint (September 15): unit-1 cleanup remains applied, plus the narrow
> exact trace-source capacity-ordering repair and testing-only replay/logging support.
> Fresh results: 4/4, 4/4, 3/4, all partial/false; these scores are not causal proof of
> the ordering repair. See trace-source-capacity-ordering.md. Unit 2 remains absent;
> units 3–10 have not been tested in this restoration sequence. Thesis stays outside
> the runtime checkpoint and must remain untouched.

### Recommended next boundary

Unit 2 is the Vue Flow-syntax malformed-callable repair: reject graph `if` blocks
misidentified as functions and recover executable function boundaries rather than a
return-type declaration. The archived patch contains explicit fixtures for both cases.
The earlier TypeScript experiment did not exercise this JS-specific behavior (saved
TS structural output was unchanged). Test the affected Vue case as the positive case,
and TypeScript as a regression control. No new experiment is started by this checkpoint.
Afterward, qualification contract unit 4 precedes owner reevaluation unit 3 because
of their dependency; other units retain the provisional boundaries below.

## Fixed starting point and policy

Source baseline `0e725b4`; branch `codex/aug29-trace-repair-repeat`. Current-version
reference `df75bfc`; later experiments preserved in stash `a43a0c2` are not baseline
restoration targets. Thesis is restored separately and must never be staged, rolled back,
stashed, rewritten, or included in experiment patches. No whole-tree operations.

Baseline runs: `20260914T210202Z`, `211656Z`, `211707Z`: 3/4 each,
partial/false, 109463/109699/113928 retrieval tokens. Different missing focal files;
Helpers in the first two is structural-only. Mean 111030 tokens.

Use the historical workspace npm profile, Node 22.22.0, TypeScript 35468,
`--skip-response-generation --exclude-path openwiki`; final selection stays enabled.
Keep the 83408-document index fixed and use gpt-5.6-luna. Original OpenWiki addition
will explicitly introduce its source connection, not add wiki pages to the code index.

Three actual runs per behavior step. Focused tests precede acceptance. Compare exact
selected source and structural traces, sufficiency, intermediate stage behavior, and tokens.
Accepted changes remain; rejected changes are archived and reversed on scoped paths.
Mixed outcomes require a loss-boundary audit and, if justified, matched confirmation.
No more than three variants per step. A dependency on a rejected change must be explicitly
handled as a combined experiment or skipped, never silently restored. Refactors require
behavior equivalence; behavior changes require demonstrated benefit, not mere plausibility.

## Dependency map / provisional test units

This is not a promise that the newer tree will be fully reinstated. Broad categories
contain multiple units. The final patch boundaries below are verified at each step.

| Unit | Boundary and dependency | Intended effect / cost | Risk and focused verification |
| --- | --- | --- | --- |
| 1 Request-analysis field cleanup | Intent schema/prompt/model and direct consumers; independent | Remove unused outputs; possibly smaller prompt/output | Prompt perturbation; intent/consumer tests and real outputs |
| 2 Callable-owner integrity | JS source AST and CodeGraph bridge; independent | Reject spurious callable identities, preserve real source owners; no added LLM stage | Changed owner resolution; recorded JS fixtures and unchanged TS controls |
| 3 Owner representation reevaluation | Resolve/compare newly inspected source owners | Recompare stronger ranges; potentially more candidates | Displacement; saved incumbent/new-owner comparisons |
| 4 Qualification assessment contract | Qualification plus all contract consumers as one atomic unit | Distinguish partial contributions from full obligation establishment | False coverage or crowding; contract invariant fixtures and payload audits |
| 5 Island-centered controller/frontiers | Controller scope/priority, before final selection; contract dependencies to verify | More coherent exploration with existing limits | Starved handoffs; scheduler/frontier fixtures and live actions |
| 6 Dormant same-file alternatives | Held-owner lifecycle and scheduler; requires current owner/qualification contracts | Inspect overlooked alternatives within budgets | Capacity displacement; lifecycle/replay tests |
| 7 Same-file nomination extraction | Behavior-preserving refactor after relevant policies | Clear stage boundary; no quality/cost change intended | Accidental scheduling changes; saved-input deterministic equivalence |
| 8 Final island-packet representation | Final payload/selection only; requires compatible island/qualification contracts | Expose connected support before selector, reduce late additions | Packet budget crowding; saved final-pool replays |
| 9 Final selection follow-up corrections | Bounded candidate/connection handling after packet comparison; split if independent | Repair measured representation losses | New displacement; fixed-pool selection and capacity tests |
| 10 Original OpenWiki integration | Repository-local connector, file hints, exact page-ID contract, code-index exclusion | Better retrieval directions, added analysis tokens | Misleading file hints; connector fixtures and real three-run comparison |

Infrastructure/ablation-only differences (Node resolution, disabled graphless/legacy modes,
removed unused BM25 profiles, server wiring) are not automatic behavior experiments.
Any prerequisite actually required is recorded explicitly. Do not mix these into a step.

## Step 1 framework

Remove turn_relation, solution_pressure, specificity, target_state from request analysis,
plus prompt/schema identifier renaming, using the scoped `a899dbe` patch. Do not alter
retrieval ranking, qualification, controller, final selection, source connections or indexes.
These fields are coupled across the intent schema/dataclasses/normalizer and consumers;
test as one contract cleanup. Baseline saved outputs and real repeats determine whether
the apparent cleanup perturbs retrieval quality. No deterministic surrogate for the LLM.

## Ledger

| Unit | Variant | Focused checks | Actual runs | Decision |
| --- | --- | --- | --- | --- |
| 1 | 1 | 79 tests pass | First batch 4/4 each; confirmation 3/4, 2/4, 3/4 | Provisional acceptance withdrawn; reverted |
| 2 | 1 | 27 tests pass; saved-output replay unchanged | 215141Z / 215151Z / 215201Z: 3/4 each | Inconclusive; not retained |
| 3–10 | — | — | — | Not started; boundaries/dependencies to verify |

### Unit 1 result

Runs on 2026-09-14: `run-20260914T214357Z` 108013 tokens,
`run-20260914T214407Z` 98819, `run-20260914T214417Z` 112484.
All 4/4, partial/false. Mean 106438.7, total 319316, approximately 4.1% below baseline.
All include WatchMode `verifyTransitiveReferences` L770-L1064 and Helpers as a file trace.
BuilderState snippets are partial: getReferencedByPaths, updateSignaturesFromCache, or
updateExportedFilesMapFromCache, not a complete diagnosis. The repeated improvement is
file-level recall and grounded structural representation, not demonstrated sufficiency.
The schema cleanup remains active; its isolated patch is
`testing/codeRepoQA/incremental-restoration/unit-01-intent-cleanup.patch`.
No stronger causal claim is made from three stochastic runs. No additional retrieval
settings were changed. This becomes the next unit's fixed checkpoint.

## Step 2 framework

Restore only `callable_owners.mjs`, its `source_ast.mjs`/`workspace_graph.mjs` integration,
and callable integrity tests from `df75bfc`. Structural resolution boundary only; no
index rebuild, ranking, qualification, or final-payload changes. Verify malformed JS
callables against actual AST fixtures, identity preservation and nested-owner call scope.
TypeScript is the unchanged main regression case; healthy TS owners should not be replaced.
No new LLM stage. Risk: changed structural owners/calls can alter candidate admission.

### Unit 2 initial result and confirmation gate

Runs `run-20260914T215141Z` / `215151Z` / `215201Z`: 3/4 each,
partial/false; 107547 / 114325 / 104186 tokens (total 326058, mean 108686).
The first and third omit Helpers from final output; the second omits BuilderState.
This is an outcome statement, not an attribution to raw retrieval or the patch.

The fix targets JS/JSX/MJS/CJS; TS callables pass the validator unchanged. Offline actual
structural-output replay using `audit-callable-transform.mjs` over the three unit-1 runs
checked 527/314/530 payloads and 361/323/361 range resolutions. All were unchanged:
1371 payloads, 1045 ranges, zero transformed outputs. This does not prove full pipeline
equivalence, but materially weakens causal attribution of the lower scores to this fix.
The audit script requires the saved unit-2 patch applied to reproduce its imports.

Unit 2 is now removed from runtime; patch/tests are recoverable in
`testing/codeRepoQA/incremental-restoration/unit-02-callable-integrity.patch`.
Only its two modified bridge files and two added runtime/test files were reversed.
Unit 1 and thesis were not touched. A three-run unit-1-only confirmation is required
before accepting/rejecting unit 2 or stacking subsequent changes.
Owner reevaluation (unit 3) depends on qualification unit 4: execution order must reflect
that dependency despite the provisional unit numbering.

### Matched confirmation and current checkpoint

Unit-1-only confirmation: `run-20260914T215946Z` 3/4, 89508 tokens;
`run-20260914T215956Z` 2/4, 103029; `run-20260914T220006Z` 3/4, 98353.
All partial/false. Total 290890. First/third include WatchMode source plus Helpers file
trace but omit Builder from final output; second selects Builder and BuilderState only.
Final path overlap does not establish the point of loss; no causal stage-loss diagnosis
is made without the full boundary audit.

The accepted 4/4 checkpoint was not reproducible under unchanged source. Therefore the
provisional unit-1 acceptance is withdrawn; lower tokens do not justify retaining an
unstable quality claim. Unit 2 cannot be fairly classified as causing a regression given
its unchanged saved TS outputs and the lower confirmation scores after removal.
Both units are removed from runtime with their scoped patches preserved. No speculative
correction was added. Total actual retrieval usage for this sequence so far: 936264 tokens,
nine completed runs, no failure retries. Later units remain untested, not rejected.

Current runtime is back at `0e725b4` (with the separately restored thesis untouched).
The sequence is paused at its repeatability gate, not completed. Before expanding it,
the next useful work is a fixed-input request-analysis/early-admission comparison and
full loss-boundary audit of the confirmation runs; additional cascading changes would
make causal interpretation worse. A fresh source-only baseline is now available, but
no assertion that it guarantees 3/4 or 4/4 is warranted.

### Additional cleanup-only repeat requested by user (2026-09-15 local time)

Reapplied the exact archived unit-1 patch, no callable fix or other behavior changes.
Thesis untouched. 79 focused tests pass. Same model/profile/index, final selection on,
response generation off. All completed runs reused the index and exited zero.

| Run (UTC ID) | Focal overlap | Final focal files | Coverage / sufficient | Retrieval tokens |
| --- | --- | --- | --- | --- |
| `run-20260914T221537Z` | 3/4 | Builder, BuilderState, WatchMode | partial / false | 105038 |
| `run-20260914T221547Z` | 4/4 | Builder, BuilderState, WatchMode, Helpers | partial / false | 108741 |
| `run-20260914T222120Z` | 2/4 | WatchMode, Helpers | partial / false | 86302 |

Helpers matches are file traces, not internal-behavior snippets. These are final-output
results, not raw retrieval absence diagnoses. Completed total 300081, mean 100027.
Initial attempt `run-20260914T221557Z` failed with API read TimeoutError during round-zero
evidence qualification. It has no final score and is excluded from the three-run quality
comparison; its trace and complete console traceback were preserved. Recorded successful
responses before timeout total 21930 tokens; the timed-out response has unknown usage.
Recorded total including failed attempt: 322011, a lower bound if the timeout was billed.
The replacement run used unchanged code/settings, no fallback or timeout adjustment.

Across all nine completed cleanup-only runs: 4,4,4; 3,2,3; 3,4,2 = 29/9 (3.22/4),
four 4/4 outcomes. All remain partial/false. This is variable file recall, not a stable
4/4 guarantee or statistically established improvement over three baseline runs.
User-requested cleanup remains applied provisionally; no automatic acceptance or further
stacking occurred. Unit-2 callable fix was tested earlier but remains absent/inconclusive.
Units 3–10 are still untested in this restoration sequence: qualification contract must
precede dependent owner reevaluation; controller/frontiers, held alternatives, nomination
refactor, final packets/corrections, and original OpenWiki integration remain pending.
