from __future__ import annotations

# Owns the top-level workspace retrieval orchestration only. It should call semantic flow modules and should not accumulate low-level candidate, validation, index, or connected-source helper logic.

from pathlib import Path
from typing import Mapping

from core.models import ConversationState, PolicyResult, RetrievalResult
from services.retrieval.workspace.pipeline.coverage import coverage_status as _coverage_status
from services.retrieval.workspace.pipeline.execution_flow.adaptive_loop import run_adaptive_retrieval_loop
from services.retrieval.workspace.pipeline.execution_flow.context import WorkspaceRetrievalContext
from services.retrieval.workspace.pipeline.execution_flow.connected_sources_flow import connected_source_context
from services.retrieval.workspace.pipeline.execution_flow.index_setup import (
    build_step2_repo_context,
    structural_tools as build_structural_tools,
    rebuild_index,
)
from services.retrieval.workspace.pipeline.execution_flow.narrowing import run_initial_narrowing
from services.retrieval.workspace.pipeline.execution_flow.run_outcomes import (
    apply_objective_role_selection,
    failed_result,
)
from services.retrieval.workspace.pipeline.evidence_flow import (
    append_accepted_decision_evidence as _append_accepted_decision_evidence,
    append_connected_source_evidence as _append_connected_source_evidence,
    drop_unhinted_late_connected_file_evidence as _drop_unhinted_late_connected_file_evidence,
    select_evidence_items as _select_evidence_items,
)
from services.retrieval.workspace.pipeline.file_level import (
    bucket_unresolved_roles as _bucket_unresolved_roles,
    coverage_area_names as _coverage_area_names,
)
from services.retrieval.workspace.step2 import (
    existing_evidence_plan,
    extract_prompt_evidence,
    plan_workspace_retrieval_step,
)
from services.retrieval.workspace.step2.common import ordered_unique
from services.retrieval.workspace.tools import OpenFileTool, QdrantHybridSearchTool, ToolObservation, ToolRequest


def run_workspace_retrieval(
    ctx: WorkspaceRetrievalContext,
    state: ConversationState,
    policy_result: PolicyResult,
) -> RetrievalResult:
    # Step 1: Reuse existing evidence if the conversation already has accepted context.
    # Existing evidence is treated as authoritative so retrieval does not spend tokens re-proving context.
    if state.evidence:
        retrieval_plan = existing_evidence_plan(
            conversation_id=state.conversation_id,
            raw_prompt=state.user_input,
            allowed_sources=policy_result.allowed_sources,
        )

        # ///////////////////////
        ctx.trace.record("retrieval_plan_created", retrieval_plan.to_dict())
        # ///////////////////////

        return RetrievalResult(
            evidence=tuple(state.evidence),
            coverage_status="sufficient_context",
            sufficient=True,
            retrieval_summary={
                "retriever": "workspace",
                "retrieval_plan": retrieval_plan.to_dict(),
                "source_registry": [entry.to_dict() for entry in ctx.config.source_registry()],
                "index_rebuilt": False,
                "tool_calls": 0,
                "exploration_rounds": 0,
                "stop_reason": "existing_context_sufficient",
            },
        )

    # Step 2: Refresh CodeGraph and sync BM25/Qdrant indexes.
    prompt_evidence = extract_prompt_evidence(state, policy_result.allowed_sources)
    structural_tools = build_structural_tools(ctx)
    # Structural refresh runs before semantic search so downstream graph/file anchors are based on the current workspace.
    if ctx.config.enable_indexing:

        # ///////////////////////
        structural_stage_started = ctx.trace.start_stage(
            "index_structural_graph",
            "Refreshing the code graph",
            workspace_root=ctx.config.workspace_root,
            index_dir=ctx.config.index_dir,
        )
        # ///////////////////////


        # ///////////////////////
        ctx.trace.record(
            "workspace_index_structural_graph_started",
            {
                "workspace_root": ctx.config.workspace_root,
                "index_dir": ctx.config.index_dir,
            },
        )
        # ///////////////////////

        index_observation = structural_tools["structural_index_repo"].run(
            ToolRequest(tool_name="structural_index_repo", arguments={}, reason="mandatory structural graph refresh")
        )

        # ///////////////////////
        ctx.trace.record_tool(ToolRequest(tool_name="structural_index_repo", arguments={}), index_observation, round_index=0)
        # ///////////////////////

        if index_observation.status != "ok":
            return failed_result(ctx, None, failure="structural_index_failed", observation=index_observation)

        # ///////////////////////
        ctx.trace.complete_stage(
            "index_structural_graph",
            "Refreshing the code graph",
            structural_stage_started,
            status="ok",
        )
        # ///////////////////////

    else:
        # Disabled indexing still produces a traceable observation so later summaries do not need special cases.
        index_observation = ToolObservation(
            tool_name="structural_index_repo",
            status="ok",
            payload={"skipped": True, "reason": "indexing_disabled"},
            metadata={"result_count": "1", "command": "skipped_indexing_disabled"},
        )

        # ///////////////////////
        ctx.trace.record_tool(ToolRequest(tool_name="structural_index_repo", arguments={}), index_observation, round_index=0)
        # ///////////////////////


    # BM25/Qdrant sync is kept in the main flow because later tools depend on the exact index object it returns.
    try:

        # ///////////////////////
        bm25_stage_started = ctx.trace.start_stage(
            "index_bm25_qdrant",
            "Syncing the local search indexes",
            workspace_root=ctx.config.workspace_root,
            index_dir=ctx.config.index_dir,
        )
        # ///////////////////////


        # ///////////////////////
        ctx.trace.record(
            "workspace_index_bm25_started",
            {
                "workspace_root": ctx.config.workspace_root,
                "index_dir": ctx.config.index_dir,
            },
        )
        # ///////////////////////

        index = rebuild_index(ctx)

        # ///////////////////////
        ctx.trace.complete_stage(
            "index_bm25_qdrant",
            "Syncing the local search indexes",
            bm25_stage_started,
            status="ok",
        )
        # ///////////////////////

    except RuntimeError as exc:
        failed_observation = ToolObservation(
            tool_name="qdrant_hybrid_search",
            status="failed",
            payload={"reason": str(exc)},
            metadata={"result_count": "0"},
        )
        return failed_result(ctx, None, failure="qdrant_index_sync_failed", observation=failed_observation)
    qdrant_tool = QdrantHybridSearchTool(
        index,
        qdrant_config=ctx.config.qdrant_config,
        embedding_config=ctx.config.embedding_config,
        cache_path=str(Path(ctx.config.index_dir) / "qdrant-embeddings-cache.json"),
    )
    open_file_tool = OpenFileTool(index)

    # Step 3: Build connected-source context and repository context hints.
    # Connected context influences planning, but repo context keeps Step2 grounded in actual indexed workspace files.

    # ///////////////////////
    connected_context_stage_started = ctx.trace.start_stage(
        "connected_context",
        "Collecting connected source context",
    )
    # ///////////////////////

    connected_context = connected_source_context(
        ctx,
        query=state.user_input,
        prompt_evidence=prompt_evidence.to_dict(),
        allowed_sources=policy_result.allowed_sources,
    )

    # ///////////////////////
    ctx.trace.complete_stage(
        "connected_context",
        "Collecting connected source context",
        connected_context_stage_started,
        selected_document_count=len(connected_context.selected_context_documents),
        available_document_count=len(connected_context.documents),
    )
    # ///////////////////////

    connected_documents = connected_context.selected_context_documents

    # ///////////////////////
    repo_context_stage_started = ctx.trace.start_stage(
        "repo_context",
        "Building repository context hints",
    )
    # ///////////////////////

    step2_repo_context, preplan_tool_calls = build_step2_repo_context(
        ctx,
        prompt_evidence,
        structural_tools["structural_find_exact_symbol"],
        index,
        connected_context=connected_context,
    )

    # ///////////////////////
    ctx.trace.complete_stage(
        "repo_context",
        "Building repository context hints",
        repo_context_stage_started,
        preplan_tool_calls=preplan_tool_calls,
        repo_context_file_count=len(step2_repo_context.get("candidate_files", []) or []),
    )
    # ///////////////////////


    # Step 4: Run Step2 planning and objective-role application.
    # Step2 decides intent/objectives first; objective-role selection then narrows the legacy role plan.

    # ///////////////////////
    retrieval_planning_stage_started = ctx.trace.start_stage(
        "retrieval_planning",
        "Planning the evidence search",
    )
    # ///////////////////////

    def record_step2_event(event_type: str, payload: Mapping[str, object]) -> None:

        # ///////////////////////
        ctx.trace.record(event_type, {"conversation_id": state.conversation_id, **payload})
        # ///////////////////////

    def record_step2_warning(payload: Mapping[str, object]) -> None:

        # ///////////////////////
        ctx.trace.record("llm_request_warning", {"conversation_id": state.conversation_id, **payload})
        # ///////////////////////

    retrieval_plan = plan_workspace_retrieval_step(
        state=state,
        policy_result=policy_result,
        connected_documents=connected_documents,
        llm_config=ctx.config.llm_config,
        prompt_evidence=prompt_evidence,
        repo_context=step2_repo_context,
        log_event=record_step2_event,
        log_warning=record_step2_warning,
    )
    retrieval_plan = apply_objective_role_selection(ctx, retrieval_plan)

    # ///////////////////////
    ctx.trace.record("retrieval_plan_created", retrieval_plan.to_dict())
    # ///////////////////////


    # ///////////////////////
    ctx.trace.complete_stage(
        "retrieval_planning",
        "Planning the evidence search",
        retrieval_planning_stage_started,
        required_roles=list(retrieval_plan.required_roles),
        supporting_roles=list(retrieval_plan.supporting_roles),
    )
    # ///////////////////////


    # Step 5: Run initial narrowing.
    # Initial narrowing bounds later role searches before they can fan out across unrelated files.

    # ///////////////////////
    initial_narrowing_stage_started = ctx.trace.start_stage(
        "initial_narrowing",
        "Narrowing the likely code areas",
    )
    # ///////////////////////

    global_narrowed_files, narrowing_observations, tool_call_count = run_initial_narrowing(
        ctx,
        retrieval_plan=retrieval_plan,
        structural_find_tool=structural_tools["structural_find_exact_symbol"],
        preplan_tool_calls=preplan_tool_calls,
    )

    # ///////////////////////
    ctx.trace.complete_stage(
        "initial_narrowing",
        "Narrowing the likely code areas",
        initial_narrowing_stage_started,
        narrowed_file_count=len(global_narrowed_files or ()),
        observation_count=len(narrowing_observations),
    )
    # ///////////////////////

    if global_narrowed_files is None:
        # If structural narrowing fails, continuing would turn role retrieval into noisy whole-repo search.
        failed_observation = narrowing_observations[0] if narrowing_observations else index_observation
        return failed_result(ctx, retrieval_plan, failure="structural_narrowing_failed", observation=failed_observation)

    # Step 6: Run the bounded retrieval loop.
    # The loop owns role retrieval, refinement, synthesis, recovery, protocol bridging, and deferred role promotion.

    loop_result = run_adaptive_retrieval_loop(
        ctx,
        retrieval_plan=retrieval_plan,
        qdrant_tool=qdrant_tool,
        open_file_tool=open_file_tool,
        structural_tools=structural_tools,
        narrowed_files=global_narrowed_files,
        starting_tool_call_count=tool_call_count,
    )
    required_buckets = loop_result.required_buckets
    supporting_buckets = loop_result.supporting_buckets
    synthesis_decision = loop_result.synthesis_decision
    deterministic_gate = loop_result.deterministic_gate
    tool_call_count = loop_result.tool_call_count
    responsibility_intents = loop_result.responsibility_intents

    # ///////////////////////
    ctx.trace.record(
        "adaptive_loop_stopped",
        {
            "stop_reason": loop_result.stop_reason,
            "exploration_rounds": loop_result.exploration_rounds,
            "adaptive_rounds": loop_result.adaptive_rounds,
            "promoted_roles": list(loop_result.promoted_roles),
            "promoted_objectives": list(loop_result.promoted_objectives),
        },
    )
    # ///////////////////////

    # Step 7: Select final evidence and build the retrieval result.
    # Evidence selection happens after all coverage updates so final items reflect accepted anchors, connected sources, and gate status.

    # ///////////////////////
    coverage_gate_stage_started = ctx.trace.start_stage(
        "coverage_gate",
        "Verifying coverage before explanation",
    )
    # ///////////////////////

    selected = _select_evidence_items(required_buckets, supporting_buckets, policy_result.allowed_sources)
    selected = _append_accepted_decision_evidence(
        selected,
        synthesis_decision=synthesis_decision,
        buckets=required_buckets + supporting_buckets,
        source_policy=policy_result.allowed_sources,
        workspace_root=ctx.config.workspace_root,
    )
    selected = _drop_unhinted_late_connected_file_evidence(
        selected,
        connected_file_hints=connected_context.file_hints,
    )
    selected = _append_connected_source_evidence(
        selected,
        connected_context=connected_context,
        source_policy=policy_result.allowed_sources,
    )

    # ///////////////////////
    ctx.trace.complete_stage(
        "coverage_gate",
        "Verifying coverage before explanation",
        coverage_gate_stage_started,
        selected_count=len(selected),
        supporting_bucket_count=len(supporting_buckets),
        coverage_status=_coverage_status(selected, synthesis_decision, retrieval_plan, deterministic_gate),
    )
    # ///////////////////////


    # ///////////////////////
    ctx.trace.record("deterministic_coverage_gate_completed", deterministic_gate.to_dict())
    # ///////////////////////

    for coverage_area in _coverage_area_names(retrieval_plan):
        bucket = next((item for item in required_buckets + supporting_buckets if item.role == coverage_area), None)
        status = bucket.role_status if bucket is not None else ("strong" if any(item.metadata.get("coverage_area") == coverage_area for item in selected) else "missing")

        # ///////////////////////
        ctx.trace.record("gap_check_completed", {"coverage_area": coverage_area, "status": status})
        # ///////////////////////

    for bucket in required_buckets + supporting_buckets:

        # ///////////////////////
        ctx.trace.record(
            "role_coverage_completed",
            {
                "role": bucket.role,
                "role_status": bucket.role_status,
                "accepted_count": len(bucket.accepted_candidates),
                "satisfying_count": len(bucket.satisfying_refs),
                "rejected_count": len(bucket.rejected_refs),
                "missing_reason": bucket.missing_reason,
            },
        )
        # ///////////////////////

    for item in selected:

        # ///////////////////////
        ctx.trace.record(
            "evidence_selected",
            {
                "source_id": item.source_id,
                "source_category": item.source_category.value,
                "rank": item.rank,
                "metadata": dict(item.metadata),
            },
        )
        # ///////////////////////


    retrieval_summary = {
        "retriever": "workspace",
        "retrieval_plan": retrieval_plan.to_dict(),
        "source_registry": [entry.to_dict() for entry in ctx.config.source_registry()],
        "connected_source_count": len(connected_context.documents),
        "connected_source_context": connected_context.to_dict(),
        "connected_sources": [
            {
                "source_category": document.source_category.value,
                "source_id": document.source_id,
                "title": document.title,
                "adapter": document.metadata.get("adapter", "connected_documents"),
            }
            for document in connected_context.documents[:20]
        ],
        "index_rebuilt": True,
        "index_document_count": len(index.documents),
        "selected_count": len(selected),
        "tool_calls": tool_call_count,
        "exploration_rounds": loop_result.exploration_rounds,
        "adaptive_rounds": loop_result.adaptive_rounds,
        "promoted_roles": list(loop_result.promoted_roles),
        "promoted_objectives": list(loop_result.promoted_objectives),
        "round_summaries": [dict(item) for item in loop_result.round_summaries],
        "stop_reason": loop_result.stop_reason or synthesis_decision.stop_reason or "late_synthesis_complete",
        "structural_graph_provider": "codegraph",
        "structural_index_provider": "codegraph",
        "structural_narrowed_file_count": len(global_narrowed_files),
        "qdrant_path_filter_count": len(global_narrowed_files),
        "required_role_buckets": [bucket.to_dict() for bucket in required_buckets],
        "supporting_role_buckets": [bucket.to_dict() for bucket in supporting_buckets],
        "refinement_policy": synthesis_decision.to_dict(),
        "responsibility_expansion_intents": [intent.to_dict() for intent in responsibility_intents],
        "deterministic_coverage_gate": deterministic_gate.to_dict(),
        "trusted_local_notes": [
            {
                "path": document.metadata.get("path", ""),
                "title": document.title,
                "score": float(document.metadata.get("score", 0.0) or 0.0),
                "selected_for_context": document.source_id in connected_context.selected_context_ids,
                "selected_for_evidence": document.source_id in connected_context.selected_evidence_ids,
            }
            for document in connected_context.documents
            if document.source_key == "local_notes"
        ],
        "trusted_local_note_file_hints": [
            path
            for path in connected_context.file_hints
            if any(document.source_key == "local_notes" for document in connected_context.selected_context_documents)
        ],
    }
    # Sufficiency requires selected evidence, LLM/deterministic synthesis acceptance, and deterministic role coverage.
    final_sufficient = bool(selected) and synthesis_decision.acceptance_satisfied and deterministic_gate.satisfied
    return RetrievalResult(
        evidence=tuple(selected),
        coverage_status=_coverage_status(selected, synthesis_decision, retrieval_plan, deterministic_gate),
        sufficient=final_sufficient,
        retrieval_summary=retrieval_summary,
        failures_or_fallbacks=tuple(ordered_unique([*_bucket_unresolved_roles(required_buckets), *deterministic_gate.missing_roles])),
    )
