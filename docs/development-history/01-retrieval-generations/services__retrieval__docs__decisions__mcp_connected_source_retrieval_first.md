# MCP-First Connected Source Retrieval

## Purpose

This note records the intended direction for retrieving evidence from non-code connected sources such as Obsidian, GitHub, Notion, Jira, Shortcut, and similar project-management or knowledge tools.

The decision here is not to implement a new subsystem immediately. It defines the preferred shape so future connected-source work can stay incremental and avoid prematurely building a graph-memory platform.

## Decision

Use MCP as the first integration boundary for external text sources.

Do not start by integrating HippoRAG or another graph-memory engine into the live request path. Build the source-access layer first:

1. Call source-specific MCP tools with bounded live searches.
2. Normalize returned items into `ConnectedSourceDocument` records.
3. Feed the best connected documents into the existing retrieval planner and evidence flow.
4. Optionally cache normalized documents locally for future retrieval.
5. Evaluate whether a graph-memory layer is actually needed before adding HippoRAG.

## Why MCP First

MCP solves the immediate integration problem: controlled access to external tools.

The retrieval pipeline should not contain hand-written GitHub, Jira, Notion, or Shortcut client logic. Those provider APIs can live behind MCP servers. Retrieval only needs a common tool-facing contract:

- search a source with a query and limit,
- fetch detail for a selected result when needed,
- normalize the response into a common document shape,
- preserve source metadata and provenance.

This keeps provider-specific authentication, pagination, rate limits, and API quirks outside the core retrieval pipeline.

## Live Retrieval Shape

Live retrieval should be a small federated search pass, not a broad crawl.

For each request:

1. Extract search anchors from the user prompt and current context:
   - issue keys,
   - PR numbers,
   - URLs,
   - quoted phrases,
   - file paths,
   - symbols,
   - feature names,
   - error strings.
2. Search already local sources first, especially Obsidian and any cached connected documents.
3. If local evidence is weak or the prompt contains exact external IDs, call enabled MCP tools.
4. Limit live calls aggressively:
   - small number of sources,
   - small number of queries per source,
   - small number of hits per query,
   - detail fetches only for top hits,
   - short per-tool timeouts.
5. Normalize and rank the returned documents.
6. Pass only the best connected-source documents into Step 2 planning and final evidence selection.

Live retrieval is for discovery and freshness. It should not try to build complete source indexes during the user request.

## Normalized Document Contract

Every connected source should become a normalized document before entering the retrieval planner.

The common shape should include:

- source category,
- stable source ID,
- title,
- content,
- source URL when available,
- updated timestamp when available,
- authority/freshness metadata,
- connector/tool metadata,
- linked files, issue keys, PR numbers, or page IDs when available.

Examples:

- GitHub issue or PR:
  - title,
  - body,
  - selected comments,
  - labels,
  - repository,
  - state,
  - changed files for PRs.
- Jira ticket:
  - key,
  - summary,
  - description,
  - selected comments,
  - status,
  - project,
  - issue type.
- Notion page:
  - page title,
  - flattened page blocks,
  - parent database/page,
  - last edited time.
- Shortcut story/document:
  - story/document title,
  - description/body,
  - comments when available,
  - workflow state,
  - epic/project metadata.
- Obsidian note:
  - path,
  - title,
  - body,
  - explicit file hints,
  - backlinks or tags when available.

## Evidence Boundary

Connected-source evidence can guide and enrich retrieval, but it must not replace code evidence when code evidence is required.

For example:

- an Obsidian note can point retrieval toward `services/retrieval/workspace.py`,
- a GitHub PR can explain why behavior was introduced,
- a Jira ticket can describe product intent,
- a Notion page can record an architectural decision.

But if the answer requires code grounding, final sufficiency still depends on source-code evidence from the code retrieval path.

## Cache Before Graph

The first durable extension after MCP live retrieval should be a simple normalized document cache.

The cache should store documents returned by live MCP calls so future requests can search them locally before calling external tools again.

This gives most of the practical benefit:

- fewer live tool calls,
- better repeatability,
- faster retrieval for recently seen project context,
- a clean corpus for later graph experiments.

The cache does not need to be HippoRAG-aware at first. It only needs stable normalized documents and metadata.

## HippoRAG Position

HippoRAG or a similar graph-memory retriever may be useful later, but it should not be the first connected-source step.

HippoRAG solves a different problem:

- associating related text across sources,
- connecting fragmented project memory,
- supporting multi-hop retrieval such as ticket -> PR -> decision note -> file hint.

That becomes valuable if plain MCP search plus a local document cache repeatedly misses cross-source context.

It is likely overengineering before we have:

- enough normalized connected-source documents,
- observed failures from simple search/cache retrieval,
- benchmark questions for connected-source context,
- a clear measurement plan for quality and token/runtime cost.

## When To Revisit HippoRAG

Revisit graph-memory retrieval when real usage shows failures like:

- GitHub, Jira, and Obsidian each contain part of the answer, but no single source uses the same wording as the user query.
- Keyword or hybrid search returns relevant individual documents but misses the document chain.
- Users ask design-history questions that require connecting requirements, implementation PRs, and decision notes.
- Existing local notes and live MCP results are too fragmented to rank reliably.

At that point, HippoRAG should consume the existing normalized document cache rather than call external tools itself.

Preferred future shape:

```text
MCP tools
  -> normalized connected documents
  -> local document cache
  -> optional HippoRAG connected-source graph
  -> connected-source evidence candidates
  -> existing retrieval planner
```

## Non-Goals For The First Version

- Do not crawl all GitHub/Jira/Notion/Shortcut content during a user request.
- Do not make HippoRAG mandatory for connected-source retrieval.
- Do not let external text evidence satisfy code-role coverage gates.
- Do not add provider-specific API clients directly to the retrieval planner when MCP can provide the integration boundary.
- Do not silently fall back if an MCP-backed source is configured as required and fails.

## Initial Implementation Expectation

The first implementation should be intentionally small:

1. Configure one MCP source.
2. Run bounded query-time search.
3. Normalize returned results into `ConnectedSourceDocument`.
4. Include selected documents in the existing retrieval planner.
5. Log source IDs, tool calls, result counts, and selected evidence refs.
6. Add tests with fake MCP responses.

Only after this path is useful and stable should local caching or graph-memory indexing be added.

## Summary

Use MCP now because it solves source access with the least architectural commitment.

Use normalized connected documents as the stable contract.

Add caching next if repeated live lookups are wasteful.

Consider HippoRAG later only if measured retrieval failures show that simple connected-source search and caching cannot connect fragmented project context well enough.
