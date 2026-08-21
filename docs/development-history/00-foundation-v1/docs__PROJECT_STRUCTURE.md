# Project Structure

This repository is building the Guided Intelligence System as a policy-guided orchestration platform. The core rule is that policy, stages, sources, response contracts, and logs stay framework-independent before any runtime shell or RAG implementation is added.

## Current Structure

```text
guidedInteligence/
  AGENTS.md
  PROJECT_STRUCTURE.md
  orchestration_build_plan.md
  step4_openswe_fit_spike.md
  step3_harness_scenarios.md
  step3_harness_scenarios.py
  v1_boundaries.md

  core/
    __init__.py
    logging_schema.py
    models.py
    policy.py
    response_contracts.py
    source_policy.py
    stages.py
    transitions.py
    violations.py

  services/
    __init__.py
    logging/
      __init__.py
      store.py
    retrieval/
      __init__.py
      contracts.py
```

## Documentation Files

- `orchestration_build_plan.md`: broad implementation roadmap from boundaries through Open SWE validation.
- `v1_boundaries.md`: frozen v1 behavior, allowed stages, allowed sources, policy violations, logging requirements, and exclusions.
- `step3_harness_scenarios.md`: scenario and behavior specification for the local framework-free Step 3 harness.
- `step3_harness_scenarios.py`: executable scenario fixture skeleton for the future local harness.
- `step4_openswe_fit_spike.md`: theoretical Step 4 mapping of the current orchestration contract into a custom LangGraph graph deployed inside or alongside Open SWE infrastructure.
- `AGENTS.md`: project-local agent memory, including the NotebookLM source to consult when local context is insufficient.
- `PROJECT_STRUCTURE.md`: central map of the repository structure and ownership boundaries.

## Core Package

The `core/` package owns the orchestration language. It must remain independent from Open SWE, MCP, model SDKs, vector databases, web frameworks, and UI code.

- `models.py`: shared dataclasses and enums for conversation state, user intent, evidence, and policy decisions.
- `stages.py`: the canonical v1 stage sequence, currently `explain -> ask -> hint`.
- `transitions.py`: allowed movements between stages and transition validation.
- `source_policy.py`: source categories that may ground v1 responses.
- `violations.py`: explicit policy violation types and violation records.
- `policy.py`: policy engine interface and the first deterministic v1 policy implementation.
- `response_contracts.py`: response templates, structural requirements, response payloads, and builder interface.
- `logging_schema.py`: minimum log event types and serializable event object.

## Services Package

The `services/` package defines replaceable service interfaces. Implementations can be added later without changing the core contract.

- `services/retrieval/contracts.py`: retrieval planning and evidence retrieval interface.
- `services/logging/store.py`: append/list interface for audit and replay storage.

## Step 3 Harness Artifacts

The Step 3 scenario artifacts are now present at the repository root. They define the local end-to-end harness behavior without adding framework dependencies. The future harness should create a `ConversationState`, call `V1PolicyEngine`, use stub retrieval evidence, build a response payload, and emit structured log events.

The Python scenario skeleton is data-only: it defines expected policy fields, expected log event sequences, and static evidence fixtures. It does not implement real retrieval, real model calls, Open SWE integration, MCP, UI, or automated task completion.

## Near-Term Additions

Later additions should follow the original build plan:

- `experiments/`: local harnesses, scenarios, and fixtures.
- `services/retrieval/`: ingestion, retrieval, reranking, and context building implementations.
- `services/models/`: one constrained model path after the deterministic harness works.
- `runtime/openswe/`: custom LangGraph wrapper around core contracts, using Open SWE for deployment, sandboxing, invocation, thread/run infrastructure, tracing, and optional middleware. It must not contain stage-policy rules.
- `tests/`: focused checks for policy, transitions, retrieval stubs, and runtime mapping.

## Boundary Rules

- Keep framework-specific code out of `core/`.
- Keep policy decisions in `core/policy.py` or later core policy modules, not in runtime glue.
- Keep future Open SWE/Deep Agents prompts from owning stage policy; runtime code should call the policy engine and branch from its decision.
- Keep source categories explicit and tied to `source_policy.py`.
- Keep violations explicit and loggable through `PolicyViolation`.
- Add `DESIGN_DECISION_REQUIRED` comments only when implementation would otherwise require guessing.
