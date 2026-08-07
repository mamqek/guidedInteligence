from __future__ import annotations

from core.models import AssistanceRequestType, ConversationState, PolicyResult, TurnType
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
        assistance_request = state.assistance_request
        if assistance_request == AssistanceRequestType.UNKNOWN:
            assistance_request = self._classify_assistance_request(state.user_input)

        violations = self._collect_state_violations(state)

        if assistance_request == AssistanceRequestType.DIRECT_SOLUTION_REQUEST:
            violations = violations + (
                PolicyViolation(
                    violation_type=PolicyViolationType.DIRECT_SOLUTION_REQUEST,
                    message="Direct solution requests violate the currently active scaffolded stage.",
                ),
            )
            return self._boundary_result(
                assistance_request=assistance_request,
                violations=violations,
                reason="Direct solution request detected; offer a guided-explanation path instead.",
            )

        if violations:
            return self._boundary_result(
                assistance_request=assistance_request,
                violations=violations,
                reason="The request or supplied context violates the active source policy.",
            )

        return PolicyResult(
            allowed=True,
            assistance_request=assistance_request,
            retrieval_required=len(state.evidence) == 0,
            allowed_sources=self.source_policy.allowed_categories,
            turn_type=TurnType.GUIDED_EXPLANATION,
            reason="Guided explanation turn selected.",
            source_policy_name=self.source_policy.policy_name,
        )

    def _boundary_result(
        self,
        *,
        assistance_request: AssistanceRequestType,
        violations: tuple[PolicyViolation, ...],
        reason: str,
    ) -> PolicyResult:
        return PolicyResult(
            allowed=False,
            assistance_request=assistance_request,
            retrieval_required=False,
            allowed_sources=self.source_policy.allowed_categories,
            turn_type=TurnType.BOUNDARY,
            reason=reason,
            source_policy_name=self.source_policy.policy_name,
            violations=violations,
            boundary_choices=("ask_for_guided_explanation", "revise_request"),
        )

    def _classify_assistance_request(self, user_input: str) -> AssistanceRequestType:
        normalized_input = user_input.lower()
        if any(marker in normalized_input for marker in self._DIRECT_SOLUTION_MARKERS):
            return AssistanceRequestType.DIRECT_SOLUTION_REQUEST
        if "follow up" in normalized_input or "more detail" in normalized_input:
            return AssistanceRequestType.FOLLOW_UP
        return AssistanceRequestType.UNDERSTAND_CODE

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
