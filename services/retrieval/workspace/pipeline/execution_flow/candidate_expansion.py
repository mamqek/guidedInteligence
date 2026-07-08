from __future__ import annotations

# Owns candidate discovery and expansion: turning role queries, code-context terms, references, and direct owner paths into RetrievalCandidate objects. Do not place validation, final ranking, synthesis, or connected-source orchestration here.

from pathlib import Path
from typing import Any, Mapping, Sequence

from core.source_policy import SourceCategory
from services.retrieval.workspace.connected_context import ConnectedSourceContextResult
from services.retrieval.workspace.pipeline.constants import (
    MAX_ROLE_CANDIDATE_EVALUATIONS,
    MAX_ROLE_CODE_CONTEXT_QUERIES,
    MAX_ROLE_FOLLOWUP_QUERIES,
    MAX_ROLE_INITIAL_PATHS,
    MAX_ROLE_PER_QUERY_TOP_PATHS,
    MAX_ROLE_REFERENCE_EXPANSION_SOURCES,
    MAX_ROLE_REFERENCE_EXPANSION_TARGETS,
    MAX_ROLE_REFERENCE_SCAN_LINE_COUNT,
)
from services.retrieval.workspace.pipeline.execution_flow.context import WorkspaceRetrievalContext
from services.retrieval.workspace.pipeline.file_level import (
    anchor_support_paths as _anchor_support_paths,
    candidate_from_chunk_payload as _candidate_from_chunk_payload,
    candidate_is_reference_expansion_source as _candidate_is_reference_expansion_source,
    candidate_rank_key as _candidate_rank_key,
    candidate_symbol as _candidate_symbol,
    collapse_candidates_to_file_candidates as _collapse_candidates_to_file_candidates,
    extract_explicit_reference_paths as _extract_explicit_reference_paths,
    has_role_owner_candidate as _has_role_owner_candidate,
    is_generic_reference_hub as _is_generic_reference_hub,
    iterative_code_context_queries as _iterative_code_context_queries,
    owner_artifact_path_match as _owner_artifact_path_match,
    rank_unique_candidates as _rank_unique_candidates,
    resolve_explicit_reference_path as _resolve_explicit_reference_path,
    role_owner_path_match as _role_owner_path_match,
    target_matches_reference_owner_vocab as _target_matches_reference_owner_vocab,
)
from services.retrieval.workspace.pipeline.models import PreparedRoleBucket, RetrievalCandidate
from services.retrieval.workspace.pipeline.snippet_level import (
    best_direct_owner_span as _best_direct_owner_span,
    read_owner_text_file as _read_owner_text_file,
)
from services.retrieval.workspace.responsibility import ResponsibilityExpansionIntent, profile_candidate
from services.retrieval.workspace.role_validation import AnchorRecord
from services.retrieval.workspace.step2.common import ordered_unique
from services.retrieval.workspace.tools import OpenFileTool, QdrantHybridSearchTool, ToolObservation, ToolRequest
from services.retrieval.workspace.tools.local import file_role as tool_file_role


def preliminary_responsibility_anchors(
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


def expand_responsibility_candidates(
    ctx: WorkspaceRetrievalContext,
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
                ctx.trace.record_tool(request, observation, round_index=0)
                tool_calls += 1
                candidates, consumed_calls = prepare_expanded_candidates(
                    role=role,
                    query=prepared_bucket.query,
                    helper_queries=prepared_bucket.helper_queries,
                    observation=observation,
                    qdrant_tool=qdrant_tool,
                    open_file_tool=open_file_tool,
                )
                tool_calls += consumed_calls
                expanded.setdefault(role, []).extend(candidates)

            context_candidates, context_paths, context_calls = expand_iterative_code_context_candidates(ctx, 
                prepared_bucket=prepared_bucket,
                qdrant_tool=qdrant_tool,
                open_file_tool=open_file_tool,
            )
            tool_calls += context_calls
            if context_candidates:
                expanded.setdefault(role, []).extend(context_candidates)
            if context_paths:
                graph_paths.setdefault(role, []).extend(context_paths)

            reference_candidates, reference_paths, reference_calls = expand_converging_reference_candidates(ctx, 
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
                ctx.trace.record_tool(request, observation, round_index=0)
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
                    ctx.trace.record_tool(request, observation, round_index=0)
                    tool_calls += 1
                    candidates, consumed_calls = prepare_expanded_candidates(
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


def expand_iterative_code_context_candidates(
    ctx: WorkspaceRetrievalContext,
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
            ctx.trace.record(
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
            ctx.trace.record_tool(request, observation, round_index=1)
            tool_calls += 1
            candidates, consumed_calls = prepare_expanded_candidates(
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


def expand_converging_reference_candidates(
    ctx: WorkspaceRetrievalContext,
        *,
        prepared_bucket: PreparedRoleBucket,
        prepared_buckets: Sequence[PreparedRoleBucket],
        qdrant_tool: QdrantHybridSearchTool,
        open_file_tool: OpenFileTool,
    ) -> tuple[tuple[RetrievalCandidate, ...], tuple[str, ...], int]:
        role = prepared_bucket.role
        source_candidates = list(
            reference_expansion_source_candidates(ctx, 
                role=role,
                prepared_bucket=prepared_bucket,
                prepared_buckets=prepared_buckets,
            )[:MAX_ROLE_REFERENCE_EXPANSION_SOURCES]
        )
        min_votes = 2 if _has_role_owner_candidate(role, prepared_bucket.candidates) else 1
        ctx.trace.record(
            "responsibility_reference_source_pool",
            {
                "role": role,
                "source_paths": [candidate.path or "" for candidate in source_candidates],
                "source_refs": [candidate.source_id for candidate in source_candidates],
                "min_votes": min_votes,
            },
        )
        converged_targets, tool_calls = collect_converging_reference_targets(ctx, 
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
            ctx.trace.record(
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
            ctx.trace.record_tool(request, observation, round_index=0)
            tool_calls += 1
            candidates, consumed_calls = prepare_expanded_candidates(
                role=role,
                query=prepared_bucket.query,
                helper_queries=prepared_bucket.helper_queries,
                observation=observation,
                qdrant_tool=qdrant_tool,
                open_file_tool=open_file_tool,
            )
            tool_calls += consumed_calls
            if not candidates:
                direct_candidate = direct_owner_candidate_from_path(ctx, 
                    role=role,
                    target_path=target_path,
                    query=prepared_bucket.query,
                    search_terms=prepared_bucket.helper_queries,
                )
                if direct_candidate is not None:
                    candidates = (direct_candidate,)
            expanded.extend(candidates)

        return tuple(_rank_unique_candidates(expanded)), tuple(ordered_unique(graph_paths)), tool_calls


def direct_owner_candidate_from_path(
    ctx: WorkspaceRetrievalContext,
        *,
        role: str,
        target_path: str,
        query: str,
        search_terms: Sequence[str] = (),
    ) -> RetrievalCandidate | None:
        normalized_path = target_path.replace("\\", "/").lstrip("/")
        if not _role_owner_path_match(role, normalized_path) and not _owner_artifact_path_match(normalized_path, search_terms):
            ctx.trace.record(
                "responsibility_direct_owner_candidate_rejected",
                {"role": role, "path": normalized_path, "reason": "owner_vocab_mismatch"},
            )
            return None
        root = Path(ctx.config.workspace_root).resolve()
        file_path = (root / normalized_path).resolve()
        try:
            file_path.relative_to(root)
        except ValueError:
            ctx.trace.record(
                "responsibility_direct_owner_candidate_rejected",
                {"role": role, "path": normalized_path, "reason": "outside_workspace_root"},
            )
            return None
        if not file_path.is_file():
            ctx.trace.record(
                "responsibility_direct_owner_candidate_rejected",
                {"role": role, "path": normalized_path, "file_path": str(file_path), "reason": "file_not_found"},
            )
            return None
        text = _read_owner_text_file(file_path)
        if text is None:
            ctx.trace.record(
                "responsibility_direct_owner_candidate_rejected",
                {"role": role, "path": normalized_path, "reason": "decode_failed"},
            )
            return None
        lines = text.splitlines()
        if not lines:
            ctx.trace.record(
                "responsibility_direct_owner_candidate_rejected",
                {"role": role, "path": normalized_path, "reason": "empty_file"},
            )
            return None
        line_start, line_end = _best_direct_owner_span(role=role, query=query, lines=lines, search_terms=search_terms)
        snippet = "\n".join(lines[line_start - 1 : line_end])
        source_id = f"repo-pre:{normalized_path}:L{line_start}-L{line_end}"
        ctx.trace.record(
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


def span_candidate_from_accepted_file(
    ctx: WorkspaceRetrievalContext,
        *,
        role: str,
        file_candidate: RetrievalCandidate,
        query: str,
        search_terms: Sequence[str] = (),
    ) -> RetrievalCandidate | None:
        path = (file_candidate.path or file_candidate.metadata.get("path") or "").replace("\\", "/").lstrip("/")
        if not path:
            return None
        root = Path(ctx.config.workspace_root).resolve()
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


def reference_expansion_source_candidates(
    ctx: WorkspaceRetrievalContext,
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
                raw_candidates.extend(candidates_from_search_observation(observation, coverage_area=bucket.role))
        ranked = _rank_unique_candidates(raw_candidates)
        ctx.trace.record(
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
            ctx.trace.record(
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


def collect_converging_reference_targets(
    ctx: WorkspaceRetrievalContext,
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
            header_text, consumed_calls = load_reference_scan_text(ctx, path, open_file_tool)
            tool_calls += consumed_calls
            extracted_references = _extract_explicit_reference_paths(header_text)
            ctx.trace.record(
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
                    ctx.trace.record(
                        "responsibility_reference_target_rejected",
                        {"role": role, "source_path": path, "reference_path": reference_path, "reason": "unresolved_reference"},
                    )
                    continue
                if tool_file_role(resolved_path) != "implementation":
                    ctx.trace.record(
                        "responsibility_reference_target_rejected",
                        {"role": role, "source_path": path, "reference_path": reference_path, "resolved_path": resolved_path, "reason": "non_implementation_target"},
                    )
                    continue
                if not _target_matches_reference_owner_vocab(role, resolved_path, owner_terms):
                    ctx.trace.record(
                        "responsibility_reference_target_rejected",
                        {"role": role, "source_path": path, "reference_path": reference_path, "resolved_path": resolved_path, "reason": "owner_vocab_mismatch"},
                    )
                    continue
                if _is_generic_reference_hub(role, resolved_path, owner_terms):
                    ctx.trace.record(
                        "responsibility_reference_target_rejected",
                        {"role": role, "source_path": path, "reference_path": reference_path, "resolved_path": resolved_path, "reason": "generic_hub_blocked"},
                    )
                    continue
                votes.setdefault(resolved_path, set()).add(path)
                accepted_target = True
                ctx.trace.record(
                    "responsibility_reference_target_accepted",
                    {"role": role, "source_path": path, "reference_path": reference_path, "resolved_path": resolved_path},
                )

        selected = [
            path
            for path, source_paths in sorted(votes.items(), key=lambda item: (-len(item[1]), item[0]))
            if len(source_paths) >= min_votes
        ]
        ctx.trace.record(
            "responsibility_reference_votes",
            {
                "role": role,
                "votes": {path: sorted(source_paths) for path, source_paths in votes.items()},
                "selected_paths": selected,
                "min_votes": min_votes,
            },
        )
        for target_path in selected:
            ctx.trace.record(
                "responsibility_reference_convergence_detected",
                {
                    "role": role,
                    "path": target_path,
                    "source_paths": sorted(votes[target_path]),
                    "reason": "multi_source_explicit_reference_convergence",
                },
            )
        return tuple(selected[:MAX_ROLE_REFERENCE_EXPANSION_TARGETS]), tool_calls


def load_reference_scan_text(ctx: WorkspaceRetrievalContext, path: str, open_file_tool: OpenFileTool) -> tuple[str, int]:
        request = ToolRequest(
            tool_name="open_file",
            arguments={"path": path, "line_start": 1, "line_count": MAX_ROLE_REFERENCE_SCAN_LINE_COUNT},
            reason="Inspect file header for explicit references that can reveal owner convergence.",
        )
        observation = open_file_tool.run(request)
        ctx.trace.record_tool(request, observation, round_index=0)
        snippets = tuple(observation.payload.get("snippets", ())) if isinstance(observation.payload, Mapping) else ()
        parts = [str(item.get("text", "")) for item in snippets if isinstance(item, Mapping)]
        return "\n".join(parts), 1



def prepare_expanded_candidates(
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
            candidates=candidates_from_search_observation(observation, coverage_area=role),
            retrieval_path="qdrant_file_expansion",
        )
        return candidates[:MAX_ROLE_CANDIDATE_EVALUATIONS], 0


def candidates_from_search_observation(observation: ToolObservation, *, coverage_area: str) -> tuple[RetrievalCandidate, ...]:
        candidates: list[RetrievalCandidate] = []
        for payload in observation.payload.get("results", ()):
            if isinstance(payload, Mapping):
                candidates.append(_candidate_from_chunk_payload(payload, coverage_area=coverage_area, retrieval_path="qdrant_hybrid_search"))
        return tuple(candidates)
