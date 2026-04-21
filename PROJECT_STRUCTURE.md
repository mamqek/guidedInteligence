# Project Structure

This repository is building the Guided Intelligence System as a policy-guided orchestration platform. The core rule is that policy, stages, sources, response contracts, and logs stay framework-independent before any runtime shell or RAG implementation is added.

## Current Structure

```text
guidedInteligence/
  AGENTS.md
  PROJECT_STRUCTURE.md
  orchestration_build_plan.md
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

## Near-Term Additions

The next planned step is a local end-to-end harness with no framework dependency. It should create a `ConversationState`, call `V1PolicyEngine`, use stub retrieval evidence, build a response payload, and emit structured log events.

Later additions should follow the original build plan:

- `experiments/`: local harnesses, scenarios, and fixtures.
- `services/retrieval/`: ingestion, retrieval, reranking, and context building implementations.
- `services/models/`: one constrained model path after the deterministic harness works.
- `runtime/openswe/`: Open SWE graph shell only after the core contract proves stable.
- `tests/`: focused checks for policy, transitions, retrieval stubs, and runtime mapping.

## Boundary Rules

- Keep framework-specific code out of `core/`.
- Keep policy decisions in `core/policy.py` or later core policy modules, not in runtime glue.
- Keep source categories explicit and tied to `source_policy.py`.
- Keep violations explicit and loggable through `PolicyViolation`.
- Add `DESIGN_DECISION_REQUIRED` comments only when implementation would otherwise require guessing.
