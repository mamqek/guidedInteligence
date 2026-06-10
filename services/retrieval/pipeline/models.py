from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from core.source_policy import SourceCategory
from services.retrieval.pipeline.constants import MAX_BUCKET_SNIPPET_PREVIEW_COUNT
from services.retrieval.tools import ToolObservation


@dataclass(frozen=True)
class RetrievalCandidate:
    candidate_id: str
    source_category: SourceCategory
    retrieval_path: str
    text: str
    score: float
    source_id: str
    path: str | None
    line_range: str | None
    metadata: Mapping[str, str]


@dataclass(frozen=True)
class RoleValidationResult:
    accepted: bool
    reason: str
    local_intent_score: float
    role_path_score: float
    dependency_support_score: float
    anchor_proximity_score: float
    call_flow_score: float
    total_score: float
    threshold: float
    acceptance_source: str
    symbol: str | None
    dependency_paths: tuple[str, ...]
    call_paths: tuple[str, ...]
    anchor_paths: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "reason": self.reason,
            "local_intent_score": round(self.local_intent_score, 3),
            "role_path_score": round(self.role_path_score, 3),
            "dependency_support_score": round(self.dependency_support_score, 3),
            "anchor_proximity_score": round(self.anchor_proximity_score, 3),
            "call_flow_score": round(self.call_flow_score, 3),
            "total_score": round(self.total_score, 3),
            "threshold": round(self.threshold, 3),
            "acceptance_source": self.acceptance_source,
            "symbol": self.symbol or "",
            "dependency_paths": list(self.dependency_paths),
            "call_paths": list(self.call_paths),
            "anchor_paths": list(self.anchor_paths),
        }


@dataclass(frozen=True)
class RoleCandidateEvaluation:
    candidate: RetrievalCandidate
    validation: RoleValidationResult
    stage: str = "initial"
    source_role: str = ""


@dataclass(frozen=True)
class PreparedRoleBucket:
    role: str
    query: str
    helper_queries: tuple[str, ...]
    observations: tuple[ToolObservation, ...]
    candidates: tuple[RetrievalCandidate, ...]


@dataclass(frozen=True)
class DeterministicCoverageGate:
    satisfied: bool
    role_status: Mapping[str, str]
    missing_roles: tuple[str, ...]
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "satisfied": self.satisfied,
            "role_status": dict(self.role_status),
            "missing_roles": list(self.missing_roles),
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class RoleRetrievalBucket:
    role: str
    query: str
    helper_queries: tuple[str, ...]
    observations: tuple[ToolObservation, ...]
    retrieved_candidates: tuple[RetrievalCandidate, ...]
    evaluations: tuple[RoleCandidateEvaluation, ...]
    accepted_candidates: tuple[RetrievalCandidate, ...]
    rejected_refs: tuple[str, ...]
    validation_notes: tuple[str, ...]
    missing_reason: str
    role_status: str = "missing"
    satisfying_refs: tuple[str, ...] = ()
    snippet_assessment: tuple[Mapping[str, str], ...] = ()
    satisfaction_source: str = "initial"

    def to_dict(self) -> dict[str, Any]:
        from services.retrieval.pipeline.snippet_level import salient_candidate_excerpt, snippet_quality_for_ref

        return {
            "role": self.role,
            "query": self.query,
            "helper_queries": list(self.helper_queries),
            "role_status": self.role_status,
            "satisfaction_source": self.satisfaction_source,
            "retrieved_refs": [candidate.source_id for candidate in self.retrieved_candidates],
            "accepted_refs": [candidate.source_id for candidate in self.accepted_candidates],
            "satisfying_refs": list(self.satisfying_refs),
            "rejected_refs": list(self.rejected_refs),
            "validation_notes": list(self.validation_notes),
            "missing_reason": self.missing_reason,
            "snippet_assessment": [dict(item) for item in self.snippet_assessment],
            "evaluations": [
                {
                    "ref": evaluation.candidate.source_id,
                    "path": evaluation.candidate.path or "",
                    "stage": evaluation.stage,
                    "source_role": evaluation.source_role or self.role,
                    "validation": evaluation.validation.to_dict(),
                }
                for evaluation in self.evaluations
            ],
            "snippets": [
                {
                    "ref": candidate.source_id,
                    "path": candidate.path or "",
                    "line_range": candidate.line_range or "",
                    "file_role": candidate.metadata.get("file_role", ""),
                    "snippet_quality": snippet_quality_for_ref(candidate.source_id, self.snippet_assessment),
                    "satisfies_role": candidate.source_id in set(self.satisfying_refs),
                    "snippet": salient_candidate_excerpt(candidate, limit=500),
                }
                for candidate in self.accepted_candidates[:MAX_BUCKET_SNIPPET_PREVIEW_COUNT]
            ],
        }


@dataclass(frozen=True)
class RetrievalSynthesisDecision:
    acceptance_satisfied: bool
    missing_areas: tuple[str, ...]
    accepted_anchor_refs: tuple[str, ...]
    rejected_anchor_refs: tuple[str, ...]
    snippet_assessment: tuple[Mapping[str, str], ...]
    stop_reason: str
    follow_up_queries: tuple[Mapping[str, str], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "acceptance_satisfied": self.acceptance_satisfied,
            "missing_areas": list(self.missing_areas),
            "accepted_anchor_refs": list(self.accepted_anchor_refs),
            "rejected_anchor_refs": list(self.rejected_anchor_refs),
            "snippet_assessment": [dict(item) for item in self.snippet_assessment],
            "stop_reason": self.stop_reason,
            "follow_up_queries": [dict(item) for item in self.follow_up_queries],
        }
