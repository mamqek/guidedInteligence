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
    payload = {
        "user_prompt": state.user_input,
        "coverage_status": retrieval_result.coverage_status,
        "retrieval_sufficient": retrieval_result.sufficient,
        "evidence": [_compact_evidence(item) for item in retrieval_result.evidence[:8]],
        "retrieval_summary": _compact_retrieval_summary(retrieval_result.retrieval_summary),
        "citation_rules": {
            "allowed_links": [_evidence_link(item) for item in retrieval_result.evidence[:8]],
            "allowed_refs": [item.source_id for item in retrieval_result.evidence[:8]],
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
    result = _validate_generation_response(response, retrieval_result.evidence)
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
