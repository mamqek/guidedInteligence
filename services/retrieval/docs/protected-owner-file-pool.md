# Protected Owner File Pool Experiment

## Stage boundary

After all initial obligation Qdrant searches, build one request-level pool from
implementation files occurring in the top 12 hybrid results of any repository
obligation. Deduplicate across obligations, order by best rank and recurrence,
and cap the pool at 24 files.

During semantic grounding, protected files may retain a low-score exact range
even when generated obligation wording has no lexical overlap. Before final LLM
selection, allocate one exact candidate representative per protected file, then
fill remaining positions from the existing connected-component shortlist. The
total request-level candidate budget remains four times the repository
obligation count; for the six-stage explain cases this is 24.

Protection means only that a candidate reaches final assessment. It does not
mark the candidate as evidence or bypass the two-evidence-per-obligation output
limit.

## Expected quality impact

The eight-run offline audit retained every causal source-owner Oracle file in a
12-22-file pool, including both TypeScript builder files in both original runs.
This experiment should prevent one winning graph component from consuming all
four positions for an obligation while a directly retrieved owner disappears.

## Expected token impact

No additional Qdrant or LLM calls. Total final-assessment candidate count stays
within the existing request-level budget, but representation shifts from up to
four candidates per obligation to one representative per protected file plus
remaining connected candidates. Exact ranges should keep prompt size close to
the current budget; actual retrieval tokens will be measured.

## Regression risks

- A top-12 implementation distractor receives survival protection alongside the
  owner and may displace a better second node from the same file or obligation.
- An obligation can receive more than four input candidates while another gets
  fewer, although final accepted evidence remains bounded per obligation.
- Generated propositions can change the protected pool because this experiment
  protects candidates, not query text.
- The eight-run rule is an empirical survival result, not proof that every
  future owner is top-12 hybrid.

## Comparison and rollback

Run the scoped TypeScript case twice and record protected paths, builder-file
presence in the final LLM request, Oracle overlap, coverage, sufficiency,
retrieval tokens, and index reuse. If the two-run comparison does not improve
owner survival or causes quality instability, remove only the protected-pool
construction and allocation. Keep direction-neutral productive provenance.

## Result and decision

The two scoped TypeScript comparisons passed the owner-survival quality gate:

- `run-20260811T173906Z` created a 19-file protected pool containing
  `src/compiler/builder.ts`. Its exact `isChangedSignagure` candidate reached the
  24-candidate final request and the LLM selected `builder.ts`. The run had one
  implementation Oracle overlap, remained `partial/false`, used 15,257
  retrieval LLM tokens, and reused the index with `rebuilt=false`.
- `run-20260811T174132Z` filled the 24-file protected pool and contained both
  builder files. Both reached the 24-candidate final request; the LLM selected
  `builderState.ts:updateExportedModules`. The run had one implementation Oracle
  overlap, remained `partial/false`, used 19,037 retrieval LLM tokens, and reused
  the index with `rebuilt=false`.

The immediately preceding backend-scope-only pair had zero/zero Oracle overlap;
this pair had one/one. The pool therefore remains enabled. It did not stabilize
which builder owner was found, and retrieval cost increased by 4,799/7,420
tokens relative to that pair. Those limitations remain explicit rather than
being hidden by a sufficiency claim.
