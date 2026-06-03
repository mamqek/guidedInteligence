from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from services.retrieval.role_validation import AnchorRecord


@dataclass(frozen=True)
class RoleCompletionContext:
    role: str
    query: str
    helper_queries: Sequence[str]
    candidate_path: str
    candidate_text: str
    candidate_source_id: str
    candidate_file_role: str
    source_role: str
    source_state: str
    prior_validation_score: float
    accepted_anchors: Sequence[AnchorRecord]
    accepted_anchors_by_role: dict[str, tuple[AnchorRecord, ...]]


@dataclass(frozen=True)
class RoleCompletionScore:
    accepted: bool
    total_score: float
    threshold: float
    architecture_score: float
    path_score: float
    vocabulary_score: float
    anchor_proximity_score: float
    prior_score: float
    source_state: str
    support_paths: tuple[str, ...]
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "accepted": self.accepted,
            "total_score": round(self.total_score, 3),
            "threshold": round(self.threshold, 3),
            "architecture_score": round(self.architecture_score, 3),
            "path_score": round(self.path_score, 3),
            "vocabulary_score": round(self.vocabulary_score, 3),
            "anchor_proximity_score": round(self.anchor_proximity_score, 3),
            "prior_score": round(self.prior_score, 3),
            "source_state": self.source_state,
            "support_paths": list(self.support_paths),
            "reasons": list(self.reasons),
        }
