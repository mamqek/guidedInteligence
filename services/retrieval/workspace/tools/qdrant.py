from __future__ import annotations

from typing import Any

from services.retrieval.workspace.bm25 import BM25Index
from services.retrieval.config import RetrievalEmbeddingConfig, RetrievalQdrantConfig
from services.retrieval.workspace.qdrant_backend import QdrantHybridBackend
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
        path = str(request.arguments.get("path", ""))
        paths = tuple(str(item) for item in request.arguments.get("paths", ()) if str(item).strip())
        min_score = float(request.arguments.get("min_score", 0.0) or 0.0)
        source_category = str(request.arguments.get("source_category", "source_code")).strip() or "source_code"
        file_role = str(request.arguments.get("file_role", "implementation")).strip() or "implementation"
        include_breakdown = bool(request.arguments.get("include_breakdown", True))
        try:
            results = self.backend.search(
                query,
                limit=limit,
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
                limit=limit,
                path=path,
                paths=paths,
                min_score=min_score,
                source_category=source_category,
                file_role=file_role,
            )
            include_breakdown = False
        if path:
            normalized = path.replace("\\", "/")
            results = tuple(result for result in results if result.chunk.path == normalized)
        if paths:
            normalized_paths = {str(item).replace("\\", "/") for item in paths}
            results = tuple(result for result in results if result.chunk.path in normalized_paths)
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
                "results": [_result_to_payload(result) for result in results],
                **breakdown_payload,
            },
            source_refs=tuple(result.chunk.chunk_id for result in results),
            metadata={
                "result_count": str(len(results)),
                "path_filter_count": str(len(paths)),
            },
        )


def qdrant_tool_specs() -> tuple[ToolSpec, ...]:
    return (
        ToolSpec(
            name="qdrant_hybrid_search",
            title="Qdrant Hybrid Chunk Search",
            description=(
                "Dense+sparse hybrid search over indexed repository chunks stored in Qdrant. "
                "Use for initial candidate discovery after CGC narrowing."
            ),
            arguments={
                "query": "Required string. Role- or issue-derived retrieval query.",
                "limit": "Optional integer from 1 to 50. Defaults to 12.",
                "path": "Optional relative repo path. Restricts search to one indexed file.",
                "paths": "Optional list of relative repo paths. Restricts search to a narrowed file set.",
                "min_score": "Optional number. Filters out fused results below this score.",
                "source_category": "Optional payload filter. Defaults to source_code.",
                "file_role": "Optional payload filter. Defaults to implementation.",
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
    }

