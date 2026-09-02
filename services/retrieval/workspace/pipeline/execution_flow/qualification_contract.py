from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Mapping, Sequence


class EvidenceDisposition(StrEnum):
    RETAIN = "retain"
    DEFER = "defer"
    REJECT = "reject"


class EvidenceKind(StrEnum):
    DIRECT_FACT = "direct_fact"
    NAVIGATION_LEAD = "navigation_lead"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True)
class EvidenceAssessment:
    disposition: EvidenceDisposition
    evidence_kind: EvidenceKind
    contributing_obligation_ids: tuple[str, ...] = ()
    individually_established_obligation_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        contributions = tuple(dict.fromkeys(value for value in self.contributing_obligation_ids if value))
        established = tuple(dict.fromkeys(value for value in self.individually_established_obligation_ids if value))
        object.__setattr__(self, "contributing_obligation_ids", contributions)
        object.__setattr__(self, "individually_established_obligation_ids", established)
        if not set(established).issubset(contributions):
            raise ValueError("qualification_assessment_invalid: established obligations must also be contributions")
        if self.evidence_kind is not EvidenceKind.DIRECT_FACT and established:
            raise ValueError("qualification_assessment_invalid: only direct facts may establish obligations")
        if self.disposition is EvidenceDisposition.REJECT and (contributions or established):
            raise ValueError("qualification_assessment_invalid: rejected evidence cannot claim obligations")
        valid_pairs = {
            (EvidenceDisposition.RETAIN, EvidenceKind.DIRECT_FACT),
            (EvidenceDisposition.RETAIN, EvidenceKind.NAVIGATION_LEAD),
            (EvidenceDisposition.DEFER, EvidenceKind.NAVIGATION_LEAD),
            (EvidenceDisposition.DEFER, EvidenceKind.INSUFFICIENT),
            (EvidenceDisposition.REJECT, EvidenceKind.INSUFFICIENT),
        }
        if (self.disposition, self.evidence_kind) not in valid_pairs:
            raise ValueError("qualification_assessment_invalid: invalid disposition/evidence-kind combination")

    @property
    def is_retained(self) -> bool:
        return self.disposition is EvidenceDisposition.RETAIN

    @property
    def is_deferred(self) -> bool:
        return self.disposition is EvidenceDisposition.DEFER

    @property
    def is_rejected(self) -> bool:
        return self.disposition is EvidenceDisposition.REJECT

    @property
    def is_direct_fact(self) -> bool:
        return self.evidence_kind is EvidenceKind.DIRECT_FACT

    @property
    def is_navigation(self) -> bool:
        return self.evidence_kind is EvidenceKind.NAVIGATION_LEAD

    @property
    def is_coverage_bearing(self) -> bool:
        return self.is_direct_fact and bool(self.individually_established_obligation_ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "disposition": self.disposition.value,
            "evidence_kind": self.evidence_kind.value,
            "contributing_obligation_ids": list(self.contributing_obligation_ids),
            "individually_established_obligation_ids": list(self.individually_established_obligation_ids),
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> EvidenceAssessment:
        return cls(
            disposition=EvidenceDisposition(str(value.get("disposition") or "")),
            evidence_kind=EvidenceKind(str(value.get("evidence_kind") or "")),
            contributing_obligation_ids=_strings(value.get("contributing_obligation_ids"), limit=12),
            individually_established_obligation_ids=_strings(
                value.get("individually_established_obligation_ids"), limit=12
            ),
        )


@dataclass(frozen=True)
class QualificationRationale:
    reason: str
    visible_support: tuple[str, ...] = ()
    missing_information: tuple[str, ...] = ()
    local_follow_up: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any], *, max_reason_chars: int) -> QualificationRationale:
        reason = str(value.get("reason") or "").strip()
        if not reason:
            raise ValueError("qualification_rationale_invalid: missing reason")
        if len(reason) > max_reason_chars:
            raise ValueError(f"qualification_rationale_invalid: reason exceeds {max_reason_chars} characters")
        return cls(
            reason=reason,
            visible_support=_strings(value.get("visible_support"), limit=6),
            missing_information=_strings(value.get("missing_information"), limit=6),
            local_follow_up=str(value.get("local_follow_up") or "").strip()[:500],
        )


def _strings(value: object, *, limit: int) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(str(item).strip() for item in value[:limit] if str(item).strip())
