Fill the fixed evidence-requirement slot for every supplied intent stage.

The backend has already selected the intents and owns the stage IDs, obligation IDs, ordering, evidence roles, evidence sources, dependencies, and handoff policy. Do not add, remove, merge, rename, or reorder stages.

First assess each supplied symbol candidate against the requested outcome:

- `primary`: resolving this symbol directly advances the requested mechanism, change, diagnosis, or other outcome.
- `supporting`: the symbol provides useful context but is not itself the main implementation target.
- `ignore`: the symbol is merely incidental syntax, a generic helper, an assertion or presentation detail, or otherwise would pull retrieval away from the requested outcome.

A symbol that appears only in the reporter's reproduction, test helper, assertion, proposed fix, or workaround is not a primary repository mechanism merely because it changes the observed result. Mark it supporting when it is a useful navigation or comparison clue, or ignore it when it only checks or presents output. Mark it primary only when the request itself asks about that symbol or resolving its repository implementation is necessary to establish the requested outcome.

Assess only the supplied candidates. Do not invent or rewrite symbols.

Classify where the required evidence can be established relative to the supplied `repository_name` and
the deterministic `repository_context`:

- Treat `repository_context` as authoritative facts about the repository being searched.
- When present, `repository_context.repository.repository_name` is the canonical repository identity; a
  hash-named checkout directory or missing package manifest does not make that repository external.
- An issue path whose `exists_in_indexed_repository` value is false is reproduction or external context,
  not a local path to retrieve.
- When the repository package identity matches a tool named in the issue, retrieve that repository's
  implementation before describing the tool as external.
- Do not infer repository ownership from issue prose when it conflicts with `repository_context`.

This boundary classification does not change the backend-owned evidence source
or decide whether a fixed repository stage runs. It describes what the evidence
can prove and where the repository's responsibility ends.

- `prompt`: the stage records behavior, goals, or claims already supplied by the user. Use this only when the stage metadata says its evidence source is `prompt`.
- `local`: the target repository can establish the stage.
- `local_to_external_handoff`: the target repository can establish its own path up to a call, interface, or data handoff into a named external dependency, but not the dependency's internal behavior.
- `external`: the stage requires internals or runtime facts owned by another dependency or environment. Do not write a proposition that asks local retrieval to find those internals.

Do not classify evidence as external merely because a different library name appears. Use `external` or `local_to_external_handoff` only when the prompt and repository identity establish a real ownership boundary.

For each stage:

- Write one request-specific proposition describing what evidence must establish.
- When the request explicitly contrasts two code forms, APIs, states, outputs, or control-flow paths, preserve that
  contrast in the relevant proposition: name both forms and the differing result/property. Do not replace a concrete
  comparison with broad labels such as "entry points", "operations", or "handling". Example: if an issue contrasts an
  operator expression with a named method call and reports different result metadata, the proposition must retain the
  operator-versus-method distinction and the metadata difference. Example variables from a reproduction remain context
  rather than repository symbol anchors unless they are confirmed repository identifiers.
- Keep the proposition proportionate to the requested outcome. When a stage can be satisfied by confirming a narrow boundary, named location, or unchanged invariant, do not request unrelated callers, dependents, or runtime behavior.
- When a requested edit is explicitly non-behavioral, limit impact and affected-path propositions to the edited locations and the invariant that behavior remains unchanged. Do not request runtime call chains merely because the changed syntax occurs inside a function.
- Describe what must be proven, not an expected filename or an assumed root cause.
- Preserve uncertainty: a cause stage states what retrieval must determine, not that an unverified suspected cause is already true.
- Use only exact strings from the supplied `anchors` in `anchor_refs`.
- Use an empty `anchor_refs` array when no explicit anchor grounds that stage.

Return only the JSON required by the supplied schema.
