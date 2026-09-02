# Graphless and controller-free retrieval ablations

Status: graphless implementation complete and smoke-validated; controller-free ablation proposed, not implemented.

## Purpose

These are thesis comparison modes, not alternative production strategies.  Each mode must retain the same issue
prompt, Qdrant/BM25 index scope, initial owner-comparison prompt, qualification contract, final evidence selector,
and evaluation procedure.  The ablation removes one named capability without silently replacing it with another
learned or structural mechanism.

## A. Graphless retrieval

Boundary: all CodeGraph indexing, symbol/range-owner resolution, graph edge discovery, graph expansion, file-neighbor
queries, and structural call tracing.

Retained behavior:

- dense/sparse Qdrant retrieval, file grouping, and held alternatives;
- raw retrieved source ranges as range-level observations when no graph owner exists;
- initial owner comparison, disclosure, qualification, evidence islands, non-graph controller actions, and final
  evidence selection.

Removed behavior:

- CodeGraph process startup and index refresh;
- CodeGraph nodes, exact symbols, outlines, graph edges, and all candidates created from them;
- graph-dependent actions, which receive deterministic empty structural results and therefore are not enumerated as
  productive continuations.

Implementation contract: `structural_graph_enabled=false` selects deterministic empty structural tools.  They do not
invoke CodeGraph and are explicitly recorded as provider `disabled`; range-level Qdrant observations are retained,
so the run measures loss of structural grounding rather than loss of all initial retrieval.  No AST or name-matching
substitute is introduced.  The CodeRepoQA surface exposes `--no-structural-graph` and the web configuration accepts
`retrieval.structural_graph_enabled: false`.

Expected result: fewer owner-specific candidates, no verified cross-file/file-trace evidence, and fewer productive
controller expansions.  It may still return useful lexical/semantic ranges, which is the intended baseline.

Initial real-run result: TypeScript 35468 `run-20260901T064425Z` ran with `--no-structural-graph`, packet and
dormant-file-alternative defaults enabled, final evidence selection enabled, and response generation skipped.  The
trace has `initial_ranges_without_codegraph` with 374 submitted ranges and zero resolved owners, and no
`index_codegraph` stage.  The run completed `partial/false`, selected six
range-level evidence items from four files, and retained 1 implementation Oracle.  A preceding attempt failed during
initial owner comparison because the external LLM returned an invalid global selection; it is excluded and did not
exercise a graphless implementation failure.

Verification: first run a real TypeScript 35468 graphless acceptance run with response generation skipped and final
selection enabled.  Confirm the run metadata and retrieval summary name provider `disabled`, there is no
`index_codegraph` stage nor CodeGraph process request, raw Qdrant ranges reach owner comparison as range observations,
and graph actions add no endpoints.  Then compare two graphless and two normal runs on TypeScript 35468 plus one
each on pandas 10068 and Vue 242.  Do not reindex: graphlessness does not change BM25/Qdrant index scope.

## B. Controller-free retrieval (proposal)

Boundary: after round-zero owner comparison and qualification, bypass `run_retrieval_controller` and send the
qualified round-zero evidence directly through the unchanged final-pool representation and final evidence selector.

This is a valid and useful second ablation, but it should not be described as simply "no actions" unless the
round-zero qualification is retained.  Without that qualification there is no common semantic admission boundary and
the result would conflate controller removal with raw-noise admission.

The correct comparison is therefore:

`initial retrieval → CodeGraph owner resolution (when enabled) → owner comparison → round-zero qualification →
final-pool construction → final evidence selection`

versus normal retrieval, which inserts controller rounds between qualification and final-pool construction.

Expected result: lower token cost and fewer discovered file traces / cross-file handoffs / local completions, but
cleaner attribution of any quality drop to controller exploration.  It is compatible with graphless mode as a later
2×2 experiment, but the first measurement should vary one factor at a time.  Before implementation, define a small
result contract carrying round-zero qualified observations, deferred/dormant diagnostics, zero controller actions,
and `stop_reason=controller_bypassed_after_round_zero`; do not emulate later controller preservation or coverage
updates.
