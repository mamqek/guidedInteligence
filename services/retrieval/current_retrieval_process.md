# Current Retrieval Process

## Summary

The current workspace retrieval flow is:

- existing evidence early exit
- deterministic prompt extraction
- LLM grounded planning
- mandatory CGC reindex
- grounded structural narrowing
- required-role subquery retrieval
- per-role validation with local context plus CGC neighborhood checks
- late LLM sufficiency assessment over role buckets
- fallback-only supporting-role retrieval when required roles remain missing

The key design change is that step 2 no longer produces one merged intent object like `entities / subqueries / file_hints`.

Instead, it separates:

- grounded prompt evidence
- LLM retrieval expansion
- speculative terms that are not allowed to become graph anchors yet

## High-Level Flow

```text
Issue / prompt
  ->
deterministic prompt extraction
  ->
LLM grounded planning
  ->
CGC reindex
  ->
grounded CGC narrowing
  ->
per-role lexical retrieval
  ->
open candidate snippets/files
  ->
role validation with callers/callees confirmation
  ->
role-bucket synthesis
  ->
late LLM sufficiency check
  ->
optional supporting-role fallback
  ->
rank and return evidence
```

## Step-by-Step

### 1. Retrieval input enters the system

Input usually includes:

- the current user request or retrieval task text
- conversation history
- existing evidence, if any
- allowed sources from policy

If evidence already exists in `ConversationState.evidence`, retrieval exits early and returns that context.

## Test Harness Pre-Step

For CodeRepoQA testing, there is an extra preprocessing step before retrieval begins.

That pre-step converts the visible issue data into the `state.user_input` text passed into the normal retrieval flow.

For the current CodeRepoQA harness, `testing/codeRepoQA/run_case.py` builds `state.user_input` like this:

```text
Explain the code context needed for this issue.

Title: <issue title>

<visible issue body>
```

So in the CodeRepoQA harness, the retrieval prompt contains:

- a task framing sentence
- the issue title
- the visible initial issue body

And in that harness path it does **not** include:

- hidden evaluator-only comments
- final resolution details
- fix commits
- later hidden oracle information

### 2. Grounded planning

Step 2 no longer begins with an LLM sufficiency gate.

The only early exit is:

- if `ConversationState.evidence` already exists, retrieval returns that context immediately

Otherwise, step 2 builds a retrieval plan with a grounded/speculative split.

### 2.1 Deterministic prompt extraction

The system first extracts hard prompt evidence only.

This includes:

- `raw_prompt_terms`
- `grounded_entities`
- `grounded_file_hints`
- prompt-driven `source_priorities`

These grounded fields come directly from the prompt and recent history, using signals such as:

- exact identifiers
- quoted strings
- file paths
- error-like lines
- config flags and keys
- file-like hints

This stage does **not** invent graph anchors.

### 2.2 LLM grounded planning

The first LLM call takes:

- the raw prompt
- deterministic prompt evidence
- allowed source policy
- required explanation roles
- supporting roles

It returns only expansion fields:

- `llm_concept_terms`
- `llm_subqueries`
- `speculative_entities`
- `source_priorities`
- `negative_filters`

The main rule is:

- grounded entities may be used for structural search
- speculative entities may be used for lexical expansion only until they are confirmed in repo evidence

So step 2 now produces a **retrieval plan**, not a merged intent object.

### 3. CGC forced reindex

The system runs:

- `cgc index --force`

This refreshes the structural code index before retrieval continues.

### 4. Initial grounded structural narrowing

The retriever no longer picks one heuristic CGC query string from the prompt.

Instead, initial CGC narrowing uses only grounded identifiers extracted in step 2.

That means:

- grounded prompt entities may be searched structurally
- speculative entities are not allowed to become graph anchors yet

The current initial CGC phase is therefore:

- small
- grounded
- multi-query rather than single-shot

Its job is to seed likely files from confirmed terms before lexical retrieval expands further.

## Why the Initial Grounding Matters

When grounded CGC narrowing returns files, BM25 can be restricted to those files.

That means the quality of grounded initial anchors strongly shapes:

- which files BM25 can see first
- which snippets rank early
- which file gets opened first
- what evidence the LLM sees in its first refinement round

If the grounded anchors are too weak, the lexical pass is broader and noisier.

### 5. Required-role retrieval

Phase 1 uses only required step-2 subqueries such as:

- `representation`
- `input_parsing`
- `validation_checking`
- `diagnostics`
- `behavior_output`

Each subquery becomes its own retrieval unit.

For each required role, the retriever:

- builds a small query package from the role subquery plus helper anchors
- runs BM25 inside the narrowed file set when available
- opens the best candidate file/snippet
- scores whether the local content matches the role intent
- accepts only the strongest initial per-role anchors
- expands structural support from those anchors with role-aware CGC confirmation
- re-scores pending candidates with dependency and anchor-proximity support

Weak or noisy matches are discarded immediately.

### 6. Role buckets

Accepted candidates are stored in per-role buckets.

Each bucket tracks:

- accepted refs
- rejected refs
- validation notes
- per-candidate weighted score breakdowns
- whether the role is still missing

Phase 1 rejects:

- tests
- baselines
- generated files
- harness / fixture paths

Non-diagnostics roles also reject diagnostics-heavy files such as diagnostic tables.

### 7. Late LLM sufficiency check

The LLM no longer drives the main exploration loop.

Instead it sees:

- the retrieval plan
- compact role buckets
- a small set of accepted snippets
- the currently missing roles

It decides only:

- whether evidence is sufficient
- which roles remain missing
- which anchors are core, secondary, or noise
- whether any very small role-scoped follow-up searches are justified

### 8. Supporting-role fallback

If required roles are still missing, the retriever may run a later supporting pass for:

- `tests`
- `docs`
- `config`

These roles do not participate in the first retrieval phase.

## Current Strengths

- keeps the original prompt alive through first retrieval
- separates grounded evidence from speculative expansion
- uses CGC before later graph expansion
- allows accepted anchors to support nearby files in other roles
- uses BM25 for exact snippet retrieval
- prevents speculative graph anchors from being used directly
- supports multiple refinement rounds
- logs full LLM requests/responses and tool activity

## Current Weaknesses

- early grounded anchors can still be too narrow
- graph traversal is still limited by the current CGC tool surface
- dependency confirmation still depends on path-to-module conversion being good enough for CGC
- some issues may not expose strong role-specific symbols, which can keep graph confirmation weak

## Practical Summary

The current retrieval system is now:

- **not** a merged intent-planning stage
- **not** purely graph traversal
- **not** purely lexical search

It is a role-bucketed process that combines:

- deterministic prompt grounding
- LLM role-directed retrieval planning
- grounded structural narrowing
- per-role BM25 retrieval
- per-role local scoring
- accepted-anchor propagation with dependency and call-flow support
- late LLM sufficiency assessment

The most important current design trait is:

**Step-2 subqueries now drive retrieval directly, and the LLM is used late to judge bucketed evidence rather than to run the main search loop.**
