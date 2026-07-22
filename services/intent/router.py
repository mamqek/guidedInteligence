from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.models import RetrievalResult
from services.intent.models import AssistanceMode, ExpectedOutput, ResponseOperation, TurnRelation, UserGoal
from services.intent.normalizer import NormalizedIntent

RESPONSE_PIPELINE_CURRENT = "current"
RESPONSE_PIPELINE_COMPREHENSION_PLAN = "comprehension_plan"
ROUTER_MODE_OFF = "off"
ROUTER_MODE_PIPELINE_SHADOW = "pipeline_shadow"
ROUTER_MODE_PIPELINE_ACTIVE = "pipeline_active"
SUPPORTED_ROUTER_MODES = (ROUTER_MODE_OFF, ROUTER_MODE_PIPELINE_SHADOW, ROUTER_MODE_PIPELINE_ACTIVE)
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
class PipelineRoutingDecision:
    status: str
    mode: str
    actual_response_pipeline: str
    effective_response_pipeline: str
    proposed_response_pipeline: str
    would_change_pipeline: bool
    applied: bool
    use_comprehension_plan: bool
    use_understanding_check: bool
    block_for_understanding_check: bool
    evidence_complexity: EvidenceComplexity
    routing_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "mode": self.mode,
            "actual_response_pipeline": self.actual_response_pipeline,
            "effective_response_pipeline": self.effective_response_pipeline,
            "proposed_response_pipeline": self.proposed_response_pipeline,
            "would_change_pipeline": self.would_change_pipeline,
            "applied": self.applied,
            "use_comprehension_plan": self.use_comprehension_plan,
            "use_understanding_check": self.use_understanding_check,
            "block_for_understanding_check": self.block_for_understanding_check,
            "evidence_complexity": self.evidence_complexity.to_dict(),
            "routing_reasons": list(self.routing_reasons),
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


def route_pipeline_shadow(
    *,
    normalized_intent: NormalizedIntent,
    retrieval_result: RetrievalResult | None,
    actual_response_pipeline: str,
    effective_assistance_mode: AssistanceMode,
    router_mode: str,
) -> PipelineRoutingDecision:
    evidence_complexity = assess_evidence_complexity(retrieval_result)
    if router_mode == ROUTER_MODE_OFF:
        return PipelineRoutingDecision(
            status="disabled",
            mode=router_mode,
            actual_response_pipeline=actual_response_pipeline,
            effective_response_pipeline=actual_response_pipeline,
            proposed_response_pipeline=actual_response_pipeline,
            would_change_pipeline=False,
            applied=False,
            use_comprehension_plan=actual_response_pipeline == RESPONSE_PIPELINE_COMPREHENSION_PLAN,
            use_understanding_check=False,
            block_for_understanding_check=False,
            evidence_complexity=evidence_complexity,
            routing_reasons=("router_disabled",),
        )

    intent = normalized_intent.classification
    reasons: list[str] = []
    use_comprehension_plan = False

    if not retrieval_result or not retrieval_result.evidence:
        reasons.append("no_retrieved_evidence")
    elif intent.primary_expected_output == ExpectedOutput.ANSWER_EVALUATION:
        use_comprehension_plan = True
        reasons.append("answer_evaluation_output")
    elif intent.turn_relation == TurnRelation.ANSWER_TO_CHECK:
        use_comprehension_plan = True
        reasons.append("answer_to_check_turn")
    elif intent.primary_expected_output == ExpectedOutput.PATCH and effective_assistance_mode == AssistanceMode.WORK:
        reasons.append("work_mode_patch_prefers_current_pipeline")
    elif intent.response_operation == ResponseOperation.PRODUCE and intent.primary_expected_output == ExpectedOutput.PATCH:
        reasons.append("patch_primary_output_prefers_current_pipeline")
    elif effective_assistance_mode in {AssistanceMode.TEACH, AssistanceMode.EVALUATION} and evidence_complexity.complexity == "multi_concept":
        use_comprehension_plan = True
        reasons.append("teaching_mode_multi_concept_evidence")
    elif UserGoal.UNDERSTAND in intent.user_goals and evidence_complexity.complexity == "multi_concept":
        use_comprehension_plan = True
        reasons.append("understand_goal_multi_concept_evidence")
    elif effective_assistance_mode == AssistanceMode.HYBRID and ExpectedOutput.EXPLANATION in intent.expected_outputs and evidence_complexity.responsibility_count >= 3:
        use_comprehension_plan = True
        reasons.append("hybrid_explanation_with_broad_responsibility_chain")
    else:
        reasons.append("single_concept_or_non_teaching_request")

    use_understanding_check = (
        effective_assistance_mode == AssistanceMode.EVALUATION
        or (effective_assistance_mode == AssistanceMode.TEACH and intent.response_operation == ResponseOperation.EXPLAIN)
        or intent.turn_relation == TurnRelation.ANSWER_TO_CHECK
    )
    block_for_understanding_check = effective_assistance_mode == AssistanceMode.EVALUATION
    proposed = RESPONSE_PIPELINE_COMPREHENSION_PLAN if use_comprehension_plan else RESPONSE_PIPELINE_CURRENT
    return PipelineRoutingDecision(
        status="shadow" if router_mode == ROUTER_MODE_PIPELINE_SHADOW else "active",
        mode=router_mode,
        actual_response_pipeline=actual_response_pipeline,
        effective_response_pipeline=_effective_pipeline(
            router_mode=router_mode,
            actual_response_pipeline=actual_response_pipeline,
            proposed_response_pipeline=proposed,
        ),
        proposed_response_pipeline=proposed,
        would_change_pipeline=proposed != actual_response_pipeline,
        applied=(
            router_mode == ROUTER_MODE_PIPELINE_ACTIVE
            and actual_response_pipeline == RESPONSE_PIPELINE_CURRENT
            and proposed == RESPONSE_PIPELINE_COMPREHENSION_PLAN
        ),
        use_comprehension_plan=use_comprehension_plan,
        use_understanding_check=use_understanding_check,
        block_for_understanding_check=block_for_understanding_check,
        evidence_complexity=evidence_complexity,
        routing_reasons=tuple(reasons),
    )


def _effective_pipeline(*, router_mode: str, actual_response_pipeline: str, proposed_response_pipeline: str) -> str:
    if (
        router_mode == ROUTER_MODE_PIPELINE_ACTIVE
        and actual_response_pipeline == RESPONSE_PIPELINE_CURRENT
        and proposed_response_pipeline == RESPONSE_PIPELINE_COMPREHENSION_PLAN
    ):
        return RESPONSE_PIPELINE_COMPREHENSION_PLAN
    return actual_response_pipeline


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
