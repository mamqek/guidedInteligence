from __future__ import annotations

# Owns top-level workspace retrieval orchestration. Request interpretation happens globally;
# this module only prepares repository indexes and executes obligation-grounded retrieval.

from pathlib import Path

from core.models import ConversationState, PolicyResult, RetrievalResult
from services.retrieval.workspace.pipeline.execution_flow.context import WorkspaceRetrievalContext
from services.retrieval.workspace.pipeline.execution_flow.connected_sources import collect_connected_context
from services.retrieval.workspace.pipeline.execution_flow.index_setup import (
    rebuild_index,
    structural_tools as build_structural_tools,
)
from services.retrieval.workspace.pipeline.execution_flow.obligation_retrieval import run_obligation_retrieval
from services.retrieval.workspace.pipeline.execution_flow.run_outcomes import failed_result
from services.retrieval.workspace.tools import QdrantHybridSearchTool, ToolObservation, ToolRequest


def run_workspace_retrieval(
    ctx: WorkspaceRetrievalContext,
    state: ConversationState,
    policy_result: PolicyResult,
) -> RetrievalResult:
    if state.evidence:
        return RetrievalResult(
            evidence=tuple(state.evidence),
            coverage_status="sufficient_context",
            sufficient=True,
            retrieval_summary={
                "retriever": "workspace",
                "request_analysis": state.intent_context.to_dict() if state.intent_context else {},
                "index_rebuilt": False,
                "tool_calls": 0,
                "exploration_rounds": 0,
                "stop_reason": "existing_context_sufficient",
            },
        )
    if state.intent_context is None or not state.intent_context.evidence_obligations:
        raise RuntimeError("Workspace retrieval requires global request analysis with evidence obligations.")

    tools = build_structural_tools(ctx)
    tool_calls = 0
    if ctx.config.enable_indexing:
        stage_started = ctx.trace.start_stage(
            "index_codegraph",
            "Synchronizing the structural repository graph",
            workspace_root=ctx.config.workspace_root,
        )
        request = ToolRequest(
            tool_name="structural_index_repo",
            arguments={},
            reason="Synchronize CodeGraph before obligation traversal.",
        )
        observation = tools["structural_index_repo"].run(request)
        ctx.trace.record_tool(request, observation, round_index=0)
        tool_calls += 1
        ctx.trace.complete_stage(
            "index_codegraph",
            "Synchronizing the structural repository graph",
            stage_started,
            status=observation.status,
        )
        if observation.status != "ok":
            return failed_result(ctx, failure="codegraph_index_failed", observation=observation)

    try:
        stage_started = ctx.trace.start_stage(
            "index_bm25_qdrant",
            "Synchronizing semantic repository indexes",
            workspace_root=ctx.config.workspace_root,
            index_dir=ctx.config.index_dir,
        )
        index_setup = rebuild_index(ctx)
        index = index_setup.index
        ctx.trace.complete_stage(
            "index_bm25_qdrant",
            "Synchronizing semantic repository indexes",
            stage_started,
            status="ok",
            document_count=len(index.documents),
        )
    except RuntimeError as exc:
        observation = ToolObservation(
            tool_name="qdrant_hybrid_search",
            status="failed",
            payload={"reason": str(exc)},
            metadata={"result_count": "0"},
        )
        return failed_result(ctx, failure="qdrant_index_sync_failed", observation=observation)

    qdrant_tool = QdrantHybridSearchTool(
        index,
        qdrant_config=ctx.config.qdrant_config,
        embedding_config=ctx.config.embedding_config,
        cache_path=str(Path(ctx.config.index_dir) / "qdrant-embeddings-cache.json"),
    )
    connected_context = collect_connected_context(
        ctx,
        query=state.user_input,
        prompt_evidence=state.intent_context.to_dict(),
        allowed_sources=policy_result.allowed_sources,
    )
    stage_started = ctx.trace.start_stage(
        "obligation_retrieval",
        "Resolving and traversing request evidence obligations",
        obligation_count=len(state.intent_context.evidence_obligations),
    )
    result = run_obligation_retrieval(
        ctx,
        state,
        qdrant_tool=qdrant_tool,
        structural_tools=tools,
        index_document_count=len(index.documents),
        starting_tool_calls=tool_calls,
        connected_context=connected_context,
        index_rebuilt=index_setup.rebuilt,
    )
    ctx.trace.complete_stage(
        "obligation_retrieval",
        "Resolving and traversing request evidence obligations",
        stage_started,
        status="ok",
        coverage_status=result.coverage_status,
        sufficient=result.sufficient,
        selected_count=len(result.evidence),
    )
    for item in result.evidence:
        ctx.trace.record(
            "evidence_selected",
            {
                "source_id": item.source_id,
                "source_category": item.source_category.value,
                "rank": item.rank,
                "metadata": dict(item.metadata),
            },
        )
    return result
