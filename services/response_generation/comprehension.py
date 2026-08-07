from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from core.models import ConversationState, EvidenceItem, RetrievalResult
from services.guidance.questions import UnderstandingCheck, UnderstandingHint
from services.intent import compose_intent_flow, get_intent_contract, validate_stage_permutation
from services.intent.models import IntentFlowPlan, TaskIntent
from services.llm.json_completion import complete_json
from services.response_generation.repair import repair_explanation_response, repair_hint_ladders, repair_understanding_checks


PROMPT_TEMPLATE_ID = "intent_composed_explanation_v5"
PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "intent_composed_explanation.md"
EXPLANATION_EVIDENCE_LIMIT = 16
MAX_FLOW_REPAIR_ATTEMPTS = 1
MAX_QUESTION_REPAIR_ATTEMPTS = 1
MAX_HINT_REPAIR_ATTEMPTS = 1
HINT_KINDS = ("direction", "focus", "scaffold")
HINT_TEXT_LIMIT = 500
QUESTION_FIELD_LIMITS = {
    "reasoning_focus": 300,
    "selection_reason": 500,
    "question": 800,
}


class FlowValidationError(RuntimeError):
    def __init__(self, errors: Sequence[str]) -> None:
        self.errors = tuple(str(error) for error in errors if str(error).strip())
        super().__init__("Invalid intent-composed flow: " + "; ".join(self.errors))


class QuestionValidationError(FlowValidationError):
    def __init__(
        self,
        errors: Sequence[str],
        *,
        accepted: Sequence[tuple[int, Mapping[str, Any]]],
        rejected: Sequence[Mapping[str, Any]],
    ) -> None:
        self.accepted = tuple((int(index), dict(raw)) for index, raw in accepted)
        self.rejected = tuple(dict(item) for item in rejected)
        super().__init__(errors)


@dataclass(frozen=True)
class ComprehensionGenerationResult:
    markdown: str
    used_evidence_refs: tuple[str, ...]
    render_notes: Mapping[str, str]
    answer_flow: Mapping[str, Any]
    story_flow: tuple[Mapping[str, Any], ...]
    understanding_checks: tuple[UnderstandingCheck, ...]
    selected_intents: tuple[str, ...]
    presentation_sections: tuple[Mapping[str, Any], ...] = ()
    presentation_lists: tuple[Mapping[str, Any], ...] = ()
    examples: tuple[Mapping[str, Any], ...] = ()
    comparison_tables: tuple[Mapping[str, Any], ...] = ()
    additional_implementation_observations: tuple[Mapping[str, Any], ...] = ()
    concept_definitions: tuple[Mapping[str, Any], ...] = ()
    source_attributions: tuple[Mapping[str, Any], ...] = ()
    next_checks: tuple[Mapping[str, str], ...] = ()
    prompt_template_id: str = PROMPT_TEMPLATE_ID
    flow_repair_attempts: int = 0
    question_repair_attempts: int = 0
    hint_repair_attempts: int = 0
    stage_input_order_mode: str = "canonical_contract_order"


def generate_comprehension_explanation(
    *,
    state: ConversationState,
    retrieval_result: RetrievalResult,
    llm_config: Any,
    log_warning: Callable[[Mapping[str, Any]], None] | None = None,
    log_event: Callable[[str, Mapping[str, Any]], None] | None = None,
    neutralize_multi_intent_stage_order: bool = False,
) -> ComprehensionGenerationResult:
    if state.intent_context is None or not state.intent_context.intents:
        raise RuntimeError("Explanation generation requires classified task intents.")
    flow_plan = compose_intent_flow(state.intent_context.intents)
    model_intent_flow, model_stage_ids, stage_input_order_mode = _model_facing_intent_flow(
        flow_plan,
        user_prompt=state.user_input,
        neutralize=neutralize_multi_intent_stage_order,
    )
    evidence = tuple(retrieval_result.evidence[:EXPLANATION_EVIDENCE_LIMIT])
    selected_evidence_connections = _selected_evidence_connections(
        retrieval_result,
        allowed_refs={item.source_id for item in evidence},
    )
    payload = {
        "user_prompt": state.user_input,
        "intent_flow": model_intent_flow,
        "question_prerequisites_by_intent": {
            contract.intent.value: list(contract.question.prerequisite_stage_ids)
            for contract in flow_plan.contracts
        },
        "retrieval_sufficient": retrieval_result.sufficient,
        "coverage_status": retrieval_result.coverage_status,
        "request_context": {
            "task_goal": state.user_input,
            "answer_scope": (
                "Ground the complete requested explanation in selected evidence."
                if retrieval_result.sufficient
                else "Explain only supported behavior and state unsupported parts clearly."
            ),
        },
        "evidence": [_compact_evidence(item) for item in evidence],
        "selected_evidence_connections": selected_evidence_connections,
        "allowed_evidence_refs": [item.source_id for item in evidence],
        "question_field_limits": dict(QUESTION_FIELD_LIMITS),
        "hint_contract": {"ordered_kinds": list(HINT_KINDS), "text_max_characters": HINT_TEXT_LIMIT},
    }
    if log_event is not None:
        log_event("comprehension_generation_request_payload", {"prompt_template_id": PROMPT_TEMPLATE_ID, "payload": payload})

    response = _complete_generation(
        llm_config=llm_config,
        payload=payload,
        flow_plan=flow_plan,
        model_stage_ids=model_stage_ids,
        log_warning=log_warning,
        log_event=log_event,
    )
    repair_attempts = 0
    question_repair_attempts = 0
    hint_repair_attempts = 0
    response, repaired_hints = _repair_invalid_hint_ladders(
        response=response,
        generation_payload=payload,
        flow_plan=flow_plan,
        llm_config=llm_config,
        log_warning=log_warning,
        log_event=log_event,
    )
    hint_repair_attempts += repaired_hints
    try:
        result = _validate_response(response, evidence=evidence, flow_plan=flow_plan)
    except QuestionValidationError as exc:
        response = _repair_questions_in_response(
            response=response,
            validation_error=exc,
            generation_payload=payload,
            evidence=evidence,
            flow_plan=flow_plan,
            llm_config=llm_config,
            log_warning=log_warning,
            log_event=log_event,
        )
        question_repair_attempts = MAX_QUESTION_REPAIR_ATTEMPTS
        try:
            result = _validate_response(response, evidence=evidence, flow_plan=flow_plan)
        except FlowValidationError as repaired_exc:
            raise RuntimeError(
                "Question generation failed after one isolated repair attempt: " + "; ".join(repaired_exc.errors)
            ) from repaired_exc
    except FlowValidationError as exc:
        if log_event is not None:
            log_event(
                "intent_flow_validation_failed",
                {
                    "attempt": 0,
                    "errors": list(exc.errors),
                    "required_stage_ids": list(flow_plan.contract_stage_ids),
                    "model_stage_ids": list(model_stage_ids),
                    "raw_response": dict(response),
                },
            )
        repair_attempts = MAX_FLOW_REPAIR_ATTEMPTS
        repaired = repair_explanation_response(
            llm_config=llm_config,
            context={
                "generation_context": payload,
                "validation_errors": list(exc.errors),
                "previous_response": dict(response),
            },
            response_format=_response_format(flow_plan, model_stage_ids=model_stage_ids),
            log_warning=log_warning,
            log_event=log_event,
        )
        repaired, repaired_hints = _repair_invalid_hint_ladders(
            response=repaired,
            generation_payload=payload,
            flow_plan=flow_plan,
            llm_config=llm_config,
            log_warning=log_warning,
            log_event=log_event,
        )
        hint_repair_attempts += repaired_hints
        try:
            result = _validate_response(repaired, evidence=evidence, flow_plan=flow_plan)
        except QuestionValidationError as question_exc:
            repaired = _repair_questions_in_response(
                response=repaired,
                validation_error=question_exc,
                generation_payload=payload,
                evidence=evidence,
                flow_plan=flow_plan,
                llm_config=llm_config,
                log_warning=log_warning,
                log_event=log_event,
            )
            question_repair_attempts = MAX_QUESTION_REPAIR_ATTEMPTS
            result = _validate_response(repaired, evidence=evidence, flow_plan=flow_plan)
        except FlowValidationError as repaired_exc:
            if log_event is not None:
                log_event(
                    "intent_flow_validation_failed",
                    {
                        "attempt": 1,
                        "errors": list(repaired_exc.errors),
                        "required_stage_ids": list(flow_plan.contract_stage_ids),
                        "model_stage_ids": list(model_stage_ids),
                        "raw_response": dict(repaired),
                    },
                )
            raise RuntimeError(
                "Intent flow planning failed after one repair attempt: " + "; ".join(repaired_exc.errors)
            ) from repaired_exc

    result = replace(
        result,
        flow_repair_attempts=repair_attempts,
        question_repair_attempts=question_repair_attempts,
        hint_repair_attempts=hint_repair_attempts,
        stage_input_order_mode=stage_input_order_mode,
    )
    if log_event is not None:
        log_event(
            "comprehension_generation_response_payload",
            {
                "prompt_template_id": PROMPT_TEMPLATE_ID,
                "selected_intents": list(result.selected_intents),
                "ordered_stage_ids": list(result.answer_flow.get("ordered_stage_ids", ())),
                "used_evidence_refs": list(result.used_evidence_refs),
                "understanding_check_count": len(result.understanding_checks),
                "flow_repair_attempts": repair_attempts,
                "question_repair_attempts": question_repair_attempts,
                "hint_repair_attempts": hint_repair_attempts,
                "stage_input_order_mode": stage_input_order_mode,
                "model_stage_ids": list(model_stage_ids),
            },
        )
    return result


def prompt_template_id() -> str:
    return PROMPT_TEMPLATE_ID


def _model_facing_intent_flow(
    flow_plan: IntentFlowPlan,
    *,
    user_prompt: str,
    neutralize: bool,
) -> tuple[dict[str, Any], tuple[str, ...], str]:
    if not neutralize or len(flow_plan.intents) < 2:
        return flow_plan.to_generation_dict(), flow_plan.contract_stage_ids, "canonical_contract_order"

    prompt_key = hashlib.sha256(user_prompt.strip().encode("utf-8")).hexdigest()
    stages = tuple(stage for contract in flow_plan.contracts for stage in contract.stages)
    model_stages = tuple(
        sorted(
            stages,
            key=lambda stage: hashlib.sha256(
                f"{prompt_key}\0{stage.id}".encode("utf-8")
            ).hexdigest(),
        )
    )
    contracts: list[dict[str, Any]] = []
    for contract in flow_plan.contracts:
        value = contract.to_dict(include_evidence_expectations=False)
        value.pop("stages", None)
        contracts.append(value)
    model_stage_ids = tuple(stage.id for stage in model_stages)
    return (
        {
            "intents": [intent.value for intent in flow_plan.intents],
            "contract_stage_ids": list(model_stage_ids),
            "stage_definitions": [stage.to_dict() for stage in model_stages],
            "contracts": contracts,
            "input_order_mode": "prompt_seeded_stable_permutation",
        },
        model_stage_ids,
        "prompt_seeded_stable_permutation",
    )


def _complete_generation(
    *,
    llm_config: Any,
    payload: Mapping[str, Any],
    flow_plan: IntentFlowPlan,
    model_stage_ids: Sequence[str],
    log_warning: Callable[[Mapping[str, Any]], None] | None,
    log_event: Callable[[str, Mapping[str, Any]], None] | None,
) -> Mapping[str, Any]:
    return complete_json(
        llm_config,
        (
            {"role": "system", "content": PROMPT_PATH.read_text(encoding="utf-8")},
            {"role": "user", "content": json.dumps(payload, sort_keys=True)},
        ),
        response_format=_response_format(flow_plan, model_stage_ids=model_stage_ids),
        log_warning=log_warning,
        log_event=log_event,
    )


def _repair_questions_in_response(
    *,
    response: Mapping[str, Any],
    validation_error: QuestionValidationError,
    generation_payload: Mapping[str, Any],
    evidence: Sequence[EvidenceItem],
    flow_plan: IntentFlowPlan,
    llm_config: Any,
    log_warning: Callable[[Mapping[str, Any]], None] | None,
    log_event: Callable[[str, Mapping[str, Any]], None] | None,
) -> Mapping[str, Any]:
    rejected = list(validation_error.rejected)
    replacements = repair_understanding_checks(
        llm_config=llm_config,
        context={
            "generation_context": dict(generation_payload),
            "completed_explanation": {
                key: value for key, value in response.items() if key != "understanding_checks"
            },
            "accepted_questions": [raw for _, raw in validation_error.accepted],
            "rejected_questions": rejected,
            "question_field_limits": dict(QUESTION_FIELD_LIMITS),
        },
        response_format=_question_repair_response_format(flow_plan, count=len(rejected)),
        log_warning=log_warning,
        log_event=log_event,
    )
    if len(replacements) != len(rejected):
        raise RuntimeError("Question repair did not return one replacement per rejected question.")
    raw_checks = response.get("understanding_checks")
    merged = list(raw_checks) if isinstance(raw_checks, list) else []
    for rejected_item, replacement in zip(rejected, replacements):
        index = int(rejected_item.get("index", len(merged)))
        if index < len(merged):
            merged[index] = dict(replacement)
        else:
            merged.append(dict(replacement))
    if log_event is not None:
        log_event(
            "understanding_check_repair_completed",
            {
                "repaired_indexes": [int(item.get("index", -1)) for item in rejected],
                "preserved_indexes": [index for index, _ in validation_error.accepted],
            },
        )
    return {**dict(response), "understanding_checks": merged}


def _question_repair_response_format(flow_plan: IntentFlowPlan, *, count: int) -> Mapping[str, Any]:
    item_schema = _response_format(flow_plan)["json_schema"]["schema"]["properties"]["understanding_checks"]["items"]
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "understanding_check_repair",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "understanding_checks": {
                        "type": "array",
                        "items": item_schema,
                        "minItems": count,
                        "maxItems": count,
                    }
                },
                "required": ["understanding_checks"],
                "additionalProperties": False,
            },
        },
    }


def _repair_invalid_hint_ladders(
    *,
    response: Mapping[str, Any],
    generation_payload: Mapping[str, Any],
    flow_plan: IntentFlowPlan,
    llm_config: Any,
    log_warning: Callable[[Mapping[str, Any]], None] | None,
    log_event: Callable[[str, Mapping[str, Any]], None] | None,
) -> tuple[Mapping[str, Any], int]:
    raw_checks = response.get("understanding_checks")
    if not isinstance(raw_checks, list):
        return response, 0
    rejected: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_checks):
        if not isinstance(raw, Mapping):
            continue
        errors = _hint_ladder_errors(raw.get("hints"))
        if errors:
            rejected.append({"question_index": index, "question": dict(raw), "errors": errors})
    if not rejected:
        return response, 0
    ladders = repair_hint_ladders(
        llm_config=llm_config,
        context={
            "generation_context": dict(generation_payload),
            "completed_explanation": {key: value for key, value in response.items() if key != "understanding_checks"},
            "all_questions": [dict(item) for item in raw_checks if isinstance(item, Mapping)],
            "rejected_hint_ladders": rejected,
            "hint_contract": {"ordered_kinds": list(HINT_KINDS), "text_max_characters": HINT_TEXT_LIMIT},
        },
        response_format=_hint_repair_response_format(count=len(rejected)),
        log_warning=log_warning,
        log_event=log_event,
    )
    if len(ladders) != len(rejected):
        raise RuntimeError("Hint repair did not return one ladder per rejected question.")
    merged = [dict(item) if isinstance(item, Mapping) else item for item in raw_checks]
    for rejected_item, ladder in zip(rejected, ladders):
        errors = _hint_ladder_errors(ladder)
        if errors:
            raise RuntimeError("Hint repair returned an invalid ladder: " + "; ".join(errors))
        index = int(rejected_item["question_index"])
        merged[index] = {**dict(merged[index]), "hints": [dict(item) for item in ladder]}
    if log_event is not None:
        log_event("understanding_hint_repair_completed", {"repaired_question_indexes": [item["question_index"] for item in rejected]})
    return {**dict(response), "understanding_checks": merged}, MAX_HINT_REPAIR_ATTEMPTS


def _hint_ladder_errors(value: Any) -> list[str]:
    if not isinstance(value, list) or len(value) != len(HINT_KINDS):
        return ["hints must contain exactly direction, focus, and scaffold"]
    errors: list[str] = []
    texts: list[str] = []
    for index, (raw, expected_kind) in enumerate(zip(value, HINT_KINDS), start=1):
        if not isinstance(raw, Mapping):
            errors.append(f"hint {index} must be an object")
            continue
        kind = str(raw.get("kind") or "").strip()
        text = str(raw.get("text") or "").strip()
        if kind != expected_kind:
            errors.append(f"hint {index} must use kind {expected_kind}")
        if not text:
            errors.append(f"hint {index} has empty text")
        elif len(text) > HINT_TEXT_LIMIT:
            errors.append(f"hint {index} exceeds {HINT_TEXT_LIMIT} characters")
        texts.append(" ".join(text.casefold().split()))
    if len(texts) != len(set(texts)):
        errors.append("hint texts must be distinct")
    return errors


def _hints_from_value(value: Any) -> tuple[UnderstandingHint, ...]:
    errors = _hint_ladder_errors(value)
    if errors:
        raise ValueError("; ".join(errors))
    return tuple(
        UnderstandingHint(kind=str(raw["kind"]).strip(), text=str(raw["text"]).strip())
        for raw in value
    )


def _hint_item_schema() -> Mapping[str, Any]:
    return {
        "type": "array",
        "minItems": len(HINT_KINDS),
        "maxItems": len(HINT_KINDS),
        "items": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": list(HINT_KINDS)},
                "text": {"type": "string", "maxLength": HINT_TEXT_LIMIT},
            },
            "required": ["kind", "text"],
            "additionalProperties": False,
        },
    }


def _hint_repair_response_format(*, count: int) -> Mapping[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "understanding_hint_repair",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "hint_ladders": {
                        "type": "array",
                        "items": _hint_item_schema(),
                        "minItems": count,
                        "maxItems": count,
                    }
                },
                "required": ["hint_ladders"],
                "additionalProperties": False,
            },
        },
    }


def _validate_response(
    response: Mapping[str, Any],
    *,
    evidence: Sequence[EvidenceItem],
    flow_plan: IntentFlowPlan,
) -> ComprehensionGenerationResult:
    allowed_refs = {item.source_id for item in evidence}
    ordered_stage_ids = _strings(response.get("ordered_stage_ids"))
    errors = list(validate_stage_permutation(flow_plan.contract_stage_ids, ordered_stage_ids))
    raw_stages = response.get("stages")
    if not isinstance(raw_stages, list):
        errors.append("stages must be an array")
        raw_stages = []
    received_stage_ids = tuple(
        str(item.get("stage_id") or "").strip() for item in raw_stages if isinstance(item, Mapping)
    )
    errors.extend(f"stage objects: {error}" for error in validate_stage_permutation(flow_plan.contract_stage_ids, received_stage_ids))
    if received_stage_ids and received_stage_ids != ordered_stage_ids:
        errors.append("stage objects are not in ordered_stage_ids order")
    if errors:
        raise FlowValidationError(errors)

    stages: list[dict[str, Any]] = []
    used_refs: list[str] = []
    content_errors: list[str] = []
    for raw_stage in raw_stages:
        if not isinstance(raw_stage, Mapping):
            content_errors.append("stage item is not an object")
            continue
        stage_id = str(raw_stage.get("stage_id") or "").strip()
        title = str(raw_stage.get("title") or "").strip()
        raw_sentences = raw_stage.get("sentences")
        sentences: list[dict[str, Any]] = []
        if not isinstance(raw_sentences, list) or not raw_sentences:
            content_errors.append(f"{stage_id}: missing sentences")
            raw_sentences = []
        for raw_sentence in raw_sentences:
            if not isinstance(raw_sentence, Mapping):
                content_errors.append(f"{stage_id}: sentence is not an object")
                continue
            text = str(raw_sentence.get("text") or "").strip()
            kind = str(raw_sentence.get("kind") or "").strip()
            refs = _strings(raw_sentence.get("evidence_refs"))
            invalid_refs = tuple(ref for ref in refs if ref not in allowed_refs)
            if not text or kind not in {"code_claim", "connective"}:
                content_errors.append(f"{stage_id}: invalid sentence text or kind")
                continue
            if invalid_refs:
                content_errors.append(f"{stage_id}: invalid evidence refs {', '.join(invalid_refs)}")
                continue
            if kind == "code_claim" and not refs:
                content_errors.append(f"{stage_id}: code_claim has no evidence refs")
                continue
            if kind == "connective" and refs:
                content_errors.append(f"{stage_id}: connective sentence has evidence refs")
                continue
            for ref in refs:
                if ref not in used_refs:
                    used_refs.append(ref)
            sentences.append({"text": text[:1200], "kind": kind, "evidence_refs": list(refs)})
        stages.append({"stage_id": stage_id, "title": title[:160], "sentences": sentences})
    if content_errors:
        raise FlowValidationError(content_errors)

    stage_ids = tuple(stage["stage_id"] for stage in stages)
    presentation_sections = _presentation_sections(
        response.get("presentation_sections"),
        ordered_stage_ids=stage_ids,
    )
    presentation_lists = _presentation_lists(
        response.get("presentation_lists"),
        allowed_refs=allowed_refs,
        allowed_stage_ids=set(stage_ids),
    )
    examples = _examples(
        response.get("examples"),
        allowed_refs=allowed_refs,
        allowed_stage_ids=set(stage_ids),
    )
    comparison_tables = _comparison_tables(
        response.get("comparison_tables"),
        allowed_refs=allowed_refs,
        allowed_stage_ids=set(stage_ids),
    )
    observations = _additional_implementation_observations(
        response.get("additional_implementation_observations"),
        allowed_refs=allowed_refs,
    )
    for ref in _presentation_evidence_refs(presentation_lists, examples, comparison_tables, observations):
        if ref not in used_refs:
            used_refs.append(ref)
    render_notes = _render_notes(response.get("render_notes"))
    evidence_by_ref = {item.source_id: item for item in evidence}
    markdown = _render_story_flow_markdown(
        stages,
        presentation_sections=presentation_sections,
        presentation_lists=presentation_lists,
        examples=examples,
        comparison_tables=comparison_tables,
        observations=observations,
        render_notes=render_notes,
        evidence_by_ref=evidence_by_ref,
    )
    if not markdown.strip():
        raise FlowValidationError(("rendered explanation is empty",))
    answer_flow = {
        "ordered_stage_ids": list(ordered_stage_ids),
        "stages": [
            {
                "stage_id": stage["stage_id"],
                "summary": " ".join(str(sentence["text"]) for sentence in stage["sentences"]),
                "evidence_refs": list(dict.fromkeys(ref for sentence in stage["sentences"] for ref in sentence["evidence_refs"])),
            }
            for stage in stages
        ],
    }
    checks = _understanding_checks_from_response(
        response.get("understanding_checks"),
        flow_plan=flow_plan,
        allowed_refs=allowed_refs,
        stage_evidence_refs={
            stage["stage_id"]: {
                ref
                for sentence in stage["sentences"]
                for ref in sentence["evidence_refs"]
            }
            for stage in stages
        },
    )
    concept_definitions = _concept_definitions(response.get("concept_definitions"), allowed_refs=allowed_refs)
    source_attributions = _source_attributions(response.get("source_attributions"), markdown=markdown, allowed_refs=allowed_refs)
    next_checks = _next_checks(response.get("next_checks"))
    return ComprehensionGenerationResult(
        markdown=markdown,
        used_evidence_refs=tuple(used_refs),
        render_notes=render_notes,
        answer_flow=answer_flow,
        story_flow=tuple(stages),
        understanding_checks=checks,
        selected_intents=tuple(intent.value for intent in flow_plan.intents),
        presentation_sections=presentation_sections,
        presentation_lists=presentation_lists,
        examples=examples,
        comparison_tables=comparison_tables,
        additional_implementation_observations=observations,
        concept_definitions=concept_definitions,
        source_attributions=source_attributions,
        next_checks=next_checks,
    )


def _understanding_checks_from_response(
    value: Any,
    *,
    flow_plan: IntentFlowPlan,
    allowed_refs: set[str],
    stage_evidence_refs: Mapping[str, set[str]],
) -> tuple[UnderstandingCheck, ...]:
    if not isinstance(value, list):
        raise QuestionValidationError(
            ("understanding_checks must be an array",), accepted=(), rejected=({"index": 0, "raw": None, "errors": ["must be an array"]},)
        )
    if not value:
        raise QuestionValidationError(
            ("at least one understanding check is required",),
            accepted=(),
            rejected=({"index": 0, "raw": None, "errors": ["at least one check is required"]},),
        )
    if len(value) > 3:
        raise QuestionValidationError(
            ("at most three understanding checks are allowed",),
            accepted=(),
            rejected=tuple({"index": index, "raw": raw, "errors": ["response contains more than three checks"]} for index, raw in enumerate(value)),
        )

    checks: list[UnderstandingCheck] = []
    accepted_raw: list[tuple[int, Mapping[str, Any]]] = []
    rejected: list[Mapping[str, Any]] = []
    all_errors: list[str] = []
    seen_ids: set[str] = set()
    seen_questions: set[str] = set()
    seen_reasoning_focuses: set[str] = set()
    seen_support_signatures: set[tuple[str, frozenset[str], frozenset[str]]] = set()
    prior_target_stage_ids: set[str] = set()
    prior_evidence_refs: set[str] = set()
    allowed_stage_ids = set(flow_plan.contract_stage_ids)
    for position, raw in enumerate(value):
        index = position + 1
        prefix = f"understanding check {index}"
        errors: list[str] = []
        if not isinstance(raw, Mapping):
            errors.append(f"{prefix} must be an object")
            rejected.append({"index": position, "raw": raw, "errors": list(errors)})
            all_errors.extend(errors)
            continue
        check_id = str(raw.get("id") or f"q{index}").strip() or f"q{index}"
        normalized_id = check_id.casefold()
        if normalized_id in seen_ids:
            errors.append(f"{prefix} has a duplicate ID")
        try:
            intent = TaskIntent(str(raw.get("intent") or ""))
        except ValueError:
            errors.append(f"{prefix} uses an unknown intent")
            rejected.append({"index": position, "raw": dict(raw), "errors": list(errors)})
            all_errors.extend(errors)
            continue
        if intent not in flow_plan.intents:
            errors.append(f"{prefix} intent was not selected")
        contract = get_intent_contract(intent)
        target_stage_ids = _strings(raw.get("target_stage_ids"))
        stem_family = str(raw.get("stem_family") or "").strip()
        reasoning_focus = str(raw.get("reasoning_focus") or "").strip()
        selection_reason = str(raw.get("selection_reason") or "").strip()
        refs = _strings(raw.get("evidence_refs"))
        question = str(raw.get("question") or "").strip()
        expected = _strings(raw.get("expected_answer_points"))
        try:
            hints = _hints_from_value(raw.get("hints"))
        except ValueError as exc:
            errors.append(f"{prefix} has an invalid hint ladder: {exc}")
            hints = ()
        normalized_question = " ".join(question.casefold().split())
        normalized_focus = " ".join(reasoning_focus.casefold().split())
        target_set = set(target_stage_ids)
        intent_stage_ids = {stage.id for stage in contract.stages}
        # Prerequisites are contract-owned metadata, not a model decision. The
        # model still receives and returns the field for schema clarity, but a
        # transcription mismatch must not discard an otherwise valid question
        # or the complete explanation that contains it.
        prerequisite_stage_ids = contract.question.prerequisite_stage_ids

        if (
            not target_stage_ids
            or len(target_stage_ids) > 2
            or len(target_set) != len(target_stage_ids)
            or not target_set.issubset(allowed_stage_ids)
        ):
            errors.append(f"{prefix} has invalid target stages")
        elif not target_set.intersection(intent_stage_ids):
            errors.append(f"{prefix} does not target a stage belonging to its intent")
        support_signature = (intent.value, frozenset(target_set), frozenset(refs))
        if support_signature in seen_support_signatures:
            errors.append(f"{prefix} repeats another check's intent, target stages, and evidence")
        if checks and not (target_set - prior_target_stage_ids or set(refs) - prior_evidence_refs):
            errors.append(f"{prefix} adds no new target stage or supporting evidence")
        if stem_family not in contract.question.stem_families:
            errors.append(f"{prefix} stem is not allowed by its intent contract")
        if not refs or any(ref not in allowed_refs for ref in refs):
            errors.append(f"{prefix} has invalid or empty evidence refs")
        reasoning_stage_ids = target_set.union(prerequisite_stage_ids)
        reasoning_refs = {
            ref
            for stage_id in reasoning_stage_ids
            for ref in stage_evidence_refs.get(stage_id, set())
        }
        if refs and not set(refs).intersection(reasoning_refs):
            errors.append(f"{prefix} evidence does not support its target or prerequisite stages")
        if not question or not expected or not hints:
            errors.append(f"{prefix} lacks question, expected points, or hints")
        if not reasoning_focus or not selection_reason:
            errors.append(f"{prefix} lacks a reasoning focus or selection reason")
        if normalized_focus in seen_reasoning_focuses:
            errors.append(f"{prefix} duplicates another reasoning focus")
        if normalized_question in seen_questions:
            errors.append(f"{prefix} duplicates another question")
        for field_name, limit in QUESTION_FIELD_LIMITS.items():
            field_value = str(raw.get(field_name) or "").strip()
            if len(field_value) > limit:
                errors.append(f"{prefix} {field_name} exceeds {limit} characters")
        if errors:
            rejected.append({"index": position, "raw": dict(raw), "errors": list(errors)})
            all_errors.extend(errors)
            continue
        seen_ids.add(normalized_id)
        seen_support_signatures.add(support_signature)
        prior_target_stage_ids.update(target_set)
        prior_evidence_refs.update(refs)
        seen_reasoning_focuses.add(normalized_focus)
        seen_questions.add(normalized_question)
        accepted_raw.append((position, dict(raw)))
        checks.append(UnderstandingCheck(
            id=check_id,
            intent=intent,
            target_stage_ids=target_stage_ids,
            prerequisite_stage_ids=prerequisite_stage_ids,
            stem_family=stem_family,
            reasoning_focus=reasoning_focus,
            selection_reason=selection_reason,
            question=question,
            expected_answer_points=expected,
            hints=hints,
            evidence_refs=refs,
        ))
    if rejected:
        raise QuestionValidationError(all_errors, accepted=accepted_raw, rejected=rejected)
    return tuple(checks)


def _presentation_sections(
    value: Any,
    *,
    ordered_stage_ids: tuple[str, ...],
) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list) or not value:
        raise FlowValidationError(("presentation_sections must be a non-empty array",))
    sections: list[dict[str, Any]] = []
    flattened: list[str] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(value):
        if not isinstance(raw, Mapping):
            raise FlowValidationError(("presentation section must be an object",))
        section_id = str(raw.get("id") or "").strip()
        title = str(raw.get("title") or "").strip()
        stage_ids = _strings(raw.get("stage_ids"))
        if not section_id or section_id in seen_ids or not stage_ids:
            raise FlowValidationError(("presentation sections require unique IDs and at least one stage",))
        if index > 0 and not title:
            raise FlowValidationError(("every presentation section after the opening section requires a title",))
        seen_ids.add(section_id)
        flattened.extend(stage_ids)
        sections.append({"id": section_id[:80], "title": title[:160], "stage_ids": list(stage_ids)})
    if tuple(flattened) != ordered_stage_ids:
        raise FlowValidationError(("presentation sections must partition ordered_stage_ids without reordering them",))
    if len(ordered_stage_ids) > 2 and len(sections) < 2:
        raise FlowValidationError(("flows longer than two stages require an opening section and at least one titled section",))
    if len(sections[0]["stage_ids"]) > 2:
        raise FlowValidationError(("the opening presentation section may contain at most two stages",))
    if any(len(section["stage_ids"]) > 3 for section in sections[1:]):
        raise FlowValidationError(("a titled presentation section may contain at most three stages",))
    return tuple(sections)


def _presentation_lists(
    value: Any,
    *,
    allowed_refs: set[str],
    allowed_stage_ids: set[str],
) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list):
        raise FlowValidationError(("presentation_lists must be an array",))
    output: list[Mapping[str, Any]] = []
    for raw in value[:4]:
        if not isinstance(raw, Mapping):
            raise FlowValidationError(("presentation list must be an object",))
        stage_id = str(raw.get("placement_stage_id") or "").strip()
        items: list[Mapping[str, Any]] = []
        raw_items = raw.get("items")
        if stage_id not in allowed_stage_ids or not isinstance(raw_items, list) or not raw_items:
            raise FlowValidationError(("presentation list has invalid placement or no items",))
        for item in raw_items[:8]:
            if not isinstance(item, Mapping):
                raise FlowValidationError(("presentation list item must be an object",))
            text = str(item.get("text") or "").strip()
            refs = _validated_refs(item.get("evidence_refs"), allowed_refs=allowed_refs)
            if not text or not refs:
                raise FlowValidationError(("presentation list items require text and evidence refs",))
            items.append({"text": text[:700], "evidence_refs": list(refs)})
        output.append(
            {
                "placement_stage_id": stage_id,
                "order": _presentation_order(raw.get("order")),
                "title": str(raw.get("title") or "").strip()[:160],
                "ordered": bool(raw.get("ordered")),
                "items": items,
            }
        )
    return tuple(output)


def _examples(
    value: Any,
    *,
    allowed_refs: set[str],
    allowed_stage_ids: set[str],
) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list):
        raise FlowValidationError(("examples must be an array",))
    output: list[Mapping[str, Any]] = []
    for raw in value[:2]:
        if not isinstance(raw, Mapping):
            raise FlowValidationError(("example must be an object",))
        stage_id = str(raw.get("placement_stage_id") or "").strip()
        title = str(raw.get("title") or "").strip()
        content = str(raw.get("content") or "").strip()
        provenance = str(raw.get("provenance") or "").strip()
        refs = _validated_refs(raw.get("evidence_refs"), allowed_refs=allowed_refs)
        if (
            stage_id not in allowed_stage_ids
            or not title
            or not content
            or provenance not in {"direct", "conceptual_from_evidence"}
            or not refs
        ):
            raise FlowValidationError(("example has invalid placement, provenance, content, or evidence refs",))
        output.append(
            {
                "placement_stage_id": stage_id,
                "order": _presentation_order(raw.get("order")),
                "title": title[:160],
                "language": str(raw.get("language") or "text").strip()[:40] or "text",
                "content": content[:6000],
                "provenance": provenance,
                "evidence_refs": list(refs),
            }
        )
    return tuple(output)


def _comparison_tables(
    value: Any,
    *,
    allowed_refs: set[str],
    allowed_stage_ids: set[str],
) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list):
        raise FlowValidationError(("comparison_tables must be an array",))
    output: list[Mapping[str, Any]] = []
    for raw in value[:2]:
        if not isinstance(raw, Mapping):
            raise FlowValidationError(("comparison table must be an object",))
        stage_id = str(raw.get("placement_stage_id") or "").strip()
        title = str(raw.get("title") or "").strip()
        columns = _strings(raw.get("columns"))
        raw_rows = raw.get("rows")
        if stage_id not in allowed_stage_ids or not title or len(columns) < 2 or len(columns) > 6 or not isinstance(raw_rows, list):
            raise FlowValidationError(("comparison table has invalid placement, title, or columns",))
        rows: list[Mapping[str, Any]] = []
        for raw_row in raw_rows[:10]:
            if not isinstance(raw_row, Mapping):
                raise FlowValidationError(("comparison table row must be an object",))
            cells = _strings_preserve_empty(raw_row.get("cells"))
            refs = _validated_refs(raw_row.get("evidence_refs"), allowed_refs=allowed_refs)
            if len(cells) != len(columns) or not refs:
                raise FlowValidationError(("comparison table rows must match columns and include evidence refs",))
            rows.append({"cells": list(cells), "evidence_refs": list(refs)})
        if len(rows) < 2:
            raise FlowValidationError(("comparison table requires at least two rows",))
        output.append(
            {
                "placement_stage_id": stage_id,
                "order": _presentation_order(raw.get("order")),
                "title": title[:160],
                "columns": list(columns),
                "rows": rows,
            }
        )
    return tuple(output)


def _additional_implementation_observations(
    value: Any,
    *,
    allowed_refs: set[str],
) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list):
        raise FlowValidationError(("additional_implementation_observations must be an array",))
    output: list[Mapping[str, Any]] = []
    for raw in value[:3]:
        if not isinstance(raw, Mapping):
            raise FlowValidationError(("additional implementation observation must be an object",))
        text = str(raw.get("text") or "").strip()
        relevance = str(raw.get("why_it_matters") or "").strip()
        refs = _validated_refs(raw.get("evidence_refs"), allowed_refs=allowed_refs)
        if not text or not relevance or not refs:
            raise FlowValidationError(("additional observations require text, relevance, and evidence refs",))
        output.append({"text": text[:700], "why_it_matters": relevance[:500], "evidence_refs": list(refs)})
    return tuple(output)


def _validated_refs(value: Any, *, allowed_refs: set[str]) -> tuple[str, ...]:
    refs = _strings(value)
    if not refs or any(ref not in allowed_refs for ref in refs):
        return ()
    return refs


def _presentation_order(value: Any) -> int:
    try:
        return max(0, min(20, int(value)))
    except (TypeError, ValueError):
        return 0


def _presentation_evidence_refs(*groups: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    refs: list[str] = []
    for group in groups:
        for value in group:
            candidates = [value]
            candidates.extend(item for item in value.get("items", ()) if isinstance(item, Mapping))
            candidates.extend(row for row in value.get("rows", ()) if isinstance(row, Mapping))
            for candidate in candidates:
                for ref in _strings(candidate.get("evidence_refs")):
                    if ref not in refs:
                        refs.append(ref)
    return tuple(refs)


def _render_story_flow_markdown(
    stages: Sequence[Mapping[str, Any]],
    *,
    presentation_sections: Sequence[Mapping[str, Any]],
    presentation_lists: Sequence[Mapping[str, Any]],
    examples: Sequence[Mapping[str, Any]],
    comparison_tables: Sequence[Mapping[str, Any]],
    observations: Sequence[Mapping[str, Any]],
    render_notes: Mapping[str, str],
    evidence_by_ref: Mapping[str, EvidenceItem],
) -> str:
    stage_by_id = {str(stage.get("stage_id") or ""): stage for stage in stages}
    blocks_by_stage: dict[str, list[tuple[int, str, Mapping[str, Any]]]] = {}
    for kind, values in (
        ("list", presentation_lists),
        ("example", examples),
        ("table", comparison_tables),
    ):
        for value in values:
            stage_id = str(value.get("placement_stage_id") or "")
            blocks_by_stage.setdefault(stage_id, []).append((int(value.get("order") or 0), kind, value))
    for values in blocks_by_stage.values():
        values.sort(key=lambda item: (item[0], item[1]))

    rendered: list[str] = []
    title = str(render_notes.get("title") or "").strip()
    if title:
        rendered.append(f"## {title}")
    for section in presentation_sections:
        section_title = str(section.get("title") or "").strip()
        if section_title:
            rendered.append(f"### {section_title}")
        paragraph: list[str] = []
        for stage_id in _strings(section.get("stage_ids")):
            stage = stage_by_id.get(stage_id)
            if stage is None:
                continue
            paragraph.extend(_render_stage_sentences(stage, evidence_by_ref=evidence_by_ref))
            stage_blocks = blocks_by_stage.get(stage_id, ())
            if stage_blocks:
                if paragraph:
                    rendered.append(" ".join(paragraph))
                    paragraph = []
                for _order, kind, block in stage_blocks:
                    if kind == "list":
                        rendered.extend(_render_presentation_list(block, evidence_by_ref=evidence_by_ref))
                    elif kind == "example":
                        rendered.extend(_render_example(block, evidence_by_ref=evidence_by_ref))
                    else:
                        rendered.extend(_render_comparison_table(block, evidence_by_ref=evidence_by_ref))
        if paragraph:
            rendered.append(" ".join(paragraph))
    if observations:
        rendered.append("### Additional implementation observations")
        for observation in observations:
            text = str(observation.get("text") or "").strip()
            relevance = str(observation.get("why_it_matters") or "").strip()
            links = _render_evidence_links(_strings(observation.get("evidence_refs")), evidence_by_ref)
            rendered.append(f"- {text} **Why it matters:** {relevance} {links}".strip())
    return "\n\n".join(part for part in rendered if part.strip()).strip()


def _render_stage_sentences(stage: Mapping[str, Any], *, evidence_by_ref: Mapping[str, EvidenceItem]) -> list[str]:
    rendered: list[str] = []
    for sentence in stage.get("sentences", ()):
        if not isinstance(sentence, Mapping):
            continue
        text = str(sentence.get("text") or "").strip()
        links = _render_evidence_links(_strings(sentence.get("evidence_refs")), evidence_by_ref)
        if text:
            rendered.append(f"{text} {links}".strip())
    return rendered


def _render_presentation_list(value: Mapping[str, Any], *, evidence_by_ref: Mapping[str, EvidenceItem]) -> list[str]:
    rendered: list[str] = []
    title = str(value.get("title") or "").strip()
    if title:
        rendered.append(f"#### {title}")
    ordered = bool(value.get("ordered"))
    for index, item in enumerate(value.get("items", ()), start=1):
        if not isinstance(item, Mapping):
            continue
        marker = f"{index}." if ordered else "-"
        links = _render_evidence_links(_strings(item.get("evidence_refs")), evidence_by_ref)
        rendered.append(f"{marker} {str(item.get('text') or '').strip()} {links}".strip())
    return rendered


def _render_example(value: Mapping[str, Any], *, evidence_by_ref: Mapping[str, EvidenceItem]) -> list[str]:
    title = str(value.get("title") or "Example").strip()
    provenance = str(value.get("provenance") or "")
    language = str(value.get("language") or "text").strip().replace("`", "") or "text"
    content = str(value.get("content") or "").rstrip()
    rendered = [f"#### {title}"]
    if provenance == "conceptual_from_evidence":
        rendered.append("*Conceptual example synthesized from the selected evidence.*")
    rendered.extend((f"```{language}", content, "```"))
    links = _render_evidence_links(_strings(value.get("evidence_refs")), evidence_by_ref)
    if links:
        rendered.append(links)
    return rendered


def _render_comparison_table(value: Mapping[str, Any], *, evidence_by_ref: Mapping[str, EvidenceItem]) -> list[str]:
    title = str(value.get("title") or "Comparison").strip()
    columns = [str(column) for column in value.get("columns", ())]
    rendered = [f"#### {title}"]
    rendered.append("| " + " | ".join(_escape_table_cell(column) for column in (*columns, "Sources")) + " |")
    rendered.append("| " + " | ".join("---" for _ in (*columns, "Sources")) + " |")
    for row in value.get("rows", ()):
        if not isinstance(row, Mapping):
            continue
        cells = [str(cell) for cell in row.get("cells", ())]
        links = _render_evidence_links(_strings(row.get("evidence_refs")), evidence_by_ref)
        rendered.append("| " + " | ".join(_escape_table_cell(cell) for cell in (*cells, links)) + " |")
    return rendered


def _render_evidence_links(refs: Sequence[str], evidence_by_ref: Mapping[str, EvidenceItem]) -> str:
    links: list[str] = []
    for ref in refs:
        item = evidence_by_ref.get(ref)
        if item is None:
            continue
        link = _evidence_link(item)
        if link not in links:
            links.append(link)
    return " ".join(links)


def _escape_table_cell(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


def _render_notes(value: Any) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {key: str(value.get(key) or "").strip()[:500] for key in ("title", "summary") if str(value.get(key) or "").strip()}


def _concept_definitions(value: Any, *, allowed_refs: set[str]) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    output: list[Mapping[str, Any]] = []
    for raw in value:
        if not isinstance(raw, Mapping):
            continue
        label = str(raw.get("label") or "").strip()
        description = str(raw.get("description") or "").strip()
        refs = tuple(ref for ref in _strings(raw.get("evidence_refs")) if ref in allowed_refs)
        if label and description:
            output.append({"label": label[:120], "description": description[:600], "evidence_refs": list(refs)})
    return tuple(output[:12])


def _source_attributions(value: Any, *, markdown: str, allowed_refs: set[str]) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    output: list[Mapping[str, Any]] = []
    for raw in value:
        if not isinstance(raw, Mapping):
            continue
        quote = str(raw.get("quote") or "").strip()
        source_kind = str(raw.get("source_kind") or "").strip()
        source_ref = str(raw.get("source_ref") or "").strip()
        note = str(raw.get("note") or "").strip()
        if not quote or quote not in markdown or not source_kind or not source_ref or not note:
            continue
        if source_kind in {"source_code", "connected_source"} and source_ref not in allowed_refs:
            continue
        output.append({"quote": quote[:500], "source_kind": source_kind[:80], "source_ref": source_ref[:500], "note": note[:500]})
    return tuple(output[:16])


def _next_checks(value: Any) -> tuple[Mapping[str, str], ...]:
    if not isinstance(value, list):
        return ()
    output: list[Mapping[str, str]] = []
    for raw in value:
        if not isinstance(raw, Mapping):
            continue
        item = {key: str(raw.get(key) or "").strip()[:600] for key in ("scenario", "action", "if_result", "then_interpretation")}
        if all(item.values()):
            output.append(item)
    return tuple(output[:3])


def _response_format(
    flow_plan: IntentFlowPlan,
    *,
    model_stage_ids: Sequence[str] | None = None,
) -> Mapping[str, Any]:
    stage_ids = list(model_stage_ids or flow_plan.contract_stage_ids)
    intent_values = [intent.value for intent in flow_plan.intents]
    stem_values = sorted({stem for contract in flow_plan.contracts for stem in contract.question.stem_families})
    string_array = {"type": "array", "items": {"type": "string"}}
    sentence_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "kind": {"type": "string", "enum": ["code_claim", "connective"]},
            "evidence_refs": string_array,
        },
        "required": ["text", "kind", "evidence_refs"],
        "additionalProperties": False,
    }
    grounded_item_schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}, "evidence_refs": string_array},
        "required": ["text", "evidence_refs"],
        "additionalProperties": False,
    }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "intent_composed_explanation",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "ordered_stage_ids": {
                        "type": "array",
                        "items": {"type": "string", "enum": stage_ids},
                        "minItems": len(stage_ids),
                        "maxItems": len(stage_ids),
                    },
                    "stages": {
                        "type": "array",
                        "minItems": len(stage_ids),
                        "maxItems": len(stage_ids),
                        "items": {
                            "type": "object",
                            "properties": {
                                "stage_id": {"type": "string", "enum": stage_ids},
                                "title": {"type": "string"},
                                "sentences": {"type": "array", "items": sentence_schema, "minItems": 1, "maxItems": 2},
                            },
                            "required": ["stage_id", "title", "sentences"],
                            "additionalProperties": False,
                        },
                    },
                    "presentation_sections": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": len(stage_ids),
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "title": {"type": "string"},
                                "stage_ids": {
                                    "type": "array",
                                    "items": {"type": "string", "enum": stage_ids},
                                    "minItems": 1,
                                },
                            },
                            "required": ["id", "title", "stage_ids"],
                            "additionalProperties": False,
                        },
                    },
                    "presentation_lists": {
                        "type": "array",
                        "maxItems": 4,
                        "items": {
                            "type": "object",
                            "properties": {
                                "placement_stage_id": {"type": "string", "enum": stage_ids},
                                "order": {"type": "integer", "minimum": 0, "maximum": 20},
                                "title": {"type": "string"},
                                "ordered": {"type": "boolean"},
                                "items": {"type": "array", "items": grounded_item_schema, "minItems": 1, "maxItems": 8},
                            },
                            "required": ["placement_stage_id", "order", "title", "ordered", "items"],
                            "additionalProperties": False,
                        },
                    },
                    "examples": {
                        "type": "array",
                        "maxItems": 2,
                        "items": {
                            "type": "object",
                            "properties": {
                                "placement_stage_id": {"type": "string", "enum": stage_ids},
                                "order": {"type": "integer", "minimum": 0, "maximum": 20},
                                "title": {"type": "string"},
                                "language": {"type": "string"},
                                "content": {"type": "string"},
                                "provenance": {"type": "string", "enum": ["direct", "conceptual_from_evidence"]},
                                "evidence_refs": string_array,
                            },
                            "required": ["placement_stage_id", "order", "title", "language", "content", "provenance", "evidence_refs"],
                            "additionalProperties": False,
                        },
                    },
                    "comparison_tables": {
                        "type": "array",
                        "maxItems": 2,
                        "items": {
                            "type": "object",
                            "properties": {
                                "placement_stage_id": {"type": "string", "enum": stage_ids},
                                "order": {"type": "integer", "minimum": 0, "maximum": 20},
                                "title": {"type": "string"},
                                "columns": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 6},
                                "rows": {
                                    "type": "array",
                                    "minItems": 2,
                                    "maxItems": 10,
                                    "items": {
                                        "type": "object",
                                        "properties": {"cells": string_array, "evidence_refs": string_array},
                                        "required": ["cells", "evidence_refs"],
                                        "additionalProperties": False,
                                    },
                                },
                            },
                            "required": ["placement_stage_id", "order", "title", "columns", "rows"],
                            "additionalProperties": False,
                        },
                    },
                    "additional_implementation_observations": {
                        "type": "array",
                        "maxItems": 3,
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"},
                                "why_it_matters": {"type": "string"},
                                "evidence_refs": string_array,
                            },
                            "required": ["text", "why_it_matters", "evidence_refs"],
                            "additionalProperties": False,
                        },
                    },
                    "understanding_checks": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 3,
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "intent": {"type": "string", "enum": intent_values},
                                "target_stage_ids": string_array,
                                "prerequisite_stage_ids": string_array,
                                "stem_family": {"type": "string", "enum": stem_values},
                                "reasoning_focus": {"type": "string", "maxLength": QUESTION_FIELD_LIMITS["reasoning_focus"]},
                                "selection_reason": {"type": "string", "maxLength": QUESTION_FIELD_LIMITS["selection_reason"]},
                                "question": {"type": "string", "maxLength": QUESTION_FIELD_LIMITS["question"]},
                                "expected_answer_points": string_array,
                                "hints": _hint_item_schema(),
                                "evidence_refs": string_array,
                            },
                            "required": ["id", "intent", "target_stage_ids", "prerequisite_stage_ids", "stem_family", "reasoning_focus", "selection_reason", "question", "expected_answer_points", "hints", "evidence_refs"],
                            "additionalProperties": False,
                        },
                    },
                    "concept_definitions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"label": {"type": "string"}, "description": {"type": "string"}, "evidence_refs": string_array},
                            "required": ["label", "description", "evidence_refs"],
                            "additionalProperties": False,
                        },
                    },
                    "source_attributions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"quote": {"type": "string"}, "source_kind": {"type": "string"}, "source_ref": {"type": "string"}, "note": {"type": "string"}},
                            "required": ["quote", "source_kind", "source_ref", "note"],
                            "additionalProperties": False,
                        },
                    },
                    "next_checks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"scenario": {"type": "string"}, "action": {"type": "string"}, "if_result": {"type": "string"}, "then_interpretation": {"type": "string"}},
                            "required": ["scenario", "action", "if_result", "then_interpretation"],
                            "additionalProperties": False,
                        },
                    },
                    "render_notes": {
                        "type": "object",
                        "properties": {"title": {"type": "string"}, "summary": {"type": "string"}},
                        "required": ["title", "summary"],
                        "additionalProperties": False,
                    },
                },
                "required": [
                    "ordered_stage_ids",
                    "stages",
                    "presentation_sections",
                    "presentation_lists",
                    "examples",
                    "comparison_tables",
                    "additional_implementation_observations",
                    "understanding_checks",
                    "concept_definitions",
                    "source_attributions",
                    "next_checks",
                    "render_notes",
                ],
                "additionalProperties": False,
            },
        },
    }


def _compact_evidence(item: EvidenceItem) -> dict[str, Any]:
    return {
        "source_id": item.source_id,
        "source_category": item.source_category.value,
        "path": str(item.metadata.get("path") or _path_from_source_id(item.source_id)),
        "line_range": str(item.metadata.get("line_range") or _line_range_from_source_id(item.source_id)),
        "claim_supported": str(item.metadata.get("claim_supported") or ""),
        "snippet": _compact_snippet(item.snippet),
    }


def _selected_evidence_connections(
    retrieval_result: RetrievalResult,
    *,
    allowed_refs: set[str],
) -> list[dict[str, Any]]:
    """Return only graph edges whose two endpoints are visible to generation."""
    graph = retrieval_result.retrieval_summary.get("evidence_connections")
    if not isinstance(graph, Mapping):
        return []
    raw_connections = graph.get("connections")
    if not isinstance(raw_connections, list):
        return []
    output: list[dict[str, Any]] = []
    for raw in raw_connections:
        if not isinstance(raw, Mapping):
            continue
        source_ref = str(raw.get("source_ref") or "").strip()
        target_ref = str(raw.get("target_ref") or "").strip()
        if source_ref not in allowed_refs or target_ref not in allowed_refs:
            continue
        output.append(
            {
                "source_ref": source_ref,
                "target_ref": target_ref,
                "relationship_kind": str(raw.get("relationship_kind") or "").strip(),
                "label": str(raw.get("label") or "").strip(),
                "description": str(raw.get("description") or "").strip(),
                "grounding": str(raw.get("grounding") or "").strip(),
                "confidence": str(raw.get("confidence") or "").strip(),
            }
        )
    return output


def _evidence_link(item: EvidenceItem) -> str:
    label = _evidence_label(item)
    path = str(item.metadata.get("path") or _path_from_source_id(item.source_id) or item.source_id)
    line_range = str(item.metadata.get("line_range") or _line_range_from_source_id(item.source_id))
    href = path.replace("\\", "/").replace(" ", "%20")
    if line_range:
        href = f"{href}#{line_range}"
    return f"[{label}]({href})"


def _evidence_label(item: EvidenceItem) -> str:
    path = str(item.metadata.get("path") or _path_from_source_id(item.source_id) or item.source_id)
    line_range = str(item.metadata.get("line_range") or _line_range_from_source_id(item.source_id))
    return f"{path}:{line_range}" if line_range and line_range not in path else path


def _path_from_source_id(source_id: str) -> str:
    for prefix in ("workspace:", "repo-pre:"):
        if source_id.startswith(prefix):
            return source_id[len(prefix):].split(":L", 1)[0]
    return ""


def _line_range_from_source_id(source_id: str) -> str:
    return "L" + source_id.rsplit(":L", 1)[1] if ":L" in source_id else ""


def _compact_snippet(snippet: str, *, max_lines: int = 12, max_line_length: int = 200) -> str:
    lines = [line.rstrip() for line in snippet.replace("```", "'''").splitlines() if line.strip()]
    output = [line[:max_line_length] for line in lines[:max_lines]]
    if len(lines) > len(output):
        output.append("...")
    return "\n".join(output)


def _strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _strings_preserve_empty(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item).strip() for item in value)
