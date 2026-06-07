---
title: Project retrieval source of truth
tags:
  - guided-inteligence
  - retrieval
  - source-of-truth
aliases:
  - retrieval source of truth
  - trusted local notes
---

# Project retrieval source of truth

Trusted project notes are allowed to steer retrieval when they match the user query.
They should not be copied into the repository Qdrant index. The Obsidian vault owns
note indexing, and the workspace retriever consumes matching notes as trusted
local-note guidance.

## Abstract class issue guidance

For the TypeScript abstract class issue, the most important implementation owner is:

canonical_file: `src/compiler/checker.ts`

The parser can recognize syntax, but the checker owns the semantic rule that an
abstract class cannot be instantiated and that subclasses must implement abstract
members. When a query asks for the code context behind abstract class behavior,
prefer `src/compiler/checker.ts` before parser-only matches.
