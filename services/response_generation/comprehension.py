from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from core.models import ConversationState, EvidenceItem, RetrievalResult
from services.comprehension import build_comprehension_plan
from services.comprehension.models import ComprehensionPlan
from services.guidance.questions import UnderstandingCheck
from services.llm.json_completion import complete_json


PROMPT_TEMPLATE_ID = "comprehension_plan_explanation_v1"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
PROMPT_PATH = PROMPTS_DIR / "comprehension_plan_explanation.md"
RETRIEVAL_LABEL_QUESTION_PATTERN = re.compile(
    r"\b(?:evidence|retrieved|coverage|role)\b"
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
    r"(?ims)^\s*(?:---\s*\n\s*)?#{1,6}\s+(?:Concept Definitions|Understanding Check)\s*$.*\Z"
)


@dataclass(frozen=True)
class ComprehensionGenerationResult:
    markdown: str
    used_evidence_refs: tuple[str, ...]
    render_notes: Mapping[str, str]
    understanding_checks: tuple[UnderstandingCheck, ...]
    comprehension_plan: ComprehensionPlan
    concept_definitions: tuple[Mapping[str, Any], ...] = ()
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
    payload = {
        "user_prompt": state.user_input,
        "retrieval_sufficient": retrieval_result.sufficient,
        "coverage_status": retrieval_result.coverage_status,
        "assistance_mode": assistance_mode,
        "comprehension_plan": plan.to_dict(),
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
            {"role": "system", "content": PROMPT_PATH.read_text(encoding="utf-8")},
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
        log_event=log_event,
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


def _validate_response(
    response: Mapping[str, Any],
    evidence: Sequence[EvidenceItem],
    plan: ComprehensionPlan,
    *,
    concept_definition_targets: Sequence[str] = (),
    log_event: Callable[[str, Mapping[str, Any]], None] | None = None,
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
    checks = _checks_from_response(
        response.get("understanding_checks"),
        markdown=markdown,
        plan=plan,
        allowed_refs=allowed_refs,
        log_event=log_event,
    )
    concept_definitions = _concept_definitions_from_response(
        response.get("concept_definitions"),
        markdown=markdown,
        allowed_refs=allowed_refs,
        allowed_labels=set(concept_definition_targets),
    )
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
        understanding_checks=checks,
        comprehension_plan=plan,
        concept_definitions=concept_definitions,
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
    sanitized = LEAKED_METADATA_SECTION_PATTERN.sub("", sanitized).rstrip()
    return sanitized


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
    log_event: Callable[[str, Mapping[str, Any]], None] | None = None,
) -> tuple[UnderstandingCheck, ...]:
    checks: list[UnderstandingCheck] = []
    rejected: list[dict[str, Any]] = []
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, Mapping):
                rejected.append({"reason": "not_mapping"})
                continue
            refs = tuple(ref for ref in _string_tuple(item.get("evidence_refs")) if ref in allowed_refs)
            points = _string_tuple(item.get("expected_answer_points"))
            question = str(item.get("question") or "").strip()
            hint = str(item.get("hint") or "").strip()
            if not refs or not points or not question or not hint:
                rejected.append({"reason": "missing_required_fields", "question": question[:200]})
                continue
            if _uses_retrieval_label_wording(question) or _uses_retrieval_label_wording(hint):
                rejected.append({"reason": "retrieval_label_wording", "question": question[:200], "hint": hint[:200]})
                continue
            if not _check_answer_path_is_in_explanation(question=question, expected_points=points, markdown=markdown):
                rejected.append({"reason": "answer_path_not_taught", "question": question[:200], "expected_answer_points": list(points[:4])})
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
                )
            )
    if checks:
        return tuple(checks[:3])
    if log_event is not None:
        log_event(
            "comprehension_understanding_checks_rejected",
            {
                "rejected": rejected[:5],
                "raw_count": len(value) if isinstance(value, list) else 0,
            },
        )
    raise RuntimeError("Comprehension explanation generation returned no valid model-generated understanding checks.")


def _uses_retrieval_label_wording(text: str) -> bool:
    return bool(RETRIEVAL_LABEL_QUESTION_PATTERN.search(text))


def _check_answer_path_is_in_explanation(
    *,
    question: str,
    expected_points: Sequence[str],
    markdown: str,
) -> bool:
    explanation_terms = _semantic_check_terms(markdown)
    if not explanation_terms:
        return False
    question_terms = _semantic_check_terms(question)
    if question_terms:
        covered = sum(1 for term in question_terms if _term_is_supported(term, explanation_terms))
        if covered < min(len(question_terms), 2):
            return False
    answer_terms: set[str] = set()
    for point in expected_points:
        answer_terms.update(_semantic_check_terms(point))
    if not answer_terms:
        return False
    covered_answer_terms = sum(1 for term in answer_terms if _term_is_supported(term, explanation_terms))
    return covered_answer_terms >= min(len(answer_terms), 4)


def _term_is_supported(term: str, explanation_terms: set[str]) -> bool:
    if term in explanation_terms:
        return True
    equivalent_terms = {
        "es5": {"non-es6", "non es6", "default"},
        "non-es6": {"es5", "default"},
        "non es6": {"es5", "default"},
        "target": {"targets", "compilation"},
        "targets": {"target", "compilation"},
        "library": {"libraries"},
        "libraries": {"library"},
        "fail": {"fails", "failure", "missing"},
        "fails": {"fail", "failure", "missing"},
        "failure": {"fail", "fails", "missing"},
        "declared": {"declaration"},
        "declaration": {"declared"},
        "selects": {"includes"},
    }
    return bool(equivalent_terms.get(term, set()) & explanation_terms)


def _semantic_check_terms(text: str) -> set[str]:
    normalized_text = text.replace("`", "")
    terms: set[str] = set()
    for match in re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+\b", normalized_text):
        terms.add(match.casefold())
    for match in re.findall(r"\b[A-Z][A-Za-z0-9_]*\b", normalized_text):
        if len(match) > 1:
            terms.add(match.casefold())
    for match in re.findall(r"\bES\d+\b", normalized_text, flags=re.IGNORECASE):
        terms.add(match.casefold())
    for match in re.findall(r"\bnon[-\s]?ES\d+\b", normalized_text, flags=re.IGNORECASE):
        terms.add(match.replace("-", " ").casefold())
        terms.add(match.replace(" ", "-").casefold())
    for match in re.findall(r"\b(?:default|target|targets|library|libraries|compiler|compile|compilation|missing|fail|fails|failure|present|absent|declared|declaration|selects|includes|excludes)\b", normalized_text, flags=re.IGNORECASE):
        terms.add(match.casefold())
    return terms


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
                },
                "required": ["markdown", "used_evidence_refs", "understanding_checks", "render_notes", "concept_definitions"],
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
