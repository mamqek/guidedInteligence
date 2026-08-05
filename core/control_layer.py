from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Callable, Mapping

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
from services.comprehension import retrieve_with_bounded_gap_pass
from services.intent import (
    IntentClassificationInput,
    NormalizedIntent,
    assess_intent_agreement,
    build_retrieval_hints,
    classify_intent,
    normalize_intent,
)
from services.logging.store import JsonlLogger
from services.retrieval.workspace import WorkspaceRetrievalStage
from services.response_generation.comprehension import prompt_template_id


EvidenceGraphBuilder = Callable[
    [RetrievalResult, ConversationState, Callable[[str, Mapping[str, Any]], None]],
    RetrievalResult,
]


@dataclass(frozen=True)
class ControlLayer:
    """Top-level orchestration entrypoint."""

    policy_stage: PolicyStage
    retrieval_stage: WorkspaceRetrievalStage
    logger: JsonlLogger | None = None
    response_llm_config: Any | None = None
    max_gap_retrieval_passes: int = 0
    intent_shadow_enabled: bool = False
    intent_llm_config: Any | None = None
    evidence_graph_builder: EvidenceGraphBuilder | None = None

    def run(self, state: ConversationState) -> OrchestrationResult:
        self._record(LogEventType.RUN_STARTED, state.conversation_id, {"turn_request": state.user_input})
        normalized_intent: NormalizedIntent | None = None
        retrieval_state = state
        if self.intent_shadow_enabled:
            normalized_intent = self._record_shadow_intent_classification(state)
            if normalized_intent is not None:
                retrieval_hints = build_retrieval_hints(normalized_intent)
                retrieval_state = replace(state, retrieval_hints=retrieval_hints)
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
                        "retrieval_hints": retrieval_state.retrieval_hints.to_dict()
                        if retrieval_state.retrieval_hints is not None
                        else {},
                    },
                )
                retrieval_result = self.retrieval_stage.retrieve(retrieval_state, policy_result)
                if self.max_gap_retrieval_passes > 0:
                    retrieval_result = retrieve_with_bounded_gap_pass(
                        retrieval_stage=self.retrieval_stage,
                        state=retrieval_state,
                        policy_result=policy_result,
                        initial_result=retrieval_result,
                        max_gap_retrieval_passes=self.max_gap_retrieval_passes,
                    )
            else:
                self._record(LogEventType.RETRIEVAL_PLAN, state.conversation_id, {"action": "skip_existing_evidence"})
                retrieval_result = RetrievalResult(
                    evidence=tuple(state.evidence),
                    coverage_status="state_evidence" if state.evidence else "missing",
                    sufficient=bool(state.evidence),
                    retrieval_summary={"source": "conversation_state", "evidence_count": len(state.evidence)},
                )
            if self.evidence_graph_builder is not None:
                retrieval_result = self.evidence_graph_builder(
                    retrieval_result,
                    retrieval_state,
                    lambda event_type, payload: self._record(
                        LogEventType(event_type),
                        state.conversation_id,
                        payload,
                    ),
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
            if normalized_intent is not None:
                self._record(
                    LogEventType.INTENT_AGREEMENT,
                    state.conversation_id,
                    (
                        agreement := assess_intent_agreement(
                            classification=normalized_intent.classification,
                            retrieval_result=retrieval_result,
                            legacy_user_intent=policy_result.intent,
                        )
                    ).to_dict(),
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
            state=retrieval_state,
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

    def _record_shadow_intent_classification(self, state: ConversationState) -> NormalizedIntent | None:
        llm_config = self.intent_llm_config
        if llm_config is None:
            llm_config = self.response_llm_config
        if llm_config is None:
            llm_config = getattr(getattr(self.retrieval_stage, "config", None), "llm_config", None)
        classification_input = IntentClassificationInput(
            user_prompt=state.user_input,
            current_turn_type=state.history[-1].turn_type.value if state.history and state.history[-1].turn_type else None,
        )
        if llm_config is None:
            payload = {
                "status": "failed",
                "classification": None,
                "error": "Missing LLM config for shadow intent classification.",
                "fallback_used": False,
                "latency_ms": 0,
                "classifier_model": "",
                "classifier_prompt_version": "intent_classification_v1",
                "classifier_schema_version": "intent_classification_v1",
            }
            result = None
        else:
            result = classify_intent(classification_input, llm_config=llm_config)
            payload = result.to_dict()
        self._record(LogEventType.INTENT_CLASSIFICATION, state.conversation_id, payload)
        if result is None or result.classification is None:
            return None
        normalized = normalize_intent(
            result.classification,
            user_prompt=state.user_input,
            active_understanding_check=False,
        )
        self._record(LogEventType.INTENT_NORMALIZATION, state.conversation_id, normalized.to_dict())
        return normalized


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
