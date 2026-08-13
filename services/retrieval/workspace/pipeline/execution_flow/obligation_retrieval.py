from __future__ import annotations

from dataclasses import dataclass, field, replace
from difflib import SequenceMatcher
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from core.models import ConversationState, EvidenceItem, RetrievalResult
from core.source_policy import SourceCategory
from services.intent.models import EvidenceObligation, EvidenceRole, EvidenceSource
from services.intent.contracts import INTENT_CONTRACTS
from services.llm.json_completion import complete_json
from services.retrieval.workspace.bm25 import file_role
from services.retrieval.workspace.pipeline.execution_flow.context import WorkspaceRetrievalContext
from services.retrieval.workspace.connected_context import ConnectedSourceContextResult
from services.retrieval.resource_references import resource_reference_between_files
from services.retrieval.workspace.tools import ToolRequest


MAX_OBLIGATIONS = 10
MAX_EVIDENCE = 14
# Final evidence is selected under one request-level budget. Obligations remain
# retrieval lenses and explanation checks; they are not per-obligation buckets.
DUPLICATE_PROVENANCE_PENALTY = 0.8
OVERSIZED_UNCONNECTED_FILE_BYTES = 200_000
OVERSIZED_UNCONNECTED_FILE_PENALTY = 1.25
INCOMPLETE_CONCEPT_COVERAGE_PENALTY = 0.15
MAX_FOCUSED_SEEDS = 4
MAX_FOCUSED_FRONTIER_FILES = 48
FOCUSED_EXPANSION_NODE_LIMIT = 80
MAX_FOCUSED_RESULTS = 12
MAX_GRAPH_EXPANSION_ROUNDS = 3
MAX_CONSOLIDATION_CANDIDATES = 4
SEMANTIC_SIGNAL_RANK_LIMIT = 12
MAX_EXPLANATION_ROOTS = 4
MAX_NEIGHBORS_PER_ROOT = 48
MAX_LOCALIZED_NEIGHBORS_PER_ROOT = 2
MAX_MECHANISM_FLOW_DEPTH = 10
MAX_MECHANISM_FLOW_SEEDS = 128
MAX_MECHANISM_FLOW_BEAM = 8
MAX_MECHANISM_FLOW_CANDIDATES = 1_024
MAX_MECHANISM_FLOWS_PER_SEED = 8
MAX_MECHANISM_CALLEE_RESOLUTIONS = 12
MAX_MECHANISM_CALLEE_ROUNDS = 2
MAX_FACTORY_HANDOFF_RESOLUTIONS = 8
MAX_FACTORY_HANDOFF_DEPTH = 4
MAX_MECHANISM_PATH_FRONTIER_FILES = 64
MAX_MECHANISM_PATH_FRONTIER_ROUNDS = 2
# The mechanism-graph experiment is intentionally unbounded. A request limit will
# be reintroduced only after graph-selection behavior is stable and measured.
MAX_EXPLANATION_INPUT_CHARS: int | None = None
MAX_CONSOLIDATION_SNIPPET_CHARS = 2400
EXPLANATION_PAYLOAD_SERIALIZATION_MARGIN = 512
MAX_STANDALONE_ANCHOR_PATHS = 4
PRODUCTIVE_RECOVERY_RELATIONSHIPS = {
    "calls",
    "contained_call",
    "references",
    "imports",
    "file_dependency",
    "implements",
    "extends",
    "overrides",
    "instantiates",
    "qualified_call",
    "registered_callback",
    "state_write_read",
    "factory_handoff",
}
DIRECT_OBLIGATION_PROVENANCE = {
    "request_anchor",
    "exact_prompt_anchor",
    "semantic_anchor",
    "graph_frontier_semantic",
    "focused_semantic_bridge",
}
CONSOLIDATION_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "obligation_evidence_consolidation.md"
SEMANTIC_BRIDGE_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "focused_semantic_bridge.md"
INTENT_STAGE_PURPOSES = {
    stage.id: stage.purpose
    for contract in INTENT_CONTRACTS.values()
    for stage in contract.stages
}
INTENT_STAGE_RETRIEVAL_TERMS = {
    "explain.subject": ("implementation owner", "responsibility"),
    "explain.trigger": ("entry event", "callback", "invocation"),
    "explain.ordered_mechanism": ("caller callee", "handoff", "producer consumer"),
    "explain.state_changes": ("mutation update", "cache signature", "dependency representation"),
    "explain.resulting_effect": ("output diagnostic", "consumer", "report"),
    "explain.why": ("invalidation propagation", "affected dependency", "owner condition"),
}


@dataclass(frozen=True)
class SemanticDiscovery:
    """One obligation-specific semantic retrieval observation for a candidate."""

    obligation_id: str
    rank: int
    score: float
    matched_terms: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "obligation_id": self.obligation_id,
            "rank": self.rank,
            "score": round(self.score, 4),
            "matched_terms": list(self.matched_terms),
        }


@dataclass(frozen=True)
class CandidateFacts:
    """Deterministic observations attached to one exact candidate.

    Facts record retrieval and source observations; they do not classify a
    candidate's semantic responsibility.  This gives later graph policies one
    auditable representation instead of repeatedly reparsing candidate text.
    """

    semantic_discoveries: tuple[SemanticDiscovery, ...] = ()
    visible_calls: tuple[str, ...] = ()
    callable_defaults: tuple[tuple[str, str], ...] = ()
    returned_names: tuple[str, ...] = ()
    written_fields: tuple[str, ...] = ()
    read_fields: tuple[str, ...] = ()
    full_range: tuple[int, int] = ()
    primary_anchor: tuple[int, int] = ()
    anchor_reliability_tier: int = 0
    anchor_decision_code: str = ""
    localization_adapter: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "semantic_discoveries": [item.to_dict() for item in self.semantic_discoveries],
            "visible_calls": list(self.visible_calls),
            "callable_defaults": [
                {"value": value, "factory": factory}
                for value, factory in self.callable_defaults
            ],
            "returned_names": list(self.returned_names),
            "written_fields": list(self.written_fields),
            "read_fields": list(self.read_fields),
            "full_range": list(self.full_range),
            "primary_anchor": list(self.primary_anchor),
            "anchor_reliability_tier": self.anchor_reliability_tier,
            "anchor_decision_code": self.anchor_decision_code,
            "localization_adapter": self.localization_adapter,
        }


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
    file_role: str = "other"
    covered_concepts: tuple[str, ...] = ()
    missing_concepts: tuple[str, ...] = ()
    base_score: float = 0.0
    provenance_origins: tuple[str, ...] = ()
    source_paths: tuple[str, ...] = ()
    relationship_types: tuple[str, ...] = ()
    obligation_ids: tuple[str, ...] = ()
    facts: CandidateFacts = field(default_factory=CandidateFacts)


@dataclass(frozen=True)
class AnchorConfirmation:
    kind: str
    value: str
    confirmed_in_repository: bool
    matches: tuple[dict[str, Any], ...] = ()
    match_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "value": self.value,
            "confirmed_in_repository": self.confirmed_in_repository,
            "matches": [dict(item) for item in self.matches],
            "match_type": self.match_type or ("repository_confirmed" if self.confirmed_in_repository else "prompt_only"),
        }


@dataclass
class ObligationProgress:
    obligation: EvidenceObligation
    status: str = "pending"
    candidates: list[GroundedCandidate] = field(default_factory=list)
    discovery_hints: list[GroundedCandidate] = field(default_factory=list)
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
                    "file_role": item.file_role,
                    "covered_concepts": list(item.covered_concepts),
                    "missing_concepts": list(item.missing_concepts),
                    "provenance_origins": list(item.provenance_origins or (item.origin,)),
                    "source_paths": list(item.source_paths),
                    "relationship_types": list(item.relationship_types or ((item.relationship,) if item.relationship else ())),
                    "obligation_ids": list(item.obligation_ids),
                }
                for item in self.candidates[:MAX_EVIDENCE]
            ],
            "discovery_hints": [
                {
                    "path": item.path,
                    "line_start": item.line_start,
                    "line_end": item.line_end,
                    "node_id": item.node_id or None,
                    "origin": item.origin,
                    "score": round(item.score, 4),
                    "file_role": item.file_role,
                    "covered_concepts": list(item.covered_concepts),
                    "missing_concepts": list(item.missing_concepts),
                    "reason": "Candidate is semantically relevant but cannot establish this evidence role.",
                    "provenance_origins": list(item.provenance_origins or (item.origin,)),
                    "source_paths": list(item.source_paths),
                    "relationship_types": list(item.relationship_types or ((item.relationship,) if item.relationship else ())),
                    "obligation_ids": list(item.obligation_ids),
                }
                for item in _dedupe_candidates(self.discovery_hints)[:4]
            ],
        }


def run_obligation_retrieval(
    ctx: WorkspaceRetrievalContext,
    state: ConversationState,
    *,
    qdrant_tool: Any,
    structural_tools: Mapping[str, Any],
    index_document_count: int,
    index_rebuilt: bool,
    starting_tool_calls: int,
    connected_context: ConnectedSourceContextResult | None = None,
) -> RetrievalResult:
    intent_context = state.intent_context
    if intent_context is None or not intent_context.evidence_obligations:
        raise RuntimeError("Workspace obligation retrieval requires global request-analysis obligations.")

    obligations = intent_context.evidence_obligations[:MAX_OBLIGATIONS]
    repository_obligations = tuple(
        obligation for obligation in obligations if obligation.evidence_source == EvidenceSource.REPOSITORY
    )
    connected_context = connected_context or ConnectedSourceContextResult()
    progress = {item.id: ObligationProgress(item) for item in obligations}
    tool_calls = starting_tool_calls

    confirmations, anchor_nodes, unresolved_symbol_anchors, ambiguous_symbol_anchors, added_calls = _ground_request_anchors(
        ctx,
        anchors=intent_context.anchors.to_dict(),
        additional_paths=connected_context.file_hints,
        additional_symbols=connected_context.symbol_hints,
        qdrant_tool=qdrant_tool,
        structural_tools=structural_tools,
    )
    tool_calls += added_calls
    confirmed_values = {
        confirmation.value
        for confirmation in confirmations
        if confirmation.confirmed_in_repository
    }
    connected_search_terms = ordered_unique(
        (
            *intent_context.search_terms,
            *connected_context.retrieval_terms,
            *connected_context.suggested_subqueries,
        )
    )
    connected_preferred_paths = tuple(
        resolved
        for value in connected_context.file_hints
        if (resolved := _resolve_repository_path(ctx.config.workspace_root, value))
    )
    exact_prompt_seeds = _exact_prompt_seed_results(confirmations, repository_obligations)
    semantic_by_obligation: dict[str, list[dict[str, Any]]] = {item.id: [] for item in repository_obligations}
    concepts_by_obligation = {
        item.id: _relevant_search_concepts(item.description, intent_context.search_terms)
        for item in repository_obligations
    }
    for obligation in repository_obligations:
        query = _obligation_query(
            _obligation_stage_query_text(obligation),
            (*unresolved_symbol_anchors, *ambiguous_symbol_anchors),
            anchors=tuple(anchor for anchor in obligation.anchor_refs if anchor in confirmed_values),
            search_terms=connected_search_terms,
        )
        search_paths = _confirmed_obligation_paths(obligation, confirmations)
        request = ToolRequest(
            tool_name="qdrant_hybrid_search",
            arguments={
                "query": query,
                "limit": MAX_FOCUSED_RESULTS,
                "max_per_path": 1,
                "source_category": _source_category_for_role(obligation.evidence_role),
                "file_role": "any",
                "paths": list(search_paths),
                "preferred_paths": list(connected_preferred_paths),
            },
            reason=f"Find conceptual anchors for evidence obligation {obligation.id}.",
        )
        observation = qdrant_tool.run(request)
        ctx.trace.record_tool(request, observation, round_index=0)
        tool_calls += 1
        if observation.status != "ok":
            raise RuntimeError(f"Semantic anchor search failed for {obligation.id}.")
        semantic_by_obligation[obligation.id] = [
            dict(item) for item in observation.payload.get("results", ()) if isinstance(item, Mapping)
        ][:MAX_FOCUSED_RESULTS]

    ranges = [
        {
            "file": str(item.get("path") or ""),
            "line_start": int(item.get("line_start") or 0),
            "line_end": int(item.get("line_end") or item.get("line_start") or 0),
        }
        for obligation_id, values in semantic_by_obligation.items()
        for item in (*exact_prompt_seeds.get(obligation_id, ()), *values)
        if str(item.get("path") or "") and int(item.get("line_start") or 0) > 0
    ]
    range_nodes: dict[tuple[str, int, int], list[dict[str, Any]]] = {}
    if ranges:
        request = ToolRequest(
            tool_name="structural_resolve_ranges",
            arguments={"ranges": ranges},
            reason="Map complete semantic chunk ranges back to overlapping CodeGraph nodes.",
        )
        observation = structural_tools["structural_resolve_ranges"].run(request)
        ctx.trace.record_tool(request, observation, round_index=0)
        tool_calls += 1
        if observation.status != "ok":
            raise RuntimeError("CodeGraph could not ground semantic result ranges.")
        for result in observation.payload.get("results", ()):
            if isinstance(result, Mapping):
                key = (
                    str(result.get("file") or ""),
                    int(result.get("line_start") or 0),
                    int(result.get("line_end") or result.get("line_start") or 0),
                )
                range_nodes[key] = _best_overlapping_nodes(
                    tuple(dict(node) for node in result.get("nodes", ()) if isinstance(node, Mapping)),
                    line_start=key[1],
                    line_end=key[2],
                )

    seed_obligations: dict[str, set[str]] = {}
    for obligation in repository_obligations:
        obligation_terms = _distinctive_terms(obligation.description)
        for node in anchor_nodes:
            score = _overlap_score(obligation_terms, _node_text(node))
            anchor_query = str(node.get("anchor_query") or "")
            if anchor_query not in obligation.anchor_refs and score <= 0:
                continue
            candidate = _candidate_from_node(
                ctx,
                node,
                score=score + 1.0,
                origin="request_anchor",
                obligation_id=obligation.id,
            )
            if candidate is not None:
                progress[obligation.id].candidates.append(candidate)
                if candidate.node_id:
                    seed_obligations.setdefault(candidate.node_id, set()).add(obligation.id)
        _append_semantic_candidates(
            progress[obligation.id],
            results=exact_prompt_seeds.get(obligation.id, ()),
            nodes_by_range=range_nodes,
            concepts=concepts_by_obligation[obligation.id],
            origin="exact_prompt_anchor",
            workspace_root=ctx.config.workspace_root,
        )
        _append_semantic_candidates(
            progress[obligation.id],
            results=semantic_by_obligation[obligation.id],
            nodes_by_range=range_nodes,
            concepts=concepts_by_obligation[obligation.id],
            origin="semantic_anchor",
            workspace_root=ctx.config.workspace_root,
            allow_without_obligation_overlap=True,
        )
        for candidate in progress[obligation.id].candidates:
            if candidate.node_id:
                seed_obligations.setdefault(candidate.node_id, set()).add(obligation.id)

    for item in progress.values():
        item.candidates = _dedupe_candidates(item.candidates)

    # The Qdrant tool events contain the raw result chunks.  This companion
    # ledger states exactly which of those results became usable candidates
    # before later graph and explanation decisions can discard them.
    ctx.trace.record(
        "initial_semantic_candidates_grounded",
        {
            "obligations": [
                {
                    "obligation_id": obligation.id,
                    "semantic_results": [
                        _semantic_result_trace_item(result, rank=rank)
                        for rank, result in enumerate(semantic_by_obligation[obligation.id], start=1)
                    ],
                    "grounded_candidates": [
                        _candidate_trace_item(candidate)
                        for candidate in progress[obligation.id].candidates
                    ],
                }
                for obligation in repository_obligations
            ],
        },
    )

    expanded_edges: list[dict[str, Any]] = []
    focused_expansion_count = 0
    focused_frontier_query_count = 0
    focused_file_neighbor_count = 0
    focused_qualified_reference_count = 0
    graph_expansion_rounds = 1
    promotion_ledger: dict[str, GroundedCandidate] = {}
    expanded_node_ids: set[str] = set()
    for obligation in repository_obligations:
        if not obligation.required:
            continue
        dependency_seeds = _dependency_seed_candidates(progress, obligation)
        own_seed_limit = MAX_FOCUSED_SEEDS - 1 if dependency_seeds else MAX_FOCUSED_SEEDS
        seed_ids = ordered_unique(
            (
                *_focused_seed_ids(
                    progress[obligation.id],
                    seed_obligations,
                    obligation.id,
                    limit=own_seed_limit,
                ),
                *(candidate.node_id for candidate in dependency_seeds if candidate.node_id),
            )
        )[:MAX_FOCUSED_SEEDS]
        if not seed_ids:
            continue
        expanded_node_ids.update(seed_ids)
        request = ToolRequest(
            tool_name="structural_expand_nodes",
            arguments={"node_ids": list(seed_ids), "depth": 1, "limit": FOCUSED_EXPANSION_NODE_LIMIT},
            reason=f"Expand the closest graph nodes for evidence obligation {obligation.id}.",
        )
        observation = structural_tools["structural_expand_nodes"].run(request)
        ctx.trace.record_tool(request, observation, round_index=1)
        tool_calls += 1
        focused_expansion_count += 1
        if observation.status != "ok":
            raise RuntimeError(f"CodeGraph obligation expansion failed for {obligation.id}.")
        raw_obligation_edges = [dict(edge) for edge in observation.payload.get("edges", ()) if isinstance(edge, Mapping)]
        _record_file_call_localization_decisions(
            ctx,
            raw_obligation_edges,
            obligation_id=obligation.id,
            round_index=1,
        )
        obligation_edges = _normalized_expansion_edges(raw_obligation_edges)
        expanded_edges.extend(obligation_edges)
        node_by_id = {
            str(node.get("id") or ""): dict(node)
            for node in observation.payload.get("nodes", ())
            if isinstance(node, Mapping)
            and str(node.get("id") or "")
            and file_role(str(node.get("path") or "")) != "baseline_or_generated"
        }
        node_by_id.update(_edge_nodes_by_id(obligation_edges))
        seed_candidate_by_id = {
            candidate.node_id: candidate
            for candidate in (
                *progress[obligation.id].candidates,
                *progress[obligation.id].discovery_hints,
                *dependency_seeds,
            )
            if candidate.node_id in seed_ids
        }
        direct_structural_candidates: list[GroundedCandidate] = []
        for edge in obligation_edges:
            source = edge.get("source") if isinstance(edge.get("source"), Mapping) else {}
            target = edge.get("target") if isinstance(edge.get("target"), Mapping) else {}
            source_id = str(source.get("id") or "")
            target_id = str(target.get("id") or "")
            for seed_id, other_id in ((source_id, target_id), (target_id, source_id)):
                if seed_id not in seed_ids:
                    continue
                obligation_terms = _distinctive_terms(obligation.description)
                node = node_by_id.get(other_id, {})
                score = _overlap_score(obligation_terms, _node_text(node))
                relationship = str(edge.get("kind") or "related")
                seed_candidate = seed_candidate_by_id.get(seed_id)
                symbol = str(node.get("name") or node.get("qualified_name") or "")
                direct_target = _is_visible_direct_target(
                    relationship=relationship,
                    target_symbol=symbol,
                    seed_candidate=seed_candidate,
                )
                usage_context_score = (
                    _direct_target_context_score(obligation_terms, seed_candidate.text, symbol)
                    if direct_target and seed_candidate is not None
                    else 0.0
                )
                if relationship not in PRODUCTIVE_RECOVERY_RELATIONSHIPS and not direct_target:
                    continue
                candidate = _candidate_from_node(
                    ctx,
                    node,
                    score=max(score, usage_context_score),
                    origin="graph_direct_target" if direct_target else "graph_neighbor",
                    relationship=relationship,
                    obligation_id=obligation.id,
                    source_paths=tuple(
                        path
                        for endpoint in (source, target)
                        if (path := str(endpoint.get("path") or "")) and path != str(node.get("path") or "")
                    ),
                )
                if candidate is not None:
                    progress[obligation.id].candidates.append(candidate)
                    if direct_target:
                        direct_structural_candidates.append(candidate)

        node_frontier_paths = _focused_frontier_paths(
            obligation_edges,
            seed_ids=seed_ids,
            limit=MAX_FOCUSED_FRONTIER_FILES,
        )
        direct_structural_paths = tuple(
            dict.fromkeys(candidate.path for candidate in direct_structural_candidates if candidate.path)
        )
        node_frontier_paths = tuple(
            path
            for path in dict.fromkeys((*direct_structural_paths, *node_frontier_paths))
            if file_role(path) != "baseline_or_generated"
        )[:MAX_FOCUSED_FRONTIER_FILES]
        seed_paths = tuple(
            dict.fromkeys(
                candidate.path
                for candidate in (*progress[obligation.id].candidates, *progress[obligation.id].discovery_hints)
                if candidate.node_id in seed_ids and candidate.path
            )
        )
        seed_candidates = tuple(
            candidate
            for candidate in (*progress[obligation.id].candidates, *progress[obligation.id].discovery_hints)
            if candidate.node_id in seed_ids and candidate.path
        ) + dependency_seeds
        file_frontier_paths: tuple[str, ...] = ()
        file_frontier_candidates: tuple[dict[str, Any], ...] = ()
        qualified_frontier_paths: tuple[str, ...] = ()
        qualified_candidates: tuple[GroundedCandidate, ...] = ()
        if seed_paths:
            qualified_candidates = _qualified_reference_expansion(
                ctx,
                structural_tools["structural_qualified_references"],
                source_paths=seed_paths,
                obligation=obligation,
                concepts=concepts_by_obligation[obligation.id],
                round_index=1,
                source_candidates=seed_candidates,
            )
            tool_calls += 1
            focused_qualified_reference_count += 1
            progress[obligation.id].candidates.extend(qualified_candidates)
            _update_promotion_ledger(promotion_ledger, qualified_candidates)
            qualified_frontier_paths = _qualified_frontier_paths(
                qualified_candidates,
            )
            request = ToolRequest(
                tool_name="structural_file_neighbors",
                arguments={"paths": list(seed_paths), "limit": MAX_FOCUSED_FRONTIER_FILES},
                reason=f"Find graph-ranked neighboring files for evidence obligation {obligation.id}.",
            )
            file_observation = structural_tools["structural_file_neighbors"].run(request)
            ctx.trace.record_tool(request, file_observation, round_index=1)
            tool_calls += 1
            focused_file_neighbor_count += 1
            if file_observation.status != "ok":
                raise RuntimeError(f"CodeGraph file-neighbor expansion failed for {obligation.id}.")
            file_frontier_candidates = tuple(
                dict(item)
                for item in file_observation.payload.get("neighbors", ())
                if isinstance(item, Mapping) and str(item.get("path") or "")
                and file_role(str(item.get("path") or "")) != "baseline_or_generated"
            )
            file_frontier_paths = tuple(str(item["path"]) for item in file_frontier_candidates)
        frontier_paths = tuple(
            dict.fromkeys((*qualified_frontier_paths, *file_frontier_paths, *node_frontier_paths))
        )[:MAX_FOCUSED_FRONTIER_FILES]
        if not frontier_paths:
            continue
        if _has_usable_exact_graph_ranges((*direct_structural_candidates, *qualified_candidates)):
            continue
        focused_query = _obligation_query(
            " ".join(
                (
                    obligation.description,
                    "Inspect the graph-connected implementation files that may establish this obligation.",
                    _qualified_reference_query_context(qualified_candidates),
                )
            ),
            (*unresolved_symbol_anchors, *ambiguous_symbol_anchors),
            anchors=tuple(anchor for anchor in obligation.anchor_refs if anchor in confirmed_values),
            search_terms=intent_context.search_terms,
        )
        focused_preferred_paths = _graph_preferred_paths(
            file_frontier_candidates,
            qualified_candidates=qualified_candidates,
            node_frontier_paths=node_frontier_paths,
        )
        request = ToolRequest(
            tool_name="qdrant_hybrid_search",
            arguments={
                "query": focused_query,
                "limit": MAX_FOCUSED_RESULTS,
                "max_per_path": 1,
                "source_category": _source_category_for_role(obligation.evidence_role),
                "file_role": "any",
                "paths": list(frontier_paths),
                "preferred_ranges": _promotion_ranges(
                    _dedupe_candidates((*direct_structural_candidates, *qualified_candidates))
                ),
                "preferred_paths": focused_preferred_paths,
            },
            reason=f"Rank snippets inside the CodeGraph frontier for evidence obligation {obligation.id}.",
        )
        observation = qdrant_tool.run(request)
        ctx.trace.record_tool(request, observation, round_index=1)
        tool_calls += 1
        focused_frontier_query_count += 1
        if observation.status != "ok":
            raise RuntimeError(f"Focused semantic search failed for {obligation.id}.")
        focused_results = [
            dict(item) for item in observation.payload.get("results", ()) if isinstance(item, Mapping)
        ][:MAX_FOCUSED_RESULTS]
        focused_ranges = [
            {
                "file": str(item.get("path") or ""),
                "line_start": int(item.get("line_start") or 0),
                "line_end": int(item.get("line_end") or item.get("line_start") or 0),
            }
            for item in focused_results
            if str(item.get("path") or "") and int(item.get("line_start") or 0) > 0
        ]
        focused_nodes: dict[tuple[str, int, int], list[dict[str, Any]]] = {}
        if focused_ranges:
            request = ToolRequest(
                tool_name="structural_resolve_ranges",
                arguments={"ranges": focused_ranges},
                reason=f"Ground complete focused semantic ranges for evidence obligation {obligation.id}.",
            )
            location_observation = structural_tools["structural_resolve_ranges"].run(request)
            ctx.trace.record_tool(request, location_observation, round_index=1)
            tool_calls += 1
            if location_observation.status != "ok":
                raise RuntimeError(f"CodeGraph could not ground focused results for {obligation.id}.")
            for result in location_observation.payload.get("results", ()):
                if not isinstance(result, Mapping):
                    continue
                nodes = [dict(node) for node in result.get("nodes", ()) if isinstance(node, Mapping)]
                if nodes:
                    key = (
                        str(result.get("file") or ""),
                        int(result.get("line_start") or 0),
                        int(result.get("line_end") or result.get("line_start") or 0),
                    )
                    focused_nodes[key] = _best_overlapping_nodes(
                        nodes,
                        line_start=key[1],
                        line_end=key[2],
                    )

        _append_semantic_candidates(
            progress[obligation.id],
            results=focused_results,
            nodes_by_range=focused_nodes,
            concepts=concepts_by_obligation[obligation.id],
            origin="graph_frontier_semantic",
            relationship="graph_frontier",
            promotions=_dedupe_candidates(
                (
                    *direct_structural_candidates,
                    *_promotion_candidates_for_obligation(promotion_ledger, obligation.id),
                )
            ),
            path_provenance=focused_preferred_paths,
            workspace_root=ctx.config.workspace_root,
        )

    added_calls, added_edges, graph_expansion_rounds = _expand_grounded_candidate_graph(
        ctx,
        states=tuple(progress[item.id] for item in repository_obligations),
        structural_expand_tool=structural_tools["structural_expand_nodes"],
        max_rounds=MAX_GRAPH_EXPANSION_ROUNDS,
        initially_visited=expanded_node_ids,
    )
    tool_calls += added_calls
    focused_expansion_count += added_calls
    expanded_edges.extend(added_edges)

    expanded_edges = _dedupe_edges(expanded_edges)

    bridge_result = _run_focused_semantic_bridge(
        ctx,
        states=tuple(progress[item.id] for item in repository_obligations),
        expanded_edges=expanded_edges,
        qdrant_tool=qdrant_tool,
        find_exact_symbol_tool=structural_tools["structural_find_exact_symbol"],
        resolve_ranges_tool=structural_tools["structural_resolve_ranges"],
        expand_nodes_tool=structural_tools["structural_expand_nodes"],
    )
    tool_calls += int(bridge_result.get("tool_calls") or 0)
    expanded_edges.extend(
        dict(edge) for edge in bridge_result.get("edges", ()) if isinstance(edge, Mapping)
    )
    expanded_edges = _dedupe_edges(expanded_edges)

    explanation_file_neighbors, explanation_neighbor_calls = _semantic_root_file_neighbors(
        ctx,
        structural_tools["structural_file_neighbors"],
        semantic_by_obligation,
        rank_limit=SEMANTIC_SIGNAL_RANK_LIMIT,
    )
    tool_calls += explanation_neighbor_calls
    neighbor_grounding_calls = _ground_semantic_root_neighbors(
        ctx,
        states=tuple(progress[item.id] for item in repository_obligations),
        semantic_by_obligation=semantic_by_obligation,
        concepts_by_obligation=concepts_by_obligation,
        file_neighbors=explanation_file_neighbors,
        qdrant_tool=qdrant_tool,
        resolve_ranges_tool=structural_tools["structural_resolve_ranges"],
    )
    tool_calls += neighbor_grounding_calls

    connected_endpoint_calls = _recover_connected_semantic_endpoints(
        ctx,
        states=tuple(progress[item.id] for item in repository_obligations),
        concepts_by_obligation=concepts_by_obligation,
        qdrant_tool=qdrant_tool,
        file_neighbors_tool=structural_tools["structural_file_neighbors"],
        resolve_ranges_tool=structural_tools["structural_resolve_ranges"],
    )
    tool_calls += connected_endpoint_calls
    callee_grounding_calls = _recover_prompt_relevant_exact_callees(
        ctx,
        states=tuple(progress[item.id] for item in repository_obligations),
        find_exact_symbol_tool=structural_tools["structural_find_exact_symbol"],
    )
    tool_calls += callee_grounding_calls
    factory_handoff_calls, factory_handoff_edges = _recover_factory_handoffs(
        ctx,
        states=tuple(progress[item.id] for item in repository_obligations),
        find_exact_symbol_tool=structural_tools["structural_find_exact_symbol"],
    )
    tool_calls += factory_handoff_calls
    expanded_edges.extend(factory_handoff_edges)
    expanded_edges = _dedupe_edges(expanded_edges)

    _apply_duplicate_provenance_ranking(
        progress,
        expanded_edges=expanded_edges,
        workspace_root=Path(ctx.config.workspace_root),
    )
    _remove_generated_candidates(progress)
    for item in progress.values():
        item.candidates = _dedupe_candidates(item.candidates)

    for obligation in obligations:
        item = progress[obligation.id]
        if obligation.evidence_source != EvidenceSource.REPOSITORY:
            continue
        item.candidates = _dedupe_candidates(item.candidates)
        conflicting_candidates = [
            candidate
            for candidate in item.candidates
            if _candidate_conflicts_with_missing_path(candidate, obligation, confirmations)
        ]
        if conflicting_candidates:
            item.discovery_hints.extend(conflicting_candidates)
            item.candidates = [
                candidate
                for candidate in item.candidates
                if candidate not in conflicting_candidates
            ]

    candidate_graph_size = sum(
        len(_dedupe_candidates((*item.candidates, *item.discovery_hints)))
        for item in progress.values()
    )
    repository_states = tuple(progress[item.id] for item in repository_obligations)
    preselection_candidates, direct_support, inherited_support = _candidate_support_graph(repository_states)
    preselection_inventory = [
        {
            **_candidate_trace_item(candidate, candidate_id=candidate_id),
            "direct_obligation_ids": sorted(direct_support.get(candidate_id, ())),
            "inherited_obligation_ids": sorted(inherited_support.get(candidate_id, ())),
            "text_chars": len(candidate.text),
        }
        for candidate_id, candidate in preselection_candidates.items()
    ]
    ctx.trace.record(
        "preselection_candidate_pool_created",
        {
            "candidate_count": len(preselection_inventory),
            "raw_file_node_candidate_count": sum(
                str(item.get("node_id") or "").startswith("file:")
                for item in preselection_inventory
            ),
            "localized_candidate_count": sum(
                bool(item.get("facts", {}).get("localization_adapter"))
                for item in preselection_inventory
            ),
            "candidates": preselection_inventory,
        },
    )
    if ctx.config.final_evidence_selection_enabled:
        consolidation = _consolidate_obligation_evidence(
            ctx,
            repository_states,
            expanded_edges=expanded_edges,
        )
    else:
        consolidation = {
            "strategy": "explicitly_skipped_for_candidate_pool_diagnostics",
            "skipped": True,
            "llm_calls": 0,
            "accepted_candidate_ids": [],
            "accepted_ids_by_obligation": {},
            "rejected_candidate_ids": [],
            "invalid_candidate_ids": [],
            "obligation_statuses": {
                state.obligation.id: "unresolved" for state in repository_states
            },
            "unresolved_reasons": {
                state.obligation.id: "Final evidence selection was explicitly disabled for this diagnostic run."
                for state in repository_states
            },
            "concepts": [],
            "usage": {},
        }
        ctx.trace.record(
            "final_evidence_selection_skipped",
            {
                "reason": "explicit_diagnostic_configuration",
                "candidate_count": len(preselection_inventory),
            },
        )

    for obligation in obligations:
        item = progress[obligation.id]
        if obligation.evidence_source == EvidenceSource.PROMPT:
            item.status = "supported"
            continue
        if obligation.evidence_source == EvidenceSource.EXTERNAL:
            item.status = "unresolved"
            item.unresolved_reason = (
                "This obligation requires evidence owned by an external dependency or runtime, "
                "so it was not searched in the selected repository."
            )
            continue
        assessment_status = consolidation.get("obligation_statuses", {}).get(obligation.id, "unresolved")
        item.status = (
            "supported"
            if assessment_status in {"prompt_grounded", "repository_supported", "jointly_supported"}
            else "unresolved"
        )
        if item.status == "unresolved":
            item.unresolved_reason = consolidation["unresolved_reasons"].get(
                obligation.id,
                "No repository-grounded graph node or semantic chunk decisively supported this obligation.",
            )

    edge_index = _edge_index(expanded_edges)
    for obligation in obligations:
        item = progress[obligation.id]
        if obligation.evidence_source == EvidenceSource.PROMPT:
            continue
        if obligation.evidence_source == EvidenceSource.EXTERNAL:
            for dependency_id in obligation.depends_on:
                item.transitions.append(
                    {
                        "from": dependency_id,
                        "status": "external_boundary",
                        "reason": "The local repository cannot prove the external dependency's internal transition.",
                    }
                )
            continue
        for dependency_id in obligation.depends_on:
            if not obligation.requires_repository_handoff:
                item.transitions.append(
                    {
                        "from": dependency_id,
                        "status": "context_only",
                        "reason": "The dependency orders retrieval context but does not require a proven repository handoff.",
                    }
                )
                continue
            dependency = progress[dependency_id]
            if (
                bridge_result.get("attempted")
                and bridge_result.get("from") == dependency_id
                and bridge_result.get("to") == obligation.id
            ):
                item.transitions.append(_transition_from_focused_bridge(dependency, item, bridge_result))
                continue
            transition = _transition_from_edges(dependency, item, edge_index)
            if transition is None:
                transition = _transition_from_shared_anchors(dependency, item, confirmed_values)
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
    selected_candidates_by_id = {
        _global_candidate_id(candidate): candidate
        for item in progress.values()
        for candidate in item.candidates
    }
    accepted_ids_by_obligation = consolidation.get("accepted_ids_by_obligation", {})
    for candidate_id in consolidation.get("accepted_candidate_ids", ()):
        candidate = selected_candidates_by_id.get(candidate_id)
        if candidate is None or len(selected) >= MAX_EVIDENCE:
            continue
        obligation_id = next(
            (
                obligation.id
                for obligation in repository_obligations
                if candidate_id in accepted_ids_by_obligation.get(obligation.id, ())
            ),
            repository_obligations[0].id if repository_obligations else "mechanism",
        )
        selected.append(_evidence_item(candidate, obligation_id=obligation_id, rank=len(selected) + 1))

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
    required_ids = {item.obligation.id for item in states if item.obligation.required}
    roots = [item for item in states if item.obligation.required and not (set(item.obligation.depends_on) & required_ids)]
    depended_on = {
        dependency
        for item in states
        if item.obligation.required
        for dependency in item.obligation.depends_on
        if dependency in required_ids
    }
    leaves = [item for item in states if item.obligation.required and item.obligation.id not in depended_on]
    endpoint_coverage = bool(roots and leaves) and all(item.status == "supported" for item in (*roots, *leaves))
    sufficient = bool(selected) and not required_unresolved and not unresolved_transitions and endpoint_coverage
    coverage = "strong" if sufficient else ("partial" if selected else "missing")
    summary = {
        "retriever": "workspace",
        "request_analysis": intent_context.to_dict(),
        "retrieval_plan": {
            "strategy": "graph_first_obligation_v3",
            "obligations": [item.to_dict() for item in states],
        },
        "index_rebuilt": index_rebuilt,
        "index_document_count": index_document_count,
        "selected_count": len(selected),
        "tool_calls": tool_calls,
        "exploration_rounds": graph_expansion_rounds,
        "focused_expansion_count": focused_expansion_count,
        "focused_file_neighbor_count": focused_file_neighbor_count,
        "focused_frontier_query_count": focused_frontier_query_count,
        "focused_qualified_reference_count": focused_qualified_reference_count,
        "candidate_graph_size_before_final_selection": candidate_graph_size,
        "unique_candidate_count_before_final_selection": len(preselection_inventory),
        "preselection_candidate_pool": preselection_inventory,
        "final_selection_llm_calls": consolidation.get("llm_calls", 0),
        "stop_reason": "all_required_obligations_supported" if sufficient else "required_obligations_unresolved",
        "structural_graph_provider": "codegraph",
        "anchor_query_count": len(confirmations),
        "anchor_confirmations": [item.to_dict() for item in confirmations],
        "prompt_only_anchors": [
            {"kind": item.kind, "value": item.value}
            for item in confirmations
            if not item.confirmed_in_repository
        ],
        "resolved_symbol_anchors": sorted({str(item.get("anchor_query") or "") for item in anchor_nodes}),
        "unresolved_symbol_anchors": list(unresolved_symbol_anchors),
        "ambiguous_symbol_anchors": list(ambiguous_symbol_anchors),
        "resolved_graph_node_count": len({item.node_id for state_item in states for item in state_item.candidates if item.node_id}),
        "graph_edge_count": len(expanded_edges),
        "focused_semantic_bridge": bridge_result,
        "unresolved_obligations": required_unresolved,
        "unresolved_transitions": unresolved_transitions,
        "endpoint_coverage": endpoint_coverage,
        "connected_source_context": connected_context.to_dict(),
        "connected_source_count": len(connected_context.documents),
        "evidence_consolidation": consolidation,
    }
    return RetrievalResult(
        evidence=tuple(selected),
        coverage_status=coverage,
        sufficient=sufficient,
        retrieval_summary=summary,
        failures_or_fallbacks=tuple((*required_unresolved, *unresolved_transitions)),
    )


def _expand_grounded_candidate_graph(
    ctx: WorkspaceRetrievalContext,
    *,
    states: Sequence[ObligationProgress],
    structural_expand_tool: Any,
    max_rounds: int,
    initially_visited: set[str] | None = None,
) -> tuple[int, list[dict[str, Any]], int]:
    visited = set(initially_visited or ())
    tool_calls = 0
    expanded_edges: list[dict[str, Any]] = []
    rounds = 1
    for round_index in range(2, max(2, max_rounds + 1)):
        round_added = 0
        round_attempted = False
        for state in states:
            candidates = _dedupe_candidates((*state.candidates, *state.discovery_hints))
            seeds = tuple(
                candidate
                for candidate in candidates
                if candidate.node_id and candidate.node_id not in visited
            )[:MAX_FOCUSED_SEEDS]
            if not seeds:
                continue
            round_attempted = True
            seed_ids = tuple(candidate.node_id for candidate in seeds)
            visited.update(seed_ids)
            request = ToolRequest(
                tool_name="structural_expand_nodes",
                arguments={
                    "node_ids": list(seed_ids),
                    "depth": 1,
                    "limit": FOCUSED_EXPANSION_NODE_LIMIT,
                },
                reason=f"Continue the grounded graph frontier for evidence obligation {state.obligation.id}.",
            )
            observation = structural_expand_tool.run(request)
            ctx.trace.record_tool(request, observation, round_index=round_index)
            tool_calls += 1
            if observation.status != "ok":
                raise RuntimeError(f"CodeGraph continuation failed for {state.obligation.id}.")
            raw_edges = [dict(edge) for edge in observation.payload.get("edges", ()) if isinstance(edge, Mapping)]
            _record_file_call_localization_decisions(
                ctx,
                raw_edges,
                obligation_id=state.obligation.id,
                round_index=round_index,
            )
            edges = _normalized_expansion_edges(raw_edges)
            expanded_edges.extend(edges)
            nodes = {
                str(node.get("id") or ""): dict(node)
                for node in observation.payload.get("nodes", ())
                if isinstance(node, Mapping)
                and str(node.get("id") or "")
                and file_role(str(node.get("path") or "")) != "baseline_or_generated"
            }
            nodes.update(_edge_nodes_by_id(edges))
            seed_by_id = {candidate.node_id: candidate for candidate in seeds}
            existing = {
                (candidate.path, candidate.line_start, candidate.line_end)
                for candidate in candidates
            }
            obligation_terms = _distinctive_terms(state.obligation.description)
            for edge in edges:
                relationship = str(edge.get("kind") or "related")
                source = edge.get("source") if isinstance(edge.get("source"), Mapping) else {}
                target = edge.get("target") if isinstance(edge.get("target"), Mapping) else {}
                source_id = str(source.get("id") or "")
                target_id = str(target.get("id") or "")
                for seed_id, other_id in ((source_id, target_id), (target_id, source_id)):
                    seed = seed_by_id.get(seed_id)
                    node = nodes.get(other_id)
                    if seed is None or node is None:
                        continue
                    symbol = str(node.get("name") or node.get("qualified_name") or "")
                    direct_target = _is_visible_direct_target(
                        relationship=relationship,
                        target_symbol=symbol,
                        seed_candidate=seed,
                    )
                    overlap = _overlap_score(obligation_terms, _node_text(node))
                    if relationship not in PRODUCTIVE_RECOVERY_RELATIONSHIPS and not direct_target:
                        continue
                    candidate = _candidate_from_node(
                        ctx,
                        node,
                        score=overlap,
                        origin="graph_continuation",
                        relationship=relationship,
                        obligation_id=state.obligation.id,
                        source_paths=(seed.path,),
                    )
                    if candidate is None:
                        continue
                    key = (candidate.path, candidate.line_start, candidate.line_end)
                    if key in existing:
                        continue
                    state.candidates.append(candidate)
                    existing.add(key)
                    round_added += 1
        if not round_attempted:
            break
        rounds = round_index
        for state in states:
            state.candidates = _dedupe_candidates(state.candidates)
        if round_added == 0:
            break
    return tool_calls, _dedupe_edges(expanded_edges), rounds


def _record_file_call_localization_decisions(
    ctx: WorkspaceRetrievalContext,
    edges: Sequence[Mapping[str, Any]],
    *,
    obligation_id: str,
    round_index: int,
) -> None:
    decisions = [
        dict(localization)
        for edge in edges
        if isinstance((localization := edge.get("file_call_localization")), Mapping)
    ]
    if not decisions:
        return
    ctx.trace.record(
        "file_call_localization_decisions",
        {
            "obligation_id": obligation_id,
            "round": round_index,
            "decision_count": len(decisions),
            "localized_count": sum(item.get("status") == "localized" for item in decisions),
            "rejected_count": sum(item.get("status") != "localized" for item in decisions),
            "decisions": decisions,
        },
    )


def _normalized_expansion_edges(
    edges: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Replace aggregate file-call edges with their audited executable owner.

    The raw file edge is a discovery hint only. A rejected localization is not
    retained in the candidate mechanism graph.
    """
    normalized: list[dict[str, Any]] = []
    for edge in edges:
        source = edge.get("source") if isinstance(edge.get("source"), Mapping) else {}
        localization = (
            edge.get("file_call_localization")
            if isinstance(edge.get("file_call_localization"), Mapping)
            else None
        )
        if str(edge.get("kind") or "") != "calls" or str(source.get("kind") or "") != "file":
            normalized.append(dict(edge))
            continue
        if localization is None or localization.get("status") != "localized":
            continue
        selected = localization.get("selected") if isinstance(localization.get("selected"), Mapping) else {}
        owner = selected.get("owner") if isinstance(selected.get("owner"), Mapping) else {}
        target = edge.get("target") if isinstance(edge.get("target"), Mapping) else {}
        if not owner or not target:
            continue
        reliability_tier = int(selected.get("reliability_tier") or 0)
        normalized.append(
            {
                "kind": "calls" if reliability_tier >= 4 else "contained_call",
                "provenance": (
                    "exact_codegraph_function_call"
                    if reliability_tier >= 4
                    else "source_localized_contained_call"
                ),
                "source": {
                    **dict(owner),
                    "localization_adapter": str(localization.get("adapter") or ""),
                    "anchor": dict(selected.get("anchor") or {}),
                    "anchor_reliability_tier": reliability_tier,
                    "anchor_decision_code": str(localization.get("decision_code") or ""),
                },
                "target": dict(target),
                "localization": {
                    "adapter": str(localization.get("adapter") or ""),
                    "decision_code": str(localization.get("decision_code") or ""),
                    "anchor": dict(selected.get("anchor") or {}),
                    "reliability_tier": reliability_tier,
                    "full_line_start": int(owner.get("full_line_start") or owner.get("line_start") or 0),
                    "full_line_end": int(owner.get("full_line_end") or owner.get("line_end") or 0),
                },
            }
        )
    return _dedupe_edges(normalized)


def _edge_nodes_by_id(edges: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        node_id: dict(endpoint)
        for edge in edges
        for endpoint in (
            edge.get("source") if isinstance(edge.get("source"), Mapping) else {},
            edge.get("target") if isinstance(edge.get("target"), Mapping) else {},
        )
        if (node_id := str(endpoint.get("id") or ""))
        and str(endpoint.get("path") or "")
        and file_role(str(endpoint.get("path") or "")) != "baseline_or_generated"
    }


def _has_usable_exact_graph_ranges(candidates: Sequence[GroundedCandidate]) -> bool:
    return any(
        candidate.node_id
        and candidate.path
        and candidate.line_start > 0
        and candidate.line_end >= candidate.line_start
        for candidate in candidates
    )


def _candidate_sets_have_graph_edge(
    source: ObligationProgress,
    target: ObligationProgress,
    edges: Sequence[Mapping[str, Any]],
) -> bool:
    source_ids = {candidate.node_id for candidate in source.candidates if candidate.node_id}
    target_ids = {candidate.node_id for candidate in target.candidates if candidate.node_id}
    if not source_ids or not target_ids or source_ids == target_ids:
        return False
    for edge in edges:
        source_node = edge.get("source") if isinstance(edge.get("source"), Mapping) else {}
        target_node = edge.get("target") if isinstance(edge.get("target"), Mapping) else {}
        pair = {str(source_node.get("id") or ""), str(target_node.get("id") or "")}
        if any(source_id in pair for source_id in source_ids) and any(target_id in pair for target_id in target_ids):
            return True
    return False


def _first_bridge_gap(
    states: Sequence[ObligationProgress],
    edges: Sequence[Mapping[str, Any]],
) -> tuple[ObligationProgress, ObligationProgress, GroundedCandidate] | None:
    by_id = {state.obligation.id: state for state in states}
    shortlists = _connected_candidate_shortlists(states, expanded_edges=edges, limit=4)
    # Start at the furthest unresolved handoff. Earlier semantic seeds may only
    # discover the path; a bridge must continue from a concrete graph endpoint.
    for target in reversed(states):
        if not target.obligation.required or not target.obligation.requires_repository_handoff:
            continue
        for dependency_id in target.obligation.depends_on:
            source = by_id.get(dependency_id)
            if source is None:
                continue
            source_candidates = tuple(shortlists.get(source.obligation.id, ())) or tuple(
                sorted(source.candidates, key=lambda item: item.score, reverse=True)[:4]
            )
            target_candidates = tuple(shortlists.get(target.obligation.id, ())) or tuple(
                sorted(target.candidates, key=lambda item: item.score, reverse=True)[:4]
            )
            shortlist_source = ObligationProgress(source.obligation, candidates=list(source_candidates))
            shortlist_target = ObligationProgress(target.obligation, candidates=list(target_candidates))
            same_endpoint = bool(
                source_candidates
                and target_candidates
                and source_candidates[0].node_id
                and source_candidates[0].node_id == target_candidates[0].node_id
            )
            if not same_endpoint and _candidate_sets_have_graph_edge(shortlist_source, shortlist_target, edges):
                continue
            endpoints = [
                candidate
                for candidate in source.candidates
                if _is_proven_bridge_endpoint(candidate)
            ]
            if endpoints:
                endpoints.sort(
                    key=lambda candidate: (
                        _bridge_endpoint_priority(candidate),
                        candidate.score,
                    ),
                    reverse=True,
                )
                return source, target, endpoints[0]
    return None


def _is_proven_bridge_endpoint(candidate: GroundedCandidate) -> bool:
    if not candidate.node_id or candidate.file_role != "implementation" or not candidate.text:
        return False
    origins = set(candidate.provenance_origins or (candidate.origin,))
    return bool(
        origins
        & {
            "graph_direct_target",
            "graph_continuation",
            "graph_owner_qualified_reference",
        }
    ) or (
        candidate.origin == "graph_neighbor"
        and candidate.relationship in PRODUCTIVE_RECOVERY_RELATIONSHIPS
    )


def _bridge_endpoint_priority(candidate: GroundedCandidate) -> int:
    origins = set(candidate.provenance_origins or (candidate.origin,))
    if "graph_direct_target" in origins:
        return 3
    if "graph_owner_qualified_reference" in origins:
        return 2
    return 1


def _semantic_bridge_response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "focused_semantic_bridge",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "produced_state": {"type": "string", "maxLength": 240},
                    "consumer_goal": {"type": "string", "maxLength": 240},
                    "produced_terms": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "maxLength": 80,
                        },
                        "minItems": 1,
                        "maxItems": 3,
                    },
                    "consumer_terms": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "maxLength": 80,
                        },
                        "minItems": 1,
                        "maxItems": 3,
                    },
                },
                "required": ["produced_state", "consumer_goal", "produced_terms", "consumer_terms"],
            },
        },
    }


def _run_focused_semantic_bridge(
    ctx: WorkspaceRetrievalContext,
    *,
    states: Sequence[ObligationProgress],
    expanded_edges: Sequence[Mapping[str, Any]],
    qdrant_tool: Any,
    find_exact_symbol_tool: Any,
    resolve_ranges_tool: Any,
    expand_nodes_tool: Any,
) -> dict[str, Any]:
    gap = _first_bridge_gap(states, expanded_edges)
    if gap is None:
        return {"attempted": False, "tool_calls": 0, "edges": [], "reason": "no_unresolved_structural_handoff"}
    source, target, endpoint = gap
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    def log_event(event_type: str, payload: Mapping[str, Any]) -> None:
        if event_type == "llm_response_received":
            raw = payload.get("raw_response", {})
            raw_usage = raw.get("usage", {}) if isinstance(raw, Mapping) else {}
            if isinstance(raw_usage, Mapping):
                for key in usage:
                    usage[key] += int(raw_usage.get(key, 0) or 0)
        ctx.trace.record(event_type, {"stage": "focused_semantic_bridge", **dict(payload)})

    response = complete_json(
        ctx.config.llm_config,
        (
            {"role": "system", "content": SEMANTIC_BRIDGE_PROMPT_PATH.read_text(encoding="utf-8")},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "proven_endpoint": {
                            "path": endpoint.path,
                            "symbol": endpoint.symbol,
                            "line_start": endpoint.line_start,
                            "line_end": endpoint.line_end,
                            "snippet": endpoint.text[:MAX_CONSOLIDATION_SNIPPET_CHARS],
                        },
                        "next_obligation": target.obligation.description,
                    },
                    sort_keys=True,
                ),
            },
        ),
        response_format=_semantic_bridge_response_format(),
        log_event=log_event,
    )
    query_terms = ordered_unique(
        tuple(
            str(value).strip()
            for key in ("produced_terms", "consumer_terms")
            for value in response.get(key, ())
            if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$.[\]]*", str(value).strip())
        )
    )
    if len(query_terms) < 2:
        raise RuntimeError("Focused semantic bridge returned fewer than two valid code-search terms.")
    query = " ".join(query_terms)
    before_ids = {candidate.node_id for candidate in target.candidates if candidate.node_id}
    tool_calls = 0
    exact_consumer_nodes: list[dict[str, Any]] = []
    consumer_terms = ordered_unique(
        str(value).strip()
        for value in response.get("consumer_terms", ())
        if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", str(value).strip())
    )
    for term in consumer_terms:
        exact_request = ToolRequest(
            tool_name="structural_find_exact_symbol",
            arguments={"query": term, "limit": 12},
            reason=f"Resolve the focused semantic bridge consumer symbol {term}.",
        )
        exact_observation = find_exact_symbol_tool.run(exact_request)
        ctx.trace.record_tool(exact_request, exact_observation, round_index=MAX_GRAPH_EXPANSION_ROUNDS + 1)
        tool_calls += 1
        if exact_observation.status != "ok":
            raise RuntimeError(f"CodeGraph could not resolve semantic bridge consumer symbol {term}.")
        nodes = _source_authored_nodes(
            tuple(
                dict(node)
                for node in exact_observation.payload.get("nodes", ())
                if isinstance(node, Mapping)
            )
        )
        if len(nodes) == 1:
            exact_consumer_nodes.append(nodes[0])
    for node in exact_consumer_nodes:
        candidate = _candidate_from_node(
            ctx,
            node,
            score=1.0,
            origin="focused_semantic_bridge",
            relationship="semantic_bridge_candidate",
            obligation_id=target.obligation.id,
        )
        if candidate is not None:
            target.candidates.append(candidate)
    request = ToolRequest(
        tool_name="qdrant_hybrid_search",
        arguments={"query": query, "limit": 12, "max_per_path": 1, "file_role": "any"},
        reason=f"Find the consumer after the proven endpoint for {target.obligation.id}.",
    )
    observation = qdrant_tool.run(request)
    ctx.trace.record_tool(request, observation, round_index=MAX_GRAPH_EXPANSION_ROUNDS + 1)
    if observation.status != "ok":
        raise RuntimeError(f"Focused semantic bridge search failed for {target.obligation.id}.")
    results = [
        dict(item)
        for item in observation.payload.get("results", ())
        if isinstance(item, Mapping)
        and str(item.get("path") or "") != endpoint.path
        and file_role(str(item.get("path") or "")) != "baseline_or_generated"
    ][:8]
    ranges = [
        {
            "file": str(item.get("path") or ""),
            "line_start": int(item.get("line_start") or 0),
            "line_end": int(item.get("line_end") or item.get("line_start") or 0),
        }
        for item in results
        if str(item.get("path") or "") and int(item.get("line_start") or 0) > 0
    ]
    bridge_paths = tuple(dict.fromkeys(str(item.get("path") or "") for item in results if item.get("path")))[:4]
    ranges.extend(
        {"file": path, "line_start": 1, "line_end": 1_000_000_000}
        for path in bridge_paths
    )
    nodes_by_range: dict[tuple[str, int, int], list[dict[str, Any]]] = {}
    nodes_by_file: dict[str, list[dict[str, Any]]] = {}
    tool_calls += 1
    if ranges:
        range_request = ToolRequest(
            tool_name="structural_resolve_ranges",
            arguments={"ranges": ranges},
            reason=f"Ground focused semantic bridge results for {target.obligation.id}.",
        )
        range_observation = resolve_ranges_tool.run(range_request)
        ctx.trace.record_tool(range_request, range_observation, round_index=MAX_GRAPH_EXPANSION_ROUNDS + 1)
        tool_calls += 1
        if range_observation.status != "ok":
            raise RuntimeError(f"CodeGraph could not ground semantic bridge results for {target.obligation.id}.")
        for item in range_observation.payload.get("results", ()):
            if not isinstance(item, Mapping):
                continue
            key = (
                str(item.get("file") or ""),
                int(item.get("line_start") or 0),
                int(item.get("line_end") or item.get("line_start") or 0),
            )
            raw_nodes = tuple(dict(node) for node in item.get("nodes", ()) if isinstance(node, Mapping))
            if key[2] >= 1_000_000_000:
                nodes_by_file[key[0]] = list(raw_nodes)
            else:
                nodes_by_range[key] = _best_overlapping_nodes(
                    raw_nodes,
                    line_start=key[1],
                    line_end=key[2],
                )
    for node in _best_bridge_nodes_in_files(nodes_by_file, query_terms=query_terms):
        candidate = _candidate_from_node(
            ctx,
            node,
            score=1.0,
            origin="focused_semantic_bridge",
            relationship="semantic_bridge_candidate",
            obligation_id=target.obligation.id,
        )
        if candidate is not None:
            target.candidates.append(candidate)
    _append_semantic_candidates(
        target,
        results=results,
        nodes_by_range=nodes_by_range,
        concepts=tuple(
            str(value)
            for key in ("produced_terms", "consumer_terms")
            for value in response.get(key, ())
            if value
        ),
        origin="focused_semantic_bridge",
        relationship="semantic_bridge_candidate",
        workspace_root=ctx.config.workspace_root,
        allow_without_obligation_overlap=True,
    )
    target.candidates = _dedupe_candidates(target.candidates)
    new_ids = {candidate.node_id for candidate in target.candidates if candidate.node_id} - before_ids
    added_calls = 0
    added_edges: list[dict[str, Any]] = []
    if new_ids:
        added_calls, added_edges, _rounds = _expand_grounded_candidate_graph(
            ctx,
            states=(target,),
            structural_expand_tool=expand_nodes_tool,
            max_rounds=2,
            initially_visited={
                candidate.node_id
                for state in states
                for candidate in state.candidates
                if candidate.node_id and candidate.node_id not in new_ids
            },
        )
        tool_calls += added_calls
    result = {
        "attempted": True,
        "from": source.obligation.id,
        "to": target.obligation.id,
        "endpoint": f"{endpoint.path}:{endpoint.line_start}-{endpoint.line_end}",
        "endpoint_symbol": endpoint.symbol,
        "endpoint_node_id": endpoint.node_id,
        "query": query,
        "candidate_count": len(results),
        "grounded_new_node_count": len(new_ids),
        "discovered_node_ids": sorted(new_ids),
        "tool_calls": tool_calls,
        "edges": added_edges,
        "usage": usage,
    }
    ctx.trace.record("focused_semantic_bridge_completed", {key: value for key, value in result.items() if key != "edges"})
    return result


def _global_candidate_id(candidate: GroundedCandidate) -> str:
    return _candidate_ledger_key(candidate)


def _candidate_support_graph(
    states: Sequence[ObligationProgress],
) -> tuple[
    dict[str, GroundedCandidate],
    dict[str, set[str]],
    dict[str, set[str]],
]:
    valid_obligations = {state.obligation.id for state in states}
    candidates: dict[str, GroundedCandidate] = {}
    direct_support: dict[str, set[str]] = {}
    inherited_support: dict[str, set[str]] = {}
    for state in states:
        for candidate in _dedupe_candidates(state.candidates):
            candidate_id = _global_candidate_id(candidate)
            current = candidates.get(candidate_id)
            candidates[candidate_id] = candidate if current is None else _merge_candidate_provenance(current, candidate)
            mapped_obligations = {
                value for value in (*candidate.obligation_ids, state.obligation.id) if value in valid_obligations
            }
            provenance = set(candidate.provenance_origins or (candidate.origin,))
            target = direct_support if provenance & DIRECT_OBLIGATION_PROVENANCE else inherited_support
            target.setdefault(candidate_id, set()).update(mapped_obligations)
    for candidate_id in candidates:
        direct_support.setdefault(candidate_id, set())
        inherited_support.setdefault(candidate_id, set()).difference_update(direct_support[candidate_id])
    return candidates, direct_support, inherited_support


def _recover_connected_semantic_endpoints(
    ctx: WorkspaceRetrievalContext,
    *,
    states: Sequence[ObligationProgress],
    concepts_by_obligation: Mapping[str, Sequence[str]],
    qdrant_tool: Any,
    file_neighbors_tool: Any,
    resolve_ranges_tool: Any,
) -> int:
    """Localize obligation-relevant functions inside a two-hop call frontier."""

    tool_calls = 0
    decisions: list[dict[str, Any]] = []
    for state in states:
        obligation_id = state.obligation.id
        obligation_terms = _distinctive_terms(_obligation_stage_query_text(state.obligation))
        direct_candidates = [
            candidate
            for candidate in _dedupe_candidates((*state.candidates, *state.discovery_hints))
            if candidate.file_role == "implementation"
            and set(candidate.provenance_origins or (candidate.origin,)) & DIRECT_OBLIGATION_PROVENANCE
        ]
        roots = tuple(
            ordered_unique(
                tuple(
                    candidate.path
                    for candidate in sorted(
                        direct_candidates,
                        key=lambda candidate: (
                            -len(_mechanism_candidate_terms(candidate) & obligation_terms),
                            -candidate.score,
                            candidate.path,
                        ),
                    )
                )
            )[:MAX_EXPLANATION_ROOTS]
        )
        if not roots:
            continue
        visited_paths = set(roots)
        frontier = set(roots)
        provenance_by_path: dict[str, set[str]] = {}
        for round_index in range(MAX_MECHANISM_PATH_FRONTIER_ROUNDS):
            request = ToolRequest(
                tool_name="structural_file_neighbors",
                arguments={
                    "paths": sorted(frontier),
                    "limit": MAX_MECHANISM_PATH_FRONTIER_FILES,
                },
                reason=f"Find call-connected implementation files for {obligation_id}.",
            )
            observation = file_neighbors_tool.run(request)
            ctx.trace.record_tool(request, observation, round_index=MAX_GRAPH_EXPANSION_ROUNDS + 2 + round_index)
            tool_calls += 1
            if observation.status != "ok":
                raise RuntimeError(f"CodeGraph connected semantic frontier failed for {obligation_id}.")
            next_frontier: set[str] = set()
            for raw in observation.payload.get("neighbors", ()):
                if not isinstance(raw, Mapping):
                    continue
                path = str(raw.get("path") or "").replace("\\", "/")
                relationships = set(str(value) for value in raw.get("edge_kinds", ()) if value)
                if (
                    not path
                    or path in visited_paths
                    or file_role(path) != "implementation"
                    or not relationships & {"calls", "qualified_call"}
                ):
                    continue
                next_frontier.add(path)
                provenance_by_path.setdefault(path, set()).update(frontier)
            if not next_frontier:
                break
            frontier = set(sorted(next_frontier)[:MAX_MECHANISM_PATH_FRONTIER_FILES])
            visited_paths.update(frontier)
        connected_paths = sorted(provenance_by_path)
        if not connected_paths:
            continue
        search = ToolRequest(
            tool_name="qdrant_hybrid_search",
            arguments={
                "query": _obligation_stage_query_text(state.obligation),
                "limit": MAX_FOCUSED_RESULTS,
                "max_per_path": 1,
                "source_category": "source_code",
                "file_role": "implementation",
                "paths": connected_paths,
                "preferred_paths": connected_paths,
            },
            reason=f"Localize the mechanism inside call-connected files for {obligation_id}.",
        )
        searched = qdrant_tool.run(search)
        ctx.trace.record_tool(search, searched, round_index=MAX_GRAPH_EXPANSION_ROUNDS + 4)
        tool_calls += 1
        if searched.status != "ok":
            raise RuntimeError(f"Connected semantic localization failed for {obligation_id}.")
        results = [
            dict(item)
            for item in searched.payload.get("results", ())
            if isinstance(item, Mapping)
            and str(item.get("path") or "").replace("\\", "/") in provenance_by_path
        ][:MAX_FOCUSED_RESULTS]
        ranges = [
            {
                "file": str(item.get("path") or ""),
                "line_start": int(item.get("line_start") or 0),
                "line_end": int(item.get("line_end") or item.get("line_start") or 0),
            }
            for item in results
            if int(item.get("line_start") or 0) > 0
        ]
        full_file_ranges: list[dict[str, Any]] = []
        for path in ordered_unique(tuple(str(item.get("path") or "") for item in results)):
            source = Path(ctx.config.workspace_root) / path
            if not path or not source.is_file():
                continue
            line_count = len(source.read_text(encoding="utf-8", errors="replace").splitlines())
            if line_count:
                full_file_ranges.append({"file": path, "line_start": 1, "line_end": line_count})
        nodes_by_range: dict[tuple[str, int, int], list[dict[str, Any]]] = {}
        full_nodes_by_path: dict[str, list[dict[str, Any]]] = {}
        if ranges:
            resolve = ToolRequest(
                tool_name="structural_resolve_ranges",
                arguments={"ranges": [*ranges, *full_file_ranges]},
                reason=f"Resolve connected semantic ranges for {obligation_id}.",
            )
            resolved = resolve_ranges_tool.run(resolve)
            ctx.trace.record_tool(resolve, resolved, round_index=MAX_GRAPH_EXPANSION_ROUNDS + 4)
            tool_calls += 1
            if resolved.status != "ok":
                raise RuntimeError(f"Connected semantic range resolution failed for {obligation_id}.")
            for item in resolved.payload.get("results", ()):
                if not isinstance(item, Mapping):
                    continue
                key = (
                    str(item.get("file") or ""),
                    int(item.get("line_start") or 0),
                    int(item.get("line_end") or item.get("line_start") or 0),
                )
                nodes_by_range[key] = _best_overlapping_nodes(
                    tuple(dict(node) for node in item.get("nodes", ()) if isinstance(node, Mapping)),
                    line_start=key[1],
                    line_end=key[2],
                )
                if key[1] == 1 and any(
                    raw["file"] == key[0] and raw["line_end"] == key[2]
                    for raw in full_file_ranges
                ):
                    full_nodes_by_path[key[0]] = [
                        dict(node)
                        for node in item.get("nodes", ())
                        if isinstance(node, Mapping)
                        and str(node.get("id") or "").startswith(("function:", "method:"))
                    ]
        before = {_candidate_ledger_key(candidate) for candidate in state.candidates}
        _append_semantic_candidates(
            state,
            results=results,
            nodes_by_range=nodes_by_range,
            concepts=concepts_by_obligation.get(obligation_id, ()),
            origin="mechanism_connected_semantic",
            relationship="call_connected_file",
            path_provenance=tuple(
                {
                    "path": path,
                    "source_paths": sorted(provenance_by_path.get(path, ())),
                    "edge_kinds": ["calls"],
                }
                for path in connected_paths
            ),
            workspace_root=ctx.config.workspace_root,
            allow_without_obligation_overlap=True,
        )
        appended = [
            candidate
            for candidate in state.candidates
            if _candidate_ledger_key(candidate) not in before
        ]
        existing_node_ids = {
            candidate.node_id
            for candidate in (*state.candidates, *state.discovery_hints)
            if candidate.node_id
        }
        reverse_callers: list[GroundedCandidate] = []
        for endpoint in appended:
            target_symbol = endpoint.symbol.rsplit("::", 1)[-1]
            if not re.fullmatch(r"[A-Za-z_$][\w$]{2,}", target_symbol):
                continue
            for node in full_nodes_by_path.get(endpoint.path, ()):
                node_id = str(node.get("id") or "")
                if not node_id or node_id in existing_node_ids:
                    continue
                caller = _candidate_from_node(
                    ctx,
                    node,
                    score=max(0.25, endpoint.score),
                    origin="mechanism_connected_source_caller",
                    relationship="qualified_call",
                    obligation_id=obligation_id,
                    source_paths=(endpoint.path,),
                )
                if caller is None or not re.search(rf"\b{re.escape(target_symbol)}\s*\(", caller.text):
                    continue
                reverse_callers.append(caller)
                existing_node_ids.add(node_id)
                if len(reverse_callers) >= 2:
                    break
            if len(reverse_callers) >= 2:
                break
        state.candidates.extend(reverse_callers)
        appended.extend(reverse_callers)
        decisions.append(
            {
                "obligation_id": obligation_id,
                "root_paths": list(roots),
                "connected_path_count": len(connected_paths),
                "qdrant_result_paths": [str(item.get("path") or "") for item in results],
                "candidate_ids": [_global_candidate_id(candidate) for candidate in appended],
            }
        )
    ctx.trace.record(
        "connected_semantic_endpoint_localization",
        {"tool_calls": tool_calls, "decisions": decisions},
    )
    return tool_calls


def _recover_prompt_relevant_exact_callees(
    ctx: WorkspaceRetrievalContext,
    *,
    states: Sequence[ObligationProgress],
    find_exact_symbol_tool: Any,
) -> int:
    """Ground named same-file callees needed to continue a mechanism flow.

    CodeGraph expansion can expose a caller without returning every local call
    target. This stage uses visible call syntax only to choose exact-symbol
    lookups; a result is accepted only when one source-authored definition in
    the caller's file matches. Obligation ownership is inherited from the
    caller and is never reassigned by Qdrant or an LLM.
    """

    request_terms = set().union(
        *(
            _distinctive_terms(_obligation_stage_query_text(state.obligation))
            for state in states
        )
    ) if states else set()
    known_node_ids = {
        candidate.node_id
        for state in states
        for candidate in (*state.candidates, *state.discovery_hints)
        if candidate.node_id
    }
    known_symbols_by_path = {
        (candidate.path, candidate.symbol.rsplit("::", 1)[-1]): candidate.node_id
        for state in states
        for candidate in (*state.candidates, *state.discovery_hints)
        if candidate.node_id and candidate.symbol
    }
    resolved_names: set[tuple[str, str]] = set()
    decisions: list[dict[str, Any]] = []
    tool_calls = 0
    call_pattern = re.compile(r"(?<![.\w$])([A-Za-z_$][\w$]{2,})\s*\(")
    ignored_names = {
        "catch",
        "constructor",
        "else",
        "for",
        "function",
        "if",
        "return",
        "switch",
        "while",
    }

    for round_index in range(MAX_MECHANISM_CALLEE_ROUNDS):
        proposals: dict[tuple[str, str], list[tuple[ObligationProgress, GroundedCandidate]]] = {}
        for state in states:
            for caller in _dedupe_candidates((*state.candidates, *state.discovery_hints)):
                if not caller.node_id or not caller.symbol:
                    continue
                caller_overlap = _mechanism_candidate_terms(caller) & request_terms
                provenance = set(caller.provenance_origins or (caller.origin,))
                if not caller_overlap and not provenance & DIRECT_OBLIGATION_PROVENANCE:
                    continue
                for name in call_pattern.findall(caller.text):
                    if (
                        name in ignored_names
                        or name[:1].isupper()
                        or name == caller.symbol.rsplit("::", 1)[-1]
                    ):
                        continue
                    name_terms = _distinctive_terms(name)
                    if not name_terms or not (name_terms & request_terms):
                        continue
                    proposals.setdefault((caller.path, name), []).append((state, caller))

        ranked_proposals = sorted(
            (
                (key, sources)
                for key, sources in proposals.items()
                if key not in resolved_names
            ),
            key=lambda item: (
                -max(
                    len(_mechanism_candidate_terms(caller) & request_terms)
                    + len(_distinctive_terms(item[0][1]) & request_terms) * 10
                        + (3 if set(caller.provenance_origins or (caller.origin,)) & DIRECT_OBLIGATION_PROVENANCE else 0)
                    + (4 if caller.file_role == "implementation" else 0)
                    + caller.score
                    for _state, caller in item[1]
                ),
                item[0][0],
                item[0][1],
            ),
        )
        remaining_budget = MAX_MECHANISM_CALLEE_RESOLUTIONS - tool_calls
        if remaining_budget <= 0 or not ranked_proposals:
            break
        added_this_round = 0
        for (caller_path, name), sources in ranked_proposals:
            resolved_names.add((caller_path, name))
            known_node_id = known_symbols_by_path.get((caller_path, name), "")
            if known_node_id:
                decisions.append(
                    {
                        "round": round_index + 1,
                        "caller_path": caller_path,
                        "callee": name,
                        "decision": "already_grounded",
                        "node_id": known_node_id,
                    }
                )
                continue
            if tool_calls >= MAX_MECHANISM_CALLEE_RESOLUTIONS:
                break
            request = ToolRequest(
                tool_name="structural_find_exact_symbol",
                arguments={"query": name, "limit": 12},
                reason=f"Resolve prompt-relevant callee {name} from {caller_path}.",
            )
            observation = find_exact_symbol_tool.run(request)
            ctx.trace.record_tool(
                request,
                observation,
                round_index=MAX_GRAPH_EXPANSION_ROUNDS + 2 + round_index,
            )
            tool_calls += 1
            if observation.status != "ok":
                raise RuntimeError(f"CodeGraph could not resolve prompt-relevant callee {name}.")
            nodes = [
                node
                for node in _source_authored_nodes(
                    tuple(
                        dict(node)
                        for node in observation.payload.get("nodes", ())
                        if isinstance(node, Mapping)
                    )
                )
                if str(node.get("path") or "").replace("\\", "/") == caller_path
            ]
            if len(nodes) != 1:
                decisions.append(
                    {
                        "round": round_index + 1,
                        "caller_path": caller_path,
                        "callee": name,
                        "decision": "rejected_not_one_same_file_definition",
                        "same_file_match_count": len(nodes),
                    }
                )
                continue
            node = nodes[0]
            node_id = str(node.get("id") or "")
            if not node_id or node_id in known_node_ids:
                decisions.append(
                    {
                        "round": round_index + 1,
                        "caller_path": caller_path,
                        "callee": name,
                        "decision": "already_grounded",
                        "node_id": node_id,
                    }
                )
                continue
            added_obligations: list[str] = []
            for state, caller in sources:
                candidate = _candidate_from_node(
                    ctx,
                    node,
                    score=max(0.25, caller.score),
                    origin="source_call_localization",
                    relationship="source_inferred_call_target",
                    obligation_id=state.obligation.id,
                    source_paths=(caller.path,),
                )
                if candidate is not None:
                    state.candidates.append(candidate)
                    added_obligations.append(state.obligation.id)
            if added_obligations:
                known_node_ids.add(node_id)
                known_symbols_by_path[(candidate.path, candidate.symbol.rsplit("::", 1)[-1])] = node_id
                added_this_round += 1
                decisions.append(
                    {
                        "round": round_index + 1,
                        "caller_path": caller_path,
                        "callee": name,
                        "decision": "localized",
                        "node_id": node_id,
                        "obligation_ids": sorted(set(added_obligations)),
                    }
                )
        if not added_this_round:
            break

    ctx.trace.record(
        "prompt_relevant_callee_localization",
        {
            "tool_calls": tool_calls,
            "resolution_budget": MAX_MECHANISM_CALLEE_RESOLUTIONS,
            "round_limit": MAX_MECHANISM_CALLEE_ROUNDS,
            "decisions": decisions,
        },
    )
    return tool_calls


_FACTORY_HANDOFF_CALL = re.compile(r"(?<![.\w$])((?:create|build)[A-Za-z_$][\w$]{2,})\s*\(")
_FACTORY_HANDOFF_DEFAULT = re.compile(
    r"\b([A-Za-z_$][\w$]*)\s*:\s*\1\s*\|\|\s*((?:create|build)[A-Za-z_$][\w$]{2,})\b"
)


def _recover_factory_handoffs(
    ctx: WorkspaceRetrievalContext,
    *,
    states: Sequence[ObligationProgress],
    find_exact_symbol_tool: Any,
) -> tuple[int, list[dict[str, Any]]]:
    """Recover a bounded function-value default handoff across source files.

    This is intentionally narrower than general cross-file callee expansion.
    It follows visible create/build calls from already grounded candidates, and
    only creates the special final edge when source text proves a function-valued
    property defaults to one named factory. Every intermediate lookup remains an
    exact CodeGraph symbol lookup and every inferred edge is labelled as such.
    """

    known_node_ids = {
        candidate.node_id
        for state in states
        for candidate in (*state.candidates, *state.discovery_hints)
        if candidate.node_id
    }
    queue: list[tuple[ObligationProgress, GroundedCandidate, int]] = []
    for state in states:
        for candidate in _dedupe_candidates((*state.candidates, *state.discovery_hints)):
            if not candidate.node_id:
                continue
            provenance = set(candidate.provenance_origins or (candidate.origin,))
            if provenance & DIRECT_OBLIGATION_PROVENANCE or candidate.source_paths:
                queue.append((state, candidate, 0))
    queue.sort(key=lambda item: (-item[1].score, item[1].path, item[1].line_start))

    tool_calls = 0
    edges: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    seen_steps: set[tuple[str, str]] = set()
    while queue and tool_calls < MAX_FACTORY_HANDOFF_RESOLUTIONS:
        state, caller, depth = queue.pop(0)
        if depth >= MAX_FACTORY_HANDOFF_DEPTH:
            continue
        facts = caller.facts if (caller.facts.visible_calls or caller.facts.callable_defaults) else _candidate_facts(caller.text)
        caller_symbol = caller.symbol.rsplit("::", 1)[-1]
        symbols = [
            symbol
            for symbol in facts.visible_calls
            if symbol != caller_symbol and re.fullmatch(r"(?:create|build)[A-Za-z_$][\w$]{2,}", symbol)
        ]
        symbols.extend(factory for _value, factory in facts.callable_defaults)
        for symbol in ordered_unique(tuple(symbols)):
            key = (caller.node_id, symbol)
            if key in seen_steps or tool_calls >= MAX_FACTORY_HANDOFF_RESOLUTIONS:
                continue
            seen_steps.add(key)
            request = ToolRequest(
                tool_name="structural_find_exact_symbol",
                arguments={"query": symbol, "limit": 12},
                reason=f"Resolve the visible factory/callable handoff {symbol} from {caller.path}.",
            )
            observation = find_exact_symbol_tool.run(request)
            ctx.trace.record_tool(request, observation, round_index=MAX_GRAPH_EXPANSION_ROUNDS + 5 + depth)
            tool_calls += 1
            if observation.status != "ok":
                raise RuntimeError(f"CodeGraph could not resolve factory handoff symbol {symbol}.")
            nodes = _source_authored_nodes(
                tuple(dict(node) for node in observation.payload.get("nodes", ()) if isinstance(node, Mapping))
            )
            paths = {str(node.get("path") or "").replace("\\", "/") for node in nodes}
            if len(paths) != 1 or not nodes:
                decisions.append({"caller": caller.node_id, "symbol": symbol, "decision": "rejected_ambiguous_exact_symbol", "match_count": len(nodes)})
                continue
            # Overloads can yield several nodes in one file. The implementation
            # is the last source declaration, which is the only one with a body
            # in the TypeScript source patterns this bridge handles.
            node = max(nodes, key=lambda item: int(item.get("line_start") or 0))
            target = _candidate_from_node(
                ctx,
                node,
                score=max(0.25, caller.score),
                origin="factory_handoff_localization",
                relationship="factory_handoff",
                obligation_id=state.obligation.id,
                source_paths=(caller.path,),
            )
            if target is None:
                decisions.append({"caller": caller.node_id, "symbol": symbol, "decision": "rejected_unreadable_target"})
                continue
            is_default = any(factory == symbol for _value, factory in facts.callable_defaults)
            if target.node_id not in known_node_ids:
                state.candidates.append(target)
                known_node_ids.add(target.node_id)
            else:
                # Keep the target in this obligation's provenance even when a
                # different obligation localized it first.
                state.candidates.append(target)
            if is_default:
                edges.append(
                    {
                        "kind": "factory_handoff",
                        "source": {"id": caller.node_id, "path": caller.path},
                        "target": {"id": target.node_id, "path": target.path},
                        "_retrieval_provenance": "source_inferred_factory_handoff",
                        "detail": f"default:{symbol}",
                    }
                )
            decisions.append(
                {
                    "caller": caller.node_id,
                    "symbol": symbol,
                    "target": target.node_id,
                    "decision": "localized_default_factory" if is_default else "localized_callable_step",
                    "depth": depth + 1,
                }
            )
            queue.append((state, target, depth + 1))
    ctx.trace.record(
        "factory_handoff_localization",
        {
            "tool_calls": tool_calls,
            "resolution_budget": MAX_FACTORY_HANDOFF_RESOLUTIONS,
            "depth_limit": MAX_FACTORY_HANDOFF_DEPTH,
            "decisions": decisions,
            "edge_count": len(edges),
        },
    )
    return tool_calls, edges


def _directed_candidate_connections(
    candidates: Mapping[str, GroundedCandidate],
    *,
    expanded_edges: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    ids_by_node: dict[str, list[str]] = {}
    for candidate_id, candidate in candidates.items():
        if candidate.node_id:
            ids_by_node.setdefault(candidate.node_id, []).append(candidate_id)
    connections: dict[tuple[str, str, str], dict[str, str]] = {}
    for edge in expanded_edges:
        relationship = str(edge.get("kind") or "")
        if relationship not in PRODUCTIVE_RECOVERY_RELATIONSHIPS:
            continue
        source_id = str((edge.get("source") or {}).get("id") or "")
        target_id = str((edge.get("target") or {}).get("id") or "")
        for source_candidate_id in ids_by_node.get(source_id, ()):
            for target_candidate_id in ids_by_node.get(target_id, ()):
                if source_candidate_id == target_candidate_id:
                    continue
                key = (source_candidate_id, target_candidate_id, relationship)
                connections[key] = {
                    "from_candidate_id": source_candidate_id,
                    "to_candidate_id": target_candidate_id,
                    "relationship": relationship,
                    "provenance": str(edge.get("_retrieval_provenance") or "exact_codegraph_edge"),
                }
                detail = str(edge.get("detail") or "")
                if detail:
                    connections[key]["detail"] = detail
    return sorted(
        connections.values(),
        key=lambda item: (
            item["from_candidate_id"],
            item["to_candidate_id"],
            item["relationship"],
        ),
    )


_LOW_SIGNAL_STATE_FIELDS = {
    "data",
    "file",
    "id",
    "key",
    "name",
    "path",
    "type",
    "value",
}


def _candidate_context_segments(candidate: GroundedCandidate) -> set[str]:
    return {
        value
        for value in _terms(candidate.path.replace("/", " "))
        if value not in {"src", "source", "module", "index", "test", "tests"}
    }


def _candidate_first_parameter(candidate: GroundedCandidate) -> str:
    patterns = (
        r"(?:export\s+default\s+)?function\s+[A-Za-z_$][\w$]*\s*\(\s*([A-Za-z_$][\w$]*)",
        r"def\s+[A-Za-z_][\w]*\s*\(\s*(?:self\s*,\s*)?([A-Za-z_][\w]*)",
    )
    for pattern in patterns:
        match = re.search(pattern, candidate.text)
        if match:
            return match.group(1)
    return ""


def _source_derived_mechanism_connections(
    candidates: Mapping[str, GroundedCandidate],
    *,
    direct_support: Mapping[str, set[str]],
    existing_connections: Sequence[Mapping[str, str]],
    request_terms: set[str],
) -> list[dict[str, str]]:
    """Infer narrowly scoped callback and state-flow relations between exact nodes.

    These relations are deliberately distinguishable from CodeGraph proof. They
    connect already grounded functions only; they never manufacture a candidate.
    """

    anchored: set[str] = {
        candidate_id
        for candidate_id, candidate in candidates.items()
        if direct_support.get(candidate_id)
        or (
            candidate.node_id
            and _mechanism_candidate_terms(candidate) & request_terms
            and set(candidate.relationship_types) & {"calls", "qualified_call"}
        )
    }
    adjacency: dict[str, set[str]] = {candidate_id: set() for candidate_id in candidates}
    for connection in existing_connections:
        if str(connection.get("relationship") or "") not in {
            "calls",
            "qualified_call",
            "instantiates",
            "overrides",
        }:
            continue
        source_id = str(connection.get("from_candidate_id") or "")
        target_id = str(connection.get("to_candidate_id") or "")
        if source_id in adjacency and target_id in adjacency:
            adjacency[source_id].add(target_id)
            adjacency[target_id].add(source_id)
    frontier = set(anchored)
    for _ in range(3):
        frontier = {
            neighbor
            for candidate_id in frontier
            for neighbor in adjacency.get(candidate_id, ())
            if neighbor not in anchored
        }
        if not frontier:
            break
        anchored.update(frontier)

    inferred: dict[tuple[str, str, str], dict[str, str]] = {}

    # CodeGraph can miss calls between nested or locally returned functions.
    # Infer only same-file calls whose target symbol is an exact grounded node.
    # This preserves executable direction without turning a file relationship
    # into a cartesian set of invented node relationships.
    symbols_by_path: dict[str, dict[str, list[str]]] = {}
    for candidate_id, candidate in candidates.items():
        if not candidate.node_id:
            continue
        symbol = candidate.symbol.rsplit("::", 1)[-1]
        if re.fullmatch(r"[A-Za-z_$][\w$]{2,}", symbol):
            symbols_by_path.setdefault(candidate.path, {}).setdefault(symbol, []).append(candidate_id)
    for caller_id, caller in candidates.items():
        if not caller.node_id:
            continue
        for symbol, target_ids in symbols_by_path.get(caller.path, {}).items():
            if len(target_ids) != 1 or not re.search(rf"\b{re.escape(symbol)}\s*\(", caller.text):
                continue
            target_id = target_ids[0]
            if target_id == caller_id:
                continue
            key = (caller_id, target_id, "qualified_call")
            inferred[key] = {
                "from_candidate_id": caller_id,
                "to_candidate_id": target_id,
                "relationship": "qualified_call",
                "provenance": "source_inferred_same_file_call",
                "detail": f"{symbol}(...)",
            }

    # Resolve explicit Owner.member(...) calls across files. The owner must
    # equal the target filename stem and the member must name one exact target,
    # so this does not guess through CommonJS exports or prototype mutation.
    targets_by_member: dict[str, list[str]] = {}
    for candidate_id, candidate in candidates.items():
        if not candidate.node_id:
            continue
        member = candidate.symbol.rsplit("::", 1)[-1]
        if re.fullmatch(r"[A-Za-z_$][\w$]{2,}", member):
            targets_by_member.setdefault(member, []).append(candidate_id)
    qualified_call = re.compile(
        r"\b([A-Za-z_$][\w$]*)\.([A-Za-z_$][\w$]*)\s*\("
    )
    for caller_id, caller in candidates.items():
        if not caller.node_id:
            continue
        for owner, member in qualified_call.findall(caller.text):
            matching_targets = [
                candidate_id
                for candidate_id in targets_by_member.get(member, ())
                if re.sub(r"[^a-z0-9]", "", Path(candidates[candidate_id].path).stem.casefold())
                == re.sub(r"[^a-z0-9]", "", owner.casefold())
            ]
            if len(matching_targets) != 1 or matching_targets[0] == caller_id:
                continue
            target_id = matching_targets[0]
            key = (caller_id, target_id, "qualified_call")
            inferred[key] = {
                "from_candidate_id": caller_id,
                "to_candidate_id": target_id,
                "relationship": "qualified_call",
                "provenance": "source_inferred_qualified_owner_call",
                "detail": f"{owner}.{member}(...)",
            }

    # Newly inferred named calls are valid anchoring links for the narrower
    # callback and state hypotheses below.
    for connection in inferred.values():
        source_id = connection["from_candidate_id"]
        target_id = connection["to_candidate_id"]
        adjacency[source_id].add(target_id)
        adjacency[target_id].add(source_id)
    frontier = set(anchored)
    for _ in range(3):
        frontier = {
            neighbor
            for candidate_id in frontier
            for neighbor in adjacency.get(candidate_id, ())
            if neighbor not in anchored
        }
        if not frontier:
            break
        anchored.update(frontier)
    callbacks_by_parameter: dict[str, list[str]] = {}
    for candidate_id, candidate in candidates.items():
        if not candidate.node_id or candidate_id not in anchored:
            continue
        parameter = _candidate_first_parameter(candidate)
        if parameter:
            callbacks_by_parameter.setdefault(parameter, []).append(candidate_id)

    dynamic_call = re.compile(
        r"\b([A-Za-z_$][\w$]*)\s*\[[^\]\n]+\]\s*\(\s*([A-Za-z_$][\w$]*)"
    )
    for dispatcher_id, dispatcher in candidates.items():
        if not dispatcher.node_id or dispatcher_id not in anchored:
            continue
        dispatcher_context = _candidate_context_segments(dispatcher)
        for match in dynamic_call.finditer(dispatcher.text):
            collection_name, argument_name = match.groups()
            for callback_id in callbacks_by_parameter.get(argument_name, ()):
                if callback_id == dispatcher_id:
                    continue
                callback = candidates[callback_id]
                if not (dispatcher_context & _candidate_context_segments(callback)):
                    continue
                if not direct_support.get(callback_id) and not adjacency.get(callback_id):
                    continue
                key = (dispatcher_id, callback_id, "registered_callback")
                inferred[key] = {
                    "from_candidate_id": dispatcher_id,
                    "to_candidate_id": callback_id,
                    "relationship": "registered_callback",
                    "provenance": "source_inferred_dynamic_collection_callback",
                    "detail": f"{collection_name}[]({argument_name})",
                }

    assignment = re.compile(
        r"\b([A-Za-z_$][\w$]*)\.([A-Za-z_$][\w$]*)\s*=(?!=|>)"
    )
    access = re.compile(r"\b([A-Za-z_$][\w$]*)\.([A-Za-z_$][\w$]*)\b")
    writers: dict[str, list[str]] = {}
    readers: dict[str, list[str]] = {}
    for candidate_id, candidate in candidates.items():
        if not candidate.node_id or candidate_id not in anchored:
            continue
        written_fields = {field for _owner, field in assignment.findall(candidate.text)}
        read_fields = {field for _owner, field in access.findall(candidate.text)} - written_fields
        for field in written_fields - _LOW_SIGNAL_STATE_FIELDS:
            if not (_terms(field) & request_terms):
                continue
            writers.setdefault(field, []).append(candidate_id)
        for field in read_fields - _LOW_SIGNAL_STATE_FIELDS:
            if not (_terms(field) & request_terms):
                continue
            readers.setdefault(field, []).append(candidate_id)
    for field, writer_ids in writers.items():
        reader_ids = readers.get(field, ())
        if not reader_ids or len(writer_ids) * len(reader_ids) > 16:
            continue
        for writer_id in writer_ids:
            writer = candidates[writer_id]
            writer_context = _candidate_context_segments(writer)
            for reader_id in reader_ids:
                if writer_id == reader_id:
                    continue
                reader = candidates[reader_id]
                if not (writer_context & _candidate_context_segments(reader)):
                    continue
                key = (writer_id, reader_id, "state_write_read")
                inferred[key] = {
                    "from_candidate_id": writer_id,
                    "to_candidate_id": reader_id,
                    "relationship": "state_write_read",
                    "provenance": "source_inferred_same_field_flow",
                    "detail": field,
                }
    return sorted(
        inferred.values(),
        key=lambda item: (
            item["from_candidate_id"],
            item["to_candidate_id"],
            item["relationship"],
        ),
    )


def _mechanism_candidate_terms(candidate: GroundedCandidate) -> set[str]:
    # The exact node name and owner path state responsibility. Body vocabulary
    # is deliberately excluded: a caller mentioning a strong callee name must
    # not score as if it were the callee that owns that behavior.
    return _distinctive_terms(" ".join((candidate.symbol, candidate.path)))


def _mechanism_candidate_roles(candidate: GroundedCandidate) -> set[str]:
    """Classify causal responsibility without using obligation ownership."""

    symbol = candidate.symbol.casefold()
    path = candidate.path.casefold()
    text = candidate.text
    roles: set[str] = set()
    if re.search(r"(?:^|::)(?:update|invalidate|set|add|remove|delete|clear|mark|change|write|handle)", symbol):
        roles.add("state_owner")
    if re.search(r"\.(?:set|add|delete|clear|push)\s*\(|(?:^|[^=!<>])=(?![=>])", text):
        roles.add("state_owner")
    if re.search(r"signature|exportedmodule|affected|invalidation|resolution|cache|dependency", symbol):
        roles.add("domain_owner")
    if re.search(r"(?:^|::)(?:create|start|build|watch|schedule|dispatch|invoke|process|render|getnext)", symbol):
        roles.add("controller")
    if re.search(r"report|diagnostic|status|summary|log|assert|checkoutput", symbol):
        roles.add("observer")
    if candidate.file_role == "test":
        roles.add("validation")
    if (
        re.search(r"(?:^|/)utilities?\.[a-z]+$", path)
        or re.search(r"(?:^|::)node(?:map|set)::", symbol)
        or re.search(r"(?:^|::)(?:addRange|createMap|assert[A-Z_$])", candidate.symbol)
    ):
        roles.add("generic_utility")
        roles.difference_update({"state_owner", "domain_owner", "controller"})
    if not roles:
        roles.add("supporting")
    return roles


def _mechanism_edge_weight(connection: Mapping[str, str]) -> float:
    relationship = str(connection.get("relationship") or "")
    provenance = str(connection.get("provenance") or "")
    if relationship in {"calls", "qualified_call"} and provenance == "exact_codegraph_edge":
        return 7.0
    if relationship in {"calls", "qualified_call", "instantiates"}:
        return 5.0
    if relationship in {"registered_callback", "state_write_read"}:
        return 4.0
    if relationship in {"references", "imports", "implements", "extends", "overrides"}:
        return 2.0
    return 1.0


def _select_mechanism_flows(
    states: Sequence[ObligationProgress],
    *,
    expanded_edges: Sequence[Mapping[str, Any]],
    input_char_budget: int | None = MAX_EXPLANATION_INPUT_CHARS,
) -> tuple[
    dict[str, GroundedCandidate],
    dict[str, set[str]],
    dict[str, set[str]],
    list[dict[str, Any]],
    list[dict[str, str]],
    dict[str, Any],
]:
    candidates, direct_support, inherited_support = _candidate_support_graph(states)
    if not candidates:
        return {}, direct_support, inherited_support, [], [], {
            "candidate_inventory": [],
            "connection_decisions": [],
            "flow_decisions": [],
            "unselected_flow_count": 0,
        }
    obligation_terms = {
        state.obligation.id: _distinctive_terms(state.obligation.description)
        for state in states
    }
    request_terms = set().union(*obligation_terms.values()) if obligation_terms else set()
    connections = _directed_candidate_connections(candidates, expanded_edges=expanded_edges)
    connections.extend(
        _source_derived_mechanism_connections(
            candidates,
            direct_support=direct_support,
            existing_connections=connections,
            request_terms=request_terms,
        )
    )
    connections = [
        dict(item)
        for item in {
            (
                item["from_candidate_id"],
                item["to_candidate_id"],
                item["relationship"],
                item.get("provenance", ""),
            ): item
            for item in connections
        }.values()
    ]
    # A connection occupies only its exact directed endpoint pair. When two
    # extractors describe A -> B differently, keep the stronger relationship;
    # B -> A and A -> C are independent facts and remain available. This avoids
    # turning either a file or a flow root into an exclusive selection slot.
    connection_decisions: list[dict[str, Any]] = []
    strongest_connection_by_endpoints: dict[tuple[str, str], dict[str, str]] = {}
    for connection in sorted(
        connections,
        key=lambda item: (
            -_mechanism_edge_weight(item),
            str(item.get("from_candidate_id") or ""),
            str(item.get("to_candidate_id") or ""),
            str(item.get("relationship") or ""),
        ),
    ):
        endpoint_key = (
            connection["from_candidate_id"],
            connection["to_candidate_id"],
        )
        winner = strongest_connection_by_endpoints.get(endpoint_key)
        if winner is None:
            strongest_connection_by_endpoints[endpoint_key] = connection
            continue
        connection_decisions.append(
            {
                "decision": "rejected_weaker_parallel_connection",
                "from_candidate_id": connection["from_candidate_id"],
                "to_candidate_id": connection["to_candidate_id"],
                "relationship": connection["relationship"],
                "provenance": connection.get("provenance", ""),
                "weight": _mechanism_edge_weight(connection),
                "replaced_by_relationship": winner["relationship"],
                "replaced_by_provenance": winner.get("provenance", ""),
                "replaced_by_weight": _mechanism_edge_weight(winner),
            }
        )
    connections = list(strongest_connection_by_endpoints.values())
    adjacency: dict[str, list[tuple[str, dict[str, str]]]] = {
        candidate_id: [] for candidate_id in candidates
    }
    incoming: dict[str, int] = {candidate_id: 0 for candidate_id in candidates}
    for connection in connections:
        if connection["relationship"] not in {
            "calls",
            "qualified_call",
            "registered_callback",
            "state_write_read",
            "instantiates",
            "overrides",
        }:
            continue
        source_id = connection["from_candidate_id"]
        target_id = connection["to_candidate_id"]
        if source_id not in candidates or target_id not in candidates:
            continue
        adjacency.setdefault(source_id, []).append((target_id, connection))
        incoming[target_id] = incoming.get(target_id, 0) + 1

    def support(candidate_id: str) -> set[str]:
        return set((*direct_support.get(candidate_id, ()), *inherited_support.get(candidate_id, ())))

    terms_by_candidate = {
        candidate_id: _mechanism_candidate_terms(candidate)
        for candidate_id, candidate in candidates.items()
    }
    roles_by_candidate = {
        candidate_id: _mechanism_candidate_roles(candidate)
        for candidate_id, candidate in candidates.items()
    }

    def node_score(candidate_id: str) -> float:
        candidate = candidates[candidate_id]
        matched_terms = terms_by_candidate[candidate_id] & request_terms
        roles = roles_by_candidate[candidate_id]
        return (
            float(len(direct_support.get(candidate_id, ())) * 6)
            + float(len(inherited_support.get(candidate_id, ())))
            + float(_candidate_provenance_tier(candidate))
            + float(bool(candidate.node_id))
            + float(len(matched_terms) * 2)
            + float("state_owner" in roles) * 4.0
            + float("domain_owner" in roles) * 5.0
            + float("controller" in roles) * 2.0
            - float("observer" in roles) * 2.0
            - float("generic_utility" in roles) * 4.0
            + max(0.0, min(3.0, candidate.score))
        )

    ranked_seed_ids = sorted(
        (
            candidate_id
            for candidate_id, candidate in candidates.items()
            if candidate.node_id
            and (
                direct_support.get(candidate_id)
                or roles_by_candidate[candidate_id]
                & {"state_owner", "domain_owner", "controller"}
                or (
                    candidate.file_role == "implementation"
                    and terms_by_candidate[candidate_id] & request_terms
                )
            )
        ),
        key=lambda candidate_id: (
            -node_score(candidate_id),
            -len(support(candidate_id)),
            incoming.get(candidate_id, 0),
            candidates[candidate_id].path,
            candidates[candidate_id].line_start,
        ),
    )
    seed_ids = ranked_seed_ids[:MAX_MECHANISM_FLOW_SEEDS]

    def flow_payload(path: tuple[str, ...], path_connections: tuple[dict[str, str], ...]) -> dict[str, Any]:
        covered_obligations = {value for candidate_id in path for value in support(candidate_id)}
        direct_obligations = {
            value for candidate_id in path for value in direct_support.get(candidate_id, ())
        }
        matched_terms = set().union(*(terms_by_candidate[candidate_id] for candidate_id in path)) & request_terms
        obligation_alignment = sum(
            max(
                (
                    len(terms_by_candidate[candidate_id] & terms) / max(1, min(len(terms), 8))
                    for candidate_id in path
                ),
                default=0.0,
            )
            for terms in obligation_terms.values()
        )
        edge_score = sum(_mechanism_edge_weight(item) for item in path_connections)
        causal_roles = set().union(*(roles_by_candidate[candidate_id] for candidate_id in path))
        responsibility_keys = {
            f"{candidates[candidate_id].path}:{role}"
            for candidate_id in path
            for role in roles_by_candidate[candidate_id]
            if role not in {"observer", "generic_utility", "supporting"}
        }
        # Repetition across independent obligation searches is useful discovery
        # evidence, but must not turn obligations into ownership slots. Reward
        # that recurrence most strongly for compact anchors; a long path with a
        # single semantic hit must not outrank a concise issue-grounded anchor
        # merely because it accumulated edges.
        direct_recurrence_bonus = (
            float(len(direct_obligations) * 20) / max(1.0, len(path) ** 0.5)
        )
        score = (
            float(len(matched_terms) * 4)
            + float(len(direct_obligations) * 8)
            + direct_recurrence_bonus
            + float(len(covered_obligations) * 2)
            + obligation_alignment * 8.0
            + edge_score
            + float("state_owner" in causal_roles) * 5.0
            + float("domain_owner" in causal_roles) * 6.0
            + float("controller" in causal_roles) * 3.0
            - float(causal_roles == {"observer"}) * 8.0
            + sum(node_score(candidate_id) for candidate_id in path) * 0.2
            - max(0, len(path) - 7) * 0.5
        )
        return {
            "root_candidate_id": path[0],
            "candidate_ids": list(path),
            "covered_obligation_ids": sorted(covered_obligations),
            "direct_obligation_ids": sorted(direct_obligations),
            "matched_request_terms": sorted(matched_terms),
            "connections": [dict(item) for item in path_connections],
            "causal_roles": sorted(causal_roles),
            "responsibility_keys": sorted(responsibility_keys),
            "direct_recurrence_bonus": round(direct_recurrence_bonus, 4),
            "score": round(score, 4),
        }

    # Generate a bounded number of hypotheses for every retained seed. The old
    # global early exit let the first few branching seeds consume the entire
    # flow budget, so a later state owner could be present in the candidate
    # graph but never receive a flow to compare.
    raw_flows: dict[tuple[str, ...], dict[str, Any]] = {}
    for seed_id in seed_ids:
        seed_flows: dict[tuple[str, ...], dict[str, Any]] = {}
        beam: list[tuple[tuple[str, ...], tuple[dict[str, str], ...]]] = [((seed_id,), ())]
        for _depth in range(MAX_MECHANISM_FLOW_DEPTH):
            next_beam: list[tuple[tuple[str, ...], tuple[dict[str, str], ...]]] = []
            for path, path_connections in beam:
                extensions = [
                    (target_id, connection)
                    for target_id, connection in adjacency.get(path[-1], ())
                    if target_id not in path
                ]
                if not extensions:
                    seed_flows[path] = flow_payload(path, path_connections)
                    continue
                for target_id, connection in extensions:
                    extended_path = (*path, target_id)
                    extended_connections = (*path_connections, connection)
                    seed_flows[extended_path] = flow_payload(extended_path, extended_connections)
                    next_beam.append((extended_path, extended_connections))
            if not next_beam:
                break
            next_beam.sort(
                key=lambda item: flow_payload(item[0], item[1])["score"],
                reverse=True,
            )
            beam = next_beam[:MAX_MECHANISM_FLOW_BEAM]
        for path, flow in sorted(
            seed_flows.items(),
            key=lambda item: (
                -float(item[1]["score"]),
                -len(item[1]["connections"]),
                item[0],
            ),
        )[:MAX_MECHANISM_FLOWS_PER_SEED]:
            existing = raw_flows.get(path)
            if existing is None or float(flow["score"]) > float(existing["score"]):
                raw_flows[path] = flow

    if len(raw_flows) > MAX_MECHANISM_FLOW_CANDIDATES:
        raw_flows = dict(
            sorted(
                raw_flows.items(),
                key=lambda item: (
                    -float(item[1]["score"]),
                    -len(item[1]["connections"]),
                    item[0],
                ),
            )[:MAX_MECHANISM_FLOW_CANDIDATES]
        )

    # Direct semantic ranges can ground the reported scenario even when graph
    # localization cannot resolve them to an exact node. Keep them as singleton
    # hypotheses so the global comparison can retain a trigger or observable
    # boundary alongside the implementation mechanism.
    for candidate_id in sorted(candidates):
        if not direct_support.get(candidate_id):
            continue
        path = (candidate_id,)
        flow = flow_payload(path, ())
        existing = raw_flows.get(path)
        if existing is None or float(flow["score"]) > float(existing["score"]):
            raw_flows[path] = flow

    if not raw_flows:
        for seed_id in seed_ids:
            raw_flows[(seed_id,)] = flow_payload((seed_id,), ())

    for flow in raw_flows.values():
        flow["protected_responsibility_terms"] = []
        if len(flow["candidate_ids"]) != 2 or len(flow["connections"]) != 1:
            continue
        source_id, target_id = flow["candidate_ids"]
        direct_ids = [
            candidate_id
            for candidate_id in (source_id, target_id)
            if direct_support.get(candidate_id)
        ]
        if not direct_ids:
            continue
        other_id = target_id if source_id in direct_ids else source_id
        direct_terms = set().union(*(terms_by_candidate[candidate_id] for candidate_id in direct_ids))
        responsibility_terms = (terms_by_candidate[other_id] - direct_terms) & request_terms
        if responsibility_terms:
            flow["protected_responsibility_terms"] = sorted(responsibility_terms)

    remaining = list(raw_flows.values())
    selected_flows: list[dict[str, Any]] = []
    selected_candidates: set[str] = set()
    selected_connections: set[tuple[str, str, str]] = set()
    selected_responsibility_keys: set[str] = set()
    payload_obligations = [
        {
            "obligation_id": state.obligation.id,
            "description": state.obligation.description,
            "evidence_role": state.obligation.evidence_role.value,
            "depends_on": list(state.obligation.depends_on),
        }
        for state in states
    ]
    used_chars = EXPLANATION_PAYLOAD_SERIALIZATION_MARGIN + len(
        json.dumps(
            {
                "obligations": payload_obligations,
                "candidates": [],
                "mechanism_flows": [],
            },
            sort_keys=True,
        )
    )
    flow_decisions: list[dict[str, Any]] = []
    unselected: list[dict[str, Any]] = []

    def candidate_request_chars(candidate_id: str) -> int:
        candidate = candidates[candidate_id]
        return len(
            json.dumps(
                {
                    "candidate_id": candidate_id,
                    "path": candidate.path,
                    "line_start": candidate.line_start,
                    "line_end": candidate.line_end,
                    "symbol": candidate.symbol,
                    "file_role": candidate.file_role,
                    "semantic_score": round(candidate.score, 4),
                    "direct_obligation_ids": sorted(direct_support.get(candidate_id, ())),
                    "inherited_obligation_ids": sorted(inherited_support.get(candidate_id, ())),
                    "covered_concepts": list(candidate.covered_concepts),
                    "source_paths": list(candidate.source_paths),
                    "relationship_types": list(candidate.relationship_types),
                    "snippet": candidate.text[:MAX_CONSOLIDATION_SNIPPET_CHARS],
                },
                sort_keys=True,
            )
        )

    def flow_request_item(flow: Mapping[str, Any], *, flow_id: str) -> dict[str, Any]:
        return {
            "flow_id": flow_id,
            "candidate_ids": list(flow.get("candidate_ids", ())),
            "score": flow.get("score", 0.0),
        }
    # Compare complete flows by absolute quality. Obligation coverage and
    # discovery terms contribute to a flow's score, but they are deliberately
    # not consumed as slots: one state-change flow cannot suppress a stronger
    # or complementary state-owner flow later in the ranking.
    def root_hypothesis_score(flow: Mapping[str, Any]) -> float:
        root_id = str(flow["root_candidate_id"])
        root = candidates[root_id]
        return (
            node_score(root_id)
            + float(len(direct_support.get(root_id, ())) * 10)
            + float(len(root.covered_concepts) * 4)
            - float("generic_utility" in roles_by_candidate[root_id]) * 8.0
            - float("observer" in roles_by_candidate[root_id]) * 2.0
        )

    def selected_connectivity(flow: Mapping[str, Any]) -> tuple[bool, bool]:
        flow_ids = set(flow["candidate_ids"])
        candidate_connected = bool(flow_ids & selected_candidates)
        if not selected_candidates:
            return candidate_connected, False
        selected_paths = {candidates[candidate_id].path for candidate_id in selected_candidates}
        selected_source_paths = {
            source_path
            for candidate_id in selected_candidates
            for source_path in candidates[candidate_id].source_paths
        }
        flow_paths = {candidates[candidate_id].path for candidate_id in flow_ids}
        flow_source_paths = {
            source_path
            for candidate_id in flow_ids
            for source_path in candidates[candidate_id].source_paths
        }
        file_connected = bool(
            (flow_source_paths & selected_paths)
            or (selected_source_paths & flow_paths)
        )
        return candidate_connected, file_connected

    while remaining:
        # Re-rank after every selection. A root that can extend the mechanism
        # already retained is more useful than a disconnected root with a
        # slightly stronger standalone score. This is a positive connectivity
        # bonus, not a penalty on Qdrant or graph-only discovery.
        remaining.sort(
            key=lambda item: (
                -(
                    root_hypothesis_score(item)
                    + float(selected_connectivity(item)[0]) * 30.0
                    + float(selected_connectivity(item)[1]) * 20.0
                    + float(bool(item.get("protected_responsibility_terms"))) * 15.0
                ),
                -float(item["score"]),
                -len(item["connections"]),
                -len(item["candidate_ids"]),
                item["root_candidate_id"],
            )
        )
        flow = remaining.pop(0)
        root_path = candidates[str(flow["root_candidate_id"])].path
        candidate_connected, file_connected = selected_connectivity(flow)
        connection_keys = {
            (
                item["from_candidate_id"],
                item["to_candidate_id"],
                item["relationship"],
            )
            for item in flow["connections"]
        }
        new_connections = connection_keys - selected_connections
        new_ids = [value for value in flow["candidate_ids"] if value not in selected_candidates]
        new_responsibility_keys = (
            set(flow.get("responsibility_keys", ())) - selected_responsibility_keys
        )
        overlapping_selected_flows = [
            {
                "flow_id": selected["flow_id"],
                "score": selected["score"],
                "shared_candidate_ids": sorted(
                    set(flow["candidate_ids"]) & set(selected["candidate_ids"])
                ),
            }
            for selected in selected_flows
            if set(flow["candidate_ids"]) & set(selected["candidate_ids"])
        ]
        if selected_flows and not new_ids:
            dominators = [
                item
                for item in selected_flows
                if set(flow["candidate_ids"]).issubset(item["candidate_ids"])
                and connection_keys.issubset(
                    {
                        (
                            connection["from_candidate_id"],
                            connection["to_candidate_id"],
                            connection["relationship"],
                        )
                        for connection in item["connections"]
                    }
                )
            ]
            flow_decisions.append(
                {
                    "root_candidate_id": flow["root_candidate_id"],
                    "candidate_ids": list(flow["candidate_ids"]),
                    "score": flow["score"],
                    "decision": "rejected_no_new_candidate",
                    "compared_with": overlapping_selected_flows,
                    "dominated_by_flow_ids": [item["flow_id"] for item in dominators],
                }
            )
            continue
        protected_handoff_terms = set(flow.get("protected_responsibility_terms", ()))
        new_substantive_ids = [
            candidate_id
            for candidate_id in new_ids
            if roles_by_candidate[candidate_id]
            & {"state_owner", "domain_owner", "controller"}
            and "generic_utility" not in roles_by_candidate[candidate_id]
        ]
        if (
            selected_flows
            and new_ids
            and not new_responsibility_keys
            and not protected_handoff_terms
            and not new_substantive_ids
        ):
            flow_decisions.append(
                {
                    "root_candidate_id": flow["root_candidate_id"],
                    "candidate_ids": list(flow["candidate_ids"]),
                    "score": flow["score"],
                    "decision": "rejected_no_new_causal_responsibility",
                    "causal_roles": list(flow.get("causal_roles", ())),
                    "new_substantive_candidate_ids": [],
                    "protected_handoff_terms": sorted(protected_handoff_terms),
                    "compared_with": overlapping_selected_flows,
                }
            )
            continue
        added_candidate_chars = sum(candidate_request_chars(candidate_id) for candidate_id in new_ids)
        next_flow_id = f"mechanism_flow_{len(selected_flows) + 1}"
        added_flow_chars = len(
            json.dumps(flow_request_item(flow, flow_id=next_flow_id), sort_keys=True)
        )
        added_connection_chars = 0
        added_chars = added_candidate_chars + added_flow_chars
        if input_char_budget is not None and used_chars + added_chars > input_char_budget:
            flow_decisions.append(
                {
                    "root_candidate_id": flow["root_candidate_id"],
                    "candidate_ids": list(flow["candidate_ids"]),
                    "score": flow["score"],
                    "root_path": root_path,
                    "root_hypothesis_score": round(root_hypothesis_score(flow), 4),
                    "decision": "rejected_input_char_budget",
                    "added_chars": added_chars,
                    "used_chars": used_chars,
                    "input_char_budget": input_char_budget,
                    "compared_with": overlapping_selected_flows,
                }
            )
            unselected.append(flow)
            continue
        selected_flows.append(
            {
                "flow_id": next_flow_id,
                **flow,
            }
        )
        selected_candidates.update(new_ids)
        selected_connections.update(connection_keys)
        selected_responsibility_keys.update(flow.get("responsibility_keys", ()))
        used_chars += added_chars
        flow_decisions.append(
            {
                "flow_id": selected_flows[-1]["flow_id"],
                "root_candidate_id": flow["root_candidate_id"],
                "candidate_ids": list(flow["candidate_ids"]),
                "score": flow["score"],
                "root_path": root_path,
                "root_hypothesis_score": round(root_hypothesis_score(flow), 4),
                "connected_to_selected_candidate": candidate_connected,
                "connected_to_selected_file": file_connected,
                "decision": "selected",
                "matched_mechanism_terms": list(flow["matched_request_terms"]),
                "direct_obligation_ids": list(flow["direct_obligation_ids"]),
                "new_responsibility_keys": sorted(new_responsibility_keys),
                "new_substantive_candidate_ids": new_substantive_ids,
                "protected_handoff_terms": sorted(protected_handoff_terms),
                "new_transition_count": len(new_connections),
                "added_chars": added_chars,
                "added_candidate_chars": added_candidate_chars,
                "added_flow_chars": added_flow_chars,
                "added_connection_chars": added_connection_chars,
                "used_chars": used_chars,
                "compared_with": overlapping_selected_flows,
            }
        )

    selected_candidate_map = {
        candidate_id: candidates[candidate_id]
        for candidate_id in sorted(selected_candidates)
    }
    eligible_connection_items = [
        connection
        for connection in connections
        if connection["from_candidate_id"] in selected_candidates
        and connection["to_candidate_id"] in selected_candidates
    ]
    eligible_connection_items.sort(
        key=lambda item: (
            -_mechanism_edge_weight(item),
            str(item.get("from_candidate_id") or ""),
            str(item.get("to_candidate_id") or ""),
            str(item.get("relationship") or ""),
        )
    )
    selected_connection_items: list[dict[str, str]] = []
    for connection in eligible_connection_items:
        connection_chars = len(json.dumps(connection, sort_keys=True)) + 2
        if input_char_budget is not None and used_chars + connection_chars > input_char_budget:
            continue
        selected_connection_items.append(connection)
        used_chars += connection_chars
    request_flows = [
        flow_request_item(flow, flow_id=str(flow["flow_id"]))
        for flow in selected_flows
    ]
    return (
        selected_candidate_map,
        direct_support,
        inherited_support,
        request_flows,
        selected_connection_items,
        {
            "candidate_inventory": [
                {
                    **_candidate_trace_item(candidate, candidate_id=candidate_id),
                    "direct_obligation_ids": sorted(direct_support.get(candidate_id, ())),
                    "inherited_obligation_ids": sorted(inherited_support.get(candidate_id, ())),
                    "node_score": round(node_score(candidate_id), 4),
                    "outgoing_transition_count": len(adjacency.get(candidate_id, ())),
                    "matched_request_terms": sorted(terms_by_candidate[candidate_id] & request_terms),
                    "causal_roles": sorted(roles_by_candidate[candidate_id]),
                    "selected_for_final_request": candidate_id in selected_candidates,
                }
                for candidate_id, candidate in candidates.items()
            ],
            "connection_decisions": connection_decisions,
            "flow_decisions": flow_decisions,
            "input_char_budget": input_char_budget,
            "used_chars": used_chars,
            "unselected_flow_count": len(unselected),
            "source_inferred_connection_count": sum(
                str(item.get("provenance") or "").startswith("source_inferred_")
                for item in connections
            ),
        },
    )


def _consolidate_obligation_evidence(
    ctx: WorkspaceRetrievalContext,
    states: Sequence[ObligationProgress],
    *,
    expanded_edges: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    (
        candidate_by_id,
        direct_support,
        inherited_support,
        mechanism_flows,
        candidate_connections,
        mechanism_flow_ledger,
    ) = _select_mechanism_flows(
        states,
        expanded_edges=expanded_edges,
    )
    candidate_ids_by_obligation = {
        state.obligation.id: [
            candidate_id
            for candidate_id in candidate_by_id
            if state.obligation.id
            in set((*direct_support.get(candidate_id, ()), *inherited_support.get(candidate_id, ())))
        ]
        for state in states
    }
    payload_obligations = [
        {
            "obligation_id": state.obligation.id,
            "description": state.obligation.description,
            "evidence_role": state.obligation.evidence_role.value,
            "depends_on": list(state.obligation.depends_on),
        }
        for state in states
    ]
    payload_candidates = [
        {
            "candidate_id": candidate_id,
            "path": candidate.path,
            "line_start": candidate.line_start,
            "line_end": candidate.line_end,
            "symbol": candidate.symbol,
            "file_role": candidate.file_role,
            "semantic_score": round(candidate.score, 4),
            "direct_obligation_ids": sorted(direct_support.get(candidate_id, ())),
            "inherited_obligation_ids": sorted(inherited_support.get(candidate_id, ())),
            "covered_concepts": list(candidate.covered_concepts),
            "source_paths": list(candidate.source_paths),
            "relationship_types": list(candidate.relationship_types),
            "facts": candidate.facts.to_dict(),
            "snippet": candidate.text[:MAX_CONSOLIDATION_SNIPPET_CHARS],
        }
        for candidate_id, candidate in candidate_by_id.items()
    ]
    ctx.trace.record(
        "mechanism_flows_selected",
        {
            "input_char_budget": MAX_EXPLANATION_INPUT_CHARS,
            "candidate_count": len(candidate_by_id),
            "flow_count": len(mechanism_flows),
            "mechanism_flows": mechanism_flows,
            "candidate_connections": candidate_connections,
            "candidates": [
                {
                    "candidate_id": candidate_id,
                    "path": candidate.path,
                    "line_start": candidate.line_start,
                    "line_end": candidate.line_end,
                    "symbol": candidate.symbol,
                    "direct_obligation_ids": sorted(direct_support.get(candidate_id, ())),
                    "inherited_obligation_ids": sorted(inherited_support.get(candidate_id, ())),
                }
                for candidate_id, candidate in candidate_by_id.items()
            ],
        },
    )
    ctx.trace.record("mechanism_flow_decision_ledger", mechanism_flow_ledger)

    if not candidate_by_id:
        return {
            "strategy": "global_causal_mechanism_selection_v2",
            "llm_calls": 0,
            "accepted_candidate_ids": [],
            "accepted_ids_by_obligation": {},
            "rejected_candidate_ids": [],
            "invalid_candidate_ids": [],
            "obligation_statuses": {
                state.obligation.id: "unresolved" for state in states
            },
            "unresolved_reasons": {
                state.obligation.id: "No candidates reached evidence consolidation."
                for state in states
            },
            "concepts": [],
            "usage": {},
        }

    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def log_event(event_type: str, payload: Mapping[str, Any]) -> None:
        if event_type == "llm_response_received":
            raw = payload.get("raw_response", {})
            raw_usage = raw.get("usage", {}) if isinstance(raw, Mapping) else {}
            if isinstance(raw_usage, Mapping):
                for key in usage:
                    usage[key] += int(raw_usage.get(key, 0) or 0)
        ctx.trace.record(event_type, {"stage": "obligation_evidence_consolidation", **dict(payload)})

    obligation_ids = [state.obligation.id for state in states]
    candidate_ids = list(candidate_by_id)
    consolidation_payload = {
        "obligations": payload_obligations,
        "candidates": payload_candidates,
        "mechanism_flows": mechanism_flows,
        "candidate_connections": candidate_connections,
    }
    ctx.trace.record(
        "mechanism_flow_request_budget",
        {
            "input_char_budget": MAX_EXPLANATION_INPUT_CHARS,
            "serialized_payload_chars": len(json.dumps(consolidation_payload, sort_keys=True)),
            "candidate_payload_chars": len(json.dumps(payload_candidates, sort_keys=True)),
            "flow_payload_chars": len(json.dumps(mechanism_flows, sort_keys=True)),
            "connection_payload_chars": len(json.dumps(candidate_connections, sort_keys=True)),
            "candidate_count": len(payload_candidates),
            "flow_count": len(mechanism_flows),
            "connection_count": len(candidate_connections),
            "candidate_paths": sorted({item["path"] for item in payload_candidates}),
        },
    )
    response = complete_json(
        ctx.config.llm_config,
        (
            {"role": "system", "content": CONSOLIDATION_PROMPT_PATH.read_text(encoding="utf-8")},
            {
                "role": "user",
                "content": json.dumps(consolidation_payload, sort_keys=True),
            },
        ),
        response_format=_consolidation_response_format(obligation_ids, candidate_ids),
        log_event=log_event,
    )

    selected_evidence = (
        response.get("selected_evidence")
        if isinstance(response.get("selected_evidence"), list)
        else []
    )
    assessments = (
        response.get("obligation_assessments")
        if isinstance(response.get("obligation_assessments"), list)
        else []
    )
    assessment_by_obligation = {
        str(item.get("obligation_id") or ""): item
        for item in assessments
        if isinstance(item, Mapping) and str(item.get("obligation_id") or "") in obligation_ids
    }
    accepted_ids: list[str] = []
    accepted_ids_by_obligation: dict[str, list[str]] = {}
    invalid_ids: list[str] = []
    selection_records: list[dict[str, Any]] = []
    for item in selected_evidence:
        if not isinstance(item, Mapping):
            continue
        candidate_id = str(item.get("candidate_id") or "")
        if candidate_id not in candidate_by_id:
            invalid_ids.append(candidate_id)
            continue
        mapped_obligations = list(
            ordered_unique(
                tuple(
                    str(value)
                    for value in item.get("obligation_ids", ())
                    if str(value) in obligation_ids
                )
            )
        )
        if not mapped_obligations:
            invalid_ids.append(candidate_id)
            continue
        if candidate_id not in accepted_ids:
            accepted_ids.append(candidate_id)
            selection_records.append(
                {
                    "candidate_id": candidate_id,
                    "mechanism_role": str(item.get("mechanism_role") or ""),
                    "obligation_ids": mapped_obligations,
                    "reason": str(item.get("reason") or ""),
                }
            )
        for obligation_id in mapped_obligations:
            accepted_ids_by_obligation.setdefault(obligation_id, []).append(candidate_id)

    accepted_id_set = set(accepted_ids)
    obligation_statuses: dict[str, str] = {}
    unresolved_reasons: dict[str, str] = {}
    for state in states:
        obligation_id = state.obligation.id
        assessment = assessment_by_obligation.get(obligation_id, {})
        assessment_ids = [
            str(value)
            for value in assessment.get("supporting_candidate_ids", ())
            if str(value) in accepted_id_set
        ]
        invalid_ids.extend(
            str(value)
            for value in assessment.get("supporting_candidate_ids", ())
            if str(value) not in candidate_by_id
        )
        valid_ids = list(
            ordered_unique(
                tuple((*accepted_ids_by_obligation.get(obligation_id, ()), *assessment_ids))
            )
        )
        accepted_ids_by_obligation[obligation_id] = valid_ids
        accepted = [candidate_by_id[candidate_id] for candidate_id in valid_ids]
        rejected = [
            candidate_by_id[candidate_id]
            for candidate_id in candidate_ids
            if candidate_id not in valid_ids
        ]
        state.candidates = _dedupe_candidates(accepted)
        state.discovery_hints.extend(rejected)
        status = str(assessment.get("status") or "unresolved")
        obligation_statuses[obligation_id] = status
        if status in {"partial", "unresolved"}:
            missing = str(assessment.get("missing_handoff") or "").strip()
            reason = str(assessment.get("reason") or "").strip()
            unresolved_reasons[obligation_id] = "; ".join(value for value in (reason, missing) if value) or (
                "The selected causal mechanism does not establish this obligation."
            )

    concepts: list[dict[str, Any]] = []
    for item in response.get("concepts", ()):
        if not isinstance(item, Mapping):
            continue
        supporting_ids = [
            str(value)
            for value in item.get("supporting_candidate_ids", ())
            if str(value) in accepted_id_set
        ]
        invalid_ids.extend(
            str(value)
            for value in item.get("supporting_candidate_ids", ())
            if str(value) not in candidate_by_id
        )
        mapped_obligations = [
            str(value)
            for value in item.get("obligation_ids", ())
            if str(value) in obligation_ids
            and any(candidate_id in accepted_ids_by_obligation.get(str(value), ()) for candidate_id in supporting_ids)
        ]
        if not supporting_ids or not mapped_obligations:
            continue
        concepts.append(
            {
                "id": str(item.get("id") or ""),
                "proposition": str(item.get("proposition") or ""),
                "supporting_candidate_ids": list(ordered_unique(tuple(supporting_ids))),
                "obligation_ids": list(ordered_unique(tuple(mapped_obligations))),
            }
        )

    selected_mechanisms: list[dict[str, Any]] = []
    for item in response.get("mechanisms", ()):
        if not isinstance(item, Mapping):
            continue
        mechanism_candidate_ids = list(
            ordered_unique(
                tuple(
                    str(value)
                    for value in item.get("candidate_ids", ())
                    if str(value) in accepted_id_set
                )
            )
        )
        if not mechanism_candidate_ids:
            continue
        selected_mechanisms.append(
            {
                "id": str(item.get("id") or ""),
                "status": str(item.get("status") or "partial"),
                "candidate_ids": mechanism_candidate_ids,
                "description": str(item.get("description") or ""),
            }
        )

    rejected_ids = [candidate_id for candidate_id in candidate_ids if candidate_id not in accepted_id_set]
    result = {
        "strategy": "global_causal_mechanism_selection_v2",
        "llm_calls": 1,
        "accepted_candidate_ids": accepted_ids,
        "accepted_ids_by_obligation": accepted_ids_by_obligation,
        "rejected_candidate_ids": rejected_ids,
        "invalid_candidate_ids": list(ordered_unique(tuple(invalid_ids))),
        "selected_mechanisms": selected_mechanisms,
        "selection_records": selection_records,
        "obligation_statuses": obligation_statuses,
        "unresolved_reasons": unresolved_reasons,
        "concepts": concepts,
        "usage": usage,
        "candidate_connection_count": len(candidate_connections),
        "mechanism_flow_count": len(mechanism_flows),
    }
    ctx.trace.record(
        "evidence_consolidation_decision_ledger",
        {
            "strategy": "global_causal_mechanism_selection_v2",
            "selected_mechanisms": selected_mechanisms,
            "selected_evidence": selection_records,
            "globally_rejected_candidate_ids": rejected_ids,
            "obligations": [
                {
                    "obligation_id": state.obligation.id,
                    "discovery_candidate_ids": candidate_ids_by_obligation[state.obligation.id],
                    "submitted_candidate_ids": candidate_ids,
                    "accepted_candidate_ids": accepted_ids_by_obligation.get(state.obligation.id, []),
                    "status": obligation_statuses.get(state.obligation.id, "unresolved"),
                    "final_llm_reason": str(assessment_by_obligation.get(state.obligation.id, {}).get("reason") or ""),
                    "missing_handoff": str(assessment_by_obligation.get(state.obligation.id, {}).get("missing_handoff") or ""),
                }
                for state in states
            ],
            "invalid_candidate_ids": list(ordered_unique(tuple(invalid_ids))),
        },
    )
    ctx.trace.record("obligation_evidence_consolidated", result)
    return result


def _connected_candidate_shortlists(
    states: Sequence[ObligationProgress],
    *,
    expanded_edges: Sequence[Mapping[str, Any]],
    limit: int,
) -> dict[str, tuple[GroundedCandidate, ...]]:
    candidates_by_obligation = {
        state.obligation.id: _dedupe_candidates(state.candidates)
        for state in states
    }
    unique: dict[str, GroundedCandidate] = {}
    obligations_by_key: dict[str, set[str]] = {}
    for obligation_id, candidates in candidates_by_obligation.items():
        for candidate in candidates:
            key = _candidate_ledger_key(candidate)
            unique[key] = candidate if key not in unique else _merge_candidate_provenance(unique[key], candidate)
            obligations_by_key.setdefault(key, set()).add(obligation_id)
    if not unique:
        return {state.obligation.id: () for state in states}

    parent = {key: key for key in unique}

    def find(key: str) -> str:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    keys_by_node: dict[str, list[str]] = {}
    keys_by_path: dict[str, list[str]] = {}
    for key, candidate in unique.items():
        if candidate.node_id:
            keys_by_node.setdefault(candidate.node_id, []).append(key)
        keys_by_path.setdefault(candidate.path, []).append(key)
    for keys in keys_by_node.values():
        for key in keys[1:]:
            union(keys[0], key)
    edge_count_by_pair: dict[frozenset[str], int] = {}
    for edge in expanded_edges:
        source_id = str((edge.get("source") or {}).get("id") or "")
        target_id = str((edge.get("target") or {}).get("id") or "")
        if not source_id or not target_id:
            continue
        for source_key in keys_by_node.get(source_id, ()):
            for target_key in keys_by_node.get(target_id, ()):
                union(source_key, target_key)
                pair = frozenset((source_key, target_key))
                edge_count_by_pair[pair] = edge_count_by_pair.get(pair, 0) + 1
    for key, candidate in unique.items():
        for source_path in candidate.source_paths:
            for source_key in keys_by_path.get(source_path, ()):
                union(key, source_key)

    components: dict[str, set[str]] = {}
    for key in unique:
        components.setdefault(find(key), set()).add(key)
    component_rank: dict[str, tuple[int, int, int, int, float, int]] = {}
    for root, keys in components.items():
        obligation_count = len({value for key in keys for value in obligations_by_key.get(key, ())})
        seed_count = sum(
            int(
                bool(
                    {"request_anchor", "exact_prompt_anchor", "semantic_anchor"}
                    & set(unique[key].provenance_origins or (unique[key].origin,))
                )
            )
            for key in keys
        )
        productive_edges = sum(
            count
            for pair, count in edge_count_by_pair.items()
            if pair and all(key in keys for key in pair)
        )
        provenance_tier = max(_candidate_provenance_tier(unique[key]) for key in keys)
        component_rank[root] = (
            obligation_count,
            seed_count,
            productive_edges,
            provenance_tier,
            max(unique[key].score for key in keys),
            -len(keys),
        )

    component_shortlists: dict[str, tuple[GroundedCandidate, ...]] = {}
    for obligation_id, candidates in candidates_by_obligation.items():
        keys = {_candidate_ledger_key(candidate) for candidate in candidates}
        available_roots = {find(key) for key in keys if key in parent}
        if not available_roots:
            component_shortlists[obligation_id] = ()
            continue
        verified_seeds = [
            candidate
            for candidate in candidates
            if {"request_anchor", "exact_prompt_anchor", "focused_semantic_bridge"}
            & set(candidate.provenance_origins or (candidate.origin,))
        ]
        best_root = max(available_roots, key=lambda root: component_rank[root])
        component_candidates = [
            candidate
            for candidate in candidates
            if find(_candidate_ledger_key(candidate)) == best_root
        ]
        ranked = sorted(
            _dedupe_candidates((*verified_seeds, *component_candidates)),
            key=lambda candidate: (
                -int(candidate in verified_seeds),
                -_candidate_provenance_tier(candidate),
                -candidate.score,
                candidate.path,
                candidate.line_start,
            ),
        )
        component_shortlists[obligation_id] = tuple(ranked[:limit])
    return component_shortlists


def _candidate_provenance_tier(candidate: GroundedCandidate) -> int:
    provenance = set(candidate.provenance_origins or (candidate.origin,))
    relationships = set(candidate.relationship_types or ((candidate.relationship,) if candidate.relationship else ()))
    if provenance & {"request_anchor", "exact_prompt_anchor"}:
        return 4
    if provenance & {"focused_semantic_bridge", "graph_direct_target"}:
        return 3
    if "qualified_reference" in relationships or relationships & PRODUCTIVE_RECOVERY_RELATIONSHIPS:
        return 3
    if "semantic_anchor" in provenance:
        return 2
    return 0


def _candidate_connections(
    candidates: Mapping[str, GroundedCandidate],
    *,
    expanded_edges: Sequence[Mapping[str, Any]],
    candidate_obligations: Mapping[str, str] | None = None,
    allowed_obligation_pairs: set[frozenset[str]] | None = None,
) -> list[dict[str, str]]:
    edge_pairs = {
        frozenset((source_id, target_id)): str(edge.get("kind") or "related")
        for edge in expanded_edges
        if (source_id := str((edge.get("source") or {}).get("id") or ""))
        and (target_id := str((edge.get("target") or {}).get("id") or ""))
    }
    connections: list[dict[str, str]] = []
    items = list(candidates.items())
    for index, (left_id, left) in enumerate(items):
        for right_id, right in items[index + 1 :]:
            if candidate_obligations is not None and allowed_obligation_pairs is not None:
                left_obligation = candidate_obligations.get(left_id, "")
                right_obligation = candidate_obligations.get(right_id, "")
                if (
                    left_obligation != right_obligation
                    and frozenset((left_obligation, right_obligation)) not in allowed_obligation_pairs
                ):
                    continue
            relationship = ""
            if left.node_id and right.node_id and left.node_id != right.node_id:
                relationship = edge_pairs.get(frozenset((left.node_id, right.node_id)), "")
            if not relationship and (left.path in right.source_paths or right.path in left.source_paths):
                relationship = "codegraph_file_relationship"
            if relationship:
                connections.append(
                    {
                        "from_candidate_id": left_id,
                        "to_candidate_id": right_id,
                        "relationship": relationship,
                    }
                )
    return connections


def _consolidation_response_format(
    obligation_ids: Sequence[str],
    _candidate_ids: Sequence[str],
) -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "obligation_evidence_consolidation",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "mechanisms": {
                        "type": "array",
                        "maxItems": 8,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "id": {"type": "string"},
                                "status": {"type": "string", "enum": ["complete", "partial"]},
                                "candidate_ids": {
                                    "type": "array",
                                    "minItems": 1,
                                    "items": {"type": "string", "minLength": 1},
                                },
                                "description": {"type": "string"},
                            },
                            "required": ["id", "status", "candidate_ids", "description"],
                        },
                    },
                    "selected_evidence": {
                        "type": "array",
                        "maxItems": MAX_EVIDENCE,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "candidate_id": {"type": "string", "minLength": 1},
                                "mechanism_role": {
                                    "type": "string",
                                    "enum": [
                                        "issue_anchor",
                                        "entry_or_trigger",
                                        "producer",
                                        "controller",
                                        "state_owner",
                                        "handoff",
                                        "consumer",
                                        "observer",
                                        "validation",
                                    ],
                                },
                                "obligation_ids": {
                                    "type": "array",
                                    "minItems": 1,
                                    "items": {"type": "string", "enum": list(obligation_ids)},
                                },
                                "reason": {"type": "string"},
                            },
                            "required": ["candidate_id", "mechanism_role", "obligation_ids", "reason"],
                        },
                    },
                    "obligation_assessments": {
                        "type": "array",
                        "minItems": len(obligation_ids),
                        "maxItems": len(obligation_ids),
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "obligation_id": {"type": "string", "enum": list(obligation_ids)},
                                "status": {
                                    "type": "string",
                                    "enum": [
                                        "prompt_grounded",
                                        "repository_supported",
                                        "jointly_supported",
                                        "partial",
                                        "unresolved",
                                    ],
                                },
                                "supporting_candidate_ids": {
                                    "type": "array",
                                    "items": {"type": "string", "minLength": 1},
                                },
                                "reason": {"type": "string"},
                                "missing_handoff": {"type": "string"},
                            },
                            "required": [
                                "obligation_id",
                                "status",
                                "supporting_candidate_ids",
                                "reason",
                                "missing_handoff",
                            ],
                        },
                    },
                    "concepts": {
                        "type": "array",
                        "maxItems": 16,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "id": {"type": "string"},
                                "proposition": {"type": "string"},
                                "supporting_candidate_ids": {
                                    "type": "array",
                                    "minItems": 1,
                                    "items": {"type": "string", "minLength": 1},
                                },
                                "obligation_ids": {
                                    "type": "array",
                                    "minItems": 1,
                                    "items": {"type": "string", "enum": list(obligation_ids)},
                                },
                            },
                            "required": ["id", "proposition", "supporting_candidate_ids", "obligation_ids"],
                        },
                    },
                },
                "required": ["mechanisms", "selected_evidence", "obligation_assessments", "concepts"],
            },
        },
    }


def _ground_request_anchors(
    ctx: WorkspaceRetrievalContext,
    *,
    anchors: Mapping[str, Sequence[str]],
    additional_paths: Sequence[str],
    additional_symbols: Sequence[str],
    qdrant_tool: Any,
    structural_tools: Mapping[str, Any],
) -> tuple[list[AnchorConfirmation], list[dict[str, Any]], list[str], list[str], int]:
    confirmations: list[AnchorConfirmation] = []
    anchor_nodes: list[dict[str, Any]] = []
    unresolved_symbols: list[str] = []
    ambiguous_symbols: list[str] = []
    tool_calls = 0

    path_confirmations: list[AnchorConfirmation] = []
    for raw_path in ordered_unique((*anchors.get("paths", ()), *additional_paths)):
        resolved = _resolve_repository_path(ctx.config.workspace_root, raw_path)
        matches = ({"path": resolved},) if resolved else ()
        confirmation = AnchorConfirmation("path", raw_path, bool(resolved), matches)
        confirmations.append(confirmation)
        path_confirmations.append(confirmation)

    symbols = ordered_unique((*anchors.get("primary_symbols", ()), *additional_symbols))[:16]
    supporting_symbols = ordered_unique(tuple(anchors.get("supporting_symbols", ())))[:16]
    structurally_confirmed: set[str] = set()
    path_qualified_values: set[str] = set()
    for symbol in symbols:
        qualified_paths = _path_qualifications(symbol, path_confirmations)
        if qualified_paths:
            path_qualified_values.add(symbol)
            confirmed_matches = tuple(
                match
                for confirmation in qualified_paths
                if confirmation.confirmed_in_repository
                for match in confirmation.matches
            )
            confirmations.append(
                AnchorConfirmation(
                    "symbol",
                    symbol,
                    bool(confirmed_matches),
                    confirmed_matches,
                    "path_qualified" if confirmed_matches else "path_qualified_prompt_only",
                )
            )
            continue
        request = ToolRequest(
            tool_name="structural_find_exact_symbol",
            arguments={"query": symbol, "limit": 12},
            reason=f"Confirm whether the extracted symbol {symbol} exists in the selected repository.",
        )
        observation = structural_tools["structural_find_exact_symbol"].run(request)
        ctx.trace.record_tool(request, observation, round_index=0)
        tool_calls += 1
        if observation.status != "ok":
            raise RuntimeError(f"CodeGraph exact-symbol resolution failed: {observation.payload.get('reason', 'unknown error')}")
        nodes = _source_authored_nodes(
            tuple(dict(node) for node in observation.payload.get("nodes", ()) if isinstance(node, Mapping))
        )
        match_count = int(observation.payload.get("match_count") or len(nodes))
        match_count = len(nodes)
        preferred_nodes = _nodes_in_confirmed_paths(nodes, path_confirmations)
        if preferred_nodes:
            nodes = list(preferred_nodes)
            match_count = len(nodes)
        if match_count:
            structurally_confirmed.add(symbol)
            confirmations.append(
                AnchorConfirmation(
                    "symbol",
                    symbol,
                    True,
                    tuple(
                        {"path": str(node.get("path") or ""), "line": int(node.get("line_start") or 0), "node_id": str(node.get("id") or "")}
                        for node in nodes[:4]
                    ),
                )
            )
        if match_count == 1 and len(nodes) == 1:
            anchor_nodes.append({**nodes[0], "anchor_query": symbol})
        elif match_count > 1:
            ambiguous_symbols.append(symbol)
        else:
            unresolved_symbols.append(symbol)

    semantic_anchors = [
        (kind, value)
        for kind in ("primary_symbols", "errors", "literals", "identifiers")
        for value in ordered_unique(tuple(anchors.get(kind, ())))
        if not (
            (kind == "primary_symbols" and value in structurally_confirmed)
            or value in path_qualified_values
            or _path_qualifications(value, path_confirmations)
        )
    ]
    for kind, value in semantic_anchors[:32]:
        distribution = _anchor_index_distribution(qdrant_tool, value)
        matches = distribution["matches"]
        is_common = _anchor_is_repository_common(distribution)
        match_type = "repository_common" if is_common else ("exact_index_text" if matches else "prompt_only")
        if kind == "errors" and not matches and len(value) >= 12 and len(_terms(value)) >= 3:
            request = ToolRequest(
                tool_name="qdrant_hybrid_search",
                arguments={"query": value, "limit": 5, "max_per_path": 1, "file_role": "any"},
                reason="Resolve a reported error message to one dominant repository source location.",
            )
            observation = qdrant_tool.run(request)
            ctx.trace.record_tool(request, observation, round_index=0)
            tool_calls += 1
            if observation.status != "ok":
                raise RuntimeError("Error-anchor search failed.")
            dominant = _dominant_error_anchor_result(
                value,
                tuple(dict(item) for item in observation.payload.get("results", ()) if isinstance(item, Mapping)),
            )
            if dominant is not None:
                matches = (dominant,)
                match_type = "strong_anchor_search"
        confirmations.append(
            AnchorConfirmation(
                "symbol" if kind == "primary_symbols" else kind[:-1],
                value,
                bool(distribution["chunk_count"] or matches),
                () if is_common else matches,
                match_type,
            )
        )

    unresolved_symbols.extend(symbol for symbol in supporting_symbols if symbol not in unresolved_symbols)
    return confirmations, anchor_nodes, unresolved_symbols, ambiguous_symbols, tool_calls


def _resolve_repository_path(workspace_root: str, raw_path: str) -> str:
    normalized = str(raw_path).replace("\\", "/").lstrip("./")
    parts = Path(normalized).parts
    root = Path(workspace_root)
    for index in range(len(parts)):
        candidate = Path(*parts[index:]).as_posix()
        if (root / candidate).is_file():
            return candidate
    return ""


def _path_qualifications(
    value: str,
    confirmations: Sequence[AnchorConfirmation],
) -> tuple[AnchorConfirmation, ...]:
    normalized_value = str(value).strip().casefold()
    if not normalized_value:
        return ()
    return tuple(
        confirmation
        for confirmation in confirmations
        if confirmation.kind == "path"
        and Path(str(confirmation.value).replace("\\", "/")).stem.casefold() == normalized_value
    )


def _nodes_in_confirmed_paths(
    nodes: Sequence[Mapping[str, Any]],
    confirmations: Sequence[AnchorConfirmation],
) -> tuple[dict[str, Any], ...]:
    confirmed_paths = {
        str(match.get("path") or "").replace("\\", "/").casefold()
        for confirmation in confirmations
        if confirmation.kind == "path" and confirmation.confirmed_in_repository
        for match in confirmation.matches
        if str(match.get("path") or "")
    }
    if not confirmed_paths:
        return ()
    return tuple(
        dict(node)
        for node in nodes
        if str(node.get("path") or "").replace("\\", "/").casefold() in confirmed_paths
    )


def _source_authored_nodes(nodes: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        dict(node)
        for node in nodes
        if file_role(str(node.get("path") or "")) != "baseline_or_generated"
    ]


def _anchor_is_visible(anchor: str, text: str) -> bool:
    normalized_anchor = " ".join(str(anchor).split()).casefold()
    normalized_text = " ".join(str(text).split()).casefold()
    return bool(normalized_anchor and normalized_anchor in normalized_text)


def _is_visible_direct_target(
    *,
    relationship: str,
    target_symbol: str,
    seed_candidate: GroundedCandidate | None,
) -> bool:
    return bool(
        relationship in PRODUCTIVE_RECOVERY_RELATIONSHIPS
        and seed_candidate is not None
        and target_symbol
        and _anchor_is_visible(target_symbol.split(".")[-1], seed_candidate.text)
    )


def _direct_target_context_score(
    obligation_terms: set[str],
    seed_text: str,
    target_symbol: str,
) -> float:
    simple_symbol = target_symbol.split(".")[-1].casefold()
    if not simple_symbol:
        return 0.0
    lines = seed_text.splitlines()
    contexts: list[str] = []
    for index, line in enumerate(lines):
        if simple_symbol not in line.casefold():
            continue
        contexts.append("\n".join(lines[max(0, index - 1) : min(len(lines), index + 2)]))
    return max((_overlap_score(obligation_terms, context) for context in contexts), default=0.0)


def _exact_index_anchor_matches(qdrant_tool: Any, anchor: str) -> tuple[dict[str, Any], ...]:
    return _anchor_index_distribution(qdrant_tool, anchor)["matches"]


def _is_informative_exact_prompt_anchor(confirmation: AnchorConfirmation) -> bool:
    if confirmation.kind not in {"error", "literal"} or confirmation.match_type not in {
        "exact_index_text",
        "strong_anchor_search",
    }:
        return False
    value = confirmation.value.strip()
    return len(value) >= 12 and len(_terms(value)) >= 3


def _normalized_token_sequence(value: str) -> tuple[str, ...]:
    expanded = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", str(value)).replace("_", " ")
    return tuple(
        token.casefold()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9]*", expanded)
        if len(token) >= 3
    )


def _longest_contiguous_anchor_match(anchor: str, text: str) -> int:
    anchor_tokens = _normalized_token_sequence(anchor)
    text_tokens = _normalized_token_sequence(text)
    best = 0
    for anchor_index in range(len(anchor_tokens)):
        for text_index in range(len(text_tokens)):
            length = 0
            while (
                anchor_index + length < len(anchor_tokens)
                and text_index + length < len(text_tokens)
                and anchor_tokens[anchor_index + length] == text_tokens[text_index + length]
            ):
                length += 1
            best = max(best, length)
    return best


def _dominant_error_anchor_result(
    anchor: str,
    results: Sequence[Mapping[str, Any]],
) -> dict[str, Any] | None:
    candidates = [
        dict(item)
        for item in results
        if str(item.get("path") or "")
        and file_role(str(item.get("path") or "")) != "baseline_or_generated"
        and _longest_contiguous_anchor_match(anchor, str(item.get("text") or "")) >= 3
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)
    top_score = float(candidates[0].get("score") or 0.0)
    if top_score < 0.15:
        return None
    if len(candidates) > 1 and float(candidates[1].get("score") or 0.0) * 1.15 >= top_score:
        return None
    return candidates[0]


def _exact_prompt_seed_results(
    confirmations: Sequence[AnchorConfirmation],
    obligations: Sequence[EvidenceObligation],
) -> dict[str, tuple[dict[str, Any], ...]]:
    by_obligation: dict[str, list[dict[str, Any]]] = {obligation.id: [] for obligation in obligations}
    for confirmation in confirmations:
        if not _is_informative_exact_prompt_anchor(confirmation):
            continue
        anchor_terms = _distinctive_terms(confirmation.value)
        matching_obligations = [
            obligation
            for obligation in obligations
            if confirmation.value in obligation.anchor_refs
            or _overlap_score(_distinctive_terms(obligation.description), confirmation.value) > 0
        ]
        if not matching_obligations:
            continue
        for obligation in matching_obligations:
            for match in confirmation.matches:
                path = str(match.get("path") or "")
                line_start = int(match.get("line_start") or 0)
                line_end = int(match.get("line_end") or line_start)
                text = str(match.get("text") or "")
                if not path or line_start <= 0 or not text:
                    continue
                by_obligation[obligation.id].append(
                    {
                        "path": path,
                        "line_start": line_start,
                        "line_end": line_end,
                        "text": text,
                        "score": 1.0,
                        "matched_terms": tuple(sorted(anchor_terms)),
                        "exact_prompt_anchor": confirmation.value,
                    }
                )
    return {
        obligation_id: tuple(
            {
                (item["path"], item["line_start"], item["line_end"]): item
                for item in values
            }.values()
        )
        for obligation_id, values in by_obligation.items()
    }


def _anchor_index_distribution(qdrant_tool: Any, anchor: str) -> dict[str, Any]:
    index = getattr(qdrant_tool, "index", None)
    documents = getattr(index, "documents", ())
    matches: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int]] = set()
    paths: set[str] = set()
    chunk_count = 0
    for document in documents:
        chunk = getattr(document, "chunk", None)
        if chunk is None or not _anchor_is_visible(anchor, str(getattr(chunk, "text", ""))):
            continue
        chunk_count += 1
        paths.add(str(getattr(chunk, "path", "")))
        key = (
            str(getattr(chunk, "path", "")),
            int(getattr(chunk, "line_start", 0) or 0),
            int(getattr(chunk, "line_end", 0) or 0),
        )
        if key in seen:
            continue
        seen.add(key)
        if len(matches) < 4:
            matches.append(
                {
                    "path": key[0],
                    "line_start": key[1],
                    "line_end": key[2],
                    "text": str(getattr(chunk, "text", "")),
                }
            )
    return {
        "chunk_count": chunk_count,
        "path_count": len(paths),
        "matches": tuple(matches),
    }


def _anchor_is_repository_common(distribution: Mapping[str, Any]) -> bool:
    return int(distribution.get("path_count") or 0) > MAX_STANDALONE_ANCHOR_PATHS


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


def _qualified_reference_expansion(
    ctx: WorkspaceRetrievalContext,
    tool: Any,
    *,
    source_paths: Sequence[str],
    obligation: EvidenceObligation,
    concepts: Sequence[str],
    round_index: int,
    source_candidates: Sequence[GroundedCandidate],
) -> tuple[GroundedCandidate, ...]:
    request = ToolRequest(
        tool_name="structural_qualified_references",
        arguments={"paths": list(source_paths), "limit": 40},
        reason=f"Resolve exact owner-qualified calls from candidate files for evidence obligation {obligation.id}.",
    )
    observation = tool.run(request)
    ctx.trace.record_tool(request, observation, round_index=round_index)
    if observation.status != "ok":
        raise RuntimeError(f"CodeGraph qualified-reference expansion failed for {obligation.id}.")

    obligation_terms = _distinctive_terms(" ".join((obligation.description, *concepts)))
    source_candidate_paths = {candidate.path for candidate in source_candidates if candidate.path}
    candidates: list[GroundedCandidate] = []
    for raw_node in observation.payload.get("nodes", ()):
        if not isinstance(raw_node, Mapping):
            continue
        node = dict(raw_node)
        relevance, productive = _qualified_reference_priority(
            node,
            obligation_terms=obligation_terms,
            source_path_count=len(source_paths),
        )
        if not productive:
            continue
        source_paths = tuple(
            sorted(
                path
                for path in (str(item) for item in node.get("source_paths", ()))
                if path in source_candidate_paths
            )
        )
        if not source_paths:
            continue
        candidate = _candidate_from_node(
            ctx,
            node,
            score=relevance,
            origin="graph_owner_qualified_reference",
            relationship="qualified_reference",
            obligation_id=obligation.id,
            source_paths=source_paths,
        )
        if candidate is None:
            continue
        covered_concepts, missing_concepts = _concept_coverage(concepts, candidate.text)
        candidates.append(
            replace(
                candidate,
                covered_concepts=covered_concepts,
                missing_concepts=missing_concepts,
            )
        )
    return tuple(_dedupe_candidates(candidates))


def _qualified_reference_priority(
    node: Mapping[str, Any],
    *,
    obligation_terms: set[str],
    source_path_count: int,
) -> tuple[float, bool]:
    relevance = _overlap_score(obligation_terms, _node_text(node))
    source_count = int(node.get("source_count") or 0)
    member_terms = _distinctive_terms(str(node.get("name") or ""))
    qualifier_reference_count = int(node.get("qualifier_reference_count") or 0)
    utility_fanout = qualifier_reference_count > max(12, source_path_count * 8)
    specific_call_target = source_count >= 1 and len(member_terms) >= 2 and not utility_fanout
    if utility_fanout and relevance < 0.25:
        return relevance, False
    return relevance, relevance > 0 or specific_call_target


def _focused_seed_ids(
    progress: ObligationProgress,
    seed_obligations: Mapping[str, set[str]],
    obligation_id: str,
    *,
    limit: int = MAX_FOCUSED_SEEDS,
) -> tuple[str, ...]:
    ordered: list[str] = []
    for candidate in sorted(
        (*progress.candidates, *progress.discovery_hints),
        key=lambda item: (-item.score, item.path, item.line_start),
    ):
        if (
            candidate.node_id
            and obligation_id in seed_obligations.get(candidate.node_id, set())
            and candidate.node_id not in ordered
        ):
            ordered.append(candidate.node_id)
            if len(ordered) >= limit:
                return tuple(ordered)
    for node_id, obligation_ids in seed_obligations.items():
        if obligation_id in obligation_ids and node_id not in ordered:
            ordered.append(node_id)
            if len(ordered) >= limit:
                break
    return tuple(ordered)


def _dependency_seed_candidates(
    progress: Mapping[str, ObligationProgress],
    obligation: EvidenceObligation,
) -> tuple[GroundedCandidate, ...]:
    candidates: list[GroundedCandidate] = []
    for dependency_id in obligation.depends_on:
        dependency = progress.get(dependency_id)
        if dependency is None:
            continue
        candidates.extend(
            sorted(
                (*dependency.candidates, *dependency.discovery_hints),
                key=lambda item: (-item.score, item.path, item.line_start),
            )[:2]
        )
    return tuple(_dedupe_candidates(candidates))


def _focused_frontier_paths(
    edges: Sequence[Mapping[str, Any]],
    *,
    seed_ids: Sequence[str],
    limit: int = MAX_FOCUSED_FRONTIER_FILES,
) -> tuple[str, ...]:
    seeds = set(seed_ids)
    seed_paths: set[str] = set()
    for edge in edges:
        for endpoint in (edge.get("source"), edge.get("target")):
            if isinstance(endpoint, Mapping) and str(endpoint.get("id") or "") in seeds:
                path = str(endpoint.get("path") or "")
                if path:
                    seed_paths.add(path)

    weights = {"calls": 4, "imports": 4, "instantiates": 3, "references": 2}
    scores: dict[str, int] = {}
    for edge in edges:
        source = edge.get("source") if isinstance(edge.get("source"), Mapping) else {}
        target = edge.get("target") if isinstance(edge.get("target"), Mapping) else {}
        source_id = str(source.get("id") or "")
        target_id = str(target.get("id") or "")
        if source_id in seeds:
            path = str(target.get("path") or "")
        elif target_id in seeds:
            path = str(source.get("path") or "")
        else:
            continue
        if not path or path in seed_paths:
            continue
        scores[path] = scores.get(path, 0) + weights.get(str(edge.get("kind") or ""), 1)
    return tuple(path for path, _score in sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:limit])


def _dedupe_edges(edges: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[tuple[str, str, str], dict[str, Any]] = {}
    for edge in edges:
        source = edge.get("source") if isinstance(edge.get("source"), Mapping) else {}
        target = edge.get("target") if isinstance(edge.get("target"), Mapping) else {}
        key = (
            str(source.get("id") or ""),
            str(target.get("id") or ""),
            str(edge.get("kind") or ""),
        )
        if key[0] and key[1]:
            unique.setdefault(key, dict(edge))
    return list(unique.values())


def _transition_from_edges(
    source: ObligationProgress,
    target: ObligationProgress,
    edge_index: Mapping[frozenset[str], Sequence[Mapping[str, Any]]],
) -> dict[str, Any] | None:
    source_ids = {item.node_id for item in source.candidates if item.node_id}
    target_ids = {item.node_id for item in target.candidates if item.node_id}
    for source_id in source_ids:
        for target_id in target_ids:
            if source_id == target_id:
                continue
            edges = edge_index.get(frozenset((source_id, target_id)), ())
            if edges:
                return {
                    "from": source.obligation.id,
                    "status": "supported",
                    "relationship": str(edges[0].get("kind") or "graph_edge"),
                }
    return None


def _transition_from_focused_bridge(
    source: ObligationProgress,
    target: ObligationProgress,
    bridge_result: Mapping[str, Any],
) -> dict[str, Any]:
    endpoint_id = str(bridge_result.get("endpoint_node_id") or "")
    discovered_ids = {str(value) for value in bridge_result.get("discovered_node_ids", ()) if value}
    selected_source_ids = {item.node_id for item in source.candidates if item.node_id}
    selected_target_ids = {item.node_id for item in target.candidates if item.node_id}
    selected_consumers = sorted((selected_target_ids & discovered_ids) - {endpoint_id})
    if endpoint_id in selected_source_ids and selected_consumers:
        return {
            "from": source.obligation.id,
            "status": "semantic_handoff",
            "relationship": "focused_semantic_bridge",
            "endpoint_node_id": endpoint_id,
            "consumer_node_ids": selected_consumers,
        }
    return {
        "from": source.obligation.id,
        "status": "unresolved",
        "reason": "focused_semantic_bridge_consumer_not_selected",
    }


def _transition_from_shared_anchors(
    source: ObligationProgress,
    target: ObligationProgress,
    confirmed_anchors: set[str],
) -> dict[str, Any] | None:
    source_ids = {item.node_id for item in source.candidates if item.node_id}
    target_ids = {item.node_id for item in target.candidates if item.node_id}
    if source_ids and source_ids == target_ids:
        return None
    source_text = "\n".join(item.text for item in source.candidates)
    target_text = "\n".join(item.text for item in target.candidates)
    shared = [
        anchor
        for anchor in sorted(confirmed_anchors, key=lambda value: (-len(value), value.casefold()))
        if _transition_anchor_visible(anchor, source_text) and _transition_anchor_visible(anchor, target_text)
    ]
    if len(shared) < 2 or not any(len(anchor) >= 6 for anchor in shared):
        return None
    return {
        "from": source.obligation.id,
        "status": "semantic_handoff",
        "relationship": "shared_confirmed_anchors",
        "supporting_anchors": shared[:6],
    }


def _transition_anchor_visible(anchor: str, text: str) -> bool:
    value = str(anchor).strip()
    if not value or "/" in value or "http://" in value.casefold() or "https://" in value.casefold():
        return False
    if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$.-]*", value):
        return re.search(rf"(?<![A-Za-z0-9_$]){re.escape(value)}(?![A-Za-z0-9_$])", text, re.IGNORECASE) is not None
    return " ".join(value.split()).casefold() in " ".join(text.split()).casefold()


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
    if source_path == target_path and source.candidates[0].node_id == target.candidates[0].node_id:
        return (
            {
                "from": source.obligation.id,
                "status": "unresolved",
                "reason": "same_evidence_does_not_establish_forward_progress",
            },
            0,
        )
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
    resource_reference = resource_reference_between_files(ctx.config.workspace_root, source_path, target_path)
    if resource_reference is not None:
        return (
            {
                "from": source.obligation.id,
                "status": "supported",
                "relationship": "resource_reference",
                "literal": str(resource_reference.get("literal") or ""),
            },
            1,
        )
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


def _obligation_query(
    description: str,
    unresolved_symbols: Sequence[str] = (),
    *,
    anchors: Sequence[str] = (),
    search_terms: Sequence[str] = (),
) -> str:
    obligation_terms = _distinctive_terms(description)
    relevant_symbols = [symbol for symbol in unresolved_symbols if obligation_terms & _terms(symbol)]
    relevant_terms = [term for term in search_terms if obligation_terms & _terms(term)]
    return " ".join(ordered_unique((description.strip(), *anchors, *relevant_symbols, *relevant_terms))).strip()


def _obligation_stage_query_text(obligation: EvidenceObligation) -> str:
    """Keep the repository-stage retrieval strand stable across LLM decompositions."""
    stage_purposes = tuple(
        INTENT_STAGE_PURPOSES[stage_id]
        for stage_id in obligation.stage_ids
        if stage_id in INTENT_STAGE_PURPOSES
    )
    stage_retrieval_terms = tuple(
        term
        for stage_id in obligation.stage_ids
        for term in INTENT_STAGE_RETRIEVAL_TERMS.get(stage_id, ())
    )
    return " ".join((*stage_purposes, *stage_retrieval_terms, obligation.description)).strip()


def _semantic_result_trace_item(result: Mapping[str, Any], *, rank: int) -> dict[str, Any]:
    """Emit metadata sufficient to reconcile a raw Qdrant result with later candidates."""
    return {
        "rank": rank,
        "path": str(result.get("path") or "").replace("\\", "/"),
        "line_start": int(result.get("line_start") or 0),
        "line_end": int(result.get("line_end") or result.get("line_start") or 0),
        "score": round(float(result.get("score") or 0.0), 4),
        "matched_terms": [str(value) for value in result.get("matched_terms", ()) if value],
    }


def _candidate_trace_item(
    candidate: GroundedCandidate,
    *,
    candidate_id: str | None = None,
) -> dict[str, Any]:
    """Serialize decision-relevant candidate state without duplicating source text in trace logs."""
    return {
        "candidate_id": candidate_id or _global_candidate_id(candidate),
        "path": candidate.path,
        "line_start": candidate.line_start,
        "line_end": candidate.line_end,
        "node_id": candidate.node_id,
        "symbol": candidate.symbol,
        "score": round(candidate.score, 4),
        "base_score": round(candidate.base_score or candidate.score, 4),
        "origin": candidate.origin,
        "provenance_origins": list(candidate.provenance_origins or (candidate.origin,)),
        "obligation_ids": list(candidate.obligation_ids),
        "source_paths": list(candidate.source_paths),
        "relationship_types": list(candidate.relationship_types or ((candidate.relationship,) if candidate.relationship else ())),
        "covered_concepts": list(candidate.covered_concepts),
        "missing_concepts": list(candidate.missing_concepts),
        "facts": candidate.facts.to_dict(),
    }


def _semantic_path_signals(
    semantic_by_obligation: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    rank_limit: int = SEMANTIC_SIGNAL_RANK_LIMIT,
) -> dict[str, dict[str, float | int]]:
    ranks_by_path: dict[str, list[int]] = {}
    for results in semantic_by_obligation.values():
        seen_in_obligation: set[str] = set()
        for rank, item in enumerate(results, start=1):
            if rank > rank_limit:
                break
            path = str(item.get("path") or "").replace("\\", "/")
            if not path or file_role(path) == "baseline_or_generated" or path in seen_in_obligation:
                continue
            ranks_by_path.setdefault(path, []).append(rank)
            seen_in_obligation.add(path)

    signals: dict[str, dict[str, float | int]] = {}
    for path, ranks in ranks_by_path.items():
        best_rank = min(ranks)
        recurrence = len(ranks)
        rank_quality = float(rank_limit - best_rank + 1) / float(max(1, rank_limit))
        exceptional_rank_bonus = float(max(0, 3 - best_rank) * 2)
        signals[path] = {
            "recurrence": recurrence,
            "best_rank": best_rank,
            "average_rank": sum(ranks) / float(recurrence),
            "rank_quality": rank_quality,
            "direct_score": (float(recurrence) * 4.0) + (rank_quality * 2.0) + exceptional_rank_bonus,
        }
    return signals


def _semantic_root_file_neighbors(
    ctx: WorkspaceRetrievalContext,
    tool: Any,
    semantic_by_obligation: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    rank_limit: int = SEMANTIC_SIGNAL_RANK_LIMIT,
) -> tuple[tuple[dict[str, Any], ...], int]:
    signals = _semantic_path_signals(semantic_by_obligation, rank_limit=rank_limit)
    roots = sorted(
        (
            path
            for path, signal in signals.items()
            if int(signal["recurrence"]) >= 2 or int(signal["best_rank"]) <= 2
        ),
        key=lambda path: (
            -float(signals[path]["direct_score"]),
            -int(signals[path]["recurrence"]),
            int(signals[path]["best_rank"]),
            path,
        ),
    )[:MAX_EXPLANATION_ROOTS]
    root_set = set(roots)
    root_candidates = {
        path
        for path, signal in signals.items()
        if int(signal["recurrence"]) >= 2 or int(signal["best_rank"]) <= 2
    }
    ctx.trace.record(
        "semantic_explanation_root_decisions",
        {
            "rank_limit": rank_limit,
            "max_roots": MAX_EXPLANATION_ROOTS,
            "paths": [
                {
                    "path": path,
                    **dict(signal),
                    "decision": (
                        "selected_explanation_root"
                        if path in root_set
                        else (
                            "rejected_explanation_root_cap"
                            if path in root_candidates
                            else "rejected_insufficient_recurrence_and_rank"
                        )
                    ),
                }
                for path, signal in sorted(
                    signals.items(),
                    key=lambda item: (
                        -float(item[1]["direct_score"]),
                        -int(item[1]["recurrence"]),
                        int(item[1]["best_rank"]),
                        item[0],
                    ),
                )
            ],
        },
    )
    combined: dict[str, dict[str, Any]] = {}
    tool_calls = 0
    for root in roots:
        request = ToolRequest(
            tool_name="structural_file_neighbors",
            arguments={"paths": [root], "limit": MAX_NEIGHBORS_PER_ROOT},
            reason=f"Discover productive file connections from semantic explanation root {root}.",
        )
        observation = tool.run(request)
        ctx.trace.record_tool(request, observation, round_index=2)
        tool_calls += 1
        if observation.status != "ok":
            raise RuntimeError(f"CodeGraph promotion-neighbor expansion failed for {root}.")
        for raw in observation.payload.get("neighbors", ()):
            if not isinstance(raw, Mapping):
                continue
            path = str(raw.get("path") or "").replace("\\", "/")
            relationships = tuple(
                relationship
                for relationship in ordered_unique(tuple(str(value) for value in raw.get("edge_kinds", ()) if value))
                if relationship in PRODUCTIVE_RECOVERY_RELATIONSHIPS
            )
            if not path or path == root or not relationships or file_role(path) == "baseline_or_generated":
                continue
            entry = combined.setdefault(
                path,
                {
                    "path": path,
                    "edge_count": 0,
                    "edge_kinds": [],
                    "source_paths": [],
                    "root_connections": [],
                },
            )
            entry["edge_count"] = int(entry["edge_count"]) + max(1, int(raw.get("edge_count") or 0))
            entry["edge_kinds"] = list(ordered_unique((*entry["edge_kinds"], *relationships)))
            entry["source_paths"] = list(ordered_unique((*entry["source_paths"], root)))
            entry["root_connections"].append(
                {
                    "path": root,
                    "edge_count": max(1, int(raw.get("edge_count") or 0)),
                    "score": max(0.0, float(raw.get("score") or 0.0)),
                }
            )
    return (
        tuple(
            sorted(
                combined.values(),
                key=lambda item: (-int(item["edge_count"]), str(item["path"])),
            )
        ),
        tool_calls,
    )


def _ground_semantic_root_neighbors(
    ctx: WorkspaceRetrievalContext,
    *,
    states: Sequence[ObligationProgress],
    semantic_by_obligation: Mapping[str, Sequence[Mapping[str, Any]]],
    concepts_by_obligation: Mapping[str, Sequence[str]],
    file_neighbors: Sequence[Mapping[str, Any]],
    qdrant_tool: Any,
    resolve_ranges_tool: Any,
) -> int:
    state_by_id = {state.obligation.id: state for state in states}
    neighbor_by_path = {
        str(item.get("path") or "").replace("\\", "/"): dict(item)
        for item in file_neighbors
        if str(item.get("path") or "")
    }
    root_connections: dict[str, list[tuple[int, float, str]]] = {}
    for path, item in neighbor_by_path.items():
        for connection in item.get("root_connections", ()):
            root = str(connection.get("path") or "").replace("\\", "/")
            if root:
                root_connections.setdefault(root, []).append(
                    (
                        int(connection.get("edge_count") or 0),
                        float(connection.get("score") or 0.0),
                        path,
                    )
                )

    selected_by_root = {
        root: tuple(
            path
            for _edges, _score, path in sorted(values, key=lambda value: (-value[0], -value[1], value[2]))[
                :MAX_LOCALIZED_NEIGHBORS_PER_ROOT
            ]
        )
        for root, values in root_connections.items()
    }
    selected_path_pairs = {
        (root, path)
        for root, paths in selected_by_root.items()
        for path in paths
    }
    ctx.trace.record(
        "semantic_root_neighbor_decisions",
        {
            "max_neighbors_localized_per_root": MAX_LOCALIZED_NEIGHBORS_PER_ROOT,
            "roots": [
                {
                    "root_path": root,
                    "neighbors": [
                        {
                            "path": path,
                            "edge_count": edge_count,
                            "graph_score": round(score, 4),
                            "decision": (
                                "selected_for_localization"
                                if (root, path) in selected_path_pairs
                                else "rejected_neighbor_rank_cap"
                            ),
                        }
                        for edge_count, score, path in sorted(
                            values,
                            key=lambda value: (-value[0], -value[1], value[2]),
                        )
                    ],
                }
                for root, values in sorted(root_connections.items())
            ],
        },
    )
    obligations_by_root = {
        root: tuple(
            state.obligation.id
            for state in states
            if any(
                str(item.get("path") or "").replace("\\", "/") == root
                for item in semantic_by_obligation.get(state.obligation.id, ())
            )
        )
        for root in selected_by_root
    }
    obligations_by_path: dict[str, set[str]] = {}
    for root, paths in selected_by_root.items():
        for path in paths:
            obligations_by_path.setdefault(path, set()).update(obligations_by_root.get(root, ()))

    localized_by_path: dict[str, dict[str, Any]] = {}
    localization_decisions: list[dict[str, Any]] = []
    tool_calls = 0
    for root, paths in selected_by_root.items():
        missing_paths = [path for path in paths if path not in localized_by_path]
        obligation_ids = obligations_by_root.get(root, ())
        if not missing_paths or not obligation_ids:
            continue
        request = ToolRequest(
            tool_name="qdrant_hybrid_search",
            arguments={
                "query": " ".join(state_by_id[value].obligation.description for value in obligation_ids),
                "limit": len(missing_paths),
                "max_per_path": 1,
                "source_category": "source_code",
                "file_role": "any",
                "paths": missing_paths,
                "preferred_paths": [neighbor_by_path[path] for path in missing_paths],
            },
            reason=f"Localize exact graph neighbors discovered from semantic root {root}.",
        )
        observation = qdrant_tool.run(request)
        ctx.trace.record_tool(request, observation, round_index=2)
        tool_calls += 1
        if observation.status != "ok":
            raise RuntimeError(f"Semantic localization failed for graph neighbors of {root}.")
        for item in observation.payload.get("results", ()):
            if isinstance(item, Mapping) and str(item.get("path") or ""):
                localized_by_path.setdefault(str(item.get("path") or "").replace("\\", "/"), dict(item))
        returned_paths = {
            str(item.get("path") or "").replace("\\", "/")
            for item in observation.payload.get("results", ())
            if isinstance(item, Mapping) and str(item.get("path") or "")
        }
        for path in missing_paths:
            if path not in returned_paths:
                localization_decisions.append(
                    {
                        "root_path": root,
                        "path": path,
                        "obligation_ids": list(obligation_ids),
                        "decision": "rejected_no_qdrant_result_in_requested_neighbor_path",
                    }
                )

    results = list(localized_by_path.values())

    ranges = [
        {
            "file": str(item.get("path") or ""),
            "line_start": int(item.get("line_start") or 0),
            "line_end": int(item.get("line_end") or item.get("line_start") or 0),
        }
        for item in results
        if str(item.get("path") or "") and int(item.get("line_start") or 0) > 0
    ]
    nodes_by_range: dict[tuple[str, int, int], list[dict[str, Any]]] = {}
    if ranges:
        resolve_request = ToolRequest(
            tool_name="structural_resolve_ranges",
            arguments={"ranges": ranges},
            reason="Ground semantic-root graph-neighbor ranges to exact CodeGraph nodes.",
        )
        resolved = resolve_ranges_tool.run(resolve_request)
        ctx.trace.record_tool(resolve_request, resolved, round_index=2)
        tool_calls += 1
        if resolved.status != "ok":
            raise RuntimeError("CodeGraph localization failed for semantic-root graph neighbors.")
        for item in resolved.payload.get("results", ()):
            if not isinstance(item, Mapping):
                continue
            key = (
                str(item.get("file") or ""),
                int(item.get("line_start") or 0),
                int(item.get("line_end") or item.get("line_start") or 0),
            )
            nodes_by_range[key] = _best_overlapping_nodes(
                tuple(dict(node) for node in item.get("nodes", ()) if isinstance(node, Mapping)),
                line_start=key[1],
                line_end=key[2],
            )

    for path, obligation_ids in obligations_by_path.items():
        neighbor = neighbor_by_path.get(path, {})
        result = localized_by_path.get(path)
        if result is None:
            continue
        for obligation_id in obligation_ids:
            target = state_by_id[obligation_id]
            before = {_candidate_ledger_key(candidate) for candidate in target.candidates}
            _append_semantic_candidates(
                target,
                results=(result,),
                nodes_by_range=nodes_by_range,
                concepts=concepts_by_obligation[obligation_id],
                origin="graph_connected_file",
                relationship="graph_file_neighbor",
                path_provenance=(neighbor,),
                workspace_root=ctx.config.workspace_root,
                allow_without_obligation_overlap=True,
            )
            appended = [
                candidate
                for candidate in target.candidates
                if _candidate_ledger_key(candidate) not in before and candidate.path == path
            ]
            localization_decisions.append(
                {
                    "path": path,
                    "obligation_ids": [obligation_id],
                    "decision": (
                        "localized_to_exact_candidate"
                        if appended else "rejected_no_exact_candidate_after_range_resolution"
                    ),
                    "candidate_ids": [_global_candidate_id(candidate) for candidate in appended],
                }
            )
    ctx.trace.record(
        "semantic_root_neighbors_localized",
        {
            "roots": [
                {
                    "path": root,
                    "obligation_ids": list(obligations_by_root.get(root, ())),
                    "neighbor_paths": list(paths),
                }
                for root, paths in selected_by_root.items()
            ],
            "localized_paths": sorted(localized_by_path),
            "localization_decisions": localization_decisions,
            "tool_calls": tool_calls,
        },
    )
    return tool_calls


def _source_category_for_role(role: EvidenceRole) -> str:
    return "documentation" if role == EvidenceRole.DOCUMENTATION else "source_code"


def _confirmed_obligation_paths(
    obligation: EvidenceObligation,
    confirmations: Sequence[AnchorConfirmation],
) -> tuple[str, ...]:
    referenced_paths = {
        str(match.get("path") or "")
        for confirmation in confirmations
        if confirmation.kind == "path"
        and confirmation.confirmed_in_repository
        and confirmation.value in obligation.anchor_refs
        for match in confirmation.matches
        if str(match.get("path") or "")
        and (
            obligation.evidence_role == EvidenceRole.ANY
            or file_role(str(match.get("path") or "")) == obligation.evidence_role.value
        )
    }
    return tuple(sorted(referenced_paths))


def _candidate_conflicts_with_missing_path(
    candidate: GroundedCandidate,
    obligation: EvidenceObligation,
    confirmations: Sequence[AnchorConfirmation],
) -> bool:
    candidate_name = Path(candidate.path).name.casefold()
    if any(
        confirmation.kind == "path"
        and not confirmation.confirmed_in_repository
        and confirmation.value in obligation.anchor_refs
        and Path(str(confirmation.value).replace("\\", "/")).name.casefold() == candidate_name
        for confirmation in confirmations
    ):
        return True

    candidate_symbol = str(candidate.symbol).split("::", 1)[0].strip().casefold()
    for confirmation in confirmations:
        if (
            confirmation.kind != "symbol"
            or not confirmation.match_type.startswith("path_qualified")
            or confirmation.value not in obligation.anchor_refs
            or confirmation.value.casefold() != candidate_symbol
        ):
            continue
        allowed_paths = {
            str(match.get("path") or "").replace("\\", "/").casefold()
            for match in confirmation.matches
            if str(match.get("path") or "")
        }
        if candidate.path.replace("\\", "/").casefold() not in allowed_paths:
            return True
    return False


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
    expanded = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", str(value)).replace("_", " ")
    return {
        normalized
        for token in re.findall(r"[A-Za-z][A-Za-z0-9]*", expanded)
        if len(normalized := _term_root(token.casefold())) >= 3
        and normalized not in {"the", "and", "for", "from", "that", "this", "with", "into", "how", "what"}
    }


def _term_root(token: str) -> str:
    if token.endswith("ies") and len(token) > 5:
        return token[:-3] + "y"
    if token.endswith("ing") and len(token) > 6:
        return token[:-3]
    if token.endswith("ed") and len(token) > 5:
        return token[:-2]
    if token.endswith("es") and len(token) > 5:
        return token[:-2]
    if token.endswith("s") and not token.endswith("ss") and len(token) > 4:
        return token[:-1]
    return token


_OBLIGATION_INSTRUCTION_TERMS = {
    "actual",
    "behavior",
    "change",
    "code",
    "compare",
    "determine",
    "error",
    "establish",
    "expected",
    "explain",
    "file",
    "identify",
    "index",
    "interface",
    "locate",
    "modify",
    "not",
    "path",
    "paths",
    "project",
    "reported",
    "repository",
    "result",
    "scenario",
    "source",
    "src",
    "state",
    "supported",
    "trace",
    "type",
    "use",
    "when",
    "without",
}


def _distinctive_terms(value: str) -> set[str]:
    return _terms(value) - _OBLIGATION_INSTRUCTION_TERMS


def _semantic_support_score(expected: set[str], result: Mapping[str, Any]) -> float:
    matched = _terms(" ".join(str(item) for item in result.get("matched_terms", ()))) & expected
    required_matches = 1 if len(expected) < 4 else 2
    if len(matched) < required_matches:
        return 0.0
    return float(len(matched)) / float(max(1, min(len(expected), 8)))


_SOURCE_CALL = re.compile(r"(?<![.\w$])([A-Za-z_$][\w$]{2,})\s*\(")
_SOURCE_DEFAULT_FACTORY = re.compile(
    r"\b([A-Za-z_$][\w$]*)\s*:\s*\1\s*\|\|\s*((?:create|build)[A-Za-z_$][\w$]{2,})\b"
)
_SOURCE_RETURN_NAME = re.compile(r"\breturn\s+([A-Za-z_$][\w$]*)\b")
_SOURCE_FIELD_WRITE = re.compile(r"\b[A-Za-z_$][\w$]*\.([A-Za-z_$][\w$]*)\s*=(?!=|>)")
_SOURCE_FIELD_READ = re.compile(r"\b[A-Za-z_$][\w$]*\.([A-Za-z_$][\w$]*)\b")


def _candidate_facts(
    text: str,
    *,
    semantic_discoveries: Sequence[SemanticDiscovery] = (),
    full_range: Sequence[int] = (),
    primary_anchor: Sequence[int] = (),
    anchor_reliability_tier: int = 0,
    anchor_decision_code: str = "",
    localization_adapter: str = "",
) -> CandidateFacts:
    """Extract bounded syntax facts from source already localized for a node."""
    calls = ordered_unique(tuple(_SOURCE_CALL.findall(text)))
    defaults = tuple(dict.fromkeys(_SOURCE_DEFAULT_FACTORY.findall(text)))
    writes = ordered_unique(tuple(_SOURCE_FIELD_WRITE.findall(text)))
    reads = tuple(field for field in ordered_unique(tuple(_SOURCE_FIELD_READ.findall(text))) if field not in set(writes))
    return CandidateFacts(
        semantic_discoveries=tuple(semantic_discoveries),
        visible_calls=calls,
        callable_defaults=defaults,
        returned_names=ordered_unique(tuple(_SOURCE_RETURN_NAME.findall(text))),
        written_fields=writes,
        read_fields=reads,
        full_range=tuple(int(value) for value in full_range[:2]),
        primary_anchor=tuple(int(value) for value in primary_anchor[:2]),
        anchor_reliability_tier=anchor_reliability_tier,
        anchor_decision_code=anchor_decision_code,
        localization_adapter=localization_adapter,
    )


def _relevant_search_concepts(description: str, search_terms: Sequence[str]) -> tuple[str, ...]:
    expected = _distinctive_terms(description)
    return ordered_unique(tuple(term for term in search_terms if expected & _terms(term)))


def _concept_coverage(concepts: Sequence[str], text: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    text_terms = _terms(text)
    covered: list[str] = []
    missing: list[str] = []
    for concept in concepts:
        concept_terms = _terms(concept)
        required_matches = max(1, (len(concept_terms) + 1) // 2)
        target = covered if len(concept_terms & text_terms) >= required_matches else missing
        target.append(concept)
    return tuple(covered), tuple(missing)


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
    obligation_id: str = "",
    source_paths: Sequence[str] = (),
) -> GroundedCandidate | None:
    node_kind = str(node.get("kind") or "")
    if node_kind in {"file", "import"}:
        ctx.trace.record(
            "raw_file_node_candidate_rejected",
            {
                "decision_code": "rejected_non_executable_graph_node",
                "node_id": str(node.get("id") or ""),
                "node_kind": node_kind,
                "path": str(node.get("path") or "").replace("\\", "/"),
                "origin": origin,
                "relationship": relationship,
                "obligation_id": obligation_id,
            },
        )
        return None
    path = str(node.get("path") or "").replace("\\", "/")
    line_start = max(1, int(node.get("line_start") or 1))
    line_end = max(line_start, int(node.get("line_end") or line_start))
    localized = bool(node.get("localization_adapter"))
    if not localized and line_end - line_start > 100:
        line_end = line_start + 100
    source = Path(ctx.config.workspace_root) / path
    if not path or file_role(path) == "baseline_or_generated" or not source.is_file():
        return None
    lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
    line_end = min(line_end, len(lines))
    actual_role = file_role(path)
    text = "\n".join(lines[line_start - 1 : line_end])
    full_line_start = max(1, int(node.get("full_line_start") or line_start))
    full_line_end = min(len(lines), max(full_line_start, int(node.get("full_line_end") or line_end)))
    fact_text = "\n".join(lines[full_line_start - 1 : full_line_end]) if localized else text
    anchor = node.get("anchor") if isinstance(node.get("anchor"), Mapping) else {}
    anchor_range = (
        int(anchor.get("line_start") or 0),
        int(anchor.get("line_end") or anchor.get("line_start") or 0),
    ) if anchor else ()
    if localized and line_start > full_line_start:
        signature_end = min(full_line_end, full_line_start + 2)
        signature = "\n".join(lines[full_line_start - 1 : signature_end])
        text = (
            f"{signature}\n"
            f"// ... lines {signature_end + 1}-{line_start - 1} omitted; primary call anchor follows ...\n"
            f"{text}"
        )
    return GroundedCandidate(
        path=path,
        line_start=line_start,
        line_end=line_end,
        text=text,
        score=score,
        origin=origin,
        node_id=str(node.get("id") or ""),
        symbol=str(node.get("qualified_name") or node.get("name") or ""),
        relationship=relationship,
        file_role=actual_role,
        base_score=score,
        provenance_origins=(origin,),
        source_paths=tuple(ordered_unique(tuple(source_paths))),
        relationship_types=((relationship,) if relationship else ()),
        obligation_ids=((obligation_id,) if obligation_id else ()),
        facts=_candidate_facts(
            fact_text,
            full_range=(full_line_start, full_line_end) if localized else (),
            primary_anchor=anchor_range,
            anchor_reliability_tier=int(node.get("anchor_reliability_tier") or 0),
            anchor_decision_code=str(node.get("anchor_decision_code") or ""),
            localization_adapter=str(node.get("localization_adapter") or ""),
        ),
    )


def _range_node_overlap_score(
    node: Mapping[str, Any],
    *,
    line_start: int,
    line_end: int,
) -> float:
    node_start = int(node.get("line_start") or 0)
    node_end = max(node_start, int(node.get("line_end") or node_start))
    if node_start <= 0 or node_start > line_end or node_end < line_start:
        return 0.0
    overlap = min(node_end, line_end) - max(node_start, line_start) + 1
    return min(
        float(overlap) / float(max(1, line_end - line_start + 1)),
        float(overlap) / float(max(1, node_end - node_start + 1)),
    )


def _best_overlapping_nodes(
    nodes: Sequence[Mapping[str, Any]],
    *,
    line_start: int,
    line_end: int,
) -> list[dict[str, Any]]:
    scored = [
        (_range_node_overlap_score(node, line_start=line_start, line_end=line_end), dict(node))
        for node in nodes
    ]
    scored = [(score, node) for score, node in scored if score > 0]
    if not scored:
        return []
    best_score = max(score for score, _node in scored)
    threshold = max(0.2, best_score * 0.5)
    return [
        node
        for score, node in sorted(
            scored,
            key=lambda item: (
                -item[0],
                int(item[1].get("line_end") or 0) - int(item[1].get("line_start") or 0),
            ),
        )
        if score >= threshold
    ]


def _best_bridge_nodes_in_files(
    nodes_by_file: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    query_terms: Sequence[str],
) -> list[dict[str, Any]]:
    expected = set().union(*(_identifier_terms(term) for term in query_terms)) if query_terms else set()
    selected: list[dict[str, Any]] = []
    for nodes in nodes_by_file.values():
        ranked: list[tuple[int, int, dict[str, Any]]] = []
        for raw_node in nodes:
            node = dict(raw_node)
            if str(node.get("kind") or "") not in {"function", "method", "class", "constant"}:
                continue
            overlap = len(expected & _identifier_terms(str(node.get("qualified_name") or node.get("name") or "")))
            if overlap < 2:
                continue
            span = int(node.get("line_end") or 0) - int(node.get("line_start") or 0)
            ranked.append((overlap, -max(0, span), node))
        if ranked:
            ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
            selected.append(ranked[0][2])
    return selected[:4]


def _identifier_terms(value: str) -> set[str]:
    expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(value))
    return {
        token.casefold()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9]*", expanded)
        if len(token) > 1
    }


def _source_text_for_range(
    workspace_root: str,
    path: str,
    line_start: int,
    line_end: int,
    fallback: str,
) -> str:
    source = Path(workspace_root) / path if workspace_root else None
    if source is None or not source.is_file():
        return fallback
    lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
    bounded_end = min(max(line_start, line_end), len(lines))
    return "\n".join(lines[max(0, line_start - 1) : bounded_end])


def _append_semantic_candidates(
    target: ObligationProgress,
    *,
    results: Sequence[Mapping[str, Any]],
    nodes_by_range: Mapping[tuple[str, int, int], Sequence[Mapping[str, Any]] | Mapping[str, Any]],
    concepts: Sequence[str],
    origin: str,
    relationship: str = "",
    promotions: Sequence[GroundedCandidate] = (),
    path_provenance: Sequence[Mapping[str, Any]] = (),
    workspace_root: str = "",
    allow_without_obligation_overlap: bool = False,
) -> None:
    obligation = target.obligation
    path_provenance_by_path = {
        str(item.get("path") or ""): item
        for item in path_provenance
        if str(item.get("path") or "")
    }
    obligation_terms = _distinctive_terms(obligation.description)
    for semantic_rank, result in enumerate(results, start=1):
        path = str(result.get("path") or "")
        if file_role(path) == "baseline_or_generated":
            continue
        line_start = int(result.get("line_start") or 0)
        line_end = int(result.get("line_end") or line_start)
        raw_nodes = nodes_by_range.get((path, line_start, line_end), ())
        nodes = [dict(raw_nodes)] if isinstance(raw_nodes, Mapping) else [
            dict(node) for node in raw_nodes if isinstance(node, Mapping)
        ]
        if not nodes:
            nodes = [{}]
        support_score = _semantic_support_score(obligation_terms, result)
        if support_score <= 0 and allow_without_obligation_overlap:
            support_score = 0.01
        covered_concepts, missing_concepts = _concept_coverage(concepts, str(result.get("text") or ""))
        concept_count = len(covered_concepts) + len(missing_concepts)
        concept_coverage = float(len(covered_concepts)) / float(concept_count) if concept_count else 1.0
        graph_path = path_provenance_by_path.get(path, {})
        graph_sources = ordered_unique(tuple(str(value) for value in graph_path.get("source_paths", ()) if value))
        graph_relationships = ordered_unique(
            tuple(str(value) for value in graph_path.get("relationship_types", ()) if value)
        )
        adjusted_score = support_score + float(result.get("score") or 0.0) \
            - ((1.0 - concept_coverage) * INCOMPLETE_CONCEPT_COVERAGE_PENALTY)
        for node in nodes:
            node_id = str(node.get("id") or "")
            exact_promotions = _matching_structural_promotions(
                promotions,
                path=path,
                line_start=line_start,
                line_end=line_end,
                node_id=node_id,
            )
            node_support_score = support_score
            if node_support_score <= 0 and exact_promotions:
                node_support_score = _overlap_score(
                    obligation_terms,
                    " ".join((str(result.get("text") or ""), *(item.symbol for item in exact_promotions))),
                )
            if node_support_score <= 0:
                continue
            candidate_start = int(node.get("line_start") or line_start)
            candidate_end = int(node.get("line_end") or line_end)
            promotion_sources = ordered_unique(tuple(source for item in exact_promotions for source in item.source_paths))
            promotion_relationships = ordered_unique(tuple(value for item in exact_promotions for value in item.relationship_types))
            promotion_origins = ordered_unique(
                (
                    origin,
                    *(value for item in exact_promotions for value in item.provenance_origins),
                )
            )
            promotion_obligations = ordered_unique(tuple(value for item in exact_promotions for value in item.obligation_ids))
            text = _source_text_for_range(
                workspace_root,
                path,
                candidate_start,
                candidate_end,
                str(result.get("text") or ""),
            )
            target.candidates.append(
                GroundedCandidate(
                    path=path,
                    line_start=candidate_start,
                    line_end=candidate_end,
                    text=text,
                    score=adjusted_score,
                    origin=origin,
                    node_id=node_id,
                    symbol=str(node.get("qualified_name") or node.get("name") or ""),
                    relationship=relationship,
                    file_role=file_role(path),
                    covered_concepts=covered_concepts,
                    missing_concepts=missing_concepts,
                    base_score=adjusted_score,
                    provenance_origins=promotion_origins,
                    source_paths=ordered_unique((*promotion_sources, *graph_sources)),
                    relationship_types=ordered_unique(
                        ((relationship,) if relationship else ()) + promotion_relationships + graph_relationships
                    ),
                    obligation_ids=ordered_unique((obligation.id, *promotion_obligations)),
                    facts=_candidate_facts(
                        text,
                        semantic_discoveries=(
                            SemanticDiscovery(
                                obligation_id=obligation.id,
                                rank=semantic_rank,
                                score=float(result.get("score") or 0.0),
                                matched_terms=tuple(str(value) for value in result.get("matched_terms", ()) if value),
                            ),
                        ),
                    ),
                )
            )


def _candidate_ledger_key(candidate: GroundedCandidate) -> str:
    if candidate.node_id:
        return f"node:{candidate.node_id}"
    return f"range:{candidate.path}:{candidate.line_start}:{candidate.line_end}"


def _candidate_review_id(obligation_id: str, candidate: GroundedCandidate) -> str:
    return f"{obligation_id}|{_candidate_ledger_key(candidate)}"


def _merge_candidate_provenance(left: GroundedCandidate, right: GroundedCandidate) -> GroundedCandidate:
    preferred = left if left.score >= right.score else right
    base_score = max(left.base_score or left.score, right.base_score or right.score)
    source_paths = ordered_unique((*left.source_paths, *right.source_paths))
    return replace(
        preferred,
        score=max(left.score, right.score),
        base_score=base_score,
        provenance_origins=ordered_unique(
            (*left.provenance_origins, left.origin, *right.provenance_origins, right.origin)
        ),
        source_paths=source_paths,
        relationship_types=ordered_unique(
            (
                *left.relationship_types,
                *((left.relationship,) if left.relationship else ()),
                *right.relationship_types,
                *((right.relationship,) if right.relationship else ()),
            )
        ),
        obligation_ids=ordered_unique((*left.obligation_ids, *right.obligation_ids)),
        covered_concepts=ordered_unique((*left.covered_concepts, *right.covered_concepts)),
        missing_concepts=tuple(
            concept
            for concept in ordered_unique((*left.missing_concepts, *right.missing_concepts))
            if concept not in set((*left.covered_concepts, *right.covered_concepts))
        ),
        facts=CandidateFacts(
            semantic_discoveries=tuple(
                sorted(
                    {
                        *left.facts.semantic_discoveries,
                        *right.facts.semantic_discoveries,
                    },
                    key=lambda item: (item.obligation_id, item.rank, -item.score),
                )
            ),
            visible_calls=ordered_unique((*left.facts.visible_calls, *right.facts.visible_calls)),
            callable_defaults=tuple(dict.fromkeys((*left.facts.callable_defaults, *right.facts.callable_defaults))),
            returned_names=ordered_unique((*left.facts.returned_names, *right.facts.returned_names)),
            written_fields=ordered_unique((*left.facts.written_fields, *right.facts.written_fields)),
            read_fields=ordered_unique((*left.facts.read_fields, *right.facts.read_fields)),
            full_range=preferred.facts.full_range or left.facts.full_range or right.facts.full_range,
            primary_anchor=preferred.facts.primary_anchor or left.facts.primary_anchor or right.facts.primary_anchor,
            anchor_reliability_tier=max(
                left.facts.anchor_reliability_tier,
                right.facts.anchor_reliability_tier,
            ),
            anchor_decision_code=(
                left.facts.anchor_decision_code
                if left.facts.anchor_reliability_tier >= right.facts.anchor_reliability_tier
                else right.facts.anchor_decision_code
            ),
            localization_adapter=preferred.facts.localization_adapter or left.facts.localization_adapter or right.facts.localization_adapter,
        ),
    )


def _update_promotion_ledger(
    ledger: dict[str, GroundedCandidate],
    candidates: Sequence[GroundedCandidate],
) -> None:
    for candidate in candidates:
        key = _candidate_ledger_key(candidate)
        current = ledger.get(key)
        ledger[key] = candidate if current is None else _merge_candidate_provenance(current, candidate)


def _promotion_candidates_for_obligation(
    ledger: Mapping[str, GroundedCandidate],
    obligation_id: str,
) -> tuple[GroundedCandidate, ...]:
    return tuple(
        sorted(
            (
                candidate
                for candidate in ledger.values()
                if obligation_id in candidate.obligation_ids
            ),
            key=lambda candidate: (
                -len(candidate.covered_concepts),
                candidate.path,
                candidate.line_start,
            ),
        )
    )


def _qualified_frontier_paths(
    candidates: Sequence[GroundedCandidate],
) -> tuple[str, ...]:
    return ordered_unique(
        tuple(
            candidate.path
            for candidate in candidates
            if candidate.path
        )
    )


def _graph_preferred_paths(
    file_neighbors: Sequence[Mapping[str, Any]],
    *,
    qualified_candidates: Sequence[GroundedCandidate] = (),
    node_frontier_paths: Sequence[str] = (),
) -> list[dict[str, Any]]:
    preferred: dict[str, dict[str, Any]] = {}
    for item in file_neighbors:
        path = str(item.get("path") or "")
        if not path:
            continue
        preferred[path] = {
            "path": path,
            "score": max(0.0, float(item.get("score") or 0.0)),
            "source_paths": list(ordered_unique(tuple(str(value) for value in item.get("source_paths", ()) if value))),
            "relationship_types": list(ordered_unique(tuple(str(value) for value in item.get("edge_kinds", ()) if value))),
        }
    for candidate in qualified_candidates:
        if not candidate.path:
            continue
        entry = preferred.setdefault(
            candidate.path,
            {"path": candidate.path, "score": 0.0, "source_paths": [], "relationship_types": []},
        )
        entry["score"] = max(float(entry["score"]), 1.0)
        entry["source_paths"] = list(
            ordered_unique((*entry["source_paths"], *candidate.source_paths))
        )
        entry["relationship_types"] = list(
            ordered_unique((*entry["relationship_types"], "qualified_reference", *candidate.relationship_types))
        )
    for path in node_frontier_paths:
        if not path:
            continue
        preferred.setdefault(
            path,
            {"path": path, "score": 1.0, "source_paths": [], "relationship_types": ["node_adjacency"]},
        )
    return sorted(preferred.values(), key=lambda item: (-float(item["score"]), str(item["path"])))


def _qualified_reference_query_context(candidates: Sequence[GroundedCandidate]) -> str:
    symbols = ordered_unique(tuple(candidate.symbol for candidate in candidates if candidate.symbol))[:8]
    if not symbols:
        return ""
    return "Inspect these exact functions reached through calls from current candidates: " + ", ".join(symbols) + "."


def _promotion_ranges(candidates: Sequence[GroundedCandidate]) -> list[dict[str, Any]]:
    return [
        {
            "path": candidate.path,
            "line_start": candidate.line_start,
            "line_end": candidate.line_end,
            "node_id": candidate.node_id,
            "symbol": candidate.symbol,
        }
        for candidate in candidates
        if candidate.path and candidate.line_start > 0 and candidate.line_end >= candidate.line_start
    ]


def _matching_structural_promotions(
    promotions: Sequence[GroundedCandidate],
    *,
    path: str,
    line_start: int,
    line_end: int,
    node_id: str,
) -> tuple[GroundedCandidate, ...]:
    return tuple(
        promotion
        for promotion in promotions
        if promotion.path == path
        and (
            bool(node_id and promotion.node_id == node_id)
            or max(line_start, promotion.line_start) <= min(line_end, promotion.line_end)
        )
    )


def _dedupe_candidates(candidates: Sequence[GroundedCandidate]) -> list[GroundedCandidate]:
    best: dict[tuple[str, int, int], GroundedCandidate] = {}
    for candidate in candidates:
        key = (candidate.path, candidate.line_start, candidate.line_end)
        current = best.get(key)
        best[key] = candidate if current is None else _merge_candidate_provenance(current, candidate)
    return sorted(best.values(), key=lambda item: (-item.score, item.path, item.line_start))


def _apply_duplicate_provenance_ranking(
    progress: Mapping[str, ObligationProgress],
    *,
    expanded_edges: Sequence[Mapping[str, Any]],
    workspace_root: Path,
) -> None:
    external_connections: dict[str, int] = {}
    for edge in expanded_edges:
        source = edge.get("source") if isinstance(edge.get("source"), Mapping) else {}
        target = edge.get("target") if isinstance(edge.get("target"), Mapping) else {}
        source_id = str(source.get("id") or "")
        target_id = str(target.get("id") or "")
        source_path = str(source.get("path") or "")
        target_path = str(target.get("path") or "")
        if not source_path or not target_path or source_path == target_path:
            continue
        if source_id:
            external_connections[source_id] = external_connections.get(source_id, 0) + 1
        if target_id:
            external_connections[target_id] = external_connections.get(target_id, 0) + 1

    file_sizes: dict[str, int] = {}
    for item in progress.values():
        candidates = item.candidates
        duplicate_groups = _near_duplicate_groups(candidates)
        penalized: set[int] = set()
        for group in duplicate_groups:
            canonical_index = max(
                group,
                key=lambda index: (
                    external_connections.get(candidates[index].node_id, 0),
                    -_candidate_file_size(candidates[index], workspace_root, file_sizes),
                    -len(candidates[index].path),
                ),
            )
            penalized.update(index for index in group if index != canonical_index)
        item.candidates = [
            replace(
                candidate,
                score=(
                    candidate.score
                    - (DUPLICATE_PROVENANCE_PENALTY if index in penalized else 0.0)
                    - (
                        OVERSIZED_UNCONNECTED_FILE_PENALTY
                        if _candidate_file_size(candidate, workspace_root, file_sizes)
                        > OVERSIZED_UNCONNECTED_FILE_BYTES
                        and not candidate.source_paths
                        and external_connections.get(candidate.node_id, 0) == 0
                        else 0.0
                    )
                ),
            )
            for index, candidate in enumerate(candidates)
        ]


def _remove_generated_candidates(
    progress: Mapping[str, ObligationProgress],
) -> None:
    for item in progress.values():
        item.candidates = [
            candidate for candidate in item.candidates if file_role(candidate.path) != "baseline_or_generated"
        ]
        item.discovery_hints = [
            candidate
            for candidate in item.discovery_hints
            if file_role(candidate.path) != "baseline_or_generated"
        ]


def _near_duplicate_groups(candidates: Sequence[GroundedCandidate]) -> tuple[tuple[int, ...], ...]:
    parents = list(range(len(candidates)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    token_sequences = [_duplicate_tokens(candidate.text) for candidate in candidates]
    for left in range(len(candidates)):
        if len(token_sequences[left]) < 12:
            continue
        for right in range(left + 1, len(candidates)):
            if candidates[left].path == candidates[right].path or len(token_sequences[right]) < 12:
                continue
            ratio = SequenceMatcher(
                None,
                token_sequences[left],
                token_sequences[right],
                autojunk=False,
            ).ratio()
            if ratio >= 0.78:
                union(left, right)

    groups: dict[int, list[int]] = {}
    for index in range(len(candidates)):
        groups.setdefault(find(index), []).append(index)
    return tuple(tuple(group) for group in groups.values() if len(group) > 1)


def _duplicate_tokens(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", text.casefold()))


def _candidate_file_size(
    candidate: GroundedCandidate,
    workspace_root: Path,
    cache: dict[str, int],
) -> int:
    if candidate.path not in cache:
        try:
            cache[candidate.path] = (workspace_root / candidate.path).stat().st_size
        except OSError:
            cache[candidate.path] = 2**63 - 1
    return cache[candidate.path]


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
            "file_role": candidate.file_role,
            "provenance_origins": list(candidate.provenance_origins or (candidate.origin,)),
            "source_paths": list(candidate.source_paths),
            "relationship_types": list(candidate.relationship_types),
            "originating_obligations": list(candidate.obligation_ids),
        },
    )
