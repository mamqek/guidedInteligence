# Responsibility Retrieval Decision Map

## Purpose

Workspace retrieval should find the code that owns the behavior, not only the files that lexically mention the issue terms. The retrieval path therefore treats first-pass search results as symptoms, expands toward likely owner files, reranks at file level, and only then selects snippets.

This design is based on three observed patterns from specialized code-retrieval work:

- Graph-guided issue localization improves recall and precision by moving from symptom files to causally connected owner files.
- Iterative repository retrieval improves code-context quality by using code discovered in the first pass to seed a second pass.
- Repository-level editing studies show that LLM reasoning helps, but structure-aware tools and deterministic sufficiency checks are needed because LLMs are weak at deciding whether retrieved context is complete.

## Decision Flow

```text
Issue prompt
  ->
deterministic prompt evidence
  ->
Step 2 LLM retrieval plan
  ->
Qdrant first-pass role retrieval
  ->
candidate responsibility profiling
  ->
second-pass code-context retrieval
  ->
mandatory owner-layer expansion
  ->
responsibility rerank
  ->
late LLM snippet assessment
  ->
deterministic coverage gate
  ->
final evidence
```

## 1. First-Pass Retrieval Produces Symptoms

Role subqueries still run as broad Qdrant hybrid searches. These results are not trusted as final owner evidence. They provide:

- files with strong lexical overlap
- snippets that reveal local symbols and file references
- candidate support layers such as parsers, diagnostics catalogs, services, harness code, or command wrappers

The first pass intentionally keeps enough breadth for noisy but useful symptom files to appear.

## 2. Candidate Profiling Separates Owner From Support

Each candidate gets a responsibility profile:

- `likely_owner`
- `possible_owner`
- `support_only`
- `noise`

Support-only files can still seed expansion, but they should not win final evidence when an owner candidate exists. Diagnostics catalogs, generated files, tests, fixtures, generic plumbing, low-level helpers, and adjacent layers are demoted outside roles where they are the actual owner.

## 3. Second-Pass Code-Context Retrieval

After the first pass, the retriever builds a second query from discovered code terms:

- path stems from top candidate files
- explicit referenced file names
- identifier-like code terms such as exported types, class names, and camel-case APIs
- role owner vocabulary, such as `checker`, `semantic`, and `TypeChecker` for validation

This is deterministic. It does not ask the LLM for another rescue plan. The goal is to let the first pass teach the retriever code-native terms that the issue prompt did not contain.

## 4. Mandatory Owner-Layer Expansion

For owner-bearing roles, retrieval must try to move upward from support files to owner files before final selection.

Owner-bearing roles are:

- `validation_checking`
- `input_parsing`
- `representation`
- `diagnostics`
- `behavior_output`

Expansion sources are path-diverse. The retriever scans unique source files instead of consuming the budget on repeated chunks from the same file. Explicit file references are resolved relative to the source file and filtered by role owner vocabulary.

For example, in a TypeScript compiler case:

- `src/compiler/tc.ts` references `checker.ts`
- `src/services/services.ts` references `..\compiler\checker.ts`
- both are support or wrapper layers
- `src/compiler/checker.ts` matches the validation owner vocabulary
- the retriever injects `checker.ts` into the validation candidate pool

If a role has no owner-layer candidate at all, one strong owner-reference vote is enough to force an owner expansion. If an owner candidate already exists, multi-source convergence is required.

## 5. Responsibility Rerank

Reranking happens at file level before final snippets are chosen. The score combines:

- Qdrant retrieval score
- role-validation score
- owner-path and owner-text signals
- graph or reference-expansion support
- support/noise penalties

Owner-path signals outrank lexical similarity. This prevents files such as service wrappers, command runners, and parser syntax snippets from winning a semantic-validation role merely because they contain query words.

## 6. Late LLM Assessment Is Not Sufficiency

The late LLM can assess snippet quality and reject noise, but it is not the final authority on completeness.

The deterministic coverage gate runs after late assessment. Required roles must have strong satisfying evidence, and owner-bearing roles must include an owner-layer candidate. If the gate fails, retrieval is not sufficient even if the late LLM accepted the snippets.

## Failure Interpretation

If TypeScript or Vue still fails after this flow:

- first check whether the owner file entered the candidate pool
- then check whether it was reranked below support files
- then check whether deterministic gates rejected the role
- only after those checks compare against the research assumptions

Expected explanations for remaining gaps:

- the indexed code lacks usable structural edges
- owner references are absent or hidden behind dynamic symbol use
- top candidates do not expose enough code-native terms for second-pass retrieval
- the role owner vocabulary is too narrow for the target framework
- Qdrant chunking splits owner evidence away from the symbols that identify the owner file

