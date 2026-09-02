from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Mapping, Sequence

if TYPE_CHECKING:
    from services.retrieval.workspace.pipeline.execution_flow.actions.pending_file_handoffs import PendingFileHandoff

from services.retrieval.workspace.pipeline.execution_flow.actions.policy import (
    ActionPool,
    ActionPurpose,
    action_pool,
    partition_actions_by_pool,
)
from services.retrieval.workspace.pipeline.execution_flow.actions.catalogue_and_execution import (
    ExpandRelationship,
    InspectDeferredObservation,
    InspectDormantFileAlternatives,
    InspectOwnerChallengers,
    InspectOwnerContinuation,
    InspectVerifiedLead,
    RetrievalAction,
    SearchNewIsland,
    ExpandWithinFileHandoff,
)
from services.retrieval.workspace.pipeline.execution_flow.actions.models import DormantFileHypothesisStrength
from services.retrieval.workspace.pipeline.execution_flow.action_novelty import (
    action_suppression_reason,
    normalized_action_effect,
)


@dataclass(frozen=True)
class ScheduledRoundActions:
    """The complete, auditable action plan for one controller round."""

    normal: tuple[RetrievalAction, ...]
    deferred_file_rescue: tuple[RetrievalAction, ...]
    test_maturation: tuple[RetrievalAction, ...]
    verified_lead: tuple[RetrievalAction, ...]
    pending_file_handoff: tuple[RetrievalAction, ...] = ()
    suppressed: tuple[dict[str, object], ...] = ()

    @property
    def selected(self) -> tuple[RetrievalAction, ...]:
        return (
            *self.normal,
            *self.deferred_file_rescue,
            *self.test_maturation,
            *self.verified_lead,
        )


def schedule_round_actions(
    actions: Sequence[RetrievalAction],
    *,
    active_root_ids: Sequence[str],
    active_island_ids: Sequence[str],
    normal_limit: int,
    round_index: int,
    refined_paths: set[str],
    attempted_action_ids: set[str],
    attempted_effects: set[tuple[str, ...]],
    pending_maturation_child_roots: set[str],
    blocked_maturation_root_ids: set[str],
    verified_lead_actions: Sequence[RetrievalAction],
    pending_file_handoffs: Sequence[PendingFileHandoff] = (),
    additional_ordinary_actions: Sequence[RetrievalAction] = (),
    continuation_priority_by_effect: Mapping[tuple[str, ...], tuple[int, int]] | None = None,
    dormant_file_attempt_limit: int = 1,
    dormant_file_followup_floor: DormantFileHypothesisStrength | None = None,
) -> ScheduledRoundActions:
    """Select every queue without letting one pool silently consume another.

    The ordinary pool receives the configured beam. Deferred-file rescue,
    implementation maturation, test maturation, and verified leads each retain
    their existing isolated one-action slot. This function centralizes selection
    only; producers and executors remain independent.
    """

    suppression_records: list[dict[str, object]] = []
    novel_actions: list[RetrievalAction] = []
    for action in actions:
        is_pending_maturation_child = (
            isinstance(action, ExpandWithinFileHandoff)
            and _action_root_id(action) in pending_maturation_child_roots
            and bool(action.handoff_reason)
        )
        suppression = None if is_pending_maturation_child else action_suppression_reason(
            action, completed_effects=tuple(attempted_effects),
        )
        if suppression is not None:
            suppression_records.append(suppression)
        else:
            novel_actions.append(action)
    by_pool = partition_actions_by_pool(novel_actions)
    maturation_actions = tuple(
        action
        for action in by_pool[ActionPool.OWNER_MATURATION]
        if _action_root_id(action) not in blocked_maturation_root_ids
    )
    maturation_children = tuple(
        action
        for action in maturation_actions
        if _action_root_id(action) in pending_maturation_child_roots
        and isinstance(action, ExpandWithinFileHandoff)
        and bool(action.handoff_reason)
    )
    maturation = _select_maturation_actions(
        maturation_children,
        maturation_actions,
        active_root_ids,
        attempted=attempted_action_ids,
        scope_order=active_island_ids,
        refined_paths=refined_paths,
        attempted_effects=attempted_effects,
    )
    ordinary_candidates = (
        *by_pool[ActionPool.ORDINARY],
        *maturation,
        *additional_ordinary_actions,
    )
    if dormant_file_followup_floor is not None:
        ordinary_candidates = tuple(
            action
            for action in ordinary_candidates
            if not isinstance(action, InspectDormantFileAlternatives)
            or action.hypothesis_strength.is_no_weaker_than(dormant_file_followup_floor)
        )
    if _dormant_file_attempt_count(attempted_effects) >= dormant_file_attempt_limit:
        ordinary_candidates = tuple(
            action
            for action in ordinary_candidates
            if not isinstance(action, InspectDormantFileAlternatives)
        )
    normal = _select_actions(
        ordinary_candidates,
        active_root_ids,
        normal_limit,
        scope_order=active_island_ids,
        refined_paths=refined_paths,
        prefer_relationship=round_index > 1,
        attempted_effects=attempted_effects,
        continuation_priority_by_effect=continuation_priority_by_effect,
    )
    normal = _reserve_dormant_file_alternatives(
        normal,
        ordinary_candidates,
        normal_limit=normal_limit,
        attempted_effects=attempted_effects,
        attempt_limit=dormant_file_attempt_limit,
    )
    normal, pending_selected = _reserve_pending_file_handoff(
        normal,
        pending_file_handoffs,
        normal_limit=normal_limit,
        round_index=round_index,
        attempted_effects=attempted_effects,
    )
    deferred = _select_deferred_file_seed_actions(
        by_pool[ActionPool.DEFERRED_FILE_RESCUE],
        attempted_effects=attempted_effects,
        refined_paths=refined_paths,
        normal_selected=normal,
    )
    test_maturation = _select_maturation_actions(
        (),
        by_pool[ActionPool.TEST_MATURATION],
        active_root_ids,
        attempted=attempted_action_ids,
        scope_order=active_island_ids,
        refined_paths=refined_paths,
        attempted_effects=attempted_effects,
    )
    novel_verified = []
    for action in verified_lead_actions:
        suppression = action_suppression_reason(action, completed_effects=tuple(attempted_effects))
        if suppression is not None:
            suppression_records.append(suppression)
        else:
            novel_verified.append(action)
    return ScheduledRoundActions(
        normal=normal,
        deferred_file_rescue=deferred,
        test_maturation=test_maturation,
        verified_lead=tuple(novel_verified[:1]),
        pending_file_handoff=pending_selected,
        suppressed=tuple(suppression_records),
    )


def _reserve_dormant_file_alternatives(
    normal: Sequence[RetrievalAction],
    ordinary_candidates: Sequence[RetrievalAction],
    *,
    normal_limit: int,
    attempted_effects: set[tuple[str, ...]],
    attempt_limit: int,
) -> tuple[RetrievalAction, ...]:
    """Reserve a bounded dormant-file opportunity within the ordinary beam."""

    if normal_limit <= 0:
        return tuple(normal)
    if _dormant_file_attempt_count(attempted_effects) >= attempt_limit:
        return tuple(normal)
    dormant = next(
        (
            action
            for action in ordinary_candidates
            if isinstance(action, InspectDormantFileAlternatives)
            and _action_effect(action) not in attempted_effects
        ),
        None,
    )
    if dormant is None or any(_action_effect(item) == _action_effect(dormant) for item in normal):
        return tuple(normal)
    kept = tuple(item for item in normal if _action_scope_id(item) != _action_scope_id(dormant))
    if normal_limit == 1:
        return (dormant,)
    return tuple((*kept[: normal_limit - 1], dormant))


def _dormant_file_attempt_count(attempted_effects: set[tuple[str, ...]]) -> int:
    return sum(bool(effect and effect[0] == "inspect_dormant_file") for effect in attempted_effects)


def select_ordinary_backfill_action(
    actions: Sequence[RetrievalAction],
    *,
    active_root_ids: Sequence[str],
    active_island_ids: Sequence[str],
    normal_limit: int,
    round_index: int,
    refined_paths: set[str],
    attempted_action_ids: set[str],
    attempted_effects: set[tuple[str, ...]],
    pending_maturation_child_roots: set[str],
    blocked_maturation_root_ids: set[str],
    pending_file_handoffs: Sequence[PendingFileHandoff] = (),
    occupied_scope_ids: set[str] | None = None,
    continuation_priority_by_effect: Mapping[tuple[str, ...], tuple[int, int]] | None = None,
) -> RetrievalAction | None:
    """Choose one novel ordinary replacement after an empty execution.

    The ordinary scheduler remains the ranking authority. Auxiliary pools are
    deliberately ignored, and an unoccupied island is preferred when one is
    available. The caller owns the bounded retry allowance.
    """

    schedule = schedule_round_actions(
        actions,
        active_root_ids=active_root_ids,
        active_island_ids=active_island_ids,
        normal_limit=normal_limit,
        round_index=round_index,
        refined_paths=refined_paths,
        attempted_action_ids=attempted_action_ids,
        attempted_effects=attempted_effects,
        pending_maturation_child_roots=pending_maturation_child_roots,
        blocked_maturation_root_ids=blocked_maturation_root_ids,
        verified_lead_actions=(),
        pending_file_handoffs=pending_file_handoffs,
        continuation_priority_by_effect=continuation_priority_by_effect,
    )
    occupied = occupied_scope_ids or set()
    return next(
        (action for action in schedule.normal if _action_scope_id(action) not in occupied),
        schedule.normal[0] if schedule.normal else None,
    )


def _reserve_pending_file_handoff(
    normal: Sequence[RetrievalAction],
    pending: Sequence[PendingFileHandoff],
    *,
    normal_limit: int,
    round_index: int,
    attempted_effects: set[tuple[str, ...]],
) -> tuple[tuple[RetrievalAction, ...], tuple[RetrievalAction, ...]]:
    """Use one existing ordinary slot for the oldest still-novel retained handoff."""

    if round_index <= 1 or normal_limit <= 0:
        return tuple(normal), ()
    eligible = [
        item.action
        for item in pending
        if _action_effect(item.action) not in attempted_effects
    ]
    if not eligible:
        return tuple(normal), ()
    pending_action = eligible[0]
    pending_effect = _action_effect(pending_action)
    natural = next((item for item in normal if _action_effect(item) == pending_effect), None)
    if natural is not None:
        return tuple(normal), (natural,)
    compatible = [
        item
        for item in normal
        if _action_effect(item) != pending_effect
        and _action_root_id(item) != _action_root_id(pending_action)
        and _action_scope_id(item) != _action_scope_id(pending_action)
    ]
    kept = compatible[: max(normal_limit - 1, 0)]
    return tuple((*kept, pending_action)), (pending_action,)


def _select_actions(
    actions: Sequence[RetrievalAction],
    root_order: Sequence[str],
    limit: int,
    *,
    scope_order: Sequence[str] = (),
    refined_paths: set[str] | None = None,
    prefer_relationship: bool = False,
    attempted_effects: set[tuple[str, ...]] | None = None,
    continuation_priority_by_effect: Mapping[tuple[str, ...], tuple[int, int]] | None = None,
) -> tuple[RetrievalAction, ...]:
    """Rank the ordinary pool while preserving file and island diversity."""

    already_refined = refined_paths or set()
    prior_effects = attempted_effects or set()
    continuation_signals = continuation_priority_by_effect or {}
    root_rank = {value: index for index, value in enumerate(root_order)}
    ranked = sorted(
        actions,
        key=lambda item: (
            0
            if prefer_relationship and isinstance(item, InspectOwnerContinuation)
            else 0
            if (
                prefer_relationship
                and isinstance(item, ExpandWithinFileHandoff)
                and item.purpose is ActionPurpose.HANDOFF_COMPLETION
            )
            else 1
            if (
                prefer_relationship
                and isinstance(item, ExpandRelationship)
                and item.seed_kind == "file"
                and bool(item.handoff_reason)
            )
            else 2
            if isinstance(item, InspectOwnerContinuation)
            else 3
            if isinstance(item, ExpandWithinFileHandoff)
            else 4
            if isinstance(item, InspectDormantFileAlternatives)
            else 5
            if isinstance(item, InspectDeferredObservation)
            else 6
            if isinstance(item, ExpandRelationship)
            else 7,
            getattr(item, "priority", 0) if isinstance(item, ExpandWithinFileHandoff) else 0,
            root_rank.get(_action_root_id(item), 10_000),
            getattr(item, "obligation_id", ""),
            getattr(item, "priority", 0),
            item.id,
        ),
    )
    available_file_hypotheses = {
        item.path.casefold()
        for item in ranked
        if isinstance(item, ExpandWithinFileHandoff) and item.path.casefold() not in already_refined
    }
    if limit > 1 and (prefer_relationship or len(available_file_hypotheses) < limit):
        exact_identifier_hypothesis = next(
            (item for item in ranked if _has_specific_exact_anchors(item)), None
        )
        relationship_hypothesis = (
            exact_identifier_hypothesis
            or next((item for item in ranked if isinstance(item, ExpandRelationship)), None)
            if prefer_relationship or len(available_file_hypotheses) == 1
            else None
        )
        # Keep one ordinary slot available for a disconnected hypothesis instead
        # of letting local inspection consume the entire configured beam.
        deferred_hypothesis = next(
            (
                item
                for item in ranked
                if item.purpose in {
                    ActionPurpose.DORMANT_FILE_ALTERNATIVES,
                    ActionPurpose.INSPECT_DEFERRED_DISCOVERY,
                }
            ),
            None,
        )
        independent_hypothesis = relationship_hypothesis or deferred_hypothesis or next(
            (item for item in ranked if isinstance(item, SearchNewIsland)), None
        )
        if independent_hypothesis is not None:
            ranked = [item for item in ranked if item is not independent_hypothesis]
            ranked.insert(1 if ranked else 0, independent_hypothesis)
    eligible: list[RetrievalAction] = []
    used_roots: set[str] = set()
    used_paths: set[str] = set()
    used_effects: set[tuple[str, ...]] = set()
    for action in ranked:
        if _action_effect(action) in prior_effects:
            continue
        if isinstance(action, ExpandWithinFileHandoff) and action.path.casefold() in already_refined:
            continue
        if isinstance(action, ExpandWithinFileHandoff) and action.path.casefold() in used_paths:
            continue
        root_id = _action_root_id(action)
        if root_id and root_id in used_roots:
            continue
        effect = _action_effect(action)
        if effect in used_effects:
            continue
        eligible.append(action)
        used_effects.add(effect)
        if root_id:
            used_roots.add(root_id)
        if isinstance(action, ExpandWithinFileHandoff):
            used_paths.add(action.path.casefold())
    actions_by_scope: dict[str, list[RetrievalAction]] = {}
    for action in eligible:
        actions_by_scope.setdefault(_action_scope_id(action), []).append(action)
    ordered_scopes = [scope for scope in scope_order if scope in actions_by_scope]
    ordered_scopes.extend(scope for scope in actions_by_scope if scope not in ordered_scopes)
    if limit > 1:
        preferred_distinct = (
            next((action for action in eligible if _has_specific_exact_anchors(action)), None)
            or (
                next((action for action in eligible if isinstance(action, ExpandRelationship)), None)
                if prefer_relationship
                else None
            )
            or next(
                (
                    action
                    for action in eligible
                    if action.purpose in {
                        ActionPurpose.DORMANT_FILE_ALTERNATIVES,
                        ActionPurpose.INSPECT_DEFERRED_DISCOVERY,
                    }
                    or isinstance(action, SearchNewIsland)
                ),
                None,
            )
        )
        independent_scope = _action_scope_id(preferred_distinct) if preferred_distinct is not None else ""
        if independent_scope and independent_scope in ordered_scopes and (
            prefer_relationship or len(ordered_scopes) < limit
        ):
            ordered_scopes.remove(independent_scope)
            ordered_scopes.insert(1 if ordered_scopes else 0, independent_scope)
    # Apply starvation protection after other scope reservations so a later
    # reordering rule cannot silently displace it. Rounds one and two remain
    # unchanged; after surviving two complete scheduling losses, at most one
    # grounded continuation may use the second existing ordinary slot.
    # Recurrence only breaks equal-age ties.
    aged_continuations = [
        (
            action,
            *continuation_signals.get(_action_effect(action), (0, 1)),
        )
        for action in eligible
        if _is_age_eligible_continuation(action)
        and continuation_signals.get(_action_effect(action), (0, 1))[0] >= 2
    ]
    if limit > 1 and aged_continuations:
        aged_action, _wait_rounds, _obligation_count = min(
            aged_continuations,
            key=lambda item: (
                -min(item[1], 2),
                -min(item[2], 4),
                root_rank.get(_action_root_id(item[0]), 10_000),
                item[0].id,
            ),
        )
        aged_scope = _action_scope_id(aged_action)
        if aged_scope in ordered_scopes and aged_scope not in ordered_scopes[:limit]:
            ordered_scopes.remove(aged_scope)
            ordered_scopes.insert(1, aged_scope)
    selected = [actions_by_scope[scope][0] for scope in ordered_scopes[:limit]]
    if len(selected) < limit:
        selected_ids = {item.id for item in selected}
        selected.extend(item for item in eligible if item.id not in selected_ids)
    return tuple(selected[:limit])


def _is_age_eligible_continuation(action: RetrievalAction) -> bool:
    """Limit waiting-age fairness to already grounded, bounded continuations."""

    return isinstance(
        action,
        (
            InspectOwnerContinuation,
            ExpandRelationship,
            ExpandWithinFileHandoff,
            InspectDeferredObservation,
        ),
    )


def _select_deferred_file_seed_actions(
    actions: Sequence[RetrievalAction],
    *,
    attempted_effects: set[tuple[str, ...]],
    refined_paths: set[str],
    normal_selected: Sequence[RetrievalAction],
) -> tuple[RetrievalAction, ...]:
    """Use the isolated file-rescue slot without displacing ordinary islands."""

    normal_paths = {
        item.path.casefold() for item in normal_selected if isinstance(item, ExpandWithinFileHandoff)
    }
    candidates = tuple(
        item
        for item in actions
        if action_pool(item.purpose) is ActionPool.DEFERRED_FILE_RESCUE
        and isinstance(item, (ExpandWithinFileHandoff, InspectOwnerChallengers))
        and item.path.casefold() not in normal_paths
    )
    direct_challengers = tuple(
        item for item in candidates if isinstance(item, InspectOwnerChallengers)
    )
    # A representation challenger discloses the already-retrieved owner that
    # could replace the weak primary. Prefer it to another same-file search.
    if direct_challengers:
        candidates = direct_challengers
    return _select_actions(
        candidates,
        (),
        1,
        refined_paths=refined_paths,
        attempted_effects=attempted_effects,
    )


def _select_maturation_actions(
    children: Sequence[RetrievalAction],
    actions: Sequence[RetrievalAction],
    active_root_ids: Sequence[str],
    *,
    attempted: set[str],
    scope_order: Sequence[str],
    refined_paths: set[str],
    attempted_effects: set[tuple[str, ...]],
) -> tuple[RetrievalAction, ...]:
    """Use one maturation slot, preferring the direct child of prior maturation."""

    if children:
        eligible_children = tuple(action for action in children if action.id not in attempted)
        if eligible_children:
            return (eligible_children[0],)
    return _select_actions(
        actions,
        active_root_ids,
        1,
        scope_order=scope_order,
        refined_paths=refined_paths,
        attempted_effects=attempted_effects,
    )


def _action_effect(action: RetrievalAction) -> tuple[str, ...]:
    return normalized_action_effect(action)


def _action_root_id(action: RetrievalAction) -> str:
    if isinstance(action, InspectVerifiedLead):
        return action.source_observation_id
    if isinstance(action, ExpandWithinFileHandoff):
        return action.source_observation_id
    if isinstance(action, InspectOwnerChallengers):
        return action.primary_observation_ids[0] if action.primary_observation_ids else ""
    if isinstance(action, InspectOwnerContinuation):
        return action.observation_id
    return str(getattr(action, "root_observation_id", "") or "")


def _action_scope_id(action: RetrievalAction) -> str:
    return str(getattr(action, "scope_id", "") or _action_root_id(action) or action.id)


def _has_specific_exact_anchors(action: RetrievalAction) -> bool:
    return isinstance(action, SearchNewIsland) and any(
        value.startswith("_") for value in action.exact_symbol_anchors
    )
