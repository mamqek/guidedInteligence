# Retrieval Experiment Open Questions

This file is the small registry for retrieval-experiment behavior that remains untested, unresolved, or
deliberately bounded. It does not repeat measured results; those remain in
[`../retrieval-changelog.md`](../retrieval-changelog.md). When a later run exposes a suspicious behavior,
map it to an entry here before treating it as a new regression or inventing another heuristic.

## How to use this registry

1. Match the observed symptom to an open item below.
2. Link the new run ID and trace event to that item.
3. Decide whether the run exercised the open boundary or exposed a different problem.
4. Update the item's status and evidence link. Put full measurements in the retrieval changelog.
5. Remove an item only after actual-pipeline evidence resolves it; do not close it from unit tests alone.

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
  - allow exactly one unselected connector and exactly two directed calls;
  - prefer native CodeGraph edges; when those are absent for qualified/conditional TypeScript calls, require unique
    CodeGraph owner resolution plus AST-localized call sites and label the result `source_verified_connector_path`;
  - require both endpoints to be promoted and to overlap on a still-unresolved obligation;
  - keep the connector as relationship/navigation metadata only, never as evidence;
  - serialize the collapsed endpoint relationship with its exact connector name and provenance for final selection.
- Still untested:
  - repeated TypeScript runs under unchanged settings;
  - whether generic utility connectors create false merges in real repositories;
  - cross-repository behavior when many promoted endpoints share one common utility caller/callee;
  - whether more than one connector is genuinely needed (do not broaden the depth from this experiment).
- Verified evidence:
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
