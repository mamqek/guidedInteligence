# Initial Admission Compatibility And Empty-Action Backfill Experiment

Date: 2026-08-30

## Scope

This record contains two independently testable changes. They share an evaluation case but do not depend on each
other and must remain independently reversible.

## Step A — Empty Ordinary-Action Backfill

### Observed problem

TypeScript 35468 run `run-20260830T001311Z` selected a file-seeded `ExpandRelationship` rooted at
`src/compiler/sys.ts` as one of the two ordinary round-one actions. Execution returned zero edges, zero endpoint
observations, and zero materialized snippets. The action made no dedicated LLM request, but the scheduler did not
replace it, so it consumed half of the round's ordinary useful-work allowance.

### Baseline and boundary

- Boundary: controller scheduling/execution inside one round.
- Unchanged: catalogue construction, action ranking, action-effect novelty, auxiliary action pools, qualification,
  coverage, round count, graph request limits, and final selection.
- Existing zero-result actions remain recorded as attempted so the same effect cannot execute repeatedly.

### Proposed behavior

After the initially scheduled actions execute, count only ordinary actions that produce a materialized observation,
edge, or new raw source toward `max_controller_actions_per_round`. For every empty ordinary execution, select the next
eligible ordinary action from the already-built catalogue, excluding attempted IDs/effects and respecting existing
island, root, path, pending-handoff, and novelty rules. Execute at most one replacement per empty ordinary slot, so a
round cannot become an unbounded scan of empty actions.

### Expected effects and risks

- Quality: recover useful work from slots otherwise lost to empty structural neighborhoods.
- Tokens: no new LLM call; later qualification/coverage payloads may grow only when a replacement produces evidence.
- Runtime/tool calls: at most `max_controller_actions_per_round` additional empty attempts in a round.
- Candidate volume: unchanged when every replacement is empty; bounded increase when a replacement succeeds.
- Risks: violating distinct-island scheduling, accidentally executing an auxiliary action as a replacement, or
  retrying an equivalent failed effect.

### Verification

- Focused deterministic test: first ordinary action returns empty; the next eligible action executes in the same
  round; the failed effect is attempted; two productive ordinary actions remain possible.
- Negative tests: a productive action is not backfilled, replacement remains ordinary, and repeated empty candidates
  cannot exceed the configured bounded attempt count.
- Actual pipeline: TypeScript 35468 trace must show explicit empty-action/backfill telemetry if an empty ordinary
  action naturally occurs. Absence of that condition is reported as unexercised, not success.

## Step B — Explicit Legacy Observation-Guardrail Initial Mode

### Observed problem

August 15 run `run-20260815T183615Z`, on commit `45a473ed30794e5e6f500c2d4338a7956e4352dd`, aggregated raw
retrieval observations directly to the configured 24-observation guardrail and sent all 24 to round-zero
qualification. Current runs first canonicalize hundreds of
observations, serialize 68–72 snippets into an owner-comparison request, spend about 17K tokens on that request, and
select 9–13 observations for qualification. On TypeScript 35468 both paths initially represented Builder,
BuilderState, and WatchMode; neither initially represented Helpers.

### Baseline and boundary

- Current default remains `semantic_owner_comparison` byte-for-byte at the branch point.
- New opt-in testing mode is `legacy_observation_guardrail`.
- Boundary: initial admission after current raw dense/sparse/exact retrieval and structural observation creation,
  before round-zero disclosure and qualification.
- The mode reproduces the August 15 aggregation/admission algorithm against current raw retrieval inputs. It does not
  claim to restore August 15 query generation, index contents, CodeGraph implementation, controller, prompts, or final
  selection. This isolates initial admission rather than combining a historical full-pipeline rollback.

### Proposed legacy behavior

Run the August 15 `aggregate_observations(raw_observations, limit=max_discovery_observations)` guardrail, aggregate the
full raw set without the limit to construct deferred observations, and omit the initial owner-comparison LLM call.
Trace the mode and lifecycle partition explicitly. Current canonicalization/source preparation/owner comparison stays
untouched and is executed only in the default mode.

### Expected effects and risks

- Quality: restore the wider, simpler 24-observation round-zero input for controlled comparison.
- Tokens: remove the initial-owner-comparison call; round-zero qualification may grow because it receives up to 24
  observations.
- Runtime: reduce initial owner-source preparation and one LLM request; later controller work may change.
- Candidate volume: up to 24 initial observations, with remaining aggregated observations deferred.
- Risks: current dense/sparse inputs differ from August 15 hybrid inputs; older aggregation may retain noisy generated
  declarations; wider qualification may consume its 40K budget and omit source from later cards.

### Verification

- Focused deterministic tests establish that the default mode still calls owner comparison and returns its selection,
  while legacy mode does not call it and returns the guardrail-ranked observations plus deferred remainder.
- Diagnostic actual-pipeline runs stop before round-zero qualification and compare selected paths, Oracle presence,
  serialized qualification input, initial-stage tokens, and lifecycle counts.
- Acceptance comparison uses final evidence selection with response generation skipped. At least two actual runs are
  required before deciding whether the legacy option is useful beyond diagnostics.

## Result Ledger

| Step | Attempt | Focused run 1 | Focused run 2 | Cost change | Decision | Remaining issue |
|---|---:|---|---|---|---|---|
| Empty ordinary-action backfill | 1 | Unit pass; live `100510Z` backfilled an empty action | Unit pass; live `100904Z` backfilled an empty action | +1 productive action in each live run | Rejected | One replacement duplicated a queued `builder.ts` island; both runs retained only two Oracles |
| Empty ordinary-action backfill | 2 | 96 focused tests passed twice; `run-20260830T101534Z` exercised backfill and retained Builder, BuilderState, WatchMode | `run-20260830T102004Z` had no empty action and retained Builder/WatchMode; confirmatory `run-20260830T102416Z` also had no empty action and retained all four target files | Exercised run: 103,241 retrieval tokens; unexercised runs: 100,792 and 110,229 | Retain | Only one acceptance run naturally exercised the boundary; ordinary final-selection variability remains independently visible |
| Legacy observation-guardrail mode | 1 | Diagnostic `run-20260830T095103Z`: 24 snippets/6 files, WatchMode initially; acceptance `run-20260830T095730Z`: Builder, WatchMode, Helpers | Diagnostic current `run-20260830T095541Z`: 16 snippets/9 files, Builder+WatchMode initially; legacy acceptance `run-20260830T100104Z`: same three legacy Oracles | Legacy acceptance mean 78,388 tokens versus roughly 100K–110K current runs, chiefly by omitting the ~17K owner-comparison call | Keep opt-in, do not promote | It reproduces commit `45a473e` admission on current raw inputs, not the historical upstream retrieval pool; BuilderState was absent in both legacy acceptances |

## Rollback Criteria

- Revert backfill if it exceeds the bounded replacement count, violates action-pool isolation, repeats an attempted
  effect, or causes two actual runs to regress quality or sufficiency.
- Keep the legacy mode opt-in only. Remove it if it cannot reproduce deterministic guardrail behavior or if it changes
  the default path. Do not promote it to the default from one favorable case.
