# Step 3 Harness Scenarios

## Purpose

Step 3 validates the v1 orchestration contract without introducing Open SWE,
real RAG, real model calls, MCP, UI, or automated task completion.

The local harness should prove that the core language from steps 1 and 2 is
usable end to end:

1. Create a `ConversationState`.
2. Call `V1PolicyEngine.decide(state)`.
3. If `retrieval_required` is true, use static `EvidenceItem` fixtures.
4. Build a deterministic `ResponsePayload` shape from the selected response
   contract.
5. Emit structured `LogEvent` records using `core.logging_schema`.
6. Advance the next state according to the policy decision.

The harness is a contract test for orchestration behavior. It should not hide
awkwardness in the current interfaces; if a scenario is clumsy to express, that
is useful feedback before framework integration begins.

## Completion Check For Steps 1 And 2

Step 1 is represented by `v1_boundaries.md`:

- The supported v1 flow is `explain -> ask -> hint`.
- Direct solution requests and stage-skipping attempts are violations and now
  recover through `ask`-stage questioning.
- Valid grounding sources are source code, documentation, issue trackers, and
  pull requests.
- Required audit data includes stage decisions, retrieval/source plans,
  evidence references, response payloads, model settings when applicable, and
  policy violations.
- MCP, Open SWE, real RAG, model complexity, task completion, and polished UI
  remain out of scope.

Step 2 is represented by the framework-independent contracts:

- `core.models` defines `ConversationState`, `UserIntent`, `EvidenceItem`, and
  `OrchestratorDecision`.
- `core.stages` and `core.transitions` define the v1 stage order and allowed
  transitions.
- `core.source_policy` defines allowed source categories.
- `core.violations` defines explicit policy violations.
- `core.policy` exposes `PolicyEngine` and `V1PolicyEngine`.
- `core.response_contracts` defines response templates, contracts, and payloads.
- `core.logging_schema` defines the minimum structured log event types.
- `services.retrieval.contracts` defines the retrieval planning and retrieval
  service interface.

## Harness Behavior Contract

The first harness should be deterministic and local:

- It should create one scenario state at a time.
- It should call `V1PolicyEngine.decide` exactly once per scenario turn.
- It should not reimplement stage, source, or violation rules outside policy.
- It should use static evidence fixtures when retrieval is required.
- It should build predictable response payloads with stable evidence refs.
- It should emit logs in the order a replay reader would expect.
- It should expose current contract gaps instead of smoothing them over.

Minimum log events by phase:

| Phase | Event |
| --- | --- |
| Policy decision | `STAGE_DECISION` |
| Retrieval planning, when `retrieval_required` is true | `RETRIEVAL_PLAN` |
| Evidence fixture selection, when retrieval runs | `EVIDENCE_SELECTED` |
| Response-builder input shape | `PROMPT_PAYLOAD` |
| Final deterministic response object | `RESPONSE_PAYLOAD` |
| Each detected violation | `POLICY_VIOLATION` |

## Scenario Matrix

Each scenario must assert the expected `OrchestratorDecision` fields:
`allowed`, `current_stage`, `next_stage`, `intent`, `retrieval_required`,
`response_template_id`, `allowed_sources`, and `violations`.

### 1. Normal Explanation Request

User asks to understand project behavior from the initial `explain` stage.

Expected decision:

| Field | Expected value |
| --- | --- |
| `allowed` | `True` |
| `current_stage` | `EXPLAIN` |
| `next_stage` | `ASK` |
| `intent` | `UNDERSTAND_CODE` |
| `retrieval_required` | `True` |
| `response_template_id` | `explanation` |
| `allowed_sources` | `DEFAULT_ALLOWED_SOURCE_CATEGORIES` |
| `violations` | none |

Expected logs:

- `STAGE_DECISION`
- `RETRIEVAL_PLAN`
- `EVIDENCE_SELECTED`
- `PROMPT_PAYLOAD`
- `RESPONSE_PAYLOAD`

Response nuance:

- The deterministic response should contain an explanation-shaped payload with
  evidence refs from static source-code or documentation fixtures.
- The explanation response itself should end with a knowledge-check question.
- The next state should move to `ASK` only after the response payload is built.

### 2. Ask-Stage Follow-Up

State is already at `ask`; user asks for more detail or continues the
explanation path.

Expected decision:

| Field | Expected value |
| --- | --- |
| `allowed` | `True` |
| `current_stage` | `ASK` |
| `next_stage` | `HINT` |
| `intent` | `FOLLOW_UP` |
| `retrieval_required` | `True` when no evidence is attached |
| `response_template_id` | `reasoning_question` |
| `allowed_sources` | `DEFAULT_ALLOWED_SOURCE_CATEGORIES` |
| `violations` | none |

Expected logs when no evidence is attached:

- `STAGE_DECISION`
- `RETRIEVAL_PLAN`
- `EVIDENCE_SELECTED`
- `PROMPT_PAYLOAD`
- `RESPONSE_PAYLOAD`

Response nuance:

- The deterministic response should ask one reasoning question, not provide a
  direct answer.
- `contract_for_decision` currently marks reasoning questions as not requiring
  evidence in the final content, but the retrieval decision can still request
  evidence when the state has none. The harness should preserve that difference.

### 3. Hint-Stage Follow-Up

State is already at `hint`; user asks for help after the explanation and
reasoning-question stages.

Expected decision:

| Field | Expected value |
| --- | --- |
| `allowed` | `True` |
| `current_stage` | `HINT` |
| `next_stage` | `HINT` |
| `intent` | `FOLLOW_UP` |
| `retrieval_required` | `True` when no evidence is attached |
| `response_template_id` | `hint` |
| `allowed_sources` | `DEFAULT_ALLOWED_SOURCE_CATEGORIES` |
| `violations` | none |

Expected logs when no evidence is attached:

- `STAGE_DECISION`
- `RETRIEVAL_PLAN`
- `EVIDENCE_SELECTED`
- `PROMPT_PAYLOAD`
- `RESPONSE_PAYLOAD`

Response nuance:

- The deterministic response should stay bounded to a hint.
- The next stage remains `HINT`; repeated hint-stage turns should not advance
  into a new hidden stage.

### 4. Direct Solution Request

User asks the system to solve, complete, or fix the task directly.

Expected decision:

| Field | Expected value |
| --- | --- |
| `allowed` | `False` |
| `current_stage` | `ASK` |
| `next_stage` | `HINT` |
| `intent` | `DIRECT_SOLUTION_REQUEST` |
| `retrieval_required` | `False` |
| `response_template_id` | `boundary_check_question` |
| `allowed_sources` | `DEFAULT_ALLOWED_SOURCE_CATEGORIES` |
| `violations` | `DIRECT_SOLUTION_REQUEST` |

Expected logs:

- `STAGE_DECISION`
- `POLICY_VIOLATION`
- `PROMPT_PAYLOAD`
- `RESPONSE_PAYLOAD`

Response nuance:

- The deterministic response should set a boundary and end with a
  knowledge-check question.
- No retrieval should run for this path.
- The recovery response uses `ASK`-stage questioning so the next normal turn
  can continue toward `HINT`.

### 5. Stage Skipping Attempt

State attempts to jump from `explain` directly to `hint`.

Expected decision with the updated recovery policy:

| Field | Expected value |
| --- | --- |
| `allowed` | `False` |
| `current_stage` | `ASK` |
| `next_stage` | `HINT` |
| `intent` | `UNDERSTAND_CODE` unless classified otherwise |
| `retrieval_required` | `False` |
| `response_template_id` | `boundary_check_question` |
| `allowed_sources` | `DEFAULT_ALLOWED_SOURCE_CATEGORIES` |
| `violations` | `STAGE_SKIPPING` |

Expected logs:

- `STAGE_DECISION`
- `POLICY_VIOLATION`
- `PROMPT_PAYLOAD`
- `RESPONSE_PAYLOAD`

Response nuance:

- The recovery response should refuse the shortcut and ask a verification
  question before allowing hint-stage help.
- No retrieval should run for this path.

### 6. Unsupported Source Evidence

Attached evidence contains a source category outside the v1 allowlist.

Expected decision with the current policy:

| Field | Expected value |
| --- | --- |
| `allowed` | `False` |
| `current_stage` | `EXPLAIN` |
| `next_stage` | `ASK` |
| `intent` | `UNDERSTAND_CODE` |
| `retrieval_required` | `False`, because evidence is attached |
| `response_template_id` | `explanation` |
| `allowed_sources` | `DEFAULT_ALLOWED_SOURCE_CATEGORIES` |
| `violations` | `UNSUPPORTED_SOURCE_USAGE` |

Expected logs:

- `STAGE_DECISION`
- `POLICY_VIOLATION`
- `PROMPT_PAYLOAD`
- `RESPONSE_PAYLOAD`

Response nuance:

- The current `SourceCategory` enum only defines allowed v1 categories. The
  scenario skeleton uses a scenario-only cast to represent a disallowed category
  without changing core types yet.
- This is a contract gap worth preserving in Step 3: v1 wants unsupported
  source usage to be loggable, but the strict enum does not naturally model
  unsupported sources.

### 7. Evidence Already Present

User asks for an explanation and the state already has valid project evidence.

Expected decision:

| Field | Expected value |
| --- | --- |
| `allowed` | `True` |
| `current_stage` | `EXPLAIN` |
| `next_stage` | `ASK` |
| `intent` | `UNDERSTAND_CODE` |
| `retrieval_required` | `False` |
| `response_template_id` | `explanation` |
| `allowed_sources` | `DEFAULT_ALLOWED_SOURCE_CATEGORIES` |
| `violations` | none |

Expected logs:

- `STAGE_DECISION`
- `PROMPT_PAYLOAD`
- `RESPONSE_PAYLOAD`

Response nuance:

- The harness should reuse attached evidence instead of running stub retrieval.
- The response payload should cite the attached evidence refs.

### 8. Unknown Intent Heuristic

State has `intent=UNKNOWN`; policy classifies intent with the current
deterministic keyword rules.

Expected decision for a "more detail" follow-up at `ask`:

| Field | Expected value |
| --- | --- |
| `allowed` | `True` |
| `current_stage` | `ASK` |
| `next_stage` | `HINT` |
| `intent` | `FOLLOW_UP` |
| `retrieval_required` | `True` when no evidence is attached |
| `response_template_id` | `reasoning_question` |
| `allowed_sources` | `DEFAULT_ALLOWED_SOURCE_CATEGORIES` |
| `violations` | none |

Expected logs:

- `STAGE_DECISION`
- `RETRIEVAL_PLAN`
- `EVIDENCE_SELECTED`
- `PROMPT_PAYLOAD`
- `RESPONSE_PAYLOAD`

Response nuance:

- This scenario should assert policy output, not copy the keyword heuristic into
  the harness.
- Direct-solution marker coverage belongs in the direct-solution scenario.

## Deterministic Fixture Rules

Static retrieval fixtures should be small and stable:

- Prefer one source-code evidence item and one documentation evidence item.
- Keep `source_id` values stable so response payloads and logs are comparable.
- Keep snippets short enough to be readable in JSON-like logs.
- Preserve rank order in the selected evidence refs.

The response payload content may be plain placeholder text in Step 3, but its
template, stage, evidence refs, and violations must match the policy decision.

## Nuances To Preserve

- `redirect` is not a v1 stage. Shortcut recovery is represented by the
  `boundary_check_question` template.
- `HINT` is terminal for v1 and advances to itself.
- `EXPLAIN` responses now end with a knowledge-check question while still
  advancing the conversation into `ASK`.
- Retrieval is decided from attached evidence, not from response-template
  evidence requirements.
- The logging schema already includes `MODEL_SETTINGS`, but Step 3 should not
  emit it because no model path exists yet.
- Scenario execution should surface policy and contract gaps early. The harness
  should stay thin so those decisions remain in `core`, not in local runner code.
