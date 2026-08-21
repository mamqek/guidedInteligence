# Guided Explanation Turn Model

## Decision

The old `explain -> ask -> hint` sequence should not be treated as three separate user-facing stages.

For the product experience, the first response should be one complete guided explanation turn:

```text
retrieve evidence
-> explain the relevant code behavior
-> ask understanding-check question(s)
-> attach hidden hints to those questions
```

The follow-up interaction begins when the user answers a question. At that point the system evaluates the answer and either repairs the misunderstood concept or deepens the discussion.

## Why Change The Stage Model

The previous stage sequence made sense as a policy scaffold, but it does not match the desired user experience.

In practice:

- the initial response already needs to explain the code,
- the explanation should naturally end with a question that checks understanding,
- the hint belongs with that question as an optional reveal,
- the user's next message is not a generic next stage; it is an answer to evaluate.

The useful boundary is therefore not `explain`, `ask`, and `hint` as separate modes. The useful boundary is:

```text
guided explanation turn
-> answer evaluation turn
-> repair or deepen turn
```

## Proposed Turn Types

### 1. Guided Explanation Turn

This is the first response to the user's prompt.

It should contain:

- a grounded explanation,
- citations to selected evidence,
- one primary understanding-check question by default,
- up to two secondary questions when coverage roles justify them,
- hidden hints for each question.

The explanation should stay centered on the main retrieved concept instead of trying to describe every retrieved artifact equally.

### 2. Answer Evaluation Turn

This happens when the user answers one of the understanding-check questions.

It should:

- identify which question the user is answering,
- compare the answer against expected answer points,
- mark the answer as `correct`, `partial`, or `incorrect`,
- briefly explain the evaluation,
- decide whether to repair, deepen, or move to another question.

This turn should not rerun the full initial explanation. It should respond to the user's demonstrated understanding.

### 3. Repair Turn

This happens when the user misunderstood a concept.

The repair should use a narrower prompt and a narrower evidence focus. The center concept is the part the user answered incorrectly about.

Full retrieval does not need to run again by default. The repair path should prefer:

1. reuse the evidence already selected for the original run,
2. inspect the evidence attached to the missed question,
3. run partial retrieval only if the existing evidence cannot support a focused correction.

The repair explanation should be much shorter than the initial explanation. If the guided explanation turn asks three questions, then each possible repair explanation should target roughly one third of the initial explanation budget, so three incorrect answers can still fit into a reasonable total interaction length.

Approximate response budget:

```text
initial explanation turn: 900-1200 words max
single-question repair: 250-350 words max
three-question repair set: about the same total size as one initial explanation
```

The repair turn should end with either:

- a revised version of the same question, or
- a smaller check focused only on the corrected concept.

### 4. Deepening Turn

This happens when the user answers correctly.

It should:

- confirm the correct understanding,
- connect the concept to the next most relevant role or adjacent file,
- optionally ask a harder follow-up question.

Deepening should not feel like a new broad retrieval session unless the user explicitly asks for a wider investigation.

### 5. Completion Turn

This happens when the relevant understanding checks have been answered or skipped.

It should summarize:

- what the user now understands,
- which code responsibilities were covered,
- which concepts remain uncertain or unverified,
- where the user could inspect or change code next.

## Question Selection

The intent system generates one to three understanding questions and never completes a successful guided explanation with zero. It selects the smallest sufficient set: one question by default, with a second or third only for an independently important reasoning transition that tests a materially different relationship. Every check declares a single `reasoning_focus` and `selection_reason`; an added check must introduce a new target stage or supporting evidence reference. Each check selects a classified task intent, copies that intent contract's prerequisite stage IDs exactly, uses an allowed stem family, and grounds the question in evidence used by its target or prerequisite stages. Retrieval roles do not define question semantics, and additional questions are not allocated mechanically per intent or stage.

## Question Object Shape

Each understanding-check question is represented as structured data before rendering:

```json
{
  "id": "q1",
  "intent": "explain",
  "target_stage_ids": ["explain.ordered_mechanism"],
  "prerequisite_stage_ids": [
    "explain.trigger",
    "explain.ordered_mechanism",
    "explain.resulting_effect"
  ],
  "stem_family": "why",
  "reasoning_focus": "parser output enables downstream validation",
  "selection_reason": "This handoff is the central mechanism the explanation asks the user to understand.",
  "question": "Why does this parser path matter for abstract class support?",
  "expected_answer_points": [
    "It identifies the syntax or modifier before later validation.",
    "It creates the representation that downstream stages inspect."
  ],
  "hints": [
    {"kind": "direction", "text": "Trace what representation is created before validation."},
    {"kind": "focus", "text": "Look at which syntax node or modifier the parser produces."},
    {"kind": "scaffold", "text": "The parser creates the representation that the later validation stage inspects; identify the important handoff."}
  ],
  "evidence_refs": [
    "repo-pre:src/parser.ts:L10-L35"
  ]
}
```

The rendered UI reveals the three hints one at a time. The first gives only a reasoning direction, the second identifies the relevant grounded area, and the third starts the connection without supplying the complete answer. The singular `hint` field has been removed rather than retained as a compatibility fallback.

## Answer Evaluation Shape

Answer evaluation should also be structured.

Suggested shape:

```json
{
  "question_id": "q1",
  "status": "partial",
  "matched_points": [
    "It identifies the syntax or modifier before later validation."
  ],
  "missing_points": [
    "It creates the representation that downstream stages inspect."
  ],
  "next_turn": "repair",
  "repair_focus": "downstream representation created by parser output"
}
```

This gives the control layer enough information to choose a repair or deepening turn without hiding the decision inside free-form prose.

## Retrieval Behavior For Follow-Ups

The first guided explanation turn may use the full retrieval pipeline.

Follow-up turns should usually avoid full reruns.

For answer evaluation:

- no retrieval is needed unless the user's answer introduces a new claim that must be checked.

For repair:

- use the question's evidence refs first,
- then use the original role bucket,
- then run partial retrieval only for the repair focus if needed.

For deepening:

- use adjacent role buckets from the original run,
- run partial retrieval only if the requested deeper concept was not covered.

This keeps the interaction fast and prevents the system from drifting away from the concept being taught.

## UI Implications

The local web UI should render the initial result as:

- explanation,
- evidence panel,
- understanding checks,
- hidden hints,
- answer input tied to a specific question.

When the user answers, the UI should show:

- correctness status,
- matched and missing points,
- focused repair or deepening response,
- revised or next question.

The UI should make it clear why each question exists by labeling its origin:

- primary role,
- supporting role,
- verification role,
- caller flow,
- diagnostic or test evidence.

## Replacement For Current Stage Names

The old names can remain internally during migration, but the target vocabulary should be:

```text
guided_explanation
answer_evaluation
repair
deepen
completion
boundary
```

`boundary` remains useful for policy violations such as direct solution requests or unsupported source usage.

## Final Target

The final product should feel like an evidence-grounded code tutor:

1. Explain the code path using retrieved evidence.
2. Ask targeted understanding checks based on retrieved roles.
3. Give optional hints without forcing them into separate turns.
4. Evaluate the user's answer.
5. Repair only the misunderstood concept with narrower evidence and a shorter response.
6. Deepen only when the user has shown enough understanding.

This keeps retrieval central, but makes the user experience centered on guided comprehension instead of stage mechanics.
