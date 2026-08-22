from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import re
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
    qualify_cards,
)
from services.retrieval.workspace.pipeline.execution_flow.dormant_island_completion import (
    completion_observation,
    qualify_dormant_island_completion,
    select_dormant_island_completions,
)
from services.retrieval.workspace.pipeline.execution_flow.file_trace_evidence import (
    FileTraceSeed,
    build_file_trace_evidence,
)
from services.retrieval.workspace.pipeline.execution_flow.actions.catalogue_and_execution import (
    ExpandRelationship,
    InspectDeferredObservation,
    InspectOwnerContinuation,
    InspectVerifiedLead,
    SearchWithinFile,
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
)
from services.retrieval.workspace.pipeline.execution_flow.source_disclosure import DisclosureCard, disclose_observations
from services.retrieval.workspace.pipeline.execution_flow.structural_components import build_structural_components
from services.retrieval.workspace.tools import ToolRequest


MAX_VERIFIED_LEAD_EXECUTIONS = 2


@dataclass(frozen=True)
class VerifiedLead:
    source_observation_id: str
    obligation_id: str
    target: str
    target_node_id: str
    target_path: str
    target_line_start: int
    target_line_end: int
    target_symbol: str
    reason: str
    discovered_round: int
    source_rank: int
    qualified_target: bool
    structural_child: bool = False


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


def _discover_verified_leads(
    *,
    round_index: int,
    changed_observation_ids: Sequence[str],
    observations: Mapping[str, DiscoveryObservation],
    decisions: Mapping[str, QualificationDecision],
    cards: Mapping[str, DisclosureCard],
    coverage: Sequence[ObligationCoverage],
    pending_node_ids: set[str],
    executed_node_ids: set[str],
    exact_symbol_tool: Any,
    trace: Any | None,
    maturation_observation_ids: set[str] | None = None,
) -> tuple[tuple[VerifiedLead, ...], list[dict[str, Any]], int]:
    """Validate newly disclosed, literal call targets before granting a reserved action."""
    coverage_by_id = {item.obligation_id: item for item in coverage}
    accepted: list[VerifiedLead] = []
    audit: list[dict[str, Any]] = []
    tool_calls = 0
    seen_targets: set[tuple[str, str]] = set()
    matured_ids = maturation_observation_ids or set()
    for observation_id in dict.fromkeys(changed_observation_ids):
        observation = observations.get(observation_id)
        decision = decisions.get(observation_id)
        card = cards.get(observation_id)
        base = {
            "observation_id": observation_id,
            "round": round_index,
            "follow_up": decision.local_follow_up if decision is not None else "",
        }
        if observation is None or decision is None or card is None:
            audit.append({**base, "status": "rejected", "reason": "missing_observation_decision_or_card"})
            continue
        is_matured = observation_id in matured_ids
        if decision.disposition != "promote" or (
            decision.support_level != "navigation_only" and not is_matured
        ):
            continue
        unresolved = [
            value
            for value in observation.obligation_ids
            if coverage_by_id.get(value) is not None
            and coverage_by_id[value].status not in {"covered", "external"}
        ]
        if not unresolved:
            audit.append({**base, "status": "rejected", "reason": "no_compatible_unresolved_obligation"})
            continue
        target_context = decision.local_follow_up
        if is_matured:
            target_context = " ".join((
                target_context,
                *(coverage_by_id[value].missing_claim for value in unresolved),
            ))
        targets = _followup_called_targets(target_context, card.source_text)
        if not targets:
            audit.append({
                **base,
                "status": "rejected",
                "reason": "no_source_called_target_named_in_followup_or_unresolved_claim",
                "maturation_source": is_matured,
            })
            continue
        target = targets[0]
        target_key = (observation_id, target.casefold())
        if target_key in seen_targets:
            continue
        seen_targets.add(target_key)
        leaf = _target_leaf(target)
        request = ToolRequest(
            tool_name="structural_find_exact_symbol",
            arguments={"query": leaf, "limit": 8},
            reason=f"Validate visible direct follow-up target {target} before reserving retrieval work.",
        )
        response = exact_symbol_tool.run(request)
        if trace is not None:
            trace.record_tool(request, response, round_index=round_index)
        tool_calls += 1
        if response.status != "ok":
            raise RuntimeError("required_tool_failed: structural_find_exact_symbol")
        nodes = _matching_target_nodes(target, response.payload.get("nodes", ()))
        if len(nodes) != 1:
            audit.append({
                **base,
                "target": target,
                "status": "rejected",
                "reason": "target_not_resolved" if not nodes else "target_resolution_ambiguous",
                "match_count": len(nodes),
            })
            continue
        node = nodes[0]
        node_id = str(node.get("id") or "")
        target_path = str(node.get("path") or "")
        structural_child = bool(
            is_matured
            and target_path
            and target_path.casefold() != observation.handle.path.casefold()
        )
        if is_matured and not structural_child and decision.support_level != "navigation_only":
            audit.append({
                **base,
                "target": target,
                "target_node_id": node_id,
                "status": "rejected",
                "reason": "maturation_direct_target_not_cross_file",
            })
            continue
        if not node_id or node_id in pending_node_ids or node_id in executed_node_ids:
            audit.append({
                **base,
                "target": target,
                "target_node_id": node_id,
                "status": "rejected",
                "reason": "target_already_pending_or_executed",
            })
            continue
        if any(item.handle.node_id == node_id for item in observations.values()):
            audit.append({
                **base,
                "target": target,
                "target_node_id": node_id,
                "status": "rejected",
                "reason": "target_already_observed",
            })
            continue
        lead = VerifiedLead(
            source_observation_id=observation_id,
            obligation_id=unresolved[0],
            target=target,
            target_node_id=node_id,
            target_path=target_path,
            target_line_start=max(1, int(node.get("line_start") or 1)),
            target_line_end=max(1, int(node.get("line_end") or node.get("line_start") or 1)),
            target_symbol=str(node.get("qualified_name") or node.get("name") or leaf),
            reason=decision.local_follow_up,
            discovered_round=round_index,
            source_rank=observation.best_rank,
            qualified_target=("." in target or "::" in target),
            structural_child=structural_child,
        )
        accepted.append(lead)
        pending_node_ids.add(node_id)
        audit.append({**base, **_verified_lead_to_dict(lead), "status": "accepted", "reason": "visible_call_resolved"})
    return tuple(accepted), audit, tool_calls


def _literal_followup_targets(value: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(
        match.group(1).strip()
        for match in re.finditer(r"`([^`]+)`", value or "")
        if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*(?:(?:::|\.)[A-Za-z_$][A-Za-z0-9_$]*)*", match.group(1).strip())
    ))


def _followup_called_targets(follow_up: str, source: str) -> tuple[str, ...]:
    """Find follow-up identifiers that are also literal calls in the disclosed source.

    Backticks are presentation, not semantics: an LLM may emit either
    ``Inspect `Series._binop``` or ``Inspect Series._binop`` for the same lead.
    """
    visible_calls = tuple(dict.fromkeys(
        match.group(1)
        for match in re.finditer(
            r"(?:\bself\.|\bthis\.|\b[A-Za-z_$][A-Za-z0-9_$]*\.)?([A-Za-z_$][A-Za-z0-9_$]*)\s*\(",
            source or "",
        )
    ))
    candidates: list[str] = []
    for literal in _literal_followup_targets(follow_up):
        if _target_leaf(literal) in visible_calls:
            candidates.append(literal)
    for leaf in visible_calls:
        qualified = re.search(
            rf"\b([A-Za-z_$][A-Za-z0-9_$]*(?:(?:::|\.){re.escape(leaf)}))\b",
            follow_up or "",
        )
        if qualified:
            candidates.append(qualified.group(1))
        elif re.search(rf"(?<![A-Za-z0-9_$]){re.escape(leaf)}(?![A-Za-z0-9_$])", follow_up or ""):
            candidates.append(leaf)
    return tuple(dict.fromkeys(candidates))


def _target_leaf(target: str) -> str:
    return re.split(r"::|\.", target)[-1]


def _source_visibly_calls(source: str, target: str) -> bool:
    leaf = _target_leaf(target)
    return bool(re.search(rf"\b{re.escape(leaf)}\s*\(", source or ""))


def _matching_target_nodes(target: str, values: Sequence[Any]) -> list[dict[str, Any]]:
    leaf = _target_leaf(target).casefold()
    normalized_target = target.replace("::", ".").casefold()
    qualified = "." in normalized_target
    matches: dict[str, dict[str, Any]] = {}
    for value in values:
        if not isinstance(value, Mapping):
            continue
        name = str(value.get("name") or "").casefold()
        qualified_name = str(value.get("qualified_name") or value.get("name") or "").replace("::", ".").casefold()
        if name != leaf and qualified_name.split(".")[-1] != leaf:
            continue
        if qualified and not (qualified_name == normalized_target or qualified_name.endswith(f".{normalized_target}")):
            continue
        node_id = str(value.get("id") or "")
        if node_id and value.get("path"):
            matches[node_id] = dict(value)
    return list(matches.values())


def _verified_lead_to_dict(lead: VerifiedLead) -> dict[str, Any]:
    return {
        "source_observation_id": lead.source_observation_id,
        "obligation_id": lead.obligation_id,
        "target": lead.target,
        "target_node_id": lead.target_node_id,
        "target_path": lead.target_path,
        "target_range": [lead.target_line_start, lead.target_line_end],
        "target_symbol": lead.target_symbol,
        "reason": lead.reason,
        "discovered_round": lead.discovered_round,
        "structural_child": lead.structural_child,
    }


def _select_verified_lead_actions(
    leads: Sequence[VerifiedLead],
    *,
    executed_count: int,
    observation_to_island: Mapping[str, str],
) -> tuple[InspectVerifiedLead, ...]:
    if not leads or executed_count >= MAX_VERIFIED_LEAD_EXECUTIONS:
        return ()
    lead = min(
        leads,
        key=lambda item: (
            0 if item.structural_child else 1,
            0 if item.qualified_target else 1,
            item.discovered_round,
            item.source_rank,
            item.target_path.casefold(),
            item.target_node_id,
        ),
    )
    digest = hashlib.sha1(
        f"{lead.source_observation_id}\0{lead.target_node_id}".encode("utf-8")
    ).hexdigest()[:16]
    return (
        InspectVerifiedLead(
            id=f"action_{digest}",
            obligation_id=lead.obligation_id,
            source_observation_id=lead.source_observation_id,
            target=lead.target,
            target_node_id=lead.target_node_id,
            target_path=lead.target_path,
            target_line_start=lead.target_line_start,
            target_line_end=lead.target_line_end,
            target_symbol=lead.target_symbol,
            reason=lead.reason,
            discovered_round=lead.discovered_round,
            scope_id=observation_to_island.get(lead.source_observation_id, ""),
            purpose=(
                ActionPurpose.STRUCTURAL_CHILD_HANDOFF
                if lead.structural_child
                else ActionPurpose.VERIFIED_SOURCE_LEAD
            ),
        ),
    )


def run_retrieval_controller(
    *,
    ctx: Any,
    user_request: str,
    obligations: Sequence[EvidenceObligation],
    initial_observations: Sequence[DiscoveryObservation],
    deferred_observations: Sequence[DiscoveryObservation] = (),
    dormant_completion_observations: Sequence[DiscoveryObservation] = (),
    structural_tools: Mapping[str, Any],
    qdrant_tool: Any,
    candidate_factory: Callable[[DiscoveryObservation, QualificationDecision, DisclosureCard], Any | None],
    candidate_payload: Callable[[Any], Mapping[str, Any]],
) -> ControllerResult:
    # Dormant owner-comparison results are visible only to the bounded island
    # completion stage. With no qualification decision they cannot become
    # roots or ordinary scheduled actions.
    observations = {
        item.id: item
        for item in (*initial_observations, *deferred_observations, *dormant_completion_observations)
    }
    cards: dict[str, DisclosureCard] = {}
    decisions: dict[str, QualificationDecision] = {}
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
            cards=disclosure.cards,
            max_input_chars=ctx.config.max_qualification_input_chars,
            trace=ctx.trace,
            round_index=round_index,
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
            if decision.disposition == "promote":
                observation = observations[decision.observation_id]
                candidate = candidate_factory(observation, decision, cards[decision.observation_id])
                if candidate is not None:
                    payload = candidate_payload(candidate)
                    candidates[str(payload["candidate_id"])] = candidate
            else:
                for candidate_id, candidate in tuple(candidates.items()):
                    if str(candidate_payload(candidate).get("observation_id") or "") == decision.observation_id:
                        candidates.pop(candidate_id, None)

    qualify(tuple(initial_observations), 0)
    coverage = _evaluate(ctx, user_request, obligations, candidates, candidate_payload, round_index=0)
    _add_usage(coverage_usage, coverage.usage)
    islands = _build_islands(
        ctx, observations, decisions, cards, coverage.coverage, structural_tools,
        previous=None, round_index=0,
    )
    tool_calls += islands.tool_calls
    all_edges.extend(_represented_connector_edges(islands.edges))
    stop_reason = "all_required_obligations_covered" if _required_covered(obligations, coverage.coverage) else ""
    completed_rounds = 0
    allow_exact_followup_round = False
    pending_maturation_child_roots: set[str] = set()
    pending_verified_leads: dict[str, VerifiedLead] = {}
    executed_verified_lead_node_ids: set[str] = set()
    verified_lead_executions = 0

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
            decisions=tuple(decisions.values()),
            cards=tuple(cards.values()),
            active_root_ids=islands.active_root_ids,
            observation_to_island=islands.observation_to_island,
            edge_capabilities_tool=structural_tools["structural_edge_capabilities"],
            file_nodes_tool=structural_tools["structural_resolve_file_nodes"],
            attempted_fingerprints=attempted,
            trace=ctx.trace,
            round_index=round_index,
        )
        tool_calls += catalogue.tool_calls
        verified_lead_selected = _select_verified_lead_actions(
            tuple(pending_verified_leads.values()),
            executed_count=verified_lead_executions,
            observation_to_island=islands.observation_to_island,
        )
        schedule = schedule_round_actions(
            catalogue.actions,
            active_root_ids=islands.active_root_ids,
            active_island_ids=islands.active_island_ids,
            normal_limit=ctx.config.max_controller_actions_per_round,
            round_index=round_index,
            refined_paths=refined_paths,
            attempted_action_ids=attempted,
            attempted_effects=attempted_effects,
            pending_maturation_child_roots=pending_maturation_child_roots,
            blocked_maturation_root_ids={
                lead.source_observation_id for lead in pending_verified_leads.values()
            },
            verified_lead_actions=verified_lead_selected,
        )
        normal_selected = schedule.normal
        deferred_file_seed_selected = schedule.deferred_file_rescue
        maturation_selected = schedule.owner_maturation
        maturation_children = schedule.maturation_children
        test_maturation_selected = schedule.test_maturation
        selected = schedule.selected
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
                "maturation_child_action_count": len(maturation_children),
                "test_maturation_action_count": len(test_maturation_selected),
                "verified_lead_action_count": len(verified_lead_selected),
                "verified_lead_pending_count": len(pending_verified_leads),
                "verified_lead_execution_count": verified_lead_executions,
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
            },
        )
        previous_candidate_ids = set(candidates)
        previous_promoted_ids = {
            observation_id for observation_id, decision in decisions.items() if decision.disposition == "promote"
        }
        previous_coverage = {item.obligation_id: item.status for item in coverage.coverage}
        changed: list[DiscoveryObservation] = []
        matured_observation_ids: set[str] = set()
        for action in selected:
            attempted.add(action.id)
            attempted_effects.add(_action_effect(action))
            if isinstance(action, SearchWithinFile):
                refined_paths.add(action.path.casefold())
            execution = execute_action(
                action,
                observations=tuple(observations.values()),
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
                if existing == observation and not isinstance(action, (InspectDeferredObservation, InspectOwnerContinuation)):
                    continue
                source_replaced = False
                if existing is None or isinstance(action, (InspectDeferredObservation, InspectOwnerContinuation)):
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
            if completion_decision.disposition != "promote":
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
            ctx.trace.record(
                "dormant_island_completion_promoted",
                {
                    "round": round_index,
                    "source_observation_id": selection.source_observation_id,
                    "target_observation_id": target_observation.id,
                    "island_id": selection.island_id,
                    "relationship_kind": selection.relationship_kind,
                    "support_level": completion_decision.support_level,
                },
            )
        discovered_leads, lead_audit, lead_tool_calls = _discover_verified_leads(
            round_index=round_index,
            changed_observation_ids=tuple(item.id for item in changed),
            observations=observations,
            decisions=decisions,
            cards=cards,
            coverage=coverage.coverage,
            pending_node_ids=set(pending_verified_leads),
            executed_node_ids=executed_verified_lead_node_ids,
            exact_symbol_tool=structural_tools["structural_find_exact_symbol"],
            trace=ctx.trace,
            maturation_observation_ids=matured_observation_ids,
        )
        tool_calls += lead_tool_calls
        for lead in discovered_leads:
            pending_verified_leads.setdefault(lead.target_node_id, lead)
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
        previous_islands = islands
        islands = _build_islands(
            ctx, observations, decisions, cards, coverage.coverage, structural_tools,
            previous=previous_islands, round_index=round_index,
        )
        tool_calls += islands.tool_calls
        all_edges.extend(_represented_connector_edges(islands.edges))
        current_coverage = {item.obligation_id: item.status for item in coverage.coverage}
        evidence_gain = set(candidates) != previous_candidate_ids
        promoted_ids = {
            observation_id for observation_id, decision in decisions.items() if decision.disposition == "promote"
        }
        navigation_gain = bool(promoted_ids - previous_promoted_ids)
        coverage_gain = any(
            _status_rank(current_coverage.get(key, "missing")) > _status_rank(value)
            for key, value in previous_coverage.items()
        )
        lead_gain = bool(discovered_leads) and verified_lead_executions < MAX_VERIFIED_LEAD_EXECUTIONS
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
            },
        )
        if _required_covered(obligations, coverage.coverage):
            stop_reason = "all_required_obligations_covered"
        elif not evidence_gain and not navigation_gain and not coverage_gain and not lead_gain:
            stop_reason = "no_evidence_gain"

    if not stop_reason:
        stop_reason = "controller_round_limit_reached"
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
        if (payload := candidate_payload(item)).get("qualification_support") == "direct_evidence"
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
