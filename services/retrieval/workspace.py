from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from core.models import ConversationState, EvidenceItem, PolicyResult, RetrievalResult
from core.source_policy import SourceCategory
from services.retrieval.bm25 import build_index_from_repo, load_index, save_index
from services.retrieval.config import ConnectedSourceDocument, WorkspaceRetrievalConfig
from services.retrieval.obsidian import (
    ObsidianHybridSearchAdapter,
    ObsidianSearchError,
    ObsidianSearchResult,
    trusted_file_hints_from_obsidian_results,
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
from services.retrieval.workspace_llm import assess_role_buckets_with_llm


MAX_EVIDENCE_ITEMS = 12
MAX_ROLE_BUCKET_CANDIDATES = 2
MAX_ROLE_CANDIDATE_EVALUATIONS = 4
MAX_ROLE_QUERIES = 5
MAX_ROLE_FILE_REFINE_QUERIES = 2
MAX_ROLE_PER_QUERY_TOP_PATHS = 2
MAX_ROLE_INITIAL_PATHS = 8
MAX_ROLE_COMPLETION_CANDIDATES = 12
MAX_ROLE_RETARGET_QUERIES = 4
MAX_ROLE_REFERENCE_EXPANSION_SOURCES = 8
MAX_ROLE_REFERENCE_EXPANSION_TARGETS = 3
MAX_ROLE_REFERENCE_SCAN_LINE_COUNT = 24
MAX_ROLE_CODE_CONTEXT_QUERIES = 2
MAX_ROLE_CODE_CONTEXT_TERMS = 18
DECLARATION_PATTERN = re.compile(r"\b(?:class|interface|function|enum|type|namespace|module)\s+([A-Za-z_][A-Za-z0-9_]*)\b")
TRIPLE_SLASH_REFERENCE_PATTERN = re.compile(r'///\s*<reference\s+path=["\']([^"\']+)["\']\s*/?>', re.IGNORECASE)


@dataclass(frozen=True)
class RetrievalCandidate:
    candidate_id: str
    source_category: SourceCategory
    retrieval_path: str
    text: str
    score: float
    source_id: str
    path: str | None
    line_range: str | None
    metadata: Mapping[str, str]


@dataclass(frozen=True)
class RoleValidationResult:
    accepted: bool
    reason: str
    local_intent_score: float
    role_path_score: float
    dependency_support_score: float
    anchor_proximity_score: float
    call_flow_score: float
    total_score: float
    threshold: float
    acceptance_source: str
    symbol: str | None
    dependency_paths: tuple[str, ...]
    call_paths: tuple[str, ...]
    anchor_paths: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "reason": self.reason,
            "local_intent_score": round(self.local_intent_score, 3),
            "role_path_score": round(self.role_path_score, 3),
            "dependency_support_score": round(self.dependency_support_score, 3),
            "anchor_proximity_score": round(self.anchor_proximity_score, 3),
            "call_flow_score": round(self.call_flow_score, 3),
            "total_score": round(self.total_score, 3),
            "threshold": round(self.threshold, 3),
            "acceptance_source": self.acceptance_source,
            "symbol": self.symbol or "",
            "dependency_paths": list(self.dependency_paths),
            "call_paths": list(self.call_paths),
            "anchor_paths": list(self.anchor_paths),
        }


@dataclass(frozen=True)
class RoleCandidateEvaluation:
    candidate: RetrievalCandidate
    validation: RoleValidationResult
    stage: str = "initial"
    source_role: str = ""


@dataclass(frozen=True)
class PreparedRoleBucket:
    role: str
    query: str
    helper_queries: tuple[str, ...]
    observations: tuple[ToolObservation, ...]
    candidates: tuple[RetrievalCandidate, ...]


@dataclass(frozen=True)
class DeterministicCoverageGate:
    satisfied: bool
    role_status: Mapping[str, str]
    missing_roles: tuple[str, ...]
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "satisfied": self.satisfied,
            "role_status": dict(self.role_status),
            "missing_roles": list(self.missing_roles),
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class RoleRetrievalBucket:
    role: str
    query: str
    helper_queries: tuple[str, ...]
    observations: tuple[ToolObservation, ...]
    retrieved_candidates: tuple[RetrievalCandidate, ...]
    evaluations: tuple[RoleCandidateEvaluation, ...]
    accepted_candidates: tuple[RetrievalCandidate, ...]
    rejected_refs: tuple[str, ...]
    validation_notes: tuple[str, ...]
    missing_reason: str
    role_status: str = "missing"
    satisfying_refs: tuple[str, ...] = ()
    snippet_assessment: tuple[Mapping[str, str], ...] = ()
    satisfaction_source: str = "initial"

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "query": self.query,
            "helper_queries": list(self.helper_queries),
            "role_status": self.role_status,
            "satisfaction_source": self.satisfaction_source,
            "retrieved_refs": [candidate.source_id for candidate in self.retrieved_candidates],
            "accepted_refs": [candidate.source_id for candidate in self.accepted_candidates],
            "satisfying_refs": list(self.satisfying_refs),
            "rejected_refs": list(self.rejected_refs),
            "validation_notes": list(self.validation_notes),
            "missing_reason": self.missing_reason,
            "snippet_assessment": [dict(item) for item in self.snippet_assessment],
            "evaluations": [
                {
                    "ref": evaluation.candidate.source_id,
                    "path": evaluation.candidate.path or "",
                    "stage": evaluation.stage,
                    "source_role": evaluation.source_role or self.role,
                    "validation": evaluation.validation.to_dict(),
                }
                for evaluation in self.evaluations
            ],
            "snippets": [
                {
                    "ref": candidate.source_id,
                    "path": candidate.path or "",
                    "line_range": candidate.line_range or "",
                    "file_role": candidate.metadata.get("file_role", ""),
                    "snippet_quality": _snippet_quality_for_ref(candidate.source_id, self.snippet_assessment),
                    "satisfies_role": candidate.source_id in set(self.satisfying_refs),
                    "snippet": _salient_candidate_excerpt(candidate, limit=500),
                }
                for candidate in self.accepted_candidates[:MAX_ROLE_BUCKET_CANDIDATES]
            ],
        }


@dataclass(frozen=True)
class RetrievalSynthesisDecision:
    acceptance_satisfied: bool
    missing_areas: tuple[str, ...]
    accepted_anchor_refs: tuple[str, ...]
    rejected_anchor_refs: tuple[str, ...]
    snippet_assessment: tuple[Mapping[str, str], ...]
    stop_reason: str
    follow_up_queries: tuple[Mapping[str, str], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "acceptance_satisfied": self.acceptance_satisfied,
            "missing_areas": list(self.missing_areas),
            "accepted_anchor_refs": list(self.accepted_anchor_refs),
            "rejected_anchor_refs": list(self.rejected_anchor_refs),
            "snippet_assessment": [dict(item) for item in self.snippet_assessment],
            "stop_reason": self.stop_reason,
            "follow_up_queries": [dict(item) for item in self.follow_up_queries],
        }


class WorkspaceRetrievalStage:
    """Workspace retrieval built around per-role subquery validation."""

    def __init__(self, config: WorkspaceRetrievalConfig) -> None:
        config.validate()
        self.config = config

    def retrieve(self, state: ConversationState, policy_result: PolicyResult) -> RetrievalResult:
        connected_documents = self._connected_documents()
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

        cgc_tools = self._cgc_tools()
        if self.config.enable_indexing:
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
        synthesis_decision = self._synthesize_role_buckets(retrieval_plan, required_buckets)
        required_buckets = self._apply_synthesis_feedback(
            buckets=required_buckets,
            decision=synthesis_decision,
            required_roles=retrieval_plan.required_roles,
        )
        deterministic_gate = self._deterministic_coverage_gate(retrieval_plan.required_roles, required_buckets)

        supporting_buckets: tuple[RoleRetrievalBucket, ...] = ()
        if not synthesis_decision.acceptance_satisfied and _bucket_unresolved_roles(required_buckets):
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
            synthesis_decision = self._synthesize_role_buckets(retrieval_plan, required_buckets + supporting_buckets)
            updated_buckets = self._apply_synthesis_feedback(
                buckets=required_buckets + supporting_buckets,
                decision=synthesis_decision,
                required_roles=retrieval_plan.required_roles,
            )
            required_buckets = tuple(bucket for bucket in updated_buckets if bucket.role in retrieval_plan.required_roles)
            supporting_buckets = tuple(bucket for bucket in updated_buckets if bucket.role in retrieval_plan.supporting_roles)
            deterministic_gate = self._deterministic_coverage_gate(retrieval_plan.required_roles, required_buckets)

        selected = self._select_evidence_items(required_buckets, supporting_buckets, policy_result.allowed_sources)
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
            coverage_status=self._coverage_status(selected, synthesis_decision, retrieval_plan, deterministic_gate),
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
        if index_path.exists():
            index = load_index(index_dir)
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
            )
            save_index(index, index_dir)
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

        expanded_by_role, graph_paths_by_role, expansion_calls = self._expand_responsibility_candidates(
            prepared_buckets=tuple(prepared_buckets),
            expansion_intents=expansion_intents,
            qdrant_tool=qdrant_tool,
            open_file_tool=open_file_tool,
            cgc_tools=cgc_tools,
        )
        tool_call_count += expansion_calls
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
            for intent in expansion_queries[:MAX_ROLE_RETARGET_QUERIES]:
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
        if not _role_owner_path_match(role, normalized_path):
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

    def _reference_expansion_source_candidates(
        self,
        *,
        role: str,
        prepared_bucket: PreparedRoleBucket,
        prepared_buckets: Sequence[PreparedRoleBucket],
    ) -> tuple[RetrievalCandidate, ...]:
        source_buckets = [prepared_bucket]
        if role == "validation_checking":
            source_buckets = list(prepared_buckets)
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
                if not _target_matches_reference_owner_vocab(role, resolved_path):
                    self._record(
                        "responsibility_reference_target_rejected",
                        {"role": role, "source_path": path, "reference_path": reference_path, "resolved_path": resolved_path, "reason": "owner_vocab_mismatch"},
                    )
                    continue
                if _is_generic_reference_hub(role, resolved_path):
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
        candidates: list[RetrievalCandidate] = []
        tool_calls = 0
        seen_paths: set[str] = set()
        for candidate in self._candidates_from_search_observation(observation, coverage_area=role):
            if candidate.path and candidate.path in seen_paths:
                continue
            if candidate.path:
                seen_paths.add(candidate.path)
            enriched_candidate, open_observation = self._open_candidate_context(candidate, open_file_tool)
            if open_observation is not None:
                tool_calls += 1
            refined_candidate, refinement_observations = self._refine_candidate_within_file(
                role=role,
                query=query,
                helper_queries=helper_queries,
                candidate=enriched_candidate,
                qdrant_tool=qdrant_tool,
                open_file_tool=open_file_tool,
            )
            tool_calls += len(refinement_observations)
            candidates.append(refined_candidate)
            if len(candidates) >= MAX_ROLE_CANDIDATE_EVALUATIONS:
                break
        return tuple(candidates), tool_calls

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
        reranked = sorted(scored, key=lambda item: (item[2].total_score, _candidate_rank_key(item[0])[0]), reverse=True)
        accepted_candidates: list[RetrievalCandidate] = []
        evaluations: list[RoleCandidateEvaluation] = []
        rejected_refs: list[str] = []
        validation_notes: list[str] = []
        for candidate, validation, score in reranked:
            hard_support_only = "diagnostics_catalog" in score.profile.reasons
            accepted = not score.profile.noise and not hard_support_only and (not score.profile.support_only or not owner_available)
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

        role_status = "strong" if accepted_candidates else "missing"
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
            missing_reason="" if accepted_candidates else "no_responsible_owner_candidates",
            role_status=role_status,
            satisfying_refs=tuple(candidate.source_id for candidate in accepted_candidates),
            snippet_assessment=tuple({"ref": candidate.source_id, "role": "core", "reason": "responsibility owner selected"} for candidate in accepted_candidates),
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

    def _retarget_role_buckets(
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
        retargeted: list[RoleRetrievalBucket] = []
        for bucket in buckets:
            if bucket.role not in rescue_roles:
                retargeted.append(bucket)
                continue
            updated_bucket, bucket_tool_calls = self._retarget_role_bucket(
                bucket=bucket,
                anchor_support=anchor_support,
                qdrant_tool=qdrant_tool,
                open_file_tool=open_file_tool,
                cgc_tools=cgc_tools,
            )
            retargeted.append(updated_bucket)
            total_tool_calls += bucket_tool_calls
        return tuple(retargeted), total_tool_calls

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
        updated: list[RoleRetrievalBucket] = []
        for bucket in buckets:
            reranked = sorted(
                bucket.accepted_candidates,
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
                satisfying_refs.append(candidate.source_id)
                saw_core = saw_core or quality == "core"
            role_status = "missing"
            if satisfying_refs:
                role_status = "strong" if saw_core and bucket.role not in follow_up_roles else "weak"
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
                    accepted_candidates=tuple(reranked),
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

        new_decision = self._synthesize_role_buckets(retrieval_plan, tuple(recovered_buckets))
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
        return self._run_role_rescue_pipeline(
            bucket=bucket,
            mode="late_recovery",
            qdrant_tool=qdrant_tool,
            open_file_tool=open_file_tool,
            cgc_tools=cgc_tools,
            anchor_support=anchor_support,
            search_specs=self._late_role_rescue_specs(
                bucket=bucket,
                follow_up_queries=follow_up_queries,
                narrowed_files=narrowed_files,
                all_buckets=all_buckets,
            ),
        )

    def _retarget_role_rescue_specs(
        self,
        bucket: RoleRetrievalBucket,
    ) -> tuple[Mapping[str, Any], ...]:
        specs: list[Mapping[str, Any]] = []
        for candidate in bucket.accepted_candidates:
            if not candidate.path:
                continue
            snippet_queries = _role_retarget_queries(
                bucket.role,
                query=bucket.query,
                helper_queries=bucket.helper_queries,
                candidate_path=candidate.path,
                candidate_text=candidate.text,
            )[:MAX_ROLE_RETARGET_QUERIES]
            for query in snippet_queries:
                specs.append(
                    {
                        "query": query,
                        "paths": (candidate.path,),
                        "origin_ref": candidate.source_id,
                    }
                )
        return tuple(specs)

    def _late_role_rescue_specs(
        self,
        *,
        bucket: RoleRetrievalBucket,
        follow_up_queries: Sequence[str],
        narrowed_files: Sequence[str],
        all_buckets: Sequence[RoleRetrievalBucket],
    ) -> tuple[Mapping[str, Any], ...]:
        anchor_queries = tuple(_recovery_anchor_queries(bucket.role, all_buckets))
        fallback_queries = tuple(_role_snippet_queries(bucket.role, query=bucket.query, helper_queries=bucket.helper_queries))
        specs: list[Mapping[str, Any]] = []
        seen_queries: set[tuple[str, tuple[str, ...]]] = set()

        for query in ordered_unique(list(follow_up_queries) + list(anchor_queries)):
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
            if len(specs) >= MAX_ROLE_RETARGET_QUERIES:
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
            if len(specs) >= MAX_ROLE_RETARGET_QUERIES:
                break

        return tuple(specs)

    def _run_role_rescue_pipeline(
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
        rescue_candidates: list[tuple[RetrievalCandidate, RoleValidationResult]] = []
        self._record(
            "role_rescue_started",
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
                reason=f"Rescue a stronger {bucket.role} snippet via {mode}.",
            )
            observation = qdrant_tool.run(request)
            self._record_tool(request, observation, round_index=0)
            tool_calls += 1
            self._record(
                "role_rescue_candidates_retrieved",
                {"role": bucket.role, "mode": mode, "query": query, "origin_ref": origin_ref, "refs": list(observation.source_refs)},
            )
            for candidate in self._candidates_from_search_observation(observation, coverage_area=bucket.role):
                enriched_candidate, open_observation = self._open_candidate_context(candidate, open_file_tool)
                if open_observation is not None:
                    tool_calls += 1
                refined_candidate, refinement_observations = self._refine_candidate_within_file(
                    role=bucket.role,
                    query=bucket.query,
                    helper_queries=bucket.helper_queries,
                    candidate=enriched_candidate,
                    qdrant_tool=qdrant_tool,
                    open_file_tool=open_file_tool,
                    snippet_queries=(query,) + _role_retarget_queries(
                        bucket.role,
                        query=bucket.query,
                        helper_queries=bucket.helper_queries,
                        candidate_path=enriched_candidate.path or "",
                        candidate_text=enriched_candidate.text,
                    ),
                )
                tool_calls += len(refinement_observations)
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
                        stage=f"role_rescue_{mode}_initial",
                        source_role=bucket.role,
                    )
                )
                self._record(
                    "role_rescue_candidate_scored",
                    {
                        "role": bucket.role,
                        "mode": mode,
                        "query": query,
                        "origin_ref": origin_ref,
                        "ref": refined_candidate.source_id,
                        "validation": validation.to_dict(),
                    },
                )
                if validation.accepted and refined_candidate.source_id not in existing_refs:
                    rescue_candidates.append((refined_candidate, validation))
                    existing_refs.add(refined_candidate.source_id)
        if not rescue_candidates:
            self._record("role_rescue_completed", {"role": bucket.role, "mode": mode, "changed": False, "selected_refs": list(bucket.satisfying_refs)})
            return bucket, tool_calls, False

        shortlist = sorted(
            rescue_candidates,
            key=lambda item: self._final_role_candidate_score(
                role=bucket.role,
                candidate=item[0],
                evaluation=RoleCandidateEvaluation(candidate=item[0], validation=item[1], stage=f"role_rescue_{mode}_initial", source_role=bucket.role),
                snippet_quality=_rescue_snippet_quality(
                    role=bucket.role,
                    candidate=item[0],
                    rescued_refs={candidate.source_id for candidate, _ in rescue_candidates},
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
                    stage=f"role_rescue_{mode}",
                    source_role=bucket.role,
                )
            )
            self._record(
                "role_rescue_candidate_verified",
                {"role": bucket.role, "mode": mode, "ref": candidate.source_id, "validation": verified_validation.to_dict()},
            )
            if verified_validation.accepted:
                verified_candidates.append(candidate)
        if not verified_candidates:
            self._record("role_rescue_completed", {"role": bucket.role, "mode": mode, "changed": False, "selected_refs": list(bucket.satisfying_refs)})
            return bucket, tool_calls, False

        rescued_ref_set = {candidate.source_id for candidate in verified_candidates}
        reranked = sorted(
            list(bucket.accepted_candidates) + verified_candidates,
            key=lambda candidate: self._final_role_candidate_score(
                role=bucket.role,
                candidate=candidate,
                evaluation=_latest_evaluation_for_ref(tuple(initial_evaluations + verified_evaluations), candidate.source_id),
                snippet_quality=_rescue_snippet_quality(
                    role=bucket.role,
                    candidate=candidate,
                    rescued_refs=rescued_ref_set,
                    existing_assessment=bucket.snippet_assessment,
                ),
            ),
            reverse=True,
        )[:MAX_ROLE_BUCKET_CANDIDATES]
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
            missing_reason=bucket.missing_reason,
            role_status=bucket.role_status,
            satisfying_refs=tuple(candidate.source_id for candidate in reranked),
            snippet_assessment=bucket.snippet_assessment,
            satisfaction_source=bucket.satisfaction_source if mode == "retarget" else "recovery_pending",
        )
        changed = tuple(candidate.source_id for candidate in reranked) != tuple(candidate.source_id for candidate in bucket.accepted_candidates)
        self._record(
            "role_rescue_completed",
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
        if evaluation is not None and evaluation.stage.startswith("role_rescue_"):
            score += 1.5
        if role == "input_parsing":
            if any(token in text for token in ("modifier", "keyword", "syntaxkind", "parseclass", "parseandcheckmodifiers", "parseexpected")):
                score += 2.0
            if any(token in text for token in ("parsingcontexterrors", "isdeclaration")):
                score -= 1.5
        elif role == "validation_checking":
            enforcement_terms = ("check", "cannot", "must", "instantiate", "implement", "super", "diagnostic", "semantic", "error", "extends")
            has_enforcement = any(token in text for token in enforcement_terms)
            if has_enforcement:
                score += 3.5
            if any(token in text for token in ("bind", "symbol", "export")) and not has_enforcement:
                score -= 3.0
            if path.endswith("binder.ts") and not has_enforcement:
                score -= 2.5
            if path.endswith("types.ts") and not has_enforcement:
                score -= 2.5
            if path.endswith("checker.ts") or "checker" in text:
                score += 2.0
            if "services" in path:
                score -= 2.0
        elif role == "behavior_output":
            if any(token in text for token in ("emit", "transform", "runtime", "output")):
                score += 2.0
            if "services" in path:
                score -= 2.0
        elif role == "representation":
            if any(token in text for token in ("nodeflags", "symbolflags", "classdeclaration", "methoddeclaration", "syntaxkind")):
                score += 1.5
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
            missing_reason="" if selected_candidates else target_bucket.missing_reason,
            role_status=target_bucket.role_status if selected_candidates else "missing",
            satisfying_refs=tuple(candidate.source_id for candidate in selected_candidates),
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

    def _retarget_role_bucket(
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
        updated_bucket, tool_calls, _changed = self._run_role_rescue_pipeline(
            bucket=bucket,
            mode="retarget",
            qdrant_tool=qdrant_tool,
            open_file_tool=open_file_tool,
            cgc_tools=cgc_tools,
            anchor_support=anchor_support,
            search_specs=self._retarget_role_rescue_specs(bucket),
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
            if normalized_path in seen_candidate_paths or not _role_owner_path_match(role, normalized_path):
                continue
            direct_candidate = self._direct_owner_candidate_from_path(
                role=role,
                target_path=normalized_path,
                query=query,
                search_terms=_in_file_search_terms(retrieval_plan, role, query, helper_queries),
            )
            if direct_candidate is None:
                continue
            raw_candidates.append(direct_candidate)
            seeded_candidates.append(direct_candidate)
            seen_candidate_paths.add(normalized_path)

        ranked_candidates = self._rank_candidates(seeded_candidates or raw_candidates)
        prepared_candidates: list[RetrievalCandidate] = []
        seen_paths: set[str] = set()
        for candidate in ranked_candidates[:MAX_ROLE_INITIAL_PATHS]:
            if candidate.path and candidate.path in seen_paths:
                continue
            if candidate.path:
                seen_paths.add(candidate.path)
            enriched_candidate, open_observation = self._open_candidate_context(candidate, open_file_tool)
            if open_observation is not None:
                observations.append(open_observation)
                tool_calls += 1
            refined_candidate, refinement_observations = self._refine_candidate_within_file(
                role=role,
                query=query,
                helper_queries=helper_queries,
                candidate=enriched_candidate,
                qdrant_tool=qdrant_tool,
                open_file_tool=open_file_tool,
                search_terms=_in_file_search_terms(retrieval_plan, role, query, helper_queries),
            )
            observations.extend(refinement_observations)
            tool_calls += len(refinement_observations)
            prepared_candidates.append(refined_candidate)
            if len(prepared_candidates) >= MAX_ROLE_CANDIDATE_EVALUATIONS:
                break

        return PreparedRoleBucket(
            role=role,
            query=query,
            helper_queries=helper_queries,
            observations=tuple(observations),
            candidates=tuple(prepared_candidates),
        ), tool_calls

    def _refine_candidate_within_file(
        self,
        *,
        role: str,
        query: str,
        helper_queries: Sequence[str],
        candidate: RetrievalCandidate,
        qdrant_tool: QdrantHybridSearchTool,
        open_file_tool: OpenFileTool,
        snippet_queries: Sequence[str] | None = None,
        search_terms: Sequence[str] = (),
    ) -> tuple[RetrievalCandidate, tuple[ToolObservation, ...]]:
        if not candidate.path:
            return candidate, ()
        observations: list[ToolObservation] = []
        best_candidate = candidate
        local_candidate = self._refine_candidate_with_local_file_search(
            role=role,
            query=query,
            helper_queries=helper_queries,
            candidate=candidate,
            search_terms=search_terms,
        )
        if local_candidate is not None and _candidate_rank_key(local_candidate) > _candidate_rank_key(best_candidate):
            best_candidate = local_candidate
        active_snippet_queries = snippet_queries or _role_snippet_queries(role, query=query, helper_queries=helper_queries)
        for snippet_query in active_snippet_queries[:MAX_ROLE_FILE_REFINE_QUERIES]:
            request = ToolRequest(
                tool_name="qdrant_hybrid_search",
                arguments={"query": snippet_query, "_coverage_area": role, "limit": 1, "paths": [candidate.path], "source_category": "source_code", "file_role": "implementation"},
                reason=f"Refine the best in-file snippet for the {role} role.",
            )
            observation = qdrant_tool.run(request)
            self._record_tool(request, observation, round_index=0)
            observations.append(observation)
            for payload in observation.payload.get("results", ()):
                if not isinstance(payload, Mapping):
                    continue
                refined = _candidate_from_chunk_payload(payload, coverage_area=role, retrieval_path="qdrant_hybrid_search")
                refined, open_observation = self._open_candidate_context(refined, open_file_tool)
                if open_observation is not None:
                    observations.append(open_observation)
                if _candidate_rank_key(refined) > _candidate_rank_key(best_candidate):
                    best_candidate = refined
        if best_candidate.source_id != candidate.source_id:
            self._record(
                "role_candidate_refined",
                {
                    "role": role,
                    "original_ref": candidate.source_id,
                    "refined_ref": best_candidate.source_id,
                    "path": candidate.path,
                },
            )
        return best_candidate, tuple(observations)

    def _refine_candidate_with_local_file_search(
        self,
        *,
        role: str,
        query: str,
        helper_queries: Sequence[str],
        candidate: RetrievalCandidate,
        search_terms: Sequence[str],
    ) -> RetrievalCandidate | None:
        if not candidate.path:
            return None
        root = Path(self.config.workspace_root).resolve()
        normalized_path = candidate.path.replace("\\", "/").lstrip("/")
        file_path = (root / normalized_path).resolve()
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
        line_start, line_end, score = _best_in_file_refinement_span(
            role=role,
            query=query,
            helper_queries=helper_queries,
            search_terms=search_terms,
            lines=lines,
        )
        if score <= 0:
            return None
        snippet = "\n".join(lines[line_start - 1 : line_end])
        source_id = f"repo-pre:{normalized_path}:L{line_start}-L{line_end}"
        self._record(
            "role_candidate_locally_refined",
            {
                "role": role,
                "original_ref": candidate.source_id,
                "refined_ref": source_id,
                "path": normalized_path,
                "line_start": line_start,
                "line_end": line_end,
                "score": round(score, 3),
            },
        )
        return RetrievalCandidate(
            candidate_id=source_id,
            source_category=SourceCategory.SOURCE_CODE,
            retrieval_path="local_in_file_refinement",
            text=snippet,
            score=max(candidate.score, 6.5) + min(score / 20.0, 3.0),
            source_id=source_id,
            path=normalized_path,
            line_range=f"L{line_start}-L{line_end}",
            metadata={
                **dict(candidate.metadata),
                "path": normalized_path,
                "coverage_area": role,
                "retrieval_path": "local_in_file_refinement",
            },
        )

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
        required_buckets = [bucket for bucket in buckets if bucket.role in retrieval_plan.required_roles]
        missing_roles = _bucket_missing_roles(required_buckets)
        accepted_candidates = [candidate for bucket in buckets for candidate in bucket.accepted_candidates]
        snippets = _planning_snippets(self._rank_candidates(accepted_candidates))
        response = assess_role_buckets_with_llm(
            intent=retrieval_plan,
            role_buckets=[bucket.to_dict() for bucket in buckets],
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

    def _connected_documents(self) -> tuple[ConnectedSourceDocument, ...]:
        documents: list[ConnectedSourceDocument] = []
        documents.extend(self.config.issue_tracker_documents)
        documents.extend(self.config.pull_request_documents)
        documents.extend(self.config.notebooklm_documents)
        for note_path in self.config.local_note_paths:
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
                    metadata={"path": path.as_posix()},
                )
            )
        return tuple(documents)

    def _search_obsidian_notes(
        self,
        query: str,
        allowed_sources: Sequence[SourceCategory],
    ) -> tuple[ObsidianSearchResult, ...]:
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
                **dict(result.metadata or {}),
            },
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
        trusted_hints = tuple(
            path
            for path in trusted_file_hints_from_obsidian_results(results)
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
                "note_refs": [f"obsidian:{result.path}" for result in results],
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
        candidates_by_role = {
            bucket.role: [candidate for candidate in bucket.accepted_candidates if candidate.source_id in set(bucket.satisfying_refs or tuple(candidate.source_id for candidate in bucket.accepted_candidates))]
            for bucket in buckets
        }
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

    def _deterministic_coverage_gate(
        self,
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

            satisfying = list(bucket.accepted_candidates)
            if bucket.role_status != "strong" or not satisfying:
                status_by_role[role] = "missing"
                missing_roles.append(role)
                reasons.append(f"{role}:no_strong_satisfying_candidate")
                continue

            if _role_requires_owner_layer(role) and not any(_candidate_satisfies_owner_layer(role, candidate) for candidate in satisfying):
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

    def _coverage_status(
        self,
        selected: Sequence[EvidenceItem],
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


def _coverage_area_names(plan: WorkspaceRetrievalPlan) -> tuple[str, ...]:
    values = [subquery.role for subquery in plan.llm_subqueries]
    values.extend(plan.required_roles)
    values.append("prompt")
    return ordered_unique(values)


def _extract_explicit_reference_paths(text: str) -> tuple[str, ...]:
    if not text.strip():
        return ()
    return ordered_unique(match.group(1).strip() for match in TRIPLE_SLASH_REFERENCE_PATTERN.finditer(text) if match.group(1).strip())


def _resolve_explicit_reference_path(candidate_path: str, reference_path: str) -> str | None:
    normalized_candidate = candidate_path.replace("\\", "/").strip()
    normalized_reference = reference_path.replace("\\", "/").strip()
    if not normalized_candidate or not normalized_reference:
        return None
    if ":" in normalized_reference or normalized_reference.startswith("/"):
        return None
    if not _looks_like_source_file(normalized_reference):
        return None
    base_dir = PurePosixPath(normalized_candidate).parent
    resolved = str((base_dir / PurePosixPath(normalized_reference)).as_posix())
    normalized_parts: list[str] = []
    for part in resolved.split("/"):
        if not part or part == ".":
            continue
        if part == "..":
            if not normalized_parts:
                return None
            normalized_parts.pop()
            continue
        normalized_parts.append(part)
    if not normalized_parts:
        return None
    return "/".join(normalized_parts)


def _role_keywords(role: str) -> tuple[str, ...]:
    mapping = {
        "representation": ("represent", "symbol", "node", "declaration", "flag", "type"),
        "input_parsing": ("parse", "parser", "parsing", "scanner", "syntax", "token", "modifier"),
        "validation_checking": ("check", "checker", "validation", "constraint", "instantiate", "abstract", "semantic"),
        "diagnostics": ("diagnostic", "error", "message", "report"),
        "behavior_output": ("emit", "runtime", "behavior", "output", "transform"),
        "tests": ("test", "conformance", "fourslash", "baseline", "unit"),
        "docs": ("docs", "documentation", "readme", "handbook"),
        "config": ("config", "setting", "option", "tsconfig", "compileroption"),
    }
    return mapping.get(role, ())


def _role_query_package(plan: WorkspaceRetrievalPlan, role: str, query: str) -> tuple[str, ...]:
    queries = [query.strip()]
    synthetic_helpers = {
        "representation": ("symbol flags type representation", "class method declaration types", "ast node declaration symbol"),
        "input_parsing": ("abstract keyword parser", "class method parser modifier", "class declaration parser", "method declaration parser"),
        "validation_checking": ("abstract class checker", "abstract method checker validation", "constraint enforcement checker", "semantic error checker"),
        "diagnostics": ("abstract diagnostic message", "super abstract error message", "diagnostic error reporting"),
        "behavior_output": ("abstract emit transform", "abstract runtime behavior", "compile time behavior"),
        "docs": ("abstract class documentation",),
        "config": ("abstract compiler option",),
        "tests": ("abstract class test",),
    }
    queries.extend(synthetic_helpers.get(role, ()))
    role_keywords = set(_role_keywords(role))
    for term in plan.retrieval_terms:
        lowered = term.lower()
        if any(keyword in lowered for keyword in role_keywords):
            queries.append(term)
    if role == "input_parsing" and plan.prompt_summary.strip():
        queries.append(f"{plan.prompt_summary.strip()} parser")
    for entity in (plan.confirmed_entities or plan.grounded_entities)[:2]:
        if entity.strip():
            queries.append(entity)
    return ordered_unique(value for value in queries if value and value.strip())[:MAX_ROLE_QUERIES]


def _role_snippet_queries(role: str, *, query: str, helper_queries: Sequence[str]) -> tuple[str, ...]:
    queries = [query.strip()]
    role_specific = {
        "representation": (
            "class declaration interface symbol flags",
            "ast node method declaration type representation",
        ),
        "input_parsing": (
            "parse declaration syntaxkind modifier keyword",
            "parseexpected createnode parser declaration",
        ),
        "validation_checking": (
            "check diagnostics error cannot must enforce",
            "checker semantic constraint implementation instantiate",
        ),
        "diagnostics": (
            "diagnostics error message grammarerror",
            "report error diagnostics message",
        ),
        "behavior_output": (
            "emit transform runtime output",
            "compile time behavior runtime prevent",
        ),
    }
    queries.extend(role_specific.get(role, ()))
    queries.extend(helper_queries[:2])
    return ordered_unique(value for value in queries if value and value.strip())


def _iterative_code_context_queries(
    *,
    role: str,
    query: str,
    candidates: Sequence[RetrievalCandidate],
) -> tuple[str, ...]:
    path_diverse = _path_diverse_candidates(candidates)
    terms: list[str] = []
    for candidate in path_diverse[:MAX_ROLE_CANDIDATE_EVALUATIONS]:
        if candidate.path:
            terms.append(PurePosixPath(candidate.path.replace("\\", "/")).stem)
        for reference_path in _extract_explicit_reference_paths(candidate.text):
            resolved = _resolve_explicit_reference_path(candidate.path or "", reference_path)
            if resolved:
                terms.append(PurePosixPath(resolved).stem)
        terms.extend(_code_identifier_terms(candidate.text))
    terms.extend(_role_owner_context_terms(role))
    selected_terms = ordered_unique(_clean_query_terms(terms))[:MAX_ROLE_CODE_CONTEXT_TERMS]
    if not selected_terms:
        return ()
    return (f"{query} {' '.join(selected_terms)}".strip(),)


def _code_identifier_terms(text: str) -> tuple[str, ...]:
    blocked = {
        "return",
        "function",
        "class",
        "interface",
        "module",
        "export",
        "public",
        "private",
        "static",
        "undefined",
        "string",
        "number",
        "boolean",
    }
    terms: list[str] = []
    for token in IDENTIFIER_PATTERN.findall(text):
        if len(token) < 5:
            continue
        lowered = token.lower()
        if lowered in blocked:
            continue
        if token[0].isupper() or any(char.isupper() for char in token[1:]):
            terms.append(token)
    return tuple(terms[:MAX_ROLE_CODE_CONTEXT_TERMS])


def _role_owner_context_terms(role: str) -> tuple[str, ...]:
    return {
        "validation_checking": ("checker", "semantic", "diagnostics", "enforce", "constraint", "TypeChecker"),
        "input_parsing": ("parser", "scanner", "SyntaxKind", "token", "modifier"),
        "representation": ("types", "symbols", "NodeFlags", "SymbolFlags", "Declaration"),
        "diagnostics": ("diagnosticMessages", "Diagnostics", "error", "message"),
        "behavior_output": ("emitter", "runtime", "transform", "behavior", "output"),
    }.get(role, ())


def _clean_query_terms(terms: Sequence[str]) -> tuple[str, ...]:
    cleaned: list[str] = []
    for term in terms:
        value = re.sub(r"[^A-Za-z0-9_./-]+", " ", str(term)).strip()
        if not value or len(value) < 3:
            continue
        cleaned.append(value)
    return tuple(cleaned)


def _path_diverse_candidates(candidates: Sequence[RetrievalCandidate]) -> tuple[RetrievalCandidate, ...]:
    selected_by_path: dict[str, RetrievalCandidate] = {}
    for candidate in _rank_unique_candidates(candidates):
        key = (candidate.path or candidate.source_id or candidate.candidate_id).replace("\\", "/").lower()
        existing = selected_by_path.get(key)
        if existing is None or _candidate_rank_key(candidate) > _candidate_rank_key(existing):
            selected_by_path[key] = candidate
    return tuple(sorted(selected_by_path.values(), key=_candidate_rank_key, reverse=True))


def _best_direct_owner_span(*, role: str, query: str, lines: Sequence[str], search_terms: Sequence[str] = ()) -> tuple[int, int]:
    line_start, line_end, score = _best_in_file_refinement_span(
        role=role,
        query=query,
        helper_queries=(),
        search_terms=search_terms,
        lines=lines,
    )
    if score > 0:
        return line_start, line_end
    window_size = 80
    step = 40
    preferred_line = _preferred_direct_owner_line(role=role, query=query, lines=lines)
    if preferred_line is not None:
        line_start = max(1, preferred_line - 20)
        return line_start, min(len(lines), line_start + window_size - 1)
    query_terms = set(_tokenize_for_direct_owner_query(query))
    query_terms.update(term.lower() for term in _role_owner_context_terms(role))
    query_terms.update(_direct_owner_bonus_terms(role))
    best_score = -1.0
    best_start = 1
    total = len(lines)
    for start_index in range(0, total, step):
        end_index = min(total, start_index + window_size)
        text = "\n".join(lines[start_index:end_index]).lower()
        score = float(sum(1 for term in query_terms if term and term in text))
        score += _direct_owner_window_bonus(role, text)
        if score > best_score:
            best_score = score
            best_start = start_index + 1
        if end_index >= total:
            break
    return best_start, min(total, best_start + window_size - 1)


def _best_in_file_refinement_span(
    *,
    role: str,
    query: str,
    helper_queries: Sequence[str],
    search_terms: Sequence[str],
    lines: Sequence[str],
) -> tuple[int, int, float]:
    window_size = 80
    query_text = " ".join([query, *helper_queries, *search_terms])
    terms = _in_file_refinement_terms(role=role, query_text=query_text)
    if not terms:
        return 1, min(len(lines), window_size), 0.0

    best_score = -1.0
    best_start = 1
    seen_starts: set[int] = set()
    for start in _in_file_candidate_window_starts(lines, terms=terms, window_size=window_size):
        if start in seen_starts:
            continue
        seen_starts.add(start)
        end = min(len(lines), start + window_size - 1)
        text = "\n".join(lines[start - 1 : end])
        score = _score_in_file_window(role=role, query_text=query_text, text=text, start_line=start)
        if score > best_score:
            best_score = score
            best_start = start
    return best_start, min(len(lines), best_start + window_size - 1), max(best_score, 0.0)


def _in_file_candidate_window_starts(lines: Sequence[str], *, terms: Sequence[str], window_size: int) -> tuple[int, ...]:
    starts: list[int] = []
    total = len(lines)
    step = max(20, window_size // 2)
    for index in range(0, total, step):
        starts.append(index + 1)
        if index + window_size >= total:
            break
    for index, line in enumerate(lines, start=1):
        lowered = line.lower()
        is_declaration = bool(DECLARATION_PATTERN.search(line)) or re.search(r"\bfunction\s+[A-Za-z_][A-Za-z0-9_]*\b", line)
        if is_declaration or any(term in lowered for term in terms[:18]):
            starts.append(max(1, index - 20))
    return tuple(ordered_unique(starts))


def _in_file_refinement_terms(*, role: str, query_text: str) -> tuple[str, ...]:
    terms = list(_tokenize_for_direct_owner_query(query_text))
    terms.extend(term.lower() for term in _role_owner_context_terms(role))
    terms.extend(_direct_owner_bonus_terms(role))
    terms.extend(
        {
            "validation_checking": (
                "check",
                "error",
                "diagnostics",
                "assignable",
                "implements",
                "extends",
                "base",
                "constructor",
                "construct",
                "call",
                "property",
                "method",
                "declaration",
            ),
            "input_parsing": ("parse", "modifier", "keyword", "token", "declaration", "member"),
            "representation": ("flags", "symbol", "declaration", "type", "interface", "enum", "modifier"),
            "diagnostics": ("diagnostics", "message", "error", "code"),
            "behavior_output": ("emit", "transform", "output", "runtime"),
        }.get(role, ())
    )
    return tuple(ordered_unique(term.lower() for term in terms if len(term) >= 3))


def _score_in_file_window(
    *,
    role: str,
    query_text: str,
    text: str,
    start_line: int,
) -> float:
    lowered = text.lower()
    query_lowered = query_text.lower()
    terms = _in_file_refinement_terms(role=role, query_text=query_text)
    score = 0.0
    for term in terms:
        if term in lowered:
            score += 1.0
            score += min(lowered.count(term), 4) * 0.2
    for phrase in _important_query_phrases(query_text):
        if phrase in lowered:
            score += 3.0
    score += _direct_owner_window_bonus(role, lowered)
    score += _declaration_anchor_bonus(role=role, query_text=query_lowered, text=text)
    score -= min(start_line / 10000.0, 0.6)
    return score


def _important_query_phrases(query_text: str) -> tuple[str, ...]:
    phrases: list[str] = []
    for raw_phrase in re.findall(r"`([^`]+)`|'([^']+)'|\"([^\"]+)\"", query_text):
        phrase = next((item for item in raw_phrase if item), "")
        normalized = re.sub(r"\s+", " ", phrase.strip().lower())
        if len(normalized) >= 5:
            phrases.append(normalized)
    for phrase in re.findall(r"\b(?:cannot|must|only|incorrectly|extends|implements)\s+[a-z0-9_ .-]{4,80}", query_text.lower()):
        phrases.append(re.sub(r"\s+", " ", phrase.strip()))
    return tuple(ordered_unique(phrases[:12]))


def _declaration_anchor_bonus(*, role: str, query_text: str, text: str) -> float:
    bonus = 0.0
    declarations = [match.group(0).lower() for match in re.finditer(r"\b(?:function|class|interface|enum|type)\s+[A-Za-z_][A-Za-z0-9_]*", text)]
    if not declarations:
        return bonus
    query_wants_class = any(term in query_text for term in ("class", "base", "extends", "implements", "constructor"))
    query_wants_super = "super" in query_text
    query_wants_diagnostics = any(term in query_text for term in ("diagnostic", "error", "cannot", "must"))
    for declaration in declarations:
        if role == "validation_checking" and declaration.startswith("function check"):
            bonus += 4.0
            if query_wants_class and "class" in declaration:
                bonus += 8.0
            if query_wants_super and "super" in declaration:
                bonus += 5.0
            if query_wants_diagnostics:
                bonus += 1.5
        elif role == "input_parsing" and declaration.startswith("function parse"):
            bonus += 5.0
        elif role == "representation" and any(kind in declaration for kind in ("interface", "enum", "type")):
            bonus += 4.0
        elif role == "behavior_output" and declaration.startswith("function emit"):
            bonus += 4.0
    return bonus


def _preferred_direct_owner_line(*, role: str, query: str, lines: Sequence[str]) -> int | None:
    if role != "validation_checking":
        return None
    lowered_query = query.lower()
    wants_class_layer = any(term in lowered_query for term in ("class", "inherit", "extends", "base", "implement"))
    wants_super_layer = "super" in lowered_query
    if wants_class_layer:
        for index, line in enumerate(lines, start=1):
            lowered = line.lower()
            if "classdeclaration" in lowered and any(term in lowered for term in ("basetype", "basetypes", "extends")):
                return index
        for index, line in enumerate(lines, start=1):
            lowered = line.lower()
            if "getdeclaredtypeofclass" in lowered or ("classdeclaration" in lowered and "declaration" in lowered):
                return index
    if wants_super_layer:
        for index, line in enumerate(lines, start=1):
            if "superkeyword" in line.lower():
                return index
    return None


def _read_owner_text_file(path: Path) -> str | None:
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1", "utf-16", "utf-16-le", "utf-16-be"):
        try:
            text = path.read_text(encoding=encoding)
        except UnicodeError:
            continue
        if _looks_like_bad_text_decode(text):
            continue
        return text
    return None


def _looks_like_bad_text_decode(text: str) -> bool:
    nul_count = text.count("\x00")
    return nul_count > max(1, len(text) // 200)


def _tokenize_for_direct_owner_query(query: str) -> tuple[str, ...]:
    return tuple(term for term in re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", query.lower()) if term not in {"where", "find", "search", "like", "with", "that", "this", "from"})


def _direct_owner_bonus_terms(role: str) -> set[str]:
    if role == "validation_checking":
        return {
            "classdeclaration",
            "basetype",
            "basetypes",
            "getbasetypes",
            "getdeclaredtypeofclass",
            "getpropertiesoftype",
            "getsignaturesoftype",
            "diagnostics",
            "error",
            "superkeyword",
            "construct",
            "instantiate",
        }
    if role == "input_parsing":
        return {"parse", "syntaxkind", "modifier", "keyword", "token"}
    if role == "representation":
        return {"interface", "enum", "nodeflags", "symbolflags", "declaration"}
    if role == "diagnostics":
        return {"diagnostics", "message", "error", "code"}
    if role == "behavior_output":
        return {"emit", "runtime", "transform", "output", "directive"}
    return set()


def _direct_owner_window_bonus(role: str, text: str) -> float:
    if role == "validation_checking":
        score = 0.0
        if "classdeclaration" in text and ("basetype" in text or "basetypes" in text):
            score += 6.0
        if "diagnostics." in text or "error(" in text:
            score += 3.0
        if "getdeclaredtypeofclass" in text or "getpropertiesoftype" in text:
            score += 2.0
        if "superkeyword" in text:
            score += 2.0
        return score
    return 0.0


def _role_retarget_queries(
    role: str,
    *,
    query: str,
    helper_queries: Sequence[str],
    candidate_path: str,
    candidate_text: str,
) -> tuple[str, ...]:
    queries = list(_role_snippet_queries(role, query=query, helper_queries=helper_queries))
    retarget_specific = {
        "representation": (
            "nodeflags modifier syntaxkind classdeclaration methoddeclaration",
            "symbolflags declaration interface class method",
        ),
        "input_parsing": (
            "parse declaration modifier syntaxkind keyword",
            "parseclassdeclaration parseclassmemberdeclaration parseandcheckmodifiers",
        ),
        "validation_checking": (
            "check abstract instantiate implement diagnostics",
            "cannot must enforce semantic error abstract",
        ),
        "diagnostics": (
            "diagnostics grammarerror error message abstract",
            "report error diagnostics instantiate super abstract",
        ),
        "behavior_output": (
            "emit transform output behavior abstract",
            "runtime transform compile output",
        ),
    }
    queries.extend(retarget_specific.get(role, ()))
    for token in DECLARATION_PATTERN.findall(candidate_text):
        if len(token) >= 5:
            queries.append(token)
    stem = Path(candidate_path).stem.lower() if candidate_path else ""
    if stem:
        queries.append(f"{stem} {query.strip()}".strip())
    return ordered_unique(value for value in queries if value and value.strip())


def _in_file_search_terms(
    retrieval_plan: WorkspaceRetrievalPlan,
    role: str,
    query: str,
    helper_queries: Sequence[str],
) -> tuple[str, ...]:
    role_queries = [subquery.query for subquery in retrieval_plan.llm_subqueries if subquery.role == role]
    return tuple(
        ordered_unique(
            [
                query,
                *helper_queries,
                *role_queries,
                *retrieval_plan.retrieval_terms,
                *retrieval_plan.raw_prompt_evidence,
                *retrieval_plan.grounded_entities,
                *retrieval_plan.confirmed_entities,
                retrieval_plan.prompt_summary,
            ]
        )
    )


def _role_scoped_narrowed_files(
    retrieval_plan: WorkspaceRetrievalPlan,
    role: str,
    narrowed_files: Sequence[str],
) -> tuple[str, ...]:
    metadata_hints = retrieval_plan.metadata.get("trusted_local_note_file_hints", ())
    trusted_hints = tuple(
        str(path).replace("\\", "/").lstrip("/")
        for path in metadata_hints
        if str(path).strip()
    ) if isinstance(metadata_hints, Sequence) and not isinstance(metadata_hints, (str, bytes)) else ()
    role_hints = tuple(path for path in trusted_hints if _role_owner_path_match(role, path))
    return merge_paths(role_hints, narrowed_files)


def _better_retarget_candidate(
    *,
    candidate: RetrievalCandidate,
    validation: RoleValidationResult,
    best_candidate: RetrievalCandidate,
    best_validation: RoleValidationResult,
) -> bool:
    if validation.accepted and not best_validation.accepted:
        return True
    if validation.accepted != best_validation.accepted:
        return False
    if validation.total_score > best_validation.total_score:
        return True
    if validation.total_score < best_validation.total_score:
        return False
    return _candidate_rank_key(candidate) > _candidate_rank_key(best_candidate)


def _select_diverse_completion_entries(
    entries: Sequence[tuple[RetrievalCandidate, str, str, RoleValidationResult, float]],
    *,
    limit: int,
) -> tuple[tuple[RetrievalCandidate, str, str, RoleValidationResult, float], ...]:
    remaining = list(entries)
    selected: list[tuple[RetrievalCandidate, str, str, RoleValidationResult, float]] = []
    while remaining and len(selected) < limit:
        best_index = 0
        best_effective_score: float | None = None
        for index, entry in enumerate(remaining):
            effective_score = entry[4] - _completion_redundancy_penalty(entry, selected)
            if best_effective_score is None or effective_score > best_effective_score:
                best_effective_score = effective_score
                best_index = index
        selected.append(remaining.pop(best_index))
    return tuple(selected)


def _completion_redundancy_penalty(
    entry: tuple[RetrievalCandidate, str, str, RoleValidationResult, float],
    selected: Sequence[tuple[RetrievalCandidate, str, str, RoleValidationResult, float]],
) -> float:
    candidate, source_role, _, _, _ = entry
    penalty = 0.0
    candidate_path = (candidate.path or "").replace("\\", "/").lower()
    candidate_dir = str(Path(candidate_path).parent).replace("\\", "/")
    for selected_candidate, selected_source_role, _, _, _ in selected:
        selected_path = (selected_candidate.path or "").replace("\\", "/").lower()
        if candidate_path and selected_path and candidate_path == selected_path:
            penalty += 2.5
        elif candidate_dir and candidate_dir == str(Path(selected_path).parent).replace("\\", "/"):
            penalty += 0.7
        if source_role and source_role == selected_source_role:
            penalty += 0.35
    return penalty


def _bucket_missing_roles(buckets: Sequence[RoleRetrievalBucket]) -> tuple[str, ...]:
    missing = [bucket.role for bucket in buckets if bucket.role_status == "missing"]
    return tuple(ordered_unique(missing))


def _bucket_unresolved_roles(buckets: Sequence[RoleRetrievalBucket]) -> tuple[str, ...]:
    missing = [bucket.role for bucket in buckets if bucket.role_status != "strong"]
    return tuple(ordered_unique(missing))


def _latest_evaluation_for_ref(
    evaluations: Sequence[RoleCandidateEvaluation],
    ref: str,
) -> RoleCandidateEvaluation | None:
    latest: RoleCandidateEvaluation | None = None
    for evaluation in evaluations:
        if evaluation.candidate.source_id == ref:
            latest = evaluation
    return latest


def _snippet_quality_for_ref(ref: str, assessments: Sequence[Mapping[str, str]]) -> str:
    for item in assessments:
        if str(item.get("ref", "")) == ref:
            role = str(item.get("role", "")).strip().lower()
            if role:
                return role
    return ""


def _snippet_reason_for_ref(ref: str, assessments: Sequence[Mapping[str, str]]) -> str:
    for item in assessments:
        if str(item.get("ref", "")) == ref:
            return str(item.get("reason", "")).strip()
    return ""


def _late_snippet_quality(
    *,
    ref: str,
    quality_by_ref: Mapping[str, str],
    rejected_refs: set[str],
    accepted_refs: set[str],
) -> str:
    if ref in rejected_refs:
        return "noise"
    quality = quality_by_ref.get(ref, "").strip().lower()
    if quality in {"core", "secondary", "noise"}:
        return quality
    if ref in accepted_refs:
        return "core"
    return "secondary"


def _rescue_snippet_quality(
    *,
    role: str,
    candidate: RetrievalCandidate,
    rescued_refs: set[str],
    existing_assessment: Sequence[Mapping[str, str]],
) -> str:
    if candidate.source_id not in rescued_refs:
        return _snippet_quality_for_ref(candidate.source_id, existing_assessment)
    if role == "validation_checking":
        text = candidate.text.lower()
        if any(token in text for token in ("cannot", "must", "instantiate", "implement", "super", "diagnostic", "semantic", "extends", "check")):
            return "core"
    if role == "input_parsing":
        text = candidate.text.lower()
        if any(token in text for token in ("parseclass", "parseandcheckmodifiers", "modifier", "syntaxkind", "keyword")):
            return "core"
    if role == "behavior_output":
        text = candidate.text.lower()
        if any(token in text for token in ("emit", "transform", "runtime", "output")):
            return "core"
    return "secondary"


def _merge_retrieved_candidates(
    existing: Sequence[RetrievalCandidate],
    new_candidates: Sequence[RetrievalCandidate],
) -> tuple[RetrievalCandidate, ...]:
    merged: dict[str, RetrievalCandidate] = {candidate.source_id: candidate for candidate in existing}
    for candidate in new_candidates:
        merged[candidate.source_id] = candidate
    return tuple(merged.values())


def _rank_unique_candidates(candidates: Sequence[RetrievalCandidate]) -> tuple[RetrievalCandidate, ...]:
    unique: dict[str, RetrievalCandidate] = {}
    for candidate in candidates:
        key = candidate.source_id or candidate.candidate_id
        existing = unique.get(key)
        if existing is None or _candidate_rank_key(candidate) > _candidate_rank_key(existing):
            unique[key] = candidate
    return tuple(sorted(unique.values(), key=_candidate_rank_key, reverse=True))


def _recovery_anchor_queries(role: str, buckets: Sequence[RoleRetrievalBucket]) -> tuple[str, ...]:
    queries: list[str] = []
    for bucket in buckets:
        if bucket.role == role or bucket.role_status != "strong":
            continue
        for candidate in bucket.accepted_candidates[:1]:
            tokens = DECLARATION_PATTERN.findall(candidate.text)
            if tokens:
                queries.append(f"{role} {' '.join(tokens[:2])}".strip())
            stem = Path(candidate.path or "").stem.lower() if candidate.path else ""
            if stem:
                queries.append(f"{role} {stem}".strip())
    return ordered_unique(queries)


def _role_phase_path_allowed(role: str, path: str) -> bool:
    normalized_path = path.lower().replace("\\", "/")
    file_role = tool_file_role(normalized_path)
    if file_role in {"test", "baseline_or_generated"}:
        return False
    if "harness" in normalized_path or "fixture" in normalized_path:
        return False
    if "diagnostic" in normalized_path and role != "diagnostics":
        return False
    if role == "diagnostics":
        return file_role == "implementation" and ("diagnostic" in normalized_path or normalized_path.endswith(".json"))
    return file_role == "implementation"


def _anchor_support_path_allowed(path: str) -> bool:
    normalized_path = path.lower().replace("\\", "/")
    file_role = tool_file_role(normalized_path)
    if file_role in {"test", "baseline_or_generated"}:
        return False
    if "harness" in normalized_path or "fixture" in normalized_path:
        return False
    return file_role == "implementation"


def _anchor_support_paths(observation: ToolObservation) -> tuple[str, ...]:
    files = observation.payload.get("files", ())
    selected: list[str] = []
    for item in files:
        if not isinstance(item, Mapping):
            continue
        path = str(item.get("path", "")).strip().replace("\\", "/")
        if path and _anchor_support_path_allowed(path):
            selected.append(path)
    return tuple(ordered_unique(selected))


def _matched_anchor_paths(
    candidate_path: str,
    anchors: Sequence[AnchorRecord],
    support_map: Mapping[str, Sequence[str]],
) -> tuple[str, ...]:
    normalized = candidate_path.replace("\\", "/").lower()
    supporting_paths: list[str] = []
    for anchor in anchors:
        supported = {path.replace("\\", "/").lower() for path in support_map.get(anchor.path, ())}
        if normalized in supported:
            supporting_paths.append(anchor.path)
    return tuple(ordered_unique(supporting_paths))


def _cypher_relative_path(path: str) -> str:
    return path.replace("/", "\\")


def _cypher_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


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


def _diagnostics_like_candidate(candidate: RetrievalCandidate) -> bool:
    path = (candidate.path or "").lower()
    text = candidate.text.lower()
    return "diagnostic" in path or "error" in text or "message" in text


def _candidate_symbol(candidate: RetrievalCandidate) -> str | None:
    for match in DECLARATION_PATTERN.finditer(candidate.text):
        symbol = match.group(1)
        if symbol and len(symbol) >= 4:
            return symbol
    for token in IDENTIFIER_PATTERN.findall(candidate.text):
        if token and len(token) >= 5 and token[0].isupper():
            return token
    return None


def _candidate_is_reference_expansion_source(role: str, path: str, profile: FileResponsibilityProfile) -> bool:
    normalized_path = path.replace("\\", "/").lower()
    if profile.noise:
        return False
    if profile.support_only or profile.classification == "possible_owner":
        return True
    if any(reason.startswith("adjacent_") for reason in profile.reasons):
        return True
    if role == "validation_checking" and any(token in normalized_path for token in ("/services/", "/compiler/tc.", "commandline", "project", "watch")):
        return True
    return False


def _role_requires_owner_layer(role: str) -> bool:
    return role in {"validation_checking", "input_parsing", "representation", "diagnostics", "behavior_output"}


def _candidate_satisfies_owner_layer(role: str, candidate: RetrievalCandidate) -> bool:
    path = candidate.path or ""
    if _role_owner_path_match(role, path):
        return True
    profile = profile_candidate(
        role,
        path=path,
        text=candidate.text,
        file_role=candidate.metadata.get("file_role", ""),
    )
    if profile.noise or profile.support_only:
        return False
    return profile.classification == "likely_owner" and not any(reason in profile.reasons for reason in ("plumbing_path", "helper_path", "low_level_leaf"))


def _has_role_owner_candidate(role: str, candidates: Sequence[RetrievalCandidate]) -> bool:
    return any(_candidate_satisfies_owner_layer(role, candidate) for candidate in candidates)


def _role_owner_path_match(role: str, path: str) -> bool:
    normalized_path = path.replace("\\", "/").lower()
    return any(token in normalized_path for token in _role_owner_path_tokens(role))


def _role_owner_path_tokens(role: str) -> tuple[str, ...]:
    return {
        "validation_checking": ("checker", "semantic", "validator", "validate", "typecheck", "type_check", "resolver", "rules"),
        "behavior_output": ("emitter", "runtime", "transform", "renderer", "directive"),
        "input_parsing": ("parser", "scanner"),
        "representation": ("types", "symbols", "ast", "nodes", "schema", "model"),
        "diagnostics": ("diagnostic", "diagnostics", "messages"),
    }.get(role, ())


def _target_matches_reference_owner_vocab(role: str, path: str) -> bool:
    return _role_owner_path_match(role, path)


def _is_generic_reference_hub(role: str, path: str) -> bool:
    normalized_path = path.replace("\\", "/").lower()
    if role == "validation_checking":
        blocked = ("types.ts", "core.ts", "scanner.ts", "binder.ts", "parser.ts")
        return any(normalized_path.endswith(token) for token in blocked)
    return False


def _looks_like_source_file(path: str) -> bool:
    lowered = path.lower()
    return lowered.endswith((".ts", ".tsx", ".js", ".jsx", ".py", ".c", ".cc", ".cpp", ".h", ".hpp", ".java", ".cs"))


def _line_start_from_range(line_range: str | None) -> int:
    if not line_range:
        return 1
    match = re.match(r"L(\d+)", line_range)
    if match is None:
        return 1
    return max(1, int(match.group(1)))


def _planning_snippets(candidates: Sequence[RetrievalCandidate]) -> tuple[dict[str, Any], ...]:
    snippets: list[dict[str, Any]] = []
    for candidate in list(candidates)[:MAX_EVIDENCE_ITEMS]:
        snippets.append(
            {
                "ref": candidate.source_id or (candidate.path or ""),
                "path": candidate.path or "",
                "line_range": candidate.line_range or "",
                "retrieval_path": candidate.retrieval_path,
                "file_role": candidate.metadata.get("file_role", ""),
                "score": candidate.score,
                "snippet": _salient_candidate_excerpt(candidate, limit=900),
            }
        )
    return tuple(snippets)


def _salient_candidate_excerpt(candidate: RetrievalCandidate, *, limit: int) -> str:
    text = candidate.text
    if len(text) <= limit:
        return text
    role = candidate.metadata.get("coverage_area", "")
    terms = _in_file_refinement_terms(role=role, query_text=text)
    lines = text.splitlines()
    best_index = 0
    best_score = -1.0
    for index, line in enumerate(lines):
        lowered = line.lower()
        score = 0.0
        if DECLARATION_PATTERN.search(line) or re.search(r"\bfunction\s+[A-Za-z_][A-Za-z0-9_]*\b", line):
            score += 5.0
        score += sum(1.0 for term in terms[:24] if term in lowered)
        if role == "validation_checking" and re.search(r"\bfunction\s+check", lowered):
            score += 6.0
            if "class" in lowered:
                score += 12.0
            if any(term in lowered for term in ("base", "implement", "inherit", "extends", "super", "construct")):
                score += 4.0
        if score > best_score:
            best_score = score
            best_index = index
    selected: list[str] = []
    char_count = 0
    start = max(0, best_index - 8)
    for line in lines[start:]:
        if selected and char_count + len(line) + 1 > limit:
            break
        selected.append(line)
        char_count += len(line) + 1
    excerpt = "\n".join(selected).strip()
    if not excerpt:
        return text[:limit]
    if start > 0:
        excerpt = "...\n" + excerpt
    return excerpt


def _is_step2_repo_path_allowed(path: str) -> bool:
    role = tool_file_role(path)
    return role in {"implementation", "documentation"}


def _candidate_from_chunk_payload(payload: Mapping[str, Any], *, coverage_area: str, retrieval_path: str) -> RetrievalCandidate:
    path = str(payload.get("path", "") or "")
    line_range = str(payload.get("line_range", "") or "")
    metadata = {
        "snapshot": str(payload.get("snapshot", "")),
        "commit": str(payload.get("commit", "")),
        "visibility": str(payload.get("visibility", "")),
        "file_role": tool_file_role(path) if path else "",
        "coverage_area": coverage_area,
        "retrieval_path": retrieval_path,
        "path": path,
    }
    return RetrievalCandidate(
        candidate_id=str(payload.get("chunk_id", "")),
        source_category=SourceCategory(str(payload.get("source_category", SourceCategory.SOURCE_CODE.value))),
        retrieval_path=retrieval_path,
        text=str(payload.get("text", "")),
        score=float(payload.get("score", 0.0) or 0.0),
        source_id=str(payload.get("chunk_id", "")),
        path=path or None,
        line_range=line_range or None,
        metadata=metadata,
    )


def _candidate_rank_key(candidate: RetrievalCandidate) -> tuple[float, float]:
    role_weight = {
        "implementation": 1.3,
        "documentation": 0.85,
        "test": 0.2,
        "baseline_or_generated": 0.1,
        "other": 0.6,
        "": 0.7,
    }.get(candidate.metadata.get("file_role", ""), 0.6)
    category_weight = {
        SourceCategory.SOURCE_CODE: 1.3,
        SourceCategory.DOCUMENTATION: 0.8,
        SourceCategory.ISSUE_TRACKER: 0.5,
        SourceCategory.PULL_REQUEST: 0.5,
        SourceCategory.LOCAL_NOTES: 0.5,
        SourceCategory.NOTEBOOKLM: 0.5,
    }.get(candidate.source_category, 0.5)
    return candidate.score * role_weight * category_weight, candidate.score


def merge_source_priorities(
    preferred: Sequence[SourceCategory],
    existing: Sequence[SourceCategory],
) -> tuple[SourceCategory, ...]:
    selected: list[SourceCategory] = []
    for category in (*preferred, *existing):
        if category not in selected:
            selected.append(category)
    return tuple(selected)


def _trusted_file_hints_for_result(result: ObsidianSearchResult) -> tuple[str, ...]:
    return trusted_file_hints_from_obsidian_results((result,))


def _obsidian_source_queries(prompt: str) -> tuple[str, ...]:
    normalized = prompt.replace("`", " ")
    candidates: list[str] = []
    title_match = re.search(r"^Title:\s*(.+)$", normalized, re.IGNORECASE | re.MULTILINE)
    if title_match:
        candidates.append(title_match.group(1))
    lowered = normalized.lower()
    if "abstract" in lowered and "class" in lowered:
        candidates.extend(
            [
                "abstract class TypeScript",
                "abstract classes",
            ]
        )
    identifiers = [
        token
        for token in IDENTIFIER_PATTERN.findall(normalized)
        if len(token) >= 4 and token.lower() not in {"explain", "code", "context", "needed", "issue", "support"}
    ]
    if identifiers:
        candidates.append(" ".join(identifiers[:5]))
    candidates.append(prompt[:500])
    return ordered_unique([candidate.strip() for candidate in candidates if candidate.strip()])


def _tool_summary_payload(observation: ToolObservation) -> dict[str, Any]:
    links: list[str] = []
    seen_links: set[str] = set()

    def add_link(value: str) -> None:
        normalized = value.strip()
        if not normalized or normalized in seen_links:
            return
        seen_links.add(normalized)
        links.append(normalized)

    for ref in observation.source_refs:
        add_link(str(ref))

    payload = observation.payload
    if isinstance(payload.get("files"), list):
        for item in payload["files"][:20]:
            if not isinstance(item, Mapping):
                continue
            path = str(item.get("path", "")).strip()
            line = item.get("line")
            add_link(f"{path}:L{line}" if path and line else path)
    if isinstance(payload.get("results"), list):
        for item in payload["results"][:20]:
            if not isinstance(item, Mapping):
                continue
            chunk_id = str(item.get("chunk_id", "")).strip()
            path = str(item.get("path", "")).strip()
            line_range = str(item.get("line_range", "")).strip()
            add_link(chunk_id or (f"{path}:{line_range}" if path and line_range else path))
    if isinstance(payload.get("snippets"), list):
        for item in payload["snippets"][:20]:
            if not isinstance(item, Mapping):
                continue
            chunk_id = str(item.get("chunk_id", "")).strip()
            path = str(item.get("path", "")).strip()
            line_range = str(item.get("line_range", "")).strip()
            add_link(chunk_id or (f"{path}:{line_range}" if path and line_range else path))

    return {
        "result_count": str(observation.metadata.get("result_count", "")),
        "result_links": links,
        "metadata": dict(observation.metadata),
    }


def _load_sync_manifest(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, Mapping) else {}


def _save_sync_manifest(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), indent=2, sort_keys=True), encoding="utf-8")
