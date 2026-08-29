from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping, Sequence

from services.retrieval.workspace.pipeline.execution_flow.actions.catalogue_and_execution import (
    ExpandRelationship,
    RetrievalAction,
)
from services.retrieval.workspace.pipeline.execution_flow.actions.scheduler import _action_effect
from services.retrieval.workspace.pipeline.execution_flow.coverage_evaluation import ObligationCoverage
from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import DiscoveryObservation
from services.retrieval.workspace.pipeline.execution_flow.evidence_qualification import QualificationDecision


MAX_PENDING_FILE_HANDOFFS = 2
PENDING_FILE_HANDOFF_TTL_ROUNDS = 2


@dataclass(frozen=True)
class PendingFileHandoff:
    """One verified catalogue action waiting for an existing ordinary slot."""

    action: ExpandRelationship
    discovered_round: int
    catalogue_rank: int


def reconcile_pending_file_handoffs(
    pending: Sequence[PendingFileHandoff],
    *,
    round_index: int,
    observations: Mapping[str, DiscoveryObservation],
    decisions: Mapping[str, QualificationDecision],
    coverage: Sequence[ObligationCoverage],
    observation_to_island: Mapping[str, str],
    active_island_ids: Sequence[str],
    attempted_effects: set[tuple[str, ...]],
) -> tuple[PendingFileHandoff, ...]:
    """Drop stale debt and refresh its island scope before scheduling."""

    active_islands = set(active_island_ids)
    unresolved = {
        item.obligation_id
        for item in coverage
        if item.status not in {"covered", "external"}
    }
    retained: list[PendingFileHandoff] = []
    used_islands: set[str] = set()
    for item in sorted(pending, key=_pending_priority):
        action = item.action
        source = observations.get(action.root_observation_id)
        decision = decisions.get(action.root_observation_id)
        island_id = observation_to_island.get(action.root_observation_id, "")
        if (
            source is None
            or source.artifact_role != "test"
            or decision is None
            or decision.disposition != "promote"
            or action.obligation_id not in unresolved
            or not island_id
            or island_id not in active_islands
            or island_id in used_islands
            or _action_effect(action) in attempted_effects
            or round_index - item.discovered_round > PENDING_FILE_HANDOFF_TTL_ROUNDS
        ):
            continue
        retained.append(replace(item, action=replace(action, scope_id=island_id)))
        used_islands.add(island_id)
        if len(retained) >= MAX_PENDING_FILE_HANDOFFS:
            break
    return tuple(retained)


def retain_pending_file_handoffs(
    pending: Sequence[PendingFileHandoff],
    catalogue_actions: Sequence[RetrievalAction],
    selected_actions: Sequence[RetrievalAction],
    *,
    round_index: int,
    observations: Mapping[str, DiscoveryObservation],
    decisions: Mapping[str, QualificationDecision],
    coverage: Sequence[ObligationCoverage],
    observation_to_island: Mapping[str, str],
    active_island_ids: Sequence[str],
    attempted_effects: set[tuple[str, ...]],
) -> tuple[PendingFileHandoff, ...]:
    """Retain only starved test-source file handoffs, with bounded diversity."""

    selected_effects = {_action_effect(action) for action in selected_actions}
    combined = [
        item for item in pending if _action_effect(item.action) not in selected_effects
    ]
    known_effects = {_action_effect(item.action) for item in combined}
    for rank, action in enumerate(catalogue_actions):
        if not _eligible_action(action, observations):
            continue
        effect = _action_effect(action)
        if effect in selected_effects or effect in attempted_effects or effect in known_effects:
            continue
        island_id = observation_to_island.get(action.root_observation_id, "")
        combined.append(
            PendingFileHandoff(
                action=replace(action, scope_id=island_id or action.scope_id),
                discovered_round=round_index,
                catalogue_rank=rank,
            )
        )
        known_effects.add(effect)
    return reconcile_pending_file_handoffs(
        combined,
        round_index=round_index,
        observations=observations,
        decisions=decisions,
        coverage=coverage,
        observation_to_island=observation_to_island,
        active_island_ids=active_island_ids,
        attempted_effects=attempted_effects,
    )


def _eligible_action(
    action: RetrievalAction,
    observations: Mapping[str, DiscoveryObservation],
) -> bool:
    if not isinstance(action, ExpandRelationship):
        return False
    source = observations.get(action.root_observation_id)
    return bool(
        action.seed_kind == "file"
        and action.cross_file_only
        and action.handoff_reason
        and source is not None
        and source.artifact_role == "test"
    )


def _pending_priority(item: PendingFileHandoff) -> tuple[int, int, str]:
    return item.discovered_round, item.catalogue_rank, item.action.id
