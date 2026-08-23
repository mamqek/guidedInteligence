# Agent-Planned Native Retrieval Controller

## Status

- State: first implementation variant complete; actual quality acceptance blocked by exhausted API credits.
- Branch: `codex/seeded-agentic-retrieval`, after runtime reversion commit `c5d30f2` restored the native `fbc01cb`
  behavior while preserving the full-agent experiment in history and documentation.
- Primary case: `pandas-dev-pandas-10068`.
- Execution protocol: [`../incremental-experiment-execution-protocol.md`](../incremental-experiment-execution-protocol.md).

## Decision

Test a hybrid controller in a separate `agent_planned` retrieval mode. Keep native localization, deterministic action
execution, grounding, evidence-island representation, and final selection. Replace the repeated native downstream
decision sequence with exactly one stateful planner call per exploration round.

```text
KEEP
  request analysis
  -> obligation Qdrant + CodeGraph prefix
  -> file grouping, held alternatives, and initial owner comparison
  -> deterministic source disclosure
  -> deterministic typed-action validation and execution
  -> deterministic observation/candidate bookkeeping
  -> structural/evidence-island construction
  -> native final evidence selector

REPLACE PER ROUND
  evidence-qualification LLM
  -> coverage-evaluation LLM
  -> action enumeration
  -> action-pool scheduler
  -> special rescue/maturation selection

WITH ONE CALL
  classify every newly disclosed observation
  -> update coverage from all promoted candidates
  -> choose at most two typed actions, or stop
  -> persist explicit summary/open questions for the next round
```

The planner is not an extra reviewer around the native controller. If a round executes both a planner call and the old
qualification or coverage model call, the implementation violates this experiment.

## Why This Boundary

The full seeded agent replaced too much. It navigated raw artifacts, maintained findings, judged sufficiency, and
selected final evidence. Its corrected pandas run spent 299,499 agent-decision tokens and selected nothing. The native
controller, however, retains useful deterministic components: bounded source disclosure, typed actions, graph/search
executors, candidate grounding, and comparative final selection.

The likely overcomplicated responsibility is semantic planning. Native action policy currently divides generic
inspection/search/traversal work into ordinary, deferred rescue, owner maturation, test maturation, verified-lead, and
control pools, then applies fixed priorities and reserved slots. A planner can judge the current evidence and choose a
typed operation directly without inheriting those pools.

## Persistent Planner State

Application-owned state remains authoritative. It contains:

- request and obligations;
- all initial, deferred, and newly discovered observations;
- disclosure cards;
- planner-produced qualification decisions;
- grounded candidates derived through the existing candidate factory;
- latest obligation coverage;
- structural edges and islands;
- attempted action fingerprints/effects;
- bounded action outcomes;
- planner summary and open questions;
- round/action/token budgets.

The model receives a reconstructed bounded projection each round, not a provider transcript and not hidden
chain-of-thought. The projection includes complete bounded source only for newly disclosed observations. Older promoted
or rejected observations are represented by compact IDs, paths, symbols, classifications, and candidate summaries.

## One Planner Decision

The strict structured response contains:

1. one classification for every pending disclosure card;
2. one coverage record for every repository obligation, using observation IDs as support references;
3. zero to two typed action proposals;
4. `stop`, `stop_reason`, a short state summary, and explicit open questions.

Classification maps to the existing `QualificationDecision` combinations:

- `promote_direct`;
- `promote_navigation`;
- `defer_navigation`;
- `defer_insufficient`;
- `reject_insufficient`.

Coverage maps to the existing `ObligationCoverage` statuses and needs. Runtime validation requires covered/partial
obligations to cite known promoted observations that map to grounded candidates.

## Typed Planner Actions

The first variant permits only:

- `inspect_observation`: disclose a known initial/deferred observation;
- `inspect_owner_continuation`: disclose a later bounded range of a known owner;
- `expand_relationship`: follow bounded CodeGraph edges from a known node;
- `search_within_file`: run the existing Qdrant/exact refinement inside a known source path;
- `search_repository`: search for one unresolved mechanism anywhere in the allowed repository.

The model supplies semantic intent, obligation, query/anchors, and a known observation ID. Deterministic code supplies
or validates node IDs, paths, ranges, limits, action IDs, scopes, allowed edge kinds, repository exclusions, duplicate
effects, and global budgets. No arbitrary shell or arbitrary evidence selection is introduced.

## Round Flow

```text
pending observations
  -> deterministic source disclosure
  -> bounded planner context
  -> ONE planner call
  -> validate classifications, coverage, and actions
  -> update decisions and grounded candidates
  -> build/update islands
  -> if stop: leave loop
  -> execute at most two validated typed actions
  -> store bounded action outcomes and new observations
  -> next round
  -> native final evidence consolidation
```

There is no model confirmation after execution. Execution results become pending observations and bounded outcomes in
the next planner call. That next call simultaneously interprets them and chooses what follows.

## Budget And Cost Boundary

First-variant defaults:

- maximum planner rounds: 3;
- maximum actions per planner round: 2;
- maximum total planner-selected actions: 6;
- maximum serialized planner input: 30,000 characters;
- maximum source disclosure per pending card: existing 4,000-character bound, water-filled inside the global limit;
- no planner call after `stop=true`;
- one unchanged native final-selection call after the controller.

The quality experiment must record planner prompt/completion/total tokens separately. The planner is acceptable only if
it improves or preserves relevant final evidence across repeated runs and its total tokens are no greater than the
native qualification-plus-coverage tokens it replaces, unless a measured quality gain explicitly justifies a small
increase. It is never acceptable merely because call count decreased.

## Expected Impact

- Qualification becomes contextual and advisory rather than a separate irreversible decision stage.
- The same call that sees new source also decides whether to inspect a referenced/deferred owner, follow a graph edge,
  search locally, search globally, or stop.
- Action pools and reserved rescue slots no longer determine exploration.
- Final evidence remains grounded and comparatively selected by the native pipeline.
- Repeated serialization should decrease because only pending source is shown in full.

## Risks

- Combining classification, coverage, and action choice may overload one call.
- Coverage may become less stable when the planner focuses on navigation.
- Generic action proposals require strict validation to avoid invented paths/nodes.
- Initial owner comparison remains an upstream bias; all deferred observations must remain listable/actionable.
- Three rounds may be insufficient for a multi-hop mechanism.
- A compact persistent state can still hide a useful observation.
- Dynamic method factories may remain hard even when the planner has better state.
- If every planner error receives a new deterministic exception, the same policy proliferation will recur.

## Incremental Steps

### Step 1: Contract and validation

- Implement planner request/result contracts independently of the controller loop.
- Validate complete pending classifications, complete obligation coverage, support IDs, action types, observation IDs,
  paths, ranges, limits, and duplicates.
- Focused tests must pass twice unchanged.

### Step 2: Bounded context and persistent outcomes

- Project pending source, prior decisions/candidates/coverage, attempted actions, and outcomes under 30,000 characters.
- Prove previous empty/error outcomes appear in the next context without replaying full old source.
- Prove deferred observations remain addressable.

### Step 3: Deterministic action conversion/execution

- Convert valid planner proposals into existing typed actions.
- Reuse existing `execute_action`; do not duplicate graph/Qdrant/source execution.
- Reject invented IDs/paths and repeated effects before execution.

### Step 4: Controller integration

- Add a separate `agent_planned` mode.
- Ensure no per-round `evidence_qualification` or `retrieval_coverage` LLM events occur.
- Retain native final candidate construction, islands, final selection, evidence adaptation, and traces.

### Step 5: Actual-pipeline comparison

- Run focused tests first.
- Run pandas with response generation skipped and final selection enabled.
- Prefer two unchanged actual runs when runtime allows.
- Compare against fixed native artifacts without changing model, prefix, index, prompts, or final selector.

## Acceptance

Accept only if:

1. the actual trace contains one planner call per executed round and zero old per-round qualification/coverage calls;
2. every executed action was model-selected, deterministically validated, and executed through the existing executor;
3. the final selector remains native and receives grounded candidates;
4. useful initial/deferred observations remain traceable even when initially classified weakly;
5. quality is repeatable across two unchanged main-case runs;
6. planner token totals meet the stated replacement-cost boundary;
7. no repository/testcase-specific symbol rule is introduced.

## Rejection

Reject or disable if:

- the planner invents invalid actions twice under unchanged context;
- combining responsibilities repeatedly produces incomplete classifications or coverage;
- the agent reaches useful source but final candidate construction loses it;
- two actual runs regress relevant evidence or produce unstable sufficiency;
- planner tokens exceed the replaced native decision tokens without stable quality gain;
- the implementation starts recreating action pools through prompt or validator heuristics.

Maximum three implementation variants are permitted at any failed boundary.

## Result Ledger

| Step | Attempt | Focused run 1 | Focused run 2 | Actual run | Tokens | Decision |
|---|---:|---|---|---|---:|---|
| Contract/validation | 1 | pass | pass | n/a | n/a | mechanically accepted |
| Bounded persistent context | 1 | pass | pass | n/a | n/a | mechanically accepted |
| Typed action conversion | 1 | pass | pass | n/a | n/a | mechanically accepted |
| Controller integration | 1 | pass | pass | `run-20260823T180922Z` failed before retrieval | 0 planner | awaiting configured API credits |

## Implementation Note — 2026-08-23

Variant 1 is implemented as `agent_planned` without modifying the ordinary `workspace` controller. The planner has a
strict JSON contract, a 30,000-character total prompt/schema/payload budget, application-owned state, and deterministic
conversion into the five allowed native action types. The loop rejects unknown observations/obligations, unsupported
covered claims, invented node-based expansion, repeated action effects, and covered support that cannot resolve to a
native grounded candidate. Relationship execution also retains native file-trace construction for final consolidation.

Focused verification passed twice. The final focused set proves one model call jointly returns qualification,
coverage, and action choice; an executed action outcome and the prior state summary reach the next round; native
candidate IDs replace planner observation support; and the typed executor is called once for the selected action. The
unchanged retrieval-server and qualification-first suites pass 124/124 tests. Full discovery ran 401 tests and had four
unrelated existing/environment failures: three `test_index_setup` fixtures omit the already-required
`lexical_ranking_profile`, and CodeGraph cannot load `node:sqlite` from the installed Node runtime.

The requested actual diagnostic command created `run-20260823T180922Z`, but request analysis failed with API HTTP 429
`insufficient_quota` before Qdrant, CodeGraph, owner comparison, or the new controller ran. It is not a retrieval run,
contains no planner tokens or quality result, and cannot count toward acceptance. The LLM failure was surfaced directly;
no deterministic, Codex, or alternate-model fallback was used.
