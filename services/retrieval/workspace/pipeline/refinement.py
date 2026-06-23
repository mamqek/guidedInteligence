from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from core.source_policy import SourceCategory
from services.retrieval.workspace.pipeline.constants import (
    MAX_ROLE_BUCKET_CANDIDATES,
    MAX_ROLE_FILE_REFINE_QUERIES,
)
from services.retrieval.workspace.pipeline.file_level import (
    candidate_from_chunk_payload,
    candidate_rank_key,
    code_identifier_terms,
)
from services.retrieval.workspace.pipeline.models import RetrievalCandidate
from services.retrieval.workspace.pipeline.snippet_level import (
    best_in_file_refinement_span,
    declaration_candidates_for_llm,
    read_owner_text_file,
)
from services.retrieval.workspace.tools import OpenFileTool, QdrantHybridSearchTool, ToolObservation, ToolRequest

MAX_ROLE_FILE_DECLARATION_SHORTLIST = 8
LINE_RANGE_PATTERN = re.compile(r"L(\d+)(?:-L(\d+))?")
ROLE_NAME_HINTS: dict[str, tuple[str, ...]] = {
    "behavior_output": ("emit", "gen", "render", "create", "update"),
    "validation_checking": ("check", "validate", "assert", "verify", "error"),
    "input_parsing": ("parse", "scan", "read", "token", "modifier"),
    "representation": ("node", "type", "symbol", "flag", "syntax", "declaration", "interface"),
}
ROLE_NAME_BLOCKLIST: dict[str, tuple[str, ...]] = {
    "behavior_output": ("write", "get", "set"),
    "validation_checking": ("emit", "render"),
    "input_parsing": ("emit", "render", "write"),
    "representation": ("check", "emit", "write", "render"),
}


@dataclass(frozen=True)
class RoleFileRefinementState:
    role: str
    path: str
    candidates: tuple[RetrievalCandidate, ...]
    snippet_queries: tuple[str, ...]
    declaration_candidates: tuple[Mapping[str, Any], ...]
    search_terms: tuple[str, ...]


@dataclass(frozen=True)
class ScoredDeclaration:
    payload: Mapping[str, Any]
    score: float
    support_hits: int


def refine_role_file_group(
    *,
    role: str,
    query: str,
    helper_queries: Sequence[str],
    path: str,
    raw_candidates: Sequence[RetrievalCandidate],
    snippet_queries: Sequence[str],
    qdrant_tool: QdrantHybridSearchTool,
    open_file_tool: OpenFileTool,
    workspace_root: str,
    llm_config: Any,
    record: Callable[[str, Mapping[str, Any]], None],
    record_tool: Callable[[ToolRequest, ToolObservation], None],
    open_candidate_context: Callable[[RetrievalCandidate, OpenFileTool], tuple[RetrievalCandidate, ToolObservation | None]],
) -> tuple[tuple[RetrievalCandidate, ...], tuple[ToolObservation, ...]]:
    state, lines = build_role_file_refinement_state(
        role=role,
        query=query,
        helper_queries=helper_queries,
        path=path,
        raw_candidates=raw_candidates,
        snippet_queries=snippet_queries,
        workspace_root=workspace_root,
        record=record,
    )
    if state is None or lines is None:
        return (), ()

    observations: list[ToolObservation] = []
    record(
        "role_file_refinement_started",
        {
            "role": role,
            "path": path,
            "candidate_count": len(state.candidates),
            "query_count": len(state.snippet_queries),
            "declaration_count": len(state.declaration_candidates),
        },
    )

    support_candidates = list(state.candidates)
    for snippet_query in state.snippet_queries[:MAX_ROLE_FILE_REFINE_QUERIES]:
        request = ToolRequest(
            tool_name="qdrant_hybrid_search",
            arguments={
                "query": snippet_query,
                "_coverage_area": role,
                "limit": 1,
                "paths": [path],
                "source_category": "source_code",
                "file_role": "implementation",
            },
            reason=f"Refine grouped {role} evidence inside {path}.",
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
            support_candidates.append(refined)

    ranked_support = _rank_unique_candidates(support_candidates)
    declaration_shortlist = score_declaration_shortlist(
        role=role,
        lines=lines,
        declarations=state.declaration_candidates,
        support_candidates=ranked_support,
        search_terms=state.search_terms,
    )
    record(
        "role_file_declaration_shortlist_built",
        {
            "role": role,
            "path": path,
            "support_candidate_count": len(ranked_support),
            "shortlist_size": len(declaration_shortlist),
            "top_names": [str(item.payload.get("name", "")) for item in declaration_shortlist[:4]],
        },
    )

    refined_candidates: list[RetrievalCandidate] = []
    record(
        "role_file_declaration_llm_skipped",
        {
            "role": role,
            "path": path,
            "reason": "deterministic_shortlist_and_local_spans_are_primary",
        },
    )
    refined_candidates.extend(
        deterministic_declaration_candidates(
            role=role,
            path=path,
            lines=lines,
            base_candidates=ranked_support,
            declaration_shortlist=declaration_shortlist,
            record=record,
        )
    )
    lexical_candidate = best_local_refinement_candidate(
        role=role,
        query=query,
        helper_queries=helper_queries,
        path=path,
        lines=lines,
        base_candidates=ranked_support,
        search_terms=state.search_terms,
        record=record,
    )
    if lexical_candidate is not None:
        refined_candidates.append(lexical_candidate)
    refined_candidates.extend(
        support_candidates_near_shortlist(
            role=role,
            support_candidates=ranked_support,
            declaration_shortlist=declaration_shortlist,
        )
    )

    ranked_refined = _rank_unique_candidates(refined_candidates)[: MAX_ROLE_BUCKET_CANDIDATES * 2]
    record(
        "role_file_refinement_completed",
        {
            "role": role,
            "path": path,
            "produced_refs": [candidate.source_id for candidate in ranked_refined],
        },
    )
    return ranked_refined, tuple(observations)


def build_role_file_refinement_state(
    *,
    role: str,
    query: str,
    helper_queries: Sequence[str],
    path: str,
    raw_candidates: Sequence[RetrievalCandidate],
    snippet_queries: Sequence[str],
    workspace_root: str,
    record: Callable[[str, Mapping[str, Any]], None],
) -> tuple[RoleFileRefinementState | None, list[str] | None]:
    normalized_path, lines = _read_path_lines(path=path, workspace_root=workspace_root)
    if normalized_path is None or lines is None:
        return None, None
    ranked_candidates = _rank_unique_candidates(raw_candidates)
    search_terms = tuple(
        _ordered_unique(
            [
                query,
                *helper_queries,
                *snippet_queries,
                *code_identifier_terms("\n".join(candidate.text for candidate in ranked_candidates[:4])),
                Path(normalized_path).stem.lower(),
            ]
        )
    )
    declarations = declaration_candidates_for_llm(
        role=role,
        query_text=" ".join(search_terms).strip(),
        path=normalized_path,
        lines=lines,
    )
    state = RoleFileRefinementState(
        role=role,
        path=normalized_path,
        candidates=ranked_candidates,
        snippet_queries=tuple(_ordered_unique(value for value in snippet_queries if value and value.strip())),
        declaration_candidates=declarations,
        search_terms=search_terms,
    )
    record(
        "role_file_refinement_state_built",
        {
            "role": role,
            "path": normalized_path,
            "seed_candidate_count": len(ranked_candidates),
            "search_term_count": len(search_terms),
            "declaration_count": len(declarations),
        },
    )
    return state, lines


def score_declaration_shortlist(
    *,
    role: str,
    lines: Sequence[str],
    declarations: Sequence[Mapping[str, Any]],
    support_candidates: Sequence[RetrievalCandidate],
    search_terms: Sequence[str],
) -> tuple[ScoredDeclaration, ...]:
    scored: list[ScoredDeclaration] = []
    term_values = [term.lower() for term in search_terms if term.strip()]
    for payload in declarations:
        start_line = int(payload.get("start_line", 0))
        end_line = int(payload.get("end_line", 0))
        header_text = " ".join(
            [
                str(payload.get("name", "")),
                str(payload.get("header", "")),
                str(payload.get("preview", "")),
            ]
        ).lower()
        declaration_text = "\n".join(lines[max(0, start_line - 1) : min(len(lines), end_line)])
        score = float(payload.get("lexical_score", 0.0))
        support_hits = 0
        name = str(payload.get("name", "")).strip()
        name_lower = name.lower()
        for term in term_values[:24]:
            if term and term in header_text:
                score += 1.5
            elif term and term in declaration_text.lower():
                score += 0.5
        for candidate in support_candidates:
            distance = _candidate_distance_to_declaration(candidate, start_line=start_line, end_line=end_line)
            if distance is None:
                continue
            if distance == 0:
                score += 7.0
                support_hits += 1
            elif distance <= 20:
                score += max(0.5, 4.0 - (distance / 8.0))
                support_hits += 1
            if name and name.lower() in candidate.text.lower():
                score += 1.0
        score += _role_name_bias(role, name_lower)
        if role == "behavior_output" and "emit" in header_text:
            score += 2.0
        elif role == "validation_checking" and any(value in header_text for value in ("check", "validate", "verify", "assert")):
            score += 2.0
        elif role == "input_parsing" and any(value in header_text for value in ("parse", "scan", "read")):
            score += 2.0
        elif role == "representation" and any(value in header_text for value in ("node", "type", "symbol", "flag", "syntax")):
            score += 2.0
        scored.append(ScoredDeclaration(payload=payload, score=score, support_hits=support_hits))
    scored.sort(
        key=lambda item: (
            item.score,
            item.support_hits,
            -int(item.payload.get("start_line", 0)),
        ),
        reverse=True,
    )
    return tuple(scored[:MAX_ROLE_FILE_DECLARATION_SHORTLIST])


def deterministic_declaration_candidates(
    *,
    role: str,
    path: str,
    lines: Sequence[str],
    base_candidates: Sequence[RetrievalCandidate],
    declaration_shortlist: Sequence[ScoredDeclaration],
    record: Callable[[str, Mapping[str, Any]], None],
) -> tuple[RetrievalCandidate, ...]:
    if not declaration_shortlist or not base_candidates:
        return ()
    best_base = base_candidates[0]
    refined: list[RetrievalCandidate] = []
    for index, declaration in enumerate(declaration_shortlist[:2], start=1):
        candidate = candidate_from_local_span(
            role=role,
            candidate=best_base,
            normalized_path=path,
            lines=lines,
            line_start=int(declaration.payload["start_line"]),
            line_end=int(declaration.payload["end_line"]),
            score=declaration.score,
            event_type="role_candidate_declaration_preselected",
            record=record,
            extra_payload={
                "declaration_name": str(declaration.payload.get("name", "")),
                "declaration_rank": index,
                "support_hits": declaration.support_hits,
            },
        )
        if candidate is not None:
            refined.append(candidate)
    return tuple(refined)


def best_local_refinement_candidate(
    *,
    role: str,
    query: str,
    helper_queries: Sequence[str],
    path: str,
    lines: Sequence[str],
    base_candidates: Sequence[RetrievalCandidate],
    search_terms: Sequence[str],
    record: Callable[[str, Mapping[str, Any]], None],
) -> RetrievalCandidate | None:
    if not base_candidates:
        return None
    line_start, line_end, score = best_in_file_refinement_span(
        role=role,
        query=query,
        helper_queries=helper_queries,
        search_terms=search_terms,
        lines=lines,
    )
    if score <= 0:
        return None
    return candidate_from_local_span(
        role=role,
        candidate=base_candidates[0],
        normalized_path=path,
        lines=lines,
        line_start=line_start,
        line_end=line_end,
        score=score,
        event_type="role_candidate_locally_refined",
        record=record,
    )


def support_candidates_near_shortlist(
    *,
    role: str,
    support_candidates: Sequence[RetrievalCandidate],
    declaration_shortlist: Sequence[ScoredDeclaration],
) -> tuple[RetrievalCandidate, ...]:
    if not support_candidates:
        return ()
    if not declaration_shortlist:
        return tuple(support_candidates[:2])
    selected: list[RetrievalCandidate] = []
    for candidate in support_candidates:
        if candidate.metadata.get("retrieval_path") == "local_in_file_refinement":
            continue
        if _candidate_is_near_shortlist(candidate, declaration_shortlist):
            selected.append(candidate)
        if len(selected) >= 2:
            break
    return tuple(selected)


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
    metadata = dict(candidate.metadata)
    metadata.pop("file_candidate", None)
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
            **metadata,
            "path": normalized_path,
            "coverage_area": role,
            "retrieval_path": "local_in_file_refinement",
        },
    )


def _read_path_lines(*, path: str, workspace_root: str) -> tuple[str | None, list[str] | None]:
    root = Path(workspace_root).resolve()
    normalized_path = path.replace("\\", "/").lstrip("/")
    file_path = (root / normalized_path).resolve()
    try:
        file_path.relative_to(root)
    except ValueError:
        return None, None
    if not file_path.is_file():
        return None, None
    text = read_owner_text_file(file_path)
    if text is None:
        return None, None
    lines = text.splitlines()
    if not lines:
        return None, None
    return normalized_path, lines


def _rank_unique_candidates(candidates: Sequence[RetrievalCandidate]) -> tuple[RetrievalCandidate, ...]:
    unique: dict[str, RetrievalCandidate] = {}
    for candidate in candidates:
        key = candidate.source_id or candidate.candidate_id
        existing = unique.get(key)
        if existing is None or candidate_rank_key(candidate) > candidate_rank_key(existing):
            unique[key] = candidate
    return tuple(sorted(unique.values(), key=candidate_rank_key, reverse=True))


def _candidate_distance_to_declaration(
    candidate: RetrievalCandidate,
    *,
    start_line: int,
    end_line: int,
) -> int | None:
    candidate_range = _parse_line_range(candidate.line_range)
    if candidate_range is None:
        return None
    candidate_start, candidate_end = candidate_range
    if candidate_end < start_line:
        return start_line - candidate_end
    if candidate_start > end_line:
        return candidate_start - end_line
    return 0


def _candidate_is_near_shortlist(
    candidate: RetrievalCandidate,
    declarations: Sequence[ScoredDeclaration],
) -> bool:
    for declaration in declarations[:3]:
        distance = _candidate_distance_to_declaration(
            candidate,
            start_line=int(declaration.payload.get("start_line", 0)),
            end_line=int(declaration.payload.get("end_line", 0)),
        )
        if distance is None:
            continue
        if distance <= 20:
            return True
    return False


def _role_name_bias(role: str, name_lower: str) -> float:
    if not name_lower:
        return -1.0
    score = 0.0
    if len(name_lower) <= 3:
        score -= 2.0
    if name_lower in {"are", "for", "and", "or", "is", "of", "to", "annotation", "contains", "must"}:
        score -= 6.0
    hints = ROLE_NAME_HINTS.get(role, ())
    if hints:
        if any(hint in name_lower for hint in hints):
            score += 4.0
        else:
            score -= 1.5
    blocked = ROLE_NAME_BLOCKLIST.get(role, ())
    if blocked and any(value in name_lower for value in blocked):
        score -= 2.0
    return score


def _parse_line_range(line_range: str | None) -> tuple[int, int] | None:
    if not line_range:
        return None
    match = LINE_RANGE_PATTERN.match(str(line_range).strip())
    if match is None:
        return None
    start_line = int(match.group(1))
    end_line = int(match.group(2) or match.group(1))
    return start_line, end_line


def _ordered_unique(values: Sequence[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered
