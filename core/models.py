from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from core.source_policy import SourceCategory
from core.violations import PolicyViolation
from services.intent.models import IntentContext


class AssistanceRequestType(str, Enum):
    """Coarse request shape used only by the teaching-policy gate."""

    UNDERSTAND_CODE = "understand_code"
    DIRECT_SOLUTION_REQUEST = "direct_solution_request"
    FOLLOW_UP = "follow_up"
    UNKNOWN = "unknown"


class TurnType(str, Enum):
    """Allowed top-level turn types owned by the control layer."""

    GUIDED_EXPLANATION = "guided_explanation"
    ANSWER_EVALUATION = "answer_evaluation"
    REPAIR = "repair"
    DEEPEN = "deepen"
    COMPLETION = "completion"
    BOUNDARY = "boundary"


@dataclass(frozen=True)
class ConversationMessage:
    """One message already exchanged in a conversation."""

    role: str
    content: str
    turn_type: TurnType | None = None


@dataclass(frozen=True)
class EvidenceItem:
    """One retrieved project artifact snippet used to ground a response."""

    source_category: SourceCategory
    source_id: str
    snippet: str
    rank: int | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_category": self.source_category.value,
            "source_id": self.source_id,
            "snippet": self.snippet,
            "rank": self.rank,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ConversationState:
    """Full policy-facing state for deciding the next orchestration action."""

    conversation_id: str
    user_input: str
    assistance_request: AssistanceRequestType = AssistanceRequestType.UNKNOWN
    history: tuple[ConversationMessage, ...] = field(default_factory=tuple)
    evidence: tuple[EvidenceItem, ...] = field(default_factory=tuple)
    intent_context: IntentContext | None = None


@dataclass(frozen=True)
class PolicyResult:
    """Bounded output of the policy gate."""

    allowed: bool
    assistance_request: AssistanceRequestType
    retrieval_required: bool
    allowed_sources: tuple[SourceCategory, ...]
    turn_type: TurnType
    reason: str
    source_policy_name: str
    violations: tuple[PolicyViolation, ...] = field(default_factory=tuple)
    boundary_choices: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "assistance_request": self.assistance_request.value,
            "retrieval_required": self.retrieval_required,
            "allowed_sources": [source.value for source in self.allowed_sources],
            "turn_type": self.turn_type.value,
            "reason": self.reason,
            "source_policy_name": self.source_policy_name,
            "violations": [_violation_to_dict(violation) for violation in self.violations],
            "boundary_choices": list(self.boundary_choices),
        }


@dataclass(frozen=True)
class RetrievalResult:
    """Bounded output of the retrieval stage."""

    evidence: tuple[EvidenceItem, ...]
    coverage_status: str
    sufficient: bool
    retrieval_summary: Mapping[str, Any] = field(default_factory=dict)
    failures_or_fallbacks: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence": [item.to_dict() for item in self.evidence],
            "coverage_status": self.coverage_status,
            "sufficient": self.sufficient,
            "retrieval_summary": _primitive_mapping(self.retrieval_summary),
            "failures_or_fallbacks": list(self.failures_or_fallbacks),
        }


@dataclass(frozen=True)
class ResponsePlan:
    """Response-planning output derived from policy and retrieval results."""

    turn_type: TurnType
    required_sections: tuple[str, ...]
    must_include_evidence: bool
    boundary_message_required: bool = False
    boundary_choices: tuple[str, ...] = field(default_factory=tuple)
    notes: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn_type": self.turn_type.value,
            "required_sections": list(self.required_sections),
            "must_include_evidence": self.must_include_evidence,
            "boundary_message_required": self.boundary_message_required,
            "boundary_choices": list(self.boundary_choices),
            "notes": _primitive_mapping(self.notes),
        }


@dataclass(frozen=True)
class ResponsePayload:
    """Optional rendered response payload produced after response planning."""

    turn_type: TurnType
    content: str
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    violations: tuple[PolicyViolation, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn_type": self.turn_type.value,
            "content": self.content,
            "evidence_refs": list(self.evidence_refs),
            "violations": [_violation_to_dict(violation) for violation in self.violations],
            "metadata": _primitive_mapping(self.metadata),
        }


@dataclass(frozen=True)
class OrchestrationResult:
    """Single source of truth for one orchestration run."""

    conversation_id: str
    policy_result: PolicyResult
    retrieval_result: RetrievalResult | None
    response_plan: ResponsePlan
    response_payload: ResponsePayload | None
    run_trace_summary: Mapping[str, Any] = field(default_factory=dict)

    @property
    def turn_type(self) -> TurnType:
        return self.policy_result.turn_type

    @property
    def allowed_sources(self) -> tuple[SourceCategory, ...]:
        return self.policy_result.allowed_sources

    @property
    def evidence(self) -> tuple[EvidenceItem, ...]:
        if self.retrieval_result is not None:
            return self.retrieval_result.evidence
        return ()

    @property
    def violations(self) -> tuple[PolicyViolation, ...]:
        return self.policy_result.violations

    def to_dict(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "policy_result": self.policy_result.to_dict(),
            "retrieval_result": self.retrieval_result.to_dict() if self.retrieval_result is not None else None,
            "response_plan": self.response_plan.to_dict(),
            "response_payload": self.response_payload.to_dict() if self.response_payload is not None else None,
            "run_trace_summary": _primitive_mapping(self.run_trace_summary),
        }


def _violation_to_dict(violation: PolicyViolation) -> dict[str, Any]:
    return {
        "violation_type": violation.violation_type.value,
        "message": violation.message,
        "metadata": dict(violation.metadata),
    }


def _primitive_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, item in value.items():
        if isinstance(item, Enum):
            output[str(key)] = item.value
        elif isinstance(item, Mapping):
            output[str(key)] = _primitive_mapping(item)
        elif isinstance(item, tuple):
            output[str(key)] = [
                nested.value if isinstance(nested, Enum) else nested
                for nested in item
            ]
        elif isinstance(item, list):
            output[str(key)] = [
                nested.value if isinstance(nested, Enum) else nested
                for nested in item
            ]
        else:
            output[str(key)] = item
    return output
