from __future__ import annotations

# Owns candidate scoring and ordering after expansion. Do not place candidate discovery, validation graph queries, retrieval orchestration, or synthesis policy here.

import re
from typing import Any, Mapping, Sequence

from services.retrieval.workspace.pipeline.constants import MAX_ROLE_BUCKET_CANDIDATES, MAX_ROLE_PER_QUERY_TOP_PATHS
from services.retrieval.workspace.pipeline.evidence_flow import rank_candidates as _rank_candidates
from services.retrieval.workspace.pipeline.execution_flow.context import WorkspaceRetrievalContext
from services.retrieval.workspace.pipeline.file_level import (
    candidate_rank_key as _candidate_rank_key,
    role_owner_path_match as _role_owner_path_match,
    role_requires_owner_layer as _role_requires_owner_layer,
)
from services.retrieval.workspace.pipeline.models import (
    PreparedRoleBucket,
    RetrievalCandidate,
    RoleCandidateEvaluation,
    RoleRetrievalBucket,
    RoleValidationResult,
)
from services.retrieval.workspace.pipeline.snippet_level import is_file_candidate as _is_file_candidate
from services.retrieval.workspace.pipeline.execution_flow.role_validation_flow import (
    responsibility_validation_result,
    validate_role_candidate,
)
from services.retrieval.workspace.responsibility import ResponsibilityScore, score_responsibility
from services.retrieval.workspace.role_specs import path_matches_role, path_matches_role_support, text_matches_role_keywords
from services.retrieval.workspace.role_validation import AnchorSupport
from services.retrieval.workspace.step2.common import ordered_unique


def responsibility_rerank_bucket(
    ctx: WorkspaceRetrievalContext,
        *,
        prepared_bucket: PreparedRoleBucket,
        candidates: Sequence[RetrievalCandidate],
        graph_paths: Sequence[str],
        anchor_support: AnchorSupport,
        structural_tools: Mapping[str, Any],
    ) -> RoleRetrievalBucket:
        scored: list[tuple[RetrievalCandidate, RoleValidationResult, ResponsibilityScore]] = []
        for candidate in candidates:
            validation = validate_role_candidate(
                ctx,
                role=prepared_bucket.role,
                query=prepared_bucket.query,
                helper_queries=prepared_bucket.helper_queries,
                candidate=candidate,
                anchor_support=anchor_support,
                structural_tools=structural_tools,
                allow_structural_queries=True,
            )
            score = score_responsibility(
                prepared_bucket.role,
                path=candidate.path or "",
                text=candidate.text,
                retrieval_score=candidate.score,
                validation_score=validation.total_score,
                graph_paths=graph_paths,
                file_role=candidate.metadata.get("file_role", ""),
            )
            scored.append((candidate, validation, score))
            ctx.trace.record(
                "responsibility_candidate_scored",
                {
                    "role": prepared_bucket.role,
                    "ref": candidate.source_id,
                    "path": candidate.path or "",
                    "validation": validation.to_dict(),
                    "responsibility": score.to_dict(),
                },
            )

        owner_available = any(not score.profile.support_only and not score.profile.noise for _candidate, _validation, score in scored)
        owner_path_available = any(
            validation.accepted and _role_owner_path_match(prepared_bucket.role, candidate.path or "")
            for candidate, validation, score in scored
            if not score.profile.noise and not score.profile.support_only
        )
        reranked = sorted(scored, key=lambda item: (item[2].total_score, _candidate_rank_key(item[0])[0]), reverse=True)
        accepted_candidates: list[RetrievalCandidate] = []
        evaluations: list[RoleCandidateEvaluation] = []
        rejected_refs: list[str] = []
        validation_notes: list[str] = []
        for candidate, validation, score in reranked:
            hard_support_only = "diagnostics_catalog" in score.profile.reasons
            blocked_by_owner_path = (
                owner_path_available
                and _role_requires_owner_layer(prepared_bucket.role)
                and not _role_owner_path_match(prepared_bucket.role, candidate.path or "")
            )
            accepted = (
                not score.profile.noise
                and not hard_support_only
                and not blocked_by_owner_path
                and (not score.profile.support_only or not owner_available)
            )
            reason = "responsibility_owner_selected" if accepted else "responsibility_support_only_downvoted"
            responsibility_validation = responsibility_validation_result(
                candidate=candidate,
                accepted=accepted,
                reason=reason,
                validation=validation,
                score=score,
                graph_paths=graph_paths,
            )
            evaluations.append(
                RoleCandidateEvaluation(
                    candidate=candidate,
                    validation=responsibility_validation,
                    stage="responsibility_rerank",
                    source_role=prepared_bucket.role,
                )
            )
            validation_notes.append(reason)
            if accepted and len(accepted_candidates) < MAX_ROLE_BUCKET_CANDIDATES:
                accepted_candidates.append(candidate)
                ctx.trace.record(
                    "responsibility_candidate_accepted",
                    {"role": prepared_bucket.role, "ref": candidate.source_id, "score": score.to_dict()},
                )
            else:
                rejected_refs.append(candidate.source_id)
                ctx.trace.record(
                    "responsibility_candidate_rejected",
                    {"role": prepared_bucket.role, "ref": candidate.source_id, "score": score.to_dict(), "reason": reason},
                )

        if accepted_candidates:
            role_status = "weak"
            missing_reason = "snippet_selection_pending"
        else:
            role_status = "missing"
            missing_reason = "no_responsible_owner_candidates"
        return RoleRetrievalBucket(
            role=prepared_bucket.role,
            query=prepared_bucket.query,
            helper_queries=prepared_bucket.helper_queries,
            observations=prepared_bucket.observations,
            retrieved_candidates=tuple(candidates),
            evaluations=tuple(evaluations),
            accepted_candidates=tuple(accepted_candidates),
            rejected_refs=tuple(ordered_unique(rejected_refs)),
            validation_notes=tuple(validation_notes),
            missing_reason=missing_reason,
            role_status=role_status,
            satisfying_refs=(),
            snippet_assessment=(),
            satisfaction_source="responsibility_rerank",
        )


def final_role_candidate_score(
        *,
        role: str,
        candidate: RetrievalCandidate,
        evaluation: RoleCandidateEvaluation | None,
        snippet_quality: str,
    ) -> float:
        text = candidate.text.lower()
        path = (candidate.path or "").lower()
        score = float(evaluation.validation.total_score if evaluation is not None else candidate.score)
        quality_bonus = {"core": 4.0, "secondary": 1.0, "noise": -8.0}.get(snippet_quality, 0.0)
        score += quality_bonus
        if evaluation is not None and evaluation.stage == "role_completion":
            score -= 1.25
        if evaluation is not None and evaluation.stage.startswith("role_followup_"):
            score += 1.5
        if _is_file_candidate(candidate):
            score -= 4.0
        if text_matches_role_keywords(role, candidate.text, minimum_hits=1):
            score += 2.0
        if path_matches_role(role, candidate.path or ""):
            score += 1.5
        if path_matches_role_support(role, candidate.path or "") and not text_matches_role_keywords(role, candidate.text, minimum_hits=1):
            score -= 1.5
        if role == "representation" and re.search(r"\b(?:class|interface|enum|type)\s+[A-Za-z_][A-Za-z0-9_]*", candidate.text, re.IGNORECASE):
            score += 1.5
        if role in {"input_parsing", "validation_checking", "behavior_output"} and re.search(r"\bfunction\s+[A-Za-z_][A-Za-z0-9_]*", candidate.text, re.IGNORECASE):
            score += 1.0
        return score


def select_helper_query_seed_candidates(candidates: Sequence[RetrievalCandidate]) -> tuple[RetrievalCandidate, ...]:
        ranked = _rank_candidates(candidates)
        selected: list[RetrievalCandidate] = []
        seen_paths: set[str] = set()
        for candidate in ranked:
            path = candidate.path or candidate.source_id
            if path in seen_paths:
                continue
            seen_paths.add(path)
            selected.append(candidate)
            if len(selected) >= MAX_ROLE_PER_QUERY_TOP_PATHS:
                break
        return tuple(selected)
