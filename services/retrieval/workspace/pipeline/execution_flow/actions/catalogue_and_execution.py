from __future__ import annotations

from dataclasses import asdict, replace
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
from services.retrieval.workspace.pipeline.execution_flow.actions.policy import (
    ActionPurpose,
    action_pool,
)
from services.retrieval.workspace.pipeline.execution_flow.actions.models import (
    ActionCatalogue,
    ActionExecution,
    ExpandRelationship,
    InspectDeferredObservation,
    InspectOwnerContinuation,
    InspectVerifiedLead,
    RetrievalAction,
    SearchNewIsland,
    SearchWithinFile,
    StopRetrieval,
)
from services.retrieval.workspace.tools import ToolRequest


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
    file_nodes_tool: Any | None = None,
    observation_to_island: Mapping[str, str] | None = None,
    trace: Any | None = None,
    round_index: int = 0,
) -> ActionCatalogue:
    observation_by_id = {item.id: item for item in observations}
    decision_by_id = {item.observation_id: item for item in decisions}
    card_by_id = {str(item.observation_id): item for item in cards}
    obligation_by_id = {item.id: item for item in obligations}
    roots = [observation_by_id[item] for item in active_root_ids if item in observation_by_id]
    active_root_set = set(active_root_ids)
    island_by_observation = observation_to_island or {}
    represented_paths = {
        observation_by_id[observation_id].handle.path.casefold()
        for observation_id, decision in decision_by_id.items()
        if decision.disposition == "promote" and observation_id in observation_by_id
    }
    deferred_seed_candidates: dict[str, list[tuple[SearchWithinFile, dict[str, Any]]]] = {}
    deferred_seed_audit: list[dict[str, Any]] = []
    bounded_handoff_pairs = {
        (root.id, gap.obligation_id)
        for gap in coverage
        for root in roots
        if (decision := decision_by_id.get(root.id)) is not None
        and gap.obligation_id in root.obligation_ids
        and _bounded_followup_allowed(decision, gap)
    }
    file_node_by_path: dict[str, str] = {}
    tool_calls = 0
    handoff_paths = tuple(dict.fromkeys(
        root.handle.path
        for root in roots
        if root.handle.path and any(pair[0] == root.id for pair in bounded_handoff_pairs)
    ))
    if handoff_paths and file_nodes_tool is not None:
        request = ToolRequest(
            tool_name="structural_resolve_file_nodes",
            arguments={"paths": list(handoff_paths[:16])},
            reason="Attach file nodes for bounded follow-up from promoted qualified observations.",
        )
        response = file_nodes_tool.run(request)
        if trace is not None:
            trace.record_tool(request, response, round_index=round_index)
        tool_calls += 1
        if response.status != "ok":
            raise RuntimeError("required_tool_failed: structural_resolve_file_nodes")
        file_node_by_path = {
            str(item.get("path") or ""): str(item.get("id") or "")
            for item in response.payload.get("nodes", ())
            if isinstance(item, Mapping) and item.get("path") and item.get("id")
        }
    node_ids = list(dict.fromkeys((
        *(item.handle.node_id for item in roots if item.handle.node_id),
        *(file_node_by_path.values()),
    )))
    capability_by_node: dict[str, dict[str, set[str]]] = {}
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
    qualified_paths = {
        observation.handle.path.casefold()
        for observation in observations
        if observation.id in decision_by_id and observation.handle.path
    }
    promoted_followups_by_path: dict[str, tuple[str, ...]] = {}
    for observation_id, decision in decision_by_id.items():
        observation = observation_by_id.get(observation_id)
        if (
            observation is None
            or decision.disposition != "promote"
            or not decision.local_follow_up.strip()
            or not observation.handle.path
        ):
            continue
        path = observation.handle.path.casefold()
        promoted_followups_by_path[path] = tuple(dict.fromkeys(
            (*promoted_followups_by_path.get(path, ()), decision.local_follow_up.strip())
        ))
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
                    priority=observation_index,
                    scope_id=_scope_id("unresolved_obligation", gap.obligation_id),
                    purpose=ActionPurpose.INSPECT_DEFERRED_DISCOVERY,
                )
                if action.id not in attempted_fingerprints:
                    actions.append(action)
                seed, audit = _deferred_file_seed_action(
                    observation=observation,
                    obligation=obligation,
                    gap=gap,
                    represented_paths=represented_paths,
                    qualified_paths=qualified_paths,
                    promoted_followups=promoted_followups_by_path.get(handle.path.casefold(), ()),
                )
                deferred_seed_audit.append(audit)
                if seed is not None and seed.id not in attempted_fingerprints:
                    deferred_seed_candidates.setdefault(gap.obligation_id, []).append((seed, audit))
                continue
            card = card_by_id.get(observation.id)
            if _owner_continuation_allowed(decision, gap, card):
                owner_start = int(getattr(card, "owner_line_start", 0) or handle.full_line_start or handle.line_start)
                owner_end = int(getattr(card, "owner_line_end", 0) or handle.full_line_end or handle.line_end)
                requested_range = _later_owner_range(owner_start, owner_end)
                action = InspectOwnerContinuation(
                    id=_action_id("owner_continuation", gap.obligation_id, observation.id),
                    obligation_id=gap.obligation_id,
                    observation_id=observation.id,
                    requested_range=requested_range,
                    owner_range=(owner_start, owner_end),
                    reason=_handoff_reason(decision, gap),
                    priority=_navigation_priority(observation, decision),
                    scope_id=island_by_observation.get(observation.id, ""),
                    purpose=(
                        ActionPurpose.OWNER_MATURATION
                        if decision.local_follow_up
                        else ActionPurpose.OWNER_CONTINUATION
                    ),
                )
                if action.id not in attempted_fingerprints:
                    actions.append(action)
            if decision.disposition == "promote" and observation.id not in active_root_set:
                continue
            bounded_followup = (observation.id, gap.obligation_id) in bounded_handoff_pairs
            source_anchors = _source_call_identifiers(
                str(getattr(card_by_id.get(observation.id), "source_text", "") or "")
            )
            if handle.path and (
                decision.support_level == "navigation_only"
                or _is_strong_navigation_observation(observation)
                or (bounded_followup and bool(handle.symbol or observation.exact_anchor_matches or source_anchors))
            ):
                anchors = tuple(
                    dict.fromkeys(
                        value
                        for value in (*observation.exact_anchor_matches, handle.symbol, *source_anchors)
                        if value
                    )
                )[:12]
                completing_handoff = bounded_followup or bool(observation.parent_observation_ids)
                handoff_reason = _handoff_reason(decision, gap) if completing_handoff else ""
                owner_maturation = (
                    decision.disposition == "promote"
                    and decision.support_level == "navigation_only"
                    and bool(decision.local_follow_up)
                    and not (observation.artifact_role == "test" and not handle.node_id)
                    and gap.status not in {"covered", "external"}
                )
                action = SearchWithinFile(
                    id=_action_id("within_file", gap.obligation_id, observation.id, handle.path, *anchors),
                    obligation_id=gap.obligation_id,
                    source_observation_id=observation.id,
                    path=handle.path,
                    dense_query=(
                        _test_maturation_query(decision, gap)
                        if observation.artifact_role == "test" and not handle.node_id and decision.local_follow_up.strip()
                        else _handoff_query(user_request, gap, decision) if completing_handoff else user_request
                    ),
                    sparse_anchors=anchors,
                    priority=_navigation_priority(observation, decision),
                    scope_id=(
                        island_by_observation.get(observation.id, "")
                        if decision.disposition == "promote"
                        else _scope_id("unresolved_obligation", gap.obligation_id)
                    ),
                    handoff_reason=handoff_reason,
                    purpose=(
                        ActionPurpose.OWNER_MATURATION
                        if owner_maturation
                        else ActionPurpose.HANDOFF_COMPLETION
                        if observation.parent_observation_ids
                        else ActionPurpose.WITHIN_FILE_SEARCH
                    ),
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
                scope_id=_scope_id("unresolved_obligation", gap.obligation_id),
            )
            if action.id not in attempted_fingerprints:
                actions.append(action)

    # A navigation-quality test range can name the exact scenario/assertion it
    # still needs even after the obligation that originally surfaced the range
    # is covered.  Do not guess that it supports another obligation.  Instead,
    # let its own local follow-up run once while any required repository work
    # remains unresolved, then qualify the returned range normally.
    required_work_remains = any(
        gap.status not in {"covered", "external"}
        and (obligation := obligation_by_id.get(gap.obligation_id)) is not None
        and obligation.required
        for gap in coverage
    )
    short_rejected_headers_by_path: dict[str, tuple[str, ...]] = {}
    for observation in observations:
        decision = decision_by_id.get(observation.id)
        handle = observation.handle
        if (
            decision is None
            or decision.disposition != "reject"
            or observation.artifact_role != "test"
            or handle.node_id
            or handle.symbol
            or observation.best_rank > 3
            or (handle.line_end - handle.line_start + 1) > 8
            or not handle.path
        ):
            continue
        path = handle.path.casefold()
        short_rejected_headers_by_path[path] = tuple(dict.fromkeys(
            (*short_rejected_headers_by_path.get(path, ()), observation.id)
        ))
    if required_work_remains:
        for observation in observations:
            decision = decision_by_id.get(observation.id)
            handle = observation.handle
            if (
                decision is None
                or observation.artifact_role != "test"
                or handle.node_id
                or decision.disposition != "promote"
                or decision.support_level != "navigation_only"
                or not decision.local_follow_up.strip()
                or not handle.path
                or not observation.obligation_ids
            ):
                continue
            # If one of this observation's original obligations is still
            # unresolved, the ordinary per-obligation action above already
            # performs the same same-file search.  The isolated pool is only
            # the recovery path for a now-covered original obligation.
            if any(
                (gap := next((item for item in coverage if item.obligation_id == obligation_id), None)) is not None
                and gap.status not in {"covered", "external"}
                for obligation_id in observation.obligation_ids
            ):
                continue
            hint_ids = short_rejected_headers_by_path.get(handle.path.casefold(), ())
            source_obligation_id = observation.obligation_ids[0]
            action = SearchWithinFile(
                id=_action_id("test_maturation", source_obligation_id, observation.id, handle.path, decision.local_follow_up),
                obligation_id=source_obligation_id,
                source_observation_id=observation.id,
                path=handle.path,
                dense_query=_test_maturation_query(decision),
                priority=_navigation_priority(observation, decision) - (200 if hint_ids else 0),
                scope_id=island_by_observation.get(observation.id, ""),
                handoff_reason=decision.local_follow_up.strip(),
                file_trigger_hint_observation_ids=hint_ids,
                purpose=ActionPurpose.TEST_SCENARIO_MATURATION,
            )
            if action.id not in attempted_fingerprints:
                actions.append(action)

        structural_added = False
        for root in roots:
            decision = decision_by_id.get(root.id)
            if decision is None:
                continue
            root_source_anchors = _source_call_identifiers(
                str(getattr(card_by_id.get(root.id), "source_text", "") or "")
            )
            bounded_followup = (root.id, gap.obligation_id) in bounded_handoff_pairs
            if decision.support_level == "direct_evidence" and not bounded_followup:
                continue
            seeds: list[tuple[str, str]] = []
            if root.handle.node_id:
                seeds.append((root.handle.node_id, "owner"))
            if bounded_followup and (file_node_id := file_node_by_path.get(root.handle.path)):
                if all(seed_id != file_node_id for seed_id, _kind in seeds):
                    seeds.append((file_node_id, "file"))
            if not seeds:
                continue
            for seed_node_id, seed_kind in seeds:
                target_symbols = _source_handoff_identifiers(root_source_anchors) if seed_kind == "file" else ()
                if seed_kind == "file" and not target_symbols:
                    unavailable.append(
                        {
                            "obligation_id": gap.obligation_id,
                            "root_observation_id": root.id,
                            "seed_node_id": seed_node_id,
                            "seed_kind": seed_kind,
                            "reason": "file_handoff_lacks_visible_callable_anchor",
                        }
                    )
                    continue
                relationships = (
                    (("outgoing", "calls"),)
                    if seed_kind == "file" and target_symbols
                    else _relationships_for_need(gap.suggested_need)
                )
                for direction, kind in relationships:
                    available = capability_by_node.get(seed_node_id, {}).get(direction, set())
                    if kind not in available:
                        unavailable.append(
                            {
                                "obligation_id": gap.obligation_id,
                                "root_observation_id": root.id,
                                "seed_node_id": seed_node_id,
                                "seed_kind": seed_kind,
                                "direction": direction,
                                "edge_kind": kind,
                                "reason": "edge_kind_not_represented_around_root",
                            }
                        )
                        continue
                    action = ExpandRelationship(
                        id=_action_id(
                            "expand", gap.obligation_id, root.id, seed_node_id, direction, kind, *target_symbols,
                        ),
                        obligation_id=gap.obligation_id,
                        root_observation_id=root.id,
                        root_node_id=seed_node_id,
                        direction=direction,
                        edge_kinds=(kind,),
                        need=gap.suggested_need,
                        scope_id=island_by_observation.get(root.id, ""),
                        handoff_reason=_handoff_reason(decision, gap) if bounded_followup else "",
                        seed_kind=seed_kind,
                        target_symbol_anchors=target_symbols,
                        target_term_anchors=_handoff_terms(user_request, decision, gap) if seed_kind == "file" else (),
                        cross_file_only=seed_kind == "file",
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
                scope_id=_scope_id("unresolved_obligation", gap.obligation_id),
            )
            if action.id not in attempted_fingerprints:
                actions.append(action)
    for obligation_id, candidates_for_obligation in deferred_seed_candidates.items():
        seed, audit = min(
            candidates_for_obligation,
            key=lambda item: (
                -int(item[1]["overlap_count"]),
                item[0].priority,
                item[0].path.casefold(),
                item[0].id,
            ),
        )
        actions.append(seed)
        audit["retained_for_obligation"] = True
        for other_seed, other_audit in candidates_for_obligation:
            if other_seed.id != seed.id:
                other_audit["reason"] = "lower_ranked_eligible_seed_for_same_obligation"
    actions = _deduplicate_file_expansions(actions)
    actions = list(dict.fromkeys(actions))
    raw_action_count = len(actions)
    actions, frontier_pruning = _bound_discovery_frontiers(actions)
    if trace is not None:
        trace.record(
            "controller_actions_enumerated",
            {
                "round": round_index,
                "actions": [action_to_dict(item) for item in actions],
                "unavailable": unavailable,
                "raw_action_count": raw_action_count,
                "bounded_action_count": len(actions),
                "scope_count": len({item.scope_id or item.id for item in actions}),
                "frontier_pruning": frontier_pruning,
                "deferred_file_seed_audit": deferred_seed_audit,
            },
        )
    return ActionCatalogue(actions=tuple(actions), unavailable=tuple(unavailable), tool_calls=tool_calls)


def _deduplicate_file_expansions(actions: Sequence[RetrievalAction]) -> list[RetrievalAction]:
    """Collapse obligation clones of one physical file-to-file traversal."""
    grouped: dict[tuple[str, str, str, tuple[str, ...], bool], list[ExpandRelationship]] = {}
    retained: list[RetrievalAction] = []
    for action in actions:
        if not isinstance(action, ExpandRelationship) or action.seed_kind != "file":
            retained.append(action)
            continue
        key = (
            action.root_observation_id,
            action.root_node_id,
            action.direction,
            action.edge_kinds,
            action.cross_file_only,
        )
        grouped.setdefault(key, []).append(action)
    for key, variants in grouped.items():
        primary = min(variants, key=lambda item: (item.obligation_id, item.id))
        obligation_ids = tuple(dict.fromkeys(
            obligation_id
            for item in variants
            for obligation_id in (item.obligation_ids or (item.obligation_id,))
        ))
        target_symbols = tuple(dict.fromkeys(
            value for item in variants for value in item.target_symbol_anchors
        ))[:12]
        target_terms = tuple(dict.fromkeys(
            value for item in variants for value in item.target_term_anchors
        ))[:32]
        retained.append(
            replace(
                primary,
                id=_action_id("expand_file", *(str(value) for value in key), *obligation_ids, *target_symbols),
                obligation_ids=obligation_ids,
                target_symbol_anchors=target_symbols,
                target_term_anchors=target_terms,
            )
        )
    return retained


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
    if isinstance(action, InspectVerifiedLead):
        observation = observation_from_node(
            {
                "id": action.target_node_id,
                "name": action.target_symbol,
                "qualified_name": action.target_symbol,
                "path": action.target_path,
                "line_start": action.target_line_start,
                "line_end": action.target_line_end,
            },
            retriever="verified_direct_lead",
            query_id=action.id,
            obligation_ids=(action.obligation_id,),
            score=1.0,
            exact_anchor=action.target,
            parent_observation_ids=(action.source_observation_id,),
            relationship_direction=(
                "outgoing" if action.purpose is ActionPurpose.STRUCTURAL_CHILD_HANDOFF else ""
            ),
            relationship_kinds=(
                ("calls",) if action.purpose is ActionPurpose.STRUCTURAL_CHILD_HANDOFF else ()
            ),
        )
        return ActionExecution(
            action_id=action.id,
            observations=((observation,) if observation is not None else ()),
            edges=(),
            tool_calls=0,
            status="ok" if observation is not None else "empty",
        )
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
    if isinstance(action, InspectOwnerContinuation):
        observation = next((item for item in observations if item.id == action.observation_id), None)
        if observation is None:
            raise RuntimeError(f"controller_action_invalid: unknown observation {action.observation_id}")
        handle = replace(
            observation.handle,
            line_start=action.requested_range[0],
            line_end=action.requested_range[1],
            full_line_start=action.owner_range[0],
            full_line_end=action.owner_range[1],
            adapter="owner_continuation",
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
                "target_symbols": list(action.target_symbol_anchors),
                "target_terms": list(action.target_term_anchors),
                "cross_file_only": action.cross_file_only,
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
                obligation_ids=action.obligation_ids or (action.obligation_id,),
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
            retriever=(
                "deferred_file_seed_search"
                if action.purpose is ActionPurpose.DEFERRED_FILE_RESCUE
                else "within_file_search"
            ),
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
    value = {"type": type(action).__name__, **asdict(action)}
    value["purpose"] = action.purpose.value
    value["pool"] = action_pool(action.purpose).value
    if isinstance(action, ExpandRelationship) and action.seed_kind == "file":
        value["obligation_recurrence"] = len(action.obligation_ids or (action.obligation_id,))
    return value


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


def _bounded_followup_allowed(
    decision: QualificationDecision,
    gap: ObligationCoverage,
) -> bool:
    return (
        decision.disposition == "promote"
        and decision.support_level in {"direct_evidence", "navigation_only"}
        and bool(decision.missing_information)
        and bool(gap.missing_claim.strip())
        and gap.status not in {"covered", "external"}
    )


def _owner_continuation_allowed(
    decision: QualificationDecision,
    gap: ObligationCoverage,
    card: Any | None,
) -> bool:
    """A navigation result may get one new view only when its owner was incomplete."""
    if (
        decision.disposition != "promote"
        or decision.support_level != "navigation_only"
        or not decision.missing_information
        or not gap.missing_claim.strip()
        or gap.status in {"covered", "external"}
        or card is None
    ):
        return False
    source = str(getattr(card, "source_text", "") or "")
    complete = str(getattr(card, "complete_source_text", "") or "")
    owner_start = int(getattr(card, "owner_line_start", 0) or 0)
    owner_end = int(getattr(card, "owner_line_end", 0) or 0)
    incomplete = bool(complete and complete != source) or "complete source lines omitted" in source
    return incomplete and owner_end > owner_start


def _later_owner_range(owner_start: int, owner_end: int) -> tuple[int, int]:
    """Choose a stable later third, away from the original header-local excerpt."""
    span = max(1, owner_end - owner_start + 1)
    window = min(24, max(8, span // 3))
    center = owner_start + (span * 2 // 3)
    start = max(owner_start, min(owner_end - window + 1, center - window // 2))
    return start, min(owner_end, start + window - 1)


def _handoff_reason(decision: QualificationDecision, gap: ObligationCoverage) -> str:
    if decision.local_follow_up:
        return decision.local_follow_up
    details = "; ".join(value.strip() for value in decision.missing_information if value.strip())
    return " | ".join(value for value in (gap.missing_claim.strip(), details) if value)


def _handoff_query(
    user_request: str,
    gap: ObligationCoverage,
    decision: QualificationDecision,
) -> str:
    missing = _handoff_reason(decision, gap)
    return f"{user_request}\n\nBounded unresolved handoff: {missing}" if missing else user_request


def _handoff_terms(
    user_request: str,
    decision: QualificationDecision,
    gap: ObligationCoverage,
) -> tuple[str, ...]:
    ignored = {
        "actual", "behavior", "code", "concrete", "evidence", "explain", "file", "from", "into",
        "issue", "missing", "repository", "required", "showing", "source", "that", "this", "through",
        "where", "which", "with", "without",
    }
    text = " ".join((user_request, gap.missing_claim, *decision.missing_information))
    terms = (
        match.group(0).casefold()
        for match in re.finditer(r"[A-Za-z_][A-Za-z0-9_]{3,}", text)
    )
    return tuple(dict.fromkeys(term for term in terms if term not in ignored))[:32]


def _is_strong_navigation_observation(observation: DiscoveryObservation) -> bool:
    """Keep a bounded navigation use for repeated/exact hits even after evidence rejection."""
    return bool(observation.exact_anchor_matches) or (
        observation.recurrence >= 2 and observation.best_rank <= 5
    )


def _deferred_file_seed_action(
    *,
    observation: DiscoveryObservation,
    obligation: EvidenceObligation,
    gap: ObligationCoverage,
    represented_paths: set[str],
    qualified_paths: set[str],
    promoted_followups: Sequence[str],
) -> tuple[SearchWithinFile | None, dict[str, Any]]:
    path = observation.handle.path
    overlap_terms = _deferred_seed_overlap_terms(observation, obligation, gap)
    mechanism_anchors = _deferred_seed_mechanism_anchors(observation, obligation, gap)
    audit: dict[str, Any] = {
        "obligation_id": obligation.id,
        "observation_id": observation.id,
        "path": path,
        "artifact_role": observation.artifact_role,
        "best_rank": observation.best_rank,
        "best_score": observation.best_score,
        "overlap_terms": list(overlap_terms),
        "overlap_count": len(overlap_terms),
        "mechanism_anchors": list(mechanism_anchors),
        "mechanism_anchor_count": len(mechanism_anchors),
        "represented_path": path.casefold() in represented_paths if path else False,
        "admission_reason": observation.admission_reason,
        "has_qualified_same_file_observation": path.casefold() in qualified_paths if path else False,
        "promoted_same_file_followups": list(promoted_followups),
        "has_named_owner": bool(observation.handle.node_id and observation.handle.symbol),
        "eligible": False,
        "retained_for_obligation": False,
        "reason": "",
    }
    if observation.artifact_role != "implementation":
        audit["reason"] = "not_implementation_file"
        return None, audit
    if not path:
        audit["reason"] = "missing_path"
        return None, audit
    if observation.admission_reason != "same_path_alternative":
        audit["reason"] = "not_an_admission_held_same_file_alternative"
        return None, audit
    if path.casefold() not in qualified_paths:
        audit["reason"] = "not_a_same_file_alternative_to_a_qualified_observation"
        return None, audit
    if not promoted_followups:
        audit["reason"] = "same_file_observation_was_not_promoted_with_a_concrete_followup"
        return None, audit
    if not observation.handle.node_id or not observation.handle.symbol:
        audit["reason"] = "deferred_alternative_has_no_named_owner"
        return None, audit
    if observation.best_rank > 12 or observation.best_score <= 0:
        audit["reason"] = "weak_initial_retrieval"
        return None, audit
    if len(mechanism_anchors) < 2:
        audit["reason"] = "insufficient_specific_mechanism_anchors"
        return None, audit
    if len(overlap_terms) < 2:
        audit["reason"] = "insufficient_concrete_overlap_with_unresolved_claim"
        return None, audit
    action = SearchWithinFile(
        id=_action_id("deferred_file_seed", obligation.id, observation.id, path),
        obligation_id=obligation.id,
        source_observation_id=observation.id,
        path=path,
        dense_query=_deferred_file_seed_query(obligation, gap, promoted_followups),
        sparse_anchors=overlap_terms[:8],
        priority=_deferred_seed_priority(observation, overlap_terms),
        scope_id=_scope_id("deferred_file_seed", obligation.id, path),
        handoff_reason=gap.missing_claim.strip(),
        purpose=ActionPurpose.DEFERRED_FILE_RESCUE,
    )
    audit["eligible"] = True
    audit["action_id"] = action.id
    audit["reason"] = "eligible_named_admission_held_same_file_implementation_alternative"
    return action, audit


def _deferred_file_seed_query(
    obligation: EvidenceObligation,
    gap: ObligationCoverage,
    promoted_followups: Sequence[str],
) -> str:
    return "\n\n".join(
        value for value in (*promoted_followups[:2], gap.missing_claim.strip(), obligation.description.strip()) if value
    )


def _test_maturation_query(decision: QualificationDecision, gap: ObligationCoverage | None = None) -> str:
    return "\n\n".join(
        value
        for value in (
            decision.local_follow_up.strip(),
            gap.missing_claim.strip() if gap is not None else "",
        )
        if value
    )


def _deferred_seed_overlap_terms(
    observation: DiscoveryObservation,
    obligation: EvidenceObligation,
    gap: ObligationCoverage,
) -> tuple[str, ...]:
    ignored = {
        "about", "across", "after", "adding", "behavior", "build", "code", "concrete", "does",
        "error", "from", "have", "including", "into", "mode", "project", "references", "repository",
        "session", "show", "source", "that", "the", "this", "through", "type", "watch", "with",
    }
    request_terms = {
        _term_stem(match.group(0))
        for match in re.finditer(r"[A-Za-z_][A-Za-z0-9_]{3,}", " ".join((obligation.description, gap.missing_claim)))
        if _term_stem(match.group(0)) not in ignored
    }
    source_terms = {
        _term_stem(term)
        for provenance in observation.provenance
        for term in provenance.matched_terms
        if _term_stem(term) not in ignored
    }
    request_overlap = request_terms & source_terms
    if not request_overlap:
        return ()
    mechanism_terms = {
        "affect", "cache", "declaration", "diagnostic", "emit", "export", "invalidat", "propagat",
        "rebuild", "signature", "state",
    }
    concrete_source_terms = {
        source_term
        for source_term in source_terms
        if source_term in mechanism_terms
    }
    return tuple(sorted(request_overlap | concrete_source_terms))


def _deferred_seed_mechanism_anchors(
    observation: DiscoveryObservation,
    obligation: EvidenceObligation,
    gap: ObligationCoverage,
) -> tuple[str, ...]:
    """Return mechanism words evidenced both by the missing claim and raw hit.

    A deferred seed is recovery for one missed implementation lead, not a
    second broad lexical search. Generic request vocabulary must therefore not
    create a seed merely because it happened to match the file.
    """
    mechanism_terms = {
        "affect", "cache", "declaration", "diagnostic", "emit", "export", "invalidat", "propagat",
        "rebuild", "signature", "state",
    }
    request_terms = {
        _term_stem(match.group(0))
        for match in re.finditer(r"[A-Za-z_][A-Za-z0-9_]{3,}", " ".join((obligation.description, gap.missing_claim)))
    }
    source_terms = {
        _term_stem(term)
        for provenance in observation.provenance
        for term in provenance.matched_terms
    }
    return tuple(sorted(request_terms & source_terms & mechanism_terms))


def _term_stem(value: str) -> str:
    term = value.casefold().strip("_-")
    if term.endswith("ies") and len(term) > 5:
        return term[:-3] + "y"
    if term.endswith("ed") and len(term) > 5:
        return term[:-2]
    if term.endswith("s") and len(term) > 4:
        return term[:-1]
    return term


def _deferred_seed_priority(observation: DiscoveryObservation, overlap_terms: Sequence[str]) -> int:
    return observation.best_rank * 100 - min(len(overlap_terms), 8) * 10


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


def _scope_id(*parts: str) -> str:
    digest = hashlib.sha1("\0".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"frontier_{digest}"


def _bound_discovery_frontiers(
    actions: Sequence[RetrievalAction],
) -> tuple[list[RetrievalAction], list[dict[str, Any]]]:
    retained: list[RetrievalAction] = []
    seen_frontier_capabilities: set[tuple[str, str]] = set()
    pruning: list[dict[str, Any]] = []
    for action in actions:
        if not action.scope_id.startswith("frontier_"):
            retained.append(action)
            continue
        capability = (
            "inspect"
            if isinstance(action, InspectDeferredObservation)
            else "within_file"
            if isinstance(action, SearchWithinFile)
            else "new_island"
            if isinstance(action, SearchNewIsland)
            else type(action).__name__
        )
        key = (action.scope_id, capability)
        if key in seen_frontier_capabilities:
            pruning.append(
                {
                    "action_id": action.id,
                    "scope_id": action.scope_id,
                    "capability": capability,
                    "reason": "frontier_capability_already_represented",
                }
            )
            continue
        seen_frontier_capabilities.add(key)
        retained.append(action)
    return retained, pruning


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


def _source_handoff_identifiers(values: Sequence[str]) -> tuple[str, ...]:
    """Keep callable names specific enough to justify a repository-wide file handoff."""
    return tuple(
        value
        for value in values
        if len(value) >= 12 and ("_" in value or any(character.isupper() for character in value[1:]))
    )
