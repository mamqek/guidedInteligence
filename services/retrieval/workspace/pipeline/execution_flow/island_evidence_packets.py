from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping, Sequence

from services.retrieval.config import (
    FINAL_SELECTION_REPRESENTATION_ISLAND_PACKETS as ISLAND_PACKET_REPRESENTATION,
    FINAL_SELECTION_REPRESENTATION_MECHANISM_FLOWS as MECHANISM_FLOW_REPRESENTATION,
)

MAX_BASE_PACKET_CANDIDATES = 3
MAX_UNIQUE_NAVIGATION_ROUTES = 1


@dataclass(frozen=True)
class IslandPacketCandidate:
    candidate_id: str
    island_id: str
    request_chars: int
    score: float
    direct: bool
    obligation_bearing: bool
    navigation: bool
    roles: tuple[str, ...]
    path: str
    handoff_grounded: bool = False


@dataclass(frozen=True)
class IslandPacketSelection:
    candidate_ids: tuple[str, ...]
    flows: tuple[dict[str, Any], ...]
    connection_keys: tuple[tuple[str, str, str], ...]
    decisions: tuple[dict[str, Any], ...]
    packets: tuple[dict[str, Any], ...]
    used_chars: int
    budget_overshoot_chars: int


def select_island_evidence_packets(
    *,
    candidates: Sequence[IslandPacketCandidate],
    raw_flows: Sequence[Mapping[str, Any]],
    connections: Sequence[Mapping[str, str]],
    input_char_budget: int | None,
    initial_used_chars: int,
    mandatory_candidate_ids: Sequence[str] = (),
    mandatory_flows: Sequence[Mapping[str, Any]] = (),
) -> IslandPacketSelection:
    """Add island context without removing the unchanged selector's candidates."""

    by_id = {item.candidate_id: item for item in candidates}
    groups: dict[str, list[IslandPacketCandidate]] = {}
    for candidate in candidates:
        island_id = candidate.island_id or f"unmapped:{candidate.candidate_id}"
        groups.setdefault(island_id, []).append(candidate)

    connections_by_island: dict[str, list[dict[str, str]]] = {}
    for connection in connections:
        source_id = str(connection.get("from_candidate_id") or "")
        target_id = str(connection.get("to_candidate_id") or "")
        source = by_id.get(source_id)
        target = by_id.get(target_id)
        if source is None or target is None:
            continue
        source_island = source.island_id or f"unmapped:{source_id}"
        target_island = target.island_id or f"unmapped:{target_id}"
        if source_island == target_island:
            connections_by_island.setdefault(source_island, []).append(dict(connection))

    flows_by_island: dict[str, list[Mapping[str, Any]]] = {}
    for flow in raw_flows:
        flow_ids = [str(value) for value in flow.get("candidate_ids", ()) if str(value) in by_id]
        if len(flow_ids) < 2:
            continue
        island_ids = {
            by_id[candidate_id].island_id or f"unmapped:{candidate_id}"
            for candidate_id in flow_ids
        }
        if len(island_ids) == 1:
            flows_by_island.setdefault(next(iter(island_ids)), []).append(flow)

    mandatory_ids = {value for value in mandatory_candidate_ids if value in by_id}
    packets: list[dict[str, Any]] = []
    for island_id, members in groups.items():
        ranked = sorted(members, key=_candidate_rank)
        island_flows = flows_by_island.get(island_id, [])
        packet_connections = connections_by_island.get(island_id, [])
        best_flow = max(
            island_flows,
            key=lambda item: (
                float(item.get("score", 0.0)),
                len(item.get("connections", ())),
                len(item.get("candidate_ids", ())),
            ),
            default=None,
        )
        preferred_ids = [
            str(value)
            for value in (best_flow or {}).get("candidate_ids", ())
            if str(value) in by_id
        ]
        connected = len(members) > 1 and bool(packet_connections or best_flow)
        base = _role_diverse_candidates(
            ranked,
            preferred_ids=preferred_ids,
            limit=(1 if len(ranked) == 1 else MAX_BASE_PACKET_CANDIDATES),
            internal_connections=packet_connections,
            reserve_grounded_navigation=connected,
        )
        base_ids = [item.candidate_id for item in base]
        remaining_ids = [item.candidate_id for item in ranked if item.candidate_id not in base_ids]
        packets.append(
            {
                "packet_id": f"island_packet:{island_id}",
                "island_id": island_id,
                "kind": "connected" if connected else "singleton" if len(members) == 1 else "grouped",
                "base_candidate_ids": base_ids,
                "optional_candidate_ids": remaining_ids,
                "candidate_ids": [],
                "connection_count": len(packet_connections),
                "score": round(sum(by_id[value].score for value in base_ids), 4),
                "contains_direct": any(by_id[value].direct for value in base_ids),
                "contains_navigation": any(by_id[value].navigation for value in base_ids),
                "contains_mandatory_seed": any(value in mandatory_ids for value in members_by_id(members)),
            }
        )

    selected_ids: set[str] = set(mandatory_ids)
    selected_packets: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    used_chars = initial_used_chars

    for packet in packets:
        seed_ids = [
            item.candidate_id
            for item in groups[str(packet["island_id"])]
            if item.candidate_id in mandatory_ids
        ]
        if seed_ids:
            admitted = dict(packet)
            admitted["candidate_ids"] = list(seed_ids)
            selected_packets.append(admitted)

    def admit(packet: dict[str, Any], candidate: IslandPacketCandidate, decision: str) -> bool:
        nonlocal used_chars
        current_ids = list(packet["candidate_ids"])
        next_ids = [*current_ids, candidate.candidate_id]
        flow_delta = (
            _packet_flow_chars(packet["packet_id"], next_ids, packet["score"])
            - (_packet_flow_chars(packet["packet_id"], current_ids, packet["score"])
               if current_ids else 0)
        )
        added_chars = candidate.request_chars + flow_delta
        if input_char_budget is not None and used_chars + added_chars > input_char_budget:
            decisions.append(
                {
                    "packet_id": packet["packet_id"],
                    "island_id": packet["island_id"],
                    "candidate_ids": [candidate.candidate_id],
                    "decision": f"rejected_{decision}_input_budget",
                    "added_chars": added_chars,
                    "used_chars": used_chars,
                    "input_char_budget": input_char_budget,
                }
            )
            return False
        packet["candidate_ids"].append(candidate.candidate_id)
        selected_ids.add(candidate.candidate_id)
        used_chars += added_chars
        decisions.append(
            {
                "packet_id": packet["packet_id"],
                "island_id": packet["island_id"],
                "candidate_ids": [candidate.candidate_id],
                "decision": decision,
                "added_chars": added_chars,
                "used_chars": used_chars,
            }
        )
        return True

    def ensure_packet(packet: dict[str, Any]) -> dict[str, Any]:
        existing = next(
            (item for item in selected_packets if item["packet_id"] == packet["packet_id"]),
            None,
        )
        if existing is not None:
            return existing
        admitted = dict(packet)
        admitted["candidate_ids"] = []
        selected_packets.append(admitted)
        return admitted

    direct_paths = {item.path.casefold() for item in candidates if item.direct}
    unique_navigation_ids = {
        item.candidate_id
        for item in sorted(
            (
                item
                for item in candidates
                if item.navigation
                and item.handoff_grounded
                and item.path.casefold() not in direct_paths
                and item.candidate_id not in selected_ids
            ),
            key=_candidate_rank,
        )[:MAX_UNIQUE_NAVIGATION_ROUTES]
    }

    def ranked_packet_members(packet: Mapping[str, Any]) -> list[IslandPacketCandidate]:
        members = {item.candidate_id: item for item in groups[str(packet["island_id"])]}
        preferred = [
            members[candidate_id]
            for candidate_id in packet["base_candidate_ids"]
            if candidate_id in members
        ]
        preferred_ids = {item.candidate_id for item in preferred}
        return [
            *preferred,
            *sorted(
                (item for item in members.values() if item.candidate_id not in preferred_ids),
                key=_candidate_rank,
            ),
        ]

    def independent_representatives(packet: Mapping[str, Any]) -> list[IslandPacketCandidate]:
        return [
            item
            for item in ranked_packet_members(packet)
            if item.obligation_bearing or (item.navigation and item.handoff_grounded)
        ]

    def packet_rank(packet: Mapping[str, Any]) -> tuple[Any, ...]:
        ranked = independent_representatives(packet) or ranked_packet_members(packet)
        return (
            0 if any(item.candidate_id in unique_navigation_ids for item in ranked) else 1,
            _candidate_rank(ranked[0]),
            -float(packet["score"]),
            str(packet["island_id"]),
        )

    # Breadth precedes depth: after preserving the unchanged normal-flow
    # seeds, give every otherwise unrepresented qualified island one compact
    # opportunity before adding any sibling context to a seeded island.
    unrepresented_packets = [
        packet
        for packet in packets
        if independent_representatives(packet)
        if not any(
            item.candidate_id in selected_ids
            for item in groups[str(packet["island_id"])]
        )
    ]
    unrepresented_packets.sort(key=packet_rank)
    for packet in unrepresented_packets:
        candidate = next(
            item
            for item in independent_representatives(packet)
            if item.candidate_id not in selected_ids
        )
        decision = (
            "selected_unique_navigation_route"
            if candidate.candidate_id in unique_navigation_ids
            else "selected_independent_island_representative"
        )
        admit(ensure_packet(packet), candidate, decision)

    # Once breadth has had its bounded opportunity, complete the compact base
    # packet around islands that contain mandatory normal-flow seeds.
    seeded_packets = sorted(
        (packet for packet in packets if packet["contains_mandatory_seed"]),
        key=packet_rank,
    )
    for packet in seeded_packets:
        for candidate in ranked_packet_members(packet):
            if candidate.candidate_id in selected_ids:
                continue
            if candidate.candidate_id not in set(packet["base_candidate_ids"]):
                continue
            admit(
                ensure_packet(packet),
                candidate,
                "selected_seeded_island_base_member",
            )

    # Spend the residual budget round-robin so one represented connected or
    # grouped island cannot consume all sibling capacity before peers receive
    # another role-diverse member.
    enrichment_packets = sorted(
        (
            packet
            for packet in packets
            if packet["kind"] != "singleton"
            and any(
                item.candidate_id in selected_ids
                for item in groups[str(packet["island_id"])]
            )
        ),
        key=lambda packet: (
            0 if packet["contains_mandatory_seed"] else 1,
            *packet_rank(packet),
        ),
    )
    enrichment_queues = {
        str(packet["packet_id"]): [
            item
            for item in ranked_packet_members(packet)
            if item.candidate_id not in selected_ids
        ]
        for packet in enrichment_packets
    }
    while any(enrichment_queues.values()):
        for packet in enrichment_packets:
            queue = enrichment_queues[str(packet["packet_id"])]
            if not queue:
                continue
            candidate = queue.pop(0)
            admit(
                ensure_packet(packet),
                candidate,
                "selected_round_robin_island_member",
            )

    selected_connection_keys = tuple(
        (
            str(item.get("from_candidate_id") or ""),
            str(item.get("to_candidate_id") or ""),
            str(item.get("relationship") or ""),
        )
        for item in connections
        if str(item.get("from_candidate_id") or "") in selected_ids
        and str(item.get("to_candidate_id") or "") in selected_ids
    )
    packet_flows = tuple(
        {
            "flow_id": str(packet["packet_id"]),
            "candidate_ids": list(packet["candidate_ids"]),
            "score": packet["score"],
            "discovery_island_id": packet["island_id"],
            "packet_kind": packet["kind"],
        }
        for packet in selected_packets
        if packet["candidate_ids"]
    )
    request_flows = tuple(dict(item) for item in mandatory_flows) + packet_flows
    return IslandPacketSelection(
        candidate_ids=tuple(
            candidate.candidate_id for candidate in candidates if candidate.candidate_id in selected_ids
        ),
        flows=request_flows,
        connection_keys=selected_connection_keys,
        decisions=tuple(decisions),
        packets=tuple(selected_packets),
        used_chars=used_chars,
        budget_overshoot_chars=(
            max(0, used_chars - input_char_budget) if input_char_budget is not None else 0
        ),
    )


def members_by_id(members: Sequence[IslandPacketCandidate]) -> tuple[str, ...]:
    return tuple(item.candidate_id for item in members)


def _candidate_rank(candidate: IslandPacketCandidate) -> tuple[Any, ...]:
    substantive_roles = set(candidate.roles) & {"state_owner", "domain_owner", "controller"}
    return (
        0 if candidate.direct else 1,
        0 if substantive_roles else 1,
        -len(substantive_roles),
        -candidate.score,
        candidate.path.casefold(),
        candidate.candidate_id,
    )


def _role_diverse_candidates(
    ranked: Sequence[IslandPacketCandidate],
    *,
    preferred_ids: Sequence[str],
    limit: int,
    internal_connections: Sequence[Mapping[str, str]],
    reserve_grounded_navigation: bool,
) -> list[IslandPacketCandidate]:
    if not ranked or limit <= 0:
        return []
    by_id = {item.candidate_id: item for item in ranked}
    preferred = [by_id[value] for value in preferred_ids if value in by_id]
    pool = [*preferred, *(item for item in ranked if item.candidate_id not in set(preferred_ids))]
    connected_pairs = {
        frozenset((str(item.get("from_candidate_id") or ""), str(item.get("to_candidate_id") or "")))
        for item in internal_connections
    }
    selected: list[IslandPacketCandidate] = []
    selected_roles: set[str] = set()
    while pool and len(selected) < limit:
        pool.sort(
            key=lambda item: (
                0
                if not selected
                or any(
                    frozenset((item.candidate_id, other.candidate_id)) in connected_pairs
                    for other in selected
                )
                else 1,
                -len(set(item.roles) - selected_roles),
                *_candidate_rank(item),
            )
        )
        chosen = pool.pop(0)
        selected.append(chosen)
        selected_roles.update(chosen.roles)
    if reserve_grounded_navigation and not any(item.navigation for item in selected):
        connected_ids = {
            str(value)
            for connection in internal_connections
            for value in (
                connection.get("from_candidate_id") or "",
                connection.get("to_candidate_id") or "",
            )
        }
        grounded_navigation = sorted(
            (
                item
                for item in ranked
                if item.navigation
                and (item.candidate_id in connected_ids or item.candidate_id in preferred_ids)
            ),
            key=_candidate_rank,
        )
        if grounded_navigation:
            navigation = grounded_navigation[0]
            if len(selected) < limit:
                selected.append(navigation)
            else:
                replace_index = next(
                    (
                        index
                        for index in range(len(selected) - 1, -1, -1)
                        if not selected[index].navigation
                    ),
                    -1,
                )
                if replace_index >= 0:
                    selected[replace_index] = navigation
    return selected


def _packet_flow_chars(packet_id: str, candidate_ids: Sequence[str], score: float) -> int:
    return len(
        json.dumps(
            {
                "flow_id": packet_id,
                "candidate_ids": list(candidate_ids),
                "score": score,
            },
            sort_keys=True,
        )
    )
