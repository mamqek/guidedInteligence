from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from core.models import ConversationState, EvidenceItem, RetrievalResult
from services.llm.json_completion import complete_json


LINE_RANGE_PATTERN = re.compile(r":L(?P<start>\d+)(?:-L(?P<end>\d+))?$")
PROMPT_TEMPLATE_ID = "explanation_markdown_v2"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
EXPLANATION_PROMPT_PATH = PROMPTS_DIR / "explanation.md"
EXPLANATION_SOURCES_PATH = PROMPTS_DIR / "explanation_sources.md"


@dataclass(frozen=True)
class ExplanationGenerationResult:
    markdown: str
    used_evidence_refs: tuple[str, ...]
    render_notes: Mapping[str, str]
    prompt_template_id: str = PROMPT_TEMPLATE_ID


def generate_explanation(
    *,
    state: ConversationState,
    retrieval_result: RetrievalResult,
    llm_config: Any,
    log_warning: Callable[[Mapping[str, Any]], None] | None = None,
    log_event: Callable[[str, Mapping[str, Any]], None] | None = None,
) -> ExplanationGenerationResult:
    required_evidence = _required_evidence_items(state.user_input, retrieval_result.evidence[:8])
    payload = {
        "user_prompt": state.user_input,
        "coverage_status": retrieval_result.coverage_status,
        "retrieval_sufficient": retrieval_result.sufficient,
        "evidence": [_compact_evidence(item) for item in retrieval_result.evidence[:8]],
        "required_evidence": [_compact_evidence(item) for item in required_evidence],
        "retrieval_summary": _compact_retrieval_summary(retrieval_result.retrieval_summary),
        "citation_rules": {
            "allowed_links": [_evidence_link(item) for item in retrieval_result.evidence[:8]],
            "allowed_refs": [item.source_id for item in retrieval_result.evidence[:8]],
            "required_refs": [item.source_id for item in required_evidence],
        },
    }
    if log_event is not None:
        log_event(
            "response_generation_request_payload",
            {
                "prompt_template_id": PROMPT_TEMPLATE_ID,
                "payload": payload,
            },
        )
    response = complete_json(
        llm_config,
        (
            {"role": "system", "content": _load_prompt(EXPLANATION_PROMPT_PATH)},
            {"role": "user", "content": json.dumps(payload, sort_keys=True)},
        ),
        response_format=_response_format(),
        log_warning=log_warning,
        log_event=log_event,
    )
    result = _validate_generation_response(response, retrieval_result.evidence, required_evidence=required_evidence)
    if log_event is not None:
        log_event(
            "response_generation_response_payload",
            {
                "prompt_template_id": PROMPT_TEMPLATE_ID,
                "used_evidence_refs": list(result.used_evidence_refs),
                "render_notes": dict(result.render_notes),
            },
        )
    return result


def prompt_template_id() -> str:
    return PROMPT_TEMPLATE_ID


def prompt_sources_path() -> Path:
    return EXPLANATION_SOURCES_PATH


def _validate_generation_response(
    response: Mapping[str, Any],
    evidence: Sequence[EvidenceItem],
    *,
    required_evidence: Sequence[EvidenceItem] = (),
) -> ExplanationGenerationResult:
    markdown = str(response.get("markdown", "")).strip()
    if not markdown:
        raise RuntimeError("Explanation generation returned empty markdown.")

    allowed_refs = {item.source_id for item in evidence}
    used_refs: list[str] = []
    for ref in response.get("used_evidence_refs", ()):
        ref_text = str(ref).strip()
        if ref_text and ref_text in allowed_refs and ref_text not in used_refs:
            used_refs.append(ref_text)

    render_notes_raw = response.get("render_notes", {})
    render_notes: dict[str, str] = {}
    if isinstance(render_notes_raw, Mapping):
        for key in ("title", "summary"):
            value = str(render_notes_raw.get(key, "")).strip()
            if value:
                render_notes[key] = value[:500]

    markdown, used_refs = _repair_missing_required_evidence(
        markdown,
        used_refs,
        evidence=evidence,
        required_evidence=required_evidence,
    )
    return ExplanationGenerationResult(
        markdown=markdown,
        used_evidence_refs=tuple(used_refs),
        render_notes=render_notes,
    )


def _compact_evidence(item: EvidenceItem) -> dict[str, Any]:
    metadata = dict(item.metadata)
    return {
        "ref": item.source_id,
        "citation_markdown": _evidence_link(item),
        "path": metadata.get("path") or _path_from_source_id(item.source_id) or item.source_id,
        "line_range": metadata.get("line_range") or _line_range_from_source_id(item.source_id),
        "coverage_area": metadata.get("coverage_area", ""),
        "retrieval_path": metadata.get("retrieval_path", ""),
        "snippet_quality": metadata.get("snippet_quality", ""),
        "snippet": _compact_snippet(item.snippet),
    }


def _required_evidence_items(user_prompt: str, evidence: Sequence[EvidenceItem]) -> tuple[EvidenceItem, ...]:
    prompt_terms = _high_signal_prompt_terms(user_prompt)
    required: list[EvidenceItem] = []
    for item in evidence:
        snippet = item.snippet or ""
        metadata = dict(item.metadata)
        coverage_area = str(metadata.get("coverage_area", "")).strip().lower()
        if _contains_prompt_anchor(snippet, prompt_terms):
            required.append(item)
            continue
        if coverage_area == "diagnostics" and _contains_diagnostic_emission(snippet):
            required.append(item)
            continue
        if _contains_diagnostic_emission(snippet) and _contains_prompt_anchor(snippet, prompt_terms, minimum_length=8):
            required.append(item)
            continue
    return tuple(required[:3])


def _high_signal_prompt_terms(user_prompt: str) -> tuple[str, ...]:
    terms: list[str] = []
    for match in re.findall(r"`([^`]+)`|'([^']+)'|\"([^\"]+)\"", user_prompt):
        value = next((item for item in match if item), "")
        normalized = _normalize_phrase(value)
        if len(normalized) >= 6:
            terms.append(normalized)
    for match in re.findall(r"\b(?:error|warning|diagnostic|expects?|cannot|must|invalid|unsafe)\b[^.\n\r]{0,90}", user_prompt, flags=re.IGNORECASE):
        normalized = _normalize_phrase(match)
        if len(normalized) >= 8:
            terms.append(normalized)
    return tuple(dict.fromkeys(terms[:12]))


def _contains_prompt_anchor(snippet: str, prompt_terms: Sequence[str], *, minimum_length: int = 6) -> bool:
    normalized_snippet = _normalize_phrase(snippet)
    if not normalized_snippet:
        return False
    for term in prompt_terms:
        if len(term) < minimum_length:
            continue
        if term in normalized_snippet:
            return True
        compact_term = re.sub(r"[^a-z0-9]+", "", term)
        if len(compact_term) >= 10 and compact_term in re.sub(r"[^a-z0-9]+", "", normalized_snippet):
            return True
    return False


def _contains_diagnostic_emission(snippet: str) -> bool:
    return bool(
        re.search(
            r"\b(?:warn|warning|error|diagnostic|throw|fail|expects?|invalid|unsafe)\b",
            snippet,
            flags=re.IGNORECASE,
        )
    )


def _normalize_phrase(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _repair_missing_required_evidence(
    markdown: str,
    used_refs: Sequence[str],
    *,
    evidence: Sequence[EvidenceItem],
    required_evidence: Sequence[EvidenceItem],
) -> tuple[str, list[str]]:
    used = list(used_refs)
    used_set = set(used)
    missing = [item for item in required_evidence if not _required_evidence_is_visibly_cited(item, markdown)]
    if not missing:
        return markdown, used

    additions: list[str] = []
    evidence_by_ref = {item.source_id: item for item in evidence}
    for item in missing:
        if item.source_id not in evidence_by_ref:
            continue
        additions.append(_required_evidence_note(item))
        if item.source_id not in used_set:
            used.append(item.source_id)
            used_set.add(item.source_id)
    if not additions:
        return markdown, used

    repaired = markdown.rstrip()
    repaired += "\n\n## Evidence Not To Miss\n\n"
    repaired += "\n".join(additions)
    return repaired, used


def _required_evidence_note(item: EvidenceItem) -> str:
    metadata = dict(item.metadata)
    coverage_area = str(metadata.get("coverage_area", "")).strip()
    link = _evidence_link(item)
    reason = "This retrieved snippet is a high-priority anchor for the explanation."
    if _contains_diagnostic_emission(item.snippet):
        reason = "This snippet matters because it shows the diagnostic or error path directly."
    if coverage_area:
        reason += f" It was retrieved for the `{coverage_area}` part of the question."
    return f"- {reason} See {link}."


def _required_evidence_is_visibly_cited(item: EvidenceItem, markdown: str) -> bool:
    if _evidence_link(item) in markdown:
        return True
    item_path = _path_from_source_id(item.source_id)
    item_range = _line_bounds_from_source_id(item.source_id)
    for cited_path, cited_range in _markdown_citation_ranges(markdown):
        if cited_path != item_path:
            continue
        if item_range is None or cited_range is None:
            return True
        if _line_ranges_overlap(item_range, cited_range):
            return True
    return False


def _markdown_citation_ranges(markdown: str) -> tuple[tuple[str, tuple[int, int] | None], ...]:
    citations: list[tuple[str, tuple[int, int] | None]] = []
    for href in re.findall(r"\]\(([^)]+)\)", markdown):
        path, _, anchor = href.partition("#")
        normalized_path = path.replace("%20", " ").replace("\\", "/")
        line_range = _line_bounds_from_anchor(anchor)
        citations.append((normalized_path, line_range))
    return tuple(citations)


def _line_bounds_from_source_id(source_id: str) -> tuple[int, int] | None:
    match = LINE_RANGE_PATTERN.search(source_id)
    if match is None:
        return None
    start = int(match.group("start"))
    end = int(match.group("end") or start)
    return (start, end)


def _line_bounds_from_anchor(anchor: str) -> tuple[int, int] | None:
    match = re.match(r"^L(?P<start>\d+)(?:-L(?P<end>\d+))?$", anchor)
    if match is None:
        return None
    start = int(match.group("start"))
    end = int(match.group("end") or start)
    return (start, end)


def _line_ranges_overlap(left: tuple[int, int], right: tuple[int, int]) -> bool:
    left_start, left_end = left
    right_start, right_end = right
    return left_start <= right_end and right_start <= left_end


def _compact_retrieval_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    gate = summary.get("deterministic_coverage_gate", {})
    compact: dict[str, Any] = {
        "selected_count": summary.get("selected_count"),
        "stop_reason": summary.get("stop_reason"),
    }
    if isinstance(gate, Mapping):
        compact["deterministic_coverage_gate"] = {
            "satisfied": gate.get("satisfied"),
            "missing_roles": list(gate.get("missing_roles", ()))[:8],
            "reasons": list(gate.get("reasons", ()))[:8],
        }
    required_buckets = summary.get("required_role_buckets", ())
    if isinstance(required_buckets, Sequence) and not isinstance(required_buckets, (str, bytes)):
        compact["required_role_buckets"] = [
            {
                "role": str(bucket.get("role", "")),
                "role_status": str(bucket.get("role_status", "")),
                "missing_reason": str(bucket.get("missing_reason", "")),
                "accepted_refs": list(bucket.get("accepted_refs", ()))[:4],
            }
            for bucket in required_buckets[:8]
            if isinstance(bucket, Mapping)
        ]
    return compact


def _response_format() -> Mapping[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "response_explanation_markdown",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "markdown": {"type": "string"},
                    "used_evidence_refs": {"type": "array", "items": {"type": "string"}},
                    "render_notes": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "summary": {"type": "string"},
                        },
                        "required": ["title", "summary"],
                        "additionalProperties": False,
                    },
                },
                "required": ["markdown", "used_evidence_refs", "render_notes"],
                "additionalProperties": False,
            },
        },
    }


def _load_prompt(path: Path) -> str:
    return path.read_text(encoding="utf-8")


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
    if metadata.get("url"):
        return str(metadata["url"])
    path = metadata.get("path") or _path_from_source_id(item.source_id) or item.source_id
    line_range = metadata.get("line_range") or _line_range_from_source_id(item.source_id)
    normalized = path.replace("\\", "/").replace(" ", "%20")
    if line_range:
        return f"{normalized}#{line_range}"
    return normalized


def _path_from_source_id(source_id: str) -> str:
    if source_id.startswith("repo-pre:"):
        return source_id[len("repo-pre:") :].split(":L", 1)[0]
    if source_id.startswith("workspace:"):
        return source_id[len("workspace:") :].split(":L", 1)[0]
    return ""


def _line_range_from_source_id(source_id: str) -> str:
    match = LINE_RANGE_PATTERN.search(source_id)
    if match is None:
        return ""
    start = match.group("start")
    end = match.group("end")
    return f"L{start}-L{end}" if end else f"L{start}"


def _compact_snippet(snippet: str, *, max_lines: int = 10, max_line_length: int = 180) -> str:
    cleaned = snippet.replace("```", "'''")
    meaningful = [line.rstrip() for line in cleaned.splitlines() if line.strip()]
    selected = meaningful[:max_lines]
    if not selected:
        return ""
    truncated: list[str] = []
    for line in selected:
        if len(line) > max_line_length:
            truncated.append(line[: max_line_length - 3].rstrip() + "...")
        else:
            truncated.append(line)
    if len(meaningful) > len(selected):
        truncated.append("...")
    return "\n".join(truncated)
