from __future__ import annotations

# Owns role validation and anchor-support evidence. Do not place retrieval orchestration, candidate expansion, ranking policy, or synthesis decisions here.

from typing import Any, Mapping, Sequence

from services.retrieval.workspace.pipeline.execution_flow.context import WorkspaceRetrievalContext
from services.retrieval.workspace.pipeline.file_level import (
    anchor_support_paths as _anchor_support_paths,
    candidate_symbol as _candidate_symbol,
    diagnostics_like_candidate as _diagnostics_like_candidate,
    line_start_from_range as _line_start_from_range,
    matched_anchor_paths as _matched_anchor_paths,
    role_phase_path_allowed as _role_phase_path_allowed,
)
from services.retrieval.workspace.pipeline.models import RetrievalCandidate, RoleRetrievalBucket, RoleValidationResult
from services.retrieval.workspace.pipeline.relationship_flow import (
    anchor_symbol_relation_query as _anchor_symbol_relation_query,
    cypher_relative_path as _cypher_relative_path,
    is_structural_symbol_name as _is_structural_symbol_name,
)
from services.retrieval.workspace.responsibility import ResponsibilityScore
from services.retrieval.workspace.role_validation import AnchorRecord, AnchorSupport, RoleValidationContext, validator_for_role
from services.retrieval.workspace.step2.common import ordered_unique
from services.retrieval.workspace.tools import OpenFileTool, ToolObservation, ToolRequest


def responsibility_validation_result(
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


def role_completion_validation_result(
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


def open_candidate_context(
    ctx: WorkspaceRetrievalContext,
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
        ctx.trace.record_tool(request, observation, round_index=0)
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


def validate_role_candidate(
    ctx: WorkspaceRetrievalContext,
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
        matched_dependency_anchors = query_anchor_candidate_support(ctx, 
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


def query_anchor_candidate_support(
    ctx: WorkspaceRetrievalContext,
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
            ctx.trace.record_tool(request, observation, round_index=0)
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
                ctx.trace.record(
                    "anchor_query_confirmed",
                    {
                        "source_role": anchor.role,
                        "anchor_path": anchor.path,
                        "candidate_path": candidate_path,
                        "shared_symbols": list(ordered_unique(symbols)),
                    },
                )
        return tuple(ordered_unique(supporting_anchor_paths))


def accepted_anchor_records(buckets: Sequence[RoleRetrievalBucket]) -> tuple[AnchorRecord, ...]:
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


def build_anchor_support(
    ctx: WorkspaceRetrievalContext,
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
                    ctx.trace.record_tool(request, observation, round_index=0)
                    tool_calls += 1
                    collected_call_paths.extend(_anchor_support_paths(observation))
                call_paths = tuple(ordered_unique(collected_call_paths))
            call_paths_by_anchor[anchor.path] = call_paths
            ctx.trace.record(
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
