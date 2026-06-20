from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from core.logging_schema import LogEvent, LogEventType
from core.models import (
    ConversationState,
    OrchestrationResult,
    PolicyResult,
    ResponsePlan,
    ResponsePayload,
    TurnType,
    RetrievalResult,
)
from core.policy import PolicyStage
from core.response_builder import render_response
from services.logging.store import JsonlLogger
from services.retrieval.workspace import WorkspaceRetrievalStage
from services.response_generation.explanation import prompt_template_id


@dataclass(frozen=True)
class ControlLayer:
    """Top-level orchestration entrypoint."""

    policy_stage: PolicyStage
    retrieval_stage: WorkspaceRetrievalStage
    logger: JsonlLogger | None = None
    response_llm_config: Any | None = None

    def run(self, state: ConversationState) -> OrchestrationResult:
        self._record(LogEventType.RUN_STARTED, state.conversation_id, {"turn_request": state.user_input})
        policy_result = self.policy_stage.decide(state)
        self._record(LogEventType.TURN_DECISION, state.conversation_id, policy_result.to_dict())

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
                "turn_type": response_plan.turn_type.value,
                "required_sections": list(response_plan.required_sections),
                "must_include_evidence": response_plan.must_include_evidence,
                "notes": dict(response_plan.notes),
            },
        )
        resolved_response_llm_config = self.response_llm_config
        if resolved_response_llm_config is None:
            resolved_response_llm_config = getattr(getattr(self.retrieval_stage, "config", None), "llm_config", None)
        response_payload = _render_response(
            policy_result,
            retrieval_result,
            response_plan,
            state=state,
            llm_config=resolved_response_llm_config,
            record_event=lambda event_type, payload: self._record(event_type, state.conversation_id, payload),
        )
        self._record(LogEventType.RESPONSE_PAYLOAD, state.conversation_id, response_payload.to_dict())

        result = OrchestrationResult(
            conversation_id=state.conversation_id,
            policy_result=policy_result,
            retrieval_result=retrieval_result,
            response_plan=response_plan,
            response_payload=response_payload,
            run_trace_summary={
                "allowed": policy_result.allowed,
                "turn_type": policy_result.turn_type.value,
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
    if policy_result.turn_type == TurnType.BOUNDARY:
        return ResponsePlan(
            turn_type=TurnType.BOUNDARY,
            required_sections=("boundary", "violation_explanation", "choices"),
            must_include_evidence=False,
            boundary_message_required=True,
            boundary_choices=policy_result.boundary_choices,
            notes={"reason": policy_result.reason},
        )

    notes = {
        "coverage_status": retrieval_result.coverage_status if retrieval_result is not None else "not_run",
        "retrieval_sufficient": retrieval_result.sufficient if retrieval_result is not None else False,
        "prompt_template_id": prompt_template_id(),
    }
    return ResponsePlan(
        turn_type=policy_result.turn_type,
        required_sections=("generated_explanation", "understanding_checks"),
        must_include_evidence=True,
        notes=notes,
    )


def _render_response(
    policy_result: PolicyResult,
    retrieval_result: RetrievalResult | None,
    response_plan: ResponsePlan,
    *,
    state: ConversationState,
    llm_config: Any | None,
    record_event,
) -> ResponsePayload:
    return render_response(
        policy_result,
        retrieval_result,
        response_plan,
        state=state,
        llm_config=llm_config,
        log_event=record_event,
    )
