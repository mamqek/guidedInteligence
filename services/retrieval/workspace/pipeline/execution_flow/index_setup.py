from __future__ import annotations

# Owns workspace index/tool setup: CGC tool construction, BM25/Qdrant synchronization, and Step2 repository context hints. Do not place role retrieval, candidate validation, synthesis, or connected-source orchestration here.

from pathlib import Path
from typing import Any, Mapping

from services.retrieval.workspace.bm25 import DEFAULT_EXCLUDED_PATHS, build_index_from_repo, load_index, save_index
from services.retrieval.workspace.connected_context import ConnectedSourceContextResult
from services.retrieval.workspace.pipeline.execution_flow.context import WorkspaceRetrievalContext
from services.retrieval.workspace.pipeline.index_flow import (
    load_sync_manifest as _load_sync_manifest,
    save_sync_manifest as _save_sync_manifest,
    sync_manifest_scope_matches as _sync_manifest_scope_matches,
)
from services.retrieval.workspace.step2.common import merge_paths, ordered_unique
from services.retrieval.workspace.tools import (
    CGCAnalyzeCalleesTool,
    CGCAnalyzeCallersTool,
    CGCFindCodeTool,
    CGCIndexRepoTool,
    CGCQueryGraphTool,
    CGCRunCliTool,
    QdrantHybridSearchTool,
    ToolRequest,
)
from services.retrieval.workspace.tools.local import build_repo_sketch, file_role as tool_file_role


def cgc_tools(ctx: WorkspaceRetrievalContext) -> dict[str, Any]:
    return {
        "cgc_index_repo": CGCIndexRepoTool(ctx.config),
        "cgc_find_code": CGCFindCodeTool(ctx.config),
        "cgc_analyze_callers": CGCAnalyzeCallersTool(ctx.config),
        "cgc_analyze_callees": CGCAnalyzeCalleesTool(ctx.config),
        "cgc_query_graph": CGCQueryGraphTool(ctx.config),
        "cgc_run_cli": CGCRunCliTool(ctx.config),
    }


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
    cgc_find_tool: CGCFindCodeTool,
    index: Any,
    *,
    connected_context: ConnectedSourceContextResult | None = None,
) -> tuple[dict[str, Any], int]:
    repo_sketch = build_repo_sketch(index)
    confirmed_entities: list[str] = []
    confirmed_file_hints: list[str] = []
    anchor_examples: list[dict[str, Any]] = []
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
    for entity in entity_candidates[:8]:
        request = ToolRequest(
            tool_name="cgc_find_code",
            arguments={"query": entity, "limit": min(ctx.config.cgc_max_files_for_bm25, 8)},
            reason="Confirm whether a prompt or connected-source entity maps to implementation files before step-2 planning.",
        )
        observation = cgc_find_tool.run(request)
        ctx.trace.record_tool(request, observation, round_index=-1)
        tool_calls += 1
        implementation_files = [
            str(item.get("path", "")).strip().replace("\\", "/")
            for item in observation.payload.get("files", ())
            if isinstance(item, Mapping) and _is_step2_repo_path_allowed(str(item.get("path", "")))
        ]
        if implementation_files:
            confirmed_entities.append(entity)
            confirmed_file_hints = list(merge_paths(implementation_files[:3], confirmed_file_hints))
            anchor_examples.append(
                {
                    "entity": entity,
                    "files": implementation_files[:3],
                    "origin": "prompt"
                    if entity in prompt_evidence.grounded_entities
                    else "connected_source",
                    "source_ids": list(
                        connected_context.signal_provenance.get(f"symbol_hints:{entity}")
                        or connected_context.signal_provenance.get(f"retrieval_terms:{entity}")
                        or ()
                    ),
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
