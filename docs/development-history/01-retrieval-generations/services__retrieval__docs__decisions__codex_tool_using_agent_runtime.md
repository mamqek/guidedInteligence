# Codex Tool-Using Agent Runtime

## Status

- State: exploratory design
- Owner: ongoing retrieval architecture discussion
- Scope: possible future `codex_agent` retrieval mode
- Last updated: 2026-06-23

## Problem

Current Codex retrieval is a one-shot delegate:

1. Build one prompt from the visible issue packet.
2. Call Codex CLI once.
3. Parse one structured evidence payload.

That path is simple, but it has two limitations:

- our runtime does not control intermediate search steps,
- Codex may spend many tokens on its own codebase search process.

The idea in this note is a different runtime: Codex acts as an agent that can request local retrieval tools step by step, while our system executes those tools and feeds results back into the loop.

## Goal

Add a separate Codex retrieval mode that can use shared local tools such as BM25, file-open, repo sketch, and possibly connected-source adapters, without merging Codex mode into the existing workspace retrieval pipeline.

The intended outcome is:

- lower or more controlled Codex token spend,
- better observability into what search steps occurred,
- reuse of local retrieval primitives across workspace and Codex modes,
- preservation of a comparable final evidence schema for benchmarking.

## Non-goal

This idea is not meant to replace the existing workspace retrieval pipeline.

It is also not meant to collapse `codex` and `workspace` into one mode. The cleaner target is separate modes with some shared infrastructure.

## Current Baseline

Current `codex` mode:

- implemented as one Codex CLI call from `services/retrieval/codex/provider.py`,
- no local iterative tool loop,
- no local BM25 or MCP step in the Codex path,
- final output is parsed from one structured response.

Current `workspace` mode:

- our runtime owns retrieval planning, search, refinement, validation, and coverage gating,
- uses local indexing and retrieval infrastructure,
- already has richer observability and stronger control.

## Proposed New Mode

Introduce a new mode conceptually named `codex_agent`.

High-level loop:

1. Provide Codex with:
   - issue packet,
   - repo context summary,
   - tool catalog,
   - final output contract.
2. Codex requests a tool call.
3. Our runtime executes the tool locally.
4. Tool result is returned to Codex.
5. Repeat until Codex signals it has enough evidence.
6. Codex emits final structured retrieval output.

This is not a prompt-only change. It requires an agent runtime in our code.

## Minimum Shared Tool Set

First candidate tool set:

- `bm25_search(query, path_filters?, top_k)`
- `open_file(path, line_start, line_end)`
- `repo_sketch(paths?)`

Second-wave candidate tools:

- connected-source / MCP query tools
- connected-source / MCP open tools

Deferred for later:

- CGC-based tools

Reason:

- BM25 and file-open are generic, cheap, and stable enough to test the architecture.
- MCP can be useful, but it adds more transport and auth surface.
- CGC currently carries operational and caching instability, so it should not be part of the first agent version.

## Framework Required

This design needs a small internal framework. At minimum:

- tool registry
- tool input/output contracts
- agent loop controller
- loop stop conditions
- dedupe / state tracking
- token and time budgeting
- per-step observability
- final output validation

This framework should stay outside the workspace-specific retrieval pipeline logic.

## Recommended Boundary

Shared infrastructure:

- BM25
- file-open
- repo sketch
- connected-source adapters
- generic tool contracts
- generic agent runtime utilities

Workspace-only:

- role bucket logic
- role refinement and recovery loops
- responsibility scoring
- role validation
- deterministic coverage gating

Codex-agent-only:

- tool-using Codex loop
- Codex agent system prompt
- stop policy
- final Codex evidence shaping

## Cost Hypothesis

The main cost question is whether local tools actually reduce Codex cost.

Current view:

- `open_file` can reduce cost if it prevents Codex from repeatedly expanding large files on its own.
- BM25 can reduce cost if it narrows the candidate set well enough that Codex avoids broad exploration.
- neither tool guarantees lower cost by default.

They help only if:

- tool outputs are compact,
- Codex receives only the useful slices,
- the loop has strict limits,
- BM25 recall is good enough not to trap Codex in the wrong area.

They can increase cost if:

- BM25 results are noisy,
- file-open outputs are too large,
- Codex repeats similar searches,
- the runtime keeps replaying too much prior context every turn.

## Practical Recommendation

If this is implemented, start with:

- one separate `codex_agent` mode,
- only `bm25_search`, `open_file`, and `repo_sketch`,
- hard limits on turns, tool calls, and result sizes,
- the same final evidence schema used by current Codex benchmarking where possible.

Do not start with:

- CGC,
- workspace role-validation logic inside the Codex loop,
- a large general-purpose agent framework.

## Open Questions

1. Should `tools/` and `mcp/` become fully shared infrastructure rather than workspace-owned?
2. Should `codex_agent` reuse the current Codex output profiles, or have its own stricter output contract?
3. How much of prior tool history should be replayed back to Codex each turn?
4. Should BM25 be used as an always-available tool, or as a mandatory first step before Codex can open files?
5. Do we want to compare `codex_delegate` vs `codex_agent` on the same retrieval-grounded benchmark set from day one?

## Current Working Position

- A tool-using Codex runtime is feasible.
- It is not a small tweak to the current one-shot provider.
- BM25 is the best first shared retrieval primitive.
- CGC should stay out of the first implementation.
- A small internal runtime framework is justified if we pursue this path.
