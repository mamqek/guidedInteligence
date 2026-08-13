# Candidate File Triage Experiment (Disabled)

This experiment was implemented, measured twice, and removed from runtime after
failing its token-reduction objective. This note preserves its boundary and the
reason it should not be reintroduced unchanged.

## Stage boundary

This experiment runs after deterministic mechanism-flow construction and before
the existing final evidence-selection LLM. It does not change Qdrant retrieval,
CodeGraph expansion, candidate localization, obligation provenance, or final
evidence-selection rules.

Candidates are grouped into relationship-centred file cards. Each card preserves
all candidate identities and ranges, semantic discoveries by obligation, and all
cross-file graph relationships involving the file. The triage LLM must classify
every file exactly once as `keep`, `inspect`, or `discard`:

- `keep`: the compact facts already establish likely issue relevance;
- `inspect`: relevance is uncertain and the existing selector needs full source;
- `discard`: the file is confidently irrelevant or redundant.

Both `keep` and `inspect` files proceed unchanged to the existing final selector.
Only `discard` files are removed. A graph-only leaf connected to a strong anchor
must therefore be inspected rather than discarded merely because it has no
semantic score.

The experimental response was strictly validated. Missing, duplicate, unknown,
or all-discard decisions failed the stage explicitly; there was no deterministic
fallback.

## Expected impact

Quality: exact evidence remains available whenever the compact card is relevant
or uncertain. The main regression risk is an unjustified confident discard of an
Oracle file, especially a disconnected semantic anchor or graph-only connector.

Tokens: the new compact triage call adds a modest request, while the much larger
full-source evidence-selection request should shrink when repetitive irrelevant
files are discarded. There is no fixed file or candidate cap.

## Comparison

TypeScript 35468 was run twice with response generation disabled but final
evidence selection enabled:

- `run-20260813T194329Z`: 226 candidates across 41 files became 209 candidates;
  triage cost 91,861 tokens and the remaining selector cost 144,010 tokens.
- `run-20260813T194645Z`: 213 candidates across 37 files became 176 candidates;
  triage cost 89,774 tokens and the remaining selector cost 128,649 tokens.

Both runs retained `builder.ts` and `builderState.ts` and finished
`partial/false`, but neither triage input contained Oracle `watchMode.ts` or
`helpers.ts`; those were lost earlier. The compact cards were themselves about
296k-310k serialized characters, and conservative `inspect` behavior retained
most candidates. The extra ~90k-token call therefore increased total cost while
providing only a 7.5%-17.4% candidate reduction. The runtime stage and prompt
were removed. A future attempt must compress deterministic repetition before an
LLM call, not ask another LLM to read nearly the same inventory.
