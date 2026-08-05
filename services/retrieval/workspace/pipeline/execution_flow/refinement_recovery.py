from __future__ import annotations

# Owns refinement and recovery after initial role retrieval: snippet follow-ups, weak-role recovery, and late candidate rescue. Do not place initial candidate discovery, validation primitives, connected-source loading, or synthesis policy definitions here.

from pathlib import Path
from typing import Any, Mapping, Sequence

from services.retrieval.workspace.pipeline.constants import (
    MAX_EVIDENCE_ITEMS,
    MAX_ROLE_BUCKET_CANDIDATES,
    MAX_ROLE_FOLLOWUP_QUERIES,
    MAX_ROLE_PER_QUERY_TOP_PATHS,
)
from services.retrieval.workspace.pipeline.execution_flow.candidate_expansion import candidates_from_search_observation as _candidates_from_search_observation_flow
from services.retrieval.workspace.pipeline.execution_flow.candidate_ranking import final_role_candidate_score as _final_role_candidate_score_flow
from services.retrieval.workspace.pipeline.execution_flow.context import WorkspaceRetrievalContext
from services.retrieval.workspace.pipeline.execution_flow.coverage_synthesis import apply_synthesis_feedback, synthesize_or_accept_deterministic
from services.retrieval.workspace.pipeline.execution_flow.role_validation_flow import (
    accepted_anchor_records as _accepted_anchor_records_flow,
    build_anchor_support as _build_anchor_support_flow,
    open_candidate_context as _open_candidate_context_flow,
    validate_role_candidate as _validate_role_candidate_flow,
)
from services.retrieval.workspace.pipeline.file_level import (
    bucket_missing_roles as _bucket_missing_roles,
    owner_artifact_path_match as _owner_artifact_path_match,
    recovery_anchor_queries as _recovery_anchor_queries,
    role_owner_path_match as _role_owner_path_match,
)
from services.retrieval.workspace.pipeline.models import RetrievalCandidate, RetrievalSynthesisDecision, RoleCandidateEvaluation, RoleRetrievalBucket
from services.retrieval.workspace.pipeline.refinement import refine_role_file_group as _refine_role_file_group
from services.retrieval.workspace.pipeline.snippet_level import (
    drop_redundant_file_candidates as _drop_redundant_file_candidates,
    followup_snippet_quality as _rescue_snippet_quality,
    in_file_refinement_terms as _in_file_refinement_terms,
    late_snippet_quality as _late_snippet_quality,
    latest_evaluation_for_ref as _latest_evaluation_for_ref,
    merge_retrieved_candidates as _merge_retrieved_candidates,
    is_file_candidate as _is_file_candidate,
    role_followup_queries as _role_followup_queries,
    role_snippet_queries as _role_snippet_queries,
    snippet_quality_for_ref as _snippet_quality_for_ref,
    snippet_reason_for_ref as _snippet_reason_for_ref,
)
from services.retrieval.workspace.role_specs import role_keywords, role_path_hints, role_phrase_from_spec
from services.retrieval.workspace.role_validation import AnchorSupport
from services.retrieval.workspace.step2 import WorkspaceRetrievalPlan
from services.retrieval.workspace.step2.common import IDENTIFIER_PATTERN, ordered_unique
from services.retrieval.workspace.tools import OpenFileTool, QdrantHybridSearchTool, ToolRequest


def refine_selected_role_buckets(
    ctx: WorkspaceRetrievalContext,
        *,
        buckets: Sequence[RoleRetrievalBucket],
        rescue_roles: Sequence[str],
        qdrant_tool: QdrantHybridSearchTool,
        open_file_tool: OpenFileTool,
        structural_tools: Mapping[str, Any],
        starting_tool_call_count: int,
    ) -> tuple[tuple[RoleRetrievalBucket, ...], int]:
        if not buckets:
            return (), starting_tool_call_count
        anchors = _accepted_anchor_records_flow(buckets)
        anchor_support, tool_call_count = _build_anchor_support_flow(ctx, anchors=anchors, structural_tools=structural_tools)
        total_tool_calls = starting_tool_call_count + tool_call_count
        refined_buckets: list[RoleRetrievalBucket] = []
        for bucket in buckets:
            if bucket.role not in rescue_roles:
                refined_buckets.append(bucket)
                continue
            updated_bucket, bucket_tool_calls = refine_selected_role_bucket(ctx, 
                bucket=bucket,
                anchor_support=anchor_support,
                qdrant_tool=qdrant_tool,
                open_file_tool=open_file_tool,
                structural_tools=structural_tools,
            )
            refined_buckets.append(updated_bucket)
            total_tool_calls += bucket_tool_calls
        return tuple(refined_buckets), total_tool_calls


def role_retarget_queries(
    role: str,
    *,
    query: str,
    helper_queries: Sequence[str],
    candidate_path: str,
    candidate_text: str,
) -> tuple[str, ...]:
    queries: list[str] = [query.strip(), *[value.strip() for value in helper_queries if value.strip()]]
    role_identifiers = [
        token
        for token in IDENTIFIER_PATTERN.findall(candidate_text)
        if len(token) >= 5 and any(hint in token.lower() for hint in role_path_hints(role))
    ]
    if role_identifiers:
        queries.append(" ".join(ordered_unique(token.lower() for token in role_identifiers)[:3]))
    queries.extend(role_keywords(role)[:2])
    queries.append(f"{role_phrase_from_spec(role, max_terms=2)} {query}".strip())
    path_stem = Path(candidate_path.replace("\\", "/")).stem.strip()
    if path_stem:
        queries.append(path_stem)
    return ordered_unique(value for value in queries if value)


def recover_weak_role_buckets(
    ctx: WorkspaceRetrievalContext,
        *,
        retrieval_plan: WorkspaceRetrievalPlan,
        buckets: Sequence[RoleRetrievalBucket],
        synthesis_decision: RetrievalSynthesisDecision,
        qdrant_tool: QdrantHybridSearchTool,
        open_file_tool: OpenFileTool,
        structural_tools: Mapping[str, Any],
        narrowed_files: Sequence[str],
        starting_tool_call_count: int,
    ) -> tuple[tuple[RoleRetrievalBucket, ...], int, RetrievalSynthesisDecision]:
        weak_roles = {
            bucket.role
            for bucket in buckets
            if bucket.role in retrieval_plan.required_roles and bucket.role_status != "strong"
        }
        if not weak_roles:
            return tuple(buckets), starting_tool_call_count, synthesis_decision

        follow_up_by_role: dict[str, list[str]] = {}
        for item in synthesis_decision.follow_up_queries:
            role = str(item.get("role", "")).strip()
            query = str(item.get("query", "")).strip()
            if role and query:
                follow_up_by_role.setdefault(role, []).append(query)

        recovered_buckets = list(buckets)
        total_tool_calls = starting_tool_call_count
        strong_required_buckets = tuple(
            bucket
            for bucket in buckets
            if bucket.role in retrieval_plan.required_roles and bucket.role_status == "strong" and bucket.satisfying_refs
        )
        anchors = _accepted_anchor_records_flow(strong_required_buckets)
        anchor_support, support_tool_calls = _build_anchor_support_flow(ctx, anchors=anchors, structural_tools=structural_tools) if anchors else (
            AnchorSupport(accepted_anchors={}, dependency_paths_by_anchor={}, call_paths_by_anchor={}),
            0,
        )
        total_tool_calls += support_tool_calls
        changed = False

        for index, bucket in enumerate(recovered_buckets):
            if bucket.role not in weak_roles:
                continue
            updated_bucket, bucket_tool_calls, bucket_changed = recover_weak_role_bucket(ctx, 
                bucket=bucket,
                follow_up_queries=tuple(follow_up_by_role.get(bucket.role, ())),
                qdrant_tool=qdrant_tool,
                open_file_tool=open_file_tool,
                structural_tools=structural_tools,
                anchor_support=anchor_support,
                narrowed_files=narrowed_files,
                all_buckets=tuple(recovered_buckets),
            )
            recovered_buckets[index] = updated_bucket
            total_tool_calls += bucket_tool_calls
            changed = changed or bucket_changed

        if not changed:
            return tuple(recovered_buckets), total_tool_calls, synthesis_decision

        new_decision = synthesize_or_accept_deterministic(ctx, retrieval_plan, tuple(recovered_buckets))
        updated_buckets = apply_synthesis_feedback(ctx, 
            buckets=tuple(recovered_buckets),
            decision=new_decision,
            required_roles=retrieval_plan.required_roles,
        )
        return updated_buckets, total_tool_calls, new_decision


def recover_weak_role_bucket(
    ctx: WorkspaceRetrievalContext,
        *,
        bucket: RoleRetrievalBucket,
        follow_up_queries: Sequence[str],
        qdrant_tool: QdrantHybridSearchTool,
        open_file_tool: OpenFileTool,
        structural_tools: Mapping[str, Any],
        anchor_support: AnchorSupport,
        narrowed_files: Sequence[str],
        all_buckets: Sequence[RoleRetrievalBucket],
        ) -> tuple[RoleRetrievalBucket, int, bool]:
        return run_role_followup_pipeline(ctx, 
            bucket=bucket,
            mode="late_recovery",
            qdrant_tool=qdrant_tool,
            open_file_tool=open_file_tool,
            structural_tools=structural_tools,
            anchor_support=anchor_support,
            search_specs=build_late_recovery_followup_specs(
                ctx,
                bucket=bucket,
                follow_up_queries=follow_up_queries,
                narrowed_files=narrowed_files,
                all_buckets=all_buckets,
            ),
        )


def build_snippet_followup_specs(
    ctx: WorkspaceRetrievalContext,
        bucket: RoleRetrievalBucket,
    ) -> tuple[Mapping[str, Any], ...]:
        specs: list[Mapping[str, Any]] = []
        for candidate in bucket.accepted_candidates:
            if not candidate.path:
                continue
            snippet_queries = _role_followup_queries(
                bucket.role,
                query=bucket.query,
                helper_queries=bucket.helper_queries,
                candidate_path=candidate.path,
                candidate_text=candidate.text,
            )[:MAX_ROLE_FOLLOWUP_QUERIES]
            for query in snippet_queries:
                specs.append(
                    {
                        "query": query,
                        "paths": (candidate.path,),
                        "origin_ref": candidate.source_id,
                    }
                )
        return tuple(specs)


def build_late_recovery_followup_specs(
    ctx: WorkspaceRetrievalContext,
        *,
        bucket: RoleRetrievalBucket,
        follow_up_queries: Sequence[str],
        narrowed_files: Sequence[str],
        all_buckets: Sequence[RoleRetrievalBucket],
    ) -> tuple[Mapping[str, Any], ...]:
        anchor_queries = tuple(_recovery_anchor_queries(bucket.role, all_buckets))
        fallback_queries = tuple(_role_snippet_queries(bucket.role, query=bucket.query, helper_queries=bucket.helper_queries))
        owner_search_terms = ordered_unique((bucket.query, *bucket.helper_queries))
        owner_paths = tuple(
            ordered_unique(
                candidate.path
                for candidate in bucket.accepted_candidates
                if candidate.path
                and (
                    _role_owner_path_match(bucket.role, candidate.path)
                    or _is_file_candidate(candidate)
                    or _owner_artifact_path_match(candidate.path, owner_search_terms)
                )
            )
        )
        specs: list[Mapping[str, Any]] = []
        seen_queries: set[tuple[str, tuple[str, ...]]] = set()

        primary_queries = ordered_unique(list(follow_up_queries) + list(anchor_queries) + list(fallback_queries))
        if owner_paths:
            for query in primary_queries:
                normalized = query.strip()
                if not normalized:
                    continue
                key = (normalized, owner_paths)
                if key in seen_queries:
                    continue
                seen_queries.add(key)
                specs.append(
                    {
                        "query": normalized,
                        "paths": owner_paths,
                        "origin_ref": "",
                    }
                )
                if len(specs) >= MAX_ROLE_FOLLOWUP_QUERIES:
                    return tuple(specs)

        narrowed_paths = tuple(narrowed_files)
        for query in fallback_queries:
            normalized = query.strip()
            if not normalized:
                continue
            key = (normalized, narrowed_paths)
            if key in seen_queries:
                continue
            seen_queries.add(key)
            specs.append(
                {
                    "query": normalized,
                    "paths": narrowed_paths,
                    "origin_ref": "",
                }
            )
            if len(specs) >= MAX_ROLE_FOLLOWUP_QUERIES:
                break

        for query in primary_queries:
            normalized = query.strip()
            if not normalized:
                continue
            key = (normalized, ())
            if key in seen_queries:
                continue
            seen_queries.add(key)
            specs.append(
                {
                    "query": normalized,
                    "paths": (),
                    "origin_ref": "",
                }
            )
            if len(specs) >= MAX_ROLE_FOLLOWUP_QUERIES:
                break

        return tuple(specs)


def run_role_followup_pipeline(
    ctx: WorkspaceRetrievalContext,
        *,
        bucket: RoleRetrievalBucket,
        mode: str,
        qdrant_tool: QdrantHybridSearchTool,
        open_file_tool: OpenFileTool,
        structural_tools: Mapping[str, Any],
        anchor_support: AnchorSupport,
        search_specs: Sequence[Mapping[str, Any]],
    ) -> tuple[RoleRetrievalBucket, int, bool]:
        if not search_specs:
            return bucket, 0, False
        tool_calls = 0
        existing_refs = {candidate.source_id for candidate in bucket.accepted_candidates}
        initial_evaluations = list(bucket.evaluations)
        followup_candidates: list[tuple[RetrievalCandidate, RoleValidationResult]] = []
        grouped_candidates: dict[str, list[RetrievalCandidate]] = {}
        grouped_queries: dict[str, list[str]] = {}
        ctx.trace.record(
            "role_followup_started",
            {"role": bucket.role, "mode": mode, "spec_count": len(search_specs)},
        )
        for spec in search_specs:
            query = str(spec.get("query", "")).strip()
            paths = tuple(str(item) for item in spec.get("paths", ()) if str(item).strip())
            origin_ref = str(spec.get("origin_ref", "")).strip()
            if not query:
                continue
            request = ToolRequest(
                tool_name="qdrant_hybrid_search",
                arguments={
                    "query": query,
                    "_coverage_area": bucket.role,
                    "limit": MAX_ROLE_PER_QUERY_TOP_PATHS * 2,
                    "paths": list(paths),
                    "source_category": "source_code",
                    "file_role": "implementation",
                },
                reason=f"Refine stronger {bucket.role} evidence via {mode}.",
            )
            observation = qdrant_tool.run(request)
            ctx.trace.record_tool(request, observation, round_index=0)
            tool_calls += 1
            ctx.trace.record(
                "role_followup_candidates_retrieved",
                {"role": bucket.role, "mode": mode, "query": query, "origin_ref": origin_ref, "refs": list(observation.source_refs)},
            )
            for candidate in _candidates_from_search_observation_flow(observation, coverage_area=bucket.role):
                enriched_candidate, open_observation = _open_candidate_context_flow(ctx, candidate, open_file_tool)
                if open_observation is not None:
                    tool_calls += 1
                followup_queries = (query,) + _role_followup_queries(
                    bucket.role,
                    query=bucket.query,
                    helper_queries=bucket.helper_queries,
                    candidate_path=enriched_candidate.path or "",
                    candidate_text=enriched_candidate.text,
                )
                if not enriched_candidate.path:
                    validation = _validate_role_candidate_flow(ctx, 
                        role=bucket.role,
                        query=bucket.query,
                        helper_queries=bucket.helper_queries,
                        candidate=enriched_candidate,
                        anchor_support=anchor_support,
                        structural_tools=structural_tools,
                        allow_structural_queries=False,
                    )
                    initial_evaluations.append(
                        RoleCandidateEvaluation(
                            candidate=enriched_candidate,
                            validation=validation,
                            stage=f"role_followup_{mode}_initial",
                            source_role=bucket.role,
                        )
                    )
                    ctx.trace.record(
                        "role_followup_candidate_scored",
                        {
                            "role": bucket.role,
                            "mode": mode,
                            "query": query,
                            "origin_ref": origin_ref,
                            "ref": enriched_candidate.source_id,
                            "validation": validation.to_dict(),
                        },
                    )
                    if validation.accepted and enriched_candidate.source_id not in existing_refs:
                        followup_candidates.append((enriched_candidate, validation))
                        existing_refs.add(enriched_candidate.source_id)
                    continue
                normalized_path = enriched_candidate.path.replace("\\", "/")
                grouped_candidates.setdefault(normalized_path, []).append(enriched_candidate)
                grouped_queries.setdefault(normalized_path, []).extend(followup_queries)
        for path, candidates in grouped_candidates.items():
            refined_candidates, refinement_observations = _refine_role_file_group(
                role=bucket.role,
                query=bucket.query,
                helper_queries=bucket.helper_queries,
                path=path,
                raw_candidates=candidates,
                snippet_queries=tuple(grouped_queries.get(path, ())),
                qdrant_tool=qdrant_tool,
                open_file_tool=open_file_tool,
                workspace_root=ctx.config.workspace_root,
                llm_config=ctx.config.llm_config,
                record=ctx.trace.record,
                record_tool=lambda request, observation: ctx.trace.record_tool(request, observation, round_index=0),
                open_candidate_context=lambda candidate, tool: _open_candidate_context_flow(ctx, candidate, tool),
            )
            tool_calls += len(refinement_observations)
            for refined_candidate in refined_candidates:
                validation = _validate_role_candidate_flow(ctx, 
                    role=bucket.role,
                    query=bucket.query,
                    helper_queries=bucket.helper_queries,
                    candidate=refined_candidate,
                    anchor_support=anchor_support,
                    structural_tools=structural_tools,
                    allow_structural_queries=False,
                )
                initial_evaluations.append(
                    RoleCandidateEvaluation(
                        candidate=refined_candidate,
                        validation=validation,
                        stage=f"role_followup_{mode}_initial",
                        source_role=bucket.role,
                    )
                )
                ctx.trace.record(
                    "role_followup_candidate_scored",
                    {
                        "role": bucket.role,
                        "mode": mode,
                        "query": path,
                        "origin_ref": "",
                        "ref": refined_candidate.source_id,
                        "validation": validation.to_dict(),
                    },
                )
                if validation.accepted and refined_candidate.source_id not in existing_refs:
                    followup_candidates.append((refined_candidate, validation))
                    existing_refs.add(refined_candidate.source_id)
        if not followup_candidates:
            ctx.trace.record("role_followup_completed", {"role": bucket.role, "mode": mode, "changed": False, "selected_refs": list(bucket.satisfying_refs)})
            return bucket, tool_calls, False

        shortlist = sorted(
            followup_candidates,
            key=lambda item: _final_role_candidate_score_flow(
                role=bucket.role,
                candidate=item[0],
                evaluation=RoleCandidateEvaluation(candidate=item[0], validation=item[1], stage=f"role_followup_{mode}_initial", source_role=bucket.role),
                snippet_quality=_rescue_snippet_quality(
                    role=bucket.role,
                    candidate=item[0],
                    rescued_refs={candidate.source_id for candidate, _ in followup_candidates},
                    existing_assessment=bucket.snippet_assessment,
                ),
            ),
            reverse=True,
        )[: MAX_ROLE_BUCKET_CANDIDATES * 2]

        verified_evaluations: list[RoleCandidateEvaluation] = []
        verified_candidates: list[RetrievalCandidate] = []
        for candidate, _initial_validation in shortlist:
            verified_validation = _validate_role_candidate_flow(ctx, 
                role=bucket.role,
                query=bucket.query,
                helper_queries=bucket.helper_queries,
                candidate=candidate,
                anchor_support=anchor_support,
                structural_tools=structural_tools,
                allow_structural_queries=True,
            )
            verified_evaluations.append(
                RoleCandidateEvaluation(
                    candidate=candidate,
                    validation=verified_validation,
                    stage=f"role_followup_{mode}",
                    source_role=bucket.role,
                )
            )
            ctx.trace.record(
                "role_followup_candidate_verified",
                {"role": bucket.role, "mode": mode, "ref": candidate.source_id, "validation": verified_validation.to_dict()},
            )
            if verified_validation.accepted:
                verified_candidates.append(candidate)
        if not verified_candidates:
            ctx.trace.record("role_followup_completed", {"role": bucket.role, "mode": mode, "changed": False, "selected_refs": list(bucket.satisfying_refs)})
            return bucket, tool_calls, False

        promoted_ref_set = {candidate.source_id for candidate in verified_candidates}
        base_candidates = list(bucket.accepted_candidates)
        if mode == "snippet_refinement":
            verified_paths = {candidate.path for candidate in verified_candidates if candidate.path}
            base_candidates = [
                candidate
                for candidate in base_candidates
                if not (candidate.metadata.get("file_candidate") == "true" and candidate.path in verified_paths)
            ]
        reranked = _drop_redundant_file_candidates(
            sorted(
                base_candidates + verified_candidates,
                key=lambda candidate: _final_role_candidate_score_flow(
                    role=bucket.role,
                    candidate=candidate,
                    evaluation=_latest_evaluation_for_ref(tuple(initial_evaluations + verified_evaluations), candidate.source_id),
                    snippet_quality=_rescue_snippet_quality(
                        role=bucket.role,
                        candidate=candidate,
                        rescued_refs=promoted_ref_set,
                        existing_assessment=bucket.snippet_assessment,
                    ),
                ),
                reverse=True,
            )
        )[:MAX_ROLE_BUCKET_CANDIDATES]
        satisfying_candidates = tuple(candidate for candidate in reranked if not _is_file_candidate(candidate))
        updated_bucket = RoleRetrievalBucket(
            role=bucket.role,
            query=bucket.query,
            helper_queries=bucket.helper_queries,
            observations=bucket.observations,
            retrieved_candidates=_merge_retrieved_candidates(bucket.retrieved_candidates, tuple(verified_candidates)),
            evaluations=tuple(initial_evaluations + verified_evaluations),
            accepted_candidates=tuple(reranked),
            rejected_refs=bucket.rejected_refs,
            validation_notes=bucket.validation_notes,
            missing_reason="" if satisfying_candidates else "owner_only_file_candidates",
            role_status="weak" if satisfying_candidates else "missing",
            satisfying_refs=tuple(candidate.source_id for candidate in satisfying_candidates),
            snippet_assessment=bucket.snippet_assessment,
            satisfaction_source=bucket.satisfaction_source if mode == "snippet_refinement" else "recovery_pending",
        )
        changed = tuple(candidate.source_id for candidate in reranked) != tuple(candidate.source_id for candidate in bucket.accepted_candidates)
        ctx.trace.record(
            "role_followup_completed",
            {"role": bucket.role, "mode": mode, "changed": changed, "selected_refs": [candidate.source_id for candidate in reranked]},
        )
        return updated_bucket, tool_calls, changed


def refine_selected_role_bucket(
    ctx: WorkspaceRetrievalContext,
        *,
        bucket: RoleRetrievalBucket,
        anchor_support: AnchorSupport,
        qdrant_tool: QdrantHybridSearchTool,
        open_file_tool: OpenFileTool,
        structural_tools: Mapping[str, Any],
    ) -> tuple[RoleRetrievalBucket, int]:
        if not bucket.accepted_candidates:
            return bucket, 0
        updated_bucket, tool_calls, _changed = run_role_followup_pipeline(ctx, 
            bucket=bucket,
            mode="snippet_refinement",
            qdrant_tool=qdrant_tool,
            open_file_tool=open_file_tool,
            structural_tools=structural_tools,
            anchor_support=anchor_support,
            search_specs=build_snippet_followup_specs(ctx, bucket),
        )
        return updated_bucket, tool_calls
