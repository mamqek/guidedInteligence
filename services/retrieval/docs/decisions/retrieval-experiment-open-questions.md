# Retrieval Experiment Open Questions

## IOG-1 — Historical initial guardrail does not recover cohort all-zero cases

- Actual-pipeline diagnostics `run-20260830T131540Z` (pandas 22698) and
  `run-20260830T131852Z` (Vue 10004) switched only initial selection to the historical
  24-observation guardrail. Both remained `partial/false` with zero of two Oracle
  files. They are outside the 80-run cohort statistics.
- The Oracle implementation file was present in raw retrieval for both cases. The
  legacy guardrail excluded pandas `core/indexes/base.py` and both Vue Oracle files
  before qualification. Current semantic admission was broader: it admitted pandas
  `base.py` in three of four cohort runs and both Vue files in all four.
- Remaining boundary: select/localize the responsibility-bearing owner after file
  admission. Current Vue sometimes selected `events.js::normalizeEvents`, which was
  correctly deferred because it did not show the requested ordinary input-listener
  teardown; it did not select `updateDOMListeners`. Current pandas admitted the file
  but selected no Oracle-file owner for round zero.
- Status: legacy mode remains a diagnostic switch, rejected as a quality remedy. A
  follow-up must compare responsibility-bearing owner localization on fixed admitted
  files; do not enlarge the historical top-24 cap or promote an Oracle path by name.

## SSA-1 — Shared snippet admission, initial boundary retained; final boundary pending

- [Shared selection experiment](snippet-first-admission-experiment.md): implements the IOC-1/FPK-1
  snippet-first proposal at initial admission only. Global canonical-snippet priority and exact incremental
  serialization replace whole-file admission. Qualified-candidate adapter exists but is not active in final
  selection. Controller, scoring signals, source cards, limits and final flow admission are unchanged.
- Controlled saved-input replays and both live-input counterfactuals demonstrate broader file access with less
  whole-group waste. Both full TypeScript runs retain Builder, BuilderState and WatchMode, still partial/false.
  Retained on the experiment branch; detailed run IDs, costs and comparisons are in the decision note/changelog.
- Remaining ordering issue: recurrence can outrank excellent single-query owners. A missing intermediate callable
  leaves a later direct helper without represented connections; the final responsibility filter then excludes it.
  Some other direct evidence still falls after final flow budgeting. Do not attribute those boundaries to file
  admission or silently change the scoring weights while integrating common selection machinery.
- Helpers has no qualified snippet or WatchMode file trace in either new run. In the second, four exact retrieved
  Helpers owners remain deferred; raw WatchMode calls provide leads in both runs. This differs from QRC-1's
  earlier exact-source file-trace rejection. Discovery/trace creation must be audited before applying that diagnosis.
- 2026-08-29 capability-retention follow-up: the two three-Oracle baseline traces show that an unexecuted WatchMode
  file action was present in round 1 but later disappeared when owner node IDs filled the combined 16-node edge-
  capability slice. [The bounded retention experiment](file-handoff-capability-retention-experiment.md) queried
  omitted file nodes separately and passed focused lifecycle coverage twice, but actual runs `015817Z` / `020528Z`
  never activated the intended WatchMode target and retained three/two Oracle files. After reverting, actual runs
  `034209Z` / `034747Z` both restored three Oracles. The experiment is reverted. The exact `020528Z` BuilderState
  loss occurred through pre-existing verified-lead competition before the first overflow request, so it does not
  prove a deterministic overflow displacement; it does prove that this unexercised additive change lacked sufficient
  live evidence to retain. Helpers recovery remains open.
- 2026-08-29 scheduling-retention follow-up: [the pending handoff experiment](pending-file-handoff-scheduling-experiment.md)
  proved in diagnostic `042117Z` that preserving the exact starved WatchMode action recovers the historical
  WatchMode-to-Helpers traversal and its 18 calls. Three bounded variants were nevertheless reverted. Broad
  retention forced a zero-edge `sys.ts` action; safer variants rarely activated, and all four acceptance runs
  retained only two Oracle overlaps. Runs `043211Z` and `044424Z` created Helpers normally but rejected its trace at
  `source_island_not_selected` because the exact WatchMode source was not accepted by final consolidation. The first
  decisive boundary is therefore run-dependent: scheduling when the action disappears, but final source acceptance
  when the trace already exists. A next experiment should isolate the latter on saved final-selection input rather
  than add more controller capacity or another scheduling heuristic.
- 2026-08-29 mixed-island resolution: [the representation experiment](mixed-island-file-trace-representation-experiment.md)
  restored the bounded test-source pending scheduler and fixed each measured downstream loss boundary without
  increasing controller slots, rounds, graph calls, or the final evidence cap. Exact file-trace source preservation
  was retained; the broader artifact-role reservation was rejected because it could preserve the wrong test file.
  Final actual runs `150112Z` and `150534Z` both retained Builder, BuilderState, WatchMode, and Helpers, using
  106,410/103,059 retrieval tokens. Helpers remained an LLM-selected structural participant with no claim about its
  internal behavior. This closes the specific Helpers scheduling/representation question; overall semantic coverage
  remains `partial/false` and is not closed by structural file evidence.
- Final snippet-first admission remains a separate experiment, with stage-specific semantic eligibility and
  connections. A common interface does not make initial retrieval associations equivalent to qualified support.

## NCA-1 / WRF-1 — Non-code artifacts and wide mechanical refactors deferred

- Keep the accepted mixed-island scheduling and exact trace-source implementation unchanged. The focused TypeScript
  pair repeated all four target files, and the ordinary Vue/Pandas mechanism regressions did not lose their existing
  implementation Oracles. Do not broaden artifact preservation or alter owner scheduling merely to improve the two
  cases below.
- Non-code artifact limitation (`vuejs-vue-13052`, `run-20260829T162949Z`): Qdrant retrieved
  `packages/compiler-sfc/package.json` at dense file rank 5 / grouped rank 9 and `pnpm-lock.yaml` at dense rank 7 /
  grouped rank 11 for the strongest matching obligations. CodeGraph correctly returned zero owners. Both were then
  excluded at initial comparison admission at global positions 160 and 173+ after the 60,237-character crossing;
  neither reached owner comparison, qualification, or final selection. The issue literally identifies
  `compileTemplate.ts`, `compileTemplate`, and `format`, but says only "compiler/sfc package" and "optional
  dependencies" rather than naming either manifest path. Exact-anchor recognition therefore did not fail. A future
  solution, if this case class is prioritized, needs a separately measured dependency-artifact inference and
  file-level configuration evidence boundary; it must not pretend manifests have CodeGraph owners.
- Wide-refactor limitation (`pandas-dev-pandas-35925`, `run-20260829T162616Z`): the hidden Oracle is a 25-file Black
  formatting cleanup spanning configuration, docs, tests, and implementation. Causal mechanism selection retained
  only `pandas/core/aggregation.py` (1/25); earlier nonempty runs varied from three to five overlaps while the four
  immediately preceding runs returned no evidence. Changed-file overlap is a poor proxy for explanation quality on
  a mechanical repository-wide patch. A future treatment would first need an explicit task/artifact contract for
  refactors (for example representative files versus exhaustive change scope) before changing retrieval.
- Status: documented and deferred, not an active implementation plan. No heuristic, extra slot, manifest bypass,
  broad artifact-role reservation, or evaluator-specific exception is authorized by these observations. Reopen only
  with a separate experiment framework, focused fixtures, and cross-repository acceptance that leaves the current
  focused behavior intact.

## QRC-1 — Bounded qualification rationale across evidence stages

- [Rationale carryforward experiment](qualification-rationale-carryforward-experiment.md): requested after SBR-1
  rollback. Existing qualification reason capped at 400 characters and carried through reassessment, candidates,
  coverage, final selection and returned evidence metadata. No description stage or new inspection calls.
- 177 focused/relevant checks pass; actual TypeScript runs `run-20260828T021522Z` / `run-20260828T021533Z`
  completed partial/false, 2/2 Oracle files, 87,747/107,062 tokens. All final/coverage candidates carry reasons;
  three real reassessments receive prior reason (one navigation-to-direct, one unchanged navigation, one unchanged
  rejection). Existing direct-proof cache reused two judgments per run; no live direct-to-navigation reassessment
  exercised the original concern. Retained for review, not quality-accepted; metadata uses unchanged budgets.
- Run 2's navigation-only watchRecursivePattern is still appended by post-LLM active-island preservation despite
  its explicit limitation. Rationale transport is not a fix for that separate deterministic admission boundary.
- Follow-up loss audit: missing Builder is excluded before comparison by whole-file prefix budgeting in both
  runs (FPK-1/IOC-1); run 1's 43-owner editorServices group adds 40,613 request characters and yields no selection.
  Helpers' snippets lose semantic eligibility, but a separate file trace is created in both runs. That trace is
  excluded by `source_island_not_selected` (955/1166): the gate actually requires the exact source candidate,
  verifyTransitiveReferences, to be accepted by final consolidation, not any selected member of its island/file.
  Later active-island preservation returns other WatchMode snippets without reevaluating file traces. This corrects
  the earlier incomplete attribution to qualification alone; see the experiment record's file-trace follow-up.

## SBR-1 — Description memory, source inspections and downstream caveats

- [Source brief / inspection experiment](source-brief-inspection-experiment.md): reverted at user request on
  2026-08-28; baseline `7c50ba2` restored and experiment branch deleted. Runs/replays preserved and explicitly
  labelled outside the baseline statistics cohort. Two completed retries showed no final-quality improvement and
  materially higher cost. Full measurements and failed attempts remain in the decision record/changelog.
- Pending owner questions coalesce and retain provenance in focused tests; live scheduling delays requests and leaves
  unanswered work at the round limit. New question wording is not proof of semantically new work.
- Description memory still grows through complete call metadata and per-owner claims. Do not resolve this by silently
  clipping evidence or increasing budgets. Generic test support is also overstated by the unchanged final selector,
  which does not receive qualification's missing-information warnings. These are separate follow-up boundaries.
- FPK-1 remains: early file admission can exclude the implementation before descriptions exist. This experiment does
  not repair it. See the record's full dense/sparse → resolution → admission → recovery → final audit.

## POS-1 / IOC-2 — Positive proof retention and pre-comparison body visibility

- 2026-08-28 follow-up: [group contract and focused cards](group-contract-and-focused-owner-cards.md).
  Group-keyed schema passes two real fixed-input calls and both actual runs; retained as a contract correction.
  Focused source windows pass two comparisons but still admit six saved-input files. Actual 225224Z / 225234Z:
  3/2 Oracle files, partial/false, 101,440/101,088 tokens. Provisional, not quality-accepted; FPK-1 still loses
  builderState before comparison in the second run. Later description/inspection work is tracked separately in SBR-1.

- Record: [positive proof / body / island experiments](positive-proof-owner-body-island-experiments.md).
- P: positive-only reuse and verified-crop source retention are provisional after 213229Z / 213541Z (3/2 Oracle
  files). No natural crop event and no live incremental quality benefit over the previous cache demonstrated.
- A targeted body repair: two isolated real calls fail the existing owner/group validation boundary (IOC-1).
  Not activated; do not repair model IDs deterministically.
- B consistent cards: two valid isolated calls and actual 214614Z / 214625Z, 2/2 Oracles. Useful formerly bodyless
  snippets reach final evidence, but enlarged cards narrow file admission. Same-input replay 17→6 files; maps to
  FPK-1. Provisional for user review, not quality-accepted. No further automatic tuning or budget increases.
- Island-aware final admission is analysis only. Four TypeScript and two each Pandas/Vue audits support inspecting
  whole-island preservation, but direct-count/majority gates exclude useful evidence and island count does not bound
  input size. This must be a separate experiment, not a silent extension of body disclosure.

## QFL-1 — Qualified call leads: semantic priority and final-flow survival

- Experiment: [`qualified-structural-file-lead-experiment.md`](qualified-structural-file-lead-experiment.md).
- Status: first integration reverted on 2026-08-27; restored explicit-request-before-incidental-call follow-up is
  best-effort retained after two complete TypeScript and one each Pandas/Vue run. Same-queue ordering is verified
  on saved inputs; no live queue winner differed. Maps to VL-1/VL-2 and ISL-1; final-flow filtering is unchanged.
- Repeatable intermediate result: a visible qualified caller recovered `getReferencedByPaths` as direct evidence in
  both actual TypeScript runs. Final flow admission discarded it as adding no new causal responsibility in both.
- Competing leads: the new structural-child priority consumed both reserved executions while explicit qualification
  follow-ups remained pending. One other lead was rejected as irrelevant; another led to direct cache evidence that
  reached, but was not selected by, final consolidation.
- Next boundary: call-level semantic priority and preservation of necessary read-only connecting owners. Do not fix
  this by raising action caps, globally boosting target files, or automatically converting every call into evidence.
- Follow-up finding: saved queues verify the new ordering, but a live run spends both slots before explicit requests
  arrive. Separately investigate timing of exploratory capacity use; do not confuse this with same-queue priority.
- Cross-language boundary: the source_owner source-kind/call-inspection incompatibility is now corrected separately;
  see [`ast-owner-recovery-compatibility.md`](ast-owner-recovery-compatibility.md). Validated AST callables can seed
  inspection without fabricated persistent nodes. Live Vue inspection reaches existing target-uniqueness and lookup
  budget boundaries, with no new recovery executions. Another live run never passes the direct-evidence gate.
  Target-side AST-only/alias resolution remains open; do not broaden eligibility and timing as part of adapter repair.
  Pandas's missing owner is already deferred by early file admission, a separate unchanged boundary.
- Detailed run IDs, trace lines, costs, and rollback artifact are in the decision note and retrieval changelog.
- Subsequent final-flow experiment: a narrow direct-evidence call-connection exception is provisionally retained;
  see [`helper-flow-and-file-packing-experiments.md`](helper-flow-and-file-packing-experiments.md). Saved pools recover
  the connecting helper; one live final LLM selects it. Another live run reclassifies all builderState snippets as
  navigation-only without obligation IDs, so they vanish between raw final pool and obligation-state flow input.
  That earlier qualification/mapping boundary is separate from the causal-role filter and remains unresolved.
  Follow-up: run-local semantic qualification reuse is provisionally retained after isolated and live checks; see
  [`qualification-reuse-and-completion-budget-experiment.md`](qualification-reuse-and-completion-budget-experiment.md).
  Recorded identical-body downgrades are suppressed, but initial incorrect judgments and changed-source
  requalification remain separate issues. No qualification-support rule or body-disclosure change is included.
  Final pair 153030Z / 153303Z has 3/1 Oracle overlaps, so combined quality is not accepted. Weak-run builderState
  helpers reach final input but are unselected; its cached direct watchMode test falls after the final budget crossing.
  Reuse does not guarantee final survival, and indirect controller/candidate effects remain unisolated.

## FPK-1 — Complete-file packing versus useful owner visibility

- Experiment: [`helper-flow-and-file-packing-experiments.md`](helper-flow-and-file-packing-experiments.md).
- The former prefix rule stopped before an oversized file. Skip-and-continue was provisionally retained after two
  completed Pandas runs, then explicitly rejected by the user on 2026-08-27. It is replaced by an append-crossing
  ranked prefix: include the complete crossing file, then stop (no smaller-file backfill). Final-flow admission is
  tested separately with the same stopping semantics. See
  [`append-crossing-input-budget-experiment.md`](append-crossing-input-budget-experiment.md).
- Append-crossing follow-up: deterministic boundaries pass, but two final calls (and retries) exhaust the unchanged
  completion allowance, and a replacement fails owner/group validation (IOC-1). No final-quality comparison exists.
  Crossing server-file snippets all remain dormant. Final crossing flows reach the LLM, but the later explicit
  connection list receives no room once flow accounting is over budget. Keep provisional for user review; investigate
  flow/connection admission units and final-output reliability separately, without silently enlarging limits.
- User-directed correction: stripping connections was an implementation error, not an intended tradeoff. Eligible
  metadata now accompanies the unchanged admitted flow/candidate prefix without a second budget gate. Two exact
  saved-input replays recover all 12 connections in each input. Fresh runs 142925Z / 142935Z finish partial/false with
  3/3 implementation Oracles and preserve 8/8 and 9/9 eligible connections. The first naturally crosses the flow
  threshold. Correction retained; output caps and owner-source visibility are unchanged. See the correction section
  in the append-crossing decision note. This does not prove the prior LLM failures were caused by missing metadata.
  Completion-limit follow-up: the optional-output-budget experiment removes the explicit generation cap, not input
  budgets. Both real saved failed-input replays return valid selections; one requires 4,574 completion tokens.
  Full-run validation and costs are in the qualification-reuse/completion-budget decision note above.
- Same-input replay proves newly admitted series.py in one live run, but _binop's owner-comparison view contains
  only its signature and the LLM leaves it dormant. Another live run still cannot fit series.py and adds plotting.py.
  Distinguish a packing improvement from source-visibility or owner-selection improvement. Both runs later recover
  _binop through independent new-island search; one retains it, the other downgrades it to navigation_only with no
  obligations and loses it before flow selection. Do not raise limits or invent a relevance guarantee from unused
  capacity. Final quality/tokens are recorded in the experiment note.

## QOS-1 — Qualification-scoped obligation support in final-flow admission

- Experiment: [`../qualification-obligation-scope-experiment.md`](../qualification-obligation-scope-experiment.md).
- Status: best-effort retained on 2026-08-26. Exact saved-batch replays twice removed all direct obligation support
  from an unrelated compile-on-save test range. Two actual TypeScript runs completed without contract failures, but
  neither naturally retrieved that range.
- Open question: when a broadly recurrent but semantically narrow candidate is naturally present, does qualification
  scoping reliably reduce its flow score and final admission without suppressing valid implementation owners?
- Constraint: do not add a blanket test penalty or conflate retrieval provenance with semantic proof. Audit qualified
  support IDs, retrieval provenance IDs, flow score, budget admission, and final selection separately.

This file is the small registry for retrieval-experiment behavior that remains untested, unresolved, or
deliberately bounded. It does not repeat measured results; those remain in
[`../retrieval-changelog.md`](../retrieval-changelog.md). When a later run exposes a suspicious behavior,
map it to an entry here before treating it as a new regression or inventing another heuristic.

## DIC-1 — Dormant completion final value and activation stability

- Experiment: [`../dormant-island-completion-experiment.md`](../dormant-island-completion-experiment.md).
- Status: candidate handoff restored as best-effort on 2026-08-26. Two TypeScript acceptance runs activated the stage
  without reducing their three implementation-Oracle overlaps; one activation produced a useful downstream handoff,
  while the other remained navigation-only. Pandas selected no dormant owner and retained its complete causal chain.
- Open question: do dormant completions repeatedly add distinct final evidence or necessary controller actions across
  more cases, rather than merely enlarging an already represented same-file island?
- Constraint: do not broaden same-file structural eligibility, the explicit missing-information match, attempt caps,
  or semantic qualification. Every activation must remain attributable in the trace with exact stage tokens and
  downstream actions.
- Symptoms that map here: repeated navigation-only dormant promotions, final omission of every completion, or a
  dormant helper consuming cost without changing later actions, coverage, or selected evidence.

## HAP-1 — One-call hybrid planner versus native action scheduling

- Experiment: [`agent-planned-native-controller.md`](agent-planned-native-controller.md).
- Status: rejected on 2026-08-23; runtime reverted in `7387d6c` and `d11537e` after valid runs
  `run-20260823T183021Z` and `run-20260823T183349Z` were both `partial/false`. The exact initially admitted
  `Series::_binop` owner survived planner qualification in only one repeat.
- Question: can one persistent planner call per round jointly classify newly disclosed observations, update coverage,
  and select bounded typed actions more reliably than qualification + coverage + deterministic pool scheduling?
- Constraint: this must replace those per-round decisions, not add another LLM call. Native action execution,
  grounding, islands, and final evidence selection remain.
- Cost boundary: planner tokens must not exceed the native qualification-plus-coverage tokens replaced unless repeated
  final-evidence quality justifies a measured small increase.
- Resolution requires repeated focused validation plus actual-pipeline comparisons with trace-confirmed absence of the
  old per-round qualification and coverage calls.
- A narrower follow-up that separates deterministic source visibility from semantic qualification, guarantees source
  for explicit inspections, and considers moving only action selection into the coverage call is specified in
  [`../temporary-source-visibility-and-agent-inspection-plan.md`](../temporary-source-visibility-and-agent-inspection-plan.md).

## AGT-1 — Referenced initial lead ignored after source inspection

- Experiment: seeded agentic downstream retrieval.
- Status: resolved for the specific early-termination boundary on 2026-08-23; overall agent quality remains
  experimental.
- Observed evidence: pandas `run-20260823T161050Z` showed exact `Series::_binop` in the first working-context
  projection, while inspected `flex_wrapper` literally called `self._binop(...)`. The agent ignored that stored lead,
  repeated empty exact searches, and hit `no_evidence_gain` before inspecting it.
- Boundary: the lead survived Qdrant, file grouping, CodeGraph, initial-lead construction, and working-context
  projection. The first loss was the agent navigation decision.
- Experiment constraint: expose exact referenced stored leads and bounded tool outcomes; do not automatically execute,
  promote, or select a lead and do not add repository-specific symbol rules.
- Resolution requires two repeatable focused model decisions plus an actual run where the present referenced lead is
  inspected before termination. Full measurements belong in the retrieval changelog.
- Resolution evidence: deterministic reference/outcome/guard checks passed repeatedly; two unchanged live provider
  calls selected the referenced `_binop` lead. Actual run `run-20260823T163733Z` inspected the exact stored lead in
  iteration 2. After progressive context compaction fixed the later integration failure, completed run
  `run-20260823T164358Z` searched and opened `_binop` and continued through all eight iterations rather than stopping
  on no gain. It still failed to resolve the separate generated `Series.add` wrapper path, so this closure must not be
  interpreted as agentic-mode quality acceptance.

## CDR-1 — Deferred sibling ranking and dynamic callable installation

- Experiment: [`controller-discovery-reliability-experiment-plan.md`](controller-discovery-reliability-experiment-plan.md).
- Status: partially resolved on 2026-08-25. Assignment-defined JavaScript functions now have stable source-owner
  identities. Expanded nonadmitted deferred recovery was tested and reverted after unstable final Oracle retention.
- Open question: how should the controller rank structurally distinct sibling owners that inherited identical Qdrant
  provenance? Pandas repeats alternated between `series_flex_funcs`, comparison wrappers, and sparse arithmetic.
- Rejected approach: a repository-wide source callable-relationship provider produced one unrelated factory edge and
  did not repeatably connect the generated `Series.add` chain; it was reverted.
- Constraint: a follow-up must produce the exact factory/registration chain repeatably without global speculative
  edges, repository-wide scan cost, or an extra unbounded controller action family.

## CSV-1 — Selective inspection of uncovered controller source

- Experiment: [`controller-uncovered-source-and-visibility-experiment.md`](controller-uncovered-source-and-visibility-experiment.md).
- Status: controller-wide residual materialization, forced complete-source reservation, rejected-owner lifecycle
  re-entry, experiment-specific residual telemetry, and trace-only completeness were rejected or reverted on
  2026-08-26. The runtime is restored to a clean pre-visibility baseline; independently accepted raw-source
  materialization-loss telemetry remains.
- Evidence: corrected acceptance runs `run-20260825T234452Z`, `run-20260825T234825Z`,
  `run-20260825T235205Z`, and `run-20260825T235513Z` retained their implementation Oracles at ranks 1–2 but remained
  `partial/false`. True residuals did not improve final mechanism coverage; a promoted Vue benchmark residual helped
  place benchmark evidence at final rank 6.
- Final retained-state evidence: Pandas `run-20260826T001953Z` / `run-20260826T002319Z` retained the implementation
  Oracle at ranks 3/2 using 73,763/65,955 tokens; Vue `run-20260826T001050Z` / `run-20260826T001345Z` retained it at
  rank 1 using 66,721/63,452 tokens. All four remained `partial/false`, and every residual remained telemetry-only.
- Open question: can the coverage/action LLM combine semantic qualification with exact fitted-source completeness to
  choose a useful inspection, without admitting all residual fragments into canonical evidence or prequalification?
- Constraint: proposals must pass typed validation, pre-slot novelty suppression, scheduler/executor accounting,
  run-local memoization, and trace logging. Suppressed outcomes return to the next action context. A selected
  inspection must materially expand the view and then undergo ordinary qualification. See the replacement plan in
  [`../temporary-source-visibility-and-agent-inspection-plan.md`](../temporary-source-visibility-and-agent-inspection-plan.md).

## RAS-1 — Stable exact anchors versus downstream retrieval quality

- Experiment: [`request-analysis-anchor-stability-experiment.md`](request-analysis-anchor-stability-experiment.md).
- Status: exact anchor inventory and the TypeScript file-admission boundary resolved on 2026-08-26. Actual runs
  `run-20260826T093942Z` and `run-20260826T094609Z` produced identical exact anchors, admitted `builderState.ts` at
  file rank 5 in both, and retained three/four implementation Oracles in final evidence.
- Remaining question: conceptual search terms, proposition wording, and stage `anchor_refs` remain LLM-generated.
  They still changed canonical snippets (382/385), admitted files (13/11), selected owners (22/15), controller work,
  and total tokens (118,400/124,770). Both runs remained `partial/false` because the precise failing handoff and
  concrete behavioral contrast were unresolved.
- Constraint: do not broaden exact anchors to eliminate semantic-query variation. Treat proposition/query stability
  and controller completion as separate experiments with their own repeated acceptance runs.

## How to use this registry

1. Match the observed symptom to an open item below.
2. Link the new run ID and trace event to that item.
3. Decide whether the run exercised the open boundary or exposed a different problem.
4. Update the item's status and evidence link. Put full measurements in the retrieval changelog.
5. Remove an item only after actual-pipeline evidence resolves it; do not close it from unit tests alone.

## IOC-1 — Initial owner comparison scale and support independence

- Proposed follow-up (not implemented): admit globally ranked individual canonical snippets, using file grouping
  only for serialization and shared metadata. Unlike the rejected shortlist, this changes admission units before
  the budget boundary, so savings can admit other files. Compare saved inputs for prior semantic-owner retention,
  file diversity, per-file concentration, and exact serialized cost before live experiments. Existing snippet
  priority is exact anchor, recurrence, rank, score, path/line; it is not a semantic relevance guarantee. Avoid
  presenting a hard ten-per-file cap or rank-only reorder as a new solution to the already measured shortlist loss.
- Experiment: compact initial owner comparison plus complete structural range resolution.
- Current budget follow-up: FPK-1 now provisionally includes the complete crossing file before stopping; 60K/100K
  are thresholds rather than strict pre-add ceilings. Replacement run 20260827T132218Z returned two watchMode owners
  under the wrong group (response line 57), correctly rejected by membership validation. No final result exists;
  request/schema reliability remains separate from mechanical admission verification.
  Recurred in uncapped-output/reuse run `run-20260827T153020Z`: response line 57 assigns `o145` to
  `g12` instead of `g13`; fails before qualification, with 25,314 tokens and no final result.
- Latest bounded follow-up: the [ten-owner semantic/diversity shortlist](owner-comparison-shortlist-experiment.md)
  was rejected and reverted on 2026-08-27. Corrected actual runs `run-20260827T033557Z` / `run-20260827T034005Z`
  reduced comparison candidates and tokens but retained 2/3 implementation Oracles versus the unchanged baseline's
  3/4. Omitted owners were recoverable, sometimes only in later rounds; recovered navigation-only test helpers did
  not complete the issue chain. No deterministic within-file shortlist is enabled. Detailed measurements and the
  reproducible patch remain in the decision note and changelog.
- Status: the single-canonical-pool rewrite, grouped owner-selection contract, and 60K quality-prefix admission are
  mechanically accepted through pre-qualification on the TypeScript case; cross-repository, controller,
  final-evidence, and overall token/quality acceptance remain open.
- Implemented behavior:
  - every initial Qdrant range is resolved through parallel CodeGraph batches of 80; no first-80 truncation remains;
  - duplicate CodeGraph node IDs and overlapping unresolved ranges canonicalize once before file admission; sibling
    owners remain independent, and classes/outer callables are context;
  - complete owner source is disclosed only after owner comparison selects it;
  - each owner records distinct owner-aligned raw views, obligations, and channels rather than exposing recurrence
    alone;
  - file admission retains one retrieval-ranked prefix, provisionally including the crossing group at the 60,000 /
    100,000 thresholds (FPK-1), with no binary obligation reservation or later-file backfill;
  - the LLM performs the only global 24-owner selection using grouped primary/additional owners. There is no numeric
    per-file cap; runtime validates global count, group membership, and exhaustive selected/deferred/dormant states.
- Measured evidence:
  - smoke `run-20260821T211044Z` resolved 172/172 ranges, later promoted exact `Series::_binop`, and spent 25,958
    owner-comparison tokens;
  - final run `run-20260821T211538Z` resolved 192/192 ranges, but its stochastic initial retrieval contained no
    `_binop` range; it ended `partial/false` and spent 26,392 comparison tokens out of 102,926 retrieval tokens;
  - one raw chunk repeated under four or five obligations can still look recurrent while having only one channel.
  - the follow-up repair playbook retained compact shared views and executable lead lines. Pandas smoke
    `run-20260821T224935Z` selected and qualified exact `Series::_binop`; two final pandas runs
    (`run-20260821T225305Z`, `run-20260821T225808Z`) were still `partial/false` and did not retain it in final
    evidence. Their comparison costs were 21,523 and 23,243 tokens.
  - TypeScript final runs `run-20260821T230249Z` and `run-20260821T231406Z` remained at two implementation-Oracle
    overlaps, with 19,116 and 20,650 comparison tokens. This is a non-regression signal, not enough to justify the
    comparison cost as a stable gain.
  - TypeScript pre-qualification runs `run-20260824T223236Z` and `run-20260824T223430Z` canonicalized 674 -> 415 and
    718 -> 464 occurrence views, admitted 49 and 38 files within exact comparison payload budgets, and selected
    15/10-files and 23/15-files without a post-LLM reducer. Their complete lifecycle equations were
    `415 = 15 selected + 86 deferred + 314 dormant` and
    `464 = 23 selected + 140 deferred + 301 dormant`.
  - Those runs spent 37,960 and 37,847 owner-comparison tokens versus 18,497 in the old-flow baseline. They retained
    central Builder/BuilderState/watch evidence but the second run still selected some unresolved test/config noise.
    This resolves the requested mechanical boundary, not the token/quality question.
  - The isolated evidence-region attempt in `run-20260825T010258Z` reduced 405 canonical snippets to 348 top-level
    regions but still filled 99,901 characters and used 38,788 comparison tokens. Repeat
    `run-20260825T010523Z` failed the unchanged two-per-file invariant after selecting three directly relevant
    `builderState.ts` regions. The attempt was reverted; details are in
    [`initial-evidence-region-experiment.md`](initial-evidence-region-experiment.md).
  - The isolated preferred-size quality-prefix admission attempt in `run-20260825T032456Z` and
    `run-20260825T032649Z` admitted ten files and 159/177 owners at 53,179/55,334 characters, reducing comparison cost
    to 20,099/21,509 tokens. Both responses concentrated on several relevant owners in central Builder,
    BuilderState, or TsBuildPublic files and were rejected by the unchanged two-per-file invariant. The runtime
    attempt was reverted; details are in
    [`initial-file-admission-cost-experiment.md`](initial-file-admission-cost-experiment.md).
  - Exact grouped-contract replays selected 15 owners across six files for both saved 159/177-owner payloads. Largest
    file shares were 26.7% and 20%; third-and-later owners were distinct Builder/BuilderState/TsBuild mechanisms.
  - Combined actual runs `run-20260825T035631Z` and `run-20260825T035754Z` admitted 172/191 owners across 14/18
    files at 59,457/59,956 characters and used 22,307/23,756 comparison tokens. They selected 10/15 owners across
    6/8 files, completed lifecycle accounting, and prepared qualification within 29,513/34,982 characters.
  - Full runs `run-20260825T043113Z` and `run-20260825T044117Z` retained three substantive Oracle implementation
    files each versus two in earlier checkpoint `run-20260825T000741Z`, while total retrieval tokens fell from
    114,240 to 101,747/93,656. Both remained `partial/false`; missing links are now downstream issue-specific
    watcher/project-reference/wildcard/direct-import/diagnostic handoffs rather than loss of the initial owners.
- Still unresolved:
  - whether comparing roughly 170-190 owners in one call remains accurate across repositories or becomes too diffuse;
  - whether the reduced comparison-token cost yields stable downstream owner-quality gains;
  - whether raw chunk/query-view/obligation/channel counts should affect selection at all, and if so how, without
    turning repeated broad queries into false independent support;
  - repeated acceptance runs where the correct owner is present in the initial ranges, so selection stability can be
    separated from upstream stochastic retrieval.
  - whether the deterministic retrieval-ranked 60K prefix is sufficiently stable across cases or needs a separately
    validated semantic/diversity admission signal. Do not restore raw first-owner order or a fixed file ceiling.
  - the compact source view is capped at 80 characters and deliberately keeps one or a few high-value complete
    lines. It preserved the observed `return self._binop(...)` lead, but secondary useful lines may still be hidden.
    Audit the literal comparison view whenever a resolved owner is unexpectedly rejected; do not call this format
    lossless until broader repositories exercise multi-line competing leads.
- Symptoms that map here:
  - all CodeGraph ranges resolve, but a present correct owner is rejected by initial owner comparison;
  - a candidate has high query-view/obligation counts but only one raw chunk or one channel;
  - owner-comparison input approaches its 100,000-character fail-fast limit or dominates retrieval tokens.
- Do not respond by restoring a first-N range slice, unioning overlapping chunks into large snippets, or treating raw
  recurrence as proof. Inspect the four support counts and the exact owner-comparison payload first.

## VL-1 — Verified-lead cap and final-round continuation

- Experiment: verified direct-lead continuation.
- Status: open; the ordinary two-lead path is implemented. Cap exhaustion and pending-lead competition were observed
  in the subsequently reverted QFL-1 experiment; the benefit of executing those remaining leads is still untested.
- Implemented behavior:
  - a newly validated direct call counts as `verified_lead_gain`, so `no_evidence_gain` cannot stop before its
    next scheduling opportunity;
  - one reserved verified-lead action may execute per round;
  - at most two verified leads execute in one run;
  - a second lead discovered in round 3 may use the controlled round 4;
  - pending work is emitted in the terminal trace with `execution_cap_reached` or
    `round_budget_exhausted` rather than disappearing silently.
- Observed evidence: pandas smoke `run-20260820T231100Z` executed `Series._binop` in round 2 and
  `_maybe_match_name` in round 4; both became direct evidence. See the
  "Verified direct-lead continuation diagnostic" entry in the retrieval changelog.
- Still untested:
  - a third valid lead discovered after two verified executions;
  - a valid lead first discovered in round 4;
  - whether the two-execution cap suppresses a necessary distinct mechanism rather than redundant/deeper work;
  - whether allowing a fifth round would improve evidence enough to justify its qualification and coverage cost.
- Symptoms that map here:
  - trace contains a useful `pending_verified_leads` entry at controller termination;
  - `verified_lead_block_reason` is `execution_cap_reached` or `round_budget_exhausted`;
  - a final evidence miss can be traced to an unexecuted, uniquely resolved direct callee already present in
    that pending queue.
- Do not respond by automatically raising the cap. First inspect whether the blocked lead is distinct,
  issue-relevant, and more useful than the two executed leads; compare the likely extra-round token cost.

## VL-2 — Acceptance stability across repositories

- Experiment: verified direct-lead continuation.
- Status: open after initial full final-selection checks; one run per repository is not enough to establish
  stochastic stability.
- Known evidence:
  - pandas `run-20260820T232259Z` executed exact `Series._binop`, promoted it, and retained it at final rank 2;
  - TypeScript `run-20260820T232621Z` executed exact `ProjectService.watchWildcardDirectory`, but final selection
    correctly rejected that editor-service method as tangential to the solution-builder mechanism;
  - neither run left a pending verified lead or exercised the two-execution cap.
  See "Verified direct-lead full-selection checks" in the retrieval changelog for measurements.
- Still untested:
  - repeated final-selection runs on pandas and TypeScript under unchanged settings;
  - the useful-to-tangential rate of verified leads across more repositories;
  - whether the added qualification cost remains bounded when a repository produces two leads.
- Symptoms that map here:
  - verified leads execute and become direct evidence but disappear in final selection;
  - token growth comes from extra continuation rounds without a corresponding candidate-quality improvement;
  - repository-generic utilities repeatedly pass exact resolution and occupy the reserved slot.

## VL-3 — Maturation-produced cross-file structural child

- Experiment: a promoted owner produced by a bounded maturation action may expose one exact cross-file callee needed
  by the same unresolved obligation.
- Status: mechanically implemented; natural actual-pipeline activation remains open.
- Implemented safety boundary:
  - the source observation must be newly produced by a maturation action and promoted;
  - the exact call must be visible in disclosed source and named by qualification follow-up or the unresolved
    coverage claim;
  - exact-symbol lookup must resolve one repository node in another file;
  - the target must not already be observed, pending, or executed;
  - the existing verified-lead pool executes at most one such child in a round and two verified leads in the run;
  - the resulting observation carries an explicit `calls` parent relationship and can seed file-level evidence.
- Evidence:
  - focused WatchMode-shaped tests prove `verifyProjectChanges -> verifyTscWatch` creates one structural child, while
    a non-matured direct observation does not open the gate;
  - TypeScript smoke `run-20260822T031233Z` did not activate the new rule because the ordinary 18-call file handoff
    reached Helpers first;
  - TypeScript final run `run-20260822T032015Z` selected WatchMode but produced no eligible maturation child. Its
    ordinary file expansion followed virtual-file-system and tsbuildPublic targets, so Helpers was absent.
- Still unresolved:
  - a natural run in which WatchMode maturation exposes `verifyTscWatch`, the new child executes, and the Helpers
    trace is judged by final selection;
  - whether unresolved-claim wording names exact callees reliably enough without becoming prompt-sensitive;
  - whether prioritizing a structural child over another verified lead ever suppresses a more useful same-file lead.

## IFC-1 — Persistent island continuations and pool comparability

- Experiment: [island-centered controller](island-centered-controller-experiment-plan.md).
- Status: ordinary persistence and owner-maturation folding are best-effort opt-in; broad pool unification is not
  accepted.
- Proven boundary: the controller can retain a normalized ordinary continuation after it disappears from the current
  graph-capability catalogue and later execute it without increasing the productive ordinary-slot cap. TypeScript
  `run-20260830T123601Z` naturally exercised this path, but the retained file expansion returned empty.
- Accepted negative result: deferred-file rescue cannot simply enter the active-island allowance. Diagnostic
  `run-20260830T124320Z` selected zero rescues, so that fold was removed.
- Promising boundary: owner maturation can compete within its already-grounded active island. TypeScript
  `125440Z` / `125843Z` retained all four target files and Vue `130338Z` retained its implementation Oracle.
- Still unresolved: Pandas regression could not reach controller execution because two runs failed the same strict
  round-zero qualification contract. Do not promote the opt-in flags or fold test maturation, verified leads, or
  pending handoffs until a valid Pandas comparison and a productive persisted-continuation activation exist.
- Symptoms that map here: a known normalized action disappears solely because a later capability request omits its
  node; an auxiliary family adds work outside the described ordinary allowance; folding a family reduces its
  selection rate to zero.

## ISL-1 — Mechanism fragmentation through an unobserved connector

- Experiment: semantic evidence islands and island-aware scheduling.
- Status: partially resolved and still open for stability/noise. The motivating one-connector path is implemented
  and verified in one full run; broader safety is not yet established.
- Observed evidence: TypeScript `run-20260820T232621Z` placed the selected Builder functions and the qualified
  BuilderState functions in separate islands. CodeGraph/source inspection shows the exact path
  `builder.ts::getNextAffectedFile -> BuilderState.getFilesAffectedBy ->
  builderState.ts::getFilesAffectedByUpdatedShapeWhenNonModuleEmit`. The middle owner was absent from the observation
  pool, so the closed-set component query could not join the endpoints and final selection saw overlapping state
  candidates without their causal relationship.
- Experimental correction under test:
  - connect two promoted endpoints directly when the language-routed source operation resolves a qualified call from
    one exact owner to the other; label this `source_verified_direct_call` rather than discarding it because both
    endpoints are already observations;
  - allow exactly one unselected connector and exactly two directed calls;
  - prefer native CodeGraph edges; when those are absent for qualified/conditional calls, require unique CodeGraph
    owner resolution plus call sites from the language-routed source-AST operation and label the result
    `source_verified_connector_path`;
  - require both endpoints to be promoted and to overlap on a still-unresolved obligation;
  - keep the connector as relationship/navigation metadata only, never as evidence;
  - serialize the collapsed endpoint relationship with its exact connector name and provenance for final selection.
- Still untested:
  - an actual-pipeline run in which the new direct source-verified edge joins the selected
    `builder.ts::getNextAffectedFile` and `builderState.ts::updateExportedFilesMapFromCache` endpoints;
  - repeated TypeScript runs under unchanged settings;
  - a full Python repository run that naturally exercises the source-verified connector fallback (the Python adapter
    and language-neutral connector contract are covered by focused tests);
  - whether generic utility connectors create false merges in real repositories;
  - cross-repository behavior when many promoted endpoints share one common utility caller/callee;
  - whether more than one connector is genuinely needed (do not broaden the depth from this experiment).
- Verified evidence:
  - exact-snapshot replay of the endpoints saved by `run-20260821T010824Z` formed one component through a real
    TypeScript-adapter `source_verified_direct_call` from `getNextAffectedFile` to
    `updateExportedFilesMapFromCache`; the next two complete stochastic runs did not naturally contain that exact
    endpoint pair, so full-run stability remains open;
  - `run-20260820T235750Z` formed one active, cross-file Builder/BuilderState island;
  - final selection received the source-verified `getNextAffectedFile -> BuilderState.getFilesAffectedBy ->
    getFilesAffectedByUpdatedShapeWhenNonModuleEmit` relationship;
  - it retained both Builder traversal and BuilderState mutation owners with distinct causal contributions and
    recovered all four implementation Oracle files within the top five unique files;
  - ten connector records produced no observed generic-utility or cross-obligation false merge in that run.
  See "One-connector semantic-island completion" in the retrieval changelog for measurements.
- Symptoms that map here:
  - promoted observations covering the same mechanism and obligation remain in separate islands despite an exact
    two-call CodeGraph path;
  - final selection describes one endpoint as redundant or isolated because the intervening navigation owner is absent;
  - multiple functions from one mechanism consume separate beam scopes solely because their exact connector was not
    retrieved as evidence.
