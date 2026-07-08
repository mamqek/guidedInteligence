from __future__ import annotations

# Owns coverage and synthesis policy: owner focus, protocol bridging, LLM/deterministic sufficiency assessment, and feedback application. Do not place retrieval execution, candidate expansion, validation primitives, or connected-source loading here.

from dataclasses import replace
from typing import Any, Mapping, Sequence

from services.retrieval.workspace.llm import assess_role_buckets_with_llm
from services.retrieval.workspace.pipeline.constants import MAX_ROLE_BUCKET_CANDIDATES
from services.retrieval.workspace.pipeline.coverage import build_deterministic_coverage_gate as _build_deterministic_coverage_gate
from services.retrieval.workspace.pipeline.evidence_flow import rank_candidates as _rank_candidates
from services.retrieval.workspace.pipeline.execution_flow.candidate_expansion import span_candidate_from_accepted_file as _span_candidate_from_accepted_file_flow
from services.retrieval.workspace.pipeline.execution_flow.candidate_ranking import final_role_candidate_score as _final_role_candidate_score_flow
from services.retrieval.workspace.pipeline.execution_flow.context import WorkspaceRetrievalContext
from services.retrieval.workspace.pipeline.file_level import (
    anchor_support_paths as _anchor_support_paths,
    bucket_missing_roles as _bucket_missing_roles,
    bucket_unresolved_roles as _bucket_unresolved_roles,
    candidate_rank_key as _candidate_rank_key,
    candidate_symbol as _candidate_symbol,
    candidate_satisfies_owner_layer as _candidate_satisfies_owner_layer,
    clean_query_terms as _clean_query_terms,
    completion_redundancy_penalty as _completion_redundancy_penalty,
    diagnostics_like_candidate as _diagnostics_like_candidate,
    owner_artifact_path_match as _owner_artifact_path_match,
    rank_unique_candidates as _rank_unique_candidates,
    role_owner_context_terms as _role_owner_context_terms,
    role_owner_path_match as _role_owner_path_match,
    role_owner_path_tokens as _role_owner_path_tokens,
    role_requires_owner_layer as _role_requires_owner_layer,
    target_matches_reference_owner_vocab as _target_matches_reference_owner_vocab,
)
from services.retrieval.workspace.pipeline.models import (
    RetrievalCandidate,
    RetrievalSynthesisDecision,
    RoleCandidateEvaluation,
    RoleRetrievalBucket,
    RoleValidationResult,
)
from services.retrieval.workspace.pipeline.relationship_flow import protocol_relationship_seed_texts as _protocol_relationship_seed_texts
from services.retrieval.workspace.pipeline.protocol_graph import discover_protocol_relationship_candidates
from services.retrieval.workspace.pipeline.snippet_level import (
    drop_redundant_file_candidates as _drop_redundant_file_candidates,
    is_file_candidate as _is_file_candidate,
    late_snippet_quality as _late_snippet_quality,
    latest_evaluation_for_ref as _latest_evaluation_for_ref,
    merge_retrieved_candidates as _merge_retrieved_candidates,
    planning_snippets as _planning_snippets,
    snippet_reason_for_ref as _snippet_reason_for_ref,
)
from services.retrieval.workspace.responsibility import profile_candidate
from services.retrieval.workspace.step2 import WorkspaceRetrievalPlan
from services.retrieval.workspace.step2.common import ordered_unique
from services.retrieval.workspace.step2.constants import INTENT_DEFECT_LOCALIZATION, ROLE_BEHAVIOR_OUTPUT, ROLE_VALIDATION_CHECKING, SPECIFICITY_NARROW
from services.retrieval.workspace.tools import ToolRequest


def apply_protocol_relationship_bridge(
    ctx: WorkspaceRetrievalContext,
        buckets: Sequence[RoleRetrievalBucket],
        *,
        retrieval_plan: WorkspaceRetrievalPlan | None = None,
    ) -> tuple[RoleRetrievalBucket, ...]:
        result = discover_protocol_relationship_candidates(
            workspace_root=ctx.config.workspace_root,
            buckets=buckets,
            max_candidates=MAX_ROLE_BUCKET_CANDIDATES,
            seed_texts=_protocol_relationship_seed_texts(retrieval_plan),
        )
        if not result.promotions:
            if result.routes or result.message_terms:
                ctx.trace.record(
                    "protocol_relationship_bridge_completed",
                    {"routes": list(result.routes), "message_terms": list(result.message_terms), "promoted_refs": []},
                )
            return tuple(buckets)

        updated = list(buckets)
        promoted_refs: list[str] = []
        promotion_sources: list[str] = []
        for promotion in result.promotions:
            if promotion.target_bucket_index is None:
                continue
            target_bucket = updated[promotion.target_bucket_index]
            updated[promotion.target_bucket_index] = bucket_with_route_bridge_candidates(ctx, target_bucket, promotion.candidates)
            promoted_refs.extend(candidate.source_id for candidate in promotion.candidates)
            promotion_sources.append(promotion.source)
        ctx.trace.record(
            "protocol_relationship_bridge_completed",
            {
                "routes": list(result.routes),
                "message_terms": list(result.message_terms),
                "promotion_sources": promotion_sources,
                "promoted_refs": promoted_refs,
            },
        )
        return tuple(updated)


def bucket_with_route_bridge_candidates(
    ctx: WorkspaceRetrievalContext,
        bucket: RoleRetrievalBucket,
        candidates: Sequence[RetrievalCandidate],
    ) -> RoleRetrievalBucket:
        evaluations = list(bucket.evaluations)
        for candidate in candidates:
            evaluations.append(
                RoleCandidateEvaluation(
                    candidate=candidate,
                    validation=RoleValidationResult(
                        accepted=True,
                        reason="protocol_relationship_candidate_promoted",
                        local_intent_score=5.0,
                        role_path_score=2.0,
                        dependency_support_score=0.0,
                        anchor_proximity_score=2.0,
                        call_flow_score=0.0,
                        total_score=9.0,
                        threshold=3.0,
                        acceptance_source="protocol_relationship_bridge",
                        symbol=None,
                        dependency_paths=(),
                        call_paths=(),
                        anchor_paths=(),
                    ),
                    stage="protocol_relationship_bridge",
                    source_role=bucket.role,
                )
            )
        merged = _merge_retrieved_candidates(bucket.retrieved_candidates, tuple(candidates))
        accepted = tuple(_rank_unique_candidates(tuple(candidates) + tuple(bucket.accepted_candidates)))[:MAX_ROLE_BUCKET_CANDIDATES]
        satisfying = tuple(candidate for candidate in accepted if not _is_file_candidate(candidate))
        return RoleRetrievalBucket(
            role=bucket.role,
            query=bucket.query,
            helper_queries=bucket.helper_queries,
            observations=bucket.observations,
            retrieved_candidates=merged,
            evaluations=tuple(evaluations),
            accepted_candidates=accepted,
            rejected_refs=tuple(ref for ref in bucket.rejected_refs if ref not in {candidate.source_id for candidate in candidates}),
            validation_notes=tuple((*bucket.validation_notes, *("protocol_relationship_bridge_promoted",) * len(candidates))),
            missing_reason="" if satisfying else bucket.missing_reason,
            role_status="strong" if satisfying else bucket.role_status,
            satisfying_refs=tuple(candidate.source_id for candidate in satisfying),
            snippet_assessment=tuple(
                (*bucket.snippet_assessment, *({"ref": candidate.source_id, "role": "core", "reason": "matched frontend route literal"} for candidate in candidates))
            ),
            satisfaction_source="protocol_relationship_bridge",
        )


def owner_focus_roles(
    ctx: WorkspaceRetrievalContext,
        *,
        retrieval_plan: WorkspaceRetrievalPlan,
        buckets: Sequence[RoleRetrievalBucket],
    ) -> tuple[str, ...]:
        bucket_by_role = {bucket.role: bucket for bucket in buckets}
        ranked_roles: list[tuple[float, int, str]] = []
        for index, role in enumerate(retrieval_plan.required_roles):
            bucket = bucket_by_role.get(role)
            if bucket is None:
                ranked_roles.append((-1000.0, -index, role))
                continue
            accepted = list(bucket.accepted_candidates)
            best_validation = max(
                (
                    evaluation.validation.total_score
                    for evaluation in bucket.evaluations
                    if evaluation.candidate.source_id in {candidate.source_id for candidate in accepted}
                ),
                default=0.0,
            )
            owner_path_hits = sum(1 for candidate in accepted if _role_owner_path_match(role, candidate.path or ""))
            only_file_level = bool(accepted) and all(_is_file_candidate(candidate) for candidate in accepted)
            has_snippet = any(not _is_file_candidate(candidate) for candidate in accepted)
            score = best_validation
            if _role_requires_owner_layer(role):
                score += 3.0
            score += owner_path_hits * 1.5
            if only_file_level:
                score += 1.5
            if has_snippet:
                score -= 0.5
            ranked_roles.append((score, -index, role))
        ordered_roles = [role for _score, _index, role in sorted(ranked_roles, reverse=True)]
        focused = [role for role in ordered_roles if role in bucket_by_role][:2]
        if not focused:
            focused = [role for role in retrieval_plan.required_roles[:1]]
        return tuple(ordered_unique(focused))


def focused_owner_grounded(
    ctx: WorkspaceRetrievalContext,
        buckets: Sequence[RoleRetrievalBucket],
        focused_roles: Sequence[str],
    ) -> bool:
        if not focused_roles:
            return False
        bucket_by_role = {bucket.role: bucket for bucket in buckets}
        for role in focused_roles:
            bucket = bucket_by_role.get(role)
            if bucket is None or bucket.role_status != "strong":
                continue
            satisfying_refs = set(bucket.satisfying_refs or ())
            satisfying_candidates = [
                candidate
                for candidate in bucket.accepted_candidates
                if (not satisfying_refs or candidate.source_id in satisfying_refs) and not _is_file_candidate(candidate)
            ]
            if satisfying_candidates:
                return True
        return False


def apply_synthesis_feedback(
    ctx: WorkspaceRetrievalContext,
        *,
        buckets: Sequence[RoleRetrievalBucket],
        decision: RetrievalSynthesisDecision,
        required_roles: Sequence[str],
    ) -> tuple[RoleRetrievalBucket, ...]:
        quality_by_ref = {str(item.get("ref", "")): str(item.get("role", "")).strip().lower() for item in decision.snippet_assessment}
        rejected_refs = set(decision.rejected_anchor_refs)
        follow_up_roles = {str(item.get("role", "")).strip() for item in decision.follow_up_queries if str(item.get("role", "")).strip()}
        missing_roles = {str(role).strip() for role in decision.missing_areas if str(role).strip()}
        updated: list[RoleRetrievalBucket] = []
        for bucket in buckets:
            accepted_file_spans: list[RetrievalCandidate] = []
            existing_non_file_paths = {
                (candidate.path or "").replace("\\", "/")
                for candidate in bucket.accepted_candidates
                if not _is_file_candidate(candidate)
            }
            for candidate in bucket.accepted_candidates:
                if not _is_file_candidate(candidate) or candidate.source_id not in decision.accepted_anchor_refs:
                    continue
                if (candidate.path or "").replace("\\", "/") in existing_non_file_paths:
                    continue
                span_candidate = _span_candidate_from_accepted_file_flow(ctx, 
                    role=bucket.role,
                    file_candidate=candidate,
                    query=bucket.query,
                    search_terms=ordered_unique((bucket.query, *bucket.helper_queries)),
                )
                if span_candidate is not None:
                    accepted_file_spans.append(span_candidate)
            reranked = sorted(
                tuple(bucket.accepted_candidates) + tuple(accepted_file_spans),
                key=lambda candidate: _final_role_candidate_score_flow(
                    role=bucket.role,
                    candidate=candidate,
                    evaluation=_latest_evaluation_for_ref(bucket.evaluations, candidate.source_id),
                    snippet_quality=_late_snippet_quality(
                        ref=candidate.source_id,
                        quality_by_ref=quality_by_ref,
                        rejected_refs=rejected_refs,
                        accepted_refs=set(decision.accepted_anchor_refs),
                    ),
                ),
                reverse=True,
            )
            reranked = _drop_redundant_file_candidates(reranked)
            satisfying_refs: list[str] = []
            noise_refs: list[str] = []
            saw_core = False
            for candidate in reranked:
                quality = _late_snippet_quality(
                    ref=candidate.source_id,
                    quality_by_ref=quality_by_ref,
                    rejected_refs=rejected_refs,
                    accepted_refs=set(decision.accepted_anchor_refs),
                )
                if quality == "noise":
                    noise_refs.append(candidate.source_id)
                    ctx.trace.record(
                        "snippet_excluded_as_noise",
                        {"role": bucket.role, "ref": candidate.source_id},
                    )
                    continue
                if _is_file_candidate(candidate):
                    continue
                satisfying_refs.append(candidate.source_id)
                saw_core = saw_core or quality == "core"
            usable_candidates = tuple(candidate for candidate in reranked if candidate.source_id not in set(noise_refs))
            role_status = "missing"
            if satisfying_refs:
                assessor_accepts_role = (
                    decision.acceptance_satisfied
                    and bucket.role in required_roles
                    and bucket.role not in follow_up_roles
                    and bucket.role not in missing_roles
                )
                role_status = "strong" if (saw_core or assessor_accepts_role) and bucket.role not in follow_up_roles else "weak"
            snippet_assessment = tuple(
                {
                    "ref": candidate.source_id,
                    "role": _late_snippet_quality(
                        ref=candidate.source_id,
                        quality_by_ref=quality_by_ref,
                        rejected_refs=rejected_refs,
                        accepted_refs=set(decision.accepted_anchor_refs),
                    ),
                    "reason": _snippet_reason_for_ref(candidate.source_id, decision.snippet_assessment),
                }
                for candidate in reranked
            )
            missing_reason = bucket.missing_reason
            if role_status != "strong" and bucket.role in required_roles:
                missing_reason = "late_assessment_downgraded"
            if bucket.role_status == "strong" and role_status != "strong":
                ctx.trace.record(
                    "late_role_downgraded",
                    {"role": bucket.role, "from_status": bucket.role_status, "to_status": role_status},
                )
            updated.append(
                RoleRetrievalBucket(
                    role=bucket.role,
                    query=bucket.query,
                    helper_queries=bucket.helper_queries,
                    observations=bucket.observations,
                    retrieved_candidates=bucket.retrieved_candidates,
                    evaluations=bucket.evaluations,
                    accepted_candidates=usable_candidates,
                    rejected_refs=bucket.rejected_refs,
                    validation_notes=bucket.validation_notes,
                    missing_reason=missing_reason,
                    role_status=role_status,
                    satisfying_refs=tuple(satisfying_refs),
                    snippet_assessment=snippet_assessment,
                    satisfaction_source="late_assessment",
                )
            )
        return tuple(updated)


def synthesize_role_buckets(
    ctx: WorkspaceRetrievalContext,
        retrieval_plan: WorkspaceRetrievalPlan,
        buckets: Sequence[RoleRetrievalBucket],
    ) -> RetrievalSynthesisDecision:
        synthesis_buckets = tuple(
            replace(
                bucket,
                accepted_candidates=_drop_redundant_file_candidates(bucket.accepted_candidates),
            )
            for bucket in buckets
        )
        required_buckets = [bucket for bucket in synthesis_buckets if bucket.role in retrieval_plan.required_roles]
        missing_roles = _bucket_missing_roles(required_buckets)
        accepted_candidates = [candidate for bucket in synthesis_buckets for candidate in bucket.accepted_candidates]
        snippets = _planning_snippets(_rank_candidates(accepted_candidates))
        response = assess_role_buckets_with_llm(
            intent=retrieval_plan,
            role_buckets=[bucket.to_dict() for bucket in synthesis_buckets],
            current_snippets=snippets,
            missing_roles=missing_roles,
            llm_config=ctx.config.llm_config,
            log_event=lambda event_type, payload: ctx.trace.record(event_type, {"conversation_id": retrieval_plan.conversation_id, **payload}),
            log_warning=lambda payload: ctx.trace.record("llm_request_warning", {"conversation_id": retrieval_plan.conversation_id, **payload}),
        )
        decision = RetrievalSynthesisDecision(
            acceptance_satisfied=bool(response.get("acceptance_satisfied", False)),
            missing_areas=tuple(str(value) for value in response.get("missing_areas", ()) if str(value).strip()),
            accepted_anchor_refs=tuple(str(value) for value in response.get("accepted_anchor_refs", ()) if str(value).strip()),
            rejected_anchor_refs=tuple(str(value) for value in response.get("rejected_anchor_refs", ()) if str(value).strip()),
            snippet_assessment=tuple(
                {
                    "ref": str(item.get("ref", "")),
                    "role": str(item.get("role", "")),
                    "reason": str(item.get("reason", "")),
                }
                for item in response.get("snippet_assessment", ())
                if isinstance(item, Mapping)
            ),
            stop_reason=str(response.get("stop_reason", "")).strip() or ("validated_role_buckets" if not missing_roles else "missing_required_roles"),
            follow_up_queries=tuple(
                {
                    "role": str(item.get("role", "")),
                    "query": str(item.get("query", "")),
                    "reason": str(item.get("reason", "")),
                }
                for item in response.get("follow_up_queries", ())
                if isinstance(item, Mapping)
            ),
        )
        ctx.trace.record("retrieval_refinement_evaluated", decision.to_dict())
        return decision


def synthesize_or_accept_deterministic(
    ctx: WorkspaceRetrievalContext,
        retrieval_plan: WorkspaceRetrievalPlan,
        buckets: Sequence[RoleRetrievalBucket],
    ) -> RetrievalSynthesisDecision:
        decision = deterministic_synthesis_decision(ctx, retrieval_plan, buckets)
        if decision is not None:
            ctx.trace.record("retrieval_refinement_evaluated", decision.to_dict())
            ctx.trace.record(
                "late_assessor_skipped",
                {
                    "reason": "deterministic_coverage_gate_satisfied",
                    "required_roles": list(retrieval_plan.required_roles),
                    "accepted_anchor_refs": list(decision.accepted_anchor_refs),
                },
            )
            return decision
        return synthesize_role_buckets(ctx, retrieval_plan, buckets)


def deterministic_synthesis_decision(
    ctx: WorkspaceRetrievalContext,
        retrieval_plan: WorkspaceRetrievalPlan,
        buckets: Sequence[RoleRetrievalBucket],
    ) -> RetrievalSynthesisDecision | None:
        required_buckets = tuple(bucket for bucket in buckets if bucket.role in retrieval_plan.required_roles)
        deterministic_gate = _build_deterministic_coverage_gate(retrieval_plan.required_roles, required_buckets)
        if not deterministic_gate.satisfied:
            return None

        accepted_anchor_refs: list[str] = []
        snippet_assessment: list[Mapping[str, str]] = []
        for bucket in buckets:
            satisfying_refs = set(bucket.satisfying_refs or ())
            candidates = tuple(_drop_redundant_file_candidates(bucket.accepted_candidates))
            for candidate in candidates:
                if _is_file_candidate(candidate):
                    continue
                quality = "core" if bucket.role in retrieval_plan.required_roles and (
                    not satisfying_refs or candidate.source_id in satisfying_refs
                ) else "secondary"
                if quality == "core":
                    accepted_anchor_refs.append(candidate.source_id)
                snippet_assessment.append(
                    {
                        "ref": candidate.source_id,
                        "role": quality,
                        "reason": "deterministic coverage gate accepted this local evidence without late assessor arbitration.",
                    }
                )

        if not accepted_anchor_refs:
            return None
        return RetrievalSynthesisDecision(
            acceptance_satisfied=True,
            missing_areas=(),
            accepted_anchor_refs=tuple(ordered_unique(accepted_anchor_refs)),
            rejected_anchor_refs=(),
            snippet_assessment=tuple(snippet_assessment),
            stop_reason="deterministic_coverage_gate_satisfied",
            follow_up_queries=(),
        )
