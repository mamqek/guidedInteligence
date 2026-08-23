# Seeded Agentic Evidence Retrieval

## Status

- State: proposed implementation and experiment plan; no behavior has been changed.
- Scope: a new retrieval mode that preserves the current obligation-based Qdrant discovery and CodeGraph grounding,
  then replaces initial owner comparison, qualification, controller rounds, evidence recovery, island scheduling, and
  final evidence selection with one stateful evidence-navigation agent.
- Primary experiment cases: `pandas-dev-pandas-10068`, `microsoft-TypeScript-35468`, and `vuejs-vue-10803`.
- Execution protocol: follow
  [`../incremental-experiment-execution-protocol.md`](../incremental-experiment-execution-protocol.md).
- Related design: [`codex_tool_using_agent_runtime.md`](codex_tool_using_agent_runtime.md). That note proposes a
  Codex-owned search loop starting with generic local tools. This plan has a different boundary: native Qdrant and
  CodeGraph discovery remain mandatory inputs, the model provider is replaceable, and the agent is not restricted to
  the initial retrieved paths or snippets.

## Executive Decision

Implement a separate seeded agentic retrieval experiment with this boundary:

```text
KEEP
  request analysis and repository evidence obligations
  -> Qdrant dense+sparse/hybrid discovery per repository obligation
  -> deterministic file grouping and retention of held alternatives
  -> CodeGraph range resolution without choosing one canonical owner
  -> compact initial-lead package

REPLACE
  initial owner comparison
  -> source-disclosure/qualification rounds
  -> promoted/deferred/dormant state transitions
  -> evidence islands and action catalogue/scheduler
  -> verified-lead, maturation, bridge, and resurrection flows
  -> coverage calls used to authorize the next action
  -> final evidence-selection LLM

WITH
  one persistent agent state
  -> inspect a promising lead or any repository location
  -> follow CodeGraph/source relationships
  -> search within a file or anywhere in the repository
  -> update grounded findings and unresolved questions
  -> repeat until sufficient, no-gain, or budget exhaustion
  -> emit final evidence and explicit uncertainty
  -> deterministic citation/scope validation
```

The initial Qdrant output is orientation, not an eligibility boundary. Qdrant rank may influence which lead the agent
inspects first, but it must never determine which files, nodes, snippets, or claims are allowed in final evidence.
Evidence discovered later through graph traversal, adjacent source inspection, exact search, lexical search, or a new
semantic query is first-class evidence.

This proposal is plausible, not pre-validated. Existing results establish that useful evidence is often present before
the current downstream decision stages and is sometimes lost or made expensive afterward. They do not establish that
an agent will reliably make better decisions, especially with a small local model. The experiment must prove that.

## Research Basis And Limits Of The Evidence

This architecture is an inference from several established patterns:

- [RepoCoder](https://aclanthology.org/2023.emnlp-main.151.pdf) combines an off-the-shelf repository retriever with an
  iterative retrieval/generation loop and reports consistent gains over one-shot repository RAG. Its task is code
  completion, not issue-evidence selection, so it supports the iterative boundary but does not validate this exact
  pipeline.
- [IRCoT](https://aclanthology.org/2023.acl-long.557.pdf) demonstrates the general multi-hop principle that what should
  be retrieved next depends on what earlier evidence established. Its experiments are knowledge-intensive QA rather
  than code retrieval.
- [SWE-agent](https://arxiv.org/abs/2405.15793) and its
  [Agent-Computer Interface guidance](https://github.com/SWE-agent/SWE-agent/blob/main/docs/background/aci.md) show that
  coding-agent behavior depends materially on concise, bounded search and file-view tools. The guidance favors small
  file windows and succinct search results rather than dumping broad command output into model context.
- [Agentless](https://openreview.net/pdf?id=dw9VUsSHGB) demonstrates that repository work can be separated into an
  initial hierarchical localization phase and a later reasoning/repair phase. This supports keeping a strong
  localization stage instead of requiring the agent to begin from an empty repository view.
- The OpenAI Responses API supports custom function tools and either server-managed conversation state or explicit
  continuation through a prior response. These are implementation conveniences, not the source of agent behavior;
  the application must still own tool execution, state validation, budgets, and durable traces. See the
  [official Responses API reference](https://developers.openai.com/api/reference/cli/resources/responses/methods/create).

None of these sources proves that the proposed agent will outperform the current workspace retriever on CodeRepoQA.
The project benchmark and boundary traces remain the acceptance authority.

## Observed Repository Problem

The current retrieval path begins with useful generic machinery:

1. Global request analysis emits repository evidence obligations.
2. `qualification_first_retrieval.py` runs `qdrant_hybrid_search` once per repository obligation.
3. Each search requests `MAX_FOCUSED_RESULTS`, currently 12.
4. Dense, sparse, and hybrid channel results are retained in trace data.
5. Results are grouped by file, with representatives and held same-file alternatives.
6. Raw ranges are resolved to CodeGraph nodes.

With four repository obligations, 12 fused representatives per obligation is often described as approximately 48
initial hits. That is only a rough description. Held alternatives, repeated obligation views, channel-specific chunks,
and multiple CodeGraph owners can produce a much larger downstream owner universe. The current open-question record
reports runs resolving 172 and 192 raw ranges and comparing roughly 220-235 owners. The new agent must therefore have
access to the complete lead store while receiving only a bounded projection of that store in any one model call.

The problematic boundary begins when the pipeline attempts to decide, before iterative exploration, which resolved
owners deserve complete source disclosure and qualification. The subsequent system then needs explicit machinery for
deferred observations, owner continuation, new-island search, relationship expansion, verified leads, maturation,
bridge continuation, evidence-island scheduling, and final evidence consolidation.

Concrete evidence:

- `pandas-dev-pandas-10068` run `run-20260816T175628Z` retrieved a relevant `Series::_binop` CodeGraph node, but the
  raw range began on the preceding method's last line. Contextual disclosure chose `Series::append`, qualification saw
  the wrong owner, and the useful lead never became an island. The measured repair required a special owner-resolution
  preference and later qualification. See
  [`qualification_first_retrieval_controller.md`](qualification_first_retrieval_controller.md), the section around
  the cross-language beam-4 verification and measured repair.
- Open question `IOC-1` records that complete initial owner comparison can consume more than 20,000 retrieval tokens
  while stable owner-quality acceptance remains unresolved.
- Open questions `VL-1` through `VL-3` describe valid continuation work that can be stranded by lead-execution caps,
  final-round timing, or eligibility rules.
- Open question `ISL-1` describes a real mechanism split across islands because an unobserved connector was absent
  from the candidate pool. The current repair adds a specialized one-connector path. A navigation agent should instead
  be able to follow the connector as ordinary exploratory work.

These observations justify testing a different downstream controller. They do not justify changing Qdrant query
construction, Qdrant fusion, the index, obligation generation, or CodeGraph adapters in the same experiment.

## Goals

1. Preserve the useful initial semantic/lexical search direction produced by Qdrant.
2. Preserve every initial lead until the run ends; do not permanently reject a lead before iterative inspection.
3. Let the model inspect complete source, adjacent code, graph neighbors, and entirely new repository locations.
4. Replace specialized action and recovery classes with a small generic tool interface.
5. Maintain explicit, durable context across model calls without replaying the full transcript.
6. Support both API-hosted and local models through one provider-neutral decision contract.
7. Produce exact file/range evidence that the existing response-generation system can consume during migration.
8. Fail explicitly when the configured LLM or required tool fails; do not fall back to deterministic surrogate
   reasoning.
9. Preserve full traceability from every final item to its first discovery source and every later inspection step.

## Non-Goals

- Do not replace request analysis or evidence-obligation generation in this experiment.
- Do not change Qdrant embeddings, sparse indexing, RRF/fusion, or initial query construction.
- Do not require final evidence to come from an initial Qdrant path.
- Do not let the agent edit repository files, execute arbitrary shell commands, or inspect forbidden benchmark data.
- Do not merge response generation or the `EXPLAIN`/`ASK`/`HINT` teaching policy into retrieval.
- Do not reproduce current workspace roles, qualification dispositions, evidence islands, or action-purpose enums inside
  the agent prompt under different names.
- Do not delete the current workspace flow until the replacement has passed the required comparisons.
- Do not treat one favorable stochastic run as acceptance.

## New Module Boundary

The agent should be implemented outside the existing workspace execution-flow class hierarchy:

```text
services/retrieval/agentic/
  contracts.py
  runtime.py
  state.py
  context.py
  budgets.py
  tracing.py

  providers/
    base.py
    openai_compatible.py
    local.py

  tools/
    contracts.py
    registry.py
    inspect_lead.py
    open_source.py
    graph_neighbors.py
    exact_search.py
    lexical_search.py
    semantic_search.py

  validation/
    scope.py
    citations.py
    final_report.py

  adapters/
    workspace_seed_builder.py
    guided_intelligence.py
```

The exact directory name can change during implementation if repository conventions require it. The responsibility
boundary may not: agent contracts must not import or encode `DiscoveryObservation`, `QualificationDecision`,
`EvidenceIsland`, `RetrievalAction`, or controller scheduling types.

The temporary Guided Intelligence adapter may import the existing `EvidenceItem` and `RetrievalResult` types. No other
agent module may depend on those compatibility types.

## Independent Contracts

### Agent request

```python
@dataclass(frozen=True)
class AgentRetrievalRequest:
    request_id: str
    question: str
    workspace_root: str
    repository_revision: str | None
    obligations: tuple[AgentObligation, ...]
    initial_leads: tuple[InitialLead, ...]
    scope: AgentScope
    budget: AgentBudget
    model: AgentModelConfig
```

`AgentObligation` is a copy-at-the-boundary representation containing only an ID, description, source expectation,
anchors, and whether repository evidence is required. It must not expose current controller roles or action hints.

### Initial lead

```python
@dataclass(frozen=True)
class InitialLead:
    id: str
    obligation_ids: tuple[str, ...]
    path: str
    raw_line_start: int
    raw_line_end: int
    preview: str
    artifact_kind: str
    retrieval_views: tuple[RetrievalView, ...]
    structural_handles: tuple[StructuralHandle, ...]
```

```python
@dataclass(frozen=True)
class RetrievalView:
    channel: str                 # dense, sparse, hybrid, exact anchor, held alternative
    rank: int | None
    score: float | None
    query_id: str
    obligation_id: str
```

```python
@dataclass(frozen=True)
class StructuralHandle:
    node_id: str
    symbol: str
    kind: str
    path: str
    line_start: int
    line_end: int
```

All plausible narrow CodeGraph handles remain attached. The seed builder must not choose one owner merely because a
raw chunk begins or ends on an adjacent declaration.

### Agent result

```python
@dataclass(frozen=True)
class AgentRetrievalReport:
    request_id: str
    status: str                  # complete, partial, failed
    sufficient: bool
    stop_reason: str
    findings: tuple[GroundedFinding, ...]
    evidence: tuple[AgentEvidence, ...]
    unresolved_questions: tuple[str, ...]
    execution: AgentExecutionSummary
```

```python
@dataclass(frozen=True)
class AgentEvidence:
    id: str
    path: str
    line_start: int
    line_end: int
    symbol: str | None
    source_text: str
    artifact_kind: str
    claim_ids: tuple[str, ...]
    discovery_origin: str        # initial lead, graph, exact, lexical, semantic, adjacent source
    parent_artifact_ids: tuple[str, ...]
```

Final eligibility is independent of `discovery_origin`. A graph-discovered or newly searched artifact can outrank and
replace every initial Qdrant lead.

## Persistent Agent State And Model Context

The durable agent state is the central component. The API is not the agent. The application becomes an agent runtime
by storing state, executing requested tools, validating observations, and calling the model again with an updated
working context.

```python
@dataclass
class AgentState:
    request: AgentRetrievalRequest
    artifact_store: dict[str, ArtifactRecord]
    initial_lead_ids: tuple[str, ...]
    inspected_artifact_ids: set[str]
    accepted_evidence_ids: set[str]
    provisional_finding_ids: set[str]
    relationships: list[RelationshipRecord]
    hypotheses: list[Hypothesis]
    open_questions: list[OpenQuestion]
    attempted_operations: set[str]
    recent_observation_ids: list[str]
    usage: AgentUsage
    iteration: int
```

The full state is stored locally in run artifacts. A bounded `WorkingContext` is constructed for each model call:

```python
@dataclass(frozen=True)
class WorkingContext:
    question: str
    obligations: tuple[AgentObligation, ...]
    repository_summary: str
    accepted_findings: tuple[FindingSummary, ...]
    open_questions: tuple[OpenQuestion, ...]
    promising_leads: tuple[ArtifactSummary, ...]
    recent_observations: tuple[ArtifactSummary, ...]
    attempted_operation_summary: tuple[str, ...]
    remaining_budget: AgentBudgetRemaining
```

Do not treat a provider-side conversation transcript as the durable source of truth. An API implementation may use a
conversation ID or prior-response ID for efficiency, but the local structured `AgentState` must be sufficient to
reconstruct a call after a retry or provider change. This also makes API and local-model execution comparable.

Do not persist or require hidden chain-of-thought. Persist explicit hypotheses, facts, gaps, selected evidence,
relationships, and tool outcomes. These fields are auditable and can be safely compacted.

### Context projection policy

Every model call should include:

1. The unchanged question and repository obligations.
2. The current grounded findings with evidence IDs, not repeated full source unless needed.
3. The most important unresolved questions.
4. A bounded set of promising uninspected leads.
5. The latest tool observations.
6. A compact summary of duplicate or failed operations.
7. Remaining iteration, tool, time, and token budgets.

The model must not receive all resolved owners or all source text at once. The artifact store can contain hundreds of
entries; the working context should normally contain tens of compact summaries and only the source windows relevant to
the current decision. Context selection is deterministic and based on recency, explicit model interest, obligation
coverage, initial retrieval rank, exact anchors, and relationship proximity. Initial Qdrant rank is an orientation
feature only and must decay after source inspection produces stronger evidence.

## Model Provider Contract

```python
class AgentModelProvider(Protocol):
    def decide(
        self,
        context: WorkingContext,
        tools: tuple[ToolDefinition, ...],
    ) -> AgentDecision:
        ...
```

```python
@dataclass(frozen=True)
class AgentDecision:
    kind: str                    # tool_calls, finish, fail
    tool_calls: tuple[AgentToolCall, ...]
    hypothesis_updates: tuple[HypothesisUpdate, ...]
    open_question_updates: tuple[OpenQuestionUpdate, ...]
    proposed_findings: tuple[ProposedFinding, ...]
    final_evidence_ids: tuple[str, ...]
    reason: str
```

For an API model, tool calls may use native function calling. For a local model without native tools, the same contract
can be emitted as schema-constrained JSON. The runtime behavior must remain identical: the model proposes, the runtime
validates and executes, and the model never receives direct filesystem authority.

Provider requirements:

- reliable structured output or tool calling;
- enough context for the bounded working set;
- configurable timeout and token accounting;
- explicit error propagation;
- no silent provider or deterministic fallback;
- provider/model identity recorded in every run.

Local-model feasibility is an empirical question. The architecture supports a local provider, but a small model may
not navigate competing leads or stop reliably. Local and API models must be evaluated separately rather than assumed
equivalent.

## Tool Contracts

The first accepted implementation should expose a small tool set. Tools return bounded structured observations and
never raw unbounded command output.

### `inspect_lead`

```text
inspect_lead(lead_id, structural_handle_id?, view)
```

Views:

- `raw_chunk`: exact original Qdrant range;
- `structural_owner`: complete bounded CodeGraph owner;
- `surrounding_source`: bounded lines before and after the range;
- `file_outline`: compact declarations for the file.

If several structural handles overlap, the model selects which to inspect. The tool may return a compact list of all
handles, but it must not silently canonicalize them to one owner.

### `open_source`

```text
open_source(path, line_start, line_end)
```

This permits arbitrary in-scope repository inspection, including files and ranges never returned by Qdrant. Enforce:

- repository-relative normalized paths;
- excluded-path policy;
- a maximum line and character window;
- exact returned line numbers;
- artifact-kind metadata.

### `graph_neighbors`

```text
graph_neighbors(node_id, direction, edge_kinds?, target_terms?, limit)
```

Return compact node handles and represented edges. The result is navigation information, not automatically accepted
evidence. The agent may inspect any returned node through `open_source` or a node-oriented view.

### `exact_search`

```text
exact_search(query, paths?, file_types?, limit)
```

Use bounded literal repository search for identifiers, diagnostics, file names, and exact strings. The tool must cap
work and output at the producer, not by piping an unrestricted `rg` process into a downstream first-N consumer. Record
effective path exclusions and return file/range matches rather than full files.

### `lexical_search`

```text
lexical_search(query, paths?, limit)
```

Reuse the existing BM25 infrastructure where practical. This is an escape hatch for reformulated queries and is not
restricted to initial-lead files.

### `semantic_search`

```text
semantic_search(query, paths?, source_kind?, limit)
```

Reuse the existing Qdrant backend with a new query generated from grounded discoveries. It may search the full allowed
repository. New results enter the artifact store with `discovery_origin=semantic`, not `initial_lead`.

### No arbitrary shell tool in the first experiment

The first retrieval-only agent does not need arbitrary shell access. Generic shell access would make scope, cost,
output bounds, and replay much harder to validate. Add a new tool only after traces demonstrate a missing capability
that cannot be represented safely by the tools above.

## Lead Versus Evidence Semantics

The runtime distinguishes leads from evidence:

```text
lead
  a location worth inspecting; it may be based on rank, an exact name, or a graph relation

evidence
  source text that directly supports a named finding in the final report
```

An initial Qdrant hit begins as a lead. It is not promoted or rejected by a separate qualification model. After
inspection, the agent may mark it:

- `supports_finding`;
- `navigation_only`;
- `contradicts_hypothesis`;
- `not_currently_relevant`;
- `uninspected`.

These states are reversible except for factual validation failures such as an invalid path or stale range. A
`not_currently_relevant` lead remains in the artifact store and can become useful after another result exposes a
relationship. This removes the need for evidence resurrection.

## Agent Loop

```python
def run_agent(request: AgentRetrievalRequest) -> AgentRetrievalReport:
    state = initialize_state(request)

    while state.usage.within_budget():
        context = build_working_context(state)
        decision = provider.decide(context, tool_registry.definitions())
        validate_decision(decision, state)

        apply_explicit_state_updates(state, decision)

        if decision.kind == "finish":
            report = build_report(state, decision)
            return validate_final_report(report, request.scope)

        if decision.kind == "fail":
            return build_explicit_failure_or_partial_report(state, decision.reason)

        calls = deduplicate_and_budget_tool_calls(decision.tool_calls, state)
        if not calls:
            return build_partial_report(state, "no_executable_tool_call")

        observations = execute_tool_calls(calls)
        validate_observations(observations, request.scope)
        update_artifact_store(state, calls, observations)
        update_progress_counters(state)

        if repeated_no_gain(state):
            return build_partial_report(state, "no_evidence_gain")

    return build_partial_report(state, "budget_exhausted")
```

### Iteration zero

The initial working context contains:

- the question and obligations;
- a compact file-level summary of the initial Qdrant leads;
- exact prompt anchors confirmed by CodeGraph;
- a bounded selection of the highest-value structural handles;
- no prequalified or preselected owner.

The agent normally inspects several promising leads first, but it may immediately issue an exact or repository-wide
search when the prompt contains a concrete identifier absent from the lead manifest.

### Later iterations

Identifiers, calls, imports, assignments, configuration keys, and diagnostic strings discovered in source become new
navigation anchors. The agent chooses whether to:

- inspect another initial lead;
- inspect adjacent or enclosing code;
- follow a graph relationship;
- open a newly discovered file;
- run an exact, lexical, or semantic search over any allowed repository path;
- revise a hypothesis;
- finish with complete or partial evidence.

The agent still has iterations. What disappears is the current fixed round semantics, action subclasses, per-action
eligibility rules, special reserved slots, island beams, and recovery-specific control paths.

## No Initial-Lead Confinement

The following invariants make the user's clarification enforceable rather than prompt-only guidance:

1. `open_source` accepts any normalized allowed repository path.
2. `graph_neighbors` can introduce nodes and files absent from all initial Qdrant results.
3. Exact, lexical, and semantic search default to the full allowed repository unless the model explicitly narrows them.
4. `AgentEvidence.discovery_origin` is provenance only; validation and final ordering do not prefer
   `initial_lead`.
5. The final report has no minimum or maximum quota for evidence originating from initial leads.
6. Traces record `first_discovery_origin` and `first_discovery_iteration` for every final evidence item.
7. Evaluation reports the proportion of final evidence paths outside the initial Qdrant path set.
8. A run that never inspects beyond initial lead snippets is valid only if those snippets genuinely establish the
   complete requested mechanism; it is not a success criterion by itself.

## Finding And Sufficiency Contract

The agent maintains explicit findings rather than current evidence roles:

```python
@dataclass(frozen=True)
class GroundedFinding:
    id: str
    statement: str
    evidence_ids: tuple[str, ...]
    obligation_ids: tuple[str, ...]
    confidence: str
```

A `complete` report requires:

1. Every material finding references at least one validated source range.
2. The central implementation owner or mechanism relevant to the request is grounded.
3. Required cross-file handoffs are grounded when the explanation depends on them.
4. Every required repository obligation is supported or explicitly shown to be inapplicable.
5. Remaining uncertainties cannot materially change the explanation.
6. No selected evidence comes solely from a file outline, graph edge, path name, or model inference.

A `partial` report is correct when useful evidence exists but one or more material questions remain unresolved. The
agent must name those questions. `sufficient=false` is not a failure to produce output; it is an honest retrieval
result.

Sufficiency is proposed by the agent and checked by deterministic structural rules. Do not add a second final
selection or coverage LLM in the first experiment. If later evidence shows that self-assessed sufficiency is
systematically overconfident, test a separate verifier as its own experimental step rather than silently adding one.

## Deterministic Final Validation

Before adapting the report to current application types:

1. Resolve every evidence path under the workspace root.
2. Reject forbidden, generated, vendored, hidden-Oracle, run-artifact, and post-resolution paths according to the
   active scope policy.
3. Re-read every exact line range from the current repository snapshot.
4. Require returned `source_text` to match those lines after the declared normalization.
5. Verify that referenced evidence IDs and finding IDs exist.
6. Deduplicate identical and nested ranges when they support the same claim.
7. Preserve distinct ranges when they support different necessary claims.
8. Fail explicitly on stale or fabricated citations; do not repair them by searching for similar text elsewhere.
9. Record artifact-kind audits and any exclusions.

Validation can reject an invalid report or downgrade it to partial only when the remaining validated evidence still
forms a coherent partial result. It may not invent replacement evidence.

## Compatibility Adapter And Product Flow

During shadow and integration testing:

```text
current ControlLayer teaching policy
  -> current request analysis and obligations
  -> unchanged Qdrant/CodeGraph initial discovery
  -> AgentRetrievalRequest boundary adapter
  -> independent agent runtime
  -> validated AgentRetrievalReport
  -> temporary Guided Intelligence adapter
  -> current RetrievalResult/EvidenceItem
  -> current response generation
```

The temporary adapter maps:

- `complete` to `strong/sufficient=true` only when all final validation rules pass;
- `partial` to `partial/sufficient=false`;
- `failed` to the current explicit retrieval failure surface;
- each `AgentEvidence` to one `EvidenceItem` with path/range/symbol/provenance metadata;
- execution statistics to `retrieval_summary`.

Explanation generation remains disabled during retrieval acceptance experiments.

## Tracing Requirements

Every run must record:

- initial Qdrant dense, sparse, and hybrid results unchanged from the baseline trace;
- file groups, held alternatives, and complete CodeGraph-handle resolution;
- the serialized initial-lead package and its character/token size;
- every working-context snapshot or a reproducible structured representation of it;
- model provider, model, prompt/profile version, and schema version;
- every model decision and tool request;
- tool results with bounded previews and complete artifact references;
- state updates to findings, gaps, hypotheses, and evidence;
- attempted-operation fingerprints and deduplication decisions;
- per-iteration and total token, time, and tool budgets;
- stop reason and remaining uninspected high-priority leads;
- final evidence provenance back to initial or newly discovered artifacts;
- paths in final evidence that were not present in the initial Qdrant path set;
- explicit provider/tool failures with no fallback substitution.

Avoid storing hidden chain-of-thought. Store only explicit structured decisions and state required to reproduce the
run.

## Budget Defaults For The First Experiment

Defaults are hypotheses and must be configurable in reusable run profiles:

```text
maximum agent iterations:             8
maximum model-selected tool calls:   20
maximum tool calls per iteration:     3
maximum source window:              120 lines
maximum exact-search results:        20
maximum graph neighbors per call:    12
maximum lexical/semantic results:    12
maximum repeated no-gain iterations:  2
```

Do not give separate hidden budgets to recovery classes because those classes do not exist in the new mode. A tool
call consumes the same global budget regardless of whether it inspects an initial lead or explores a newly discovered
path.

The working-context character/token ceiling must be explicit. When state exceeds it, compact old tool results into
artifact summaries while retaining full source in the local artifact store. Do not silently drop accepted findings,
unresolved questions, exact evidence IDs, or pending user-visible uncertainties.

## Expected Impact

### Quality hypothesis

- Strong initial Qdrant recall is retained.
- Correct candidates cannot disappear solely because an early owner-comparison or qualification call rejected them.
- The model can follow concrete identifiers and relationships discovered after source inspection.
- Cross-file mechanisms do not require predeclared island, connector, maturation, or verified-lead categories.
- Final evidence is selected from the complete discovered workspace, not only the initial candidates.

### Token hypothesis

Possible reductions:

- remove large initial owner-comparison calls;
- remove qualification and coverage calls on every controller round;
- remove a separate final evidence-selection call;
- avoid repeatedly serializing the same broad card sets.

Possible increases:

- multiple agent-decision calls;
- repeated source inspection when context compaction is poor;
- repository-wide reformulated searches;
- local models may require more iterations than stronger API models.

No token reduction should be claimed until actual runs measure total model input, cached input, output, and any local
indexing cost under a fixed model/profile.

### Runtime hypothesis

Qdrant and CodeGraph preparation remain unchanged. Post-discovery runtime may decrease by removing multi-stage LLM
calls or increase because of serial agent iterations. Tool calls should be cheap relative to model calls, but graph and
semantic searches still require measurement.

## Known Regression Risks

1. **Initial-rank anchoring:** the model may over-trust top Qdrant paths even though unrestricted tools exist.
   Measure out-of-seed exploration and use prompt/schema wording that calls initial results `leads`, never `evidence`.
2. **Candidate overload:** hundreds of resolved owners cannot fit in one useful context. Keep the full artifact store
   outside the model and expose a deterministic bounded projection.
3. **Premature finish:** a model may produce a coherent story from incomplete evidence. Require explicit unresolved
   questions and deterministic sufficiency checks; evaluate against hidden-Oracle survival and causal trace quality.
4. **Exploration drift:** unrestricted search can leave the relevant subsystem. Record the purpose and expected signal
   for every call, deduplicate searches, and stop repeated no-gain work.
5. **Weak local tool use:** small local models may emit invalid calls or fail to revise hypotheses. Treat that as a
   provider-specific failure, not evidence that the architecture is impossible.
6. **Stale CodeGraph handles:** graph nodes may point to incorrect ranges. Re-read source and validate ranges before
   accepting evidence.
7. **Obligation anchoring:** preserved obligations may themselves bias retrieval incorrectly. Keep this fixed during
   the first experiment; test obligation-free or agent-revised goals only as a later independent experiment.
8. **Loss of deterministic comparability:** model decisions are stochastic. Preserve exact inputs and run accepted
   variants twice under unchanged conditions.
9. **Provider transcript dependence:** relying only on API-side conversation state would make local replay and provider
   changes ambiguous. Keep structured application-owned state authoritative.
10. **Hidden fallback growth:** do not call the old qualification/controller flow when the agent fails. Surface the
    failure. Comparative modes belong in run configuration, not inside one execution path.

## Incremental Implementation Plan

Each step is independently testable and limited to three implementation variants. Do not combine steps merely to
reach an end-to-end demo sooner.

### Step 0 — Preserve baseline artifacts

Boundary:

- no production behavior change;
- run or select valid current workspace baselines;
- preserve initial query/channel results, grouped candidates, resolved handles, qualification decisions, controller
  trace, final candidates, and final evidence.

Required cases:

- `pandas-dev-pandas-10068` as the main known downstream-loss case;
- `microsoft-TypeScript-35468` as a multi-file mechanism case;
- `vuejs-vue-10803` as a smaller cross-language regression check.

Keep model, prompt profile, index signature, obligations, Qdrant configuration, and testcase snapshot fixed.

### Step 1 — Build the initial-lead package

Changed boundary:

- convert saved real Qdrant/file-group/CodeGraph outputs into independent `InitialLead` records.

Must remain unchanged:

- query generation, Qdrant results, grouping, held alternatives, CodeGraph range results;
- no agent call;
- no current qualification or final selection in the focused replay test.

Focused acceptance:

- every raw representative and held alternative is traceable to at least one lead record;
- all plausible resolved structural handles remain available;
- no canonical owner is chosen;
- payload is deterministic and within the declared serialization budget;
- known `_binop` raw range and `_binop` structural handle coexist in the replay fixture.

### Step 2 — Implement provider-neutral state and decision runtime

Changed boundary:

- `AgentState`, `WorkingContext`, provider contract, decision schema, budgets, and tracing;
- use saved lead packages and a fake deterministic provider only for protocol mechanics, never as a substitute for the
  real LLM acceptance test.

Focused acceptance:

- state survives multiple calls;
- working-context compaction retains accepted findings, open questions, and evidence IDs;
- invalid or repeated tool calls are rejected or deduplicated;
- provider failure surfaces explicitly;
- budget exhaustion produces a valid partial report.

Then exercise the same boundary twice with the configured real model and replayed saved leads. This proves schema and
state behavior, not retrieval quality.

### Step 3 — Implement bounded inspection tools

Changed boundary:

- `inspect_lead`, `open_source`, and `exact_search` only.

Focused acceptance:

- the model can inspect any alternative structural handle;
- arbitrary allowed repository paths can be opened;
- forbidden paths are rejected;
- exact search is capped at the producer and records exclusions;
- returned evidence line numbers and contents validate exactly.

First quality variant:

- initial leads plus inspection/exact search only.

Do not add graph or new semantic search to repair the first weak result until the trace identifies a missing capability.

### Step 4 — Add relationship navigation

Dependency:

- proceed only if Step 3 traces show that a concrete relationship is needed and cannot be recovered through exact
  search/source inspection within the budget.

Changed boundary:

- add `graph_neighbors` with exact node/edge provenance.

Focused acceptance:

- an initial lead can reach a node/file absent from initial Qdrant paths;
- source must be inspected before the node becomes evidence;
- relationship provenance is preserved;
- repeated graph calls are deduplicated;
- one missing CodeGraph edge does not fabricate a relationship.

### Step 5 — Add unrestricted reformulated retrieval

Dependency:

- proceed only if Steps 3-4 show a genuine need to search beyond exact identifiers and graph relationships.

Changed boundary:

- add lexical search first;
- add semantic Qdrant follow-up as the next attempt only when lexical search is insufficient.

Focused acceptance:

- default scope is the full allowed repository;
- final evidence can originate from paths absent from initial leads;
- new queries record the grounded observation or unresolved question that motivated them;
- results enter the same artifact store and have no lower evidence status than initial leads.

At most three tool-set variants are allowed for the combined agent experiment:

1. initial leads + source inspection + exact search;
2. variant 1 + graph navigation;
3. variant 2 + unrestricted lexical/semantic follow-up.

Do not tune three prompts, tool sets, and budget policies simultaneously and call them one variant.

### Step 6 — Final report validation and compatibility adapter

Changed boundary:

- validate the independent report;
- convert it to current `EvidenceItem`/`RetrievalResult` only after validation.

Focused acceptance:

- fabricated/stale ranges fail explicitly;
- partial results remain partial;
- discovered-outside-seed evidence converts normally;
- no qualification, controller, evidence-island, recovery, coverage-LLM, or final-selector code executes in agent mode.

### Step 7 — Shadow actual-pipeline integration

Run the normal initial discovery once, save the lead package, and feed the identical package to:

1. the unchanged current downstream flow;
2. the new agent downstream flow.

This shared-prefix comparison is the primary experiment. It isolates downstream behavior from stochastic Qdrant
variation.

Diagnostic runs may skip explanation generation. They must not be counted as final acceptance when later evidence
selection differs from production behavior. For agent mode, the validated agent report is itself the replacement final
selection, so there is no current final-selector stage to enable.

### Step 8 — End-to-end repeated acceptance

After the replay/shared-prefix boundary passes:

- run at least two actual-pipeline agent executions on the main case with unchanged settings;
- run at least two unchanged current-workspace comparisons when a fresh baseline is required by changed external
  conditions;
- run the TypeScript and Vue regression cases;
- keep explanation generation disabled;
- record every run ID and complete trace boundary.

Only after acceptance should a separate cleanup change remove the replaced downstream production path. Do not leave a
hidden fallback branch beside the replacement.

## Evaluation Metrics

### Quality

- implementation, test, and documentation Oracle overlap by unique file;
- P@1, P@2, P@5, P@10;
- R@1, R@2, R@5, R@10;
- NDCG@1, NDCG@2, NDCG@5, NDCG@10;
- valid evidence-range rate;
- number of grounded cross-file handoffs;
- required obligations supported;
- `complete` versus `partial` stability;
- useful non-Oracle mechanism evidence, inspected manually;
- final evidence paths absent from initial Qdrant paths.

### Evidence survival

For every relevant lead, record:

```text
raw Qdrant channel/rank
-> file group and held status
-> structural handles
-> initial-lead manifest
-> working-context appearances
-> inspection
-> finding/evidence state
-> final report
```

Do not say an item was not retrieved when it was present in the initial lead store but never placed into a working
context or inspected. Name the first boundary where it stopped progressing.

### Cost and runtime

- initial indexing tokens and time, unchanged from baseline;
- initial discovery tool calls and time;
- agent input, cached input, output, and total tokens by iteration;
- tool calls by type;
- working-context size by iteration;
- end-to-end retrieval time;
- current owner-comparison, qualification, coverage, controller, and final-selection token totals for comparison;
- model/provider-specific monetary estimates only with a recorded pricing snapshot and formula.

### Agent behavior

- iterations;
- repeated/blocked calls;
- no-gain iterations;
- initial leads inspected;
- newly discovered artifacts inspected;
- graph depth and search breadth;
- proportion of selected evidence discovered by each origin;
- uninspected high-priority leads at stop;
- unresolved questions at stop.

## Acceptance Criteria

The experiment is accepted only if all of the following hold:

1. Initial Qdrant and CodeGraph behavior is unchanged and trace-equivalent at the shared prefix.
2. Every final evidence citation validates against the repository snapshot.
3. The agent can select evidence outside initial Qdrant paths in a focused fixture and at least one natural run or a
   clearly documented natural opportunity.
4. The main-case improvement or non-regression is repeatable across two unchanged runs.
5. TypeScript and Vue checks show no repeated material quality regression.
6. Useful leads are not silently lost; every unselected lead remains traceable with inspection/state history.
7. Total retrieval cost and runtime are measured and judged proportionate to quality.
8. The new mode invokes none of the replaced qualification/controller/island/recovery/final-selection stages.
9. Provider or tool failures surface explicitly without using the old downstream flow as a fallback.
10. The final result is understandable from structured state and traces without hidden chain-of-thought.

Acceptance does not require every final item to originate outside initial Qdrant results. It requires unrestricted
eligibility and demonstrated ability to leave the initial lead set when the evidence demands it.

## Rejection And Rollback Criteria

Revert or leave the mode experimental when:

- two unchanged main-case runs regress relevant evidence survival or ranking;
- the model repeatedly stops before inspecting present high-value leads;
- unrestricted search produces large cost/noise without necessary new evidence;
- local/API provider behavior cannot satisfy the decision schema reliably;
- context compaction hides accepted facts or unresolved questions;
- the agent relies on testcase-specific names or prompt hardcoding;
- invalid citations occur after deterministic validation should have prevented them;
- gains cannot be distinguished from initial Qdrant variation;
- token/runtime growth is not justified by stable quality.

After three unsuccessful variants at any one step, follow the incremental protocol: retain only a measurably improved,
explicitly limited best-effort variant or revert the step and stop dependent work.

## Result Ledger

Update this table during implementation:

| Step | Attempt | Focused run 1 | Focused run 2 | Cost change | Decision | Remaining issue |
|---|---:|---|---|---|---|---|
| Initial-lead package | 1 | focused unit pass | actual trace: 185 leads | prefix cost unchanged | retain experimental | natural run projected only 40 leads at once |
| Stateful runtime | 1 | focused unit pass | `run-20260823T161050Z`, 4 decisions | 80,573 tokens | mechanically valid | first policy is too expensive |
| Inspection/exact tools | 1 | outside-path fixture pass | actual run inspected 2 sources | included above | retain | exact-query quality is model-sensitive |
| Graph navigation | 1 | contract implemented | not naturally selected | none measured | unproven | needs a natural graph-following run |
| Unrestricted follow-up search | 1 | outside-path fixture pass | actual semantic/exact searches executed | included above | capability proven, quality unproven | no outside-initial path selected naturally |
| Final validation/adapter | 1 | invalid URL/ID rejection pass | 2 ranges revalidated | one forced synthesis call | mechanically valid | selected no Oracle file |
| Shared-prefix integration | 1 | focused boundary checks | `run-20260823T161050Z` | 8 prefix + 6 agent tool calls | mechanically valid | sparse-only acceptance profile differs from production hybrid |

For failed variants:

| Attempt | Hypothesis | Exact change | Observed failure | Root cause | Future option |
|---:|---|---|---|---|---|
| 1 | Let Codex CLI act as a JSON provider with its default tools | Only output-schema and read-only sandbox were applied | Model used provider-native shell/GitHub tools and returned URL evidence IDs | A read-only agent is not a tool-less completion provider | Disable plugins/apps/shell/unified exec for JSON completion; keep deterministic grounding validation |
| 2 | Stop immediately after repeated no-gain searches | Finalized the last ordinary decision | 20 inspected artifacts were discarded because the last decision had no findings | Exploration and synthesis were not separated at the stopping boundary | Use one final model-only synthesis decision over inspected state |
| 3 | Strict file-only search scope is sufficient | Exact-search `path` required a file | Natural run requested `pandas/core/indexes` and aborted | Repository search scopes are commonly directories | Permit allowed file or directory scopes and return recoverable tool errors to state |

## Open-Question Registry Mapping

This proposal intersects existing unresolved boundaries but does not close them:

- `IOC-1`: replaces initial owner comparison in agent mode; baseline traces and costs remain comparison evidence.
- `VL-1`, `VL-2`, `VL-3`: replaces specialized verified-lead eligibility and caps with generic bounded navigation;
  pending leads still need traceable stop reporting.
- `ISL-1`: replaces semantic-island connector repair with model-directed relationship/navigation tools; exact
  relationship provenance remains required.

Do not update those statuses until actual-pipeline agent runs exercise the corresponding behavior. Record full
measurements in `../retrieval-changelog.md`, not in the registry or this plan.

## Implementation Completion Checklist

- [ ] Shared-prefix baseline artifacts saved.
- [x] Independent contracts contain no current controller/action/qualification types.
- [x] Initial lead package retains representatives, held alternatives, and all plausible structural handles.
- [x] Application-owned agent state survives retries and provider changes.
- [x] Working context is bounded and reproducible.
- [x] Initial leads are explicitly hints, not an eligibility universe.
- [x] Arbitrary allowed source opening works.
- [x] Graph navigation can introduce new paths.
- [x] Exact/lexical/semantic follow-up can search the full allowed repository.
- [x] Every tool is bounded at the producer.
- [x] Every evidence range is deterministically revalidated.
- [x] LLM/tool failure surfaces explicitly with no surrogate or old-flow fallback.
- [x] Current teaching policy and response generation remain outside the agent.
- [ ] Each stochastic step passes twice before acceptance.
- [ ] Main and regression cases run through the actual pipeline.
- [x] Run IDs, quality, tokens, time, and notable evidence changes are recorded in the retrieval changelog.
- [ ] Replaced downstream code is removed only in a later authorized cleanup after acceptance.

## Referenced-Lead Activation Experiment (2026-08-23)

### Observed problem and fixed baseline

Actual run `run-20260823T161050Z` placed exact `pandas/core/series.py::Series::_binop` at position 33 of the first
40 initial leads shown to the agent. It was rank 1 for `explain_state_changes` and rank 2 for `explain_why`. The agent
instead inspected `_flex_method_SERIES` and `flex_wrapper`, whose source literally calls `self._binop(...)`, then ran
two rounds of empty fixed-string searches for `def __add__` and `def add`. Two no-gain iterations forced partial
synthesis. `_binop` was therefore retrieved and visible but never inspected; its first loss boundary was the agent's
navigation decision, not Qdrant, file grouping, CodeGraph, context projection, or final validation.

The experiment keeps the retrieval prefix, initial-lead ordering, tool implementations, model/schema, evidence
validation, and final adapter unchanged.

### Independent steps

| Step | Changed boundary | Expected quality effect | Expected cost | Risks | Focused verification |
|---|---|---|---|---|---|
| A. Bounded tool outcomes | Agent state/context only | Make empty searches and recoverable errors explicit instead of inferential | Small context increase | Repeated error text crowds source | Two identical fixtures preserve bounded, ordered outcomes |
| B. Referenced-lead projection | Deterministic context projection only | Surface uninspected stored leads whose exact terminal symbol is referenced by inspected source | Small local scan; no LLM/tool call | Common short identifiers create noise | `self._binop(...)` surfaces `Series::_binop`; unrelated symbols do not |
| C. No-gain guard | Agent stopping boundary only | Do not force synthesis while an uninspected referenced lead remains actionable | Existing-budget decisions/tools only | Agent may still ignore the lead and loop | Replayed decisions prove the guard keeps the loop open, then normal stop resumes after inspection/rejection |

No step may automatically select or inspect evidence. The model remains responsible for choosing `inspect_lead`;
the application only makes already-grounded navigation state explicit. Candidate matching is generic exact identifier
matching, never a pandas/path/testcase rule.

### Acceptance and rollback

- Deterministic steps A and B must pass twice through focused tests with identical output.
- The model boundary must choose the referenced lead in two unchanged focused calls before an actual-pipeline run.
- The pandas run must inspect `Series::_binop` before no-gain termination when the same lead is present.
- Final quality may remain partial, but the former loss boundary must move past inspection without materially larger
  context or controller-like automatic execution.
- Revert B/C if common-symbol noise dominates, the model still ignores the exact lead twice, or the guard merely
  converts the same failure into budget exhaustion. Maximum three variants per step.

### Result ledger

| Step | Attempt | Focused run 1 | Focused run 2 | Cost change | Decision | Remaining issue |
|---|---:|---|---|---|---|---|
| A. Bounded tool outcomes | 1 | pass: empty result persisted | repeat pass | compact state only | retain | outcome history still contributes to context size |
| B. Referenced-lead projection | 1 | pass: `self._binop` -> exact lead | repeat pass | deterministic local scan | retain | common-symbol candidates remain possible |
| C. No-gain guard | 1 | pass: one bounded deferral | repeat pass; two live model calls chose `inspect_lead` | no extra call unless guard activates | retain, narrow boundary resolved | final generated-wrapper navigation remains weak |

Actual pipeline evidence: `run-20260823T163733Z` directly inspected stored lead `obs_7fcee82d964fc060`
(`Series::_binop`) in iteration 2, but exposed a separate context-projection defect at iteration 7. The projection now
uses tested progressive source-preview compaction and preserves reminded referenced leads. The completed rerun
`run-20260823T164358Z` stayed below 30,000 serialized characters for all eight iterations, searched for `_binop`,
and opened its `series.py` implementation instead of stopping after empty searches. It nevertheless ended
`failed/false` with no evidence and 299,499 agent-decision tokens because it did not close the generated `Series.add`
wrapper path. This accepts the specific navigation correction only; it is not evidence that the agentic mode has met
overall quality or cost acceptance.
