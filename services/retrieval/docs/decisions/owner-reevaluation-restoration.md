# Owner reevaluation restoration experiment

Baseline: 6f5c17b; thesis is outside the experiment. Status: bounded variant tested
and rejected; original ranking restored, trace-only audit retained.

## Boundaries and dependency gate

The historical df75bfc implementation combines (1) deterministic qualified-primary
election, (2) island-root priority changes, and (3) extra held-challenger inspection
actions. It depends on the later qualification assessment contract. None is active
at this checkpoint. Existing island representatives already recompute after each
qualification update; newly qualified owners are not automatically discarded.

Before restoring behavior, instrument the existing island boundary without changing
its decisions. For every multi-owner island and update, record the incumbent, visible
qualification decisions, newly qualified owners, retained competitors, and exact
ranking signals. Also record same-file owners outside that island. This distinguishes
an actual stale representative from semantic ties and separate evidence islands.

The current contract supplies supported_obligation_ids (asserted established claims),
not the later separate partial-contribution IDs. Do not invent partial support or
silently restore the qualification contract. First determine whether an independent
owner-reevaluation intervention is justified by these actual inputs.

## Plan

1. Trace-only instrumentation and deterministic equivalence checks. Two fresh
   TypeScript and two Vue full pipeline runs, unchanged model/profile/index, final
   selection on, response generation off. Compare with recorded checkpoint pairs.
2. Audit every naturally occurring representative change and each new-owner
   competition; retain exact source/qualification/ranking evidence. Count initial
   elections, unchanged reelections, replacements and genuinely new challengers
   separately. Report reviewer agreement, disagreement and indeterminate cases;
   never equate a metadata winner or oracle hit with semantic superiority.
3. If a concrete defect is independently repairable, implement at most three narrow
   variants, test exact saved inputs twice, then run two main-case acceptance runs
   and two regression runs. If the required change is the separate qualification
   contract, report the dependency instead of mixing it into the experiment.

Scope excludes extra search actions, held-alternative nomination, final evidence
budgets, LLM prompts, source disclosure and index changes. No new LLM stage during
instrumentation; zero expected token effect. A later priority intervention could
change active islands/actions and displace valuable context, so final file recall
alone cannot prove it correct. Revert a variant with repeated quality loss or no
repeatable intended-boundary benefit. Preserve failed attempts and diagnostics.

Relevant open questions: CDR-1 (siblings with identical provenance), QRC-1 (qualified
contribution retention) and ISL-1 (separate components). Detailed ledger pending.

## Variant 1: qualification-backed election only

Both baseline TypeScript runs naturally replace a broader propagation representative
with getReferencedByPaths because exact-anchor priority precedes semantic breadth.
The source helper is useful but its reverse-map lookup is narrower than the retained
export-propagation implementation. In 050625Z a later updateShapeSignature does replace
that helper, disproving an absolute stale-incumbent lock.

Test just the independent primary-election/priority part of the historical proposal:
elect one retained owner per file and explicitly supported obligation, preserving all
other candidates. Use current supported_obligation_ids, never pretend to have the
later partial-contribution contract. A primary count precedes existing island root
ranking, as in the historical integration. Election prefers direct support, exact
anchor, supported-obligation breadth, recurrence/rank, then stable source tie-breaks.
No held-owner inspection action is restored, and no new qualification or search is
scheduled directly. This is a narrower experiment, not the entire df75bfc feature.

Risk: qualification breadth can overstate an owner's importance; singleton files and
generated copies can receive primary counts; different island priority can change
follow-ups despite retaining all candidates. Audit these effects explicitly. Run two
TypeScript variants and two Vue regression variants after focused invariants and
saved-pool counterfactual checks. Reject ranking-only changes that do not demonstrate
repeatable intended-boundary improvement or show repeated end-to-end regression.

## Baseline live observations

Trace-only instrumentation has an explicit traced/untraced island-output equality test.
86 focused checks initially passed; variant/equivalence additions bring the total to 89.
An initial test command named a nonexistent test_evidence_islands module; corrected to
the actual test_qualification_first_retrieval suite. No failed live run was hidden.

| Run | Case | Initial elections | Preserved updates | Replacements | Merges | New-owner competitions | Reviewer agree / disagree | Oracle | Tokens |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- | ---: |
| 050616Z | TS | 8 | 12 | 2 | 1 | 5 | 2 / 3 | 4/4 | 106276 |
| 050625Z | TS | 6 | 13 | 2 | 1 | 6 | 5 / 1 | 4/4 | 109283 |
| 050636Z | Vue | 2 | 1 | 0 | 1 | 1 | 1 / 0 | 1/2 | 53692 |
| 050646Z | Vue | 5 | 8 | 0 | 1 | 1 | 1 / 0 | 1/2 | 60753 |

Run prefix: run-20260915T. All partial/false. Agreement counts assess the 13 events
where newly promoted owners compete with an existing island, not 13 independent
testcases and not all routine unchanged elections. Agreement means a defensible
representative among the visible alternatives, not a proven unique optimal owner.

### Every baseline new-owner competition

| Run / round | Selected representative | Review and exact reason |
| --- | --- | --- |
| TS 050616 / 1 | getReferencedByPaths replaces export traversal | Disagree: exact anchor wins over the retained export-map traversal; a reverse-map lookup is narrower than the propagation mechanism. |
| TS 050616 / 1 | updateWatchingWildcardDirectories survives merge | Disagree: recurrence 6 wins, but this only creates/closes watcher handles; visible getNextInvalidatedProject and watchWildCardDirectories expose actual scheduling/state gates. |
| TS 050616 / 2 | getReferencedByPaths retained | Disagree: newly inspected getFilesAffectedByUpdatedShapeWhenModuleEmit exposes the queue, signature test and recursive dependent propagation; the anchored lookup still wins. |
| TS 050616 / 2 | getSemanticDiagnosticsOfNextAffectedFile replaces watcher utility | Agree: visible affected-file draining and diagnostics computation are stronger issue behavior than watcher-handle maintenance, although anchor priority rather than semantic comparison caused it. |
| TS 050616 / 3 | diagnostics owner retained over introduceError | Agree: the new test helper triggers a build but does not expose diagnostics propagation; it stays complementary. |
| TS 050625 / 1 | getReferencedByPaths replaces export traversal | Disagree: same anchored lookup versus concrete export-map propagation distinction as the other repeat. |
| TS 050625 / 1 | getNextInvalidatedProject retained | Agree: keeps the project processing gate over an API interface and status helper; complements remain available. |
| TS 050625 / 1 | introduceError retained | Agree: it actually mutates input and starts a build; incoming test ranges expose a section heading/config invalidation rather than stronger source-change behavior. |
| TS 050625 / 2 | updateShapeSignature replaces getReferencedByPaths | Agree: declaration hashing and exported-module updates are stronger state evidence than reverse-map lookup. |
| TS 050625 / 2 | getNextInvalidatedProject survives merge | Agree: watch-host constructors and createNewProgram are relevant leads, but not stronger than the visible project status/processing gate. |
| TS 050625 / 3 | updateShapeSignature retained | Agree: new isChangedSignagure only compares existing/computed signatures, whereas the incumbent exposes their computation and export tracking. |
| Vue 050636 / 1 | original assertProp survives merge | Agree against new validateProp entry wrapper and bundle assertProp copy; original source directly exposes failed-type-to-diagnostic handoff. getInvalidTypeMessage remains a useful complement, not inferior proof. |
| Vue 050646 / 1 | original assertProp survives merge | Agree against the only newly promoted generated copy; not a claim that it is uniquely better than the already retained getInvalidTypeMessage. |

These choices do not delete other island members. Both TypeScript baselines retain
all four final focal files despite the four disputed intermediate priorities.
Full exact visible source, qualification reasons, IDs and ranking keys are preserved
in owner-reevaluation-ts-baseline.json / owner-reevaluation-vue-baseline.json under
testing/codeRepoQA/incremental-restoration. The raw run traces retain every election.

### Fixed-island counterfactual

Two deterministic executions over the saved records agree exactly: 23/22/4/14
island elections checked, 5/7/0/3 proposed winners changed. This is not a simulated
final score. Both first-round anchored lookup choices become export traversal.
Other changes include updateShapeSignature to export traversal and invalidation
gate to watchInputFiles; those are tradeoffs, not automatically improvements.
The replay uses exactly the election fields consumed by this variant; unlike the
historical implementation it does not add a best-score tie-breaker unavailable in
the existing island key. No source text or qualification result is synthesized.

## Variant 1 actual results

| Run | Case | Oracle | Tokens | Initial / preserved / replaced / merged island elections | New-owner island competitions: agree / disagree |
| --- | --- | --- | ---: | --- | --- |
| 051437Z | TS | 2/4 | 103292 | 6 / 14 / 1 / 0 | 3 / 1 |
| 051447Z | TS | 4/4 | 110969 | 13 / 31 / 0 / 1 | 5 / 0 |
| 051458Z | Vue | 1/2 | 54675 | 4 / 3 / 0 / 1 | 1 / 0 |
| 051508Z | Vue | 1/2 | 58271 | 2 / 2 / 0 / 1 | 1 / 0 |

All completed successfully, partial/false. Each election is a recorded island at one
controller update, not an additional LLM invocation. New-owner competition totals
are 4/5/1/1. They are different candidate populations from baseline, so 10/11 versus
9/13 agreement is NOT a controlled accuracy-improvement estimate.

### Every variant new-owner island competition

| Run / round | Winner | Review |
| --- | --- | --- |
| 051437 / 1 | export traversal retained | Agree: retains changed-signature/export-map propagation over reverse lookup, recursive export helper and whole-program diagnostic consumption. |
| 051437 / 1 | getUpToDateStatusWorker replaces buildNextInvalidatedProject | Disagree as a trigger representative: the visible upstream-status checks omit the source-change/timestamp part, while the incumbent visibly consumes invalidated work and schedules the next project. Qualification calls the new owner trigger-supporting; the election does not independently verify that label. |
| 051437 / 2 | export traversal retained | Agree: module propagation is a useful complement, non-module emit is less specific; the incumbent retains the explicit re-export map mechanism. |
| 051437 / 3 | emitFilesAndReportErrors retained | Agree: new createDiagnosticReporter only formats/writes already supplied diagnostics; the incumbent collects semantic diagnostics and reports them. |
| 051447 / 1 | export traversal survives merge | Agree: signature/export propagation is more issue-specific than reverse lookup, affected-queue draining or non-module rebuild scope; all remain available. |
| 051447 / 1 | verifyScenario retained | Agree: its visible edit, timeout execution and checkOutputErrorsIncremental exceed introduceError's mutation-only helper and a test-suite heading. |
| 051447 / 2 | verifyScenario retained | Agree: watch-host constructors and verifyTscWatch dispatcher provide navigation, not a stronger scenario/assertion packet. |
| 051447 / 3 | verifyScenario retained | Agree: TextStorage.edit, timeout draining and solution construction are useful helper responsibilities but not stronger than the scenario's visible edit/check sequence. |
| 051447 / 3 | getNextInvalidatedProject retained | Agree: status worker and invalidated-project interface add context, not a stronger project-processing gate. |
| 051458 / 1 | original assertProp survives merge | Agree against the new generated assertProp duplicate; formatting and entry owners remain complements. |
| 051508 / 1 | original assertProp survives merge | Agree against newly inspected generated duplicate and validateProp entry wrapper. |

### Core per-file/per-obligation election audit

This is distinct from island representative selection. The new policy executes after
qualification; file groups with a single qualified contributor elect it trivially.
Only groups acquiring another qualified competitor or changing primary are reviewed
below. Repeat unchanged votes are counted separately, not presented as independent successes.

| Run | Initial votes | Preserved votes | Replacements | Nontrivial competitions | Agree / disagree |
| --- | ---: | ---: | ---: | ---: | --- |
| 051437Z | 8 | 16 | 1 | 4 | 2 / 2 |
| 051447Z | 18 | 48 | 1 | 6 | 4 / 2 |
| 051458Z | 6 | 10 | 0 | 0 | not exercised |
| 051508Z | 6 | 15 | 0 | 2 | 2 / 0 |

| Run / round | File / obligation | Winner and review |
| --- | --- | --- |
| 051437 / 1 | builder / ordered mechanism | Export traversal retained: agree; the new export recursion and diagnostic consumer are complementary. |
| 051437 / 1 | builder / state changes | Export traversal retained: agree; directly shows the signature condition and export-map processing. |
| 051437 / 1 | tsbuildPublic / trigger | Status worker replaces build queue: disagree for the source/qualification reasons above. |
| 051437 / 2 | builderState / ordered mechanism | Reverse lookup retained over module propagation: disagree; exact anchor wins even though the new source exposes a queue, updateShapeSignature and recursive dependent propagation. |
| 051447 / 1 | builder / ordered mechanism | Export traversal retained: agree over queue consumption/diagnostics. |
| 051447 / 1 | builder / state changes | Export traversal retained: agree; complementary consumers are not removed. |
| 051447 / 1 | builderState / ordered mechanism | Reverse lookup replaces getAllDependencies: disagree; module propagation is available and more directly explains affected dependents. |
| 051447 / 1 | builderState / state changes | getAllDependencies retained: disagree; it enumerates dependency closure and its view is truncated, whereas the new module owner exposes propagation based on changed signatures. Equal support breadth falls back to recurrence/rank. |
| 051447 / 3 | tsbuildPublic / state changes | getNextInvalidatedProject retained: agree; retains status-to-build processing over status inspection alone. |
| 051447 / 3 | tsbuildPublic / subject | startWatching retained: acceptable watch entry representative; status helper is complementary, not a uniquely better subject summary. |
| 051508 / 1 | props / ordered mechanism | assertProp retained: agree over new validateProp entry wrapper. |
| 051508 / 1 | props / subject | assertProp retained: agree over the new entry wrapper; this does not settle the separate formatter-versus-validator question. |

The central problem remains observable despite the nicer island winner: a metadata
vote cannot reliably distinguish which part of a broad obligation a snippet proves.
Only two per-file replacements occurred; one is the questionable trigger replacement,
the other picks the anchored lookup over dependency enumeration while overlooking
the stronger module-propagation alternative. This is not the desired reliable
"better newly inspected owner replaces the incumbent" behavior.

## Why the 2/4 final result is not proof of election-caused loss

051437Z WatchMode: raw dense/sparse/hybrid hits 112/6/5; 34 canonical owners/ranges;
file admitted to comparison; two owners selected. Round-zero qualification defers
verifyTransitiveReferences (navigation-only, config-deletion scenario instead of the
reported interface edit) and an unresolved bad-reference-update test (insufficient,
missing assertions). This happens BEFORE the changed election stage. Neither becomes
a promoted island member; no WatchMode-rooted action executes and none reaches the
final pool. Do not attribute their initial qualification to the later priority change.

Helpers: raw dense/sparse/hybrid hits 4/0/1; four canonical observations, but its file
is outside comparison admission. No initial selection, promoted owner, later matching
action or final candidate follows. The absent WatchMode handoff removes a later route
that existed in other runs. This is an admission/qualification-to-discovery chain,
not representative replacement deleting Helpers. The unchanged dormant completion
feature remains disabled. A different controller priority could in principle affect
later recovery; this experiment does not prove that no alternative action could help.

Exact record: owner-reevaluation-variant1-loss.json. The two baseline final pools still
contain both Builder and BuilderState despite poor intermediate representatives;
the variant final pools likewise do not enforce a one-owner-per-file evidence cap.

## Decision and possible next adjustment

**Reject variant 1 and restore original ranking.** Do not add another numeric tie-breaker
to make these examples win. The unchanged baseline already reevaluates representatives;
the tested policy improves some island priorities but does not reliably choose the
better same-file owner, and end-to-end results provide no repeated improvement.
The 2/4 score is a non-regression concern, not a demonstrated causal effect of this patch.

An appropriate next experiment would first clarify qualification's distinction between
a local partial contribution and establishing an obligation, then compare newly disclosed
owners against the incumbent for that specific unresolved question using their actual
source and limitations. Preserve complementary owners, allow "no clear improvement",
and do not turn the number of obligation labels into semantic proof. Whether an existing
LLM stage can perform that bounded comparison, versus requiring another call, needs a
separate cost/contract experiment. The full historical contract and challenger-inspection
action have not been restored or tested here; this is intentionally not their acceptance.

The primary-count runtime integration was removed; the original ranking plus trace-only
instrumentation is active. Prototype, patch, fixed-input comparisons and all live traces
are preserved. 117 focused regression/audit tests pass after rollback. No new LLM prompts,
qualification fallback, indexing exclusions, limits or thesis changes were introduced.
No post-rollback full runs are claimed. The eight fresh runs used existing indexes.

## Cost and artifacts

Baseline: TS 215559 + Vue 114445 = 330004 retrieval tokens.
Variant: TS 214261 + Vue 112946 = 327207. Combined **657211**.
The election and replay consume no LLM tokens; pipeline totals reflect different actual
downstream workloads. Totals exclude request analysis, embeddings and explanation.

Artifacts under testing/codeRepoQA/incremental-restoration:
owner-reevaluation-{ts,vue}-{baseline,variant1}.json, owner-election-counterfactual.json,
owner-reevaluation-variant1-loss.json, owner-election-variant1.patch. Exact API/source
traces remain in each external testcase run folder. Audit tools are maintained under
testing/codeRepoQA; archived prototype is owner_election_variant.py and is not imported
by runtime. The patch describes the variant relative to the original checkpoint and
requires the separately preserved owner_reevaluation_audit module.
