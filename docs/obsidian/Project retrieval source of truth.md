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

This note describes how the vault participates in retrieval. It intentionally does
not identify implementation files or provide feature-specific guidance; project
context belongs in separate human-readable notes.
