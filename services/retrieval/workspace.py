from __future__ import annotations

import json
import re
import subprocess
import hashlib
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from core.models import ConversationState, EvidenceItem, PolicyResult, RetrievalResult
from core.source_policy import SourceCategory
from services.retrieval.bm25 import DEFAULT_EXCLUDED_PATHS, build_index_from_repo, load_index, save_index
from services.retrieval.config import ConnectedSourceDocument, WorkspaceRetrievalConfig
from services.retrieval.mcp import (
    LocalMCPConnectedSourceAdapter,
    MCPConnectedSourceError,
    RemoteMCPConnectedSourceAdapter,
    RemoteMCPConnectedSourceError,
)
from services.retrieval.obsidian import (
    ObsidianHybridSearchAdapter,
    ObsidianSearchError,
    ObsidianSearchResult,
    trusted_file_hints_from_obsidian_results,
)
from services.retrieval.pipeline.constants import (
    MAX_EVIDENCE_ITEMS,
    MAX_FILE_ROLE_ALTERNATES,
    MAX_FILE_ROLE_RESOLUTION_ROUNDS,
    MAX_ROLE_BUCKET_CANDIDATES,
    MAX_ROLE_CANDIDATE_EVALUATIONS,
    MAX_ROLE_CODE_CONTEXT_QUERIES,
    MAX_ROLE_CODE_CONTEXT_TERMS,
    MAX_ROLE_COMPLETION_CANDIDATES,
    MAX_ROLE_FOLLOWUP_QUERIES,
    MAX_ROLE_INITIAL_PATHS,
    MAX_ROLE_PER_QUERY_TOP_PATHS,
    MAX_ROLE_QUERIES,
    MAX_ROLE_REFERENCE_EXPANSION_SOURCES,
    MAX_ROLE_REFERENCE_EXPANSION_TARGETS,
    MAX_ROLE_REFERENCE_SCAN_LINE_COUNT,
)
from services.retrieval.pipeline.coverage import (
    build_deterministic_coverage_gate as _build_deterministic_coverage_gate,
    coverage_status as _coverage_status,
)
from services.retrieval.pipeline.file_level import (
    anchor_support_paths as _anchor_support_paths,
    bucket_missing_roles as _bucket_missing_roles,
    bucket_unresolved_roles as _bucket_unresolved_roles,
    candidate_from_chunk_payload as _candidate_from_chunk_payload,
    candidate_is_reference_expansion_source as _candidate_is_reference_expansion_source,
    candidate_rank_key as _candidate_rank_key,
    candidate_satisfies_owner_layer as _candidate_satisfies_owner_layer,
    candidate_symbol as _candidate_symbol,
    clean_query_terms as _clean_query_terms,
    collapse_candidates_to_file_candidates as _collapse_candidates_to_file_candidates,
    code_identifier_terms as _code_identifier_terms,
    completion_redundancy_penalty as _completion_redundancy_penalty,
    coverage_area_names as _coverage_area_names,
    diagnostics_like_candidate as _diagnostics_like_candidate,
    extract_explicit_reference_paths as _extract_explicit_reference_paths,
    has_role_owner_candidate as _has_role_owner_candidate,
    is_generic_reference_hub as _is_generic_reference_hub,
    iterative_code_context_queries as _iterative_code_context_queries,
    line_start_from_range as _line_start_from_range,
    looks_like_source_file as _looks_like_source_file,
    matched_anchor_paths as _matched_anchor_paths,
    merge_source_priorities,
    obsidian_source_queries as _obsidian_source_queries,
    owner_artifact_path_match as _owner_artifact_path_match,
    path_diverse_candidates as _path_diverse_candidates,
    rank_unique_candidates as _rank_unique_candidates,
    recovery_anchor_queries as _recovery_anchor_queries,
    resolve_explicit_reference_path as _resolve_explicit_reference_path,
    role_query_package as _role_query_package,
    role_owner_context_terms as _role_owner_context_terms,
    role_owner_path_match as _role_owner_path_match,
    role_owner_path_tokens as _role_owner_path_tokens,
    role_phase_path_allowed as _role_phase_path_allowed,
    role_requires_owner_layer as _role_requires_owner_layer,
    role_scoped_narrowed_files as _role_scoped_narrowed_files,
    select_diverse_completion_entries as _select_diverse_completion_entries,
    target_matches_reference_owner_vocab as _target_matches_reference_owner_vocab,
    tool_summary_payload as _tool_summary_payload,
    trusted_file_hints_for_result as _trusted_file_hints_for_result,
)
from services.retrieval.pipeline.models import (
    PreparedRoleBucket,
    RetrievalCandidate,
    RetrievalSynthesisDecision,
    RoleCandidateEvaluation,
    RoleRetrievalBucket,
    RoleValidationResult,
)
from services.retrieval.pipeline.protocol_graph import discover_protocol_relationship_candidates
from services.retrieval.pipeline.refinement import refine_role_file_group as _refine_role_file_group
from services.retrieval.pipeline.snippet_level import (
    best_direct_owner_span as _best_direct_owner_span,
    direct_owner_window_bonus as _direct_owner_window_bonus,
    drop_redundant_file_candidates as _drop_redundant_file_candidates,
    followup_snippet_quality as _rescue_snippet_quality,
    in_file_refinement_terms as _in_file_refinement_terms,
    in_file_search_terms as _in_file_search_terms,
    is_file_candidate as _is_file_candidate,
    late_snippet_quality as _late_snippet_quality,
    latest_evaluation_for_ref as _latest_evaluation_for_ref,
    merge_retrieved_candidates as _merge_retrieved_candidates,
    planning_snippets as _planning_snippets,
    read_owner_text_file as _read_owner_text_file,
    role_followup_queries as _role_followup_queries,
    role_snippet_queries as _role_snippet_queries,
    salient_candidate_excerpt as _salient_candidate_excerpt,
    snippet_quality_for_ref as _snippet_quality_for_ref,
    snippet_reason_for_ref as _snippet_reason_for_ref,
)
from services.retrieval.role_specs import (
    path_matches_role,
    path_matches_role_support,
    role_keywords,
    role_path_hints,
    role_phrase_from_spec,
    text_matches_role_keywords,
)
from services.retrieval.role_completion import RoleCompletionContext, score_role_completion
from services.retrieval.role_validation import AnchorRecord, AnchorSupport, RoleValidationContext, validator_for_role
from services.retrieval.responsibility import (
    FileResponsibilityProfile,
    ResponsibilityExpansionIntent,
    ResponsibilityScore,
    infer_expansion_intents,
    profile_candidate,
    score_responsibility,
)
from services.retrieval.step2 import WorkspaceRetrievalPlan, existing_evidence_plan, extract_prompt_evidence, plan_workspace_retrieval_step
from services.retrieval.step2.common import IDENTIFIER_PATTERN, merge_paths, ordered_unique
from services.retrieval.tools import (
    CGCAnalyzeCalleesTool,
    CGCAnalyzeCallersTool,
    CGCFindCodeTool,
    CGCIndexRepoTool,
    CGCQueryGraphTool,
    CGCRunCliTool,
    OpenFileTool,
    QdrantHybridSearchTool,
    ToolObservation,
    ToolRequest,
)
from services.retrieval.tools.local import build_repo_sketch, file_role as tool_file_role
from services.retrieval.workspace_llm import (
    assess_role_buckets_with_llm,
)


class WorkspaceRetrievalStage:
    """Workspace retrieval built around per-role subquery validation."""

    def __init__(self, config: WorkspaceRetrievalConfig) -> None:
        config.validate()
        resolved_qdrant = replace(
            config.qdrant_config,
            collection_name=self._repo_scoped_collection_name(
                base_collection_name=config.qdrant_config.collection_name,
                workspace_root=Path(config.workspace_root),
            ),
        )
        self.config = replace(config, qdrant_config=resolved_qdrant)

    def retrieve(self, state: ConversationState, policy_result: PolicyResult) -> RetrievalResult:
        if state.evidence:
            retrieval_plan = existing_evidence_plan(
                conversation_id=state.conversation_id,
                raw_prompt=state.user_input,
                allowed_sources=policy_result.allowed_sources,
            )
            self._record("retrieval_plan_created", retrieval_plan.to_dict())
            return RetrievalResult(
                evidence=tuple(state.evidence),
                coverage_status="sufficient_context",
                sufficient=True,
                retrieval_summary={
                    "retriever": "workspace",
                    "retrieval_plan": retrieval_plan.to_dict(),
                    "source_registry": [entry.to_dict() for entry in self.config.source_registry()],
                    "index_rebuilt": False,
                    "tool_calls": 0,
                    "exploration_rounds": 0,
                    "stop_reason": "existing_context_sufficient",
                },
            )

        connected_documents = self._connected_documents(state.user_input, policy_result.allowed_sources)
        cgc_tools = self._cgc_tools()
        if self.config.enable_indexing:
            self._record(
                "workspace_index_cgc_started",
                {
                    "workspace_root": self.config.workspace_root,
                    "index_dir": self.config.index_dir,
                },
            )
            index_observation = cgc_tools["cgc_index_repo"].run(
                ToolRequest(tool_name="cgc_index_repo", arguments={}, reason="mandatory code graph refresh")
            )
            self._record_tool(ToolRequest(tool_name="cgc_index_repo", arguments={}), index_observation, round_index=0)
            if index_observation.status != "ok":
                return self._failed_result(None, failure="cgc_index_failed", observation=index_observation)
        else:
            index_observation = ToolObservation(
                tool_name="cgc_index_repo",
                status="ok",
                payload={"skipped": True, "reason": "indexing_disabled"},
                metadata={"result_count": "1", "command": "skipped_indexing_disabled"},
            )
            self._record_tool(ToolRequest(tool_name="cgc_index_repo", arguments={}), index_observation, round_index=0)

        try:
            self._record(
                "workspace_index_bm25_started",
                {
                    "workspace_root": self.config.workspace_root,
                    "index_dir": self.config.index_dir,
                },
            )
            index = self._rebuild_index()
        except RuntimeError as exc:
            failed_observation = ToolObservation(
                tool_name="qdrant_hybrid_search",
                status="failed",
                payload={"reason": str(exc)},
                metadata={"result_count": "0"},
            )
            return self._failed_result(None, failure="qdrant_index_sync_failed", observation=failed_observation)
        qdrant_tool = QdrantHybridSearchTool(
            index,
            qdrant_config=self.config.qdrant_config,
            embedding_config=self.config.embedding_config,
            cache_path=str(Path(self.config.index_dir) / "qdrant-embeddings-cache.json"),
        )
        open_file_tool = OpenFileTool(index)
        obsidian_results = self._search_obsidian_notes(state.user_input, policy_result.allowed_sources)
        if obsidian_results:
            filtered_obsidian_results = tuple(
                result for result in obsidian_results if result.score >= self.config.obsidian_min_guidance_score
            )
            if len(filtered_obsidian_results) != len(obsidian_results):
                self._record(
                    "trusted_local_notes_results_filtered",
                    {
                        "adapter": "obsidian-hybrid-search",
                        "min_score": self.config.obsidian_min_guidance_score,
                        "kept_count": len(filtered_obsidian_results),
                        "dropped_count": len(obsidian_results) - len(filtered_obsidian_results),
                        "scores": [result.score for result in obsidian_results],
                    },
                )
            obsidian_results = filtered_obsidian_results
        if obsidian_results:
            connected_documents = tuple(
                self._obsidian_result_to_connected_document(result)
                for result in obsidian_results
            ) + connected_documents
        prompt_evidence = extract_prompt_evidence(state, policy_result.allowed_sources)
        step2_repo_context, preplan_tool_calls = self._build_step2_repo_context(prompt_evidence, cgc_tools["cgc_find_code"], index)
        retrieval_plan = plan_workspace_retrieval_step(
            state=state,
            policy_result=policy_result,
            connected_documents=connected_documents,
            llm_config=self.config.llm_config,
            prompt_evidence=prompt_evidence,
            repo_context=step2_repo_context,
            log_event=lambda event_type, payload: self._record(event_type, {"conversation_id": state.conversation_id, **payload}),
            log_warning=lambda payload: self._record("llm_request_warning", {"conversation_id": state.conversation_id, **payload}),
        )
        retrieval_plan, trusted_note_hints = self._apply_obsidian_guidance(retrieval_plan, obsidian_results, index)
        self._record("retrieval_plan_created", retrieval_plan.to_dict())

        global_narrowed_files, narrowing_observations, tool_call_count = self._run_initial_narrowing(
            retrieval_plan=retrieval_plan,
            cgc_find_tool=cgc_tools["cgc_find_code"],
            preplan_tool_calls=preplan_tool_calls,
        )
        if global_narrowed_files is None:
            failed_observation = narrowing_observations[0] if narrowing_observations else index_observation
            return self._failed_result(retrieval_plan, failure="cgc_narrowing_failed", observation=failed_observation)

        required_buckets, tool_call_count, responsibility_intents = self._retrieve_responsibility_role_buckets(
            retrieval_plan=retrieval_plan,
            subquery_roles=retrieval_plan.required_roles,
            qdrant_tool=qdrant_tool,
            open_file_tool=open_file_tool,
            cgc_tools=cgc_tools,
            narrowed_files=global_narrowed_files,
            starting_tool_call_count=tool_call_count,
            phase="required",
        )
        owner_focus_roles = self._owner_focus_roles(retrieval_plan=retrieval_plan, buckets=required_buckets)
        self._record(
            "owner_focus_roles_selected",
            {
                "required_roles": list(retrieval_plan.required_roles),
                "focused_roles": list(owner_focus_roles),
            },
        )
        required_buckets, tool_call_count = self._refine_selected_role_buckets(
            buckets=required_buckets,
            rescue_roles=owner_focus_roles,
            qdrant_tool=qdrant_tool,
            open_file_tool=open_file_tool,
            cgc_tools=cgc_tools,
            starting_tool_call_count=tool_call_count,
        )
        synthesis_decision = self._synthesize_or_accept_deterministic(retrieval_plan, required_buckets)
        required_buckets = self._apply_synthesis_feedback(
            buckets=required_buckets,
            decision=synthesis_decision,
            required_roles=retrieval_plan.required_roles,
        )
        required_buckets, tool_call_count, synthesis_decision = self._recover_weak_role_buckets(
            retrieval_plan=retrieval_plan,
            buckets=required_buckets,
            synthesis_decision=synthesis_decision,
            qdrant_tool=qdrant_tool,
            open_file_tool=open_file_tool,
            cgc_tools=cgc_tools,
            narrowed_files=global_narrowed_files,
            starting_tool_call_count=tool_call_count,
        )
        required_buckets = self._apply_protocol_relationship_bridge(required_buckets, retrieval_plan=retrieval_plan)
        deterministic_gate = _build_deterministic_coverage_gate(retrieval_plan.required_roles, required_buckets)

        supporting_buckets: tuple[RoleRetrievalBucket, ...] = ()
        owner_grounded = self._focused_owner_grounded(required_buckets, owner_focus_roles)
        self._record(
            "owner_grounding_checked",
            {
                "focused_roles": list(owner_focus_roles),
                "grounded": owner_grounded,
            },
        )
        if not synthesis_decision.acceptance_satisfied and _bucket_unresolved_roles(required_buckets) and owner_grounded:
            supporting_buckets, tool_call_count, supporting_intents = self._retrieve_responsibility_role_buckets(
                retrieval_plan=retrieval_plan,
                subquery_roles=retrieval_plan.supporting_roles,
                qdrant_tool=qdrant_tool,
                open_file_tool=open_file_tool,
                cgc_tools=cgc_tools,
                narrowed_files=global_narrowed_files,
                starting_tool_call_count=tool_call_count,
                phase="supporting",
            )
            responsibility_intents = tuple((*responsibility_intents, *supporting_intents))
            supporting_buckets, tool_call_count = self._refine_selected_role_buckets(
                buckets=supporting_buckets,
                rescue_roles=retrieval_plan.supporting_roles,
                qdrant_tool=qdrant_tool,
                open_file_tool=open_file_tool,
                cgc_tools=cgc_tools,
                starting_tool_call_count=tool_call_count,
            )
            synthesis_decision = self._synthesize_or_accept_deterministic(retrieval_plan, required_buckets + supporting_buckets)
            updated_buckets = self._apply_synthesis_feedback(
                buckets=required_buckets + supporting_buckets,
                decision=synthesis_decision,
                required_roles=retrieval_plan.required_roles,
            )
            required_buckets = tuple(bucket for bucket in updated_buckets if bucket.role in retrieval_plan.required_roles)
            supporting_buckets = tuple(bucket for bucket in updated_buckets if bucket.role in retrieval_plan.supporting_roles)
            deterministic_gate = _build_deterministic_coverage_gate(retrieval_plan.required_roles, required_buckets)
        elif not owner_grounded and _bucket_unresolved_roles(required_buckets):
            self._record(
                "supporting_expansion_deferred",
                {
                    "reason": "owner_not_grounded",
                    "unresolved_required_roles": list(_bucket_unresolved_roles(required_buckets)),
                    "focused_roles": list(owner_focus_roles),
                },
            )

        selected = self._select_evidence_items(required_buckets, supporting_buckets, policy_result.allowed_sources)
        selected = self._append_accepted_decision_evidence(
            selected,
            synthesis_decision=synthesis_decision,
            buckets=required_buckets + supporting_buckets,
            source_policy=policy_result.allowed_sources,
        )
        selected = self._append_connected_source_evidence(
            selected,
            connected_documents=connected_documents,
            retrieval_plan=retrieval_plan,
            source_policy=policy_result.allowed_sources,
        )
        self._record("deterministic_coverage_gate_completed", deterministic_gate.to_dict())
        for coverage_area in _coverage_area_names(retrieval_plan):
            bucket = next((item for item in required_buckets + supporting_buckets if item.role == coverage_area), None)
            status = bucket.role_status if bucket is not None else ("strong" if any(item.metadata.get("coverage_area") == coverage_area for item in selected) else "missing")
            self._record("gap_check_completed", {"coverage_area": coverage_area, "status": status})
        for bucket in required_buckets + supporting_buckets:
            self._record(
                "role_coverage_completed",
                {
                    "role": bucket.role,
                    "role_status": bucket.role_status,
                    "accepted_count": len(bucket.accepted_candidates),
                    "satisfying_count": len(bucket.satisfying_refs),
                    "rejected_count": len(bucket.rejected_refs),
                    "missing_reason": bucket.missing_reason,
                },
            )
        for item in selected:
            self._record(
                "evidence_selected",
                {
                    "source_id": item.source_id,
                    "source_category": item.source_category.value,
                    "rank": item.rank,
                    "metadata": dict(item.metadata),
                },
            )

        retrieval_summary = {
            "retriever": "workspace",
            "retrieval_plan": retrieval_plan.to_dict(),
            "source_registry": [entry.to_dict() for entry in self.config.source_registry()],
            "connected_source_count": len(connected_documents),
            "connected_sources": [
                {
                    "source_category": document.source_category.value,
                    "source_id": document.source_id,
                    "title": document.title,
                    "adapter": document.metadata.get("adapter", "connected_documents"),
                }
                for document in connected_documents[:20]
            ],
            "index_rebuilt": True,
            "index_document_count": len(index.documents),
            "selected_count": len(selected),
            "tool_calls": tool_call_count,
            "exploration_rounds": 0,
            "stop_reason": synthesis_decision.stop_reason or "late_synthesis_complete",
            "cgc_command_prefix": list(self.config.cgc_command),
            "cgc_index_command": index_observation.payload.get("command", []),
            "cgc_narrowed_file_count": len(global_narrowed_files),
            "qdrant_path_filter_count": len(global_narrowed_files),
            "required_role_buckets": [bucket.to_dict() for bucket in required_buckets],
            "supporting_role_buckets": [bucket.to_dict() for bucket in supporting_buckets],
            "refinement_policy": synthesis_decision.to_dict(),
            "responsibility_expansion_intents": [intent.to_dict() for intent in responsibility_intents],
            "deterministic_coverage_gate": deterministic_gate.to_dict(),
            "trusted_local_notes": [
                {
                    "path": result.path,
                    "title": result.title,
                    "score": result.score,
                    "trusted_file_hints": list(_trusted_file_hints_for_result(result)),
                }
                for result in obsidian_results
            ],
            "trusted_local_note_file_hints": list(trusted_note_hints),
        }
        final_sufficient = bool(selected) and synthesis_decision.acceptance_satisfied and deterministic_gate.satisfied
        return RetrievalResult(
            evidence=tuple(selected),
            coverage_status=_coverage_status(selected, synthesis_decision, retrieval_plan, deterministic_gate),
            sufficient=final_sufficient,
            retrieval_summary=retrieval_summary,
            failures_or_fallbacks=tuple(ordered_unique([*_bucket_unresolved_roles(required_buckets), *deterministic_gate.missing_roles])),
        )

    def _failed_result(
        self,
        retrieval_plan: WorkspaceRetrievalPlan | None,
        *,
        failure: str,
        observation: ToolObservation,
    ) -> RetrievalResult:
        self._record(
            "retrieval_failed",
            {
                "failure": failure,
                "tool_name": observation.tool_name,
                "status": observation.status,
                "payload": dict(observation.payload),
            },
        )
        return RetrievalResult(
            evidence=(),
            coverage_status="failed",
            sufficient=False,
            retrieval_summary={
                "retriever": "workspace",
                **({"retrieval_plan": retrieval_plan.to_dict()} if retrieval_plan is not None else {}),
                "source_registry": [entry.to_dict() for entry in self.config.source_registry()],
                "cgc_command_prefix": list(self.config.cgc_command),
                "failure": failure,
            },
            failures_or_fallbacks=(failure,),
        )

    def _rebuild_index(self):
        index_dir = Path(self.config.index_dir)
        index_path = index_dir / "bm25-index.json"
        scope_manifest_path = index_dir / "bm25-scope-manifest.json"
        scope_manifest = _load_sync_manifest(scope_manifest_path)
        effective_exclude_paths = (
            DEFAULT_EXCLUDED_PATHS if self.config.index_exclude_paths is None else self.config.index_exclude_paths
        )
        scope_signature = {
            "workspace_root": str(Path(self.config.workspace_root).resolve()),
            "exclude_paths": list(effective_exclude_paths),
            "chunk_line_count": self.config.chunk_line_count,
            "chunk_line_overlap": self.config.chunk_line_overlap,
        }
        default_scope = self.config.index_exclude_paths is None
        legacy_default_scope = index_path.exists() and not scope_manifest and default_scope
        if index_path.exists() and (_sync_manifest_scope_matches(scope_manifest, scope_signature) or legacy_default_scope):
            index = load_index(index_dir)
            self._record(
                "workspace_bm25_index_reused",
                {
                    "workspace_root": self.config.workspace_root,
                    "index_dir": self.config.index_dir,
                    "document_count": len(index.documents),
                },
            )
        else:
            if not self.config.enable_indexing:
                raise RuntimeError(f"Missing BM25 index while RETRIEVAL_ENABLE_INDEXING=false: {index_path}")
            index = build_index_from_repo(
                repo_path=self.config.workspace_root,
                commit="workspace",
                chunk_line_count=self.config.chunk_line_count,
                chunk_line_overlap=self.config.chunk_line_overlap,
                snapshot="workspace_current",
                visibility="workspace_visible",
                origin="workspace_index",
                exclude_paths=self.config.index_exclude_paths,
            )
            save_index(index, index_dir)
            _save_sync_manifest(scope_manifest_path, scope_signature)
            self._record(
                "workspace_bm25_index_rebuilt",
                {
                    "workspace_root": self.config.workspace_root,
                    "index_dir": self.config.index_dir,
                    "document_count": len(index.documents),
                },
            )
        qdrant_tool = QdrantHybridSearchTool(
            index,
            qdrant_config=self.config.qdrant_config,
            embedding_config=self.config.embedding_config,
            cache_path=str(index_dir / "qdrant-embeddings-cache.json"),
        )
        manifest_path = index_dir / "qdrant-sync-manifest.json"
        manifest = _load_sync_manifest(manifest_path)
        index_signature = qdrant_tool.backend.index_signature()
        cached_signature = str(manifest.get("index_signature", ""))
        collection_name = str(manifest.get("collection_name", ""))
        collection_exists = qdrant_tool.backend.collection_exists()
        point_count = qdrant_tool.backend.point_count() if collection_exists else 0
        if (
            cached_signature == index_signature
            and collection_name == self.config.qdrant_config.collection_name
            and collection_exists
            and point_count > 0
        ):
            indexed_points = len(index.documents)
            self._record(
                "workspace_index_reused",
                {
                    "workspace_root": self.config.workspace_root,
                    "index_dir": self.config.index_dir,
                    "document_count": len(index.documents),
                    "qdrant_collection": self.config.qdrant_config.collection_name,
                    "indexed_points": indexed_points,
                    "collection_point_count": point_count,
                },
            )
        else:
            if not self.config.enable_indexing:
                raise RuntimeError(
                    "Qdrant collection is not in sync while RETRIEVAL_ENABLE_INDEXING=false. "
                    "Re-enable indexing once to rebuild the collection."
                )
            indexed_points = qdrant_tool.backend.rebuild_collection(
                log_event=lambda event_type, payload: self._record(event_type, payload),
            )
            _save_sync_manifest(
                manifest_path,
                {
                    "collection_name": self.config.qdrant_config.collection_name,
                    "document_count": len(index.documents),
                    "index_signature": index_signature,
                },
            )
        self._record(
            "workspace_index_rebuilt",
            {
                "workspace_root": self.config.workspace_root,
                "index_dir": self.config.index_dir,
                "document_count": len(index.documents),
                "qdrant_collection": self.config.qdrant_config.collection_name,
                "indexed_points": indexed_points,
                "reindex_policy": self.config.reindex_policy,
            },
        )
        return index

    def _cgc_tools(self) -> dict[str, Any]:
        return {
            "cgc_index_repo": CGCIndexRepoTool(self.config),
            "cgc_find_code": CGCFindCodeTool(self.config),
            "cgc_analyze_callers": CGCAnalyzeCallersTool(self.config),
            "cgc_analyze_callees": CGCAnalyzeCalleesTool(self.config),
            "cgc_query_graph": CGCQueryGraphTool(self.config),
            "cgc_run_cli": CGCRunCliTool(self.config),
        }
    def _build_step2_repo_context(
        self,
        prompt_evidence: Any,
        cgc_find_tool: CGCFindCodeTool,
        index: Any,
    ) -> tuple[dict[str, Any], int]:
        repo_sketch = build_repo_sketch(index)
        confirmed_entities: list[str] = []
        confirmed_file_hints: list[str] = []
        anchor_examples: list[dict[str, Any]] = []
        tool_calls = 0
        for entity in prompt_evidence.grounded_entities[:4]:
            request = ToolRequest(
                tool_name="cgc_find_code",
                arguments={"query": entity, "limit": min(self.config.cgc_max_files_for_bm25, 8)},
                reason="Confirm whether a prompt-grounded entity maps to implementation files before step-2 planning.",
            )
            observation = cgc_find_tool.run(request)
            self._record_tool(request, observation, round_index=-1)
            tool_calls += 1
            implementation_files = [
                str(item.get("path", "")).strip().replace("\\", "/")
                for item in observation.payload.get("files", ())
                if isinstance(item, Mapping) and _is_step2_repo_path_allowed(str(item.get("path", "")))
            ]
            if implementation_files:
                confirmed_entities.append(entity)
                confirmed_file_hints = list(merge_paths(implementation_files[:3], confirmed_file_hints))
                anchor_examples.append({"entity": entity, "files": implementation_files[:3]})
        return (
            {
                "repo_sketch": {
                    "top_directories": repo_sketch.get("top_directories", [])[:8],
                    "file_roles": repo_sketch.get("file_roles", {}),
                    "representative_files": repo_sketch.get("representative_files", [])[:12],
                    "file_index": [
                        {
                            "path": str(entry.get("path", "")),
                            "role": str(entry.get("role", "")),
                            "identifiers": list(entry.get("identifiers", ())[:8]),
                        }
                        for entry in repo_sketch.get("file_index", [])[:12]
                    ],
                },
                "confirmed_entities": list(ordered_unique(confirmed_entities)),
                "confirmed_file_hints": list(ordered_unique(confirmed_file_hints)),
                "confirmed_anchor_examples": anchor_examples[:6],
            },
            tool_calls,
        )

    def _run_initial_narrowing(
        self,
        *,
        retrieval_plan: WorkspaceRetrievalPlan,
        cgc_find_tool: CGCFindCodeTool,
        preplan_tool_calls: int,
    ) -> tuple[tuple[str, ...] | None, tuple[ToolObservation, ...], int]:
        narrowed_files = merge_paths(retrieval_plan.confirmed_file_hints, retrieval_plan.grounded_file_hints)
        observations: list[ToolObservation] = []
        tool_call_count = 1 + preplan_tool_calls
        for entity in (retrieval_plan.confirmed_entities or retrieval_plan.grounded_entities)[:4]:
            request = ToolRequest(
                tool_name="cgc_find_code",
                arguments={"query": entity, "limit": self.config.cgc_max_files_for_bm25},
                reason="Grounded symbol or identifier from the prompt for initial structural narrowing.",
            )
            observation = cgc_find_tool.run(request)
            self._record_tool(request, observation, round_index=0)
            tool_call_count += 1
            observations.append(observation)
            if observation.status != "ok":
                return None, tuple(observations), tool_call_count
            narrowed_files = merge_paths(self._narrowed_files(observation), narrowed_files)
        return tuple(narrowed_files), tuple(observations), tool_call_count

    def _retrieve_responsibility_role_buckets(
        self,
        *,
        retrieval_plan: WorkspaceRetrievalPlan,
        subquery_roles: Sequence[str],
        qdrant_tool: QdrantHybridSearchTool,
        open_file_tool: OpenFileTool,
        cgc_tools: Mapping[str, Any],
        narrowed_files: Sequence[str],
        starting_tool_call_count: int,
        phase: str,
    ) -> tuple[tuple[RoleRetrievalBucket, ...], int, tuple[ResponsibilityExpansionIntent, ...]]:
        subqueries = [subquery for subquery in retrieval_plan.llm_subqueries if subquery.role in subquery_roles]
        prepared_buckets: list[PreparedRoleBucket] = []
        tool_call_count = starting_tool_call_count
        for subquery in subqueries:
            bucket, consumed_calls = self._prepare_role_bucket(
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
                self._record(
                    "responsibility_candidate_profiled",
                    {"role": prepared_bucket.role, "ref": candidate.source_id, "profile": profile.to_dict()},
                )

        expansion_intents = infer_expansion_intents(
            required_roles=subquery_roles,
            prompt_summary=retrieval_plan.prompt_summary,
            candidates_by_role=profile_entries,
        )
        for intent in expansion_intents:
            self._record("responsibility_expansion_inferred", intent.to_dict())

        expanded_by_role: dict[str, tuple[RetrievalCandidate, ...]] = {}
        graph_paths_by_role: dict[str, tuple[str, ...]] = {}
        for round_index in range(min(MAX_FILE_ROLE_RESOLUTION_ROUNDS, 1)):
            self._record(
                "file_role_resolution_round_started",
                {"phase": phase, "round": round_index + 1, "max_rounds": MAX_FILE_ROLE_RESOLUTION_ROUNDS},
            )
            expanded_by_role, graph_paths_by_role, expansion_calls = self._expand_responsibility_candidates(
                prepared_buckets=tuple(prepared_buckets),
                expansion_intents=expansion_intents,
                qdrant_tool=qdrant_tool,
                open_file_tool=open_file_tool,
                cgc_tools=cgc_tools,
            )
            tool_call_count += expansion_calls
            self._record(
                "file_role_resolution_round_completed",
                {
                    "phase": phase,
                    "round": round_index + 1,
                    "expanded_roles": sorted(expanded_by_role.keys()),
                    "graph_roles": sorted(graph_paths_by_role.keys()),
                },
            )
        anchor_support, support_calls = self._build_anchor_support(
            anchors=self._preliminary_responsibility_anchors(prepared_buckets),
            cgc_tools=cgc_tools,
        )
        tool_call_count += support_calls

        buckets: list[RoleRetrievalBucket] = []
        for prepared_bucket in prepared_buckets:
            merged_candidates = _merge_retrieved_candidates(
                prepared_bucket.candidates,
                expanded_by_role.get(prepared_bucket.role, ()),
            )
            buckets.append(
                self._responsibility_rerank_bucket(
                    prepared_bucket=prepared_bucket,
                    candidates=merged_candidates,
                    graph_paths=graph_paths_by_role.get(prepared_bucket.role, ()),
                    anchor_support=anchor_support,
                    cgc_tools=cgc_tools,
                )
            )
        return tuple(buckets), tool_call_count, expansion_intents

    def _preliminary_responsibility_anchors(
        self,
        prepared_buckets: Sequence[PreparedRoleBucket],
    ) -> tuple[AnchorRecord, ...]:
        anchors: list[AnchorRecord] = []
        for bucket in prepared_buckets:
            selected = 0
            for candidate in bucket.candidates:
                if not candidate.path:
                    continue
                profile = profile_candidate(
                    bucket.role,
                    path=candidate.path,
                    text=candidate.text,
                    file_role=candidate.metadata.get("file_role", ""),
                )
                if profile.noise or profile.support_only:
                    continue
                anchors.append(
                    AnchorRecord(
                        role=bucket.role,
                        path=candidate.path,
                        source_id=candidate.source_id,
                        symbol=_candidate_symbol(candidate),
                        text=candidate.text,
                    )
                )
                selected += 1
                if selected >= 1:
                    break
        return tuple(anchors)

    def _expand_responsibility_candidates(
        self,
        *,
        prepared_buckets: Sequence[PreparedRoleBucket],
        expansion_intents: Sequence[ResponsibilityExpansionIntent],
        qdrant_tool: QdrantHybridSearchTool,
        open_file_tool: OpenFileTool,
        cgc_tools: Mapping[str, Any],
    ) -> tuple[dict[str, tuple[RetrievalCandidate, ...]], dict[str, tuple[str, ...]], int]:
        expanded: dict[str, list[RetrievalCandidate]] = {}
        graph_paths: dict[str, list[str]] = {}
        tool_calls = 0
        intent_by_role: dict[str, list[ResponsibilityExpansionIntent]] = {}
        for intent in expansion_intents:
            intent_by_role.setdefault(intent.role, []).append(intent)

        for prepared_bucket in prepared_buckets:
            role = prepared_bucket.role
            expansion_queries = list(intent_by_role.get(role, ()))
            for intent in expansion_queries[:MAX_ROLE_FOLLOWUP_QUERIES]:
                request = ToolRequest(
                    tool_name="qdrant_hybrid_search",
                    arguments={
                        "query": intent.query,
                        "_coverage_area": role,
                        "limit": MAX_ROLE_INITIAL_PATHS,
                        "source_category": "source_code",
                        "file_role": "implementation",
                    },
                    reason=f"Search for the inferred responsibility owner layer for {role}.",
                )
                observation = qdrant_tool.run(request)
                self._record_tool(request, observation, round_index=0)
                tool_calls += 1
                candidates, consumed_calls = self._prepare_expanded_candidates(
                    role=role,
                    query=prepared_bucket.query,
                    helper_queries=prepared_bucket.helper_queries,
                    observation=observation,
                    qdrant_tool=qdrant_tool,
                    open_file_tool=open_file_tool,
                )
                tool_calls += consumed_calls
                expanded.setdefault(role, []).extend(candidates)

            context_candidates, context_paths, context_calls = self._expand_iterative_code_context_candidates(
                prepared_bucket=prepared_bucket,
                qdrant_tool=qdrant_tool,
                open_file_tool=open_file_tool,
            )
            tool_calls += context_calls
            if context_candidates:
                expanded.setdefault(role, []).extend(context_candidates)
            if context_paths:
                graph_paths.setdefault(role, []).extend(context_paths)

            reference_candidates, reference_paths, reference_calls = self._expand_converging_reference_candidates(
                prepared_bucket=prepared_bucket,
                prepared_buckets=prepared_buckets,
                qdrant_tool=qdrant_tool,
                open_file_tool=open_file_tool,
            )
            tool_calls += reference_calls
            if reference_candidates:
                expanded.setdefault(role, []).extend(reference_candidates)
            if reference_paths:
                graph_paths.setdefault(role, []).extend(reference_paths)

            weak_sources = [
                candidate
                for candidate in prepared_bucket.candidates
                if profile_candidate(
                    role,
                    path=candidate.path or "",
                    text=candidate.text,
                    file_role=candidate.metadata.get("file_role", ""),
                ).support_only
            ][:4]
            for source_candidate in weak_sources:
                symbol = _candidate_symbol(source_candidate)
                if not symbol:
                    continue
                request = ToolRequest(
                    tool_name="cgc_analyze_callers",
                    arguments={"symbol": symbol, "file": source_candidate.path or ""},
                    reason=f"Move upward from a support-only {role} candidate to likely owner callers.",
                )
                observation = cgc_tools["cgc_analyze_callers"].run(request)
                self._record_tool(request, observation, round_index=0)
                tool_calls += 1
                candidate_paths = _anchor_support_paths(observation)
                graph_paths.setdefault(role, []).extend(candidate_paths)
                for path in candidate_paths[:MAX_ROLE_PER_QUERY_TOP_PATHS]:
                    request = ToolRequest(
                        tool_name="qdrant_hybrid_search",
                        arguments={
                            "query": prepared_bucket.query,
                            "_coverage_area": role,
                            "limit": 1,
                            "paths": [path],
                            "source_category": "source_code",
                            "file_role": "implementation",
                        },
                        reason=f"Target the upward CGC owner candidate for {role}.",
                    )
                    observation = qdrant_tool.run(request)
                    self._record_tool(request, observation, round_index=0)
                    tool_calls += 1
                    candidates, consumed_calls = self._prepare_expanded_candidates(
                        role=role,
                        query=prepared_bucket.query,
                        helper_queries=prepared_bucket.helper_queries,
                        observation=observation,
                        qdrant_tool=qdrant_tool,
                        open_file_tool=open_file_tool,
                    )
                    tool_calls += consumed_calls
                    expanded.setdefault(role, []).extend(candidates)

        return (
            {role: tuple(_rank_unique_candidates(candidates)) for role, candidates in expanded.items()},
            {role: tuple(ordered_unique(paths)) for role, paths in graph_paths.items()},
            tool_calls,
        )

    def _expand_iterative_code_context_candidates(
        self,
        *,
        prepared_bucket: PreparedRoleBucket,
        qdrant_tool: QdrantHybridSearchTool,
        open_file_tool: OpenFileTool,
    ) -> tuple[tuple[RetrievalCandidate, ...], tuple[str, ...], int]:
        role = prepared_bucket.role
        expanded: list[RetrievalCandidate] = []
        owner_paths: list[str] = []
        tool_calls = 0
        queries = _iterative_code_context_queries(
            role=role,
            query=prepared_bucket.query,
            candidates=prepared_bucket.candidates,
        )
        if queries:
            self._record(
                "responsibility_code_context_queries_created",
                {"role": role, "queries": list(queries)},
            )
        for query in queries[:MAX_ROLE_CODE_CONTEXT_QUERIES]:
            request = ToolRequest(
                tool_name="qdrant_hybrid_search",
                arguments={
                    "query": query,
                    "_coverage_area": role,
                    "limit": MAX_ROLE_INITIAL_PATHS,
                    "source_category": "source_code",
                    "file_role": "implementation",
                },
                reason=f"Retrieve a second-pass {role} owner candidate from first-pass code terms.",
            )
            observation = qdrant_tool.run(request)
            self._record_tool(request, observation, round_index=1)
            tool_calls += 1
            candidates, consumed_calls = self._prepare_expanded_candidates(
                role=role,
                query=prepared_bucket.query,
                helper_queries=prepared_bucket.helper_queries,
                observation=observation,
                qdrant_tool=qdrant_tool,
                open_file_tool=open_file_tool,
            )
            tool_calls += consumed_calls
            expanded.extend(candidates)
            owner_paths.extend(candidate.path or "" for candidate in candidates if candidate.path and _role_owner_path_match(role, candidate.path))

        return tuple(_rank_unique_candidates(expanded)), tuple(ordered_unique(owner_paths)), tool_calls

    def _expand_converging_reference_candidates(
        self,
        *,
        prepared_bucket: PreparedRoleBucket,
        prepared_buckets: Sequence[PreparedRoleBucket],
        qdrant_tool: QdrantHybridSearchTool,
        open_file_tool: OpenFileTool,
    ) -> tuple[tuple[RetrievalCandidate, ...], tuple[str, ...], int]:
        role = prepared_bucket.role
        source_candidates = list(
            self._reference_expansion_source_candidates(
                role=role,
                prepared_bucket=prepared_bucket,
                prepared_buckets=prepared_buckets,
            )[:MAX_ROLE_REFERENCE_EXPANSION_SOURCES]
        )
        min_votes = 2 if _has_role_owner_candidate(role, prepared_bucket.candidates) else 1
        self._record(
            "responsibility_reference_source_pool",
            {
                "role": role,
                "source_paths": [candidate.path or "" for candidate in source_candidates],
                "source_refs": [candidate.source_id for candidate in source_candidates],
                "min_votes": min_votes,
            },
        )
        converged_targets, tool_calls = self._collect_converging_reference_targets(
            role=role,
            candidates=source_candidates,
            open_file_tool=open_file_tool,
            owner_terms=ordered_unique((prepared_bucket.query, *prepared_bucket.helper_queries)),
            min_votes=min_votes,
        )
        if not converged_targets:
            return (), (), tool_calls

        expanded: list[RetrievalCandidate] = []
        graph_paths: list[str] = []
        for target_path in converged_targets[:MAX_ROLE_REFERENCE_EXPANSION_TARGETS]:
            graph_paths.append(target_path)
            self._record(
                "responsibility_reference_convergence_selected",
                {"role": role, "path": target_path, "reason": "multi_source_explicit_reference_convergence"},
            )
            request = ToolRequest(
                tool_name="qdrant_hybrid_search",
                arguments={
                    "query": prepared_bucket.query,
                    "_coverage_area": role,
                    "limit": 1,
                    "paths": [target_path],
                    "source_category": "source_code",
                    "file_role": "implementation",
                },
                reason=f"Target converging explicit reference owner candidate for {role}.",
            )
            observation = qdrant_tool.run(request)
            self._record_tool(request, observation, round_index=0)
            tool_calls += 1
            candidates, consumed_calls = self._prepare_expanded_candidates(
                role=role,
                query=prepared_bucket.query,
                helper_queries=prepared_bucket.helper_queries,
                observation=observation,
                qdrant_tool=qdrant_tool,
                open_file_tool=open_file_tool,
            )
            tool_calls += consumed_calls
            if not candidates:
                direct_candidate = self._direct_owner_candidate_from_path(
                    role=role,
                    target_path=target_path,
                    query=prepared_bucket.query,
                    search_terms=prepared_bucket.helper_queries,
                )
                if direct_candidate is not None:
                    candidates = (direct_candidate,)
            expanded.extend(candidates)

        return tuple(_rank_unique_candidates(expanded)), tuple(ordered_unique(graph_paths)), tool_calls

    def _direct_owner_candidate_from_path(
        self,
        *,
        role: str,
        target_path: str,
        query: str,
        search_terms: Sequence[str] = (),
    ) -> RetrievalCandidate | None:
        normalized_path = target_path.replace("\\", "/").lstrip("/")
        if not _role_owner_path_match(role, normalized_path) and not _owner_artifact_path_match(normalized_path, search_terms):
            self._record(
                "responsibility_direct_owner_candidate_rejected",
                {"role": role, "path": normalized_path, "reason": "owner_vocab_mismatch"},
            )
            return None
        root = Path(self.config.workspace_root).resolve()
        file_path = (root / normalized_path).resolve()
        try:
            file_path.relative_to(root)
        except ValueError:
            self._record(
                "responsibility_direct_owner_candidate_rejected",
                {"role": role, "path": normalized_path, "reason": "outside_workspace_root"},
            )
            return None
        if not file_path.is_file():
            self._record(
                "responsibility_direct_owner_candidate_rejected",
                {"role": role, "path": normalized_path, "file_path": str(file_path), "reason": "file_not_found"},
            )
            return None
        text = _read_owner_text_file(file_path)
        if text is None:
            self._record(
                "responsibility_direct_owner_candidate_rejected",
                {"role": role, "path": normalized_path, "reason": "decode_failed"},
            )
            return None
        lines = text.splitlines()
        if not lines:
            self._record(
                "responsibility_direct_owner_candidate_rejected",
                {"role": role, "path": normalized_path, "reason": "empty_file"},
            )
            return None
        line_start, line_end = _best_direct_owner_span(role=role, query=query, lines=lines, search_terms=search_terms)
        snippet = "\n".join(lines[line_start - 1 : line_end])
        source_id = f"repo-pre:{normalized_path}:L{line_start}-L{line_end}"
        self._record(
            "responsibility_direct_owner_candidate_created",
            {
                "role": role,
                "path": normalized_path,
                "source_id": source_id,
                "line_start": line_start,
                "line_end": line_end,
                "reason": "expanded_owner_path_missing_from_qdrant_results",
            },
        )
        return RetrievalCandidate(
            candidate_id=source_id,
            source_category=SourceCategory.SOURCE_CODE,
            retrieval_path="direct_owner_file",
            text=snippet,
            score=6.0,
            source_id=source_id,
            path=normalized_path,
            line_range=f"L{line_start}-L{line_end}",
            metadata={
                "path": normalized_path,
                "coverage_area": role,
                "file_role": "implementation",
                "retrieval_path": "direct_owner_file",
                "commit": "workspace",
                "snapshot": "workspace_current",
                "visibility": "workspace_visible",
            },
        )

    def _span_candidate_from_accepted_file(
        self,
        *,
        role: str,
        file_candidate: RetrievalCandidate,
        query: str,
        search_terms: Sequence[str] = (),
    ) -> RetrievalCandidate | None:
        path = (file_candidate.path or file_candidate.metadata.get("path") or "").replace("\\", "/").lstrip("/")
        if not path:
            return None
        root = Path(self.config.workspace_root).resolve()
        file_path = (root / path).resolve()
        try:
            file_path.relative_to(root)
        except ValueError:
            return None
        if not file_path.is_file():
            return None
        text = _read_owner_text_file(file_path)
        if text is None:
            return None
        lines = text.splitlines()
        if not lines:
            return None
        line_start, line_end = _best_direct_owner_span(role=role, query=query, lines=lines, search_terms=search_terms)
        snippet = "\n".join(lines[line_start - 1 : line_end])
        source_id = f"repo-pre:{path}:L{line_start}-L{line_end}"
        metadata = dict(file_candidate.metadata)
        metadata.pop("file_candidate", None)
        return RetrievalCandidate(
            candidate_id=source_id,
            source_category=file_candidate.source_category,
            retrieval_path="late_accepted_file_span",
            text=snippet,
            score=max(file_candidate.score, 7.5),
            source_id=source_id,
            path=path,
            line_range=f"L{line_start}-L{line_end}",
            metadata={
                **metadata,
                "path": path,
                "coverage_area": role,
                "retrieval_path": "late_accepted_file_span",
            },
        )

    def _reference_expansion_source_candidates(
        self,
        *,
        role: str,
        prepared_bucket: PreparedRoleBucket,
        prepared_buckets: Sequence[PreparedRoleBucket],
    ) -> tuple[RetrievalCandidate, ...]:
        source_buckets = [prepared_bucket]
        raw_candidates: list[RetrievalCandidate] = []
        for bucket in source_buckets:
            raw_candidates.extend(bucket.candidates)
            for observation in bucket.observations:
                raw_candidates.extend(self._candidates_from_search_observation(observation, coverage_area=bucket.role))
        ranked = _rank_unique_candidates(raw_candidates)
        self._record(
            "responsibility_reference_raw_candidates",
            {
                "role": role,
                "candidate_paths": [candidate.path or "" for candidate in ranked[:MAX_ROLE_REFERENCE_EXPANSION_SOURCES * 3]],
                "candidate_refs": [candidate.source_id for candidate in ranked[:MAX_ROLE_REFERENCE_EXPANSION_SOURCES * 3]],
            },
        )
        eligible: list[RetrievalCandidate] = []
        for candidate in ranked:
            path = candidate.path or ""
            if not path:
                continue
            profile = profile_candidate(
                role,
                path=path,
                text=candidate.text,
                file_role=candidate.metadata.get("file_role", ""),
            )
            eligible_source = _candidate_is_reference_expansion_source(role, path, profile)
            self._record(
                "responsibility_reference_candidate_evaluated",
                {
                    "role": role,
                    "path": path,
                    "ref": candidate.source_id,
                    "classification": profile.classification,
                    "reasons": list(profile.reasons),
                    "support_only": profile.support_only,
                    "eligible_source": eligible_source,
                },
            )
            if eligible_source:
                existing = next((item for item in eligible if (item.path or "").replace("\\", "/").lower() == path.replace("\\", "/").lower()), None)
                if existing is None:
                    eligible.append(candidate)
                elif _candidate_rank_key(candidate) > _candidate_rank_key(existing):
                    eligible[eligible.index(existing)] = candidate
        return tuple(sorted(eligible, key=_candidate_rank_key, reverse=True))

    def _collect_converging_reference_targets(
        self,
        *,
        role: str,
        candidates: Sequence[RetrievalCandidate],
        open_file_tool: OpenFileTool,
        owner_terms: Sequence[str] = (),
        min_votes: int = 2,
    ) -> tuple[tuple[str, ...], int]:
        votes: dict[str, set[str]] = {}
        tool_calls = 0
        for candidate in candidates:
            path = candidate.path or ""
            if not path:
                continue
            profile = profile_candidate(
                role,
                path=path,
                text=candidate.text,
                file_role=candidate.metadata.get("file_role", ""),
            )
            if not _candidate_is_reference_expansion_source(role, path, profile):
                continue
            header_text, consumed_calls = self._load_reference_scan_text(path, open_file_tool)
            tool_calls += consumed_calls
            extracted_references = _extract_explicit_reference_paths(header_text)
            self._record(
                "responsibility_reference_extracted",
                {
                    "role": role,
                    "source_path": path,
                    "source_ref": candidate.source_id,
                    "references": list(extracted_references),
                },
            )
            for reference_path in extracted_references:
                resolved_path = _resolve_explicit_reference_path(path, reference_path)
                accepted_target = False
                if not resolved_path:
                    self._record(
                        "responsibility_reference_target_rejected",
                        {"role": role, "source_path": path, "reference_path": reference_path, "reason": "unresolved_reference"},
                    )
                    continue
                if tool_file_role(resolved_path) != "implementation":
                    self._record(
                        "responsibility_reference_target_rejected",
                        {"role": role, "source_path": path, "reference_path": reference_path, "resolved_path": resolved_path, "reason": "non_implementation_target"},
                    )
                    continue
                if not _target_matches_reference_owner_vocab(role, resolved_path, owner_terms):
                    self._record(
                        "responsibility_reference_target_rejected",
                        {"role": role, "source_path": path, "reference_path": reference_path, "resolved_path": resolved_path, "reason": "owner_vocab_mismatch"},
                    )
                    continue
                if _is_generic_reference_hub(role, resolved_path, owner_terms):
                    self._record(
                        "responsibility_reference_target_rejected",
                        {"role": role, "source_path": path, "reference_path": reference_path, "resolved_path": resolved_path, "reason": "generic_hub_blocked"},
                    )
                    continue
                votes.setdefault(resolved_path, set()).add(path)
                accepted_target = True
                self._record(
                    "responsibility_reference_target_accepted",
                    {"role": role, "source_path": path, "reference_path": reference_path, "resolved_path": resolved_path},
                )

        selected = [
            path
            for path, source_paths in sorted(votes.items(), key=lambda item: (-len(item[1]), item[0]))
            if len(source_paths) >= min_votes
        ]
        self._record(
            "responsibility_reference_votes",
            {
                "role": role,
                "votes": {path: sorted(source_paths) for path, source_paths in votes.items()},
                "selected_paths": selected,
                "min_votes": min_votes,
            },
        )
        for target_path in selected:
            self._record(
                "responsibility_reference_convergence_detected",
                {
                    "role": role,
                    "path": target_path,
                    "source_paths": sorted(votes[target_path]),
                    "reason": "multi_source_explicit_reference_convergence",
                },
            )
        return tuple(selected[:MAX_ROLE_REFERENCE_EXPANSION_TARGETS]), tool_calls

    def _load_reference_scan_text(self, path: str, open_file_tool: OpenFileTool) -> tuple[str, int]:
        request = ToolRequest(
            tool_name="open_file",
            arguments={"path": path, "line_start": 1, "line_count": MAX_ROLE_REFERENCE_SCAN_LINE_COUNT},
            reason="Inspect file header for explicit references that can reveal owner convergence.",
        )
        observation = open_file_tool.run(request)
        self._record_tool(request, observation, round_index=0)
        snippets = tuple(observation.payload.get("snippets", ())) if isinstance(observation.payload, Mapping) else ()
        parts = [str(item.get("text", "")) for item in snippets if isinstance(item, Mapping)]
        return "\n".join(parts), 1

    def _prepare_expanded_candidates(
        self,
        *,
        role: str,
        query: str,
        helper_queries: Sequence[str],
        observation: ToolObservation,
        qdrant_tool: QdrantHybridSearchTool,
        open_file_tool: OpenFileTool,
    ) -> tuple[tuple[RetrievalCandidate, ...], int]:
        candidates = _collapse_candidates_to_file_candidates(
            role=role,
            candidates=self._candidates_from_search_observation(observation, coverage_area=role),
            retrieval_path="qdrant_file_expansion",
        )
        return candidates[:MAX_ROLE_CANDIDATE_EVALUATIONS], 0

    def _responsibility_rerank_bucket(
        self,
        *,
        prepared_bucket: PreparedRoleBucket,
        candidates: Sequence[RetrievalCandidate],
        graph_paths: Sequence[str],
        anchor_support: AnchorSupport,
        cgc_tools: Mapping[str, Any],
    ) -> RoleRetrievalBucket:
        scored: list[tuple[RetrievalCandidate, RoleValidationResult, ResponsibilityScore]] = []
        for candidate in candidates:
            validation = self._validate_role_candidate(
                role=prepared_bucket.role,
                query=prepared_bucket.query,
                helper_queries=prepared_bucket.helper_queries,
                candidate=candidate,
                anchor_support=anchor_support,
                cgc_tools=cgc_tools,
                allow_cgc_queries=True,
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
            self._record(
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
            responsibility_validation = self._responsibility_validation_result(
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
                self._record(
                    "responsibility_candidate_accepted",
                    {"role": prepared_bucket.role, "ref": candidate.source_id, "score": score.to_dict()},
                )
            else:
                rejected_refs.append(candidate.source_id)
                self._record(
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

    def _responsibility_validation_result(
        self,
        *,
        candidate: RetrievalCandidate,
        accepted: bool,
        reason: str,
        validation: RoleValidationResult,
        score: ResponsibilityScore,
        graph_paths: Sequence[str],
    ) -> RoleValidationResult:
        return RoleValidationResult(
            accepted=accepted,
            reason=reason,
            local_intent_score=validation.local_intent_score,
            role_path_score=validation.role_path_score,
            dependency_support_score=validation.dependency_support_score,
            anchor_proximity_score=score.owner_score,
            call_flow_score=score.graph_score,
            total_score=score.total_score,
            threshold=0.0,
            acceptance_source=validation.acceptance_source if validation.accepted else "responsibility_rerank",
            symbol=_candidate_symbol(candidate),
            dependency_paths=validation.dependency_paths,
            call_paths=tuple(path for path in graph_paths if path == (candidate.path or "")),
            anchor_paths=tuple(graph_paths),
        )

    def _retrieve_role_buckets(
        self,
        *,
        retrieval_plan: WorkspaceRetrievalPlan,
        subquery_roles: Sequence[str],
        qdrant_tool: QdrantHybridSearchTool,
        open_file_tool: OpenFileTool,
        cgc_tools: Mapping[str, Any],
        narrowed_files: Sequence[str],
        starting_tool_call_count: int,
        phase: str,
    ) -> tuple[tuple[RoleRetrievalBucket, ...], int]:
        subqueries = [subquery for subquery in retrieval_plan.llm_subqueries if subquery.role in subquery_roles]
        prepared_buckets: list[PreparedRoleBucket] = []
        tool_call_count = starting_tool_call_count
        for subquery in subqueries:
            bucket, consumed_calls = self._prepare_role_bucket(
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
            self._evaluate_prepared_role_bucket(
                prepared_bucket,
                anchor_support=initial_support,
                max_accept_count=1,
                cgc_tools=cgc_tools,
            )
            for prepared_bucket in prepared_buckets
        )
        anchor_records = self._accepted_anchor_records(seeded_buckets)
        anchor_support, support_tool_calls = self._build_anchor_support(anchors=anchor_records, cgc_tools=cgc_tools)
        tool_call_count += support_tool_calls
        final_buckets = tuple(
            self._evaluate_prepared_role_bucket(
                prepared_bucket,
                anchor_support=anchor_support,
                max_accept_count=MAX_ROLE_BUCKET_CANDIDATES,
                cgc_tools=cgc_tools,
            )
            for prepared_bucket in prepared_buckets
        )
        return final_buckets, tool_call_count

    def _complete_role_buckets(
        self,
        *,
        retrieval_plan: WorkspaceRetrievalPlan,
        buckets: Sequence[RoleRetrievalBucket],
    ) -> tuple[RoleRetrievalBucket, ...]:
        accepted_anchors = self._accepted_anchor_records(buckets)
        accepted_by_role: dict[str, tuple[AnchorRecord, ...]] = {}
        for role in retrieval_plan.required_roles:
            accepted_by_role[role] = tuple(anchor for anchor in accepted_anchors if anchor.role == role)
        completed: list[RoleRetrievalBucket] = []
        for bucket in buckets:
            if bucket.role not in retrieval_plan.required_roles:
                completed.append(bucket)
                continue
            completed.append(
                self._complete_role_bucket(
                    retrieval_plan=retrieval_plan,
                    target_bucket=bucket,
                    all_buckets=buckets,
                    accepted_anchors=accepted_anchors,
                accepted_by_role=accepted_by_role,
            )
        )
        return tuple(completed)

    def _refine_selected_role_buckets(
        self,
        *,
        buckets: Sequence[RoleRetrievalBucket],
        rescue_roles: Sequence[str],
        qdrant_tool: QdrantHybridSearchTool,
        open_file_tool: OpenFileTool,
        cgc_tools: Mapping[str, Any],
        starting_tool_call_count: int,
    ) -> tuple[tuple[RoleRetrievalBucket, ...], int]:
        if not buckets:
            return (), starting_tool_call_count
        anchors = self._accepted_anchor_records(buckets)
        anchor_support, tool_call_count = self._build_anchor_support(anchors=anchors, cgc_tools=cgc_tools)
        total_tool_calls = starting_tool_call_count + tool_call_count
        refined_buckets: list[RoleRetrievalBucket] = []
        for bucket in buckets:
            if bucket.role not in rescue_roles:
                refined_buckets.append(bucket)
                continue
            updated_bucket, bucket_tool_calls = self._refine_selected_role_bucket(
                bucket=bucket,
                anchor_support=anchor_support,
                qdrant_tool=qdrant_tool,
                open_file_tool=open_file_tool,
                cgc_tools=cgc_tools,
            )
            refined_buckets.append(updated_bucket)
            total_tool_calls += bucket_tool_calls
        return tuple(refined_buckets), total_tool_calls

    def _apply_protocol_relationship_bridge(
        self,
        buckets: Sequence[RoleRetrievalBucket],
        *,
        retrieval_plan: WorkspaceRetrievalPlan | None = None,
    ) -> tuple[RoleRetrievalBucket, ...]:
        result = discover_protocol_relationship_candidates(
            workspace_root=self.config.workspace_root,
            buckets=buckets,
            max_candidates=MAX_ROLE_BUCKET_CANDIDATES,
            seed_texts=_protocol_relationship_seed_texts(retrieval_plan),
        )
        if not result.promotions:
            if result.routes or result.message_terms:
                self._record(
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
            updated[promotion.target_bucket_index] = self._bucket_with_route_bridge_candidates(target_bucket, promotion.candidates)
            promoted_refs.extend(candidate.source_id for candidate in promotion.candidates)
            promotion_sources.append(promotion.source)
        self._record(
            "protocol_relationship_bridge_completed",
            {
                "routes": list(result.routes),
                "message_terms": list(result.message_terms),
                "promotion_sources": promotion_sources,
                "promoted_refs": promoted_refs,
            },
        )
        return tuple(updated)

    def _bucket_with_route_bridge_candidates(
        self,
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

    def _owner_focus_roles(
        self,
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

    def _focused_owner_grounded(
        self,
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

    def _apply_synthesis_feedback(
        self,
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
                span_candidate = self._span_candidate_from_accepted_file(
                    role=bucket.role,
                    file_candidate=candidate,
                    query=bucket.query,
                    search_terms=ordered_unique((bucket.query, *bucket.helper_queries)),
                )
                if span_candidate is not None:
                    accepted_file_spans.append(span_candidate)
            reranked = sorted(
                tuple(bucket.accepted_candidates) + tuple(accepted_file_spans),
                key=lambda candidate: self._final_role_candidate_score(
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
                    self._record(
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
                self._record(
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

    def _recover_weak_role_buckets(
        self,
        *,
        retrieval_plan: WorkspaceRetrievalPlan,
        buckets: Sequence[RoleRetrievalBucket],
        synthesis_decision: RetrievalSynthesisDecision,
        qdrant_tool: QdrantHybridSearchTool,
        open_file_tool: OpenFileTool,
        cgc_tools: Mapping[str, Any],
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
        anchors = self._accepted_anchor_records(strong_required_buckets)
        anchor_support, support_tool_calls = self._build_anchor_support(anchors=anchors, cgc_tools=cgc_tools) if anchors else (
            AnchorSupport(accepted_anchors={}, dependency_paths_by_anchor={}, call_paths_by_anchor={}),
            0,
        )
        total_tool_calls += support_tool_calls
        changed = False

        for index, bucket in enumerate(recovered_buckets):
            if bucket.role not in weak_roles:
                continue
            updated_bucket, bucket_tool_calls, bucket_changed = self._recover_weak_role_bucket(
                bucket=bucket,
                follow_up_queries=tuple(follow_up_by_role.get(bucket.role, ())),
                qdrant_tool=qdrant_tool,
                open_file_tool=open_file_tool,
                cgc_tools=cgc_tools,
                anchor_support=anchor_support,
                narrowed_files=narrowed_files,
                all_buckets=tuple(recovered_buckets),
            )
            recovered_buckets[index] = updated_bucket
            total_tool_calls += bucket_tool_calls
            changed = changed or bucket_changed

        if not changed:
            return tuple(recovered_buckets), total_tool_calls, synthesis_decision

        new_decision = self._synthesize_or_accept_deterministic(retrieval_plan, tuple(recovered_buckets))
        updated_buckets = self._apply_synthesis_feedback(
            buckets=tuple(recovered_buckets),
            decision=new_decision,
            required_roles=retrieval_plan.required_roles,
        )
        return updated_buckets, total_tool_calls, new_decision

    def _recover_weak_role_bucket(
        self,
        *,
        bucket: RoleRetrievalBucket,
        follow_up_queries: Sequence[str],
        qdrant_tool: QdrantHybridSearchTool,
        open_file_tool: OpenFileTool,
        cgc_tools: Mapping[str, Any],
        anchor_support: AnchorSupport,
        narrowed_files: Sequence[str],
        all_buckets: Sequence[RoleRetrievalBucket],
        ) -> tuple[RoleRetrievalBucket, int, bool]:
        return self._run_role_followup_pipeline(
            bucket=bucket,
            mode="late_recovery",
            qdrant_tool=qdrant_tool,
            open_file_tool=open_file_tool,
            cgc_tools=cgc_tools,
            anchor_support=anchor_support,
            search_specs=self._build_late_recovery_followup_specs(
                bucket=bucket,
                follow_up_queries=follow_up_queries,
                narrowed_files=narrowed_files,
                all_buckets=all_buckets,
            ),
        )

    def _build_snippet_followup_specs(
        self,
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

    def _build_late_recovery_followup_specs(
        self,
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

    def _run_role_followup_pipeline(
        self,
        *,
        bucket: RoleRetrievalBucket,
        mode: str,
        qdrant_tool: QdrantHybridSearchTool,
        open_file_tool: OpenFileTool,
        cgc_tools: Mapping[str, Any],
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
        self._record(
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
            self._record_tool(request, observation, round_index=0)
            tool_calls += 1
            self._record(
                "role_followup_candidates_retrieved",
                {"role": bucket.role, "mode": mode, "query": query, "origin_ref": origin_ref, "refs": list(observation.source_refs)},
            )
            for candidate in self._candidates_from_search_observation(observation, coverage_area=bucket.role):
                enriched_candidate, open_observation = self._open_candidate_context(candidate, open_file_tool)
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
                    validation = self._validate_role_candidate(
                        role=bucket.role,
                        query=bucket.query,
                        helper_queries=bucket.helper_queries,
                        candidate=enriched_candidate,
                        anchor_support=anchor_support,
                        cgc_tools=cgc_tools,
                        allow_cgc_queries=False,
                    )
                    initial_evaluations.append(
                        RoleCandidateEvaluation(
                            candidate=enriched_candidate,
                            validation=validation,
                            stage=f"role_followup_{mode}_initial",
                            source_role=bucket.role,
                        )
                    )
                    self._record(
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
                workspace_root=self.config.workspace_root,
                llm_config=self.config.llm_config,
                record=self._record,
                record_tool=lambda request, observation: self._record_tool(request, observation, round_index=0),
                open_candidate_context=self._open_candidate_context,
            )
            tool_calls += len(refinement_observations)
            for refined_candidate in refined_candidates:
                validation = self._validate_role_candidate(
                    role=bucket.role,
                    query=bucket.query,
                    helper_queries=bucket.helper_queries,
                    candidate=refined_candidate,
                    anchor_support=anchor_support,
                    cgc_tools=cgc_tools,
                    allow_cgc_queries=False,
                )
                initial_evaluations.append(
                    RoleCandidateEvaluation(
                        candidate=refined_candidate,
                        validation=validation,
                        stage=f"role_followup_{mode}_initial",
                        source_role=bucket.role,
                    )
                )
                self._record(
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
            self._record("role_followup_completed", {"role": bucket.role, "mode": mode, "changed": False, "selected_refs": list(bucket.satisfying_refs)})
            return bucket, tool_calls, False

        shortlist = sorted(
            followup_candidates,
            key=lambda item: self._final_role_candidate_score(
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
            verified_validation = self._validate_role_candidate(
                role=bucket.role,
                query=bucket.query,
                helper_queries=bucket.helper_queries,
                candidate=candidate,
                anchor_support=anchor_support,
                cgc_tools=cgc_tools,
                allow_cgc_queries=True,
            )
            verified_evaluations.append(
                RoleCandidateEvaluation(
                    candidate=candidate,
                    validation=verified_validation,
                    stage=f"role_followup_{mode}",
                    source_role=bucket.role,
                )
            )
            self._record(
                "role_followup_candidate_verified",
                {"role": bucket.role, "mode": mode, "ref": candidate.source_id, "validation": verified_validation.to_dict()},
            )
            if verified_validation.accepted:
                verified_candidates.append(candidate)
        if not verified_candidates:
            self._record("role_followup_completed", {"role": bucket.role, "mode": mode, "changed": False, "selected_refs": list(bucket.satisfying_refs)})
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
                key=lambda candidate: self._final_role_candidate_score(
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
        self._record(
            "role_followup_completed",
            {"role": bucket.role, "mode": mode, "changed": changed, "selected_refs": [candidate.source_id for candidate in reranked]},
        )
        return updated_bucket, tool_calls, changed

    def _final_role_candidate_score(
        self,
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

    def _complete_role_bucket(
        self,
        *,
        retrieval_plan: WorkspaceRetrievalPlan,
        target_bucket: RoleRetrievalBucket,
        all_buckets: Sequence[RoleRetrievalBucket],
        accepted_anchors: Sequence[AnchorRecord],
        accepted_by_role: Mapping[str, tuple[AnchorRecord, ...]],
    ) -> RoleRetrievalBucket:
        self._record(
            "role_completion_started",
            {
                "role": target_bucket.role,
                "accepted_refs": [candidate.source_id for candidate in target_bucket.accepted_candidates],
                "rejected_refs": list(target_bucket.rejected_refs),
            },
        )
        candidate_entries = self._role_completion_candidates(target_bucket=target_bucket, all_buckets=all_buckets)
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
            self._record(
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
                        self._role_completion_validation_result(
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
            self._record(
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
            self._record(
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
            self._record(
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
        self._record(
            "role_completion_completed",
            {
                "role": target_bucket.role,
                "promoted_refs": promoted_refs,
                "selected_refs": [candidate.source_id for candidate in selected_candidates],
            },
        )
        return completed_bucket

    def _refine_selected_role_bucket(
        self,
        *,
        bucket: RoleRetrievalBucket,
        anchor_support: AnchorSupport,
        qdrant_tool: QdrantHybridSearchTool,
        open_file_tool: OpenFileTool,
        cgc_tools: Mapping[str, Any],
    ) -> tuple[RoleRetrievalBucket, int]:
        if not bucket.accepted_candidates:
            return bucket, 0
        updated_bucket, tool_calls, _changed = self._run_role_followup_pipeline(
            bucket=bucket,
            mode="snippet_refinement",
            qdrant_tool=qdrant_tool,
            open_file_tool=open_file_tool,
            cgc_tools=cgc_tools,
            anchor_support=anchor_support,
            search_specs=self._build_snippet_followup_specs(bucket),
        )
        return updated_bucket, tool_calls

    def _prepare_role_bucket(
        self,
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
        self._record("role_subquery_started", {"role": role, "query": query, "phase": phase, "helper_queries": list(helper_queries)})
        observations: list[ToolObservation] = []
        raw_candidates: list[RetrievalCandidate] = []
        seeded_candidates: list[RetrievalCandidate] = []
        direct_owner_candidates: list[RetrievalCandidate] = []
        tool_calls = 0
        role_narrowed_files = _role_scoped_narrowed_files(retrieval_plan, role, narrowed_files)
        shared_arguments: dict[str, Any] = {"limit": min(self.config.cgc_max_files_for_bm25, MAX_EVIDENCE_ITEMS)}
        for query_index, helper_query in enumerate(helper_queries[:MAX_ROLE_QUERIES]):
            request = ToolRequest(
                tool_name="qdrant_hybrid_search",
                arguments={"query": helper_query, "_coverage_area": role, "source_category": "source_code", "file_role": "implementation", **shared_arguments},
                reason=f"Retrieve broad code evidence for the {role} role.",
            )
            observation = qdrant_tool.run(request)
            self._record_tool(request, observation, round_index=0)
            observations.append(observation)
            tool_calls += 1
            helper_candidates = self._candidates_from_search_observation(observation, coverage_area=role)
            raw_candidates.extend(helper_candidates)
            seeded_candidates.extend(self._select_helper_query_seed_candidates(helper_candidates))
            if role_narrowed_files and query_index < 2:
                narrowed_request = ToolRequest(
                    tool_name="qdrant_hybrid_search",
                    arguments={
                        "query": helper_query,
                        "_coverage_area": role,
                        "source_category": "source_code",
                        "file_role": "implementation",
                        "paths": list(role_narrowed_files),
                        "limit": min(self.config.cgc_max_files_for_bm25, MAX_EVIDENCE_ITEMS),
                    },
                    reason=f"Boost grounded CGC-narrowed candidates for the {role} role without excluding global results.",
                )
                narrowed_observation = qdrant_tool.run(narrowed_request)
                self._record_tool(narrowed_request, narrowed_observation, round_index=0)
                observations.append(narrowed_observation)
                tool_calls += 1
                narrowed_candidates = self._candidates_from_search_observation(narrowed_observation, coverage_area=role)
                raw_candidates.extend(narrowed_candidates)
                seeded_candidates.extend(self._select_helper_query_seed_candidates(narrowed_candidates))

        seen_candidate_paths = {candidate.path for candidate in raw_candidates if candidate.path}
        for narrowed_path in role_narrowed_files:
            normalized_path = str(narrowed_path).replace("\\", "/").lstrip("/")
            if normalized_path in seen_candidate_paths:
                continue
            search_terms = _in_file_search_terms(retrieval_plan, role, query, helper_queries)
            if not _role_owner_path_match(role, normalized_path) and not _owner_artifact_path_match(normalized_path, search_terms):
                continue
            direct_candidate = self._direct_owner_candidate_from_path(
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
            candidates=self._rank_candidates(seeded_candidates or raw_candidates),
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

        return PreparedRoleBucket(
            role=role,
            query=query,
            helper_queries=helper_queries,
            observations=tuple(observations),
            candidates=tuple(prepared_candidates),
        ), tool_calls

    def _select_helper_query_seed_candidates(self, candidates: Sequence[RetrievalCandidate]) -> tuple[RetrievalCandidate, ...]:
        ranked = self._rank_candidates(candidates)
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

    def _role_completion_candidates(
        self,
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

    def _role_completion_validation_result(
        self,
        *,
        candidate: RetrievalCandidate,
        source_state: str,
        support_paths: Sequence[str],
        score_total: float,
        threshold: float,
        reasons: Sequence[str],
    ) -> RoleValidationResult:
        acceptance_source = "role_completion_promoted"
        if source_state == "rejected":
            acceptance_source = "role_completion_recovered"
        return RoleValidationResult(
            accepted=True,
            reason="role_completion_promoted",
            local_intent_score=0.0,
            role_path_score=0.0,
            dependency_support_score=0.0,
            anchor_proximity_score=0.0,
            call_flow_score=0.0,
            total_score=score_total,
            threshold=threshold,
            acceptance_source=acceptance_source,
            symbol=_candidate_symbol(candidate),
            dependency_paths=(),
            call_paths=(),
            anchor_paths=tuple(support_paths),
        )

    def _evaluate_prepared_role_bucket(
        self,
        prepared_bucket: PreparedRoleBucket,
        *,
        anchor_support: AnchorSupport,
        max_accept_count: int,
        cgc_tools: Mapping[str, Any],
    ) -> RoleRetrievalBucket:
        evaluations: list[RoleCandidateEvaluation] = []
        accepted: list[RetrievalCandidate] = []
        rejected_refs: list[str] = []
        validation_notes: list[str] = []
        for candidate in prepared_bucket.candidates:
            validation = self._validate_role_candidate(
                role=prepared_bucket.role,
                query=prepared_bucket.query,
                helper_queries=prepared_bucket.helper_queries,
                candidate=candidate,
                anchor_support=anchor_support,
                cgc_tools=cgc_tools,
            )
            evaluations.append(RoleCandidateEvaluation(candidate=candidate, validation=validation))
            self._record(
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
                self._record(
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
                self._record(
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

    def _open_candidate_context(
        self,
        candidate: RetrievalCandidate,
        open_file_tool: OpenFileTool,
    ) -> tuple[RetrievalCandidate, ToolObservation | None]:
        if not candidate.path:
            return candidate, None
        line_start = _line_start_from_range(candidate.line_range)
        request = ToolRequest(
            tool_name="open_file",
            arguments={"path": candidate.path, "line_start": line_start, "line_count": 80},
            reason="Inspect a role-scoped candidate file before validation.",
        )
        observation = open_file_tool.run(request)
        self._record_tool(request, observation, round_index=0)
        if observation.status != "ok":
            return candidate, observation
        extra_text = "\n".join(str(item.get("text", "")) for item in observation.payload.get("snippets", ()) if isinstance(item, Mapping))
        if not extra_text.strip():
            return candidate, observation
        merged_text = f"{candidate.text}\n{extra_text}".strip()
        return (
            RetrievalCandidate(
                candidate_id=candidate.candidate_id,
                source_category=candidate.source_category,
                retrieval_path=candidate.retrieval_path,
                text=merged_text[:3000],
                score=candidate.score,
                source_id=candidate.source_id,
                path=candidate.path,
                line_range=candidate.line_range,
                metadata=dict(candidate.metadata),
            ),
            observation,
        )

    def _validate_role_candidate(
        self,
        *,
        role: str,
        query: str,
        helper_queries: Sequence[str],
        candidate: RetrievalCandidate,
        anchor_support: AnchorSupport,
        cgc_tools: Mapping[str, Any],
        allow_cgc_queries: bool = True,
    ) -> RoleValidationResult:
        path = candidate.path or ""
        if not _role_phase_path_allowed(role, path):
            return RoleValidationResult(
                accepted=False,
                reason="disallowed_path_for_role",
                local_intent_score=0.0,
                role_path_score=0.0,
                dependency_support_score=0.0,
                anchor_proximity_score=0.0,
                call_flow_score=0.0,
                total_score=0.0,
                threshold=0.0,
                acceptance_source="local_only",
                symbol=None,
                dependency_paths=(),
                call_paths=(),
                anchor_paths=(),
            )
        symbol = _candidate_symbol(candidate)
        try:
            validator = validator_for_role(role)
        except KeyError:
            return RoleValidationResult(
                accepted=False,
                reason="unsupported_role_validator",
                local_intent_score=0.0,
                role_path_score=0.0,
                dependency_support_score=0.0,
                anchor_proximity_score=0.0,
                call_flow_score=0.0,
                total_score=0.0,
                threshold=0.0,
                acceptance_source="local_only",
                symbol=symbol,
                dependency_paths=(),
                call_paths=(),
                anchor_paths=(),
            )
        compatible_anchors = anchor_support.anchors_for_roles(getattr(validator, "compatible_anchor_roles", (role,)))
        matched_dependency_anchors = self._query_anchor_candidate_support(
            role=role,
            candidate_path=path,
            candidate=candidate,
            anchors=compatible_anchors,
            cgc_tools=cgc_tools,
            allow_cgc_queries=allow_cgc_queries,
        )
        matched_call_anchors = _matched_anchor_paths(path, compatible_anchors, anchor_support.call_paths_by_anchor)
        context = RoleValidationContext(
            role=role,
            query=query,
            helper_queries=helper_queries,
            candidate_path=path,
            candidate_text=candidate.text,
            candidate_source_id=candidate.source_id,
            candidate_file_role=str(candidate.metadata.get("file_role", "")),
            dependency_paths=matched_dependency_anchors,
            call_paths=matched_call_anchors,
            anchor_support=anchor_support,
        )
        score = validator.score(context)
        if role == "diagnostics" and not _diagnostics_like_candidate(candidate):
            return RoleValidationResult(
                accepted=False,
                reason="diagnostics_role_without_diagnostic_evidence",
                local_intent_score=score.local_intent_score,
                role_path_score=score.role_path_score,
                dependency_support_score=score.dependency_support_score,
                anchor_proximity_score=score.anchor_proximity_score,
                call_flow_score=score.call_flow_score,
                total_score=score.total_score,
                threshold=score.threshold,
                acceptance_source=score.acceptance_source,
                symbol=symbol,
                dependency_paths=tuple(matched_dependency_anchors),
                call_paths=tuple(matched_call_anchors),
                anchor_paths=tuple(ordered_unique(matched_dependency_anchors + matched_call_anchors)),
            )
        accepted = score.total_score >= score.threshold
        return RoleValidationResult(
            accepted=accepted,
            reason="validated_role_candidate" if accepted else "insufficient_role_support",
            local_intent_score=score.local_intent_score,
            role_path_score=score.role_path_score,
            dependency_support_score=score.dependency_support_score,
            anchor_proximity_score=score.anchor_proximity_score,
            call_flow_score=score.call_flow_score,
            total_score=score.total_score,
            threshold=score.threshold,
            acceptance_source=score.acceptance_source,
            symbol=symbol,
            dependency_paths=tuple(matched_dependency_anchors),
            call_paths=tuple(matched_call_anchors),
            anchor_paths=tuple(ordered_unique(matched_dependency_anchors + matched_call_anchors)),
        )

    def _query_anchor_candidate_support(
        self,
        *,
        role: str,
        candidate_path: str,
        candidate: RetrievalCandidate,
        anchors: Sequence[AnchorRecord],
        cgc_tools: Mapping[str, Any],
        allow_cgc_queries: bool = True,
    ) -> tuple[str, ...]:
        if role != "representation" or not candidate_path or not allow_cgc_queries:
            return ()
        candidate_relative = _cypher_relative_path(candidate_path)
        supporting_anchor_paths: list[str] = []
        for anchor in anchors:
            if not anchor.path or anchor.path == candidate_path:
                continue
            query = _anchor_symbol_relation_query(anchor.path, candidate_relative)
            request = ToolRequest(
                tool_name="cgc_query_graph",
                arguments={"query": query},
                reason=f"Confirm whether accepted {anchor.role} anchors reference symbols declared in the {role} candidate.",
            )
            observation = cgc_tools["cgc_query_graph"].run(request)
            self._record_tool(request, observation, round_index=0)
            if observation.status != "ok":
                continue
            rows = observation.payload.get("rows", ())
            if not isinstance(rows, Sequence):
                continue
            symbols = [
                str(item.get("shared_symbol", "")).strip()
                for item in rows
                if isinstance(item, Mapping) and _is_structural_symbol_name(str(item.get("shared_symbol", "")).strip())
            ]
            if symbols:
                supporting_anchor_paths.append(anchor.path)
                self._record(
                    "anchor_query_confirmed",
                    {
                        "source_role": anchor.role,
                        "anchor_path": anchor.path,
                        "candidate_path": candidate_path,
                        "shared_symbols": list(ordered_unique(symbols)),
                    },
                )
        return tuple(ordered_unique(supporting_anchor_paths))

    def _accepted_anchor_records(self, buckets: Sequence[RoleRetrievalBucket]) -> tuple[AnchorRecord, ...]:
        anchors: list[AnchorRecord] = []
        for bucket in buckets:
            for candidate in bucket.accepted_candidates:
                if not candidate.path:
                    continue
                anchors.append(
                    AnchorRecord(
                        role=bucket.role,
                        path=candidate.path,
                        source_id=candidate.source_id,
                        symbol=_candidate_symbol(candidate),
                        text=candidate.text,
                    )
                )
        return tuple(anchors)

    def _build_anchor_support(
        self,
        *,
        anchors: Sequence[AnchorRecord],
        cgc_tools: Mapping[str, Any],
    ) -> tuple[AnchorSupport, int]:
        accepted_anchors: dict[str, list[AnchorRecord]] = {}
        dependency_paths_by_anchor: dict[str, tuple[str, ...]] = {}
        call_paths_by_anchor: dict[str, tuple[str, ...]] = {}
        tool_calls = 0
        for anchor in anchors:
            accepted_anchors.setdefault(anchor.role, []).append(anchor)
            dependency_paths_by_anchor[anchor.path] = ()
            call_paths: tuple[str, ...] = ()
            if anchor.symbol:
                collected_call_paths: list[str] = []
                for tool_name in ("cgc_analyze_callers", "cgc_analyze_callees"):
                    request = ToolRequest(
                        tool_name=tool_name,
                        arguments={"symbol": anchor.symbol, "file": anchor.path},
                        reason=f"Expand role support around the accepted {anchor.role} anchor.",
                    )
                    observation = cgc_tools[tool_name].run(request)
                    self._record_tool(request, observation, round_index=0)
                    tool_calls += 1
                    collected_call_paths.extend(_anchor_support_paths(observation))
                call_paths = tuple(ordered_unique(collected_call_paths))
            call_paths_by_anchor[anchor.path] = call_paths
            self._record(
                "anchor_support_resolved",
                {
                    "source_role": anchor.role,
                    "anchor_ref": anchor.source_id,
                    "anchor_path": anchor.path,
                    "dependency_paths": [],
                    "call_paths": list(call_paths),
                },
            )
        return (
            AnchorSupport(
                accepted_anchors={role: tuple(values) for role, values in accepted_anchors.items()},
                dependency_paths_by_anchor=dependency_paths_by_anchor,
                call_paths_by_anchor=call_paths_by_anchor,
            ),
            tool_calls,
        )

    def _synthesize_role_buckets(
        self,
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
        snippets = _planning_snippets(self._rank_candidates(accepted_candidates))
        response = assess_role_buckets_with_llm(
            intent=retrieval_plan,
            role_buckets=[bucket.to_dict() for bucket in synthesis_buckets],
            current_snippets=snippets,
            missing_roles=missing_roles,
            llm_config=self.config.llm_config,
            log_event=lambda event_type, payload: self._record(event_type, {"conversation_id": retrieval_plan.conversation_id, **payload}),
            log_warning=lambda payload: self._record("llm_request_warning", {"conversation_id": retrieval_plan.conversation_id, **payload}),
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
        self._record("retrieval_refinement_evaluated", decision.to_dict())
        return decision

    def _synthesize_or_accept_deterministic(
        self,
        retrieval_plan: WorkspaceRetrievalPlan,
        buckets: Sequence[RoleRetrievalBucket],
    ) -> RetrievalSynthesisDecision:
        decision = self._deterministic_synthesis_decision(retrieval_plan, buckets)
        if decision is not None:
            self._record("retrieval_refinement_evaluated", decision.to_dict())
            self._record(
                "late_assessor_skipped",
                {
                    "reason": "deterministic_coverage_gate_satisfied",
                    "required_roles": list(retrieval_plan.required_roles),
                    "accepted_anchor_refs": list(decision.accepted_anchor_refs),
                },
            )
            return decision
        return self._synthesize_role_buckets(retrieval_plan, buckets)

    def _deterministic_synthesis_decision(
        self,
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

    def _connected_documents(
        self,
        query: str = "",
        allowed_sources: Sequence[SourceCategory] = (),
    ) -> tuple[ConnectedSourceDocument, ...]:
        documents: list[ConnectedSourceDocument] = []
        enabled_source_keys = set(self.config.enabled_sources)
        if not enabled_source_keys or "issue_tracker" in enabled_source_keys:
            documents.extend(self.config.issue_tracker_documents)
        if not enabled_source_keys or "pull_request" in enabled_source_keys:
            documents.extend(self.config.pull_request_documents)
        if not enabled_source_keys or "notebooklm" in enabled_source_keys:
            documents.extend(self.config.notebooklm_documents)
        if query and self.config.connected_source_adapters.get("remote_mcp", True):
            for source_config in self.config.remote_mcp_connected_sources:
                if not source_config.enabled:
                    continue
                if enabled_source_keys and source_config.source_key not in enabled_source_keys:
                    continue
                adapter = RemoteMCPConnectedSourceAdapter(source_config)
                try:
                    source_documents = adapter.search(query)
                except RemoteMCPConnectedSourceError as exc:
                    self._record(
                        "remote_mcp_connected_source_failed",
                        {
                            "adapter": "remote_mcp",
                            "provider": source_config.provider,
                            "source_name": source_config.name,
                            "source_key": source_config.source_key,
                            "source_category": source_config.source_category.value,
                            "endpoint_url": source_config.endpoint_url,
                            "tool_name": source_config.query_tool_name,
                            "reason": str(exc)[:400],
                        },
                    )
                    continue
                documents.extend(source_documents)
                self._record(
                    "remote_mcp_connected_source_searched",
                    {
                        "adapter": "remote_mcp",
                        "provider": source_config.provider,
                        "source_name": source_config.name,
                        "source_key": source_config.source_key,
                        "source_category": source_config.source_category.value,
                        "endpoint_url": source_config.endpoint_url,
                        "tool_name": source_config.query_tool_name,
                        "result_count": len(source_documents),
                        "source_refs": [document.source_id for document in source_documents],
                    },
                )
        if query and self.config.connected_source_adapters.get("mcp", True):
            for source_config in self.config.mcp_connected_sources:
                if enabled_source_keys and source_config.source_key not in enabled_source_keys:
                    continue
                adapter = LocalMCPConnectedSourceAdapter(source_config)
                try:
                    source_documents = adapter.search(query)
                except MCPConnectedSourceError as exc:
                    self._record(
                        "mcp_connected_source_failed",
                        {
                            "adapter": "mcp",
                            "source_name": source_config.name,
                            "source_key": source_config.source_key,
                            "source_category": source_config.source_category.value,
                            "tool_name": source_config.query_tool_name,
                            "reason": str(exc)[:400],
                        },
                    )
                    continue
                documents.extend(source_documents)
                self._record(
                    "mcp_connected_source_searched",
                    {
                        "adapter": "mcp",
                        "source_name": source_config.name,
                        "source_key": source_config.source_key,
                        "source_category": source_config.source_category.value,
                        "tool_name": source_config.query_tool_name,
                        "result_count": len(source_documents),
                        "source_refs": [document.source_id for document in source_documents],
                    },
                )
        for note_path in self.config.local_note_paths:
            if enabled_source_keys and "local_notes" not in enabled_source_keys:
                break
            path = Path(note_path)
            if not path.exists() or not path.is_file():
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            documents.append(
                ConnectedSourceDocument(
                    source_category=SourceCategory.LOCAL_NOTES,
                    source_id=path.as_posix(),
                    title=path.name,
                    content=content,
                    metadata={"path": path.as_posix(), "source_key": "local_notes"},
                    source_key="local_notes",
                )
            )
        return tuple(documents)

    def _search_obsidian_notes(
        self,
        query: str,
        allowed_sources: Sequence[SourceCategory],
    ) -> tuple[ObsidianSearchResult, ...]:
        if self.config.enabled_sources and "local_notes" not in self.config.enabled_sources:
            return ()
        if SourceCategory.LOCAL_NOTES not in allowed_sources:
            return ()
        if not self.config.connected_source_adapters.get("local_notes", True):
            return ()
        if not self.config.obsidian_vault_path:
            return ()
        vault_path = Path(self.config.obsidian_vault_path)
        if not vault_path.exists():
            return ()
        if self.config.obsidian_db_path and not Path(self.config.obsidian_db_path).exists():
            return ()
        adapter = ObsidianHybridSearchAdapter(
            vault_path=str(vault_path),
            command=self.config.obsidian_command,
            db_path=self.config.obsidian_db_path,
            mode=self.config.obsidian_search_mode,
            timeout_seconds=self.config.obsidian_timeout_seconds,
        )
        try:
            results = ()
            for obsidian_query in _obsidian_source_queries(query):
                results = adapter.search(obsidian_query, limit=self.config.obsidian_search_limit)
                if results:
                    break
        except (ObsidianSearchError, OSError, subprocess.SubprocessError) as exc:
            self._record(
                "trusted_local_notes_search_failed",
                {
                    "adapter": "obsidian-hybrid-search",
                    "vault_path": str(vault_path),
                    "reason": str(exc)[:400],
                },
            )
            return ()
        self._record(
            "trusted_local_notes_searched",
            {
                "adapter": "obsidian-hybrid-search",
                "vault_path": str(vault_path),
                "result_count": len(results),
                "queries": list(_obsidian_source_queries(query)),
                "results": [{"path": result.path, "title": result.title, "score": result.score} for result in results],
            },
        )
        return results

    def _obsidian_result_to_connected_document(self, result: ObsidianSearchResult) -> ConnectedSourceDocument:
        return ConnectedSourceDocument(
            source_category=SourceCategory.LOCAL_NOTES,
            source_id=f"obsidian:{result.path}",
            title=result.title or result.path,
            content=result.content or result.snippet,
            metadata={
                "adapter": "obsidian-hybrid-search",
                "path": result.path,
                "vault_path": str(self.config.obsidian_vault_path or ""),
                "score": f"{result.score:.6f}",
                "source_key": "local_notes",
                **dict(result.metadata or {}),
            },
            source_key="local_notes",
        )

    def _apply_obsidian_guidance(
        self,
        retrieval_plan: WorkspaceRetrievalPlan,
        results: Sequence[ObsidianSearchResult],
        index: Any,
    ) -> tuple[WorkspaceRetrievalPlan, tuple[str, ...]]:
        if not results:
            return retrieval_plan, ()
        indexed_paths = {document.chunk.path for document in index.documents}
        workspace_root = Path(self.config.workspace_root)
        guidance_results = tuple(result for result in results if result.score >= self.config.obsidian_min_guidance_score)
        if not guidance_results:
            self._record(
                "trusted_local_notes_guidance_skipped",
                {
                    "adapter": "obsidian-hybrid-search",
                    "reason": "below_min_guidance_score",
                    "min_score": self.config.obsidian_min_guidance_score,
                    "scores": [result.score for result in results],
                },
            )
            return retrieval_plan, ()
        trusted_hints = tuple(
            path
            for path in trusted_file_hints_from_obsidian_results(guidance_results)
            if path in indexed_paths or (workspace_root / path).is_file()
        )
        if not trusted_hints:
            return retrieval_plan, ()
        source_priorities = merge_source_priorities(
            (SourceCategory.LOCAL_NOTES, SourceCategory.SOURCE_CODE),
            retrieval_plan.source_priorities,
        )
        updated_plan = replace(
            retrieval_plan,
            retrieval_terms=ordered_unique(
                [
                    *retrieval_plan.retrieval_terms,
                    *[Path(path).stem for path in trusted_hints],
                ]
            ),
            source_priorities=source_priorities,
            metadata={
                **dict(retrieval_plan.metadata),
                "trusted_local_notes": "obsidian-hybrid-search",
                "trusted_local_note_file_hints": list(trusted_hints),
            },
        )
        self._record(
            "trusted_local_notes_applied",
            {
                "adapter": "obsidian-hybrid-search",
                "file_hints": list(trusted_hints),
                "note_refs": [f"obsidian:{result.path}" for result in guidance_results],
            },
        )
        return updated_plan, trusted_hints

    def _candidates_from_search_observation(self, observation: ToolObservation, *, coverage_area: str) -> tuple[RetrievalCandidate, ...]:
        candidates: list[RetrievalCandidate] = []
        for payload in observation.payload.get("results", ()):
            if isinstance(payload, Mapping):
                candidates.append(_candidate_from_chunk_payload(payload, coverage_area=coverage_area, retrieval_path="qdrant_hybrid_search"))
        return tuple(candidates)

    def _narrowed_files(self, observation: ToolObservation) -> tuple[str, ...]:
        files = observation.payload.get("files", ())
        selected: list[str] = []
        seen: set[str] = set()
        for item in files:
            if not isinstance(item, Mapping):
                continue
            path = str(item.get("path", "")).strip().replace("\\", "/")
            if not path or path in seen:
                continue
            seen.add(path)
            selected.append(path)
            if len(selected) >= self.config.cgc_max_files_for_bm25:
                break
        return tuple(selected)

    def _rank_candidates(self, candidates: Sequence[RetrievalCandidate]) -> tuple[RetrievalCandidate, ...]:
        unique: dict[str, RetrievalCandidate] = {}
        for candidate in candidates:
            existing = unique.get(candidate.candidate_id)
            if existing is None or candidate.score > existing.score:
                unique[candidate.candidate_id] = candidate
        return tuple(sorted(unique.values(), key=_candidate_rank_key, reverse=True))

    def _select_evidence_items(
        self,
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
            candidates_by_role[bucket.role] = list(_drop_redundant_file_candidates(
                [
                    candidate
                    for candidate in bucket.accepted_candidates
                    if candidate.source_id in satisfying and candidate.source_id not in noise_refs
                ]
            ))
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

    def _append_accepted_decision_evidence(
        self,
        selected: Sequence[EvidenceItem],
        *,
        synthesis_decision: RetrievalSynthesisDecision,
        buckets: Sequence[RoleRetrievalBucket],
        source_policy: Sequence[SourceCategory],
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
                evidence = self._evidence_item_from_source_ref(ref, rank=len(expanded) + 1, role=role)
                if evidence is None or evidence.source_category not in source_policy:
                    continue
            expanded.append(evidence)
            seen_refs.add(ref)
        return expanded

    def _append_connected_source_evidence(
        self,
        selected: Sequence[EvidenceItem],
        *,
        connected_documents: Sequence[ConnectedSourceDocument],
        retrieval_plan: WorkspaceRetrievalPlan,
        source_policy: Sequence[SourceCategory],
    ) -> list[EvidenceItem]:
        expanded = list(selected)
        seen_refs = {item.source_id for item in expanded}
        priority_categories = set(retrieval_plan.source_priorities)
        for document in connected_documents:
            if len(expanded) >= MAX_EVIDENCE_ITEMS:
                break
            if document.source_id in seen_refs or document.source_category not in source_policy:
                continue
            if priority_categories and document.source_category not in priority_categories:
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
                        **dict(document.metadata),
                    },
                )
            )
            seen_refs.add(document.source_id)
        return expanded

    def _evidence_item_from_source_ref(self, ref: str, *, rank: int, role: str = "") -> EvidenceItem | None:
        match = re.match(r"^repo-pre:(?P<path>.+):L(?P<start>\d+)-L(?P<end>\d+)$", ref)
        if match is None:
            return None
        path = match.group("path").replace("\\", "/").lstrip("/")
        line_start = max(1, int(match.group("start")))
        line_end = max(line_start, int(match.group("end")))
        root = Path(self.config.workspace_root).resolve()
        file_path = (root / path).resolve()
        try:
            file_path.relative_to(root)
        except ValueError:
            return None
        text = _read_owner_text_file(file_path)
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

    def _record_tool(self, request: ToolRequest, observation: ToolObservation, *, round_index: int) -> None:
        self._record("tool_call_requested", {"round": round_index, **request.to_dict()})
        self._record("tool_observation_created", {"round": round_index, **observation.to_dict()})
        self._record(
            "tool_result_summary",
            {
                "round": round_index,
                "tool_name": request.tool_name,
                "request_reason": request.reason,
                "request_arguments": dict(request.arguments),
                "status": observation.status,
                **_tool_summary_payload(observation),
            },
        )

    def _record(self, event_type: str, payload: Mapping[str, Any]) -> None:
        if not self.config.run_dir:
            return
        run_dir = Path(self.config.run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        event = {
            "event_type": event_type,
            "conversation_id": payload.get("conversation_id", ""),
            "payload": dict(payload),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with (run_dir / "retrieval-trace.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")

    @staticmethod
    def _repo_scoped_collection_name(*, base_collection_name: str, workspace_root: Path) -> str:
        identity = WorkspaceRetrievalStage._repo_identity(workspace_root)
        slug = re.sub(r"[^a-z0-9]+", "_", identity.lower()).strip("_") or "workspace"
        digest = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:8]
        candidate = f"{base_collection_name}__{slug}__{digest}"
        return candidate[:180]

    @staticmethod
    def _repo_identity(workspace_root: Path) -> str:
        resolved = workspace_root.resolve()
        parts = resolved.parts
        if len(parts) >= 3 and parts[-2].lower() == "s":
            return parts[-3]

        git_root = WorkspaceRetrievalStage._git_root(resolved)
        if git_root is not None:
            identity = git_root.name.strip() or "repo"
            digest = hashlib.sha1(str(git_root).lower().encode("utf-8")).hexdigest()[:8]
            return f"{identity}:{digest}"

        identity = resolved.name.strip() or "workspace"
        digest = hashlib.sha1(str(resolved).lower().encode("utf-8")).hexdigest()[:8]
        return f"{identity}:{digest}"

    @staticmethod
    def _git_root(start: Path) -> Path | None:
        current = start
        while True:
            if (current / ".git").exists():
                return current
            if current.parent == current:
                return None
            current = current.parent

def _cypher_relative_path(path: str) -> str:
    return path.replace("/", "\\")


def _cypher_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _protocol_relationship_seed_texts(retrieval_plan: WorkspaceRetrievalPlan | None) -> tuple[str, ...]:
    if retrieval_plan is None:
        return ()
    values: list[str] = [
        retrieval_plan.raw_prompt,
        retrieval_plan.prompt_summary,
        *retrieval_plan.raw_prompt_evidence,
        *retrieval_plan.retrieval_terms,
        *retrieval_plan.surface_context_terms,
        *retrieval_plan.owner_artifact_terms,
        *retrieval_plan.llm_concept_terms,
        *retrieval_plan.speculative_entities,
    ]
    values.extend(subquery.query for subquery in retrieval_plan.llm_subqueries)
    values.extend(subquery.query for subquery in retrieval_plan.owner_subqueries)
    values.extend(subquery.query for subquery in retrieval_plan.support_subqueries)
    return ordered_unique(value for value in values if value and value.strip())


def _role_retarget_queries(
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


def _anchor_symbol_relation_query(anchor_path: str, candidate_path: str) -> str:
    anchor_value = _cypher_string(_cypher_relative_path(anchor_path))
    candidate_value = _cypher_string(candidate_path)
    return (
        "MATCH (fa:File)-[:CONTAINS]->(fn:Function), (fc:File)-[:CONTAINS]->(decl) "
        f"WHERE fa.relative_path = '{anchor_value}' "
        f"AND fc.relative_path = '{candidate_value}' "
        "AND fn.source IS NOT NULL "
        "AND decl.name IS NOT NULL "
        "AND fn.source CONTAINS decl.name "
        "RETURN DISTINCT decl.name AS shared_symbol, fn.name AS anchor_function, fn.line_number AS anchor_line "
        "LIMIT 25"
    )


def _is_structural_symbol_name(value: str) -> bool:
    return len(value) >= 5 and value[:1].isupper()


def _is_step2_repo_path_allowed(path: str) -> bool:
    role = tool_file_role(path)
    return role in {"implementation", "documentation"}

def _load_sync_manifest(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, Mapping) else {}


def _sync_manifest_scope_matches(manifest: Mapping[str, Any], expected_scope: Mapping[str, Any]) -> bool:
    return {key: manifest.get(key) for key in expected_scope} == dict(expected_scope)


def _save_sync_manifest(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    output = dict(payload)
    output["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(output, indent=2, sort_keys=True), encoding="utf-8")
