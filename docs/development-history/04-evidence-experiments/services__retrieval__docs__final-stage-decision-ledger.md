# Final-stage decision ledger

## Boundary

This is observability for the connected-explanation retrieval path. It does not
change Qdrant queries, CodeGraph traversal, candidate scores, explanation
ranking, or final LLM instructions.

## Ledger events

- `initial_semantic_candidates_grounded`: raw Qdrant ranks alongside the exact
  candidates they produced.
- `semantic_explanation_root_decisions`: every semantic file signal and whether
  it was selected as a graph-expansion root, lost to the root cap, or lacked the
  recurrence/rank threshold.
- `semantic_root_neighbor_decisions` and `semantic_root_neighbors_localized`:
  each graph neighbor's localize/not-localize decision and whether localization
  produced an exact candidate for each originating obligation.
- `mechanism_flow_decision_ledger`: every grounded candidate, direct and
  inherited discovery provenance, causal roles, fair per-seed flow hypotheses,
  exact-endpoint connection competitions, root/file connectivity, serialized
  marginal cost, and the exact reason every flow was selected or rejected.
- `mechanism_flow_request_budget`: the final serialized size split across
  candidate, flow, and connection records, plus the exact candidate paths sent
  to final assessment.
- `evidence_consolidation_decision_ledger`: the globally selected mechanisms,
  globally accepted/rejected candidates, many-to-many obligation mappings, and
  the LLM's support or missing-handoff assessment for every obligation.

Raw tool calls remain in `retrieval-trace.jsonl`; the ledger links their raw
results to every later decision without writing duplicate source snippets.

## Expected impact and comparison

The ledger itself has no quality or token impact; events are local JSONL trace
writes only. The mechanism experiment currently has no aggregate serialized
character ceiling because the prior limits excluded viable builder explanations
solely because earlier generic bundles consumed capacity. The trace still records
the exact serialized size so a later boundary can be based on measurements.

`--skip-response-generation` test mode still executes final evidence
consolidation and therefore reports the snippets accepted by that LLM. It skips
only the later prose explanation call. This keeps upstream absence, connection
replacement, flow rejection, and final evidence-LLM rejection separately
observable while avoiding explanation-generation tokens. The regression risk is
an unbounded consolidation request that is too large or noisy. Compare warm
TypeScript 35468 and Vue 10803 runs by retained Oracle nodes, exact causal
transitions, final accepted evidence, serialized size, and retrieval LLM usage.
