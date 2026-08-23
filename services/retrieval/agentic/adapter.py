from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from core.models import EvidenceItem, RetrievalResult
from core.source_policy import SourceCategory
from services.retrieval.agentic.contracts import (
    AgentBudget,
    AgentObligation,
    AgentRetrievalReport,
    AgentRetrievalRequest,
    AgentScope,
)
from services.retrieval.agentic.runtime import run_seeded_agent
from services.retrieval.agentic.seed_builder import initial_leads_from_observations


def run_agentic_downstream(
    *,
    ctx: Any,
    state: Any,
    obligations: Sequence[Any],
    observations: Sequence[Any],
    qdrant_tool: Any,
    structural_tools: Mapping[str, Any],
    starting_tool_calls: int,
    index_document_count: int,
    index_rebuilt: bool,
) -> RetrievalResult:
    leads = initial_leads_from_observations(observations)
    request = AgentRetrievalRequest(
        request_id=state.conversation_id,
        question=state.user_input,
        workspace_root=ctx.config.workspace_root,
        obligations=tuple(
            AgentObligation(
                id=str(item.id),
                description=str(item.description),
                required=bool(getattr(item, "required", True)),
                anchors=tuple(str(value) for value in getattr(item, "anchor_refs", ()) if str(value)),
            )
            for item in obligations
        ),
        initial_leads=leads,
        scope=AgentScope(
            excluded_paths=tuple(ctx.config.index_exclude_paths or ()),
            dense_search_enabled=ctx.config.agent_dense_search_enabled,
        ),
        budget=AgentBudget(
            max_iterations=ctx.config.agent_max_iterations,
            max_tool_calls=ctx.config.agent_max_tool_calls,
            max_tool_calls_per_iteration=ctx.config.agent_max_tool_calls_per_iteration,
            max_context_chars=ctx.config.agent_max_context_chars,
            max_source_lines=ctx.config.agent_max_source_lines,
            max_no_gain_iterations=ctx.config.agent_max_no_gain_iterations,
        ),
    )
    ctx.trace.record(
        "agent_initial_leads_created",
        {
            "lead_count": len(leads),
            "path_count": len({item.path for item in leads}),
            "leads": [item.to_dict(include_preview=False) for item in leads],
        },
    )
    report = run_seeded_agent(
        request,
        llm_config=ctx.config.llm_config,
        qdrant_tool=qdrant_tool,
        structural_tools=structural_tools,
        trace=ctx.trace,
    )
    evidence = tuple(
        EvidenceItem(
            source_category=_source_category(item.path, item.artifact_kind),
            source_id=f"workspace:{item.path}:L{item.line_start}-L{item.line_end}",
            snippet=item.source_text,
            rank=index,
            metadata={
                "path": item.path,
                "line_start": str(item.line_start),
                "line_end": str(item.line_end),
                "symbol": item.symbol,
                "artifact_kind": item.artifact_kind,
                "discovery_origin": item.discovery_origin,
                "agent_evidence_id": item.id,
                "obligation_ids": ",".join(item.obligation_ids),
                "parent_ids": ",".join(item.parent_ids),
            },
        )
        for index, item in enumerate(report.evidence, start=1)
    )
    summary = {
        "retriever": "seeded_agentic",
        "request_analysis": state.intent_context.to_dict() if state.intent_context else {},
        "retrieval_plan": {
            "strategy": "qdrant_codegraph_seeded_agent_v1",
            "obligations": [
                item.to_dict() if hasattr(item, "to_dict") else {"id": str(item.id), "description": str(item.description)}
                for item in obligations
            ],
        },
        "initial_lead_count": len(leads),
        "initial_path_count": len({item.path for item in leads}),
        "index_document_count": index_document_count,
        "index_rebuilt": index_rebuilt,
        "agent_status": report.status,
        "stop_reason": report.stop_reason,
        "findings": [asdict(item) for item in report.findings],
        "unresolved_questions": list(report.unresolved_questions),
        "agent_execution": dict(report.execution),
        "tool_calls": starting_tool_calls + int(report.execution.get("tool_calls", 0)),
    }
    return RetrievalResult(
        evidence=evidence,
        coverage_status="strong" if report.sufficient else ("partial" if evidence else "failed"),
        sufficient=report.sufficient,
        retrieval_summary=summary,
        failures_or_fallbacks=() if evidence else (report.stop_reason,),
    )


def _source_category(path: str, artifact_kind: str) -> SourceCategory:
    normalized = path.casefold().replace("\\", "/")
    suffix = Path(normalized).suffix
    if artifact_kind in {"documentation", "docs"} or suffix in {".md", ".rst", ".txt"}:
        return SourceCategory.DOCUMENTATION
    return SourceCategory.SOURCE_CODE
