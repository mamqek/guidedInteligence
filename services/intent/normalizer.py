from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.intent.models import (
    ExpectedOutput,
    IntentClassification,
    RankedRetrievalIntent,
    ResponseOperation,
    SolutionPressure,
    TargetReference,
    TurnRelation,
    UserGoal,
)


@dataclass(frozen=True)
class NormalizedIntent:
    classification: IntentClassification
    corrections: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "classification": self.classification.to_dict(),
            "corrections": list(self.corrections),
        }


def normalize_intent(classification: IntentClassification, *, user_prompt: str, active_understanding_check: bool = False) -> NormalizedIntent:
    corrections: list[str] = []
    expected_outputs = _dedupe_outputs(classification.expected_outputs)
    if expected_outputs != classification.expected_outputs:
        corrections.append("deduplicated_expected_outputs")
    primary_expected_output = classification.primary_expected_output
    if primary_expected_output not in expected_outputs:
        expected_outputs = (primary_expected_output, *expected_outputs)
        corrections.append("added_primary_expected_output")

    response_operation = classification.response_operation
    if response_operation == ResponseOperation.PRODUCE and primary_expected_output not in _PRODUCIBLE_OUTPUTS:
        response_operation = ResponseOperation.EXPLAIN if primary_expected_output == ExpectedOutput.EXPLANATION else ResponseOperation.PROPOSE
        corrections.append("corrected_produce_without_producible_primary_output")

    turn_relation = classification.turn_relation
    if turn_relation == TurnRelation.ANSWER_TO_CHECK and not active_understanding_check:
        turn_relation = TurnRelation.CLARIFY
        corrections.append("corrected_answer_to_check_without_active_check")

    explicit_targets = tuple(
        target for target in classification.explicit_targets if target.value and target.value.lower() in user_prompt.lower()
    )
    if len(explicit_targets) != len(classification.explicit_targets):
        corrections.append("removed_nonliteral_explicit_targets")

    user_goals = _dedupe_goals(classification.user_goals)
    if user_goals != classification.user_goals:
        corrections.append("deduplicated_user_goals")

    solution_pressure = classification.solution_pressure
    if solution_pressure == SolutionPressure.COMPLETE_SOLUTION and response_operation != ResponseOperation.PRODUCE:
        corrections.append("recorded_complete_solution_without_produce")

    normalized = IntentClassification(
        user_goals=user_goals,
        response_operation=response_operation,
        turn_relation=turn_relation,
        recommended_assistance_mode=classification.recommended_assistance_mode,
        solution_pressure=solution_pressure,
        retrieval_intents=_dedupe_retrieval_intents(classification.retrieval_intents),
        primary_expected_output=primary_expected_output,
        expected_outputs=expected_outputs,
        specificity=classification.specificity,
        explicit_targets=explicit_targets,
        confidence=classification.confidence,
        classification_basis=classification.classification_basis,
    )
    if len(normalized.retrieval_intents) != len(classification.retrieval_intents):
        corrections.append("deduplicated_retrieval_intents")
    return NormalizedIntent(classification=normalized, corrections=tuple(corrections))


_PRODUCIBLE_OUTPUTS = {
    ExpectedOutput.PATCH,
    ExpectedOutput.TEST_PLAN,
}


def _dedupe_outputs(outputs: tuple[ExpectedOutput, ...]) -> tuple[ExpectedOutput, ...]:
    seen: set[str] = set()
    result: list[ExpectedOutput] = []
    for output in outputs:
        if output.value in seen:
            continue
        seen.add(output.value)
        result.append(output)
    return tuple(result or (ExpectedOutput.EVIDENCE_REPORT,))


def _dedupe_goals(goals: tuple[UserGoal, ...]) -> tuple[UserGoal, ...]:
    seen: set[str] = set()
    result: list[UserGoal] = []
    for goal in goals:
        if goal.value in seen:
            continue
        seen.add(goal.value)
        result.append(goal)
    return tuple(result or (UserGoal.UNKNOWN,))


def _dedupe_retrieval_intents(intents: tuple[RankedRetrievalIntent, ...]) -> tuple[RankedRetrievalIntent, ...]:
    seen: set[str] = set()
    result: list[RankedRetrievalIntent] = []
    for intent in intents:
        if intent.intent.value in seen:
            continue
        seen.add(intent.intent.value)
        result.append(intent)
    return tuple(result)
