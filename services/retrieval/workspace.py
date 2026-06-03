from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from core.models import ConversationState, EvidenceItem, PolicyResult, RetrievalResult
from core.source_policy import SourceCategory
from services.retrieval.bm25 import build_index_from_repo, load_index, save_index
from services.retrieval.config import ConnectedSourceDocument, WorkspaceRetrievalConfig
from services.retrieval.role_completion import RoleCompletionContext, score_role_completion
from services.retrieval.role_validation import AnchorRecord, AnchorSupport, RoleValidationContext, validator_for_role
from services.retrieval.step2 import WorkspaceRetrievalPlan, existing_evidence_plan, extract_prompt_evidence, plan_workspace_retrieval_step
from services.retrieval.step2.common import IDENTIFIER_PATTERN, merge_paths, ordered_unique
from services.retrieval.tools import (
    BM25SearchTool,
    CGCAnalyzeCalleesTool,
    CGCAnalyzeCallersTool,
    CGCFindCodeTool,
    CGCIndexRepoTool,
    CGCQueryGraphTool,
    CGCRunCliTool,
    OpenFileTool,
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
DECLARATION_PATTERN = re.compile(r"\b(?:class|interface|function|enum|type|namespace|module)\s+([A-Za-z_][A-Za-z0-9_]*)\b")


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
class RoleRetrievalBucket:
    role: str
    query: str
    helper_queries: tuple[str, ...]
    observations: tuple[ToolObservation, ...]
    evaluations: tuple[RoleCandidateEvaluation, ...]
    accepted_candidates: tuple[RetrievalCandidate, ...]
    rejected_refs: tuple[str, ...]
    validation_notes: tuple[str, ...]
    missing_reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "query": self.query,
            "helper_queries": list(self.helper_queries),
            "accepted_refs": [candidate.source_id for candidate in self.accepted_candidates],
            "rejected_refs": list(self.rejected_refs),
            "validation_notes": list(self.validation_notes),
            "missing_reason": self.missing_reason,
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
                    "snippet": candidate.text[:400],
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
        index_observation = cgc_tools["cgc_index_repo"].run(
            ToolRequest(tool_name="cgc_index_repo", arguments={}, reason="mandatory code graph refresh")
        )
        self._record_tool(ToolRequest(tool_name="cgc_index_repo", arguments={}), index_observation, round_index=0)
        if index_observation.status != "ok":
            return self._failed_result(None, failure="cgc_index_failed", observation=index_observation)

        index = self._rebuild_index()
        bm25_tool = BM25SearchTool(index)
        open_file_tool = OpenFileTool(index)
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
        self._record("retrieval_plan_created", retrieval_plan.to_dict())

        global_narrowed_files, narrowing_observations, tool_call_count = self._run_initial_narrowing(
            retrieval_plan=retrieval_plan,
            cgc_find_tool=cgc_tools["cgc_find_code"],
            preplan_tool_calls=preplan_tool_calls,
        )
        if global_narrowed_files is None:
            failed_observation = narrowing_observations[0] if narrowing_observations else index_observation
            return self._failed_result(retrieval_plan, failure="cgc_narrowing_failed", observation=failed_observation)

        required_buckets, tool_call_count = self._retrieve_role_buckets(
            retrieval_plan=retrieval_plan,
            subquery_roles=retrieval_plan.required_roles,
            bm25_tool=bm25_tool,
            open_file_tool=open_file_tool,
            cgc_tools=cgc_tools,
            narrowed_files=global_narrowed_files,
            starting_tool_call_count=tool_call_count,
            phase="required",
        )
        required_buckets = self._complete_role_buckets(retrieval_plan=retrieval_plan, buckets=required_buckets)
        required_buckets, tool_call_count = self._retarget_role_buckets(
            buckets=required_buckets,
            bm25_tool=bm25_tool,
            open_file_tool=open_file_tool,
            cgc_tools=cgc_tools,
            starting_tool_call_count=tool_call_count,
        )
        synthesis_decision = self._synthesize_role_buckets(retrieval_plan, required_buckets)

        supporting_buckets: tuple[RoleRetrievalBucket, ...] = ()
        if not synthesis_decision.acceptance_satisfied and _bucket_missing_roles(required_buckets):
            supporting_buckets, tool_call_count = self._retrieve_role_buckets(
                retrieval_plan=retrieval_plan,
                subquery_roles=retrieval_plan.supporting_roles,
                bm25_tool=bm25_tool,
                open_file_tool=open_file_tool,
                cgc_tools=cgc_tools,
                narrowed_files=global_narrowed_files,
                starting_tool_call_count=tool_call_count,
                phase="supporting",
            )
            supporting_buckets, tool_call_count = self._retarget_role_buckets(
                buckets=supporting_buckets,
                bm25_tool=bm25_tool,
                open_file_tool=open_file_tool,
                cgc_tools=cgc_tools,
                starting_tool_call_count=tool_call_count,
            )
            synthesis_decision = self._synthesize_role_buckets(retrieval_plan, required_buckets + supporting_buckets)

        selected = self._select_evidence_items(required_buckets, supporting_buckets, policy_result.allowed_sources)
        for coverage_area in _coverage_area_names(retrieval_plan):
            present = any(item.metadata.get("coverage_area") == coverage_area for item in selected)
            self._record("gap_check_completed", {"coverage_area": coverage_area, "status": "strong" if present else "missing"})
        for bucket in required_buckets + supporting_buckets:
            self._record(
                "role_coverage_completed",
                {
                    "role": bucket.role,
                    "accepted_count": len(bucket.accepted_candidates),
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
            "bm25_paths_count": len(global_narrowed_files),
            "required_role_buckets": [bucket.to_dict() for bucket in required_buckets],
            "supporting_role_buckets": [bucket.to_dict() for bucket in supporting_buckets],
            "refinement_policy": synthesis_decision.to_dict(),
        }
        return RetrievalResult(
            evidence=tuple(selected),
            coverage_status=self._coverage_status(selected, synthesis_decision, retrieval_plan),
            sufficient=bool(selected) and synthesis_decision.acceptance_satisfied,
            retrieval_summary=retrieval_summary,
            failures_or_fallbacks=tuple(_bucket_missing_roles(required_buckets)),
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
        index = build_index_from_repo(
            repo_path=self.config.workspace_root,
            commit="workspace",
            chunk_line_count=self.config.chunk_line_count,
            chunk_line_overlap=self.config.chunk_line_overlap,
            snapshot="workspace_current",
            visibility="workspace_visible",
            origin="workspace_index",
        )
        save_index(index, self.config.index_dir)
        self._record(
            "workspace_index_rebuilt",
            {
                "workspace_root": self.config.workspace_root,
                "index_dir": self.config.index_dir,
                "document_count": len(index.documents),
                "reindex_policy": self.config.reindex_policy,
            },
        )
        return load_index(self.config.index_dir)

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

    def _retrieve_role_buckets(
        self,
        *,
        retrieval_plan: WorkspaceRetrievalPlan,
        subquery_roles: Sequence[str],
        bm25_tool: BM25SearchTool,
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
                bm25_tool=bm25_tool,
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
        bm25_tool: BM25SearchTool,
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
            updated_bucket, bucket_tool_calls = self._retarget_role_bucket(
                bucket=bucket,
                anchor_support=anchor_support,
                bm25_tool=bm25_tool,
                open_file_tool=open_file_tool,
                cgc_tools=cgc_tools,
            )
            retargeted.append(updated_bucket)
            total_tool_calls += bucket_tool_calls
        return tuple(retargeted), total_tool_calls

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
            evaluations=tuple(new_evaluations),
            accepted_candidates=selected_candidates,
            rejected_refs=rejected_refs,
            validation_notes=tuple(validation_notes),
            missing_reason="" if selected_candidates else target_bucket.missing_reason,
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
        bm25_tool: BM25SearchTool,
        open_file_tool: OpenFileTool,
        cgc_tools: Mapping[str, Any],
    ) -> tuple[RoleRetrievalBucket, int]:
        if not bucket.accepted_candidates:
            return bucket, 0
        tool_calls = 0
        evaluations = list(bucket.evaluations)
        evaluation_by_ref = {evaluation.candidate.source_id: evaluation for evaluation in bucket.evaluations}
        retargeted_candidates: list[RetrievalCandidate] = []
        for candidate in bucket.accepted_candidates:
            best_candidate = candidate
            original_evaluation = evaluation_by_ref.get(candidate.source_id)
            best_validation = original_evaluation.validation if original_evaluation is not None else self._validate_role_candidate(
                role=bucket.role,
                query=bucket.query,
                helper_queries=bucket.helper_queries,
                candidate=candidate,
                anchor_support=anchor_support,
                cgc_tools=cgc_tools,
            )
            snippet_queries = _role_retarget_queries(
                bucket.role,
                query=bucket.query,
                helper_queries=bucket.helper_queries,
                candidate_path=candidate.path or "",
                candidate_text=candidate.text,
            )[:MAX_ROLE_RETARGET_QUERIES]
            for snippet_query in snippet_queries:
                request = ToolRequest(
                    tool_name="bm25_search",
                    arguments={"query": snippet_query, "_coverage_area": bucket.role, "limit": 2, "paths": [candidate.path]},
                    reason=f"Retarget the strongest in-file snippet for the {bucket.role} role.",
                )
                observation = bm25_tool.run(request)
                self._record_tool(request, observation, round_index=0)
                tool_calls += 1
                for payload in observation.payload.get("results", ()):
                    if not isinstance(payload, Mapping):
                        continue
                    refined = _candidate_from_chunk_payload(payload, coverage_area=bucket.role, retrieval_path="bm25_search")
                    refined, open_observation = self._open_candidate_context(refined, open_file_tool)
                    if open_observation is not None:
                        tool_calls += 1
                    validation = self._validate_role_candidate(
                        role=bucket.role,
                        query=bucket.query,
                        helper_queries=bucket.helper_queries,
                        candidate=refined,
                        anchor_support=anchor_support,
                        cgc_tools=cgc_tools,
                    )
                    self._record(
                        "role_candidate_retarget_scored",
                        {
                            "role": bucket.role,
                            "original_ref": candidate.source_id,
                            "candidate_ref": refined.source_id,
                            "query": snippet_query,
                            "validation": validation.to_dict(),
                        },
                    )
                    if _better_retarget_candidate(
                        candidate=refined,
                        validation=validation,
                        best_candidate=best_candidate,
                        best_validation=best_validation,
                    ):
                        best_candidate = refined
                        best_validation = validation
            if best_candidate.source_id != candidate.source_id:
                evaluations.append(
                    RoleCandidateEvaluation(
                        candidate=best_candidate,
                        validation=best_validation,
                        stage="snippet_retarget",
                        source_role=bucket.role,
                    )
                )
                self._record(
                    "role_candidate_retargeted",
                    {
                        "role": bucket.role,
                        "original_ref": candidate.source_id,
                        "retargeted_ref": best_candidate.source_id,
                        "validation": best_validation.to_dict(),
                    },
                )
            retargeted_candidates.append(best_candidate)
        return (
            RoleRetrievalBucket(
                role=bucket.role,
                query=bucket.query,
                helper_queries=bucket.helper_queries,
                observations=bucket.observations,
                evaluations=tuple(evaluations),
                accepted_candidates=tuple(retargeted_candidates),
                rejected_refs=bucket.rejected_refs,
                validation_notes=bucket.validation_notes,
                missing_reason=bucket.missing_reason,
            ),
            tool_calls,
        )

    def _prepare_role_bucket(
        self,
        *,
        retrieval_plan: WorkspaceRetrievalPlan,
        role: str,
        query: str,
        bm25_tool: BM25SearchTool,
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
        shared_arguments: dict[str, Any] = {"limit": min(self.config.cgc_max_files_for_bm25, MAX_EVIDENCE_ITEMS)}
        if narrowed_files:
            shared_arguments["paths"] = list(narrowed_files)
        for helper_query in helper_queries[:MAX_ROLE_QUERIES]:
            request = ToolRequest(
                tool_name="bm25_search",
                arguments={"query": helper_query, "_coverage_area": role, **shared_arguments},
                reason=f"Retrieve code evidence for the {role} role.",
            )
            observation = bm25_tool.run(request)
            self._record_tool(request, observation, round_index=0)
            observations.append(observation)
            tool_calls += 1
            helper_candidates = self._candidates_from_bm25_observation(observation, coverage_area=role)
            raw_candidates.extend(helper_candidates)
            seeded_candidates.extend(self._select_helper_query_seed_candidates(helper_candidates))

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
                bm25_tool=bm25_tool,
                open_file_tool=open_file_tool,
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
        bm25_tool: BM25SearchTool,
        open_file_tool: OpenFileTool,
        snippet_queries: Sequence[str] | None = None,
    ) -> tuple[RetrievalCandidate, tuple[ToolObservation, ...]]:
        if not candidate.path:
            return candidate, ()
        observations: list[ToolObservation] = []
        best_candidate = candidate
        active_snippet_queries = snippet_queries or _role_snippet_queries(role, query=query, helper_queries=helper_queries)
        for snippet_query in active_snippet_queries[:MAX_ROLE_FILE_REFINE_QUERIES]:
            request = ToolRequest(
                tool_name="bm25_search",
                arguments={"query": snippet_query, "_coverage_area": role, "limit": 1, "paths": [candidate.path]},
                reason=f"Refine the best in-file snippet for the {role} role.",
            )
            observation = bm25_tool.run(request)
            self._record_tool(request, observation, round_index=0)
            observations.append(observation)
            for payload in observation.payload.get("results", ()):
                if not isinstance(payload, Mapping):
                    continue
                refined = _candidate_from_chunk_payload(payload, coverage_area=role, retrieval_path="bm25_search")
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
            evaluations=tuple(evaluations),
            accepted_candidates=tuple(accepted),
            rejected_refs=tuple(ordered_unique(rejected_refs)),
            validation_notes=tuple(validation_notes),
            missing_reason=missing_reason or ("no_validated_candidates" if not accepted else ""),
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
        validator = validator_for_role(role)
        compatible_anchors = anchor_support.anchors_for_roles(getattr(validator, "compatible_anchor_roles", (role,)))
        matched_dependency_anchors = self._query_anchor_candidate_support(
            role=role,
            candidate_path=path,
            candidate=candidate,
            anchors=compatible_anchors,
            cgc_tools=cgc_tools,
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
    ) -> tuple[str, ...]:
        if role != "representation" or not candidate_path:
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

    def _candidates_from_bm25_observation(self, observation: ToolObservation, *, coverage_area: str) -> tuple[RetrievalCandidate, ...]:
        candidates: list[RetrievalCandidate] = []
        for payload in observation.payload.get("results", ()):
            if isinstance(payload, Mapping):
                candidates.append(_candidate_from_chunk_payload(payload, coverage_area=coverage_area, retrieval_path="bm25_search"))
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
        accepted_by_role = {bucket.role: list(bucket.accepted_candidates) for bucket in buckets}
        role_order = [bucket.role for bucket in required_buckets if bucket.accepted_candidates]
        role_order.extend(bucket.role for bucket in supporting_buckets if bucket.accepted_candidates and bucket.role not in role_order)

        while len(selected) < MAX_EVIDENCE_ITEMS:
            progressed = False
            for role in role_order:
                candidates = accepted_by_role.get(role, [])
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

    def _coverage_status(
        self,
        selected: Sequence[EvidenceItem],
        decision: RetrievalSynthesisDecision,
        retrieval_plan: WorkspaceRetrievalPlan,
    ) -> str:
        if not selected:
            return "missing"
        covered_roles = {item.metadata.get("coverage_area", "") for item in selected}
        required_roles = set(retrieval_plan.required_roles)
        if required_roles.issubset(covered_roles) and decision.acceptance_satisfied:
            return "strong"
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
    missing = [bucket.role for bucket in buckets if not bucket.accepted_candidates]
    return tuple(ordered_unique(missing))


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
                "snippet": candidate.text[:800],
            }
        )
    return tuple(snippets)


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
