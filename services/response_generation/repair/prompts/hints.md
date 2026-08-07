Regenerate only the rejected hint ladders. Do not change any question, expected answer point, evidence reference, reasoning focus, or accepted sibling question.

For every rejected question, return three progressively revealing hints in this exact order:

1. `direction`: name the next reasoning operation without revealing the answer.
2. `focus`: point to the relevant component, stage, or evidence-backed relationship.
3. `scaffold`: reveal the beginning of the connection while leaving the learner to complete the conclusion. It may reveal one important handoff, but must leave at least one expected answer point unstated.

Every hint must be specific to its question and supported by the supplied explanation and evidence context. Do not copy an expected answer point or provide the full answer. Fix the stated problems and return the ladders in the same order as `rejected_hint_ladders`.

Return only JSON matching the supplied schema.
