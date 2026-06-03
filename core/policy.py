from __future__ import annotations

from core.models import ConversationState, PolicyResult, ResponseMode, UserIntent
from core.source_policy import DEFAULT_SOURCE_POLICY, SourcePolicy, is_allowed_source_category
from core.stages import ResponseStage, next_stage
from core.transitions import can_transition
from core.violations import PolicyViolation, PolicyViolationType

class PolicyStage:
    """Deterministic v1 policy stage."""

    _DIRECT_SOLUTION_MARKERS = (
        "give me the answer",
        "just solve",
        "write the solution",
        "do it for me",
        "fix it for me",
        "complete the task",
    )

    def __init__(self, source_policy: SourcePolicy = DEFAULT_SOURCE_POLICY) -> None:
        self.source_policy = source_policy

    def decide(self, state: ConversationState) -> PolicyResult:
        intent = state.intent
        if intent == UserIntent.UNKNOWN:
            intent = self._classify_intent(state.user_input)

        violations = self._collect_state_violations(state)

        if intent == UserIntent.DIRECT_SOLUTION_REQUEST:
            violations = violations + (
                PolicyViolation(
                    violation_type=PolicyViolationType.DIRECT_SOLUTION_REQUEST,
                    message="Direct solution requests violate the currently active scaffolded stage.",
                ),
            )
            return self._boundary_result(
                active_stage=self._active_stage_for_violation(state, violations),
                intent=intent,
                violations=violations,
                reason="Direct solution request detected; keep the current stage and offer stage choices.",
            )

        if any(violation.violation_type == PolicyViolationType.STAGE_SKIPPING for violation in violations):
            return self._boundary_result(
                active_stage=self._active_stage_for_violation(state, violations),
                intent=intent,
                violations=violations,
                reason="Stage skipping detected; keep the last valid stage and offer stage choices.",
            )

        return PolicyResult(
            allowed=len(violations) == 0,
            active_stage=state.current_stage,
            next_stage=next_stage(state.current_stage),
            intent=intent,
            retrieval_required=len(state.evidence) == 0,
            allowed_sources=self.source_policy.allowed_categories,
            response_mode=self._mode_for_stage(state.current_stage),
            reason="V1 scaffolded assistance path selected.",
            source_policy_name=self.source_policy.policy_name,
            violations=violations,
        )

    def _boundary_result(
        self,
        *,
        active_stage: ResponseStage,
        intent: UserIntent,
        violations: tuple[PolicyViolation, ...],
        reason: str,
    ) -> PolicyResult:
        return PolicyResult(
            allowed=False,
            active_stage=active_stage,
            next_stage=active_stage,
            intent=intent,
            retrieval_required=False,
            allowed_sources=self.source_policy.allowed_categories,
            response_mode=ResponseMode.BOUNDARY,
            reason=reason,
            source_policy_name=self.source_policy.policy_name,
            violations=violations,
            boundary_choices=("follow_current_stage", "return_to_explanation"),
        )

    def _active_stage_for_violation(
        self,
        state: ConversationState,
        violations: tuple[PolicyViolation, ...],
    ) -> ResponseStage:
        if any(violation.violation_type == PolicyViolationType.STAGE_SKIPPING for violation in violations):
            return state.stage_history[-1]
        return state.current_stage

    def _classify_intent(self, user_input: str) -> UserIntent:
        normalized_input = user_input.lower()
        if any(marker in normalized_input for marker in self._DIRECT_SOLUTION_MARKERS):
            return UserIntent.DIRECT_SOLUTION_REQUEST
        if "follow up" in normalized_input or "more detail" in normalized_input:
            return UserIntent.FOLLOW_UP
        return UserIntent.UNDERSTAND_CODE

    def _collect_state_violations(self, state: ConversationState) -> tuple[PolicyViolation, ...]:
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
            if not is_allowed_source_category(evidence_item.source_category, self.source_policy):
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

    def _mode_for_stage(self, stage: ResponseStage) -> ResponseMode:
        if stage == ResponseStage.EXPLAIN:
            return ResponseMode.EXPLANATION
        if stage == ResponseStage.ASK:
            return ResponseMode.REASONING_QUESTION
        if stage == ResponseStage.HINT:
            return ResponseMode.HINT
        raise ValueError(f"Unsupported response stage: {stage.value}")
