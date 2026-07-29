from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Callable, Iterable, Mapping, Sequence

from core.logging_schema import LogEventType
from core.models import ConversationState, EvidenceItem, PolicyResult, ResponsePayload, ResponsePlan, RetrievalResult, TurnType
from services.response_generation.comprehension import generate_comprehension_explanation, prompt_template_id


LINE_RANGE_PATTERN = re.compile(r":L(?P<start>\d+)(?:-L(?P<end>\d+))?$")
MAX_EXCERPT_LINES = 8
MAX_EXCERPT_LINE_LENGTH = 140
MAX_IDENTIFIER_COUNT = 5


def render_response(
    policy_result: PolicyResult,
    retrieval_result: RetrievalResult | None,
    response_plan: ResponsePlan,
    *,
    state: ConversationState | None = None,
    llm_config: Any | None = None,
    assistance_mode: str = "teach",
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
            assistance_mode=assistance_mode,
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
    assistance_mode: str,
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
                    "assistance_mode": assistance_mode,
                    "coverage_status": retrieval_result.coverage_status,
                    "retrieval_sufficient": retrieval_result.sufficient,
                    "evidence_count": len(retrieval_result.evidence),
                },
            )
        generated = generate_comprehension_explanation(
            state=state,
            retrieval_result=retrieval_result,
            llm_config=llm_config,
            assistance_mode=assistance_mode,
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


def _render_hint(retrieval_result: RetrievalResult | None) -> str:
    evidence = tuple(retrieval_result.evidence if retrieval_result is not None else ())
    if not evidence:
        return _section("Hint", "No grounded evidence is available yet.")
    top = evidence[0]
    return "\n\n".join(
        [
            _section("Hint", f"Start with {_evidence_link(top)}; it is the highest-ranked retrieved snippet."),
            _section("Evidence", _evidence_markdown(evidence[:3])),
        ]
    )


def _render_reasoning_question(retrieval_result: RetrievalResult | None) -> str:
    evidence = tuple(retrieval_result.evidence if retrieval_result is not None else ())
    if not evidence:
        question = "Which part of the codebase should be checked first, and what behavior would prove it?"
    else:
        question = f"Which responsibility does {_evidence_link(evidence[0])} appear to own, and what adjacent file should verify the flow into it?"
    return "\n\n".join(
        [
            _section("Question", question),
            _section("Why This Matters", "The next step should connect a concrete snippet to the behavior being explained."),
        ]
    )


def _summary_text(retrieval_result: RetrievalResult, evidence: Sequence[EvidenceItem]) -> str:
    status = retrieval_result.coverage_status or "unknown"
    sufficiency = "sufficient" if retrieval_result.sufficient else "partial"
    source_count = len(evidence)
    role_counts = _coverage_counts(evidence)
    role_text = ", ".join(f"{role}: {count}" for role, count in role_counts.items()) if role_counts else "no role metadata"
    return (
        f"Retrieved {source_count} evidence snippet(s). Coverage is `{status}` and the sufficiency decision is `{sufficiency}`. "
        f"Role coverage: {role_text}."
    )


def _evidence_markdown(evidence: Sequence[EvidenceItem]) -> str:
    if not evidence:
        return "- No evidence snippets were selected."
    blocks: list[str] = []
    for index, item in enumerate(evidence, start=1):
        metadata = item.metadata
        role = metadata.get("coverage_area", "unclassified")
        retrieval_path = metadata.get("retrieval_path", "unknown")
        quality = metadata.get("snippet_quality", "")
        quality_text = f", quality `{quality}`" if quality else ""
        blocks.append(
            "\n".join(
                [
                    f"{index}. {_evidence_link(item)}",
                    f"   Role `{role}`, retrieval `{retrieval_path}`{quality_text}.",
                    "",
                    "   ```",
                    _compact_snippet(item.snippet),
                    "   ```",
                ]
            )
        )
    return "\n\n".join(blocks)


def _reasoning_path_markdown(evidence: Sequence[EvidenceItem], retrieval_summary: Mapping[str, object]) -> str:
    if not evidence:
        return "- Retrieval selected no snippets, so there is no grounded reasoning path."

    role_groups: dict[str, list[EvidenceItem]] = defaultdict(list)
    for item in evidence:
        role_groups[item.metadata.get("coverage_area", "unclassified")].append(item)

    bullets: list[str] = []
    for role, items in sorted(role_groups.items()):
        links = ", ".join(_evidence_link(item) for item in items[:4])
        bullets.append(f"- `{role}` is represented by {links}.")

    gate = retrieval_summary.get("deterministic_coverage_gate")
    if isinstance(gate, Mapping):
        satisfied = gate.get("satisfied")
        reasons = gate.get("reasons")
        bullets.append(f"- Deterministic coverage gate satisfied: `{satisfied}`.")
        if isinstance(reasons, list) and reasons:
            bullets.append(f"- Gate reasons: {', '.join(f'`{reason}`' for reason in reasons)}.")
    return "\n".join(bullets)


def _confirmed_markdown(evidence: Sequence[EvidenceItem]) -> str:
    if not evidence:
        return "- Nothing can be confirmed from code evidence yet."
    bullets: list[str] = []
    for item in evidence[:8]:
        role = item.metadata.get("coverage_area", "unclassified")
        identifiers = _interesting_identifiers(item.snippet)
        identifier_text = f" It exposes or references `{', '.join(identifiers)}`." if identifiers else ""
        bullets.append(f"- {_evidence_link(item)} is selected source evidence for `{role}`.{identifier_text}")
    return "\n".join(bullets)


def _hypotheses_markdown(retrieval_result: RetrievalResult) -> str:
    gate = retrieval_result.retrieval_summary.get("deterministic_coverage_gate")
    if isinstance(gate, Mapping):
        missing = gate.get("missing_roles")
        reasons = gate.get("reasons")
        if isinstance(missing, list) and missing:
            reason_text = ""
            if isinstance(reasons, list) and reasons:
                reason_text = " Reasons: " + ", ".join(f"`{reason}`" for reason in reasons) + "."
            return f"- Treat `{', '.join(str(role) for role in missing)}` as still needing confirmation.{reason_text}"
    if retrieval_result.sufficient:
        return "- No immediate retrieval gaps were reported. Validate behavior by following the ranked evidence from owner files to callers/tests."
    return "- Retrieval is partial. Check whether selected snippets include the actual owner files and not only support or wrapper layers."


def _knowledge_check_question(evidence: Sequence[EvidenceItem]) -> str:
    if not evidence:
        return "Which missing code area would most reduce uncertainty?"
    role = evidence[0].metadata.get("coverage_area", "the top responsibility")
    return f"Which linked snippet best supports `{role}`, and what specific line or function in that snippet proves it?"


def _coverage_counts(evidence: Sequence[EvidenceItem]) -> Mapping[str, int]:
    counts: dict[str, int] = {}
    for item in evidence:
        role = item.metadata.get("coverage_area", "unclassified")
        counts[role] = counts.get(role, 0) + 1
    return counts


def _evidence_link(item: EvidenceItem) -> str:
    label = _evidence_label(item)
    href = _evidence_href(item)
    return f"[{label}]({href})"


def _evidence_label(item: EvidenceItem) -> str:
    metadata = item.metadata
    path = metadata.get("path") or metadata.get("url") or _path_from_source_id(item.source_id) or item.source_id
    line_range = metadata.get("line_range") or _line_range_from_source_id(item.source_id)
    if line_range and line_range not in path:
        return f"{path}:{line_range}"
    return path


def _evidence_href(item: EvidenceItem) -> str:
    metadata = item.metadata
    if metadata.get("url"):
        return metadata["url"]
    path = metadata.get("path") or _path_from_source_id(item.source_id) or item.source_id
    line_range = metadata.get("line_range") or _line_range_from_source_id(item.source_id)
    path = path.replace("\\", "/").replace(" ", "%20")
    if line_range:
        return f"{path}#{line_range}"
    return path


def _path_from_source_id(source_id: str) -> str:
    if source_id.startswith("repo-pre:"):
        return source_id[len("repo-pre:") :].split(":L", 1)[0]
    return ""


def _line_range_from_source_id(source_id: str) -> str:
    match = LINE_RANGE_PATTERN.search(source_id)
    if match is None:
        return ""
    start = match.group("start")
    end = match.group("end")
    return f"L{start}-L{end}" if end else f"L{start}"


def _compact_snippet(snippet: str) -> str:
    cleaned = snippet.replace("```", "'''")
    meaningful = [line.rstrip() for line in cleaned.splitlines() if line.strip()]
    selected = meaningful[:MAX_EXCERPT_LINES]
    if not selected:
        return ""
    truncated = [_truncate_line(line) for line in selected]
    if len(meaningful) > len(selected):
        truncated.append("...")
    return "\n".join(truncated)


def _truncate_line(line: str) -> str:
    if len(line) <= MAX_EXCERPT_LINE_LENGTH:
        return line
    return line[: MAX_EXCERPT_LINE_LENGTH - 3].rstrip() + "..."


def _interesting_identifiers(snippet: str) -> tuple[str, ...]:
    identifiers: list[str] = []
    for token in re.findall(r"\b[A-Za-z_$][A-Za-z0-9_$]*\b", snippet):
        if len(token) < 4 or token in {"function", "return", "const", "var", "let", "this", "true", "false", "null"}:
            continue
        if token not in identifiers:
            identifiers.append(token)
        if len(identifiers) >= MAX_IDENTIFIER_COUNT:
            break
    return tuple(identifiers)


def _section(title: str, body: str) -> str:
    return f"**{title}**\n{body}"
