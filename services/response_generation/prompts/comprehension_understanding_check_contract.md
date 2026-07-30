Understanding checks:

First return a single global `answer_flow` for the whole explanation. This is the canonical story path that the visible explanation teaches and the understanding check tests.

Use this `answer_flow` object shape:

```json
{
  "symptom": "The issue-reported behavior the user sees.",
  "evidence": "The selected code fact or handoff that establishes the relevant mechanism.",
  "cause": "The strongest supported cause, or the bounded interpretation when the final trigger is external or unverified.",
  "tested_concepts": ["concept from this flow", "another concept from this flow"],
  "evidence_refs": ["evidence-ref"]
}
```

`answer_flow.symptom`, `answer_flow.evidence`, and `answer_flow.cause` must be written as final answer points, not labels or fragments. They should be specific enough that a reader could answer the check from them.

Return checks only in the `understanding_checks` JSON field, not in the markdown body.

Each understanding check must be derived from this same `answer_flow`; do not invent a separate path for the question. Build the question around the concrete symptom or tested concept from `answer_flow`, then let the expected answer explain the evidence and cause.

The check object still includes `expected_answer_points` and `answer_point_map` for API compatibility, but those fields are mirrors of `answer_flow`, not another place to restate or reinterpret the answer.

Use this check object shape:

```json
{
  "id": "q1",
  "role": "reader",
  "question_type": "why",
  "question": "Why does <concrete symptom or tested concept from answer_flow> behave this way?",
  "expected_answer_points": [
    "<copy answer_flow.symptom exactly>",
    "<copy answer_flow.evidence exactly>",
    "<copy answer_flow.cause exactly>"
  ],
  "hint": "Connect the reported symptom to the code behavior described in the explanation.",
  "evidence_refs": ["evidence-ref"],
  "origin": "model_generated",
  "tested_concepts": ["<copy one or more answer_flow.tested_concepts exactly>"],
  "answer_point_map": [
    {"kind": "symptom", "point": "<copy answer_flow.symptom exactly>"},
    {"kind": "evidence", "point": "<copy answer_flow.evidence exactly>"},
    {"kind": "cause", "point": "<copy answer_flow.cause exactly>"}
  ]
}
```

Field rules:

- The question should test a concrete proposition from the explanation's symptom -> evidence -> cause chain.
- The question text must name at least one concrete term from `answer_flow.tested_concepts`, `answer_flow.symptom`, `answer_flow.evidence`, or `answer_flow.cause`.
- The question must not give away the answer by restating the full evidence or cause. Keep the question focused on the concrete behavior; put the evidence and cause in `expected_answer_points`.
- Do not use generic wrapper questions like "Why does the reported behavior happen?" The question must tell the reader what specific behavior, API, file, state, option, or data shape it is asking about.
- If multiple candidate checks ask the same idea in different words, keep the strongest one and discard the rest.
- The answer must be reachable from the generated markdown without adding new repository facts.
- Use concrete file, function, module, class, state, behavior, or data-shape names when they are part of the taught explanation.
- Ask about the real user-facing behavior and the reason behind it, not about evidence mechanics.
- The visible markdown must already teach the semantic chain for the check using the same important domain terms.
- `expected_answer_points` must be exactly the three `answer_flow` points in symptom/evidence/cause order.
- `answer_point_map` must map exactly those same strings to `symptom`, `evidence`, and `cause`.
- `tested_concepts` must copy one to six concepts from `answer_flow.tested_concepts`.
- Do not ask a generic component-role question such as "What role does this file play?"
- Do not ask why a "part" matters. Do not use retrieval role wording such as "main implementation behavior", "entry point or parsing", "state or representation", "supporting context", "output or emission", or "validation or checking".
