from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol, Sequence

from core.models import ConversationState, EvidenceItem, OrchestratorDecision
from core.source_policy import SourceCategory


@dataclass(frozen=True)
class RetrievalPlan:
    """Source plan produced before candidate retrieval runs."""

    #: Conversation this retrieval plan belongs to.
    conversation_id: str
    #: Ordered source categories that retrieval must consult.
    ordered_sources: tuple[SourceCategory, ...]
    #: Query text derived from the current user request and policy decision.
    query: str
    #: Optional structured planning details, such as stage or policy reason.
    metadata: Mapping[str, str] = field(default_factory=dict)


class RetrievalService(Protocol):
    """Interface for pluggable retrieval implementations."""

    def plan(self, state: ConversationState, decision: OrchestratorDecision) -> RetrievalPlan:
        """Create a source-aware retrieval plan from state and policy."""

        ...

    def retrieve(self, plan: RetrievalPlan) -> Sequence[EvidenceItem]:
        """Return evidence items that follow the supplied retrieval plan."""

        ...
