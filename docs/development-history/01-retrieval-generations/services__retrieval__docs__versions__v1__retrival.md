# V1 Retrieval Outline

## Version Summary

This version captures the initial structured retrieval flow for the repository-level retrieval system.

Compared with later versions, it establishes the main stages of planning, narrowing, retrieval, enrichment, and refinement, but it does not yet express a strong owner-first retrieval rule or a decisive snippet-grounding requirement.

##

- `Policy / retrieval decision`
  - deterministic
  - no file/snippet yet

- `Step-2 issue decomposition and role planning`
  - LLM
  - no file/snippet yet

- `Initial CGC narrowing`
  - CGC tool + deterministic filtering
  - file-level

- `Per-role first-pass Qdrant retrieval`
  - Qdrant hybrid search
  - file/chunk-level

- `Per-query seeding and path dedup`
  - deterministic
  - file-level

- `Open-file enrichment`
  - local file open tool
  - snippet/context-level

- `Local in-file refinement`
  - deterministic scoring over local windows
  - snippet-level

- `Prepared role bucket assembly`
  - deterministic
  - file + chosen snippet

- `Responsibility profiling`
  - deterministic heuristics in `profile_candidate(...)`
  - mainly file-level, using current snippet text

- `Responsibility expansion`
  - deterministic orchestration over Qdrant + CGC + explicit references
  - file-level

- `Responsibility rerank`
  - deterministic scoring in `score_responsibility(...)` + role validation
  - file selection with current snippet attached

- `Anchor support / graph support`
  - CGC + deterministic matching
  - file-level structural support

- `Retarget / role rescue`
  - Qdrant + local file open + deterministic refinement/validation
  - file retrieval + snippet retargeting

- `Late LLM role assessment`
  - LLM
  - snippet/evidence-level judgment

- `Late downgrade / weak-role recovery`
  - deterministic orchestration, using late LLM output plus Qdrant/CGC
  - role status + more file/snippet retrieval

- `Final evidence selection`
  - deterministic
  - snippet-level

- `Response synthesis`
  - deterministic response builder
  - final explanation over selected snippets
