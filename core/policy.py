from __future__ import annotations

from typing import Protocol

from core.models import ConversationState, OrchestratorDecision, UserIntent
from core.response_contracts import ResponseTemplate
from core.source_policy import DEFAULT_ALLOWED_SOURCE_CATEGORIES, is_allowed_source_category
from core.stages import ResponseStage, next_stage
from core.transitions import can_transition
from core.violations import PolicyViolation, PolicyViolationType


class PolicyEngine(Protocol):
    """Main control surface for orchestration decisions.

    Runtime shells, harnesses, and future adapters should call this interface
    instead of embedding stage or source rules directly.
    """

    def decide(self, state: ConversationState) -> OrchestratorDecision:
        """Return the policy decision for the current conversation state."""

        ...


class V1PolicyEngine:
    """Small deterministic v1 policy engine for the frozen contract.

    This implementation is deliberately simple: it validates the explicit v1
    boundaries before real retrieval, model classification, or Open SWE are
    introduced.
    """

    # Temporary keyword heuristic for the direct-solution violation path.
    _DIRECT_SOLUTION_MARKERS = (
        "give me the answer",
        "just solve",
        "write the solution",
        "do it for me",
        "fix it for me",
        "complete the task",
    )

    def decide(self, state: ConversationState) -> OrchestratorDecision:
        """Choose the next response contract and policy status for a state."""

        intent = state.intent
        if intent == UserIntent.UNKNOWN:
            intent = self._classify_intent(state.user_input)

        violations = self._collect_state_violations(state)

        if intent == UserIntent.DIRECT_SOLUTION_REQUEST:
            violations = violations + (
                PolicyViolation(
                    violation_type=PolicyViolationType.DIRECT_SOLUTION_REQUEST,
                    message="Direct solution requests must be redirected into scaffolded assistance.",
                ),
            )
            return self._recovery_decision(
                intent=intent,
                violations=violations,
                reason="Direct solution request detected; recover through ASK-stage questioning.",
            )

        if any(violation.violation_type == PolicyViolationType.STAGE_SKIPPING for violation in violations):
            return self._recovery_decision(
                intent=intent,
                violations=violations,
                reason="Stage skipping detected; recover through ASK-stage questioning.",
            )

        # Non-violation path: proceed through explain -> ask -> hint.
        return OrchestratorDecision(
            allowed=len(violations) == 0,
            current_stage=state.current_stage,
            next_stage=next_stage(state.current_stage),
            intent=intent,
            retrieval_required=len(state.evidence) == 0,
            allowed_sources=DEFAULT_ALLOWED_SOURCE_CATEGORIES,
            response_template_id=self._template_for_stage(state.current_stage),
            reason="V1 scaffolded assistance path selected.",
            violations=violations,
        )

    def _recovery_decision(
        self,
        *,
        intent: UserIntent,
        violations: tuple[PolicyViolation, ...],
        reason: str,
    ) -> OrchestratorDecision:
        """Route shortcut violations into ASK-stage recovery behavior."""

        return OrchestratorDecision(
            allowed=False,
            current_stage=ResponseStage.ASK,
            next_stage=ResponseStage.HINT,
            intent=intent,
            retrieval_required=False,
            allowed_sources=DEFAULT_ALLOWED_SOURCE_CATEGORIES,
            response_template_id=ResponseTemplate.BOUNDARY_CHECK_QUESTION.value,
            reason=reason,
            violations=violations,
            metadata={"recovery_target_stage": ResponseStage.ASK.value},
        )

    def _classify_intent(self, user_input: str) -> UserIntent:
        """Classify intent with a small deterministic heuristic for v1."""

        normalized_input = user_input.lower()
        if any(marker in normalized_input for marker in self._DIRECT_SOLUTION_MARKERS):
            return UserIntent.DIRECT_SOLUTION_REQUEST
        if "follow up" in normalized_input or "more detail" in normalized_input:
            return UserIntent.FOLLOW_UP
        return UserIntent.UNDERSTAND_CODE

    def _collect_state_violations(self, state: ConversationState) -> tuple[PolicyViolation, ...]:
        """Find policy violations that are visible from current state alone."""

        violations: list[PolicyViolation] = []

        if state.stage_history:
            previous_stage = state.stage_history[-1]
            if not can_transition(previous_stage, state.current_stage):
                violations.append(
                    PolicyViolation(
                        violation_type=PolicyViolationType.STAGE_SKIPPING,
                        message="Current stage is not reachable from the previous stage.",
                        metadata={
                            "previous_stage": previous_stage.value,
                            "current_stage": state.current_stage.value,
                        },
                    )
                )

        for evidence_item in state.evidence:
            if not is_allowed_source_category(evidence_item.source_category):
                violations.append(
                    PolicyViolation(
                        violation_type=PolicyViolationType.UNSUPPORTED_SOURCE_USAGE,
                        message="Evidence item uses a source category outside the v1 source policy.",
                        metadata={
                            "source_category": evidence_item.source_category.value,
                            "source_id": evidence_item.source_id,
                        },
                    )
                )

        return tuple(violations)

    def _template_for_stage(self, stage: ResponseStage) -> str:
        """Map the allowed response stage to the response template ID."""

        if stage == ResponseStage.EXPLAIN:
            return ResponseTemplate.EXPLANATION.value
        if stage == ResponseStage.ASK:
            return ResponseTemplate.REASONING_QUESTION.value
        if stage == ResponseStage.HINT:
            return ResponseTemplate.HINT.value
        raise ValueError(f"Unsupported response stage: {stage.value}")
