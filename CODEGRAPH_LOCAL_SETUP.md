# Project-Local CodeGraph

This repository uses `@colbymchenry/codegraph` as its project-local structural index for native workspace retrieval and evidence-graph construction. It is installed by the normal `npm install` or `npm ci` workflow and does not require a global executable or user-level agent configuration.

## Commands

```powershell
npm run codegraph:init
npm run codegraph:status
npm run codegraph:sync
npm run codegraph:explore -- "next-check generation and rendering"
```

- `codegraph:init` creates the initial `.codegraph/` SQLite index.
- `codegraph:sync` incrementally applies changed source files.
- `codegraph:explore` returns the relevant symbols, structural relationships, and bounded source context for a focused flow.
- `codegraph:index` forces a complete rebuild when required.

The `.codegraph/` directory is generated locally and ignored by Git. CodeGraph telemetry is disabled by the npm commands.

Native retrieval uses the package API through a run-scoped Node bridge. During indexing it temporarily merges the configured workspace exclusions into `codegraph.json`, then restores the user's original file byte-for-byte or removes the temporary file when none existed. The bridge stays open for structural queries during that retrieval run and is closed deterministically afterward.

## Initial Measurement

The repository contains 453 tracked files. Of those, 141 use source formats supported by CodeGraph; three are generated CodeRepoQA fixture files excluded from the working graph. A clean full rebuild indexed all 138 intended source files into 3,407 nodes and 9,834 edges. CodeGraph reported 443 milliseconds for indexing; the complete npm command took 1.95 seconds. The resulting database is 12.64 MB. An unchanged incremental sync took 0.45 seconds.

## Next-Check Flow Result

For the existing Next-check evidence case, CodeGraph directly recovered useful local relationships:

- `_validate_response` calls `_repair_next_checks`;
- `render_response` calls `_render_explanation`;
- `GuidedResponsePanel` calls `getNextChecks`;
- `GuidedResponsePanel` renders `NextChecksBox` through a synthesized JSX edge.

It did not infer the serialization boundary between Python response metadata and the TypeScript `getNextChecks` consumer. Markdown prompt files are not indexed as first-class code nodes, although Python constants that reference their paths are indexed. The implemented post-retrieval evidence-graph stage therefore uses CodeGraph edges as its grounded structural backbone, resolves exact selected document references locally, and leaves unresolved cross-language or semantic boundaries for the bounded graph-enrichment model described in `LLM_EVIDENCE_GRAPH_TOKEN_PLAN.md`.

The graph stage runs after evidence selection and stores its result only in retrieval metadata for the graph UI. Graph metadata is not sent back into Codex retrieval or explanation generation. The previous design that asked Codex retrieval to generate the graph was removed completely; there is no compatibility or fallback branch beside the hybrid path.
