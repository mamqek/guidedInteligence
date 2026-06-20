from __future__ import annotations

from core.models import ConversationState, PolicyResult, TurnType, UserIntent
from core.source_policy import DEFAULT_SOURCE_POLICY, SourcePolicy, is_allowed_source_category
from core.violations import PolicyViolation, PolicyViolationType

class PolicyStage:
    """Deterministic policy gate for guided explanation turns."""

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
                intent=intent,
                violations=violations,
                reason="Direct solution request detected; offer a guided-explanation path instead.",
            )

        if violations:
            return self._boundary_result(
                intent=intent,
                violations=violations,
                reason="The request or supplied context violates the active source policy.",
            )

        return PolicyResult(
            allowed=True,
            intent=intent,
            retrieval_required=len(state.evidence) == 0,
            allowed_sources=self.source_policy.allowed_categories,
            turn_type=TurnType.GUIDED_EXPLANATION,
            reason="Guided explanation turn selected.",
            source_policy_name=self.source_policy.policy_name,
        )

    def _boundary_result(
        self,
        *,
        intent: UserIntent,
        violations: tuple[PolicyViolation, ...],
        reason: str,
    ) -> PolicyResult:
        return PolicyResult(
            allowed=False,
            intent=intent,
            retrieval_required=False,
            allowed_sources=self.source_policy.allowed_categories,
            turn_type=TurnType.BOUNDARY,
            reason=reason,
            source_policy_name=self.source_policy.policy_name,
            violations=violations,
            boundary_choices=("ask_for_guided_explanation", "revise_request"),
        )

    def _classify_intent(self, user_input: str) -> UserIntent:
        normalized_input = user_input.lower()
        if any(marker in normalized_input for marker in self._DIRECT_SOLUTION_MARKERS):
            return UserIntent.DIRECT_SOLUTION_REQUEST
        if "follow up" in normalized_input or "more detail" in normalized_input:
            return UserIntent.FOLLOW_UP
        return UserIntent.UNDERSTAND_CODE

    def _collect_state_violations(self, state: ConversationState) -> tuple[PolicyViolation, ...]:
        violations: list[PolicyViolation] = []

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
