from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from services.retrieval.workspace.pipeline.execution_flow.actions.catalogue_and_execution import (
    ExpandRelationship,
    InspectDeferredObservation,
    InspectOwnerContinuation,
    InspectVerifiedLead,
    RetrievalAction,
    SearchNewIsland,
    ExpandWithinFileHandoff,
)
from services.retrieval.workspace.pipeline.execution_flow.actions.policy import action_pool
from services.retrieval.workspace.pipeline.execution_flow.actions.scheduler import _action_effect
from services.retrieval.workspace.pipeline.execution_flow.coverage_evaluation import ObligationCoverage
from services.retrieval.workspace.pipeline.execution_flow.evidence_islands import IslandSelection
from services.retrieval.workspace.pipeline.execution_flow.evidence_qualification import QualificationDecision


@dataclass(frozen=True)
class IslandContinuation:
    continuation_id: str
    action_ids: tuple[str, ...]
    frontier_id: str
    frontier_kind: str
    gap_id: str
    obligation_ids: tuple[str, ...]
    source_observation_id: str
    executor_kind: str
    normalized_effect: tuple[str, ...]
    grounding: str
    estimated_cost: str
    state: str
    first_seen_round: int
    last_seen_round: int
    present_in_catalogue: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "continuation_id": self.continuation_id,
            "action_ids": list(self.action_ids),
            "frontier_id": self.frontier_id,
            "frontier_kind": self.frontier_kind,
            "gap_id": self.gap_id,
            "obligation_ids": list(self.obligation_ids),
            "source_observation_id": self.source_observation_id,
            "executor_kind": self.executor_kind,
            "normalized_effect": list(self.normalized_effect),
            "grounding": self.grounding,
            "estimated_cost": self.estimated_cost,
            "state": self.state,
            "first_seen_round": self.first_seen_round,
            "last_seen_round": self.last_seen_round,
            "present_in_catalogue": self.present_in_catalogue,
        }


@dataclass(frozen=True)
class IslandFrontier:
    frontier_id: str
    frontier_kind: str
    active: bool
    established_evidence_ids: tuple[str, ...]
    established_navigation_ids: tuple[str, ...]
    unresolved_gap_ids: tuple[str, ...]
    completed_gap_ids: tuple[str, ...]
    continuations: tuple[IslandContinuation, ...]
    terminal_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "frontier_id": self.frontier_id,
            "frontier_kind": self.frontier_kind,
            "active": self.active,
            "established_evidence_ids": list(self.established_evidence_ids),
            "established_navigation_ids": list(self.established_navigation_ids),
            "unresolved_gap_ids": list(self.unresolved_gap_ids),
            "completed_gap_ids": list(self.completed_gap_ids),
            "continuations": [item.to_dict() for item in self.continuations],
            "terminal_reason": self.terminal_reason,
        }


@dataclass
class _ContinuationRecord:
    continuation_id: str
    action_ids: set[str]
    action: RetrievalAction
    frontier_id: str
    frontier_kind: str
    gap_id: str
    obligation_ids: set[str]
    source_observation_id: str
    normalized_effect: tuple[str, ...]
    grounding: str
    estimated_cost: str
    first_seen_round: int
    last_seen_round: int
    catalogue_rank: int
    present_in_catalogue: bool = True
    state: str = "available"


@dataclass
class IslandFrontierLedger:
    """Read-only projection of persistent executable controller intentions.

    The controller's existing catalogue and scheduler remain authoritative.
    This ledger deliberately has no selection method in experiment step 1.
    """

    _records: dict[tuple[str, ...], _ContinuationRecord] = field(default_factory=dict)
    _action_to_effect: dict[str, tuple[str, ...]] = field(default_factory=dict)
    _frontiers: tuple[IslandFrontier, ...] = ()

    def observe_catalogue(
        self,
        actions: Sequence[RetrievalAction],
        *,
        islands: IslandSelection,
        decisions: Mapping[str, QualificationDecision],
        coverage: Sequence[ObligationCoverage],
        round_index: int,
    ) -> tuple[IslandFrontier, ...]:
        for record in self._records.values():
            record.present_in_catalogue = False

        for catalogue_rank, action in enumerate(actions):
            effect = _action_effect(action)
            source_id = _source_observation_id(action)
            frontier_id, frontier_kind = _frontier_identity(
                action,
                source_observation_id=source_id,
                observation_to_island=islands.observation_to_island,
                active_island_ids=islands.active_island_ids,
            )
            gap_id = _gap_id(action)
            obligation_ids = set(_obligation_ids(action))
            record = self._records.get(effect)
            if record is None:
                record = _ContinuationRecord(
                    continuation_id=f"continuation_{len(self._records) + 1}",
                    action_ids={action.id},
                    action=action,
                    frontier_id=frontier_id,
                    frontier_kind=frontier_kind,
                    gap_id=gap_id,
                    obligation_ids=obligation_ids,
                    source_observation_id=source_id,
                    normalized_effect=effect,
                    grounding=_grounding(action, frontier_kind),
                    estimated_cost=_estimated_cost(action),
                    first_seen_round=round_index,
                    last_seen_round=round_index,
                    catalogue_rank=catalogue_rank,
                )
                self._records[effect] = record
            else:
                record.action_ids.add(action.id)
                record.action = action
                record.frontier_id = frontier_id
                record.frontier_kind = frontier_kind
                record.gap_id = gap_id or record.gap_id
                record.obligation_ids.update(obligation_ids)
                record.source_observation_id = source_id or record.source_observation_id
                record.last_seen_round = round_index
                record.catalogue_rank = catalogue_rank
                record.present_in_catalogue = True
            self._action_to_effect[action.id] = effect

        self._reconcile_sources(islands)
        self._expire_completed_gaps(coverage)
        self._frontiers = self._build_frontiers(islands, decisions, coverage)
        return self._frontiers

    def record_execution(self, action_id: str, *, produced_result: bool) -> None:
        effect = self._action_to_effect.get(action_id)
        if effect is None or effect not in self._records:
            return
        self._records[effect].state = "produced_gain" if produced_result else "attempted_empty"

    def continuation_for_action(self, action_id: str) -> IslandContinuation | None:
        effect = self._action_to_effect.get(action_id)
        record = self._records.get(effect) if effect is not None else None
        return _freeze_continuation(record) if record is not None else None

    def persisted_available_ordinary_actions(self) -> tuple[RetrievalAction, ...]:
        """Return only missing persisted ordinary continuations.

        Current catalogue actions must stay byte-for-byte under scheduler
        ownership; the ledger is only an additive memory source.
        """

        return tuple(
            item.action
            for item in sorted(
                self._records.values(),
                key=lambda value: (value.catalogue_rank, value.first_seen_round, value.continuation_id),
            )
            if (
                item.state == "available"
                and not item.present_in_catalogue
                and action_pool(item.action.purpose).value == "ordinary"
            )
        )

    def ordinary_scheduling_signals(
        self,
        *,
        round_index: int,
    ) -> dict[tuple[str, ...], tuple[int, int]]:
        """Return bounded wait/support signals for available ordinary effects."""

        return {
            item.normalized_effect: (
                max(0, round_index - item.first_seen_round),
                max(1, len(item.obligation_ids)),
            )
            for item in self._records.values()
            if item.state == "available"
            and action_pool(item.action.purpose).value in {"ordinary", "owner_maturation"}
        }

    def snapshot(self) -> tuple[IslandFrontier, ...]:
        return self._frontiers

    def refresh(
        self,
        *,
        islands: IslandSelection,
        decisions: Mapping[str, QualificationDecision],
        coverage: Sequence[ObligationCoverage],
    ) -> tuple[IslandFrontier, ...]:
        self._reconcile_sources(islands)
        self._expire_completed_gaps(coverage)
        self._frontiers = self._build_frontiers(islands, decisions, coverage)
        return self._frontiers

    def _reconcile_sources(self, islands: IslandSelection) -> None:
        active = set(islands.active_island_ids)
        for record in self._records.values():
            mapped = islands.observation_to_island.get(record.source_observation_id, "")
            if mapped:
                record.frontier_id = mapped
                record.frontier_kind = "active_island" if mapped in active else "inactive_island"

    def _expire_completed_gaps(self, coverage: Sequence[ObligationCoverage]) -> None:
        completed = {
            item.obligation_id for item in coverage if item.status in {"covered", "external"}
        }
        for record in self._records.values():
            if (
                record.state == "available"
                and record.obligation_ids
                and record.obligation_ids.issubset(completed)
            ):
                record.state = "expired"

    def _build_frontiers(
        self,
        islands: IslandSelection,
        decisions: Mapping[str, QualificationDecision],
        coverage: Sequence[ObligationCoverage],
    ) -> tuple[IslandFrontier, ...]:
        unresolved = tuple(
            item.obligation_id for item in coverage if item.status not in {"covered", "external"}
        )
        completed = tuple(
            item.obligation_id for item in coverage if item.status in {"covered", "external"}
        )
        island_by_id = {item.id: item for item in islands.islands}
        grouped: dict[str, list[_ContinuationRecord]] = {}
        for record in self._records.values():
            grouped.setdefault(record.frontier_id, []).append(record)
        frontier_ids = tuple(dict.fromkeys((*islands.active_island_ids, *sorted(grouped))))
        result: list[IslandFrontier] = []
        for frontier_id in frontier_ids:
            island = island_by_id.get(frontier_id)
            records = sorted(grouped.get(frontier_id, ()), key=lambda item: item.continuation_id)
            observation_ids = island.observation_ids if island is not None else ()
            direct = tuple(
                item for item in observation_ids
                if (decision := decisions.get(item)) is not None
                and decision.assessment.is_direct_fact
            )
            navigation = tuple(
                item for item in observation_ids
                if (decision := decisions.get(item)) is not None
                and decision.assessment.is_navigation
            )
            relevant_gaps = tuple(dict.fromkeys(
                gap_id
                for record in records
                for gap_id in sorted(record.obligation_ids)
                if gap_id in unresolved
            ))
            result.append(IslandFrontier(
                frontier_id=frontier_id,
                frontier_kind=(
                    "active_island" if frontier_id in islands.active_island_ids
                    else "inactive_island" if island is not None
                    else records[0].frontier_kind if records
                    else "active_island"
                ),
                active=frontier_id in islands.active_island_ids,
                established_evidence_ids=direct,
                established_navigation_ids=navigation,
                unresolved_gap_ids=relevant_gaps,
                completed_gap_ids=tuple(
                    dict.fromkeys(
                        gap_id
                        for record in records
                        for gap_id in sorted(record.obligation_ids)
                        if gap_id in completed
                    )
                ),
                continuations=tuple(_freeze_continuation(item) for item in records),
                terminal_reason=(
                    "all_known_gaps_complete" if records and all(item.state == "expired" for item in records)
                    else ""
                ),
            ))
        return tuple(result)


def _freeze_continuation(record: _ContinuationRecord) -> IslandContinuation:
    return IslandContinuation(
        continuation_id=record.continuation_id,
        action_ids=tuple(sorted(record.action_ids)),
        frontier_id=record.frontier_id,
        frontier_kind=record.frontier_kind,
        gap_id=record.gap_id,
        obligation_ids=tuple(sorted(record.obligation_ids)),
        source_observation_id=record.source_observation_id,
        executor_kind=type(record.action).__name__,
        normalized_effect=record.normalized_effect,
        grounding=record.grounding,
        estimated_cost=record.estimated_cost,
        state=record.state,
        first_seen_round=record.first_seen_round,
        last_seen_round=record.last_seen_round,
        present_in_catalogue=record.present_in_catalogue,
    )


def _source_observation_id(action: RetrievalAction) -> str:
    if isinstance(action, ExpandRelationship):
        return action.root_observation_id
    if isinstance(action, (ExpandWithinFileHandoff, InspectVerifiedLead)):
        return action.source_observation_id
    if isinstance(action, (InspectDeferredObservation, InspectOwnerContinuation)):
        return action.observation_id
    return ""


def _gap_id(action: RetrievalAction) -> str:
    return str(getattr(action, "obligation_id", "") or "")


def _obligation_ids(action: RetrievalAction) -> tuple[str, ...]:
    values = tuple(str(value) for value in getattr(action, "obligation_ids", ()) if value)
    gap_id = _gap_id(action)
    return tuple(dict.fromkeys((*values, *((gap_id,) if gap_id else ()))))


def _frontier_identity(
    action: RetrievalAction,
    *,
    source_observation_id: str,
    observation_to_island: Mapping[str, str],
    active_island_ids: Sequence[str],
) -> tuple[str, str]:
    island_id = observation_to_island.get(source_observation_id, "")
    if island_id:
        return island_id, "active_island" if island_id in active_island_ids else "inactive_island"
    if isinstance(action, SearchNewIsland):
        return f"discovery:{action.obligation_id}", "new_island_discovery"
    gap_id = _gap_id(action)
    if gap_id:
        return f"unresolved:{gap_id}", "unresolved_obligation"
    return f"grounded:{action.scope_id or source_observation_id or action.id}", "grounded_unassigned"


def _grounding(action: RetrievalAction, frontier_kind: str) -> str:
    if isinstance(action, InspectVerifiedLead):
        return "source_verified_exact_symbol"
    if isinstance(action, ExpandRelationship):
        return f"represented_{action.seed_kind}_node"
    if isinstance(action, ExpandWithinFileHandoff):
        return "represented_file_handoff" if frontier_kind.endswith("island") else "retrieved_file_lead"
    if isinstance(action, (InspectDeferredObservation, InspectOwnerContinuation)):
        return "retrieved_owner_handle"
    if isinstance(action, SearchNewIsland):
        return "unresolved_obligation_query"
    return "controller_state"


def _estimated_cost(action: RetrievalAction) -> str:
    if isinstance(action, (InspectDeferredObservation, InspectOwnerContinuation, InspectVerifiedLead)):
        return "source_disclosure"
    if isinstance(action, ExpandRelationship):
        return "structural_query"
    if isinstance(action, (ExpandWithinFileHandoff, SearchNewIsland)):
        return "retrieval_query"
    return action_pool(action.purpose).value
