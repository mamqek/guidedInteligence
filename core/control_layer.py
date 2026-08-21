from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
import re
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
from services.intent import (
    IntentClassificationInput,
    NormalizedIntent,
    build_intent_context,
    classify_intent,
    evaluate_intent_sufficiency,
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
    intent_enabled: bool = True
    intent_sufficiency_enabled: bool = False
    intent_llm_config: Any | None = None
    evidence_graph_builder: EvidenceGraphBuilder | None = None
    multi_intent_stage_order_neutralization_enabled: bool = False
    response_generation_enabled: bool = True

    def run(self, state: ConversationState) -> OrchestrationResult:
        self._record(LogEventType.RUN_STARTED, state.conversation_id, {"turn_request": state.user_input})
        retrieval_state = state
        normalized_intent: NormalizedIntent | None = None
        if self.intent_enabled:
            normalized_intent = self._classify_intent(state)
            retrieval_state = replace(state, intent_context=build_intent_context(normalized_intent.classification))
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
                        "intent_context": retrieval_state.intent_context.to_dict()
                        if retrieval_state.intent_context is not None
                        else {},
                    },
                )
                retrieval_result = self.retrieval_stage.retrieve(retrieval_state, policy_result)
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
            if self.intent_sufficiency_enabled and normalized_intent is not None:
                sufficiency_config = self.intent_llm_config or self.response_llm_config
                if sufficiency_config is None:
                    sufficiency_observation: Mapping[str, Any] = {
                        "status": "error",
                        "error": "Intent sufficiency observation requires a configured LLM.",
                    }
                else:
                    try:
                        observations = evaluate_intent_sufficiency(
                            intents=normalized_intent.classification.intents,
                            evidence=retrieval_result.evidence,
                            llm_config=sufficiency_config,
                        )
                        sufficiency_observation = {
                            "status": "complete",
                            "results": [observation.to_dict() for observation in observations],
                        }
                    except Exception as exc:
                        sufficiency_observation = {"status": "error", "error": str(exc)}
                retrieval_result = replace(
                    retrieval_result,
                    retrieval_summary={**dict(retrieval_result.retrieval_summary), "intent_sufficiency": sufficiency_observation},
                )
                self._record(LogEventType.INTENT_SUFFICIENCY, state.conversation_id, sufficiency_observation)
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
        if self.response_generation_enabled:
            response_payload = _render_response(
                policy_result,
                retrieval_result,
                response_plan,
                state=retrieval_state,
                llm_config=resolved_response_llm_config,
                record_event=lambda event_type, payload: self._record(event_type, state.conversation_id, payload),
                neutralize_multi_intent_stage_order=self.multi_intent_stage_order_neutralization_enabled,
            )
        else:
            response_payload = ResponsePayload(
                turn_type=response_plan.turn_type,
                content="",
                evidence_refs=(),
                violations=policy_result.violations,
                metadata={
                    **dict(response_plan.notes),
                    "generator": "explicitly_skipped",
                },
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
                "intents": [intent.value for intent in normalized_intent.classification.intents]
                if normalized_intent is not None
                else [],
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

    def _classify_intent(self, state: ConversationState) -> NormalizedIntent:
        llm_config = self.intent_llm_config
        if llm_config is None:
            llm_config = self.response_llm_config
        if llm_config is None:
            llm_config = getattr(getattr(self.retrieval_stage, "config", None), "llm_config", None)
        classification_input = IntentClassificationInput(
            user_prompt=state.user_input,
            repository_name=_retrieval_repository_name(self.retrieval_stage),
            repository_context=_retrieval_repository_context(self.retrieval_stage, state.user_input),
            current_turn_type=state.history[-1].turn_type.value if state.history and state.history[-1].turn_type else None,
        )
        if llm_config is None:
            raise RuntimeError("Intent classification requires a configured LLM.")
        result = classify_intent(classification_input, llm_config=llm_config)
        payload = result.to_dict()
        self._record(LogEventType.INTENT_CLASSIFICATION, state.conversation_id, payload)
        if result.classification is None:
            raise RuntimeError(f"Intent classification failed: {result.error or 'unknown error'}")
        normalized = normalize_intent(
            result.classification,
            user_prompt=state.user_input,
            active_understanding_check=False,
        )
        self._record(LogEventType.INTENT_NORMALIZATION, state.conversation_id, normalized.to_dict())
        return normalized


def _retrieval_repository_name(retrieval_stage: Any) -> str | None:
    context = _retrieval_repository_context(retrieval_stage, "")
    repository_name = str(context.get("repository", {}).get("repository_name") or "")
    if repository_name:
        return repository_name
    package_name = str(context.get("repository", {}).get("package_name") or "")
    if package_name:
        return package_name
    workspace_root = getattr(getattr(retrieval_stage, "config", None), "workspace_root", None)
    if not workspace_root:
        return None
    return Path(str(workspace_root)).name or None


_ISSUE_PATH_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_./\\-])(?:\.{1,2}[\\/])?[A-Za-z0-9_@()+.-]+(?:[\\/][A-Za-z0-9_@()+.-]+)+\.[A-Za-z0-9_+-]+"
)


def _retrieval_repository_context(retrieval_stage: Any, user_prompt: str) -> dict[str, object]:
    """Build immutable request-analysis facts from the checked-out indexed workspace."""
    config = getattr(retrieval_stage, "config", None)
    workspace_root = Path(str(getattr(config, "workspace_root", "") or ""))
    repository_name = str(getattr(config, "repository_name", "") or "").strip()
    repository_owner = str(getattr(config, "repository_owner", "") or "").strip()
    package_name = ""
    package_path = workspace_root / "package.json"
    if package_path.is_file():
        try:
            package_value = json.loads(package_path.read_text(encoding="utf-8"))
            if isinstance(package_value, dict):
                package_name = str(package_value.get("name") or "").strip()
        except (OSError, json.JSONDecodeError):
            pass
    references = tuple(dict.fromkeys(
        match.group(0).replace("\\", "/").lstrip("./")
        for match in _ISSUE_PATH_PATTERN.finditer(user_prompt)
    ))[:12]
    return {
        "repository": {
            "workspace_name": workspace_root.name,
            "repository_name": repository_name,
            "repository_owner": repository_owner,
            "package_name": package_name,
        },
        "indexed_scope": {
            "excluded_paths": list(getattr(config, "index_exclude_paths", ()) or ()),
        },
        "issue_path_checks": [
            {
                "issue_reference": reference,
                "exists_in_indexed_repository": (workspace_root / reference).is_file(),
            }
            for reference in references
        ],
    }


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
    neutralize_multi_intent_stage_order: bool = False,
) -> ResponsePayload:
    return render_response(
        policy_result,
        retrieval_result,
        response_plan,
        state=state,
        llm_config=llm_config,
        log_event=record_event,
        neutralize_multi_intent_stage_order=neutralize_multi_intent_stage_order,
    )
