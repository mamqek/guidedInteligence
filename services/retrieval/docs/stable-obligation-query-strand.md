# Stable Obligation Query Strand

## Stage boundary

Initial semantic discovery runs two independent Qdrant searches for every
backend-owned repository obligation:

1. a deterministic base query built from fixed intent-stage purposes, a
   deterministic request subject, and explicit prompt paths/symbols; and
2. the request-analysis LLM's generated proposition, enriched by its related
   anchors and search terms.

The two ranked result lists are deduplicated and interleaved into the existing
bounded initial-candidate budget. CodeGraph localization, graph expansion,
connected shortlisting, final LLM selection, and sufficiency validation remain
unchanged.

Backend stage policy, rather than the generated evidence boundary, owns whether
a fixed repository stage enters retrieval. The boundary remains available to
describe whether evidence is local, a local-to-external handoff, or external.
Prompt-owned stages remain prompt-only.

## Expected quality impact

- Repeated requests retain the same repository-obligation count.
- Every retained obligation has one byte-stable semantic search even when the
  generated proposition changes.
- Generated propositions remain useful as an additive refinement and cannot
  replace the stable strand before candidate pooling.
- Interleaving preserves representatives from both strands instead of allowing
  one result list to consume the entire initial candidate budget.

## Expected token and runtime impact

This adds one embedding/Qdrant search per repository obligation but no LLM call.
The merged semantic candidate cap remains unchanged, limiting downstream graph
and final-selection growth. Retrieval tool-call counts will rise predictably by
the number of repository obligations.

## Regression risks

- Fixed stage purposes can be broad, so stable results may be generic despite
  the deterministic request subject and anchors.
- Giving both strands representation can displace a useful lower-ranked result
  from the generated-only list.
- More Qdrant calls increase runtime even though downstream candidate and LLM
  budgets remain bounded.
- Stable queries do not make embedding service rankings deterministic and do not
  by themselves solve connected-shortlist owner selection.

## Comparison

First verify locally that external boundaries do not remove repository-policy
stages, each repository obligation emits exactly two distinguishable searches,
stable query text is unchanged across differing generated propositions, and the
merged candidate list remains bounded and strand-balanced. Then run the scoped
TypeScript case twice with `lib` and `tests/cases` excluded. Record emitted query
texts, builder-file shortlist presence, Oracle overlap, `coverage_status`,
`sufficient`, retrieval tokens, runtime, and index reuse. Retain the combined
behavior only if it avoids a repeated quality regression.

## Result and decision

The mechanism was deterministic but did not improve retrieval:

- `run-20260811T165608Z` emitted six stable and six generated initial
  searches, reused the index with `rebuilt=false`, and finished
  `partial/false` with zero Oracle overlap. `builderState.ts` appeared in one
  generated result list, but neither builder file reached the connected
  shortlist. Retrieval used 18,236 LLM tokens.
- `run-20260811T165945Z` again emitted six stable and six generated searches,
  reused the index with `rebuilt=false`, and finished `partial/false` with zero
  Oracle overlap. Neither builder file appeared in an initial result list or
  the shortlist. Retrieval used 16,735 LLM tokens.
- All six stable queries were byte-identical across the pair; none of the six
  generated queries were identical. Thus the implementation achieved query
  stability but the stable stage-purpose/title searches favored broad
  `tsbuildPublic.ts`, server, and test neighborhoods instead of the decisive
  builder state owners.

The extra query strand was removed after the two-run comparison. It added six
Qdrant calls and increased retrieval cost without recovering an owner. The
backend-owned repository-scope rule remains enabled as a separate generic
stability improvement requested by the user.
