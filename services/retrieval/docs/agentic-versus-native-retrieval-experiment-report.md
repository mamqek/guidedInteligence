# Seeded Agentic Retrieval Versus Native Retrieval

## Experimental Report And Thesis Record

**Status:** implemented experiment, mechanically verified, not accepted for retrieval quality

**Repository branch:** `codex/seeded-agentic-retrieval`

**Primary experiment date:** 2026-08-23

**Primary benchmark case:** `pandas-dev-pandas-10068`
**Canonical term:** *agentic retrieval*. The implementation is model/provider-agnostic at its contract boundary, but
it is not a genetic algorithm and it is not retrieval without an agent.

This report is intentionally separate from the chronological
[`retrieval-changelog.md`](retrieval-changelog.md). Its purpose is to preserve the complete experiment as a coherent
case study suitable for later thesis use: the motivation, system boundary, implementation, actual behavior, failure
analysis, comparison with native retrieval, limitations of the evidence, and the architectural conclusion.

The detailed implementation proposal remains in
[`decisions/seeded-agentic-evidence-retrieval.md`](decisions/seeded-agentic-evidence-retrieval.md). This report describes
what was actually built and observed rather than restating the proposal as if every planned component were accepted.

---

## 1. Abstract

Guided Intelligence's native repository retriever combines obligation-scoped Qdrant search, CodeGraph structural
resolution, LLM owner comparison and source qualification, a deterministic multi-round action controller, evidence
islands and recovery policies, and a separate final evidence selector. The native system accumulated increasingly
specific controller rules because useful code was often retrieved early but subsequently rejected, hidden, stranded,
or displaced at one of several downstream decision boundaries.

The seeded agentic retrieval experiment tested a substantially different downstream architecture. It preserved the
native request-analysis, Qdrant, file-grouping, held-alternative, and CodeGraph prefix. It converted the complete output
of that prefix into an initial lead store and then bypassed native owner comparison, qualification, action rounds,
island/recovery logic, and final evidence selection. A persistent model-directed agent could inspect any stored lead,
open arbitrary allowed repository source, follow graph neighbors, run exact repository search, or issue a new semantic
search. Qdrant output was explicitly treated as orientation rather than as the final evidence universe.

The experiment established that this architecture is implementable. The agent maintained application-owned state,
used a provider-neutral JSON decision contract, executed bounded tools, could select evidence outside the seed set in
focused tests, and produced snapshot-validated evidence without falling back to the native downstream flow. However,
the measured natural runs did not establish a quality or efficiency advantage. The first completed pandas run stopped
prematurely after inspecting two `ops.py` ranges even though the exact `Series::_binop` lead was already present in its
working context. A targeted referenced-lead correction moved that loss boundary beyond `_binop` inspection, but the
corrected run consumed 299,499 agent-decision tokens, exhausted eight iterations, failed to resolve the dynamically
generated `Series.add` path, and selected no final evidence.

The result rejects the broad claim that replacing the complete downstream native system with one free-form retrieval
agent is automatically simpler or better. It supports a narrower follow-up hypothesis: preserve deterministic search,
tool execution, grounding, and final selection, but test an agent as the semantic planner that chooses among bounded
retrieval actions. In other words, the evidence favors an **agent-planned native controller**, not a fully agent-owned
retrieval pipeline.

---

## 2. Research Question

The experiment investigated the following practical question:

> If the initial obligation-scoped Qdrant and CodeGraph stages already provide useful repository direction, can one
> stateful tool-using agent replace the increasingly complicated downstream owner-selection, qualification,
> controller, recovery, and final-selection flow without reducing evidence quality or creating disproportionate cost?

The question contains three separable hypotheses:

1. **Evidence-survival hypothesis.** Retaining all initial leads and allowing later unrestricted inspection should
   prevent useful owners from disappearing because of an early binary qualification or controller eligibility rule.
2. **Adaptivity hypothesis.** A model that observes the results of its previous actions should choose more appropriate
   follow-up searches and graph/source inspections than a fixed collection of recovery categories and scheduler
   priorities.
3. **Simplification hypothesis.** Replacing repeated native LLM stages and specialized controller rules with one
   persistent loop might reduce both conceptual complexity and token cost.

The experiment confirmed only the mechanical part of the first hypothesis: all initial leads could remain addressable
and the agent could inspect them later. It did not confirm natural-run quality improvement, reliable adaptivity, or
cost reduction.

---

## 3. Evidence Basis And Comparability Limits

### 3.1 Primary local evidence

This report is grounded in the following repository and run artifacts:

- the implemented agent package under [`../agentic/`](../agentic/);
- the design and result ledger in
  [`decisions/seeded-agentic-evidence-retrieval.md`](decisions/seeded-agentic-evidence-retrieval.md);
- the relevant open-question state in
  [`decisions/retrieval-experiment-open-questions.md`](decisions/retrieval-experiment-open-questions.md);
- the native controller in
  [`../workspace/pipeline/execution_flow/retrieval_controller.py`](../workspace/pipeline/execution_flow/retrieval_controller.py);
- native action models, enumeration/execution, and scheduling under
  [`../workspace/pipeline/execution_flow/actions/`](../workspace/pipeline/execution_flow/actions/);
- run profiles [`../../../configs/testing/agentic.json`](../../../configs/testing/agentic.json) and
  [`../../../configs/web-ui/agentic.json`](../../../configs/web-ui/agentic.json);
- CodeRepoQA artifacts under
  `C:\Programming\guidedInteligence_testcases\pandas-dev-pandas-10068\runs\`.

The principal run IDs are:

- native comparison: `run-20260822T184944Z`;
- first completed agentic run: `run-20260823T161050Z`;
- referenced-lead integration run: `run-20260823T163733Z`;
- completed post-correction agentic run: `run-20260823T164358Z`.

### 3.2 Relevant Git history

The native downstream design did not appear in one change. The inspected local history includes:

| Commit | Local message | Relevance |
|---|---|---|
| `143d643` | `before double qualification` | monolithic controller/action baseline before the latest owner-comparison work |
| `2ac79d7` | `actions refactor` | added compact initial owner comparison and further controller repair machinery |
| `fbc01cb` | `kinda good` | split action models, purpose policy, scheduler, and execution into explicit modules |
| current experimental branch | `codex/seeded-agentic-retrieval` | adds a separate mode that bypasses, but does not delete, the native downstream flow |

At `143d643`, the native `retrieval_controller.py` and `retrieval_actions.py` contained approximately 1,169 and 1,273
lines respectively. At `fbc01cb`, the refactored controller contained approximately 1,075 lines, while action
catalogue/execution, scheduler, and models contained approximately 1,180, 362, and 138 lines. Line count is not a
quality metric, but it makes the architectural issue concrete: downstream retrieval policy had become a substantial
system rather than a small loop.

### 3.3 Why the measured runs are not a controlled A/B experiment

The native and agentic natural runs must not be presented as if only the controller changed:

- the native comparison used `gpt-5.6-luna` through OpenAI Chat Completions;
- the agentic runs used `gpt-5.4-mini` through Codex CLI JSON completion;
- the checked-in agentic testing profile used sparse retrieval because the embedding API account was unavailable;
- the normal web agentic profile still enables dense plus sparse retrieval;
- request-analysis output is stochastic and therefore changed the number and wording of obligations between some
  attempts;
- `run-20260823T163733Z` failed before normal result/scorecard completion and is diagnostic, not an acceptance run.

The comparison therefore supports architectural diagnosis and falsifies overly strong claims about the full agent. It
does not provide a statistically controlled estimate of the causal effect of changing only the downstream controller.
A thesis should describe it as a **case-study comparison with measured natural runs**, not as a benchmark victory or a
formal ablation.

### 3.4 External research basis

The experiment's general plausibility was informed by prior work, but project runs remained the acceptance authority:

- [RepoCoder](https://aclanthology.org/2023.emnlp-main.151.pdf) supports iterative repository retrieval for code
  completion, not this project's evidence-selection task.
- [IRCoT](https://aclanthology.org/2023.acl-long.557.pdf) supports the broader principle that later retrieval can depend
  on facts established by earlier retrieval steps.
- [SWE-agent](https://arxiv.org/abs/2405.15793) supports bounded, model-usable repository interaction tools.
- [Agentless](https://openreview.net/pdf?id=dw9VUsSHGB) supports separating strong localization from later reasoning
  instead of making the model discover the repository from nothing.

These sources justify evaluating iterative, tool-mediated retrieval. None demonstrates that the exact agent built here
should outperform the native Guided Intelligence retriever.

---

## 4. Shared Retrieval Prefix

The native and agentic modes deliberately shared the initial repository-localization prefix. This isolation was
important because the motivating observation was not that Qdrant failed completely. The frequent pattern was that a
useful file or source range appeared early and was later lost.

The shared prefix performs the following work:

1. Request analysis transforms the issue/question into repository evidence obligations.
2. Each repository obligation produces a focused Qdrant query.
3. Qdrant returns sparse and, when configured, dense/hybrid results.
4. Results are grouped by file and obligation.
5. A representative range is retained for each admitted group while same-file alternatives remain available.
6. Raw ranges are submitted to CodeGraph for structural owner resolution.
7. The prefix retains provenance including obligation IDs, query views, ranks, scores, raw ranges, artifact role, and
   plausible structural handles.

The commonly used description of “approximately 48 initial hits” comes from four obligations multiplied by twelve
focused results. The actual downstream universe is usually larger. Duplicate obligation views, held alternatives,
overlapping ranges, and multiple CodeGraph owners can expand a few dozen Qdrant representatives into hundreds of
addressable leads. Both completed agentic pandas runs recorded **231 initial leads across 30 paths**.

The experiment did not change Qdrant fusion, embeddings, sparse indexing, initial query construction, CodeGraph
adapters, or index exclusions. This allowed downstream evidence loss to be distinguished from raw retrieval absence.

---

## 5. Native Retrieval Downstream Architecture

### 5.1 Native flow

After the shared prefix, the native workspace mode follows approximately this sequence:

```text
Qdrant/file groups/CodeGraph owners
  -> initial observation aggregation and path guardrails
  -> LLM comparison among owners in already-admitted file groups
  -> bounded source disclosure
  -> LLM qualification of disclosed source
  -> grounded candidate construction
  -> LLM obligation-coverage evaluation
  -> semantic evidence-island construction
  -> deterministic action enumeration
  -> deterministic action scheduling by pool, scope, path, and effect
  -> deterministic action execution
  -> disclosure/qualification of newly discovered observations
  -> repeated coverage/island/action rounds
  -> final candidate pool
  -> LLM evidence consolidation and obligation support decision
  -> deterministic evidence adaptation
```

The native controller stores explicit observations, disclosure cards, qualification decisions, promoted candidates,
coverage states, evidence-island relationships, attempted action IDs/effects, refined paths, verified leads, and file
trace seeds.

### 5.2 Native typed actions

The current action contract is not itself arbitrary. It gives the executor bounded operations:

| Action | Responsibility |
|---|---|
| `InspectDeferredObservation` | disclose a retrieved observation that did not receive an initial decision |
| `InspectOwnerContinuation` | inspect a later omitted range of a known large owner |
| `ExpandRelationship` | traverse represented CodeGraph relationships from an owner or file |
| `ExpandWithinFileHandoff` | expand a qualified source through an explicit missing handoff inside the same path |
| `SearchNewIsland` | seek a separate mechanism outside represented evidence islands |
| `InspectVerifiedLead` | inspect an exact repository node visibly named by newly grounded source |
| `StopRetrieval` | express that no further bounded native action is available |

The action executor validates targets, invokes existing structural/Qdrant tools, returns observations and edges, and
records exact action provenance. These are useful safety and audit properties.

### 5.3 Policy pools and accumulated specialization

Actions are partitioned into purpose-specific pools:

- ordinary exploration;
- deferred-file rescue;
- owner maturation;
- test maturation;
- verified leads and structural children;
- controller stop/control.

The scheduler protects separate slots so that one family cannot consume another. It also ranks by action type, active
root/island order, path refinement state, prior effects, obligation, and handoff status. Later rounds prefer certain
relationship or continuation work. Other rules preserve a disconnected hypothesis, avoid duplicate paths, and limit
the number of verified-lead executions.

Each rule is individually understandable. The collective problem is that the system increasingly represents
retrieval behavior through categories invented in response to earlier failures. “Deferred rescue,” “owner
maturation,” “test maturation,” and “verified structural child” are not repository primitives; they are controller
interpretations of when a generic inspect/search/follow operation should be allowed a protected opportunity.

### 5.4 Native strengths

The native flow has several empirically important advantages:

- tool arguments and repository scope remain deterministic and auditable;
- qualifications and candidate construction create compact evidence objects;
- coverage is evaluated explicitly against every required obligation;
- structural edges and file traces can support cross-file explanations;
- separate scheduling pools prevent one noisy behavior from exhausting all exploration capacity;
- final selection considers a prepared candidate pool instead of requiring the exploring model to synthesize a final
  report from raw state;
- mature tracing makes every evidence-loss boundary inspectable.

### 5.5 Native weaknesses motivating the experiment

The main weaknesses are downstream decision coupling and corrective complexity:

- initial owner comparison may demote a good owner before complete disclosure;
- qualification may treat a useful navigation lead as insufficient evidence and prevent it from becoming an active
  root;
- observations can become promoted, deferred, dormant, or held under different eligibility rules;
- graph-connected mechanism parts can remain in separate evidence islands when a connector is absent;
- action caps and round timing can strand a valid continuation;
- final evidence selection can discard candidates that survived every earlier stage;
- each observed failure invites a new recovery category, cap exception, or reserved slot.

The native pipeline is therefore strong at bounded execution but increasingly fragile at deciding **which bounded
operation should happen next**.

---

## 6. Seeded Agentic Downstream Architecture

### 6.1 Replacement boundary

The experimental `agentic` mode exits the shared native prefix immediately after raw/held observations and CodeGraph
handles are available. It bypasses:

- initial owner comparison;
- native source qualification;
- promoted/deferred/dormant eligibility transitions;
- evidence-island construction and repair;
- action catalogue and scheduler;
- verified-lead, maturation, bridge, and resurrection flows;
- native coverage calls used to authorize further exploration;
- the separate final evidence-selection model call.

Those components remain present for `workspace` mode. There is no fallback from a failed agentic run into the native
controller.

### 6.2 Implemented module boundary

The implementation is isolated under [`../agentic/`](../agentic/):

| Module | Implemented responsibility |
|---|---|
| `contracts.py` | provider-neutral request, budget, state, tool-call, finding, evidence, outcome, and report contracts |
| `seed_builder.py` | converts native prefix observations into independent initial leads and structural handles |
| `runtime.py` | working-context projection, decision loop, stopping, findings, referenced-lead reminders, and finalization |
| `tools.py` | bounded tool validation/execution and artifact/outcome persistence |
| `adapter.py` | invokes the agent from the shared prefix and maps its report to Guided Intelligence retrieval results |

The implementation is somewhat more consolidated than the original proposed directory structure, but it preserves the
important responsibility boundary: the agent contracts do not encode native `QualificationDecision`, `EvidenceIsland`,
or `RetrievalAction` types.

### 6.3 Initial leads are hints, not eligibility

Every raw or held observation becomes an addressable `InitialLead` containing:

- a stable ID;
- path and source range;
- bounded preview;
- artifact kind;
- obligation memberships;
- retrieval views and provenance;
- zero or more plausible CodeGraph structural handles.

The complete lead store remains in application memory for the run. Only a bounded projection is shown in each model
call. The agent can list or inspect a lead outside the current projection.

An initial lead is not considered evidence merely because Qdrant returned it. It becomes eligible final evidence only
after bounded source inspection and snapshot validation. Conversely, a later graph/search/open-source artifact is not
penalized because Qdrant did not retrieve it initially.

### 6.4 Application-owned persistent state

The model API is not treated as the agent. The runtime owns persistent structured state containing:

- the unchanged request and obligations;
- every initial or newly discovered artifact;
- inspected and uninspected status;
- recent artifact IDs;
- grounded findings and their evidence IDs;
- unresolved questions;
- attempted-operation fingerprints;
- bounded tool outcomes;
- referenced-lead reminders;
- iteration, tool-call, token, and no-gain counters;
- protocol errors and remaining budgets.

Each decision call receives a serialized working context reconstructed from that state. Provider-side conversation
continuity is optional and was not the authoritative memory mechanism. This makes local/API providers conceptually
interchangeable and allows a run to be diagnosed without hidden chain-of-thought.

### 6.5 Working-context projection

The model cannot receive hundreds of full owners on every iteration. The runtime therefore projects:

- question and obligations;
- a bounded initial-lead summary;
- recent and inspected source artifacts;
- grounded findings;
- open questions;
- recent tool outcomes, including empty results;
- attempted operations;
- exact stored leads referenced by inspected source;
- remaining iteration/tool budgets;
- concise tool guidance.

The initial implementation allowed up to 30,000 serialized characters. A later run showed that fixed slices of
inspected and recent artifacts could duplicate source and make a subsequent iteration exceed this contract. The final
experimental version uses progressive projection profiles that reduce counts and preview sizes while preserving
required state and prioritized reminded leads.

### 6.6 Agent decision contract

Each model decision has one of three kinds:

- `tool_calls`: execute one or more bounded retrieval operations;
- `finish`: return grounded findings, evidence IDs, and remaining questions;
- `fail`: explicitly report that the task cannot be completed under the available evidence/budget.

Every tool call includes a purpose and expected signal. The runtime validates the call, deduplicates attempted effects,
executes it, stores the returned artifact/outcome, and reconstructs the next context.

Premature or invalid completion is rejected. A final evidence ID must name an inspected local artifact, not an
arbitrary URL or an uninspected lead. The runtime re-reads the exact repository range before adapting it into an
evidence item.

### 6.7 Bounded tools

The implemented tools expose generic repository operations:

| Tool | Behavior |
|---|---|
| `list_leads` | search the complete initial lead store by optional path/query filters |
| `inspect_lead` | inspect a stored raw/structural source lead by ID |
| `open_source` | read an arbitrary allowed repository-relative source window |
| `graph_neighbors` | expand bounded CodeGraph neighbors from a known node |
| `exact_search` | run bounded literal `rg` search in a file, directory, or repository scope |
| `semantic_search` | issue a fresh Qdrant query against any allowed repository scope |

The agent receives no arbitrary shell. Tool output is bounded before entering context. Scope, path normalization,
excluded directories, source windows, search limits, and evidence citations remain application-enforced.

### 6.8 Provider isolation

The actual experiment used Codex CLI as a JSON completion provider. An early attempt demonstrated that read-only
sandboxing alone was insufficient: Codex could still use its own shell/GitHub/plugin capabilities and returned URL
evidence IDs outside the application-owned tool protocol. JSON completion was therefore isolated by disabling
plugins, apps, shell tools, and unified execution for these calls.

This failure is conceptually important. A coding agent cannot simply be embedded as if it were a pure model endpoint.
If the host application is meant to own grounding and budgets, provider-native tools must be removed or explicitly
mediated. Otherwise two different agent runtimes act simultaneously and the local state ceases to be authoritative.

### 6.9 Loop and stopping policy

The first experiment configured:

- at most 8 model iterations;
- at most 20 model-selected tool calls;
- at most 3 tool calls per iteration;
- at most 120 source lines per source window;
- at most 2 repeated no-gain iterations;
- one forced model-only final synthesis when ordinary exploration stops without a valid final report.

After the first completed run, no-gain stopping received one narrow correction. If inspected source references an exact
uninspected stored symbol, the runtime can defer no-gain termination once and explicitly remind the model. It does not
automatically inspect or select the lead.

---

## 7. Experiment Chronology

### 7.1 Phase A: contract and integration implementation

The first implementation phase established:

- independent agent contracts;
- complete initial-lead conversion;
- bounded lead inspection and arbitrary source opening;
- exact, semantic, and graph navigation tools;
- persistent application-owned state;
- structured Codex JSON decisions;
- deterministic scope and citation validation;
- a compatibility adapter returning ordinary Guided Intelligence retrieval results;
- a separate `agentic` run mode with no native downstream fallback.

Focused tests demonstrated that the agent could select an artifact outside the initial Qdrant path set, reject invalid
evidence IDs, persist state across decisions, and expose provider/tool errors explicitly.

### 7.2 Mechanical failures discovered before the main completed run

| Failure | Observed behavior | Root cause | Correction |
|---|---|---|---|
| provider-native tool leakage | Codex used shell/GitHub-style tools and proposed URL evidence | JSON schema plus read-only sandbox did not make Codex a tool-less completion provider | disable provider plugins/apps/shell/unified execution |
| invalid stopping finalization | inspected artifacts disappeared when the last ordinary decision contained no findings | exploration and final synthesis were conflated | add one forced model-only synthesis decision over current inspected state |
| directory search rejected | exact search aborted when the model supplied `pandas/core/indexes` | path validation accepted only files | permit allowed file or directory scopes and return recoverable errors to state |
| unavailable API embedding/LLM account | live API calls returned `credit_balance_exhausted` | environment/account state | use explicit Codex CLI plus sparse-only test profile; do not silently substitute reasoning |
| CodeGraph runtime mismatch | `node:sqlite` was unavailable under Node 20.11 | CodeGraph required the bundled newer Node runtime | run the actual pipeline with bundled Node 24 |

These corrections made the experiment executable. They are not evidence of retrieval quality.

### 7.3 First completed run: `run-20260823T161050Z`

#### Configuration

- retrieval mode: `agentic`;
- model/provider: `gpt-5.4-mini` through Codex CLI;
- dense retrieval: disabled in the explicit testing profile;
- response generation: skipped;
- agent final evidence selection: enabled;
- initial lead store: 231 leads across 30 paths.

#### Observed navigation

The agent inspected two relevant `pandas/core/ops.py` leads:

- `_flex_method_SERIES`;
- its nested `flex_wrapper`.

The disclosed wrapper visibly called `self._binop(...)`. The exact
`pandas/core/series.py::Series::_binop` lead was already in the first 40-lead working-context projection at position
33. Its retrieval provenance ranked it first for the state-change obligation and second for the why obligation.

The agent nevertheless issued exact fixed-string searches for:

- `def __add__` in `pandas/core/series.py`;
- `def add` in `pandas/core/series.py`;
- two malformed/redundant variations of the same searches.

All four searches produced no useful evidence because pandas generated these arithmetic methods dynamically rather
than declaring literal `def add`/`def __add__` methods in `Series`.

After repeated no-gain iterations, the runtime invoked forced final synthesis. The final report explicitly recognized
that the inspected `ops.py` ranges were insufficient and that the implementation divergence was unresolved, but it
selected only the two inspected `ops.py` ranges.

#### Result

| Metric | Value |
|---|---:|
| coverage/sufficiency | `partial / false` |
| selected evidence | 2 ranges |
| Oracle overlap | 0 files |
| implementation-Oracle overlap | 0 files |
| ordinary exploration iterations | 3 |
| total model decisions including forced final | 4 |
| agent tool calls | 6 |
| agent decision tokens | 80,573 |
| total retrieval-trace LLM tokens | 89,842 |
| stop reason | `forced_final_after_no_evidence_gain` |
| native qualification/controller/island/final-selector events | 0 |

#### Exact loss-boundary diagnosis

`Series::_binop` was not absent from raw retrieval. It survived:

```text
Qdrant result
-> file grouping/held alternatives
-> CodeGraph range resolution
-> initial lead store
-> first bounded working-context projection
```

The first loss was the model's navigation decision: it ignored a visible exact lead named by inspected source. This
finding matters because improving Qdrant would not fix the observed failure.

### 7.4 Referenced-lead activation correction

The correction was deliberately narrow and split into independently tested parts:

1. persist bounded outcomes such as `matches=0` so the next model call does not have to infer whether a search failed;
2. scan inspected source for exact terminal symbol references such as `self._binop`;
3. project matching uninspected initial leads prominently in the next working context;
4. defer no-gain stopping once when such an unreminded exact lead remains actionable;
5. never automatically inspect, promote, or select the candidate.

Focused deterministic checks passed repeatedly. Two unchanged live provider calls selected `inspect_lead` for the
referenced `_binop` lead.

### 7.5 Integration run: `run-20260823T163733Z`

The actual pipeline then inspected exact stored lead `obs_7fcee82d964fc060` (`Series::_binop`) in iteration 2. This
confirmed the intended change at the natural pipeline boundary.

The run later failed before completion because the next working context exceeded the 30,000-character contract.
Accumulated inspected-source summaries and recent-source summaries duplicated much of the same source. This was an
integration failure, not a model sufficiency result, so the run is not counted as final retrieval acceptance.

The correction introduced progressive context profiles. When a context is too large, the runtime reduces the number
and preview length of initial, inspected, recent, outcome, and referenced-candidate records. Required question,
obligation, finding, uncertainty, budget, and reminded-lead state remains present. A focused regression test verifies
that the smallest projection still retains the reminded `_binop` lead.

### 7.6 Completed corrected run: `run-20260823T164358Z`

#### Observed navigation

The corrected run followed a different stochastic route. It did not immediately inspect the same stored `_binop`
lead. Instead, it:

- inspected several `ops.py` leads;
- searched for `_binop` within `pandas/core`;
- searched specifically for `def _binop` in `pandas/core/series.py`;
- opened the corresponding `series.py` implementation;
- searched for name-assignment behavior around `_binop`;
- continued trying exact and semantic searches for the generated `Series.add` path.

The earlier behavior—two empty literal searches followed by immediate no-gain surrender—did not recur. Every one of
the eight working contexts stayed within the limit, ranging from 16,801 to 27,812 serialized characters.

However, the agent still failed to ground the complete divergence. It continued looking for a literal `Series.add`
implementation even though the method was dynamically installed from the arithmetic-method factories in `ops.py`.
The run ended with two unresolved questions:

- where the generated `Series.add` wrapper preserves the left operand name;
- whether the operator path clears the name directly in `_binop` or through downstream helper behavior.

#### Result

| Metric | Value |
|---|---:|
| coverage/sufficiency | `failed / false` |
| selected evidence | 0 |
| Oracle overlap | 0 files |
| implementation-Oracle overlap | 0 files |
| agent iterations | 8 |
| agent tool calls | 19 |
| inspected artifacts | 16 |
| prompt tokens | 283,161 |
| completion tokens | 16,338 |
| total agent decision tokens | 299,499 |
| total retrieval-trace LLM tokens | 308,718 |
| stop reason | `budget_exhausted` |
| native qualification/controller/island/final-selector events | 0 |

The referenced-lead correction therefore succeeded at its stated narrow boundary but did not improve final retrieval
quality in the completed run. It moved the first loss from “ignored `_binop` before inspection” to “could not assemble
the generated `Series.add` and name-propagation mechanism after inspection.”

---

## 8. Quantitative Native-Agentic Comparison

The following table summarizes the available natural runs. It must be read together with the comparability caveats in
Section 3.3.

| Run | Mode/model | Result | Evidence | Oracle overlap | Key work | Recorded retrieval-trace LLM tokens |
|---|---|---|---:|---:|---|---:|
| `run-20260822T184944Z` | native workspace, `gpt-5.6-luna` API | `strong / true` | 9 | 2 total, 1 implementation | 4 controller rounds, 13 executed actions, native qualification/islands/final selection | 104,695 |
| `run-20260823T161050Z` | agentic, `gpt-5.4-mini` Codex CLI | `partial / false` | 2 | 0 | 4 decisions including forced final, 6 tools | 89,842 total; 80,573 agent decisions |
| `run-20260823T163733Z` | agentic integration diagnostic | incomplete | n/a | n/a | inspected exact stored `_binop`; later context-budget failure | incomplete accounting |
| `run-20260823T164358Z` | corrected agentic, `gpt-5.4-mini` Codex CLI | `failed / false` | 0 | 0 | 8 decisions, 19 tools, `_binop` opened, generated `add` unresolved | 308,718 total; 299,499 agent decisions |

### 8.1 Native run detail

The native comparison selected nine evidence owners including:

- `add_special_arithmetic_methods`;
- `add_flex_arithmetic_methods`;
- `_create_methods` and its nested `names` helper;
- `_arith_method_SERIES::wrapper` and `na_op`;
- `_flex_method_SERIES::flex_wrapper`;
- exact `Series::_binop`;
- a `TestSeries::test_op_method::check` test owner.

This is materially better mechanism coverage than either completed agentic run. It does not prove that every native
selection was equally valuable. The contemporaneous experiment record specifically judged `_create_methods::names` a
weak helper selected by a rejected dormant-island completion experiment. Thus `strong/true` and Oracle overlap should
not be equated with perfect explanation quality.

### 8.2 Token interpretation

The native 104,695 figure is the sum of all 14 `llm_response_received` usages in its retrieval trace. The first agentic
trace totaled 89,842 tokens: 80,573 for four agent decisions and 9,269 for connected-source context. The corrected
agentic trace totaled 308,718: 299,499 for eight agent decisions and 9,219 for connected-source context. Request
analysis is recorded in the orchestration trace rather than these retrieval-trace totals. The provider/model difference
still prevents a price or model-efficiency A/B claim, but the measurements reject the predicted order-of-magnitude
pipeline simplification: the corrected free agent alone spent nearly three hundred thousand decision tokens without
selecting evidence.

### 8.3 What was not measured

No claim can be made about:

- repeated agentic behavior on TypeScript and Vue natural runs;
- statistically stable sufficiency;
- API-agent performance under the same `gpt-5.6-luna` model as the native run;
- local small-model performance;
- dense-plus-sparse agentic acceptance performance;
- natural selection of final evidence outside the initial Qdrant path set;
- monetary cost under one frozen pricing snapshot.

The architecture supports these evaluations, but the experiment stopped when the primary case showed unacceptable
quality and cost.

---

## 9. Qualitative Findings

### 9.1 The initial retriever was not the main failure in the studied case

The most important forensic result is that exact `Series::_binop` was already retrieved, structurally resolved, stored,
and shown. The first agentic failure occurred during navigation. This supports the broader project observation that a
final missing file cannot be assumed absent from Qdrant without auditing every later boundary.

### 9.2 Persistent context is necessary but not sufficient

The agent did have application-owned memory. It knew the question, obligations, leads, inspected source, open
questions, attempted operations, and budgets. The first run still repeated ineffective searches because the state did
not initially make empty outcomes and exact source-referenced leads salient enough. Context possession does not imply
correct context projection or correct attention.

### 9.3 “Agentic” does not mean “just connect an API to tools”

The working system required:

- durable local state;
- bounded context construction;
- strict structured decisions;
- application-owned tool execution;
- scope and argument validation;
- deduplication and no-gain accounting;
- evidence-ID validation;
- final source re-reading;
- token/tool/iteration budgets;
- trace persistence;
- explicit provider failure handling.

The model supplied semantic choices. The application remained responsible for everything that made those choices
bounded, grounded, and reproducible.

### 9.4 Unrestricted retrieval capability did not guarantee useful exploration

Focused tests proved that the agent could open and select evidence outside the initial Qdrant paths. Neither completed
natural run selected such evidence. The corrected run had unrestricted exact, semantic, source, and graph tools, yet
spent most of its effort inside `ops.py` and `series.py`. Capability and natural policy behavior must be evaluated
separately.

### 9.5 Generic tools removed policy categories but transferred responsibility to the model

The agentic design eliminated explicit concepts such as dormant owners, maturation slots, evidence islands, and
verified-lead caps. It did not eliminate the underlying decisions:

- which lead deserves full source;
- when to follow a call;
- when to search locally or globally;
- how to recognize a generated method;
- when evidence is sufficient;
- which inspected artifacts belong in the final explanation.

Those decisions moved into repeated model calls. The resulting code boundary was conceptually cleaner, but behavior
became more expensive and less reliable in the tested case.

### 9.6 Context growth was a first-class systems problem

Even with bounded source windows, repeated decisions accumulated overlapping inspected and recent summaries. The
integration failure at iteration 7 demonstrated that context budgeting cannot be treated as prompt cleanup. It is a
runtime policy affecting whether the agent can continue and whether important leads remain visible.

### 9.7 Dynamic code-generation patterns are a difficult navigation test

Pandas did not provide literal `def add` or `def __add__` declarations on `Series`. The methods were generated and
bound through factory functions. The agent repeatedly searched for literal definitions, even after relevant factories
were present. The native system's accumulated owner/action machinery happened to retain factory, wrapper, `_binop`,
and test evidence together. This case suggests that a useful planner must reason over assignment/factory registration
and not treat identifier lookup as definition lookup only.

### 9.8 Final selection should not necessarily belong to the exploration agent

The first agentic run required forced final synthesis because ordinary stopping discarded inspected artifacts when the
last decision contained no findings. The corrected run selected nothing despite inspecting relevant code. Exploration
and evidence consolidation require different attention patterns. Combining them in one loop saved one named native
stage but did not remove the need for final comparative judgment.

---

## 10. Hypotheses Versus Results

| Hypothesis | Observation | Conclusion |
|---|---|---|
| preserve every initial lead | all 231 leads remained addressable; `_binop` could be inspected later | mechanically confirmed |
| escape Qdrant eligibility | focused fixture selected outside-path evidence; natural runs did not | capability confirmed, natural value unproven |
| improve adaptive navigation | first run ignored a visible exact lead; correction fixed that boundary; later run still failed generated-method navigation | not confirmed |
| remove early qualification loss | agent bypassed qualification completely | mechanically confirmed, but final quality did not improve |
| simplify recovery behavior | specialized native categories disappeared from agent contracts | architectural simplification confirmed |
| reduce tokens | 80,573 tokens for partial result; 299,499 for failed corrected result | rejected for current policy/provider |
| retain grounding | invalid IDs rejected and selected ranges revalidated | confirmed |
| support local/API providers | provider-neutral contract exists | architectural capability only; model-quality equivalence untested |
| stop reliably | first run stopped too early; corrected run exhausted full budget | not confirmed |
| outperform native result | native comparison retained mechanism and Oracle evidence; agentic runs did not | rejected by available case evidence |

---

## 11. Architectural Comparison

| Dimension | Native retrieval | Full seeded agentic retrieval |
|---|---|---|
| initial search | obligation-scoped Qdrant + CodeGraph | same shared prefix |
| early owner eligibility | owner comparison and qualification can suppress owners | every lead remains addressable |
| next-step planning | deterministic catalogue, pools, priorities, caps | model selects generic tools from state |
| execution safety | typed actions and deterministic executors | bounded application-owned tools |
| state representation | observations, cards, decisions, coverage, islands, actions | artifacts, findings, questions, outcomes, attempts |
| recovery | explicit deferred/maturation/island/verified-lead policies | ordinary inspect/search/graph/open operations |
| stopping | coverage plus round/action availability | model finish/fail plus no-gain and global budgets |
| final selection | separate comparative consolidation | agent proposes its own final evidence |
| strengths | predictable bounded behavior, prepared final pool, strong tracing | no hard initial eligibility, simpler conceptual operations, flexible search |
| weaknesses | policy accretion, early evidence suppression, many LLM stages | expensive context loop, stochastic navigation/stopping, weak final synthesis |

The comparison suggests that the two systems fail in complementary places. Native retrieval has stronger execution,
coverage, and consolidation structure but an overcomplicated planner. Full agentic retrieval has a cleaner navigation
model but asks one model policy to perform too many responsibilities.

---

## 12. Recommended Interpretation: A Hybrid Agent-Planned Native Controller

The strongest architectural conclusion is not to discard agentic retrieval. It is to narrow its responsibility.

The next defensible experiment would retain:

- obligation-scoped Qdrant and CodeGraph localization;
- complete observation/lead storage;
- typed and validated action/tool execution;
- exact source grounding;
- native candidate construction;
- native final evidence selection;
- global deterministic budgets and duplicate-effect guards.

It would replace only the semantic action-selection policy:

```text
shared prefix
  -> observations and source cards
  -> qualification/coverage labels treated as advisory state
  -> agent selects up to N typed actions or tool calls
  -> deterministic executor
  -> native disclosure/qualification/candidate update
  -> repeat under a small round budget
  -> native final evidence consolidation
```

This is materially different from both current modes:

- unlike native retrieval, it does not rely exclusively on fixed pool priorities to decide the next action;
- unlike the full agent, it does not make the exploring model responsible for every source summary, evidence
  qualification, obligation judgment, and final selection;
- unlike a literal “agent instead of actions” design, it retains typed actions as the safe tool interface. The agent
  replaces the **planner/scheduler**, not the executor.

The first incremental test should replace only `schedule_round_actions()` with one schema-constrained selection among
already enumerated action IDs. That isolates whether semantic model choice improves the scheduler without changing
action production or execution. A shadow run can record the model's proposed actions while still executing the native
schedule. Only repeated evidence-quality improvement should authorize live execution or later simplification of the
catalogue.

Qualification labels should be advisory to the planner rather than hard invisibility boundaries. Otherwise the hybrid
agent cannot reconsider the exact good files that motivated the experiment.

---

## 13. Threats To Validity

### 13.1 Model confound

Native and agentic runs used different models and providers. A stronger agent model might navigate the generated
method path more successfully, while a weaker model might make the native qualification stages less reliable. The
current evidence judges the implemented configurations, not an abstract optimal agent.

### 13.2 Retrieval-channel confound

The agentic test profile disabled dense search because of environment/API availability. Although exact `_binop` was
still present, the overall lead distribution differed from production hybrid retrieval.

### 13.3 Stochastic request analysis

Obligation wording and count can change between runs. This affects Qdrant queries, lead counts, and what the agent or
native controller considers sufficient.

### 13.4 Single primary repository case

Natural agentic acceptance was stopped after the pandas case. The conclusions may not transfer directly to TypeScript,
Vue, or repositories where direct symbol declarations dominate over generated APIs.

### 13.5 Oracle limitations

Oracle overlap measures whether selected files overlap the known patch/resolution files. It does not by itself measure
causal explanatory quality. Native `strong/true` results can include weak helpers, and useful non-Oracle context can be
legitimate.

### 13.6 Token-accounting boundary

Agent execution summaries and native total retrieval summaries do not necessarily include exactly the same shared
stages. Cost conclusions should therefore focus on the clear magnitude and absence of quality gain, not claim a
precise percentage difference.

### 13.7 Intervention after diagnosis

The referenced-lead correction added deterministic salience and a one-time stopping guard. It improved one observed
failure boundary, but it also demonstrates that an agentic system can begin accumulating controller-like policy if
every model mistake receives a new special rule. The correction was kept only because it is generic, bounded, and
source-grounded.

---

## 14. Reproduction

### 14.1 Checked-in configuration

The experimental benchmark profile is [`../../../configs/testing/agentic.json`](../../../configs/testing/agentic.json).
The web profile is [`../../../configs/web-ui/agentic.json`](../../../configs/web-ui/agentic.json).

The benchmark command is:

```powershell
npm run coderepoqa:evaluate:agentic -- `
  --issue-json testing/codeRepoQA/corpus/cases/pandas-dev-pandas-10068/issue.json `
  --skip-response-generation
```

Response generation is skipped because this experiment evaluates repository evidence retrieval and selection, not
explanation prose. Final evidence selection must remain enabled for an acceptance run.

### 14.2 Focused verification

The ordinary focused suite is:

```powershell
.venv\Scripts\python.exe -m unittest `
  tests.test_seeded_agentic_retrieval `
  tests.test_bm25_indexing `
  tests.test_retrieval_server `
  tests.test_qualification_first_retrieval
```

After the referenced-lead and context-compaction correction, this suite ran 168 tests successfully with one gated live
model test skipped.

The live model test is gated by `RUN_LIVE_AGENTIC_MODEL_TESTS=1` because it consumes an actual provider call. It was
run twice unchanged for the `_binop` referenced-lead decision and passed both times.

### 14.3 Required trace audit

For any later comparison, audit in this order:

1. raw dense/sparse results;
2. file representatives and held alternatives;
3. CodeGraph range resolution and all plausible owners;
4. initial lead store and bounded context appearances;
5. inspected source and exact references;
6. model decisions and tool outcomes;
7. grounded findings;
8. final evidence report and adapter validation.

Do not infer “not retrieved” from the final evidence list.

---

## 15. Thesis-Suitable Conclusions

The experiment provides five defensible conclusions.

First, **a stateful agentic retriever is technically feasible without giving the model unrestricted filesystem or shell
authority**. Persistent context can be owned by the application, tool calls can be schema-constrained, and final
citations can be deterministically grounded.

Second, **preserving all initial retrieval leads removes one class of irreversible evidence loss but does not guarantee
that a model will inspect the right lead**. The first run had exact `_binop` evidence available and visible but ignored
it. Retrieval recall and agent attention are separate boundaries.

Third, **context construction is part of the retrieval algorithm**. Tool outcomes, source references, recency,
duplication, and compaction materially changed the agent's behavior and even its ability to continue running.

Fourth, **replacing an engineered downstream pipeline with one general agent transfers rather than eliminates
complexity**. Specialized native policies disappeared from code, but the model then had to perform exploration,
qualification, sufficiency judgment, stopping, and final evidence selection through repeated large contexts. In the
tested case this was less reliable and substantially more expensive.

Fifth, **the most promising synthesis is a hybrid architecture**. Deterministic retrieval and typed tools are valuable;
the likely overengineered component is the policy that selects among them. An agent should therefore be evaluated as a
bounded semantic planner inside the native controller, while deterministic execution, grounding, and final evidence
consolidation remain outside the model.

The experiment should consequently be reported as a useful negative/diagnostic result: the broad full-agent
replacement was implemented and falsified under the tested configuration, while its observed strengths directly
motivated a narrower and more testable hybrid hypothesis.

---

## Appendix A. Run Ledger

| Run ID | Purpose | Terminal result | Main observation |
|---|---|---|---|
| `run-20260822T184944Z` | recent native comparison | `strong/true` | retained factory, wrapper, `_binop`, and test evidence; included at least one weak helper |
| `run-20260823T161050Z` | first completed full agent | `partial/false` | ignored visible `_binop`, repeated empty literal searches, selected two `ops.py` ranges |
| `run-20260823T163733Z` | referenced-lead integration | explicit runtime failure | inspected exact stored `_binop`; later exposed context-projection overflow |
| `run-20260823T164358Z` | completed correction rerun | `failed/false` | opened `_binop`, continued eight iterations, failed generated `Series.add` path, selected nothing |

## Appendix B. Failure-Boundary Movement

```text
First completed agentic run
  useful `_binop` lead survives retrieval and context
  -> model ignores exact source reference
  -> empty literal searches
  -> no-gain stop

After referenced-lead correction
  useful `_binop` lead survives retrieval and context
  -> exact reference becomes salient
  -> `_binop` is inspected/opened
  -> agent searches for generated `Series.add` behavior
  -> cannot assemble dynamic factory/metadata path
  -> global budget exhaustion
```

This is improvement at one boundary, not overall retrieval success.

## Appendix C. Decision Status

- Keep the experimental `agentic` mode isolated for research and replay.
- Do not promote it as the production/default retriever.
- Do not claim token reduction or quality improvement.
- Preserve the referenced-lead and context-compaction findings as reusable agent-runtime lessons.
- Evaluate an agent-selected typed-action scheduler as a separate incremental experiment.
- Require repeated actual-pipeline comparisons under fixed model, prompts, dense/sparse settings, index, and final
  selector before accepting any hybrid behavior.
