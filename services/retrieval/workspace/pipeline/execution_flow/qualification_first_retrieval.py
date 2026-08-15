from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping, Sequence

from core.models import ConversationState, EvidenceItem, RetrievalResult
from services.intent.models import EvidenceSource
from services.retrieval.workspace.connected_context import ConnectedSourceContextResult
from services.retrieval.workspace.pipeline.execution_flow.context import WorkspaceRetrievalContext
from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import (
    DiscoveryObservation,
    aggregate_observations,
    observation_from_node,
    observation_from_result,
)
from services.retrieval.workspace.pipeline.execution_flow.evidence_qualification import QualificationDecision
from services.retrieval.workspace.pipeline.execution_flow.obligation_retrieval import (
    MAX_EVIDENCE,
    MAX_FOCUSED_RESULTS,
    MAX_OBLIGATIONS,
    GroundedCandidate,
    ObligationProgress,
    SemanticDiscovery,
    _best_overlapping_nodes,
    _candidate_facts,
    _candidate_trace_item,
    _confirmed_obligation_paths,
    _consolidate_obligation_evidence,
    _distinctive_terms,
    _edge_index,
    _evidence_item,
    _exact_prompt_seed_results,
    _global_candidate_id,
    _ground_request_anchors,
    _node_text,
    _obligation_query,
    _obligation_stage_query_text,
    _overlap_score,
    _resolve_repository_path,
    _source_category_for_role,
    _transition_from_edges,
    _transition_from_shared_anchors,
    ordered_unique,
)
from services.retrieval.workspace.pipeline.execution_flow.retrieval_controller import run_retrieval_controller
from services.retrieval.workspace.pipeline.execution_flow.source_disclosure import DisclosureCard
from services.retrieval.workspace.tools import ToolRequest


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
    repository_obligations = tuple(item for item in obligations if item.evidence_source == EvidenceSource.REPOSITORY)
    connected_context = connected_context or ConnectedSourceContextResult()
    progress = {item.id: ObligationProgress(item) for item in obligations}
    tool_calls = starting_tool_calls

    confirmations, anchor_nodes, unresolved_symbols, ambiguous_symbols, added_calls = _ground_request_anchors(
        ctx,
        anchors=intent_context.anchors.to_dict(),
        additional_paths=connected_context.file_hints,
        additional_symbols=connected_context.symbol_hints,
        qdrant_tool=qdrant_tool,
        structural_tools=structural_tools,
    )
    tool_calls += added_calls
    confirmed_values = {item.value for item in confirmations if item.confirmed_in_repository}
    connected_terms = ordered_unique(
        (*intent_context.search_terms, *connected_context.retrieval_terms, *connected_context.suggested_subqueries)
    )
    connected_preferred_paths = tuple(
        {"path": resolved, "score": 1.0}
        for value in connected_context.file_hints
        if (resolved := _resolve_repository_path(ctx.config.workspace_root, value))
    )
    exact_prompt_seeds = _exact_prompt_seed_results(confirmations, repository_obligations)
    semantic_by_obligation: dict[str, list[dict[str, Any]]] = {}
    for obligation in repository_obligations:
        query = _obligation_query(
            _obligation_stage_query_text(obligation),
            (*unresolved_symbols, *ambiguous_symbols),
            anchors=tuple(value for value in obligation.anchor_refs if value in confirmed_values),
            search_terms=connected_terms,
        )
        request = ToolRequest(
            tool_name="qdrant_hybrid_search",
            arguments={
                "query": query,
                "limit": MAX_FOCUSED_RESULTS,
                "max_per_path": 1,
                "source_category": _source_category_for_role(obligation.evidence_role),
                "file_role": "any",
                "paths": list(_confirmed_obligation_paths(obligation, confirmations)),
                "preferred_paths": list(connected_preferred_paths),
            },
            reason=f"Discover observations for evidence obligation {obligation.id}.",
        )
        response = qdrant_tool.run(request)
        ctx.trace.record_tool(request, response, round_index=0)
        tool_calls += 1
        if response.status != "ok":
            raise RuntimeError(f"required_tool_failed: qdrant_hybrid_search:{obligation.id}")
        semantic_by_obligation[obligation.id] = [
            dict(item) for item in response.payload.get("results", ()) if isinstance(item, Mapping)
        ][:MAX_FOCUSED_RESULTS]

    all_results = [
        (obligation.id, origin, rank, item)
        for obligation in repository_obligations
        for origin, values in (
            ("exact_prompt_anchor", exact_prompt_seeds.get(obligation.id, ())),
            ("qdrant_hybrid", semantic_by_obligation.get(obligation.id, ())),
        )
        for rank, item in enumerate(values, start=1)
    ]
    ranges = [
        {"file": item.get("path"), "line_start": item.get("line_start"), "line_end": item.get("line_end")}
        for _obligation_id, _origin, _rank, item in all_results
        if item.get("path") and item.get("line_start")
    ]
    range_nodes: dict[tuple[str, int, int], tuple[dict[str, Any], ...]] = {}
    if ranges:
        request = ToolRequest(
            tool_name="structural_resolve_ranges",
            arguments={"ranges": ranges},
            reason="Attach the narrowest available structural handles to initial observations.",
        )
        response = structural_tools["structural_resolve_ranges"].run(request)
        ctx.trace.record_tool(request, response, round_index=0)
        tool_calls += 1
        if response.status != "ok":
            raise RuntimeError("required_tool_failed: structural_resolve_ranges")
        for item in response.payload.get("results", ()):
            if not isinstance(item, Mapping):
                continue
            key = (str(item.get("file") or ""), int(item.get("line_start") or 0), int(item.get("line_end") or 0))
            nodes = tuple(dict(node) for node in item.get("nodes", ()) if isinstance(node, Mapping))
            range_nodes[key] = tuple(_best_overlapping_nodes(nodes, line_start=key[1], line_end=key[2]))

    raw_observations: list[DiscoveryObservation] = []
    for obligation in repository_obligations:
        obligation_terms = _distinctive_terms(obligation.description)
        for node in anchor_nodes:
            anchor = str(node.get("anchor_query") or "")
            score = _overlap_score(obligation_terms, _node_text(node))
            if anchor not in obligation.anchor_refs and score <= 0:
                continue
            observation = observation_from_node(
                node,
                retriever="exact_anchor",
                query_id=f"anchor:{anchor}",
                obligation_ids=(obligation.id,),
                score=score + 1.0,
                exact_anchor=anchor,
            )
            if observation is not None:
                raw_observations.append(observation)
    for obligation_id, origin, rank, result in all_results:
        key = (str(result.get("path") or ""), int(result.get("line_start") or 0), int(result.get("line_end") or 0))
        raw_observations.extend(
            observation_from_result(
                result,
                obligation_id=obligation_id,
                query_id=f"{origin}:{obligation_id}",
                rank=rank,
                retriever=origin,
                nodes=range_nodes.get(key, ()),
                exact_anchor=str(result.get("exact_prompt_anchor") or "") if origin == "exact_prompt_anchor" else "",
            )
        )
    initial_observations, guardrail_decisions = aggregate_observations(
        raw_observations,
        limit=ctx.config.max_discovery_observations,
    )
    all_aggregated_observations, _all_decisions = aggregate_observations(
        raw_observations,
        limit=max(1, len(raw_observations)),
    )
    initial_ids = {item.id for item in initial_observations}
    deferred_observations = tuple(item for item in all_aggregated_observations if item.id not in initial_ids)
    ctx.trace.record(
        "discovery_observations_created",
        {
            "raw_count": len(raw_observations),
            "raw_observations": [item.to_dict(include_text=False) for item in raw_observations],
            "aggregated_count": len(initial_observations),
            "deferred_count": len(deferred_observations),
            "observations": [item.to_dict(include_text=False) for item in initial_observations],
            "guardrail_decisions": list(guardrail_decisions),
        },
    )

    controller = run_retrieval_controller(
        ctx=ctx,
        user_request=state.user_input,
        obligations=repository_obligations,
        initial_observations=initial_observations,
        deferred_observations=deferred_observations,
        structural_tools=structural_tools,
        qdrant_tool=qdrant_tool,
        candidate_factory=lambda observation, decision, card: _candidate_from_qualified(
            observation, decision, card
        ),
        candidate_payload=_controller_candidate_payload,
    )
    tool_calls += controller.tool_calls
    candidates_by_id = {_global_candidate_id(item): item for item in controller.candidates}
    for coverage in controller.coverage:
        for candidate_id in coverage.supporting_candidate_ids:
            candidate = candidates_by_id.get(candidate_id)
            if candidate is not None:
                candidates_by_id[candidate_id] = replace(
                    candidate,
                    obligation_ids=ordered_unique((*candidate.obligation_ids, coverage.obligation_id)),
                )
    for candidate in candidates_by_id.values():
        for obligation_id in candidate.obligation_ids:
            if obligation_id in progress:
                progress[obligation_id].candidates.append(candidate)

    repository_states = tuple(progress[item.id] for item in repository_obligations)
    preselection = [
        {**_candidate_trace_item(candidate, candidate_id=candidate_id), "text_chars": len(candidate.text)}
        for candidate_id, candidate in candidates_by_id.items()
    ]
    ctx.trace.record(
        "final_candidate_pool_created",
        {
            "candidate_count": len(preselection),
            "candidate_ids": list(candidates_by_id),
            "files": sorted({item.path for item in candidates_by_id.values()}),
            "islands": [item.to_dict() for item in controller.islands.islands],
            "relationships": list(controller.edges),
            "candidates": preselection,
        },
    )
    if ctx.config.final_evidence_selection_enabled:
        candidate_islands = _candidate_island_ids(candidates_by_id, controller)
        consolidation = _consolidate_obligation_evidence(
            ctx,
            repository_states,
            expanded_edges=controller.edges,
            input_char_budget=ctx.config.max_final_selection_input_chars,
            candidate_islands=candidate_islands,
        )
        consolidation = _preserve_active_island_candidates(
            consolidation,
            candidates_by_id,
            candidate_islands,
            controller,
        )
    else:
        consolidation = _skipped_consolidation(repository_states)
        ctx.trace.record("final_evidence_selection_skipped", {"reason": "explicit_diagnostic_configuration"})

    for obligation in obligations:
        item = progress[obligation.id]
        if obligation.evidence_source == EvidenceSource.PROMPT:
            item.status = "supported"
            continue
        if obligation.evidence_source == EvidenceSource.EXTERNAL:
            item.status = "unresolved"
            item.unresolved_reason = "This obligation requires evidence outside the selected repository."
            continue
        status = str(consolidation.get("obligation_statuses", {}).get(obligation.id, "unresolved"))
        item.status = "supported" if status in {"prompt_grounded", "repository_supported", "jointly_supported"} else "unresolved"
        if item.status == "unresolved":
            item.unresolved_reason = str(consolidation.get("unresolved_reasons", {}).get(obligation.id) or "Final evidence selection did not establish this obligation.")

    edge_index = _edge_index(controller.edges)
    for obligation in repository_obligations:
        item = progress[obligation.id]
        for dependency_id in obligation.depends_on:
            if not obligation.requires_repository_handoff:
                item.transitions.append({"from": dependency_id, "status": "context_only", "reason": "No repository handoff is required."})
                continue
            dependency = progress[dependency_id]
            transition = _transition_from_edges(dependency, item, edge_index)
            if transition is None:
                transition = _transition_from_shared_anchors(dependency, item, confirmed_values)
            item.transitions.append(transition or {"from": dependency_id, "status": "unresolved", "reason": "No qualified controller action established this handoff."})

    selected = _selected_evidence(consolidation, candidates_by_id, repository_obligations)
    selected.extend(_selected_connected_evidence(connected_context, start_rank=len(selected) + 1, remaining=MAX_EVIDENCE - len(selected)))
    states = [progress[item.id] for item in obligations]
    required_unresolved = [item.obligation.id for item in states if item.obligation.required and item.status != "supported"]
    unresolved_transitions = [
        f"{transition['from']}->{item.obligation.id}"
        for item in states
        if item.obligation.required
        for transition in item.transitions
        if transition.get("status") == "unresolved"
    ]
    sufficient = bool(selected) and not required_unresolved and not unresolved_transitions
    summary = {
        "retriever": "workspace",
        "request_analysis": intent_context.to_dict(),
        "retrieval_plan": {"strategy": "qualification_first_controller_v1", "obligations": [item.to_dict() for item in states]},
        "index_rebuilt": index_rebuilt,
        "index_document_count": index_document_count,
        "selected_count": len(selected),
        "tool_calls": tool_calls,
        "exploration_rounds": controller.rounds,
        "stop_reason": controller.stop_reason,
        "raw_observation_count": len(raw_observations),
        "observation_count": len(controller.decisions),
        "deferred_observation_count": len(controller.observations) - len(controller.decisions),
        "active_root_ids": list(controller.islands.active_root_ids),
        "evidence_island_count": len(controller.islands.islands),
        "candidate_graph_size_before_final_selection": len(candidates_by_id),
        "unique_candidate_count_before_final_selection": len(candidates_by_id),
        "preselection_candidate_pool": preselection,
        "qualification_decisions": [item.to_dict() for item in controller.decisions],
        "controller_coverage": [item.to_dict() for item in controller.coverage],
        "qualification_usage": dict(controller.qualification_usage),
        "coverage_usage": dict(controller.coverage_usage),
        "anchor_query_count": len(confirmations),
        "anchor_confirmations": [item.to_dict() for item in confirmations],
        "resolved_symbol_anchors": sorted({str(item.get("anchor_query") or "") for item in anchor_nodes}),
        "unresolved_symbol_anchors": list(unresolved_symbols),
        "ambiguous_symbol_anchors": list(ambiguous_symbols),
        "graph_edge_count": len(controller.edges),
        "unresolved_obligations": required_unresolved,
        "unresolved_transitions": unresolved_transitions,
        "connected_source_context": connected_context.to_dict(),
        "evidence_consolidation": consolidation,
    }
    return RetrievalResult(
        evidence=tuple(selected),
        coverage_status="strong" if sufficient else ("partial" if selected else "missing"),
        sufficient=sufficient,
        retrieval_summary=summary,
        failures_or_fallbacks=tuple((*required_unresolved, *unresolved_transitions)),
    )


def _candidate_from_qualified(
    observation: DiscoveryObservation,
    decision: QualificationDecision,
    card: DisclosureCard,
) -> GroundedCandidate | None:
    if not card.source_text.strip():
        return None
    handle = observation.handle
    qualification_origin = (
        "qualified_direct_evidence"
        if decision.support_level == "direct_evidence"
        else "qualified_navigation_evidence"
    )
    origins = ordered_unique((qualification_origin, *(item.retriever for item in observation.provenance)))
    semantic = tuple(
        SemanticDiscovery(
            obligation_id=obligation_id,
            rank=provenance.ranks[0] if provenance.ranks else 0,
            score=provenance.scores[0] if provenance.scores else 0.0,
            matched_terms=provenance.matched_terms,
        )
        for provenance in observation.provenance
        for obligation_id in provenance.obligation_ids
    )
    relationship = observation.relationship_kinds[0] if observation.relationship_kinds else ""
    line_start = handle.full_line_start if card.mode == "full" and handle.full_line_start else handle.line_start
    line_end = handle.full_line_end if card.mode == "full" and handle.full_line_end else handle.line_end
    return GroundedCandidate(
        path=handle.path,
        line_start=line_start,
        line_end=line_end,
        text=card.source_text,
        score=observation.best_score,
        origin=qualification_origin,
        node_id=handle.node_id,
        symbol=handle.symbol,
        relationship=relationship,
        file_role=observation.artifact_role,
        base_score=observation.best_score,
        provenance_origins=origins,
        source_paths=(),
        relationship_types=observation.relationship_kinds,
        obligation_ids=observation.obligation_ids,
        facts=_candidate_facts(
            card.source_text,
            semantic_discoveries=semantic,
            full_range=(handle.full_line_start, handle.full_line_end),
            primary_anchor=(handle.line_start, handle.line_end),
            localization_adapter=handle.adapter,
        ),
    )


def _controller_candidate_payload(candidate: GroundedCandidate) -> dict[str, Any]:
    return {
        "candidate_id": _global_candidate_id(candidate),
        "observation_id": _observation_id_for_candidate(candidate),
        "path": candidate.path,
        "line_start": candidate.line_start,
        "line_end": candidate.line_end,
        "symbol": candidate.symbol,
        "snippet": candidate.text,
        "obligation_ids": list(candidate.obligation_ids),
        "qualification_support": (
            "direct_evidence"
            if candidate.origin == "qualified_direct_evidence"
            else "navigation_only"
        ),
    }


def _candidate_island_ids(
    candidates: Mapping[str, GroundedCandidate],
    controller: Any,
) -> dict[str, str]:
    observation_by_id = {item.id: item for item in controller.observations}
    result: dict[str, str] = {}
    for island in controller.islands.islands:
        island_observations = [
            observation_by_id[observation_id]
            for observation_id in island.observation_ids
            if observation_id in observation_by_id
        ]
        for candidate_id, candidate in candidates.items():
            if candidate_id in result:
                continue
            if any(_candidate_matches_observation(candidate, observation) for observation in island_observations):
                result[candidate_id] = island.id
    return result


def _candidate_matches_observation(candidate: GroundedCandidate, observation: DiscoveryObservation) -> bool:
    if candidate.node_id and observation.handle.node_id:
        return candidate.node_id == observation.handle.node_id
    if candidate.path != observation.handle.path:
        return False
    return candidate.line_start <= observation.handle.line_end and observation.handle.line_start <= candidate.line_end


def _preserve_active_island_candidates(
    consolidation: Mapping[str, Any],
    candidates: Mapping[str, GroundedCandidate],
    candidate_islands: Mapping[str, str],
    controller: Any,
) -> dict[str, Any]:
    active_roots = set(controller.islands.active_root_ids)
    active_islands = {
        island.id
        for island in controller.islands.islands
        if active_roots.intersection(island.observation_ids)
    }
    island_choices: dict[str, list[tuple[str, GroundedCandidate]]] = {}
    for candidate_id, candidate in candidates.items():
        island_id = candidate_islands.get(candidate_id, "")
        if island_id:
            island_choices.setdefault(island_id, []).append((candidate_id, candidate))
    ranked_candidate_islands = sorted(
        island_choices,
        key=lambda island_id: min(
            (
                -candidate.score,
                0 if candidate.origin == "qualified_direct_evidence" else 1,
                candidate.path.casefold(),
                candidate.line_start,
            )
            for _candidate_id, candidate in island_choices[island_id]
        ),
    )
    protected_islands = set(active_islands)
    for island_id in ranked_candidate_islands:
        if len(protected_islands) >= 6:
            break
        protected_islands.add(island_id)
    accepted = [
        str(candidate_id)
        for candidate_id in consolidation.get("accepted_candidate_ids", ())
        if str(candidate_id) in candidates
    ]
    represented = {candidate_islands.get(candidate_id, "") for candidate_id in accepted}
    preserved: list[str] = []
    for island_id in sorted(protected_islands - represented):
        choices = island_choices.get(island_id, [])
        if not choices or len(accepted) >= MAX_EVIDENCE:
            continue
        candidate_id, _candidate = min(
            choices,
            key=lambda item: (
                0 if item[1].origin == "qualified_direct_evidence" else 1,
                -item[1].score,
                item[1].path.casefold(),
                item[1].line_start,
            ),
        )
        accepted.append(candidate_id)
        preserved.append(candidate_id)
    result = dict(consolidation)
    result["accepted_candidate_ids"] = accepted
    result["preserved_active_island_candidate_ids"] = preserved
    return result


def _observation_id_for_candidate(candidate: GroundedCandidate) -> str:
    from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import SourceHandle, observation_id

    return observation_id(
        SourceHandle(
            path=candidate.path,
            line_start=candidate.line_start,
            line_end=candidate.line_end,
            node_id=candidate.node_id,
        )
    )


def _selected_evidence(
    consolidation: Mapping[str, Any],
    candidates: Mapping[str, GroundedCandidate],
    obligations: Sequence[Any],
) -> list[EvidenceItem]:
    selected: list[EvidenceItem] = []
    accepted_by_obligation = consolidation.get("accepted_ids_by_obligation", {})
    for candidate_id in consolidation.get("accepted_candidate_ids", ()):
        candidate = candidates.get(str(candidate_id))
        if candidate is None or len(selected) >= MAX_EVIDENCE:
            continue
        obligation_id = next(
            (item.id for item in obligations if candidate_id in accepted_by_obligation.get(item.id, ())),
            obligations[0].id if obligations else "mechanism",
        )
        selected.append(_evidence_item(candidate, obligation_id=obligation_id, rank=len(selected) + 1))
    return selected


def _selected_connected_evidence(
    connected_context: ConnectedSourceContextResult,
    *,
    start_rank: int,
    remaining: int,
) -> list[EvidenceItem]:
    selected_ids = set(connected_context.selected_evidence_ids)
    values: list[EvidenceItem] = []
    for document in connected_context.documents:
        if document.source_id not in selected_ids or len(values) >= remaining:
            continue
        values.append(
            EvidenceItem(
                source_category=document.source_category,
                source_id=document.source_id,
                snippet=document.content,
                rank=start_rank + len(values),
                metadata={"title": document.title, "source_key": document.source_key, "retrieval_origin": "connected_source"},
            )
        )
    return values


def _skipped_consolidation(states: Sequence[ObligationProgress]) -> dict[str, Any]:
    return {
        "strategy": "explicitly_skipped_for_candidate_pool_diagnostics",
        "skipped": True,
        "llm_calls": 0,
        "accepted_candidate_ids": [],
        "accepted_ids_by_obligation": {},
        "obligation_statuses": {item.obligation.id: "unresolved" for item in states},
        "unresolved_reasons": {item.obligation.id: "Final evidence selection was explicitly disabled." for item in states},
        "usage": {},
    }
