from __future__ import annotations

from typing import Any, Callable, Mapping

from core.logging_schema import LogEventType
from core.models import ConversationState, PolicyResult, ResponsePayload, ResponsePlan, RetrievalResult, TurnType
from services.response_generation.comprehension import generate_comprehension_explanation, prompt_template_id


def render_response(
    policy_result: PolicyResult,
    retrieval_result: RetrievalResult | None,
    response_plan: ResponsePlan,
    *,
    state: ConversationState | None = None,
    llm_config: Any | None = None,
    log_event: Callable[[LogEventType, Mapping[str, object]], None] | None = None,
) -> ResponsePayload:
    evidence = tuple(retrieval_result.evidence if retrieval_result is not None else ())
    evidence_refs = tuple(item.source_id for item in evidence)
    metadata: dict[str, object] = dict(response_plan.notes)
    if retrieval_result is not None and retrieval_result.retrieval_summary.get("artifact_trace"):
        metadata["artifact_trace"] = retrieval_result.retrieval_summary["artifact_trace"]
    if response_plan.turn_type == TurnType.BOUNDARY:
        content = f"Boundary: {policy_result.reason}"
    else:
        content, evidence_refs, generated_metadata = _render_explanation(
            retrieval_result,
            state=state,
            llm_config=llm_config,
            log_event=log_event,
        )
        metadata.update(generated_metadata)
    return ResponsePayload(
        turn_type=response_plan.turn_type,
        content=content,
        evidence_refs=evidence_refs,
        violations=policy_result.violations,
        metadata=metadata,
    )


def _render_explanation(
    retrieval_result: RetrievalResult | None,
    *,
    state: ConversationState | None,
    llm_config: Any | None,
    log_event: Callable[[LogEventType, Mapping[str, object]], None] | None,
) -> tuple[str, tuple[str, ...], Mapping[str, object]]:
    if retrieval_result is None or state is None:
        return (
            _render_explanation_error("Explanation generation requires retrieval context, but none is available."),
            (),
            {
                "generator": "llm_explanation",
                "prompt_template_id": prompt_template_id(),
                "used_evidence_refs": [],
                "render_notes": {},
                "error": "missing_retrieval_context",
            },
        )
    if llm_config is None:
        return (
            _render_explanation_error("Explanation generation requires a configured LLM. No response LLM configuration is available."),
            tuple(item.source_id for item in retrieval_result.evidence),
            {
                "generator": "llm_explanation",
                "prompt_template_id": prompt_template_id(),
                "used_evidence_refs": [],
                "render_notes": {},
                "error": "missing_llm_config",
            },
        )

    try:
        if log_event is not None:
            log_event(
                LogEventType.RESPONSE_GENERATION_REQUESTED,
                {
                    "prompt_template_id": prompt_template_id(),
                    "coverage_status": retrieval_result.coverage_status,
                    "retrieval_sufficient": retrieval_result.sufficient,
                    "evidence_count": len(retrieval_result.evidence),
                },
            )
        generated = generate_comprehension_explanation(
            state=state,
            retrieval_result=retrieval_result,
            llm_config=llm_config,
            log_event=_response_generation_log_adapter(log_event),
        )
        if log_event is not None:
            log_event(
                LogEventType.RESPONSE_GENERATION_RECEIVED,
                {
                    "prompt_template_id": generated.prompt_template_id,
                    "used_evidence_refs": list(generated.used_evidence_refs),
                    "render_notes": dict(generated.render_notes),
                    "answer_flow": dict(generated.answer_flow),
                    "story_flow": list(getattr(generated, "story_flow", ())),
                    "understanding_checks": [check.to_dict() for check in generated.understanding_checks],
                    "source_attributions": list(getattr(generated, "source_attributions", ())),
                    "next_checks": list(getattr(generated, "next_checks", ())),
                    "next_check_requirement": dict(getattr(generated, "next_check_requirement", {}) or {}),
                },
            )
        return (
            generated.markdown,
            tuple(generated.used_evidence_refs or tuple(item.source_id for item in retrieval_result.evidence)),
            {
                "generator": "llm_explanation",
                "prompt_template_id": generated.prompt_template_id,
                "used_evidence_refs": list(generated.used_evidence_refs),
                "render_notes": dict(generated.render_notes),
                "answer_flow": dict(generated.answer_flow),
                "story_flow": list(getattr(generated, "story_flow", ())),
                "understanding_checks": [check.to_dict() for check in generated.understanding_checks],
                "concept_definitions": list(getattr(generated, "concept_definitions", ())),
                "source_attributions": list(getattr(generated, "source_attributions", ())),
                "next_checks": list(getattr(generated, "next_checks", ())),
                "next_check_requirement": dict(getattr(generated, "next_check_requirement", {}) or {}),
                "comprehension_plan": generated.comprehension_plan.to_dict(),
            },
        )
    except Exception as exc:
        if log_event is not None:
            log_event(
                LogEventType.RESPONSE_GENERATION_FAILED,
                {
                    "prompt_template_id": prompt_template_id(),
                    "reason": str(exc),
                },
            )
        return (
            _render_explanation_error(f"Explanation generation failed: {exc}"),
            tuple(item.source_id for item in retrieval_result.evidence),
            {
                "generator": "llm_explanation",
                "prompt_template_id": prompt_template_id(),
                "used_evidence_refs": [],
                "render_notes": {},
                "error": str(exc),
            },
        )


def _response_generation_log_adapter(
    log_event: Callable[[LogEventType, Mapping[str, object]], None] | None,
) -> Callable[[str, Mapping[str, object]], None] | None:
    if log_event is None:
        return None

    def emit(event_type: str, payload: Mapping[str, object]) -> None:
        try:
            typed_event = LogEventType(event_type)
        except ValueError:
            typed_event = LogEventType.PROMPT_PAYLOAD
            payload = {"event_type": event_type, "payload": dict(payload)}
        log_event(typed_event, payload)

    return emit


def _render_explanation_error(message: str) -> str:
    return _section("Error", message)


def _section(title: str, body: str) -> str:
    return f"**{title}**\n{body}"
