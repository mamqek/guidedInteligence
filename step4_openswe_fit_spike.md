# Step 4 Open SWE Fit Spike

## Purpose

This document maps the current v1 orchestration flow into a theoretical
Open SWE runtime graph before any real runtime integration begins.

This is a fit-spike document, not an implementation file. It answers:

- What is the smallest graph that can represent the current policy flow?
- Can the repo's own state and decision types stay central?
- Where would policy, retrieval, response, and logging hook into a runtime?
- Which parts of the current contract look easy to map, and which parts look
  awkward or risky?

This document intentionally avoids making framework-specific API claims. It
describes the expected control flow that a real Open SWE spike should test.

## Current V1 Flow To Preserve

The current repo behavior is defined by the framework-independent core
contracts:

- `ConversationState` is the input to orchestration.
- `V1PolicyEngine.decide(state)` is the main control point.
- `OrchestratorDecision` determines:
  - `current_stage`
  - `next_stage`
  - `retrieval_required`
  - `response_template_id`
  - `violations`
- Retrieval is represented by `RetrievalService.plan(...)` and
  `RetrievalService.retrieve(...)`.
- Response structure is derived by `contract_for_decision(...)`.
- Logging is represented by `LogEvent` and `LogEventType`.

The current stage-driven behavior is:

```text
EXPLAIN -> ASK -> HINT
```

Important current policy details that the fit spike must preserve:

- `EXPLAIN` responses now end with a knowledge-check question.
- Direct-solution requests recover through `ASK`.
- Stage-skipping attempts recover through `ASK`.
- `HINT` is terminal for normal progress.
- `HINT -> ASK` is allowed only as a recovery transition.

## Minimal Graph To Test

The theoretical minimum graph should be small enough to validate fit, not
complete enough to commit to runtime architecture.

Recommended node sequence:

```text
start
  |
  v
state_load
  |
  v
policy_decision
  |
  +--> violation_recovery_response
  |
  +--> retrieval_plan
         |
         +--> retrieval_fetch
                |
                v
            response_build
                |
                v
             state_update
                |
                v
               end
```

Equivalent condensed path:

```text
policy -> retrieval -> response -> state update
```

Violation path:

```text
policy -> boundary-check response -> state update
```

This graph is enough to answer Step 4's real question:

```text
Can Open SWE act as the shell around our policy core without owning the policy?
```

## Node Responsibilities

### 1. `state_load`

Input:

- raw user input
- current conversation state
- prior stage history
- any already attached evidence

Output:

- one `ConversationState`

Expectation:

- Open SWE graph state should carry our `ConversationState` or a thin wrapper
  around it.
- The runtime should not force `ConversationState` fields to be split across
  unrelated framework-owned state objects.

### 2. `policy_decision`

Input:

- `ConversationState`

Logic:

- call `V1PolicyEngine.decide(state)`

Output:

- one `OrchestratorDecision`

Expectation:

- This node is the central branching point.
- The runtime should allow branching on `OrchestratorDecision` fields without
  re-encoding policy logic in graph glue.

### 3. `retrieval_plan`

Input:

- `ConversationState`
- `OrchestratorDecision`

Logic:

- if `retrieval_required` is `True`, call `RetrievalService.plan(...)`

Output:

- one `RetrievalPlan`

Expectation:

- The runtime should make conditional node execution easy.
- Retrieval should be skipped cleanly when `retrieval_required` is `False`.

### 4. `retrieval_fetch`

Input:

- `RetrievalPlan`

Logic:

- call `RetrievalService.retrieve(plan)`

Output:

- `Sequence[EvidenceItem]`

Expectation:

- Evidence should remain structured and provenance-aware.
- The runtime should not require flattening evidence into prompt strings too
  early.

### 5. `response_build`

Input:

- `OrchestratorDecision`
- retrieved or existing `EvidenceItem` values

Logic:

- derive `ResponseContract` from `contract_for_decision(decision)`
- later call a deterministic response builder or model-backed builder

Output:

- one `ResponsePayload`

Expectation:

- Response construction should remain downstream of policy.
- Recovery responses should use the same node shape as normal responses, with a
  different template.

### 6. `violation_recovery_response`

Input:

- `OrchestratorDecision` with violations

Logic:

- build a `BOUNDARY_CHECK_QUESTION` response without retrieval

Output:

- one `ResponsePayload`

Expectation:

- The graph should support a short-circuit path for violations.
- The runtime should not force violations through the full retrieval path.

### 7. `state_update`

Input:

- prior `ConversationState`
- `OrchestratorDecision`
- optional evidence
- `ResponsePayload`

Logic:

- append message history
- attach evidence when retrieval ran
- advance the stage using `decision.next_stage`

Output:

- next `ConversationState`

Expectation:

- Our own next-state logic should remain explicit and testable.
- The runtime should not hide the transition update inside framework callbacks.

## Theoretical Graph By Scenario

### Normal Explanation Request

```text
state_load
  -> policy_decision
  -> retrieval_plan
  -> retrieval_fetch
  -> response_build
  -> state_update
  -> end
```

Expected result:

- response template: `explanation`
- response includes a closing knowledge-check question
- next state stage: `ASK`

### Ask-Stage Follow-Up

```text
state_load
  -> policy_decision
  -> retrieval_plan (only if no evidence is attached)
  -> retrieval_fetch (only if retrieval ran)
  -> response_build
  -> state_update
  -> end
```

Expected result:

- response template: `reasoning_question`
- next state stage: `HINT`

### Hint-Stage Follow-Up

```text
state_load
  -> policy_decision
  -> retrieval_plan (only if no evidence is attached)
  -> retrieval_fetch (only if retrieval ran)
  -> response_build
  -> state_update
  -> end
```

Expected result:

- response template: `hint`
- next state stage: `HINT`

### Direct Solution Request

```text
state_load
  -> policy_decision
  -> violation_recovery_response
  -> state_update
  -> end
```

Expected result:

- response template: `boundary_check_question`
- retrieval is skipped
- next state stage: `HINT` after the recovery turn is emitted from `ASK`

Important nuance:

```text
The current response is an ASK-stage recovery response.
The next state still becomes HINT, because the policy treats the recovery turn
as the ASK-stage turn itself.
```

### Stage-Skipping Attempt

```text
state_load
  -> policy_decision
  -> violation_recovery_response
  -> state_update
  -> end
```

Expected result:

- violation: `STAGE_SKIPPING`
- response template: `boundary_check_question`
- retrieval is skipped
- next state stage: `HINT`

### Unsupported Source Evidence

```text
state_load
  -> policy_decision
  -> response_build
  -> state_update
  -> end
```

Expected result under the current contract:

- violation: `UNSUPPORTED_SOURCE_USAGE`
- current stage remains `EXPLAIN`
- no new retrieval because evidence is already attached

Important nuance:

```text
Unsupported-source handling does not currently use the ASK-stage recovery path.
It stays in the normal stage-driven decision shape with violations attached.
```

That is acceptable for the fit spike as long as the runtime can carry violation
metadata without forcing one universal error branch.

## State Mapping Hypothesis

The cleanest runtime mapping is:

```text
Open SWE graph state
  {
    conversation_state: ConversationState
    decision: OrchestratorDecision | None
    retrieval_plan: RetrievalPlan | None
    evidence: tuple[EvidenceItem, ...]
    response: ResponsePayload | None
    events: list[LogEvent]
  }
```

Why this shape is attractive:

- It keeps the repo's own contracts intact.
- It treats framework state as a transport container, not a replacement domain
  model.
- It preserves explicit node outputs for replay and debugging.

What should not happen:

- splitting stage, decision, and violation fields into unrelated runtime-local
  dict keys
- flattening evidence into raw prompt text before response construction
- replacing `ConversationState` with framework-native state objects inside the
  core package

## Policy Injection Points

The fit spike should confirm three concrete policy injection points:

### Pre-retrieval gating

```text
policy_decision decides whether retrieval is allowed or required
before any retrieval node runs
```

This is required because source usage is policy-governed, not runtime-governed.

### Template selection before response generation

```text
policy_decision selects the response template
before any response builder or model call runs
```

This is required because the model layer is constrained by stage and policy.

### Recovery branching for shortcut violations

```text
policy_decision decides whether the graph uses the short recovery path
instead of the retrieval path
```

This is required because direct-solution and stage-skipping handling is not a
generic runtime exception; it is domain policy.

## Logging Feasibility Map

A good fit means each control point can emit `LogEvent` records without runtime
contortions.

Recommended event emission points:

```text
policy_decision              -> STAGE_DECISION
retrieval_plan               -> RETRIEVAL_PLAN
retrieval_fetch              -> EVIDENCE_SELECTED
response_build input         -> PROMPT_PAYLOAD
response_build output        -> RESPONSE_PAYLOAD
violation handling anywhere  -> POLICY_VIOLATION
```

This is a good sign if:

- each node can emit one append-only event cleanly
- the runtime preserves execution order
- the conversation ID is easy to thread through every node

This is a bad sign if:

- logging must be duplicated across many framework hooks
- event order becomes ambiguous
- node-local data is hard to access at logging time

## Fit Assessment Against Current Contracts

### Looks easy

- `V1PolicyEngine.decide(state)` is already a single clean branch point.
- Retrieval already has a two-step interface: plan first, then fetch.
- Response shape is already contract-driven through `response_template_id`.
- Logging already has a small explicit schema.
- The current stage machine is intentionally small.

### Looks manageable but worth testing

- Recovery responses use `current_stage=ASK` and `next_stage=HINT`, even when
  the incoming state was not `ASK`. The runtime must tolerate policy-driven
  stage reassignment.
- Unsupported-source violations currently stay inside the normal stage-driven
  path instead of using one universal recovery branch.
- A real runtime will need a thin state-update layer because `ConversationState`
  is immutable.

### Looks risky

- If Open SWE expects the framework graph to own branching semantics instead of
  letting node outputs drive branches, policy logic could leak into graph glue.
- If runtime state strongly prefers ad hoc mutable dicts, it may encourage
  duplication of information already present in `ConversationState` and
  `OrchestratorDecision`.
- If logging is only convenient at framework callback boundaries, replay-quality
  observability may become awkward.

## What Would Count As A Good Fit

- The graph can branch directly from `OrchestratorDecision`.
- `ConversationState` remains the central state type for orchestration logic.
- Retrieval and response nodes can stay thin wrappers around repo-owned
  interfaces.
- Recovery paths can bypass retrieval cleanly.
- Log events can be emitted at node boundaries in a stable order.

## What Would Count As A Forced Fit

- Policy rules must be re-encoded in graph routing configuration.
- Core types must be rewritten to satisfy runtime-specific state requirements.
- Logging depends on scattered framework hooks instead of explicit node outputs.
- Retrieval and recovery paths cannot branch naturally from policy output.
- Stage transitions become implicit side effects instead of explicit updates.

## Recommended Output Of The Real Step 4 Spike

The actual Open SWE spike should produce:

1. a tiny graph with only policy, retrieval, response, and state-update nodes
2. a minimal runtime-local state wrapper around existing core contracts
3. one normal explanation trace
4. one direct-solution recovery trace
5. one stage-skipping recovery trace
6. a short conclusion stating whether the runtime fit felt natural or forced

If the runtime cannot support that tiny graph cleanly, Step 5 should not begin.
