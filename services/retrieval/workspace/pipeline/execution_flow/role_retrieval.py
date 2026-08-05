from __future__ import annotations

# Owns role-bucket retrieval and preparation: executing planned role subqueries, preparing candidate buckets, and completing bucket coverage. Do not place candidate expansion internals, validation scoring internals, synthesis policy, or connected-source orchestration here.

import time
from typing import Any, Mapping, Sequence

from services.retrieval.workspace.pipeline.constants import (
    MAX_EVIDENCE_ITEMS,
    MAX_FILE_ROLE_ALTERNATES,
    MAX_FILE_ROLE_RESOLUTION_ROUNDS,
    MAX_ROLE_BUCKET_CANDIDATES,
    MAX_ROLE_CANDIDATE_EVALUATIONS,
    MAX_ROLE_COMPLETION_CANDIDATES,
    MAX_ROLE_INITIAL_PATHS,
    MAX_ROLE_QUERIES,
)
from services.retrieval.workspace.pipeline.evidence_flow import rank_candidates as _rank_candidates
from services.retrieval.workspace.pipeline.execution_flow.candidate_expansion import (
    candidates_from_search_observation as _candidates_from_search_observation_flow,
    direct_owner_candidate_from_path as _direct_owner_candidate_from_path_flow,
    expand_responsibility_candidates as _expand_responsibility_candidates_flow,
    preliminary_responsibility_anchors as _preliminary_responsibility_anchors_flow,
)
from services.retrieval.workspace.pipeline.execution_flow.candidate_ranking import (
    responsibility_rerank_bucket as _responsibility_rerank_bucket_flow,
    select_helper_query_seed_candidates as _select_helper_query_seed_candidates_flow,
)
from services.retrieval.workspace.pipeline.execution_flow.context import WorkspaceRetrievalContext
from services.retrieval.workspace.pipeline.execution_flow.role_validation_flow import (
    accepted_anchor_records as _accepted_anchor_records_flow,
    build_anchor_support as _build_anchor_support_flow,
    role_completion_validation_result as _role_completion_validation_result_flow,
    validate_role_candidate as _validate_role_candidate_flow,
)
from services.retrieval.workspace.pipeline.file_level import (
    collapse_candidates_to_file_candidates as _collapse_candidates_to_file_candidates,
    owner_artifact_path_match as _owner_artifact_path_match,
    rank_unique_candidates as _rank_unique_candidates,
    role_owner_path_match as _role_owner_path_match,
    role_query_package as _role_query_package,
    role_scoped_narrowed_files as _role_scoped_narrowed_files,
    select_diverse_completion_entries as _select_diverse_completion_entries,
)
from services.retrieval.workspace.pipeline.models import (
    PreparedRoleBucket,
    RetrievalCandidate,
    RoleCandidateEvaluation,
    RoleRetrievalBucket,
    RoleValidationResult,
)
from services.retrieval.workspace.pipeline.snippet_level import (
    in_file_search_terms as _in_file_search_terms,
    merge_retrieved_candidates as _merge_retrieved_candidates,
)
from services.retrieval.workspace.responsibility import FileResponsibilityProfile, ResponsibilityExpansionIntent, infer_expansion_intents, profile_candidate
from services.retrieval.workspace.role_completion import RoleCompletionContext, score_role_completion
from services.retrieval.workspace.role_validation import AnchorRecord, AnchorSupport
from services.retrieval.workspace.step2 import RoleDirectedSubquery, WorkspaceRetrievalPlan
from services.retrieval.workspace.step2.common import ordered_unique
from services.retrieval.workspace.tools import OpenFileTool, QdrantHybridSearchTool, ToolObservation, ToolRequest


def retrieve_responsibility_role_buckets(
    ctx: WorkspaceRetrievalContext,
        *,
        retrieval_plan: WorkspaceRetrievalPlan,
        subquery_roles: Sequence[str],
        qdrant_tool: QdrantHybridSearchTool,
        open_file_tool: OpenFileTool,
        structural_tools: Mapping[str, Any],
        narrowed_files: Sequence[str],
        starting_tool_call_count: int,
        phase: str,
    ) -> tuple[tuple[RoleRetrievalBucket, ...], int, tuple[ResponsibilityExpansionIntent, ...]]:
        subqueries = _role_subqueries_for_phase(retrieval_plan, subquery_roles=subquery_roles, phase=phase)
        _record_missing_role_subqueries(ctx, requested_roles=subquery_roles, subqueries=subqueries, phase=phase)
        prepared_buckets: list[PreparedRoleBucket] = []
        tool_call_count = starting_tool_call_count
        for subquery in subqueries:
            bucket, consumed_calls = prepare_role_bucket(ctx, 
                retrieval_plan=retrieval_plan,
                role=subquery.role,
                query=subquery.query,
                qdrant_tool=qdrant_tool,
                open_file_tool=open_file_tool,
                narrowed_files=narrowed_files,
                phase=phase,
            )
            prepared_buckets.append(bucket)
            tool_call_count += consumed_calls

        profile_entries: dict[str, list[tuple[str, str, FileResponsibilityProfile]]] = {}
        for prepared_bucket in prepared_buckets:
            for candidate in prepared_bucket.candidates:
                profile = profile_candidate(
                    prepared_bucket.role,
                    path=candidate.path or "",
                    text=candidate.text,
                    file_role=candidate.metadata.get("file_role", ""),
                )
                profile_entries.setdefault(prepared_bucket.role, []).append((candidate.path or "", candidate.text, profile))
                ctx.trace.record(
                    "responsibility_candidate_profiled",
                    {"role": prepared_bucket.role, "ref": candidate.source_id, "profile": profile.to_dict()},
                )

        expansion_intents = infer_expansion_intents(
            required_roles=subquery_roles,
            prompt_summary=retrieval_plan.prompt_summary,
            candidates_by_role=profile_entries,
        )
        for intent in expansion_intents:
            ctx.trace.record("responsibility_expansion_inferred", intent.to_dict())

        expanded_by_role: dict[str, tuple[RetrievalCandidate, ...]] = {}
        graph_paths_by_role: dict[str, tuple[str, ...]] = {}
        for round_index in range(min(MAX_FILE_ROLE_RESOLUTION_ROUNDS, 1)):
            ctx.trace.record(
                "file_role_resolution_round_started",
                {"phase": phase, "round": round_index + 1, "max_rounds": MAX_FILE_ROLE_RESOLUTION_ROUNDS},
            )
            expanded_by_role, graph_paths_by_role, expansion_calls = _expand_responsibility_candidates_flow(ctx, 
                prepared_buckets=tuple(prepared_buckets),
                expansion_intents=expansion_intents,
                qdrant_tool=qdrant_tool,
                open_file_tool=open_file_tool,
                structural_tools=structural_tools,
            )
            tool_call_count += expansion_calls
            ctx.trace.record(
                "file_role_resolution_round_completed",
                {
                    "phase": phase,
                    "round": round_index + 1,
                    "expanded_roles": sorted(expanded_by_role.keys()),
                    "graph_roles": sorted(graph_paths_by_role.keys()),
                },
            )
        anchor_support, support_calls = _build_anchor_support_flow(ctx, 
            anchors=_preliminary_responsibility_anchors_flow(prepared_buckets),
            structural_tools=structural_tools,
        )
        tool_call_count += support_calls

        buckets: list[RoleRetrievalBucket] = []
        for prepared_bucket in prepared_buckets:
            merged_candidates = _merge_retrieved_candidates(
                prepared_bucket.candidates,
                expanded_by_role.get(prepared_bucket.role, ()),
            )
            buckets.append(
                _responsibility_rerank_bucket_flow(ctx, 
                    prepared_bucket=prepared_bucket,
                    candidates=merged_candidates,
                    graph_paths=graph_paths_by_role.get(prepared_bucket.role, ()),
                    anchor_support=anchor_support,
                    structural_tools=structural_tools,
                )
            )
        return tuple(buckets), tool_call_count, expansion_intents


def retrieve_role_buckets(
    ctx: WorkspaceRetrievalContext,
        *,
        retrieval_plan: WorkspaceRetrievalPlan,
        subquery_roles: Sequence[str],
        qdrant_tool: QdrantHybridSearchTool,
        open_file_tool: OpenFileTool,
        structural_tools: Mapping[str, Any],
        narrowed_files: Sequence[str],
        starting_tool_call_count: int,
        phase: str,
    ) -> tuple[tuple[RoleRetrievalBucket, ...], int]:
        subqueries = _role_subqueries_for_phase(retrieval_plan, subquery_roles=subquery_roles, phase=phase)
        _record_missing_role_subqueries(ctx, requested_roles=subquery_roles, subqueries=subqueries, phase=phase)
        prepared_buckets: list[PreparedRoleBucket] = []
        tool_call_count = starting_tool_call_count
        for subquery in subqueries:
            bucket, consumed_calls = prepare_role_bucket(ctx, 
                retrieval_plan=retrieval_plan,
                role=subquery.role,
                query=subquery.query,
                qdrant_tool=qdrant_tool,
                open_file_tool=open_file_tool,
                narrowed_files=narrowed_files,
                phase=phase,
            )
            prepared_buckets.append(bucket)
            tool_call_count += consumed_calls
        initial_support = AnchorSupport(accepted_anchors={}, dependency_paths_by_anchor={}, call_paths_by_anchor={})
        seeded_buckets = tuple(
            evaluate_prepared_role_bucket(ctx, 
                prepared_bucket,
                anchor_support=initial_support,
                max_accept_count=1,
                structural_tools=structural_tools,
            )
            for prepared_bucket in prepared_buckets
        )
        anchor_records = _accepted_anchor_records_flow(seeded_buckets)
        anchor_support, support_tool_calls = _build_anchor_support_flow(ctx, anchors=anchor_records, structural_tools=structural_tools)
        tool_call_count += support_tool_calls
        final_buckets = tuple(
            evaluate_prepared_role_bucket(ctx, 
                prepared_bucket,
                anchor_support=anchor_support,
                max_accept_count=MAX_ROLE_BUCKET_CANDIDATES,
                structural_tools=structural_tools,
            )
            for prepared_bucket in prepared_buckets
        )
        return final_buckets, tool_call_count


def _role_subqueries_for_phase(
    retrieval_plan: WorkspaceRetrievalPlan,
    *,
    subquery_roles: Sequence[str],
    phase: str,
) -> tuple[RoleDirectedSubquery, ...]:
        requested_roles = set(subquery_roles)
        if phase == "supporting":
            candidates = (*retrieval_plan.support_subqueries, *retrieval_plan.llm_subqueries)
        else:
            candidates = retrieval_plan.llm_subqueries
        selected: list[RoleDirectedSubquery] = []
        seen: set[tuple[str, str]] = set()
        for subquery in candidates:
            if subquery.role not in requested_roles:
                continue
            key = (subquery.role, subquery.query)
            if key in seen:
                continue
            seen.add(key)
            selected.append(subquery)
        return tuple(selected)


def _record_missing_role_subqueries(
    ctx: WorkspaceRetrievalContext,
    *,
    requested_roles: Sequence[str],
    subqueries: Sequence[RoleDirectedSubquery],
    phase: str,
) -> None:
        executable_roles = {subquery.role for subquery in subqueries}
        missing_roles = tuple(role for role in ordered_unique(requested_roles) if role not in executable_roles)
        if not missing_roles:
            return
        ctx.trace.record(
            "role_subquery_missing",
            {
                "phase": phase,
                "roles": list(missing_roles),
                "reason": "no_planned_subquery_for_role",
            },
        )


def complete_role_buckets(
    ctx: WorkspaceRetrievalContext,
        *,
        retrieval_plan: WorkspaceRetrievalPlan,
        buckets: Sequence[RoleRetrievalBucket],
    ) -> tuple[RoleRetrievalBucket, ...]:
        accepted_anchors = _accepted_anchor_records_flow(buckets)
        accepted_by_role: dict[str, tuple[AnchorRecord, ...]] = {}
        for role in retrieval_plan.required_roles:
            accepted_by_role[role] = tuple(anchor for anchor in accepted_anchors if anchor.role == role)
        completed: list[RoleRetrievalBucket] = []
        for bucket in buckets:
            if bucket.role not in retrieval_plan.required_roles:
                completed.append(bucket)
                continue
            completed.append(
                complete_role_bucket(ctx, 
                    retrieval_plan=retrieval_plan,
                    target_bucket=bucket,
                    all_buckets=buckets,
                    accepted_anchors=accepted_anchors,
                accepted_by_role=accepted_by_role,
            )
        )
        return tuple(completed)


def complete_role_bucket(
    ctx: WorkspaceRetrievalContext,
        *,
        retrieval_plan: WorkspaceRetrievalPlan,
        target_bucket: RoleRetrievalBucket,
        all_buckets: Sequence[RoleRetrievalBucket],
        accepted_anchors: Sequence[AnchorRecord],
        accepted_by_role: Mapping[str, tuple[AnchorRecord, ...]],
    ) -> RoleRetrievalBucket:
        ctx.trace.record(
            "role_completion_started",
            {
                "role": target_bucket.role,
                "accepted_refs": [candidate.source_id for candidate in target_bucket.accepted_candidates],
                "rejected_refs": list(target_bucket.rejected_refs),
            },
        )
        candidate_entries = role_completion_candidates(ctx, target_bucket=target_bucket, all_buckets=all_buckets)
        scored_entries: list[tuple[RetrievalCandidate, str, str, RoleValidationResult, float]] = []
        for candidate, source_role, source_state, prior_validation in candidate_entries:
            score = score_role_completion(
                RoleCompletionContext(
                    role=target_bucket.role,
                    query=target_bucket.query,
                    helper_queries=target_bucket.helper_queries,
                    candidate_path=candidate.path or "",
                    candidate_text=candidate.text,
                    candidate_source_id=candidate.source_id,
                    candidate_file_role=candidate.metadata.get("file_role", ""),
                    source_role=source_role,
                    source_state=source_state,
                    prior_validation_score=prior_validation.total_score,
                    accepted_anchors=accepted_anchors,
                    accepted_anchors_by_role=dict(accepted_by_role),
                )
            )
            ctx.trace.record(
                "role_completion_candidate_scored",
                {
                    "role": target_bucket.role,
                    "ref": candidate.source_id,
                    "path": candidate.path or "",
                    "source_role": source_role,
                    "source_state": source_state,
                    "score": score.to_dict(),
                },
            )
            if score.accepted:
                scored_entries.append(
                    (
                        candidate,
                        source_role,
                        source_state,
                        _role_completion_validation_result_flow(
                            candidate=candidate,
                            source_state=source_state,
                            support_paths=score.support_paths,
                            score_total=score.total_score,
                            threshold=score.threshold,
                            reasons=score.reasons,
                        ),
                        score.total_score,
                    )
                )

        if not scored_entries:
            ctx.trace.record(
                "role_completion_completed",
                {"role": target_bucket.role, "promoted_refs": [], "selected_refs": [candidate.source_id for candidate in target_bucket.accepted_candidates]},
            )
            return target_bucket

        scored_entries.sort(key=lambda item: (-item[4], item[0].path or "", item[0].source_id))
        selected_entries = _select_diverse_completion_entries(scored_entries, limit=MAX_ROLE_BUCKET_CANDIDATES)
        selected_refs = {candidate.source_id for candidate, _, _, _, _ in selected_entries}
        existing_refs = {candidate.source_id for candidate in target_bucket.accepted_candidates}
        promoted_entries = [entry for entry in selected_entries if entry[0].source_id not in existing_refs]
        if not promoted_entries and selected_refs == existing_refs:
            ctx.trace.record(
                "role_completion_completed",
                {"role": target_bucket.role, "promoted_refs": [], "selected_refs": [candidate.source_id for candidate in target_bucket.accepted_candidates]},
            )
            return target_bucket

        promoted_refs: list[str] = []
        new_evaluations = list(target_bucket.evaluations)
        for candidate, source_role, source_state, validation, _ in promoted_entries:
            new_evaluations.append(
                RoleCandidateEvaluation(
                    candidate=candidate,
                    validation=validation,
                    stage="role_completion",
                    source_role=source_role,
                )
            )
            promoted_refs.append(candidate.source_id)
            ctx.trace.record(
                "role_completion_candidate_promoted",
                {
                    "role": target_bucket.role,
                    "ref": candidate.source_id,
                    "source_role": source_role,
                    "source_state": source_state,
                    "acceptance_source": validation.acceptance_source,
                },
            )

        selected_candidates = tuple(candidate for candidate, _, _, _, _ in selected_entries)
        selected_ref_set = {candidate.source_id for candidate in selected_candidates}
        rejected_refs = tuple(ref for ref in target_bucket.rejected_refs if ref not in selected_ref_set)
        validation_notes = list(target_bucket.validation_notes)
        if promoted_refs:
            validation_notes.extend(["role_completion_promoted"] * len(promoted_refs))
        if selected_candidates:
            role_status = "weak"
            missing_reason = "snippet_selection_pending"
        else:
            role_status = "missing"
            missing_reason = target_bucket.missing_reason
        completed_bucket = RoleRetrievalBucket(
            role=target_bucket.role,
            query=target_bucket.query,
            helper_queries=target_bucket.helper_queries,
            observations=target_bucket.observations,
            retrieved_candidates=_merge_retrieved_candidates(target_bucket.retrieved_candidates, tuple(candidate for candidate, _, _, _, _ in selected_entries)),
            evaluations=tuple(new_evaluations),
            accepted_candidates=selected_candidates,
            rejected_refs=rejected_refs,
            validation_notes=tuple(validation_notes),
            missing_reason=missing_reason,
            role_status=role_status,
            satisfying_refs=(),
            snippet_assessment=target_bucket.snippet_assessment,
            satisfaction_source=target_bucket.satisfaction_source,
        )
        ctx.trace.record(
            "role_completion_completed",
            {
                "role": target_bucket.role,
                "promoted_refs": promoted_refs,
                "selected_refs": [candidate.source_id for candidate in selected_candidates],
            },
        )
        return completed_bucket


def prepare_role_bucket(
    ctx: WorkspaceRetrievalContext,
        *,
        retrieval_plan: WorkspaceRetrievalPlan,
        role: str,
        query: str,
        qdrant_tool: QdrantHybridSearchTool,
        open_file_tool: OpenFileTool,
        narrowed_files: Sequence[str],
        phase: str,
    ) -> tuple[PreparedRoleBucket, int]:
        helper_queries = _role_query_package(retrieval_plan, role, query)
        ctx.trace.record("role_subquery_started", {"role": role, "query": query, "phase": phase, "helper_queries": list(helper_queries)})
        role_stage_started = time.perf_counter()
        observations: list[ToolObservation] = []
        raw_candidates: list[RetrievalCandidate] = []
        seeded_candidates: list[RetrievalCandidate] = []
        direct_owner_candidates: list[RetrievalCandidate] = []
        tool_calls = 0
        role_narrowed_files = _role_scoped_narrowed_files(retrieval_plan, role, narrowed_files)
        shared_arguments: dict[str, Any] = {"limit": min(ctx.config.structural_graph_max_files, MAX_EVIDENCE_ITEMS)}
        for query_index, helper_query in enumerate(helper_queries[:MAX_ROLE_QUERIES]):
            request = ToolRequest(
                tool_name="qdrant_hybrid_search",
                arguments={"query": helper_query, "_coverage_area": role, "source_category": "source_code", "file_role": "implementation", **shared_arguments},
                reason=f"Retrieve broad code evidence for the {role} role.",
            )
            observation = qdrant_tool.run(request)
            ctx.trace.record_tool(request, observation, round_index=0)
            observations.append(observation)
            tool_calls += 1
            helper_candidates = _candidates_from_search_observation_flow(observation, coverage_area=role)
            raw_candidates.extend(helper_candidates)
            seeded_candidates.extend(_select_helper_query_seed_candidates_flow(helper_candidates))
            if role_narrowed_files and query_index < 2:
                narrowed_request = ToolRequest(
                    tool_name="qdrant_hybrid_search",
                    arguments={
                        "query": helper_query,
                        "_coverage_area": role,
                        "source_category": "source_code",
                        "file_role": "implementation",
                        "paths": list(role_narrowed_files),
                        "limit": min(ctx.config.structural_graph_max_files, MAX_EVIDENCE_ITEMS),
                    },
                    reason=f"Boost exact-symbol structural candidates for the {role} role without excluding global results.",
                )
                narrowed_observation = qdrant_tool.run(narrowed_request)
                ctx.trace.record_tool(narrowed_request, narrowed_observation, round_index=0)
                observations.append(narrowed_observation)
                tool_calls += 1
                narrowed_candidates = _candidates_from_search_observation_flow(narrowed_observation, coverage_area=role)
                raw_candidates.extend(narrowed_candidates)
                seeded_candidates.extend(_select_helper_query_seed_candidates_flow(narrowed_candidates))

        seen_candidate_paths = {candidate.path for candidate in raw_candidates if candidate.path}
        for narrowed_path in role_narrowed_files:
            normalized_path = str(narrowed_path).replace("\\", "/").lstrip("/")
            if normalized_path in seen_candidate_paths:
                continue
            search_terms = _in_file_search_terms(retrieval_plan, role, query, helper_queries)
            if not _role_owner_path_match(role, normalized_path) and not _owner_artifact_path_match(normalized_path, search_terms):
                continue
            direct_candidate = _direct_owner_candidate_from_path_flow(ctx, 
                role=role,
                target_path=normalized_path,
                query=query,
                search_terms=search_terms,
            )
            if direct_candidate is None:
                continue
            raw_candidates.append(direct_candidate)
            seeded_candidates.append(direct_candidate)
            direct_owner_candidates.append(direct_candidate)
            seen_candidate_paths.add(normalized_path)

        ranked_file_candidates = _collapse_candidates_to_file_candidates(
            role=role,
            candidates=_rank_candidates(seeded_candidates or raw_candidates),
            retrieval_path="qdrant_file_candidate",
        )
        direct_owner_paths = {candidate.path for candidate in direct_owner_candidates if candidate.path}
        ranked_candidates = tuple(
            _rank_unique_candidates(
                list(direct_owner_candidates)
                + [candidate for candidate in ranked_file_candidates if candidate.path not in direct_owner_paths]
            )
        )
        prepared_candidates: list[RetrievalCandidate] = []
        seen_paths: set[str] = set()
        for candidate in ranked_candidates[:MAX_ROLE_INITIAL_PATHS]:
            if candidate.path and candidate.path in seen_paths:
                continue
            if candidate.path:
                seen_paths.add(candidate.path)
            prepared_candidates.append(candidate)
            if len(prepared_candidates) >= MAX_ROLE_CANDIDATE_EVALUATIONS:
                break

        prepared_bucket = PreparedRoleBucket(
            role=role,
            query=query,
            helper_queries=helper_queries,
            observations=tuple(observations),
            candidates=tuple(prepared_candidates),
        )
        ctx.trace.record(
            "role_subquery_completed",
            {
                "role": role,
                "query": query,
                "phase": phase,
                "helper_queries": list(helper_queries),
                "candidate_count": len(prepared_bucket.candidates),
                "observation_count": len(observations),
                "tool_calls": tool_calls,
                "elapsed_ms": int((time.perf_counter() - role_stage_started) * 1000),
            },
        )
        return prepared_bucket, tool_calls


def role_completion_candidates(
    ctx: WorkspaceRetrievalContext,
        *,
        target_bucket: RoleRetrievalBucket,
        all_buckets: Sequence[RoleRetrievalBucket],
    ) -> tuple[tuple[RetrievalCandidate, str, str, RoleValidationResult], ...]:
        entries: list[tuple[RetrievalCandidate, str, str, RoleValidationResult]] = []
        seen_refs: set[str] = set()
        target_accepted_refs = {candidate.source_id for candidate in target_bucket.accepted_candidates}
        for bucket in all_buckets:
            for evaluation in bucket.evaluations:
                ref = evaluation.candidate.source_id
                if ref in seen_refs:
                    continue
                seen_refs.add(ref)
                if ref in target_accepted_refs:
                    source_state = "accepted_same_role"
                elif any(candidate.source_id == ref for candidate in bucket.accepted_candidates):
                    source_state = "accepted_other_role"
                else:
                    source_state = "rejected"
                entries.append((evaluation.candidate, bucket.role, source_state, evaluation.validation))
        return tuple(entries[:MAX_ROLE_COMPLETION_CANDIDATES])


def evaluate_prepared_role_bucket(
    ctx: WorkspaceRetrievalContext,
        prepared_bucket: PreparedRoleBucket,
        *,
        anchor_support: AnchorSupport,
        max_accept_count: int,
        structural_tools: Mapping[str, Any],
    ) -> RoleRetrievalBucket:
        evaluations: list[RoleCandidateEvaluation] = []
        accepted: list[RetrievalCandidate] = []
        rejected_refs: list[str] = []
        validation_notes: list[str] = []
        for candidate in prepared_bucket.candidates:
            validation = _validate_role_candidate_flow(ctx, 
                role=prepared_bucket.role,
                query=prepared_bucket.query,
                helper_queries=prepared_bucket.helper_queries,
                candidate=candidate,
                anchor_support=anchor_support,
                structural_tools=structural_tools,
            )
            evaluations.append(RoleCandidateEvaluation(candidate=candidate, validation=validation))
            ctx.trace.record(
                "role_candidate_evaluated",
                {
                    "role": prepared_bucket.role,
                    "ref": candidate.source_id,
                    "path": candidate.path or "",
                    "validation": validation.to_dict(),
                },
            )
            if validation.accepted:
                if len(accepted) < max_accept_count:
                    accepted.append(candidate)
                validation_notes.append(validation.reason)
                ctx.trace.record(
                    "role_candidate_accepted",
                    {
                        "role": prepared_bucket.role,
                        "ref": candidate.source_id,
                        "reason": validation.reason,
                        "acceptance_source": validation.acceptance_source,
                    },
                )
            else:
                rejected_refs.append(candidate.source_id)
                validation_notes.append(validation.reason)
                ctx.trace.record(
                    "role_candidate_rejected",
                    {
                        "role": prepared_bucket.role,
                        "ref": candidate.source_id,
                        "reason": validation.reason,
                        "acceptance_source": validation.acceptance_source,
                    },
                )
        missing_reason = validation_notes[-1] if not accepted and validation_notes else ""
        return RoleRetrievalBucket(
            role=prepared_bucket.role,
            query=prepared_bucket.query,
            helper_queries=prepared_bucket.helper_queries,
            observations=prepared_bucket.observations,
            retrieved_candidates=prepared_bucket.candidates,
            evaluations=tuple(evaluations),
            accepted_candidates=tuple(accepted),
            rejected_refs=tuple(ordered_unique(rejected_refs)),
            validation_notes=tuple(validation_notes),
            missing_reason=missing_reason or ("no_validated_candidates" if not accepted else ""),
            role_status="strong" if accepted else "missing",
            satisfying_refs=tuple(candidate.source_id for candidate in accepted),
            snippet_assessment=(),
            satisfaction_source="first_pass",
        )
