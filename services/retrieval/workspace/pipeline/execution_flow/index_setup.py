from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from services.retrieval.workspace.bm25 import (
    DEFAULT_EXCLUDED_PATHS,
    build_index_from_repo,
    bm25_index_schema_version,
    indexable_content_signature,
    load_index,
    save_index,
)
from services.retrieval.workspace.pipeline.execution_flow.context import WorkspaceRetrievalContext
from services.retrieval.workspace.pipeline.index_flow import (
    load_sync_manifest as _load_sync_manifest,
    save_sync_manifest as _save_sync_manifest,
    sync_manifest_scope_matches as _sync_manifest_scope_matches,
)
from services.retrieval.workspace.tools import QdrantHybridSearchTool, codegraph_tools


@dataclass(frozen=True)
class IndexSetupResult:
    index: Any
    rebuilt: bool


def structural_tools(ctx: WorkspaceRetrievalContext) -> dict[str, Any]:
    tools, _bridge = codegraph_tools(ctx.config)
    return tools


def _index_scope_signature(ctx: WorkspaceRetrievalContext) -> dict[str, Any]:
    effective_exclude_paths = DEFAULT_EXCLUDED_PATHS if ctx.config.index_exclude_paths is None else ctx.config.index_exclude_paths
    lexical_ranking_profile = getattr(ctx.config, "lexical_ranking_profile", "flat_bm25")
    return {
        "index_schema_version": bm25_index_schema_version(lexical_ranking_profile),
        "lexical_ranking_profile": lexical_ranking_profile,
        "workspace_root": str(Path(ctx.config.workspace_root).resolve()),
        "content_signature": indexable_content_signature(
            ctx.config.workspace_root,
            exclude_paths=tuple(effective_exclude_paths),
        ),
        "exclude_paths": list(effective_exclude_paths),
        "chunk_line_count": ctx.config.chunk_line_count,
        "chunk_line_overlap": ctx.config.chunk_line_overlap,
    }


def _reuse_or_build_bm25_index(
    ctx: WorkspaceRetrievalContext,
    *,
    index_dir: Path,
    index_path: Path,
    scope_manifest_path: Path,
    scope_manifest: dict[str, Any],
    scope_signature: dict[str, Any],
    default_scope: bool,
) -> tuple[Any, bool]:
    legacy_default_scope = index_path.exists() and not scope_manifest and default_scope
    if index_path.exists() and (_sync_manifest_scope_matches(scope_manifest, scope_signature) or legacy_default_scope):
        index = load_index(index_dir)
        ctx.trace.record(
            "workspace_bm25_index_reused",
            {"document_count": len(index.documents), "lexical_ranking_profile": index.lexical_ranking_profile},
        )
        rebuilt = False
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
            lexical_ranking_profile=ctx.config.lexical_ranking_profile,
        )
        save_index(index, index_dir)
        _save_sync_manifest(scope_manifest_path, scope_signature)
        ctx.trace.record(
            "workspace_bm25_index_rebuilt",
            {"document_count": len(index.documents), "lexical_ranking_profile": index.lexical_ranking_profile},
        )
        rebuilt = True
    return index, rebuilt


def rebuild_index(ctx: WorkspaceRetrievalContext) -> IndexSetupResult:
    index_dir = Path(ctx.config.index_dir)
    index_path = index_dir / "bm25-index.json"
    scope_manifest_path = index_dir / "bm25-scope-manifest.json"
    scope_manifest = _load_sync_manifest(scope_manifest_path)
    scope_signature = _index_scope_signature(ctx)
    index, bm25_rebuilt = _reuse_or_build_bm25_index(
        ctx,
        index_dir=index_dir,
        index_path=index_path,
        scope_manifest_path=scope_manifest_path,
        scope_manifest=scope_manifest,
        scope_signature=scope_signature,
        default_scope=ctx.config.index_exclude_paths is None,
    )

    qdrant_tool = QdrantHybridSearchTool(
        index,
        qdrant_config=ctx.config.qdrant_config,
        embedding_config=ctx.config.embedding_config,
        cache_path=ctx.config.embedding_cache_path or str(index_dir / "qdrant-embeddings-cache.json"),
    )
    manifest_path = index_dir / "qdrant-sync-manifest.json"
    manifest = _load_sync_manifest(manifest_path)
    index_signature = qdrant_tool.backend.index_signature()
    collection_exists = qdrant_tool.backend.collection_exists()
    collection_current = (
        str(manifest.get("index_signature", "")) == index_signature
        and str(manifest.get("collection_name", "")) == ctx.config.qdrant_config.collection_name
        and collection_exists
        and qdrant_tool.backend.point_count() > 0
    )
    if collection_current:
        indexed_points = len(index.documents)
        qdrant_rebuilt = False
        ctx.trace.record("workspace_index_reused", {"document_count": len(index.documents), "indexed_points": indexed_points})
    else:
        if not ctx.config.enable_indexing:
            raise RuntimeError("Qdrant collection is not in sync while RETRIEVAL_ENABLE_INDEXING=false.")
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
        qdrant_rebuilt = True
        ctx.trace.record(
            "workspace_index_rebuilt",
            {
                "document_count": len(index.documents),
                "indexed_points": indexed_points,
                "reason": "missing_or_stale_qdrant_collection",
            },
        )
    rebuilt = bm25_rebuilt or qdrant_rebuilt
    ctx.trace.record(
        "workspace_index_ready",
        {
            "document_count": len(index.documents),
            "indexed_points": indexed_points,
            "rebuilt": rebuilt,
            "lexical_ranking_profile": index.lexical_ranking_profile,
            "collection_name": ctx.config.qdrant_config.collection_name,
        },
    )
    return IndexSetupResult(index=index, rebuilt=rebuilt)
