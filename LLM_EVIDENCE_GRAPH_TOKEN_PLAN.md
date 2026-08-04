# Compact LLM Evidence Graph Plan

## Goal

Keep evidence-connection graphs LLM-generated while avoiding the retrieval-token increase caused by asking the Codex retrieval agent to discover evidence and prove a complete graph in the same run.

## Stage Boundary

Run graph enrichment after normal retrieval has selected evidence. The graph stage receives only the selected evidence and must not have repository tools or feed its output into explanation generation.

```text
Codex retrieval -> selected evidence -> graph enrichment -> evidence graph metadata
                                      \-> explanation generation (without graph metadata)
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

The model returns edges only:

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

Code constructs nodes from existing evidence and validates only structural constraints:

- source and target IDs exist;
- no self-links;
- no duplicate edges;
- relationship kinds are from the schema;
- descriptions stay within the configured length;
- edge and token limits are respected.

Do not add phrase-based semantic validation or a deterministic substitute for failed LLM output. A graph failure should be surfaced as an explicit graph-generation error while leaving the independently completed retrieval result available.

## Caching

Cache graph output by a stable hash of evidence IDs, source ranges, and excerpt contents. Identical evidence selections should not incur another graph-model call.

## Optional Structural Assistance

Tree-sitter, Graphify, or CodeGraph may propose direct structural relationships from selected evidence. These relationships can reduce what the graph model must infer, but they must not force repository-wide indexing or become a silent fallback. Cross-language boundaries may still require the bounded LLM pass.

## Measurement

Compare against the pre-graph retrieval baseline and record:

- graph-stage input and output tokens separately;
- total retrieval tokens;
- connected and disconnected evidence counts;
- missing, incorrect, or unnecessary edges;
- cache hit rate;
- graph-generation latency.

The working target is approximately 8,000-25,000 graph input tokens and 1,000-3,000 output tokens, but this remains an estimate until measured on real runs.
