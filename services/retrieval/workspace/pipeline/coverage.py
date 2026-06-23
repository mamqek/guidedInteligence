from __future__ import annotations

from typing import Sequence

from services.retrieval.workspace.pipeline.file_level import candidate_satisfies_owner_layer, role_requires_owner_layer
from services.retrieval.workspace.pipeline.models import (
    DeterministicCoverageGate,
    RetrievalSynthesisDecision,
    RoleRetrievalBucket,
)
from services.retrieval.workspace.pipeline.snippet_level import drop_redundant_file_candidates
from services.retrieval.workspace.step2 import WorkspaceRetrievalPlan
from services.retrieval.workspace.step2.common import ordered_unique


def build_deterministic_coverage_gate(
    required_roles: Sequence[str],
    buckets: Sequence[RoleRetrievalBucket],
) -> DeterministicCoverageGate:
    status_by_role: dict[str, str] = {}
    missing_roles: list[str] = []
    reasons: list[str] = []
    bucket_by_role = {bucket.role: bucket for bucket in buckets}
    for role in required_roles:
        bucket = bucket_by_role.get(role)
        if bucket is None:
            status_by_role[role] = "missing"
            missing_roles.append(role)
            reasons.append(f"{role}:bucket_missing")
            continue

        satisfying_refs = set(bucket.satisfying_refs)
        satisfying = [
            candidate
            for candidate in bucket.accepted_candidates
            if not satisfying_refs or candidate.source_id in satisfying_refs
        ]
        satisfying = list(drop_redundant_file_candidates(satisfying))
        if bucket.role_status != "strong" or not satisfying:
            status_by_role[role] = "missing"
            missing_roles.append(role)
            reasons.append(f"{role}:no_strong_satisfying_candidate")
            continue

        if role_requires_owner_layer(role) and not any(candidate_satisfies_owner_layer(role, candidate) for candidate in satisfying):
            status_by_role[role] = "missing_owner"
            missing_roles.append(role)
            reasons.append(f"{role}:owner_layer_missing")
            continue

        status_by_role[role] = "strong"

    return DeterministicCoverageGate(
        satisfied=not missing_roles,
        role_status=status_by_role,
        missing_roles=tuple(ordered_unique(missing_roles)),
        reasons=tuple(reasons),
    )


def coverage_status(
    selected,
    decision: RetrievalSynthesisDecision,
    retrieval_plan: WorkspaceRetrievalPlan,
    deterministic_gate: DeterministicCoverageGate,
) -> str:
    if not selected:
        return "missing"
    required_roles = set(retrieval_plan.required_roles)
    if not required_roles:
        return "strong" if decision.acceptance_satisfied and deterministic_gate.satisfied else "partial"
    covered_roles = {item.metadata.get("coverage_area", "") for item in selected}
    if required_roles.issubset(covered_roles) and decision.acceptance_satisfied and deterministic_gate.satisfied:
        return "strong"
    if covered_roles.intersection(required_roles):
        return "partial"
    if selected:
        return "partial"
    return "partial"
