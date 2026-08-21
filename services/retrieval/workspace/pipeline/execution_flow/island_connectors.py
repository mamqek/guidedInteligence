from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
import re
from typing import Any, Mapping, Sequence

from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import DiscoveryObservation
from services.retrieval.workspace.tools import ToolRequest


MAX_SOURCE_AST_OWNER_NODES = 40
MAX_SOURCE_AST_EXACT_RESOLUTIONS = 80
MAX_SOURCE_AST_CONNECTOR_PATHS = 40
SOURCE_AST_CALLABLE_NODE_KINDS = frozenset({"function", "method"})


@dataclass(frozen=True)
class IslandConnectorSelection:
    edges: tuple[dict[str, Any], ...]
    nodes: dict[str, dict[str, Any]]
    tool_calls: int


def discover_island_connectors(
    observations: Sequence[DiscoveryObservation],
    *,
    relationship_tool: Any,
    source_calls_tool: Any | None = None,
    exact_symbol_tool: Any | None = None,
    trace: Any | None = None,
    round_index: int = 0,
) -> IslandConnectorSelection:
    """Return all bounded relationships used to connect promoted observations.

    This is the single stage boundary for native CodeGraph edges, native one-owner
    connector paths, and language-routed source verification when CodeGraph omits
    a direct or one-owner call relationship.
    """
    node_ids = tuple(item.handle.node_id for item in observations if item.handle.node_id)
    if not node_ids:
        return IslandConnectorSelection((), {}, 0)

    request = ToolRequest(
        tool_name="structural_relationships_within_nodes",
        arguments={"node_ids": list(node_ids)},
        reason="Discover bounded relationships among already qualified observations.",
    )
    response = relationship_tool.run(request)
    if trace is not None:
        trace.record_tool(request, response, round_index=round_index)
    if response.status != "ok":
        raise RuntimeError("required_tool_failed: structural_relationships_within_nodes")

    nodes = {
        str(item.get("id") or ""): dict(item)
        for item in response.payload.get("nodes", ())
        if isinstance(item, Mapping) and str(item.get("id") or "")
    }
    edges = [dict(item) for item in response.payload.get("edges", ()) if isinstance(item, Mapping)]
    edges.extend(_collapsed_connector_edges(response.payload.get("connector_paths", ())))
    tool_calls = 1

    if source_calls_tool is not None and exact_symbol_tool is not None:
        source_edges, source_tool_calls = _source_verified_edges(
            observations,
            nodes,
            source_calls_tool=source_calls_tool,
            exact_symbol_tool=exact_symbol_tool,
            trace=trace,
            round_index=round_index,
        )
        edges.extend(source_edges)
        tool_calls += source_tool_calls

    return IslandConnectorSelection(tuple(_dedupe_edges(edges)), nodes, tool_calls)


def _collapsed_connector_edges(paths: Any) -> list[dict[str, Any]]:
    """Represent an exact two-edge call path between promoted endpoints."""
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
                "source_anchors": [
                    dict(anchor) for anchor in item.get("source_anchors", ()) if isinstance(anchor, Mapping)
                ],
            }
        )
    return result


def _source_verified_edges(
    observations: Sequence[DiscoveryObservation],
    nodes: Mapping[str, Mapping[str, Any]],
    *,
    source_calls_tool: Any,
    exact_symbol_tool: Any,
    trace: Any | None,
    round_index: int,
) -> tuple[list[dict[str, Any]], int]:
    """Recover exact direct and one-owner call links through the source-AST router."""
    known_nodes = {str(node_id): dict(node) for node_id, node in nodes.items()}
    by_node = {
        item.handle.node_id: item
        for item in observations
        if item.handle.node_id in known_nodes
        and str(known_nodes[item.handle.node_id].get("kind") or "") in SOURCE_AST_CALLABLE_NODE_KINDS
    }
    call_cache: dict[str, tuple[dict[str, Any], ...]] = {}
    symbol_cache: dict[str, tuple[dict[str, Any], ...]] = {}
    tool_calls = 0
    symbol_resolutions = 0

    def owner_calls(node_id: str) -> tuple[dict[str, Any], ...]:
        nonlocal tool_calls
        if node_id in call_cache:
            return call_cache[node_id]
        request = ToolRequest(
            tool_name="structural_source_owner_calls",
            arguments={"node": dict(known_nodes[node_id])},
            reason="Normalize source-level calls through the language AST adapter.",
        )
        response = source_calls_tool.run(request)
        if trace is not None:
            trace.record_tool(request, response, round_index=round_index)
        tool_calls += 1
        calls = tuple(
            dict(item) for item in response.payload.get("calls", ()) if isinstance(item, Mapping)
        ) if response.status == "ok" else ()
        call_cache[node_id] = calls
        return calls

    def symbols(name: str) -> tuple[dict[str, Any], ...]:
        nonlocal symbol_resolutions, tool_calls
        key = name.casefold()
        if key in symbol_cache:
            return symbol_cache[key]
        if symbol_resolutions >= MAX_SOURCE_AST_EXACT_RESOLUTIONS:
            return ()
        request = ToolRequest(
            tool_name="structural_find_exact_symbol",
            arguments={"query": name},
            reason="Resolve one AST-localized call target to an exact repository owner.",
        )
        response = exact_symbol_tool.run(request)
        if trace is not None:
            trace.record_tool(request, response, round_index=round_index)
        tool_calls += 1
        symbol_resolutions += 1
        values = tuple(
            dict(item) for item in response.payload.get("nodes", ()) if isinstance(item, Mapping)
        ) if response.status == "ok" else ()
        symbol_cache[key] = values
        return values

    def resolve(source: Mapping[str, Any], call: Mapping[str, Any]) -> dict[str, Any] | None:
        name = str(call.get("name") or "")
        if not name:
            return None
        matches = [item for item in symbols(name) if _call_can_target(source, call, item)]
        return matches[0] if len(matches) == 1 else None

    edges: list[dict[str, Any]] = []
    raw_paths: list[dict[str, Any]] = []
    seen_paths: set[tuple[str, str, str]] = set()
    for source_id, source_observation in tuple(by_node.items())[:MAX_SOURCE_AST_OWNER_NODES]:
        source = known_nodes[source_id]
        possible_targets = {
            node_id: observation
            for node_id, observation in by_node.items()
            if node_id != source_id and set(source_observation.obligation_ids) & set(observation.obligation_ids)
        }
        if not possible_targets:
            continue
        for first_call in owner_calls(source_id):
            # The source fallback is deliberately restricted to qualified calls;
            # ordinary same-owner calls should already be represented by CodeGraph.
            if not str(first_call.get("qualifier") or ""):
                continue
            first_target = resolve(source, first_call)
            first_target_id = str((first_target or {}).get("id") or "")
            if not first_target_id:
                continue

            if first_target_id in possible_targets:
                target = known_nodes[first_target_id]
                target_name = str(target.get("qualified_name") or target.get("name") or first_target_id)
                edges.append(
                    {
                        "kind": "calls",
                        "source": dict(source),
                        "target": dict(target),
                        "detail": f"Source-verified direct call to exact CodeGraph owner {target_name}.",
                        "_retrieval_provenance": "source_verified_direct_call",
                        "source_anchors": [
                            {
                                "path": str(source.get("path") or ""),
                                "line": int(first_call.get("line_start") or 0),
                            }
                        ],
                    }
                )
                continue

            connector = first_target
            connector_id = first_target_id
            if connector_id not in known_nodes:
                known_nodes[connector_id] = dict(connector)
            for second_call in owner_calls(connector_id):
                target = resolve(connector, second_call)
                target_id = str((target or {}).get("id") or "")
                if target_id not in possible_targets:
                    continue
                key = (source_id, connector_id, target_id)
                if key in seen_paths:
                    continue
                seen_paths.add(key)
                raw_paths.append(
                    {
                        "source": dict(source),
                        "connector": dict(connector),
                        "target": dict(known_nodes[target_id]),
                        "edge_kinds": ["source_qualified_call", "source_ast_call"],
                        "source_anchors": [
                            {"path": str(source.get("path") or ""), "line": int(first_call.get("line_start") or 0)},
                            {"path": str(connector.get("path") or ""), "line": int(second_call.get("line_start") or 0)},
                        ],
                    }
                )
                if len(raw_paths) >= MAX_SOURCE_AST_CONNECTOR_PATHS:
                    edges.extend(_collapsed_connector_edges(raw_paths))
                    return _dedupe_edges(edges), tool_calls
    edges.extend(_collapsed_connector_edges(raw_paths))
    return _dedupe_edges(edges), tool_calls


def _dedupe_edges(edges: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for edge in edges:
        source = edge.get("source") if isinstance(edge.get("source"), Mapping) else {}
        target = edge.get("target") if isinstance(edge.get("target"), Mapping) else {}
        key = (str(source.get("id") or ""), str(target.get("id") or ""), str(edge.get("kind") or ""))
        if not key[0] or not key[1] or key in seen:
            continue
        seen.add(key)
        result.append(dict(edge))
    return result


def _call_can_target(
    source: Mapping[str, Any], call: Mapping[str, Any], target: Mapping[str, Any],
) -> bool:
    source_path = str(source.get("path") or "").replace("\\", "/").casefold()
    target_path = str(target.get("path") or "").replace("\\", "/").casefold()
    qualifier = str(call.get("qualifier") or "").split(".")[-1]
    if not qualifier:
        return source_path == target_path
    qualifier_id = _normalized_identifier(qualifier)
    if qualifier_id in {"self", "cls"}:
        return source_path == target_path
    basename = _normalized_identifier(PurePosixPath(target_path).stem)
    qualified_owner = str(target.get("qualified_name") or "").split("::", 1)[0].split(".", 1)[0]
    return qualifier_id in {basename, _normalized_identifier(qualified_owner)}


def _normalized_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())
