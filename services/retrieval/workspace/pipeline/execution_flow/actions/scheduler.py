from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from services.retrieval.workspace.pipeline.execution_flow.actions.policy import (
    ActionPool,
    ActionPurpose,
    action_pool,
    partition_actions_by_pool,
)
from services.retrieval.workspace.pipeline.execution_flow.actions.catalogue_and_execution import (
    ExpandRelationship,
    InspectDeferredObservation,
    InspectOwnerContinuation,
    InspectVerifiedLead,
    RetrievalAction,
    SearchNewIsland,
    SearchWithinFile,
)
from services.retrieval.workspace.pipeline.execution_flow.action_novelty import (
    action_suppression_reason,
    normalized_action_effect,
)


@dataclass(frozen=True)
class ScheduledRoundActions:
    """The complete, auditable action plan for one controller round."""

    normal: tuple[RetrievalAction, ...]
    deferred_file_rescue: tuple[RetrievalAction, ...]
    owner_maturation: tuple[RetrievalAction, ...]
    maturation_children: tuple[RetrievalAction, ...]
    test_maturation: tuple[RetrievalAction, ...]
    verified_lead: tuple[RetrievalAction, ...]
    suppressed: tuple[dict[str, object], ...] = ()

    @property
    def selected(self) -> tuple[RetrievalAction, ...]:
        return (
            *self.normal,
            *self.deferred_file_rescue,
            *self.owner_maturation,
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
            isinstance(action, SearchWithinFile)
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
    normal = _select_actions(
        by_pool[ActionPool.ORDINARY],
        active_root_ids,
        normal_limit,
        scope_order=active_island_ids,
        refined_paths=refined_paths,
        prefer_relationship=round_index > 1,
        attempted_effects=attempted_effects,
    )
    deferred = _select_deferred_file_seed_actions(
        by_pool[ActionPool.DEFERRED_FILE_RESCUE],
        attempted_effects=attempted_effects,
        refined_paths=refined_paths,
        normal_selected=normal,
    )
    maturation_actions = tuple(
        action
        for action in by_pool[ActionPool.OWNER_MATURATION]
        if _action_root_id(action) not in blocked_maturation_root_ids
    )
    maturation_children = tuple(
        action
        for action in maturation_actions
        if _action_root_id(action) in pending_maturation_child_roots
        and isinstance(action, SearchWithinFile)
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
    test_maturation = _select_maturation_actions(
        (),
        by_pool[ActionPool.TEST_MATURATION],
        active_root_ids,
        attempted=attempted_action_ids,
        scope_order=active_island_ids,
        refined_paths=refined_paths,
        attempted_effects=attempted_effects,
    )
    return ScheduledRoundActions(
        normal=normal,
        deferred_file_rescue=deferred,
        owner_maturation=maturation,
        maturation_children=maturation_children,
        test_maturation=test_maturation,
        verified_lead=tuple(verified_lead_actions),
        suppressed=tuple(suppression_records),
    )


def _select_actions(
    actions: Sequence[RetrievalAction],
    root_order: Sequence[str],
    limit: int,
    *,
    scope_order: Sequence[str] = (),
    refined_paths: set[str] | None = None,
    prefer_relationship: bool = False,
    attempted_effects: set[tuple[str, ...]] | None = None,
) -> tuple[RetrievalAction, ...]:
    """Rank the ordinary pool while preserving file and island diversity."""

    already_refined = refined_paths or set()
    prior_effects = attempted_effects or set()
    root_rank = {value: index for index, value in enumerate(root_order)}
    ranked = sorted(
        actions,
        key=lambda item: (
            0
            if prefer_relationship and isinstance(item, InspectOwnerContinuation)
            else 0
            if (
                prefer_relationship
                and isinstance(item, SearchWithinFile)
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
            if isinstance(item, SearchWithinFile)
            else 4
            if isinstance(item, InspectDeferredObservation)
            else 5
            if isinstance(item, ExpandRelationship)
            else 6,
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
                if item.purpose is ActionPurpose.INSPECT_DEFERRED_DISCOVERY
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
        eligible.append(action)
        used_effects.add(effect)
        if root_id:
            used_roots.add(root_id)
        if isinstance(action, SearchWithinFile):
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
                    if action.purpose is ActionPurpose.INSPECT_DEFERRED_DISCOVERY
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
    selected = [actions_by_scope[scope][0] for scope in ordered_scopes[:limit]]
    if len(selected) < limit:
        selected_ids = {item.id for item in selected}
        selected.extend(item for item in eligible if item.id not in selected_ids)
    return tuple(selected[:limit])


def _select_deferred_file_seed_actions(
    actions: Sequence[RetrievalAction],
    *,
    attempted_effects: set[tuple[str, ...]],
    refined_paths: set[str],
    normal_selected: Sequence[RetrievalAction],
) -> tuple[RetrievalAction, ...]:
    """Use the isolated file-rescue slot without displacing ordinary islands."""

    normal_paths = {
        item.path.casefold() for item in normal_selected if isinstance(item, SearchWithinFile)
    }
    candidates = tuple(
        item
        for item in actions
        if action_pool(item.purpose) is ActionPool.DEFERRED_FILE_RESCUE
        and isinstance(item, SearchWithinFile)
        and item.path.casefold() not in normal_paths
    )
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
    if isinstance(action, SearchWithinFile):
        return action.source_observation_id
    if isinstance(action, InspectOwnerContinuation):
        return action.observation_id
    return str(getattr(action, "root_observation_id", "") or "")


def _action_scope_id(action: RetrievalAction) -> str:
    return str(getattr(action, "scope_id", "") or _action_root_id(action) or action.id)


def _has_specific_exact_anchors(action: RetrievalAction) -> bool:
    return isinstance(action, SearchNewIsland) and any(
        value.startswith("_") for value in action.exact_symbol_anchors
    )
