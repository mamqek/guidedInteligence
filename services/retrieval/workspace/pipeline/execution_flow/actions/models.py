from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.retrieval.workspace.pipeline.execution_flow.actions.policy import ActionPurpose
from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import DiscoveryObservation


@dataclass(frozen=True)
class InspectDeferredObservation:
    id: str
    observation_id: str
    requested_range: tuple[int, int]
    reason: str
    priority: int = 0
    scope_id: str = ""
    purpose: ActionPurpose = ActionPurpose.DISCLOSE_DEFERRED_OWNER


@dataclass(frozen=True)
class InspectOwnerContinuation:
    """Show one omitted, later section of an already identified owner."""

    id: str
    obligation_id: str
    observation_id: str
    requested_range: tuple[int, int]
    owner_range: tuple[int, int]
    reason: str
    priority: int = 0
    scope_id: str = ""
    purpose: ActionPurpose = ActionPurpose.OWNER_CONTINUATION


@dataclass(frozen=True)
class ExpandRelationship:
    id: str
    obligation_id: str
    root_observation_id: str
    root_node_id: str
    direction: str
    edge_kinds: tuple[str, ...]
    need: str
    max_results: int = 3
    scope_id: str = ""
    handoff_reason: str = ""
    seed_kind: str = "owner"
    target_symbol_anchors: tuple[str, ...] = ()
    target_term_anchors: tuple[str, ...] = ()
    cross_file_only: bool = False
    obligation_ids: tuple[str, ...] = ()
    purpose: ActionPurpose = ActionPurpose.RELATIONSHIP_EXPANSION


@dataclass(frozen=True)
class SearchWithinFile:
    id: str
    obligation_id: str
    source_observation_id: str
    path: str
    dense_query: str
    sparse_anchors: tuple[str, ...] = ()
    result_limit: int = 3
    priority: int = 0
    scope_id: str = ""
    handoff_reason: str = ""
    # This hint can corroborate that a file was retrieved for the request, but
    # never turns a rejected short header into evidence or a graph seed.
    file_trigger_hint_observation_ids: tuple[str, ...] = ()
    purpose: ActionPurpose = ActionPurpose.WITHIN_FILE_SEARCH


@dataclass(frozen=True)
class SearchNewIsland:
    id: str
    obligation_id: str
    dense_query: str
    sparse_anchors: tuple[str, ...] = ()
    exact_symbol_anchors: tuple[str, ...] = ()
    exact_path_anchors: tuple[str, ...] = ()
    result_limit: int = 6
    scope_id: str = ""
    purpose: ActionPurpose = ActionPurpose.NEW_ISLAND_SEARCH


@dataclass(frozen=True)
class InspectVerifiedLead:
    """Disclose one repository node named by a newly grounded source-code lead."""

    id: str
    obligation_id: str
    source_observation_id: str
    target: str
    target_node_id: str
    target_path: str
    target_line_start: int
    target_line_end: int
    target_symbol: str
    reason: str
    discovered_round: int
    scope_id: str = ""
    purpose: ActionPurpose = ActionPurpose.VERIFIED_SOURCE_LEAD


@dataclass(frozen=True)
class StopRetrieval:
    id: str
    reason_code: str
    scope_id: str = ""
    purpose: ActionPurpose = ActionPurpose.STOP


RetrievalAction = (
    InspectDeferredObservation
    | InspectOwnerContinuation
    | InspectVerifiedLead
    | SearchWithinFile
    | ExpandRelationship
    | SearchNewIsland
    | StopRetrieval
)


@dataclass(frozen=True)
class ActionCatalogue:
    actions: tuple[RetrievalAction, ...]
    unavailable: tuple[dict[str, Any], ...]
    tool_calls: int


@dataclass(frozen=True)
class ActionExecution:
    action_id: str
    observations: tuple[DiscoveryObservation, ...]
    edges: tuple[dict[str, Any], ...]
    tool_calls: int
    status: str
