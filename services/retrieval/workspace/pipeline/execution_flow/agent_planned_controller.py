from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from services.intent.models import EvidenceObligation
from services.llm.json_completion import complete_json
from services.retrieval.workspace.pipeline.execution_flow.actions.catalogue_and_execution import (
    action_to_dict,
    execute_action,
)
from services.retrieval.workspace.pipeline.execution_flow.actions.models import (
    ExpandRelationship,
    InspectDeferredObservation,
    InspectOwnerContinuation,
    RetrievalAction,
    SearchNewIsland,
    SearchWithinFile,
)
from services.retrieval.workspace.pipeline.execution_flow.actions.policy import ActionPurpose
from services.retrieval.workspace.pipeline.execution_flow.actions.scheduler import _action_effect
from services.retrieval.workspace.pipeline.execution_flow.coverage_evaluation import ObligationCoverage
from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import (
    DiscoveryObservation,
    merge_observation_pair,
)
from services.retrieval.workspace.pipeline.execution_flow.evidence_islands import IslandSelection
from services.retrieval.workspace.pipeline.execution_flow.file_trace_evidence import (
    FileTraceSeed,
    build_file_trace_evidence,
)
from services.retrieval.workspace.pipeline.execution_flow.evidence_qualification import (
    CLASSIFICATION_TO_DECISION,
    QualificationDecision,
)
from services.retrieval.workspace.pipeline.execution_flow.retrieval_controller import (
    ControllerResult,
    _build_islands,
    _dedupe_edges,
    _file_connection_summary,
    _represented_connector_edges,
    _required_covered,
)
from services.retrieval.workspace.pipeline.execution_flow.source_disclosure import (
    DisclosureCard,
    disclose_observations,
    fit_cards_to_source_capacity,
)


PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "agent_planned_round.md"
CLASSIFICATIONS = tuple(CLASSIFICATION_TO_DECISION)
COVERAGE_STATUSES = ("covered", "partial", "missing", "contradictory", "external")
SUGGESTED_NEEDS = (
    "trigger", "downstream", "implementation", "dependency", "state",
    "registration", "contract", "new_island", "unknown",
)
ACTION_TYPES = (
    "inspect_observation", "inspect_owner_continuation", "expand_relationship",
    "search_within_file", "search_repository",
)
EDGE_KINDS = ("calls", "imports", "implements", "overrides", "extends", "instantiates")
DIRECTIONS = ("incoming", "outgoing")
USAGE_KEYS = ("prompt_tokens", "completion_tokens", "total_tokens")


@dataclass(frozen=True)
class PlannerRound:
    decisions: tuple[QualificationDecision, ...]
    coverage: tuple[ObligationCoverage, ...]
    action_specs: tuple[Mapping[str, Any], ...]
    stop: bool
    stop_reason: str
    state_summary: str
    open_questions: tuple[str, ...]
    usage: Mapping[str, int]
    cards: tuple[DisclosureCard, ...]
    input_chars: int


def run_agent_planned_controller(
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
    """Run one persistent planner decision per round over native typed executors."""
    observations = {
        item.id: item
        for item in (*initial_observations, *deferred_observations, *dormant_completion_observations)
    }
    cards: dict[str, DisclosureCard] = {}
    decisions: dict[str, QualificationDecision] = {}
    candidates: dict[str, Any] = {}
    coverage: tuple[ObligationCoverage, ...] = tuple(
        ObligationCoverage(item.id, "missing", (), item.description, "unknown") for item in obligations
    )
    islands: IslandSelection | None = None
    all_edges: list[dict[str, Any]] = []
    file_trace_seeds: list[FileTraceSeed] = []
    attempted_ids: set[str] = set()
    attempted_effects: set[tuple[str, ...]] = set()
    action_history: list[dict[str, Any]] = []
    planner_usage = {key: 0 for key in USAGE_KEYS}
    tool_calls = 0
    state_summary = ""
    open_questions: tuple[str, ...] = ()
    pending = tuple(initial_observations)
    stop_reason = ""
    completed_rounds = 0
    max_rounds = min(ctx.config.max_agent_planner_rounds, ctx.config.max_exploration_rounds)
    max_actions = min(
        ctx.config.max_agent_planner_actions_per_round,
        ctx.config.max_controller_actions_per_round,
    )

    for round_index in range(max_rounds):
        completed_rounds = round_index + 1
        ctx.trace.record(
            "controller_round_started",
            {
                "controller": "agent_planned",
                "round": round_index,
                "pending_observation_ids": [item.id for item in pending],
                "coverage": [item.to_dict() for item in coverage],
                "attempted_action_ids": sorted(attempted_ids),
            },
        )
        disclosure = disclose_observations(
            pending,
            workspace_root=ctx.config.workspace_root,
            outline_tool=structural_tools["structural_file_outline"],
            trace=ctx.trace,
            round_index=round_index,
        )
        tool_calls += disclosure.tool_calls
        ctx.trace.record(
            "disclosure_cards_created",
            {
                "controller": "agent_planned",
                "round": round_index,
                "cards": [
                    {
                        "observation_id": item.observation_id,
                        "mode": item.mode,
                        "handle": item.to_dict()["handle"],
                        "chars": len(item.source_text),
                        "owner_kind": item.owner_kind,
                        "owner_name": item.owner_name,
                        "owner_range": [item.owner_line_start, item.owner_line_end],
                        "truncation_reason": item.truncation_reason,
                    }
                    for item in disclosure.cards
                ],
            },
        )
        plan = plan_agent_round(
            llm_config=ctx.config.llm_config,
            user_request=user_request,
            obligations=obligations,
            pending_cards=disclosure.cards,
            observations=tuple(observations.values()),
            decisions=tuple(decisions.values()),
            candidate_payloads=tuple(candidate_payload(item) for item in candidates.values()),
            prior_coverage=coverage,
            action_history=tuple(action_history),
            state_summary=state_summary,
            open_questions=open_questions,
            remaining_rounds=max_rounds - round_index,
            remaining_actions=max_actions,
            max_input_chars=ctx.config.max_agent_planner_input_chars,
            trace=ctx.trace,
            round_index=round_index,
        )
        _add_usage(planner_usage, plan.usage)
        state_summary = plan.state_summary
        open_questions = plan.open_questions
        coverage = plan.coverage
        for card in plan.cards:
            cards[card.observation_id] = card
            observations[card.observation_id] = replace(
                observations[card.observation_id], disclosure_status=card.mode,
            )
        for decision in plan.decisions:
            decisions[decision.observation_id] = decision
            if decision.disposition == "promote":
                candidate = candidate_factory(
                    observations[decision.observation_id], decision, cards[decision.observation_id]
                )
                if candidate is not None:
                    payload = candidate_payload(candidate)
                    candidates[str(payload["candidate_id"])] = candidate
            else:
                for candidate_id, candidate in tuple(candidates.items()):
                    if str(candidate_payload(candidate).get("observation_id") or "") == decision.observation_id:
                        candidates.pop(candidate_id, None)

        # Resolve the planner's observation-grounded support to native candidate IDs.
        coverage = _resolve_candidate_support(coverage, candidates, candidate_payload)
        islands = _build_islands(
            ctx, observations, decisions, cards, coverage, structural_tools,
            previous=islands, round_index=round_index,
        )
        tool_calls += islands.tool_calls
        all_edges.extend(_represented_connector_edges(islands.edges))

        if _required_covered(obligations, coverage):
            stop_reason = "all_required_obligations_covered"
            break
        if plan.stop:
            stop_reason = plan.stop_reason or "planner_stopped"
            break

        selected: list[RetrievalAction] = []
        for spec in plan.action_specs[:max_actions]:
            action = _action_from_spec(
                spec,
                observations=observations,
                cards=cards,
                obligation_ids={item.id for item in obligations},
                observation_to_island=islands.observation_to_island,
                round_index=round_index,
            )
            effect = _action_effect(action)
            if action.id in attempted_ids or effect in attempted_effects:
                raise RuntimeError("agent_planner_repeated_action_effect")
            attempted_ids.add(action.id)
            attempted_effects.add(effect)
            selected.append(action)
        if not selected:
            stop_reason = "planner_returned_no_action"
            break

        ctx.trace.record(
            "agent_planned_actions_selected",
            {"round": round_index, "actions": [action_to_dict(item) for item in selected]},
        )
        changed: list[DiscoveryObservation] = []
        for action in selected:
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
            endpoint_ids: list[str] = []
            for observation in execution.observations:
                existing = observations.get(observation.id)
                if existing is None or isinstance(action, (InspectDeferredObservation, InspectOwnerContinuation)):
                    updated = observation
                else:
                    try:
                        updated = merge_observation_pair(existing, observation)
                    except ValueError:
                        updated = observation
                observations[updated.id] = updated
                changed.append(updated)
                endpoint_ids.append(updated.id)
            if isinstance(action, ExpandRelationship) and execution.edges:
                source = observations.get(action.root_observation_id)
                source_path = source.handle.path if source is not None else ""
                for endpoint in execution.observations:
                    if endpoint.handle.path and endpoint.handle.path.casefold() != source_path.casefold():
                        file_trace_seeds.append(FileTraceSeed(
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
                        ))
            outcome = {
                "round": round_index,
                "action": action_to_dict(action),
                "status": execution.status,
                "endpoint_observation_ids": endpoint_ids,
                "edge_count": len(execution.edges),
            }
            action_history.append(outcome)
            ctx.trace.record("controller_action_executed", outcome)
        pending = _latest_changed(changed, observations)
        ctx.trace.record(
            "agent_planned_round_completed",
            {
                "round": round_index,
                "new_observation_ids": [item.id for item in pending],
                "candidate_ids": sorted(candidates),
                "coverage": [item.to_dict() for item in coverage],
                "state_summary": state_summary,
                "open_questions": list(open_questions),
            },
        )

    if islands is None:
        raise RuntimeError("agent_planner_created_no_island_state")
    if not stop_reason:
        stop_reason = "agent_planner_round_limit_reached"
    file_traces = build_file_trace_evidence(
        file_trace_seeds, tuple(decisions.values()), islands.observation_to_island,
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
            "controller": "agent_planned",
            "stop_reason": stop_reason,
            "rounds": completed_rounds,
            "tool_calls": tool_calls,
            "candidate_ids": sorted(candidates),
            "planner_usage": dict(planner_usage),
        },
    )
    return ControllerResult(
        observations=tuple(observations.values()),
        cards=tuple(cards.values()),
        decisions=tuple(decisions.values()),
        candidates=tuple(candidates.values()),
        coverage=coverage,
        islands=islands,
        edges=tuple(_dedupe_edges(all_edges)),
        tool_calls=tool_calls,
        rounds=completed_rounds,
        stop_reason=stop_reason,
        qualification_usage={key: 0 for key in USAGE_KEYS},
        coverage_usage={key: 0 for key in USAGE_KEYS},
        file_traces=tuple(item.to_dict() for item in file_traces),
        planner_usage=dict(planner_usage),
    )


def plan_agent_round(
    *, llm_config: Any, user_request: str, obligations: Sequence[EvidenceObligation],
    pending_cards: Sequence[DisclosureCard], observations: Sequence[DiscoveryObservation],
    decisions: Sequence[QualificationDecision], candidate_payloads: Sequence[Mapping[str, Any]],
    prior_coverage: Sequence[ObligationCoverage], action_history: Sequence[Mapping[str, Any]],
    state_summary: str, open_questions: Sequence[str], remaining_rounds: int,
    remaining_actions: int, max_input_chars: int, trace: Any | None = None,
    round_index: int = 0,
) -> PlannerRound:
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    pending_ids = tuple(card.observation_id for card in pending_cards)
    observation_ids = tuple(dict.fromkeys(item.id for item in observations))
    obligation_ids = tuple(item.id for item in obligations)
    response_format = _response_format(pending_ids, observation_ids, obligation_ids, remaining_actions)
    compact = {
        "request": user_request,
        "obligations": [_compact_obligation(item) for item in obligations],
        "known_observation_columns": [
            "id", "path", "symbol", "obligation_ids", "qualification",
        ],
        "known_observations": [_compact_observation(item, decisions) for item in observations],
        "promoted_candidates": [_compact_candidate(item) for item in candidate_payloads],
        "prior_coverage": [item.to_dict() for item in prior_coverage],
        "recent_action_outcomes": list(action_history[-6:]),
        "planner_state": {"summary": state_summary, "open_questions": list(open_questions)},
        "budget": {"remaining_rounds": remaining_rounds, "max_actions_this_round": remaining_actions},
    }
    empty_cards = fit_cards_to_source_capacity(pending_cards, source_capacity=0)
    fixed_payload = {**compact, "new_disclosures": [_planner_card_payload(item) for item in empty_cards]}
    prompt_chars = len(prompt)
    schema_chars = len(json.dumps(response_format, sort_keys=True))
    fixed_payload_chars = len(json.dumps(fixed_payload, sort_keys=True))
    fixed_chars = prompt_chars + schema_chars + fixed_payload_chars
    source_capacity = max_input_chars - fixed_chars - 512
    if source_capacity < 0:
        if trace is not None:
            trace.record(
                "agent_planner_budget_rejected",
                {
                    "round": round_index,
                    "input_char_budget": max_input_chars,
                    "prompt_chars": prompt_chars,
                    "schema_chars": schema_chars,
                    "fixed_payload_chars": fixed_payload_chars,
                    "known_observation_count": len(observations),
                    "pending_card_count": len(pending_cards),
                },
            )
        raise RuntimeError("agent_planner_input_budget_too_small_for_metadata")
    bounded_cards = fit_cards_to_source_capacity(pending_cards, source_capacity=source_capacity)
    payload = {**compact, "new_disclosures": [_planner_card_payload(item) for item in bounded_cards]}
    serialized = json.dumps(payload, sort_keys=True)
    input_chars = len(prompt) + len(json.dumps(response_format, sort_keys=True)) + len(serialized)
    if input_chars > max_input_chars:
        raise RuntimeError("agent_planner_input_budget_exceeded")
    usage = {key: 0 for key in USAGE_KEYS}

    def log_event(event_type: str, value: Mapping[str, Any]) -> None:
        if event_type == "llm_response_received":
            raw = value.get("raw_response", {})
            raw_usage = raw.get("usage", {}) if isinstance(raw, Mapping) else {}
            if isinstance(raw_usage, Mapping):
                for key in usage:
                    usage[key] += int(raw_usage.get(key, 0) or 0)
        if trace is not None:
            trace.record(event_type, {"stage": "agent_planned_round", "round": round_index, **dict(value)})

    if trace is not None:
        trace.record(
            "agent_planner_requested",
            {
                "round": round_index,
                "pending_observation_ids": list(pending_ids),
                "known_observation_count": len(observation_ids),
                "input_chars": input_chars,
                "input_char_budget": max_input_chars,
                "source_capacity": source_capacity,
                "prior_action_count": len(action_history),
            },
        )
    response = complete_json(
        llm_config,
        ({"role": "system", "content": prompt}, {"role": "user", "content": serialized}),
        response_format=response_format,
        log_event=log_event,
    )
    result = _validate_round(
        response,
        pending_ids=pending_ids,
        observation_ids=set(observation_ids),
        obligations=obligations,
        prior_decisions=decisions,
        max_actions=remaining_actions,
    )
    if trace is not None:
        trace.record(
            "agent_planner_decision_created",
            {
                "round": round_index,
                "decisions": [item.to_dict() for item in result.decisions],
                "coverage": [item.to_dict() for item in result.coverage],
                "actions": list(result.action_specs),
                "stop": result.stop,
                "stop_reason": result.stop_reason,
                "state_summary": result.state_summary,
                "open_questions": list(result.open_questions),
                "usage": dict(usage),
            },
        )
    return replace(result, usage=dict(usage), cards=bounded_cards, input_chars=input_chars)


def _validate_round(
    response: Mapping[str, Any], *, pending_ids: Sequence[str], observation_ids: set[str],
    obligations: Sequence[EvidenceObligation], prior_decisions: Sequence[QualificationDecision],
    max_actions: int,
) -> PlannerRound:
    raw_classifications = response.get("classifications")
    if not isinstance(raw_classifications, list):
        raise RuntimeError("agent_planner_invalid_classifications")
    by_id: dict[str, QualificationDecision] = {}
    for item in raw_classifications:
        observation_id = str(item.get("observation_id") or "")
        classification = str(item.get("classification") or "")
        if observation_id not in pending_ids or classification not in CLASSIFICATION_TO_DECISION:
            raise RuntimeError("agent_planner_invalid_classification_item")
        disposition, support = CLASSIFICATION_TO_DECISION[classification]
        by_id[observation_id] = QualificationDecision(
            observation_id=observation_id,
            disposition=disposition,
            support_level=support,
            reason=str(item.get("reason") or ""),
            visible_support=tuple(str(value) for value in item.get("visible_support", ()) if str(value)),
            missing_information=tuple(str(value) for value in item.get("missing_information", ()) if str(value)),
            local_follow_up=str(item.get("local_follow_up") or ""),
        )
    if set(by_id) != set(pending_ids):
        raise RuntimeError("agent_planner_must_classify_every_pending_observation")
    direct_ids = {
        item.observation_id for item in prior_decisions if item.disposition == "promote" and item.support_level == "direct_evidence"
    }
    direct_ids.update(
        item.observation_id for item in by_id.values()
        if item.disposition == "promote" and item.support_level == "direct_evidence"
    )
    raw_coverage = response.get("coverage")
    if not isinstance(raw_coverage, list):
        raise RuntimeError("agent_planner_invalid_coverage")
    coverage_by_id: dict[str, ObligationCoverage] = {}
    obligation_ids = {item.id for item in obligations}
    for item in raw_coverage:
        obligation_id = str(item.get("obligation_id") or "")
        status = str(item.get("status") or "")
        supporting = tuple(str(value) for value in item.get("supporting_observation_ids", ()) if str(value))
        if obligation_id not in obligation_ids or status not in COVERAGE_STATUSES:
            raise RuntimeError("agent_planner_invalid_coverage_item")
        if any(value not in direct_ids for value in supporting):
            raise RuntimeError("agent_planner_coverage_support_must_be_promoted_direct")
        if status == "covered" and not supporting:
            raise RuntimeError("agent_planner_covered_obligation_requires_direct_support")
        suggested_need = str(item.get("suggested_need") or "unknown")
        if suggested_need not in SUGGESTED_NEEDS:
            raise RuntimeError("agent_planner_invalid_suggested_need")
        coverage_by_id[obligation_id] = ObligationCoverage(
            obligation_id, status, supporting,
            str(item.get("missing_claim") or ""), suggested_need,
        )
    if set(coverage_by_id) != obligation_ids:
        raise RuntimeError("agent_planner_must_cover_every_obligation")
    actions = response.get("actions")
    if not isinstance(actions, list) or len(actions) > max_actions:
        raise RuntimeError("agent_planner_invalid_action_count")
    for action in actions:
        action_type = str(action.get("action_type") or "")
        if action_type not in ACTION_TYPES:
            raise RuntimeError("agent_planner_invalid_action_type")
        observation_id = str(action.get("observation_id") or "")
        if action_type == "search_repository" and observation_id != "repository":
            raise RuntimeError("agent_planner_repository_search_requires_sentinel")
        if action_type != "search_repository" and observation_id not in observation_ids:
            raise RuntimeError("agent_planner_action_unknown_observation")
        if str(action.get("obligation_id") or "") not in obligation_ids:
            raise RuntimeError("agent_planner_action_unknown_obligation")
    stop = bool(response.get("stop"))
    if stop and actions:
        raise RuntimeError("agent_planner_cannot_stop_and_schedule_actions")
    if not stop and not actions:
        raise RuntimeError("agent_planner_must_stop_or_schedule_an_action")
    return PlannerRound(
        decisions=tuple(by_id[value] for value in pending_ids),
        coverage=tuple(coverage_by_id[item.id] for item in obligations),
        action_specs=tuple(dict(item) for item in actions),
        stop=stop,
        stop_reason=str(response.get("stop_reason") or ""),
        state_summary=str(response.get("state_summary") or ""),
        open_questions=tuple(str(value) for value in response.get("open_questions", ()) if str(value)),
        usage={}, cards=(), input_chars=0,
    )


def _action_from_spec(
    spec: Mapping[str, Any], *, observations: Mapping[str, DiscoveryObservation],
    cards: Mapping[str, DisclosureCard], obligation_ids: set[str],
    observation_to_island: Mapping[str, str], round_index: int,
) -> RetrievalAction:
    action_type = str(spec.get("action_type") or "")
    obligation_id = str(spec.get("obligation_id") or "")
    observation_id = str(spec.get("observation_id") or "")
    if obligation_id not in obligation_ids:
        raise RuntimeError("agent_planner_action_unknown_obligation")
    observation = observations.get(observation_id) if observation_id else None
    if action_type != "search_repository" and observation is None:
        raise RuntimeError("agent_planner_action_requires_known_observation")
    digest = hashlib.sha1(
        json.dumps({**dict(spec), "round": round_index}, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    action_id = f"agent_action_{digest}"
    reason = str(spec.get("reason") or "Agent-selected bounded retrieval action.")
    scope_id = observation_to_island.get(observation_id, observation_id)
    limit = max(1, min(int(spec.get("limit") or 3), 6))
    if action_type == "inspect_observation":
        assert observation is not None
        handle = observation.handle
        return InspectDeferredObservation(
            action_id, observation_id,
            (max(1, handle.full_line_start or handle.line_start), max(handle.line_end, handle.full_line_end)),
            reason, scope_id=scope_id, purpose=ActionPurpose.INSPECT_DEFERRED_DISCOVERY,
        )
    if action_type == "inspect_owner_continuation":
        assert observation is not None
        card = cards.get(observation_id)
        owner_start = max(1, (card.owner_line_start if card else 0) or observation.handle.full_line_start or observation.handle.line_start)
        owner_end = max(owner_start, (card.owner_line_end if card else 0) or observation.handle.full_line_end or observation.handle.line_end)
        raw_start = int(spec.get("line_start") or 0)
        raw_end = int(spec.get("line_end") or 0)
        if raw_start <= 0 or raw_end < raw_start:
            raise RuntimeError("agent_planner_owner_continuation_requires_valid_range")
        requested_start = max(owner_start, raw_start)
        requested_end = min(owner_end, max(requested_start, raw_end))
        return InspectOwnerContinuation(
            action_id, obligation_id, observation_id, (requested_start, requested_end),
            (owner_start, owner_end), reason, scope_id=scope_id,
        )
    if action_type == "expand_relationship":
        assert observation is not None
        if not observation.handle.node_id:
            raise RuntimeError("agent_planner_relationship_requires_node_id")
        edge_kinds = tuple(dict.fromkeys(str(value) for value in spec.get("edge_kinds", ()) if str(value) in EDGE_KINDS))
        if not edge_kinds:
            raise RuntimeError("agent_planner_relationship_requires_edge_kind")
        direction = str(spec.get("direction") or "outgoing")
        if direction not in DIRECTIONS:
            raise RuntimeError("agent_planner_relationship_invalid_direction")
        return ExpandRelationship(
            action_id, obligation_id, observation_id, observation.handle.node_id,
            direction, edge_kinds, str(spec.get("expected_signal") or reason),
            max_results=min(limit, 3), scope_id=scope_id,
            handoff_reason=reason, obligation_ids=(obligation_id,),
        )
    if action_type == "search_within_file":
        assert observation is not None
        query = str(spec.get("query") or "").strip()
        if not query:
            raise RuntimeError("agent_planner_search_requires_query")
        return SearchWithinFile(
            action_id, obligation_id, observation_id, observation.handle.path, query,
            tuple(str(value) for value in spec.get("sparse_anchors", ()) if str(value)),
            result_limit=min(limit, 3), scope_id=scope_id, handoff_reason=reason,
        )
    if action_type == "search_repository":
        query = str(spec.get("query") or "").strip()
        exact = tuple(str(value) for value in spec.get("exact_symbol_anchors", ()) if str(value))
        if not query and not exact:
            raise RuntimeError("agent_planner_repository_search_requires_query_or_exact_anchor")
        return SearchNewIsland(
            action_id, obligation_id, query,
            tuple(str(value) for value in spec.get("sparse_anchors", ()) if str(value)),
            exact, result_limit=limit, scope_id=obligation_id,
        )
    raise RuntimeError("agent_planner_invalid_action_type")


def _response_format(
    pending_ids: Sequence[str], observation_ids: Sequence[str], obligation_ids: Sequence[str], max_actions: int,
) -> Mapping[str, Any]:
    string_array = {"type": "array", "items": {"type": "string"}}
    classification = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "observation_id": {"type": "string", "enum": list(pending_ids) or [""]},
            "classification": {"type": "string", "enum": list(CLASSIFICATIONS)},
            "reason": {"type": "string"}, "visible_support": string_array,
            "missing_information": string_array, "local_follow_up": {"type": "string"},
        },
        "required": ["observation_id", "classification", "reason", "visible_support", "missing_information", "local_follow_up"],
    }
    coverage = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "obligation_id": {"type": "string", "enum": list(obligation_ids)},
            "status": {"type": "string", "enum": list(COVERAGE_STATUSES)},
            "supporting_observation_ids": string_array,
            "missing_claim": {"type": "string"},
            "suggested_need": {"type": "string", "enum": list(SUGGESTED_NEEDS)},
        },
        "required": ["obligation_id", "status", "supporting_observation_ids", "missing_claim", "suggested_need"],
    }
    action_properties = {
        "action_type": {"type": "string", "enum": list(ACTION_TYPES)},
        "obligation_id": {"type": "string", "enum": list(obligation_ids)},
        "observation_id": {"type": "string", "enum": ["repository", *observation_ids]},
        "query": {"type": "string"}, "reason": {"type": "string"},
        "expected_signal": {"type": "string"},
        "direction": {"type": "string", "enum": list(DIRECTIONS)},
        "edge_kinds": {"type": "array", "items": {"type": "string", "enum": list(EDGE_KINDS)}},
        "line_start": {"type": "integer", "minimum": 0},
        "line_end": {"type": "integer", "minimum": 0},
        "sparse_anchors": string_array, "exact_symbol_anchors": string_array,
        "limit": {"type": "integer", "minimum": 1, "maximum": 6},
    }
    action = {
        "type": "object", "additionalProperties": False,
        "properties": action_properties, "required": list(action_properties),
    }
    schema = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "classifications": {"type": "array", "items": classification},
            "coverage": {"type": "array", "items": coverage},
            "actions": {"type": "array", "maxItems": max_actions, "items": action},
            "stop": {"type": "boolean"}, "stop_reason": {"type": "string"},
            "state_summary": {"type": "string"}, "open_questions": string_array,
        },
        "required": ["classifications", "coverage", "actions", "stop", "stop_reason", "state_summary", "open_questions"],
    }
    return {"type": "json_schema", "json_schema": {"name": "agent_planned_round", "strict": True, "schema": schema}}


def _compact_observation(
    observation: DiscoveryObservation, decisions: Sequence[QualificationDecision],
) -> list[Any]:
    decision = next((item for item in decisions if item.observation_id == observation.id), None)
    return [
        observation.id,
        observation.handle.path,
        observation.handle.symbol,
        list(observation.obligation_ids),
        f"{decision.disposition}/{decision.support_level}" if decision else "",
    ]


def _compact_obligation(obligation: EvidenceObligation) -> Mapping[str, Any]:
    return {
        "id": obligation.id,
        "description": obligation.description,
        "required": obligation.required,
        "depends_on": list(obligation.depends_on),
        "anchors": list(obligation.anchor_refs),
    }


def _planner_card_payload(card: DisclosureCard) -> Mapping[str, Any]:
    return {
        "observation_id": card.observation_id,
        "mode": card.mode,
        "source": card.source_text,
        "owner": card.owner_name,
        "owner_range": [card.owner_line_start, card.owner_line_end],
        "truncation_reason": card.truncation_reason,
    }


def _compact_candidate(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        key: payload.get(key)
        for key in ("candidate_id", "observation_id", "path", "symbol", "obligation_ids", "qualification_support")
        if key in payload
    }


def _resolve_candidate_support(
    coverage: Sequence[ObligationCoverage], candidates: Mapping[str, Any],
    candidate_payload: Callable[[Any], Mapping[str, Any]],
) -> tuple[ObligationCoverage, ...]:
    candidate_by_observation = {
        str(payload.get("observation_id") or ""): candidate_id
        for candidate_id, candidate in candidates.items()
        if (payload := candidate_payload(candidate)).get("observation_id")
    }
    resolved = tuple(
        replace(
            item,
            supporting_candidate_ids=tuple(
                candidate_by_observation[value]
                for value in item.supporting_candidate_ids
                if value in candidate_by_observation
            ),
        )
        for item in coverage
    )
    if any(item.status == "covered" and not item.supporting_candidate_ids for item in resolved):
        raise RuntimeError("agent_planner_covered_support_has_no_native_candidate")
    return resolved


def _latest_changed(
    changed: Sequence[DiscoveryObservation], observations: Mapping[str, DiscoveryObservation],
) -> tuple[DiscoveryObservation, ...]:
    return tuple(observations[value] for value in dict.fromkeys(item.id for item in changed))


def _add_usage(target: dict[str, int], source: Mapping[str, int]) -> None:
    for key in target:
        target[key] += int(source.get(key, 0) or 0)
