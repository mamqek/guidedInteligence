from __future__ import annotations

# Owns initial structural narrowing from Step2 entities into candidate workspace files. Do not place role bucket retrieval, validation, synthesis, or index synchronization here.

from typing import Mapping

from services.retrieval.workspace.pipeline.execution_flow.context import WorkspaceRetrievalContext
from services.retrieval.workspace.step2 import WorkspaceRetrievalPlan
from services.retrieval.workspace.step2.common import merge_paths
from services.retrieval.workspace.tools import ToolObservation, ToolRequest


def run_initial_narrowing(
    ctx: WorkspaceRetrievalContext,
    *,
    retrieval_plan: WorkspaceRetrievalPlan,
    structural_find_tool: object,
    preplan_tool_calls: int,
) -> tuple[tuple[str, ...] | None, tuple[ToolObservation, ...], int]:
    narrowed_files = merge_paths(retrieval_plan.confirmed_file_hints, retrieval_plan.grounded_file_hints)
    observations: list[ToolObservation] = []
    tool_call_count = 1 + preplan_tool_calls
    for entity in (retrieval_plan.confirmed_entities or retrieval_plan.grounded_entities)[:4]:
        request = ToolRequest(
            tool_name="structural_find_exact_symbol",
            arguments={"query": entity, "limit": ctx.config.structural_graph_max_files},
            reason="Grounded symbol or identifier from the prompt for initial structural narrowing.",
        )
        observation = structural_find_tool.run(request)  # type: ignore[attr-defined]
        ctx.trace.record_tool(request, observation, round_index=0)
        tool_call_count += 1
        observations.append(observation)
        if observation.status != "ok":
            return None, tuple(observations), tool_call_count
        narrowed_files = merge_paths(narrowed_files_from_observation(ctx, observation), narrowed_files)
    return tuple(narrowed_files), tuple(observations), tool_call_count


def narrowed_files_from_observation(ctx: WorkspaceRetrievalContext, observation: ToolObservation) -> tuple[str, ...]:
    files = observation.payload.get("files", ())
    selected: list[str] = []
    seen: set[str] = set()
    for item in files:
        if not isinstance(item, Mapping):
            continue
        path = str(item.get("path", "")).strip().replace("\\", "/")
        if not path or path in seen:
            continue
        seen.add(path)
        selected.append(path)
        if len(selected) >= ctx.config.structural_graph_max_files:
            break
    return tuple(selected)
