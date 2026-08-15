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
    build_islands_and_select_roots,
)
from services.retrieval.workspace.pipeline.execution_flow.evidence_qualification import (
    QualificationDecision,
    qualify_cards,
)
from services.retrieval.workspace.pipeline.execution_flow.retrieval_actions import (
    ExpandRelationship,
    InspectDeferredObservation,
    RetrievalAction,
    SearchNewIsland,
    SearchWithinFile,
    action_to_dict,
    enumerate_actions,
    execute_action,
)
from services.retrieval.workspace.pipeline.execution_flow.source_disclosure import DisclosureCard, disclose_observations


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


def run_retrieval_controller(
    *,
    ctx: Any,
    user_request: str,
    obligations: Sequence[EvidenceObligation],
    initial_observations: Sequence[DiscoveryObservation],
    deferred_observations: Sequence[DiscoveryObservation] = (),
    structural_tools: Mapping[str, Any],
    qdrant_tool: Any,
    candidate_factory: Callable[[DiscoveryObservation, QualificationDecision, DisclosureCard], Any | None],
    candidate_payload: Callable[[Any], Mapping[str, Any]],
) -> ControllerResult:
    observations = {item.id: item for item in (*initial_observations, *deferred_observations)}
    cards: dict[str, DisclosureCard] = {}
    decisions: dict[str, QualificationDecision] = {}
    candidates: dict[str, Any] = {}
    all_edges: list[dict[str, Any]] = []
    attempted: set[str] = set()
    attempted_effects: set[tuple[str, ...]] = set()
    refined_paths: set[str] = set()
    tool_calls = 0
    qualification_usage = _zero_usage()
    coverage_usage = _zero_usage()

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
        for card in disclosure.cards:
            cards[card.observation_id] = card
            observations[card.observation_id] = replace(
                observations[card.observation_id],
                disclosure_status=card.mode,
            )
        ctx.trace.record(
            "disclosure_cards_created",
            {
                "round": round_index,
                "cards": [
                    {
                        "observation_id": item.observation_id,
                        "mode": item.mode,
                        "handle": item.to_dict()["handle"],
                        "chars": len(item.source_text),
                        "truncation_reason": item.truncation_reason,
                    }
                    for item in disclosure.cards
                ],
            },
        )
        qualification = qualify_cards(
            llm_config=ctx.config.llm_config,
            user_request=user_request,
            cards=disclosure.cards,
            max_input_chars=ctx.config.max_qualification_input_chars,
            trace=ctx.trace,
            round_index=round_index,
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
    islands = _build_islands(ctx, observations, decisions, structural_tools, round_index=0)
    tool_calls += islands.tool_calls
    coverage = _evaluate(ctx, user_request, obligations, candidates, candidate_payload, round_index=0)
    _add_usage(coverage_usage, coverage.usage)
    stop_reason = "all_required_obligations_covered" if _required_covered(obligations, coverage.coverage) else ""
    completed_rounds = 0
    allow_exact_followup_round = False

    for round_index in range(1, ctx.config.max_exploration_rounds + 1):
        if stop_reason:
            break
        if round_index == 4 and not allow_exact_followup_round:
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
            edge_capabilities_tool=structural_tools["structural_edge_capabilities"],
            attempted_fingerprints=attempted,
            trace=ctx.trace,
            round_index=round_index,
        )
        tool_calls += catalogue.tool_calls
        selected = _select_actions(
            catalogue.actions,
            islands.active_root_ids,
            ctx.config.max_controller_actions_per_round,
            refined_paths=refined_paths,
            prefer_relationship=round_index > 1,
            attempted_effects=attempted_effects,
        )
        if not selected:
            stop_reason = "no_executable_action"
            break
        ctx.trace.record(
            "controller_actions_selected",
            {
                "round": round_index,
                "actions": [action_to_dict(item) for item in selected],
                "selection_policy": "qualified_file_refinement_then_inspect_then_capability_checked_relationship_with_new_island_beam",
            },
        )
        previous_candidate_ids = set(candidates)
        previous_promoted_ids = {
            observation_id for observation_id, decision in decisions.items() if decision.disposition == "promote"
        }
        previous_coverage = {item.obligation_id: item.status for item in coverage.coverage}
        changed: list[DiscoveryObservation] = []
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
            tool_calls += execution.tool_calls
            all_edges.extend(execution.edges)
            for observation in execution.observations:
                existing = observations.get(observation.id)
                if existing == observation and not isinstance(action, InspectDeferredObservation):
                    continue
                updated = (
                    observation
                    if existing is None or isinstance(action, InspectDeferredObservation)
                    else merge_observation_pair(existing, observation)
                )
                observations[observation.id] = updated
                changed.append(updated)
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
        qualify(_latest_changed_observations(changed, observations), round_index)
        islands = _build_islands(ctx, observations, decisions, structural_tools, round_index=round_index)
        tool_calls += islands.tool_calls
        coverage = _evaluate(ctx, user_request, obligations, candidates, candidate_payload, round_index=round_index)
        _add_usage(coverage_usage, coverage.usage)
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
            },
        )
        if _required_covered(obligations, coverage.coverage):
            stop_reason = "all_required_obligations_covered"
        elif not evidence_gain and not navigation_gain and not coverage_gain:
            stop_reason = "no_evidence_gain"

    if not stop_reason:
        stop_reason = "controller_round_limit_reached"
    ctx.trace.record(
        "retrieval_controller_stopped",
        {
            "stop_reason": stop_reason,
            "rounds": completed_rounds,
            "tool_calls": tool_calls,
            "candidate_ids": sorted(candidates),
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
    )


def _build_islands(
    ctx: Any,
    observations: Mapping[str, DiscoveryObservation],
    decisions: Mapping[str, QualificationDecision],
    tools: Mapping[str, Any],
    *,
    round_index: int,
) -> IslandSelection:
    return build_islands_and_select_roots(
        tuple(observations.values()),
        tuple(decisions.values()),
        relationship_tool=tools["structural_relationships_within_nodes"],
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


def _select_actions(
    actions: Sequence[RetrievalAction],
    root_order: Sequence[str],
    limit: int,
    *,
    refined_paths: set[str] | None = None,
    prefer_relationship: bool = False,
    attempted_effects: set[tuple[str, ...]] | None = None,
) -> tuple[RetrievalAction, ...]:
    already_refined = refined_paths or set()
    prior_effects = attempted_effects or set()
    root_rank = {value: index for index, value in enumerate(root_order)}
    ranked = sorted(
        actions,
        key=lambda item: (
            0
            if isinstance(item, SearchWithinFile)
            else 1
            if isinstance(item, InspectDeferredObservation)
            else 2
            if isinstance(item, ExpandRelationship)
            else 3,
            getattr(item, "priority", 0) if isinstance(item, SearchWithinFile) else 0,
            root_rank.get(_action_root_id(item), 10_000),
            getattr(item, "obligation_id", ""),
            getattr(item, "priority", 0),
            item.id,
        ),
    )
    available_file_hypotheses = {
        item.path.casefold()
        for item in ranked
        if isinstance(item, SearchWithinFile) and item.path.casefold() not in already_refined
    }
    if limit > 1 and (prefer_relationship or len(available_file_hypotheses) < limit):
        exact_identifier_hypothesis = next(
            (
                item
                for item in ranked
                if _has_specific_exact_anchors(item)
            ),
            None,
        )
        relationship_hypothesis = (
            exact_identifier_hypothesis
            or next((item for item in ranked if isinstance(item, ExpandRelationship)), None)
            if prefer_relationship or len(available_file_hypotheses) == 1
            else None
        )
        # Keep one slot available for a disconnected-island hypothesis. Without
        # this beam discipline, local graph/inspection actions can consume every
        # round before an independent search runs. Distinct path-scoped searches
        # already constitute separate bounded hypotheses and should not be
        # displaced by an arbitrary deferred-pool item.
        deferred_hypothesis = next(
            (
                item
                for item in ranked
                if isinstance(item, InspectDeferredObservation) and item.deferred_pool
            ),
            None,
        )
        independent_hypothesis = relationship_hypothesis or deferred_hypothesis or next(
            (item for item in ranked if isinstance(item, SearchNewIsland)),
            None,
        )
        if independent_hypothesis is not None:
            ranked = [item for item in ranked if item is not independent_hypothesis]
            ranked.insert(1 if ranked else 0, independent_hypothesis)
    selected: list[RetrievalAction] = []
    used_roots: set[str] = set()
    used_paths: set[str] = set()
    used_effects: set[tuple[str, ...]] = set()
    for action in ranked:
        if _action_effect(action) in prior_effects:
            continue
        if isinstance(action, SearchWithinFile) and action.path.casefold() in already_refined:
            continue
        if isinstance(action, SearchWithinFile) and action.path.casefold() in used_paths:
            continue
        root_id = _action_root_id(action)
        if root_id and root_id in used_roots:
            continue
        effect = _action_effect(action)
        if effect in used_effects:
            continue
        selected.append(action)
        used_effects.add(effect)
        if root_id:
            used_roots.add(root_id)
        if isinstance(action, SearchWithinFile):
            used_paths.add(action.path.casefold())
        if len(selected) >= limit:
            break
    return tuple(selected)


def _action_effect(action: RetrievalAction) -> tuple[str, ...]:
    if isinstance(action, InspectDeferredObservation):
        return ("inspect", action.observation_id, str(action.requested_range))
    if isinstance(action, ExpandRelationship):
        return ("expand", action.root_observation_id, action.direction, *action.edge_kinds)
    if isinstance(action, SearchWithinFile):
        return ("within_file", action.obligation_id, action.path, action.dense_query)
    if isinstance(action, SearchNewIsland):
        if action.exact_symbol_anchors:
            return ("exact_search", *sorted(set(action.exact_symbol_anchors)))
        return ("search", action.obligation_id, action.dense_query)
    return ("stop", action.id)


def _action_root_id(action: RetrievalAction) -> str:
    if isinstance(action, SearchWithinFile):
        return action.source_observation_id
    return str(getattr(action, "root_observation_id", "") or "")


def _has_specific_exact_anchors(action: RetrievalAction) -> bool:
    return isinstance(action, SearchNewIsland) and any(
        value.startswith("_") for value in action.exact_symbol_anchors
    )


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
