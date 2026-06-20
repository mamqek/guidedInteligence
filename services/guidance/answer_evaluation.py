from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from services.llm.json_completion import complete_json


PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "answer_evaluation.md"


@dataclass(frozen=True)
class AnswerEvaluation:
    question_id: str
    status: str
    matched_points: tuple[str, ...]
    missing_points: tuple[str, ...]
    feedback: str
    next_turn: str
    repair_focus: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "status": self.status,
            "matched_points": list(self.matched_points),
            "missing_points": list(self.missing_points),
            "feedback": self.feedback,
            "next_turn": self.next_turn,
            "repair_focus": self.repair_focus,
        }


def evaluate_answers(
    *,
    checks: Sequence[Mapping[str, Any]],
    answers: Mapping[str, str],
    llm_config: Any,
    log_event: Any | None = None,
) -> tuple[AnswerEvaluation, ...]:
    payload = {
        "checks": [dict(check) for check in checks],
        "answers": {str(key): str(value) for key, value in answers.items()},
        "evaluation_rules": {
            "statuses": ["correct", "partial", "incorrect", "unanswered"],
            "next_turns": ["deepen", "repair", "completion"],
            "feedback_max_words": 90,
        },
    }
    response = complete_json(
        llm_config,
        (
            {"role": "system", "content": PROMPT_PATH.read_text(encoding="utf-8")},
            {"role": "user", "content": json.dumps(payload, sort_keys=True)},
        ),
        response_format=_response_format(),
        log_event=log_event,
    )
    return _validate_response(response, checks)


def _validate_response(response: Mapping[str, Any], checks: Sequence[Mapping[str, Any]]) -> tuple[AnswerEvaluation, ...]:
    allowed_ids = {str(check.get("id")) for check in checks}
    evaluations_raw = response.get("evaluations", ())
    if not isinstance(evaluations_raw, Sequence) or isinstance(evaluations_raw, (str, bytes)):
        raise RuntimeError("Answer evaluation response must include an evaluations array.")
    evaluations: list[AnswerEvaluation] = []
    for item in evaluations_raw:
        if not isinstance(item, Mapping):
            continue
        question_id = str(item.get("question_id") or "").strip()
        if question_id not in allowed_ids:
            continue
        status = str(item.get("status") or "partial").strip()
        if status not in {"correct", "partial", "incorrect", "unanswered"}:
            status = "partial"
        next_turn = str(item.get("next_turn") or ("deepen" if status == "correct" else "repair")).strip()
        if next_turn not in {"deepen", "repair", "completion"}:
            next_turn = "repair"
        evaluations.append(
            AnswerEvaluation(
                question_id=question_id,
                status=status,
                matched_points=_string_tuple(item.get("matched_points")),
                missing_points=_string_tuple(item.get("missing_points")),
                feedback=str(item.get("feedback") or "").strip()[:800],
                next_turn=next_turn,
                repair_focus=str(item.get("repair_focus") or "").strip()[:300],
            )
        )
    if len(evaluations) != len(allowed_ids):
        raise RuntimeError("Answer evaluation did not cover every understanding check.")
    return tuple(evaluations)


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _response_format() -> Mapping[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "guided_answer_evaluation",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "evaluations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "question_id": {"type": "string"},
                                "status": {"type": "string"},
                                "matched_points": {"type": "array", "items": {"type": "string"}},
                                "missing_points": {"type": "array", "items": {"type": "string"}},
                                "feedback": {"type": "string"},
                                "next_turn": {"type": "string"},
                                "repair_focus": {"type": "string"},
                            },
                            "required": [
                                "question_id",
                                "status",
                                "matched_points",
                                "missing_points",
                                "feedback",
                                "next_turn",
                                "repair_focus",
                            ],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["evaluations"],
                "additionalProperties": False,
            },
        },
    }
