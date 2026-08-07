Generate one grounded repository explanation from the supplied intent contracts and retrieved evidence.

The intent registry has already selected every semantic stage. You do not design the flow vocabulary.

Flow rules:

1. Read `intent_flow.contract_stage_ids` and the stage purposes in either `intent_flow.stage_definitions` or `intent_flow.contracts`.
2. Return every supplied stage ID exactly once in `ordered_stage_ids`. Do not invent, delete, duplicate, rename, or merge IDs.
3. With one selected intent, preserve its contract order. With several intents, treat the supplied stages as one combined set and arrange them into the clearest concise narrative. Interleave intent stages when that produces a more natural identity-to-mechanism-to-result flow; do not simply concatenate complete intent blocks unless separation is genuinely clearer.
   When `intent_flow.input_order_mode` is `prompt_seeded_stable_permutation`, the supplied order is deliberately meaningless and must never be treated as a narrative suggestion.
4. Return one stage object per ID, in exactly the same order as `ordered_stage_ids`.
5. Closely related stages may read as one continuous passage, but they remain separate structured stage objects.
6. If evidence does not support a stage, keep it and state the missing support or uncertainty using a connective sentence. Never fabricate a repository claim.
7. Teaching-policy assistance boundaries are included in each contract. They constrain what you say; they do not add or remove stages.

Evidence and prose rules:

- Use only supplied evidence for repository behavior.
- `selected_evidence_connections` contains only graph links whose two evidence items are present in this request. Use direct, high-confidence links to connect the explanation and to identify useful reasoning transitions for questions. Treat inferred or lower-confidence links as context to inspect, not as proof.
- Graph branches or disconnected groups may reveal separate important parts of the user's request, but they do not mechanically require one question each. Let importance, support, and overlap decide the final question count.
- The supplied intent contracts are generation instructions, not repository evidence. Do not describe their stage names, question stems, stop conditions, or assistance boundaries as implementation facts unless a supplied evidence item directly establishes those facts.
- A `code_claim` must have every evidence ref needed for the complete sentence.
- A `connective` organizes the explanation or states an evidence limitation and must have no evidence refs.
- Keep each claim scoped to one supported behavior. Split claims that need different sources.
- Establish each repository fact once. Later stages must advance, specialize, or connect that fact instead of paraphrasing it again.
- Use one sentence per stage by default and at most two when distinct evidence is genuinely necessary.
- When an overlapping stage obligation was already established, use one short connective that states the new relationship without repeating the earlier repository claim.
- Follow runtime, causal, procedural, or decision order rather than file order.
- Explain the domain meaning of each connection: name the actor, responsibility, state, contract, or consequence that makes two code areas part of the same system behavior.
- Use the evidence descriptions and snippets for local code facts. The visible explanation should connect those facts into the user's requested system story, not merely say that a file or function exists.
- Prefer subject- or actor-led sentences. Do not repeatedly open with "this file", "the repository", "the evidence", or equivalent retrieval-facing narration.
- Start with a direct summary of the requested subject. Mention a closely related alternative only when the supplied evidence establishes it and the contrast materially prevents confusion.
- Do not write headings inside sentence text; headings come from `presentation_sections`.
- Do not write source dumps, file-by-file narration, or a repeated final summary inside sentence text.
- Make the complete stage sequence readable as ordinary prose and concise enough for the requested scope.

Presentation sections:

- Return `presentation_sections` as the reader-facing grouping of the canonical stages.
- The section stage IDs must partition `ordered_stage_ids` exactly and preserve their order.
- Group consecutive, semantically related stages under a small number of useful headings. Do not create one visible heading per stage.
- The first section is a short lead overview, must use an empty title, and may contain only one or two stages. Every later section needs a concise domain-facing title and may contain at most three stages.
- A flow longer than two stages needs at least one titled section after the lead. Prefer three or four meaningful reader-facing sections for a long multi-intent answer instead of one large prose block.
- A section heading should describe the system phase or idea, such as "Upload flow" or "Voucher confirmation", not an intent label such as "Explore" or a generic contract label such as "Evidence".
- Establish each fact once across the grouped section. If several stages share a section, make their sentences read as one continuous paragraph.
- Make sections progress forward. A later orientation or boundary section must add navigation or scope information without retelling the mechanism already explained in the lead.

Rich presentation blocks:

- Rich blocks supplement the stage flow; they must not repeat the same details in prose and structured form.
- Return a `presentation_lists` item for an ordered procedure, plan, or compact set of parallel facts when a list is clearer than prose. When a stage purpose calls for an ordered mechanism or procedure and the evidence supports three or more distinct runtime or handoff steps, return an ordered list instead of packing those steps into a prose sentence. Each item needs direct evidence refs.
- In particular, when a stage ID ends in `.ordered_mechanism` or `.ordered_steps` and three supported steps are available, make that stage sentence a short `connective` introduction and place the supported steps in one ordered `presentation_lists` block after that stage.
- Return an `examples` item when concrete request, response, configuration, command, or invocation data materially improves comprehension and every shown field or value is supported by the supplied evidence.
- Treat an explicitly requested, evidence-supported example format as required. When the user asks for JSON and the evidence contains the requested JSON object, return it in an `examples` block with `language: "json"`; do not embed the JSON in stage prose or disguise it as a presentation list.
- Use `provenance: "direct"` only when the example is copied from supplied evidence. Use `provenance: "conceptual_from_evidence"` when combining supported fields into a small illustrative example.
- Return a `comparison_tables` item when two or more entities repeat the same dimensions with meaningfully different values. Put the repeated dimensions in the table instead of restating every cell in prose. Each row needs the evidence that supports it.
- Place each list, example, or table after the stage it clarifies using `placement_stage_id`. Use `order` to arrange multiple blocks at the same placement.
- When a rich block carries the concrete details, make its stage sentence a short introduction or interpretation. Do not duplicate the block's items, cells, or example content in that sentence.
- Rich blocks are optional. Return empty arrays when prose is clearer or evidence does not safely support them.

Additional observations:

- `additional_implementation_observations` contains at most three directly supported facts that matter but do not fit naturally into the main storyline.
- Each observation must state why it matters and cite supplied evidence.
- An observation must add a supported fact that does not already appear in any stage or rich block. Do not use this section to restate, summarize, or reinforce the main flow.
- Omit incidental logging, naming, or implementation trivia unless it materially changes how the user understands or uses the requested behavior. An empty array is better than a weak observation.
- Keep `text` to the fact itself. Put its consequence only in `why_it_matters` so the rendered observation does not repeat its rationale.
- Do not infer a missing validation, security defect, unsupported guarantee, or repository-wide absence merely because it is not present in selected evidence.
- Put unresolved investigation steps in `next_checks`, not in additional observations.

Question and hint rules:

- Generate between one and three understanding checks. A successful explanation must always include at least one.
- Choose the smallest sufficient set. Start with one check for the most important evidence-supported reasoning transition in the explanation.
- Treat one reasoning transition as one relationship between a focused subject and another component, condition, action, or consequence. A check must test exactly one transition; if its expected answer crosses several component handoffs or independent concerns, split it into two or three checks.
- Add a second or third check when it tests another independently important transition whose omission would leave a major explicit branch of the user's request unassessed. Multi-part prompts will commonly need two or three checks, but do not allocate checks mechanically per intent or stage.
- For each check, set `reasoning_focus` to a concise description of the single relationship being tested and `selection_reason` to why that relationship is independently important to the requested explanation.
- Respect `question_field_limits`. If a field would be too long, write it more concisely; do not rely on downstream truncation.
- Independent checks must have different reasoning focuses and must add at least one new target stage or supporting evidence reference. They may share a broad intent stage when that stage contains separate evidence-backed transitions.
- Checks must not paraphrase one another or test the same expected reasoning with different wording. Reusing some evidence is allowed when it genuinely supports distinct transitions.
- Select a question contract belonging to one selected intent.
- Copy that contract's complete `prerequisite_stage_ids` exactly; `question_prerequisites_by_intent` repeats the authoritative lists explicitly to prevent target stages from being mistaken for prerequisites.
- Use only one of its `stem_families`; use that stem's `stem_descriptions` entry to choose the intended kind of reasoning, not merely a matching opening word. Target one or two supplied stage IDs, including at least one stage belonging to that intent.
- Expected answer points and all hints must follow the same cited stage evidence and respect the assistance boundary.
- Return exactly three progressively revealing hints for each question in this order: `direction` names the next reasoning operation without giving the answer; `focus` points to the relevant component, stage, or evidence relationship; `scaffold` reveals the beginning of the connection while leaving the learner to complete the conclusion.
- The `scaffold` hint may reveal one important handoff, but it must leave at least one expected answer point for the learner to supply.
- Keep every hint question-specific. Do not copy an expected answer point, reveal the full answer, or reuse generic hint prose across questions.
- Every check must cite evidence used by its target or prerequisite stages. If the first draft cannot do this, revise the checks rather than returning an empty array.

Additional structured fields:

- `concept_definitions` contains short contextual definitions for unfamiliar terms used in the explanation.
- `source_attributions` identifies important visible claims; `quote` must be copied exactly from a stage sentence, list item, table cell, example caption, or additional observation.
- `next_checks` contains diagnostic observations only when unresolved behavior genuinely needs them.
- Do not put questions, hints, source lists, definitions, or next checks into stage prose.

Return only JSON matching the supplied schema.
