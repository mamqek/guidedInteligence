from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
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


class EvidenceRole(str, Enum):
    IMPLEMENTATION = "implementation"
    TEST = "test"
    CONFIGURATION = "configuration"
    DOCUMENTATION = "documentation"
    ANY = "any"


class EvidenceSource(str, Enum):
    REPOSITORY = "repository"
    PROMPT = "prompt"
    EXTERNAL = "external"


class EvidenceBoundary(str, Enum):
    PROMPT = "prompt"
    LOCAL = "local"
    LOCAL_TO_EXTERNAL_HANDOFF = "local_to_external_handoff"
    EXTERNAL = "external"


@dataclass(frozen=True)
class TargetReference:
    target_type: TargetType
    value: str

    def to_dict(self) -> dict[str, str]:
        return {"target_type": self.target_type.value, "value": self.value}


@dataclass(frozen=True)
class RequestAnchors:
    paths: tuple[str, ...] = ()
    primary_symbols: tuple[str, ...] = ()
    supporting_symbols: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    literals: tuple[str, ...] = ()
    identifiers: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "paths": list(self.paths),
            "primary_symbols": list(self.primary_symbols),
            "supporting_symbols": list(self.supporting_symbols),
            "errors": list(self.errors),
            "literals": list(self.literals),
            "identifiers": list(self.identifiers),
        }


@dataclass(frozen=True)
class EvidenceObligation:
    id: str
    description: str
    required: bool
    depends_on: tuple[str, ...] = ()
    anchor_refs: tuple[str, ...] = ()
    evidence_role: EvidenceRole = EvidenceRole.IMPLEMENTATION
    evidence_source: EvidenceSource = EvidenceSource.REPOSITORY
    evidence_boundary: EvidenceBoundary = EvidenceBoundary.LOCAL
    stage_ids: tuple[str, ...] = ()
    requires_repository_handoff: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "required": self.required,
            "depends_on": list(self.depends_on),
            "anchor_refs": list(self.anchor_refs),
            "evidence_role": self.evidence_role.value,
            "evidence_source": self.evidence_source.value,
            "evidence_boundary": self.evidence_boundary.value,
            "stage_ids": list(self.stage_ids),
            "requires_repository_handoff": self.requires_repository_handoff,
        }


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
    anchors: RequestAnchors = RequestAnchors()
    search_terms: tuple[str, ...] = ()
    evidence_obligations: tuple[EvidenceObligation, ...] = ()

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
            "anchors": self.anchors.to_dict(),
            "search_terms": list(self.search_terms),
            "evidence_obligations": [obligation.to_dict() for obligation in self.evidence_obligations],
        }


@dataclass(frozen=True)
class IntentClassificationInput:
    user_prompt: str
    repository_name: str | None = None
    repository_context: Mapping[str, Any] | None = None
    active_task_goal: str | None = None
    current_turn_type: str | None = None
    previous_user_request_summary: str | None = None
    previous_response_summary: str | None = None
    last_understanding_check: str | None = None
    last_answer_evaluation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_prompt": self.user_prompt,
            "repository_name": self.repository_name,
            "repository_context": dict(self.repository_context or {}),
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
    anchors: RequestAnchors = RequestAnchors()
    search_terms: tuple[str, ...] = ()
    evidence_obligations: tuple[EvidenceObligation, ...] = ()

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
            "anchors": self.anchors.to_dict(),
            "search_terms": list(self.search_terms),
            "evidence_obligations": [obligation.to_dict() for obligation in self.evidence_obligations],
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
    anchors = _request_anchors(value.get("anchors"))
    known_anchors = {
        item
        for values in anchors.to_dict().values()
        for item in values
    }
    return IntentClassification(
        intents=intents,
        turn_relation=_required_enum(value.get("turn_relation"), TurnRelation, "turn_relation"),
        solution_pressure=_required_enum(value.get("solution_pressure"), SolutionPressure, "solution_pressure"),
        specificity=_required_enum(value.get("specificity"), Specificity, "specificity"),
        target_state=_required_enum(value.get("target_state"), TargetState, "target_state"),
        explicit_targets=_target_references(value.get("explicit_targets")),
        confidence=_confidence(value.get("confidence")),
        classification_basis=_strings(value.get("classification_basis"), limit=8),
        anchors=anchors,
        search_terms=_strings(value.get("search_terms"), limit=16),
        evidence_obligations=_evidence_obligations(value.get("evidence_obligations"), known_anchors=known_anchors),
    )


def _request_anchors(value: object) -> RequestAnchors:
    mapping = value if isinstance(value, Mapping) else {}
    return RequestAnchors(
        paths=_strings(mapping.get("paths"), limit=12),
        primary_symbols=_strings(mapping.get("primary_symbols"), limit=16),
        supporting_symbols=_strings(mapping.get("supporting_symbols"), limit=16),
        errors=_strings(mapping.get("errors"), limit=8),
        literals=_strings(mapping.get("literals"), limit=12),
        identifiers=_strings(mapping.get("identifiers"), limit=16),
    )


def _evidence_obligations(value: object, *, known_anchors: set[str] | None = None) -> tuple[EvidenceObligation, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    obligations: list[EvidenceObligation] = []
    seen: set[str] = set()
    for raw in value[:12]:
        if not isinstance(raw, Mapping):
            continue
        obligation_id = str(raw.get("id") or "").strip()[:80]
        description = str(raw.get("description") or "").strip()[:500]
        if (
            not re.fullmatch(r"[a-z][a-z0-9_]{0,47}", obligation_id)
            or not description
            or obligation_id in seen
        ):
            raise ValueError("Request analysis returned an invalid or duplicate evidence obligation.")
        valid_dependencies = tuple(
            dependency
            for dependency in _strings(raw.get("depends_on"), limit=8)
            if dependency in seen
        )
        seen.add(obligation_id)
        evidence_source = _optional_enum(raw.get("evidence_source"), EvidenceSource, EvidenceSource.REPOSITORY)
        evidence_boundary = _optional_enum(
            raw.get("evidence_boundary"),
            EvidenceBoundary,
            EvidenceBoundary.PROMPT if evidence_source == EvidenceSource.PROMPT else EvidenceBoundary.LOCAL,
        )
        obligations.append(
            EvidenceObligation(
                id=obligation_id,
                description=description,
                required=bool(raw.get("required")),
                depends_on=valid_dependencies,
                anchor_refs=tuple(
                    item for item in _strings(raw.get("anchor_refs"), limit=12) if known_anchors is None or item in known_anchors
                ),
                evidence_role=(
                    EvidenceRole.ANY
                    if evidence_source != EvidenceSource.REPOSITORY
                    else _optional_enum(raw.get("evidence_role"), EvidenceRole, EvidenceRole.IMPLEMENTATION)
                ),
                evidence_source=evidence_source,
                evidence_boundary=evidence_boundary,
                stage_ids=_strings(raw.get("stage_ids"), limit=16),
                requires_repository_handoff=(
                    evidence_source == EvidenceSource.REPOSITORY
                    and bool(valid_dependencies)
                    and bool(raw.get("requires_repository_handoff"))
                ),
            )
        )
    if obligations and not any(item.required for item in obligations):
        raise ValueError("Request analysis returned no required evidence obligation.")
    _validate_acyclic_obligations(obligations)
    return tuple(obligations)


def _validate_acyclic_obligations(obligations: Sequence[EvidenceObligation]) -> None:
    dependencies = {item.id: item.depends_on for item in obligations}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(obligation_id: str) -> None:
        if obligation_id in visiting:
            raise ValueError("Request analysis returned cyclic evidence obligations.")
        if obligation_id in visited:
            return
        visiting.add(obligation_id)
        for dependency_id in dependencies.get(obligation_id, ()):
            visit(dependency_id)
        visiting.remove(obligation_id)
        visited.add(obligation_id)

    for obligation_id in dependencies:
        visit(obligation_id)


def _optional_enum(value: object, enum_type: type[Enum], default: Any) -> Any:
    candidate = str(value or "").strip()
    for item in enum_type:
        if item.value == candidate:
            return item
    return default


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
