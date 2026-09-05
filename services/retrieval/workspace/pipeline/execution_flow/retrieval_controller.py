from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Callable, Mapping, Sequence

from services.intent.models import EvidenceObligation
from services.retrieval.workspace.pipeline.execution_flow.coverage_evaluation import (
    CoverageBatch,
    ObligationCoverage,
    evaluate_coverage,
)
from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import (
    DiscoveryObservation,
    merge_observation_pair,
)
from services.retrieval.workspace.pipeline.execution_flow.evidence_islands import (
    IslandSelection,
    build_semantic_islands,
)
from services.retrieval.workspace.pipeline.execution_flow.evidence_qualification import (
    QualificationDecision,
    QualificationReuseCache,
    qualify_cards,
)
from services.retrieval.workspace.pipeline.execution_flow.dormant_island_completion import (
    announce_dormant_completion_promotion,
    completion_observation,
    qualify_dormant_island_completion,
    select_dormant_island_completions,
)
from services.retrieval.workspace.pipeline.execution_flow.file_trace_evidence import (
    FileTraceSeed,
    build_file_trace_evidence,
)
from services.retrieval.workspace.pipeline.execution_flow.island_frontiers import IslandFrontierLedger
from services.retrieval.workspace.pipeline.execution_flow.owner_representation import (
    OwnerRepresentationSelection,
    build_owner_representations,
)
from services.retrieval.workspace.pipeline.execution_flow.actions.catalogue_and_execution import (
    ExpandRelationship,
    InspectDeferredObservation,
    InspectDormantFileAlternatives,
    InspectOwnerContinuation,
    InspectVerifiedLead,
    ExpandWithinFileHandoff,
    action_to_dict,
    enumerate_actions,
    execute_action,
)
from services.retrieval.workspace.pipeline.execution_flow.actions.policy import (
    ActionPool,
    ActionPurpose,
    action_pool,
)
from services.retrieval.workspace.pipeline.execution_flow.actions.scheduler import (
    _action_effect,
    _action_root_id,
    _action_scope_id,
    _has_specific_exact_anchors,
    schedule_round_actions,
    select_ordinary_backfill_action,
)
from services.retrieval.workspace.pipeline.execution_flow.actions.dormant_file_alternatives import (
    evaluate_dormant_file_qualification_gain,
)
from services.retrieval.workspace.pipeline.execution_flow.actions.pending_file_handoffs import (
    PendingFileHandoff,
    reconcile_pending_file_handoffs,
    retain_pending_file_handoffs,
)
from services.retrieval.workspace.pipeline.execution_flow.source_disclosure import DisclosureCard, disclose_observations
from services.retrieval.workspace.pipeline.execution_flow.structural_components import build_structural_components
from services.retrieval.workspace.tools import ToolRequest


from services.retrieval.workspace.pipeline.execution_flow.verified_leads import (
    MAX_VERIFIED_LEAD_EXECUTIONS, VerifiedLead, _discover_verified_leads,
    _verified_lead_to_dict, _select_verified_lead_actions, discover_qualified_file_leads,
    retain_verified_lead, verified_lead_priority,
)


@dataclass(frozen=True)
class ControllerResult:
    observations: tuple[DiscoveryObservation, ...]
    cards: tuple[DisclosureCard, ...]
    decisions: tuple[QualificationDecision, ...]
    candidates: tuple[Any, ...]
    coverage: tuple[ObligationCoverage, ...]
    islands: IslandSelection
    edges: tuple[dict[str, Any], ...]
    tool_calls: int
    rounds: int
    stop_reason: str
    qualification_usage: Mapping[str, int]
    coverage_usage: Mapping[str, int]
    file_traces: tuple[dict[str, object], ...]




def run_retrieval_controller(
    *,
    ctx: Any,
    user_request: str,
    obligations: Sequence[EvidenceObligation],
    initial_observations: Sequence[DiscoveryObservation],
    deferred_observations: Sequence[DiscoveryObservation] = (),
    dormant_completion_observations: Sequence[DiscoveryObservation] = (),
    dormant_file_observations: Sequence[DiscoveryObservation] = (),
    structural_tools: Mapping[str, Any],
    qdrant_tool: Any,
    candidate_factory: Callable[[DiscoveryObservation, QualificationDecision, DisclosureCard], Any | None],
    candidate_payload: Callable[[Any], Mapping[str, Any]],
) -> ControllerResult:
    from services.retrieval.workspace.pipeline.execution_flow.action_novelty import RequestMemoizer

    structural_tools = RequestMemoizer().wrap_tools(structural_tools)
    # Dormant owner-comparison results are visible only to the bounded island
    # completion stage. With no qualification decision they cannot become
    # roots or ordinary scheduled actions.
    observations = {
        item.id: item
        for item in (*initial_observations, *deferred_observations, *dormant_completion_observations)
    }
    cards: dict[str, DisclosureCard] = {}
    decisions: dict[str, QualificationDecision] = {}
    qualification_cache = QualificationReuseCache()
    candidates: dict[str, Any] = {}
    all_edges: list[dict[str, Any]] = []
    file_trace_seeds: list[FileTraceSeed] = []
    attempted: set[str] = set()
    attempted_effects: set[tuple[str, ...]] = set()
    refined_paths: set[str] = set()
    tool_calls = 0
    qualification_usage = _zero_usage()
    coverage_usage = _zero_usage()
    completion_candidate_ids = {item.id for item in dormant_completion_observations}
    attempted_completion_target_ids: set[str] = set()
    successful_completion_source_ids: list[str] = []
    owner_representations: OwnerRepresentationSelection | None = None
    dormant_file_attempt_limit = 1
    dormant_second_opportunity_pending = False
    dormant_file_followup_floor = None

    def qualify(items: Sequence[DiscoveryObservation], round_index: int) -> None:
        nonlocal tool_calls
        if not items:
            return
        disclosure = disclose_observations(
            items,
            workspace_root=ctx.config.workspace_root,
            outline_tool=structural_tools["structural_file_outline"],
            trace=ctx.trace,
            round_index=round_index,
        )
        tool_calls += disclosure.tool_calls
        qualification = qualify_cards(
            llm_config=ctx.config.llm_config,
            user_request=user_request,
            cards=tuple(
                replace(card, previous_qualification={
                    "assessment": previous.assessment.to_dict(),
                    "rationale": previous.rationale.to_dict(),
                }) if (previous := decisions.get(card.observation_id)) is not None else card
                for card in disclosure.cards
            ),
            obligations=obligations,
            max_input_chars=ctx.config.max_qualification_input_chars,
            trace=ctx.trace,
            round_index=round_index,
            reuse_cache=qualification_cache,
        )
        rendered_cards = qualification.cards or disclosure.cards
        for card in rendered_cards:
            cards[card.observation_id] = card
            observations[card.observation_id] = replace(
                observations[card.observation_id],
                disclosure_status=card.mode,
            )
        ctx.trace.record(
            "disclosure_cards_created",
            {
                "round": round_index,
                "global_source_capacity": qualification.source_capacity,
                "cards": [
                    {
                        "observation_id": item.observation_id,
                        "mode": item.mode,
                        "handle": item.to_dict()["handle"],
                        "chars": len(item.source_text),
                        "allocated_chars": item.allocated_chars,
                        "used_chars": item.used_chars,
                        "owner_kind": item.owner_kind,
                        "owner_name": item.owner_name,
                        "owner_range": [item.owner_line_start, item.owner_line_end],
                        "outer_owner_range": [item.outer_owner_line_start, item.outer_owner_line_end],
                        "truncation_reason": item.truncation_reason,
                    }
                    for item in rendered_cards
                ],
            },
        )
        _add_usage(qualification_usage, qualification.usage)
        for decision in qualification.decisions:
            decisions[decision.observation_id] = decision
            if decision.assessment.is_retained:
                observation = observations[decision.observation_id]
                candidate = candidate_factory(observation, decision, cards[decision.observation_id])
                if candidate is not None:
                    payload = candidate_payload(candidate)
                    candidates[str(payload["candidate_id"])] = candidate
            else:
                for candidate_id, candidate in tuple(candidates.items()):
                    if str(candidate_payload(candidate).get("observation_id") or "") == decision.observation_id:
                        candidates.pop(candidate_id, None)

    def reevaluate_owner_representations(round_index: int) -> None:
        nonlocal owner_representations
        previous = owner_representations
        owner_representations = build_owner_representations(
            tuple(observations.values()),
            tuple(decisions.values()),
            previous=previous,
        )
        previous_by_group = {
            item.id: item.primary_observation_id for item in (previous.groups if previous else ())
        }
        ctx.trace.record(
            "owner_representations_evaluated",
            {
                "round": round_index,
                **owner_representations.to_dict(),
                "primary_changes": [
                    {
                        "group_id": item.id,
                        "path": item.path,
                        "obligation_id": item.obligation_id,
                        "previous_primary_observation_id": previous_by_group.get(item.id, ""),
                        "primary_observation_id": item.primary_observation_id,
                        "reason": item.election_reason,
                    }
                    for item in owner_representations.groups
                    if previous_by_group.get(item.id, "") != item.primary_observation_id
                ],
            },
        )

    qualify(tuple(initial_observations), 0)
    reevaluate_owner_representations(0)
    coverage = _evaluate(ctx, user_request, obligations, candidates, candidate_payload, round_index=0)
    _add_usage(coverage_usage, coverage.usage)
    islands = _build_islands(
        ctx, observations, decisions, cards, coverage.coverage, structural_tools,
        owner_representations=owner_representations,
        previous=None, round_index=0,
    )
    tool_calls += islands.tool_calls
    all_edges.extend(_represented_connector_edges(islands.edges))
    if not getattr(ctx.config, "adaptive_controller_enabled", True):
        stop_reason = "adaptive_controller_disabled_after_round_zero"
        ctx.trace.record(
            "retrieval_controller_bypassed",
            {
                "stop_reason": stop_reason,
                "rounds": 0,
                "tool_calls": tool_calls,
                "qualified_observation_count": len(decisions),
                "candidate_ids": sorted(candidates),
                "island_ids": [item.id for item in islands.islands],
                "deferred_observation_count": len(observations) - len(decisions),
            },
        )
        return ControllerResult(
            observations=tuple(observations.values()),
            cards=tuple(cards.values()),
            decisions=tuple(decisions.values()),
            candidates=tuple(candidates.values()),
            coverage=coverage.coverage,
            islands=islands,
            edges=tuple(_dedupe_edges(all_edges)),
            tool_calls=tool_calls,
            rounds=0,
            stop_reason=stop_reason,
            qualification_usage=dict(qualification_usage),
            coverage_usage=dict(coverage_usage),
            file_traces=(),
        )
    stop_reason = "all_required_obligations_covered" if _required_covered(obligations, coverage.coverage) else ""
    completed_rounds = 0
    allow_exact_followup_round = False
    pending_maturation_child_roots: set[str] = set()
    pending_verified_leads: dict[str, VerifiedLead] = {}
    executed_verified_lead_node_ids: set[str] = set()
    verified_lead_executions = 0
    seen_raw_source_ids: set[str] = set()
    pending_file_handoffs: tuple[PendingFileHandoff, ...] = ()
    frontier_ledger = IslandFrontierLedger()

    def discover_qualified_leads(changed_ids: Sequence[str], round_index: int) -> bool:
        nonlocal tool_calls
        leads, audit, calls = discover_qualified_file_leads(
            round_index=round_index, changed_observation_ids=changed_ids,
            observations=observations, decisions=decisions, cards=cards, coverage=coverage.coverage,
            pending_node_ids=set(pending_verified_leads), executed_node_ids=executed_verified_lead_node_ids,
            structural_tools=structural_tools, workspace_root=ctx.config.workspace_root, trace=ctx.trace,
            pending_leads=pending_verified_leads,
        )
        tool_calls += calls
        for lead in leads:
            retain_verified_lead(pending_verified_leads, lead)
        ctx.trace.record("qualified_structural_file_leads_evaluated", {
            "round": round_index, "audit": audit, "new_lead_count": len(leads),
            "leads": [_verified_lead_to_dict(lead) for lead in leads], "tool_calls": calls,
            "execution_cap": MAX_VERIFIED_LEAD_EXECUTIONS,
        })
        return bool(leads)

    discover_qualified_leads(tuple(item.id for item in initial_observations), 0)

    for round_index in range(1, ctx.config.max_exploration_rounds + 1):
        if stop_reason:
            break
        verified_lead_round_available = (
            bool(pending_verified_leads)
            and verified_lead_executions < MAX_VERIFIED_LEAD_EXECUTIONS
        )
        if round_index == 4 and not (allow_exact_followup_round or verified_lead_round_available):
            stop_reason = "three_round_budget_complete"
            break
        completed_rounds = round_index
        ctx.trace.record(
            "controller_round_started",
            {
                "round": round_index,
                "active_root_ids": list(islands.active_root_ids),
                "coverage": [item.to_dict() for item in coverage.coverage],
                "attempted_action_ids": sorted(attempted),
            },
        )
        catalogue = enumerate_actions(
            user_request=user_request,
            obligations=obligations,
            coverage=coverage.coverage,
            observations=tuple(observations.values()),
            dormant_file_observations=dormant_file_observations,
            decisions=tuple(decisions.values()),
            cards=tuple(cards.values()),
            active_root_ids=islands.active_root_ids,
            observation_to_island=islands.observation_to_island,
            owner_representations=owner_representations,
            edge_capabilities_tool=structural_tools["structural_edge_capabilities"],
            file_nodes_tool=structural_tools["structural_resolve_file_nodes"],
            attempted_fingerprints=attempted,
            dormant_file_alternatives_enabled=bool(
                getattr(ctx.config, "dormant_file_alternatives_enabled", False)
            ),
            trace=ctx.trace,
            round_index=round_index,
        )
        tool_calls += catalogue.tool_calls
        pending_file_handoffs = reconcile_pending_file_handoffs(
            pending_file_handoffs,
            round_index=round_index,
            observations=observations,
            decisions=decisions,
            coverage=coverage.coverage,
            observation_to_island=islands.observation_to_island,
            active_island_ids=islands.active_island_ids,
            attempted_effects=attempted_effects,
        )
        verified_lead_selected = _select_verified_lead_actions(
            tuple(pending_verified_leads.values()),
            executed_count=verified_lead_executions,
            observation_to_island=islands.observation_to_island,
            limit=len(pending_verified_leads),
        )
        projected_actions = tuple(dict.fromkeys((
            *catalogue.actions,
            *verified_lead_selected,
            *(item.action for item in pending_file_handoffs),
        )))
        projected_frontiers = frontier_ledger.observe_catalogue(
            projected_actions,
            islands=islands,
            decisions=decisions,
            coverage=coverage.coverage,
            round_index=round_index,
        )
        ctx.trace.record(
            "island_frontiers_projected",
            {
                "round": round_index,
                "mode": "read_only",
                "catalogue_action_count": len(catalogue.actions),
                "projected_action_count": len(projected_actions),
                "frontier_count": len(projected_frontiers),
                "continuation_count": sum(len(item.continuations) for item in projected_frontiers),
                "available_persisted_continuation_count": sum(
                    1
                    for item in projected_frontiers
                    for continuation in item.continuations
                    if continuation.state == "available" and not continuation.present_in_catalogue
                ),
                "frontiers": [item.to_dict() for item in projected_frontiers],
            },
        )
        schedule_arguments = {
            "active_root_ids": islands.active_root_ids,
            "active_island_ids": islands.active_island_ids,
            "normal_limit": ctx.config.max_controller_actions_per_round,
            "round_index": round_index,
            "refined_paths": refined_paths,
            "attempted_action_ids": attempted,
            "attempted_effects": attempted_effects,
            "pending_maturation_child_roots": pending_maturation_child_roots,
            "blocked_maturation_root_ids": {
                lead.source_observation_id for lead in pending_verified_leads.values()
            },
            "verified_lead_actions": verified_lead_selected,
            "pending_file_handoffs": pending_file_handoffs,
            "continuation_priority_by_effect": frontier_ledger.ordinary_scheduling_signals(
                round_index=round_index,
            ),
            "dormant_file_attempt_limit": dormant_file_attempt_limit,
            "dormant_file_followup_floor": dormant_file_followup_floor,
        }
        schedule = schedule_round_actions(
            catalogue.actions,
            additional_ordinary_actions=frontier_ledger.persisted_available_ordinary_actions(),
            **schedule_arguments,
        )
        ctx.trace.record(
            "island_frontier_ordinary_schedule_created",
            {
                "round": round_index,
                "action_ids": [item.id for item in schedule.normal],
                "effects": [list(_action_effect(item)) for item in schedule.normal],
                "persisted_selected_action_ids": [
                    item.id
                    for item in schedule.normal
                    if (continuation := frontier_ledger.continuation_for_action(item.id)) is not None
                    and not continuation.present_in_catalogue
                ],
            },
        )
        normal_selected = schedule.normal
        deferred_file_seed_selected = schedule.deferred_file_rescue
        ordinary_owner_maturation_selected = tuple(
            item for item in schedule.normal
            if action_pool(item.purpose) is ActionPool.OWNER_MATURATION
        )
        maturation_selected = ordinary_owner_maturation_selected
        maturation_children: tuple[RetrievalAction, ...] = ()
        test_maturation_selected = schedule.test_maturation
        suppressed_ids = {item["action_id"] for item in schedule.suppressed}
        ctx.trace.record("verified_lead_scheduling", {
            "round": round_index, "executed_count": verified_lead_executions,
            "execution_cap": MAX_VERIFIED_LEAD_EXECUTIONS,
            "policy": "explicit_source_grounded_request_before_incidental_call",
            "ranked_pending": [_verified_lead_to_dict(lead) for lead in
                               sorted(pending_verified_leads.values(), key=verified_lead_priority)],
            "selected_node_ids": [action.target_node_id for action in schedule.verified_lead],
            "suppressed_actions": [item for item in schedule.suppressed
                                   if item["action_id"] in {action.id for action in verified_lead_selected}],
            "blocked_reason": "execution_cap_reached" if verified_lead_executions >= MAX_VERIFIED_LEAD_EXECUTIONS else "",
        })
        for action in verified_lead_selected:
            if action.id in suppressed_ids:
                pending_verified_leads.pop(action.target_node_id, None)
        verified_lead_selected = schedule.verified_lead
        selected = schedule.selected
        selected_continuations = [frontier_ledger.continuation_for_action(item.id) for item in selected]
        ctx.trace.record(
            "island_frontier_schedule_audit",
            {
                "round": round_index,
                "mode": "read_only",
                "selected_action_count": len(selected),
                "mapped_selected_action_count": sum(item is not None for item in selected_continuations),
                "all_selected_actions_mapped": all(item is not None for item in selected_continuations),
                "selected": [
                    {
                        "action_id": action.id,
                        "continuation": continuation.to_dict() if continuation is not None else None,
                    }
                    for action, continuation in zip(selected, selected_continuations)
                ],
            },
        )
        pending_file_handoffs = retain_pending_file_handoffs(
            pending_file_handoffs,
            catalogue.actions,
            selected,
            round_index=round_index,
            observations=observations,
            decisions=decisions,
            coverage=coverage.coverage,
            observation_to_island=islands.observation_to_island,
            active_island_ids=islands.active_island_ids,
            attempted_effects=attempted_effects,
        )
        ctx.trace.record(
            "pending_file_handoffs_updated",
            {
                "round": round_index,
                "policy": "test_source_only_max_two_one_per_island_ttl_two_rounds",
                "selected_action_ids": [item.id for item in schedule.pending_file_handoff],
                "pending": [
                    {
                        "action": action_to_dict(item.action),
                        "discovered_round": item.discovered_round,
                        "catalogue_rank": item.catalogue_rank,
                    }
                    for item in pending_file_handoffs
                ],
            },
        )
        if schedule.suppressed:
            ctx.trace.record("controller_actions_suppressed", {"round": round_index, "actions": list(schedule.suppressed)})
        if not selected:
            stop_reason = "no_executable_action"
            break
        ctx.trace.record(
            "controller_actions_selected",
            {
                "round": round_index,
                "actions": [action_to_dict(item) for item in selected],
                "normal_action_count": len(normal_selected),
                "deferred_file_seed_action_count": len(deferred_file_seed_selected),
                "maturation_action_count": len(maturation_selected),
                "ordinary_owner_maturation_action_count": len(ordinary_owner_maturation_selected),
                "maturation_child_action_count": len(maturation_children),
                "test_maturation_action_count": len(test_maturation_selected),
                "verified_lead_action_count": len(verified_lead_selected),
                "verified_lead_pending_count": len(pending_verified_leads),
                "verified_lead_execution_count": verified_lead_executions,
                "pending_file_handoff_action_count": len(schedule.pending_file_handoff),
                "scope_assignments": [
                    {
                        "slot": index,
                        "scope_id": _action_scope_id(item),
                        "reason": (
                            "distinct_island_or_frontier"
                            if _action_scope_id(item) not in {
                                _action_scope_id(prior) for prior in selected[: index - 1]
                            }
                            else "unused_slot_returned_to_best_scope"
                        ),
                    }
                    for index, item in enumerate(selected, start=1)
                ],
                "selection_policy": "two_normal_island_actions_plus_one_isolated_deferred_file_seed_action_plus_one_maturation_action_plus_one_test_maturation_action_plus_one_verified_lead_action",
                "suppressed_action_count": len(schedule.suppressed),
                "suppressed_actions": list(schedule.suppressed),
            },
        )
        previous_candidate_ids = set(candidates)
        previous_promoted_ids = {
            observation_id for observation_id, decision in decisions.items() if decision.assessment.is_retained
        }
        previous_coverage = {item.obligation_id: item.status for item in coverage.coverage}
        changed: list[DiscoveryObservation] = []
        round_new_raw_source_ids: set[str] = set()
        round_materialization_losses: list[dict[str, Any]] = []
        matured_observation_ids: set[str] = set()
        action_queue = list(selected)
        round_dormant_actions: list[InspectDormantFileAlternatives] = []
        ordinary_action_ids = {action.id for action in normal_selected}
        productive_ordinary_scopes: set[str] = set()
        productive_ordinary_count = 0
        ordinary_attempt_count = 0
        max_ordinary_attempts = max(
            len(normal_selected),
            ctx.config.max_controller_actions_per_round * 2,
        )
        action_index = 0
        while action_index < len(action_queue):
            action = action_queue[action_index]
            action_index += 1
            attempted.add(action.id)
            attempted_effects.add(_action_effect(action))
            if isinstance(action, InspectDormantFileAlternatives):
                round_dormant_actions.append(action)
                if dormant_file_followup_floor is None:
                    dormant_file_followup_floor = action.hypothesis_strength
            if isinstance(action, ExpandWithinFileHandoff):
                refined_paths.add(action.path.casefold())
            execution = execute_action(
                action,
                observations=tuple(dict.fromkeys((
                    *observations.values(),
                    *dormant_file_observations,
                ))),
                relationship_tool=structural_tools["structural_expand_relationships"],
                qdrant_tool=qdrant_tool,
                resolve_ranges_tool=structural_tools["structural_resolve_ranges"],
                exact_symbol_tool=structural_tools["structural_find_exact_symbol"],
                trace=ctx.trace,
                round_index=round_index,
            )
            if action_pool(action.purpose) in {ActionPool.OWNER_MATURATION, ActionPool.TEST_MATURATION}:
                pending_maturation_child_roots.update(item.id for item in execution.observations)
                matured_observation_ids.update(item.id for item in execution.observations)
            if action in maturation_selected and _action_root_id(action) in pending_maturation_child_roots:
                pending_maturation_child_roots.discard(_action_root_id(action))
            if isinstance(action, InspectVerifiedLead):
                pending_verified_leads.pop(action.target_node_id, None)
                executed_verified_lead_node_ids.add(action.target_node_id)
                verified_lead_executions += 1
            tool_calls += execution.tool_calls
            new_raw_ids = set(execution.raw_source_ids) - seen_raw_source_ids
            round_new_raw_source_ids.update(new_raw_ids)
            seen_raw_source_ids.update(execution.raw_source_ids)
            round_materialization_losses.extend(
                item for item in execution.materialization_losses
                if str(item.get("raw_source_id") or "") in new_raw_ids
            )
            all_edges.extend(execution.edges)
            if isinstance(action, ExpandRelationship) and action.seed_kind == "file" and execution.edges:
                source_path = observations.get(action.root_observation_id, None)
                source_path = source_path.handle.path if source_path is not None else ""
                for endpoint in execution.observations:
                    if endpoint.handle.path and endpoint.handle.path.casefold() != source_path.casefold():
                        file_trace_seeds.append(
                            FileTraceSeed(
                                path=endpoint.handle.path,
                                source_path=source_path,
                                source_observation_id=action.root_observation_id,
                                endpoint_observation_id=endpoint.id,
                                endpoint_symbol=endpoint.handle.symbol,
                                action_id=action.id,
                                obligation_id=action.obligation_id,
                                relationship_direction=action.direction,
                                relationship_kinds=action.edge_kinds,
                                obligation_ids=tuple(dict.fromkeys((
                                    *action.obligation_ids,
                                    *observations[action.root_observation_id].obligation_ids,
                                ))),
                                connection_summary=_file_connection_summary(
                                    execution.edges, source_path, endpoint.handle.path,
                                ),
                            )
                        )
            if (
                isinstance(action, InspectVerifiedLead)
                and action.purpose is ActionPurpose.STRUCTURAL_CHILD_HANDOFF
                and execution.observations
            ):
                source = observations.get(action.source_observation_id)
                if source is not None and source.handle.path.casefold() != action.target_path.casefold():
                    endpoint = execution.observations[0]
                    file_trace_seeds.append(FileTraceSeed(
                        path=action.target_path,
                        source_path=source.handle.path,
                        source_observation_id=action.source_observation_id,
                        endpoint_observation_id=endpoint.id,
                        endpoint_symbol=action.target_symbol,
                        action_id=action.id,
                        obligation_id=action.obligation_id,
                        relationship_direction="outgoing",
                        relationship_kinds=("calls",),
                        obligation_ids=source.obligation_ids,
                        connection_summary={
                            "source_path": source.handle.path,
                            "destination_path": action.target_path,
                            "direct_call_site_count": 1,
                            "localized_source_owners": [source.handle.symbol],
                            "destination_symbols": [{
                                "symbol": action.target_symbol,
                                "call_site_count": 1,
                                "call_lines": [],
                            }],
                            "provenance": "maturation_visible_exact_call",
                        },
                    ))
            for observation in execution.observations:
                existing = observations.get(observation.id)
                if existing == observation and not isinstance(action, (InspectDeferredObservation, InspectDormantFileAlternatives, InspectOwnerContinuation)):
                    continue
                source_replaced = False
                if existing is None or isinstance(action, (InspectDeferredObservation, InspectDormantFileAlternatives, InspectOwnerContinuation)):
                    updated = observation
                else:
                    try:
                        updated = merge_observation_pair(existing, observation)
                    except ValueError:
                        # A later path-local search can resolve the same logical observation ID
                        # to a more specific structural range.  It is a refinement, not evidence
                        # that two unrelated sources should be merged.
                        updated = observation
                        source_replaced = True
                observations[observation.id] = updated
                changed.append(updated)
                if source_replaced:
                    ctx.trace.record(
                        "controller_observation_source_replaced",
                        {
                            "round": round_index,
                            "action_id": action.id,
                            "observation_id": observation.id,
                            "previous_path": existing.handle.path,
                            "previous_range": [existing.handle.line_start, existing.handle.line_end],
                            "replacement_path": observation.handle.path,
                            "replacement_range": [observation.handle.line_start, observation.handle.line_end],
                        },
                    )
            ctx.trace.record(
                "controller_action_executed",
                {
                    "round": round_index,
                    "action": action_to_dict(action),
                    "status": execution.status,
                    "endpoint_observation_ids": [item.id for item in execution.observations],
                    "edge_count": len(execution.edges),
                    "raw_source_count": len(execution.raw_source_ids),
                    "new_raw_source_count": len(new_raw_ids),
                    "materialized_snippet_count": len(execution.observations),
                    "materialization_losses": list(execution.materialization_losses),
                },
            )
            produced_result = bool(execution.observations or execution.edges or new_raw_ids)
            frontier_ledger.record_execution(action.id, produced_result=produced_result)
            if action.id in ordinary_action_ids:
                ordinary_attempt_count += 1
                if produced_result:
                    productive_ordinary_count += 1
                    productive_ordinary_scopes.add(_action_scope_id(action))
                elif (
                    ordinary_attempt_count < max_ordinary_attempts
                    and productive_ordinary_count < ctx.config.max_controller_actions_per_round
                ):
                    reserved_actions = action_queue[action_index:]
                    reserved_ordinary_scopes = {
                        _action_scope_id(item)
                        for item in reserved_actions
                        if item.id in ordinary_action_ids
                    }
                    replacement = select_ordinary_backfill_action(
                        catalogue.actions,
                        active_root_ids=islands.active_root_ids,
                        active_island_ids=islands.active_island_ids,
                        normal_limit=ctx.config.max_controller_actions_per_round,
                        round_index=round_index,
                        refined_paths=refined_paths,
                        attempted_action_ids={*attempted, *(item.id for item in reserved_actions)},
                        attempted_effects={
                            *attempted_effects,
                            *(_action_effect(item) for item in reserved_actions),
                        },
                        pending_maturation_child_roots=pending_maturation_child_roots,
                        blocked_maturation_root_ids={
                            lead.source_observation_id for lead in pending_verified_leads.values()
                        },
                        pending_file_handoffs=pending_file_handoffs,
                        continuation_priority_by_effect=frontier_ledger.ordinary_scheduling_signals(
                            round_index=round_index,
                        ),
                        occupied_scope_ids={
                            *productive_ordinary_scopes,
                            *reserved_ordinary_scopes,
                        },
                    )
                    if replacement is not None:
                        action_queue.append(replacement)
                        ordinary_action_ids.add(replacement.id)
                    ctx.trace.record(
                        "controller_empty_ordinary_action_backfill",
                        {
                            "round": round_index,
                            "empty_action_id": action.id,
                            "empty_action_effect": list(_action_effect(action)),
                            "replacement_action": (
                                action_to_dict(replacement) if replacement is not None else None
                            ),
                            "ordinary_attempt_count": ordinary_attempt_count,
                            "ordinary_attempt_limit": max_ordinary_attempts,
                            "productive_ordinary_scope_count": len(productive_ordinary_scopes),
                            "productive_ordinary_action_count": productive_ordinary_count,
                            "productive_ordinary_slot_limit": ctx.config.max_controller_actions_per_round,
                        },
                    )
            if isinstance(action, InspectOwnerContinuation):
                ctx.trace.record(
                    "owner_continuation_executed",
                    {
                        "round": round_index,
                        "observation_id": action.observation_id,
                        "owner_range": list(action.owner_range),
                        "requested_range": list(action.requested_range),
                        "missing_behavior": action.reason,
                    },
                )
        qualify(_latest_changed_observations(changed, observations), round_index)
        for dormant_action in round_dormant_actions:
            unresolved_before = {
                obligation_id
                for obligation_id, status in previous_coverage.items()
                if status not in {"covered", "external"}
            }
            gain = evaluate_dormant_file_qualification_gain(
                dormant_action,
                decisions=tuple(decisions.values()),
                unresolved_obligation_ids=unresolved_before,
            )
            dormant_attempt_count = sum(
                bool(effect and effect[0] == "inspect_dormant_file")
                for effect in attempted_effects
            )
            dormant_second_opportunity_pending = (
                not gain.productive and dormant_attempt_count < 2
            )
            if dormant_second_opportunity_pending:
                dormant_file_attempt_limit = 2
            ctx.trace.record(
                "dormant_file_qualification_gain_evaluated",
                {
                    "round": round_index,
                    "action_id": dormant_action.id,
                    "path": dormant_action.path,
                    **gain.to_dict(),
                    "second_opportunity_enabled": dormant_second_opportunity_pending,
                    "attempt_limit": dormant_file_attempt_limit,
                },
            )
        completion_audit = select_dormant_island_completions(
            matured_observation_ids=tuple(matured_observation_ids),
            observations=observations,
            decisions=decisions,
            completion_candidate_ids=completion_candidate_ids,
            attempted_target_ids=attempted_completion_target_ids,
            successful_source_ids=successful_completion_source_ids,
            observation_to_island=islands.observation_to_island,
            coverage=coverage.coverage,
            source_calls_tool=structural_tools.get("structural_source_owner_calls"),
            exact_symbol_tool=structural_tools.get("structural_find_exact_symbol"),
            trace=ctx.trace,
            round_index=round_index,
        )
        tool_calls += completion_audit.tool_calls
        ctx.trace.record(
            "dormant_island_completion_evaluated",
            {
                "round": round_index,
                "matured_observation_ids": sorted(matured_observation_ids),
                "eligible_candidate_count": len(completion_candidate_ids),
                "eligible_candidates": [
                    {
                        "observation_id": observation_id,
                        "path": observations[observation_id].handle.path,
                        "symbol": observations[observation_id].handle.symbol,
                        "obligation_ids": list(observations[observation_id].obligation_ids),
                    }
                    for observation_id in sorted(completion_candidate_ids)
                    if observation_id in observations
                    and observations[observation_id].handle.path.casefold() in {
                        observations[source_id].handle.path.casefold()
                        for source_id in matured_observation_ids
                        if source_id in observations
                    }
                ],
                "attempted_target_ids": sorted(attempted_completion_target_ids),
                "selections": [
                    {
                        "source_observation_id": item.source_observation_id,
                        "target_observation_id": item.target.id,
                        "target_path": item.target.handle.path,
                        "target_symbol": item.target.handle.symbol,
                        "island_id": item.island_id,
                        "relationship_kind": item.relationship_kind,
                        "matched_name": item.matched_name,
                    }
                    for item in completion_audit.selections
                ],
                "rejected": list(completion_audit.rejected),
            },
        )
        for selection in completion_audit.selections:
            attempted_completion_target_ids.add(selection.target.id)
            target_observation = completion_observation(selection)
            disclosure = disclose_observations(
                (target_observation,),
                workspace_root=ctx.config.workspace_root,
                outline_tool=structural_tools["structural_file_outline"],
                trace=ctx.trace,
                round_index=round_index,
            )
            tool_calls += disclosure.tool_calls
            if not disclosure.cards or selection.source_observation_id not in cards:
                ctx.trace.record(
                    "dormant_island_completion_skipped",
                    {
                        "round": round_index,
                        "source_observation_id": selection.source_observation_id,
                        "target_observation_id": selection.target.id,
                        "reason": "source_or_target_disclosure_unavailable",
                    },
                )
                continue
            completion_decision, completion_usage, bounded_pair = qualify_dormant_island_completion(
                llm_config=ctx.config.llm_config,
                user_request=user_request,
                source_card=cards[selection.source_observation_id],
                target_card=disclosure.cards[0],
                source_decision=decisions[selection.source_observation_id],
                relationship_kind=selection.relationship_kind,
                max_input_chars=ctx.config.max_qualification_input_chars,
                trace=ctx.trace,
                round_index=round_index,
            )
            _add_usage(qualification_usage, completion_usage)
            if not completion_decision.assessment.is_retained:
                continue
            target_card = bounded_pair[1]
            target_observation = replace(target_observation, disclosure_status=target_card.mode)
            observations[target_observation.id] = target_observation
            cards[target_observation.id] = target_card
            decisions[target_observation.id] = completion_decision
            candidate = candidate_factory(target_observation, completion_decision, target_card)
            if candidate is not None:
                payload = candidate_payload(candidate)
                candidates[str(payload["candidate_id"])] = candidate
            changed.append(target_observation)
            successful_completion_source_ids.append(selection.source_observation_id)
            announce_dormant_completion_promotion(
                round_index=round_index,
                source_observation_id=selection.source_observation_id,
                target_observation_id=target_observation.id,
                evidence_kind=completion_decision.assessment.evidence_kind.value,
            )
            ctx.trace.record(
                "dormant_island_completion_promoted",
                {
                    "round": round_index,
                    "source_observation_id": selection.source_observation_id,
                    "target_observation_id": target_observation.id,
                    "island_id": selection.island_id,
                    "relationship_kind": selection.relationship_kind,
                    "evidence_kind": completion_decision.assessment.evidence_kind.value,
                },
            )
        reevaluate_owner_representations(round_index)
        discovered_leads, lead_audit, lead_tool_calls = _discover_verified_leads(
            round_index=round_index,
            changed_observation_ids=tuple(item.id for item in changed),
            observations=observations,
            decisions=decisions,
            cards=cards,
            coverage=coverage.coverage,
            pending_node_ids={key for key, lead in pending_verified_leads.items()
                              if lead.inspection_basis != "incidental_visible_call"},
            executed_node_ids=executed_verified_lead_node_ids,
            exact_symbol_tool=structural_tools["structural_find_exact_symbol"],
            trace=ctx.trace,
            maturation_observation_ids=matured_observation_ids,
        )
        tool_calls += lead_tool_calls
        for lead in discovered_leads:
            retain_verified_lead(pending_verified_leads, lead)
        ctx.trace.record(
            "verified_leads_evaluated",
            {
                "round": round_index,
                "audit": lead_audit,
                "new_lead_count": len(discovered_leads),
                "pending_leads": [_verified_lead_to_dict(item) for item in pending_verified_leads.values()],
                "executed_count": verified_lead_executions,
                "execution_cap": MAX_VERIFIED_LEAD_EXECUTIONS,
            },
        )
        coverage = _evaluate(ctx, user_request, obligations, candidates, candidate_payload, round_index=round_index)
        _add_usage(coverage_usage, coverage.usage)
        qualified_lead_gain = discover_qualified_leads(tuple(item.id for item in changed), round_index)
        previous_islands = islands
        islands = _build_islands(
            ctx, observations, decisions, cards, coverage.coverage, structural_tools,
            owner_representations=owner_representations,
            previous=previous_islands, round_index=round_index,
        )
        tool_calls += islands.tool_calls
        all_edges.extend(_represented_connector_edges(islands.edges))
        current_coverage = {item.obligation_id: item.status for item in coverage.coverage}
        evidence_gain = set(candidates) != previous_candidate_ids
        promoted_ids = {
            observation_id for observation_id, decision in decisions.items() if decision.assessment.is_retained
        }
        navigation_gain = bool(promoted_ids - previous_promoted_ids)
        coverage_gain = any(
            _status_rank(current_coverage.get(key, "missing")) > _status_rank(value)
            for key, value in previous_coverage.items()
        )
        lead_gain = (bool(discovered_leads) or qualified_lead_gain) and verified_lead_executions < MAX_VERIFIED_LEAD_EXECUTIONS
        if round_index == 3:
            allow_exact_followup_round = (
                any(_has_specific_exact_anchors(action) for action in selected)
                and (evidence_gain or navigation_gain)
            )
        ctx.trace.record(
            "controller_round_completed",
            {
                "round": round_index,
                "new_observation_ids": [item.id for item in changed],
                "candidate_ids": sorted(candidates),
                "coverage": [item.to_dict() for item in coverage.coverage],
                "evidence_gain": evidence_gain,
                "navigation_gain": navigation_gain,
                "coverage_gain": coverage_gain,
                "verified_lead_gain": lead_gain,
                "pending_verified_lead_count": len(pending_verified_leads),
                "verified_lead_execution_count": verified_lead_executions,
                "new_raw_source_count": len(round_new_raw_source_ids),
                "new_materialized_snippet_count": len(changed),
                "source_materialization_loss_count": len(round_materialization_losses),
                "source_materialization_losses": round_materialization_losses,
                "dormant_second_opportunity_pending": dormant_second_opportunity_pending,
            },
        )
        if _required_covered(obligations, coverage.coverage):
            stop_reason = "all_required_obligations_covered"
        elif (
            not dormant_second_opportunity_pending
            and not evidence_gain and not navigation_gain and not coverage_gain and not lead_gain
        ):
            stop_reason = (
                "source_materialization_loss"
                if round_new_raw_source_ids and round_materialization_losses
                else "no_evidence_gain"
            )

    if not stop_reason:
        stop_reason = "controller_round_limit_reached"
    terminal_frontiers = frontier_ledger.refresh(
        islands=islands,
        decisions=decisions,
        coverage=coverage.coverage,
    )
    ctx.trace.record(
        "island_frontiers_terminal",
        {
            "mode": "read_only",
            "stop_reason": stop_reason,
            "frontier_count": len(terminal_frontiers),
            "continuation_count": sum(len(item.continuations) for item in terminal_frontiers),
            "available_continuation_count": sum(
                1
                for item in terminal_frontiers
                for continuation in item.continuations
                if continuation.state == "available"
            ),
            "available_persisted_continuation_count": sum(
                1
                for item in terminal_frontiers
                for continuation in item.continuations
                if continuation.state == "available" and not continuation.present_in_catalogue
            ),
            "frontiers": [item.to_dict() for item in terminal_frontiers],
        },
    )
    file_traces = build_file_trace_evidence(
        file_trace_seeds,
        tuple(decisions.values()),
        islands.observation_to_island,
    )
    ctx.trace.record(
        "file_trace_evidence_created",
        {
            "trace_count": len(file_traces),
            "seed_count": len(file_trace_seeds),
            "selection_cap_stage": "final_evidence_consolidation",
            "traces": [item.to_dict() for item in file_traces],
        },
    )
    ctx.trace.record(
        "retrieval_controller_stopped",
        {
            "stop_reason": stop_reason,
            "rounds": completed_rounds,
            "tool_calls": tool_calls,
            "candidate_ids": sorted(candidates),
            "pending_verified_leads": [_verified_lead_to_dict(item) for item in pending_verified_leads.values()],
            "verified_lead_execution_count": verified_lead_executions,
            "verified_lead_execution_cap": MAX_VERIFIED_LEAD_EXECUTIONS,
            "verified_lead_block_reason": (
                "execution_cap_reached"
                if pending_verified_leads and verified_lead_executions >= MAX_VERIFIED_LEAD_EXECUTIONS
                else "round_budget_exhausted"
                if pending_verified_leads
                else ""
            ),
        },
    )
    return ControllerResult(
        observations=tuple(observations.values()),
        cards=tuple(cards.values()),
        decisions=tuple(decisions.values()),
        candidates=tuple(candidates.values()),
        coverage=coverage.coverage,
        islands=islands,
        edges=tuple(_dedupe_edges(all_edges)),
        tool_calls=tool_calls,
        rounds=completed_rounds,
        stop_reason=stop_reason,
        qualification_usage=dict(qualification_usage),
        coverage_usage=dict(coverage_usage),
        file_traces=tuple(item.to_dict() for item in file_traces),
    )


def _build_islands(
    ctx: Any,
    observations: Mapping[str, DiscoveryObservation],
    decisions: Mapping[str, QualificationDecision],
    cards: Mapping[str, DisclosureCard],
    coverage: Sequence[ObligationCoverage],
    tools: Mapping[str, Any],
    *,
    owner_representations: OwnerRepresentationSelection | None,
    previous: IslandSelection | None,
    round_index: int,
) -> IslandSelection:
    structural = build_structural_components(
        tuple(observations.values()),
        tuple(decisions.values()),
        relationship_tool=tools["structural_relationships_within_nodes"],
        source_calls_tool=tools.get("structural_source_owner_calls"),
        exact_symbol_tool=tools.get("structural_find_exact_symbol"),
        trace=ctx.trace,
        round_index=round_index,
    )
    return build_semantic_islands(
        tuple(observations.values()),
        tuple(decisions.values()),
        tuple(cards.values()),
        coverage,
        structural,
        primary_owner_counts=(owner_representations.primary_counts if owner_representations else {}),
        beam_size=getattr(ctx.config, "semantic_island_beam_size", 4),
        previous=previous,
        trace=ctx.trace,
        round_index=round_index,
    )


def _evaluate(
    ctx: Any,
    user_request: str,
    obligations: Sequence[EvidenceObligation],
    candidates: Mapping[str, Any],
    candidate_payload: Callable[[Any], Mapping[str, Any]],
    *,
    round_index: int,
) -> CoverageBatch:
    direct_candidates = tuple(
        payload
        for item in candidates.values()
        if (
            (payload := candidate_payload(item)).get("qualification_assessment") or {}
        ).get("evidence_kind") == "direct_fact"
    )
    return evaluate_coverage(
        llm_config=ctx.config.llm_config,
        user_request=user_request,
        obligations=obligations,
        candidates=direct_candidates,
        max_input_chars=ctx.config.max_qualification_input_chars,
        trace=ctx.trace,
        round_index=round_index,
    )


def _file_connection_summary(
    edges: Sequence[Mapping[str, Any]],
    source_path: str,
    destination_path: str,
) -> Mapping[str, object]:
    """Keep the bounded, CodeGraph-resolved call summary for one file handoff."""
    normalized_source = source_path.replace("\\", "/").casefold()
    normalized_destination = destination_path.replace("\\", "/").casefold()
    for edge in edges:
        summary = edge.get("file_connection_summary")
        if not isinstance(summary, Mapping):
            continue
        edge_source = str(summary.get("source_path") or "").replace("\\", "/").casefold()
        edge_destination = str(summary.get("destination_path") or "").replace("\\", "/").casefold()
        if edge_source == normalized_source and edge_destination == normalized_destination:
            return dict(summary)
    return {}


def _latest_changed_observations(
    changed: Sequence[DiscoveryObservation],
    observations: Mapping[str, DiscoveryObservation],
) -> tuple[DiscoveryObservation, ...]:
    changed_ids = tuple(dict.fromkeys(item.id for item in changed))
    return tuple(observations[observation_id] for observation_id in changed_ids)


def _required_covered(obligations: Sequence[EvidenceObligation], coverage: Sequence[ObligationCoverage]) -> bool:
    by_id = {item.obligation_id: item.status for item in coverage}
    return all(by_id.get(item.id) == "covered" for item in obligations if item.required)


def _status_rank(value: str) -> int:
    return {"contradictory": 0, "missing": 0, "external": 0, "partial": 1, "covered": 2}.get(value, 0)


def _zero_usage() -> dict[str, int]:
    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def _add_usage(target: dict[str, int], source: Mapping[str, int]) -> None:
    for key in target:
        target[key] += int(source.get(key, 0) or 0)


def _dedupe_edges(edges: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    values: dict[tuple[str, str, str], dict[str, Any]] = {}
    for edge in edges:
        source = edge.get("source") if isinstance(edge.get("source"), Mapping) else {}
        target = edge.get("target") if isinstance(edge.get("target"), Mapping) else {}
        key = (str(source.get("id") or ""), str(target.get("id") or ""), str(edge.get("kind") or ""))
        values[key] = dict(edge)
    return list(values.values())


def _represented_connector_edges(edges: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        dict(edge)
        for edge in edges
        if str(edge.get("_retrieval_provenance") or "") in {
            "exact_codegraph_connector_path",
            "source_verified_direct_call",
            "source_verified_connector_path",
        }
    ]
