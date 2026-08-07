Continue teaching from the accepted explanation and the learner's evaluated answers.

Use only the supplied answer flow, story flow, original checks, evaluations, answers, and teaching state. There are no role-based concepts or assumed consecutive dependencies.

- For `repair`, address the actual missing points and target stages. Do not repeat the full explanation.
- For `deepen`, extend one already-taught relationship without inventing repository facts.
- For `completion`, close briefly and do not manufacture another problem.
- A revised check is optional. When included, derive it from the same intent contract, taught stages, and evidence as the accepted explanation.
- Preserve generated semantic fields exactly. Respect `question_field_limits`; no downstream truncation or hardcoded hint will repair them.
- A revised check must include the same `direction`, `focus`, and `scaffold` hint ladder described by `hint_contract`.

Return only JSON matching the supplied schema.
