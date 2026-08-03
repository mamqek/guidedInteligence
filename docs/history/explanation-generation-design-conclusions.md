# Explanation Generation Design Conclusions

This note records the main engineering conclusions from the explanation-generation experiments described in the [Explanation Generation Changelog](explanation-generation-changelog.md).

## Primary Conclusion

Detailed prompt instructions are useful for expressing intent, but they do not guarantee mechanically correct output.

We repeatedly gave the model clear rules for citation placement, explanation ordering, question construction, and Next-check generation. The model often understood those rules, but behavior still varied between runs. It could place citations at the end of a paragraph, omit a requested stage, repeat the same idea, produce a generic question, or return structurally incomplete checks.

The final approach is therefore:

> When correctness can be represented structurally, ask the model for the semantic structure, validate that structure, and let deterministic code enforce the mechanical behavior.

The prompt should explain what the output means. It should not be the only mechanism responsible for properties the backend can guarantee directly.

## What Did Not Work Reliably

### Prompt-Only Formatting Rules

Instructions such as "place every citation immediately after its sentence" improved average output but did not make placement stable. The model could still group links at paragraph boundaries or forget a link.

### Exact Text Anchors

Having the model return `markdown_anchor_text` required it to predict or copy the exact wording of separately generated prose. Minor rewriting caused anchor validation to fail, even when the intended claim and evidence were correct.

### Citation Markers

Markers removed exact-text matching, but the model still controlled their position. A marker placed at the end of a paragraph produced the same undesirable result as a directly generated paragraph-end citation.

### Independent Parallel Outputs

Generating prose, an answer path, expected answer points, citation placement, and questions as separate model outputs allowed those representations to disagree. Each additional parallel representation created another consistency problem.

### Phrase-Based Classification

Inferring structured state from generated wording, such as deciding that Next checks were needed because the prose contained words like "likely" or "unverified", was brittle and domain-dependent. The decision belonged to structured retrieval state available before prose generation.

### Open-Ended Regeneration

Retrying the same task without changing its contract did not guarantee a better result. A repair call is useful only when it receives structured rejection reasons and has a narrow output responsibility. Otherwise, it can reproduce the same failure repeatedly.

## What Worked

### One Semantic Source of Truth

`answer_flow` defines the symptom, evidence, cause, tested concepts, and supporting evidence. The explanation and understanding question derive from the same path instead of inventing independent versions.

### Story Structure Before Prose

`story_flow` defines the reader-facing sequence before rendering. It follows causal or runtime order, groups helper artifacts by the phase they serve, and preserves explicit user-requested outcomes.

### Sentence-Level Claim Mapping

Each visible sentence is returned as structured data:

```json
{
  "text": "The UI fetches the available Codex models.",
  "kind": "code_claim",
  "evidence_refs": ["workspace:ui/src/App.tsx:L1601-L1614"]
}
```

A repository `code_claim` must carry valid evidence refs. A `connective` sentence may organize the story without a citation, but it cannot introduce repository behavior.

### Deterministic Rendering

The backend renders every sentence and immediately appends links generated from that sentence's evidence refs. Citation position is no longer a model decision, so citations cannot drift to another sentence or paragraph.

### Structured Conditional Features

Next checks, concept definitions, source attributions, and understanding questions use dedicated fields. The frontend renders those fields through dedicated components instead of discovering them inside explanation markdown.

### Structured Decisions Before Generation

Evidence confidence and Next-check requirements are derived from retrieval and comprehension-plan data. Generated prose describes those decisions; it does not determine them retroactively.

### Narrow Repairs

Repairs receive the rejected structured items and explicit rejection reasons. They preserve accepted items and replace only invalid output. They do not switch to a hidden fallback or regenerate the whole explanation through an unrelated prompt.

## Responsibility Boundary

The model remains responsible for semantic judgment:

- choosing the clearest explanation sequence;
- writing understandable sentences;
- mapping claims to the evidence that supports them;
- distinguishing direct evidence from inference;
- generating useful questions and diagnostic checks within their contracts.

Deterministic code is responsible for enforceable mechanics:

- validating required fields and references;
- deriving shared question-answer structures from `answer_flow`;
- deciding whether Next checks are required from structured retrieval state;
- keeping structured sections separate from explanation prose;
- rendering citations immediately after their mapped sentences;
- rejecting invalid output instead of silently substituting a fallback.

This boundary keeps the model focused on tasks that require language understanding while moving consistency-sensitive behavior into code.

## Remaining Limitation

The structural approach guarantees placement and completeness of accepted mappings, not semantic truth by itself.

The model may still select an existing evidence ref that does not fully support its sentence, especially when retrieval returns an overly broad or incomplete snippet. The backend can prove that a citation is present and correctly positioned, but it cannot establish semantic support through simple string checks without reintroducing brittle heuristics.

The remaining quality work therefore belongs primarily in:

- retrieval completeness and line-range precision;
- clearer evidence claims and responsibility labels;
- semantic evaluation of claim-to-evidence support;
- corpus testing across different repositories and explanation shapes.

## General Rule

Use prompts to communicate meaning, priorities, and judgment criteria. Use schemas to represent decisions and relationships. Use validators to reject malformed structures. Use deterministic rendering and orchestration for behavior that must happen the same way every time.

Do not keep adding prompt wording when the required behavior can instead be made impossible to violate by the system's structure.
