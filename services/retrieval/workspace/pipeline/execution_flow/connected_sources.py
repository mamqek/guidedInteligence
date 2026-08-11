from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from core.source_policy import SourceCategory
from services.retrieval.config import ConnectedSourceDocument
from services.retrieval.workspace.connected_context import (
    ConnectedSourceContextResult,
    ConnectedSourceContextSettings,
    ConnectedSourceContextStage,
    ConnectedSourceHandle,
)
from services.retrieval.workspace.mcp import LocalMCPConnectedSourceAdapter, RemoteMCPConnectedSourceAdapter
from services.retrieval.workspace.obsidian import ObsidianHybridSearchAdapter
from services.retrieval.workspace.pipeline.execution_flow.context import WorkspaceRetrievalContext


def collect_connected_context(
    ctx: WorkspaceRetrievalContext,
    *,
    query: str,
    prompt_evidence: dict[str, Any],
    allowed_sources: Sequence[SourceCategory],
) -> ConnectedSourceContextResult:
    if not ctx.config.connected_context_enabled:
        return ConnectedSourceContextResult()
    handles = _handles(ctx, allowed_sources)
    if not handles:
        return ConnectedSourceContextResult()
    stage = ConnectedSourceContextStage(
        llm_config=ctx.config.llm_config,
        settings=ConnectedSourceContextSettings(
            max_sources=ctx.config.connected_context_max_sources,
            max_calls=ctx.config.connected_context_max_calls,
            max_candidates_per_source=ctx.config.connected_context_max_candidates_per_source,
            max_candidates_total=ctx.config.connected_context_max_candidates_total,
            max_candidate_chars=ctx.config.connected_context_max_candidate_chars,
            max_candidate_chars_total=ctx.config.connected_context_max_candidate_chars_total,
            max_selected_context=ctx.config.connected_context_max_selected_context,
            max_selected_evidence=ctx.config.connected_context_max_selected_evidence,
            total_timeout_seconds=ctx.config.connected_context_timeout_seconds,
            disclaimer_required_terms=ctx.config.connected_context_disclaimer_required_terms,
            stale_block_terms=ctx.config.connected_context_stale_block_terms,
        ),
        log_event=lambda event_type, payload: ctx.trace.record(event_type, payload),
    )
    return stage.run(prompt=query, prompt_evidence=prompt_evidence, sources=handles)


def _handles(
    ctx: WorkspaceRetrievalContext,
    allowed_sources: Sequence[SourceCategory],
) -> tuple[ConnectedSourceHandle, ...]:
    allowed = set(allowed_sources)
    enabled = set(ctx.config.enabled_sources)
    handles: list[ConnectedSourceHandle] = []

    def add_static(source_key: str, provider: str, name: str, documents: Sequence[ConnectedSourceDocument]) -> None:
        selected = tuple(document for document in documents if document.source_category in allowed)
        if selected and (not enabled or source_key in enabled):
            handles.append(ConnectedSourceHandle(source_key, provider, name, lambda _query, values=selected: values))

    add_static("github_issues", "github", "GitHub issues", ctx.config.issue_tracker_documents)
    add_static("github_pull_requests", "github", "GitHub pull requests", ctx.config.pull_request_documents)
    add_static("notebooklm", "notebooklm", "NotebookLM", ctx.config.notebooklm_documents)

    if ctx.config.connected_source_adapters.get("remote_mcp", True):
        for config in ctx.config.remote_mcp_connected_sources:
            if config.enabled and config.source_category in allowed and (not enabled or config.source_key in enabled):
                handles.append(
                    ConnectedSourceHandle(
                        config.source_key,
                        config.provider,
                        config.name,
                        lambda source_query, value=config: RemoteMCPConnectedSourceAdapter(value).search(source_query),
                        scope=config.scope,
                        metadata={"features": dict(config.features)},
                    )
                )
    if ctx.config.connected_source_adapters.get("mcp", True):
        for config in ctx.config.mcp_connected_sources:
            if config.source_category in allowed and (not enabled or config.source_key in enabled):
                handles.append(
                    ConnectedSourceHandle(
                        config.source_key,
                        "local_mcp",
                        config.name,
                        lambda source_query, value=config: LocalMCPConnectedSourceAdapter(value).search(source_query),
                    )
                )

    if SourceCategory.LOCAL_NOTES in allowed and (not enabled or "local_notes" in enabled):
        note_paths = tuple(Path(value) for value in ctx.config.local_note_paths)
        obsidian = (
            ObsidianHybridSearchAdapter(
                vault_path=ctx.config.obsidian_vault_path,
                command=ctx.config.obsidian_command,
                db_path=ctx.config.obsidian_db_path,
                mode=ctx.config.obsidian_search_mode,
                timeout_seconds=ctx.config.obsidian_timeout_seconds,
            )
            if ctx.config.obsidian_vault_path
            else None
        )

        def read_notes(query: str) -> tuple[ConnectedSourceDocument, ...]:
            documents: list[ConnectedSourceDocument] = []
            for path in note_paths:
                if not path.is_file():
                    continue
                documents.append(
                    ConnectedSourceDocument(
                        source_category=SourceCategory.LOCAL_NOTES,
                        source_id=path.as_posix(),
                        title=path.name,
                        content=path.read_text(encoding="utf-8", errors="replace"),
                        metadata={"path": path.as_posix(), "source_key": "local_notes"},
                        source_key="local_notes",
                    )
                )
            if obsidian is not None:
                for result in obsidian.search(query, limit=ctx.config.obsidian_search_limit):
                    documents.append(
                        ConnectedSourceDocument(
                            source_category=SourceCategory.LOCAL_NOTES,
                            source_id=f"obsidian:{result.path}",
                            title=result.title or Path(result.path).name,
                            content=result.content or result.snippet,
                            metadata={
                                "path": result.path,
                                "score": result.score,
                                "source_key": "local_notes",
                                **dict(result.metadata or {}),
                            },
                            source_key="local_notes",
                        )
                    )
            return tuple(documents)

        if note_paths or obsidian is not None:
            handles.append(ConnectedSourceHandle("local_notes", "obsidian", "Local notes", read_notes))
    return tuple(handles)
