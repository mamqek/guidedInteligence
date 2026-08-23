# Temporary Plan: Source Visibility Guard and Agent-Selected Inspection

## Status

- Planning document only. Do not implement from this file without a separately authorized experiment.
- Branch runtime remains the restored native workspace controller.
- Primary measured case: `pandas-dev-pandas-10068`.
- Related rejected experiment: [`decisions/agent-planned-native-controller.md`](decisions/agent-planned-native-controller.md).
- Execution policy: [`incremental-experiment-execution-protocol.md`](incremental-experiment-execution-protocol.md).

## Goal

Let an action-planning model distinguish between:

1. source that was actually shown and appears irrelevant; and
2. a promising source handle whose relevant owner was not fully shown.

Then let it select a bounded existing inspection/search action to obtain a better source view before semantic evidence
admission becomes irreversible.

This is not a proposal to restore the rejected controller that jointly classified evidence, judged coverage, selected
actions, and stopped retrieval. The proposed agent control is narrower: choose native actions using explicit source
visibility information. Native source resolution, qualification, coverage representation, action execution, grounding,
islands, and final consolidation remain distinct stages.

## Concrete Failure Being Addressed

Both valid agent-planned pandas runs retained exact `Series::_binop` as `obs_7fcee82d964fc060` through raw Qdrant
dense/sparse retrieval, file grouping and held alternatives, CodeGraph owner resolution, initial owner comparison, and
initial controller admission.

The disclosure system initially constructed a 1,700-character class-skeleton/member view for the 46-line `_binop`
owner. The global planner payload then water-filled all pending cards into one request:

- `run-20260823T183021Z`: `_binop` reached round 0 with 598 characters;
- `run-20260823T183349Z`: `_binop` reached round 0 with 371 characters.

Neither rendered view contained alignment, `_maybe_match_name`, or result construction. Run `183021` deferred the
observation as navigation-only. When it was eventually inspected, it again received only 439 characters and was
deferred again. Run `183349` optimistically promoted the short preview, immediately inspected it, then received the
complete 1,700-character view in round 1; that view contained alignment and `_maybe_match_name`, and final selection
retained `_binop`.

The failure was not absence from Qdrant and not failure to resolve the CodeGraph owner. It was loss of the distinction
between **owner available** and **owner actually rendered after global source fitting**.

## Correction: Do Not Add Four Semantic States

The earlier `complete / partial / preview / unresolved` table mixed two existing concerns:

- `DisclosureCard.mode` already describes how source was rendered (`full`, `preview`, or `fold`);
- `QualificationDecision` already describes the semantic decision (`promote`, `defer`, or `reject`, with direct,
  navigation, or insufficient support).

Adding another semantic state machine would duplicate both. `needs_inspection` is not an existing state and should not
be added.

The implementation needs one orthogonal, deterministic fact:

```python
owner_source_complete: bool
```

Supporting telemetry may include:

```python
owner_source_chars: int
rendered_source_chars: int
```

`owner_source_complete` means the complete smallest structurally resolved owner is present in the exact text sent to
the decision model. It says nothing about relevance or evidence quality.

This deliberately collapses the proposed `partial` and `preview` distinction. In current code, `preview` is a rendering
strategy, not a reliable completeness judgment:

- a class-member skeleton can be `mode="preview"` while containing the complete nested member;
- a large owner can be `mode="preview"` while containing only its signature and hit-local lines;
- a card initially containing a complete member can be truncated later by `fit_cards_to_source_capacity`.

The behavioral distinction comes only from `owner_source_complete`:

- `true`: a negative semantic judgment applies to the complete resolved owner;
- `false`: a negative judgment applies only to the rendered view; the stable handle remains eligible for inspection.

No new qualification enum is required. Existing `defer_navigation`, `defer_insufficient`,
`InspectDeferredObservation`, and `InspectOwnerContinuation` remain the vocabulary.

## How Completeness Can Be Computed

### At deterministic disclosure

`source_disclosure.disclose_observations` already has:

- the resolved owner range;
- `complete_source_text`;
- the initially rendered `preview_source_text`;
- the 80-line and 4,000-character limits.

For the first experiment, an owner is eligible to be marked complete only when:

1. repository source was available;
2. CodeGraph or deterministic outline resolution identified a smallest owner;
3. the owner has at most 80 lines;
4. its complete text has at most 4,000 characters; and
5. the initially rendered card contains that complete owner.

Large owners remain incomplete in this experiment even if the hit-local excerpt is excellent. General page coverage for
large owners is a separate problem.

### After global source fitting

`fit_cards_to_source_capacity` must set `owner_source_complete=False` whenever it truncates a card that was initially
complete. The final value must describe the payload card, not the pre-budget card recorded by disclosure tracing.

For nested members, comparing only character counts is unsafe because the rendered text can contain an outer-class
header and omission marker. The conservative implementation is:

- disclosure records whether the complete owner is contained in the prepared view;
- fitting preserves `true` only when that prepared view is not truncated;
- any truncation changes the value to `false`.

This is intentionally conservative and deterministic.

## Existing Data Structures to Change

### `DisclosureCard`

File: `workspace/pipeline/execution_flow/source_disclosure.py`

Add only:

```python
owner_source_complete: bool = False
owner_source_chars: int = 0
```

`rendered_source_chars` does not need storage because `len(source_text)` is authoritative. Include the two new fields in
`to_dict()` and qualification payloads.

Do not add completeness to `DiscoveryObservation`. Completeness belongs to one rendered view and may change between
rounds while the stable observation handle remains identical.

### `QualificationDecision`

No field or enum change in the first variant. Its decision continues to describe visible support. Prompt wording should
say that `reject_insufficient` over an incomplete view does not retire the underlying handle.

### Retrieval actions

No new action class. Reuse:

- `InspectDeferredObservation` for a complete small-owner redisclosure;
- `InspectOwnerContinuation` for a later bounded portion of a large owner;
- existing relationship and Qdrant actions for neighbours and repository-wide search.

Calling the action `open_full_owner` in prose is acceptable, but implementing another action with the same executor
would be unnecessary duplication.

## Handle Lifecycle Versus Semantic Qualification

Current code effectively lets a qualification disposition influence whether an observation can become a candidate,
root, or scheduled inspection. The revised invariant is:

```text
qualification judges the rendered source
visibility controls whether the underlying handle may be retired
```

Therefore:

- promoted visible evidence behaves normally;
- a deferred incomplete handle remains inspectable;
- a rejected complete handle may be retired normally;
- a rejected incomplete handle produces no evidence candidate, but remains in the compact actionable catalogue;
- final evidence still requires normal qualification after a better view is obtained.

This avoids silently changing an LLM rejection into a deterministic promotion. It also avoids treating metadata as
evidence.

The qualification validator should not rewrite decisions. Silent rewriting would violate the repository's explicit LLM
failure policy and would hide model behavior. The trace must record both the semantic decision and the independent
completeness value.

## Why the Agent Would Request a Better View

The action planner should not receive twenty competing source bodies. It should receive a compact catalogue entry for
every actionable incomplete handle:

```json
{
  "observation_id": "obs_...",
  "path": "pandas/core/series.py",
  "symbol": "Series::_binop",
  "owner_line_count": 46,
  "owner_source_chars": 1700,
  "rendered_source_chars": 598,
  "owner_source_complete": false,
  "exact_anchor_matches": ["Series"],
  "obligation_ids": ["explain_ordered_mechanism", "explain_state_changes"],
  "best_rank": 3,
  "channels": 2,
  "semantic_decision": "defer/navigation_only",
  "local_follow_up": "inspect alignment and result metadata"
}
```

This entry gives the planner an explicit value-of-information comparison:

- how relevant the handle appears;
- which unresolved obligations it could address;
- how much source is missing;
- whether a complete view is cheap;
- what prior qualification or action observed.

The planner is not guaranteed to select the correct owner. No prompt can guarantee that. The measurable hypothesis is
that separating visibility from relevance makes selection more stable than asking one call to infer both from an
unknown amount of source.

## Guaranteed Source for an Explicit Inspection

Selecting an inspection must materially change the next view. The failed controller violated this: an explicit `_binop`
inspection later returned another 439-character card.

Extend `fit_cards_to_source_capacity` with a parameter such as:

```python
reserved_card_ids: Sequence[str] = ()
```

Allocation order:

1. compute the existing fixed prompt/schema/metadata cost;
2. for at most two explicitly inspected small owners, render `complete_source_text` as owner-only source rather than
   reusing a class-skeleton preview; outer context remains available through existing owner/file metadata;
3. reserve those owner-only views, each still capped at 4,000 characters and 80 lines;
4. fail explicitly if the configured request cannot hold the reservation;
5. water-fill only the remaining source capacity across non-reserved cards;
6. record requested, reserved, rendered, and complete IDs in the trace.

The controller already knows which observations came from `InspectDeferredObservation` or `InspectOwnerContinuation`,
so it can pass reserved IDs into qualification without adding persistent state or another enum.

This adds no model call and no extra repository read: `complete_source_text` is already materialized by disclosure. It
redistributes the existing input budget toward a model-selected view.

## Proposed Agent Boundary

Do not restore the rejected one-call joint qualification/coverage/action controller. The model should not again control
irreversible qualification and action scheduling in the same response.

The most plausible no-extra-call design is to extend the existing coverage call so it also selects the next typed
actions:

```text
deterministic disclosure
→ existing qualification call over exact rendered views
→ coverage + bounded action-planning call
→ existing typed action validation/execution
→ reserved disclosure for explicit inspections
→ repeat
→ native final selection
```

The coverage/action call receives:

- promoted grounded candidate summaries;
- current obligation coverage input;
- compact incomplete-handle catalogue;
- prior attempted action effects and bounded outcomes;
- remaining round/action budget.

It returns:

- the existing complete `ObligationCoverage` records;
- zero to two proposals using existing action types;
- a stop reason only when required coverage is complete or no executable information-gain action remains.

This replaces deterministic `enumerate_actions` plus `schedule_round_actions`; it does not add a third model call to a
native round. Typed validation continues to derive paths, node IDs, ranges, limits, and duplicate effects from known
state.

### Feasibility warning

This combined payload may not fit the existing 40,000-character coverage budget. The rejected planner measured 36,836
fixed characters for 76 known observations and 21 cards before source compaction. A coverage request also contains
direct-evidence source. Therefore, the first work item for this agent boundary is a replay-only serialization audit.

If the fixed compact catalogue plus unchanged coverage payload exceeds 40,000 characters, do not silently raise the
budget and do not immediately add another call. The choice must be explicit:

1. accept an additional action-planning call and measure its token cost; or
2. abandon agent scheduling and keep only the deterministic visibility/reservation fixes.

The second option is the recommended fallback because the visibility bug is independently real and cheaper to repair.

## Round Semantics

The rejected controller executed actions in its final planner round, leaving no later call to interpret new results.
The revised loop must use one of these explicit semantics:

- rounds 1 through `N-1` may select actions; round `N` is classification/coverage/finalization only; or
- allow `N` action rounds plus one separately budgeted finalization call.

The first option adds no call but reduces exploration. Use it for the initial experiment. Returning actions in the last
round must be schema-invalid.

## Incremental Implementation Plan

### Step 1 — Visibility telemetry only

Boundary: `source_disclosure.py` and qualification serialization/tracing.

Change:

- add `owner_source_complete` and `owner_source_chars` to `DisclosureCard`;
- compute them before and after fitting;
- trace post-fit visibility, not only the larger pre-fit disclosure card.

Unchanged:

- qualification prompt and decisions;
- controller actions and scheduling;
- candidates, coverage, and final selection.

Verification:

- nested `_binop`-style member is complete before fitting;
- fitting to 598 or 371 characters marks it incomplete;
- fitting the complete 1,700-character card preserves complete;
- large owner and unavailable source remain incomplete;
- repeat deterministic fixtures twice.

Cost: trivial runtime and payload overhead; two scalars per card.

### Step 2 — Explicit-inspection reservation

Boundary: source fitting plus the controller's call to qualification.

Change:

- pass IDs produced by explicit inspection actions as reserved cards;
- guarantee complete rendering for at most two small owners;
- fail when the configured budget cannot satisfy the reservation;
- make action eligibility check fitted-card completeness rather than comparing only observation ranges and
  `disclosure_status`.

Unchanged:

- native action catalogue and scheduler choose the action;
- qualification semantics;
- coverage and final selection.

Verification:

- an observation whose handle already spans the full owner but whose payload was truncated still receives an
  inspection action;
- that action's next qualification payload contains the complete owner;
- `_binop` replay obtains 1,700 characters in two unchanged runs;
- non-reserved cards remain bounded and no total request exceeds 40,000 characters.

Cost: no new LLM call; up to 8,000 source characters reserved from the existing qualification budget. Other cards may
receive less source, so candidate diversity is a regression risk that must be measured.

### Step 3 — Incomplete-handle lifecycle

Boundary: action catalogue eligibility and trace state.

Change:

- keep rejected/deferred incomplete handles in a compact actionable catalogue;
- allow them to be inspected but not used as evidence or graph roots;
- retire normally after a complete-owner negative judgment or exhausted bounded inspection.

Unchanged:

- no deterministic promotion;
- no new qualification classification;
- native candidate construction and final selection.

Verification:

- incomplete rejected comment/signature remains inspectable;
- complete rejected irrelevant helper does not regain actions;
- an incomplete handle cannot become evidence without later normal promotion;
- repeated inspection effects remain capped.

Cost: modest state/candidate bookkeeping; potential action-pool growth. Limit actionable incomplete handles using the
existing admitted/deferred pool and global action budget, not repository-specific rules.

### Step 4 — Coverage-owned agent action selection

Boundary: coverage payload/schema and controller orchestration.

Attempt 1 must begin with saved-artifact serialization only.

Change:

- add the compact actionable catalogue and prior outcomes to the existing coverage request;
- extend its response with at most two existing typed actions;
- replace action enumeration/scheduling only after the payload and model contract pass twice;
- disallow actions in the finalization round.

Unchanged:

- qualification remains a separate call;
- native typed executors, grounding, islands, and final selector remain;
- Qdrant results remain hints rather than a closed candidate set because repository search and graph expansion stay
  available actions.

Verification:

- saved pandas state selects inspection of the incomplete `_binop` handle twice without an Oracle-specific rule;
- an irrelevant short comment/signature can be left parked without inspection;
- invented IDs and source-bound actions without handles fail validation;
- empty action outcomes affect the next selection;
- qualification and coverage token counts remain measurable separately.

Cost: medium-to-high implementation complexity and likely 5,000–20,000 additional serialized characters in the coverage
request. It may be impossible under the unchanged 40,000-character cap. Do not proceed to live integration until the
replay proves it fits.

### Step 5 — Actual-pipeline comparison

- Use the same pandas snapshot, model, index, initial-owner prompt, qualification prompt, and final selector as the
  native baseline.
- Diagnostic smoke may skip final selection, but acceptance requires two actual runs with response generation skipped
  and final selection enabled.
- Audit `_binop` through raw retrieval, grouping/held alternatives, CodeGraph, owner comparison, fitted visibility,
  qualification, selected/executed inspection, complete redisclosure, candidate pool, and final selection.
- Add one irrelevant-comment/signature regression case so the agent is not accepted merely for opening every handle.

Acceptance requires:

1. explicitly inspected small owners are completely rendered in both repeats;
2. no incomplete negative decision permanently removes a handle before its bounded inspection opportunity;
3. the agent does not inspect every incomplete handle;
4. `_binop` reaches the final pool in both pandas repeats when present upstream;
5. final quality does not regress from the unchanged native baseline;
6. total retrieval tokens do not increase without a repeatable evidence-quality gain.

## Cost and Complexity Assessment

| Proposal | Feasibility | Cost / overhead | Recommendation |
|---|---|---|---|
| Two completeness scalars on `DisclosureCard` | straightforward | negligible | implement first |
| Post-fit completeness tracing | straightforward | negligible | implement first |
| Reserved full view for up to two small owners | straightforward | redistributes up to 8k chars, no call | strong candidate |
| Reuse existing inspect actions | already supported | small controller plumbing | do this; no new action enum |
| Keep incomplete rejected handles actionable | feasible | larger action catalogue, lifecycle tests | isolate as its own step |
| Combine action choice with coverage call | feasible in code, payload fit unknown | medium/high; schema and prompt grow | replay before implementation |
| Separate action-planner call | feasible | substantial token/API overhead | do not default to this |
| Full source for every initial owner | technically possible | 16–24 owners can require 64k–96k source | reject |
| Complete arbitrary large owners under 4k | impossible | information does not fit | use bounded pages later |
| Exact unseen-line accounting with current strings | not reliable | needs structured rendered ranges | exclude from first variant |
| Guarantee the agent chooses the correct owner | impossible probabilistically | requires deterministic policy or repeated calls | measure stability instead |

## Known Overcomplication Traps

- Do not create `complete`, `partial`, `preview`, `unresolved`, and `needs_inspection` as a second semantic state machine.
- Do not add `OpenFullOwner` beside an executor-equivalent `InspectDeferredObservation`.
- Do not silently rewrite LLM rejections into promotions.
- Do not serialize full source for every dormant/deferred handle.
- Do not add a separate model call before and after each action.
- Do not reserve source based on pandas symbols, Oracle files, or testcase-specific ranks.
- Do not claim that a complete owner is available for functions larger than the established line/character caps.

## Result Ledger

| Step | Attempt | Focused run 1 | Focused run 2 | Cost change | Decision | Remaining issue |
|---|---:|---|---|---|---|---|
| Visibility telemetry | 1 | pending | pending | pending | pending | deterministic contract only |
| Inspection reservation | 1 | pending | pending | pending | pending | diversity under redistributed source |
| Incomplete-handle lifecycle | 1 | pending | pending | pending | pending | bounded catalogue growth |
| Coverage-owned action selection | 1 | pending | pending | pending | pending | 40k payload feasibility |
| Actual integration | 1 | n/a | n/a | pending | pending | two valid final-selection runs |

## Recommendation

Authorize Steps 1 and 2 as a deterministic source-integrity experiment before restoring any agentic scheduling. They
directly repair the observed fact that an explicit inspection could still return a shorter incomplete view, and they do
so without another LLM call or new semantic states.

Proceed to Step 3 only if the reserved view is repeatably complete and does not materially starve other cards. Attempt
Step 4 only if a saved real payload proves that coverage plus the compact action catalogue fits the unchanged budget.
If it does not fit, retain the visibility/reservation improvements and do not recreate the rejected high-cost agent
loop merely to preserve the agentic label.
