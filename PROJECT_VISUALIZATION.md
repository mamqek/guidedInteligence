# Project Visualization

This file shows the current Guided Intelligence project structure as Mermaid diagrams. It is based on the local repository state, not on a live CodeGraphContext MCP connection.

## MCP Graph Tool Status

The NotebookLM source about a code graph MCP server is available as reference material in the project notebook, but this chat session does not currently expose that server as a callable MCP tool. The available callable tools here are NotebookLM, GitHub, and shadcn-related tools.

If a code graph MCP server is installed and exposed to this chat later, this document can be regenerated from that live graph instead of from local file inspection.

## Repository Map

```mermaid
flowchart TD
    repo["guidedInteligence/"]

    repo --> docs["Project docs"]
    docs --> agents["AGENTS.md<br/>NotebookLM project memory"]
    docs --> buildPlan["orchestration_build_plan.md<br/>Full roadmap"]
    docs --> boundaries["v1_boundaries.md<br/>Frozen v1 scope"]
    docs --> structure["PROJECT_STRUCTURE.md<br/>Central structure map"]
    docs --> visualization["PROJECT_VISUALIZATION.md<br/>Current diagrams"]

    repo --> core["core/<br/>Framework-independent orchestration contracts"]
    core --> models["models.py<br/>State, intent, evidence, decisions"]
    core --> stages["stages.py<br/>explain -> ask -> hint"]
    core --> transitions["transitions.py<br/>Allowed stage movement"]
    core --> sourcePolicy["source_policy.py<br/>Allowed source categories"]
    core --> violations["violations.py<br/>Explicit policy failures"]
    core --> policy["policy.py<br/>PolicyEngine + V1PolicyEngine"]
    core --> responseContracts["response_contracts.py<br/>Response templates + payloads"]
    core --> loggingSchema["logging_schema.py<br/>Audit event schema"]

    repo --> services["services/<br/>Replaceable service interfaces"]
    services --> retrieval["retrieval/contracts.py<br/>RetrievalPlan + RetrievalService"]
    services --> loggingStore["logging/store.py<br/>LoggingStore protocol"]
```

## Core Dependency Graph

```mermaid
flowchart LR
    stages["core.stages<br/>ResponseStage"]
    sourcePolicy["core.source_policy<br/>SourceCategory"]
    violations["core.violations<br/>PolicyViolation"]
    models["core.models<br/>ConversationState<br/>EvidenceItem<br/>OrchestratorDecision"]
    transitions["core.transitions<br/>can_transition"]
    policy["core.policy<br/>V1PolicyEngine"]
    response["core.response_contracts<br/>ResponseContract<br/>ResponsePayload"]
    loggingSchema["core.logging_schema<br/>LogEvent"]

    stages --> models
    sourcePolicy --> models
    violations --> models

    stages --> transitions
    transitions --> policy
    models --> policy
    sourcePolicy --> policy
    violations --> policy

    stages --> response
    models --> response
    violations --> response

    loggingSchema -. "independent audit schema" .-> policy
    loggingSchema -. "used by future stores" .-> response
```

## Service Boundary Graph

```mermaid
flowchart TD
    coreContracts["core contracts"]
    retrievalContracts["services.retrieval.contracts<br/>plan() + retrieve()"]
    loggingContracts["services.logging.store<br/>append() + list_events()"]

    futureHarness["future experiments/harness.py"]
    futureRuntime["future runtime/openswe/*"]
    futureRag["future retrieval implementation"]
    futureLogStore["future logging implementation"]

    coreContracts --> retrievalContracts
    coreContracts --> loggingContracts

    futureHarness --> coreContracts
    futureHarness --> retrievalContracts
    futureHarness --> loggingContracts

    futureRuntime --> coreContracts
    futureRuntime --> retrievalContracts
    futureRuntime --> loggingContracts

    futureRag -. implements .-> retrievalContracts
    futureLogStore -. implements .-> loggingContracts
```

## V1 Decision Flow

```mermaid
flowchart TD
    input["User input"] --> state["ConversationState"]
    state --> policy["V1PolicyEngine.decide(state)"]

    policy --> intent{"Intent"}
    intent -->|"direct solution request"| violation["PolicyViolation<br/>direct_solution_request"]
    violation --> redirect["Response template<br/>violation_redirect"]

    intent -->|"understand code / follow-up"| stage{"Current stage"}
    stage -->|"explain"| explain["Response template<br/>explanation"]
    stage -->|"ask"| ask["Response template<br/>reasoning_question"]
    stage -->|"hint"| hint["Response template<br/>hint"]

    explain --> nextAsk["Next stage: ask"]
    ask --> nextHint["Next stage: hint"]
    hint --> stayHint["Next stage: hint"]

    policy --> retrieval{"Evidence present?"}
    retrieval -->|"no"| retrievalRequired["retrieval_required = true"]
    retrieval -->|"yes"| retrievalNotRequired["retrieval_required = false"]
```

