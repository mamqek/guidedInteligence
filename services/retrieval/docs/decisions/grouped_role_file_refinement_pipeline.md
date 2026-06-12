# Grouped Role-File Refinement Pipeline

## Problem with the previous snippet stage

The previous snippet refinement stage spent most of its tokens inside repeated owner-declaration selection calls. The expensive step was not broad retrieval itself. The expensive step was repeatedly asking the LLM, for the same `(role, file)` pair, which declaration inside that file looked best.

That structure had two problems at the same time:

- it was expensive because the same file-level declaration shortlist kept getting rebuilt and resent,
- it was fragile because later retries were acting as recovery opportunities, so naive caching of the first answer reduced token cost but also reduced retrieval quality.

The key lesson from the 2026-06-11 experiments was that repeated same-file LLM calls were not pure duplicate waste. Later passes were often seeing different file-local evidence, different shortlist ordering, and different better spans. The system needed to preserve that mutation over iterations without paying for a full declaration-selection prompt every time a new candidate from the same file appeared.

## What the new design is trying to fix

The new pipeline changes the refinement unit from:

- one retrieved candidate inside a file

to:

- one grouped `(role, file)` refinement state per follow-up round

This keeps iterative mutation, but moves that mutation into deterministic local state instead of repeated full LLM prompts.

The intended effect is:

- broad file-restricted snippet search can still discover new local evidence,
- file-local evidence can still change which declarations are preferred,
- the LLM is called once per grouped role/file refinement pass,
- local span expansion and declaration rescoring do the rest.

## Updated stage boundaries

### 1. Follow-up retrieval still happens per role

The role bucket still produces follow-up queries and still runs Qdrant searches. That part remains the cheap evidence-gathering stage.

### 2. Returned candidates are grouped by file before in-file refinement

Instead of refining each returned candidate separately, all candidates for the same `(role, file)` are merged into one grouped refinement pass.

For each grouped file pass, the system accumulates:

- the raw retrieved candidates from that file,
- the follow-up queries that led to them,
- candidate text that surfaced useful file-local terms,
- file-restricted Qdrant refinement hits gathered during the grouped pass.

### 3. Declarations are inventoried once for the file

The file is read once and declaration candidates are extracted once for that grouped pass.

Each declaration becomes a stable local object with:

- name,
- kind,
- line range,
- preview,
- lexical score.

The extraction is intentionally stricter than the older selector stage:

- source files such as `.ts`, `.tsx`, `.js`, and `.jsx` only contribute declaration candidates from real declaration-shaped lines,
- `.json` files do not pretend to have code declarations at all,
- diagnostics-style files therefore stay on chunk/span evidence instead of being forced through fake declaration names.

### 4. Declaration ranking mutates locally

Before any LLM call, declarations are rescored deterministically using the grouped file evidence:

- original role query,
- helper queries,
- grouped follow-up queries,
- identifier terms extracted from the observed snippets,
- distance between observed snippet spans and declaration spans,
- role-specific header/name cues such as `emit`, `check`, `parse`, or `scan`.

The grouped scorer now also applies stronger role-shaped name bias:

- `behavior_output` favors names such as `emit*`, `gen*`, or `render*`,
- `validation_checking` favors names such as `check*`, `validate*`, `assert*`, or `verify*`,
- `input_parsing` favors names such as `parse*`, `scan*`, or `read*`,
- `representation` favors AST/type/symbol/flag structures and downweights generic helpers.

This is where the useful iteration now lives. New snippet evidence can still move a declaration up or down without requiring a full LLM rerun for every raw candidate.

### 5. The LLM sees one compact shortlist per role/file pass

After deterministic rescoring, the system builds one compact shortlist for the file and asks the LLM once which declarations are best.

The shortlist is no longer tied to one raw candidate. It is tied to the grouped file state for that round.

### 6. Snippets are expanded locally

The system does not rely on repeated LLM calls just to get slightly different spans from the same file.

After the grouped declaration choice, the pipeline expands snippets locally from:

- the LLM-selected declarations,
- the top deterministic declarations,
- the best local lexical span,
- only those raw file-restricted Qdrant snippet hits that stay structurally close to the shortlisted declarations.

These candidates are then sent into the existing validation and reranking machinery.

### 7. Validation and late assessment stay downstream

Role validation, bucket reranking, late assessment, and downgrade behavior remain downstream of grouped file refinement.

That means the redesign changes the reranking boundary, not the final acceptance contract.

## How this keeps mutation without repeated full context

The previous design mutated by repeatedly re-asking the LLM on near-duplicate file prompts.

The new design mutates by updating local grouped file state:

- new snippets add new terms,
- new terms change declaration scores,
- changed declaration scores change the compact shortlist,
- the LLM only resolves the final ambiguity inside that updated shortlist.

So the mutation is preserved, but the expensive prompt is not repeated per candidate.

## Practical rule for this stage

Inside snippet refinement:

- Qdrant may repeat per file/query,
- deterministic rescoring may repeat per file/round,
- the owner-declaration LLM should run once per `(role, file, round)`, not once per candidate.

## Expected outcome

If the grouped role-file refinement works as intended:

- token cost should drop because declaration selection is no longer per-candidate,
- retrieval quality should hold better than the previous cache experiments,
- later refinement rounds can still recover to better spans because grouped file state remains mutable.

## Observed result after the stabilization pass

The first grouped implementation proved the structural idea, but it still drifted because:

- declaration extraction was too permissive,
- generic helper names could outrank role-shaped declarations,
- raw support snippets could leak directly into final refinement output.

The stabilization pass tightened those three points and improved repeat-run behavior on the TypeScript case:

- `run-20260612T020815Z`: `strong`, `sufficient=True`, `32316` total retrieval tokens
- `run-20260612T172412Z`: `strong`, `sufficient=True`, `29148` total retrieval tokens
- `run-20260612T172630Z`: `strong`, `sufficient=True`, `29004` total retrieval tokens

That kept the grouped role-file design, reduced owner-declaration selector calls to `3`, and pushed TypeScript retrieval below `30k` total retrieval tokens while staying strong across repeated reruns.
