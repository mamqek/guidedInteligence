# In-File Refinement Design Note

When retrieval has selected a likely owner file, the next step should fuse existing retrieval state with a Codex-style local search inside that file.

The in-file search should use:

- the raw issue title/body/examples
- deterministic prompt evidence
- retrieval terms and role-directed subqueries
- trusted Obsidian/local-note hints
- source priorities
- previous weak snippets and rejection reasons
- role-specific vocabulary
- file path, file role, and indexed/unindexed status

This is not a generic repo-wide search loop. The retrieval system narrows the problem to likely files and roles first. The in-file refinement step then searches only those selected files for better spans, using the accumulated retrieval state as a compact search intent.

The goal is to improve snippet quality without replacing the existing retrieval pipeline.
