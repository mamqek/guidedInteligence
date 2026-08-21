# Deferred final-evidence corrections: unresolved files and overlapping snippets

Status: implemented on 2026-08-18 with focused tests and provisional real-run verification. The separately deferred island-restoration review remains open.

This note records two changes identified while examining the BM25F TypeScript 35468 run `run-20260818T042025Z`:

1. preserve a strongly grounded file-level handoff when exact snippet localization remains unresolved;
2. prevent a containing owner and its nested or substantially overlapping snippet from occupying redundant final-evidence positions.

It also records a separate follow-up reminder about the existing post-rerank island-preservation invariant. That invariant is deliberately out of scope for this implementation plan: complete and assess the file-fallback and overlap changes first, then explicitly return to the restoration policy as its own decision.

## Observed failure that motivates the design

The TypeScript run formed a strong watch/build island containing:

- `src/testRunner/unittests/tsbuild/watchMode.ts`;
- `src/testRunner/unittests/tscWatch/helpers.ts`;
- `src/compiler/tsbuildPublic.ts`.

The island contained eight observations, three executed actions, five structural components, seven enclosing owners, both direct and navigation qualification support, and recurrence four. Retrieval followed an explicit bounded handoff from the selected `watchMode.ts` flow into `tscWatch/helpers.ts`, then performed a path-scoped search there.

The path-scoped search found `TscWatchCompile`, `tscWatchCompile`, and `verifyTscWatch`, but not the narrower relevant `baselineProgram` diagnostic-cache check. The final LLM reasonably rejected those three exact snippets because none proved the requested cache/path behavior. The pipeline then lost the file entirely even though its structural handoff remained credible.

The existing file-trace path did not give the LLM a chance to retain `tscWatch/helpers.ts`. Trace construction currently stops after the first two unique traces in controller action order, before snippet consolidation determines which source mechanisms are accepted. In this run the two available trace slots were consumed by `src/testRunner/unittests/tsbuild/helpers.ts` and `src/compiler/tsbuildPublic.ts`; the later `src/testRunner/unittests/tscWatch/helpers.ts` endpoint was therefore absent from the file-trace array shown to final consolidation. This is an ordering/cap failure in addition to the missing independent file-selection contract.

In the same run, final selection retained three `watchMode.ts` candidates:

- `verifyTransitiveReferences`, lines 770-1064;
- its nested `verifyScenario`, lines 876-912;
- a separate range, lines 688-716.

The first two are structurally nested and substantially redundant. They received different mechanism-role labels, but the final result did not test whether the large parent added a necessary claim beyond the child.

## Deferred follow-up reminder: existing post-rerank island invariant

The qualification-first controller introduced a rule that the final selector could not erase all context from the strongest six candidate islands. The intended purpose was diversity: preserve disconnected builder/state and watch/test hypotheses despite stochastic final selection.

The current implementation runs after LLM consolidation:

1. begin with the four controller-active islands;
2. add ranked candidate islands until six are protected;
3. determine which protected islands have no LLM-accepted candidate;
4. append one candidate from every unrepresented protected island until the evidence cap is reached.

The number six is a fixed heuristic. The original decision note and changelog describe the diversity objective and acknowledge selection inflation as a risk, but do not provide a measured derivation for six. The TypeScript run exposed two boundary problems:

- an inactive, lexical-only `server/session.ts` island became protected and was restored after the LLM rejected it;
- snippet restoration is being used where an honest file-level unresolved handoff would be the correct representation.

Do not change this invariant as part of the file-fallback and overlap implementation. After the current plan is complete, explicitly remind the user to review both questionable parts as a separate experiment or policy correction:

1. the code protects two additional inactive islands merely to increase the protected set from four to six, even when the final LLM did not select those islands;
2. the code forces one snippet from an active or additionally protected island when that island is absent from the LLM result, thereby overriding the final selector simply because the island was protected.

The follow-up should decide whether any post-selection restoration is justified at all, whether diversity belongs only in construction of the preselection pool, and whether an unresolved hypothesis should instead compete through the explicit file-level contract. Do not silently bundle that decision into the present work.

## Change 1: independent unresolved file evidence

### Intended stage boundary

Snippet selection and file-level selection are separate decisions over shared provenance:

- snippet selection asks whether particular visible lines establish a claim;
- file-level selection asks whether a repository file is a strongly grounded continuation of an accepted mechanism even though the exact supporting owner remains unresolved.

Failure to select a snippet does not itself reject the file. Conversely, a file cannot survive merely because its path or vocabulary resembles the request.

The file decision should run after snippet consolidation has identified accepted source mechanisms, but it should consume the controller's pre-consolidation handoff ledger. It must not infer connections from the surviving snippets after the fact.

Controller-time trace collection must therefore retain all bounded, deduplicated trace seeds needed for the later decision rather than selecting the first two. Apply the presentation cap only after accepted-source gating and file-level relevance ordering. The cap is a final payload budget, not a chronological admission limit.

For the motivating path, preserve the full provenance sequence rather than treating the three destination snippets as unrelated hits:

1. the selected `watchMode.ts` mechanism executes a file-seeded outgoing `calls` expansion;
2. that bounded handoff reaches `tscWatch/helpers.ts::verifyTscWatch`;
3. a path-scoped follow-up in `tscWatch/helpers.ts` retrieves `TscWatchCompile`, `tscWatchCompile`, and `verifyTscWatch`;
4. exact snippet consolidation rejects those snippets because the diagnostic-cache owner is still missing;
5. file-level selection independently retains the path as an unresolved structural participant;
6. deeper localization may later follow `tscWatchCompile -> runWatchBaseline -> watchBaseline -> baselineProgram`, but file retention must not depend on completing that chain within the controller's three-round budget.

### Proposed file-level candidate contract

Each candidate should carry at least:

- stable file-trace ID;
- destination path;
- source island ID;
- source observation and source candidate IDs;
- whether the source candidate was accepted by final snippet selection;
- executed action ID and action type;
- represented relationship kind and direction when applicable;
- source and destination symbols, if known;
- originating and unresolved obligation IDs;
- destination qualification disposition and support level;
- destination observation IDs and count;
- path-scoped follow-up attempts and their outcome;
- an explicit localization status such as `exact_owner_selected`, `qualified_owner_not_selected`, `owner_unresolved`, or `endpoint_irrelevant`;
- a bounded factual reason that never claims the unresolved file proves the behavior.

### Eligibility gates

A file can become unresolved file evidence only when all of these hold:

1. **Accepted source mechanism.** At least one source-side snippet in the handoff's island was accepted by final consolidation for the same mechanism or obligation.
2. **Executed, path-specific provenance.** The destination came from an executed bounded relationship handoff or another explicit repository-local action. Lexical similarity, a shared filename, a broad independent search, or merely sharing an obligation is insufficient.
3. **Obligation continuity.** The handoff and destination address an obligation that remains unresolved or partial after snippet consolidation.
4. **Qualified destination signal.** At least one destination observation was promoted as direct or navigation support, or multiple mutually consistent destination observations survived qualification. A final snippet omission is allowed; a qualification-level `reject/irrelevant` decision is not.
5. **Unresolved localization.** No selected snippet from that destination file already represents the same handoff adequately. File evidence is a fallback representation, not an automatic duplicate of selected code.
6. **Bounded provenance.** The trace must name the concrete source, action, destination, and missing owner. Generic graph degree or repeated lexical hits cannot satisfy this gate.

### Vetoes

Reject the file-level candidate when any of these hold:

- the source island has no final-accepted mechanism evidence;
- the only provenance is Qdrant/BM25 similarity, basename matching, or recurrence;
- the destination was explicitly qualified as unrelated;
- the relationship came from a broad independent search rather than a represented handoff;
- the trace crosses a generated, vendored, or excluded artifact boundary contrary to the index policy;
- the destination is already represented by a selected snippet or equivalent selected file trace for the same role;
- the claimed relationship cannot be reproduced from the action ledger.

### Selection policy

Do not calculate a free-form score from raw connection count. Use categorical evidence strength first:

1. accepted source + represented structural edge + obligation continuity + promoted destination;
2. accepted source + represented structural edge + obligation continuity + deferred/insufficient endpoint;
3. anything lacking an accepted source or represented edge is ineligible.

Within the same category, deterministic ordering may use:

- number of distinct qualified destination owners, capped so repeated hits cannot dominate;
- direct support before navigation support;
- whether a path-scoped follow-up was attempted;
- unresolved-obligation priority;
- stable path/trace ID for deterministic ties.

The final LLM consumer should receive file-level candidates in a separate array from snippet candidates. It must be told that selecting a file trace means “retain this structural lead,” not “these unknown lines prove the claim.” The response schema should also keep selected file traces separate from selected snippets.

### Expected TypeScript behavior

Under these gates:

- `src/testRunner/unittests/tscWatch/helpers.ts` survives as unresolved file evidence because it was reached from the accepted `watchMode.ts` mechanism through an executed bounded handoff, addresses the same ordered watch mechanism, produced three qualified observations, and still lacks the exact diagnostic-cache owner.
- `src/compiler/tsbuildPublic.ts` remains represented by its selected exact snippets; a same-role file fallback is unnecessary.
- `src/server/session.ts` is rejected because it has one lexical observation, no executed handoff, no structural provenance, and no accepted source mechanism.
- `src/testRunner/unittests/tsc/helpers.ts::BuildKind` is rejected because it has no handoff and only a generic navigation match.
- `src/testRunner/unittests/tsc/incremental.ts` is rejected because it is a standalone navigation island with no accepted source.
- the existing `src/testRunner/unittests/tsbuild/helpers.ts` trace is rejected or remains below selection because its source `tsc/incremental.ts` island was not accepted and its endpoint was deferred/insufficient.

This comparison shows that the proposed gate recovers the missing Oracle helper without admitting the observed false positives.

### Logging

Emit a decision record for every file-level candidate with:

- eligibility result;
- accepted-source check;
- provenance/action check;
- obligation-continuity check;
- destination qualification summary;
- localization status;
- duplicate-with-selected-snippet check;
- final selected/rejected result and reason.

The trace should explicitly distinguish `snippet_not_selected_file_retained` from `endpoint_irrelevant_file_rejected`.

## Change 2: containment and marginal-contribution deduplication

### Intended behavior

Multiple snippets from one file are allowed when they establish distinct, non-redundant mechanism steps. There must not be an arbitrary one-file or top-five quota.

However, a large owner and a nested child should not both survive merely because the LLM assigned them different labels. The selected set should be the smallest grounded set that preserves every supported proposition and mechanism transition.

### Candidate relationships

Before final consolidation, compute same-path relationships:

- identical stable owner or range;
- exact containment;
- parent/child structural ownership;
- substantial line overlap;
- nearby but non-overlapping ranges;
- unrelated ranges in the same file.

Record overlap characters/lines, containment direction, structural owner IDs, obligations, qualification support, and disclosed-text status. Do not infer redundancy from path identity alone.

### Safe deterministic normalization

Before the LLM call, deterministically merge or remove only representations that are provably equivalent:

- identical node IDs;
- identical ranges;
- equivalent range and structural-node representations of the same disclosed lines;
- a disclosure artifact duplicated through multiple provenance paths.

Merge their provenance and obligation associations into one canonical candidate.

Do not deterministically remove a parent merely because it contains a child: the parent may contain necessary setup. Instead, expose the containment relationship to consolidation.

### Final consolidation instruction

Require the final selector to apply marginal contribution:

- select the smallest candidate that fully supports a proposition;
- do not select both parent and child for the same proposition or mechanism role;
- retain both only when the selection record identifies the additional claim supported exclusively by each;
- allow separate, non-overlapping snippets from the same file when they prove different steps;
- treat a large containing owner as a context fallback, not an automatic companion to a focused child.

The response schema should require an `exclusive_contribution` explanation when two selected candidates overlap substantially or have a parent/child relationship. A validator must reject a response that selects both without naming distinct supported propositions. Repair should ask the same LLM stage to choose the minimal set; it must not silently select or delete semantic evidence with a deterministic surrogate.

### Expected TypeScript behavior

For `watchMode.ts`:

- lines 876-912 (`verifyScenario`) provide the focused validation behavior;
- lines 688-716 provide a separate concrete invalidation/build trigger;
- lines 770-1064 (`verifyTransitiveReferences`) contain the focused child and should survive only if the selector identifies necessary setup or another proposition not established by the child and the separate range.

The likely minimal result is the focused child plus the separate invalidation range. This is an expected diagnostic outcome, not a hardcoded testcase rule.

### Logging

For every same-file cluster, record:

- cluster ID and member IDs;
- containment and overlap relationships;
- canonicalization decisions made before the LLM;
- candidates selected by consolidation;
- exclusive contribution claimed for each overlapping selection;
- validation or repair outcome;
- final number of positions saved.

## Integration order

Implement in this order so each stage has one responsibility:

1. add overlap/containment metadata and exact-equivalence canonicalization;
2. strengthen the final-consolidation prompt/schema with minimal-set and exclusive-contribution rules;
3. validate overlapping selections without deterministic semantic fallback;
4. introduce the separate unresolved-file candidate contract and selector;
5. serialize snippet and file-level evidence as separate final evidence types;
6. add trace records and focused tests;
7. run the TypeScript case through cheap smoke diagnostics, then normal final-selection acceptance runs under the repository run policy;
8. after reporting this plan's results, remind the user about the separately deferred active/six-island post-selection restoration review.

## Focused tests

Add tests for at least:

- parent and child support the same proposition: child only;
- parent adds unique setup: parent and child allowed with explicit exclusive contributions;
- two non-overlapping snippets in one file support different mechanism steps: both allowed;
- exact range/node duplicate: canonicalized before the LLM;
- accepted source plus bounded handoff plus navigation destination: file trace eligible;
- final snippet rejection caused by insufficient localization: file trace remains eligible;
- qualification `reject/irrelevant`: file trace vetoed;
- lexical-only Session-style island: file trace ineligible;
- graph edge from an unaccepted source island: file trace ineligible;
- selected exact snippet already represents the destination: redundant file trace suppressed;
- more than two traces are discovered and the relevant trace arrives later: accepted-source gating selects the relevant later trace rather than the first two chronologically.

## Real-run evaluation

For the TypeScript run, inspect more than Oracle overlap:

- whether `tscWatch/helpers.ts` appears honestly as unresolved file evidence;
- whether the new file-level selector excludes `server/session.ts`, `BuildKind`, and unrelated incremental traces, independently of any legacy snippets still restored by the out-of-scope island invariant;
- whether the nested `watchMode.ts` candidates collapse to a minimal non-redundant set;
- whether builder, builder-state, watch validation, and project-queue mechanism steps remain represented;
- candidate counts before consolidation and after canonicalization;
- selected snippet count and selected file-trace count;
- final-selection and total retrieval tokens;
- coverage status, sufficiency, and unresolved transitions;
- every file-fallback and overlap decision record.

Acceptance requires that the new boundary preserve mechanism coverage while adding the correct unresolved file representation and removing overlapping-snippet redundancy. The separate post-selection restoration behavior must be reported transparently but is not changed or accepted by this plan. Token reduction alone is not acceptance evidence.

## 2026-08-18 implementation and verification

- Controller-time file-trace construction now retains every bounded deduplicated trace seed. The previous first-two chronological cap was removed; the two-trace cap now applies only to final selected file evidence.
- Final snippet consolidation and unresolved file selection are separate typed LLM decisions. The file stage runs only after deterministic accepted-source, destination-not-selected, endpoint-not-rejected, and unresolved-obligation gates.
- Every trace receives a `file_trace_selection_evaluated` record, including ineligible traces that never reach the focused LLM.
- Same-file containment and substantial overlap are serialized to final consolidation. Every selected snippet must state its exclusive contribution, and selecting overlapping candidates without distinct contributions fails explicitly.
- Focused verification passes 127 `unittest` cases across file traces, obligation retrieval, and qualification-first retrieval.
- TypeScript run `run-20260818T153523Z` was `partial/false`, used 25 final candidates and 68,269 calculated retrieval LLM tokens, selected 11 evidence items, and retained two implementation-Oracle files. It generated both the `tsbuildPublic.ts` and `tscWatch/helpers.ts` traces. `tsbuildPublic.ts` was correctly suppressed as redundant with selected snippets. `tscWatch/helpers.ts` passed every file-level gate but the old combined LLM decision did not select it; this run motivated the dedicated focused stage.
- TypeScript run `run-20260818T154042Z` was `partial/false`, used 24 candidates and 60,664 calculated retrieval LLM tokens, selected 11 evidence items, and retained two implementation-Oracle files. Retrieval did not rediscover the `tscWatch/helpers.ts` handoff, so no dedicated helper-file decision was possible. It did verify that unrelated tsserver traces were rejected by accepted-source and endpoint gates.
- A focused actual-LLM replay used the eligible helper trace and selected-source context produced by `run-20260818T153523Z`. The dedicated stage selected `file_trace:island_54bef7bbf4b8baf5:src/testRunner/unittests/tscWatch/helpers.ts` specifically because it preserved a distinct downstream participant while leaving the exact owner unresolved.
- Overlap behavior was directly observed. In `run-20260818T153523Z`, the 295-line `verifyTransitiveReferences` parent was rejected while nested `verifyScenario` and the separate invalidation range survived. In `run-20260818T154042Z`, `createWatchProgram` and nested `reportWatchDiagnostic` both survived with distinct recorded contributions outside and inside the child range, which is permitted by the contract.
- Retrieval variation across the two runs changed the available candidate mechanisms and Oracle overlap. This implementation is therefore verified at its intended stage boundaries but is not claimed to stabilize upstream discovery.

After reporting these results, explicitly return to the out-of-scope question recorded above: whether the four-active-plus-two-extra island protection and forced post-LLM restoration should exist at all.

## Consolidated follow-up ledger (2026-08-19)

This section is the single reminder list for the remaining related work. It separates
implemented behavior from the next bounded changes so that a future experiment does
not accidentally reintroduce or bundle them.

### Already implemented and keep under observation

| Item | Current contract | What to watch in later runs |
| --- | --- | --- |
| Contextual disclosure | Resolve the exact structural owner before rendering a qualification card; include the useful owner context rather than a comment-only fragment. | Wrong-owner boundaries, empty source, and oversized owner previews. |
| Same-owner continuation | A qualified, incomplete navigation owner can receive one deterministic later-owner view. | Whether it exposes the named missing behavior rather than merely producing another plausible excerpt. |
| Separate unresolved file evidence | A final-selected source plus an executed bounded handoff can retain an unresolved destination file independently of rejected destination snippets. | `tscWatch/helpers.ts` should remain a structural lead only when the source, handoff, obligation, and destination gates all hold. |
| Overlapping final snippets | Exact duplicates are canonicalized; overlapping parent/child snippets require distinct exclusive contributions. | Whether multiple same-file positions are genuinely separate mechanism steps. |
| Local follow-up questions | Qualification emits a source- and file-role-scoped next question, used by owner continuation and within-file search. | Test observations should request scenarios/assertions/helpers, not an entire issue-level explanation. |
| Deterministic repository context | Request analysis receives package identity, index exclusions, and exact issue-path existence checks. | Reproduction paths absent from the repository must not become local architecture or make the repository's own tool appear external. |

### Next bounded implementation: admission diversity before qualification

**Problem.** Several raw ranges from the same file can consume multiple entries in
the pre-qualification observation guardrail. In TypeScript 35468 this allowed three
`watchMode.ts` ranges to displace `builder.ts` and `builderState.ts` before the LLM
could qualify them.

**Change.** Admit one representative raw observation per path into the first
qualification set. Keep the other ranges as attached path-local alternatives, not as
independent roots or hidden evidence. The representative is the existing strongest
ranked observation. A later qualified `SearchWithinFile` action may still select a
different attached range when its local follow-up warrants it.

**Guardrails.** Do not merge unrelated owners into one semantic observation; this is
only an admission-slot policy. Preserve every excluded range in the trace with the
reason `same_path_alternative`. Do not use oracle paths or hardcoded repository names.

**Verification.** Use a focused fixture with three ranges from one test file and two
implementation files. Verify that exactly one test-file representative enters initial
qualification, both implementation candidates remain eligible, and the alternatives
can still be reached by a bounded path-local search. Then inspect TypeScript 35468
smoke traces before normal acceptance runs.

### Next bounded implementation: repeated structural file participation

**Problem.** `watchMode.ts` has 18 represented direct calls into
`tscWatch/helpers.ts` (16 `verifyTscWatch`, two `checkOutputErrorsInitial`) across
three source owners. A good WatchMode mechanism can therefore be structurally linked
to Helpers even when retrieval cannot identify Helpers' exact changed owner. The
current file-evidence contract can use this information only after a controller
file-expansion action happens to execute.

**Change.** When an exact source candidate is accepted, deterministically inspect the
already-indexed outgoing file relationships once. Create one *candidate* unresolved
file trace for a destination only when all of these are true:

1. the edge is repository-local and direct;
2. the source file is part of the accepted mechanism;
3. the same unresolved obligation continues across the edge;
4. the destination has at least three call sites or two distinct localized source
   owners (capped counts; raw graph degree is never sufficient);
5. the destination is not already represented by an accepted exact snippet and was
   not qualification-rejected as irrelevant.

This does **not** automatically select the file. It gives the existing file-level LLM
stage an honest, bounded candidate stating that the file repeatedly participates in
the accepted mechanism while its exact supporting owner remains unresolved.

**Verification.** TypeScript 35468 must produce a trace for
`tscWatch/helpers.ts` from an accepted `watchMode.ts` source, while lexical-only
`server/session.ts`, unrelated test helpers, and broad utility files remain
ineligible. Inspect the LLM decision and all deterministic gate records.

### Next bounded implementation: deduplicate repeated file expansions

**Problem.** The controller generated the identical `watchMode.ts` file-level
outgoing-calls expansion once for each of five unresolved obligations. These are not
five independent actions, but their recurrence is meaningful evidence that the
structural expansion could address several unresolved needs.

**Change.** Canonicalize identical file/direction/relationship expansions into one
action with a stable action ID and the union of its obligation IDs. Record
`obligation_recurrence` and the concrete obligations in the trace. This recurrence
becomes a bounded action-strength signal for the later scheduler review; it must not
by itself force execution or create additional action slots.

**Verification.** A fixture with one file/action repeated across five obligations
emits one executable expansion, retains all five obligation IDs, and reports
recurrence five. Different direction, relationship kind, or path must remain a
separate action.

### Explicitly deferred: scheduler preference redesign

Do **not** implement this together with the three bounded changes above.

The current scheduler gives owner continuation priority in early rounds and only
prefers file-level relationship expansion after round two. TypeScript 35468 can stop
after round one, so an already-ready WatchMode-to-Helpers expansion may never run.
The broader preference system—including action-type ordering, round-sensitive
priority, isolated pools, and how repeated obligation recurrence should influence
selection—needs a separate design and experiment. It must compare noise, token use,
and missed structural handoffs across multiple cases rather than being tuned to
Helpers alone.

After the three bounded changes are implemented and measured, explicitly remind the
user to review this scheduler-preference redesign together with the already-deferred
four-active-plus-two-extra island restoration policy.
