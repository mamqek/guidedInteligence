# Step 4 Open SWE Fit Spike

## Purpose

This document maps the current v1 orchestration flow into a custom LangGraph
graph that can run inside or alongside Open SWE infrastructure before any real
runtime integration begins.

This is a fit-spike document, not an implementation file. It answers:

- What is the smallest custom LangGraph graph that can represent the current
  policy flow?
- Can the repo's own state and decision types stay central?
- Where would policy, retrieval, response, and logging hook into an Open SWE
  deployment shell?
- Which parts of the current contract look easy to map, and which parts look
  awkward or risky?

This document uses current Open SWE and LangGraph behavior as the fit target:
Open SWE is built on LangGraph and Deep Agents, and provides sandbox,
invocation, thread/run, middleware, and deployment infrastructure. Guided
Intelligence stage policy must remain in this repo's own custom LangGraph nodes,
not in Deep Agents prompts.

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
- Direct-solution requests produce a stage-boundary choice response without
  advancing the active stage.
- Stage-skipping attempts keep the last valid stage active.
- `HINT` is terminal for normal progress.

## Open SWE Role Boundary

Open SWE should be treated as operational infrastructure around the Guided
Intelligence graph, not as the owner of the teaching policy.

Use Open SWE for:

- LangGraph deployment and run management.
- Sandbox creation, reuse, and execution environment boundaries.
- Invocation surfaces such as Slack, Linear, and GitHub.
- Thread IDs, run IDs, persistence, traces, and optional operational middleware.

Do not use Open SWE for:

- Encoding stage policy in a Deep Agents system prompt.
- Letting the default Deep Agents agent loop choose `EXPLAIN`, `ASK`, `HINT`, or
  `STAGE_BOUNDARY_CHOICE`.
- Replacing `ConversationState`, `OrchestratorDecision`, `PolicyViolation`, or
  repo-owned logging events with framework-local ad hoc fields.

Deep Agents may be useful later for separate coding-agent tasks, but it must not
be the controller for Guided Intelligence stage flow.

## Minimal Graph To Test

The theoretical minimum custom LangGraph graph should be small enough to
validate fit, not complete enough to commit to runtime architecture.

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
  v
branch_on_decision
  |
  +--> stage_boundary_response
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
state_load -> policy_decision -> branch -> retrieval/response -> state_update
```

Violation path:

```text
state_load -> policy_decision -> branch -> stage-boundary response -> state_update
```

This graph is enough to answer Step 4's real question:

```text
Can Open SWE act as the shell around our policy core without owning the policy?
```

The spike should expose a graph entrypoint compatible with LangGraph deployment
conventions, while ensuring that the graph calls `V1PolicyEngine.decide(...)`
instead of reimplementing policy in routing glue or prompts.

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

- Custom LangGraph state should carry our `ConversationState` or a thin wrapper
  around it when deployed through Open SWE infrastructure.
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

### 3. `branch_on_decision`

Input:

- `OrchestratorDecision`

Logic:

- route shortcut violations to `stage_boundary_response`
- route non-boundary decisions with `retrieval_required=True` to `retrieval_plan`
- route non-boundary decisions with `retrieval_required=False` to `response_build`

Output:

- the selected next LangGraph node

Expectation:

- Branching should use LangGraph conditional edges or `Command`, not prompt
  wording.
- The branch function may inspect `OrchestratorDecision` fields, but must not
  duplicate the policy rules that produced them.

### 4. `retrieval_plan`

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

### 5. `retrieval_fetch`

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

### 6. `response_build`

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
- Boundary responses should use the same node shape as normal responses, with a
  different template.

### 7. `stage_boundary_response`

Input:

- `OrchestratorDecision` with violations

Logic:

- build a `STAGE_BOUNDARY_CHOICE` response without retrieval

Output:

- one `ResponsePayload`

Expectation:

- The graph should support a short-circuit path for shortcut violations.
- The runtime should not force violations through the full retrieval path.

### 8. `state_update`

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
  -> branch_on_decision
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
  -> branch_on_decision
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
  -> branch_on_decision
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
  -> branch_on_decision
  -> stage_boundary_response
  -> state_update
  -> end
```

Expected result:

- response template: `stage_boundary_choice`
- retrieval is skipped
- next state stage: `EXPLAIN`

Important nuance:

```text
The response is a boundary response for the active EXPLAIN stage.
The next state remains EXPLAIN until the user follows the current stage or
chooses to return to explanation.
```

### Stage-Skipping Attempt

```text
state_load
  -> policy_decision
  -> branch_on_decision
  -> stage_boundary_response
  -> state_update
  -> end
```

Expected result:

- violation: `STAGE_SKIPPING`
- response template: `stage_boundary_choice`
- retrieval is skipped
- next state stage: the last valid stage, `EXPLAIN` in the baseline scenario

### Unsupported Source Evidence

```text
state_load
  -> policy_decision
  -> branch_on_decision
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
Unsupported-source handling does not use the shortcut boundary path in this
pass. It stays in the normal stage-driven decision shape with violations
attached.
```

That is acceptable for the fit spike as long as the runtime can carry violation
metadata without forcing one universal error branch.

## State Mapping Hypothesis

The cleanest runtime mapping is:

```text
Custom LangGraph state inside Open SWE deployment
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
- It treats LangGraph/Open SWE state as a transport container, not a replacement
  domain model.
- It preserves explicit node outputs for replay and debugging.

What should not happen:

- splitting stage, decision, and violation fields into unrelated runtime-local
  dict keys
- flattening evidence into raw prompt text before response construction
- replacing `ConversationState` with framework-native state objects inside the
  core package

## Policy Injection Points

The fit spike should confirm three concrete policy injection points. Each point
must live in custom LangGraph nodes or edges, not in Deep Agents prompt text.

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

### Boundary branching for shortcut violations

```text
policy_decision decides whether the graph uses the short boundary path
instead of the retrieval path
```

This is required because direct-solution and stage-skipping handling is not a
generic runtime exception; it is domain policy.

## Deep Agents Boundary

Default Open SWE composes a Deep Agents loop with tools, middleware, and a
system prompt. That is a good coding-agent harness, but it is the wrong place to
own Guided Intelligence stage policy.

Acceptable Deep Agents usage:

- later downstream coding-agent tasks that happen after the Guided Intelligence
  controller has made a policy decision
- optional operational middleware that does not decide stages
- sandbox-backed tool execution when the task explicitly becomes code-changing

Rejected Deep Agents usage:

- asking a prompt to decide whether the user is in `EXPLAIN`, `ASK`, or `HINT`
- placing direct-solution or stage-skipping handling only in prompt rules
- letting middleware infer policy instead of calling `V1PolicyEngine`

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
- Raw LangGraph conditional edges or `Command` can branch from
  `OrchestratorDecision` without requiring a model.
- Retrieval already has a two-step interface: plan first, then fetch.
- Response shape is already contract-driven through `response_template_id`.
- Logging already has a small explicit schema.
- The current stage machine is intentionally small.
- Open SWE already contributes useful infrastructure: sandboxing, invocation
  surfaces, thread/run management, middleware, and deployment around LangGraph.

### Looks manageable but worth testing

- Shortcut boundary responses keep `current_stage` and `next_stage` equal, so
  the runtime must tolerate explicit no-op stage updates on disallowed turns.
- Unsupported-source violations currently stay inside the normal stage-driven
  path instead of using the shortcut boundary branch.
- A real runtime will need a thin state-update layer because `ConversationState`
  is immutable.
- The Open SWE invocation payloads must be normalized into `ConversationState`
  inside `state_load`.
- Open SWE thread metadata can carry operational IDs, but should not become the
  source of truth for stage policy.

### Looks risky

- If the default Open SWE Deep Agents loop is used as the Guided Intelligence
  controller, policy logic will leak into prompts and middleware.
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
- Shortcut boundary paths can bypass retrieval cleanly.
- Log events can be emitted at node boundaries in a stable order.
- Open SWE provides deployment, sandbox, invocation, and trace infrastructure
  without owning stage decisions.

## What Would Count As A Forced Fit

- Policy rules must be re-encoded in Deep Agents prompts, middleware, or graph
  routing configuration.
- Core types must be rewritten to satisfy runtime-specific state requirements.
- Logging depends on scattered framework hooks instead of explicit node outputs.
- Retrieval and shortcut boundary paths cannot branch naturally from policy output.
- Stage transitions become implicit side effects instead of explicit updates.
- Open SWE's default coding-agent workflow becomes the primary controller for
  Guided Intelligence rather than a deployable shell around the custom graph.

## Recommended Output Of The Real Step 4 Spike

The actual Open SWE spike should produce:

1. a tiny custom LangGraph graph with policy, branch, retrieval, response, and
   state-update nodes
2. a minimal runtime-local state wrapper around existing core contracts
3. one normal explanation trace
4. one direct-solution boundary trace
5. one stage-skipping boundary trace
6. a short conclusion stating whether Open SWE works cleanly as infrastructure
   around the custom graph

If the runtime cannot support that tiny graph cleanly, Step 5 should not begin.
