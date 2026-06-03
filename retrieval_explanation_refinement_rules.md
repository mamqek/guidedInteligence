# Retrieval Explanation Refinement Rules

## Goal

The retriever should gather enough context for a good explanation, not just enough text to stop searching.

A good explanation-oriented retrieval result should help the system:

- explain why the capability, behavior, or failure is currently unsupported or failing
- identify where the system first recognizes or represents the relevant concept
- identify where the system enforces the relevant rules, checks, or constraints

## Hard Requirements

- `Refine Mixed Clusters`
  If the top retrieval cluster includes obvious support, test, harness, fixture, baseline, or generated files, the retriever must perform at least one refinement round unless the user is clearly asking about tests or support code.

- `Refine Narrow Clusters`
  If the initial cluster is too narrow to support a good explanation, the retriever must perform at least one refinement round.
  Current narrow-cluster rule:
  Fewer than two implementation files appear in the top explanation candidates.

- `Use Real Anchors`
  Refinement should expand from the strongest non-support candidates first.
  Current strategy:
  Reuse strong code anchors, then search nearby sibling files and an additional anchor query.

## Success Signals

- `Failure / Unsupported Area`
  The retrieved context includes evidence for where the behavior fails, is unsupported, is rejected, or raises diagnostics.

- `Recognition / Representation Area`
  The retrieved context includes evidence for where the concept is parsed, scanned, modeled, typed, or otherwise represented.

- `Enforcement Area`
  The retrieved context includes evidence for where rules, checks, validation, policy, diagnostics, or constraints are applied.

These are explanation-level success signals. They do not require exact future patch files.

## Stop Conditions

- `Minimum Refinement Satisfied`
  Required refinement rounds have completed.

- `Explanation Signals Satisfied`
  The retriever has enough evidence to cover the failure/unsupported area, the recognition/representation area, and the enforcement area.

- `No Better Anchors`
  A refinement round fails to produce better anchors or new relationships after the minimum required refinement work has already been done.

The retriever may stop when:

- minimum refinement is satisfied, and
- either explanation signals are satisfied or no better anchors are emerging

## Hard Limits

- `Minimum Refinement Rounds`
  Default: `1`
  Applied when the initial cluster is mixed or narrow.

- `Maximum Additional Refinement Rounds`
  Default: `3`
  This is a hard cap on extra retrieval work after the initial pass.

- `Maximum Tool Calls Per Round`
  Configured separately to keep refinement bounded and observable.

## Non-Goals

- These rules do not require exact fix-file prediction.
- These rules do not assume compiler repositories, issue trackers, or any one codebase shape.
- These rules are for explanation quality first; stricter evaluation scoring can be layered on later.

## Current Implementation Notes

- The workspace retriever now evaluates refinement policy explicitly after the initial pass and after each refinement round.
- Deterministic refinement expands from strong code anchors and searches nearby sibling implementation files.
- Retrieval summaries expose the active refinement-policy evaluation so behavior can be inspected and tuned later.
