# Intent System Design

## Purpose

This document defines a small intent system for repository-assistance prompts. The intents describe the outcome the user wants. They influence evidence retrieval, explanation structure, understanding questions, and hints, but they do not decide how much of the requested solution the system is allowed to provide.

The teaching policy remains authoritative: the system supports the user's reasoning with grounded explanations, questions, and hints instead of directly completing the work. Intent classification and assistance permission are separate decisions.

## Core Model

Classify each task-bearing prompt with:

- exactly one `primary_intent`, representing the main requested outcome;
- zero or more `secondary_intents`, used only when the user independently requests additional outcomes;
- a target and target-resolution state;
- specificity and expected output metadata;
- solution pressure, evaluated separately by policy.

Conversation-control turns such as `clarify`, `continue`, `answer_to_check`, and `mode_change` are turn relations, not task intents.

```text
prompt + conversation state
  -> primary intent + optional secondary intents
  -> target resolution
  -> existing retrieval process
  -> retrieved evidence
       -> observational evidence-contract comparison -> display-only sufficiency marker
       -> structured answer flow -> policy-limited response -> question and hint contract
```

## Intent Contracts

Each intent owns a reusable contract rather than just a label. Its contract specifies:

- expected evidence used for an observational sufficiency comparison;
- the semantic phases expected in the response;
- a response stop condition;
- prerequisites for generating an understanding question;
- allowed question stems;
- the policy-constrained form of assistance.

| Intent | Unique purpose and boundary | Evidence contract | Response and stop condition | Question contract | Policy-constrained assistance |
|---|---|---|---|---|---|
| `explore` | Find what exists, where it lives, who owns it, and how major pieces relate. It asks for a map, not a full causal account. | Scope anchors, likely owners, entry points, boundaries, and major relations. | Present the relevant territory and connections. Stop when ownership and navigation are clear; use explanation only as connective context. | Prerequisite: a grounded scope and at least one relevant owner or relation. Stems: **What**, **Where**, **Which**. | Show where to investigate and why each entry point matters without doing the user's task. |
| `explain` | Establish how or why normal or known behavior occurs. Unlike `explore`, it requires a supported mechanism or causal path. | Trigger or entry, relevant state, ordered behavior path, constraints, and observable effect. | Follow trigger-to-effect or cause-to-result order. Stop when the requested mechanism is supported end to end, or explicitly identify the missing link. | Prerequisite: a supported relationship between at least two meaningful stages. Stems: **How**, **Why**, **What causes**. | Explain the mechanism and ask the user to reason over a key transition. |
| `use` | Show how to accomplish a goal through an existing interface. It concerns the public contract rather than internal mechanism. | Interface, inputs, preconditions, configuration, expected result, and a grounded usage example when available. | Present prerequisites, invocation, and expected outcome. Stop when the user could describe the correct usage without needing implementation internals. | Prerequisite: a grounded contract with inputs and outcome. Stems: **How**, **What is required**, **When**. | Teach the contract and guide the next usage step; avoid completing a prohibited task on the user's behalf. |
| `debug` | Diagnose abnormal behavior by connecting an observed symptom to a cause. It is distinct from explaining normal behavior. | Expected versus actual behavior, reproduction or diagnostic surface, implementation owner, causal path, and relevant constraint. | Move from symptom to localization to cause. Stop when the cause is credibly supported or when the precise unresolved diagnostic gap is known. | Prerequisite: an observed symptom plus evidence for a causal or discriminating step. Stems: **Why**, **Where**, **How does it fail**, **What distinguishes**. | Guide diagnosis and the next discriminating check; do not silently turn diagnosis into a complete fix. |
| `change` | Recognize that the user wants something added, fixed, removed, or refactored. It describes the requested outcome even when policy forbids producing it. | Current owner and behavior, extension or change points, constraints, affected dependents, and validation surface. | Establish the current limitation, relevant change surface, and consequences. Stop at the assistance boundary selected by policy. | Prerequisite: a grounded current-state model and a meaningful change decision. Stems: **What must change**, **Where**, **How would this affect**. | Identify change points, trade-offs, and a next reasoning step; withhold a complete patch when required. |
| `plan` | Produce an ordered future approach without carrying out the change. Unlike `change`, the requested artifact is the plan itself. | Goal, current state, dependencies, constraints, risks, validation points, and ordering dependencies. | Present ordered steps with rationale and validation. Stop when each step has an owner or outcome and important dependencies are explicit. | Prerequisite: at least one real dependency or sequencing decision. Stems: **What comes first**, **Why this order**, **What must be verified**. | Provide a grounded plan while leaving implementation decisions or execution to the user. |
| `review` | Make a qualitative or comparative judgment using stated criteria. It asks what is preferable or problematic, not merely whether a claim is factually true. | Reviewed artifact, relevant criteria, observed evidence, alternatives when requested, and consequences. | State findings and trade-offs in evidence order. Stop when every judgment names its criterion and supporting evidence. | Prerequisite: a concrete criterion and evidence that can be judged against it. Stems: **Should**, **Which is better**, **What is the risk**, **Why is this preferable**. | Surface issues and improvement directions without automatically rewriting the artifact. |
| `verify` | Establish whether a concrete claim holds or whether behavior is demonstrated. Unlike `review`, it seeks evidential confidence rather than a value judgment. | Claim, observable condition, test or assertion, result, and gaps or counterevidence. | Connect the claim to confirming or disconfirming evidence. Stop with supported, refuted, or explicitly unverified status. | Prerequisite: a falsifiable claim and relevant observable evidence. Stems: **Does**, **Is**, **What proves**, **How is it tested**. | Show how to establish confidence and identify missing proof; do not fabricate verification when evidence is absent. |

## Evidence Contract Is Observational

For the first intent rewrite, the evidence contract is evaluated **after the existing retrieval process has finished**. It compares the evidence that happened to be retrieved with the expectations associated with the classified intent.

The comparison produces a display-only sufficiency marker or score and may show which expected evidence areas appear covered or missing. It is diagnostic metadata for users and later evaluation, not a control signal.

It must not:

- generate or modify retrieval queries;
- change candidate ranking or filtering;
- reject, devalue, or hide evidence because it does not match the contract;
- trigger broader retrieval, retries, or additional rounds;
- act as a hard validation gate;
- determine whether response generation is allowed;
- alter policy or assistance permissions.

A low score means only that the retrieved set does not visibly cover much of the intent's expected evidence shape. It does not prove that the evidence is irrelevant or that the response is incorrect. Likewise, a high score indicates apparent coverage, not semantic truth.

The system should log the selected intent, its evidence contract, the retrieved evidence used in the comparison, and the resulting marker so this observational feature can be evaluated before any future proposal lets it influence behavior.

## Intent-Selected Narrative Profiles

The primary intent selects the semantic narrative spine. These are the default profiles:

```text
debug
symptom -> expected/actual -> evidence -> cause -> next diagnostic check

explore
what it is -> owners/users -> major relationships -> boundaries -> entry points

explain
subject -> trigger -> ordered mechanism -> state changes -> resulting effect -> why

use
goal -> prerequisites -> contract -> invocation -> result -> common constraints

change
current behavior -> change surface -> constraints -> affected paths -> validation

plan
goal -> dependencies -> ordered steps -> risks -> validation points

review
scope -> criteria -> findings -> consequences -> improvement directions

verify
claim -> observable condition -> evidence -> result -> remaining uncertainty
```

These profiles define semantic obligations and their natural order. A stage is omitted when it is irrelevant to the request, unsupported by evidence, or forbidden by policy. The profiles must not be padded with empty or generic sections merely to reproduce every listed stage.

## Combining Intents

Do not define a separate taxonomy entry or hand-written pipeline for every intent combination. That would create a combinatorial system with duplicated and inconsistent rules.

Instead, compose the contracts:

1. The primary intent supplies the requested final outcome and base response shape.
2. Secondary intents contribute only their independently requested semantic phases.
3. Evidence selected by the shared retrieval process may support more than one phase and should not be duplicated.
4. Response phases are placed into a shared semantic dependency order.
5. Policy removes or transforms disallowed phases; it never changes the classified user intent to hide solution pressure.
6. The answer planner maps retrieved evidence onto the composed phases and reports unsupported phases explicitly.

The common semantic order is:

```text
scope/target
  -> observed or current behavior
  -> mechanism/cause/constraints
  -> judgment or proposed direction
  -> validation
```

An intent selects the phases it needs. The order therefore comes from dependencies between semantic phases, not from a table of every possible intent pair.

### Example: `change` + `debug`

Prompt: "Explain why this fails and fix it."

- `change` is primary because the requested final outcome is a modification.
- `debug` is secondary because diagnosis is an independently requested and necessary prerequisite.
- `debug` contributes symptom, expected/actual, and causal phases to the answer structure.
- `change` contributes change-surface, constraints, impact, and validation phases.
- Evidence that supports more than one phase is referenced once and reused; unavailable evidence becomes an explicit unsupported point.
- The causal finding must precede the suggested change because the change depends on the diagnosis.
- Teaching policy may render the final phase as a bounded suggestion, next step, hint, or question instead of a patch.

Resulting response order:

```text
symptom -> cause -> change surface -> constraints/impact -> policy-allowed next step
```

This behavior is obtained from the two reusable contracts plus semantic dependencies. It does not require a special `change_and_debug` intent.

The same composition rule applies to every combination: the primary intent supplies the spine, while a secondary intent inserts or expands only the stages required for its independently requested outcome. For example, `explore + explain` uses the exploration spine and expands its major-relationships stage into a supported end-to-end mechanism. It does not concatenate two complete templates.

## Secondary Intent Rule

A secondary intent represents another user-requested outcome, not an internal step the system happens to perform.

For example, "How does authentication work?" is normally only `explain`. Retrieval will still locate the authentication subsystem, but that discovery work does not make `explore` a user intent. Add `explore` only if the user also asks for a map, such as "Show me where authentication is implemented and explain how it works."

This distinction prevents retrieval mechanics from leaking into semantic classification.

## Target Resolution

"Known target" means known to the pipeline at planning time, not known before the user sends a request. A target may become known from:

1. an explicit literal target in the current prompt, such as a file, symbol, route, error, or subsystem;
2. an unambiguous target carried by conversation state;
3. a lightweight target-resolution step that finds a sufficiently confident owner before deeper evidence retrieval.

Target state should be explicit:

- `explicit`: named in the prompt;
- `contextual`: resolved from active conversation state;
- `resolved`: discovered with grounded evidence;
- `unresolved`: still ambiguous.

An unresolved target changes retrieval strategy and may require clarification, but it does not automatically change the user's intent to `explore`.

## Answer Flow And Story Flow

Conceptually, the two structures have different responsibilities:

- `answer_flow` specifies the facts and relationships that must be established;
- `story_flow` specifies how those facts are presented to the reader.

They may eventually diverge so the same semantic answer can be rendered as a tutorial, concise explanation, documentation-style overview, or review. Intent, response style, verbosity, and policy may influence that later presentation layer.

For the current design, keep them identical:

```text
intent-selected narrative profile
  = answer_flow stage order
  = story_flow stage order
```

This avoids introducing two independently generated structures before their consistency contract is proven. The current implementation should first replace the universal symptom/evidence/cause shape with an intent-selected ordered stage list. A later measured change may separate presentation order from semantic order without changing the underlying facts.

## Question And Hint Generation

Question prerequisites are part of each intent contract and should be decided when the intent plan is created. The generator must not invent an understanding question until the corresponding evidence prerequisite is satisfied.

The composed question process is:

1. Select the primary intent's question contract.
2. Verify that its evidence prerequisite is satisfied by the answer flow.
3. Generate one primary question about the most important reasoning transition.
4. Add a secondary question only when a secondary intent introduces a prerequisite without which the primary outcome cannot be understood.
5. Derive the hint from the same expected answer path; do not let it reveal more solution content than policy permits.

Examples:

- `explore`: ask the user to identify the owner or boundary from the presented map.
- `explain`: ask why one stage causes or enables the next.
- `use`: ask which precondition or input is required before invocation.
- `debug`: ask which observation separates the leading cause from an alternative.
- `change`: ask which constraint the proposed change must preserve.
- `plan`: ask why one step must precede another.
- `review`: ask which criterion makes a finding important.
- `verify`: ask what evidence would confirm or refute the claim.

## Coverage Boundary

These eight intents cover task-bearing repository-assistance prompts by requested outcome:

- finding and orientation: `explore`;
- normal behavior and causality: `explain`;
- procedural application: `use`;
- abnormal behavior and diagnosis: `debug`;
- modification: `change`;
- future sequencing: `plan`;
- qualitative judgment: `review`;
- evidential judgment: `verify`.

Multi-part requests use primary and secondary labels. Turn management, social dialogue, policy state, output format, specificity, and repository topic remain separate dimensions rather than being forced into the intent vocabulary.

## Sources And Adopted Decisions

- [ISO 24617-2 dialogue-act annotation guidelines](https://dialogbank.lsv.uni-saarland.de/wp-content/uploads/2015/12/ISO24617-2_Annotation_Guidelines2017.pdf): supports separating information-seeking from requests to perform actions and distinguishes open, propositional, check, and choice questions. This informs the separation between knowledge intents, action-oriented `change`, and question form.
- [Liu, Calvo, and Rus, *G-Asks: An Intelligent Automatic Question Generation System for Academic Writing Support*](https://aclanthology.org/2012.dnd-3.4.pdf): summarizes the Graesser and Person taxonomy, including definition, comparison, causal, procedural, expectation, judgment, verification, and directive categories. Most importantly, it classifies by information sought rather than interrogative word and permits a question to have multiple categories. This supports semantic intents, multiple labels, and intent-specific question stems rather than treating `why` or `how` as intents.
- [Sillito, Murphy, and De Volder, *Asking and Answering Questions during a Programming Change Task*](https://doi.org/10.1109/TSE.2008.26): catalogs 44 developer question types around finding focus points, building on them, understanding subgraphs, and relating groups of subgraphs. This supports the `explore`/`explain` boundary and progressively retrieving owner, relation, and path evidence instead of creating dozens of top-level intents.
- [Ko, DeLine, and Venolia, *Information Needs in Collocated Software Development Teams*](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/icse07_ko.pdf): documents developer needs involving code behavior, rationale, expected behavior, failures, reproduction, and implementation work. This supports keeping `explain`, `debug`, `change`, and `verify` distinct even though their evidence can overlap.
- [Bloom's revised cognitive taxonomy, University of Utah summary](https://cte.utah.edu/instructor-education/Blooms-Taxonomy.php): provides the broad operations remember, understand, apply, analyze, evaluate, and create. It is used only as a coverage check that the proposed intents span knowledge, application, analysis, judgment, and creation; its terminology is not exposed as the product taxonomy.
- [Explanation Generation Design Conclusions](history/explanation-generation-design-conclusions.md): establishes one semantic source of truth for explanation and question generation, structured answer flow before prose, and deterministic enforcement of mechanical rules. This supports composing one evidence and answer flow rather than generating independent outputs per intent.
- [V1 Boundaries](v1_boundaries.md): defines the product constraint that assistance is grounded and scaffolded through explanation, questions, and hints rather than automated task completion. This is why policy transforms the response to `change` intent without erasing or misclassifying that intent.

## Recommended Structured Shape

```json
{
  "primary_intent": "change",
  "secondary_intents": ["debug"],
  "target_state": "explicit",
  "flow_type": "change",
  "response_phases": [
    "observed_behavior",
    "cause",
    "change_surface",
    "constraints",
    "policy_allowed_next_step"
  ],
  "question_contract": {
    "intent": "change",
    "prerequisites": ["grounded_current_state", "meaningful_change_decision"],
    "allowed_stems": ["what_must_change", "where", "how_would_this_affect"]
  }
}
```

This structure is illustrative. It records the design decisions needed before implementation without prescribing the final schema or code ownership.

## Deferred Related Work

An intent-derived pre-retrieval Evidence Plan is intentionally excluded from this design's first implementation. Its rationale, prior experiment evidence, and possible future evaluation contract are preserved separately in [Evidence Plan: Deferred Design](evidence_plan_deferred_design.md).
