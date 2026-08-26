# Retrieval Experiment Open Questions

This file is the small registry for retrieval-experiment behavior that remains untested, unresolved, or
deliberately bounded. It does not repeat measured results; those remain in
[`../retrieval-changelog.md`](../retrieval-changelog.md). When a later run exposes a suspicious behavior,
map it to an entry here before treating it as a new regression or inventing another heuristic.

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

## How to use this registry

1. Match the observed symptom to an open item below.
2. Link the new run ID and trace event to that item.
3. Decide whether the run exercised the open boundary or exposed a different problem.
4. Update the item's status and evidence link. Put full measurements in the retrieval changelog.
5. Remove an item only after actual-pipeline evidence resolves it; do not close it from unit tests alone.

## IOC-1 — Initial owner comparison scale and support independence

- Experiment: compact initial owner comparison plus complete structural range resolution.
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
  - file admission retains one retrieval-ranked file prefix under a preferred 60,000-character request target, with
    100,000 as a hard ceiling and no binary obligation reservation or later-file backfill;
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
- Status: open; the ordinary two-lead path is implemented and observed, but the overflow boundary is untested.
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
