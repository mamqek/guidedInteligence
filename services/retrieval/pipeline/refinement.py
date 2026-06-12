from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from core.source_policy import SourceCategory
from services.retrieval.pipeline.constants import MAX_ROLE_FILE_REFINE_QUERIES
from services.retrieval.pipeline.file_level import candidate_from_chunk_payload, candidate_rank_key
from services.retrieval.pipeline.models import RetrievalCandidate
from services.retrieval.pipeline.snippet_level import (
    best_in_file_refinement_span,
    declaration_candidates_for_llm,
    read_owner_text_file,
    role_snippet_queries,
)
from services.retrieval.tools import OpenFileTool, QdrantHybridSearchTool, ToolObservation, ToolRequest
from services.retrieval.workspace_llm import select_owner_declarations_with_llm


def refine_candidate_within_file(
    *,
    role: str,
    query: str,
    helper_queries: Sequence[str],
    candidate: RetrievalCandidate,
    qdrant_tool: QdrantHybridSearchTool,
    open_file_tool: OpenFileTool,
    snippet_queries: Sequence[str] | None = None,
    search_terms: Sequence[str] = (),
    workspace_root: str,
    llm_config: Any,
    owner_declaration_file_cache: dict[str, tuple[dict[str, str], ...]],
    record: Callable[[str, Mapping[str, Any]], None],
    record_tool: Callable[[ToolRequest, ToolObservation], None],
    open_candidate_context: Callable[[RetrievalCandidate, OpenFileTool], tuple[RetrievalCandidate, ToolObservation | None]],
) -> tuple[RetrievalCandidate, tuple[ToolObservation, ...]]:
    if not candidate.path:
        return candidate, ()
    observations: list[ToolObservation] = []
    best_candidate = candidate
    local_candidate = refine_candidate_with_local_file_search(
        role=role,
        query=query,
        helper_queries=helper_queries,
        candidate=candidate,
        search_terms=search_terms,
        workspace_root=workspace_root,
        llm_config=llm_config,
        owner_declaration_file_cache=owner_declaration_file_cache,
        record=record,
    )
    if local_candidate is not None and candidate_rank_key(local_candidate) > candidate_rank_key(best_candidate):
        best_candidate = local_candidate
    active_snippet_queries = snippet_queries or role_snippet_queries(role, query=query, helper_queries=helper_queries)
    for snippet_query in active_snippet_queries[:MAX_ROLE_FILE_REFINE_QUERIES]:
        request = ToolRequest(
            tool_name="qdrant_hybrid_search",
            arguments={
                "query": snippet_query,
                "_coverage_area": role,
                "limit": 1,
                "paths": [candidate.path],
                "source_category": "source_code",
                "file_role": "implementation",
            },
            reason=f"Refine the best in-file snippet for the {role} role.",
        )
        observation = qdrant_tool.run(request)
        record_tool(request, observation)
        observations.append(observation)
        for payload in observation.payload.get("results", ()):
            if not isinstance(payload, Mapping):
                continue
            refined = candidate_from_chunk_payload(payload, coverage_area=role, retrieval_path="qdrant_hybrid_search")
            refined, open_observation = open_candidate_context(refined, open_file_tool)
            if open_observation is not None:
                observations.append(open_observation)
            if candidate_rank_key(refined) > candidate_rank_key(best_candidate):
                best_candidate = refined
    if best_candidate.source_id != candidate.source_id:
        record(
            "role_candidate_refined",
            {
                "role": role,
                "original_ref": candidate.source_id,
                "refined_ref": best_candidate.source_id,
                "path": candidate.path,
            },
        )
    return best_candidate, tuple(observations)


def refine_candidate_with_local_file_search(
    *,
    role: str,
    query: str,
    helper_queries: Sequence[str],
    candidate: RetrievalCandidate,
    search_terms: Sequence[str],
    workspace_root: str,
    llm_config: Any,
    owner_declaration_file_cache: dict[str, tuple[dict[str, str], ...]],
    record: Callable[[str, Mapping[str, Any]], None],
) -> RetrievalCandidate | None:
    if not candidate.path:
        return None
    root = Path(workspace_root).resolve()
    normalized_path = candidate.path.replace("\\", "/").lstrip("/")
    file_path = (root / normalized_path).resolve()
    try:
        file_path.relative_to(root)
    except ValueError:
        return None
    if not file_path.is_file():
        return None
    text = read_owner_text_file(file_path)
    if text is None:
        return None
    lines = text.splitlines()
    if not lines:
        return None
    query_text = " ".join([query, *helper_queries, *search_terms]).strip()
    declarations = declaration_candidates_for_llm(
        role=role,
        query_text=query_text,
        path=normalized_path,
        lines=lines,
    )
    llm_candidate = select_owner_declaration_candidate(
        role=role,
        query=query,
        helper_queries=helper_queries,
        path=normalized_path,
        lines=lines,
        base_candidate=candidate,
        declaration_candidates=declarations,
        llm_config=llm_config,
        owner_declaration_file_cache=owner_declaration_file_cache,
        record=record,
    )
    line_start, line_end, score = best_in_file_refinement_span(
        role=role,
        query=query,
        helper_queries=helper_queries,
        search_terms=search_terms,
        lines=lines,
    )
    lexical_candidate: RetrievalCandidate | None = None
    if score > 0:
        lexical_candidate = candidate_from_local_span(
            role=role,
            candidate=candidate,
            normalized_path=normalized_path,
            lines=lines,
            line_start=line_start,
            line_end=line_end,
            score=score,
            event_type="role_candidate_locally_refined",
            record=record,
        )
    if llm_candidate is None:
        return lexical_candidate
    if lexical_candidate is None or candidate_rank_key(llm_candidate) >= candidate_rank_key(lexical_candidate):
        return llm_candidate
    return lexical_candidate


def select_owner_declaration_candidate(
    *,
    role: str,
    query: str,
    helper_queries: Sequence[str],
    path: str,
    lines: Sequence[str],
    base_candidate: RetrievalCandidate,
    declaration_candidates: Sequence[Mapping[str, Any]],
    llm_config: Any,
    owner_declaration_file_cache: dict[str, tuple[dict[str, str], ...]],
    record: Callable[[str, Mapping[str, Any]], None],
) -> RetrievalCandidate | None:
    if not declaration_candidates:
        return None
    cached_selections = owner_declaration_file_cache.get(path)
    if cached_selections is not None:
        record("owner_declaration_selection_file_cache_hit", {"path": path, "role": role, "selection_count": len(cached_selections)})
        selections = cached_selections
    else:
        selections = select_owner_declarations_with_llm(
            role=role,
            query=query,
            helper_queries=helper_queries,
            path=path,
            declaration_candidates=declaration_candidates,
            llm_config=llm_config,
            log_warning=lambda payload: record("llm_request_warning", payload),
            log_event=record,
        )
        owner_declaration_file_cache[path] = tuple(dict(item) for item in selections)
        record("owner_declaration_selection_file_cache_miss", {"path": path, "role": role, "selection_count": len(selections)})
    selected_by_id = {str(item.get("id", "")): item for item in declaration_candidates}
    best_candidate: RetrievalCandidate | None = None
    for selection in selections:
        selected = selected_by_id.get(selection["id"])
        if selected is None:
            continue
        candidate = candidate_from_local_span(
            role=role,
            candidate=base_candidate,
            normalized_path=path,
            lines=lines,
            line_start=int(selected["start_line"]),
            line_end=int(selected["end_line"]),
            score=float(selected.get("lexical_score", 0.0)) + 4.0,
            event_type="role_candidate_declaration_selected",
            record=record,
            extra_payload={
                "selection_reason": selection.get("reason", ""),
                "declaration_name": str(selected.get("name", "")),
            },
        )
        if candidate is None:
            continue
        if best_candidate is None or candidate_rank_key(candidate) > candidate_rank_key(best_candidate):
            best_candidate = candidate
    return best_candidate


def candidate_from_local_span(
    *,
    role: str,
    candidate: RetrievalCandidate,
    normalized_path: str,
    lines: Sequence[str],
    line_start: int,
    line_end: int,
    score: float,
    event_type: str,
    record: Callable[[str, Mapping[str, Any]], None],
    extra_payload: Mapping[str, Any] | None = None,
) -> RetrievalCandidate | None:
    if line_start < 1 or line_end < line_start:
        return None
    snippet = "\n".join(lines[line_start - 1 : line_end])
    source_id = f"repo-pre:{normalized_path}:L{line_start}-L{line_end}"
    payload = {
        "role": role,
        "original_ref": candidate.source_id,
        "refined_ref": source_id,
        "path": normalized_path,
        "line_start": line_start,
        "line_end": line_end,
        "score": round(score, 3),
    }
    if extra_payload:
        payload.update(dict(extra_payload))
    record(event_type, payload)
    return RetrievalCandidate(
        candidate_id=source_id,
        source_category=SourceCategory.SOURCE_CODE,
        retrieval_path="local_in_file_refinement",
        text=snippet,
        score=max(candidate.score, 6.5) + min(score / 20.0, 3.5),
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
