# Hybrid Evidence Graph Architecture

## Goal

Keep evidence-connection graphs semantically useful while avoiding the retrieval-token increase caused by asking the Codex retrieval agent to discover evidence and prove a complete graph in the same run.

## Stage Boundary

Run graph enrichment after normal retrieval has selected evidence. CodeGraph receives the workspace and selected source ranges. The bounded graph model receives only selected evidence plus direct structural candidates and must not have repository tools or feed its output into explanation generation.

```text
Codex retrieval -> selected evidence -> CodeGraph/direct document edges -> bounded semantic graph -> evidence graph metadata
                                      \-----------------------------------------------> explanation generation (without graph metadata)
```

## Bounded Input

For each selected evidence item, provide only:

- its existing evidence ID;
- its existing title or claim;
- source path and line range;
- a bounded source excerpt, initially capped at 60 lines.

Reuse evidence titles as graph node labels. Do not ask the graph model to summarize nodes again.

Initial limits to measure rather than assume:

- at most 12 evidence nodes;
- at most 20 graph edges;
- at most 20,000 input tokens;
- at most 2,000 output tokens.

## Output

The model returns the root, the minimal edge set, and any honestly disconnected evidence. Existing evidence titles remain the node labels.

```json
{
  "source": "ev2",
  "target": "ev4",
  "kind": "validation",
  "description": "The generated response is passed into validation."
}
```

The graph should contain the smallest set of relationships needed to communicate the main behavior. Disconnected evidence is allowed. The model must not retrieve more files merely to connect every node.

## Deterministic Handling

Code constructs nodes from existing evidence, extracts exact CodeGraph and source-to-document candidates, and validates structural constraints:

- source and target IDs exist;
- no self-links;
- no duplicate edges;
- relationship kinds are from the schema;
- descriptions stay within the configured length;
- edge and token limits are respected;
- direct source-to-document edges match an exact locally discovered reference;
- all selected nodes are reachable from the declared root or explicitly disconnected;
- cycles and redundant shortcuts are removed from the displayed flow.

Do not add phrase-based semantic validation or a deterministic substitute for failed LLM output. A graph failure should be surfaced as an explicit graph-generation error while leaving the independently completed retrieval result available.

## Caching

Cache graph output by a stable hash of evidence IDs, source ranges, and excerpt contents. Identical evidence selections should not incur another graph-model call.

## Structural Assistance

CodeGraph supplies direct structural relationships from selected evidence. Exact source constants that name selected Markdown/config files supply document-reference relationships. These direct relationships form the factual graph backbone after a successful semantic-model call; the model cannot silently omit them. Cross-language, transport, and conceptual boundaries remain the bounded LLM pass's responsibility and are labeled inferred. If the model call fails, graph generation still fails explicitly instead of returning only the structural subset.

## Measurement

Compare against the pre-graph retrieval baseline and record:

- graph-stage input and output tokens separately;
- total retrieval tokens;
- connected and disconnected evidence counts;
- missing, incorrect, or unnecessary edges;
- cache hit rate;
- graph-generation latency.

The isolated 10-item Next-check comparison measured 6,735 input tokens and 943 output tokens. A subsequent live retrieval selected 9 items; replaying the graph stage over those exact items measured 5,432 input and 819 output tokens and produced a minimal 8-edge graph connecting all 9 nodes. Both match the useful shape of the earlier expensive graph without embedding graph discovery in Codex retrieval.
