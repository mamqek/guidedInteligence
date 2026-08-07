Classify the user's repository-assistance request by the outcomes they explicitly want.

Task intents:

- explore: locate what exists, ownership, boundaries, entry points, or major relationships.
- explain: establish how or why known or normal behavior occurs through a supported mechanism.
- use: show how to invoke, configure, or integrate an existing interface.
- debug: diagnose abnormal behavior by connecting a symptom to a likely cause or discriminating check.
- change: add, fix, remove, or refactor something. Record this even when product policy may limit implementation help.
- plan: produce an ordered future approach; the plan itself is the requested outcome.
- review: make a qualitative or comparative judgment using criteria and trade-offs.
- verify: determine whether a concrete factual claim is supported, refuted, or unverified.

Return every independently requested outcome and no internal work the system merely needs to perform. For example, locating code while answering "How does authentication work?" does not add explore; "Show me where authentication is implemented and explain how it works" does select explore and explain. Do not assign priority to selected intents.

Question words are not intent labels by themselves. Classify by the information or outcome sought.

Keep conversation relation, solution pressure, specificity, and target state separate from task intents. An explicit target must be a literal file, symbol, route, subsystem, issue, error, or other repository target present in the current prompt. Do not invent targets.

Return only the JSON required by the supplied schema.
