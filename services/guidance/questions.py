from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from core.models import EvidenceItem, RetrievalResult


@dataclass(frozen=True)
class QuestionContext:
    id: str
    role: str
    question_type: str
    origin: str
    role_status: str
    evidence_refs: tuple[str, ...]
    focus: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "question_type": self.question_type,
            "origin": self.origin,
            "role_status": self.role_status,
            "evidence_refs": list(self.evidence_refs),
            "focus": self.focus,
        }


@dataclass(frozen=True)
class UnderstandingCheck:
    id: str
    role: str
    question_type: str
    question: str
    expected_answer_points: tuple[str, ...]
    hint: str
    evidence_refs: tuple[str, ...]
    origin: str
    tested_concepts: tuple[str, ...] = ()
    answer_point_map: tuple[Mapping[str, str], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "question_type": self.question_type,
            "question": self.question,
            "expected_answer_points": list(self.expected_answer_points),
            "hint": self.hint,
            "evidence_refs": list(self.evidence_refs),
            "origin": self.origin,
            "tested_concepts": list(self.tested_concepts),
            "answer_point_map": [dict(item) for item in self.answer_point_map],
        }


def build_question_contexts(retrieval_result: RetrievalResult, *, limit: int = 3) -> tuple[QuestionContext, ...]:
    summary = retrieval_result.retrieval_summary
    bucket_contexts = _contexts_from_buckets(summary, retrieval_result.evidence)
    if bucket_contexts:
        return tuple(bucket_contexts[:limit])
    return _contexts_from_evidence(retrieval_result.evidence, limit=limit)


def _contexts_from_buckets(summary: Mapping[str, Any], evidence: Sequence[EvidenceItem]) -> list[QuestionContext]:
    evidence_by_role = _evidence_refs_by_role(evidence)
    required = _bucket_items(summary.get("required_role_buckets"))
    supporting = _bucket_items(summary.get("supporting_role_buckets"))
    contexts: list[QuestionContext] = []

    for bucket in required:
        context = _context_from_bucket(
            bucket,
            question_type="primary" if not contexts else "secondary",
            origin="main retrieved role" if not contexts else "required supporting responsibility",
            evidence_by_role=evidence_by_role,
            index=len(contexts) + 1,
        )
        if context is not None:
            contexts.append(context)
    for bucket in supporting:
        if len(contexts) >= 3:
            break
        context = _context_from_bucket(
            bucket,
            question_type="secondary",
            origin="supporting retrieved role",
            evidence_by_role=evidence_by_role,
            index=len(contexts) + 1,
        )
        if context is not None:
            contexts.append(context)
    return contexts


def _context_from_bucket(
    bucket: Mapping[str, Any],
    *,
    question_type: str,
    origin: str,
    evidence_by_role: Mapping[str, tuple[str, ...]],
    index: int,
) -> QuestionContext | None:
    role = str(bucket.get("role") or "").strip()
    if not role:
        return None
    refs = _string_tuple(bucket.get("satisfying_refs")) or _string_tuple(bucket.get("accepted_refs")) or evidence_by_role.get(role, ())
    if not refs:
        return None
    role_status = str(bucket.get("role_status") or "")
    focus = _answer_outline_for_role(role, question_type=question_type)
    return QuestionContext(
        id=f"q{index}",
        role=role,
        question_type=question_type,
        origin=origin,
        role_status=role_status,
        evidence_refs=refs[:4],
        focus=focus,
    )


def _contexts_from_evidence(evidence: Sequence[EvidenceItem], *, limit: int) -> tuple[QuestionContext, ...]:
    contexts: list[QuestionContext] = []
    seen_roles: set[str] = set()
    for item in evidence:
        role = str(item.metadata.get("coverage_area") or item.source_category.value).strip()
        if not role or role in seen_roles:
            continue
        seen_roles.add(role)
        contexts.append(
            QuestionContext(
                id=f"q{len(contexts) + 1}",
                role=role,
                question_type="primary" if not contexts else "secondary",
                origin="selected evidence coverage area" if not contexts else "additional selected evidence",
                role_status="selected",
                evidence_refs=(item.source_id,),
                focus=_answer_outline_for_role(role, question_type="primary" if not contexts else "secondary"),
            )
        )
        if len(contexts) >= limit:
            break
    return tuple(contexts)


def _bucket_items(value: Any) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _evidence_refs_by_role(evidence: Sequence[EvidenceItem]) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, list[str]] = {}
    for item in evidence:
        role = str(item.metadata.get("coverage_area") or "").strip()
        if not role:
            continue
        grouped.setdefault(role, []).append(item.source_id)
    return {role: tuple(refs) for role, refs in grouped.items()}


def _answer_outline_for_role(role: str, *, question_type: str) -> str:
    role_name = role.strip().replace("_", " ") or "selected code"
    priority = "primary" if question_type == "primary" else "supporting"
    return (
        f"{priority} check for {role_name}: ask a request-specific question about what the cited code does, "
        "what data or state enters or leaves it, and what later code path depends on that behavior. "
        "Do not ask the reader to identify or explain the retrieval role name."
    )
