# Explanation Generation Changelog

This document records the major explanation-generation changes developed during the Codex-mode evaluation work. It intentionally leaves out narrow debugging edits and records the larger changes in the order they were introduced.

## Grouped Index

### Explanation

1. [Explicit source provenance](#01-explicit-source-provenance)
2. [Non-repetitive causal storytelling](#02-non-repetitive-causal-storytelling)
3. [Evidence-confidence modes for explanation style](#03-evidence-confidence-modes)
5. [Structured source attributions and hover context](#05-structured-source-attributions)
6. [Removal of the visible Answer Path section](#06-remove-visible-answer-path)
7. [Concept definitions outside visible prose](#07-concept-definitions-outside-prose)
11. [Centralized prompts and reusable repair contracts](#11-centralized-prompt-contracts)
12. [Symptom -> evidence -> cause answer flow](#12-global-answer-flow)
15. [Explanation timeout retry and error reporting](#15-explanation-timeout-retry)
16. [Story flow planned before prose](#16-story-flow-before-prose)
17. [Coverage of all requested outcomes](#17-requested-outcome-coverage)
18. [Structured sentence-level evidence mapping](#18-structured-sentence-evidence)
19. [Deterministic inline citation rendering](#19-deterministic-inline-citations)

### Checks

4. [Conditional structured Next checks](#04-conditional-structured-next-checks)
8. [Next checks rendered separately from explanation markdown](#08-separate-next-check-rendering)
9. [Removal of phrase-based uncertainty detection](#09-remove-phrase-based-uncertainty)
10. [User-feasible and distinct Next checks](#10-feasible-distinct-next-checks)

### Questions

13. [Understanding questions derived from the answer flow](#13-questions-from-answer-flow)
14. [Generic-question prevention](#14-generic-question-prevention)

## Chronological Timeline

1. [Explicit source provenance](#01-explicit-source-provenance)
2. [Non-repetitive causal storytelling](#02-non-repetitive-causal-storytelling)
3. [Evidence-confidence modes for explanation style](#03-evidence-confidence-modes)
4. [Conditional structured Next checks](#04-conditional-structured-next-checks)
5. [Structured source attributions and hover context](#05-structured-source-attributions)
6. [Removal of the visible Answer Path section](#06-remove-visible-answer-path)
7. [Concept definitions outside visible prose](#07-concept-definitions-outside-prose)
8. [Next checks rendered separately from explanation markdown](#08-separate-next-check-rendering)
9. [Removal of phrase-based uncertainty detection](#09-remove-phrase-based-uncertainty)
10. [User-feasible and distinct Next checks](#10-feasible-distinct-next-checks)
11. [Centralized prompts and reusable repair contracts](#11-centralized-prompt-contracts)
12. [Symptom -> evidence -> cause answer flow](#12-global-answer-flow)
13. [Understanding questions derived from the answer flow](#13-questions-from-answer-flow)
14. [Generic-question prevention](#14-generic-question-prevention)
15. [Explanation timeout retry and error reporting](#15-explanation-timeout-retry)
16. [Story flow planned before prose](#16-story-flow-before-prose)
17. [Coverage of all requested outcomes](#17-requested-outcome-coverage)
18. [Structured sentence-level evidence mapping](#18-structured-sentence-evidence)
19. [Deterministic inline citation rendering](#19-deterministic-inline-citations)

## Detailed History

<a id="01-explicit-source-provenance"></a>
### 1. Explicit Source Provenance

**Reason.** Early explanations could state a workaround, symptom, environment detail, or error as if it were established by repository code even when it actually came from an issue body, title, user sample, or external runtime. The categorical-column workaround in the pandas case made the problem concrete: the explanation mentioned replacing the column with an integer but did not say that this observation came from the issue report.

**Goal.** Every important fact should reveal where it came from. Issue-reported observations should be introduced as issue evidence, retrieved code should be described as code evidence, and external behavior should remain explicitly external rather than being converted into a repository fact.

**Result.** The explanation prompt began requiring inline source language such as "The issue body reports..." and "The selected code shows...". This made claims easier to audit and reduced the impression that issue details or external failures were model inventions.

Once facts had named origins, another weakness became more visible: an explanation could still repeat the same fact under several labels instead of building understanding.

<a id="02-non-repetitive-causal-storytelling"></a>
### 2. Non-Repetitive Causal Storytelling

**Reason.** Some generated explanations reused essentially the same sentence as the symptom, evidence, and cause. Rejecting such an explanation was not enough because the request still needed a useful response, and repeated regeneration could simply reproduce the same structure.

**Goal.** Keep the symptom -> evidence -> cause progression while requiring each part to add a new piece of understanding. The system should rearrange and tighten the explanation rather than adding another fallback or open-ended retry loop.

**Result.** Prompt rules were added so that symptom, evidence, and cause had distinct jobs: establish what happened, identify what the available evidence proves, and explain why that evidence accounts for the behavior. This improved causal movement and reduced repeated paragraphs.

That clearer progression exposed a deeper distinction: not every evidence set supports the same level of certainty or the same style of explanation.

<a id="03-evidence-confidence-modes"></a>
### 3. Evidence-Confidence Modes for Explanation Style

**Reason.** A direct repository bug, a locally proven path with an inferred trigger, an external dependency failure, and insufficient retrieval should not all be narrated as a single confident root cause. Earlier explanations sometimes sounded more certain than the evidence allowed.

**Goal.** Let structured evidence status change the entire storytelling style. Direct cases should give a focused causal explanation; bounded-inference cases should separate proven local behavior from inferred links; external-unverified cases should identify the handoff boundary and plausible areas; insufficient cases should state what is missing.

**Result.** The explanation path adopted modes such as `direct`, `bounded_inference`, `external_unverified`, and `insufficient`, based on retrieval and comprehension-plan data. Uncertain explanations became more branching and explicit about what would distinguish plausible causes instead of merely adding one cautious sentence to an otherwise overconfident story.

Once uncertainty became structured, the system could provide useful follow-up actions only in the cases that genuinely needed them.

<a id="04-conditional-structured-next-checks"></a>
### 4. Conditional Structured Next Checks

**Reason.** Prompt-only requests for a visible "Next checks" paragraph were inconsistently followed. They could disappear, appear on direct answers that did not need them, or be mixed into the main explanation.

**Goal.** Represent follow-up diagnostics as structured data and require them only when unresolved evidence affects the answer. Each check needed a scenario, action, observable result, and interpretation so a one-shot user could act without another chat turn.

**Result.** A `next_checks` response field and a `next_check_requirement` contract were introduced. The backend could request a minimum count, validate the objects, and repair an insufficient set when required, while direct explanations could return no checks at all.

Structured checks solved presence and shape, but provenance still needed a richer UI treatment than repeated visible source labels.

<a id="05-structured-source-attributions"></a>
### 5. Structured Source Attributions and Hover Context

**Reason.** Naming a source in prose improved trust, but repeatedly spelling out every source could make explanations heavy. The desired UI was to keep a fact readable while allowing the user to inspect where it came from on demand.

**Goal.** Preserve normal explanatory prose while attaching traceable source metadata to important visible phrases. Source-code, issue, connected-source, and external-runtime facts needed a stable representation that the frontend could underline and explain on hover or focus.

**Result.** Explanation output gained structured `source_attributions` containing a visible quote, source kind, source reference, and note. This separated attribution metadata from prose and enabled contextual source UI without turning the explanation into a source list.

With more information moving into structured UI, the visible explanation could be simplified further.

<a id="06-remove-visible-answer-path"></a>
### 6. Removal of the Visible Answer Path Section

**Reason.** The visible Answer Path section repeated the understanding already conveyed by the explanation's causal steps. It read like internal evaluation scaffolding and made the response longer without adding a new user-facing idea.

**Goal.** Retain the structured learning path for generation and question validation, but stop rendering it as a separate explanation section.

**Result.** Answer-path information remained available to the backend and understanding-check system while the visible "Answer Path" block was removed. The main explanation became the single place where the causal story was taught.

Removing that duplicate section highlighted another kind of clutter: useful definitions and implementation context were still interrupting the main story.

<a id="07-concept-definitions-outside-prose"></a>
### 7. Concept Definitions Outside Visible Prose

**Reason.** Some explanations became long because they paused to define every contextual concept, helper, or internal term. The information could help a new reader, but showing all of it by default obscured the specific problem being explained.

**Goal.** Keep the visible explanation focused on the shortest useful causal chain while preserving definitions as optional context.

**Result.** Important terms moved into structured `concept_definitions` rendered as hover or focus help. The explanation could use a term naturally, while users who needed background could inspect it without everyone having to read a long detour.

The same separation principle then had to be applied consistently to Next checks.

<a id="08-separate-next-check-rendering"></a>
### 8. Next Checks Rendered Separately from Explanation Markdown

**Reason.** Even after `next_checks` existed as structured output, model-generated markdown could still contain a visible Next checks section. This created duplicate rendering and made frontend behavior depend on accidental prose.

**Goal.** Establish one ownership path: the model returns checks only in structured data, the response builder carries them in metadata, and the frontend renders the dedicated checks component.

**Result.** Next checks were removed from the main explanation contract and rendered exclusively from `next_checks` metadata. Defensive markdown stripping remained for leaked legacy content, but it was no longer the normal source of the UI section.

The rendering path was now clean, but the decision to request checks was still being inferred from generated wording.

<a id="09-remove-phrase-based-uncertainty"></a>
### 9. Removal of Phrase-Based Uncertainty Detection

**Reason.** The system temporarily decided whether Next checks were required by scanning generated prose for words such as "likely", "outside", or "unverified". This was brittle, domain-dependent, and disconnected from structured evidence already available before generation.

**Goal.** Decide the requirement from retrieval state, not from how the model happened to phrase its answer. Scope notes that merely recorded what retrieval did not inspect should not automatically become user-facing uncertainty.

**Result.** The phrase classifier was removed. `answer_blocking_uncertainties`, evidence presence, retrieval sufficiency, and structured scope notes now drive `next_check_requirement`. This prevented harmless scope caveats from creating unnecessary checks and eliminated an opaque string-matching branch.

Once checks were requested for the right reason, their practical quality became the next problem.

<a id="10-feasible-distinct-next-checks"></a>
### 10. User-Feasible and Distinct Next Checks

**Reason.** Some checks asked users to inspect private PyTables attributes, HDF5 metadata, debugger state, or several variants of the same underlying condition. They were technically related but unrealistic for a user working in a normal code-editing and test environment.

**Goal.** Produce checks that users can run with ordinary project commands, tests, source edits, configuration changes, or version comparisons. Multiple checks should test genuinely different scenarios rather than repeat one hypothesis with different wording.

**Result.** The generation and repair contracts required practical actions with observable `if_result` and `then_interpretation` fields. Validation rejected low-level and duplicate checks, while repair preserved useful accepted checks and replaced rejected items. The result was a smaller but more actionable set of follow-up diagnostics.

By this point, repeated prompt rules had accumulated in both Python and Markdown, making the system itself difficult to reason about.

<a id="11-centralized-prompt-contracts"></a>
### 11. Centralized Prompts and Reusable Repair Contracts

**Reason.** Explanation, question, and check instructions existed partly in Python strings and partly in Markdown prompt files. Repair prompts also copied large sections of the initial prompt, allowing nearly identical contracts to drift apart.

**Goal.** Keep model-facing behavior in Markdown files and compose prompts from reusable contracts. A repair prompt should receive the previous output and rejection reasons, then add only the repair-specific instruction rather than restating a second version of the whole contract.

**Result.** Prompt composition was centralized under `services/response_generation/prompts`. Common contracts are reused by initial generation and repair, while repair files describe only the delta. This reduced duplication, made behavior changes easier to inspect, and lowered the chance of contradictory instructions.

With the prompt system cleaner, the explanation and its understanding question could finally share one explicit semantic foundation.

<a id="12-global-answer-flow"></a>
### 12. Symptom -> Evidence -> Cause Answer Flow

**Reason.** The explanation, expected answer, and generated question could independently choose different concepts. Even a good question could be rejected because its expected points did not line up with what the explanation had actually taught.

**Goal.** Define one global `answer_flow` at the start of explanation generation. It should capture the symptom, the evidence that establishes the mechanism, the cause or strongest supported interpretation, tested concepts, and supporting evidence refs.

**Result.** `answer_flow` became a structured part of explanation output and the common source for the visible explanation and question contract. This stabilized the taught path and made the relationship between explanation content and evaluation explicit.

The next step was to stop letting question output invent a second version of that path.

<a id="13-questions-from-answer-flow"></a>
### 13. Understanding Questions Derived from the Answer Flow

**Reason.** Model-generated `expected_answer_points` and `answer_point_map` could diverge from the explanation even when the question text sounded reasonable. Missing symptom points and mismatched concepts caused intermittent "no valid understanding checks" failures.

**Goal.** Ask the model for a question about the established answer flow, while deriving the expected answer points and symptom/evidence/cause mapping from that same flow rather than trusting a parallel model-generated structure.

**Result.** Understanding questions became anchored to `answer_flow`; expected points and their mapping are produced consistently from the taught path. This removed one major source of cross-run question/answer mismatch.

That consistency made a different weakness obvious: a question could still use a vague wrapper while technically pointing to a strong expected answer.

<a id="14-generic-question-prevention"></a>
### 14. Generic-Question Prevention

**Reason.** Questions such as "Why does the reported behavior happen?" could pass because their hidden expected answer was specific, even though the visible question did not name what the reader was supposed to reason about.

**Goal.** Make the question itself visibly about the answer flow. It should name a concrete tested concept or concrete term from the symptom/evidence/cause chain without leaking an answer that the explanation did not teach.

**Result.** Prompt and validation rules tied question wording to tested concepts and answer-flow terms. Previously generic corpus cases began producing concrete questions about the actual behavior while retaining the same expected-answer contract.

After content quality stabilized, live use exposed an operational failure that corpus scoring alone had not emphasized.

<a id="15-explanation-timeout-retry"></a>
### 15. Explanation Timeout Retry and Error Reporting

**Reason.** A Codex retrieval could complete successfully, then the separate explanation LLM call could hit a read timeout. Without clear handling, the UI could make the whole run appear lost even though retrieval evidence was already available.

**Goal.** Surface the correct stage-specific error and retry explanation generation once with the same prompt and data. The retry should not introduce a different prompt, deterministic fallback, or hidden alternative behavior.

**Result.** Explanation-generation timeouts gained explicit UI-visible error reporting and a same-request retry path. Successful second attempts preserve the usable run, while repeated failure remains an explicit failure rather than silently substituting lower-quality output.

With live reliability covered, attention returned to the explanation itself: source-complete prose was still sometimes organized as one comment per evidence item.

<a id="16-story-flow-before-prose"></a>
### 16. Story Flow Planned Before Prose

**Reason.** Requiring every code claim to have evidence initially encouraged the model to walk the evidence list and write one paragraph per snippet. Citations were present, but the explanation lost its forward narrative and repeated stages such as validation and repair in different places.

**Goal.** Plan a reader-facing sequence before writing prose. The sequence should follow causal or runtime order, group helper artifacts by the phase they serve, mention loops without re-explaining earlier stages, and connect back to the global answer flow.

**Result.** A structured `story_flow` was introduced. It distinguishes opening orientation, evidence stages, bridges, and the final causal or downstream outcome. Explanations began following the behavior itself rather than repository file order.

Planning the story solved ordering, but early versions could still spend the stage budget on helper details and omit an explicit part of the user's request.

<a id="17-requested-outcome-coverage"></a>
### 17. Coverage of All Requested Outcomes

**Reason.** In the Next-check explanation, the model sometimes explained decision logic, prompt contracts, and repair details but stopped before response serialization or UI rendering, despite direct evidence for those requested stages.

**Goal.** Preserve every explicit outcome from `user_prompt` and `comprehension_plan.task_goal`. Internal helpers must be grouped or removed before they are allowed to displace a requested producer, consumer, renderer, or final output.

**Result.** Story-flow rules require an initial orientation, ordered evidence stages, and a final operational cause/result stage that reaches the requested endpoint. The model must compare its story against the original task before returning. This produced complete flows such as decision -> generation -> repair -> response metadata -> UI rendering.

At this point the narrative was complete, but citation placement still depended on the model copying or positioning exact text correctly.

<a id="18-structured-sentence-evidence"></a>
### 18. Structured Sentence-Level Evidence Mapping

**Reason.** Several citation strategies failed for the same reason. Prompt instructions did not reliably prevent paragraph-end citation groups, exact `markdown_anchor_text` values drifted when prose was rewritten, and citation markers could still be placed at the end of a paragraph. The model was being asked to plan, write, map evidence, and control final rendering simultaneously.

**Goal.** Make the model responsible only for semantic mapping: each visible sentence declares whether it is a repository `code_claim` or a non-technical `connective`, and each code claim carries the evidence refs that support that complete sentence.

**Result.** `story_flow` stages now contain ordered sentence objects with `text`, `kind`, and `evidence_refs`. Code claims without valid refs are rejected; connective sentences are explicitly uncited. Separately generated markdown, anchor text, and citation-debug placement data were removed, so the story plan and visible explanation can no longer diverge.

Once sentence-to-evidence mapping was structural, final citation placement no longer needed any model judgment at all.

<a id="19-deterministic-inline-citations"></a>
### 19. Deterministic Inline Citation Rendering

**Reason.** Even correctly mapped evidence was not enough while the model controlled where links appeared. It could omit a link, move several links to a paragraph boundary, or provide text that the backend could not match exactly.

**Goal.** Give the backend sole ownership of visual citation placement. For every structured sentence, render its text and immediately append links generated from that sentence's evidence refs; then join sentences into story-stage paragraphs.

**Result.** Citation placement is now deterministic. The model cannot move a mapped citation to another sentence or paragraph, and there is no anchor matching, citation marker, phrase heuristic, or secondary debug path. Real Codex runs across Next-check behavior, Codex model selection, and inline evidence previews consistently placed references immediately after their supporting sentences.

The remaining uncertainty is semantic rather than positional: retrieval and the model must still choose evidence that genuinely supports the claim. The renderer now guarantees that every accepted mapping is shown exactly where it belongs.

The broader engineering lessons from these changes are summarized in [Explanation Generation Design Conclusions](explanation-generation-design-conclusions.md).

<a id="20-single-generation-path-and-strict-question-contract"></a>
### 20. Single Generation Path and Strict Question Contract

**Stage boundary.** Intent classification may still provide retrieval intent and requested-output metadata, but it no longer recommends or routes a `teach`, `work`, `hybrid`, or `evaluation` mode. Retrieval, comprehension planning, explanation generation, and understanding-check generation now use one path. Bounded gap retrieval remains an independent retrieval setting.

**Expected quality impact.** Removing the mode-specific prompt bias should make evidence selection depend on the actual request and retrieval intents. Understanding-check validation now preserves accepted model fields and rejects missing, mismatched, over-limit, or invalid fields; one LLM repair is allowed, followed by an explicit error.

**Expected token impact.** Intent and retrieval prompts are slightly smaller because assistance-mode inputs and conditional instructions were removed. No material generation-token change is expected until the planned question-generation refactor introduces a separate learning-target stage.

**Regression risks.** Retrieval may choose a different evidence balance now that `teach` no longer asks for role-diverse context and `work` no longer favors implementation owners. Existing mocked policy tests also need migration to the already-required structured `story_flow` contract before they can exercise the stricter question contract end to end.

**Comparison method.** Run the configured `microsoft-TypeScript-35468` Codex smoke case at least twice, then compare run IDs, `coverage_status`, `sufficient`, retrieval token totals, evidence relevance, and explanation/question grounding with the latest comparable runs. On 2026-08-05, `npm run coderepoqa:batch:codex` failed before retrieval because the OpenAI-compatible generation endpoint, API key, and model were not configured. No fallback run was used, and no run IDs or token totals were produced.
