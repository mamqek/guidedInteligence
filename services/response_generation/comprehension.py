from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from core.models import ConversationState, EvidenceItem, RetrievalResult
from services.comprehension import build_comprehension_plan
from services.comprehension.models import ComprehensionPlan
from services.guidance.questions import UnderstandingCheck
from services.llm.json_completion import complete_json


PROMPT_TEMPLATE_ID = "comprehension_plan_explanation_v1"
CHECK_REPAIR_PROMPT_TEMPLATE_ID = "comprehension_understanding_check_repair_v1"
NEXT_CHECK_REPAIR_PROMPT_TEMPLATE_ID = "comprehension_next_checks_repair_v1"
SOURCE_ATTRIBUTION_REPAIR_PROMPT_TEMPLATE_ID = "comprehension_source_attribution_repair_v1"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
PROMPT_PATH = PROMPTS_DIR / "comprehension_plan_explanation.md"
UNDERSTANDING_CHECK_PROMPT_PATH = PROMPTS_DIR / "comprehension_understanding_check_contract.md"
NEXT_CHECK_PROMPT_PATH = PROMPTS_DIR / "comprehension_next_checks_contract.md"
REPAIR_COMMON_PROMPT_PATH = PROMPTS_DIR / "comprehension_repair_common.md"
CHECK_REPAIR_PROMPT_PATH = PROMPTS_DIR / "comprehension_understanding_check_repair.md"
NEXT_CHECK_REPAIR_PROMPT_PATH = PROMPTS_DIR / "comprehension_next_checks_repair.md"
SOURCE_ATTRIBUTION_REPAIR_PROMPT_PATH = PROMPTS_DIR / "comprehension_source_attribution_repair.md"
RETRIEVAL_LABEL_QUESTION_PATTERN = re.compile(
    r"\b(?:retrieved|coverage)\b"
    r"|main implementation behavior"
    r"|entry point or parsing"
    r"|state or representation"
    r"|output or emission"
    r"|supporting context"
    r"|validation or checking"
    r"|diagnostic or error"
    r"|implementation owner"
    r"|cited lines"
    r"|cited file"
    r"|line range"
    r"|\bpart matter\b",
    re.IGNORECASE,
)

LEAKED_METADATA_SECTION_PATTERN = re.compile(
    r"(?ims)^\s*(?:---\s*\n\s*)?#{1,6}\s+(?:Concept Definitions|Key Concepts|Key Terms in Context|Understanding Checks?|Understanding Check Question)\s*$.*\Z"
)
LEAKED_SOURCE_ATTRIBUTIONS_PATTERN = re.compile(
    r"(?ims)^\s*(?:#{1,6}\s+Source Attributions|\[source_attributions\]|\[Source Attributions\])\s*$\n(?:\s*[-*]\s+.*(?:\n|$))+"
)
LEAKED_CONCEPT_HEADING_SECTION_PATTERN = re.compile(
    r"(?ims)^\s*(?:---\s*\n\s*)?#{1,6}\s+Key concepts:?\s*$\n(?:\s*[-*]\s+.*(?:\n|$))+"
)
LEAKED_UNDERSTANDING_CHECK_SECTION_PATTERN = re.compile(
    r"(?ims)^\s*(?:---\s*\n\s*)?#{1,6}\s+Understanding checks?:?\s*$.*\Z"
)
LEAKED_NEXT_CHECKS_PATTERN = re.compile(
    r"(?ims)^\s*(?:---\s*\n\s*)?(?:#{1,6}\s*)?Next checks\s*:\s*$.*\Z"
)
LEAKED_ANSWER_PATH_PATTERN = re.compile(
    r"(?ims)^\s*(?:#{1,6}\s*)?(?:Explicit\s+)?Answer path(?:\s+for\s+understanding\s+check)?\s*:\s*$\n(?:\s*[-*]\s+.*(?:\n|$))+"
)
LEAKED_BOLD_CONCEPT_DEFINITIONS_PATTERN = re.compile(
    r"(?ims)^\s*(?:---\s*\n\s*)?(?:\*\*Concept definitions:\*\*|Concept definitions:|\[Concept definitions\]|Key terms:)\s*$\n(?:\s*[-*]\s+.*(?:\n|$))+"
)


@dataclass(frozen=True)
class ComprehensionGenerationResult:
    markdown: str
    used_evidence_refs: tuple[str, ...]
    render_notes: Mapping[str, str]
    answer_flow: Mapping[str, Any]
    understanding_checks: tuple[UnderstandingCheck, ...]
    comprehension_plan: ComprehensionPlan
    concept_definitions: tuple[Mapping[str, Any], ...] = ()
    source_attributions: tuple[Mapping[str, Any], ...] = ()
    next_checks: tuple[Mapping[str, str], ...] = ()
    next_check_requirement: Mapping[str, Any] = field(default_factory=dict)
    prompt_template_id: str = PROMPT_TEMPLATE_ID


def generate_comprehension_explanation(
    *,
    state: ConversationState,
    retrieval_result: RetrievalResult,
    llm_config: Any,
    assistance_mode: str = "teach",
    log_warning: Callable[[Mapping[str, Any]], None] | None = None,
    log_event: Callable[[str, Mapping[str, Any]], None] | None = None,
) -> ComprehensionGenerationResult:
    plan = build_comprehension_plan(
        user_prompt=state.user_input,
        retrieval_result=retrieval_result,
        assistance_mode=assistance_mode,
    )
    concept_definition_targets = _concept_definition_targets(state.user_input, retrieval_result.evidence[:8])
    next_check_requirement = _next_check_requirement(plan=plan, retrieval_result=retrieval_result)
    payload = {
        "user_prompt": state.user_input,
        "retrieval_sufficient": retrieval_result.sufficient,
        "coverage_status": retrieval_result.coverage_status,
        "assistance_mode": assistance_mode,
        "comprehension_plan": plan.to_dict(),
        "next_check_requirement": next_check_requirement,
        "concept_definition_targets": concept_definition_targets,
        "evidence": [_compact_evidence(item) for item in retrieval_result.evidence[:8]],
        "citation_rules": {
            "allowed_refs": [item.source_id for item in retrieval_result.evidence[:8]],
            "allowed_links": [_evidence_link(item) for item in retrieval_result.evidence[:8]],
        },
    }
    if log_event is not None:
        log_event(
            "comprehension_generation_request_payload",
            {
                "prompt_template_id": PROMPT_TEMPLATE_ID,
                "payload": payload,
            },
        )
    response = complete_json(
        llm_config,
        (
            {"role": "system", "content": _compose_generation_prompt(next_check_requirement=next_check_requirement)},
            {"role": "user", "content": json.dumps(payload, sort_keys=True)},
        ),
        response_format=_response_format(),
        log_warning=log_warning,
        log_event=log_event,
    )
    result = _validate_response(
        response,
        retrieval_result.evidence,
        plan,
        concept_definition_targets=concept_definition_targets,
        repair_llm_config=llm_config,
        repair_context={
            "user_prompt": state.user_input,
            "assistance_mode": assistance_mode,
            "coverage_status": retrieval_result.coverage_status,
            "retrieval_sufficient": retrieval_result.sufficient,
            "comprehension_plan": plan.to_dict(),
            "next_check_requirement": next_check_requirement,
            "evidence": [_compact_evidence(item) for item in retrieval_result.evidence[:8]],
        },
        log_event=log_event,
        log_warning=log_warning,
    )
    if log_event is not None:
        log_event(
            "comprehension_generation_response_payload",
            {
                "prompt_template_id": PROMPT_TEMPLATE_ID,
                "used_evidence_refs": list(result.used_evidence_refs),
                "comprehension_plan": plan.to_dict(),
            },
        )
    return result


def prompt_template_id() -> str:
    return PROMPT_TEMPLATE_ID


def _read_prompt(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _compose_repair_prompt(path: Path) -> str:
    parts = [_read_prompt(REPAIR_COMMON_PROMPT_PATH)]
    if path == CHECK_REPAIR_PROMPT_PATH:
        parts.append(_read_prompt(UNDERSTANDING_CHECK_PROMPT_PATH))
    elif path == NEXT_CHECK_REPAIR_PROMPT_PATH:
        parts.append(_read_prompt(NEXT_CHECK_PROMPT_PATH))
    parts.append(_read_prompt(path))
    return "\n\n".join(parts)


def _compose_generation_prompt(*, next_check_requirement: Mapping[str, Any]) -> str:
    parts = [_read_prompt(PROMPT_PATH), _read_prompt(UNDERSTANDING_CHECK_PROMPT_PATH)]
    if bool(next_check_requirement.get("required")):
        parts.append(_read_prompt(NEXT_CHECK_PROMPT_PATH))
    return "\n\n".join(parts)


def _validate_response(
    response: Mapping[str, Any],
    evidence: Sequence[EvidenceItem],
    plan: ComprehensionPlan,
    *,
    concept_definition_targets: Sequence[str] = (),
    repair_llm_config: Any | None = None,
    repair_context: Mapping[str, Any] | None = None,
    log_event: Callable[[str, Mapping[str, Any]], None] | None = None,
    log_warning: Callable[[Mapping[str, Any]], None] | None = None,
) -> ComprehensionGenerationResult:
    markdown = _sanitize_comprehension_markdown(str(response.get("markdown") or "").strip())
    if not markdown:
        raise RuntimeError("Comprehension explanation generation returned empty markdown.")
    allowed_refs = {item.source_id for item in evidence}
    used_refs: list[str] = []
    for ref in response.get("used_evidence_refs", ()):
        ref_text = str(ref).strip()
        if ref_text in allowed_refs and ref_text not in used_refs:
            used_refs.append(ref_text)
    answer_flow = _answer_flow_from_response(response.get("answer_flow"), allowed_refs=allowed_refs)
    if not answer_flow:
        raise RuntimeError("Comprehension explanation generation returned no valid answer_flow.")
    checks, rejected, raw_count = _collect_checks_from_response(
        response.get("understanding_checks"),
        markdown=markdown,
        plan=plan,
        allowed_refs=allowed_refs,
        answer_flow=answer_flow,
    )
    if not checks and repair_llm_config is not None:
        if log_event is not None:
            log_event(
                "comprehension_understanding_checks_rejected",
                {
                    "rejected": rejected[:5],
                    "raw_count": raw_count,
                    "repair_attempted": True,
                },
            )
        checks = _repair_understanding_checks(
            markdown=markdown,
            rejected=rejected,
            allowed_refs=allowed_refs,
            plan=plan,
            repair_context=repair_context or {},
            answer_flow=answer_flow,
            llm_config=repair_llm_config,
            log_event=log_event,
            log_warning=log_warning,
        )
    if not checks:
        if log_event is not None:
            log_event(
                "comprehension_understanding_checks_rejected",
                {
                    "rejected": rejected[:5],
                    "raw_count": raw_count,
                    "repair_attempted": False,
                },
            )
        raise RuntimeError("Comprehension explanation generation returned no valid model-generated understanding checks.")
    concept_definitions = _concept_definitions_from_response(
        response.get("concept_definitions"),
        markdown=markdown,
        allowed_refs=allowed_refs,
        allowed_labels=set(concept_definition_targets),
    )
    source_attributions = _source_attributions_from_response(
        response.get("source_attributions"),
        markdown=markdown,
        allowed_refs=allowed_refs,
    )
    raw_source_attributions = response.get("source_attributions")
    if (
        not source_attributions
        and isinstance(raw_source_attributions, list)
        and raw_source_attributions
        and repair_llm_config is not None
    ):
        source_attributions = _repair_source_attributions(
            markdown=markdown,
            repair_context=repair_context or {},
            allowed_refs=allowed_refs,
            llm_config=repair_llm_config,
            log_event=log_event,
            log_warning=log_warning,
        )
    next_check_requirement = _coerce_next_check_requirement(repair_context.get("next_check_requirement") if repair_context else None)
    required_next_check_count = int(next_check_requirement.get("min_checks") or 0)
    next_checks = _next_checks_from_response(response.get("next_checks")) if required_next_check_count else ()
    if required_next_check_count and len(next_checks) < required_next_check_count and repair_llm_config is not None:
        next_checks = _repair_next_checks(
            markdown=markdown,
            generated_next_checks=response.get("next_checks"),
            repair_context=repair_context or {},
            llm_config=repair_llm_config,
            log_event=log_event,
            log_warning=log_warning,
        )
    if required_next_check_count and len(next_checks) < required_next_check_count:
        raise RuntimeError("Comprehension explanation generation marked an external or unverified trigger but returned no structured next checks.")
    render_notes_raw = response.get("render_notes")
    render_notes: dict[str, str] = {}
    if isinstance(render_notes_raw, Mapping):
        for key in ("title", "summary"):
            value = str(render_notes_raw.get(key) or "").strip()
            if value:
                render_notes[key] = value[:500]
    return ComprehensionGenerationResult(
        markdown=markdown,
        used_evidence_refs=tuple(used_refs) or tuple(item.source_id for item in evidence[:4]),
        render_notes=render_notes,
        answer_flow=answer_flow,
        understanding_checks=checks,
        comprehension_plan=plan,
        concept_definitions=concept_definitions,
        source_attributions=source_attributions,
        next_checks=next_checks,
        next_check_requirement=next_check_requirement,
    )


def _sanitize_comprehension_markdown(markdown: str) -> str:
    replacements = {
        "main implementation behavior": "source declaration",
        "output or emission": "build output",
        "state or representation": "library declaration shape",
        "supporting context": "supporting declaration context",
        "entry point or parsing": "compiler selection point",
    }
    sanitized = markdown
    for original, replacement in replacements.items():
        sanitized = re.sub(re.escape(original), replacement, sanitized, flags=re.IGNORECASE)
    sanitized = LEAKED_ANSWER_PATH_PATTERN.sub("", sanitized).rstrip()
    sanitized = LEAKED_SOURCE_ATTRIBUTIONS_PATTERN.sub("", sanitized).rstrip()
    sanitized = LEAKED_CONCEPT_HEADING_SECTION_PATTERN.sub("", sanitized).rstrip()
    sanitized = LEAKED_UNDERSTANDING_CHECK_SECTION_PATTERN.sub("", sanitized).rstrip()
    sanitized = LEAKED_NEXT_CHECKS_PATTERN.sub("", sanitized).rstrip()
    sanitized = LEAKED_BOLD_CONCEPT_DEFINITIONS_PATTERN.sub("", sanitized).rstrip()
    sanitized = LEAKED_METADATA_SECTION_PATTERN.sub("", sanitized).rstrip()
    sanitized = re.sub(
        r"(?im)^\s*Concept definitions are provided[^.\n]*(?:\.\s*)?$",
        "",
        sanitized,
    ).rstrip()
    sanitized = _dedupe_repeated_absence_caveats(sanitized)
    return sanitized


def _dedupe_repeated_absence_caveats(markdown: str) -> str:
    absence_markers = (
        "does not show",
        "do not show",
        "does not explicitly",
        "do not explicitly",
        "not explicitly",
        "not shown",
        "not confirm",
        "not confirmed",
        "no explicit",
    )
    output: list[str] = []
    seen_absence_terms: set[str] = set()
    in_final_absence_section = False
    for line in markdown.splitlines():
        normalized_heading = line.strip().strip("#").strip().lower()
        if normalized_heading.startswith("what is not shown") or normalized_heading.startswith("not shown"):
            in_final_absence_section = True
            output.append(line)
            continue
        if line.lstrip().startswith("#"):
            in_final_absence_section = False
        if in_final_absence_section or not line.strip():
            output.append(line)
            continue
        kept_sentences: list[str] = []
        for sentence in _split_sentences_preserving_punctuation(line):
            lowered = sentence.lower()
            if any(marker in lowered for marker in absence_markers):
                terms = _absence_caveat_terms(lowered)
                if terms and terms & seen_absence_terms:
                    continue
                seen_absence_terms.update(terms)
            kept_sentences.append(sentence)
        cleaned_line = "".join(kept_sentences).strip()
        if cleaned_line:
            output.append(cleaned_line)
    return "\n".join(output).strip()


def _split_sentences_preserving_punctuation(text: str) -> list[str]:
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])(\s+)", text)
    sentences: list[str] = []
    current = ""
    for part in parts:
        current += part
        if re.search(r"[.!?]\s*$", current):
            sentences.append(current)
            current = ""
    if current:
        sentences.append(current)
    return sentences


def _absence_caveat_terms(text: str) -> set[str]:
    stop_words = {
        "the",
        "this",
        "that",
        "these",
        "those",
        "snippet",
        "snippets",
        "current",
        "code",
        "show",
        "shows",
        "shown",
        "mention",
        "explicitly",
        "explicit",
        "handling",
        "checks",
        "support",
    }
    return {
        token
        for token in re.findall(r"\b[A-Za-z][A-Za-z0-9_]{3,}\b", text)
        if token not in stop_words
    }


def _concept_definitions_from_response(
    value: Any,
    *,
    markdown: str,
    allowed_refs: set[str],
    allowed_labels: set[str],
) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    definitions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, Mapping):
            continue
        label = str(item.get("label") or "").strip()
        description = str(item.get("description") or "").strip()
        if not label or not description:
            continue
        if allowed_labels and label not in allowed_labels:
            continue
        if _is_retrieval_role_label(label):
            continue
        key = label.casefold()
        if key in seen:
            continue
        if label not in markdown:
            continue
        refs = tuple(ref for ref in _string_tuple(item.get("evidence_refs")) if ref in allowed_refs)
        definitions.append(
            {
                "label": label[:80],
                "description": description[:320],
                "evidence_refs": list(refs[:3]),
            }
        )
        seen.add(key)
        if len(definitions) >= 12:
            break
    return tuple(definitions)


def _source_attributions_from_response(
    value: Any,
    *,
    markdown: str,
    allowed_refs: set[str],
) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    attributions: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in value:
        if not isinstance(item, Mapping):
            continue
        quote = str(item.get("quote") or "").strip()
        source_kind = str(item.get("source_kind") or "").strip()
        source_ref = str(item.get("source_ref") or "").strip()
        note = str(item.get("note") or "").strip()
        if not quote or not source_kind or quote not in markdown:
            continue
        if source_kind in {"source_code", "repo_docs", "local_notes", "notebooklm", "connected_source"} and source_ref not in allowed_refs:
            continue
        key = (quote.casefold(), source_kind.casefold(), source_ref)
        if key in seen:
            continue
        attributions.append(
            {
                "quote": quote[:180],
                "source_kind": source_kind[:80],
                "source_ref": source_ref[:220],
                "note": note[:320],
            }
        )
        seen.add(key)
        if len(attributions) >= 16:
            break
    return tuple(attributions)


def _next_checks_from_response(value: Any) -> tuple[Mapping[str, str], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    checks: list[dict[str, str]] = []
    seen_actions: set[str] = set()
    seen_scenarios: set[str] = set()
    for item in value:
        if not isinstance(item, Mapping):
            continue
        scenario = str(item.get("scenario") or "").strip()
        action = str(item.get("action") or "").strip()
        if_result = str(item.get("if_result") or "").strip()
        then_interpretation = str(item.get("then_interpretation") or "").strip()
        if not scenario or not action or not if_result or not then_interpretation:
            continue
        action_key = " ".join(action.casefold().split())
        scenario_key = " ".join(scenario.casefold().split())
        if action_key in seen_actions or scenario_key in seen_scenarios:
            continue
        checks.append(
            {
                "scenario": scenario[:120],
                "action": action[:320],
                "if_result": if_result[:320],
                "then_interpretation": then_interpretation[:420],
            }
        )
        seen_actions.add(action_key)
        seen_scenarios.add(scenario_key)
        if len(checks) >= 4:
            break
    return tuple(checks)


def _answer_flow_from_response(value: Any, *, allowed_refs: set[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    symptom = str(value.get("symptom") or "").strip()
    evidence_point = str(value.get("evidence") or "").strip()
    cause = str(value.get("cause") or "").strip()
    tested_concepts = _string_tuple(value.get("tested_concepts"))
    refs = tuple(ref for ref in _string_tuple(value.get("evidence_refs")) if ref in allowed_refs)
    if not symptom or not evidence_point or not cause or not tested_concepts or not refs:
        return {}
    return {
        "symptom": symptom[:500],
        "evidence": evidence_point[:500],
        "cause": cause[:650],
        "tested_concepts": list(tested_concepts[:6]),
        "evidence_refs": list(refs[:6]),
    }


def _next_check_requirement(*, plan: ComprehensionPlan, retrieval_result: RetrievalResult) -> dict[str, Any]:
    summary = retrieval_result.retrieval_summary if isinstance(retrieval_result.retrieval_summary, Mapping) else {}
    uncertainties = _string_tuple(summary.get("uncertainties"))
    if uncertainties:
        return {
            "mode": "bounded_inference",
            "required": True,
            "min_checks": 2,
            "reason": "The retrieval result reports unresolved uncertainty outside the selected evidence.",
            "signals": {"uncertainties": list(uncertainties[:4])},
        }
    if not retrieval_result.evidence:
        return {
            "mode": "insufficient",
            "required": True,
            "min_checks": 2,
            "reason": "Retrieval selected no evidence.",
            "signals": {"coverage_status": retrieval_result.coverage_status, "retrieval_sufficient": retrieval_result.sufficient},
        }
    return {
        "mode": "direct",
        "required": False,
        "min_checks": 0,
        "reason": "Selected evidence is sufficient and no unresolved retrieval uncertainty was reported.",
        "signals": {},
    }


def _coerce_next_check_requirement(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        return {"mode": "direct", "required": False, "min_checks": 0, "reason": "", "signals": {}}
    min_checks = value.get("min_checks")
    try:
        parsed_min = int(min_checks)
    except (TypeError, ValueError):
        parsed_min = 0
    return {
        "mode": str(value.get("mode") or "direct"),
        "required": bool(value.get("required")),
        "min_checks": max(0, min(parsed_min, 4)),
        "reason": str(value.get("reason") or ""),
        "signals": value.get("signals") if isinstance(value.get("signals"), Mapping) else {},
    }


def _concept_definition_targets(user_prompt: str, evidence: Sequence[EvidenceItem]) -> list[str]:
    ordered: list[str] = []
    text = "\n".join((user_prompt, *(item.snippet for item in evidence), *(str(item.metadata.get("path") or "") for item in evidence)))
    high_signal_terms = (
        "ArrayBuffer",
        "ArrayBufferView",
        "DataView",
        "Int16Array",
        "lib.d.ts",
        "lib.es6.d.ts",
        "es6.d.ts",
        "extensions.d.ts",
        "src/lib/es6.d.ts",
        "src/lib/extensions.d.ts",
        "bin/lib.d.ts",
        "Jakefile.js",
        "getDefaultLibFileName",
    )
    for term in high_signal_terms:
        if term in text and term not in ordered:
            ordered.append(term)
    for item in evidence:
        path = str(item.metadata.get("path") or _path_from_source_id(item.source_id) or "").strip()
        if path and path not in ordered:
            ordered.append(path)
    return ordered[:16]


def _is_retrieval_role_label(label: str) -> bool:
    normalized = re.sub(r"[_\s/-]+", " ", label).strip().casefold()
    return normalized in {
        "entry point or parsing",
        "entry or parsing",
        "state or representation",
        "implementation owner",
        "validation or checking",
        "diagnostic or error",
        "output or emission",
        "test or expected behavior",
        "supporting context",
    }


def _checks_from_response(
    value: Any,
    *,
    markdown: str,
    plan: ComprehensionPlan,
    allowed_refs: set[str],
    answer_flow: Mapping[str, Any],
    log_event: Callable[[str, Mapping[str, Any]], None] | None = None,
) -> tuple[UnderstandingCheck, ...]:
    checks, rejected, raw_count = _collect_checks_from_response(
        value,
        markdown=markdown,
        plan=plan,
        allowed_refs=allowed_refs,
        answer_flow=answer_flow,
    )
    if checks:
        return checks
    if log_event is not None:
        log_event(
            "comprehension_understanding_checks_rejected",
            {
                "rejected": rejected[:5],
                "raw_count": raw_count,
                "repair_attempted": False,
            },
        )
    raise RuntimeError("Comprehension explanation generation returned no valid model-generated understanding checks.")


def _collect_checks_from_response(
    value: Any,
    *,
    markdown: str,
    plan: ComprehensionPlan,
    allowed_refs: set[str],
    answer_flow: Mapping[str, Any],
) -> tuple[tuple[UnderstandingCheck, ...], list[dict[str, Any]], int]:
    checks: list[UnderstandingCheck] = []
    rejected: list[dict[str, Any]] = []
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, Mapping):
                rejected.append({"reason": "not_mapping"})
                continue
            refs = tuple(ref for ref in _string_tuple(item.get("evidence_refs")) if ref in allowed_refs)
            points = _string_tuple(item.get("expected_answer_points"))
            tested_concepts = _string_tuple(item.get("tested_concepts"))
            answer_point_map = _answer_point_map_from_response(item.get("answer_point_map"))
            question = str(item.get("question") or "").strip()
            hint = str(item.get("hint") or "").strip()
            if not refs or not points or not question or not hint:
                rejected.append({"reason": "missing_required_fields", "question": question[:200]})
                continue
            grounding_error = _check_grounding_contract(
                question=question,
                tested_concepts=tested_concepts,
                answer_point_map=answer_point_map,
                expected_points=points,
                plan=plan,
                markdown=markdown,
                answer_flow=answer_flow,
            )
            if grounding_error:
                rejected.append({"reason": grounding_error, "question": question[:200]})
                continue
            if _uses_retrieval_label_wording(question) or _uses_retrieval_label_wording(hint):
                rejected.append({"reason": "retrieval_label_wording", "question": question[:200], "hint": hint[:200]})
                continue
            checks.append(
                UnderstandingCheck(
                    id=str(item.get("id") or f"q{len(checks) + 1}").strip(),
                    role=str(item.get("role") or "comprehension_plan").strip(),
                    question_type=str(item.get("question_type") or "primary").strip(),
                    question=question[:600],
                    expected_answer_points=points[:4],
                    hint=hint[:500],
                    evidence_refs=refs[:4],
                    origin="model_generated",
                    tested_concepts=tested_concepts[:6],
                    answer_point_map=answer_point_map[:4],
                )
            )
    if checks:
        return tuple(checks[:3]), rejected, len(value) if isinstance(value, list) else 0
    return (), rejected, len(value) if isinstance(value, list) else 0


def _repair_understanding_checks(
    *,
    markdown: str,
    rejected: Sequence[Mapping[str, Any]],
    allowed_refs: set[str],
    plan: ComprehensionPlan,
    repair_context: Mapping[str, Any],
    answer_flow: Mapping[str, Any],
    llm_config: Any,
    log_event: Callable[[str, Mapping[str, Any]], None] | None = None,
    log_warning: Callable[[Mapping[str, Any]], None] | None = None,
) -> tuple[UnderstandingCheck, ...]:
    payload = {
        "user_prompt": repair_context.get("user_prompt", ""),
        "assistance_mode": repair_context.get("assistance_mode", ""),
        "coverage_status": repair_context.get("coverage_status", ""),
        "retrieval_sufficient": repair_context.get("retrieval_sufficient", False),
        "generated_markdown": markdown,
        "answer_flow": dict(answer_flow),
        "rejected_checks": [dict(item) for item in rejected[:5]],
        "allowed_refs": sorted(allowed_refs),
        "comprehension_plan": repair_context.get("comprehension_plan") or plan.to_dict(),
        "evidence": list(repair_context.get("evidence") or ()),
        "repair_rules": {
            "return_only_understanding_checks": True,
            "do_not_rewrite_markdown": True,
            "question_must_be_answerable_from_generated_markdown": True,
            "avoid_retrieval_or_evidence_label_wording": True,
            "test_semantic_chain": "symptom -> observed evidence -> cause",
        },
    }
    if log_event is not None:
        log_event(
            "comprehension_understanding_check_repair_requested",
            {
                "prompt_template_id": CHECK_REPAIR_PROMPT_TEMPLATE_ID,
                "rejected_count": len(rejected),
                "allowed_ref_count": len(allowed_refs),
                "payload": payload,
            },
        )
    response = complete_json(
        llm_config,
        (
            {"role": "system", "content": _compose_repair_prompt(CHECK_REPAIR_PROMPT_PATH)},
            {"role": "user", "content": json.dumps(payload, sort_keys=True)},
        ),
        response_format=_check_repair_response_format(),
        log_warning=log_warning,
        log_event=log_event,
    )
    checks, repair_rejected, raw_count = _collect_checks_from_response(
        response.get("understanding_checks"),
        markdown=markdown,
        plan=plan,
        allowed_refs=allowed_refs,
        answer_flow=answer_flow,
    )
    if log_event is not None:
        log_event(
            "comprehension_understanding_check_repair_received",
            {
                "prompt_template_id": CHECK_REPAIR_PROMPT_TEMPLATE_ID,
                "accepted_count": len(checks),
                "raw_count": raw_count,
                "rejected": repair_rejected[:5],
            },
        )
    if checks:
        return tuple(
            UnderstandingCheck(
                id=check.id,
                role=check.role,
                question_type=check.question_type,
                question=check.question,
                expected_answer_points=check.expected_answer_points,
                hint=check.hint,
                evidence_refs=check.evidence_refs,
                origin="model_repaired",
                tested_concepts=check.tested_concepts,
                answer_point_map=check.answer_point_map,
            )
            for check in checks
        )
    return ()


def _repair_next_checks(
    *,
    markdown: str,
    repair_context: Mapping[str, Any],
    llm_config: Any,
    generated_next_checks: Any = None,
    log_event: Callable[[str, Mapping[str, Any]], None] | None = None,
    log_warning: Callable[[Mapping[str, Any]], None] | None = None,
) -> tuple[Mapping[str, str], ...]:
    payload = {
        "user_prompt": repair_context.get("user_prompt", ""),
        "coverage_status": repair_context.get("coverage_status", ""),
        "retrieval_sufficient": repair_context.get("retrieval_sufficient", False),
        "generated_markdown": markdown,
        "generated_next_checks": generated_next_checks if isinstance(generated_next_checks, list) else [],
        "evidence": list(repair_context.get("evidence") or ()),
        "next_check_requirement": repair_context.get("next_check_requirement") or {},
        "task": "Return only concrete next checks required by next_check_requirement.",
    }
    if log_event is not None:
        log_event(
            "comprehension_next_checks_repair_requested",
            {
                "prompt_template_id": NEXT_CHECK_REPAIR_PROMPT_TEMPLATE_ID,
                "payload": payload,
            },
        )
    response = complete_json(
        llm_config,
        (
            {"role": "system", "content": _compose_repair_prompt(NEXT_CHECK_REPAIR_PROMPT_PATH)},
            {"role": "user", "content": json.dumps(payload, sort_keys=True)},
        ),
        response_format=_next_check_repair_response_format(),
        log_warning=log_warning,
        log_event=log_event,
    )
    next_checks = _next_checks_from_response(response.get("next_checks"))
    if log_event is not None:
        log_event(
            "comprehension_next_checks_repair_received",
            {
                "prompt_template_id": NEXT_CHECK_REPAIR_PROMPT_TEMPLATE_ID,
                "accepted_count": len(next_checks),
            },
        )
    return next_checks


def _repair_source_attributions(
    *,
    markdown: str,
    repair_context: Mapping[str, Any],
    allowed_refs: set[str],
    llm_config: Any,
    log_event: Callable[[str, Mapping[str, Any]], None] | None = None,
    log_warning: Callable[[Mapping[str, Any]], None] | None = None,
) -> tuple[Mapping[str, Any], ...]:
    quote_candidates = _source_attribution_quote_candidates(markdown)
    if not quote_candidates:
        return ()
    quote_ids = {f"q{index + 1}": quote for index, quote in enumerate(quote_candidates)}
    payload = {
        "user_prompt": repair_context.get("user_prompt", ""),
        "generated_markdown": markdown,
        "quote_candidates": [{"id": quote_id, "quote": quote} for quote_id, quote in quote_ids.items()],
        "allowed_refs": sorted(allowed_refs),
        "evidence": list(repair_context.get("evidence") or ()),
        "task": "Return source_attributions whose quote values are selected from quote_candidates.",
    }
    if log_event is not None:
        log_event(
            "comprehension_source_attribution_repair_requested",
            {
                "prompt_template_id": SOURCE_ATTRIBUTION_REPAIR_PROMPT_TEMPLATE_ID,
                "payload": payload,
            },
        )
    response = complete_json(
        llm_config,
        (
            {"role": "system", "content": _compose_repair_prompt(SOURCE_ATTRIBUTION_REPAIR_PROMPT_PATH)},
            {"role": "user", "content": json.dumps(payload, sort_keys=True)},
        ),
        response_format=_source_attribution_repair_response_format(tuple(quote_ids)),
        log_warning=log_warning,
        log_event=log_event,
    )
    attributions = _source_attributions_from_repair_response(
        response.get("source_attributions"),
        quote_ids=quote_ids,
        allowed_refs=allowed_refs,
    )
    if log_event is not None:
        log_event(
            "comprehension_source_attribution_repair_received",
            {
                "prompt_template_id": SOURCE_ATTRIBUTION_REPAIR_PROMPT_TEMPLATE_ID,
                "accepted_count": len(attributions),
            },
        )
    return attributions


def _source_attributions_from_repair_response(
    value: Any,
    *,
    quote_ids: Mapping[str, str],
    allowed_refs: set[str],
) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    expanded: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        quote_id = str(item.get("quote_id") or "").strip()
        quote = quote_ids.get(quote_id)
        if not quote:
            continue
        expanded.append(
            {
                "quote": quote,
                "source_kind": str(item.get("source_kind") or ""),
                "source_ref": str(item.get("source_ref") or ""),
                "note": str(item.get("note") or ""),
            }
        )
    return _source_attributions_from_response(expanded, markdown="\n".join(quote_ids.values()), allowed_refs=allowed_refs)


def _source_attribution_quote_candidates(markdown: str) -> list[str]:
    candidates: list[str] = []
    for sentence in _split_sentences_preserving_punctuation(markdown):
        pieces = [sentence]
        if "([" in sentence:
            pieces.append(sentence.split("([", 1)[0])
        for piece in pieces:
            quote = re.sub(r"\s+", " ", piece).strip()
            quote = re.sub(r"\s*\($", "", quote).strip()
            if not quote or len(quote) > 220 or "[" in quote or "](" in quote:
                continue
            lowered = quote.casefold()
            if (
                "issue" in lowered
                or "reported" in lowered
                or "retrieved code" in lowered
                or "code shows" in lowered
                or "`" in quote
                or "pandas" in lowered
                or "pytables" in lowered
                or "categorical" in lowered
                or "group" in lowered
                or "append" in lowered
            ):
                if quote not in candidates:
                    candidates.append(quote)
            if len(candidates) >= 18:
                break
        if len(candidates) >= 18:
            break
    return candidates


def _uses_retrieval_label_wording(text: str) -> bool:
    return bool(RETRIEVAL_LABEL_QUESTION_PATTERN.search(text))


def _answer_point_map_from_response(value: Any) -> tuple[Mapping[str, str], ...]:
    if not isinstance(value, list):
        return ()
    mapped: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        kind = str(item.get("kind") or "").strip().casefold()
        point = str(item.get("point") or "").strip()
        if kind and point:
            mapped.append({"kind": kind, "point": point})
    return tuple(mapped)


def _check_grounding_contract(
    *,
    question: str,
    tested_concepts: Sequence[str],
    answer_point_map: Sequence[Mapping[str, str]],
    expected_points: Sequence[str],
    plan: ComprehensionPlan,
    markdown: str,
    answer_flow: Mapping[str, Any],
) -> str:
    if _is_generic_understanding_question(question):
        return "generic_understanding_question"
    if not tested_concepts:
        return "missing_tested_concepts"
    if any(_is_retrieval_role_label(concept) for concept in tested_concepts):
        return "retrieval_label_concept"
    flow_concepts = {_normalize_contract_text(concept) for concept in _string_tuple(answer_flow.get("tested_concepts"))}
    if not flow_concepts:
        return "missing_answer_flow_concepts"
    if not any(_normalize_contract_text(concept) in flow_concepts for concept in tested_concepts):
        return "tested_concept_not_in_answer_flow"
    if not _question_names_answer_flow_term(question=question, answer_flow=answer_flow):
        return "question_not_about_answer_flow"
    if not answer_point_map:
        return "missing_answer_point_map"
    expected_set = {_normalize_contract_text(point) for point in expected_points}
    flow_points_by_kind = {
        "symptom": _normalize_contract_text(str(answer_flow.get("symptom") or "")),
        "evidence": _normalize_contract_text(str(answer_flow.get("evidence") or "")),
        "cause": _normalize_contract_text(str(answer_flow.get("cause") or "")),
    }
    flow_set = {point for point in flow_points_by_kind.values() if point}
    if expected_set != flow_set:
        return "expected_points_do_not_match_answer_flow"
    mapped_kinds: set[str] = set()
    mapped_points: set[str] = set()
    for item in answer_point_map:
        kind = str(item.get("kind") or "").strip().casefold()
        point = str(item.get("point") or "").strip()
        if kind not in {"symptom", "evidence", "cause"}:
            return "invalid_answer_point_kind"
        normalized_point = _normalize_contract_text(point)
        if normalized_point not in expected_set:
            return "answer_point_map_mismatch"
        if normalized_point != flow_points_by_kind.get(kind):
            return "answer_point_map_kind_mismatch"
        mapped_kinds.add(kind)
        mapped_points.add(normalized_point)
    if mapped_kinds != {"symptom", "evidence", "cause"}:
        return "incomplete_answer_point_map"
    if not expected_set.issubset(mapped_points):
        return "unmapped_expected_answer_point"
    return ""


def _is_generic_understanding_question(question: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", question.casefold()).strip()
    generic_questions = {
        "why does the reported behavior happen",
        "why does this behavior happen",
        "why does the issue happen",
        "why does the reported issue happen",
        "what causes the reported behavior",
        "what causes this behavior",
        "what is the cause of the reported behavior",
    }
    return normalized.rstrip(" ?.") in generic_questions


def _question_names_answer_flow_term(*, question: str, answer_flow: Mapping[str, Any]) -> bool:
    question_text = _normalize_contract_text(question)
    if not question_text:
        return False
    terms = _answer_flow_question_terms(answer_flow)
    return any(term in question_text for term in terms)


def _answer_flow_question_terms(answer_flow: Mapping[str, Any]) -> set[str]:
    terms: set[str] = set()
    for concept in _string_tuple(answer_flow.get("tested_concepts")):
        normalized = _normalize_question_term(concept)
        if normalized and not _is_generic_question_term(normalized):
            terms.add(normalized)
    fields = (
        str(answer_flow.get("symptom") or ""),
        str(answer_flow.get("evidence") or ""),
        str(answer_flow.get("cause") or ""),
    )
    for text in fields:
        terms.update(_concrete_question_terms(text))
    return terms


def _concrete_question_terms(text: str) -> set[str]:
    terms: set[str] = set()
    for match in re.findall(r"`([^`]{2,80})`", text):
        normalized = _normalize_question_term(match)
        if normalized:
            terms.add(normalized)
    for match in re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*(?:[._/-][A-Za-z0-9_]+)+\b", text):
        normalized = _normalize_question_term(match)
        if normalized:
            terms.add(normalized)
    for match in re.findall(r"\b[A-Z][A-Za-z0-9_]{2,}\b", text):
        normalized = _normalize_question_term(match)
        if normalized:
            terms.add(normalized)
    for phrase in _string_tuple([text]):
        normalized_phrase = _normalize_question_term(phrase)
        if normalized_phrase and 2 <= len(normalized_phrase.split()) <= 6:
            terms.add(normalized_phrase)
    return {term for term in terms if not _is_generic_question_term(term)}


def _normalize_question_term(value: str) -> str:
    normalized = _normalize_contract_text(value)
    if len(normalized) < 3:
        return ""
    return normalized


def _is_generic_question_term(term: str) -> bool:
    return term in {
        "the",
        "this",
        "that",
        "issue",
        "reported",
        "behavior",
        "reported behavior",
        "symptom",
        "evidence",
        "cause",
        "code",
        "selected code",
        "user",
        "users",
        "data",
        "file",
        "files",
        "method",
        "function",
        "module",
        "path",
    }


def _normalized_contract_texts(*, plan: ComprehensionPlan, markdown: str) -> tuple[str, ...]:
    plan_payload = plan.to_dict()
    values: list[str] = [str(plan_payload.get("task_goal") or ""), _answer_path_section(markdown)]
    for concept in plan_payload.get("concepts") or ():
        if isinstance(concept, Mapping):
            values.extend(
                str(concept.get(key) or "")
                for key in ("id", "name", "description")
            )
    return tuple(_normalize_contract_text(value) for value in values if str(value).strip())


def _answer_path_section(markdown: str) -> str:
    match = re.search(r"(?is)answer path[^:\n]*:\s*(?P<section>.*?)(?:\n\s*\n|$)", markdown)
    return match.group("section") if match else markdown


def _contract_text_contains(needle: str, haystacks: Sequence[str]) -> bool:
    normalized = _normalize_contract_text(needle)
    return bool(normalized) and any(normalized in haystack for haystack in haystacks)


def _normalize_contract_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9_.]+", " ", value.casefold())).strip()


def _compact_evidence(item: EvidenceItem) -> dict[str, Any]:
    metadata = dict(item.metadata)
    return {
        "ref": item.source_id,
        "citation_markdown": _evidence_link(item),
        "path": metadata.get("path") or _path_from_source_id(item.source_id) or item.source_id,
        "line_range": metadata.get("line_range") or _line_range_from_source_id(item.source_id),
        "coverage_area": metadata.get("coverage_area", ""),
        "claim_supported": metadata.get("claim_supported", ""),
        "snippet": _compact_snippet(item.snippet),
    }


def _response_format() -> Mapping[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "comprehension_plan_explanation",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "markdown": {"type": "string"},
                    "used_evidence_refs": {"type": "array", "items": {"type": "string"}},
                    "answer_flow": {
                        "type": "object",
                        "properties": {
                            "symptom": {"type": "string"},
                            "evidence": {"type": "string"},
                            "cause": {"type": "string"},
                            "tested_concepts": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 6},
                            "evidence_refs": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 6},
                        },
                        "required": ["symptom", "evidence", "cause", "tested_concepts", "evidence_refs"],
                        "additionalProperties": False,
                    },
                    "understanding_checks": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 3,
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "role": {"type": "string"},
                                "question_type": {"type": "string"},
                                "question": {"type": "string"},
                                "expected_answer_points": {"type": "array", "items": {"type": "string"}},
                                "hint": {"type": "string"},
                                "evidence_refs": {"type": "array", "items": {"type": "string"}},
                                "origin": {"type": "string"},
                                "tested_concepts": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 6},
                                "answer_point_map": {
                                    "type": "array",
                                    "minItems": 3,
                                    "maxItems": 4,
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "kind": {"type": "string", "enum": ["symptom", "evidence", "cause"]},
                                            "point": {"type": "string"},
                                        },
                                        "required": ["kind", "point"],
                                        "additionalProperties": False,
                                    },
                                },
                            },
                            "required": [
                                "id",
                                "role",
                                "question_type",
                                "question",
                                "expected_answer_points",
                                "hint",
                                "evidence_refs",
                                "origin",
                                "tested_concepts",
                                "answer_point_map",
                            ],
                            "additionalProperties": False,
                        },
                    },
                    "render_notes": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "summary": {"type": "string"},
                        },
                        "required": ["title", "summary"],
                        "additionalProperties": False,
                    },
                    "concept_definitions": {
                        "type": "array",
                        "maxItems": 12,
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string"},
                                "description": {"type": "string"},
                                "evidence_refs": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["label", "description", "evidence_refs"],
                            "additionalProperties": False,
                        },
                    },
                    "source_attributions": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 16,
                        "items": {
                            "type": "object",
                            "properties": {
                                "quote": {"type": "string"},
                                "source_kind": {
                                    "type": "string",
                                    "enum": [
                                        "issue_title",
                                        "issue_body",
                                        "user_sample",
                                        "error_text",
                                        "source_code",
                                        "repo_docs",
                                        "local_notes",
                                        "notebooklm",
                                        "connected_source",
                                        "external_runtime",
                                    ],
                                },
                                "source_ref": {"type": "string"},
                                "note": {"type": "string"},
                            },
                            "required": ["quote", "source_kind", "source_ref", "note"],
                            "additionalProperties": False,
                        },
                    },
                    "next_checks": {
                        "type": "array",
                        "maxItems": 4,
                        "items": {
                            "type": "object",
                            "properties": {
                                "scenario": {"type": "string"},
                                "action": {"type": "string"},
                                "if_result": {"type": "string"},
                                "then_interpretation": {"type": "string"},
                            },
                            "required": ["scenario", "action", "if_result", "then_interpretation"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": [
                    "markdown",
                    "used_evidence_refs",
                    "answer_flow",
                    "understanding_checks",
                    "render_notes",
                    "concept_definitions",
                    "source_attributions",
                    "next_checks",
                ],
                "additionalProperties": False,
            },
        },
    }


def _check_repair_response_format() -> Mapping[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "comprehension_understanding_check_repair",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "understanding_checks": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 3,
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "role": {"type": "string"},
                                "question_type": {"type": "string"},
                                "question": {"type": "string"},
                                "expected_answer_points": {"type": "array", "items": {"type": "string"}},
                                "hint": {"type": "string"},
                                "evidence_refs": {"type": "array", "items": {"type": "string"}},
                                "origin": {"type": "string"},
                                "tested_concepts": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 6},
                                "answer_point_map": {
                                    "type": "array",
                                    "minItems": 3,
                                    "maxItems": 4,
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "kind": {"type": "string", "enum": ["symptom", "evidence", "cause"]},
                                            "point": {"type": "string"},
                                        },
                                        "required": ["kind", "point"],
                                        "additionalProperties": False,
                                    },
                                },
                            },
                            "required": [
                                "id",
                                "role",
                                "question_type",
                                "question",
                                "expected_answer_points",
                                "hint",
                                "evidence_refs",
                                "origin",
                                "tested_concepts",
                                "answer_point_map",
                            ],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["understanding_checks"],
                "additionalProperties": False,
            },
        },
    }


def _next_check_repair_response_format() -> Mapping[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "comprehension_next_checks_repair",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "next_checks": {
                        "type": "array",
                        "minItems": 2,
                        "maxItems": 4,
                        "items": {
                            "type": "object",
                            "properties": {
                                "scenario": {"type": "string"},
                                "action": {"type": "string"},
                                "if_result": {"type": "string"},
                                "then_interpretation": {"type": "string"},
                            },
                            "required": ["scenario", "action", "if_result", "then_interpretation"],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["next_checks"],
                "additionalProperties": False,
            },
        },
    }


def _source_attribution_repair_response_format(quote_ids: Sequence[str]) -> Mapping[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "comprehension_source_attribution_repair",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "source_attributions": {
                        "type": "array",
                        "minItems": 3,
                        "maxItems": 8,
                        "items": {
                            "type": "object",
                            "properties": {
                                "quote_id": {"type": "string", "enum": list(quote_ids)},
                                "source_kind": {
                                    "type": "string",
                                    "enum": [
                                        "issue_title",
                                        "issue_body",
                                        "user_sample",
                                        "error_text",
                                        "source_code",
                                        "repo_docs",
                                        "local_notes",
                                        "notebooklm",
                                        "connected_source",
                                        "external_runtime",
                                    ],
                                },
                                "source_ref": {"type": "string"},
                                "note": {"type": "string"},
                            },
                            "required": ["quote_id", "source_kind", "source_ref", "note"],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["source_attributions"],
                "additionalProperties": False,
            },
        },
    }


def _evidence_link(item: EvidenceItem) -> str:
    label = _evidence_label(item)
    href = _evidence_href(item)
    return f"[{label}]({href})"


def _evidence_label(item: EvidenceItem) -> str:
    metadata = dict(item.metadata)
    path = metadata.get("path") or _path_from_source_id(item.source_id) or item.source_id
    line_range = metadata.get("line_range") or _line_range_from_source_id(item.source_id)
    if line_range and line_range not in path:
        return f"{path}:{line_range}"
    return path


def _evidence_href(item: EvidenceItem) -> str:
    metadata = dict(item.metadata)
    path = str(metadata.get("path") or _path_from_source_id(item.source_id) or item.source_id)
    line_range = str(metadata.get("line_range") or _line_range_from_source_id(item.source_id))
    normalized = path.replace("\\", "/").replace(" ", "%20")
    return f"{normalized}#{line_range}" if line_range else normalized


def _path_from_source_id(source_id: str) -> str:
    if source_id.startswith("workspace:"):
        return source_id[len("workspace:") :].split(":L", 1)[0]
    if source_id.startswith("repo-pre:"):
        return source_id[len("repo-pre:") :].split(":L", 1)[0]
    return ""


def _line_range_from_source_id(source_id: str) -> str:
    marker = ":L"
    if marker not in source_id:
        return ""
    return "L" + source_id.rsplit(marker, 1)[1]


def _compact_snippet(snippet: str, *, max_lines: int = 8, max_line_length: int = 160) -> str:
    lines = [line.rstrip() for line in snippet.replace("```", "'''").splitlines() if line.strip()]
    output: list[str] = []
    for line in lines[:max_lines]:
        output.append(line[: max_line_length - 3].rstrip() + "..." if len(line) > max_line_length else line)
    if len(lines) > len(output):
        output.append("...")
    return "\n".join(output)


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())
