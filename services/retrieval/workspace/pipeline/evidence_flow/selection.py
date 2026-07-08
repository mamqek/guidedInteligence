from __future__ import annotations

# Owns final evidence item assembly and candidate ordering for returned retrieval evidence. Do not place workspace tool execution, role validation, or synthesis policy here.

import re
from pathlib import Path
from typing import Sequence

from core.models import EvidenceItem
from core.source_policy import SourceCategory
from services.retrieval.workspace.connected_context import ConnectedSourceContextResult
from services.retrieval.workspace.pipeline.constants import MAX_EVIDENCE_ITEMS
from services.retrieval.workspace.pipeline.file_level import candidate_rank_key
from services.retrieval.workspace.pipeline.models import RetrievalCandidate, RetrievalSynthesisDecision, RoleRetrievalBucket
from services.retrieval.workspace.pipeline.snippet_level import drop_redundant_file_candidates, read_owner_text_file


def rank_candidates(candidates: Sequence[RetrievalCandidate]) -> tuple[RetrievalCandidate, ...]:
    unique: dict[str, RetrievalCandidate] = {}
    for candidate in candidates:
        existing = unique.get(candidate.candidate_id)
        if existing is None or candidate.score > existing.score:
            unique[candidate.candidate_id] = candidate
    return tuple(sorted(unique.values(), key=candidate_rank_key, reverse=True))


def select_evidence_items(
    required_buckets: Sequence[RoleRetrievalBucket],
    supporting_buckets: Sequence[RoleRetrievalBucket],
    source_policy: Sequence[SourceCategory],
) -> list[EvidenceItem]:
    selected: list[EvidenceItem] = []
    seen_refs: set[str] = set()
    buckets = list(required_buckets) + list(supporting_buckets)
    candidates_by_role = {}
    for bucket in buckets:
        noise_refs = {
            str(item.get("ref", ""))
            for item in bucket.snippet_assessment
            if str(item.get("role", "")).strip().lower() == "noise"
        }
        satisfying = set(bucket.satisfying_refs or tuple(candidate.source_id for candidate in bucket.accepted_candidates))
        candidates_by_role[bucket.role] = list(
            drop_redundant_file_candidates(
                [
                    candidate
                    for candidate in bucket.accepted_candidates
                    if candidate.source_id in satisfying and candidate.source_id not in noise_refs
                ]
            )
        )
    role_order = [bucket.role for bucket in required_buckets if bucket.satisfying_refs]
    role_order.extend(bucket.role for bucket in supporting_buckets if bucket.satisfying_refs and bucket.role not in role_order)

    while len(selected) < MAX_EVIDENCE_ITEMS:
        progressed = False
        for role in role_order:
            candidates = candidates_by_role.get(role, [])
            while candidates:
                candidate = candidates.pop(0)
                if candidate.source_category not in source_policy or candidate.source_id in seen_refs:
                    continue
                seen_refs.add(candidate.source_id)
                selected.append(
                    EvidenceItem(
                        source_category=candidate.source_category,
                        source_id=candidate.source_id,
                        snippet=candidate.text,
                        rank=len(selected) + 1,
                        metadata=dict(candidate.metadata),
                    )
                )
                progressed = True
                break
            if len(selected) >= MAX_EVIDENCE_ITEMS:
                break
        if not progressed:
            break
    return selected


def append_accepted_decision_evidence(
    selected: Sequence[EvidenceItem],
    *,
    synthesis_decision: RetrievalSynthesisDecision,
    buckets: Sequence[RoleRetrievalBucket],
    source_policy: Sequence[SourceCategory],
    workspace_root: str,
) -> list[EvidenceItem]:
    expanded = list(selected)
    seen_refs = {item.source_id for item in expanded}
    noise_refs = {
        str(item.get("ref", ""))
        for item in synthesis_decision.snippet_assessment
        if str(item.get("role", "")).strip().lower() == "noise"
    }
    candidates_by_ref: dict[str, tuple[str, RetrievalCandidate]] = {}
    for bucket in buckets:
        for candidate in bucket.accepted_candidates:
            if any(
                str(item.get("ref", "")) == candidate.source_id
                and str(item.get("role", "")).strip().lower() == "noise"
                for item in bucket.snippet_assessment
            ):
                continue
            candidates_by_ref.setdefault(candidate.source_id, (bucket.role, candidate))

    for ref in synthesis_decision.accepted_anchor_refs:
        if len(expanded) >= MAX_EVIDENCE_ITEMS or ref in seen_refs or ref.endswith(":FILE") or ref in noise_refs:
            continue
        role, candidate = candidates_by_ref.get(ref, ("", None))  # type: ignore[assignment]
        if candidate is not None:
            if candidate.source_category not in source_policy:
                continue
            evidence = EvidenceItem(
                source_category=candidate.source_category,
                source_id=candidate.source_id,
                snippet=candidate.text,
                rank=len(expanded) + 1,
                metadata=dict(candidate.metadata),
            )
        else:
            evidence = evidence_item_from_source_ref(ref, workspace_root=workspace_root, rank=len(expanded) + 1, role=role)
            if evidence is None or evidence.source_category not in source_policy:
                continue
        expanded.append(evidence)
        seen_refs.add(ref)
    return expanded


def append_connected_source_evidence(
    selected: Sequence[EvidenceItem],
    *,
    connected_context: ConnectedSourceContextResult,
    source_policy: Sequence[SourceCategory],
) -> list[EvidenceItem]:
    expanded = list(selected)
    seen_refs = {item.source_id for item in expanded}
    documents_by_id = {document.source_id: document for document in connected_context.documents}
    for source_id in connected_context.selected_evidence_ids:
        if len(expanded) >= MAX_EVIDENCE_ITEMS:
            break
        document = documents_by_id.get(source_id)
        if document is None:
            continue
        if document.source_id in seen_refs or document.source_category not in source_policy:
            continue
        content = document.content.strip()
        if not content:
            continue
        expanded.append(
            EvidenceItem(
                source_category=document.source_category,
                source_id=document.source_id,
                snippet=content[:1600],
                rank=len(expanded) + 1,
                metadata={
                    "title": document.title,
                    "retrieval_path": "connected_source",
                    "source_key": document.source_key,
                    **dict(document.metadata),
                },
            )
        )
        seen_refs.add(document.source_id)
    return expanded


def evidence_item_from_source_ref(ref: str, *, workspace_root: str, rank: int, role: str = "") -> EvidenceItem | None:
    match = re.match(r"^repo-pre:(?P<path>.+):L(?P<start>\d+)-L(?P<end>\d+)$", ref)
    if match is None:
        return None
    path = match.group("path").replace("\\", "/").lstrip("/")
    line_start = max(1, int(match.group("start")))
    line_end = max(line_start, int(match.group("end")))
    root = Path(workspace_root).resolve()
    file_path = (root / path).resolve()
    try:
        file_path.relative_to(root)
    except ValueError:
        return None
    text = read_owner_text_file(file_path)
    if text is None:
        return None
    lines = text.splitlines()
    if not lines:
        return None
    snippet = "\n".join(lines[line_start - 1 : min(line_end, len(lines))])
    return EvidenceItem(
        source_category=SourceCategory.SOURCE_CODE,
        source_id=ref,
        snippet=snippet,
        rank=rank,
        metadata={
            "path": path,
            "coverage_area": role,
            "file_role": "implementation",
            "retrieval_path": "accepted_decision_ref",
            "line_range": f"L{line_start}-L{line_end}",
        },
    )
