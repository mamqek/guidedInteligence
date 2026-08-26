# Plan: LLM-Guided Incomplete-Source Inspection

## Status

- Rejected experiment; all runtime, prompt-schema, and focused-fixture changes from this attempt are reverted.
- The semantic replay succeeded, but the real controller produced zero eligible incomplete small-owner handles in
  Pandas and Vue. The experiment therefore had no natural action to execute and could not satisfy its live acceptance
  criterion. Four final-selection acceptance runs were intentionally not spent on a demonstrated no-op.
- Historical measurements and rejected variants remain recorded in
  [`decisions/controller-uncovered-source-and-visibility-experiment.md`](decisions/controller-uncovered-source-and-visibility-experiment.md)
  and [`retrieval-changelog.md`](retrieval-changelog.md).
- This plan does not change initial retrieval, prequalification, owner comparison, or round-zero selection.
- Primary replay and acceptance case: `pandas-dev-pandas-10068`; cross-repository case: `vuejs-vue-10803`.
- Follow [`incremental-experiment-execution-protocol.md`](incremental-experiment-execution-protocol.md).

## Experiment outcome — 2026-08-26

- Clean-baseline audit: the retained Pandas runs already showed `Series::_binop` completely (46 lines, 1,700 fitted
  characters). The only relevant incomplete Pandas owner found in saved traces was `_create_methods` at 90 lines,
  outside the experiment's 80-line boundary. Saved Vue incomplete small owners were generated-bundle noise.
- Payload audit: deterministic 1-, 8-, and 24-handle requests measured 24,015, 28,173, and 37,762 total characters,
  respectively, including prompt, schema, metadata, and direct evidence. All fit the unchanged 40,000-character
  ceiling.
- Source-backed Pandas replay: two real qualification-plus-coverage repeats selected the incomplete
  `Series::_binop` owner and the issue-relevant arithmetic-name test, never the unrelated pickle-name test. A second
  coverage call supplied completed outcomes and proposed neither action again. Replay totals were 8,580 and 8,438
  LLM tokens across qualification, initial coverage/action selection, and outcome-aware follow-up coverage.
- Real Pandas diagnostic `run-20260826T055210Z`: every coverage call contained zero eligible handles. `_binop` and
  the nested Index numeric owner were already complete. The run stopped after three controller rounds with
  `no_evidence_gain`; the experiment executed no action.
- A second Pandas diagnostic `run-20260826T055501Z` again recorded zero handles in rounds 0 and 1, then failed the
  unchanged qualification validator because an LLM promotion lacked visible support. It is not a valid acceptance
  run, but it confirms no activation before that unrelated failure.
- Real Vue diagnostic `run-20260826T055743Z`: rounds 0–3 each contained zero eligible handles, no action proposal,
  and no execution. It stopped at the ordinary three-round budget.
- Decision: reject and revert. Small structurally resolved owners are already disclosed completely by the existing
  source-card policy, while incomplete owners encountered in the measured runs exceed the experiment's bound. The
  source-backed counterfactual proves the proposed decision contract can work, but not that the live pipeline needs
  or benefits from it. A future retry requires a naturally occurring, semantically promising incomplete bounded
  owner or a deliberately broader large-owner paging hypothesis with its own risk and budget analysis.

## Central hypothesis

The experiment is not “show every incomplete owner completely” and it is not “preserve every uncovered range.” Its
central hypothesis is:

> An LLM can use semantic relevance together with an explicit source-completeness fact to distinguish a promising but
> incompletely shown owner from a sufficiently shown irrelevant owner, and can request a bounded existing inspection
> action only for the former.

The complete behavioral unit is therefore:

```text
visible snippet + semantic qualification
        ↓
compact incomplete-handle catalogue
        ↓
coverage/action LLM chooses zero to two existing typed actions
        ↓
typed validation + novelty suppression before slot allocation
        ↓
selected inspection materially expands the source view
        ↓
ordinary qualification judges the expanded source
```

No individual plumbing step is a retrieval-quality success by itself. In particular, source reservation is not an
independent policy and must not be tested as though deterministic scheduling had already selected the right owner.

## Clean baseline

The experiment starts from the current controller with:

- ordinary qualification and coverage calls;
- deterministic typed action construction and execution;
- run-local structural-request memoization;
- pre-slot action-novelty suppression;
- raw-source/materialized-snippet/loss telemetry;
- existing deferred, dormant, rejected, and promoted lifecycle behavior.

The reverted experiment leaves no `owner_source_complete` runtime field, uncovered-residual candidate, forced source
reservation, or rejected-owner re-entry rule. Those pieces will be introduced only inside the integrated experiment
below.

## Non-goals

- Do not materialize uncovered range fragments as canonical snippets.
- Do not alter Qdrant retrieval, CodeGraph resolution, initial canonicalization, file admission, owner comparison, or
  round-zero qualification input.
- Do not automatically inspect every incomplete handle.
- Do not deterministically override promote/defer/reject decisions.
- Do not restore the rejected monolithic controller that jointly qualified evidence, judged coverage, and executed
  arbitrary actions.
- Do not add repository-specific symbols, paths, or Oracle-derived rules.
- Do not add unbounded large-owner paging.

## Source-completeness fact

For each post-fit disclosure card, derive a non-semantic fact:

```text
owner_source_complete = true
```

only when the exact source sent to qualification contains the complete smallest resolved owner. It is false for
unresolved ranges, folds, unavailable source, bounded previews, and post-fit truncation.

The fact must be computed from the exact fitted payload, not from the larger source available before fitting. It does
not mean relevant, sufficient, or promotable.

The ordinary qualification model continues to judge only what its visible source establishes. The coverage/action
model receives the completeness fact alongside that judgment and decides whether more source has enough expected
value to inspect.

## Compact actionable catalogue

The coverage/action request receives one compact entry for each currently actionable incomplete handle:

```json
{
  "observation_id": "obs_...",
  "path": "pandas/core/series.py",
  "symbol": "Series::_binop",
  "owner_line_count": 46,
  "owner_source_chars": 1700,
  "rendered_source_chars": 598,
  "owner_source_complete": false,
  "semantic_disposition": "defer",
  "support_level": "navigation_only",
  "visible_support": ["generic binary operation is visible"],
  "missing_information": ["result-name handoff is outside the rendered view"],
  "local_follow_up": "inspect alignment and result metadata",
  "obligation_ids": ["explain_ordered_mechanism", "explain_state_changes"],
  "retrieval_rank": 3,
  "retrieval_channels": ["dense", "sparse"],
  "prior_action_outcomes": []
}
```

Eligibility is deterministic and bounded:

- structurally resolved stable handle;
- incomplete exact rendered owner view;
- still relevant to at least one unresolved obligation;
- complete owner is within the existing small-owner limit of 80 lines and 4,000 characters;
- no prior complete inspection or novelty-equivalent exhausted action.

Rejected and deferred handles can appear in the catalogue, but neither becomes evidence or a graph root merely by
appearing there.

## Coverage-owned action decision

Extend the existing coverage call so it may propose zero to two existing typed actions. This replaces the native
semantic choice of which catalogue entries to inspect; it does not bypass native mechanics.

The response contains:

- the existing complete obligation-coverage records;
- zero to two action proposals using existing action types and known IDs;
- a grounded expected-information-gain reason tied to an unresolved obligation;
- a stop reason only when coverage is complete or no executable information-gain action remains.

The model is explicitly asked to distinguish:

- promising but incomplete: visible code and qualification follow-up point toward a missing local mechanism;
- sufficiently shown and irrelevant: additional owner lines are unlikely to address an unresolved obligation;
- incomplete but weak/noisy: low-value test, catalogue, generated, benchmark, or unrelated subsystem evidence;
- already exhausted: the same semantic effect was previously attempted or completely inspected.

The last action-selecting round must be followed by a qualification/coverage round that can interpret its result.
Actions are invalid in the finalization-only round.

## Mandatory execution path

Model proposals are candidates, not queued actions.

1. Resolve each proposal against existing observation IDs, handles, paths, ranges, and action constructors.
2. Reject invented IDs, unavailable owners, invalid scopes, or unsupported action types.
3. Pass proposals through the existing structured action-novelty/subsumption validator before allocating round slots.
4. Suppressed duplicate or subsumed effects consume no slot; a later novel proposal may backfill the vacancy.
5. Execute through the existing scheduler/executor accounting and normal trace logging.
6. Route repeat deterministic structural requests through the run-local memoization layer.
7. Return every suppression result, covering prior effect, and executed outcome in the next coverage/action context.

The agent must not bypass typed validation, novelty checks, scheduler/executor accounting, grounding, or tracing.

## Meaningful inspection contract

When—and only when—the coverage/action LLM selects a valid incomplete small owner for inspection, its next
qualification must receive the complete owner-only source, bounded by 80 lines and 4,000 characters.

This source allocation is part of the integrated semantic experiment, not a standalone deterministic reservation
policy. It is evaluated together with whether the model selected the right owner.

- At most two selected owner views can be guaranteed in one round.
- The complete request must remain within the existing 40,000-character qualification limit.
- If metadata plus selected complete views cannot fit, fail explicitly before the LLM call.
- Nonselected cards use the ordinary fitting policy.
- Large owners remain bounded and are excluded from this first experiment.
- The expanded observation undergoes ordinary qualification; inspection never promotes it automatically.

## Incremental experiment sequence

### Step 0 — Baseline restoration and contract audit

- Confirm no runtime visibility, residual-materialization, reservation, or rejected-owner re-entry behavior remains.
- Retain historical results rather than deleting them.
- Run the focused controller, qualification, novelty, and CodeGraph suites.

Acceptance: current behavior and tests are restored without touching independently accepted controller experiments.

### Step 1 — Saved-artifact payload audit

- Build the exact compact catalogue from saved Pandas traces without changing live runtime behavior.
- Add it to the existing coverage payload and measure fixed characters, catalogue characters, schema characters, and
  total input under the unchanged 40,000-character limit.
- Test small, medium, and worst observed controller states.

Acceptance: two deterministic serializations fit. If they do not fit, stop and choose explicitly between a separate
action-planning call or abandoning model-selected inspection; do not silently raise the budget.

### Step 2 — Replay-only LLM action selection

- Extend the coverage response schema with zero to two typed proposals.
- Replay saved states through the real configured LLM without executing actions.
- Required Pandas contrast: incomplete relevant `Series::_binop` versus complete/weak test and unrelated owners.
- Repeat each saved state twice.

Acceptance: the model selects a relevant incomplete implementation owner in both repeats, does not repeatedly select
complete or exhausted work, and does not prefer weak test/benchmark material merely because it is incomplete.

If this fails, record exact prompts/responses and revert the schema/prompt attempt before trying at most two revised
variants.

### Step 3 — Validation and suppression integration

- Convert replay proposals through existing typed constructors.
- Apply structured novelty/subsumption before round-slot allocation.
- Feed suppressed and executed outcomes into the next saved coverage/action context.
- Do not execute repository tools yet.

Acceptance: invented and duplicate proposals are rejected; suppressed actions consume no slots; the next replay does
not propose the same covered effect; every decision is traceable.

### Step 4 — Live integrated inspection

- Enable coverage-owned proposal selection in the controller.
- Execute only validated novel actions.
- Guarantee complete small-owner source only for the LLM-selected inspection.
- Requalify the expanded source normally.

Acceptance: two Pandas diagnostics select and completely disclose a relevant implementation owner, qualification
changes are grounded in newly visible lines, no test/benchmark owner displaces the mechanism merely because it was
inspected, and no action/result disappears from lifecycle accounting.

### Step 5 — Actual-pipeline acceptance

- Two Pandas and two Vue actual-pipeline runs.
- Keep final evidence selection enabled and skip explanation generation.
- Keep model, prompts outside this experiment, index, snapshot, and unrelated retrieval settings fixed.

Record for every run:

- catalogue entries and exact completeness facts;
- model-proposed, validation-rejected, novelty-suppressed, and executed actions;
- round slots before and after suppression/backfill;
- source characters before/after the selected inspection;
- qualification decision before/after inspection;
- candidates and final evidence first affected by the action;
- implementation/test/generated/benchmark file roles;
- `coverage_status`, `sufficient`, Oracle positions, and total retrieval tokens.

Acceptance requires repeatable mechanism improvement or a clear downstream handoff improvement without unstable
Oracle retention. Token reduction alone is not acceptance. If two actual runs regress or remain unstable because of
the new action choices, revert the integrated behavior and preserve the traces as a rejected experiment.

## Budget

- Existing qualification ceiling: 40,000 characters per call.
- Preferred whole-run retrieval target: at most 100,000 reported LLM tokens.
- Do not start optional action work after 125,000 reported tokens.
- Absolute experiment ceiling: 150,000 retrieval tokens, enforced conservatively before another optional call.
- The intended coverage/action integration replaces deterministic action choice; it must not add an unbounded third
  model call per round.

## Success criterion

Success is not that `owner_source_complete` exists or that an inspection contains more characters. Success requires
the LLM to use completeness and semantic evidence together to choose a useful inspection, reveal previously hidden
mechanism source, and improve the resulting evidence chain without systematically promoting noise.
