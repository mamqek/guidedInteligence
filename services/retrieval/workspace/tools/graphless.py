"""Deterministic structural-tool boundary for the no-CodeGraph ablation."""

from __future__ import annotations

from typing import Any, Mapping

from services.retrieval.workspace.tools.contracts import ToolObservation, ToolRequest


_STRUCTURAL_TOOL_NAMES = (
    "structural_index_repo",
    "structural_find_exact_symbol",
    "structural_resolve_locations",
    "structural_resolve_ranges",
    "structural_file_outline",
    "structural_resolve_file_nodes",
    "structural_relationships_within_nodes",
    "structural_source_owner_calls",
    "structural_edge_capabilities",
    "structural_expand_relationships",
    "structural_expand_nodes",
    "structural_callers",
    "structural_callees",
    "structural_file_neighbors",
    "structural_qualified_references",
    "structural_relationship",
)


class GraphlessStructuralTool:
    """Return an explicit empty structural result without invoking CodeGraph.

    Raw Qdrant/BM25 ranges remain usable as range-level observations.  This tool
    intentionally contributes no owner, symbol, outline, or relationship, so
    graph-dependent continuations are not manufactured by a substitute parser.
    """

    def __init__(self, name: str) -> None:
        self.name = name

    def run(self, request: ToolRequest) -> ToolObservation:
        return ToolObservation(
            tool_name=self.name,
            status="ok",
            payload={
                "results": [],
                "nodes": [],
                "edges": [],
                "outlines": [],
                "capabilities": [],
                "batch_diagnostics": {"provider": "disabled"},
                "provider": "disabled",
            },
            metadata={"result_count": "0", "structural_provider": "disabled"},
        )


def graphless_structural_tools() -> Mapping[str, GraphlessStructuralTool]:
    return {name: GraphlessStructuralTool(name) for name in _STRUCTURAL_TOOL_NAMES}
