# Qualified structural file-lead experiment

## Hypothesis

A semantically qualified source owner can expose an exact owner-qualified call into a file that initial retrieval did
not admit. That call should create an unqualified structural lead for later inspection without inheriting semantic
support from the caller.

Example shape:

```text
qualified builder.ts owner
  -> exact call BuilderState.updateShapeSignature
  -> target file builderState.ts
  -> preferred target updateShapeSignature
  -> later typed inspection
  -> ordinary source qualification
```

## Proposed first experiment

- Create the lead only from visible, semantically qualified source and an exact owner-qualified call.
- Resolve and retain the target file, exact target node, source candidate, supported obligation, and call-site
  provenance.
- Promote the lead into the controller's eligible and prioritized inspection frontier; do not alter the target file's
  earlier Qdrant/file-admission rank and do not create an evidence candidate yet.
- Let the typed controller action inspect the exact target first, then another owner in the same file only when the
  exact target is unavailable or insufficient.
- Route the action through existing typed validation, novelty suppression, scheduler accounting, and trace logging.
- Qualify disclosed target source normally. No support is inherited from the caller.

This intentionally bypasses the completed initial owner-comparison boundary rather than trying to keep the target file
alive inside it. A pre-comparison file-rank boost would act on unqualified source, increase the comparison payload, and
make high-fan-out utilities substantially more dangerous. The later qualified lead is therefore expected to have
higher precision but one-round latency and possible competition for bounded controller actions. The experiment must
measure whether prioritized scheduling reliably offsets that latency before considering an earlier admission boost.

## Utility and role controls

Candidate suppression should use measurable properties such as distinct calling files, distinct calling owners,
target-node indegree, qualifier-wide fan-out, repository calling proportion, and whether a qualifier exposes many
unrelated members. Tests remain eligible, but their qualified obligation support and later target qualification keep
them within the evidence role they actually establish.

## Status

2026-08-27 follow-up: discovery attempt 2 and explicit-request priority are reapplied and best-effort retained.
Subsequent source-owner compatibility repair is recorded separately in
[`ast-owner-recovery-compatibility.md`](ast-owner-recovery-compatibility.md). It supersedes the source-kind limitation
below, not the historical run results; target uniqueness, semantic eligibility and final-flow limits remain unchanged.
The requested four complete evaluations are finished. Same-queue priority is verified; end-to-end improvement and
protection of future, not-yet-discovered requests are not established. No caps or downstream filtering were changed.
The historical rollback below remains the record for the first integration, not the decision on this follow-up.

### Follow-up: requested inspection before incidental qualified calls

- Boundary: restore the archived verified-lead module/discovery and pre-slot novelty checks; change only priority
  within the existing one-per-round, two-per-run verified-lead pool. Initial retrieval, qualification, final flow
  selection, prompts, models, indexes, and all slot/round caps remain unchanged.
- Hypothesis: an exact visible target explicitly named by qualification or a missing-information assessment should
  precede a callee discovered incidentally in qualified source. Cross-file status alone does not establish urgency.
- Record why each lead is prioritized, the complete eligible ranking, selected target, suppressed targets, and
  cap-blocked pending work. Preserve explicit-request provenance when the same target also occurs incidentally.
- Expected quality effect: preserve targeted follow-up capacity while retaining exploratory calls as pending leads.
  No additional LLM calls or slots are introduced; different inspected source can change qualification/final tokens.
- Risks: explicit follow-ups can be mistaken or generic; exploratory but decisive callees may wait until the cap is
  exhausted. This does not fix the separate final-flow exclusion of connecting helpers (QFL-1).
- Focused checks: explicit follow-up versus structural-child priority, same-target provenance upgrades, novelty
  suppression before selection, unchanged caps and discovery regression tests; replay old pending queues where possible.
- Acceptance: TypeScript twice, Pandas once, Vue once through the npm workspace evaluation surface, final evidence
  selection enabled, explanation generation skipped, existing indexes reused. Record exact run IDs, scheduling and
  source/qualification/final outcomes, coverage/sufficiency, and actual retrieval tokens. Single Pandas/Vue runs are
  cross-case checks, not repeatability claims. Compare with earlier runs without attributing upstream variation to
  this post-qualification change. At most three scheduling variants; revert if repeated quality regression outweighs
  demonstrated intermediate benefit. Lack of final retention alone is not evidence that recovered source was irrelevant.

| Follow-up run | Case | Status | Scheduling / qualification / final result |
|---|---|---|---|
| run-20260827T104715Z | TypeScript attempt 1 | Invalid, excluded from acceptance | Qualification round 2 promoted obs_f81305018e14309d without visible support; existing validator failed explicitly. No verified leads executed. 59,249 recorded retrieval tokens. |
| run-20260827T105127Z | TypeScript completed repetition 1 | Complete | Partial/false; 3 implementation Oracles, 10 items / 6 files, 109,229 tokens; helper promoted, default-library predicate rejected |
| run-20260827T105613Z | TypeScript completed repetition 2 | Complete | Partial/false; 3 implementation Oracles, 10 items / 5 files, 116,904 tokens; helper direct, explicit buildNextInvalidatedProject direct and final rank 6 |
| run-20260827T104726Z | Pandas 10068 | Complete | Partial/false; 0 implementation Oracles, 3 items / 2 files, 53,091 tokens; no eligible leads or verified executions |
| run-20260827T104818Z | Vue 242 | Complete | Partial/false; 1 implementation Oracle, 8 items / 4 files, 64,936 tokens; no eligible leads or verified executions |

Focused scheduling variant 1: 99 discovery/qualification/action-policy tests pass. Two real source/AST/graph replays
(`priority-repeat-1-compatible-node`, `priority-repeat-2`) are byte-identical in their result payload, each 21 tool
requests and zero LLM tokens. Both initial calls are correctly labelled incidental; no new semantic support is inferred.
The initial replay `priority-repeat-1` failed before discovery because the default shell Node lacks `node:sqlite`.
Replays and actual evaluations use the existing CodeGraph package's bundled Node v24.16.0 via process-local PATH;
no dependency, index policy, or repository source change was needed. The Vue cross-case is the expression-parser
case 242 used in the earlier assignment-owner/recovery experiments, not the separate SSR case 10803.

#### Scheduling and source-level observations

- The old run `070351Z` pending queue at trace line 492 is replayed with recorded source ranks and target identities.
  Previously `resolutionCache.resolveModuleNames` won; now the explicit request for
  `getSemanticDiagnosticsOfNextAffectedFile` wins. Two replays are identical. This proves the ordering boundary,
  not a counterfactual final answer. Queues missing recorded source ranks are marked skipped rather than assigning
  invented tie-breakers. Artifact: `testing/codeRepoQA/qualified-file-lead-replays/priority-saved-queues.json`.
- Live TypeScript `105127Z`: round 1 queue (504) contains only incidental calls. `BuilderState.getReferencedByPaths`
  wins and qualifies direct at 538 (state changes), then 973 (subject). This five-line reverse-reference lookup is
  useful with the dependency traversal that calls it; no semantic proof was inherited at discovery.
- Round 2 queue (953) contains only incidental `program.isSourceFileDefaultLibrary`. It executes, then qualification
  correctly rejects it at 973. Its caller is `handleDtsMayChangeOfAffectedFile`, builder.ts:428, but the call guards
  default-library cleanup in the all-files-affected branch, not the reported wildcard/project-reference mechanism.
  This is a real connection but low-value issue evidence.
- By round 3 (1406), explicit requests for `createSolutionBuilderWorker` and `tscWatchCompile` have appeared, but both
  executions are already spent. Stop event 1834 also retains `updateRootFileNames`. Priority cannot protect requests
  that do not exist yet. No scheduling order changed on these live queues; the remaining problem is when exploratory
  calls may spend scarce capacity, not sorting simultaneously available requests.
- The helper reaches the final candidate inventory (1837), but all six containing flows are excluded by
  `rejected_no_new_causal_responsibility`; it does not reach the final LLM. This is unchanged downstream behavior,
  not evidence that the recovered helper is irrelevant. No flow-admission fix is included in this experiment.
- Replacement TypeScript `105613Z`: the only round-1 lead is the same reverse-reference helper (queue 395), promoted
  at 423 for ordered mechanism and state changes. Rounds 2/3 have empty verified queues. After round 3, explicit
  follow-ups appear; the unchanged pending-lead rule permits round 4. `buildNextInvalidatedProject` wins that queue
  (1482), qualifies direct at 1514, and reaches final rank 6. Its body (tsbuildPublic.ts:1749-1770) gets the next
  invalidated project in build order, completes it, schedules pending watch builds, and reports errors: useful
  orchestration evidence, not proof of the wildcard defect by itself. This is an existing follow-up type, not a
  newly introduced discovery mechanism. All live queue winners are identical under the old and new ordering on
  those same inputs; do not attribute this successful inspection specifically to the priority change.
- In that replacement, all three final flows containing the reverse-reference helper are filtered before final LLM
  input (1892). A late `resolutionCache.removeResolutionsOfFile` lead is recorded after round 4, never executed or
  qualified. It is pending discovery, not recovered evidence. Pending at stop (1889): that lead, createWatchHost,
  tscWatchCompile, and getSemanticDiagnosticsOfNextAffectedFile. BuilderState and tsbuildPublic were already known
  files: the successful recoveries add missing owners, not newly admitted files.
- Pandas `104726Z`: five new discovery-tool requests, zero leads/actions. `_binop` appears in raw retrieval (27/32/
  37/42/47/52), resolves to a canonical owner (60/61), but series.py is nonadmitted (62/69) before owner comparison.
  Only four files pass the preferred-size prefix; comparison includes `_flex_method_SERIES`/`flex_wrapper` in ops.py
  but selects arithmetic wrappers/registration instead (65/66). `_binop` remains deferred, never qualifies, and is
  absent from final evidence. New recovery has no eligible source-grounded target and does not rescue this upstream
  loss. It neither caused the initial exclusion nor demonstrated robustness against it.
- Vue `104818Z`: ten discovery-tool requests, zero leads/actions. Seven source occurrences fail the resolved-callable
  requirement; nine target attempts fail unique resolution (including `compiler.eval`, `Directive.inlineFilters`,
  and regex `test` calls). No speculative edge or candidate is invented. Final evidence retains makeGetter, the
  implementation Oracle. This cross-case checks conservative failure behavior, not scheduling effectiveness.
  The rejected source kinds include real assignment-defined functions (`CompilerProto.compileElement`,
  `CompilerProto.bindDirective`, `Directive.parse`, `CompilerProto.checkPriorityDir`) represented as `source_owner`.
  The restored discovery gate accepts only function/method/constructor, so those AST-resolved owners cannot seed
  this recovery feature. This is an existing compatibility limitation, not proof that those sources lack callable
  bodies. Extending that gate/adapter contract is a separate experiment, not changed during these runs.

All measured runs use gpt-5.6-luna and keep dormant completion disabled. Successful index checks report rebuilt=false.
The large TypeScript content/index check in the first attempt took several minutes but reused the 83,401 chunks.
The graph's ordinary sync reports two source paths checked as added with zero node updates; this is not a full rebuild.

#### Costs and follow-up decision

| Complete run | Context | Initial comparison | Qualification | Coverage | Final selection | Total |
|---|---:|---:|---:|---:|---:|---:|
| 105127Z, TypeScript | 1,855 | 22,008 | 32,039 | 36,709 | 16,618 | 109,229 |
| 105613Z, TypeScript | 1,867 | 22,170 | 38,316 | 38,158 | 16,393 | 116,904 |
| 104726Z, Pandas | 1,453 | 7,819 | 23,339 | 13,333 | 7,147 | 53,091 |
| 104818Z, Vue | 1,301 | 23,444 | 15,133 | 13,728 | 11,330 | 64,936 |

These are recorded retrieval LLM tokens; no explanation was generated. Four complete runs total 344,160 tokens;
including the invalid TypeScript attempt totals 403,409. New discovery issues 51/42 structural requests in the two
completed TypeScript runs (including memoized requests), and 5/10 in Pandas/Vue. No extra LLM selector is added.
The previous reapplied-discovery experiment used 105,287/104,307 tokens and three rounds each; this pair uses three
and four rounds. Compared with the unmodified baselines (102,546/146,101; 3/4 implementation Oracles), both current
TypeScript runs retain 3 Oracles. Whole-run differences include upstream variation and different continuation/final
selection work; they are not a controlled estimate of scheduling cost or a demonstrated end-to-end quality gain.

Decision: retain the restored discovery and corrected ordering as an explicitly experimental, best-effort integration.
The ordering fixes the original same-queue priority defect in repeatable saved-input tests; useful dependency-owner
recovery repeats in both complete main-case runs. No two-run regression attributable to the scheduling change is
demonstrated. This is not acceptance of the broader scheduling strategy: an incidental default-library predicate
still consumes a slot, explicit requests may arrive too late, and the helper's final-flow loss persists. The Pandas
failure originates before this stage; Vue does not exercise its scheduling at all. Do not claim those runs validate
cross-language recovery. Investigate exploratory-slot timing, source_owner compatibility, and final connecting-owner
preservation separately; none was changed in this follow-up.

Complete machine-readable outcomes with per-event trace lines:
`testing/codeRepoQA/qualified-file-lead-replays/priority-acceptance.json`.
The old large patch remains a historical archive; the active change is a normal contextual working-tree diff plus
the cohesive verified_leads module, focused tests, and replay/analyzer scripts. No new whole-file backup patch was made.

Historical first integration: tested and reverted, 2026-08-27. Baseline restored: conceptual-query stabilization retained; owner shortlist reverted;
dormant completion disabled. Main-case baselines are `run-20260827T023945Z` and `run-20260827T024536Z`
(3/4 implementation Oracles, partial/false, 102,546/146,101 tokens).

## Execution boundaries

1. Extract the existing verified-lead implementation into one cohesive module without changing behavior; focused
   baseline tests must remain green. Existing navigation/maturation leads retain their rules.
2. Add qualified structural-lead discovery after round-zero qualification/coverage and after later qualification.
   Only promoted direct evidence with explicit supported unresolved obligations qualifies. The language-routed AST
   must report a qualified call whose actual source line is visible in the fitted qualification card. Resolve a
   unique cross-file callable using the existing qualifier/file-owner matching rule. A target already qualified,
   pending, or executed is excluded; an unqualified canonical/deferred target remains inspectable. No candidate or
   semantic support is created at discovery time. Record exact call-site provenance and the target's prior state.
3. Reuse the existing one-per-round, two-per-run verified-lead slot and typed executor. Apply novelty filtering to
   this reserved pool before selection, just as for ordinary actions. Do not alter initial retrieval, file ranking,
   owner comparison, qualification prompts, round limits, or final selection. Insufficient target source uses the
   existing qualification-follow-up machinery; no new automatic file-search fallback is added.

First-attempt utility control uses the graph's measured incoming `calls` edge count: more than 12 rejects a target.
Missing graph capability data rejects the lead rather than inventing a count. Zero known incoming edges is logged as
zero known static edges, not proof of repository-wide rarity. Global distinct-caller-file proportion and qualifier-wide
fan-out are not available from this operation and are not claimed by this attempt. Resolve at most eight distinct
qualified targets per discovery batch; log budget omissions. Retain at most one new target per qualified source.

Expected effect: earlier exact cross-file inspection, without adding comparison candidates or LLM calls. There may
be additional qualification tokens from using an otherwise empty verified-lead slot; existing run/round caps remain.
Risks: static qualifier ambiguity, incomplete call graphs, utilities consuming reserved slots, and competition with
existing navigation/maturation leads. This maps to VL-1/VL-2/VL-3 and ISL-1 in the open-questions registry.

Focused verification covers visible versus omitted calls, semantic support versus retrieval provenance, ambiguous
resolution, utility rejection, existing deferred targets, no support inheritance, duplicate suppression, and existing
slot limits. Replay real qualified TypeScript source against actual AST/CodeGraph twice before acceptance runs.
Then run two actual TypeScript pipelines with final evidence selection enabled and explanation skipped, reusing the
existing index. Audit discovery, suppression, execution, target qualification, final retention, and stage/total tokens.
At most three variants per step; revert behavior that is unexercised or fails to improve the intended boundary without
justified quality/cost tradeoffs. Preserve failed evidence and do not tune against Oracle names.

| Step | Attempt | Focused evidence | Actual evidence | Decision |
|---|---:|---|---|---|
| Verified-lead module extraction | 1 | 95 existing tests passed unchanged | Not behavioral | Reverted with experiment |
| Qualified visible-call discovery | 1/2 | Attempt 1 admitted utility; attempt 2 repeats identically, 104 focused/regression tests pass | Useful exact helper recovered and qualified twice, then dropped by flow admission twice | Reverted |
| Existing reserved-slot integration | 1 | Duplicate suppressed before one-slot selection; next novel lead selected; cap 2 unchanged | Both runs spent both slots and left qualification-requested leads pending | Reverted |

### Discovery attempt 1: focused failure

Two real AST/graph replays of the unchanged fitted round-zero cards from `run-20260827T023945Z`
both produced `program.getSyntacticDiagnostics`, `BuilderState.getReferencedByPaths`, and
`Debug.assertDefined` (23 structural requests, zero LLM tokens). The intended builderState lead
worked, but the utility filter failed: the graph reported only six incoming calls for assertDefined,
while its literal qualified call occurs 23 times across 22 lines in builder.ts alone. No full run used this attempt.
Artifacts: `testing/codeRepoQA/qualified-file-lead-replays/baseline-023945-repeat-{1,2}/retrieval-trace.jsonl`.

### Discovery attempt 2

Add a source-local utility guard: reject a target when its exact qualified call syntax occurs more
than 12 times in the caller file, retaining the unchanged graph-indegree guard. This uses no utility
name list or Oracle information. The trace calls this `source_file_literal_calls`, not resolved caller
count; comments/strings can inflate this conservative signal. It does not establish graph relationships
or semantic relevance. This narrower rule tests the demonstrated sparse-static-graph failure without
adding repository-wide scanning. Exact-symbol responses that reach the 20-node result limit are also
rejected because uniqueness cannot be proven from a truncated list.

Attempt 2 repeats have identical lead/audit payloads: 21 structural requests and zero LLM tokens;
`program.getSyntacticDiagnostics` and `BuilderState.getReferencedByPaths` survive, while
`Debug.assertDefined` is rejected with 23 literal calls. Artifacts:
`testing/codeRepoQA/qualified-file-lead-replays/attempt-2-repeat-{1,2}/retrieval-trace.jsonl`.
These deterministic replays are boundary checks, not final-evidence acceptance runs.

## Actual-pipeline run ledger

All runs use `configs/testing/workspace.json`, existing TypeScript snapshot/index, and
`--skip-response-generation`; final evidence selection remains enabled. The standard harness performs
index synchronization checks; the first trace confirms `workspace_index_ready.rebuilt=false` (83,401 documents).
No forced rebuild or index-policy change is requested.

| Run | Configuration | State | Result |
|---|---|---|---|
| `run-20260827T065406Z` | Discovery attempt 2 + reserved-slot validation | Failed upstream | Owner comparison selected `o93` outside group `g5`; 24,358 retrieval tokens; controller experiment never ran. Excluded from acceptance. |
| `run-20260827T065917Z` | Identical retry | Complete | Partial/false; 3 implementation Oracles; 9 items / 5 files; 105,287 retrieval tokens. |
| `run-20260827T070351Z` | Identical second repetition | Complete | Partial/false; 3 implementation Oracles; 11 items / 5 files; 104,307 retrieval tokens. |

### First completed run: exact effects

- New discovery at trace line 495 created `BuilderState.getReferencedByPaths` and
  `program.getSyntacticDiagnostics`. The latter executed first and qualification rejected it at line 537:
  syntactic diagnostics do not establish the missing semantic error.
- The builderState target executed in round 2, became direct evidence at line 959, and was requalified after a
  within-file search at line 1378. Its last semantic support was only `explain_subject`, not inherited caller support.
- It remained in the final candidate pool (1760), but all three flows containing it were rejected as
  `rejected_no_new_causal_responsibility` (1762). Its causal role was `supporting`; it never entered the final LLM input.
  This is a later flow-admission loss, not failed retrieval or final-LLM rejection.
- The unchanged two-execution cap was exhausted. Existing qualification-follow-up leads
  `getSemanticDiagnosticsOfNextAffectedFile` and `createSolutionBuilderWorker`, plus new
  `resolutionCache.removeResolutionsOfFile`, remained pending with `execution_cap_reached` (1759).
  This shows bounded-slot competition; it does not prove what a counterfactual final answer would have selected.
- The builder-state call was already textually present in initial Qdrant results (18/28/33), and existing island
  construction had resolved the exact target at 131 without creating an evidence snippet. New discovery changes
  its inspection eligibility, not whether the system ever saw its name. The audit field
  `target_previously_canonical=false` means absent from this controller's input snippet pool; it does not prove
  absence from every earlier raw result or dormant record.
- Stage tokens: connected context 1,764; initial comparison 21,268; qualification 31,009;
  coverage 34,530; final consolidation 16,716. Initial-comparison differences are upstream variation, not caused
  by this post-qualification change. Baseline 1 total 102,546 versus variant 105,287 is +2,741 (+2.7%), not a
  controlled estimate of the added calls' standalone token cost.

### Second completed run: exact effects

- Discovery at line 441 produced `BuilderState.getReferencedByPaths` and `resolutionCache.resolveModuleNames`.
  The builderState helper executed in round 1 (450), was promoted as direct state evidence (480), and retained that
  qualification on redisclosure (866). It remained in the final candidate pool (1660), but all four flows containing
  it were rejected as `rejected_no_new_causal_responsibility` (1662), again before the final LLM request.
- The resolution-cache wrapper executed in round 2 (845), was navigation-only (866), and triggered ordinary owner
  maturation into `resolveNamesWithLocalCache` in round 3 (1267). That descendant became direct evidence and did
  enter the final LLM payload (1662/1665). The final response (1666) did not select it; it provides no individual
  rejection rationale for that owner. Its file trace was also excluded because its source island was not selected
  (1668). This is genuine downstream discovery, but not demonstrated final-evidence improvement.
- The two new leads exhausted the same cap. Pending old follow-ups included `getSemanticDiagnosticsOfNextAffectedFile`,
  `createSolutionBuilderWorker`, `createWatchHost`, and `tscWatchCompile` (1659). In round 2, a new structural lead
  outranked an already-pending qualification-requested lead because the existing selector prefers structural children.
- Stage tokens: connected context 1,762; initial comparison 21,125; qualification 32,865; coverage 31,913;
  final consolidation 16,642. Both completed runs used three controller rounds and four qualification/coverage calls.
- Discovery issued 56/45 structural requests across the completed runs, including memoized requests; total controller
  requests were 540/506. The extra LLM tokens cannot be isolated from shared batches and downstream changes by
  subtracting whole-run totals. Neither run rebuilt its indexes or generated an explanation.

## Historical first-integration decision and reproducibility

Revert the whole runtime experiment, including the mechanical extraction and reserved-pool change. The experiment
proved repeatable exact-target discovery and qualification, but its main recovered helper was removed at the next
selection boundary in both runs. Broader visible-call eligibility also used scarce reserved capacity ahead of explicit
qualification follow-ups. There is no repeatable final-result benefit justifying this integration as-is. This is not
proof that structural leads are useless, nor proof that every final-file difference was caused by this patch.

The two completed runs consumed 209,594 retrieval tokens. The upstream-invalid attempt consumed 24,358 more;
total measured retrieval spend was 233,952. The unchanged baselines were 102,546/146,101 tokens and 3/4 Oracles;
the second baseline used a fourth round, a final-selector retry, and file-trace selection, so lower totals against it
must not be attributed to this experiment.

The exact experimental implementation, focused tests, and real-boundary replay are archived in
[`artifacts/qualified-structural-file-lead-attempt-2.patch`](artifacts/qualified-structural-file-lead-attempt-2.patch).
`git apply --check` passes against the restored runtime. Original 95 focused/regression tests pass after rollback.
The read-only `testing/codeRepoQA/analyze_qualified_file_leads.py` and generated measurements remain available;
they contain no active retrieval behavior. Existing unrelated working-tree changes were preserved.

Future separate experiments, not implemented here:

1. Prioritize call-level relevance to missing information rather than granting all visible callees of a qualified
   owner structural-child priority. Protect explicit semantic follow-ups without simply raising the cap.
2. Audit whether the final flow reducer's `supporting` role wrongly removes a qualified read-only dependency lookup
   needed to connect a mechanism. Distinguish a genuinely redundant helper from a necessary causal connection.
3. If revisited, replace source-local textual utility repetition with better available caller metrics. Literal counts
   are conservative and can include comments/strings; they are not repository-wide resolved fan-in.
