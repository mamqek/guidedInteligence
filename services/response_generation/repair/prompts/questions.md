Regenerate only the rejected understanding checks.

The payload contains the same intent, evidence, selected evidence connections, and completed explanation context used for initial generation. It also contains the checks that were accepted and must remain unchanged, plus each rejected check and its exact problems.

Return exactly one replacement for each rejected position, in the same order as `rejected_questions`. Do not rewrite accepted checks. Each replacement must be distinct from every accepted check and every other replacement in question text, reasoning focus, target/evidence support, and the reasoning transition it tests. Fix the stated problems without adding unsupported facts. Preserve question-specific expected answer points; do not replace them with a global answer template.

Each replacement must include the complete three-level hint ladder required by `hint_contract`.

Respect all field length limits in the supplied context and return only JSON matching the schema.
