from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import DiscoveryObservation
from services.retrieval.workspace.pipeline.execution_flow.evidence_qualification import QualificationDecision
from services.retrieval.workspace.tools import ToolRequest


@dataclass(frozen=True)
class EvidenceIsland:
    id: str
    observation_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IslandSelection:
    islands: tuple[EvidenceIsland, ...]
    active_root_ids: tuple[str, ...]
    inactive_promoted_ids: tuple[str, ...]
    edges: tuple[dict[str, Any], ...]
    tool_calls: int


def build_islands_and_select_roots(
    observations: Sequence[DiscoveryObservation],
    decisions: Sequence[QualificationDecision],
    *,
    relationship_tool: Any,
    max_active_roots: int = 4,
    trace: Any | None = None,
    round_index: int = 0,
) -> IslandSelection:
    decision_by_id = {item.observation_id: item for item in decisions}
    eligible = [item for item in observations if decision_by_id.get(item.id, _REJECT).disposition == "promote"]
    node_to_observation = {item.handle.node_id: item.id for item in eligible if item.handle.node_id}
    edges: list[dict[str, Any]] = []
    tool_calls = 0
    if node_to_observation:
        request = ToolRequest(
            tool_name="structural_relationships_within_nodes",
            arguments={"node_ids": list(node_to_observation)},
            reason="Build relationships only among already qualified observations.",
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
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for edge in edges:
        source = edge.get("source") if isinstance(edge.get("source"), Mapping) else {}
        target = edge.get("target") if isinstance(edge.get("target"), Mapping) else {}
        left = node_to_observation.get(str(source.get("id") or ""))
        right = node_to_observation.get(str(target.get("id") or ""))
        if left and right:
            union(left, right)

    components: dict[str, list[str]] = {}
    for item in eligible:
        components.setdefault(find(item.id), []).append(item.id)
    islands = tuple(
        EvidenceIsland(id=f"island_{index}", observation_ids=tuple(sorted(ids)))
        for index, ids in enumerate(sorted(components.values(), key=lambda value: tuple(sorted(value))), start=1)
    )
    observation_by_id = {item.id: item for item in eligible}
    ranked_islands = sorted(
        (
            (
                min(
                    island.observation_ids,
                    key=lambda observation_id: _root_key(
                        observation_by_id[observation_id], decision_by_id[observation_id]
                    ),
                ),
                island,
            )
            for island in islands
            if island.observation_ids
        ),
        key=lambda value: _root_key(observation_by_id[value[0]], decision_by_id[value[0]]),
    )
    # Preserve component diversity, but spend the bounded beam on the strongest
    # qualified components rather than whichever hashed observation IDs sort first.
    roots = [root_id for root_id, _island in ranked_islands[:max_active_roots]]
    remaining = sorted(
        (item.id for item in eligible if item.id not in roots),
        key=lambda observation_id: _root_key(observation_by_id[observation_id], decision_by_id[observation_id]),
    )
    roots.extend(remaining[: max(0, max_active_roots - len(roots))])
    inactive = tuple(item.id for item in eligible if item.id not in roots)
    result = IslandSelection(
        islands=islands,
        active_root_ids=tuple(roots),
        inactive_promoted_ids=inactive,
        edges=tuple(edges),
        tool_calls=tool_calls,
    )
    if trace is not None:
        trace.record(
            "closed_set_relationships_created",
            {
                "round": round_index,
                "requested_node_ids": list(node_to_observation),
                "edges": edges,
                "islands": [item.to_dict() for item in islands],
            },
        )
        trace.record(
            "active_roots_selected",
            {
                "round": round_index,
                "active_root_ids": list(result.active_root_ids),
                "inactive_promoted_ids": list(inactive),
            },
        )
    return result


def _root_key(observation: DiscoveryObservation, decision: QualificationDecision) -> tuple[Any, ...]:
    return (
        0 if observation.exact_anchor_matches else 1,
        -observation.recurrence,
        0 if decision.support_level == "direct_evidence" else 1,
        observation.best_rank,
        observation.handle.path.casefold(),
        observation.handle.line_start,
    )


_REJECT = QualificationDecision("", "reject", "insufficient", "missing")
