Analyze this fresh repository-assistance request before retrieval.

Evaluate every task intent independently in the fixed `intent_decisions` object:

- `explore`: the requested outcome is locating what exists, ownership, boundaries, entry points, or major relationships.
- `explain`: the requested outcome is establishing how or why a behavior works through a supported mechanism.
- `use`: the requested outcome is learning how to invoke, configure, or integrate an existing interface.
- `debug`: the requested outcome is diagnosing abnormal behavior by connecting a symptom to a cause or discriminating check.
- `change`: the user requests adding, fixing, removing, or refactoring something.
- `plan`: the requested outcome is an ordered future approach.
- `review`: the requested outcome is a qualitative or comparative judgment.
- `verify`: the requested outcome is determining whether a concrete factual claim is supported.

Select an intent only when it is an independently requested answer outcome. Internal work does not add an intent: locating code while explaining behavior is still `explain`, and reading a reported issue does not by itself make the request `debug`.

Use the requested outcome to distinguish adjacent intents:

- "Explain how or why this code produces the behavior" selects `explain`.
- "Diagnose this failure and determine what is wrong" selects `debug`.
- Select both only when the user independently requests both a mechanism explanation and a diagnosis.
- A request to "explain the code context needed for this issue" selects `explain`; expected/actual issue details are context for that explanation, not a separate debugging request.

Question words are not intent labels by themselves. Keep conversation relation, solution pressure, specificity, and target state separate from task intents. An explicit target must be literally present in the current prompt.

Extract error text, literals, identifiers, and concise conceptual search terms. For code examples, preserve literal repository-facing type/API names and member names as separate identifiers (for example, `Series` and `add`), rather than replacing them only with local variables such as `s1` and `s2`. Do not invent names that are absent from the prompt. Paths and symbols will be normalized against the prompt after this call, so do not reinterpret paths or turn natural-language phrases into symbols.

Return only the JSON required by the supplied schema.
