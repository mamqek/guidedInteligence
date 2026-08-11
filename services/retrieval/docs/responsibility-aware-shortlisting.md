# Responsibility-Aware Shortlisting

## Evidence from the repeated regression matrix

The comparison set is the eight valid 2026-08-11 workspace runs recorded in
`retrieval-changelog.md`: two runs each for `vuejs-vue-242`, `vuejs-vue-10803`,
`microsoft-TypeScript-35468`, and `pandas-dev-pandas-10068`.

The runs separate three sources of variation:

1. Request analysis retained the same intent and obligation topology, but the
   generated obligation propositions and semantic query wording still varied.
2. Qdrant was deterministic for identical exact-error queries (`vuejs-vue-242`)
   but different generated obligation queries produced different semantic seed
   rankings in the unstable Vue, TypeScript, and pandas pairs.
3. CodeGraph repeatedly found owner files that did not reach final selection.
   The loss occurred in `_connected_candidate_shortlists`, before the final LLM.

The Oracle implementation files share a useful observable signal in these
runs: they are independently corroborated. The same file is reached by a
semantic seed or exact prompt anchor and by a productive structural route such
as a call, reference, file dependency, qualified reference, or continuation.
Examples are `src/exp-parser.js`, server `dom-props.js`, `Series::_binop`, and
the TypeScript builder files. The rejected distractors are more often supported
by one broad semantic route, one speculative focused bridge, or high graph
connectivity without a prompt-grounded owner signal.

The previous shortlist did not preserve that distinction. It selected exactly
one connected component per obligation, ranked component obligation breadth
before owner evidence, promoted `focused_semantic_bridge` to the same tier as a
direct structural target, and allowed several snippets from the same speculative
file to consume the four-candidate budget. Graph neighborhood was therefore not
enough: neighboring paths and edges could exist in the trace while their owner
component still lost the winner-take-all comparison.

The first post-change TypeScript comparison exposed two additional pre-LLM
surrogates. Exact AST snippets were penalized by the byte size of their containing
file, and initial Qdrant results still needed at least two lexical terms from the
obligation even after the graph's percentage-overlap gate had been removed.
`builder.ts` was therefore present in final Qdrant results and range localization
but could still be omitted from the candidate ledger or pushed below every
shortlist slot. File bytes do not represent snippet cost or responsibility, and
Qdrant rank should remain a hypothesis even when code vocabulary differs from
issue prose.

## Experiment and decision

The tested boundary was completed candidate graph -> four-candidate deterministic
shortlist -> unchanged final evidence-selection LLM. The experiment tried, in
sequence, component diversification, semantic-plus-structural corroboration,
executable responsibility scoring, recovery from the individual dense/sparse
channels, and a distinction between executable sources of `references` edges
and passive referenced declarations. The final prompt budget remained four
candidates per obligation.

One probe, `run-20260811T142238Z`, selected both builder files, but its unchanged
repeat `run-20260811T142519Z` lost them. Later probes continued to alternate:

- `run-20260811T144216Z` exposed both builder files to final assessment and
  selected only `builderState.ts` (Oracle 1, `partial/false`, 16,007 tokens).
- `run-20260811T144544Z` exposed and selected only `builder.ts` (Oracle 1,
  `partial/false`, 12,220 tokens).
- `run-20260811T145056Z` and `run-20260811T145506Z` selected neither owner
  (Oracle 0, `partial/false`, 14,283 and 13,338 tokens).
- The audited `run-20260811T145757Z` shortlisted exact
  `builderState.ts:updateExportedModules`, but the final LLM rejected it
  (Oracle 0, `partial/false`, 11,109 tokens).

All of those runs reused the BM25 and Qdrant indexes and reported
`index_rebuilt=false`. The final two-run comparison therefore regressed against
the historical pair and did not stabilize sufficiency or owner selection. The
responsibility-ranking behavior was reverted in accordance with the retrieval
experiment policy. No Vue or pandas control was run after that failed gate.

The useful retained change is observability: the trace records the exact
per-obligation deterministic shortlist with path, range, symbol, score,
provenance, and relationship types. Future runs can now distinguish raw search
discovery, graph discovery, deterministic shortlist loss, and final-LLM
rejection directly.

The result also narrows the next design requirement. File-level corroboration is
real but insufficient: generic high-fanout paths can be corroborated too, and a
correct owner can still be rejected after reaching the final LLM. A replacement
must score a candidate's role in the concrete state transition (producer,
mutation owner, consumer) and evaluate the owner chain jointly, rather than
ranking isolated nodes with lexical overlap, component breadth, or edge direction
as surrogates. That is a new measured design, not a safe patch to leave enabled
from this experiment.

## Index lifecycle finding

Each CodeRepoQA snapshot already owns its BM25 files, Qdrant manifest, CodeGraph
database, and repository-scoped Qdrant collection. The warm runs in the matrix
did not rebuild Qdrant. The apparent restart had two separate causes:

- a newly changed exclusion scope legitimately forced the first TypeScript
  BM25/CodeGraph reconciliation; and
- `prepare_index` wrote BM25 data without the scope manifest consumed by the
  runtime, so a fresh prepared index could be rebuilt immediately by the real
  pipeline.

`prepare_index` now writes the same schema, workspace, exclusion, and chunking
scope manifest used by runtime reuse checks. CodeGraph still performs a cheap
synchronization check on every run; that check is not a rebuild when its result
reports zero added, modified, and removed files.
