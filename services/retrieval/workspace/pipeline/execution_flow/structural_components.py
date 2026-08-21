from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from typing import Any, Mapping, Sequence

from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import DiscoveryObservation
from services.retrieval.workspace.pipeline.execution_flow.evidence_qualification import QualificationDecision
from services.retrieval.workspace.tools import ToolRequest


@dataclass(frozen=True)
class StructuralComponent:
    id: str
    observation_ids: tuple[str, ...]
    node_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StructuralComponentSelection:
    components: tuple[StructuralComponent, ...]
    edges: tuple[dict[str, Any], ...]
    tool_calls: int


def build_structural_components(
    observations: Sequence[DiscoveryObservation],
    decisions: Sequence[QualificationDecision],
    *,
    relationship_tool: Any,
    trace: Any | None = None,
    round_index: int = 0,
) -> StructuralComponentSelection:
    decision_by_id = {item.observation_id: item for item in decisions}
    eligible = [item for item in observations if decision_by_id.get(item.id, _REJECT).disposition == "promote"]
    node_to_observation = {item.handle.node_id: item.id for item in eligible if item.handle.node_id}
    edges: list[dict[str, Any]] = []
    tool_calls = 0
    if node_to_observation:
        request = ToolRequest(
            tool_name="structural_relationships_within_nodes",
            arguments={"node_ids": list(node_to_observation)},
            reason="Build graph-only components among already qualified observations.",
        )
        response = relationship_tool.run(request)
        if trace is not None:
            trace.record_tool(request, response, round_index=round_index)
        tool_calls += 1
        if response.status != "ok":
            raise RuntimeError("required_tool_failed: structural_relationships_within_nodes")
        edges = [dict(item) for item in response.payload.get("edges", ()) if isinstance(item, Mapping)]
        edges.extend(_collapsed_connector_edges(response.payload.get("connector_paths", ())))

    parent = {item.id: item.id for item in eligible}

    def find(value: str) -> str:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for edge in edges:
        source = edge.get("source") if isinstance(edge.get("source"), Mapping) else {}
        target = edge.get("target") if isinstance(edge.get("target"), Mapping) else {}
        left = node_to_observation.get(str(source.get("id") or ""))
        right = node_to_observation.get(str(target.get("id") or ""))
        if left and right:
            union(left, right)

    grouped: dict[str, list[DiscoveryObservation]] = {}
    for item in eligible:
        grouped.setdefault(find(item.id), []).append(item)
    components = tuple(
        _component(items)
        for items in sorted(grouped.values(), key=lambda values: tuple(sorted(item.id for item in values)))
    )
    result = StructuralComponentSelection(components, tuple(edges), tool_calls)
    if trace is not None:
        trace.record(
            "structural_components_created",
            {
                "round": round_index,
                "requested_node_ids": list(node_to_observation),
                "edges": edges,
                "components": [item.to_dict() for item in components],
            },
        )
    return result


def _component(observations: Sequence[DiscoveryObservation]) -> StructuralComponent:
    observation_ids = tuple(sorted(item.id for item in observations))
    node_ids = tuple(sorted(item.handle.node_id for item in observations if item.handle.node_id))
    identity = node_ids or observation_ids
    digest = hashlib.sha1("\0".join(identity).encode("utf-8")).hexdigest()[:16]
    return StructuralComponent(f"structural_{digest}", observation_ids, node_ids)


def _collapsed_connector_edges(paths: Any) -> list[dict[str, Any]]:
    """Represent an exact two-edge call path between promoted endpoints.

    The connector remains navigation context, not a promoted observation or evidence candidate.
    """
    if not isinstance(paths, Sequence) or isinstance(paths, (str, bytes)):
        return []
    result: list[dict[str, Any]] = []
    for item in paths:
        if not isinstance(item, Mapping):
            continue
        source = item.get("source") if isinstance(item.get("source"), Mapping) else {}
        connector = item.get("connector") if isinstance(item.get("connector"), Mapping) else {}
        target = item.get("target") if isinstance(item.get("target"), Mapping) else {}
        kinds = tuple(str(value) for value in item.get("edge_kinds", ()) if str(value))
        if not source.get("id") or not connector.get("id") or not target.get("id"):
            continue
        if kinds not in {
            ("calls", "calls"),
            ("source_qualified_call", "source_ast_call"),
        }:
            continue
        connector_name = str(connector.get("qualified_name") or connector.get("name") or connector.get("id"))
        native_graph_path = kinds == ("calls", "calls")
        result.append(
            {
                "kind": "calls",
                "source": dict(source),
                "target": dict(target),
                "connector": dict(connector),
                "detail": (
                    f"Exact two-call CodeGraph path via {connector_name}."
                    if native_graph_path
                    else f"Source-verified two-call path via exact CodeGraph owner {connector_name}."
                ),
                "_retrieval_provenance": (
                    "exact_codegraph_connector_path"
                    if native_graph_path
                    else "source_verified_connector_path"
                ),
            }
        )
    return result


_REJECT = QualificationDecision("", "reject", "insufficient", "missing")
