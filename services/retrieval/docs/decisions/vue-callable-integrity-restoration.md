# Vue callable integrity restoration

## Current-code assessment before inspecting the historical implementation

Checkpoint: 3a4a705. Current resolve_ranges trusts nodesOverlappingRange. Python
observation_from_result clips retrieved text to those reported boundaries. Actual bridge
probe on Vue 10519 snapshot b97606cdc658: props.js L20-65 returns function `if` L33-35;
L145-175 returns assertType L151-154. Original validateProp is L21-62, and assertType's
body extends beyond its return-type declaration. These are representation bugs, not
evidence that the relevant source was absent from raw retrieval.

Independent proposal: validate callable identity/boundaries against source AST before
clipping; recover a validated overlapping owner when possible; otherwise reject invalid
ownership and preserve raw source range. Never invent graph edges for AST-only identities.

## Historical comparison and scope

a899dbe contains callable_owners.mjs and integration into source_ast/workspace_graph.
The archived unit-02 patch matches this design, including validation at all bridge exits,
explicit rejection reasons and source-only call inspection. TypeScript parser reports no
parse diagnostics for the actual Flow-annotated props.js. Restore the historical patch,
then verify real-source boundaries and compare all changed outputs, not only synthetic
fixtures. Additional corrections require concrete failure evidence, maximum three variants.

Keep request analysis, qualification, controller, final selection, source connections,
model and evidence budgets fixed at checkpoint. No thesis changes. The callable bridge
is the only runtime boundary allowed to change. No added LLM stage; larger correct
snippets and new structural leads may increase later token usage or displace candidates.
Expected benefit: stop presenting conditional blocks/type declarations as complete owners.

## Measurement

Three fresh Vue baselines before restoration, three fresh Vue variants afterward, and
three TypeScript regression runs compared with checkpoint runs 232154Z/232229Z/232239Z
(4/4,4/4,3/4; 105549/101153/94317 tokens). Actual npm workspace pipeline, final selection
enabled, explanation disabled, Node22, gpt-5.6-luna. Frozen-stage replays isolate any
regression at raw retrieval, grouping, resolution, comparison, qualification, actions or
final selection. Do not explain worse scores as randomness without matched-input evidence.

Docker engine unavailable. Restarted existing WSL Qdrant 1.18.3. TypeScript collection
present; Vue collection absent and requires population from cached vectors on first
baseline. Verify full count before concurrent runs. Inspect effective exclusions and keep
them unchanged across baseline/variant; no authored sources removed using oracle data.

Acceptance: correct the concrete malformed owner bugs and show preserved useful source
through actual pipeline; audit every lower result before deciding. Do not restore known
false owner identities just to improve a score. Separate a verified structural fix from
unproven overall quality gains. Any dependent heuristic is a separate experiment.

## Variant 1 and discovered historical defect

Historical patch restored without reimplementation. Six original integrity tests and
ten router/graph tests pass. Real source probes recover validateProp L21-62 (1261 visible
characters) and assertType L151-175 (618), versus 120/97 characters at baseline. The broad
145-175 probe also overlaps assertProp's final closing lines; it is not a pure owner probe.
Saved TypeScript checkpoint replays: 1345 structural outputs, 1136 ranges, zero changes.

However, real Vue replays reject genuine processAttrs/looseIndexOf owners because the
TypeScript parser cannot parse unrelated Flow syntax elsewhere in the same file. Babel's
Flow parser verifies these functions. New focused test with `%checks` preceding an
ordinary valid function fails against variant 1: the valid owner is discarded solely
because whole-file TypeScript parsing fails. This is a concrete historical defect, not
a stochastic explanation for any benchmark result.

Variant 2 replaces the JavaScript validator's parser with Babel's Flow-capable parser,
keeping exact identity/range validation and raw-range preservation on actual syntax errors.
Recovered-owner call inspection must use that same validated AST, retain nested-call
isolation, and keep source identity separate from graph edges. Existing healthy graph
call extraction and the TypeScript path remain unchanged. Add @babel/parser as a direct
runtime dependency (already installed transitively, version 7.29.7). No parser fallback
chain and no ranking/qualification/scheduling changes. Complete variant-1 runs before
changing runtime code, then three corrected Vue runs and three TypeScript controls.

Fresh Vue baselines: 234506Z 2/2,76238 tokens; 234634Z 1/2,65535; 234645Z 1/2,45482.
All partial/false. Total 187255.

## Results so far

| Condition | Run | Oracle files | Retrieval tokens |
|---|---|---|---:|
| Historical patch | 20260914T235154Z | 1/2 | 50533 |
| Historical patch | 20260914T235204Z | 1/2 | 56006 |
| Historical patch | 20260914T235214Z | 1/2 | 56259 |
| Flow-capable correction | 20260914T235805Z | 1/2 | 51684 |
| Flow-capable correction | 20260914T235815Z | 1/2 | 59197 |
| Flow-capable correction | 20260915T003449Z | 1/2 | 48013 |
| TypeScript regression | 20260915T000114Z | 4/4 | 95024 |
| TypeScript regression | 20260915T000333Z | 4/4 | 100609 |
| TypeScript regression | 20260915T000343Z | 4/4 | 111020 |

All completed runs are partial/false. TypeScript total 306653, mean 102218 rounded,
versus checkpoint total 301019: +1.87%. No causal TypeScript gain claimed: JS validation
is dormant for TS, with unchanged structural replay outputs. Historical Vue total 162798.

Excluded corrected attempt 20260914T235840Z failed in qualification with invalid model
obligation ID `explain_ordered` for obs_8a5c3ff870502037. Recorded response usage 32836;
no final score. Retried unchanged code/config as 003449Z, no fallback or validator weakening.

17 focused integrity/router/graph tests pass; all 84 qualification/controller tests pass.
Full suite: 489/493 pass. Same three missing lexical_ranking_profile fixture errors and
one analyze_qualified_file_leads manifest failure as the checkpoint, no new suite failures.

## Exact selection-loss audit and matched counterfactual

In baseline 234506Z, raw props.spec.js evidence is admitted as group g5; owner o63
(obs_bc4b6169b205f9ea) is selected. Final test range L220-246 includes the Symbol test;
qualification explicitly says it does NOT test a Symbol supplied against another type
or the failing conversion. It is useful neighboring test context, not complete proof.

In historical 235154Z/235204Z/235214Z, props.spec.js is retrieved and admitted, but initial
owner comparison selects only core props.js and leaves all test owners dormant. The test
therefore never reaches qualification or the final pool. Corrected 235805Z and 235815Z
also preserve the original implementation; test selection remains a separate boundary.
The repaired final evidence contains genuine validateProp/assertProp/assertType owners,
alongside getInvalidTypeMessage, rather than conditional fragments. This improves source
representation but does not establish the Symbol coercion inside styleValue; partial/false
is still appropriate.

Four actual LLM selector replays freeze the entire successful baseline request. Two exact
original-input repeats select (1) factory.js + core props.js, (2) factory.js only. Two
counterfactual repeats change only two bogus owner labels and their three source views:
assertProp from already-retrieved portions L100-121/L122-147 and validateProp L21-60.
Ranks, group IDs, owner IDs, obligations, test views, system prompt and schema are unchanged.
Both repaired repeats select core props.js only, with assertProp, validateProp and
getInvalidTypeMessage. API-recorded request hashes match the intended requests in all four.

Original request SHA256: 8614b597ee632e70af48c0b1df5d9e1d5c18ef88480c9d74001232ceb1151d93.
Repaired request SHA256: 7f4924fb76f581a0c14787e4fc5a02ac13d098ec93937e12b14a47ea60b15b16.
Replay tokens: 21089,21021 / 21577,21130; total 84817. Artifacts and source-view probe
outputs are under testing/codeRepoQA/incremental-restoration/vue-*. Replays are diagnostics,
NOT full-pipeline oracle scores. They isolate the source-vs-bundle selection benefit but do
not prove the patch caused test omission: the unchanged original request also omits it twice.
This is observed matched-input selection evidence, not an unexplained randomness claim.

Remaining issue: the initial selector leaves useful neighboring tests dormant even when
they fit. Do not add oracle-specific reservation, change ranking, or broaden controller
budgets inside a callable correctness repair. Replacement 003449Z repeats the same
initial test omission, completing the corrected three-run set. Its final evidence includes
getInvalidTypeMessage and a structural trace to compiled build.dev.js; improved initial
source selection does not mean all later compiled participants have disappeared.

## Final decision and cost

Retain variant 2 as a verified structural correctness repair, not an accepted increase
in Vue file recall or sufficiency. Historical variant 1 is superseded (archived unit-02
patch remains unchanged). Two source-view counterfactuals show repeatable original-source
selection instead of compiled copies. The two concrete malformed owners are corrected,
the unrelated Flow false rejection is fixed, and TypeScript shows no observed regression.
Do not restore known-invalid function boundaries to recover an occasional test-file score.
The original successful baseline selector input itself omits that test on both exact
repeats, so the test loss cannot be assigned solely to this patch. A separate selection
experiment is needed for test-context retention; no such heuristic is added here.

Corrected Vue total 158894, mean 52965 rounded, about 15.15% below baseline; this is an
observed workload change, not a causal cost guarantee. Total completed actual-pipeline
retrieval tokens across all twelve new runs: 815600. Add four selector diagnostics 84817
and failed qualification attempt 32836: total recorded 933253. Request-analysis,
embedding and any other unreported provider costs are outside this retrieval-token total.
No generated response prose. No new OpenWiki generation.

Runtime changes are limited to callable_owners.mjs, its two bridge integrations, and
the direct @babel/parser dependency/lockfile. Tests, probes and diagnostics are preserved.
Checkpoint 3a4a705 remains available. This experiment is being checkpointed separately;
the unresolved-snippet presentation change below is not implemented. Thesis untouched.

## Subsequent diagnosis: unresolved test views lose their distinguishing behavior

All three corrected runs (235805Z, 235815Z, 003449Z) retain observation
obs_4a3f6c615e3e5389 for props.spec.js L220-246 through canonicalization and admission.
It has no node_id; owner source preparation records unresolved_owner_unchanged.
The final serialization therefore uses _compact_source_view (80-character target),
which selects early dotted calls and generic semantic terms. Its actual output is:

    expect(console.error.calls.count()).toBe(0)
    makeInstance([], Array)

The retrieved range's makeInstance(Symbol('foo'), Symbol), makeInstance({}, Symbol),
and Expected Symbol warning assertion disappear. No serialized test view contains
"symbol" in any of these three runs, and each test group receives null. The selector
schema does not record rejection reasons. This proves a visibility failure before
selection, not the model's private reason or guaranteed selection after repair.

The old-input replays establish only that the callable fix is not necessary for test
omission; they do not prove it cannot affect selection. A subsequent focused experiment
should preserve bounded actual source for unresolved ranges, apply the existing total
admission budget to the rendered payload, and compare identical saved inputs. Do not
introduce a test-file boost, a forced selection, or extra qualification credit.
