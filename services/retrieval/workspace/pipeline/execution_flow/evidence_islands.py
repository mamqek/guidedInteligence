from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
from pathlib import PurePosixPath
from typing import Any, Mapping, Sequence

from services.retrieval.workspace.pipeline.execution_flow.coverage_evaluation import ObligationCoverage
from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import DiscoveryObservation
from services.retrieval.workspace.pipeline.execution_flow.evidence_qualification import QualificationDecision
from services.retrieval.workspace.pipeline.execution_flow.source_disclosure import DisclosureCard
from services.retrieval.workspace.pipeline.execution_flow.structural_components import StructuralComponentSelection


@dataclass(frozen=True)
class EvidenceIsland:
    id: str
    observation_ids: tuple[str, ...]
    normalized_files: tuple[str, ...] = ()
    enclosing_owners: tuple[str, ...] = ()
    obligation_ids: tuple[str, ...] = ()
    unresolved_obligation_ids: tuple[str, ...] = ()
    qualification_support: tuple[str, ...] = ()
    exact_anchors: tuple[str, ...] = ()
    action_provenance: tuple[str, ...] = ()
    structural_component_ids: tuple[str, ...] = ()
    representative_observation_id: str = ""
    subsystem_id: str = ""
    predecessor_ids: tuple[str, ...] = ()
    rank_features: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["rank_features"] = dict(self.rank_features)
        return value


@dataclass(frozen=True)
class IslandSelection:
    islands: tuple[EvidenceIsland, ...]
    active_root_ids: tuple[str, ...]
    inactive_promoted_ids: tuple[str, ...]
    edges: tuple[dict[str, Any], ...]
    tool_calls: int
    active_island_ids: tuple[str, ...] = ()
    observation_to_island: Mapping[str, str] = field(default_factory=dict)
    selection_reasons: Mapping[str, str] = field(default_factory=dict)


def build_semantic_islands(
    observations: Sequence[DiscoveryObservation],
    decisions: Sequence[QualificationDecision],
    cards: Sequence[DisclosureCard],
    coverage: Sequence[ObligationCoverage],
    structural: StructuralComponentSelection,
    *,
    beam_size: int = 3,
    previous: IslandSelection | None = None,
    trace: Any | None = None,
    round_index: int = 0,
) -> IslandSelection:
    if beam_size <= 0:
        raise ValueError("semantic island beam_size must be greater than zero")
    decision_by_id = {item.observation_id: item for item in decisions}
    observation_by_id = {
        item.id: item for item in observations
        if decision_by_id.get(item.id, _REJECT).disposition == "promote"
    }
    card_by_id = {item.observation_id: item for item in cards}
    unresolved = {
        item.obligation_id for item in coverage
        if item.status not in {"covered", "external"}
    }
    parent = {item_id: item_id for item_id in observation_by_id}

    def find(value: str) -> str:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(left: str, right: str) -> None:
        if left not in parent or right not in parent:
            return
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    merge_events: list[dict[str, Any]] = []

    def merge(left: str, right: str, reason: str) -> None:
        if left not in parent or right not in parent or find(left) == find(right):
            return
        union(left, right)
        merge_events.append({"left": left, "right": right, "reason": reason})

    if previous is not None:
        for island in previous.islands:
            surviving = [item for item in island.observation_ids if item in observation_by_id]
            for item in surviving[1:]:
                merge(surviving[0], item, "preserve_prior_island")

    owner_groups: dict[str, list[str]] = {}
    for observation_id, observation in observation_by_id.items():
        owner = _owner_identity(observation, card_by_id.get(observation_id))
        if owner:
            owner_groups.setdefault(owner, []).append(observation_id)
    for ids in owner_groups.values():
        for item in ids[1:]:
            merge(ids[0], item, "same_enclosing_owner")

    # Parent IDs exist only for bounded path-local or represented relationship
    # actions. Broad independent searches intentionally have no parent.
    for observation in observation_by_id.values():
        for parent_id in observation.parent_observation_ids:
            merge(observation.id, parent_id, "bounded_action_handoff")

    action_groups: dict[str, list[str]] = {}
    for observation in observation_by_id.values():
        for provenance in observation.provenance:
            if provenance.retriever in {"within_file_search", "graph_action"}:
                action_groups.setdefault(provenance.query_id, []).append(observation.id)
    for ids in action_groups.values():
        for left_index, left in enumerate(ids):
            for right in ids[left_index + 1:]:
                if _overlapping_unresolved(observation_by_id[left], observation_by_id[right], unresolved):
                    merge(left, right, "same_bounded_action_and_obligation")

    node_to_observation = {
        item.handle.node_id: item.id for item in observation_by_id.values() if item.handle.node_id
    }
    for edge in structural.edges:
        source = edge.get("source") if isinstance(edge.get("source"), Mapping) else {}
        target = edge.get("target") if isinstance(edge.get("target"), Mapping) else {}
        left = node_to_observation.get(str(source.get("id") or ""))
        right = node_to_observation.get(str(target.get("id") or ""))
        if left and right and _overlapping_unresolved(observation_by_id[left], observation_by_id[right], unresolved):
            merge(left, right, "structural_edge_and_obligation")

    grouped: dict[str, list[str]] = {}
    for observation_id in observation_by_id:
        grouped.setdefault(find(observation_id), []).append(observation_id)
    previous_by_observation = {
        observation_id: island.id
        for island in (previous.islands if previous else ())
        for observation_id in island.observation_ids
    }
    component_by_observation = {
        observation_id: component.id
        for component in structural.components
        for observation_id in component.observation_ids
    }
    islands = tuple(
        _make_island(
            tuple(ids), observation_by_id, decision_by_id, card_by_id, unresolved,
            component_by_observation, previous_by_observation,
        )
        for ids in sorted(grouped.values(), key=lambda values: tuple(sorted(values)))
    )
    ranked = sorted(
        islands,
        key=lambda item: _root_key(
            observation_by_id[item.representative_observation_id],
            decision_by_id[item.representative_observation_id],
        ),
    )
    active, reasons = _select_diverse_beam(ranked, beam_size)
    active_roots = tuple(
        observation_id
        for island in active
        for observation_id in sorted(
            island.observation_ids,
            key=lambda value: _root_key(observation_by_id[value], decision_by_id[value]),
        )
    )
    active_observations = set(active_roots)
    inactive = tuple(item for item in observation_by_id if item not in active_observations)
    mapping = {
        observation_id: island.id
        for island in islands
        for observation_id in island.observation_ids
    }
    result = IslandSelection(
        islands=islands,
        active_root_ids=active_roots,
        inactive_promoted_ids=inactive,
        edges=structural.edges,
        tool_calls=structural.tool_calls,
        active_island_ids=tuple(item.id for item in active),
        observation_to_island=mapping,
        selection_reasons=reasons,
    )
    if trace is not None:
        trace.record(
            "semantic_islands_created",
            {
                "round": round_index,
                "beam_size": beam_size,
                "core_support_counts": {
                    "direct_evidence": sum(
                        1 for item in observation_by_id if decision_by_id[item].support_level == "direct_evidence"
                    ),
                    "navigation_only": sum(
                        1 for item in observation_by_id if decision_by_id[item].support_level == "navigation_only"
                    ),
                },
                "merge_events": merge_events,
                "islands": [item.to_dict() for item in islands],
                "active_island_ids": list(result.active_island_ids),
                "active_root_ids": list(result.active_root_ids),
                "inactive_promoted_ids": list(result.inactive_promoted_ids),
                "selection_reasons": dict(reasons),
            },
        )
    return result


def _make_island(
    ids: tuple[str, ...],
    observations: Mapping[str, DiscoveryObservation],
    decisions: Mapping[str, QualificationDecision],
    cards: Mapping[str, DisclosureCard],
    unresolved: set[str],
    component_by_observation: Mapping[str, str],
    previous_by_observation: Mapping[str, str],
) -> EvidenceIsland:
    ordered_ids = tuple(sorted(ids))
    representative = min(ordered_ids, key=lambda value: _root_key(observations[value], decisions[value]))
    files = tuple(sorted({observations[item].handle.path.casefold() for item in ordered_ids}))
    owners = tuple(sorted(filter(None, (_owner_identity(observations[item], cards.get(item)) for item in ordered_ids))))
    obligations = tuple(sorted({value for item in ordered_ids for value in observations[item].obligation_ids}))
    unresolved_ids = tuple(value for value in obligations if value in unresolved)
    support = tuple(sorted({decisions[item].support_level for item in ordered_ids}))
    anchors = tuple(sorted({value for item in ordered_ids for value in observations[item].exact_anchor_matches}))
    provenance = tuple(sorted({
        entry.query_id for item in ordered_ids for entry in observations[item].provenance
        if entry.retriever in {"within_file_search", "graph_action"}
    }))
    components = tuple(sorted({component_by_observation[item] for item in ordered_ids if item in component_by_observation}))
    predecessors = tuple(sorted({previous_by_observation[item] for item in ordered_ids if item in previous_by_observation}))
    island_id = _stable_island_id(ordered_ids, owners, files, predecessors)
    root = observations[representative]
    return EvidenceIsland(
        id=island_id,
        observation_ids=ordered_ids,
        normalized_files=files,
        enclosing_owners=owners,
        obligation_ids=obligations,
        unresolved_obligation_ids=unresolved_ids,
        qualification_support=support,
        exact_anchors=anchors,
        action_provenance=provenance,
        structural_component_ids=components,
        representative_observation_id=representative,
        subsystem_id=_subsystem_identity(root, cards.get(representative)),
        predecessor_ids=predecessors if len(predecessors) > 1 else (),
        rank_features={
            "inherited_from_observation_id": representative,
            "exact_anchor": bool(root.exact_anchor_matches),
            "recurrence": root.recurrence,
            "qualification_support": decisions[representative].support_level,
            "best_rank": root.best_rank,
        },
    )


def _select_diverse_beam(
    ranked: Sequence[EvidenceIsland], beam_size: int,
) -> tuple[tuple[EvidenceIsland, ...], dict[str, str]]:
    remaining = list(ranked)
    selected: list[EvidenceIsland] = []
    reasons: dict[str, str] = {}
    covered_obligations: set[str] = set()
    covered_subsystems: set[str] = set()
    while remaining and len(selected) < beam_size:
        if not selected:
            chosen, reason = remaining[0], "best_inherited_member_rank"
        else:
            chosen = next(
                (item for item in remaining if set(item.unresolved_obligation_ids) - covered_obligations),
                None,
            )
            reason = "adds_unresolved_obligation"
            if chosen is None:
                chosen = next(
                    (item for item in remaining if item.subsystem_id not in covered_subsystems),
                    None,
                )
                reason = "adds_subsystem"
            if chosen is None:
                chosen, reason = remaining[0], "next_inherited_member_rank"
        selected.append(chosen)
        remaining.remove(chosen)
        reasons[chosen.id] = reason
        covered_obligations.update(chosen.unresolved_obligation_ids)
        covered_subsystems.add(chosen.subsystem_id)
    return tuple(selected), reasons


def _stable_island_id(
    observation_ids: Sequence[str], owners: Sequence[str], files: Sequence[str], predecessors: Sequence[str],
) -> str:
    if len(predecessors) == 1:
        return predecessors[0]
    # A file is not a semantic identity: two unrelated range-only observations
    # in one file must remain distinct unless an explicit merge rule joins them.
    identity = tuple(sorted(predecessors)) if predecessors else tuple(owners) or tuple(observation_ids)
    digest = hashlib.sha1("\0".join(identity).encode("utf-8")).hexdigest()[:16]
    return f"island_{digest}"


def _owner_identity(observation: DiscoveryObservation, card: DisclosureCard | None) -> str:
    path = observation.handle.path.casefold()
    if card and card.owner_name:
        return f"{path}:{card.owner_kind}:{card.owner_name}:{card.owner_line_start}:{card.owner_line_end}"
    if observation.handle.node_id:
        return f"{path}:node:{observation.handle.node_id}"
    return ""


def _subsystem_identity(observation: DiscoveryObservation, card: DisclosureCard | None) -> str:
    path = PurePosixPath(observation.handle.path.casefold())
    parent = str(path.parent)
    owner = (card.owner_name if card else observation.handle.symbol).split("::", 1)[0].split(".", 1)[0]
    return f"{parent}:{owner.casefold()}" if owner else parent


def _overlapping_unresolved(
    left: DiscoveryObservation, right: DiscoveryObservation, unresolved: set[str],
) -> bool:
    left_ids = set(left.obligation_ids) & unresolved
    right_ids = set(right.obligation_ids) & unresolved
    return bool(left_ids & right_ids)


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
