from __future__ import annotations

from typing import Any

from services.retrieval.workspace.bm25 import BM25Index
from services.retrieval.workspace.qdrant_backend import QdrantHybridBackend, QdrantSearchResult
from services.retrieval.config import RetrievalEmbeddingConfig, RetrievalQdrantConfig
from services.retrieval.workspace.tools.contracts import ToolObservation, ToolRequest, ToolSpec


class QdrantHybridSearchTool:
    name = "qdrant_hybrid_search"

    def __init__(
        self,
        index: BM25Index,
        *,
        qdrant_config: RetrievalQdrantConfig,
        embedding_config: RetrievalEmbeddingConfig,
        cache_path: str | None = None,
    ) -> None:
        self.index = index
        self.backend = QdrantHybridBackend(
            index=index,
            qdrant_config=qdrant_config,
            embedding_config=embedding_config,
            cache_path=cache_path,
        )

    def run(self, request: ToolRequest) -> ToolObservation:
        query = str(request.arguments.get("query", ""))
        limit = max(1, min(int(request.arguments.get("limit", 12) or 12), 50))
        max_per_path = max(0, min(int(request.arguments.get("max_per_path", 0) or 0), 10))
        search_limit = min(50, max(limit, limit * 4)) if max_per_path else limit
        path = str(request.arguments.get("path", ""))
        paths = tuple(str(item) for item in request.arguments.get("paths", ()) if str(item).strip())
        preferred_ranges = tuple(
            dict(item)
            for item in request.arguments.get("preferred_ranges", ())
            if isinstance(item, dict) and str(item.get("path") or "").strip()
        )
        preferred_paths = tuple(
            dict(item)
            for item in request.arguments.get("preferred_paths", ())
            if isinstance(item, dict) and str(item.get("path") or "").strip()
        )
        min_score = float(request.arguments.get("min_score", 0.0) or 0.0)
        source_category = str(request.arguments.get("source_category", "source_code")).strip() or "source_code"
        requested_file_role = str(request.arguments.get("file_role", "implementation")).strip()
        file_role = "" if requested_file_role == "any" else (requested_file_role or "implementation")
        include_breakdown = bool(request.arguments.get("include_breakdown", True))
        try:
            results = self.backend.search(
                query,
                limit=search_limit,
                path=path,
                paths=paths,
                min_score=min_score,
                source_category=source_category,
                file_role=file_role,
                include_breakdown=include_breakdown,
            )
        except TypeError as exc:
            if "include_breakdown" not in str(exc):
                raise
            results = self.backend.search(
                query,
                limit=search_limit,
                path=path,
                paths=paths,
                min_score=min_score,
                source_category=source_category,
                file_role=file_role,
            )
            include_breakdown = False
        results = _include_preferred_range_results(results, self.index, preferred_ranges)
        if path:
            normalized = path.replace("\\", "/")
            results = tuple(result for result in results if result.chunk.path == normalized)
        if paths:
            normalized_paths = {str(item).replace("\\", "/") for item in paths}
            results = tuple(result for result in results if result.chunk.path in normalized_paths)
        results = _prioritize_preferred_paths(results, preferred_paths)
        results = _prioritize_preferred_ranges(results, preferred_ranges)
        results = _limit_results_per_path(results, limit=limit, max_per_path=max_per_path)
        breakdown_payload: dict[str, Any] = {}
        if include_breakdown:
            breakdown = self.backend.last_search_breakdown() or {}
            breakdown_payload = {
                "breakdown": {
                    label: [_result_to_payload(result) for result in values]
                    for label, values in breakdown.items()
                }
            }
        return ToolObservation(
            tool_name=self.name,
            status="ok",
            payload={
                "query": query,
                "path": path,
                "paths": list(paths),
                "preferred_ranges": [dict(item) for item in preferred_ranges],
                "preferred_paths": [dict(item) for item in preferred_paths],
                "results": [_result_to_payload(result) for result in results],
                **breakdown_payload,
            },
            source_refs=tuple(result.chunk.chunk_id for result in results),
            metadata={
                "result_count": str(len(results)),
                "path_filter_count": str(len(paths)),
                "max_per_path": str(max_per_path),
            },
        )


def qdrant_tool_specs() -> tuple[ToolSpec, ...]:
    return (
        ToolSpec(
            name="qdrant_hybrid_search",
            title="Qdrant Hybrid Chunk Search",
            description=(
                "Dense+sparse hybrid search over indexed repository chunks stored in Qdrant. "
                "Use for conceptual candidate discovery, optionally boosted by exact-symbol CodeGraph narrowing."
            ),
            arguments={
                "query": "Required string. Role- or issue-derived retrieval query.",
                "limit": "Optional integer from 1 to 50. Defaults to 12.",
                "path": "Optional relative repo path. Restricts search to one indexed file.",
                "paths": "Optional list of relative repo paths. Restricts search to a narrowed file set.",
                "preferred_ranges": "Optional CodeGraph target ranges to prioritize within the semantic result set.",
                "preferred_paths": "Optional graph-connected paths with structural scores used to rerank semantic results.",
                "max_per_path": "Optional positive integer. Diversifies results across files before applying the final limit.",
                "min_score": "Optional number. Filters out fused results below this score.",
                "source_category": "Optional payload filter. Defaults to source_code.",
                "file_role": "Optional payload filter. Defaults to implementation; use any to search every file role.",
                "include_breakdown": "Optional boolean. Defaults to true and includes sparse-only, dense-only, and hybrid top-k results in the payload.",
            },
            examples=(
                {
                    "tool_name": "qdrant_hybrid_search",
                    "arguments": {"query": "abstract class checker validation", "limit": 12},
                    "reason": "Find semantically and lexically relevant chunks for abstract-class enforcement logic.",
                },
            ),
        ),
    )


def _result_to_payload(result: Any) -> dict[str, Any]:
    chunk = result.chunk
    return {
        "chunk_id": chunk.chunk_id,
        "source_category": chunk.source_category.value,
        "snapshot": chunk.snapshot,
        "commit": chunk.commit,
        "path": chunk.path,
        "line_start": chunk.line_start,
        "line_end": chunk.line_end,
        "line_range": "" if chunk.line_start is None or chunk.line_end is None else f"L{chunk.line_start}-L{chunk.line_end}",
        "text": chunk.text,
        "score": result.score,
        "matched_terms": list(result.matched_terms),
        "visibility": str(chunk.metadata.get("visibility", "")),
        "file_role": str(chunk.metadata.get("file_role", "")),
    }


def _limit_results_per_path(results: tuple[Any, ...], *, limit: int, max_per_path: int) -> tuple[Any, ...]:
    if max_per_path <= 0:
        return tuple(results[:limit])
    counts: dict[str, int] = {}
    selected: list[Any] = []
    for result in results:
        path = str(result.chunk.path)
        if counts.get(path, 0) >= max_per_path:
            continue
        counts[path] = counts.get(path, 0) + 1
        selected.append(result)
        if len(selected) >= limit:
            break
    return tuple(selected)


def _include_preferred_range_results(
    results: tuple[Any, ...],
    index: BM25Index,
    preferred_ranges: tuple[dict[str, Any], ...],
) -> tuple[Any, ...]:
    if not preferred_ranges:
        return results
    existing_ids = {str(result.chunk.chunk_id) for result in results}
    maximum_score = max((float(result.score) for result in results), default=1.0)
    pinned: list[QdrantSearchResult] = []
    for preferred in preferred_ranges:
        preferred_path = str(preferred.get("path") or "").replace("\\", "/")
        preferred_start = int(preferred.get("line_start") or 0)
        preferred_end = int(preferred.get("line_end") or preferred_start)
        matches = [
            document.chunk
            for document in index.documents
            if document.chunk.path == preferred_path
            and int(document.chunk.line_start or 0) <= preferred_end
            and int(document.chunk.line_end or 0) >= preferred_start
        ]
        if not matches:
            continue
        chunk = min(
            matches,
            key=lambda item: (
                abs(int(item.line_start or 0) - preferred_start),
                int(item.line_end or 0) - int(item.line_start or 0),
            ),
        )
        if chunk.chunk_id in existing_ids:
            continue
        existing_ids.add(chunk.chunk_id)
        pinned.append(
            QdrantSearchResult(
                chunk=chunk,
                score=maximum_score,
                matched_terms=(),
                retrieval_path="codegraph_preferred_range",
            )
        )
    return tuple((*pinned, *results))


def _prioritize_preferred_ranges(
    results: tuple[Any, ...],
    preferred_ranges: tuple[dict[str, Any], ...],
) -> tuple[Any, ...]:
    if not preferred_ranges:
        return results
    normalized = tuple(
        (
            str(item.get("path") or "").replace("\\", "/"),
            int(item.get("line_start") or 0),
            int(item.get("line_end") or item.get("line_start") or 0),
        )
        for item in preferred_ranges
    )

    def priority(result: Any) -> int:
        path = str(result.chunk.path).replace("\\", "/")
        start = int(result.chunk.line_start or 0)
        end = int(result.chunk.line_end or start)
        return 0 if any(
            path == preferred_path and start <= preferred_end and end >= preferred_start
            for preferred_path, preferred_start, preferred_end in normalized
        ) else 1

    return tuple(
        item[1]
        for item in sorted(enumerate(results), key=lambda item: (priority(item[1]), item[0]))
    )


def _prioritize_preferred_paths(
    results: tuple[Any, ...],
    preferred_paths: tuple[dict[str, Any], ...],
) -> tuple[Any, ...]:
    if not preferred_paths:
        return results
    raw_scores = {
        str(item.get("path") or "").replace("\\", "/"): max(0.0, float(item.get("score") or 0.0))
        for item in preferred_paths
    }
    maximum = max(raw_scores.values(), default=0.0)
    if maximum <= 0:
        return results
    maximum_semantic = max((max(0.0, float(result.score)) for result in results), default=0.0)

    def combined_score(result: Any) -> float:
        path = str(result.chunk.path).replace("\\", "/")
        graph_score = raw_scores.get(path, 0.0) / maximum
        semantic_score = max(0.0, float(result.score)) / maximum_semantic if maximum_semantic else 0.0
        return (semantic_score * 0.72) + (graph_score * 0.28)

    return tuple(
        item[1]
        for item in sorted(enumerate(results), key=lambda item: (-combined_score(item[1]), item[0]))
    )
