# Orchestration Refactor Plan

## Purpose

This document defines a refactoring direction for the Guided Intelligence System that makes the **overall control layer** the primary architectural boundary.

The goal is to simplify the system without changing its product intent:

- preserve the scaffolded `explain -> ask -> hint` interaction model
- preserve explicit source-policy enforcement
- preserve evidence-grounded responses
- preserve auditability and replay
- treat retrieval as **one stage** inside orchestration, not as the conceptual center of the system

This plan is intentionally architectural. It does not prescribe immediate code edits in one sweep. It defines what should remain, what should collapse, and how to migrate safely.

---

## Core Decision

The system should be reorganized around **one explicit control layer** that owns:

- request classification
- stage policy enforcement
- source-policy enforcement
- the decision to invoke retrieval or skip it
- evidence sufficiency checks
- response-mode selection
- fallback and failure handling
- structured logging for the whole run

All other subsystems should become **stage workers** or **supporting services**.

This is the main architectural decision. Everything else in this plan follows from it.

---

## What Must Stay

These are not implementation details. They are core system intent and should remain first-class.

### 1. The product behavior

The system still exists to provide scaffolded, project-grounded assistance rather than direct task completion.

The staged progression remains:

```text
explain -> ask -> hint
```

### 2. Explicit policy boundaries

The system must continue to explicitly reject or redirect:

- direct-solution requests
- stage skipping
- unsupported source usage
- ungrounded answers

These are control-layer rules, not prompt-only rules.

### 3. Source-policy governance

The system must continue to decide and enforce:

- which source categories are allowed
- when they may be used
- whether the produced answer stayed within policy

### 4. Evidence as a first-class artifact

Responses should continue to be grounded in structured evidence items with stable identifiers and source provenance.

### 5. Auditability

The system must still produce structured logs describing:

- the decision path
- sources allowed and consulted
- evidence selected
- response mode chosen
- violations and fallback behavior

---

## What Should Change

The current system has the right concepts, but the orchestration logic is distributed across too many neighboring abstractions.

### Main simplification target

Move from:

- many small contracts that each encode part of workflow state

to:

- one control-layer run with a small number of stage results

### Architectural change in one sentence

The system should read as:

1. control layer decides what happens next
2. stage workers execute bounded work
3. control layer decides again

It should no longer read as:

- policy decides some things
- retrieval decides some things
- response contracts decide some things
- transition helpers decide some things

---

## Explicit Decisions

This section records the recommended keep/collapse/remove decisions.

### Keep

- `ConversationState` as the external input state for a run
- `EvidenceItem` as the stable evidence artifact
- stage vocabulary: `EXPLAIN`, `ASK`, `HINT`
- policy violations as explicit structured objects
- source categories and source-policy rules
- structured logging schema

### Collapse

#### 1. `OrchestratorDecision` and `ResponseContract`

These currently split one decision across two adjacent abstractions.

Recommended direction:

- keep one primary control-layer decision object
- derive any response-shape details inside the response-planning stage instead of exposing a separate first-class contract unless it proves necessary later

Practical meaning:

- the system should not require reading both `OrchestratorDecision` and `ResponseContract` to understand what response happens next

#### 2. Transition rules as a separate conceptual layer

`can_transition()` is useful, but the stage machine should not feel like an independent subsystem.

Recommended direction:

- keep transition validation logic
- move ownership of stage progression clearly into the control layer

Transitions should be a rule used by the control layer, not a peer abstraction to it.

#### 3. Retrieval planning metadata as orchestration state

Too much important state currently rides through metadata blobs and stage-local structures.

Recommended direction:

- keep retrieval-local planning data inside retrieval
- expose only a bounded retrieval request and retrieval result to the control layer

The control layer should not need to inspect retrieval metadata internals to understand the run.

### Remove or strongly reduce

#### 1. Cross-cutting decision logic outside the control layer

Any module that implicitly decides:

- whether to continue
- whether evidence is sufficient
- whether fallback should happen
- what broader mode the system is in

should be reduced unless it is the control layer itself.

#### 2. Duplicate workflow encoding

The orchestration flow is currently encoded in multiple places:

- stage definitions
- transition rules
- policy engine decisions
- response template selection
- retrieval-required flags

Recommended direction:

- one top-level run model should own workflow progression
- other modules should consume that decision, not restate it

#### 3. Metadata-as-hidden-state

Metadata should remain for trace and provenance, not as the main carrier of orchestration state.

When a field is required for a later decision, it should usually become a typed field on a stage result instead of staying buried in `metadata`.

---

## Target Architecture

The target architecture should have three layers.

### 1. Control Layer

This becomes the single source of truth for run flow.

Responsibilities:

- accept a `ConversationState`
- determine current operating mode
- enforce stage and source policy
- decide whether retrieval is needed
- invoke stage workers in order
- evaluate sufficiency of returned evidence/context
- select the response mode
- handle retry, refusal, fallback, or stop conditions
- emit run-level logs

Suggested primary entry point:

```text
ControlLayer.run(state) -> OrchestrationResult
```

### 2. Stage Workers

These do bounded work and do not own overall flow.

Suggested workers:

- `PolicyStage`
- `RetrievalStage`
- `ResponsePlanningStage`
- `ResponseBuilderStage`

Possible later worker:

- `EvidenceEvaluationStage`

Each worker should:

- accept a narrow typed input
- produce a narrow typed output
- avoid deciding global workflow beyond its local status

### 3. Shared Contracts

Keep these small and stable.

Recommended shared contract set:

- `ConversationState`
- `EvidenceItem`
- `PolicyViolation`
- `RunContext`
- `StageResult`
- `OrchestrationResult`

---

## Recommended Stage Model

The control layer should operate over explicit stage results.

### `PolicyResult`

Owns:

- allowed or blocked
- active stage
- next permitted stage
- source policy
- whether retrieval is required
- boundary or violation action

### `RetrievalResult`

Owns:

- evidence items
- coverage summary
- sufficiency status
- retrieval trace summary
- failure or fallback status

Retrieval should not decide the response mode. It should only report what it found and how complete that result is.

### `ResponsePlan`

Owns:

- response mode
- required content sections
- whether evidence is mandatory
- any boundary messaging requirements

### `OrchestrationResult`

Owns:

- final response payload
- final stage transition outcome
- evidence references used
- violations triggered
- run trace summary

---

## Proposed Runtime Flow

The top-level run should become legible enough to read in one screen.

Suggested flow:

```text
1. Read conversation state
2. Run policy stage
3. If blocked:
   build boundary response
   log and stop
4. If retrieval required:
   run retrieval stage
   evaluate sufficiency
5. Build response plan
6. Build final response payload
7. Record structured run events
8. Return orchestration result
```

This should be the main mental model for the system.

---

## Current-to-Target Mapping

### Current modules that should remain conceptually

- `core/models.py` equivalent concepts
- `policy`
- `retrieval`
- `logging`
- `response building`

### Current modules whose role should narrow

- `core/policy.py`
  It should become a stage worker or policy evaluator used by the control layer, not the whole orchestration surface by itself.

- `core/response_contracts.py`
  It should become response-planning support rather than a parallel orchestration abstraction.

- `core/transitions.py`
  It should remain as a helper for valid stage progression, but not carry independent architectural weight.

- `services/retrieval/*`
  Retrieval should expose a bounded stage interface and return sufficiency-oriented results to the control layer.

### New conceptual module to introduce

- `core/control_layer.py` or equivalent

This should become the orchestration center.

---

## Refactoring Phases

The migration should be staged to preserve behavior and keep tests meaningful.

### Phase 1. Freeze the target boundary

Deliverable:

- this document accepted as the architectural direction

Actions:

- confirm the control layer is the owner of flow
- confirm retrieval is one stage
- confirm response contracts will be reduced in architectural weight

### Phase 2. Introduce the control-layer shell

Deliverable:

- a new top-level orchestration entry point that delegates to existing modules

Actions:

- create a control-layer module
- make it call the existing policy logic first
- make it invoke retrieval only when needed
- make it route to response construction
- keep existing behavior intact

This phase should mostly be re-wiring, not behavior change.

### Phase 3. Unify stage results

Deliverable:

- typed stage result objects for policy, retrieval, and response planning

Actions:

- define `PolicyResult`, `RetrievalResult`, and `ResponsePlan`
- remove reliance on metadata blobs for control decisions where possible
- move run-level decisions back into the control layer

### Phase 4. Collapse redundant abstractions

Deliverable:

- fewer top-level concepts needed to explain the system

Actions:

- reduce overlap between `OrchestratorDecision` and `ResponseContract`
- reduce separate transition ownership
- simplify how template selection is represented

### Phase 5. Move logging to run boundaries

Deliverable:

- logs that describe the orchestration run clearly

Actions:

- emit stage-entry and stage-exit events from the control layer
- keep stage-local debug logs only where operationally useful
- make replay understandable without reading stage internals

### Phase 6. Narrow retrieval to a stage contract

Deliverable:

- retrieval exposed as a bounded subsystem rather than a co-orchestrator

Actions:

- keep retrieval planning and search internals inside retrieval
- return evidence, coverage, and sufficiency to the control layer
- avoid leaking broader workflow state upward from retrieval internals

---

## Risk Management

### Main risk

The main refactoring risk is collapsing abstractions too aggressively and accidentally losing policy guarantees.

### How to avoid it

- preserve the current tests around stage progression and violations
- add orchestration-level tests before removing old layers
- refactor wiring before refactoring behavior
- keep the old product invariants explicit throughout the migration

### Invariants that must not change during refactor

- direct-solution requests remain blocked
- stage skipping remains blocked
- stage progression remains `explain -> ask -> hint`
- source-policy restrictions remain enforced
- responses remain evidence-grounded where required

---

## Testing Strategy For The Refactor

### Keep

- policy tests as invariant tests
- retrieval tests as stage-worker tests

### Add

- control-layer end-to-end tests
- blocked-path tests
- retrieval-not-required tests
- evidence-insufficient tests
- response-mode selection tests

### Shift emphasis

Move the highest-level confidence from subsystem tests to orchestration-run tests.

The key question should become:

- does the system choose and execute the right run path?

not only:

- did policy/retrieval/response modules each behave locally?

---

## Final Recommendation

Proceed with a control-layer-first refactor.

Do not start by rewriting retrieval again. Do not start by expanding response contract machinery. Do not start by introducing more orchestration helper layers.

Start by introducing one visible orchestration entry point and making all existing modules subordinate to it.

If the refactor is successful, the system should become easier to explain in one paragraph:

> The control layer evaluates the user request against stage and source policy, decides whether grounded evidence is needed, invokes retrieval as one stage when necessary, checks whether the resulting context is sufficient, and then builds the allowed response form while logging the full decision path.

That is the target shape.
