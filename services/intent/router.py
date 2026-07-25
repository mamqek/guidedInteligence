from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.models import RetrievalResult
from services.intent.models import AssistanceMode, ExpectedOutput, ResponseOperation, TurnRelation, UserGoal
from services.intent.normalizer import NormalizedIntent

ROUTER_MODE_OFF = "off"
ASSISTANCE_MODE_ROUTER_OFF = "off"
ASSISTANCE_MODE_ROUTER_SHADOW = "shadow"
ASSISTANCE_MODE_ROUTER_ACTIVE = "active"
SUPPORTED_ASSISTANCE_ROUTER_MODES = (
    ASSISTANCE_MODE_ROUTER_OFF,
    ASSISTANCE_MODE_ROUTER_SHADOW,
    ASSISTANCE_MODE_ROUTER_ACTIVE,
)


@dataclass(frozen=True)
class EvidenceComplexity:
    evidence_count: int
    responsibility_count: int
    artifact_count: int
    complexity: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_count": self.evidence_count,
            "responsibility_count": self.responsibility_count,
            "artifact_count": self.artifact_count,
            "complexity": self.complexity,
        }


@dataclass(frozen=True)
class AssistanceModeDecision:
    status: str
    mode: str
    configured_assistance_mode: str
    recommended_assistance_mode: str
    effective_assistance_mode: str
    would_change_mode: bool
    applied: bool
    conflict: bool
    decision_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "mode": self.mode,
            "configured_assistance_mode": self.configured_assistance_mode,
            "recommended_assistance_mode": self.recommended_assistance_mode,
            "effective_assistance_mode": self.effective_assistance_mode,
            "would_change_mode": self.would_change_mode,
            "applied": self.applied,
            "conflict": self.conflict,
            "decision_reasons": list(self.decision_reasons),
        }


def route_assistance_mode_shadow(
    *,
    normalized_intent: NormalizedIntent,
    configured_assistance_mode: AssistanceMode,
    mode: str,
    retrieval_result: RetrievalResult | None = None,
    intent_agreement: str | None = None,
) -> AssistanceModeDecision:
    recommended = normalized_intent.classification.recommended_assistance_mode
    reasons: list[str] = []
    conflict = False
    if mode == ASSISTANCE_MODE_ROUTER_OFF:
        reasons.append("assistance_router_disabled")
        return AssistanceModeDecision(
            status="disabled",
            mode=mode,
            configured_assistance_mode=configured_assistance_mode.value,
            recommended_assistance_mode=recommended.value,
            effective_assistance_mode=configured_assistance_mode.value,
            would_change_mode=False,
            applied=False,
            conflict=False,
            decision_reasons=tuple(reasons),
        )
    if configured_assistance_mode != recommended:
        conflict = True
        reasons.append("classifier_recommendation_differs_from_configured_mode")
    intent = normalized_intent.classification
    if intent.primary_expected_output == ExpectedOutput.PATCH and configured_assistance_mode == AssistanceMode.TEACH:
        conflict = True
        reasons.append("patch_primary_output_in_teach_mode")
    if intent.response_operation == ResponseOperation.EXPLAIN and configured_assistance_mode == AssistanceMode.WORK:
        conflict = True
        reasons.append("explanation_operation_in_work_mode")
    if intent.turn_relation == TurnRelation.ANSWER_TO_CHECK and configured_assistance_mode != AssistanceMode.EVALUATION:
        conflict = True
        reasons.append("answer_to_check_outside_evaluation_mode")
    if not reasons:
        reasons.append("configured_mode_matches_intent")
    effective = configured_assistance_mode
    applied = False
    if mode == ASSISTANCE_MODE_ROUTER_ACTIVE:
        active_allowed, active_block_reasons = _active_response_context_allows(
            retrieval_result=retrieval_result,
            intent_agreement=intent_agreement,
        )
        if active_allowed:
            effective, active_reasons = _active_assistance_mode(
                normalized_intent=normalized_intent,
                configured_assistance_mode=configured_assistance_mode,
                recommended_assistance_mode=recommended,
            )
        else:
            active_reasons = active_block_reasons
        reasons.extend(active_reasons)
        applied = effective != configured_assistance_mode
    return AssistanceModeDecision(
        status="active" if mode == ASSISTANCE_MODE_ROUTER_ACTIVE else "shadow",
        mode=mode,
        configured_assistance_mode=configured_assistance_mode.value,
        recommended_assistance_mode=recommended.value,
        effective_assistance_mode=effective.value,
        would_change_mode=configured_assistance_mode != recommended,
        applied=applied,
        conflict=conflict,
        decision_reasons=tuple(reasons),
    )


def _active_response_context_allows(
    *,
    retrieval_result: RetrievalResult | None,
    intent_agreement: str | None,
) -> tuple[bool, tuple[str, ...]]:
    reasons: list[str] = []
    if retrieval_result is None or not retrieval_result.evidence:
        reasons.append("active_blocked_missing_evidence")
    if str(intent_agreement or "").strip().lower() == "conflicting":
        reasons.append("active_blocked_conflicting_intent_agreement")
    return not reasons, tuple(reasons)


def _active_assistance_mode(
    *,
    normalized_intent: NormalizedIntent,
    configured_assistance_mode: AssistanceMode,
    recommended_assistance_mode: AssistanceMode,
) -> tuple[AssistanceMode, tuple[str, ...]]:
    intent = normalized_intent.classification
    if (
        intent.turn_relation == TurnRelation.ANSWER_TO_CHECK
        or intent.primary_expected_output == ExpectedOutput.ANSWER_EVALUATION
    ):
        if configured_assistance_mode != AssistanceMode.EVALUATION:
            return AssistanceMode.EVALUATION, ("active_answer_check_uses_evaluation_mode",)
        return configured_assistance_mode, ("active_answer_check_already_evaluation_mode",)
    if (
        recommended_assistance_mode == AssistanceMode.TEACH
        and configured_assistance_mode in {AssistanceMode.WORK, AssistanceMode.HYBRID}
        and intent.response_operation == ResponseOperation.EXPLAIN
        and intent.primary_expected_output == ExpectedOutput.EXPLANATION
        and UserGoal.UNDERSTAND in intent.user_goals
    ):
        return AssistanceMode.TEACH, ("active_explanation_understand_uses_teach_mode",)
    return configured_assistance_mode, ("active_no_allowed_transition",)


def assess_evidence_complexity(retrieval_result: RetrievalResult | None) -> EvidenceComplexity:
    if retrieval_result is None:
        return EvidenceComplexity(evidence_count=0, responsibility_count=0, artifact_count=0, complexity="none")
    responsibilities: set[str] = set()
    artifacts: set[str] = set()
    for item in retrieval_result.evidence:
        role = str(item.metadata.get("coverage_area") or item.metadata.get("file_role") or "").strip()
        if role:
            responsibilities.add(role)
        path = str(item.metadata.get("path") or item.source_id).strip()
        if path:
            artifacts.add(path)
    evidence_count = len(retrieval_result.evidence)
    responsibility_count = len(responsibilities)
    artifact_count = len(artifacts)
    if evidence_count == 0:
        complexity = "none"
    elif evidence_count >= 3 and (responsibility_count >= 2 or artifact_count >= 2):
        complexity = "multi_concept"
    elif responsibility_count >= 3:
        complexity = "multi_concept"
    else:
        complexity = "single_concept"
    return EvidenceComplexity(
        evidence_count=evidence_count,
        responsibility_count=responsibility_count,
        artifact_count=artifact_count,
        complexity=complexity,
    )
