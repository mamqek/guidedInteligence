from __future__ import annotations

from enum import Enum
from typing import Iterable, Protocol, TypeVar


class ActionPool(str, Enum):
    """Independent scheduler queues; the scheduler owns their actual limits."""

    ORDINARY = "ordinary"
    DEFERRED_FILE_RESCUE = "deferred_file_rescue"
    OWNER_MATURATION = "owner_maturation"
    TEST_MATURATION = "test_maturation"
    VERIFIED_LEAD = "verified_lead"
    CONTROL = "control"


class ActionPurpose(str, Enum):
    """Why an action exists, independently of the tool used to execute it."""

    INSPECT_DEFERRED_DISCOVERY = "inspect_deferred_discovery"
    DISCLOSE_DEFERRED_OWNER = "disclose_deferred_owner"
    OWNER_CONTINUATION = "owner_continuation"
    RELATIONSHIP_EXPANSION = "relationship_expansion"
    WITHIN_FILE_SEARCH = "within_file_search"
    HANDOFF_COMPLETION = "handoff_completion"
    DEFERRED_FILE_RESCUE = "deferred_file_rescue"
    OWNER_MATURATION = "owner_maturation"
    TEST_SCENARIO_MATURATION = "test_scenario_maturation"
    NEW_ISLAND_SEARCH = "new_island_search"
    VERIFIED_SOURCE_LEAD = "verified_source_lead"
    STRUCTURAL_CHILD_HANDOFF = "structural_child_handoff"
    STOP = "stop"


# This is runtime configuration, not documentation. The nearby comments explain
# why each family uses its pool; concrete caps remain enforced by the scheduler.
ACTION_POOLS: dict[ActionPurpose, ActionPool] = {
    # Ordinary exploration competes for the configured per-round action slots.
    # Inspect an unresolved raw discovery before deciding whether it is evidence.
    ActionPurpose.INSPECT_DEFERRED_DISCOVERY: ActionPool.ORDINARY,
    # Disclose the available owner after qualification deferred a folded preview.
    ActionPurpose.DISCLOSE_DEFERRED_OWNER: ActionPool.ORDINARY,
    # Reveal a later omitted section of an already identified large owner.
    ActionPurpose.OWNER_CONTINUATION: ActionPool.ORDINARY,
    # Follow represented calls/imports/inheritance from an active observation.
    ActionPurpose.RELATIONSHIP_EXPANSION: ActionPool.ORDINARY,
    # Search a known useful file for a more precise unresolved mechanism.
    ActionPurpose.WITHIN_FILE_SEARCH: ActionPool.ORDINARY,
    # Continue locally after a cross-file handoff stayed incomplete.
    ActionPurpose.HANDOFF_COMPLETION: ActionPool.ORDINARY,
    # Search for a distinct unresolved mechanism outside represented islands.
    ActionPurpose.NEW_ISLAND_SEARCH: ActionPool.ORDINARY,
    # Each bounded recovery/maturation family gets its own scheduler opportunity.
    # Rescue one strong held implementation-file alternative using a specific lead.
    ActionPurpose.DEFERRED_FILE_RESCUE: ActionPool.DEFERRED_FILE_RESCUE,
    # Improve one promoted but incomplete implementation owner.
    ActionPurpose.OWNER_MATURATION: ActionPool.OWNER_MATURATION,
    # Find scenario/assertion code behind a promising unowned test range.
    ActionPurpose.TEST_SCENARIO_MATURATION: ActionPool.TEST_MATURATION,
    # Exact source-grounded continuations share one tightly capped lead queue.
    # Inspect an exact repository node visibly named by newly disclosed source.
    ActionPurpose.VERIFIED_SOURCE_LEAD: ActionPool.VERIFIED_LEAD,
    # Follow one exact cross-file call exposed by a newly matured owner.
    ActionPurpose.STRUCTURAL_CHILD_HANDOFF: ActionPool.VERIFIED_LEAD,
    # Stop is controller flow, never evidence work.
    ActionPurpose.STOP: ActionPool.CONTROL,
}


def action_pool(purpose: ActionPurpose) -> ActionPool:
    return ACTION_POOLS[purpose]


class PurposeBearingAction(Protocol):
    purpose: ActionPurpose


ActionT = TypeVar("ActionT", bound=PurposeBearingAction)


def partition_actions_by_pool(actions: Iterable[ActionT]) -> dict[ActionPool, tuple[ActionT, ...]]:
    """Place each action in exactly one scheduler queue."""

    grouped: dict[ActionPool, list[ActionT]] = {pool: [] for pool in ActionPool}
    for action in actions:
        grouped[action_pool(action.purpose)].append(action)
    return {pool: tuple(items) for pool, items in grouped.items()}
