# Qualification Assessment Contract Experiment

Date: 2026-08-30

Status: retained after focused tests and five actual-pipeline runs.

## Stage Boundary

Replace the qualification stage's flat `classification`, `disposition`, `support_level`, and
`supported_obligation_ids` coupling with one immutable assessment value. Qualification owns a
candidate-level judgment: whether to retain it, what kind of visible evidence it contains, which
obligations it contributes to, and which obligations this candidate individually establishes.
The later coverage stage remains authoritative for aggregate `covered`, `partial`, and `missing`
status.

The runtime representation is:

```text
QualificationDecision
  observation_id
  assessment: EvidenceAssessment
    disposition
    evidence_kind
    contributing_obligation_ids
    individually_established_obligation_ids
  rationale: QualificationRationale
    reason
    visible_support
    missing_information
    local_follow_up
```

The assessment is transported intact through controller candidates, islands, coverage, and final
selection. Provenance strings remain provenance and must not be used to reconstruct qualification.

## Motivation And Evidence

Pandas 10068 runs `run-20260830T130550Z` and `run-20260830T130714Z` failed before controller
execution. In both, the LLM classified
`pandas/tests/test_series.py::CheckNameIntegration::test_binop_maybe_preserve_name` as direct
evidence while returning no supported obligation. The source directly proves the operator-side
name result, but does not establish the full operator-versus-named-add mechanism requested by any
single coarse obligation. The current validator rejected this representable partial-direct fact as
an impossible combination.

The downstream support graph also currently adds `state.obligation.id` to every candidate mapped
through that state and treats `qualified_direct_evidence` provenance as direct support. Merely
relaxing the validator would therefore manufacture obligation support. The experiment must replace
that inference with explicit assessment fields before accepting partial direct evidence.

## Expected Impact

- Quality: retain grounded partial direct facts without falsely resolving obligations; preserve
  navigation semantics and established-evidence priority.
- Tokens: qualification payload changes only structurally. No retry or additional LLM call is
  introduced. More supporting facts may reach coverage/final consolidation, so downstream token
  use may increase and must be measured.
- Regression risks: supporting facts could crowd established evidence; contribution IDs could be
  mistaken for coverage; existing origin-string gates could silently reconstruct the old model;
  saved trace tools could fail after the schema change.

## Comparison And Acceptance

1. Focused tests must cover domain invariants, the recorded pandas response, direct-support graph
   separation, candidate serialization, islands, controller actions, coverage, and final flow.
2. Run actual pandas 10068 twice with both then-experimental island-frontier flags. Qualification must complete and
   the controller must execute; no hidden deterministic fallback is allowed.
3. Run actual TypeScript 35468 twice and Vue 242 once with the same flags and unchanged indexes,
   model, prompts outside qualification, final selection, and response-generation policy.
4. Record run IDs, Oracle overlap, coverage/sufficiency, and retrieval tokens. Revert or disable the
   contract if two main-case runs lose the stable four-file TypeScript result or cross-repository
   evidence materially regresses.

Historical trace compatibility, if needed, belongs in an explicit offline migration adapter. The
runtime will not keep the legacy flat qualification branch beside the replacement.

## Measured Result

Focused qualification/controller coverage passes, including a regression that accepts a direct
fact contributing to an obligation while individually establishing none, verifies that no direct
or inherited support is manufactured, and verifies that the fact remains eligible for final
comparison. Full unit discovery ran 492 tests; all affected tests passed. Five unrelated existing
environment/fixture failures remained: three index fixtures missing `lexical_ranking_profile`, one
CodeGraph integration test invoking a Node build without `node:sqlite`, and one requirements-
manifest fixture import.

Actual runs, all with both then-experimental island-frontier flags, final evidence selection enabled, and response
generation skipped:

| Run | Result | Retrieval tokens |
|---|---|---:|
| pandas `run-20260830T191824Z` | completed; partial/false; 0/3 Oracle files | 64,501 |
| pandas `run-20260830T193112Z` | completed; partial/false; 2/3 Oracle files | 97,062 |
| TypeScript `run-20260830T192105Z` | partial/false; all four implementation Oracles | 119,288 |
| TypeScript `run-20260830T192716Z` | partial/false; all four implementation Oracles | 109,858 |
| Vue `run-20260830T193506Z` | partial/false; `src/exp-parser.js` rank 2 | 74,380 |

The pandas crash is fixed repeatably, but its final file quality is not stable. The main TypeScript
acceptance result is stable across two consecutive runs, and Vue retains its important parser
implementation file. Retain the contract; treat broader pandas scheduling/selection as a separate
retrieval problem.

Follow-up outlier checks did not broaden that claim. Pandas 22698
`run-20260830T200532Z` and Vue 10004 `run-20260830T200802Z` both remained zero-overlap. Their first
loss occurred before qualification: pandas admitted `indexes/base.py` but selected no owner from
it, while Vue admitted both Oracle files but selected neither in global owner comparison. The new
contract therefore had no opportunity to change those outcomes.

Post-retention cleanup (2026-08-31) removed the flat `QualificationDecision` compatibility
properties and migrated production consumers to the nested values directly. The offline saved-
trace adapter is the only legacy-schema reader. The three earlier index-fixture failures named
above disappeared when the rejected lexical-profile configuration was removed; the manifest
fixture import was also corrected. The remaining full-suite environment failure is CodeGraph
running under a Node build without `node:sqlite`.
