# Workspace Retrieval Issues And Planner Direction

## Context

The second CodeRepoQA batch exposed two different failure modes in workspace retrieval:

1. Infrastructure/performance failures.
2. Planner/ranking failures on narrow bug reports.

These should not be treated as the same problem.

The timeout cases are mostly CGC indexing failures in the critical path. They prevent a clean comparison of retrieval quality.

The cleaner retrieval-quality signal is `vue-10803`: the issue is narrow, contains a validating repro path, and still ends with partial coverage after the planner spreads effort across broad role buckets.

## Problem Summary

### 1. Planner defaults are too broad for narrow bug reports

The planner currently injects the same fixed role set into every retrieval plan:

- required: `representation`, `input_parsing`, `validation_checking`, `diagnostics`, `behavior_output`
- supporting: `tests`, `docs`, `config`

This is visible in:

- [services/retrieval/workspace/step2/constants.py](C:/Programming/guidedInteligence/services/retrieval/workspace/step2/constants.py)
- [services/retrieval/workspace/step2/step2.py](C:/Programming/guidedInteligence/services/retrieval/workspace/step2/step2.py)

That makes the planner behave as if every issue needs broad subsystem coverage before it can stop. For narrow bug reports, this is the wrong optimization target.

### 2. The role-bucket design rewards coverage breadth over owner-first precision

The retrieval stage evaluates success through required role coverage and synthesis validation. That pushes the run toward filling buckets instead of first proving:

- which implementation artifact most likely owns the behavior, and
- which validating repro/test artifact best constrains the bug.

This behavior is mostly enforced in:

- [services/retrieval/workspace/stage.py](C:/Programming/guidedInteligence/services/retrieval/workspace/stage.py)

The result is over-expansion into support surfaces even when the issue is already specific enough to justify a narrow owner-first search.

### 3. The stage is not yet a true adaptive objective loop

The current stage has internal retries and follow-up passes, but it does not run the full retrieval process as an outer loop over objectives.

The missing loop is:

1. retrieve for the current active objectives;
2. rerank candidate files;
3. select/refine snippets;
4. assess whether the stop contract is satisfied;
5. if not satisfied, promote the smallest deferred objective or retry the weak objective with feedback;
6. repeat with a bounded round limit.

This is the fix for the second problem. Without this loop, removing docs/config/tests or other support roles from the first pass is unsafe, because the stage has no clean mechanism to bring them back only when evidence proves they are needed.

The `vue-10803` verification showed this directly:

- narrowing required roles preserved quality when deferred support roles remained available;
- removing initial support roles entirely reduced tokens but missed the oracle owner file;
- therefore support deferral should wait until Stage can promote deferred objectives after an evidence check.

## What Should Change First

The first problem to solve is the planner breadth problem.

This is the cleaner change because:

- it is upstream of most retrieval behavior;
- it can be implemented generically;
- it does not require hardcoded directory-name heuristics;
- it uses information the system already has at planning time.

## Recommended Insertion Point

### Primary insertion point: `step2` planner

The main change should start in:

- [services/retrieval/workspace/step2/step2.py](C:/Programming/guidedInteligence/services/retrieval/workspace/step2/step2.py)

Reason:

- `WorkspaceRetrievalPlan` already supports dynamic `required_roles`, `supporting_roles`, subqueries, and metadata.
- The current implementation hardcodes default roles into the planner payload and the returned plan.
- If the planner is going to distinguish narrow issues from broad architectural questions, that decision belongs here.

This is the right control-plane boundary:

- `step2` decides how broad the search should be.
- `stage.py` executes and validates that plan.

### Secondary insertion point: retrieval stage stop conditions

After `step2` is changed, `stage.py` should honor the narrower plan and stop earlier when the owner-first objective is already satisfied.

This should be a follow-on change, not the first insertion point.

## Pathway For Solving Problem 1

### Goal

Make the planner narrow required roles earlier when the issue is specific enough, and bias the plan toward:

1. owner artifact identification;
2. nearest validating repro/test artifact;
3. expansion only if coverage is still weak after those are grounded.

### Generic signals the planner can use

These are acceptable because they are issue-derived, not testcase-derived:

- presence of explicit file hints in the prompt;
- presence of symbol-like grounded entities;
- presence of inline code identifiers;
- presence of quoted error text;
- presence of a single concrete behavioral symptom rather than a broad design request;
- concentration of grounded evidence around one artifact family instead of many unrelated areas.

These signals are already close to the current prompt-evidence extraction path.

### Proposed planner changes

#### A. Add issue-specificity classification in `step2`

The planner should explicitly classify the request as one of:

- narrow bug report
- medium-scope behavioral question
- broad subsystem/design question

This does not need to be a separate model stage. It can be a small structured output added to the existing step2 planner response and stored in plan metadata.

Suggested metadata:

- `issue_specificity`
- `owner_first_mode`
- `role_breadth`

#### B. Stop hardcoding the same role set into every returned plan

Today `plan_workspace_retrieval_step()` returns:

- `required_roles=DEFAULT_REQUIRED_RETRIEVAL_ROLES`
- `supporting_roles=DEFAULT_SUPPORTING_RETRIEVAL_ROLES`

That should become adaptive.

For a narrow bug report, an initial plan might instead emphasize:

- required: `behavior_output`, `representation`, `tests`
- supporting: `diagnostics`, `input_parsing`

The exact mix can be debated, but the important part is that:

- `tests` can move from supporting to required when it is the best validating artifact;
- docs/config should usually stay out of the first pass for narrow issues;
- some currently required roles should be deferred unless the first pass fails.

#### C. Generate an owner-first first-pass plan

For narrow issues, the planner should emit:

- fewer required roles;
- stronger owner subqueries;
- explicit validation intent in metadata, such as "do not broaden until owner or repro anchor is resolved."

#### D. Preserve a generic escape hatch

If the first pass cannot resolve a credible owner artifact, the stage can expand into the deferred roles.

This keeps the behavior generic and avoids locking the system into overconfident narrow searches.

## What `stage.py` Should Do After The Planner Change

Once `step2` emits an owner-first plan, `stage.py` should:

- treat the first pass as a narrow retrieval phase;
- avoid support-role expansion until the narrow phase fails;
- stop early when there is both:
  - a credible owner artifact, and
  - a validating repro/test anchor or equivalent constraint.

This should be implemented as a plan-driven stop rule, not as a hardcoded special case for test files or common directory names.

## Why The Change Belongs In `step2` First

If this logic is added only in `stage.py`, the execution layer will still receive a broad plan and will spend effort trying to undo it later.

If this logic is added in `step2`, then:

- subqueries are narrower from the start;
- required-role coverage gates are narrower from the start;
- support expansion becomes conditional instead of automatic;
- the later stage remains an executor rather than an implicit planner.

## Practical First Implementation Slice

The smallest high-value change is:

1. Extend the step2 planner response to classify issue specificity.
2. Return adaptive `required_roles` and `supporting_roles` from `plan_workspace_retrieval_step()`.
3. Store `owner_first_mode` in `WorkspaceRetrievalPlan.metadata`.
4. Make `stage.py` respect that mode by delaying support-role expansion until the first narrow pass fails.

That is enough to test the idea without rewriting the whole retrieval stage.

## Expected Impact

Expected quality impact:

- better precision on narrow bug reports;
- less time spent on support surfaces before owner resolution;
- better chance of reaching sufficient coverage within the budget.

Expected token/tool impact:

- fewer early broad retrieval branches;
- fewer snippets from docs/config/noisy diagnostics;
- possibly lower total retrieval cost on narrow cases.

Known risks:

- false narrowing on issues that only look specific;
- under-coverage if the owner artifact is indirect;
- tests being overweighted when they encode symptoms but not ownership.

## Comparison Plan

To validate the change, compare before/after on:

- `vue-10803` as the main narrow-bug signal;
- one previously successful workspace case such as `TypeScript-2953`;
- at least one case with weaker explicit file hints to ensure the planner does not collapse too aggressively.

Track:

- run ID;
- coverage status;
- sufficient flag;
- retrieval token total;
- selected evidence count;
- whether support-role expansion happened;
- whether the run found an owner artifact before broadening.
