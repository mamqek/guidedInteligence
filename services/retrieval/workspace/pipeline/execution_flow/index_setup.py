from __future__ import annotations

# Owns workspace index/tool setup: CodeGraph tool construction, BM25/Qdrant synchronization, and Step2 repository context hints. Do not place role retrieval, candidate validation, synthesis, or connected-source orchestration here.

from pathlib import Path
from typing import Any, Mapping, Sequence

from services.retrieval.workspace.bm25 import DEFAULT_EXCLUDED_PATHS, build_index_from_repo, load_index, save_index
from services.retrieval.workspace.connected_context import ConnectedSourceContextResult
from services.retrieval.workspace.pipeline.execution_flow.context import WorkspaceRetrievalContext
from services.retrieval.workspace.pipeline.index_flow import (
    load_sync_manifest as _load_sync_manifest,
    save_sync_manifest as _save_sync_manifest,
    sync_manifest_scope_matches as _sync_manifest_scope_matches,
)
from services.retrieval.workspace.step2.common import merge_paths, ordered_unique
from services.retrieval.workspace.tools import QdrantHybridSearchTool, ToolRequest, codegraph_tools
from services.retrieval.workspace.tools.local import build_repo_sketch, file_role as tool_file_role


def structural_tools(ctx: WorkspaceRetrievalContext) -> dict[str, Any]:
    tools, _bridge = codegraph_tools(ctx.config)
    return tools


def rebuild_index(ctx: WorkspaceRetrievalContext) -> Any:
    index_dir = Path(ctx.config.index_dir)
    index_path = index_dir / "bm25-index.json"
    scope_manifest_path = index_dir / "bm25-scope-manifest.json"
    scope_manifest = _load_sync_manifest(scope_manifest_path)
    effective_exclude_paths = (
        DEFAULT_EXCLUDED_PATHS if ctx.config.index_exclude_paths is None else ctx.config.index_exclude_paths
    )
    scope_signature = {
        "workspace_root": str(Path(ctx.config.workspace_root).resolve()),
        "exclude_paths": list(effective_exclude_paths),
        "chunk_line_count": ctx.config.chunk_line_count,
        "chunk_line_overlap": ctx.config.chunk_line_overlap,
    }
    default_scope = ctx.config.index_exclude_paths is None
    legacy_default_scope = index_path.exists() and not scope_manifest and default_scope
    if index_path.exists() and (_sync_manifest_scope_matches(scope_manifest, scope_signature) or legacy_default_scope):
        index = load_index(index_dir)
        ctx.trace.record(
            "workspace_bm25_index_reused",
            {
                "workspace_root": ctx.config.workspace_root,
                "index_dir": ctx.config.index_dir,
                "document_count": len(index.documents),
            },
        )
    else:
        if not ctx.config.enable_indexing:
            raise RuntimeError(f"Missing BM25 index while RETRIEVAL_ENABLE_INDEXING=false: {index_path}")
        index = build_index_from_repo(
            repo_path=ctx.config.workspace_root,
            commit="workspace",
            chunk_line_count=ctx.config.chunk_line_count,
            chunk_line_overlap=ctx.config.chunk_line_overlap,
            snapshot="workspace_current",
            visibility="workspace_visible",
            origin="workspace_index",
            exclude_paths=ctx.config.index_exclude_paths,
        )
        save_index(index, index_dir)
        _save_sync_manifest(scope_manifest_path, scope_signature)
        ctx.trace.record(
            "workspace_bm25_index_rebuilt",
            {
                "workspace_root": ctx.config.workspace_root,
                "index_dir": ctx.config.index_dir,
                "document_count": len(index.documents),
            },
        )
    qdrant_tool = QdrantHybridSearchTool(
        index,
        qdrant_config=ctx.config.qdrant_config,
        embedding_config=ctx.config.embedding_config,
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
        and collection_name == ctx.config.qdrant_config.collection_name
        and collection_exists
        and point_count > 0
    ):
        indexed_points = len(index.documents)
        ctx.trace.record(
            "workspace_index_reused",
            {
                "workspace_root": ctx.config.workspace_root,
                "index_dir": ctx.config.index_dir,
                "document_count": len(index.documents),
                "qdrant_collection": ctx.config.qdrant_config.collection_name,
                "indexed_points": indexed_points,
                "collection_point_count": point_count,
            },
        )
    else:
        if not ctx.config.enable_indexing:
            raise RuntimeError(
                "Qdrant collection is not in sync while RETRIEVAL_ENABLE_INDEXING=false. "
                "Re-enable indexing once to rebuild the collection."
            )
        indexed_points = qdrant_tool.backend.rebuild_collection(
            log_event=lambda event_type, payload: ctx.trace.record(event_type, payload),
            timeout_seconds=ctx.config.qdrant_index_timeout_seconds,
        )
        _save_sync_manifest(
            manifest_path,
            {
                "collection_name": ctx.config.qdrant_config.collection_name,
                "document_count": len(index.documents),
                "index_signature": index_signature,
            },
        )
    ctx.trace.record(
        "workspace_index_rebuilt",
        {
            "workspace_root": ctx.config.workspace_root,
            "index_dir": ctx.config.index_dir,
            "document_count": len(index.documents),
            "qdrant_collection": ctx.config.qdrant_config.collection_name,
            "indexed_points": indexed_points,
            "reindex_policy": ctx.config.reindex_policy,
        },
    )
    return index


def build_step2_repo_context(
    ctx: WorkspaceRetrievalContext,
    prompt_evidence: Any,
    structural_search_tool: Any,
    index: Any,
    *,
    connected_context: ConnectedSourceContextResult | None = None,
) -> tuple[dict[str, Any], int]:
    repo_sketch = build_repo_sketch(index)
    confirmed_entities: list[str] = []
    confirmed_file_hints: list[str] = []
    anchor_examples: list[dict[str, Any]] = []
    candidate_anchor_examples: list[dict[str, Any]] = []
    tool_calls = 0
    connected_context = connected_context or ConnectedSourceContextResult()
    indexed_paths = {document.chunk.path for document in index.documents}
    workspace_root = Path(ctx.config.workspace_root)
    for path in connected_context.file_hints:
        normalized = path.strip().replace("\\", "/").lstrip("/")
        if normalized and (normalized in indexed_paths or (workspace_root / normalized).is_file()):
            confirmed_file_hints.append(normalized)

    entity_candidates = ordered_unique(
        (
            *prompt_evidence.grounded_entities,
            *connected_context.symbol_hints,
            *connected_context.retrieval_terms,
        )
    )
    selected_entities = entity_candidates[:8]
    search_results: Sequence[Any] = ()
    if selected_entities:
        request = ToolRequest(
            tool_name="structural_search_symbols",
            arguments={"queries": list(selected_entities), "limit_per_query": min(ctx.config.structural_graph_max_files, 8)},
            reason="Rank prompt and connected-source terms against repository symbols before step-2 planning.",
        )
        observation = structural_search_tool.run(request)
        ctx.trace.record_tool(request, observation, round_index=-1)
        tool_calls += 1
        if observation.status == "ok" and isinstance(observation.payload.get("results"), Sequence):
            search_results = observation.payload.get("results", ())

    result_by_query = {
        str(item.get("query", "")).strip(): item
        for item in search_results
        if isinstance(item, Mapping) and str(item.get("query", "")).strip()
    }
    for entity in selected_entities:
        result = result_by_query.get(entity, {})
        matches = [
            item
            for item in result.get("matches", ())
            if isinstance(item, Mapping) and _is_step2_repo_path_allowed(str(item.get("path", "")))
        ] if isinstance(result, Mapping) else []
        confirmed_matches = [item for item in matches if bool(item.get("confirmed"))]
        candidate_matches = [item for item in matches if not bool(item.get("confirmed"))]
        confirmed_files = list(
            ordered_unique(str(item.get("path", "")).strip().replace("\\", "/") for item in confirmed_matches)
        )[:3]
        origin = "prompt" if entity in prompt_evidence.grounded_entities else "connected_source"
        source_ids = list(
            connected_context.signal_provenance.get(f"symbol_hints:{entity}")
            or connected_context.signal_provenance.get(f"retrieval_terms:{entity}")
            or ()
        )
        if confirmed_files:
            confirmed_entities.append(entity)
            confirmed_file_hints = list(merge_paths(confirmed_files, confirmed_file_hints))
            anchor_examples.append(
                {
                    "entity": entity,
                    "files": confirmed_files,
                    "matches": [_anchor_match_payload(item) for item in confirmed_matches[:3]],
                    "origin": origin,
                    "source_ids": source_ids,
                }
            )
        if candidate_matches:
            candidate_anchor_examples.append(
                {
                    "entity": entity,
                    "matches": [_anchor_match_payload(item) for item in candidate_matches[:3]],
                    "origin": origin,
                    "source_ids": source_ids,
                }
            )
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
            "candidate_anchor_examples": candidate_anchor_examples[:6],
            "connected_context": {
                "retrieval_terms": list(connected_context.retrieval_terms),
                "file_hints": list(connected_context.file_hints),
                "symbol_hints": list(connected_context.symbol_hints),
                "suggested_subqueries": list(connected_context.suggested_subqueries),
                "facts": [fact.to_dict() for fact in connected_context.facts],
                "conflicts": [conflict.to_dict() for conflict in connected_context.conflicts],
                "selected_context_ids": list(connected_context.selected_context_ids),
            },
        },
        tool_calls,
    )


def _is_step2_repo_path_allowed(path: str) -> bool:
    role = tool_file_role(path)
    return role in {"implementation", "documentation"}


def _anchor_match_payload(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "symbol": str(item.get("qualified_name") or item.get("name") or ""),
        "file": str(item.get("path") or "").replace("\\", "/"),
        "kind": str(item.get("kind") or ""),
        "line_start": int(item.get("line_start") or 0),
        "line_end": int(item.get("line_end") or 0),
        "match_type": str(item.get("match_type") or ""),
        "matched_words": [str(value) for value in item.get("matched_words", ())],
        "search_score": item.get("search_score"),
    }
