# Evidence Plan: Deferred Design

## Status

This is deferred related work for the [Intent System Design](intent_system_design.md). It is preserved as a possible future retrieval experiment, but it is not part of the recommended first intent rewrite.

The first intent rewrite should leave retrieval behavior stable and focus on intent classification, intent-selected answer/story flows, intent-specific questions and hints, policy boundaries, and evaluation against real prompts.

The active intent design may compare already retrieved evidence with a per-intent evidence contract and display a sufficiency marker. That observational comparison is not an Evidence Plan: it occurs after retrieval and cannot influence retrieval, evidence acceptance, response generation, or policy. This document concerns the separate deferred idea of using intent-derived evidence expectations to direct retrieval before or during search.

## Purpose

An Evidence Plan could conceptually sit after intent classification and target resolution but before retrieval:

```text
intent contract + prompt-specific target
  -> evidence plan
  -> retrieval
  -> coverage assessment
  -> bounded promotion or explicit insufficiency
```

The plan would answer **what must be established**, not **which fixed repository roles or files must be returned**.

## Why It Is Deferred

The repository's earlier role, responsibility, and objective experiments show that changing the vocabulary from roles to semantic evidence objectives does not remove anchoring risk. A model can over-focus on `owner`, `path`, `constraint`, or `observable effect` just as it over-focused on `representation`, `validation`, or `behavior_output`.

The repository has already tested closely related directions:

- The Codex `responsibility-complete` profile asked for implementation owners, responsibility chains, role classifications, and coverage gaps. On two measured cases it improved owner targeting modestly without a sufficiency regression, but retrieval latency increased by 86% and 126%, gross tokens by 100% and 166%, and uncached tokens by 53% and 171%. It was retained only as an opt-in experiment; the compact `efficient` profile was restored as the default.
- Workspace objective-to-role selection preserved overlap on one accepted Vue run while reducing retrieval LLM tokens by 30%, but a stricter support-deferral attempt reduced tokens further and missed the oracle owner file.
- Later adaptive-loop Vue runs missed the oracle owner in two consecutive real runs before support promotion could occur. A plausible objective plan therefore did not guarantee that retrieval followed the correct ownership path.
- Other owner-routing experiments reduced cost but redirected roles to incorrect files on a previously strong TypeScript case.

These results are mixed rather than uniformly negative, but they are strong evidence against changing intent classification, retrieval planning, answer structure, and question generation simultaneously. Doing so would make regressions difficult to attribute and would repeat the earlier tendency to encode an attractive theory of evidence before proving that it improves retrieval across cases.

Calling the plan advisory would not be a sufficient safeguard. Suggested evidence categories can still anchor an LLM's search and interpretation.

## Possible Semantic Objectives

A future experiment could use objectives such as:

- an implementation or subsystem owner;
- an interface or entry point;
- a behavior, call, dependency, or state path;
- a constraint or invariant;
- an observable output, symptom, or effect;
- a usage contract or example;
- a test, assertion, or other verification surface.

These are candidate research concepts, not the approved retrieval contract.

## Experimental Safeguards

If this direction is revisited, it should have an isolated feature flag, an unchanged-retrieval baseline, real multi-case comparisons, and explicit rollback criteria.

1. **Plan claims, not files.** An objective says what the answer must establish. Retrieval decides which artifact can establish it.
2. **Separate required, alternative, optional, and deferred evidence.** Do not retrieve every possibly useful category in the first pass.
3. **Allow `one_of` requirements.** For example, a debug explanation may establish expected behavior through a test, public contract, issue reproduction, or invariant; it should not require all four.
4. **Compose intent defaults deterministically.** Union and deduplicate the primary and secondary contracts rather than asking a model to invent an unrestricted plan.
5. **Adapt with prompt signals.** A stack trace can activate diagnostics; an explicit API can activate usage evidence; a broad architecture request can activate subsystem boundaries.
6. **Use bounded promotion.** Promote deferred evidence only when a required claim remains unsupported after a retrieval round.
7. **Report insufficiency honestly.** Missing required evidence produces an explicit unresolved point; it does not trigger unconditional retrieval of every old role.

## Possible Experimental Shape

```json
{
  "intent": "debug",
  "required": ["observed_symptom", "implementation_owner", "causal_connection"],
  "one_of": ["reproduction", "diagnostic_surface", "failing_assertion"],
  "optional": ["state_path", "relevant_constraint"],
  "deferred": ["configuration_context", "usage_contract"],
  "promote_when": {
    "cause_is_unsupported": ["state_path", "relevant_constraint"],
    "expected_behavior_is_unclear": ["usage_contract", "verification_surface"]
  }
}
```

This shape preserves the proposal for later evaluation. It must not be interpreted as an approved schema or implementation plan.

## Evaluation Requirements

A future experiment should change only the retrieval-planning boundary. Intent classification, explanation generation, and question generation should remain fixed during comparison.

At minimum, compare:

- implementation-owner overlap and rank;
- evidence precision and noise share;
- `coverage_status` and `sufficient` stability;
- retrieval tokens and latency;
- how often suggested objectives distract retrieval from the correct path;
- behavior across narrow bugs, broad exploration, usage, explanation, review, and verification prompts.

Disable or revise the experiment if repeated runs show owner misses, unstable sufficiency, substantial evidence noise, or cost growth without meaningful quality improvement.

## Project Sources

- [Workspace retrieval Step2 source-grounded planner design](../testing/codeRepoQA/workspace%20retrieval%20step2%20source-grounded%20planner%20design.md): records the earlier intent-to-objective proposal and its mixed implementation results, including one accepted narrower run and intermediate regressions that missed the owner file.
- [Retrieval changelog](../services/retrieval/docs/retrieval-changelog.md): records the measured `responsibility-complete` cost increase, restoration of `efficient` as the default, objective-role regressions, and later owner-grounding failures.
- [Reranking redesign summary](../services/retrieval/docs/decisions/reranking_redesign_summary.md): records owner-routing experiments that reduced cost but misrouted roles or retained excessive surface noise.
