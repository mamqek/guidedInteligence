from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from core.models import ConversationState, EvidenceItem, RetrievalResult
from core.source_policy import SourceCategory
from services.intent.models import EvidenceObligation
from services.retrieval.workspace.pipeline.execution_flow.context import WorkspaceRetrievalContext
from services.retrieval.workspace.connected_context import ConnectedSourceContextResult
from services.retrieval.workspace.tools import ToolRequest


MAX_OBLIGATIONS = 10
MAX_EVIDENCE = 14
MAX_PER_OBLIGATION = 2


@dataclass(frozen=True)
class GroundedCandidate:
    path: str
    line_start: int
    line_end: int
    text: str
    score: float
    origin: str
    node_id: str = ""
    symbol: str = ""
    relationship: str = ""


@dataclass
class ObligationProgress:
    obligation: EvidenceObligation
    status: str = "pending"
    candidates: list[GroundedCandidate] = field(default_factory=list)
    unresolved_reason: str = ""
    transitions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.obligation.to_dict(),
            "status": self.status,
            "unresolved_reason": self.unresolved_reason or None,
            "transitions": [dict(item) for item in self.transitions],
            "evidence": [
                {
                    "path": item.path,
                    "line_start": item.line_start,
                    "line_end": item.line_end,
                    "node_id": item.node_id or None,
                    "symbol": item.symbol or None,
                    "origin": item.origin,
                    "relationship": item.relationship or None,
                    "score": round(item.score, 4),
                }
                for item in self.candidates[:MAX_PER_OBLIGATION]
            ],
        }


def run_obligation_retrieval(
    ctx: WorkspaceRetrievalContext,
    state: ConversationState,
    *,
    qdrant_tool: Any,
    structural_tools: Mapping[str, Any],
    index_document_count: int,
    starting_tool_calls: int,
    connected_context: ConnectedSourceContextResult | None = None,
) -> RetrievalResult:
    intent_context = state.intent_context
    if intent_context is None or not intent_context.evidence_obligations:
        raise RuntimeError("Workspace obligation retrieval requires global request-analysis obligations.")

    obligations = intent_context.evidence_obligations[:MAX_OBLIGATIONS]
    connected_context = connected_context or ConnectedSourceContextResult()
    progress = {item.id: ObligationProgress(item) for item in obligations}
    tool_calls = starting_tool_calls

    anchor_queries = ordered_unique(
        (
            *intent_context.anchors.symbols,
            *connected_context.symbol_hints,
        )
    )[:12]
    anchor_nodes: list[dict[str, Any]] = []
    unresolved_symbol_anchors: list[str] = []
    ambiguous_symbol_anchors: list[str] = []
    for anchor_query in anchor_queries:
        request = ToolRequest(
            tool_name="structural_find_exact_symbol",
            arguments={"query": anchor_query, "limit": 12},
            reason=f"Resolve the exact request-analysis symbol {anchor_query}.",
        )
        observation = structural_tools["structural_find_exact_symbol"].run(request)
        ctx.trace.record_tool(request, observation, round_index=0)
        tool_calls += 1
        if observation.status != "ok":
            raise RuntimeError(f"CodeGraph exact-symbol resolution failed: {observation.payload.get('reason', 'unknown error')}")
        nodes = [dict(node) for node in observation.payload.get("nodes", ()) if isinstance(node, Mapping)]
        match_count = int(observation.payload.get("match_count") or len(nodes))
        if match_count == 1 and len(nodes) == 1:
            anchor_nodes.extend({**node, "anchor_query": anchor_query} for node in nodes)
        elif match_count > 1:
            ambiguous_symbol_anchors.append(anchor_query)
        else:
            unresolved_symbol_anchors.append(anchor_query)

    semantic_by_obligation: dict[str, list[dict[str, Any]]] = {item.id: [] for item in obligations}
    for obligation in obligations:
        query = _obligation_query(
            obligation.description,
            (*unresolved_symbol_anchors, *ambiguous_symbol_anchors),
        )
        request = ToolRequest(
            tool_name="qdrant_hybrid_search",
            arguments={"query": query, "limit": 8, "source_category": "source_code", "file_role": "any"},
            reason=f"Find conceptual anchors for evidence obligation {obligation.id}.",
        )
        observation = qdrant_tool.run(request)
        ctx.trace.record_tool(request, observation, round_index=0)
        tool_calls += 1
        if observation.status != "ok":
            raise RuntimeError(f"Semantic anchor search failed for {obligation.id}.")
        semantic_by_obligation[obligation.id] = [
            dict(item) for item in observation.payload.get("results", ()) if isinstance(item, Mapping)
        ][:4]

    locations = [
        {"file": str(item.get("path") or ""), "line": int(item.get("line_start") or 0)}
        for values in semantic_by_obligation.values()
        for item in values
        if str(item.get("path") or "") and int(item.get("line_start") or 0) > 0
    ]
    location_nodes: dict[tuple[str, int], list[dict[str, Any]]] = {}
    if locations:
        request = ToolRequest(
            tool_name="structural_resolve_locations",
            arguments={"locations": locations},
            reason="Map semantic chunk anchors back to CodeGraph nodes.",
        )
        observation = structural_tools["structural_resolve_locations"].run(request)
        ctx.trace.record_tool(request, observation, round_index=0)
        tool_calls += 1
        if observation.status != "ok":
            raise RuntimeError("CodeGraph could not ground semantic result locations.")
        for result in observation.payload.get("results", ()):
            if isinstance(result, Mapping):
                key = (str(result.get("file") or ""), int(result.get("line") or 0))
                location_nodes[key] = [dict(node) for node in result.get("nodes", ()) if isinstance(node, Mapping)]

    seed_obligations: dict[str, set[str]] = {}
    for obligation in obligations:
        obligation_terms = _distinctive_terms(obligation.description)
        for node in anchor_nodes:
            score = _overlap_score(obligation_terms, _node_text(node))
            if score <= 0:
                continue
            candidate = _candidate_from_node(ctx, node, score=score + 1.0, origin="request_anchor")
            if candidate is not None:
                progress[obligation.id].candidates.append(candidate)
                if candidate.node_id:
                    seed_obligations.setdefault(candidate.node_id, set()).add(obligation.id)
        for result in semantic_by_obligation[obligation.id]:
            path = str(result.get("path") or "")
            line_start = int(result.get("line_start") or 0)
            nodes = location_nodes.get((path, line_start), [])
            node = nodes[0] if nodes else {}
            support_score = _semantic_support_score(obligation_terms, result)
            if support_score <= 0:
                continue
            candidate = GroundedCandidate(
                path=path,
                line_start=line_start,
                line_end=int(result.get("line_end") or line_start),
                text=str(result.get("text") or ""),
                score=support_score + float(result.get("score") or 0.0),
                origin="semantic_anchor",
                node_id=str(node.get("id") or ""),
                symbol=str(node.get("qualified_name") or node.get("name") or ""),
            )
            progress[obligation.id].candidates.append(candidate)
            if candidate.node_id:
                seed_obligations.setdefault(candidate.node_id, set()).add(obligation.id)

    expanded_edges: list[dict[str, Any]] = []
    if seed_obligations:
        request = ToolRequest(
            tool_name="structural_expand_nodes",
            arguments={"node_ids": list(seed_obligations), "depth": 1, "limit": 160},
            reason="Expand only one graph hop from nodes already assigned to unresolved evidence obligations.",
        )
        observation = structural_tools["structural_expand_nodes"].run(request)
        ctx.trace.record_tool(request, observation, round_index=1)
        tool_calls += 1
        if observation.status != "ok":
            raise RuntimeError("CodeGraph obligation expansion failed.")
        expanded_edges = [dict(edge) for edge in observation.payload.get("edges", ()) if isinstance(edge, Mapping)]
        node_by_id = {
            str(node.get("id") or ""): dict(node)
            for node in observation.payload.get("nodes", ())
            if isinstance(node, Mapping) and str(node.get("id") or "")
        }
        for edge in expanded_edges:
            source = edge.get("source") if isinstance(edge.get("source"), Mapping) else {}
            target = edge.get("target") if isinstance(edge.get("target"), Mapping) else {}
            source_id = str(source.get("id") or "")
            target_id = str(target.get("id") or "")
            for seed_id, other_id in ((source_id, target_id), (target_id, source_id)):
                for obligation_id in seed_obligations.get(seed_id, ()):
                    obligation_terms = _distinctive_terms(progress[obligation_id].obligation.description)
                    node = node_by_id.get(other_id, {})
                    score = _overlap_score(obligation_terms, _node_text(node))
                    if score <= 0:
                        continue
                    candidate = _candidate_from_node(
                        ctx,
                        node,
                        score=score,
                        origin="graph_neighbor",
                        relationship=str(edge.get("kind") or "related"),
                    )
                    if candidate is not None:
                        progress[obligation_id].candidates.append(candidate)

    for obligation in obligations:
        item = progress[obligation.id]
        item.candidates = _dedupe_candidates(item.candidates)
        item.status = "supported" if item.candidates else "unresolved"
        if item.status == "unresolved":
            item.unresolved_reason = "No repository-grounded graph node or semantic chunk supported this obligation."

    edge_index = _edge_index(expanded_edges)
    for obligation in obligations:
        item = progress[obligation.id]
        for dependency_id in obligation.depends_on:
            dependency = progress[dependency_id]
            transition = _transition_from_edges(dependency, item, edge_index)
            if transition is None:
                transition, added_calls = _resolve_file_transition(
                    ctx,
                    dependency,
                    item,
                    structural_tools["structural_relationship"],
                )
                tool_calls += added_calls
            item.transitions.append(transition)

    selected: list[EvidenceItem] = []
    selected_keys: set[tuple[str, int, int]] = set()
    for obligation in obligations:
        item = progress[obligation.id]
        for candidate in item.candidates[:MAX_PER_OBLIGATION]:
            key = (candidate.path, candidate.line_start, candidate.line_end)
            if key in selected_keys or len(selected) >= MAX_EVIDENCE:
                continue
            selected_keys.add(key)
            selected.append(_evidence_item(candidate, obligation_id=obligation.id, rank=len(selected) + 1))

    selected_external_ids = set(connected_context.selected_evidence_ids)
    for document in connected_context.documents:
        if document.source_id not in selected_external_ids or len(selected) >= MAX_EVIDENCE:
            continue
        selected.append(
            EvidenceItem(
                source_category=document.source_category,
                source_id=document.source_id,
                snippet=document.content,
                rank=len(selected) + 1,
                metadata={
                    "title": document.title,
                    "source_key": document.source_key,
                    "retrieval_origin": "connected_source",
                },
            )
        )

    states = [progress[item.id] for item in obligations]
    required_unresolved = [item.obligation.id for item in states if item.obligation.required and item.status != "supported"]
    unresolved_transitions = [
        f"{transition['from']}->{item.obligation.id}"
        for item in states
        if item.obligation.required
        for transition in item.transitions
        if transition.get("status") == "unresolved"
    ]
    roots = [item for item in states if not item.obligation.depends_on]
    depended_on = {dependency for item in obligations for dependency in item.depends_on}
    leaves = [item for item in states if item.obligation.id not in depended_on]
    endpoint_coverage = bool(roots and leaves) and all(item.status == "supported" for item in (*roots, *leaves))
    sufficient = bool(selected) and not required_unresolved and not unresolved_transitions and endpoint_coverage
    coverage = "strong" if sufficient else ("partial" if selected else "missing")
    summary = {
        "retriever": "workspace",
        "request_analysis": intent_context.to_dict(),
        "retrieval_plan": {
            "strategy": "obligation_graph_v1",
            "obligations": [item.to_dict() for item in states],
        },
        "index_rebuilt": True,
        "index_document_count": index_document_count,
        "selected_count": len(selected),
        "tool_calls": tool_calls,
        "exploration_rounds": 1,
        "stop_reason": "all_required_obligations_supported" if sufficient else "required_obligations_unresolved",
        "structural_graph_provider": "codegraph",
        "anchor_query_count": len(anchor_queries),
        "resolved_symbol_anchors": sorted({str(item.get("anchor_query") or "") for item in anchor_nodes}),
        "unresolved_symbol_anchors": list(unresolved_symbol_anchors),
        "ambiguous_symbol_anchors": list(ambiguous_symbol_anchors),
        "resolved_graph_node_count": len({item.node_id for state_item in states for item in state_item.candidates if item.node_id}),
        "graph_edge_count": len(expanded_edges),
        "unresolved_obligations": required_unresolved,
        "unresolved_transitions": unresolved_transitions,
        "endpoint_coverage": endpoint_coverage,
        "connected_source_context": connected_context.to_dict(),
        "connected_source_count": len(connected_context.documents),
    }
    return RetrievalResult(
        evidence=tuple(selected),
        coverage_status=coverage,
        sufficient=sufficient,
        retrieval_summary=summary,
        failures_or_fallbacks=tuple((*required_unresolved, *unresolved_transitions)),
    )


def _edge_index(edges: Sequence[Mapping[str, Any]]) -> dict[frozenset[str], list[dict[str, Any]]]:
    index: dict[frozenset[str], list[dict[str, Any]]] = {}
    for edge in edges:
        source = edge.get("source") if isinstance(edge.get("source"), Mapping) else {}
        target = edge.get("target") if isinstance(edge.get("target"), Mapping) else {}
        source_id = str(source.get("id") or "")
        target_id = str(target.get("id") or "")
        if source_id and target_id:
            index.setdefault(frozenset((source_id, target_id)), []).append(dict(edge))
    return index


def _transition_from_edges(
    source: ObligationProgress,
    target: ObligationProgress,
    edge_index: Mapping[frozenset[str], Sequence[Mapping[str, Any]]],
) -> dict[str, Any] | None:
    source_ids = {item.node_id for item in source.candidates if item.node_id}
    target_ids = {item.node_id for item in target.candidates if item.node_id}
    shared = source_ids & target_ids
    if shared:
        return {"from": source.obligation.id, "status": "supported", "relationship": "shared_node"}
    for source_id in source_ids:
        for target_id in target_ids:
            edges = edge_index.get(frozenset((source_id, target_id)), ())
            if edges:
                return {
                    "from": source.obligation.id,
                    "status": "supported",
                    "relationship": str(edges[0].get("kind") or "graph_edge"),
                }
    return None


def _resolve_file_transition(
    ctx: WorkspaceRetrievalContext,
    source: ObligationProgress,
    target: ObligationProgress,
    relationship_tool: Any,
) -> tuple[dict[str, Any], int]:
    if not source.candidates or not target.candidates:
        return ({"from": source.obligation.id, "status": "unresolved", "reason": "missing_obligation_evidence"}, 0)
    source_path = source.candidates[0].path
    target_path = target.candidates[0].path
    if source_path == target_path:
        return ({"from": source.obligation.id, "status": "supported", "relationship": "same_file"}, 0)
    request = ToolRequest(
        tool_name="structural_relationship",
        arguments={"source_path": source_path, "target_path": target_path},
        reason=f"Verify the repository transition from {source.obligation.id} to {target.obligation.id}.",
    )
    observation = relationship_tool.run(request)
    ctx.trace.record_tool(request, observation, round_index=2)
    if observation.status == "ok" and bool(observation.payload.get("related")):
        edges = observation.payload.get("edges") if isinstance(observation.payload.get("edges"), list) else []
        relationship = str(edges[0].get("edge_kind") or "file_dependency") if edges else "file_dependency"
        return ({"from": source.obligation.id, "status": "supported", "relationship": relationship}, 1)
    source_suffix = Path(source_path).suffix.lower()
    target_suffix = Path(target_path).suffix.lower()
    if source_suffix and target_suffix and source_suffix != target_suffix:
        return (
            {
                "from": source.obligation.id,
                "status": "open_boundary",
                "relationship": "cross_format_or_language_boundary",
                "reason": "No static CodeGraph edge connects the selected artifacts across file formats or languages.",
            },
            1,
        )
    return (
        {
            "from": source.obligation.id,
            "status": "unresolved",
            "reason": "No graph edge or explicit repository boundary connects the selected evidence.",
        },
        1,
    )


def _obligation_query(description: str, unresolved_symbols: Sequence[str] = ()) -> str:
    obligation_terms = _distinctive_terms(description)
    relevant_symbols = [symbol for symbol in unresolved_symbols if obligation_terms & _terms(symbol)]
    return " ".join((description.strip(), *relevant_symbols)).strip()


def ordered_unique(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = str(value).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return tuple(result)


def _terms(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", value.lower())
        if len(token) >= 3 and token not in {"the", "and", "for", "from", "that", "this", "with", "into", "how", "what"}
    }


_OBLIGATION_INSTRUCTION_TERMS = {
    "actual",
    "code",
    "compare",
    "determine",
    "establish",
    "expected",
    "explain",
    "identify",
    "locate",
    "path",
    "paths",
    "reported",
    "repository",
    "state",
    "supported",
    "trace",
}


def _distinctive_terms(value: str) -> set[str]:
    return _terms(value) - _OBLIGATION_INSTRUCTION_TERMS


def _semantic_support_score(expected: set[str], result: Mapping[str, Any]) -> float:
    matched = _terms(" ".join(str(item) for item in result.get("matched_terms", ()))) & expected
    required_matches = 1 if len(expected) < 4 else 2
    if len(matched) < required_matches:
        return 0.0
    return float(len(matched)) / float(max(1, min(len(expected), 8)))


def _node_text(node: Mapping[str, Any]) -> str:
    return " ".join(
        str(node.get(key) or "")
        for key in ("name", "qualified_name", "path", "kind", "anchor_query")
    )


def _overlap_score(expected: set[str], actual: str) -> float:
    actual_terms = _terms(actual)
    if not expected or not actual_terms:
        return 0.0
    return float(len(expected & actual_terms)) / float(max(1, min(len(expected), 8)))


def _candidate_from_node(
    ctx: WorkspaceRetrievalContext,
    node: Mapping[str, Any],
    *,
    score: float,
    origin: str,
    relationship: str = "",
) -> GroundedCandidate | None:
    path = str(node.get("path") or "").replace("\\", "/")
    line_start = max(1, int(node.get("line_start") or 1))
    line_end = max(line_start, int(node.get("line_end") or line_start))
    if line_end - line_start > 100:
        line_end = line_start + 100
    source = Path(ctx.config.workspace_root) / path
    if not path or not source.is_file():
        return None
    lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
    line_end = min(line_end, len(lines))
    return GroundedCandidate(
        path=path,
        line_start=line_start,
        line_end=line_end,
        text="\n".join(lines[line_start - 1 : line_end]),
        score=score,
        origin=origin,
        node_id=str(node.get("id") or ""),
        symbol=str(node.get("qualified_name") or node.get("name") or ""),
        relationship=relationship,
    )


def _dedupe_candidates(candidates: Sequence[GroundedCandidate]) -> list[GroundedCandidate]:
    best: dict[tuple[str, int, int], GroundedCandidate] = {}
    for candidate in candidates:
        key = (candidate.path, candidate.line_start, candidate.line_end)
        current = best.get(key)
        if current is None or candidate.score > current.score:
            best[key] = candidate
    return sorted(best.values(), key=lambda item: (-item.score, item.path, item.line_start))


def _evidence_item(candidate: GroundedCandidate, *, obligation_id: str, rank: int) -> EvidenceItem:
    return EvidenceItem(
        source_category=SourceCategory.SOURCE_CODE,
        source_id=f"workspace:{candidate.path}:L{candidate.line_start}-L{candidate.line_end}",
        snippet=candidate.text,
        rank=rank,
        metadata={
            "path": candidate.path,
            "line_start": str(candidate.line_start),
            "line_end": str(candidate.line_end),
            "symbol": candidate.symbol,
            "coverage_area": obligation_id,
            "obligation_id": obligation_id,
            "retrieval_origin": candidate.origin,
            "graph_relationship": candidate.relationship,
        },
    )
