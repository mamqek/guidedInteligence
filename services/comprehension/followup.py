from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from services.comprehension.models import (
    ComprehensionPlan,
    ComprehensionState,
    ConceptFamiliarity,
    PlanUnderstandingCheck,
    RepairPlan,
    plan_from_mapping,
)
from services.llm.json_completion import complete_json


PROMPT_TEMPLATE_ID = "comprehension_followup_v1"
PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "followup.md"


@dataclass(frozen=True)
class ComprehensionFollowUpResult:
    next_turn: str
    markdown: str
    revised_check: PlanUnderstandingCheck | None
    comprehension_state: ComprehensionState
    prompt_template_id: str = PROMPT_TEMPLATE_ID

    def to_dict(self) -> dict[str, Any]:
        return {
            "next_turn": self.next_turn,
            "markdown": self.markdown,
            "revised_check": self.revised_check.to_dict() if self.revised_check is not None else None,
            "comprehension_state": self.comprehension_state.to_dict(),
            "prompt_template_id": self.prompt_template_id,
        }


def generate_followup(
    *,
    comprehension_plan: Mapping[str, Any],
    checks: Sequence[Mapping[str, Any]],
    evaluations: Sequence[Mapping[str, Any]],
    answers: Mapping[str, str],
    llm_config: Any,
    log_event: Callable[[str, Mapping[str, Any]], None] | None = None,
) -> ComprehensionFollowUpResult:
    plan = plan_from_mapping(comprehension_plan)
    state = build_comprehension_state(plan=plan, checks=checks, evaluations=evaluations)
    payload = {
        "comprehension_plan": plan.to_dict(),
        "comprehension_state": state.to_dict(),
        "checks": [dict(check) for check in checks],
        "evaluations": [dict(evaluation) for evaluation in evaluations],
        "answers": {str(key): str(value) for key, value in answers.items()},
        "response_rules": {
            "repair_max_words": 350,
            "deepen_max_words": 300,
            "completion_max_words": 220,
            "do_not_repeat_full_explanation": True,
        },
    }
    if log_event is not None:
        log_event(
            "comprehension_followup_request_payload",
            {
                "prompt_template_id": PROMPT_TEMPLATE_ID,
                "payload": payload,
            },
        )
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
        log_event(
            "comprehension_followup_response_payload",
            {
                "prompt_template_id": PROMPT_TEMPLATE_ID,
                "next_turn": result.next_turn,
                "comprehension_state": result.comprehension_state.to_dict(),
            },
        )
    return result


def build_comprehension_state(
    *,
    plan: ComprehensionPlan,
    checks: Sequence[Mapping[str, Any]],
    evaluations: Sequence[Mapping[str, Any]],
) -> ComprehensionState:
    concepts_by_check = _concepts_by_check(plan, checks)
    familiarity: dict[str, ConceptFamiliarity] = {
        concept.id: ConceptFamiliarity(concept_id=concept.id, level="unknown", evidence="Concept was planned but not evaluated.")
        for concept in plan.concepts
    }
    failed_concepts: list[str] = []
    repair_focus = ""
    statuses: list[str] = []
    for evaluation in evaluations:
        question_id = str(evaluation.get("question_id") or "").strip()
        status = str(evaluation.get("status") or "partial").strip()
        statuses.append(status)
        concept_ids = concepts_by_check.get(question_id, ())
        level = _level_for_status(status)
        evidence = str(evaluation.get("feedback") or status).strip()
        for concept_id in concept_ids:
            familiarity[concept_id] = ConceptFamiliarity(concept_id=concept_id, level=level, evidence=evidence)
            if level in {"partial", "misunderstood"} and concept_id not in failed_concepts:
                failed_concepts.append(concept_id)
        if status in {"partial", "incorrect"} and not repair_focus:
            repair_focus = str(evaluation.get("repair_focus") or "").strip()
    next_stage = _next_stage(evaluations)
    repair_plan = None
    if next_stage == "repair":
        repair_plan = RepairPlan(
            failed_concept_ids=tuple(failed_concepts),
            misconception=repair_focus,
            repair_strategy=_repair_strategy(repair_focus),
            follow_up_check=plan.understanding_check,
        )
    return ComprehensionState(
        concepts_explained=tuple(concept.id for concept in plan.concepts),
        concept_familiarity=tuple(familiarity.values()),
        checks_asked=tuple(str(check.get("id") or "") for check in checks if str(check.get("id") or "").strip()),
        check_results=tuple(dict(evaluation) for evaluation in evaluations),
        current_teaching_stage=next_stage,
        repair_plan=repair_plan,
    )


def _concepts_by_check(plan: ComprehensionPlan, checks: Sequence[Mapping[str, Any]]) -> dict[str, tuple[str, ...]]:
    plan_check = plan.understanding_check
    default = plan_check.concept_ids if plan_check is not None else tuple(concept.id for concept in plan.concepts if concept.role == "core")
    mapping: dict[str, tuple[str, ...]] = {}
    for check in checks:
        check_id = str(check.get("id") or "").strip()
        refs = tuple(str(ref) for ref in check.get("evidence_refs", ()) if str(ref).strip())
        concept_ids = tuple(
            concept.id
            for concept in plan.concepts
            if refs and any(ref in concept.evidence_refs for ref in refs)
        )
        if check_id:
            mapping[check_id] = concept_ids or default
    return mapping


def _next_stage(evaluations: Sequence[Mapping[str, Any]]) -> str:
    next_turns = [str(item.get("next_turn") or "").strip() for item in evaluations]
    statuses = [str(item.get("status") or "").strip() for item in evaluations]
    if "repair" in next_turns or any(status in {"partial", "incorrect"} for status in statuses):
        return "repair"
    if "deepen" in next_turns or any(status == "correct" for status in statuses):
        return "deepen"
    return "completion"


def _level_for_status(status: str) -> str:
    if status == "correct":
        return "demonstrated"
    if status == "partial":
        return "partial"
    if status == "incorrect":
        return "misunderstood"
    return "unknown"


def _repair_strategy(repair_focus: str) -> str:
    normalized = repair_focus.lower()
    if "instead" in normalized or "vs" in normalized or "contrast" in normalized:
        return "contrast"
    if "evidence" in normalized or "file" in normalized or "line" in normalized:
        return "evidence_revisit"
    return "concept_capsule"


def _validate_response(response: Mapping[str, Any], state: ComprehensionState) -> ComprehensionFollowUpResult:
    markdown = str(response.get("markdown") or "").strip()
    if not markdown:
        raise RuntimeError("Comprehension follow-up generation returned empty markdown.")
    next_turn = str(response.get("next_turn") or state.current_teaching_stage).strip()
    if next_turn not in {"repair", "deepen", "completion"}:
        next_turn = state.current_teaching_stage
    revised_raw = response.get("revised_check")
    revised_check = _check_from_mapping(revised_raw) if isinstance(revised_raw, Mapping) else None
    return ComprehensionFollowUpResult(
        next_turn=next_turn,
        markdown=markdown,
        revised_check=revised_check,
        comprehension_state=state,
    )


def _check_from_mapping(value: Mapping[str, Any]) -> PlanUnderstandingCheck:
    return PlanUnderstandingCheck(
        id=str(value.get("id") or "q1"),
        type=_literal(str(value.get("type") or "why"), {"prediction", "re_explanation", "trace", "why", "transfer"}, "why"),
        question=str(value.get("question") or ""),
        expected_points=tuple(str(item) for item in value.get("expected_points", ()) if str(item).strip()),
        misconceptions=tuple(str(item) for item in value.get("misconceptions", ()) if str(item).strip()),
        hidden_hints=tuple(str(item) for item in value.get("hidden_hints", ()) if str(item).strip()),
        evidence_refs=tuple(str(item) for item in value.get("evidence_refs", ()) if str(item).strip()),
        concept_ids=tuple(str(item) for item in value.get("concept_ids", ()) if str(item).strip()),
    )


def _literal(value: str, allowed: set[str], default: str) -> Any:
    return value if value in allowed else default


def _response_format() -> Mapping[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "comprehension_followup",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "next_turn": {"type": "string"},
                    "markdown": {"type": "string"},
                    "revised_check": {
                        "type": ["object", "null"],
                        "properties": {
                            "id": {"type": "string"},
                            "type": {"type": "string"},
                            "question": {"type": "string"},
                            "expected_points": {"type": "array", "items": {"type": "string"}},
                            "misconceptions": {"type": "array", "items": {"type": "string"}},
                            "hidden_hints": {"type": "array", "items": {"type": "string"}},
                            "evidence_refs": {"type": "array", "items": {"type": "string"}},
                            "concept_ids": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": [
                            "id",
                            "type",
                            "question",
                            "expected_points",
                            "misconceptions",
                            "hidden_hints",
                            "evidence_refs",
                            "concept_ids",
                        ],
                        "additionalProperties": False,
                    },
                },
                "required": ["next_turn", "markdown", "revised_check"],
                "additionalProperties": False,
            },
        },
    }
