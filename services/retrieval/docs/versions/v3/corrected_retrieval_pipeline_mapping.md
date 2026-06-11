# Corrected Retrieval Pipeline Mapping

## Version Summary

This document maps the corrected V3 pipeline back onto the current implementation.

Compared with the V3 pipeline spec itself, this file is implementation-facing: it explains where each corrected stage lives in code, what parts already exist, and what orchestration changes are needed to make the implementation match the corrected design.

## Purpose

This document maps the corrected retrieval pipeline onto the current implementation.

It does not propose a fresh architecture. It answers a narrower question:

- where in the current code does each step already live?
- what should stay?
- what should change?

The intent is to make the correction actionable without inventing a new system.

## Current Top-Level Entry

The current retrieval flow starts in:

- `services/retrieval/workspace.py`
  - `WorkspaceRetrievalStage.retrieve(...)`

This method currently owns:

- index setup
- Obsidian/local-note retrieval
- step-2 planning
- initial narrowing
- role-bucket retrieval
- snippet refinement
- role completion / sufficiency
- final evidence assembly
- explanation handoff

That file remains the orchestration point. The correction is mostly about changing the order and strictness inside this flow.

## Corrected Pipeline to Current Code Mapping

### Step 0. Deterministic prompt distillation

Corrected intent:

- reduce the raw issue prompt to grounded lexical evidence
- do not infer behavior structure yet

Current location:

- `services/retrieval/step2/step2.py`
  - `extract_prompt_evidence(...)`
  - `_extract_raw_prompt_evidence(...)`
  - `_extract_grounded_entities(...)`
  - `_extract_grounded_file_hints(...)`

Status:

- this already exists in roughly the right place
- it should stay deterministic

What to keep:

- inline code extraction
- identifier extraction
- file-hint extraction
- source-priority derivation

What not to add here:

- role fanout
- speculative repo structure
- broad LLM reasoning

### Step 1. Compact repo grounding

Corrected intent:

- provide compact repo context before retrieval planning widens

Current location:

- `services/retrieval/workspace.py`
  - `_build_step2_repo_context(...)`
- `services/retrieval/tools/local.py`
  - `build_repo_sketch(...)`

Status:

- this already exists
- this is the right place to keep the compact repo sketch

What to keep:

- representative files
- top directories
- file-role counts
- compact file index / identifiers
- confirmed file hints from pre-plan repo checks

What this step should remain:

- compact, deterministic repo orientation

What it should not become:

- a substitute for owner selection

### Step 2. Owner hypothesis

Corrected intent:

- pick the most likely implementation owner first
- do not treat all roles symmetrically too early

Current locations involved:

- `services/retrieval/step2/step2.py`
  - `plan_workspace_retrieval_step(...)`
- `services/retrieval/workspace_llm.py`
  - helper-query generation
- `services/retrieval/pipeline/file_level.py`
  - `role_query_package(...)`
  - `iterative_code_context_queries(...)`
  - `collapse_candidates_to_file_candidates(...)`
  - owner-path matching helpers
- `services/retrieval/responsibility.py`
  - `profile_candidate(...)`
  - `score_responsibility(...)`
  - `infer_expansion_intents(...)`

Status:

- the current system still thinks in terms of role buckets
- that can stay for now
- but the practical correction is:
  - the primary owner candidate must dominate the next stage

Minimal correction in current code:

- do not let broad multi-role symmetry decide the retrieval order
- after initial file-level ranking, identify:
  - one primary owner candidate
  - optionally one alternate owner candidate

In current terms, this means:

- `required_buckets` can still exist
- but the strongest implementation owner bucket should be treated as first-class
- the rest should not consume equal refinement budget before the owner is grounded

### Step 3. Mandatory in-file snippet targeting

Corrected intent:

- a file-level owner is only routing
- real evidence must come from inside the file

Current locations:

- `services/retrieval/workspace.py`
  - `_refine_selected_role_buckets(...)`
  - later rescue/refinement passes
- `services/retrieval/pipeline/snippet_level.py`
  - `best_direct_owner_span(...)`
  - `best_in_file_refinement_span(...)`
  - `in_file_search_terms(...)`
  - `in_file_refinement_terms(...)`
  - `role_snippet_queries(...)`
  - `role_followup_queries(...)`
  - `salient_candidate_excerpt(...)`

Status:

- snippet refinement already exists
- but the current failure shows it is still too soft

The needed correction in current code is explicit:

- if a bucket has accepted `X:FILE`
- snippet refinement for that bucket must run inside `X`
- and that bucket cannot be considered grounded until a snippet-level result exists

That is the single highest-confidence behavior change.

The exact place this should be enforced is in:

- `services/retrieval/workspace.py`
  - the logic around required bucket refinement and late bucket assessment

The supporting low-level code already exists in:

- `services/retrieval/pipeline/snippet_level.py`

So this is mostly an orchestration correction, not a missing capability.

### Step 4. Decisive snippet check

Corrected intent:

- ask whether the chosen snippet actually explains the issue behavior
- not whether the file is related in general

Current locations:

- `services/retrieval/role_validation/registry.py`
- `services/retrieval/role_validation/generic.py`
- `services/retrieval/role_completion.py`
- `services/retrieval/workspace_llm.py`
  - `assess_role_buckets_with_llm(...)`
- `services/retrieval/workspace.py`
  - late assessment / completion / sufficiency assembly

Status:

- the current system already has validation and assessment layers
- the correction is not “add assessment”
- it is “make assessment care about snippet decisiveness, not file ownership”

What to change:

- file-level acceptance should count as weak routing evidence only
- decisive acceptance should require snippet-level grounding
- the bucket should remain unresolved if the best snippet is generic or off-target

This is where the current `checker.ts:FILE` problem should be cut off.

### Step 5. Local support expansion

Corrected intent:

- once the owner snippet is grounded, retrieve only what is needed to close specific gaps

Current locations:

- `services/retrieval/workspace.py`
  - supporting bucket retrieval
  - rescue rounds
  - refinement rounds
- `services/retrieval/pipeline/file_level.py`
  - context query generation
- `services/retrieval/pipeline/snippet_level.py`
  - follow-up snippet queries

Status:

- the current system already has support expansion machinery
- the issue is that it can expand too broadly too soon

Minimal correction:

- support expansion should happen after the main owner snippet is grounded
- not before

In practice:

- parser/types/diagnostics/emitter support should only close explicit missing areas
- tests/docs/config should remain deferred until later

### Step 6. Deferred broad support

Corrected intent:

- weak supporting sources should not create false completeness

Current locations:

- `services/retrieval/workspace.py`
  - supporting bucket assembly
- `services/retrieval/pipeline/file_level.py`
  - candidate filtering and role-phase constraints

Status:

- the code already has some support-only downranking
- but not enough to prevent early distraction

What to enforce:

- tests/docs/harness/baselines should not absorb significant retrieval budget while the main implementation role is still only file-level

### Step 7. Explanation generation

Corrected intent:

- explanation should follow evidence quality

Current locations:

- retrieval result assembled in `services/retrieval/workspace.py`
- response generation happens later outside retrieval

Status:

- the explanation stage is already outside retrieval now
- that is fine

What matters for retrieval:

- retrieval must output honest sufficiency and coverage
- retrieval must not inflate confidence when decisive snippet grounding is missing

## What Should Stay As-Is

These parts are directionally correct and should remain:

- deterministic prompt evidence extraction
- compact repo sketching
- file-level narrowing before snippet work
- in-file snippet refinement helpers
- role validation as a separate concept
- explanation generation outside retrieval

## What Should Change First

These are the smallest high-value corrections in the current codebase.

### 1. Make file-level acceptance non-sufficient

Current problem:

- a role bucket can effectively survive with `X:FILE`

Correction:

- `X:FILE` is only a routing win
- the bucket remains unresolved until in-file snippet refinement runs

Primary target file:

- `services/retrieval/workspace.py`

### 2. Force in-file snippet refinement before broad recovery

Current problem:

- the system can still drift into broader recovery while owner grounding is weak

Correction:

- if an owner file is chosen, spend the initial snippet budget inside that file
- do not let global snippet recovery consume that first budget

Primary target files:

- `services/retrieval/workspace.py`
- `services/retrieval/pipeline/snippet_level.py`

### 3. Make late assessment care about snippet quality more than file relevance

Current problem:

- late assessment can still ratify broad owner relevance

Correction:

- late assessment should strongly prefer:
  - snippet-level grounding
  - issue-deciding checks
  - direct diagnostics
  - direct parser branches

Primary target files:

- `services/retrieval/workspace.py`
- `services/retrieval/role_validation/generic.py`
- `services/retrieval/role_completion.py`

### 4. Delay broad support expansion

Current problem:

- support roles can consume attention before the owner path is sharp

Correction:

- support roles should only close explicit gaps after owner grounding

Primary target file:

- `services/retrieval/workspace.py`

## Immediate Rule to Encode

If you want one concrete rule to encode first, it is this:

- if a bucket accepts owner file `X:FILE`, that bucket must run path-scoped in-file snippet refinement inside `X` before it can be treated as grounded

That rule is:

- simple
- local
- high-confidence
- directly supported by the failure pattern we already observed

## Practical Reading of the Current Pipeline

If we rewrite the current implementation in the corrected mental model, it becomes:

1. `step2.py`
   - distill prompt and repo context
2. `file_level.py`
   - choose likely owner files
3. `snippet_level.py`
   - find decisive snippet inside the owner
4. `role_validation/*`
   - decide whether the snippet is actually enough
5. `workspace.py`
   - orchestrate retries, support expansion, and final sufficiency

That is already very close to the code you have.

So the correction is not “throw away the system.”

It is:

- make the orchestration obey the evidence hierarchy that the low-level code already implies

## Bottom Line

The current codebase already contains most of the machinery needed for the corrected pipeline.

The main issue is not missing modules.

The main issue is that `workspace.py` still allows broad bucket progress and partial acceptance before the decisive owner snippet is properly grounded.

That is the place where the correction should be applied first.
