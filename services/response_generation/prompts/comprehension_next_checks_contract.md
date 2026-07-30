Next checks:

The backend has already decided that structured `next_checks` are required for this response. Return at least `next_check_requirement.min_checks` items in the `next_checks` JSON field and do not put next checks in the markdown body. Aim for `next_check_requirement.target_checks` when there are that many genuinely different feasible scenarios; return fewer rather than adding a low-level or repetitive check.

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
- Prefer observable comparisons: reproduce the reported case, add or adjust a focused test, compare a public option/version/path, or inspect ordinary source/config files.
- When the unresolved question is about counts, ordering, or performance observations, use existing public diagnostics, tracing output, test output, source/config comparison, or environment comparison. Do not modify implementation code just to observe internal calls.
- Do not ask the user to instrument internals, add temporary diagnostic logging, set breakpoints, inspect runtime object state, or step through private implementation paths. If a check needs that kind of internal probing, replace it with a higher-level test or source/config comparison whose result would narrow the same diagnosis.
- Do not require specialized inspection tools, internal runtime object spelunking, binary/file-format investigation, debugger-only state, or ecosystem-specific internals that a normal codebase user would not know how to inspect.
- Hard NO: do not make a next check about inspecting metadata.
- If the only available check seems too low-level, replace it with a higher-level observable comparison that narrows the diagnosis.
