from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, Sequence

from core.models import EvidenceItem, OrchestratorDecision
from core.stages import ResponseStage
from core.violations import PolicyViolation


class ResponseTemplate(str, Enum):
    """Named response shapes selected by policy and enforced by builders."""

    #: Evidence-grounded explanation of code or project behavior.
    EXPLANATION = "explanation"
    #: Follow-up question intended to promote user reasoning.
    REASONING_QUESTION = "reasoning_question"
    #: Bounded hint that comes after explanation and reasoning question stages.
    HINT = "hint"
    #: Boundary-setting response that ends with a knowledge-check question.
    BOUNDARY_CHECK_QUESTION = "boundary_check_question"
    #: Boundary-setting response for direct solution requests or other violations.
    VIOLATION_REDIRECT = "violation_redirect"


@dataclass(frozen=True)
class ResponseContract:
    """Structural requirements a response builder must satisfy."""

    #: Stage the response is being built for.
    stage: ResponseStage
    #: Template selected by policy.
    template: ResponseTemplate
    #: Logical sections expected in the final response payload.
    required_sections: tuple[str, ...]
    #: Whether response content must include project evidence references.
    must_include_evidence: bool = True


@dataclass(frozen=True)
class ResponsePayload:
    """Final structured response object before rendering to a user."""

    #: Stage that produced the response.
    stage: ResponseStage
    #: Template used to construct response content.
    template: ResponseTemplate
    #: User-facing response body.
    content: str
    #: Stable references to evidence items used in the response.
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    #: Policy violations surfaced by this response, if any.
    violations: tuple[PolicyViolation, ...] = field(default_factory=tuple)


class ResponseBuilder(Protocol):
    """Interface for converting decisions and evidence into response payloads."""

    def build(self, decision: OrchestratorDecision, evidence: Sequence[EvidenceItem]) -> ResponsePayload:
        """Build a structured response that satisfies the policy decision."""

        ...


def contract_for_decision(decision: OrchestratorDecision) -> ResponseContract:
    """Derive the response structure that a decision requires."""

    if decision.response_template_id == ResponseTemplate.BOUNDARY_CHECK_QUESTION.value:
        return ResponseContract(
            stage=decision.current_stage,
            template=ResponseTemplate.BOUNDARY_CHECK_QUESTION,
            required_sections=("boundary", "knowledge_check_question"),
            must_include_evidence=False,
        )

    if decision.violations and decision.response_template_id == ResponseTemplate.VIOLATION_REDIRECT.value:
        return ResponseContract(
            stage=decision.current_stage,
            template=ResponseTemplate.VIOLATION_REDIRECT,
            required_sections=("boundary", "scaffolded_next_step"),
            must_include_evidence=False,
        )

    template = ResponseTemplate(decision.response_template_id)
    # Required sections are intentionally high-level until real rendering exists.
    sections_by_template = {
        ResponseTemplate.EXPLANATION: ("summary", "evidence", "reasoning_path", "knowledge_check_question"),
        ResponseTemplate.REASONING_QUESTION: ("question", "why_this_matters"),
        ResponseTemplate.HINT: ("hint", "evidence"),
    }
    return ResponseContract(
        stage=decision.current_stage,
        template=template,
        required_sections=sections_by_template[template],
        must_include_evidence=template != ResponseTemplate.REASONING_QUESTION,
    )
