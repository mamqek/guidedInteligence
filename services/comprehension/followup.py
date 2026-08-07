from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from services.guidance.questions import UnderstandingCheck, UnderstandingHint
from services.intent import get_intent_contract
from services.intent.models import TaskIntent
from services.llm.json_completion import complete_json


PROMPT_TEMPLATE_ID = "comprehension_followup_v2"
PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "followup.md"
QUESTION_FIELD_LIMITS = {"reasoning_focus": 300, "selection_reason": 500, "question": 800}
HINT_KINDS = ("direction", "focus", "scaffold")
HINT_TEXT_LIMIT = 500


@dataclass(frozen=True)
class TeachingState:
    stages_taught: tuple[str, ...]
    checks_asked: tuple[str, ...]
    check_results: tuple[Mapping[str, Any], ...]
    current_teaching_stage: str
    target_stage_ids: tuple[str, ...]
    missing_points: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "stages_taught": list(self.stages_taught),
            "checks_asked": list(self.checks_asked),
            "check_results": [dict(item) for item in self.check_results],
            "current_teaching_stage": self.current_teaching_stage,
            "target_stage_ids": list(self.target_stage_ids),
            "missing_points": list(self.missing_points),
        }


@dataclass(frozen=True)
class ComprehensionFollowUpResult:
    next_turn: str
    markdown: str
    revised_check: UnderstandingCheck | None
    teaching_state: TeachingState
    prompt_template_id: str = PROMPT_TEMPLATE_ID

    def to_dict(self) -> dict[str, Any]:
        return {
            "next_turn": self.next_turn,
            "markdown": self.markdown,
            "revised_check": self.revised_check.to_dict() if self.revised_check is not None else None,
            "teaching_state": self.teaching_state.to_dict(),
            "prompt_template_id": self.prompt_template_id,
        }


def generate_followup(
    *,
    answer_flow: Mapping[str, Any],
    story_flow: Sequence[Mapping[str, Any]],
    checks: Sequence[Mapping[str, Any]],
    evaluations: Sequence[Mapping[str, Any]],
    answers: Mapping[str, str],
    llm_config: Any,
    log_event: Callable[[str, Mapping[str, Any]], None] | None = None,
) -> ComprehensionFollowUpResult:
    state = build_teaching_state(answer_flow=answer_flow, checks=checks, evaluations=evaluations)
    payload = {
        "answer_flow": dict(answer_flow),
        "story_flow": [dict(stage) for stage in story_flow],
        "teaching_state": state.to_dict(),
        "checks": [dict(check) for check in checks],
        "evaluations": [dict(evaluation) for evaluation in evaluations],
        "answers": {str(key): str(value) for key, value in answers.items()},
        "question_field_limits": dict(QUESTION_FIELD_LIMITS),
        "hint_contract": {"ordered_kinds": list(HINT_KINDS), "text_max_characters": HINT_TEXT_LIMIT},
        "response_rules": {
            "repair_max_words": 350,
            "deepen_max_words": 300,
            "completion_max_words": 220,
            "do_not_repeat_full_explanation": True,
        },
    }
    if log_event is not None:
        log_event("comprehension_followup_request_payload", {"prompt_template_id": PROMPT_TEMPLATE_ID, "payload": payload})
    response = complete_json(
        llm_config,
        (
            {"role": "system", "content": PROMPT_PATH.read_text(encoding="utf-8")},
            {"role": "user", "content": json.dumps(payload, sort_keys=True)},
        ),
        response_format=_response_format(),
        log_event=log_event,
    )
    result = _validate_response(response, state)
    if log_event is not None:
        log_event("comprehension_followup_response_payload", {"prompt_template_id": PROMPT_TEMPLATE_ID, "next_turn": result.next_turn, "teaching_state": state.to_dict()})
    return result


def build_teaching_state(
    *,
    answer_flow: Mapping[str, Any],
    checks: Sequence[Mapping[str, Any]],
    evaluations: Sequence[Mapping[str, Any]],
) -> TeachingState:
    next_stage = _next_stage(evaluations)
    failed_question_ids = {
        str(item.get("question_id") or "").strip()
        for item in evaluations
        if str(item.get("status") or "").strip() in {"partial", "incorrect"}
    }
    target_stage_ids: list[str] = []
    for check in checks:
        if str(check.get("id") or "").strip() not in failed_question_ids:
            continue
        for stage_id in check.get("target_stage_ids", ()):
            value = str(stage_id).strip()
            if value and value not in target_stage_ids:
                target_stage_ids.append(value)
    missing_points = tuple(
        value
        for evaluation in evaluations
        for value in (
            str(evaluation.get("repair_focus") or "").strip(),
            *(str(item).strip() for item in evaluation.get("missing_points", ()) if str(item).strip()),
        )
        if value and str(evaluation.get("status") or "").strip() in {"partial", "incorrect"}
    )
    return TeachingState(
        stages_taught=tuple(str(item) for item in answer_flow.get("ordered_stage_ids", ()) if str(item).strip()),
        checks_asked=tuple(str(check.get("id") or "") for check in checks if str(check.get("id") or "").strip()),
        check_results=tuple(dict(item) for item in evaluations),
        current_teaching_stage=next_stage,
        target_stage_ids=tuple(target_stage_ids),
        missing_points=tuple(dict.fromkeys(missing_points)),
    )


def _next_stage(evaluations: Sequence[Mapping[str, Any]]) -> str:
    next_turns = [str(item.get("next_turn") or "").strip() for item in evaluations]
    statuses = [str(item.get("status") or "").strip() for item in evaluations]
    if "repair" in next_turns or any(status in {"partial", "incorrect"} for status in statuses):
        return "repair"
    if "deepen" in next_turns or any(status == "correct" for status in statuses):
        return "deepen"
    return "completion"


def _validate_response(response: Mapping[str, Any], state: TeachingState) -> ComprehensionFollowUpResult:
    markdown = str(response.get("markdown") or "").strip()
    if not markdown:
        raise RuntimeError("Comprehension follow-up generation returned empty markdown.")
    next_turn = str(response.get("next_turn") or "").strip()
    if next_turn not in {"repair", "deepen", "completion"}:
        raise RuntimeError("Comprehension follow-up returned an invalid next_turn.")
    revised_raw = response.get("revised_check")
    revised_check = _check_from_mapping(revised_raw) if isinstance(revised_raw, Mapping) else None
    return ComprehensionFollowUpResult(next_turn=next_turn, markdown=markdown, revised_check=revised_check, teaching_state=state)


def _check_from_mapping(value: Mapping[str, Any]) -> UnderstandingCheck:
    try:
        intent = TaskIntent(str(value.get("intent") or ""))
    except ValueError as exc:
        raise RuntimeError("Follow-up check returned an unknown intent.") from exc
    contract = get_intent_contract(intent)
    stem_family = str(value.get("stem_family") or "").strip()
    prerequisites = tuple(str(item) for item in value.get("prerequisite_stage_ids", ()) if str(item).strip())
    if stem_family not in contract.question.stem_families or prerequisites != contract.question.prerequisite_stage_ids:
        raise RuntimeError("Follow-up check does not follow its intent question contract.")
    fields = {name: str(value.get(name) or "").strip() for name in QUESTION_FIELD_LIMITS}
    if any(not text for text in fields.values()) or any(len(fields[name]) > limit for name, limit in QUESTION_FIELD_LIMITS.items()):
        raise RuntimeError("Follow-up check has a missing or overlong question field.")
    expected = tuple(str(item).strip() for item in value.get("expected_answer_points", ()) if str(item).strip())
    refs = tuple(str(item).strip() for item in value.get("evidence_refs", ()) if str(item).strip())
    raw_hints = value.get("hints")
    if not isinstance(raw_hints, list) or len(raw_hints) != len(HINT_KINDS):
        raise RuntimeError("Follow-up check lacks its three-level hint ladder.")
    hints: list[UnderstandingHint] = []
    for raw_hint, expected_kind in zip(raw_hints, HINT_KINDS):
        if not isinstance(raw_hint, Mapping):
            raise RuntimeError("Follow-up check contains an invalid hint.")
        kind = str(raw_hint.get("kind") or "").strip()
        text = str(raw_hint.get("text") or "").strip()
        if kind != expected_kind or not text or len(text) > HINT_TEXT_LIMIT:
            raise RuntimeError("Follow-up check contains an invalid hint ladder.")
        hints.append(UnderstandingHint(kind=kind, text=text))
    if len({hint.text.casefold() for hint in hints}) != len(hints) or not expected or not refs:
        raise RuntimeError("Follow-up check lacks expected answer points or evidence references.")
    return UnderstandingCheck(
        id=str(value.get("id") or "q1").strip() or "q1",
        intent=intent,
        target_stage_ids=tuple(str(item) for item in value.get("target_stage_ids", ()) if str(item).strip()),
        prerequisite_stage_ids=prerequisites,
        stem_family=stem_family,
        reasoning_focus=fields["reasoning_focus"],
        selection_reason=fields["selection_reason"],
        question=fields["question"],
        expected_answer_points=expected,
        hints=tuple(hints),
        evidence_refs=refs,
    )


def _response_format() -> Mapping[str, Any]:
    string_array = {"type": "array", "items": {"type": "string"}}
    question = {
        "type": ["object", "null"],
        "properties": {
            "id": {"type": "string"},
            "intent": {"type": "string", "enum": [intent.value for intent in TaskIntent]},
            "target_stage_ids": string_array,
            "prerequisite_stage_ids": string_array,
            "stem_family": {"type": "string"},
            "reasoning_focus": {"type": "string", "maxLength": QUESTION_FIELD_LIMITS["reasoning_focus"]},
            "selection_reason": {"type": "string", "maxLength": QUESTION_FIELD_LIMITS["selection_reason"]},
            "question": {"type": "string", "maxLength": QUESTION_FIELD_LIMITS["question"]},
            "expected_answer_points": string_array,
            "hints": {
                "type": "array",
                "minItems": 3,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "enum": list(HINT_KINDS)},
                        "text": {"type": "string", "maxLength": HINT_TEXT_LIMIT},
                    },
                    "required": ["kind", "text"],
                    "additionalProperties": False,
                },
            },
            "evidence_refs": string_array,
        },
        "required": ["id", "intent", "target_stage_ids", "prerequisite_stage_ids", "stem_family", "reasoning_focus", "selection_reason", "question", "expected_answer_points", "hints", "evidence_refs"],
        "additionalProperties": False,
    }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "comprehension_followup",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {"next_turn": {"type": "string", "enum": ["repair", "deepen", "completion"]}, "markdown": {"type": "string"}, "revised_check": question},
                "required": ["next_turn", "markdown", "revised_check"],
                "additionalProperties": False,
            },
        },
    }
