# Controller Discovery Reliability Experiment Plan

## Objective

Improve controller discovery reliability at the exact boundaries exposed by the 2026-08-25 Pandas and Vue runs:

- repeated actions and repeated deterministic structural requests consume controller budget without opening a new
  frontier;
- canonical implementation snippets from wholly nonadmitted files are deferred but cannot seed controller recovery;
- assignment-defined JavaScript functions such as `exports.parse = function (...)` are not exposed as complete
  source owners;
- callable factories, dictionaries, returned wrappers, and runtime class installation are not represented by the
  ordinary static-call graph;
- `no_evidence_gain` does not distinguish an empty/repeated search from new source lost during materialization.

Every behavior below is an independently reversible experiment. An accepted step becomes the fixed baseline for the
next step. A rejected step is documented and reverted before work continues.

## Fixed baseline

The main saved runs are:

| Case | Run | Result | Controller boundary |
|---|---|---|---|
| Pandas | `run-20260825T062635Z` | `partial/false` | 4 rounds, 14 selected actions, 59 repeated exact round-level structural requests |
| Pandas | `run-20260825T063006Z` | `partial/false` | 3 rounds, 9 selected actions, 59 repeated exact round-level structural requests |
| Vue | `run-20260825T063303Z` | `partial/false` | 3 rounds, 6 selected actions, 23 repeated exact round-level structural requests |
| Vue | `run-20260825T063619Z` | `partial/false` | stopped after round 1 with `no_evidence_gain` |

Pandas initially canonicalized the exact `_arith_method_SERIES::wrapper` and
`_flex_method_SERIES::flex_wrapper`, but deferred-file seed auditing rejected them as
`not_an_admission_held_same_file_alternative`. Vue retrieved the beginning of `exports.parse`, but range resolution
retained only the small `escapeDollar` owner and discarded the unowned remainder.

Keep the testcase snapshots, index signatures, workspace profile, models, prompts, final-selection behavior, and
unrelated retrieval settings fixed while comparing a step.

## Execution and decision rules

For each active experiment:

1. Write the precise stage contract and change only that boundary.
2. Run focused deterministic tests or replay a saved real artifact.
3. Use no more than three implementation variants.
4. Require two repeatable focused or pre-qualification executions under unchanged settings.
5. Inspect exact trace decisions, snippets, lifecycle transitions, request counts, payload characters, runtime, and
   LLM tokens rather than relying on final status alone.
6. Run two actual-pipeline acceptance executions with explanation generation disabled and final evidence selection
   enabled before calling retrieval behavior accepted.
7. Retain only repeatable improvements without a material quality regression. Otherwise record the result and revert
   the step before continuing.

The combined accepted system receives final Pandas and Vue acceptance runs after all isolated decisions.

## Active experiment 1 — Run-scoped repeat prevention

### Boundary

Create one cohesive action/request novelty component used by controller action scheduling and deterministic structural
tool execution. Do not put caching, novelty comparison, or exploration-ledger algorithms into the controller
orchestrator.

### 1A. Exact deterministic request reuse

- Cache deterministic read-only structural results by tool name, normalized arguments, workspace index signature,
  and source snapshot.
- Initially cover exact-symbol lookup, file outlines, source-owner calls, node/range resolution, edge capabilities,
  and identical relationship expansion. Do not cache LLM calls or Qdrant in the first variant.
- Emit explicit cache-hit trace records while preserving the original grounded result.

### 1B. Action novelty before slot allocation

- Compare typed action effects before scheduling, using root, path/scope, capability, direction, edge kinds, target
  symbols/terms, range, obligation, and search kind.
- Record predicted effects and actual requests, sources, snippets, relationships, and gain in a run-scoped exploration
  ledger.
- Reject an action before queue/slot allocation only when its effect is equal to or fully subsumed by a completed
  effect and it introduces no new target, range, frontier, or unresolved relationship.
- A discarded repeated action must not consume either normal action slot or any reserved action slot. Scheduling
  backfills from the remaining novel actions.
- Changed prose alone is not novelty. Unknown effects execute once. Do not use an embedding or LLM similarity gate in
  the first variants.

### Expected impact and acceptance

- Exact repeat counts fall while evidence and final selection remain unchanged for 1A.
- Semantically redundant `_binop`/`Index`/metadata actions fall in 1B without suppressing a unique path, target, or
  source range.
- Traces name every cache hit and every pre-slot suppressed action, the prior effect that covered it, and the action
  selected in its place.

Rollback if useful evidence disappears, action slots remain unfilled despite eligible novel actions, cache scope
crosses a snapshot/index change, or the apparent saving only moves the same requests elsewhere.

## Active experiment 2 — Complete canonical deferred eligibility

### Boundary

Replace the deferred-file seed eligibility restriction `admission-held same-file alternative` with `canonical
deferred implementation snippet`. Preserve existing relevance ranking, scheduling slots, action limits, and lifecycle
states. Deduplicate by canonical snippet ID.

### Expected impact and acceptance

- The saved Pandas state makes `_arith_method_SERIES::wrapper`, `_flex_method_SERIES`, and
  `_flex_method_SERIES::flex_wrapper` eligible instead of recording
  `not_an_admission_held_same_file_alternative`.
- Trace comparison must enumerate every changed eligibility, ranking, scheduling, execution, qualification, and
  lifecycle decision caused by the rule change.
- The controller inspects the relevant deferred wrappers before a weaker new-island rediscovery, without executing
  the full deferred pool.
- Candidate volume and controller cost remain bounded by the unchanged scheduler.

Rollback if generic deferred implementation files displace stronger active-frontier work, the relevant wrappers are
eligible but not meaningfully ranked, or downstream selection regresses in two acceptance runs.

## Active experiment 3 — Language-routed assignment-defined source owners

### Boundary

Add a language-neutral `resolve_source_owners(range)` contract to the existing source-AST router. Each adapter owns
language-specific syntax; retrieval calls the common contract.

- JavaScript/TypeScript: recognize direct `=` assignments whose right side is a function expression or arrow
  function and whose left side is a stable property/element path, including `exports.parse`, `module.exports.foo`,
  and `Foo.prototype.bar`.
- Python: preserve existing `def`/`async def` ownership and recognize the real analogous definition form
  (`name = lambda` or `obj.attr = lambda`). Treat `obj.method = existing_function` as a relationship for experiment
  4, not as a new function definition.
- When external CodeGraph has no persistent owner, return a deterministic source-owner identity with the complete
  function range and provenance.

### Expected impact and acceptance

- Vue `exports.parse` becomes one complete owner containing its expression transformation and nested `replacePath`.
- Existing ordinary function/method resolution does not change.
- Focused fixtures cover positive and negative assignment forms in both routed language adapters.
- Owner counts, canonical IDs, disclosed source, and comparison/qualification payload changes are recorded exactly.

Rollback if later reassignment/callback syntax is misidentified, IDs are unstable, or full-owner disclosure creates
unbounded source payload growth.

## Active experiment 4 — Source-derived callable-registration relationships

### Boundary

Implement a cohesive relationship provider behind the source-AST/CodeGraph boundary, not inside retrieval-controller
orchestration. It may emit only source-proven relationships with exact anchors and a decision/reliability code.

Initial relationship kinds:

- `binds_callable`;
- `returns_callable`;
- `installs_callable`;
- `installs_method` only when the destination name is literal and locally provable.

The first variants are limited to direct assignments, dictionary/keyword values and unpacking, returned named or
nested callables, and literal class/module installation. They must not claim arbitrary runtime behavior.

### Expected impact and acceptance

- Focused Pandas-shaped fixtures trace the source-proven chain from `series_flex_funcs`, through
  `_flex_method_SERIES` and its returned `flex_wrapper`, to the generated `Series.add` installation.
- The real Pandas run either uses the relationship to connect the two arithmetic branches or demonstrates that
  co-present deferred snippets already make the relationship unnecessary.
- Traces distinguish exact CodeGraph edges, source-AST relationships, and unsupported dynamic gaps.

Rollback if generic dictionaries or factories produce false graph relationships, graph noise changes unrelated
islands, or relationship construction grows into orchestration logic.

## Active experiment 5 — Materialization-aware `no_evidence_gain`

This is deliberately the final active behavior experiment.

### Boundary

Record per action:

- raw source count and whether each source is new or previously seen;
- materialized canonical snippet count;
- discarded intervals and reasons;
- new relationships;
- evidence, navigation, coverage, and verified-lead gain.

Keep ordinary `no_evidence_gain` for repeated/empty raw results. When genuinely new source was discarded during
ownership/materialization, emit `source_materialization_loss` and optionally permit exactly one typed repair action,
not an unrestricted extra exploration round.

### Expected impact and acceptance

- Vue run 2 no longer describes newly retrieved-but-lost source as an empty search.
- Repeated identical-source fixtures still stop promptly.
- Logs support a source-backed judgment about whether the distinction improved behavior, merely delayed stopping, or
  should be reverted.

Rollback if termination loops, extra rounds repeat the same source, token cost rises without a new usable snippet, or
the repair path obscures the original materialization defect.

## Deferred experiments and future ideas

### Preserve uncovered retrieved source

Do not implement this in the active sequence. Revisit only after the other experiments and the planned distinction
between an unsuitable snippet and an incomplete snippet are understood.

The proposed future behavior computes the meaningful portions of a Qdrant range not covered by resolved owners and
retains them as unresolved snippets with original provenance. It addresses module-level statements, partial parser
support, and mixed structural/nonstructural chunks, but risks fragmenting source and increasing noise.

### Explicit branch-contrast controller state

Do not implement in the active sequence. A future experiment may retain separately named incomplete chains for
explicitly contrasted entry points such as `+` and `.add`, but this changes coverage semantics and is too bug-prone to
combine with the current source-preservation and navigation work.

## Result ledger

| Experiment | Attempt | Focused run 1 | Focused run 2 | Acceptance runs | Cost change | Decision | Remaining issue |
|---|---:|---|---|---|---|---|---|
| 1A exact request reuse | 1 | Pass | Pass | Pandas `run-20260825T185635Z`, `run-20260825T190049Z` | 57/130 cache hits | Retain | Exact reuse fell, causal coverage did not improve. |
| 1B action novelty | 1 | Pass | Pass | Same runs | 2/6 actions suppressed before slots | Retain | Structured subsumption does not detect every semantic repetition. |
| 2 deferred eligibility | 1 | Pass | Pass | Pandas `run-20260825T202126Z`, `run-20260825T202420Z` | No new calls | Reject variant | TypeScript-only mechanism vocabulary rejected every Pandas candidate. |
| 2 deferred eligibility | 2 | Pass | Pass | Pandas `run-20260825T202753Z`, `run-20260825T203210Z`; combined `run-20260825T212159Z`, `run-20260825T212535Z` | At most one isolated rescue/round | Reverted | Combined repeats alternated between losing the sole implementation Oracle and retaining it at rank 1. |
| 3 assignment owners | 1 | Pass | Pass | Vue `run-20260825T204226Z`, `run-20260825T204554Z` | 53–56 initial source owners | Retain | `exports.parse` reached final evidence at ranks 4/3; caller/error chain remained partial. |
| 4 callable registration | 1 | Pass | Pass | Pandas `run-20260825T205220Z`, `run-20260825T205601Z` | Provider constructed capabilities | Reject variant | New capability was not scheduled. |
| 4 callable registration | 2 | Pass | Pass | Pandas `run-20260825T210310Z`, `run-20260825T210655Z` | One new edge execution in two runs | Reverted | Selected unrelated `_wrap_inplace_method -> f`; never formed the target installation chain. |
| 5 materialization-aware stopping | 1 | Pass | Pass | Vue `run-20260825T211321Z`, `run-20260825T211857Z` | Telemetry only when no loss | Retain telemetry/stop distinction | Both runs recorded zero losses and retained `no_evidence_gain`; repair behavior remains untriggered. |

Invalid infrastructure/LLM runs are excluded: Node-20 starts `run-20260825T185436Z` and
`run-20260825T185510Z`; initial-owner failures during experiments 4 and 5; the experiment-4 provider exception; and
post-controller invalid consolidation JSON during experiment 5. After the Experiment 2 rollback, two additional
Pandas confirmations reached controller qualification but failed explicitly because the LLM emitted promotions
without schema-required visible support; they are not counted as acceptance. The unchanged same-file deferred
baseline remains covered by Experiment 1's two valid Pandas runs.
