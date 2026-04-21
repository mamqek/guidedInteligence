# Guided Intelligence System Build Plan

## Intended system structure

The system should be built as a **policy-guided orchestration platform** whose main purpose is to control how assistance is produced, not just to connect a model to repository data. The core idea from the proposal is that the system must explicitly govern **which sources may be used, in what order they are consulted, and which response stage is currently allowed**, while logging those decisions for later analysis and reproducibility. The proposal also makes modularity, replaceability, and observability central design constraints, which means no framework or tool should become the conceptual center of the system. fileciteturn3file1

### High-level components

- **Open SWE runtime shell**: Runs the workflow graph, sandboxing, and execution environment, but should not contain the actual policy logic.
- **Core orchestration logic**: The single source of truth for stages, transition rules, source restrictions, response rules, and policy decisions.
- **RAG layer**: Handles ingestion, retrieval, reranking, and evidence packaging across repository artifacts such as code, docs, issues, and pull requests, which the proposal explicitly names as relevant sources. fileciteturn3file1
- **Model layer**: Provides constrained model calls for classification and response generation, while keeping the model as a controlled component rather than the decision-maker.
- **Response enforcement layer**: Ensures that outputs follow the allowed stage and template, such as explanation-first behavior or redirection of direct-solution requests.
- **Logging and replay layer**: Captures retrieval decisions, prompts, model settings, outputs, and policy events, because reproducibility is one of the core requirements in the proposal. fileciteturn3file1
- **Evaluation instrumentation**: Stores traces and structured outputs in a way that later supports the explanation-quality rubric, reasoning analysis, and overreliance analysis described in the proposal. fileciteturn3file1

### Intended repository structure

```text
repo/
  core/
    models.py
    policy.py
    transitions.py
    stages.py
    source_policy.py
    response_contracts.py
    violations.py
    logging_schema.py

  services/
    retrieval/
      ingest.py
      retrieve.py
      rerank.py
      context_builder.py
    models/
      gateway.py
      prompts.py
    logging/
      store.py
      replay.py

  runtime/
    openswe/
      graph.py
      nodes.py
      state_mapping.py
      hooks.py

  experiments/
    harness.py
    scenarios.py
    fixtures/

  tests/
    core/
    retrieval/
    runtime/
```

### Main internal types and responsibilities

- **UserIntent**: Represents what the user is currently trying to do, such as understanding code, asking for a direct solution, or making a follow-up request, so the policy layer can decide whether the next action is allowed.
- **EvidenceItem**: Represents one retrieved piece of grounded context, including its source type, identifier, ranking, and snippet, so all downstream decisions can remain tied to concrete project artifacts.
- **OrchestratorDecision**: Represents the outcome of the policy layer for a given state, including whether the action is allowed, what the next stage is, whether retrieval is needed, and which response template should be used.
- **PolicyViolation**: Represents a failure or forbidden action, such as asking for a direct solution in the wrong stage or attempting to rely on a disallowed source, so violations are explicit and loggable rather than being handled implicitly.

### RAG responsibilities

- **Ingestion**: Parse and normalize project artifacts into indexed units that can later be retrieved consistently.
- **Retrieval planning**: Decide which source categories should be searched first based on the current stage and policy rules.
- **Primary retrieval**: Fetch candidate evidence from the allowed sources in the required order.
- **Reranking**: Reorder candidates so the evidence most useful for explanation or hinting appears first, while keeping source provenance intact.
- **Context building**: Assemble a bounded, structured evidence package that is stage-aware and suitable for the current model call.

https://arxiv.org/html/2509.16112v1

### Out of scope for this first implementation phase, but important for later reuse

These should not be implemented yet, but the architecture should remain reusable with them in mind:

- **MCP adapter layer**: The core logic should remain host-agnostic so it can later be exposed as MCP tools without being rewritten.
- **External API wrappers for Codex or Claude**: Later compatibility should be possible by placing thin adapters around the same core types and services.
- **Full web UI polish**: A minimal interface may come later, but the first phase should prioritize the orchestration loop and evidence flow.
- **Expanded model portfolio**: The architecture should allow multiple models later, but the first version should keep the model path minimal.

---

## Implementation plan

### 1. Freeze the v1 system boundaries

- **Define the exact v1 user flow**: Write down the supported interaction path for the first version so you are not building generic infrastructure before the actual behavior is fixed.
- **Fix the initial response stages**: Lock the first stage sequence, such as `explain -> ask -> hint -> redirect`, because many later design decisions depend on these stage boundaries.
- **Define allowed source categories**: Decide which artifacts count as valid grounded evidence in v1, for example code, docs, issues, and pull requests, since the proposal explicitly expects project-specific artifacts to drive assistance. fileciteturn3file1
- **Define what counts as a policy violation**: Make forbidden behavior explicit early, such as direct-solution requests, unsupported source usage, or stage skipping, so these rules do not stay vague.
- **List required logs**: Specify the minimum events that must be recorded, such as stage changes, retrieval plans, evidence IDs, prompts, outputs, and violations, because reproducibility is a first-class requirement. fileciteturn3file1
- **State v1 exclusions clearly**: Mark things like MCP exposure, multi-model orchestration, and polished UI as intentionally out of scope so they do not distort early architectural choices.

### 2. Define the internal core contract before framework code

- **Create core state types**: Implement the internal models such as `ConversationState`, `UserIntent`, `EvidenceItem`, `OrchestratorDecision`, and `PolicyViolation`, so the system has its own language before any framework-specific types appear.
- **Create stage and transition types**: Represent stages and possible transitions explicitly so the workflow is governed by code-level rules rather than being buried inside prompts.
- **Define the policy engine interface**: Add a single entry point such as `PolicyEngine.decide(state) -> OrchestratorDecision`, which becomes the main control surface for the orchestration logic.
- **Define the retrieval service interface**: Add a minimal interface for retrieval planning and candidate retrieval so the RAG layer stays modular and can later be swapped or extended.
- **Define the response builder interface**: Specify how grounded evidence and a policy decision become a scaffolded response payload, so output generation is separated from policy selection.
- **Define the logging interface**: Add a clear way to record structured events, because later evaluation and reproducibility depend on logs being systematic rather than ad hoc. fileciteturn3file1

### 3. Build a local end-to-end harness with no framework dependency

- **Create a minimal harness script**: Build a small Python runner that creates a `ConversationState`, calls the policy engine, runs retrieval stubs, and produces a response, so you can validate the architecture without committing to runtime infrastructure yet.
- **Stub the RAG flow first**: Use fake or static evidence items initially so you can verify the orchestration flow before spending time on indexing and retrieval quality.
- **Stub the model path first**: Return canned or deterministic outputs at this stage so you can test whether the response structure and stage flow are correct independent of model quality.
- **Exercise the main interaction paths**: Run simple scenarios such as explanation requests, direct-solution requests, and follow-up questions, so you can detect weak abstractions before frameworks are involved.
- **Refine the core types if needed**: Treat awkwardness here as a warning signal, because if the interface is clumsy in the harness it will become worse once Open SWE is added.

### 4. Do a strict Open SWE fit spike before deeper integration

- **Map the stage flow to a tiny graph**: Represent only a minimal path like policy -> retrieval -> response -> redirect, so you can see whether your desired control flow fits Open SWE naturally.
- **Check whether your own state can stay central**: Verify that your internal state types can be mapped cleanly into Open SWE graph state without framework types leaking into the core.
- **Check policy injection points**: Confirm that the policy engine can run exactly where you need it, rather than forcing you to bury important decisions inside framework-specific callbacks.
- **Check logging feasibility**: Make sure you can record the control points you care about, such as transitions, retrieval plans, and violations, because poor observability would make the runtime a bad fit. fileciteturn3file1
- **Stop if the fit feels forced**: Treat this as a validation spike, not a commitment phase, so you can reject the runtime early if it requires awkward compromises.

### 5. Commit to Open SWE as the runtime shell

- **Implement the graph around your own policy core**: Build the actual runtime graph only after the fit spike works, so Open SWE becomes the execution shell rather than the owner of your system logic.
- **Keep decisions in your code, not the runtime defaults**: Nodes should call your `PolicyEngine` and related services, instead of gradually shifting important logic into framework glue.
- **Use only the Open SWE capabilities you need**: Ignore extra agentic features if they do not help the thesis, because your proposal prioritizes bounded roles and replaceability over tool-centric design. fileciteturn3file1
- **Preserve a strict stage-driven flow**: Keep the graph aligned with your explicit stage machine so the runtime remains compatible with the proposal’s deterministic orchestration idea. fileciteturn3file1

### 6. Implement the first real RAG layer as a separate service

- **Build ingestion for the selected repository artifacts**: Parse code, docs, issues, and pull requests into retrievable units, because the proposal’s grounding requirement depends on project-specific artifacts rather than generic model knowledge. fileciteturn3file1
- **Implement retrieval planning**: Use the current stage and source policy to decide the order in which sources should be searched, reflecting the proposal’s requirement for explicit source priority and retrieval order. fileciteturn3file1
- **Implement candidate retrieval**: Fetch an initial pool of evidence items from the allowed source categories so the next steps can remain grounded.
- **Implement reranking**: Reorder evidence items so the most explanation-relevant candidates appear first, while preserving source provenance for later logging and citation.
- **Implement context building**: Package the top evidence into a bounded stage-aware context object so the model layer receives only what is allowed and relevant.
- **Keep RAG independent of Open SWE**: Make retrieval and context building callable as normal Python services so they remain reusable in later adapters and experiments.

### 7. Add structured logging and replay before real model complexity

- **Log state transitions**: Record how and why the system moved between stages so the control flow can later be audited.
- **Log retrieval plans and source usage**: Capture which source categories were consulted, in what order, and which evidence items were selected, since this is central to your claim of explicit context construction. fileciteturn3file1
- **Log prompts and evidence payloads**: Store the exact model inputs or stage payloads so later analysis can explain why a particular response was generated.
- **Log outputs and policy decisions**: Record both the final response and the policy decision that led to it, because the system should expose structured, analyzable behavior rather than opaque generation. fileciteturn3file1
- **Implement replay support**: Make it possible to rerun a recorded trace or inspect it step by step, since reproducibility is part of the proposal’s methodological core. fileciteturn3file1

### 8. Add one minimal real model path

- **Choose one bounded model role first**: Start with either a lightweight classifier or a single constrained response generator so you validate the orchestration before increasing model complexity.
- **Keep the model under explicit control**: Pass in only the evidence and instructions allowed by the current stage so the model remains a controlled component, as the proposal requires. fileciteturn3file1
- **Use deterministic settings where possible**: Keep temperature and related settings stable so you can observe the effect of orchestration rather than chasing avoidable variability. fileciteturn3file1
- **Verify stage-aware responses**: Check that the model output differs appropriately between explanation, follow-up, hinting, and redirection cases.
- **Do not add multiple models yet**: Delay supervisor/main-model splits until the first constrained path works reliably, because early multi-model complexity would increase scope without validating the foundation.

### 9. Validate the end-to-end v1 loop in Open SWE

- **Test the normal explanation path**: Confirm that a standard understanding request moves cleanly through policy, retrieval, response construction, and output.
- **Test direct-solution rejection or redirection**: Verify that forbidden requests trigger the intended response path rather than slipping through as partial answers.
- **Test follow-up and hint progression**: Check that later-stage interactions only happen when the prior stage conditions are satisfied.
- **Test insufficient-evidence behavior**: Make sure the system reacts sensibly when allowed retrieval does not provide enough grounded context, because that is a realistic constraint in onboarding scenarios.
- **Test source restriction enforcement**: Confirm that the system does not rely on disallowed source categories or unsupported context even when that would be convenient.
- **Freeze the v1 base after this point**: Once these paths work, treat the architecture as the stable foundation and postpone new scope until the base is documented and understood.

---

## After step 9: not in scope now, but the base should remain reusable for it

- **MCP exposure**: Later expose selected policy-aware capabilities through an MCP adapter built around the same internal types and services.
- **Codex or Claude connectivity**: Later connect host agents to the same core through API or MCP-facing adapters, without moving orchestration rules into those connectors.
- **Web interface improvements**: Later add a cleaner participant-facing interface once the orchestration base is stable.
- **Broader evaluation support**: Later add study-specific dashboards, export tools, and richer analytics once the end-to-end runtime is already validated.
