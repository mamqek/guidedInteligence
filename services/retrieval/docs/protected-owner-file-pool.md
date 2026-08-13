# Recurrence And Connected-File Promotion Pool (Superseded)

This experiment was removed and replaced by
`connected-evidence-explanations.md`. It remains here as the historical design
and measurement record; none of its 24-file allocation behavior remains active.

## Why the previous experiment was invalid

The first 24-file pool admitted only files classified as `implementation`. That
assumption was not supported by the complete TypeScript Oracle set:
`watchMode.ts` and `tscWatch/helpers.ts` are test-role Oracle files. Both were
present in the broader candidate universe, then excluded or not restored during
the implementation-only allocation. The implementation-role eligibility rule
has therefore been removed rather than retained as a fallback.

## Stage boundary

The replacement has two deterministic stages:

1. After the initial per-obligation hybrid searches, compute a file-level signal
   from independent-obligation recurrence, best rank, and an exceptional bonus
   for ranks one and two. This role-neutral set also allows low-overlap semantic
   results to survive exact range grounding.
2. After graph expansion, query the file-level neighborhoods of the four
   strongest semantic roots separately. Files can enter through their own
   semantic score or inherit promotion from productive `calls`, `references`,
   `imports`, dependency, inheritance, override, and instantiation edges to
   those roots. Direction is deliberately neutral. Multiple edges and multiple
   strong roots increase the inherited score.
3. Reserve the top two productive neighbors of each strong root, then fill the
   remaining positions by global direct-plus-inherited score. This prevents a
   single high-degree generic root from consuming the entire pool. Graph-only
   promoted files receive one grouped Qdrant localization and CodeGraph range
   grounding so they have an exact representative for final assessment.

The final pool remains capped at 24 files. Allocation still assigns one exact
candidate representative per promoted file before filling unused request slots
from connected-component shortlists. Promotion means only that a file reaches
the final LLM assessment; it does not accept the file as evidence.

## Expected quality impact

- Repeated independent retrieval should preserve files such as `watchMode.ts`,
  which appeared in 4/6 and 6/6 initial searches in the measured TypeScript
  runs.
- Exceptional obligation-specific results remain eligible even without broad
  recurrence.
- Graph-only files such as `tscWatch/helpers.ts` can inherit promotion from a
  strongly recurring connected file.
- Test, support, and implementation files compete under the same evidence
  signals rather than a role assumption.

## Expected token impact

No LLM calls are added. The policy adds four deterministic CodeGraph
file-neighbor calls and, when selected graph-only files lack candidates, one
grouped Qdrant localization plus one CodeGraph range-grounding call. The final
request still contains at most four candidates per repository obligation, so
the six-stage explain contract remains capped at 24 candidates.

## Known regression risks

- Generic files can recur across several broad obligations and receive a high
  direct score without being Oracle evidence.
- Highly connected utility files can inherit promotion from a strong root.
- A graph-only owner not connected to a recurrent or top-two semantic root can
  still depend on the component-fill portion of the allocator.
- Generated obligations remain variable, so recurrence strength can vary even
  though the number and purposes of obligation searches are stable.

## Comparison method and decision rule

Run the scoped TypeScript case twice. Record the final promoted paths, presence
of all four Oracle files in the 24-candidate LLM request, selected Oracle overlap,
coverage, sufficiency, retrieval token totals, and index reuse. Compare against
`run-20260811T173906Z` and `run-20260811T174132Z`.

Per explicit user direction, this replacement remains enabled even if those two
runs do not improve final evidence. Direction-neutral productive provenance also
remains enabled. Any failure is recorded for follow-up tuning rather than causing
automatic rollback.

## Final measured result

Two unchanged scoped TypeScript runs used `--exclude-path lib` and
`--exclude-path tests/cases`:

- `run-20260811T190625Z`: the 24-file pool and final LLM request contained
  `builderState.ts`, `watchMode.ts`, and graph-only `tscWatch/helpers.ts`.
  `helpers.ts` had zero direct semantic recurrence and survived through 40
  productive connections plus a reserved-neighbor slot. Final Oracle overlap
  was 1, coverage was `partial`, sufficiency was `false`, retrieval LLM usage
  was 18,080 tokens, and Qdrant reported `rebuilt=false`.
- `run-20260811T190912Z`: all four Oracle files entered both the pool and final
  LLM request. `helpers.ts` again had zero direct recurrence and survived through
  39 connections plus reservation. Final Oracle overlap was 2, coverage was
  `partial`, sufficiency was `false`, retrieval LLM usage was 17,541 tokens, and
  Qdrant reported `rebuilt=false`.

The shortlist-survival goal improved from 1/4 and 2/4 Oracle files in the prior
implementation-only pair to 3/4 and 4/4. Final selection remains imperfect: the
LLM did not accept every surviving Oracle, and the selected evidence remained
partial. The promotion policy remains enabled per the stated decision rule.
