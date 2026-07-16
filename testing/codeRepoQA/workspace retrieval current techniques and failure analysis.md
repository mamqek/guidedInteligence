# Workspace Retrieval Current Techniques And Failure Analysis

## Purpose

This note summarizes the current workspace retrieval pipeline in implementation-level detail so future work can compare the design against external references and decide what to change.

It describes what the pipeline does now, not only what we intend it to do. The current design is a hybrid of:

- Step2 LLM planning;
- deterministic prompt-signal normalization;
- legacy role-bucket retrieval;
- owner-first responsibility scoring;
- CGC graph support;
- BM25/Qdrant semantic search;
- late LLM synthesis;
- deterministic coverage gating;
- a first bounded adaptive loop for narrow defect localization.

The most important current result is that the Python/npm environment is fixed, but recent real `vuejs-vue-10803` workspace runs still regress:

| Run | Coverage | Sufficient | Oracle overlap | Retrieved source files | Tool calls | Retrieval LLM tokens | Loop behavior |
|---|---:|---:|---:|---:|---:|---:|---|
| `run-20260712T164219Z` | `partial` | `false` | `0` | `2` | `226` | `12,439` | owner recovery, no support promotion |
| `run-20260712T164506Z` | `partial` | `false` | `0` | `2` | `237` | `12,509` | owner recovery, no support promotion |

Both runs missed the oracle owner file. That means the current failure is not mainly "tests/support promotion did not retrieve enough"; the loop did not even reach support promotion because `owner_grounded=false`.

## Top-Level Runtime Flow

The current orchestration entrypoint is:

```text
services/retrieval/workspace/pipeline/execution_flow/retrieval.py
```

`run_workspace_retrieval(...)` controls the whole retrieval path. Its stages are:

1. Existing evidence short-circuit.
2. CGC index refresh.
3. BM25/Qdrant index rebuild or reuse.
4. Connected-source context collection.
5. Repository context hints for Step2.
6. Step2 LLM planning.
7. Objective-role selection.
8. Initial CGC narrowing.
9. Adaptive retrieval loop.
10. Final evidence selection.
11. Coverage gate and retrieval result construction.

The top-level function is intentionally only orchestration now. Most behavior has been moved into semantic modules:

| Area | Main file |
|---|---|
| Top-level orchestration | `pipeline/execution_flow/retrieval.py` |
| Adaptive rounds and promotion policy | `pipeline/execution_flow/adaptive_loop.py` |
| Role-bucket retrieval | `pipeline/execution_flow/role_retrieval.py` |
| Initial CGC narrowing | `pipeline/execution_flow/narrowing.py` |
| Candidate reranking | `pipeline/execution_flow/candidate_ranking.py` |
| Candidate validation | `pipeline/execution_flow/role_validation_flow.py` |
| Coverage and synthesis | `pipeline/execution_flow/coverage_synthesis.py` |
| Deterministic coverage gate | `pipeline/coverage.py` |
| Objective-to-legacy-role bridge | `pipeline/objective_flow/mapping.py` |
| Step2 planning | `workspace/step2/step2.py` |
| Responsibility profiling | `workspace/responsibility.py` |
| File/path utilities and owner heuristics | `pipeline/file_level.py` |

## Step2 Planning

Step2 lives in:

```text
services/retrieval/workspace/step2/step2.py
```

It sends a structured planning prompt to the LLM with:

- raw user prompt;
- recent history;
- existing evidence;
- allowed source categories;
- connected-source snippets;
- default required/supporting legacy roles;
- deterministic prompt evidence;
- repo-context hints from indexed workspace files.

The Step2 output becomes a `WorkspaceRetrievalPlan` with:

- `prompt_summary`;
- `retrieval_terms`;
- `surface_context_terms`;
- `owner_artifact_terms`;
- `llm_concept_terms`;
- `llm_subqueries`;
- `owner_subqueries`;
- `support_subqueries`;
- `speculative_entities`;
- `source_priorities`;
- `negative_filters`;
- `primary_intent`;
- `secondary_intents`;
- `specificity`;
- `active_objectives`;
- `deferred_objectives`;
- `preferred_relations`;
- `stop_contract`;
- `expansion_policy`;
- deterministic `prompt_signal_flags`.

Important current limitation:

```text
Step2 still returns legacy required/supporting roles as defaults first.
Objective-role selection later rewrites them only when the gated compatibility path is enabled.
```

## Deterministic Prompt Evidence

Step2 also extracts deterministic evidence from the prompt before LLM planning:

- inline code spans;
- quoted strings;
- path-like terms;
- error/warning/traceback-like lines;
- flags and dotted identifiers;
- salient fallback tokens.

It also extracts:

- grounded entities;
- grounded file hints;
- source-priority hints.

Prompt signal flags are computed from raw prompt plus extracted evidence:

| Flag | Current detection |
|---|---|
| `has_error_or_warning` | regex for error, exception, warning, traceback, failed, cannot, unsupported |
| `has_wrong_output` | phrases like expected, actually, wrong output, incorrect, got, should, `toContain` |
| `has_diagnostic_surface` | currently same as `has_error_or_warning` |
| `has_output_symptom` | currently same as `has_wrong_output` |
| `has_native_repro` | repro/test terms such as `test/`, `.spec.`, `expect(`, `assert` |
| `mentions_config` | config/settings/env/file-extension terms |

These flags are generic, but still fairly lexical. For example, `mentions_config` can become true from `.json` or other file-extension evidence even when config is not semantically central.

## Objective Normalization

For `defect_localization:narrow`, `_normalize_objectives(...)` adjusts the LLM's objective list:

- ensures `implementation_owner` is active;
- removes `diagnostic_surface` unless an actual error/warning surface exists;
- adds `effects_output` if wrong-output symptoms exist;
- removes or adds `verification_repro` based on native repro/test evidence;
- defers `configuration_context` unless config is mentioned;
- ensures `behavior_path`, `configuration_context`, and `usage_contract` remain available as deferred objectives.

This is the first layer of owner-first behavior. It is still planner-side metadata until the compatibility role bridge applies it.

## Objective-To-Legacy-Role Mapping

The current execution engine still mostly runs on legacy roles. Objectives are translated into roles in:

```text
services/retrieval/workspace/pipeline/objective_flow/mapping.py
```

Current required-role mapping:

| Objective | Legacy required roles |
|---|---|
| `implementation_owner` | `behavior_output`, `validation_checking` |
| `interface_entry` | `input_parsing` |
| `behavior_path` | `behavior_output`, `representation` |
| `data_state` | `representation` |
| `constraints_validation` | `validation_checking` |
| `effects_output` | `behavior_output` |
| `diagnostic_surface` | `diagnostics` |

Current support-role mapping:

| Objective | Legacy support role |
|---|---|
| `verification_repro` | `tests` |
| `configuration_context` | `config` |
| `usage_contract` | `docs` |

The important design consequence:

```text
The new objective layer is not yet a full retrieval engine.
It narrows, orders, and promotes old role buckets.
```

## Objective-Role Selection Gate

The behavior-changing path is gated by:

```text
ctx.config.objective_role_selection_enabled
```

When enabled, `apply_objective_role_selection(...)` rewrites plan roles from objectives.

For narrow defect localization, the intended first-pass role set usually becomes:

```text
required: behavior_output, validation_checking, representation
supporting: tests, config, docs
```

This is narrower than the original five required roles:

```text
representation, input_parsing, validation_checking, diagnostics, behavior_output
```

But it still has a key weakness:

```text
implementation_owner is mapped to behavior_output and validation_checking.
There is no dedicated owner-file objective with its own scorer and stop rule.
```

That means owner discovery is still inferred through old roles rather than directly optimized.

## Indexing And Search Backends

The pipeline uses multiple local retrieval mechanisms:

| Mechanism | Purpose |
|---|---|
| CGC index | graph/code structure refresh |
| BM25 index | local lexical search over workspace chunks |
| Qdrant hybrid backend | vector/lexical hybrid search over indexed chunks |
| Open file tool | retrieve concrete file spans around candidate lines |
| CGC find/analyze/query tools | structural narrowing and graph support |

The top-level flow first refreshes CGC unless indexing is disabled. Then it rebuilds or reuses BM25/Qdrant.

If CGC index refresh fails, retrieval returns an explicit failure. This is consistent with the project policy: no silent deterministic fallback for an LLM/tool-backed stage that should be available.

## Connected Source Context

Connected-source context is collected before Step2 planning. It can influence the planning prompt and final evidence, but it is not supposed to override workspace owner retrieval.

Connected context currently contributes:

- selected context documents for Step2;
- connected evidence later appended to selected evidence when allowed;
- local-note file hints in metadata.

The workspace retrieval failure we observed on Vue is not primarily a connected-source issue. It happens inside workspace source retrieval and owner grounding.

## Repository Context Hints

Before Step2, `build_step2_repo_context(...)` builds repo hints using indexed workspace information. These hints become part of the Step2 user payload.

The intent is to ground Step2 in actual files/entities rather than pure prompt speculation.

Current risk:

```text
Repo hints can bias Step2 subqueries, but they do not guarantee owner-file recall.
If hints point toward runtime DOM props instead of SSR server DOM props, later role retrieval can miss the oracle owner.
```

## Initial Structural Narrowing

Initial narrowing is in:

```text
services/retrieval/workspace/pipeline/execution_flow/narrowing.py
```

It starts with:

- confirmed file hints;
- grounded file hints.

Then it runs `cgc_find_code` for up to four confirmed/grounded entities:

```text
retrieval_plan.confirmed_entities or retrieval_plan.grounded_entities
```

The results are merged into `global_narrowed_files`.

Important behavior:

- If a CGC query fails, retrieval fails with `cgc_narrowing_failed`.
- If no files are found, retrieval can still proceed with an empty narrowed-file set.
- The narrowed files are not exclusive filters for all search. They are used as boosts/scoped searches inside role retrieval.

This means initial narrowing can help owner recall, but it can also fail to rescue a case when the entity terms are generic or point to adjacent runtime code.

## Role-Bucket Retrieval

Role-bucket retrieval is in:

```text
services/retrieval/workspace/pipeline/execution_flow/role_retrieval.py
```

The main function is:

```text
retrieve_responsibility_role_buckets(...)
```

It does:

1. Select role subqueries for the current phase.
2. Prepare a role bucket for each subquery.
3. Profile candidates by responsibility.
4. Infer expansion intents.
5. Expand candidates using code context / graph paths.
6. Build anchor support.
7. Rerank candidates by responsibility.
8. Return `RoleRetrievalBucket` objects.

### Subquery Selection

For required phase:

```text
subqueries = retrieval_plan.llm_subqueries for requested roles
```

For supporting phase:

```text
subqueries = support_subqueries first, then llm_subqueries
```

This was recently fixed because promoted `tests` roles could previously have no executable subquery if the plan put tests only in `support_subqueries`.

If a requested role has no executable subquery, the trace records:

```text
role_subquery_missing
```

### Preparing A Role Bucket

`prepare_role_bucket(...)` builds helper queries from:

- the role's main query;
- matching `owner_subqueries`;
- role-specific query hints;
- owner artifact terms;
- retrieval terms that match role keywords;
- prompt summary plus role phrase;
- up to two grounded/confirmed entities.

Then it runs up to `MAX_ROLE_QUERIES` hybrid searches.

For each helper query, it does:

1. global Qdrant hybrid search;
2. if narrowed files exist and the query index is less than 2, another path-scoped Qdrant search over narrowed files.

This is important:

```text
Narrowed files are boosted only for the first two helper queries.
They do not dominate all role queries.
```

Retrieved chunks are converted to candidates, seed candidates are selected, and then candidates are collapsed to file-level candidates.

### Direct Owner Candidate Injection

After search, the code checks narrowed files that did not appear in raw search results.

For each narrowed file:

- normalize path;
- skip if already seen;
- compute search terms;
- require either role owner path match or owner artifact path match;
- if it passes, open/read the file and extract a best span;
- inject it as a direct owner candidate.

This is meant to keep important narrowed files from being lost just because Qdrant/BM25 did not rank them.

Potential weakness:

```text
Direct owner candidate injection still depends on path matching and owner-term matching.
If the true owner path does not look like the role according to current role path hints, it can be rejected.
```

In the Vue failure trace, `src/platforms/web/server/modules/dom-props.js` appeared as a rejected file candidate in late synthesis, meaning it was seen but not selected as final owner evidence.

## Candidate Collapse And File Candidates

Search chunks are collapsed to file candidates in:

```text
pipeline/file_level.py
```

`collapse_candidates_to_file_candidates(...)` groups candidates by file path and creates a synthetic source id:

```text
repo-pre:<path>:FILE
```

It preserves:

- top chunk refs;
- line ranges;
- merged text snippets;
- max score.

File candidates are useful for owner discovery, but later gates generally prefer concrete snippet candidates. Many later steps penalize file-level candidates or convert accepted file candidates into spans.

This is a recurring tension:

```text
File-level candidates help recall owner files.
Snippet-level candidates are needed for final coverage and sufficiency.
```

## Responsibility Profiling

Responsibility profiling is in:

```text
services/retrieval/workspace/responsibility.py
```

Each candidate is classified as:

- `likely_owner`;
- `possible_owner`;
- `support_only`;
- `noise`.

The profile uses path and text signals.

Noise signals include:

- tests;
- fixtures;
- baselines;
- generated files;
- node_modules.

Support-only signals include:

- diagnostic catalogs outside diagnostics role;
- helper/util paths;
- plumbing paths;
- low-level leaf paths;
- paths that look like another role's owner.

Owner signals include:

- path matching the role;
- role keywords in text;
- public API path/text;
- role-specific path hints.

Responsibility score combines:

```text
base_score = min(retrieval_score, 8) + min(validation_score, 5)
owner_score = role/path/text owner signals
graph_score = 2 if graph support path matches
support_penalty = 10 for noise, 5 for support_only
```

Then:

```text
total = base_score + owner_score + graph_score - support_penalty
```

Important weakness:

```text
The owner classifier is path/keyword-heavy.
It can demote true owner files if the role vocabulary does not match the actual subsystem vocabulary.
```

For Vue SSR, the true owner is:

```text
src/platforms/web/server/modules/dom-props.js
```

Current scoring can drift toward runtime DOM props:

```text
src/platforms/web/runtime/modules/dom-props.js
```

because both contain `domProps`, but the runtime file has strong generic DOM-props signals while the SSR-specific owner requires understanding server rendering responsibility.

## Responsibility Reranking

Responsibility reranking is in:

```text
pipeline/execution_flow/candidate_ranking.py
```

For each candidate:

1. Run role validation.
2. Compute responsibility score.
3. Sort by responsibility score and candidate rank.
4. Accept candidates unless blocked by noise/support-only/owner-path constraints.

Special rule:

```text
If an owner-path candidate is available for a role requiring owner layer, other candidates can be blocked by owner path.
```

The bucket status after responsibility reranking is:

- `weak` if any accepted candidates exist;
- `missing` if none exist.

It is usually not `strong` yet. Strong status tends to come later after LLM synthesis, deterministic acceptance, protocol bridging, or snippet assessment.

This matters because adaptive loop decisions depend on strong status and owner grounding.

## Role Validation

Role validation is in:

```text
pipeline/execution_flow/role_validation_flow.py
```

Validation first checks whether the path is allowed for the role:

- tests/baselines/generated are disallowed for source roles;
- harness/fixture is disallowed;
- diagnostics paths are disallowed except for diagnostics role;
- diagnostics role requires implementation and diagnostic/json-like path.

Then it selects a role-specific validator from:

```text
workspace/role_validation.py
```

The validation context includes:

- role;
- role query;
- helper queries;
- candidate path;
- candidate text;
- file role;
- dependency paths;
- call paths;
- anchor support.

For representation candidates, validation may run CGC graph queries to confirm whether accepted anchors reference symbols declared in the candidate.

Validation produces:

- local intent score;
- role path score;
- dependency support score;
- anchor proximity score;
- call flow score;
- total score;
- threshold;
- symbol;
- dependency/call/anchor paths.

This score is then absorbed into responsibility reranking.

## Anchor Support

Anchor support connects accepted candidates across roles.

`build_anchor_support(...)` collects accepted anchors and, when an anchor has a symbol, calls:

- `cgc_analyze_callers`;
- `cgc_analyze_callees`.

This produces call paths by anchor. Later validators can use those paths to score candidates.

Current limitation:

```text
Anchor support depends on already accepted anchors.
If initial accepted anchors point at the wrong adjacent file, graph support can reinforce the wrong neighborhood.
```

## Candidate Expansion

Candidate expansion is pulled from:

```text
pipeline/execution_flow/candidate_expansion.py
pipeline/file_level.py
```

The pipeline expands around responsibility candidates using:

- candidate text identifiers;
- explicit references/imports/requires;
- role owner context terms;
- CGC graph relationships;
- converging reference targets;
- protocol relationship candidates.

The intent is to move from a nearby support file to a stronger owner file.

Known risk:

```text
Expansion is only as good as the source candidates and reference vocabulary.
If the initial pool is centered on runtime DOM updates, expansion can stay in runtime DOM update space rather than moving to SSR string generation.
```

## Role Completion

Role completion tries to reuse candidates from other buckets to satisfy weak or missing roles.

It scores cross-role candidates with:

```text
workspace/role_completion.py
```

Inputs include:

- target role;
- target query;
- helper queries;
- candidate path/text/source id;
- source role;
- source state;
- prior validation score;
- accepted anchors by role.

Accepted candidates can be promoted into another role's bucket.

This is meant to avoid retrieving the same file repeatedly and allow one owner file to satisfy multiple adjacent roles.

Current limitation:

```text
Role completion is still role-bucket based.
It does not yet say: "this is the implementation owner objective, therefore it can satisfy owner grounding even if legacy behavior_output/validation_checking/representation are not all strong."
```

## Late Synthesis

Late synthesis is in:

```text
pipeline/execution_flow/coverage_synthesis.py
```

The pipeline first tries deterministic acceptance:

```text
deterministic_synthesis_decision(...)
```

If deterministic coverage gate is not satisfied, it calls an LLM assessor:

```text
assess_role_buckets_with_llm(...)
```

The LLM assessor receives:

- retrieval intent/plan;
- role bucket dictionaries;
- current planning snippets;
- missing roles.

It returns:

- `acceptance_satisfied`;
- `stop_reason`;
- `missing_areas`;
- `accepted_anchor_refs`;
- `rejected_anchor_refs`;
- `snippet_assessment`;
- `follow_up_queries`.

`snippet_assessment` labels refs as:

- `core`;
- `secondary`;
- `noise`.

## Applying Synthesis Feedback

`apply_synthesis_feedback(...)` applies the late assessor's decision back onto buckets.

It:

- converts accepted file candidates to concrete span candidates where possible;
- reranks accepted candidates using final role candidate score;
- drops redundant file candidates;
- removes noise refs;
- builds `satisfying_refs`;
- sets role status to `strong`, `weak`, or `missing`;
- sets `missing_reason`.

Role status becomes `strong` only if:

- there are satisfying snippet refs; and
- the assessor marks a core snippet, or global acceptance is satisfied without follow-up/missing role flags.

If the assessor says a role is missing or asks follow-up for that role, the role can be downgraded:

```text
late_assessment_downgraded
```

This is important in Vue:

```text
The LLM assessor may accept runtime dom-props snippets as core/secondary context but still mark required SSR-specific roles missing.
That causes deterministic gate failure and owner_grounded=false.
```

## Deterministic Coverage Gate

The deterministic gate is in:

```text
pipeline/coverage.py
```

It requires every required role to have:

1. a bucket;
2. `role_status == "strong"`;
3. at least one satisfying candidate;
4. if the role requires owner layer, at least one candidate satisfying owner-layer checks.

Roles requiring owner layer currently include:

```text
validation_checking
input_parsing
representation
diagnostics
behavior_output
```

Owner-layer satisfaction requires either:

- role owner path match; or
- responsibility profile is `likely_owner`, not noise/support-only, and not a plumbing/helper/low-level leaf.

This is a strict legacy role gate.

Important weakness:

```text
For objective-driven narrow bug search, the gate still requires legacy-role strength.
It does not directly evaluate the objective stop contract, such as:
credible owner + symptom-owner connection + repro/output evidence.
```

So even when the oracle owner is found, the run can fail if `behavior_output`, `validation_checking`, and `representation` are not all strong in the old sense.

## Coverage Status And Sufficiency

Final sufficiency is computed in `run_workspace_retrieval(...)`:

```text
final_sufficient =
  bool(selected)
  and synthesis_decision.acceptance_satisfied
  and deterministic_gate.satisfied
```

Coverage status is:

- `strong` only when all required roles are covered in selected evidence and synthesis/gate pass;
- `partial` if selected evidence intersects required roles or any evidence exists;
- `missing` if no selected evidence.

This means:

```text
The deterministic gate is part of final sufficiency, not just an advisory metric.
```

## Adaptive Loop

The adaptive loop is in:

```text
pipeline/execution_flow/adaptive_loop.py
```

It is enabled only when:

```text
objective_role_selection_enabled == true
primary_intent == defect_localization
specificity == narrow
```

Otherwise the legacy compatibility loop runs.

Current max rounds:

```text
MAX_ADAPTIVE_ROUNDS = 3
```

### Round 0

Round 0 retrieves and refines required roles:

```text
round_reason = initial_active_objectives
phase = required
roles = retrieval_plan.required_roles
```

Then it runs:

1. owner focus role selection;
2. synthesis or deterministic acceptance;
3. synthesis feedback;
4. protocol relationship bridge;
5. deterministic gate;
6. focused owner grounded check.

If synthesis and deterministic gate both pass, the loop stops.

### Owner Recovery Round

If Round 0 is not sufficient and `owner_grounded=false`, the loop runs one recovery round:

```text
round_reason = same_objective_owner_recovery
```

It calls:

```text
recover_weak_role_buckets(...)
```

Then reruns:

- protocol bridge;
- deterministic gate;
- owner grounded check.

If no evidence signature changes and owner is still not grounded, it stops with:

```text
partial_no_owner_gain
```

In the two latest Vue runs, this is the important path:

```text
Round 0 did not ground owner.
Round 1 tried same-objective owner recovery.
Owner remained ungrounded.
Support promotion did not happen.
```

### Deferred Objective Promotion

If owner is grounded but sufficiency is not satisfied, the loop promotes the next deferred objective.

Promotion order:

```text
verification_repro
diagnostic_surface
behavior_path
configuration_context
usage_contract
```

It maps promoted objectives back to legacy support/required roles:

- `verification_repro` -> `tests`;
- `diagnostic_surface` -> `diagnostics` if diagnostics is required;
- `configuration_context` -> `config`;
- `usage_contract` -> `docs`.

Before executing a promotion, the loop checks whether the role has an executable subquery in either:

- `support_subqueries`;
- `llm_subqueries`.

If not, it records:

```text
deferred_objective_promotion_skipped
reason = no_executable_promotion_query
```

If promotion runs, supporting-phase retrieval now uses `support_subqueries` first.

Current limitation:

```text
Promotion only happens after owner_grounded=true.
If owner grounding is too strict or wrong, support evidence never gets a chance to help.
```

This is exactly what happened in the latest Vue runs.

## Owner Focus Roles

Owner focus role selection is in:

```text
coverage_synthesis.owner_focus_roles(...)
```

It scores each required role based on:

- best validation score among accepted candidates;
- whether the role requires owner layer;
- number of accepted candidates whose path matches role owner path;
- whether accepted candidates are only file-level;
- whether accepted candidates include snippet-level evidence.

It selects up to two focused roles.

Then `focused_owner_grounded(...)` requires:

- one focused role bucket exists;
- bucket status is `strong`;
- at least one satisfying non-file candidate.

This is strict.

Important weakness:

```text
Owner grounding depends on a legacy role becoming strong.
It does not separately ask whether an implementation-owner candidate was found.
```

So a correct owner file can be present as rejected, weak, file-level, or non-satisfying evidence and still not count as grounded.

## Protocol Relationship Bridge

Protocol bridging uses:

```text
pipeline/protocol_graph.py
pipeline/relationship_flow
```

It discovers candidates related to protocol routes/message terms and can promote them into buckets.

When it promotes candidates:

- validation result is created with acceptance source `protocol_relationship_bridge`;
- role status can become `strong` if promoted candidates are concrete snippets;
- snippet assessment marks them as core.

This is useful for frontend/backend route-like relationships. It is likely less central to the Vue SSR domProps failure.

## Evidence Selection

Final evidence selection is in:

```text
pipeline/evidence_flow
```

The top-level flow selects evidence from required/supporting buckets, then appends:

- accepted decision evidence;
- connected-source evidence.

Selected evidence metadata includes:

- source category;
- source id;
- coverage area;
- file role;
- path;
- retrieval path;
- rank.

The scorecard later evaluates selected/retrieved source files against CodeRepoQA oracle files.

Current issue:

```text
A run can retrieve or see the oracle owner as a rejected file candidate but fail to select it as final evidence.
For benchmark success, final selected/retrieved source files need oracle overlap.
```

## Current Vue Failure Behavior

The latest repaired-runtime Vue runs are important because they show current behavior after the adaptive-loop and support-subquery fixes.

### Run `run-20260712T164219Z`

Summary:

- `coverage_status=partial`;
- `sufficient=false`;
- `overlap_count=0`;
- `implementation_overlap_count=0`;
- retrieved source files:
  - `src/platforms/web/compiler/directives/model.js`;
  - `src/platforms/web/runtime/modules/dom-props.js`;
- no promoted roles;
- no promoted objectives;
- owner grounded false.

Round behavior:

- Round 0: required roles all weak after initial retrieval;
- Round 1: same-objective owner recovery;
- owner remained ungrounded;
- support promotion did not run.

### Run `run-20260712T164506Z`

Summary:

- `coverage_status=partial`;
- `sufficient=false`;
- `overlap_count=0`;
- `implementation_overlap_count=0`;
- retrieved source files:
  - `src/platforms/web/runtime/directives/model.js`;
  - `src/platforms/web/runtime/modules/dom-props.js`;
- no promoted roles;
- no promoted objectives;
- owner grounded false.

Round 0 initially had behavior output strong, but after recovery and late synthesis all required role statuses ended missing/weak and owner grounding remained false.

The late assessor explicitly rejected the oracle-like server file candidate in one trace:

```text
repo-pre:src/platforms/web/server/modules/dom-props.js:FILE
```

This suggests the file can enter the candidate pool but fail ranking/snippet/late-assessment conversion.

## Why Support Promotion Did Not Help

The recent support-subquery fix is real and unit-covered:

```text
supporting phase now uses support_subqueries first.
```

But Vue did not exercise it because the loop condition is:

```text
promote deferred objective only if owner_grounded == true and sufficiency == false
```

In both real runs:

```text
owner_grounded == false
```

So the loop uses owner recovery, not support promotion.

This means the next useful work is probably not increasing loop limit and not further improving tests/docs/config promotion. The next useful work is owner grounding and owner candidate selection.

## Likely Failure Points

### 1. No Dedicated Implementation Owner Engine

`implementation_owner` currently maps to:

```text
behavior_output
validation_checking
```

This forces owner discovery through legacy role semantics. For narrow defect localization, the first question should be:

```text
Which source artifact most likely owns the fix?
```

Current logic instead asks:

```text
Which behavior_output/validation_checking/representation role buckets are strong?
```

That can miss a true owner if it does not cleanly satisfy those legacy roles.

### 2. Owner Grounding Is Too Dependent On Strong Legacy Buckets

`focused_owner_grounded(...)` requires:

- selected focus role;
- bucket status strong;
- satisfying non-file candidate.

This ignores intermediate states like:

- true owner present as file candidate;
- true owner accepted but downgraded by late synthesis;
- true owner rejected as support-only;
- true owner found in a non-focused role;
- true owner lacks snippet conversion.

For adaptive retrieval, this is dangerous because owner grounding controls whether support promotion can happen.

### 3. Late Synthesis Can Downgrade Useful Owner Evidence

The LLM assessor can mark roles missing and request follow-up. `apply_synthesis_feedback(...)` then downgrades bucket status.

This is useful when evidence is genuinely weak, but it can overrule candidate ranking in a way that blocks loop progress.

In Vue, the assessor wants SSR string-generation evidence and rejects runtime-only evidence. That is reasonable. But the result is:

```text
owner not grounded -> support promotion blocked -> run ends partial
```

There is no separate path that says:

```text
The assessor's follow-up query points to a better owner target; run a targeted owner round using that query.
```

The owner recovery round exists, but the latest runs still failed to promote the server dom-props file.

### 4. File-Level Owner Candidates Are Not Enough

The true Vue owner can appear as:

```text
repo-pre:src/platforms/web/server/modules/dom-props.js:FILE
```

But final grounding wants non-file satisfying snippets. If file-to-span conversion or snippet selection fails, owner grounding fails.

A future owner engine may need a two-stage state:

```text
owner_file_grounded
owner_snippet_grounded
```

Then the loop can decide whether to open/refine a promising owner file before declaring owner missing.

### 5. Path/Keyword Responsibility Heuristics May Prefer Adjacent Runtime Files

Current responsibility scoring uses role path hints and text keyword matches.

For Vue:

- runtime `dom-props.js` has strong DOM props signals;
- server `dom-props.js` is the SSR owner but needs the search to care about server string rendering;
- compiler/runtime model directive files can appear because textarea/model terms are in the issue.

Without a stronger owner objective, the system can select plausible adjacent files that explain DOM props generally, not the SSR bug owner.

### 6. Stop Contract Is Not Objective-Aware Enough

Step2 emits a stop contract, but final sufficiency is still:

```text
selected evidence exists
and synthesis acceptance satisfied
and deterministic legacy-role gate satisfied
```

For `defect_localization:narrow`, a better contract might be:

```text
credible implementation owner
and symptom-owner connection
and one of native repro / observable output / diagnostic surface
```

The current deterministic gate does not implement that directly.

### 7. Recovery Does Not Escalate From LLM Follow-Up Into Owner Search Strongly Enough

The late assessor returns follow-up queries like:

```text
Show the SSR renderer code that generates the final HTML string for textarea elements...
```

But current recovery still operates inside role-bucket mechanics. It may not treat follow-up as:

```text
new owner-search query with high priority
```

So the system can keep retrieving nearby runtime/directive files.

## What Seems To Work

These parts are useful and should probably be preserved unless proven otherwise:

1. Explicit Step2 planner contract with intent/specificity/objectives.
2. Deterministic prompt signal flags to correct/normalize LLM objectives.
3. Gated rollout through `objective_role_selection_enabled`.
4. Separate `support_subqueries` and support-phase retrieval.
5. Trace-rich round summaries.
6. Real-run changelog discipline.
7. Owner/support/noise responsibility profiling.
8. Hybrid global plus narrowed-path search.
9. File-level candidate collapse for owner recall.
10. Late LLM synthesis as an assessor rather than the only gate.

The main problem is not absence of techniques. The problem is the interaction among them:

```text
objective planner -> legacy role mapping -> role scoring -> late downgrade -> strict owner grounding -> no support promotion
```

## What Looks Most Worth Reworking

### A. Add A Dedicated `implementation_owner` Retrieval Bucket

Instead of mapping owner to `behavior_output` and `validation_checking`, create a first-class owner retrieval path:

```text
role/objective: implementation_owner
goal: rank likely fix files
evidence unit: source file first, snippet second
stop contribution: credible_owner
```

This owner path should be allowed to accept a file-level candidate as `owner_file_grounded`, then force snippet opening/refinement before final sufficiency.

### B. Split Owner Grounding Into File And Snippet States

Current boolean:

```text
owner_grounded
```

Possible replacement:

```text
owner_file_grounded
owner_snippet_grounded
owner_role_satisfied
```

Loop behavior could then be:

- no owner file -> broaden owner search;
- owner file found but no snippet -> open/refine exact file;
- owner snippet found but stop contract missing -> promote repro/support/path objective.

### C. Use LLM Follow-Up Queries As Owner-Recovery Queries

If late synthesis says behavior_output/validation is missing and follow-up query mentions a concrete subsystem, the next recovery round should execute that query with owner priority, not just normal role recovery.

In Vue, the follow-up query explicitly asks for:

```text
SSR renderer code that generates final HTML string for textarea elements
```

That should strongly bias search toward `server/modules/dom-props.js` and `server/render.js`, not runtime DOM props.

### D. Make The Gate Objective-Aware

Keep the legacy deterministic gate for compatibility, but add an objective stop-contract gate for narrow defects:

```text
implementation_owner: credible owner file/snippet
effects_output: wrong/expected output connection
verification_repro: native repro/test if available
behavior_path: only required if owner-output connection is not direct
```

Then final sufficiency can use objective gate for objective-enabled runs.

### E. Treat Rejected Oracle-Like File Candidates As Diagnostic Signals

When a file candidate is rejected but matches owner terms or late follow-up query terms, log it as:

```text
owner_candidate_rejected
```

Then recovery can target rejected owner-like candidates for snippet opening before abandoning the owner.

### F. Add "No Owner Gain" Diagnostics

When the loop stops with `partial_no_owner_gain` or owner remains false after recovery, the summary should say:

- which files were closest owner candidates;
- why they were rejected;
- whether they were file-only;
- whether late synthesis rejected them;
- which follow-up query should be retried.

This would make benchmark failures easier to debug.

## Questions For External Reference Search

Future literature/reference work should focus less on generic retrieval and more on these precise questions:

1. How should bug-localization systems separate file-level localization from snippet-level explanation?
2. How do IR bug-localization methods rank owner/fix files when symptom files share vocabulary with owner files?
3. How should iterative retrieval use assessor feedback without drifting into adjacent but wrong subsystems?
4. How should a retrieval agent decide between broadening search and refining a promising file candidate?
5. How do program-analysis-backed retrieval systems combine graph reachability with textual bug-report matching?
6. What stop criteria are used for bug localization vs explanation vs API usage search?
7. How can role/objective taxonomies be evaluated without overfitting to benchmark oracle comments?

## Current Verification Commands

Python/npm runtime is now fixed so these commands should use the project venv:

```powershell
npm.cmd run coderepoqa:evaluate:workspace -- --issue-json testing/codeRepoQA/corpus/cases/vuejs-vue-10803/issue.json
```

Focused unit gate:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_workspace_step2_objectives tests.test_coderepoqa_retrieval tests.test_workspace_retrieval
```

The unit gate passed after the support-subquery fix:

```text
Ran 85 tests in ~22s
OK
```

But the real Vue runs regressed, so the next implementation should be validated by at least two real Vue runs and should not be accepted on token reduction alone.

