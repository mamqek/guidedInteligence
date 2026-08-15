from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import re
from typing import Any, Mapping, Sequence

from services.intent.models import EvidenceObligation
from services.retrieval.workspace.pipeline.execution_flow.coverage_evaluation import ObligationCoverage
from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import (
    DiscoveryObservation,
    aggregate_observations,
    observation_from_node,
    observation_from_result,
)
from services.retrieval.workspace.pipeline.execution_flow.evidence_qualification import QualificationDecision
from services.retrieval.workspace.tools import ToolRequest


@dataclass(frozen=True)
class InspectDeferredObservation:
    id: str
    observation_id: str
    requested_range: tuple[int, int]
    reason: str
    deferred_pool: bool = False
    priority: int = 0


@dataclass(frozen=True)
class ExpandRelationship:
    id: str
    obligation_id: str
    root_observation_id: str
    root_node_id: str
    direction: str
    edge_kinds: tuple[str, ...]
    need: str
    max_results: int = 3


@dataclass(frozen=True)
class SearchWithinFile:
    id: str
    obligation_id: str
    source_observation_id: str
    path: str
    dense_query: str
    sparse_anchors: tuple[str, ...] = ()
    result_limit: int = 3
    priority: int = 0


@dataclass(frozen=True)
class SearchNewIsland:
    id: str
    obligation_id: str
    dense_query: str
    sparse_anchors: tuple[str, ...] = ()
    exact_symbol_anchors: tuple[str, ...] = ()
    exact_path_anchors: tuple[str, ...] = ()
    result_limit: int = 6


@dataclass(frozen=True)
class StopRetrieval:
    id: str
    reason_code: str


RetrievalAction = InspectDeferredObservation | SearchWithinFile | ExpandRelationship | SearchNewIsland | StopRetrieval


@dataclass(frozen=True)
class ActionCatalogue:
    actions: tuple[RetrievalAction, ...]
    unavailable: tuple[dict[str, Any], ...]
    tool_calls: int


@dataclass(frozen=True)
class ActionExecution:
    action_id: str
    observations: tuple[DiscoveryObservation, ...]
    edges: tuple[dict[str, Any], ...]
    tool_calls: int
    status: str


def enumerate_actions(
    *,
    user_request: str,
    obligations: Sequence[EvidenceObligation],
    coverage: Sequence[ObligationCoverage],
    observations: Sequence[DiscoveryObservation],
    decisions: Sequence[QualificationDecision],
    cards: Sequence[Any],
    active_root_ids: Sequence[str],
    edge_capabilities_tool: Any,
    attempted_fingerprints: set[str],
    trace: Any | None = None,
    round_index: int = 0,
) -> ActionCatalogue:
    observation_by_id = {item.id: item for item in observations}
    decision_by_id = {item.observation_id: item for item in decisions}
    card_by_id = {str(item.observation_id): item for item in cards}
    obligation_by_id = {item.id: item for item in obligations}
    roots = [observation_by_id[item] for item in active_root_ids if item in observation_by_id]
    node_ids = [item.handle.node_id for item in roots if item.handle.node_id]
    capability_by_node: dict[str, dict[str, set[str]]] = {}
    tool_calls = 0
    if node_ids:
        request = ToolRequest(
            tool_name="structural_edge_capabilities",
            arguments={"node_ids": node_ids[:16]},
            reason="Enumerate only directional relationship actions represented around qualified roots.",
        )
        response = edge_capabilities_tool.run(request)
        if trace is not None:
            trace.record_tool(request, response, round_index=round_index)
        tool_calls += 1
        if response.status != "ok":
            raise RuntimeError("required_tool_failed: structural_edge_capabilities")
        for item in response.payload.get("nodes", ()):
            if not isinstance(item, Mapping):
                continue
            capability_by_node[str(item.get("node_id") or "")] = {
                "incoming": {str(value.get("kind") or "") for value in item.get("incoming", ()) if isinstance(value, Mapping)},
                "outgoing": {str(value.get("kind") or "") for value in item.get("outgoing", ()) if isinstance(value, Mapping)},
            }

    actions: list[RetrievalAction] = []
    unavailable: list[dict[str, Any]] = []
    for gap in coverage:
        if gap.status in {"covered", "external"} or gap.obligation_id not in obligation_by_id:
            continue
        obligation = obligation_by_id[gap.obligation_id]
        for observation_index, observation in enumerate(observations):
            decision = decision_by_id.get(observation.id)
            if gap.obligation_id not in observation.obligation_ids:
                continue
            handle = observation.handle
            if decision is None:
                action = InspectDeferredObservation(
                    id=_action_id("inspect_deferred_pool", gap.obligation_id, observation.id),
                    observation_id=observation.id,
                    requested_range=(
                        handle.full_line_start or handle.line_start,
                        handle.full_line_end or handle.line_end,
                    ),
                    reason=f"Inspect deferred discovery handle for unresolved obligation {gap.obligation_id}.",
                    deferred_pool=True,
                    priority=observation_index,
                )
                if action.id not in attempted_fingerprints:
                    actions.append(action)
                continue
            if handle.path and (
                decision.support_level == "navigation_only" or _is_strong_navigation_observation(observation)
            ):
                anchors = tuple(
                    dict.fromkeys(
                        value for value in (*observation.exact_anchor_matches, handle.symbol) if value
                    )
                )
                action = SearchWithinFile(
                    id=_action_id("within_file", gap.obligation_id, observation.id, handle.path, *anchors),
                    obligation_id=gap.obligation_id,
                    source_observation_id=observation.id,
                    path=handle.path,
                    dense_query=user_request,
                    sparse_anchors=anchors,
                    priority=_navigation_priority(observation, decision),
                )
                if action.id not in attempted_fingerprints:
                    actions.append(action)
            if decision.disposition != "defer":
                continue
            full_range = (handle.full_line_start or handle.line_start, handle.full_line_end or handle.line_end)
            if full_range == (handle.line_start, handle.line_end) and observation.disclosure_status != "fold":
                continue
            action = InspectDeferredObservation(
                id=_action_id("inspect", gap.obligation_id, observation.id, str(full_range)),
                observation_id=observation.id,
                requested_range=full_range,
                reason=gap.missing_claim or "Inspect the deferred owner with fuller source.",
                priority=observation_index,
            )
            if action.id not in attempted_fingerprints:
                actions.append(action)

        structural_added = False
        for root in roots:
            if not root.handle.node_id:
                continue
            for direction, kind in _relationships_for_need(gap.suggested_need):
                available = capability_by_node.get(root.handle.node_id, {}).get(direction, set())
                if kind not in available:
                    unavailable.append(
                        {
                            "obligation_id": gap.obligation_id,
                            "root_observation_id": root.id,
                            "direction": direction,
                            "edge_kind": kind,
                            "reason": "edge_kind_not_represented_around_root",
                        }
                    )
                    continue
                action = ExpandRelationship(
                    id=_action_id("expand", gap.obligation_id, root.id, direction, kind),
                    obligation_id=gap.obligation_id,
                    root_observation_id=root.id,
                    root_node_id=root.handle.node_id,
                    direction=direction,
                    edge_kinds=(kind,),
                    need=gap.suggested_need,
                )
                if action.id not in attempted_fingerprints:
                    actions.append(action)
                    structural_added = True
        learned_identifiers = tuple(
            sorted(
                dict.fromkeys(
                    identifier
                    for root in roots
                    for identifier in _source_call_identifiers(
                        str(getattr(card_by_id.get(root.id), "source_text", "") or "")
                    )
                ),
                key=lambda value: (0 if value.startswith("_") else 1, len(value), value.casefold()),
            )
        )
        if learned_identifiers or not structural_added:
            anchors = tuple(
                dict.fromkeys(
                    value
                    for value in (
                        *learned_identifiers,
                        *(value for root in roots for value in root.exact_anchor_matches),
                        *(root.handle.symbol for root in roots),
                    )
                    if value
                )
            )[:12]
            action = SearchNewIsland(
                id=_action_id("search", gap.obligation_id, obligation.description, *anchors),
                obligation_id=gap.obligation_id,
                dense_query=obligation.description,
                sparse_anchors=anchors,
                exact_symbol_anchors=tuple(value for value in anchors if value.isidentifier()),
            )
            if action.id not in attempted_fingerprints:
                actions.append(action)
    actions = list(dict.fromkeys(actions))
    if trace is not None:
        trace.record(
            "controller_actions_enumerated",
            {
                "round": round_index,
                "actions": [action_to_dict(item) for item in actions],
                "unavailable": unavailable,
            },
        )
    return ActionCatalogue(actions=tuple(actions), unavailable=tuple(unavailable), tool_calls=tool_calls)


def execute_action(
    action: RetrievalAction,
    *,
    observations: Sequence[DiscoveryObservation],
    relationship_tool: Any,
    qdrant_tool: Any,
    resolve_ranges_tool: Any,
    exact_symbol_tool: Any,
    trace: Any | None = None,
    round_index: int = 0,
) -> ActionExecution:
    if isinstance(action, InspectDeferredObservation):
        observation = next((item for item in observations if item.id == action.observation_id), None)
        if observation is None:
            raise RuntimeError(f"controller_action_invalid: unknown observation {action.observation_id}")
        handle = replace(
            observation.handle,
            line_start=action.requested_range[0],
            line_end=action.requested_range[1],
        )
        return ActionExecution(
            action_id=action.id,
            observations=(replace(observation, handle=handle, disclosure_status="undisclosed", ambiguity_count=1),),
            edges=(),
            tool_calls=0,
            status="ok",
        )
    if isinstance(action, ExpandRelationship):
        request = ToolRequest(
            tool_name="structural_expand_relationships",
            arguments={
                "node_ids": [action.root_node_id],
                "direction": action.direction,
                "edge_kinds": list(action.edge_kinds),
                "limit": action.max_results,
            },
            reason=f"Resolve {action.need} for {action.obligation_id} from a qualified root.",
        )
        response = relationship_tool.run(request)
        if trace is not None:
            trace.record_tool(request, response, round_index=round_index)
        if response.status != "ok":
            raise RuntimeError("required_tool_failed: structural_expand_relationships")
        created = tuple(
            item
            for node in response.payload.get("nodes", ())
            if isinstance(node, Mapping)
            if (item := observation_from_node(
                node,
                retriever="graph_action",
                query_id=action.id,
                obligation_ids=(action.obligation_id,),
                score=0.0,
                parent_observation_ids=(action.root_observation_id,),
                relationship_direction=action.direction,
                relationship_kinds=action.edge_kinds,
            )) is not None
        )
        return ActionExecution(
            action_id=action.id,
            observations=created,
            edges=tuple(dict(item) for item in response.payload.get("edges", ()) if isinstance(item, Mapping)),
            tool_calls=1,
            status="ok",
        )
    if isinstance(action, SearchWithinFile):
        return _execute_search(
            action_id=action.id,
            obligation_id=action.obligation_id,
            dense_query=action.dense_query,
            sparse_anchors=action.sparse_anchors,
            result_limit=action.result_limit,
            path=action.path,
            retriever="within_file_search",
            parent_observation_ids=(action.source_observation_id,),
            exact_symbol_anchors=(),
            qdrant_tool=qdrant_tool,
            resolve_ranges_tool=resolve_ranges_tool,
            exact_symbol_tool=exact_symbol_tool,
            trace=trace,
            round_index=round_index,
        )
    if isinstance(action, SearchNewIsland):
        return _execute_search(
            action_id=action.id,
            obligation_id=action.obligation_id,
            dense_query=action.dense_query,
            sparse_anchors=action.sparse_anchors,
            result_limit=action.result_limit,
            path="",
            retriever="new_island_search",
            parent_observation_ids=(),
            exact_symbol_anchors=action.exact_symbol_anchors,
            qdrant_tool=qdrant_tool,
            resolve_ranges_tool=resolve_ranges_tool,
            exact_symbol_tool=exact_symbol_tool,
            trace=trace,
            round_index=round_index,
        )
    return ActionExecution(action.id, (), (), 0, "stopped")


def action_to_dict(action: RetrievalAction) -> dict[str, Any]:
    return {"type": type(action).__name__, **asdict(action)}


def _relationships_for_need(need: str) -> tuple[tuple[str, str], ...]:
    if need == "trigger":
        return (("incoming", "calls"),)
    if need == "downstream":
        return (("outgoing", "calls"), ("outgoing", "instantiates"))
    if need == "implementation":
        return tuple(
            (direction, kind)
            for kind in ("implements", "overrides", "extends")
            for direction in ("incoming", "outgoing")
        )
    if need == "dependency":
        return (("outgoing", "imports"),)
    return ()


def _is_strong_navigation_observation(observation: DiscoveryObservation) -> bool:
    """Keep a bounded navigation use for repeated/exact hits even after evidence rejection."""
    return bool(observation.exact_anchor_matches) or (
        observation.recurrence >= 2 and observation.best_rank <= 5
    )


def _navigation_priority(
    observation: DiscoveryObservation,
    decision: QualificationDecision,
) -> int:
    return (
        (0 if observation.exact_anchor_matches else 10_000)
        - min(observation.recurrence, 20) * 100
        + max(0, observation.best_rank)
        + (0 if decision.support_level == "navigation_only" else 25)
    )


def _action_id(*parts: str) -> str:
    digest = hashlib.sha1("\0".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"action_{digest}"


def _expanded_sparse_anchors(anchors: Sequence[str]) -> tuple[str, ...]:
    values: list[str] = []
    for anchor in anchors:
        value = str(anchor).strip()
        if not value:
            continue
        values.append(value)
        values.extend(
            part
            for part in re.findall(r"[A-Za-z][A-Za-z0-9]*", value.replace("::", "_"))
            if len(part) >= 3 and part.casefold() not in {"test", "tests", "src"}
        )
    return tuple(dict.fromkeys(values))


def _execute_search(
    *,
    action_id: str,
    obligation_id: str,
    dense_query: str,
    sparse_anchors: Sequence[str],
    result_limit: int,
    path: str,
    retriever: str,
    parent_observation_ids: tuple[str, ...],
    exact_symbol_anchors: Sequence[str],
    qdrant_tool: Any,
    resolve_ranges_tool: Any,
    exact_symbol_tool: Any,
    trace: Any | None,
    round_index: int,
) -> ActionExecution:
    sparse_query = " ".join(dict.fromkeys((dense_query, *_expanded_sparse_anchors(sparse_anchors))))
    arguments: dict[str, Any] = {
        "query": dense_query,
        "sparse_query": sparse_query,
        "limit": result_limit,
        "max_per_path": 0 if path else 1,
        "source_category": "source_code",
        "file_role": "any",
    }
    if path:
        arguments["path"] = path
    exact_observations: list[DiscoveryObservation] = []
    tool_calls = 0
    for anchor in tuple(dict.fromkeys(exact_symbol_anchors))[:6]:
        exact_request = ToolRequest(
            tool_name="structural_find_exact_symbol",
            arguments={"query": anchor, "limit": 4},
            reason=f"Resolve exact source identifier {anchor} for {obligation_id}.",
        )
        exact_response = exact_symbol_tool.run(exact_request)
        if trace is not None:
            trace.record_tool(exact_request, exact_response, round_index=round_index)
        tool_calls += 1
        if exact_response.status != "ok":
            raise RuntimeError("required_tool_failed: structural_find_exact_symbol")
        nodes = [dict(item) for item in exact_response.payload.get("nodes", ()) if isinstance(item, Mapping)]
        for node in nodes[:4]:
            observation = observation_from_node(
                node,
                retriever="exact_action_anchor",
                query_id=action_id,
                obligation_ids=(obligation_id,),
                score=1.0,
                exact_anchor=anchor,
                parent_observation_ids=parent_observation_ids,
            )
            if observation is not None:
                exact_observations.append(replace(observation, ambiguity_count=max(1, len(nodes))))
    request = ToolRequest(
        tool_name="qdrant_hybrid_search",
        arguments=arguments,
        reason=(
            f"Search within qualified file {path} for {obligation_id}."
            if path
            else f"Search independently for unresolved obligation {obligation_id}."
        ),
    )
    response = qdrant_tool.run(request)
    if trace is not None:
        trace.record_tool(request, response, round_index=round_index)
    if response.status != "ok":
        raise RuntimeError("required_tool_failed: qdrant_hybrid_search")
    results = [dict(item) for item in response.payload.get("results", ()) if isinstance(item, Mapping)]
    ranges = [
        {"file": item.get("path"), "line_start": item.get("line_start"), "line_end": item.get("line_end")}
        for item in results
        if item.get("path") and item.get("line_start")
    ]
    nodes_by_range: dict[tuple[str, int, int], tuple[dict[str, Any], ...]] = {}
    tool_calls += 1
    if ranges:
        range_request = ToolRequest(
            tool_name="structural_resolve_ranges",
            arguments={"ranges": ranges},
            reason=f"Resolve {retriever} ranges for {obligation_id}.",
        )
        range_response = resolve_ranges_tool.run(range_request)
        if trace is not None:
            trace.record_tool(range_request, range_response, round_index=round_index)
        tool_calls += 1
        if range_response.status != "ok":
            raise RuntimeError("required_tool_failed: structural_resolve_ranges")
        for item in range_response.payload.get("results", ()):
            if not isinstance(item, Mapping):
                continue
            key = (str(item.get("file") or ""), int(item.get("line_start") or 0), int(item.get("line_end") or 0))
            nodes_by_range[key] = tuple(dict(node) for node in item.get("nodes", ()) if isinstance(node, Mapping))
    created: list[DiscoveryObservation] = []
    for rank, result in enumerate(results, start=1):
        key = (str(result.get("path") or ""), int(result.get("line_start") or 0), int(result.get("line_end") or 0))
        created.extend(
            observation_from_result(
                result,
                obligation_id=obligation_id,
                query_id=action_id,
                rank=rank,
                retriever=retriever,
                nodes=nodes_by_range.get(key, ()),
            )
        )
    bounded, _decisions = aggregate_observations(
        (*exact_observations, *created),
        limit=result_limit + min(3, len(exact_observations)),
    )
    if parent_observation_ids:
        bounded = tuple(replace(item, parent_observation_ids=parent_observation_ids) for item in bounded)
    return ActionExecution(action_id, bounded, (), tool_calls, "ok")


def _source_call_identifiers(source: str) -> tuple[str, ...]:
    ignored = {
        "if", "for", "while", "return", "assert", "len", "str", "int", "float", "list", "dict", "tuple",
        "isinstance", "issubclass", "type", "wrapper", "isnull", "notnull", "isscalar",
    }
    values = []
    for match in re.finditer(r"(?:\bself\.|\bthis\.|\b[A-Za-z_][A-Za-z0-9_]*\.)?([A-Za-z_][A-Za-z0-9_]*)\s*\(", source):
        value = match.group(1)
        if value.casefold() not in ignored:
            values.append(value)
    return tuple(dict.fromkeys(values))[:12]
