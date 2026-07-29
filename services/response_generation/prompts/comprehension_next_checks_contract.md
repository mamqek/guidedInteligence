Next checks:

The backend has already decided that structured `next_checks` are required for this response. Return at least `next_check_requirement.min_checks` items in the `next_checks` JSON field and do not put next checks in the markdown body.

Use this object shape:

```json
{
  "scenario": "Short name of the distinct uncertainty being tested",
  "action": "A concrete action the user can run from their normal code editing or test environment.",
  "if_result": "The observable result to look for after running the action.",
  "then_interpretation": "What that result means for the diagnosis."
}
```

Field rules:

- Each check must test a different scenario, assumption, or concept behind the unresolved part of the explanation.
- If two candidate checks would lead to the same diagnostic conclusion, keep only the clearer one.
- Use `next_check_requirement.signals` and the generated markdown to target the missing evidence boundary.
- Keep checks feasible for the target user: they should be understandable and runnable from normal project commands, tests, examples, source edits, or dependency/version comparisons.
- Do not require specialized inspection tools, internal runtime object spelunking, binary/file-format investigation, debugger-only state, or ecosystem-specific internals that a normal codebase user would not know how to inspect.
- Hard NO: do not make a next check about inspecting metadata.
- If the only available check seems too low-level, replace it with a higher-level observable comparison that narrows the diagnosis.
