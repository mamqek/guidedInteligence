from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence


class TaskIntent(str, Enum):
    EXPLORE = "explore"
    EXPLAIN = "explain"
    USE = "use"
    DEBUG = "debug"
    CHANGE = "change"
    PLAN = "plan"
    REVIEW = "review"
    VERIFY = "verify"


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
    SUBSYSTEM = "subsystem"
    ERROR = "error"
    UNKNOWN = "unknown"


class TargetState(str, Enum):
    EXPLICIT = "explicit"
    CONTEXTUAL = "contextual"
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class TargetReference:
    target_type: TargetType
    value: str

    def to_dict(self) -> dict[str, str]:
        return {"target_type": self.target_type.value, "value": self.value}


@dataclass(frozen=True)
class IntentStage:
    id: str
    label: str
    purpose: str

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "label": self.label, "purpose": self.purpose}


@dataclass(frozen=True)
class IntentQuestionContract:
    prerequisite_stage_ids: tuple[str, ...]
    stem_families: tuple[str, ...]
    stem_descriptions: Mapping[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "prerequisite_stage_ids": list(self.prerequisite_stage_ids),
            "stem_families": list(self.stem_families),
            "stem_descriptions": dict(self.stem_descriptions),
        }


@dataclass(frozen=True)
class IntentContract:
    intent: TaskIntent
    retrieval_description: str
    stages: tuple[IntentStage, ...]
    evidence_expectations: tuple[str, ...]
    stop_condition: str
    question: IntentQuestionContract
    constrained_assistance: str

    def to_dict(self, *, include_evidence_expectations: bool = True) -> dict[str, Any]:
        value: dict[str, Any] = {
            "intent": self.intent.value,
            "retrieval_description": self.retrieval_description,
            "stages": [stage.to_dict() for stage in self.stages],
            "stop_condition": self.stop_condition,
            "question": self.question.to_dict(),
            "constrained_assistance": self.constrained_assistance,
        }
        if include_evidence_expectations:
            value["evidence_expectations"] = list(self.evidence_expectations)
        return value


@dataclass(frozen=True)
class IntentClassification:
    intents: tuple[TaskIntent, ...]
    turn_relation: TurnRelation
    solution_pressure: SolutionPressure
    specificity: Specificity
    target_state: TargetState
    explicit_targets: tuple[TargetReference, ...]
    confidence: float
    classification_basis: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "intents": [intent.value for intent in self.intents],
            "turn_relation": self.turn_relation.value,
            "solution_pressure": self.solution_pressure.value,
            "specificity": self.specificity.value,
            "target_state": self.target_state.value,
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


@dataclass(frozen=True)
class IntentContext:
    intents: tuple[TaskIntent, ...]
    specificity: Specificity
    explicit_targets: tuple[TargetReference, ...]

    def to_dict(self) -> dict[str, Any]:
        from services.intent.contracts import get_intent_contract

        return {
            "intents": [
                {
                    "intent": intent.value,
                    "description": get_intent_contract(intent).retrieval_description,
                }
                for intent in self.intents
            ],
            "specificity": self.specificity.value,
            "explicit_targets": [target.to_dict() for target in self.explicit_targets],
        }


@dataclass(frozen=True)
class IntentFlowPlan:
    intents: tuple[TaskIntent, ...]
    contract_stage_ids: tuple[str, ...]
    contracts: tuple[IntentContract, ...]

    def to_generation_dict(self) -> dict[str, Any]:
        return {
            "intents": [intent.value for intent in self.intents],
            "contract_stage_ids": list(self.contract_stage_ids),
            "contracts": [contract.to_dict(include_evidence_expectations=False) for contract in self.contracts],
        }


def classification_from_mapping(value: Mapping[str, Any]) -> IntentClassification:
    intents = _enum_sequence(value.get("intents"), TaskIntent)
    if not intents:
        raise ValueError("Intent classification returned no recognized task intents.")
    return IntentClassification(
        intents=intents,
        turn_relation=_required_enum(value.get("turn_relation"), TurnRelation, "turn_relation"),
        solution_pressure=_required_enum(value.get("solution_pressure"), SolutionPressure, "solution_pressure"),
        specificity=_required_enum(value.get("specificity"), Specificity, "specificity"),
        target_state=_required_enum(value.get("target_state"), TargetState, "target_state"),
        explicit_targets=_target_references(value.get("explicit_targets")),
        confidence=_confidence(value.get("confidence")),
        classification_basis=_strings(value.get("classification_basis"), limit=8),
    )


def _required_enum(value: object, enum_type: type[Enum], field_name: str) -> Any:
    candidate = str(value or "").strip()
    for item in enum_type:
        if item.value == candidate:
            return item
    raise ValueError(f"Intent classification returned invalid {field_name}: {candidate!r}.")


def _enum_sequence(value: object, enum_type: type[Enum]) -> tuple[Any, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    seen: set[str] = set()
    items: list[Any] = []
    for raw in value:
        candidate = str(raw or "").strip()
        item = next((entry for entry in enum_type if entry.value == candidate), None)
        if item is None:
            raise ValueError(f"Intent classification returned invalid {enum_type.__name__}: {candidate!r}.")
        if item.value in seen:
            raise ValueError(f"Intent classification returned duplicate {enum_type.__name__}: {candidate!r}.")
        seen.add(item.value)
        items.append(item)
    return tuple(items)


def _target_references(value: object) -> tuple[TargetReference, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    items: list[TargetReference] = []
    for raw in value:
        if not isinstance(raw, Mapping):
            continue
        target_type = _required_enum(raw.get("target_type"), TargetType, "target_type")
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
    except (TypeError, ValueError) as exc:
        raise ValueError("Intent classification returned invalid confidence.") from exc
    if not 0.0 <= numeric <= 1.0:
        raise ValueError("Intent classification confidence must be between 0 and 1.")
    return numeric
