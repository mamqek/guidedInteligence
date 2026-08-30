# Retained file-trace representation design

## Purpose and status

This document describes the retrieval design retained after the 2026-08-29 mixed-island
file-trace experiment. It is the stable architectural account intended for evaluation
and thesis documentation. The chronological attempts, intermediate failures, and run
ledger remain in
[`decisions/mixed-island-file-trace-representation-experiment.md`](decisions/mixed-island-file-trace-representation-experiment.md).

The change solves a specific general problem: a repository file can be structurally
necessary to explain a cross-file mechanism even when no localized snippet from that
destination proves its internal behavior. The system must retain the grounded source,
represent the cross-file relationship, and allow a bounded LLM judgment to select the
destination as supportive evidence without converting structural reachability into a
semantic claim.

The retained implementation produced Builder, BuilderState, WatchMode, and Helpers in
two consecutive TypeScript acceptance runs. It remains intentionally bounded and does
not attempt to solve manifest-only changes or repository-wide mechanical refactors.

## Terminology

- **Observation:** a retrieved or structurally materialized source range with repository
  provenance, obligations, artifact role, and optional CodeGraph owner.
- **Island:** a connected group of observations used as the unit of controller scope
  and deterministic final representation.
- **Owner:** a CodeGraph-resolved function, method, class, or source-owner range.
- **File handoff:** a file-seeded, cross-file relationship expansion intended to reach
  a distinct repository participant.
- **File trace:** a controller-created record that a selected source file reaches a
  destination file through recorded structural relationships. It carries provenance
  and connection counts but does not claim destination behavior.
- **Snippet evidence:** localized source whose qualification and final selection support
  a semantic claim about visible code.
- **Supportive structural evidence:** a file selected because its grounded relationship
  completes navigation through an unresolved mechanism, with internal behavior left
  explicitly unresolved.

## Previous failure mode

The historical successful TypeScript run constructed a WatchMode-to-Helpers file trace
by expanding a file-level cross-file action. Later runs exposed a chain of independent
losses:

1. The WatchMode action could be enumerated but lose the limited round-one scheduling
   competition.
2. When the trace was created, WatchMode could still disappear from final evidence
   because its island was represented by another compiler file.
3. Trace eligibility could depend on the primary scheduling obligation even when the
   same source was relevant to a different unresolved obligation.
4. A rejected localized Helpers snippet could block strong repeated structural
   participation.
5. The trace LLM could accept Helpers after the 14 snippet positions were already full.
6. A repeat that retained WatchMode and Helpers could independently lose BuilderState
   before comparison because global admission consumed the preferred input budget.

These are different stage boundaries. Treating them as one ranking problem would either
miss later failures or introduce an unnecessarily broad exception.

## Retained pipeline

```text
initial hybrid retrieval
    → exact range and owner resolution
    → one strongest comparison observation per obligation
    → globally ranked owner-comparison input within the unchanged budget
    → qualification and evidence islands
    → controller action enumeration
    → bounded pending test-source file handoffs
    → file-trace construction with source obligation provenance
    → final candidate LLM
    → deterministic island and exact trace-source preservation
    → file-trace eligibility
    → dedicated file-trace LLM
    → trace-aware composition within MAX_EVIDENCE
```

The order is part of the design. File-trace eligibility runs after deterministic source
preservation so that an exact source restored by an existing invariant can satisfy the
trace gate. File traces run after the candidate LLM so they supplement selected semantic
evidence rather than competing as if they were equivalent snippets.

## Six retained corrections

### 1. Coverage-aware initial owner-comparison admission

Implementation:
[`initial_owner_comparison.py`](../workspace/pipeline/execution_flow/initial_owner_comparison.py),
`fit_initial_owner_comparison_admission` and
`_coverage_reserved_observation_ids`.

Before global snippet ranking, the admission stage chooses the strongest retrieved
observation associated with each repository obligation. Multiple obligations can select
the same observation; IDs are deduplicated before serialization. Remaining capacity is
filled by the unchanged global ranking.

This is budget redistribution, not budget expansion. The preferred and maximum input
budgets remain unchanged. A reservation can displace a lower-ranked observation, and
the owner-comparison LLM can still reject the reserved input. The trace records
`coverage_reserved_ids` and `coverage_reserved_paths` so the effect can be audited.

This correction was added after `run-20260829T145414Z`: BuilderState was the top raw
file for `explain_state_changes` and yielded nine exact owners, but all nine appeared
after the global preferred-budget crossing. No downstream controller or final-selection
rule could recover evidence that never entered owner comparison.

### 2. Bounded pending test-source file handoffs

Implementation:
[`actions/pending_file_handoffs.py`](../workspace/pipeline/execution_flow/actions/pending_file_handoffs.py),
[`actions/scheduler.py`](../workspace/pipeline/execution_flow/actions/scheduler.py), and
[`retrieval_controller.py`](../workspace/pipeline/execution_flow/retrieval_controller.py).

The controller may retain an enumerated but unselected action only when all of these are
true:

- it is an `ExpandRelationship` action;
- its seed is a file;
- `cross_file_only` is true;
- it has file-handoff provenance;
- its source observation has repository-derived `artifact_role == "test"`.

The ledger holds at most two entries globally and one per island. Each entry has a
two-round lifetime. Reconciliation removes entries whose island is inactive, obligation
is covered, effect was attempted or completed, equivalent action was selected naturally,
or lifetime expired. Starting after round 1, one valid pending handoff may occupy one
existing ordinary action slot.

The scheduler therefore changes which bounded action runs, not how many actions can run.
It adds no controller rounds, graph-call allowance, or unconditional LLM call.

### 3. Exact trace-source representation before trace eligibility

Implementation:
[`qualification_first_retrieval.py`](../workspace/pipeline/execution_flow/qualification_first_retrieval.py),
`_preserve_active_island_candidates`.

The existing deterministic rule preserves a representative for a protected active
island when the candidate LLM selects none. The retained extension handles a narrower
case: if the controller created a file trace from an observation in that island, but
the accepted candidates represent the island only through another file, preserve the
best candidate for that exact source observation.

The condition is provenance-specific. It does not reserve every file or artifact role
inside a mixed island. Candidate deduplication and `MAX_EVIDENCE` still apply. The
consolidation trace records `preserved_file_trace_source_candidate_ids`.

Final orchestration applies this preservation before file-trace eligibility. Otherwise
the trace would be rejected as `source_island_not_selected` and never reevaluated after
its source was restored.

### 4. Obligation-stable file traces

Implementation:
[`file_trace_evidence.py`](../workspace/pipeline/execution_flow/file_trace_evidence.py)
and
[`obligation_retrieval.py`](../workspace/pipeline/execution_flow/obligation_retrieval.py),
`_select_unresolved_file_trace_evidence`.

`FileTraceSeed` and `FileTraceEvidence` carry both the action's primary scheduling
obligation and all repository obligations associated with the source observation. A
trace remains eligible when at least one of those related obligations is partial or
unresolved.

This makes equivalent structural traversals independent of whichever gap happened to
schedule them. It does not allow a trace with no unresolved need: the related-obligation
gate remains mandatory.

### 5. Repeated structural participation remains LLM-gated

Implementation:
[`obligation_retrieval.py`](../workspace/pipeline/execution_flow/obligation_retrieval.py),
`_select_unresolved_file_trace_evidence`.

Snippet qualification asks whether a localized range proves relevant internal behavior.
A file trace asks whether the destination is a grounded structural participant. Those
judgments are related but not identical. A rejected endpoint normally blocks a trace;
the retained exception applies only when the controller recorded at least two direct
source-to-destination call sites.

The threshold only opens the trace LLM gate. Selection still requires:

- an accepted exact source candidate;
- at least one partial or unresolved related obligation;
- no selected snippet already representing the destination;
- endpoint qualification that is not blocking, or the repeated-call exception;
- explicit selection by the dedicated file-trace LLM.

The output reason is constrained to structural participation. It must not infer or
describe unobserved behavior inside the destination file. A one-call rejected endpoint
remains blocked; focused tests cover both the 18-call positive and one-call negative
cases.

### 6. Trace-aware output composition

Implementation:
[`qualification_first_retrieval.py`](../workspace/pipeline/execution_flow/qualification_first_retrieval.py),
`_accepted_file_trace_count`, `_accepted_file_trace_source_candidate_ids`, and final
evidence composition.

Accepted traces reserve positions inside the existing `MAX_EVIDENCE = 14` cap before
snippet candidates are truncated. If a snippet must be displaced, the exact source of
an accepted trace is protected. The trace is then emitted from remaining capacity, and
connected external evidence uses only capacity still available.

This preserves the interpretability invariant:

```text
emitted structural destination ⇒ emitted exact grounded source
```

No accepted trace can increase the final evidence count above 14.

## File-trace eligibility contract

A file trace can reach the dedicated LLM only when all deterministic gates pass:

| Gate | Purpose |
|---|---|
| Exact source accepted | Grounds the relationship in evidence the final result actually contains |
| Source island protected/represented | Prevents unrelated traces from bypassing active-island selection |
| Related obligation unresolved | Requires a current explanatory need |
| Destination absent as snippet | Avoids duplicating already localized semantic evidence |
| Endpoint not blocked, or repeated direct calls | Prevents a weak or rejected one-edge lead from becoming file evidence |
| Trace selection cap available | Bounds the dedicated stage |
| File-trace LLM selects | Requires a contextual judgment that structural participation is useful |

Passing the contract authorizes only a structural claim. It does not upgrade the
endpoint's semantic qualification and does not mark an obligation complete by itself.

## Rejected alternative: representation by artifact role

The experiment compared exact trace-source preservation with reserving an unrepresented
artifact role inside a mixed island. Role diversity appeared attractive because a test
and an implementation file can provide distinct perspectives. It failed the competing-
test fixture: the strongest candidate for the missing `test` role could be a different
test file from the actual trace source.

That alternative would consume evidence capacity without satisfying trace provenance.
It was removed rather than combined with the exact-source rule. The retained design
uses a controller-created trace as the justification for the extra representation,
not artifact diversity alone.

## Resource and safety invariants

The accepted implementation preserves these bounds:

| Resource or behavior | Retained invariant |
|---|---|
| Ordinary controller slots | Unchanged; pending work may replace one slot after round 1 |
| Controller rounds | Unchanged |
| Graph-call allowance | Unchanged |
| Pending ledger | Maximum two entries, one per island, two-round lifetime |
| Initial comparison budget | Unchanged; per-obligation reservation displaces rather than appends |
| Final evidence | `MAX_EVIDENCE = 14` |
| File-trace LLM | Called only when at least one trace passes deterministic eligibility |
| Semantic claims | File evidence cannot claim unobserved destination behavior |
| Domain specificity | No TypeScript path, symbol, testcase, or obligation name in production policy |

## Measured result

The final acceptance profile kept final evidence selection enabled and skipped response
generation:

| Run | Final items | Oracle files retained | Helpers position | Retrieval tokens | Coverage / sufficient |
|---|---:|---|---:|---:|---|
| `run-20260829T150112Z` | 14 | Builder, BuilderState, WatchMode, Helpers | 14 | 106,410 | `partial / false` |
| `run-20260829T150534Z` | 12 | Builder, BuilderState, WatchMode, Helpers | 11 | 103,059 | `partial / false` |

In both runs, Helpers was selected through the file-trace LLM as a supportive structural
participant. Neither decision claimed knowledge of Helpers' internal behavior. The
result is therefore four-file representation stability, not complete semantic coverage.

Focused verification passed twice at 194 tests; the broader relevant suite passed all
214 tests. These measurements were completed before this final documentation revision;
no tests were run as part of the documentation-only change.

## Cross-repository interpretation

Regression runs on Vue 242 and Pandas 10068 retained their implementation Oracles. Most
TypeScript-specific activation paths were dormant: pending scheduling, exact mixed-
island restoration, and the rejected-endpoint exception did not run. Ordinary file
traces selected `src/text-parser.js` and `pandas/core/ops.py` with navigation-only
wording and did not displace an Oracle.

Two additional non-held-out cases exposed separate scope limitations rather than a
failure of this design:

- Vue 13052 is a dependency-manifest case. Qdrant retrieved the package manifest and
  lockfile, but owner-oriented initial admission excluded them before comparison. A
  future solution would require dependency-artifact inference and file-level
  configuration evidence, not changes to CodeGraph scheduling or trace-source
  representation.
- Pandas 35925 is a 25-file mechanical formatting patch. Exhaustive changed-file
  overlap is not equivalent to selecting explanatory mechanism evidence. The required
  evaluation contract for wide refactors must be defined before retrieval is broadened.

Both are registered as deferred NCA-1 / WRF-1 questions in
[`decisions/retrieval-experiment-open-questions.md`](decisions/retrieval-experiment-open-questions.md).
The retained design is frozen while those task classes remain undefined.

## Implementation map

| Responsibility | Module |
|---|---|
| Pending handoff lifecycle | `execution_flow/actions/pending_file_handoffs.py` |
| Ordinary-slot integration | `execution_flow/actions/scheduler.py` |
| Controller ledger and trace events | `execution_flow/retrieval_controller.py` |
| File-trace data contract and aggregation | `execution_flow/file_trace_evidence.py` |
| Initial per-obligation admission | `execution_flow/initial_owner_comparison.py` |
| Final ordering, exact-source preservation, and cap composition | `execution_flow/qualification_first_retrieval.py` |
| Trace eligibility and dedicated LLM selection | `execution_flow/obligation_retrieval.py` |

## Thesis interpretation

The central result is not that more retrieval always improves evidence. The successful
change preserves a causal provenance chain across bounded stages:

```text
unresolved obligation
    → selected source evidence
    → controller-observed repeated cross-file relationship
    → exact source representation
    → explicitly limited structural destination claim
```

Each deterministic correction protects one link in that chain while leaving semantic
selection with the LLM and leaving all resource caps fixed. This is why the retained
design is narrower than general diversity, extra controller capacity, or automatic
promotion of connected files—and why those broader alternatives were not retained.
