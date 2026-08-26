from __future__ import annotations

from dataclasses import replace
import re
from typing import Any, Mapping, Sequence

from core.models import ConversationState, EvidenceItem, RetrievalResult
from core.source_policy import SourceCategory
from services.intent.models import EvidenceSource
from services.retrieval.workspace.connected_context import ConnectedSourceContextResult
from services.retrieval.workspace.pipeline.execution_flow.context import WorkspaceRetrievalContext
from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import (
    DiscoveryObservation,
    canonicalize_observations,
    merge_observation_pair,
    observation_from_node,
    observation_from_result,
)
from services.retrieval.workspace.pipeline.execution_flow.evidence_qualification import (
    PROMPT_PATH as QUALIFICATION_PROMPT_PATH,
    QualificationDecision,
    prepare_qualification_request,
)
from services.retrieval.workspace.pipeline.execution_flow.initial_owner_comparison import (
    compare_initial_owners,
    fit_initial_owner_comparison_admission,
    select_range_candidate_owners,
)
from services.retrieval.workspace.pipeline.execution_flow.initial_file_admission import rank_initial_files
from services.retrieval.workspace.pipeline.execution_flow.obligation_retrieval import (
    MAX_EVIDENCE,
    MAX_FOCUSED_RESULTS,
    MAX_OBLIGATIONS,
    GroundedCandidate,
    ObligationProgress,
    SemanticDiscovery,
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
from services.retrieval.workspace.pipeline.execution_flow.source_disclosure import (
    DisclosureCard,
    disclose_observations,
)
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
    exact_repository_symbols = {
        item.value
        for item in confirmations
        if item.kind == "symbol" and item.match_type == "exact_symbol"
    }
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
        repository_sparse_anchors = _repository_sparse_anchors(obligation, exact_repository_symbols)
        sparse_query = _initial_sparse_query(
            obligation,
            exact_repository_symbols=exact_repository_symbols,
        )
        request = ToolRequest(
            tool_name="qdrant_hybrid_search",
            arguments={
                "query": query,
                "sparse_query": sparse_query,
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
        ctx.trace.record(
            "initial_query_channel_results",
            {
                "obligation_id": obligation.id,
                "dense_query": query,
                "sparse_query": sparse_query,
                "requested_sparse_query": sparse_query,
                "effective_sparse_query": str(response.payload.get("sparse_query") or ""),
                "repository_sparse_anchors": list(repository_sparse_anchors),
                "excluded_sparse_anchor_refs": list(
                    _excluded_sparse_anchor_refs(obligation, exact_repository_symbols)
                ),
                "hybrid_results": _channel_result_summary(response.payload.get("results", ())),
                "dense_results": _channel_result_summary(
                    response.payload.get("breakdown", {}).get("dense", ())
                    if isinstance(response.payload.get("breakdown", {}), Mapping) else ()
                ),
                "sparse_results": _channel_result_summary(
                    response.payload.get("breakdown", {}).get("sparse", ())
                    if isinstance(response.payload.get("breakdown", {}), Mapping) else ()
                ),
                "hybrid_result_count": len(response.payload.get("results", ())),
                "dense_result_count": len(
                    response.payload.get("breakdown", {}).get("dense", ())
                    if isinstance(response.payload.get("breakdown", {}), Mapping) else ()
                ),
                "sparse_result_count": len(
                    response.payload.get("breakdown", {}).get("sparse", ())
                    if isinstance(response.payload.get("breakdown", {}), Mapping) else ()
                ),
                "hybrid_unique_file_count": _unique_result_path_count(response.payload.get("results", ())),
                "dense_unique_file_count": _unique_result_path_count(
                    response.payload.get("breakdown", {}).get("dense", ())
                    if isinstance(response.payload.get("breakdown", {}), Mapping) else ()
                ),
                "sparse_unique_file_count": _unique_result_path_count(
                    response.payload.get("breakdown", {}).get("sparse", ())
                    if isinstance(response.payload.get("breakdown", {}), Mapping) else ()
                ),
                "requested_final_limit": MAX_FOCUSED_RESULTS,
                "backend_hybrid_limit": min(50, MAX_FOCUSED_RESULTS * 4),
                "backend_channel_prefetch_limit": min(50, MAX_FOCUSED_RESULTS * 4) * 3,
                "sparse_query_diagnostics": dict(response.payload.get("sparse_query_diagnostics", {})),
            },
        )
        tool_calls += 1
        if response.status != "ok":
            raise RuntimeError(f"required_tool_failed: qdrant_hybrid_search:{obligation.id}")
        representatives, alternatives, file_groups = _file_group_initial_results(
            response.payload,
            limit=max(
                1,
                _unique_result_path_count(
                    tuple(response.payload.get("breakdown", {}).get("dense", ()))
                    + tuple(response.payload.get("breakdown", {}).get("sparse", ()))
                    if isinstance(response.payload.get("breakdown", {}), Mapping) else ()
                ),
            ),
        )
        all_channel_ranges = (*representatives, *alternatives)
        semantic_by_obligation[obligation.id] = list(all_channel_ranges)
        ctx.trace.record(
            "initial_file_candidates_scored",
            {
                "obligation_id": obligation.id,
                "candidate_file_count": len(file_groups),
                "file_limit_applied": False,
                "representative_count": len(representatives),
                "alternative_count": len(alternatives),
                "candidate_range_count": len(all_channel_ranges),
                "representative_file_count": _unique_result_path_count(representatives),
                "alternative_file_count": _unique_result_path_count(alternatives),
                "dense_input_count": len(response.payload.get("breakdown", {}).get("dense", ())),
                "sparse_input_count": len(response.payload.get("breakdown", {}).get("sparse", ())),
                "candidate_disposition": "all channel ranges continue to global exact-range deduplication",
                "file_groups": list(file_groups),
            },
        )

    all_results = [
        (obligation.id, origin, rank, item)
        for obligation in repository_obligations
        for origin, values in (
            ("exact_prompt_anchor", exact_prompt_seeds.get(obligation.id, ())),
            ("qdrant_all_channels", semantic_by_obligation.get(obligation.id, ())),
        )
        for rank, item in enumerate(values, start=1)
    ]
    submitted_ranges = [
        {"file": item.get("path"), "line_start": item.get("line_start"), "line_end": item.get("line_end")}
        for _obligation_id, _origin, _rank, item in all_results
        if item.get("path") and item.get("line_start")
    ]
    ranges = list({(str(item["file"]), int(item["line_start"]), int(item["line_end"])): item for item in submitted_ranges}.values())
    ctx.trace.record(
        "initial_exact_ranges_deduplicated",
        {
            "input_range_count": len(submitted_ranges),
            "unique_range_count": len(ranges),
            "duplicate_range_count": len(submitted_ranges) - len(ranges),
            "input_file_count": len({str(item["file"]) for item in submitted_ranges}),
            "unique_file_count": len({str(item["file"]) for item in ranges}),
            "ranges": ranges,
        },
    )
    range_nodes: dict[tuple[str, int, int], tuple[dict[str, Any], ...]] = {
        (str(item["file"]), int(item["line_start"]), int(item["line_end"])): ()
        for item in ranges
    }
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
            range_nodes[key] = select_range_candidate_owners(
                nodes,
                line_start=key[1],
                line_end=key[2],
            )
        resolution_rows = [
            {
                "path": path,
                "line_start": line_start,
                "line_end": line_end,
                "owner_count": len(nodes),
                "owners": [
                    {
                        "node_id": str(node.get("id") or ""),
                        "kind": str(node.get("kind") or ""),
                        "symbol": str(node.get("qualified_name") or node.get("name") or ""),
                        "line_start": int(node.get("line_start") or 0),
                        "line_end": int(node.get("line_end") or 0),
                    }
                    for node in nodes
                ],
            }
            for (path, line_start, line_end), nodes in range_nodes.items()
        ]
        ctx.trace.record(
            "initial_codegraph_ranges_resolved",
            {
                "requested_range_count": len(ranges),
                "returned_range_count": len(response.payload.get("results", ())),
                "resolved_range_count": sum(bool(row["owner_count"]) for row in resolution_rows),
                "unresolved_range_count": sum(not row["owner_count"] for row in resolution_rows),
                "single_owner_range_count": sum(row["owner_count"] == 1 for row in resolution_rows),
                "multi_owner_range_count": sum(row["owner_count"] > 1 for row in resolution_rows),
                "owner_snippet_count": sum(int(row["owner_count"]) for row in resolution_rows),
                "file_count": len({row["path"] for row in resolution_rows}),
                "batch_diagnostics": dict(response.payload.get("batch_diagnostics", {})),
                "ranges": resolution_rows,
            },
        )

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
    structural_exact_anchor_snippet_count = len(raw_observations)
    for obligation_id, origin, rank, result in all_results:
        key = (str(result.get("path") or ""), int(result.get("line_start") or 0), int(result.get("line_end") or 0))
        observations = observation_from_result(
            result,
            obligation_id=obligation_id,
            query_id=f"{_file_group_result_origin(result, origin)}:{obligation_id}",
            rank=int(result.get("file_group_rank") or rank),
            retriever=_file_group_result_origin(result, origin),
            nodes=range_nodes.get(key, ()),
            exact_anchor=str(result.get("exact_prompt_anchor") or "") if origin == "exact_prompt_anchor" else "",
        )
        raw_observations.extend(observations)
    canonical_snippets, canonicalization_decisions = canonicalize_observations(raw_observations)
    ctx.trace.record(
        "initial_snippets_canonicalized",
        {
            **_aggregation_trace_payload(
                input_observations=raw_observations,
                output_observations=canonical_snippets,
                decisions=canonicalization_decisions,
                limit=0,
                per_file_limit=0,
            ),
            "exact_anchor_snippet_count": structural_exact_anchor_snippet_count,
            "exact_prompt_seed_snippet_count": (
                sum(origin == "exact_prompt_anchor" for _obligation_id, origin, _rank, _item in all_results)
            ),
            "channel_range_occurrence_count": len(all_results),
            "canonical_file_count": len({item.handle.path for item in canonical_snippets}),
            "canonicalization_pass_count": 1,
            "canonical_disposition": "shared immutable candidate pool for file admission and owner comparison",
        },
    )

    file_ranking = rank_initial_files(canonical_snippets)
    admission = fit_initial_owner_comparison_admission(
        obligation_descriptions={item.id: item.description for item in repository_obligations},
        observations=canonical_snippets,
        ranked_paths=file_ranking.ranked_paths,
        preferred_input_chars=ctx.config.preferred_initial_owner_comparison_input_chars,
        max_input_chars=ctx.config.max_initial_owner_comparison_input_chars,
        max_files=max(1, len(file_ranking.ranked_paths)),
        max_selected=ctx.config.max_discovery_observations,
    )
    admitted_path_keys = {path.casefold() for path in admission.admitted_paths}
    file_admission_decisions = tuple(
        {
            "observation_id": item.id,
            "path": item.handle.path,
            "symbol": item.handle.symbol,
            "reason": "file_not_admitted",
        }
        for item in canonical_snippets
        if item.handle.path.casefold() not in admitted_path_keys
    )
    ctx.trace.record(
        "initial_files_admitted",
        {
            "input_snippet_count": len(canonical_snippets),
            "input_file_count": len(file_ranking.ranked_paths),
            "admitted_file_count": len(admission.admitted_paths),
            "admitted_paths": list(admission.admitted_paths),
            "coverage_reserved_paths": [],
            "excluded_file_count": len(admission.excluded_paths),
            "excluded_paths": list(admission.excluded_paths),
            "participating_candidate_count": admission.candidate_count,
            "comparison_total_input_chars": admission.total_input_chars,
            "comparison_preferred_input_chars": ctx.config.preferred_initial_owner_comparison_input_chars,
            "comparison_input_char_budget": ctx.config.max_initial_owner_comparison_input_chars,
            "file_limit": 0,
            "admission_limit": "ranked_quality_prefix_under_preferred_input_chars",
            "stopping_reason": admission.stopping_reason,
            "stopped_at_path": admission.stopped_at_path,
            "path_decisions": list(admission.path_decisions),
            "ranking": list(file_ranking.path_details),
            "nonadmitted_disposition": "deferred",
        },
    )
    owner_comparison = compare_initial_owners(
        llm_config=ctx.config.llm_config,
        obligation_descriptions={item.id: item.description for item in repository_obligations},
        observations=canonical_snippets,
        admitted_groups=admission.admitted_groups,
        max_input_chars=ctx.config.max_initial_owner_comparison_input_chars,
        max_selected=ctx.config.max_discovery_observations,
        trace=ctx.trace,
    )
    initial_observations = owner_comparison.selected
    ctx.trace.record(
        "round_zero_snippets_selected",
        {
            "input_snippet_count": admission.candidate_count,
            "input_file_count": len(admission.admitted_paths),
            "output_snippet_count": len(initial_observations),
            "output_file_count": len({item.handle.path for item in initial_observations}),
            "global_limit": ctx.config.max_discovery_observations,
            "per_file_limit": 0,
            "per_file_selection_policy": "grouped_primary_plus_semantically_distinct_additional_owners",
            "selection_method": "initial_owner_comparison_global_semantic_selection",
            "post_comparison_reducer_applied": False,
            "owner_comparison_dormant_count": len(owner_comparison.dormant),
            "output_snippets": [item.to_dict(include_text=False) for item in initial_observations],
        },
    )
    deferred_observations = _deferred_after_initial_owner_comparison(
        baseline_candidates=canonical_snippets,
        owner_comparison_selected=owner_comparison.selected,
        round_zero_selected=initial_observations,
        owner_comparison_dormant=owner_comparison.dormant,
        guardrail_decisions=file_admission_decisions,
    )
    ctx.trace.record(
        "discovery_observations_created",
        {
            "raw_count": len(raw_observations),
            "canonical_count": len(canonical_snippets),
            "raw_observations": [item.to_dict(include_text=False) for item in raw_observations],
            "aggregated_count": len(initial_observations),
            "deferred_count": len(deferred_observations),
            "deferred_observations": [
                item.to_dict(include_text=False) for item in deferred_observations
            ],
            "deferred_disposition": (
                "passed_to_controller_in_normal_execution_and_eligible_for_explicit_deferred_inspection; "
                "not inspected by the pre-qualification diagnostic stop"
            ),
            "observations": [item.to_dict(include_text=False) for item in initial_observations],
            "file_admission_decisions": list(file_admission_decisions),
            "lifecycle_partition_complete": (
                len(initial_observations) + len(deferred_observations) + len(owner_comparison.dormant)
                == len(canonical_snippets)
            ),
            "initial_owner_comparison_selected_count": len(owner_comparison.selected),
            "initial_owner_comparison_dormant_count": len(owner_comparison.dormant),
            "dormant_island_completion_enabled": ctx.config.dormant_island_completion_enabled,
        },
    )

    if ctx.config.stop_before_round_zero_qualification:
        disclosure = disclose_observations(
            initial_observations,
            workspace_root=ctx.config.workspace_root,
            outline_tool=structural_tools["structural_file_outline"],
            trace=ctx.trace,
            round_index=0,
        )
        tool_calls += disclosure.tool_calls
        preparation = prepare_qualification_request(
            user_request=state.user_input,
            cards=disclosure.cards,
            max_input_chars=ctx.config.max_qualification_input_chars,
        )
        ctx.trace.record(
            "round_zero_qualification_input_prepared",
            {
                "round": 0,
                "diagnostic_stop": True,
                "llm_called": False,
                "snippet_count": len(preparation.cards),
                "file_count": len({item.handle.path for item in preparation.cards}),
                "serialized_chars": preparation.serialized_chars,
                "total_input_chars": preparation.input_chars,
                "fixed_input_chars": preparation.fixed_input_chars,
                "source_capacity": preparation.source_capacity,
                "source_used_chars": sum(len(item.source_text) for item in preparation.cards),
                "input_char_budget": ctx.config.max_qualification_input_chars,
                "prompt": str(QUALIFICATION_PROMPT_PATH),
                "cards": [item.to_dict() for item in preparation.cards],
                "payload": dict(preparation.payload),
            },
        )
        return RetrievalResult(
            evidence=(),
            coverage_status="missing",
            sufficient=False,
            retrieval_summary={
                "retriever": "workspace",
                "diagnostic_stop": "before_round_zero_qualification",
                "request_analysis": intent_context.to_dict(),
                "retrieval_plan": {
                    "strategy": "qualification_first_controller_v1",
                    "obligations": [item.to_dict() for item in progress.values()],
                },
                "index_rebuilt": index_rebuilt,
                "index_document_count": index_document_count,
                "tool_calls": tool_calls,
                "round_zero_snippet_count": len(initial_observations),
                "round_zero_file_count": len({item.handle.path for item in initial_observations}),
                "initial_owner_comparison_usage": dict(owner_comparison.usage),
                "qualification_llm_called": False,
            },
            failures_or_fallbacks=("diagnostic_stop_before_round_zero_qualification",),
        )

    controller = run_retrieval_controller(
        ctx=ctx,
        user_request=state.user_input,
        obligations=repository_obligations,
        initial_observations=initial_observations,
        deferred_observations=deferred_observations,
        dormant_completion_observations=(
            owner_comparison.dormant if ctx.config.dormant_island_completion_enabled else ()
        ),
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
            file_traces=controller.file_traces,
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
    selected.extend(
        _selected_file_trace_evidence(
            consolidation,
            controller.file_traces,
            start_rank=len(selected) + 1,
            remaining=MAX_EVIDENCE - len(selected),
        )
    )
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
        "initial_owner_comparison_usage": dict(owner_comparison.usage),
        "initial_owner_comparison_serialized_chars": owner_comparison.serialized_chars,
        "initial_owner_comparison_group_count": owner_comparison.compared_group_count,
        "dormant_island_completion_enabled": ctx.config.dormant_island_completion_enabled,
        "coverage_usage": dict(controller.coverage_usage),
        "anchor_query_count": len(confirmations),
        "anchor_confirmations": [item.to_dict() for item in confirmations],
        "resolved_symbol_anchors": sorted({str(item.get("anchor_query") or "") for item in anchor_nodes}),
        "unresolved_symbol_anchors": list(unresolved_symbols),
        "ambiguous_symbol_anchors": list(ambiguous_symbols),
        "graph_edge_count": len(controller.edges),
        "file_trace_evidence": list(controller.file_traces),
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
    handle = card.handle
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
        obligation_ids=decision.supported_obligation_ids,
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


def _selected_file_trace_evidence(
    consolidation: Mapping[str, Any],
    file_traces: Sequence[Mapping[str, object]],
    *,
    start_rank: int,
    remaining: int,
) -> list[EvidenceItem]:
    accepted = {str(value) for value in consolidation.get("accepted_file_trace_ids", ())}
    values: list[EvidenceItem] = []
    for trace in file_traces:
        path = str(trace.get("path") or "")
        island_id = str(trace.get("source_island_id") or "unknown")
        trace_id = f"file_trace:{island_id}:{path}"
        if not path or trace_id not in accepted or len(values) >= remaining:
            continue
        source_path = str(trace.get("source_path") or "")
        relationship = "/".join(str(value) for value in trace.get("relationship_kinds", ()) if str(value)) or "structural"
        values.append(
            EvidenceItem(
                source_category=SourceCategory.SOURCE_CODE,
                source_id=f"workspace-file:{path}",
                snippet=str(trace.get("reason") or ""),
                rank=start_rank + len(values),
                metadata={
                    "evidence_kind": "file_trace",
                    "path": path,
                    "source_path": source_path,
                    "relationship": relationship,
                    "claim_supported": "This file is structurally connected to the unresolved path; it does not prove behavior inside the file.",
                },
            )
        )
    return values


def _initial_sparse_query(
    obligation: Any,
    *,
    exact_repository_symbols: set[str],
) -> str:
    """Use only exact-CodeGraph-confirmed identifiers for lexical retrieval.

    The dense channel keeps the complete stage/obligation question.  This
    companion deliberately excludes example variables, literals, and proposed
    names even when they occur literally in the issue.
    """
    return " ".join(_repository_sparse_anchors(obligation, exact_repository_symbols)).strip()


def _file_group_initial_results(
    payload: Mapping[str, Any],
    *,
    limit: int,
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    """Fuse dense/sparse file ranks while preserving each channel's owner candidate.

    Qdrant's native RRF operates on chunks, so a file with many similar chunks
    can push other files down before a later path decision. Initial discovery
    instead gives each path one rank per channel. The first dense and sparse
    chunks are returned separately from the remaining ranges for traceability;
    the canonical-pool caller retains both collections without admitting files.
    """
    breakdown = payload.get("breakdown", {})
    if not isinstance(breakdown, Mapping):
        breakdown = {}
    dense = tuple(dict(item) for item in breakdown.get("dense", ()) if isinstance(item, Mapping))
    sparse = tuple(dict(item) for item in breakdown.get("sparse", ()) if isinstance(item, Mapping))
    if not dense and not sparse:
        native = tuple(
            dict(item) for item in payload.get("results", ()) if isinstance(item, Mapping)
        )[:limit]
        return native, (), tuple(
            {
                "file_group_rank": rank,
                "path": str(item.get("path") or ""),
                "file_group_score": float(item.get("score") or 0.0),
                "dense_rank": None,
                "sparse_rank": None,
                "fallback_native_hybrid": True,
            }
            for rank, item in enumerate(native, start=1)
        )

    dense_by_path = _channel_results_by_path(dense)
    sparse_by_path = _channel_results_by_path(sparse)
    dense_file_ranks = {path: rank for rank, path in enumerate(dense_by_path, start=1)}
    sparse_file_ranks = {path: rank for rank, path in enumerate(sparse_by_path, start=1)}
    paths = ordered_unique((*dense_by_path.keys(), *sparse_by_path.keys()))
    scored_paths = sorted(
        paths,
        key=lambda path: (
            -_file_rrf_score(dense_file_ranks.get(path), sparse_file_ranks.get(path)),
            min(dense_file_ranks.get(path, 10**9), sparse_file_ranks.get(path, 10**9)),
            path,
        ),
    )[:limit]

    representatives: list[dict[str, Any]] = []
    held: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    for file_group_rank, path in enumerate(scored_paths, start=1):
        dense_values = dense_by_path.get(path, ())
        sparse_values = sparse_by_path.get(path, ())
        group_score = _file_rrf_score(dense_file_ranks.get(path), sparse_file_ranks.get(path))
        representative_keys: set[tuple[str, int, int]] = set()
        representative_records: list[dict[str, Any]] = []
        for channel, values, file_rank in (
            ("dense", dense_values, dense_file_ranks.get(path)),
            ("sparse", sparse_values, sparse_file_ranks.get(path)),
        ):
            if not values:
                continue
            result = _annotate_file_group_result(
                values[0],
                channel=channel,
                channel_file_rank=file_rank or 0,
                file_group_rank=file_group_rank,
                file_group_score=group_score,
            )
            key = _result_range_key(result)
            if key not in representative_keys:
                representatives.append(result)
                representative_keys.add(key)
            representative_records.append(
                {
                    "channel": channel,
                    "channel_file_rank": file_rank,
                    "line_start": int(result.get("line_start") or 0),
                    "line_end": int(result.get("line_end") or 0),
                }
            )
        held_keys = set(representative_keys)
        for channel, values, file_rank in (
            ("dense", dense_values, dense_file_ranks.get(path)),
            ("sparse", sparse_values, sparse_file_ranks.get(path)),
        ):
            for alternative in values[1:]:
                alternative_key = _result_range_key(alternative)
                if alternative_key in held_keys:
                    continue
                held.append(
                    _annotate_file_group_result(
                        alternative,
                        channel=channel,
                        channel_file_rank=file_rank or 0,
                        file_group_rank=file_group_rank,
                        file_group_score=group_score,
                    )
                )
                held_keys.add(alternative_key)
        groups.append(
            {
                "file_group_rank": file_group_rank,
                "path": path,
                "file_group_score": round(group_score, 6),
                "dense_file_rank": dense_file_ranks.get(path),
                "sparse_file_rank": sparse_file_ranks.get(path),
                "dense_chunk_count": len(dense_values),
                "sparse_chunk_count": len(sparse_values),
                "representatives": representative_records,
            }
        )
    return tuple(representatives), tuple(held), tuple(groups)


def _channel_results_by_path(
    values: Sequence[Mapping[str, Any]],
) -> dict[str, tuple[dict[str, Any], ...]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in values:
        path = str(item.get("path") or "").replace("\\", "/")
        if not path:
            continue
        grouped.setdefault(path, []).append(dict(item))
    return {path: tuple(items) for path, items in grouped.items()}


def _file_rrf_score(dense_rank: int | None, sparse_rank: int | None) -> float:
    return sum(1.0 / (rank + 1.0) for rank in (dense_rank, sparse_rank) if rank is not None)


def _annotate_file_group_result(
    item: Mapping[str, Any],
    *,
    channel: str,
    channel_file_rank: int,
    file_group_rank: int,
    file_group_score: float,
) -> dict[str, Any]:
    return {
        **dict(item),
        "retrieval_channel": channel,
        "channel_file_rank": channel_file_rank,
        "file_group_rank": file_group_rank,
        "file_group_score": file_group_score,
        "score": file_group_score,
    }


def _result_range_key(item: Mapping[str, Any]) -> tuple[str, int, int]:
    return (
        str(item.get("path") or "").replace("\\", "/").casefold(),
        int(item.get("line_start") or 0),
        int(item.get("line_end") or item.get("line_start") or 0),
    )


def _file_group_result_origin(item: Mapping[str, Any], fallback: str) -> str:
    channel = str(item.get("retrieval_channel") or "").strip()
    return f"qdrant_file_group_{channel}" if channel else fallback


_REPOSITORY_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _repository_sparse_anchors(obligation: Any, exact_repository_symbols: set[str]) -> tuple[str, ...]:
    """Return concrete, nontrivial symbol anchors that CodeGraph resolved."""
    return ordered_unique(
        value
        for value in obligation.anchor_refs
        if value in exact_repository_symbols
        and len(value) >= 3
        and _REPOSITORY_IDENTIFIER.fullmatch(value) is not None
    )


def _excluded_sparse_anchor_refs(obligation: Any, exact_repository_symbols: set[str]) -> tuple[str, ...]:
    return tuple(
        value
        for value in obligation.anchor_refs
        if value not in _repository_sparse_anchors(obligation, exact_repository_symbols)
    )


def _channel_result_summary(values: object) -> list[dict[str, object]]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return []
    return [
        {
            "rank": index,
            "path": str(item.get("path") or "").replace("\\", "/"),
            "line_start": int(item.get("line_start") or 0),
            "line_end": int(item.get("line_end") or item.get("line_start") or 0),
            "score": round(float(item.get("score") or 0.0), 4),
            "matched_terms": [str(value) for value in item.get("matched_terms", ()) if str(value)],
        }
        for index, item in enumerate(values, start=1)
        if isinstance(item, Mapping)
    ]


def _unique_result_path_count(values: object) -> int:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return 0
    return len({
        str(item.get("path") or "").replace("\\", "/")
        for item in values
        if isinstance(item, Mapping) and str(item.get("path") or "").strip()
    })


def _deferred_after_initial_owner_comparison(
    *,
    baseline_candidates: Sequence[DiscoveryObservation],
    owner_comparison_selected: Sequence[DiscoveryObservation],
    round_zero_selected: Sequence[DiscoveryObservation],
    owner_comparison_dormant: Sequence[DiscoveryObservation],
    guardrail_decisions: Sequence[Mapping[str, Any]],
) -> tuple[DiscoveryObservation, ...]:
    """Retain every plausible snippet removed by a deterministic boundary.

    Selected owners can originate only from held ranges and therefore may not
    exist in the representative-only baseline pool.  They remain plausible
    when the round-zero guardrail removes them and must become deferred rather
    than disappearing into the trace.  Owners explicitly left unselected by
    owner comparison remain dormant and are intentionally excluded here.
    """
    candidates_by_id: dict[str, DiscoveryObservation] = {}
    for candidate in (*baseline_candidates, *owner_comparison_selected):
        current = candidates_by_id.get(candidate.id)
        candidates_by_id[candidate.id] = (
            merge_observation_pair(current, candidate) if current is not None else candidate
        )
    selected_ids = {item.id for item in round_zero_selected}
    dormant_ids = {item.id for item in owner_comparison_dormant}
    admission_reason_by_id = {
        str(item.get("observation_id") or ""): str(item.get("reason") or "")
        for item in guardrail_decisions
    }
    return tuple(
        replace(candidate, admission_reason=admission_reason_by_id.get(candidate.id, ""))
        for candidate in candidates_by_id.values()
        if candidate.id not in selected_ids and candidate.id not in dormant_ids
    )


def _aggregation_trace_payload(
    *,
    input_observations: Sequence[DiscoveryObservation],
    output_observations: Sequence[DiscoveryObservation],
    decisions: Sequence[Mapping[str, Any]],
    limit: int,
    per_file_limit: int,
) -> dict[str, Any]:
    reason_counts: dict[str, int] = {}
    for decision in decisions:
        reason = str(decision.get("reason") or "unknown")
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
    return {
        "input_snippet_count": len(input_observations),
        "input_file_count": len({item.handle.path for item in input_observations}),
        "output_snippet_count": len(output_observations),
        "output_file_count": len({item.handle.path for item in output_observations}),
        "removed_or_merged_count": len(input_observations) - len(output_observations),
        "global_limit": limit,
        "per_file_limit": per_file_limit,
        "decision_reason_counts": reason_counts,
        "decisions": [dict(item) for item in decisions],
        "output_snippets": [item.to_dict(include_text=False) for item in output_observations],
    }


def _skipped_consolidation(states: Sequence[ObligationProgress]) -> dict[str, Any]:
    return {
        "strategy": "explicitly_skipped_for_candidate_pool_diagnostics",
        "skipped": True,
        "llm_calls": 0,
        "accepted_candidate_ids": [],
        "accepted_file_trace_ids": [],
        "accepted_ids_by_obligation": {},
        "obligation_statuses": {item.obligation.id: "unresolved" for item in states},
        "unresolved_reasons": {item.obligation.id: "Final evidence selection was explicitly disabled." for item in states},
        "usage": {},
    }
