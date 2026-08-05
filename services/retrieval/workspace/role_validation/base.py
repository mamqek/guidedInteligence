from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence


@dataclass(frozen=True)
class AnchorRecord:
    role: str
    path: str
    source_id: str
    symbol: str | None
    text: str
    line_start: int = 1


@dataclass(frozen=True)
class AnchorSupport:
    accepted_anchors: Mapping[str, Sequence[AnchorRecord]]
    dependency_paths_by_anchor: Mapping[str, Sequence[str]]
    call_paths_by_anchor: Mapping[str, Sequence[str]]

    def anchors_for_roles(self, roles: Sequence[str]) -> tuple[AnchorRecord, ...]:
        anchors: list[AnchorRecord] = []
        for role in roles:
            anchors.extend(self.accepted_anchors.get(role, ()))
        return tuple(anchors)


@dataclass(frozen=True)
class RoleValidationContext:
    role: str
    query: str
    helper_queries: Sequence[str]
    candidate_path: str
    candidate_text: str
    candidate_source_id: str
    candidate_file_role: str
    dependency_paths: Sequence[str]
    call_paths: Sequence[str]
    anchor_support: AnchorSupport


@dataclass(frozen=True)
class RoleScoreBreakdown:
    local_intent_score: float
    role_path_score: float
    dependency_support_score: float
    anchor_proximity_score: float
    call_flow_score: float
    total_score: float
    threshold: float
    acceptance_source: str
    reasons: tuple[str, ...]


class RoleValidator(Protocol):
    role: str

    def score(self, context: RoleValidationContext) -> RoleScoreBreakdown:
        ...
