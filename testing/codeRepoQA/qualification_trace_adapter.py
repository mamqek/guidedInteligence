"""Offline adapter for qualification decisions stored in old and new run traces."""
from __future__ import annotations

from typing import Any, Mapping

from services.retrieval.workspace.pipeline.execution_flow.evidence_qualification import QualificationDecision
from services.retrieval.workspace.pipeline.execution_flow.qualification_contract import (
    EvidenceAssessment,
    EvidenceDisposition,
    EvidenceKind,
    QualificationRationale,
)


def qualification_decision_from_trace(row: Mapping[str, Any]) -> QualificationDecision:
    assessment = row.get("assessment")
    rationale = row.get("rationale")
    if isinstance(assessment, Mapping) and isinstance(rationale, Mapping):
        return QualificationDecision(
            observation_id=str(row.get("observation_id") or ""),
            assessment=EvidenceAssessment.from_mapping(assessment),
            rationale=QualificationRationale.from_mapping(rationale, max_reason_chars=10_000),
        )

    disposition = {
        "promote": EvidenceDisposition.RETAIN,
        "defer": EvidenceDisposition.DEFER,
        "reject": EvidenceDisposition.REJECT,
    }[str(row.get("disposition") or "")]
    evidence_kind = {
        "direct_evidence": EvidenceKind.DIRECT_FACT,
        "navigation_only": EvidenceKind.NAVIGATION_LEAD,
        "insufficient": EvidenceKind.INSUFFICIENT,
    }[str(row.get("support_level") or "")]
    obligations = tuple(str(value) for value in row.get("supported_obligation_ids", ()) if str(value))
    contributions = obligations if disposition is not EvidenceDisposition.REJECT else ()
    return QualificationDecision(
        observation_id=str(row.get("observation_id") or ""),
        assessment=EvidenceAssessment(
            disposition=disposition,
            evidence_kind=evidence_kind,
            contributing_obligation_ids=contributions,
            individually_established_obligation_ids=(
                obligations if evidence_kind is EvidenceKind.DIRECT_FACT else ()
            ),
        ),
        rationale=QualificationRationale(
            reason=str(row.get("reason") or ""),
            visible_support=tuple(str(value) for value in row.get("visible_support", ()) if str(value)),
            missing_information=tuple(
                str(value) for value in row.get("missing_information", ()) if str(value)
            ),
            local_follow_up=str(row.get("local_follow_up") or ""),
        ),
    )
