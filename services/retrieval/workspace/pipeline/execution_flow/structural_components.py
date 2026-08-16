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


_REJECT = QualificationDecision("", "reject", "insufficient", "missing")
