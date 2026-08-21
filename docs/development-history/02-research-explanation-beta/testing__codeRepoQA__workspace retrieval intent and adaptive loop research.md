# Workspace Retrieval Intent And Adaptive Loop Research

## Purpose

This note establishes a research-backed direction for a future workspace retrieval rewrite. It addresses two questions:

1. Does adaptive role expansion require retrieval, reranking, snippet selection, and sufficiency assessment to run as a loop?
2. How should request intent map to the first evidence objectives, and are the current retrieval roles adequate for that mapping?

This is a design note, not an implemented behavior change.

Step2-specific follow-up: [workspace retrieval step2 source-grounded planner design.md](workspace%20retrieval%20step2%20source-grounded%20planner%20design.md) is the authoritative planner-design artifact for future role/objective selection. It supersedes the preliminary intent/objective mapping in this note where the two differ. That follow-up is grounded in extracted full text from the accessible priority papers, not abstracts or NotebookLM summaries.

## Step2 Source-Grounded Decisions

The Step2 restructure should be treated as a planner-contract change, not a retrieval-engine rewrite. The planner should emit request intent, specificity, active evidence objectives, deferred objectives, preferred structural relations, and stop/expansion conditions. `stage.py` should then execute retrieval rounds and decide whether the evidence satisfies that contract.

| Step2 decision | Source-backed reason | Primary sources |
|---|---|---|
| Start narrow defect reports with `implementation_owner`, not the universal five-role set. | Bug localization research frames the task as ranking source files likely to need a fix, and structured source fields improve localization compared with flat text. | Zhou, Zhang, and Lo, "Where Should the Bugs Be Fixed? More Accurate Information Retrieval-Based Bug Localization Based on Bug Reports"; Saha, Lease, Khurshid, and Perry, "Improving Bug Localization Using Structured Information Retrieval" |
| Treat docs/config/tests as evidence kinds that can be promoted, not unconditional first-pass roles. | Developer questions often require composing heterogeneous evidence, but which domains are needed depends on the question; retrieving every domain upfront is not implied by the evidence. | Fritz and Murphy, "Using Information Fragments to Answer the Questions Developers Ask"; Ko, DeLine, and Venolia, "Information Needs in Collocated Software Development Teams" |
| Add explicit `behavior_path`, `dependent_callers`, and relation objectives. | Many hard questions are about reachability, causal paths, subgraphs, and relations between code elements rather than isolated files. | LaToza and Myers, "Developers Ask Reachability Questions"; Sillito, Murphy, and De Volder, "Questions Programmers Ask During Software Evolution Tasks" |
| Make query specificity control expansion. | Search behavior and IR query-reformulation work show that targeted/scoped queries and vague/verbose queries need different treatment. | Sadowski, Stolee, and Elbaum, "How Developers Search for Code: A Case Study"; Haiduc et al., "Automatic Query Reformulations for Text Retrieval in Software Engineering" |
| Use bounded evidence-driven rounds instead of one unconditional broad retrieval pass. | Iterative retrieval can improve repository context when later queries are informed by earlier evidence, but it must be bounded by marginal value and stop conditions. | Zhang et al., "RepoCoder: Repository-Level Code Completion Through Iterative Retrieval and Generation"; Haiduc et al., "Automatic Query Reformulations for Text Retrieval in Software Engineering"; Sadowski, Stolee, and Elbaum, "How Developers Search for Code: A Case Study" |
| Keep verification-only benchmark comments out of retrieval anchors. | This is a benchmark-validity constraint for this project: verification material should evaluate retrieval, not seed it. | Project policy decision; not derived from the papers |

The first implementation pathway should therefore keep the current role names as compatibility aliases, but stop making them the planner's conceptual model. Step2 should select objectives first, then map those objectives to legacy roles only at the execution boundary until benchmark comparisons prove the new objective vocabulary is stable.

## Executive Conclusions

### 1. The current pipeline is staged and partially iterative, but it is not an adaptive outer loop

The current flow in `services/retrieval/workspace/stage.py` is approximately:

```text
plan fixed roles
  -> narrow candidate files
  -> retrieve all required roles
  -> responsibility expansion and rerank
  -> refine selected owner roles
  -> assess sufficiency
  -> recover weak required roles once
  -> optionally retrieve all supporting roles once
  -> final deterministic coverage gate
```

It already contains useful loop components:

- responsibility expansion from first-pass candidates;
- file-level reranking;
- snippet refinement for selected roles;
- synthesis feedback and follow-up queries;
- one weak-role recovery pass;
- one conditional supporting-role pass.

However, it does not have a controller that can:

- reassess the request intent after observing evidence;
- promote a subset of deferred evidence objectives;
- run the same complete retrieval cycle again for those objectives;
- compare marginal evidence gain against cost;
- stop after a bounded number of adaptive rounds.

The current summary explicitly reports `exploration_rounds: 0`, and file-role expansion is effectively capped to one pass with `range(min(MAX_FILE_ROLE_RESOLUTION_ROUNDS, 1))`.

### 2. The present roles are not a clean intent taxonomy

The current role set mixes code responsibilities with artifact types:

- responsibilities: `representation`, `input_parsing`, `validation_checking`, `diagnostics`, `behavior_output`;
- artifact types: `tests`, `docs`, `config`.

This causes three problems:

- there is no explicit `implementation_owner` objective even though owner discovery is the central retrieval goal;
- there is no explicit execution/dependency-path objective for reachability and impact questions;
- tests, documentation, and configuration are treated like semantic responsibilities even though they are better modeled as evidence kinds that can satisfy different objectives.

The replacement should separate:

1. request intent;
2. evidence objective;
3. structural relation;
4. artifact/source kind.

## Current Flow Assessment

### What can be reused

The rewrite should preserve the current low-level machinery:

- candidate generation through CGC and Qdrant;
- responsibility profiling;
- graph/reference expansion;
- file-level reranking;
- snippet refinement;
- deterministic coverage checks;
- synthesis feedback and follow-up query generation.

These are the inner operations of a retrieval round.

### What is missing

The missing piece is a bounded outer controller around those operations. The controller should own:

- the active intent profile;
- active evidence objectives;
- deferred evidence objectives;
- round-specific acceptance criteria;
- promotion and broadening decisions;
- remaining tool/token/time budget;
- evidence gain between rounds.

The current planner should not emit one permanently fixed list of required roles. It should emit an initial search contract plus deferred objectives and expansion conditions.

## Proposed Adaptive Retrieval Controller

### Control flow

```text
classify request intent and specificity
  -> create initial evidence objectives and stop contract
  -> retrieval round
       discover candidates
       expand structural neighbors
       rerank files
       select/refine snippets
       assess objective coverage
  -> sufficient? stop
  -> weak evidence for an active objective? retry that objective with feedback
  -> owner grounded but explanation incomplete? promote the smallest deferred objective set
  -> search direction contradicted by evidence? revise intent profile once
  -> no useful gain or budget exhausted? return explicit partial result
```

### Round state

A future `RetrievalRoundState` should contain at least:

- `primary_intent`;
- `secondary_intents`;
- `specificity`;
- `active_objectives`;
- `deferred_objectives`;
- `objective_coverage`;
- `accepted_anchors`;
- `unresolved_questions`;
- `round_index`;
- `tool_calls_used`;
- `retrieval_tokens_used`;
- `evidence_gain`;
- `stop_reason`.

### Expansion decisions

Expansion should be based on evidence state, not merely on whether every role bucket is strong.

Useful generic transitions are:

- no credible owner: broaden owner discovery or traverse structural neighbors;
- owner found but symptom-to-cause path missing: add control-flow/dependency evidence;
- behavior path found but expected/actual distinction unclear: add verification or contract evidence;
- public interface found but implementation unclear: add implementation-owner evidence;
- change owner found but impact unknown: add callers, references, configuration consumers, and verification evidence;
- evidence gain is negligible: stop instead of adding every remaining objective.

### Recommended bounds

Start with a maximum of three rounds:

1. focused initial objectives;
2. same-objective recovery or the smallest deferred-objective promotion;
3. final controlled broadening.

The planner should normally run once. A full intent reclassification should be allowed only when retrieved evidence contradicts the initial classification. This limits LLM drift and token growth.

## Request Intent Model

The literature does not provide one universally accepted intent taxonomy that directly maps to repository artifacts. The strongest foundation is a synthesis of:

- empirical developer question taxonomies;
- observed program-comprehension and navigation behavior;
- concept-location and bug-localization research;
- modern repository-level issue-localization systems.

The intent classifier should be multi-label. Real requests often combine intent, such as "explain why this fails and show where to fix it."

### Proposed top-level intents

| Intent | Typical request | Initial evidence objectives | Deferred objectives | Initial stop contract |
|---|---|---|---|---|
| Defect localization | Find why a reported behavior is wrong and where it is owned | symptom surface, implementation owner, nearest behavioral constraint | control flow, diagnostics, verification, configuration | credible owner plus evidence connecting the symptom to that owner |
| Behavior explanation | Explain how or why a behavior occurs | interface/entry, control flow, data/state, effects/output | constraints, configuration, diagnostics | a supported path from entry or trigger to externally visible effect |
| Feature or change planning | Identify where and how a requested behavior should be added | interface/entry, implementation owner, data/state, verification | control flow, configuration, usage contract | owner and extension point plus constraints and validation surface |
| Impact or refactor analysis | Determine what depends on a symbol or behavior | implementation owner, callers/references, dependency path | configuration consumers, tests, public contract | bounded dependent set with at least one validating path for each important branch |
| Repository exploration | Understand architecture, subsystem boundaries, or responsibilities | subsystem owners, interfaces, dependency structure | configuration, usage contracts, representative tests | coherent subsystem map with explicit boundaries and major relations |
| API or usage lookup | Learn how to invoke or integrate a capability | public interface, usage contract, examples/call sites | implementation owner, configuration, verification | callable contract plus one grounded usage example |
| Configuration or runtime behavior | Explain how settings alter execution | configuration definition, parser/loader, consumer, constraints/defaults | effects/output, diagnostics, verification | path from setting definition through consumption to behavior |
| Verification or test analysis | Find how behavior is asserted or reproduced | verification artifact, behavior owner, fixture/setup constraints | diagnostics, configuration, control flow | assertion/reproduction linked to the implementation behavior it constrains |

These are planner intents, not final evidence roles. They decide which evidence objectives become active first.

## Evidence Objective Model

### Proposed objectives

| Evidence objective | Meaning | Current-role compatibility |
|---|---|---|
| `implementation_owner` | Code that owns the behavior or policy under investigation | missing; currently inferred indirectly across all owner-bearing roles |
| `interface_entry` | Public API, command, handler, route, callback, or other entry surface | partly covered by `input_parsing` and `behavior_output` |
| `data_state` | Core representations, state, models, and transformations | replacement/clarification for `representation` |
| `control_flow` | Calls, dispatch, reachability, dependency paths, and orchestration | missing as an explicit objective |
| `constraints_validation` | Guards, semantic checks, invariants, policy, defaults, and rejection rules | broader and clearer form of `validation_checking` |
| `effects_output` | Returned values, mutations, emitted events, rendering, persistence, and external effects | clearer form of `behavior_output` |
| `observability_diagnostics` | Errors, logs, warnings, telemetry, and diagnostic construction | clearer form of `diagnostics` |
| `verification` | Tests, assertions, reproducers, fixtures, and executable checks | semantic objective replacing artifact-only `tests` |
| `configuration` | Setting definitions, loading, precedence, defaults, and consumers | semantic objective replacing artifact-only `config` |
| `usage_contract` | Documentation, examples, call sites, compatibility promises, and expected use | semantic objective replacing artifact-only `docs` |

### Structural relations

Objectives should be queried through explicit relations where available:

- defines / implemented_by;
- calls / called_by;
- references / referenced_by;
- reads / writes;
- validates / constrained_by;
- emits / handles;
- configures / configured_by;
- tests / tested_by;
- documents / exemplifies;
- imports / depends_on.

This is important because many developer questions are relational. A lexical role alone cannot cleanly express "what can reach this function?", "who consumes this option?", or "which implementation produces this diagnostic?"

### Artifact kinds

Artifact kind should remain a separate attribute:

- production source;
- test/reproducer;
- configuration;
- documentation/example;
- generated source;
- build/deployment definition;
- issue/change history, when policy permits it.

For example, a test can satisfy `verification`, demonstrate `usage_contract`, expose an `interface_entry`, or reveal a configuration dependency. It should not be limited to one fixed supporting role.

## Planner Output Shape

A future plan should resemble:

```json
{
  "primary_intent": "defect_localization",
  "secondary_intents": ["behavior_explanation"],
  "specificity": "narrow",
  "active_objectives": [
    "implementation_owner",
    "constraints_validation",
    "verification"
  ],
  "deferred_objectives": [
    "control_flow",
    "observability_diagnostics",
    "configuration"
  ],
  "preferred_relations": [
    "implemented_by",
    "validated_by",
    "tested_by"
  ],
  "stop_contract": {
    "required": ["credible_owner", "symptom_owner_connection"],
    "one_of": ["behavioral_reproducer", "executable_constraint"]
  },
  "expansion_policy": {
    "on_missing_owner": ["broaden_owner_candidates", "follow_structural_neighbors"],
    "on_missing_causal_path": ["promote:control_flow"],
    "on_missing_expected_behavior": ["promote:verification", "promote:usage_contract"]
  }
}
```

This is a search contract, not a rigid template. The LLM should choose objectives from a controlled vocabulary and provide structured expansion conditions.

## Migration Path

### Phase 1: Introduce intent metadata without changing behavior

- Add primary intent, secondary intents, and specificity to the Step 2 schema.
- Log classifications and compare them against benchmark cases.
- Continue using the current roles unchanged.

### Phase 2: Add objective aliases and adaptive first-pass selection

- Add `implementation_owner` and `control_flow` first because they fill the clearest gaps.
- Map existing roles to the new objective vocabulary.
- Let narrow requests activate only the objectives needed by their stop contract.

### Phase 3: Extract one reusable retrieval round

- Refactor the existing required-role retrieval, rerank, refinement, and assessment sequence into a round function.
- Preserve all current candidate and snippet machinery.
- Make round input explicit: active objectives, accepted anchors, feedback queries, and remaining budget.

### Phase 4: Add the bounded outer controller

- Promote deferred objectives based on unresolved evidence requirements.
- Stop on sufficiency, negligible evidence gain, or budget exhaustion.
- Record each round and promotion decision.

### Phase 5: Retire artifact-type roles

- Replace `tests`, `docs`, and `config` role buckets with objective plus artifact-kind filtering.
- Keep compatibility aliases until benchmark comparisons show stable quality.

## Stage Boundary

The responsibility split should be:

- `step2`: classify intent and specificity; emit active/deferred objectives, preferred relations, stop contract, and expansion policy;
- `stage.py`: execute bounded rounds, maintain evidence state, evaluate deterministic gates, and promote objectives;
- existing retrieval helpers: remain responsible for candidate discovery, expansion, reranking, and snippet refinement.

The planner should decide what evidence is needed. The stage should decide whether the evidence obtained satisfies that contract and which allowed transition to execute next.

## Expected Impact And Risks

### Expected quality impact

- higher precision on narrow bug and usage requests;
- better handling of reachability, impact, and architecture questions that the current roles do not express directly;
- fewer irrelevant support artifacts in the first pass;
- clearer stop conditions tied to the user request instead of universal role coverage;
- controlled recovery when the initial intent or owner hypothesis is incomplete.

### Expected token and tool impact

- lower first-pass cost for narrow requests;
- additional cost only when evidence-driven expansion occurs;
- one planner call in the normal path;
- up to three retrieval rounds, with hard tool, token, and time budgets;
- reduced duplicate work if accepted anchors and candidates are carried between rounds.

### Regression risks

- intent misclassification can narrow retrieval incorrectly;
- too many objectives can recreate the current breadth problem under new names;
- repeated rounds can multiply latency if evidence gain is not measured;
- objective promotion can become LLM-driven drift unless transitions are constrained;
- artifact-kind removal can weaken tests/docs/config retrieval if compatibility mappings are removed too early;
- a universal stop contract is not sufficient; each intent needs its own evidence requirements.

## Evaluation Plan

Before changing behavior, label a mixed benchmark set with:

- primary and secondary intent;
- specificity;
- expected owner artifact;
- expected evidence objectives;
- expected structural relations;
- minimum sufficient evidence.

Then compare current and experimental retrieval on:

- owner-file recall and rank;
- function/snippet recall and precision;
- `coverage_status` and `sufficient`;
- retrieval token totals;
- tool calls and elapsed time;
- number of adaptive rounds;
- objectives promoted per round;
- evidence gain per round;
- noise share in final evidence.

Use at least:

- narrow defect localization cases;
- symptom-to-cause cases;
- feature/change requests;
- reachability or impact questions;
- architecture exploration questions;
- API/usage questions;
- configuration-driven behavior questions.

Per repository policy, run the actual retrieval pipeline and record run IDs. A behavior change should not remain enabled if two real-run comparisons show quality regression or unstable sufficiency.

## Selected Research Foundation

The following sources were selected because they directly inform developer intent, evidence needs, iterative retrieval, or repository issue localization. The role/objective model above is a synthesis; no single paper prescribes it verbatim.

### Review priority and intended use

These papers are not equal in importance. When PDFs are available, review and synthesize them in this order so future notes do not mix foundational evidence with secondary comparison material.

| Priority | Sources | Intended use |
|---|---|---|
| 1. Must-read foundation | Sillito 2006; Sillito 2008; Ko 2007; LaToza reachability 2010; Sadowski 2015; BugLocator 2012; BLUiR/Saha 2013 | Ground the request-intent taxonomy, the evidence-objective vocabulary, and the basic issue/code-localization model. These should drive the rewrite assumptions. |
| 2. Pipeline-design support | Fritz and Murphy 2010; LaToza hard questions 2010; relevance feedback 2009; query reformulation 2013; RepoCoder 2023; reasoning-for-context-retrieval 2024; OrcaLoca 2025; SweRank 2025 | Inform adaptive rounds, feedback, sufficiency checks, reranking, and cost/precision tradeoffs. These should refine the architecture, not replace the foundations. |
| 3. Secondary comparison | Agentless 2024; CoSIL 2025; GraphLocator 2025; Sim/Clarke/Holt 1998 | Use for comparison, terminology, and sanity checks. Promote any of these only if full-text review shows a directly useful mechanism for our workspace retrieval design. |

Do not exclude a source solely from abstract-level reading. If all PDFs are available, keep them in NotebookLM or an ignored local paper folder, but only promote a paper to "foundation" after full-text review supports a concrete design claim.

### Developer questions and information needs

1. Sillito, Murphy, and De Volder, "Questions Programmers Ask During Software Evolution Tasks" (FSE 2006).  
   https://doi.org/10.1145/1181775.1181779  
   Selected for its hierarchy of questions developers ask while moving from an initial focus point toward broader relationships and behavior.

2. Sillito, Murphy, and De Volder, "Asking and Answering Questions during a Programming Change Task" (TSE 2008).  
   https://doi.org/10.1109/TSE.2008.26  
   Selected for empirical evidence that change work progresses through multiple question types and information sources rather than one static search.

3. Ko, DeLine, and Venolia, "Information Needs in Collocated Software Development Teams" (ICSE 2007).  
   https://doi.org/10.1109/ICSE.2007.45  
   Selected for its broader information-needs taxonomy, including code, people, history, rationale, and task context.

4. Fritz and Murphy, "Using Information Fragments to Answer the Questions Developers Ask" (ICSE 2010).  
   https://doi.org/10.1145/1806799.1806828  
   Selected for the idea that answers require composing heterogeneous information fragments instead of retrieving one uniformly typed result.

5. LaToza and Myers, "Developers Ask Reachability Questions" (ICSE 2010).  
   https://doi.org/10.1145/1806799.1806829  
   Selected because reachability, callers, and runtime paths are common information needs that the current flat role set does not represent.

6. LaToza and Myers, "Hard-to-Answer Questions about Code" (PLATEAU 2010).  
   https://doi.org/10.1145/1937117.1937125  
   Selected for its taxonomy of difficult code questions, especially rationale, behavior, dependencies, and implications of change.

### Code-search behavior and concept location

7. Sim, Clarke, and Holt, "Archetypal Source Code Searches: A Survey of Software Developers and Maintainers" (WPC 1998).  
   https://doi.org/10.1109/WPC.1998.693351  
   Selected as an early empirical foundation showing that source search has recurring target and task archetypes.

8. Sadowski, Stolee, and Elbaum, "How Developers Search for Code: A Case Study" (ESEC/FSE 2015).  
   https://doi.org/10.1145/2786805.2786855  
   Selected for large-scale evidence about real code-search behavior, query reformulation, and the difference between lookup and exploratory search.

9. Gay, Haiduc, Marcus, and Menzies, "On the Use of Relevance Feedback in IR-based Concept Location" (ICSM 2009).  
   https://doi.org/10.1109/ICSM.2009.5306315  
   Selected for evidence that feedback from initial retrieval can improve subsequent concept-location queries.

10. Haiduc et al., "Automatic Query Reformulations for Text Retrieval in Software Engineering" (ICSE 2013).  
    https://doi.org/10.1109/ICSE.2013.6606630  
    Selected for systematic query reformulation based on properties of the initial query and retrieval task.

### Bug and issue localization

11. Zhou, Zhang, and Lo, "Where Should the Bugs Be Fixed? More Accurate Information Retrieval-Based Bug Localization Based on Bug Reports" (ICSE 2012).  
    https://doi.org/10.1109/ICSE.2012.6227210  
    Selected for the core formulation of bug reports as queries over candidate source files and the importance of file ranking.

12. Saha, Lease, Khurshid, and Perry, "Improving Bug Localization Using Structured Information Retrieval" (ASE 2013).  
    https://doi.org/10.1109/ASE.2013.6693093  
    Selected because structured code fields such as classes and methods improve localization beyond flat document similarity.

13. Xia et al., "Agentless: Demystifying LLM-based Software Engineering Agents" (2024).  
    https://arxiv.org/abs/2407.01489  
    Selected for its simple localization-repair-validation decomposition and evidence that bounded, interpretable stages can compete with complex agents.

14. Jiang et al., "CoSIL: Issue Localization via LLM-Driven Iterative Code Graph Searching" (2025).  
    https://arxiv.org/abs/2503.22424  
    Selected for controlled broad file-level exploration followed by deeper function-level graph search and pruning.

15. "GraphLocator: Graph-guided Causal Reasoning for Issue Localization" (2025).  
    https://arxiv.org/abs/2512.22469  
    Selected for explicitly modeling symptom-to-cause and one-to-many issue localization through iterative graph expansion.

16. "On The Importance of Reasoning for Context Retrieval in Repository-Level Code Editing" (2024).  
    https://arxiv.org/abs/2406.04464  
    Selected for the finding that reasoning helps context precision but remains weak at judging sufficiency, supporting deterministic stop contracts.

### Iterative repository retrieval

17. Zhang et al., "RepoCoder: Repository-Level Code Completion Through Iterative Retrieval and Generation" (EMNLP 2023).  
    https://aclanthology.org/2023.emnlp-main.151/  
    Selected for using first-pass generated/discovered code context to improve later retrieval iterations.

18. "OrcaLoca: An LLM Agent Framework for Software Issue Localization" (2025).  
    https://arxiv.org/abs/2502.00350  
    Selected for action decomposition, priority scheduling, relevance scoring, and distance-aware context pruning.

19. "SweRank: Software Issue Localization with Code Ranking" (2025).  
    https://arxiv.org/abs/2505.07849  
    Selected for efficient retrieve-then-rerank issue localization and for treating issue descriptions as distinct from short code-search queries.

## Research Limitations

- The project NotebookLM MCP is now authenticated and can see the 19-source notebook, but during the Step2 follow-up pass its `ask_question` endpoint repeatedly returned the stale access-check answer instead of answering new questions. The Step2 design follow-up therefore uses directly extracted full-text PDFs from accessible paper sources, not NotebookLM summaries.
- The general web-search endpoint returned an access error during this research. Primary-source discovery and verification therefore used the repository's existing bibliography, Crossref, OpenAlex, Semantic Scholar metadata/abstracts, arXiv, ACL Anthology, and DOI records.
- The source list is a reading queue plus preliminary selection. The Step2 follow-up upgrades the planner-role claims using full-text review for the accessible priority papers; remaining sources should still be promoted only after full-text review supports a concrete design claim.
- The proposed intent-to-objective map is an engineering synthesis that must be validated against this project's benchmark distribution before implementation.
> Historical retrieval research. The retrieval-local `primary_intent`/`secondary_intents` proposal was superseded on 2026-08-06 by the central task `IntentContext`; examples below are retained only as experiment history.
