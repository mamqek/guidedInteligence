from __future__ import annotations

from core.models import RetrievalResult
from services.retrieval.workspace.pipeline.execution_flow.context import WorkspaceRetrievalContext
from services.retrieval.workspace.tools import ToolObservation


def failed_result(
    ctx: WorkspaceRetrievalContext,
    *,
    failure: str,
    observation: ToolObservation,
) -> RetrievalResult:
    ctx.trace.record(
        "retrieval_failed",
        {
            "failure": failure,
            "tool_name": observation.tool_name,
            "status": observation.status,
            "payload": dict(observation.payload),
        },
    )
    return RetrievalResult(
        evidence=(),
        coverage_status="failed",
        sufficient=False,
        retrieval_summary={
            "retriever": "workspace",
            "source_registry": [entry.to_dict() for entry in ctx.config.source_registry()],
            "structural_graph_provider": "codegraph",
            "failure": failure,
            "failure_reason": str(observation.payload.get("reason", "")),
        },
        failures_or_fallbacks=(failure,),
    )
