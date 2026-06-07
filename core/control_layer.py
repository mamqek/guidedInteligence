from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from core.logging_schema import LogEvent, LogEventType
from core.models import (
    ConversationState,
    OrchestrationResult,
    PolicyResult,
    ResponsePlan,
    ResponsePayload,
    ResponseMode,
    RetrievalResult,
)
from core.policy import PolicyStage
from core.response_builder import render_response
from services.logging.store import JsonlLogger
from services.retrieval.workspace import WorkspaceRetrievalStage


@dataclass(frozen=True)
class ControlLayer:
    """Top-level orchestration entrypoint."""

    policy_stage: PolicyStage
    retrieval_stage: WorkspaceRetrievalStage
    logger: JsonlLogger | None = None

    def run(self, state: ConversationState) -> OrchestrationResult:
        self._record(LogEventType.RUN_STARTED, state.conversation_id, {"current_stage": state.current_stage.value})
        policy_result = self.policy_stage.decide(state)
        self._record(LogEventType.STAGE_DECISION, state.conversation_id, policy_result.to_dict())

        if policy_result.violations:
            self._record(
                LogEventType.POLICY_VIOLATION,
                state.conversation_id,
                {"violations": [violation.violation_type.value for violation in policy_result.violations]},
            )

        retrieval_result: RetrievalResult | None = None
        if policy_result.allowed:
            if policy_result.retrieval_required:
                self._record(
                    LogEventType.RETRIEVAL_PLAN,
                    state.conversation_id,
                    {
                        "action": "invoke",
                        "allowed_sources": [source.value for source in policy_result.allowed_sources],
                    },
                )
                retrieval_result = self.retrieval_stage.retrieve(state, policy_result)
            else:
                self._record(LogEventType.RETRIEVAL_PLAN, state.conversation_id, {"action": "skip_existing_evidence"})
                retrieval_result = RetrievalResult(
                    evidence=tuple(state.evidence),
                    coverage_status="state_evidence" if state.evidence else "missing",
                    sufficient=bool(state.evidence),
                    retrieval_summary={"source": "conversation_state", "evidence_count": len(state.evidence)},
                )
            self._record(
                LogEventType.EVIDENCE_SELECTED,
                state.conversation_id,
                {
                    "coverage_status": retrieval_result.coverage_status,
                    "sufficient": retrieval_result.sufficient,
                    "evidence_count": len(retrieval_result.evidence),
                },
            )
        else:
            self._record(LogEventType.RETRIEVAL_PLAN, state.conversation_id, {"action": "blocked"})

        response_plan = _build_response_plan(policy_result, retrieval_result)
        self._record(LogEventType.RESPONSE_PLAN, state.conversation_id, response_plan.to_dict())

        self._record(
            LogEventType.PROMPT_PAYLOAD,
            state.conversation_id,
            {
                "response_mode": response_plan.mode.value,
                "required_sections": list(response_plan.required_sections),
                "must_include_evidence": response_plan.must_include_evidence,
            },
        )
        response_payload = _render_response(policy_result, retrieval_result, response_plan)
        self._record(LogEventType.RESPONSE_PAYLOAD, state.conversation_id, response_payload.to_dict())

        result = OrchestrationResult(
            conversation_id=state.conversation_id,
            policy_result=policy_result,
            retrieval_result=retrieval_result,
            response_plan=response_plan,
            response_payload=response_payload,
            run_trace_summary={
                "allowed": policy_result.allowed,
                "response_mode": policy_result.response_mode.value,
                "retrieval_invoked": bool(policy_result.allowed and policy_result.retrieval_required),
                "coverage_status": retrieval_result.coverage_status if retrieval_result is not None else "not_run",
                "violation_count": len(policy_result.violations),
            },
        )
        self._record(LogEventType.RUN_COMPLETED, state.conversation_id, result.run_trace_summary)
        return result

    def _record(
        self,
        event_type: LogEventType,
        conversation_id: str,
        payload: Mapping[str, object],
    ) -> None:
        if self.logger is None:
            return
        self.logger.record(LogEvent(event_type=event_type, conversation_id=conversation_id, payload=dict(payload)))


def _build_response_plan(
    policy_result: PolicyResult,
    retrieval_result: RetrievalResult | None,
) -> ResponsePlan:
    if policy_result.response_mode == ResponseMode.BOUNDARY:
        return ResponsePlan(
            mode=ResponseMode.BOUNDARY,
            stage=policy_result.active_stage,
            required_sections=("boundary", "expected_current_stage", "violation_explanation", "choices"),
            must_include_evidence=False,
            boundary_message_required=True,
            boundary_choices=policy_result.boundary_choices,
            notes={"reason": policy_result.reason},
        )

    sections_by_mode = {
        ResponseMode.EXPLANATION: (
            "summary",
            "evidence",
            "reasoning_path",
            "confirmed_from_evidence",
            "hypotheses_to_investigate",
            "knowledge_check_question",
        ),
        ResponseMode.REASONING_QUESTION: ("question", "why_this_matters"),
        ResponseMode.HINT: ("hint", "evidence"),
    }
    must_include_evidence = policy_result.response_mode != ResponseMode.REASONING_QUESTION
    notes = {
        "coverage_status": retrieval_result.coverage_status if retrieval_result is not None else "not_run",
        "retrieval_sufficient": retrieval_result.sufficient if retrieval_result is not None else False,
    }
    return ResponsePlan(
        mode=policy_result.response_mode,
        stage=policy_result.active_stage,
        required_sections=sections_by_mode[policy_result.response_mode],
        must_include_evidence=must_include_evidence,
        notes=notes,
    )


def _render_response(
    policy_result: PolicyResult,
    retrieval_result: RetrievalResult | None,
    response_plan: ResponsePlan,
) -> ResponsePayload:
    return render_response(policy_result, retrieval_result, response_plan)
