from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence


class UserGoal(str, Enum):
    UNDERSTAND = "understand"
    CHANGE = "change"
    DEBUG = "debug"
    REVIEW = "review"
    PLAN = "plan"
    VERIFY = "verify"
    EXPLORE = "explore"
    UNKNOWN = "unknown"


class ResponseOperation(str, Enum):
    EXPLAIN = "explain"
    INVESTIGATE = "investigate"
    PROPOSE = "propose"
    PRODUCE = "produce"
    EVALUATE = "evaluate"


class TurnRelation(str, Enum):
    NEW_TASK = "new_task"
    CLARIFY = "clarify"
    CONTINUE = "continue"
    MODE_CHANGE = "mode_change"
    ANSWER_TO_CHECK = "answer_to_check"


class SolutionPressure(str, Enum):
    NONE = "none"
    GUIDANCE = "guidance"
    PARTIAL_SOLUTION = "partial_solution"
    COMPLETE_SOLUTION = "complete_solution"


class RetrievalIntent(str, Enum):
    DEFECT_LOCALIZATION = "defect_localization"
    API_OR_USAGE_LOOKUP = "api_or_usage_lookup"
    BEHAVIOR_EXPLANATION = "behavior_explanation"
    CHANGE_OR_IMPACT_PLANNING = "change_or_impact_planning"
    REPOSITORY_EXPLORATION = "repository_exploration"
    CONFIGURATION_RUNTIME = "configuration_runtime"
    VERIFICATION_ANALYSIS = "verification_analysis"


class ExpectedOutput(str, Enum):
    EXPLANATION = "explanation"
    DIAGNOSIS = "diagnosis"
    IMPLEMENTATION_PLAN = "implementation_plan"
    PATCH = "patch"
    REVIEW = "review"
    TEST_PLAN = "test_plan"
    ARCHITECTURE_ASSESSMENT = "architecture_assessment"
    COMPARISON = "comparison"
    EVIDENCE_REPORT = "evidence_report"
    ANSWER_EVALUATION = "answer_evaluation"


class Specificity(str, Enum):
    NARROW = "narrow"
    MEDIUM = "medium"
    BROAD = "broad"


class TargetType(str, Enum):
    FILE = "file"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    MODULE = "module"
    CONFIGURATION = "configuration"
    TEST = "test"
    ISSUE = "issue"
    PULL_REQUEST = "pull_request"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RankedRetrievalIntent:
    intent: RetrievalIntent
    priority: str

    def to_dict(self) -> dict[str, str]:
        return {"intent": self.intent.value, "priority": self.priority}


@dataclass(frozen=True)
class TargetReference:
    target_type: TargetType
    value: str

    def to_dict(self) -> dict[str, str]:
        return {"target_type": self.target_type.value, "value": self.value}


@dataclass(frozen=True)
class IntentClassification:
    user_goals: tuple[UserGoal, ...]
    response_operation: ResponseOperation
    turn_relation: TurnRelation
    solution_pressure: SolutionPressure
    retrieval_intents: tuple[RankedRetrievalIntent, ...]
    primary_expected_output: ExpectedOutput
    expected_outputs: tuple[ExpectedOutput, ...]
    specificity: Specificity
    explicit_targets: tuple[TargetReference, ...]
    confidence: float
    classification_basis: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_goals": [goal.value for goal in self.user_goals],
            "response_operation": self.response_operation.value,
            "turn_relation": self.turn_relation.value,
            "solution_pressure": self.solution_pressure.value,
            "retrieval_intents": [item.to_dict() for item in self.retrieval_intents],
            "primary_expected_output": self.primary_expected_output.value,
            "expected_outputs": [output.value for output in self.expected_outputs],
            "specificity": self.specificity.value,
            "explicit_targets": [target.to_dict() for target in self.explicit_targets],
            "confidence": self.confidence,
            "classification_basis": list(self.classification_basis),
        }


@dataclass(frozen=True)
class IntentClassificationInput:
    user_prompt: str
    active_task_goal: str | None = None
    current_turn_type: str | None = None
    previous_user_request_summary: str | None = None
    previous_response_summary: str | None = None
    last_understanding_check: str | None = None
    last_answer_evaluation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_prompt": self.user_prompt,
            "active_task_goal": self.active_task_goal,
            "current_turn_type": self.current_turn_type,
            "previous_user_request_summary": self.previous_user_request_summary,
            "previous_response_summary": self.previous_response_summary,
            "last_understanding_check": self.last_understanding_check,
            "last_answer_evaluation": self.last_answer_evaluation,
        }


def classification_from_mapping(value: Mapping[str, Any]) -> IntentClassification:
    expected_outputs = tuple(
        _enum_sequence(value.get("expected_outputs"), ExpectedOutput, default=(ExpectedOutput.EVIDENCE_REPORT,))
    )
    primary_expected_output = _enum_value(
        value.get("primary_expected_output"),
        ExpectedOutput,
        default=expected_outputs[0] if expected_outputs else ExpectedOutput.EVIDENCE_REPORT,
    )
    if primary_expected_output not in expected_outputs:
        expected_outputs = (primary_expected_output, *expected_outputs)
    return IntentClassification(
        user_goals=tuple(_enum_sequence(value.get("user_goals"), UserGoal, default=(UserGoal.UNKNOWN,))),
        response_operation=_enum_value(value.get("response_operation"), ResponseOperation, default=ResponseOperation.INVESTIGATE),
        turn_relation=_enum_value(value.get("turn_relation"), TurnRelation, default=TurnRelation.NEW_TASK),
        solution_pressure=_enum_value(value.get("solution_pressure"), SolutionPressure, default=SolutionPressure.NONE),
        retrieval_intents=_ranked_retrieval_intents(value.get("retrieval_intents")),
        primary_expected_output=primary_expected_output,
        expected_outputs=expected_outputs,
        specificity=_enum_value(value.get("specificity"), Specificity, default=Specificity.MEDIUM),
        explicit_targets=_target_references(value.get("explicit_targets")),
        confidence=_confidence(value.get("confidence")),
        classification_basis=_strings(value.get("classification_basis"), limit=8),
    )


def _enum_value(value: object, enum_type: type[Enum], *, default: Any) -> Any:
    candidate = str(value or "").strip()
    for item in enum_type:
        if item.value == candidate:
            return item
    return default


def _enum_sequence(value: object, enum_type: type[Enum], *, default: Sequence[Any]) -> tuple[Any, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return tuple(default)
    seen: set[str] = set()
    items: list[Any] = []
    for raw in value:
        item = _enum_value(raw, enum_type, default=None)
        if item is not None and item.value not in seen:
            seen.add(item.value)
            items.append(item)
    return tuple(items or default)


def _ranked_retrieval_intents(value: object) -> tuple[RankedRetrievalIntent, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    items: list[RankedRetrievalIntent] = []
    seen: set[str] = set()
    for raw in value:
        if not isinstance(raw, Mapping):
            continue
        intent = _enum_value(raw.get("intent"), RetrievalIntent, default=None)
        priority = str(raw.get("priority") or "").strip()
        if intent is None or priority not in {"primary", "secondary"} or intent.value in seen:
            continue
        seen.add(intent.value)
        items.append(RankedRetrievalIntent(intent=intent, priority=priority))
    return tuple(items)


def _target_references(value: object) -> tuple[TargetReference, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    items: list[TargetReference] = []
    for raw in value:
        if not isinstance(raw, Mapping):
            continue
        target_type = _enum_value(raw.get("target_type"), TargetType, default=TargetType.UNKNOWN)
        target_value = str(raw.get("value") or "").strip()
        if target_value:
            items.append(TargetReference(target_type=target_type, value=target_value[:240]))
    return tuple(items[:12])


def _strings(value: object, *, limit: int) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(str(item).strip()[:300] for item in value[:limit] if str(item).strip())


def _confidence(value: object) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, numeric))
