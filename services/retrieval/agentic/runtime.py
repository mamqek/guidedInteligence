from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from services.llm.json_completion import complete_json
from services.retrieval.agentic.contracts import (
    AgentDecision,
    AgentEvidence,
    AgentRetrievalReport,
    AgentRetrievalRequest,
    AgentState,
    AgentToolCall,
    GroundedFinding,
    ProposedFinding,
)
from services.retrieval.agentic.tools import TOOL_NAMES, AgentToolExecutor, artifact_from_lead


SYSTEM_PROMPT = """You are the navigation controller for repository evidence retrieval.

The initial leads came from obligation-based Qdrant retrieval and CodeGraph grounding. Treat them as useful directions,
not as an allowed universe and not as evidence until source has been inspected. You may inspect adjacent source, open
any allowed repository file, follow graph nodes, or run exact and semantic searches over the full repository.

Maintain an evidence-seeking loop. Choose the smallest useful next operations based on what the source has established.
Do not recreate fixed evidence roles, qualification labels, evidence islands, or recovery categories. A finding is valid
only when its evidence IDs refer to inspected source text. Do not guess file paths, line ranges, artifact IDs, or node
IDs. If the available evidence is incomplete, keep investigating within budget or finish partial with explicit gaps.

You have no provider-native repository, shell, web, app, or MCP tools. The JSON tools listed in the working context are
the only operations available, and the caller executes them after your response. Never claim to have inspected source
that is not listed with inspected=true. On the first iteration, source is uninspected, so request tool_calls rather than
finishing. final_evidence_ids and finding evidence_ids must be exact inspected artifact IDs from the working context.

Return only JSON matching the schema. Use kind=tool_calls to investigate, kind=finish when the selected inspected
evidence is enough (or a useful explicit partial result is the best possible outcome), and kind=fail only for a genuine
blocking condition. Initial Qdrant rank affects orientation only; newly discovered evidence has equal eligibility.
"""


def run_seeded_agent(
    request: AgentRetrievalRequest,
    *,
    llm_config: Any,
    qdrant_tool: Any,
    structural_tools: Mapping[str, Any],
    trace: Any,
) -> AgentRetrievalReport:
    if not request.initial_leads:
        return AgentRetrievalReport(
            request_id=request.request_id,
            status="failed",
            sufficient=False,
            stop_reason="no_initial_leads",
            findings=(),
            evidence=(),
            unresolved_questions=("Initial Qdrant/CodeGraph discovery produced no repository leads.",),
            execution={"iterations": 0, "tool_calls": 0, "usage": _zero_usage()},
        )
    artifacts = {lead.id: artifact_from_lead(lead) for lead in request.initial_leads}
    state = AgentState(
        request=request,
        artifacts=artifacts,
        initial_lead_ids=tuple(lead.id for lead in request.initial_leads),
        open_questions=[item.description for item in request.obligations if item.required],
    )
    executor = AgentToolExecutor(qdrant_tool=qdrant_tool, structural_tools=structural_tools, trace=trace)
    trace.record(
        "agent_retrieval_started",
        {
            "request_id": request.request_id,
            "initial_lead_count": len(request.initial_leads),
            "initial_path_count": len({item.path for item in request.initial_leads}),
            "budget": asdict(request.budget),
            "model": getattr(llm_config, "model", ""),
            "api_style": getattr(llm_config, "api_style", ""),
        },
    )

    last_decision: AgentDecision | None = None
    while state.iteration < request.budget.max_iterations and state.tool_calls < request.budget.max_tool_calls:
        state.iteration += 1
        context = _working_context(state)
        trace.record(
            "agent_working_context_created",
            {
                "iteration": state.iteration,
                "serialized_chars": len(context),
                "context": json.loads(context),
            },
        )
        decision = _decide(state, context, llm_config=llm_config, trace=trace)
        last_decision = decision
        _apply_findings(state, decision.findings)
        state.open_questions = list(dict.fromkeys(value for value in decision.open_questions if value))
        trace.record(
            "agent_decision_created",
            {
                "iteration": state.iteration,
                "kind": decision.kind,
                "summary": decision.summary,
                "open_questions": list(decision.open_questions),
                "tool_calls": [asdict(item) for item in decision.tool_calls],
                "finding_count": len(decision.findings),
                "final_evidence_ids": list(decision.final_evidence_ids),
                "reason": decision.reason,
            },
        )
        if decision.kind == "finish":
            finish_errors = _finish_validation_errors(state, decision)
            if finish_errors:
                state.protocol_errors.extend(finish_errors)
                state.open_questions = list(dict.fromkeys((*state.open_questions, *finish_errors)))
                state.no_gain_iterations += 1
                trace.record(
                    "agent_finish_rejected",
                    {"iteration": state.iteration, "errors": finish_errors},
                )
                if state.no_gain_iterations >= state.request.budget.max_no_gain_iterations:
                    return _finalize(
                        state,
                        decision,
                        stop_reason="invalid_finish_repeated",
                        trace=trace,
                        force_partial=True,
                    )
                continue
            return _finalize(state, decision, stop_reason="agent_finished", trace=trace)
        if decision.kind == "fail":
            return _finalize(state, decision, stop_reason="agent_reported_failure", trace=trace, force_partial=True)

        selected_calls = []
        for call in decision.tool_calls[: request.budget.max_tool_calls_per_iteration]:
            if state.tool_calls + len(selected_calls) >= request.budget.max_tool_calls:
                break
            fingerprint = call.fingerprint()
            if fingerprint in state.attempted_operations:
                trace.record(
                    "agent_tool_call_deduplicated",
                    {"iteration": state.iteration, "tool": call.tool, "fingerprint": fingerprint},
                )
                continue
            state.attempted_operations.add(fingerprint)
            selected_calls.append(call)
        if not selected_calls:
            state.no_gain_iterations += 1
            if state.no_gain_iterations >= request.budget.max_no_gain_iterations:
                if _defer_no_gain_for_referenced_lead(state, trace=trace):
                    continue
                return _force_final_decision(
                    state,
                    llm_config=llm_config,
                    trace=trace,
                    trigger="no_executable_tool_call",
                )
            continue

        before_artifact_count = len(state.artifacts)
        before_inspected_count = sum(item.inspected for item in state.artifacts.values())
        state.recent_artifact_ids.clear()
        for call in selected_calls:
            executor.execute(state, call)
            state.tool_calls += 1
        after_inspected_count = sum(item.inspected for item in state.artifacts.values())
        gained = len(state.artifacts) > before_artifact_count or after_inspected_count > before_inspected_count
        state.no_gain_iterations = 0 if gained else state.no_gain_iterations + 1
        trace.record(
            "agent_iteration_completed",
            {
                "iteration": state.iteration,
                "artifact_count": len(state.artifacts),
                "inspected_count": after_inspected_count,
                "new_information": gained,
                "no_gain_iterations": state.no_gain_iterations,
                "tool_calls": state.tool_calls,
            },
        )
        if state.no_gain_iterations >= request.budget.max_no_gain_iterations:
            if _defer_no_gain_for_referenced_lead(state, trace=trace):
                continue
            return _force_final_decision(
                state,
                llm_config=llm_config,
                trace=trace,
                trigger="no_evidence_gain",
            )

    fallback = last_decision or AgentDecision(
        kind="fail", summary="Agent budget ended before a model decision completed.",
        open_questions=tuple(state.open_questions), reason="budget_exhausted",
    )
    return _finalize(state, fallback, stop_reason="budget_exhausted", trace=trace, force_partial=True)


def _force_final_decision(
    state: AgentState,
    *,
    llm_config: Any,
    trace: Any,
    trigger: str,
) -> AgentRetrievalReport:
    if not any(item.inspected and item.source_text.strip() for item in state.artifacts.values()):
        fallback = AgentDecision(
            kind="fail",
            summary="Investigation stopped without inspected source.",
            open_questions=tuple(state.open_questions),
            reason=trigger,
        )
        return _finalize(state, fallback, stop_reason=trigger, trace=trace, force_partial=True)
    if state.iteration >= state.request.budget.max_iterations:
        fallback = AgentDecision(
            kind="fail",
            summary="The decision budget ended before grounded synthesis.",
            open_questions=tuple(state.open_questions),
            reason=trigger,
        )
        return _finalize(state, fallback, stop_reason="budget_exhausted", trace=trace, force_partial=True)

    state.iteration += 1
    payload = json.loads(_working_context(state))
    payload["tools"] = []
    payload["remaining_budget"]["tool_calls"] = 0
    payload["controller_directive"] = (
        "Exploration has stopped because further tool calls made no progress. Return kind=finish now. "
        "Select the best inspected artifact IDs as final_evidence_ids and write source-grounded findings. "
        "Cover every obligation supported by the inspected text. Keep genuinely unsupported obligations or facts "
        "as concise open_questions; a useful partial result is valid. Do not request tools."
    )
    decision = _decide(
        state,
        json.dumps(payload, sort_keys=True),
        llm_config=llm_config,
        trace=trace,
    )
    _apply_findings(state, decision.findings)
    state.open_questions = list(dict.fromkeys(value for value in decision.open_questions if value))
    trace.record(
        "agent_forced_final_decision",
        {
            "iteration": state.iteration,
            "trigger": trigger,
            "kind": decision.kind,
            "finding_count": len(decision.findings),
            "final_evidence_ids": list(decision.final_evidence_ids),
            "open_questions": list(decision.open_questions),
        },
    )
    errors = _finish_validation_errors(state, decision)
    if decision.kind != "finish":
        errors.append(f"forced_final_decision_returned:{decision.kind}")
    if errors:
        state.protocol_errors.extend(errors)
        trace.record("agent_finish_rejected", {"iteration": state.iteration, "errors": errors})
    return _finalize(
        state,
        decision,
        stop_reason=f"forced_final_after_{trigger}",
        trace=trace,
        force_partial=bool(errors or decision.open_questions),
    )


def _working_context(state: AgentState) -> str:
    referenced_candidates = _referenced_lead_candidates(state)
    referenced_candidates.sort(
        key=lambda item: (
            0 if state.referenced_lead_reminders.get(str(item["lead"]["id"]), 0) > 0 else 1,
        )
    )
    reminded_ids = [
        item["lead"]["id"]
        for item in referenced_candidates
        if state.referenced_lead_reminders.get(str(item["lead"]["id"]), 0) > 0
    ]
    fixed_payload = {
        "question": state.request.question,
        "obligations": [item.to_dict() for item in state.request.obligations],
        "iteration": state.iteration,
        "grounded_findings": [asdict(item) for item in state.findings],
        "open_questions": state.open_questions,
        "protocol_errors": state.protocol_errors[-6:],
        "attempted_operations": list(sorted(state.attempted_operations))[-30:],
        "navigation_directive": (
            "A no-gain stop was deferred because inspected source references the listed stored leads. "
            "Inspect a referenced lead before repeating broad/empty searches, or finish with a grounded reason "
            "that it is unnecessary."
            if reminded_ids
            else ""
        ),
        "reminded_referenced_lead_ids": reminded_ids,
        "remaining_budget": {
            "iterations": state.request.budget.max_iterations - state.iteration + 1,
            "tool_calls": state.request.budget.max_tool_calls - state.tool_calls,
        },
        "tools": _tool_guidance(),
    }

    # Keep the state contract stable while progressively reducing repeated source
    # previews.  Inspected and recent artifacts overlap heavily during long runs;
    # fixed slicing previously allowed that duplication to make iteration N+1 fail.
    profiles = (
        (40, 240, 24, 700, 12, 1000, 12, 12),
        (20, 200, 10, 500, 6, 600, 10, 8),
        (8, 160, 6, 360, 4, 400, 8, 6),
        (4, 120, 4, 240, 2, 300, 6, 4),
    )
    serialized = ""
    for (
        initial_limit,
        initial_preview,
        inspected_limit,
        inspected_preview,
        recent_limit,
        recent_preview,
        outcome_limit,
        reference_limit,
    ) in profiles:
        initial = [
            state.artifacts[value].summary(preview_chars=initial_preview)
            for value in state.initial_lead_ids[:initial_limit]
        ]
        inspected = [
            item.summary(preview_chars=inspected_preview)
            for item in state.artifacts.values()
            if item.inspected
        ][-inspected_limit:]
        recent = [
            state.artifacts[value].summary(preview_chars=recent_preview)
            for value in state.recent_artifact_ids[-recent_limit:]
            if value in state.artifacts
        ]
        payload = {
            **fixed_payload,
            "initial_lead_summary": {
                "total": len(state.initial_lead_ids),
                "shown": len(initial),
                "note": "Use list_leads to inspect leads outside this bounded projection.",
                "leads": initial,
            },
            "inspected_artifacts": inspected,
            "recent_artifacts": recent,
            "recent_tool_outcomes": [item.to_dict() for item in state.tool_outcomes[-outcome_limit:]],
            "referenced_lead_candidates": referenced_candidates[:reference_limit],
        }
        serialized = json.dumps(payload, sort_keys=True)
        if len(serialized) <= state.request.budget.max_context_chars:
            return serialized
    raise RuntimeError("agent_context_budget_too_small_for_required_state")


def _referenced_lead_candidates(state: AgentState, *, limit: int = 12) -> list[dict[str, Any]]:
    references: dict[str, tuple[int, str, set[str]]] = {}
    for artifact in state.artifacts.values():
        if not artifact.inspected or not artifact.source_text:
            continue
        for priority, expression, terminal in _source_symbol_references(artifact.source_text):
            folded = terminal.casefold()
            previous = references.get(folded)
            if previous is None or priority < previous[0]:
                references[folded] = (priority, expression, {artifact.id})
            elif priority == previous[0]:
                previous[2].add(artifact.id)

    candidates = []
    for lead_position, artifact_id in enumerate(state.initial_lead_ids, start=1):
        artifact = state.artifacts[artifact_id]
        if artifact.inspected or not artifact.symbol:
            continue
        terminal = re.split(r"::|\.", artifact.symbol)[-1].strip()
        match = references.get(terminal.casefold())
        if match is None:
            continue
        priority, expression, referenced_by = match
        candidates.append(
            (
                priority,
                lead_position,
                {
                    "lead": artifact.summary(preview_chars=360),
                    "referenced_as": expression,
                    "referenced_by_artifact_ids": sorted(referenced_by),
                    "reason": "An inspected source range references this exact stored symbol; inspect it before broad search.",
                },
            )
        )
    candidates.sort(key=lambda value: (value[0], value[1]))
    return [value[2] for value in candidates[: max(1, limit)]]


def _source_symbol_references(source_text: str) -> tuple[tuple[int, str, str], ...]:
    values: dict[tuple[str, str], tuple[int, str, str]] = {}
    for match in re.finditer(r"\b(self|cls)\.([A-Za-z_]\w*)\b", source_text):
        expression = match.group(0)
        terminal = match.group(2)
        values[(expression.casefold(), terminal.casefold())] = (0, expression, terminal)
    for match in re.finditer(r"\b([A-Za-z_]\w*)\.([A-Za-z_]\w*)\b", source_text):
        expression = match.group(0)
        terminal = match.group(2)
        values.setdefault((expression.casefold(), terminal.casefold()), (1, expression, terminal))
    ignored = {"def", "class", "if", "for", "while", "return", "raise", "isinstance", "len", "range"}
    for match in re.finditer(r"(?<![.])\b([A-Za-z_]\w*)\s*\(", source_text):
        terminal = match.group(1)
        if terminal.casefold() in ignored:
            continue
        values.setdefault((terminal.casefold(), terminal.casefold()), (2, terminal, terminal))
    return tuple(sorted(values.values(), key=lambda value: (value[0], value[1].casefold())))


def _defer_no_gain_for_referenced_lead(state: AgentState, *, trace: Any) -> bool:
    candidates = _referenced_lead_candidates(state)
    actionable = [
        item
        for item in candidates
        if state.referenced_lead_reminders.get(str(item["lead"]["id"]), 0) == 0
    ]
    if not actionable:
        return False
    reminded_ids = [str(item["lead"]["id"]) for item in actionable[:3]]
    for artifact_id in reminded_ids:
        state.referenced_lead_reminders[artifact_id] = 1
    state.no_gain_iterations = 0
    trace.record(
        "agent_no_gain_deferred_for_referenced_leads",
        {
            "iteration": state.iteration,
            "lead_ids": reminded_ids,
            "reason": "Inspected source references exact uninspected stored symbols.",
        },
    )
    return True


def _decide(state: AgentState, context: str, *, llm_config: Any, trace: Any) -> AgentDecision:
    usage = _zero_usage()

    def log_event(event_type: str, payload: Mapping[str, Any]) -> None:
        if event_type == "llm_response_received":
            raw = payload.get("raw_response", {})
            raw_usage = raw.get("usage", {}) if isinstance(raw, Mapping) else {}
            if isinstance(raw_usage, Mapping):
                prompt_tokens = int(raw_usage.get("prompt_tokens") or raw_usage.get("input_tokens") or 0)
                completion_tokens = int(
                    raw_usage.get("completion_tokens") or raw_usage.get("output_tokens") or 0
                )
                usage["prompt_tokens"] += prompt_tokens
                usage["completion_tokens"] += completion_tokens
                usage["total_tokens"] += int(
                    raw_usage.get("total_tokens") or prompt_tokens + completion_tokens
                )
        trace.record(event_type, {"stage": "agent_decision", "iteration": state.iteration, **dict(payload)})

    response = complete_json(
        llm_config,
        (
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ),
        response_format=_decision_response_format(),
        log_event=log_event,
    )
    for key in state.usage:
        state.usage[key] += usage[key]
    return _decision_from_payload(response)


def _decision_from_payload(payload: Mapping[str, Any]) -> AgentDecision:
    kind = str(payload.get("kind") or "").strip()
    if kind not in {"tool_calls", "finish", "fail"}:
        raise RuntimeError(f"agent_decision_invalid_kind:{kind}")
    calls = []
    for value in payload.get("tool_calls", ()):
        if not isinstance(value, Mapping):
            continue
        tool = str(value.get("tool") or "")
        if tool not in TOOL_NAMES:
            raise RuntimeError(f"agent_decision_unknown_tool:{tool}")
        calls.append(
            AgentToolCall(
                tool=tool,
                purpose=str(value.get("purpose") or ""),
                expected_signal=str(value.get("expected_signal") or ""),
                lead_id=str(value.get("lead_id") or ""),
                path=str(value.get("path") or ""),
                line_start=max(0, int(value.get("line_start") or 0)),
                line_end=max(0, int(value.get("line_end") or 0)),
                node_id=str(value.get("node_id") or ""),
                direction=str(value.get("direction") or "outgoing"),
                query=str(value.get("query") or ""),
                limit=max(1, int(value.get("limit") or 12)),
            )
        )
    findings = tuple(
        ProposedFinding(
            statement=str(value.get("statement") or "").strip(),
            evidence_ids=tuple(str(item) for item in value.get("evidence_ids", ()) if str(item)),
            obligation_ids=tuple(str(item) for item in value.get("obligation_ids", ()) if str(item)),
        )
        for value in payload.get("findings", ())
        if isinstance(value, Mapping) and str(value.get("statement") or "").strip()
    )
    return AgentDecision(
        kind=kind,
        summary=str(payload.get("summary") or ""),
        open_questions=tuple(str(value) for value in payload.get("open_questions", ()) if str(value)),
        tool_calls=tuple(calls),
        findings=findings,
        final_evidence_ids=tuple(str(value) for value in payload.get("final_evidence_ids", ()) if str(value)),
        reason=str(payload.get("reason") or ""),
    )


def _apply_findings(state: AgentState, findings: Sequence[ProposedFinding]) -> None:
    existing = {(item.statement, item.evidence_ids) for item in state.findings}
    for value in findings:
        evidence_ids = tuple(
            item for item in value.evidence_ids
            if item in state.artifacts and state.artifacts[item].inspected
        )
        if not evidence_ids or (value.statement, evidence_ids) in existing:
            continue
        digest = hashlib.sha1(f"{value.statement}|{'|'.join(evidence_ids)}".encode("utf-8")).hexdigest()[:12]
        finding = GroundedFinding(
            id=f"finding_{digest}",
            statement=value.statement,
            evidence_ids=evidence_ids,
            obligation_ids=value.obligation_ids,
        )
        state.findings.append(finding)
        state.accepted_evidence_ids.update(evidence_ids)
        for evidence_id in evidence_ids:
            state.artifacts[evidence_id].status = "supports_finding"
        existing.add((value.statement, evidence_ids))


def _finish_validation_errors(state: AgentState, decision: AgentDecision) -> list[str]:
    errors: list[str] = []
    inspected_ids = {item.id for item in state.artifacts.values() if item.inspected and item.source_text.strip()}
    invalid_final_ids = [value for value in decision.final_evidence_ids if value not in inspected_ids]
    if not inspected_ids:
        errors.append("finish_rejected:no_source_has_been_inspected; request tool_calls")
    if invalid_final_ids:
        errors.append(
            "finish_rejected:final_evidence_ids_are_not_inspected_artifact_ids:"
            + ",".join(invalid_final_ids[:6])
        )
    grounded_finding_count = sum(
        1 for finding in decision.findings if any(value in inspected_ids for value in finding.evidence_ids)
    )
    if grounded_finding_count == 0:
        errors.append("finish_rejected:no_finding_references_inspected_source")
    return errors


def _finalize(
    state: AgentState,
    decision: AgentDecision,
    *,
    stop_reason: str,
    trace: Any,
    force_partial: bool = False,
) -> AgentRetrievalReport:
    requested_ids = tuple(dict.fromkeys((*decision.final_evidence_ids, *state.accepted_evidence_ids)))
    evidence = []
    for evidence_id in requested_ids[:12]:
        item = state.artifacts.get(evidence_id)
        if item is None or not item.inspected or not item.source_text.strip():
            continue
        _validate_artifact_source(state.request, item)
        evidence.append(
            AgentEvidence(
                id=item.id,
                path=item.path,
                line_start=item.line_start,
                line_end=item.line_end,
                source_text=item.source_text,
                symbol=item.symbol,
                artifact_kind=item.artifact_kind,
                obligation_ids=item.obligation_ids,
                discovery_origin=item.discovery_origin,
                parent_ids=item.parent_ids,
            )
        )
    evidence_ids = {item.id for item in evidence}
    findings = tuple(
        item for item in state.findings if any(value in evidence_ids for value in item.evidence_ids)
    )
    required_ids = {item.id for item in state.request.obligations if item.required}
    supported_ids = {value for item in findings for value in item.obligation_ids}
    complete = bool(evidence and findings) and (not required_ids or required_ids <= supported_ids)
    sufficient = complete and not force_partial and decision.kind == "finish" and not decision.open_questions
    status = "complete" if sufficient else ("partial" if evidence else "failed")
    initial_paths = {state.artifacts[value].path for value in state.initial_lead_ids}
    report = AgentRetrievalReport(
        request_id=state.request.request_id,
        status=status,
        sufficient=sufficient,
        stop_reason=stop_reason,
        findings=findings,
        evidence=tuple(evidence),
        unresolved_questions=tuple(decision.open_questions or state.open_questions),
        execution={
            "iterations": state.iteration,
            "tool_calls": state.tool_calls,
            "usage": dict(state.usage),
            "artifact_count": len(state.artifacts),
            "inspected_count": sum(item.inspected for item in state.artifacts.values()),
            "initial_lead_count": len(state.initial_lead_ids),
            "selected_outside_initial_paths": sum(item.path not in initial_paths for item in evidence),
            "remaining_uninspected_initial_leads": sum(
                not state.artifacts[value].inspected for value in state.initial_lead_ids
            ),
        },
    )
    trace.record(
        "agent_retrieval_completed",
        {
            "status": report.status,
            "sufficient": report.sufficient,
            "stop_reason": report.stop_reason,
            "evidence": [asdict(item) for item in report.evidence],
            "findings": [asdict(item) for item in report.findings],
            "unresolved_questions": list(report.unresolved_questions),
            "execution": dict(report.execution),
        },
    )
    return report


def _validate_artifact_source(request: AgentRetrievalRequest, item: Any) -> None:
    root = Path(request.workspace_root).resolve()
    target = (root / item.path).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(f"agent_evidence_outside_workspace:{item.path}") from exc
    lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    start = max(1, item.line_start)
    end = min(len(lines), max(start, item.line_end), start + request.budget.max_source_lines - 1)
    expected = "\n".join(f"{number}: {lines[number - 1]}" for number in range(start, end + 1))
    if expected != item.source_text:
        raise RuntimeError(f"agent_evidence_stale_or_invalid:{item.id}")


def _tool_guidance() -> list[dict[str, str]]:
    return [
        {"name": "list_leads", "use": "Find initial leads by optional query/path when they are outside the shown projection."},
        {"name": "inspect_lead", "use": "Read the bounded structural owner or raw range for a known lead_id."},
        {"name": "open_source", "use": "Read any allowed repository-relative path and bounded line range."},
        {"name": "graph_neighbors", "use": "Expand a known CodeGraph node_id; inspect returned source before citing it."},
        {"name": "exact_search", "use": "Search an exact identifier/string anywhere in the allowed repository."},
        {"name": "semantic_search", "use": "Run a new Qdrant hybrid query anywhere in the allowed repository."},
    ]


def _decision_response_format() -> dict[str, Any]:
    string_array = {"type": "array", "items": {"type": "string"}}
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "seeded_agent_decision",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind", "summary", "open_questions", "tool_calls", "findings", "final_evidence_ids", "reason"],
                "properties": {
                    "kind": {"type": "string", "enum": ["tool_calls", "finish", "fail"]},
                    "summary": {"type": "string"},
                    "open_questions": string_array,
                    "tool_calls": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": [
                                "tool", "purpose", "expected_signal", "lead_id", "path", "line_start",
                                "line_end", "node_id", "direction", "query", "limit",
                            ],
                            "properties": {
                                "tool": {"type": "string", "enum": list(TOOL_NAMES)},
                                "purpose": {"type": "string"},
                                "expected_signal": {"type": "string"},
                                "lead_id": {"type": "string"},
                                "path": {"type": "string"},
                                "line_start": {"type": "integer", "minimum": 0},
                                "line_end": {"type": "integer", "minimum": 0},
                                "node_id": {"type": "string"},
                                "direction": {"type": "string", "enum": ["incoming", "outgoing", "both"]},
                                "query": {"type": "string"},
                                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                            },
                        },
                    },
                    "findings": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["statement", "evidence_ids", "obligation_ids"],
                            "properties": {
                                "statement": {"type": "string"},
                                "evidence_ids": string_array,
                                "obligation_ids": string_array,
                            },
                        },
                    },
                    "final_evidence_ids": string_array,
                    "reason": {"type": "string"},
                },
            },
        },
    }


def _zero_usage() -> dict[str, int]:
    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
