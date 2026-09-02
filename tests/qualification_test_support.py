from services.retrieval.workspace.pipeline.execution_flow.evidence_qualification import (
    QualificationDecision as RuntimeQualificationDecision,
)
from services.retrieval.workspace.pipeline.execution_flow.qualification_contract import (
    EvidenceAssessment,
    EvidenceDisposition,
    EvidenceKind,
    QualificationRationale,
)


def QualificationDecision(
    observation_id: str,
    disposition: str,
    support_level: str,
    reason: str,
    visible_support: tuple[str, ...] = (),
    missing_information: tuple[str, ...] = (),
    local_follow_up: str = "",
    supported_obligation_ids: tuple[str, ...] = (),
) -> RuntimeQualificationDecision:
    resolved_disposition = {
        "promote": EvidenceDisposition.RETAIN,
        "defer": EvidenceDisposition.DEFER,
        "reject": EvidenceDisposition.REJECT,
    }[disposition]
    evidence_kind = {
        "direct_evidence": EvidenceKind.DIRECT_FACT,
        "navigation_only": EvidenceKind.NAVIGATION_LEAD,
        "insufficient": EvidenceKind.INSUFFICIENT,
    }[support_level]
    obligations = tuple(supported_obligation_ids)
    return RuntimeQualificationDecision(
        observation_id=observation_id,
        assessment=EvidenceAssessment(
            disposition=resolved_disposition,
            evidence_kind=evidence_kind,
            contributing_obligation_ids=(
                obligations if resolved_disposition is not EvidenceDisposition.REJECT else ()
            ),
            individually_established_obligation_ids=(
                obligations if evidence_kind is EvidenceKind.DIRECT_FACT else ()
            ),
        ),
        rationale=QualificationRationale(
            reason=reason,
            visible_support=tuple(visible_support),
            missing_information=tuple(missing_information),
            local_follow_up=local_follow_up,
        ),
    )


def replace_qualification_decision(
    decision: RuntimeQualificationDecision,
    *,
    observation_id: str | None = None,
    disposition: str | None = None,
    support_level: str | None = None,
    supported_obligation_ids: tuple[str, ...] | None = None,
    local_follow_up: str | None = None,
) -> RuntimeQualificationDecision:
    current_disposition = {
        EvidenceDisposition.RETAIN: "promote",
        EvidenceDisposition.DEFER: "defer",
        EvidenceDisposition.REJECT: "reject",
    }[decision.assessment.disposition]
    current_support_level = {
        EvidenceKind.DIRECT_FACT: "direct_evidence",
        EvidenceKind.NAVIGATION_LEAD: "navigation_only",
        EvidenceKind.INSUFFICIENT: "insufficient",
    }[decision.assessment.evidence_kind]
    return QualificationDecision(
        observation_id or decision.observation_id,
        disposition or current_disposition,
        support_level or current_support_level,
        decision.rationale.reason,
        decision.rationale.visible_support,
        decision.rationale.missing_information,
        decision.rationale.local_follow_up if local_follow_up is None else local_follow_up,
        (
            decision.assessment.individually_established_obligation_ids
            if supported_obligation_ids is None
            else supported_obligation_ids
        ),
    )
