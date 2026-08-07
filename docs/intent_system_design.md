# Intent System Design

## Purpose And Scope

This document is the implementation contract for task intent classification and its connections to retrieval context, answer/story flow, explanation generation, questions, and hints.

The first implementation includes the eight intents defined here. It does **not** include a pre-retrieval Evidence Plan. The separate teaching policy remains authoritative: intent records what outcome the user requested; policy decides how much help may be given. Conversation control, presentation format, and retrieval's internal planning are separate concerns.

## Core Model

Classify each task-bearing prompt into one or more unique `intents`:

- `explore`, `explain`, `use`, `debug`, `change`, `plan`, `review`, or `verify`;
- a target plus `explicit`, `contextual`, `resolved`, or `unresolved` target state;
- specificity, confidence, and classification basis;
- solution pressure, evaluated separately by policy.

There is no primary/secondary hierarchy. If the prompt independently requests several outcomes, retain each applicable intent. Discovery performed internally by retrieval is not an extra user intent.

Do not retain `UserGoal`, `ResponseOperation`, `RetrievalIntent`, or `ExpectedOutput` as parallel metadata. Output/presentation format may be designed later as an orthogonal feature; it is not part of this rewrite.

Conversation-control turns such as `clarify`, `continue`, `answer_to_check`, and `mode_change` remain turn relations rather than task intents.

```text
prompt + conversation state
  -> selected task intents + target state
  -> minimal intent context -> existing retrieval process
  -> retrieved evidence
       -> deterministic intent-stage union -> LLM-selected permutation
       -> identical story flow -> policy-limited explanation
       -> intent/stage-based question and hint
       -> optional display-only sufficiency observation (production-disabled)
```

## Intent Contracts

Each intent owns a reusable contract: a neutral retrieval description, semantic response stages, an evidence sufficiency contract, a stop condition, question prerequisites and stems, and the policy-constrained form of assistance.

| Intent | Unique purpose and boundary | Evidence contract | Response and stop condition | Question contract | Policy-constrained assistance |
|---|---|---|---|---|---|
| `explore` | Find what exists, where it lives, who owns it, and how major pieces relate. It asks for a map, not a full causal account. Exploration may explain relationships briefly, but stops when territory and ownership are clear. | Scope anchors, likely owners, entry points, boundaries, and major relations. | Present the relevant territory and connections. Stop when ownership and navigation are clear. | Prerequisite: grounded scope and at least one owner or relation. Stems: **What**, **Where**, **Which**. | Show where to investigate and why each entry point matters without doing the user's task. |
| `explain` | Establish how or why normal or known behavior occurs. Unlike `explore`, it continues until it establishes a supported trigger-to-effect or cause-to-result path. | Trigger or entry, relevant state, ordered behavior path, constraints, and observable effect. | Follow trigger-to-effect or cause-to-result order. Stop when the requested mechanism is supported end to end, or identify the missing link. | Prerequisite: a supported relationship between at least two meaningful stages. Stems: **How**, **Why**, **What causes**. | Explain the mechanism and ask the user to reason over a key transition. |
| `use` | Show how to accomplish a goal through an existing interface. It concerns the public contract rather than internal mechanism. | Interface, inputs, preconditions, configuration, expected result, and a grounded example when available. | Present prerequisites, invocation, and expected outcome. Stop when correct usage is clear without unnecessary internals. | Prerequisite: a grounded contract with inputs and outcome. Stems: **How**, **What is required**, **When**. | Teach the contract and guide the next usage step without completing prohibited work. |
| `debug` | Diagnose abnormal behavior by connecting an observed symptom to a cause. It differs from explaining known normal behavior. | Expected versus actual behavior, reproduction or diagnostic surface, implementation owner, causal path, and relevant constraint. | Move from symptom through localization to cause. Stop when the cause is credibly supported or the unresolved diagnostic gap is precise. | Prerequisite: an observed symptom plus evidence for a causal or discriminating step. Stems: **Why**, **Where**, **How does it fail**, **What distinguishes**. | Guide diagnosis and the next discriminating check; do not silently turn diagnosis into a complete fix. |
| `change` | Record that the user wants something added, fixed, removed, or refactored. It describes the outcome even when policy restricts implementation. | Current owner and behavior, change points, constraints, affected dependents, and validation surface. | Establish current behavior, change surface, and consequences. Stop at the assistance boundary selected by policy. | Prerequisite: a grounded current-state model and meaningful change decision. Stems: **What must change**, **Where**, **How would this affect**. | Identify change points, trade-offs, and a next reasoning step; withhold a complete patch when required. |
| `plan` | Produce an ordered future approach without carrying out the change. Unlike `change`, the requested artifact is the plan. | Goal, current state, dependencies, constraints, risks, validation points, and ordering dependencies. | Present ordered steps with rationale and validation. Stop when outcomes and important dependencies are explicit. | Prerequisite: at least one real dependency or sequencing decision. Stems: **What comes first**, **Why this order**, **What must be verified**. | Provide a grounded plan while leaving execution to the user. |
| `review` | Make a qualitative or comparative judgment using stated criteria. It asks what is preferable or problematic, not merely whether a claim is true. | Reviewed artifact, relevant criteria, observed evidence, alternatives when requested, and consequences. | State findings and trade-offs in evidence order. Stop when each judgment names its criterion and support. | Prerequisite: a concrete criterion and evidence that can be judged against it. Stems: **Should**, **Which is better**, **What is the risk**, **Why is this preferable**. | Surface issues and improvement directions without automatically rewriting the artifact. |
| `verify` | Establish whether a concrete claim holds or behavior is demonstrated. Unlike `review`, it seeks evidential confidence rather than a value judgment. | Claim, observable condition, test or assertion, result, and gaps or counterevidence. | Connect the claim to confirming or disconfirming evidence. Stop with supported, refuted, or explicitly unverified status. | Prerequisite: a falsifiable claim and relevant observable evidence. Stems: **Does**, **Is**, **What proves**, **How is it tested**. | Show how to establish confidence and identify missing proof; never fabricate verification. |

## Minimal Intent Context For Retrieval

Retrieval receives the selected labels, their fixed neutral descriptions, specificity, and explicit targets. This provides outcome context without prescribing what evidence to find.

```json
{
  "intents": [
    {
      "intent": "explain",
      "description": "Establish how or why the requested behavior works."
    }
  ],
  "specificity": "medium",
  "explicit_targets": []
}
```

| Intent | Retrieval-facing description |
|---|---|
| `explore` | Locate and orient the user within the relevant repository area and its major relationships. |
| `explain` | Establish how or why the requested behavior works. |
| `use` | Establish how an existing interface is invoked, configured, or integrated. |
| `debug` | Investigate the reported abnormal behavior and its likely cause. |
| `change` | Gather context needed to reason about a requested modification without implementing it. |
| `plan` | Gather context needed to propose an ordered future approach. |
| `review` | Gather context needed to assess an artifact or approach against relevant criteria. |
| `verify` | Gather context needed to determine whether a concrete claim is supported. |

This context can influence the retriever's general posture. For example, `explore` favors orientation while `explain` follows a mechanism deeply enough to support how/why understanding. `explain` never implies editing files; modification is `change`, and proposing an approach is `plan`.

Do not pass evidence-contract expectations, evidence objectives, response stages, question contracts, file roles, artifact quotas, required file kinds, generated search queries, or retrieval stop rules. The existing retrieval planner remains free to discover whichever evidence actually answers the prompt. This deliberately avoids the anchoring risk of the deferred Evidence Plan.

## Intent-Selected Flow Contracts

Each selected intent contributes all of its semantic stage obligations:

```text
debug:   symptom -> expected/actual -> evidence -> cause -> next diagnostic check
explore: what it is -> owners/users -> major relationships -> boundaries -> entry points
explain: subject -> trigger -> ordered mechanism -> state changes -> resulting effect -> why
use:     goal -> prerequisites -> contract -> invocation -> result -> common constraints
change:  current behavior -> change surface -> constraints -> affected paths -> validation
plan:    goal -> dependencies -> ordered steps -> risks -> validation points
review:  scope -> criteria -> findings -> consequences -> improvement directions
verify:  claim -> observable condition -> evidence -> result -> remaining uncertainty
```

These are predefined semantic obligations, not generic vocabulary invented per response. For a single intent, use the listed flow. For several intents:

1. Take the union of every selected intent's stages.
2. Give that complete, fixed stage set to the answer-planning LLM.
3. Let the LLM return only a permutation of those stage IDs, choosing an order that makes the combined explanation coherent and concise.
4. Validate deterministically that the output contains exactly the supplied stage IDs: no invented, dropped, duplicated, renamed, or semantically merged stages.
5. Closely related stages may be presented together in the prose, but they remain distinct obligations in the structured flow. Unsupported obligations explicitly state uncertainty or missing support rather than disappearing.
6. Policy may limit what a stage says, especially for `change`, but it must not erase the classified intent or its semantic obligation.

No intent-pair templates, primary-intent spine, global deterministic phase order, or allowed insertion-point matrix is needed.

Example for "Explain why this fails and fix it": selected intents are `debug` and `change`. The system supplies every `debug.*` and `change.*` stage; the LLM may return this ordering:

```text
debug.symptom -> debug.expected_actual -> debug.evidence -> debug.cause
  -> change.current_behavior -> change.change_surface -> change.constraints
  -> change.affected_paths -> debug.next_check -> change.validation
```

The order is model-selected and schema-validated as an exact permutation of the supplied IDs. Teaching policy constrains the content written for relevant stages; it does not add, remove, or rename a flow stage. This is not a special `debug_change` contract.

## Intent Selection Rule

Use several intents only when the prompt independently requests several outcomes. "How does authentication work?" is normally only `explain`; retrieval locating the subsystem does not add `explore`. "Show me where authentication is implemented and explain how it works" selects both `explore` and `explain`.

This keeps internal retrieval work out of semantic classification while avoiding an artificial priority between genuine user outcomes.

## Target Resolution

A target can be named explicitly, carried by conversation state, resolved by a lightweight repository step, or remain unresolved. An unresolved target may change retrieval posture or require clarification, but it does not automatically add `explore`.

## Answer Flow And Story Flow

Conceptually:

- `answer_flow` lists the facts and relationships that must be established;
- `story_flow` controls how those facts are presented.

They may later diverge for tutorials, concise answers, documentation, or reviews. In this implementation they use the same ordered stages. Build the stage set from the selected intent contracts, ask the LLM only to arrange that set, and use the validated order for both `answer_flow` and `story_flow`. Do not ask the LLM to invent either flow or generate two independent plans.

```text
fixed stages from selected intent contracts
  -> deterministic union
  -> LLM returns a permutation of the supplied stage IDs
  -> exact-set validation
  -> answer_flow order = story_flow order
```

This replaces the universal symptom/evidence/cause structure without prematurely adding a separate presentation system.

## Question And Hint Generation

Question prerequisites are selected with the intents. The generator uses the union of selected intents' question contracts and the completed canonical flow. It generates an adaptive set of one to three useful questions about distinct supported reasoning transitions, not one question per intent or stage.

The generator chooses the smallest sufficient set: one question is the default; a second or third is justified only when it tests a materially different relationship and covers an independently important part of the requested outcome. Examples include ownership/boundary, trigger/mechanism/effect, constraint/impact, and claim/verification. Each question declares one `reasoning_focus` plus a `selection_reason`. Additional questions must introduce a new target stage or supporting evidence reference. Broad stages may be shared when they contain separate evidence-backed transitions, but question meaning may not be repeated.

The generator must:

1. choose only a question contract belonging to a selected intent;
2. identify one or two flow stages it assesses, including a stage belonging to that intent, and verify that the question evidence supports its target or prerequisite stages;
3. choose an allowed stem family based on the information sought, not merely its interrogative word;
4. derive expected answer points and the hint from the same cited flow stages;
5. respect the same teaching-policy boundary as the explanation.

Every successfully generated guided explanation must contain at least one validated question. Empty output, more than three questions, duplicate IDs or text, overlapping target stages, invalid contracts, and unrelated evidence references trigger the existing single repair attempt. A second invalid result fails explicitly rather than silently omitting questions or synthesizing a deterministic fallback.

The new question shape should include `intent`, `target_stage_ids`, `prerequisite_stage_ids`, `stem_family`, `reasoning_focus`, `selection_reason`, question text, expected answer points, hint, and evidence references. It replaces `prediction`, `re_explanation`, `trace`, `why`, `transfer`, free-form `question_type`, retrieval-role `role`, `origin`, and `PlanUnderstandingCheck`.

Examples: `explore` asks for an owner or boundary; `explain` asks why one stage enables the next; `use` asks for an invocation precondition; `debug` asks for a discriminating observation; `change` asks which constraint must be preserved; `plan` asks why one step precedes another; `review` asks which criterion supports a finding; `verify` asks what would confirm or refute the claim.

## Observational Sufficiency Marker

This is **not** an Evidence Plan. It runs only after retrieval and is not required for retrieval or explanation/question generation. It must be disabled in production for the first implementation and guarded by an explicit experimental flag.

When enabled, use a hybrid evaluator:

- an LLM judges semantic coverage of each selected intent's evidence expectations;
- deterministic code rejects nonexistent references, normalizes statuses, and calculates the summary.

```json
{
  "intent": "debug",
  "areas": [
    {
      "expectation": "observed symptom",
      "status": "covered",
      "evidence_refs": ["ref-1"],
      "reason": "The issue and cited code establish the failing behavior."
    },
    {
      "expectation": "causal connection",
      "status": "partial",
      "evidence_refs": ["ref-2"],
      "reason": "The internal path is shown, but the triggering condition is missing."
    }
  ],
  "overall": "partial"
}
```

Allowed statuses are `covered`, `partial`, `missing`, and `unclear`. Deterministic summary: all covered -> `covered`; all missing -> `missing`; all unclear -> `unclear`; every mixed set, or any `partial`, -> `partial`. Calculate one result per selected intent and optionally a display aggregate using the same rule.

The marker must never generate queries, rank/filter/reject evidence, trigger retries, gate generation, modify policy, or be fed back into the explanation. Low coverage does not imply irrelevant evidence; high coverage does not prove truth.

## Coverage Boundary

The fixed set covers task-bearing repository requests by requested outcome: orientation (`explore`), normal mechanism (`explain`), procedural application (`use`), abnormal diagnosis (`debug`), modification (`change`), future sequencing (`plan`), qualitative judgment (`review`), and evidential judgment (`verify`). Multi-outcome prompts select multiple labels.

Turn relation, social dialogue, policy state, specificity, repository topic, and future output formatting remain orthogonal dimensions.

## Implementation Arrangement

Implement the replacement as connected vertical slices; do not delete a live producer before migrating its consumers, and do not retain the old path as fallback or compatibility behavior.

### Intent package is the single source of truth

All fixed values derived from an intent must be owned by `services/intent/`, with one canonical registry in `services/intent/contracts.py`. The registry contains, once per `TaskIntent`:

- the neutral retrieval-facing description;
- the fixed ordered answer-flow stage IDs;
- the evidence expectations used only by the optional observational sufficiency evaluator;
- the response boundary and stop condition;
- question prerequisites and allowed stem families;
- any fixed labels needed to serialize or display the contract.

`services/intent/models.py` owns the domain types (`TaskIntent`, `IntentContract`, selected-intent context, target state, and composed flow-plan types), while `contracts.py` owns the concrete eight contract instances. Splitting types from values does not create two sources of truth: no consumer may redefine concrete intent values.

Expose narrow intent-package operations such as:

```text
get_intent_contract(intent)
build_retrieval_intent_context(selection)
compose_contract_stage_ids(selection)
get_question_contracts(selection)
```

Downstream boundaries consume those results:

- the classifier schema derives its allowed intent labels from `TaskIntent`;
- retrieval receives only `build_retrieval_intent_context(...)`;
- the flow planner receives `compose_contract_stage_ids(...)` and returns their validated permutation;
- explanation generation receives the resolved ordered flow and evidence, not copied per-intent stage tables;
- question/hint generation receives the selected question contracts and resolved flow;
- the optional sufficiency evaluator receives evidence expectations after retrieval;
- API/logging/UI receive serialized selected intents and resolved runtime data, not independent intent definitions.

Static prompt files may explain how to use a contract, but must not duplicate the eight labels, stage lists, question mappings, or descriptions. Insert the registry-derived contract payload into the LLM input at runtime. If the TypeScript UI ever needs the full catalog, serve or generate it from the backend registry; do not maintain a handwritten second catalog.

Add contract-integrity tests that fail when an intent lacks a description, stages, evidence expectations, or a question contract; when stage IDs are not uniquely namespaced; when a consumer uses an unknown stage/stem; or when the classifier schema and registry disagree.

1. **Intent contract and classification**
   - Replace the old models in `services/intent/models.py` with `TaskIntent`, selection/target metadata, and fixed contracts (a separate `contracts.py` is appropriate).
   - Replace the classifier prompt, output schema, normalizer, and tests.
   - Remove `UserGoal`, `ResponseOperation`, `RetrievalIntent`, and `ExpectedOutput` completely.
2. **Pipeline context**
   - Replace `services/intent/retrieval_hints.py` with the minimal intent context above and migrate `core/control_layer.py` plus retrieval consumers.
   - Remove `services/intent/agreement.py`; intent conformance is separately deferred.
3. **Flow and explanation**
   - Replace role-derived explanation ordering and fixed symptom/evidence/cause models, prompts, validators, repair prompts, expected-answer mappings, fixtures, and tests with the deterministic intent-stage union plus an LLM-selected, exact-set-validated ordering.
   - Keep evidence items, citations, concept definitions, depth policy, answer evaluation, repair, and deepen behavior after migrating them to the new flow.
4. **Questions and hints**
   - Replace the old pedagogical check types and all `PlanUnderstandingCheck`/follow-up consumers atomically with the intent/stage-based question contract.
5. **API and UI**
   - Update API types, logs for new runs, and UI rendering to the new intent, flow, and question shapes.
   - Do not add readers or UI branches for historical response metadata. Historical log files can remain stored but need not render in the updated UI.
6. **Optional sufficiency experiment**
   - Add only behind a production-disabled flag. It is observational and is not a prerequisite for completing the intent rewrite.

Retrieval's internal workspace/Codex planning, candidate roles, and selection machinery remain unless a concrete consumer migration makes a piece dead. They are retrieval implementation details, not competing task intents.

The repository audit identified these active migration surfaces:

- classification and handoff: `services/intent/`, `core/control_layer.py`, and `services/retrieval/codex/provider.py`;
- flow/explanation and follow-up: `services/comprehension/`, `services/response_generation/`, `services/guidance/questions.py`, `core/response_builder.py`, and `services/retrieval/server.py`;
- serialization and clients: `core/logging_schema.py`, `ui/src/api.ts`, and `ui/src/App.tsx`;
- active verification: `tests/test_intent.py`, `tests/test_comprehension_checks.py`, `tests/test_codex_provider.py`, `tests/test_retrieval_server.py`, and affected policy/pipeline tests;
- benchmark tooling that reads response shapes: `testing/codeRepoQA/run_case.py`.

Stored benchmark outputs and historical log files are records, not active compatibility targets, and should not be rewritten.

## Removal Checklist

Remove together with the relevant consumer migrations:

- the old `UserGoal`, `ResponseOperation`, `RetrievalIntent`, and `ExpectedOutput` enums and every schema field, mapping, config, prompt, fixture, test, API type, and UI surface that refers to them;
- the old intent agreement comparison;
- fixed `answer_flow.symptom/evidence/cause` and fixed story relations `symptom/evidence/cause/bridge`;
- old role-derived narrative ordering;
- `prediction`, `re_explanation`, `trace`, `why`, `transfer`, free-form `question_type`, question `role`/`origin`, and `PlanUnderstandingCheck`;
- all compatibility and fallback branches for these replaced representations.

Keep policy intent/solution-pressure enforcement, conversation turn relations, source evidence and citations, deterministic reference validation, and retrieval-internal machinery with distinct responsibilities.

## Deferred Intent-Conformance Validation

The old agreement module should not be repurposed in this rewrite. A future LLM evaluator could observe whether a response follows the selected intents and flow, but it adds cost and latency. If tried later, it must begin as optional observational telemetry, never a hidden retry or fallback.

## Recommended Structured Shape

```json
{
  "intents": ["debug", "change"],
  "target": {
    "state": "explicit",
    "values": ["reported failure"]
  },
  "contract_stage_ids": [
    "debug.symptom",
    "debug.expected_actual",
    "debug.evidence",
    "debug.cause",
    "debug.next_check",
    "change.current_behavior",
    "change.change_surface",
    "change.constraints",
    "change.affected_paths",
    "change.validation"
  ],
  "flow": {
    "ordered_stage_ids": [
      "debug.symptom",
      "debug.expected_actual",
      "debug.evidence",
      "debug.cause",
      "change.current_behavior",
      "change.change_surface",
      "change.constraints",
      "change.affected_paths",
      "debug.next_check",
      "change.validation"
    ],
    "stage_evidence": {
      "debug.symptom": ["ref-1"],
      "debug.cause": ["ref-2"],
      "change.change_surface": ["ref-3"]
    }
  },
  "question": {
    "intent": "debug",
    "target_stage_ids": ["debug.cause"],
    "prerequisite_stage_ids": ["debug.symptom", "debug.evidence"],
    "stem_family": "what_distinguishes"
  }
}
```

The canonical `flow.ordered_stage_ids` supplies both answer flow and story flow for now. Mechanical validation checks known and unique intent labels, valid references, and exact set equality between `contract_stage_ids` and `ordered_stage_ids`. The LLM makes semantic classification, combined-stage ordering, explanation, and question choices; it does not invent, delete, or merge contract stages. Failures surface explicitly rather than falling back to the legacy system.

## Sources And Adopted Decisions

- [ISO 24617-2 dialogue-act annotation guidelines](https://dialogbank.lsv.uni-saarland.de/wp-content/uploads/2015/12/ISO24617-2_Annotation_Guidelines2017.pdf): separates information-seeking from action requests and distinguishes question forms. This informed the task-intent/policy/question separation.
- [Liu, Calvo, and Rus, *G-Asks*](https://aclanthology.org/2012.dnd-3.4.pdf): classifies questions by information sought, permits multiple categories, and includes causal, procedural, judgment, and verification forms. This informed semantic multi-label intents and intent-specific question contracts.
- [Sillito, Murphy, and De Volder, *Asking and Answering Questions during a Programming Change Task*](https://doi.org/10.1109/TSE.2008.26): distinguishes locating focus points and relationships from understanding larger execution subgraphs. This informed the `explore`/`explain` boundary.
- [Ko, DeLine, and Venolia, *Information Needs in Collocated Software Development Teams*](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/icse07_ko.pdf): documents distinct needs around behavior, rationale, failures, reproduction, and implementation work. This supports separate `explain`, `debug`, `change`, and `verify` intents.
- [Bloom's revised taxonomy, University of Utah summary](https://cte.utah.edu/instructor-education/Blooms-Taxonomy.php): used only as a coverage check across understanding, application, analysis, evaluation, and creation; its vocabulary is not exposed.
- [Explanation Generation Design Conclusions](history/explanation-generation-design-conclusions.md): supports one semantic source of truth, structured flow before prose, and deterministic mechanical validation.
- [V1 Boundaries](v1_boundaries.md): establishes grounded, scaffolded assistance and the separation between requested outcome and permitted assistance.

## Deferred Related Work

An intent-derived pre-retrieval Evidence Plan is excluded from this implementation. Its rationale, experiment history, and possible future contract are preserved in [Evidence Plan: Deferred Design](evidence_plan_deferred_design.md).
