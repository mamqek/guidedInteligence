# Project-Local CodeGraph

This repository uses `@colbymchenry/codegraph` as a project-local development tool. It is installed by the normal `npm install` or `npm ci` workflow and does not require a global executable or user-level agent configuration.

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

## Initial Measurement

The first run indexed 140 source files into 3,412 nodes and 9,837 edges. After generated CodeRepoQA workspaces were excluded, the focused index contains 138 source files, 3,407 nodes, and 9,834 edges. CodeGraph reported 488 milliseconds for the focused rebuild; the complete npm command took 2.02 seconds. The resulting database is 12.64 MB. An unchanged incremental sync took 0.45 seconds.

## Next-Check Flow Result

For the existing Next-check evidence case, CodeGraph directly recovered useful local relationships:

- `_validate_response` calls `_repair_next_checks`;
- `render_response` calls `_render_explanation`;
- `GuidedResponsePanel` calls `getNextChecks`;
- `GuidedResponsePanel` renders `NextChecksBox` through a synthesized JSX edge.

It did not infer the serialization boundary between Python response metadata and the TypeScript `getNextChecks` consumer. Markdown prompt files are not indexed as first-class code nodes, although Python constants that reference their paths are indexed. A future evidence-graph adapter should therefore use CodeGraph edges as grounded structural input and leave unresolved cross-language or document boundaries for the bounded graph-enrichment model described in `LLM_EVIDENCE_GRAPH_TOKEN_PLAN.md`.

CodeGraph is not connected to retrieval or explanation generation yet. This setup is an isolated, measurable prerequisite rather than a hidden replacement path.
