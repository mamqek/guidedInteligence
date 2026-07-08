from __future__ import annotations

# Owns connected and external context sources: configured documents, MCP/remote adapters, Notebook/local note payloads, Obsidian search, and note-derived file guidance. Do not place code retrieval, candidate validation, ranking, or synthesis policy here.

import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

from core.source_policy import SourceCategory
from services.retrieval.config import ConnectedSourceDocument
from services.retrieval.workspace.connected_context import (
    ConnectedSourceContextResult,
    ConnectedSourceContextSettings,
    ConnectedSourceContextStage,
    ConnectedSourceHandle,
)
from services.retrieval.workspace.mcp import (
    LocalMCPConnectedSourceAdapter,
    MCPConnectedSourceError,
    RemoteMCPConnectedSourceAdapter,
    RemoteMCPConnectedSourceError,
)
from services.retrieval.workspace.obsidian import (
    ObsidianHybridSearchAdapter,
    ObsidianSearchError,
    ObsidianSearchResult,
    trusted_file_hints_from_obsidian_results,
)
from services.retrieval.workspace.pipeline.execution_flow.context import WorkspaceRetrievalContext
from services.retrieval.workspace.pipeline.file_level import obsidian_source_queries as _obsidian_source_queries
from services.retrieval.workspace.step2 import WorkspaceRetrievalPlan
from services.retrieval.workspace.step2.common import ordered_unique


def connected_source_context(
    ctx: WorkspaceRetrievalContext,
        *,
        query: str,
        prompt_evidence: Mapping[str, Any],
        allowed_sources: Sequence[SourceCategory],
    ) -> ConnectedSourceContextResult:
        if not ctx.config.connected_context_enabled:
            return ConnectedSourceContextResult()
        handles = connected_source_handles(ctx, allowed_sources)
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
            ),
            log_event=lambda event_type, payload: ctx.trace.record(event_type, payload),
        )
        return stage.run(prompt=query, prompt_evidence=prompt_evidence, sources=handles)


def connected_source_handles(
    ctx: WorkspaceRetrievalContext,
        allowed_sources: Sequence[SourceCategory],
    ) -> tuple[ConnectedSourceHandle, ...]:
        enabled_source_keys = set(ctx.config.enabled_sources)
        searchers: dict[str, list[Any]] = {}
        descriptors: dict[str, dict[str, Any]] = {}

        def source_enabled(source_key: str) -> bool:
            return source_key in enabled_source_keys

        def add_source(
            *,
            source_key: str,
            provider: str,
            name: str,
            category: SourceCategory,
            search: Any,
            scope: str = "",
            metadata: Mapping[str, Any] | None = None,
        ) -> None:
            if not source_key or not source_enabled(source_key):
                return
            searchers.setdefault(source_key, []).append(search)
            descriptors.setdefault(
                source_key,
                {
                    "provider": provider,
                    "name": name,
                    "scope": scope,
                    "metadata": dict(metadata or {}),
                },
            )

        def static_search(documents: Sequence[ConnectedSourceDocument]) -> Any:
            selected = tuple(documents)
            return lambda _query: selected

        if ctx.config.issue_tracker_documents:
            add_source(
                source_key="github_issues",
                provider="github",
                name="GitHub issues",
                category=SourceCategory.ISSUE_TRACKER,
                search=static_search(ctx.config.issue_tracker_documents),
            )
        if ctx.config.pull_request_documents:
            add_source(
                source_key="github_pull_requests",
                provider="github",
                name="GitHub pull requests",
                category=SourceCategory.PULL_REQUEST,
                search=static_search(ctx.config.pull_request_documents),
            )
        if ctx.config.notebooklm_documents:
            add_source(
                source_key="notebooklm",
                provider="notebooklm",
                name="NotebookLM",
                category=SourceCategory.NOTEBOOKLM,
                search=static_search(ctx.config.notebooklm_documents),
            )

        if ctx.config.connected_source_adapters.get("remote_mcp", True):
            for source_config in ctx.config.remote_mcp_connected_sources:
                if not source_config.enabled:
                    continue
                add_source(
                    source_key=source_config.source_key,
                    provider=source_config.provider,
                    name=source_config.name,
                    category=source_config.source_category,
                    scope=source_config.scope,
                    metadata={"features": dict(source_config.features)},
                    search=lambda source_query, config=source_config: RemoteMCPConnectedSourceAdapter(config).search(source_query),
                )

        if ctx.config.connected_source_adapters.get("mcp", True):
            for source_config in ctx.config.mcp_connected_sources:
                add_source(
                    source_key=source_config.source_key,
                    provider="local_mcp",
                    name=source_config.name,
                    category=source_config.source_category,
                    search=lambda source_query, config=source_config: LocalMCPConnectedSourceAdapter(config).search(source_query),
                )

        if (
            ctx.config.connected_source_adapters.get("local_notes", True)
            and ctx.config.obsidian_vault_path
            and Path(ctx.config.obsidian_vault_path).exists()
        ):
            def search_obsidian(source_query: str) -> tuple[ConnectedSourceDocument, ...]:
                results = search_obsidian_notes(ctx, source_query, allowed_sources)
                return tuple(
                    obsidian_result_to_connected_document(ctx, result)
                    for result in results
                    if result.score >= ctx.config.obsidian_min_guidance_score
                )

            add_source(
                source_key="local_notes",
                provider="obsidian",
                name="Obsidian local notes",
                category=SourceCategory.LOCAL_NOTES,
                search=search_obsidian,
                scope=ctx.config.obsidian_vault_path,
            )

        if ctx.config.local_note_paths:
            def search_local_note_paths(_source_query: str) -> tuple[ConnectedSourceDocument, ...]:
                documents: list[ConnectedSourceDocument] = []
                for raw_path in ctx.config.local_note_paths:
                    path = Path(raw_path)
                    if not path.is_file():
                        continue
                    try:
                        content = path.read_text(encoding="utf-8")
                    except UnicodeDecodeError:
                        continue
                    documents.append(
                        ConnectedSourceDocument(
                            source_category=SourceCategory.LOCAL_NOTES,
                            source_id=path.as_posix(),
                            title=path.name,
                            content=content,
                            metadata={"path": path.as_posix(), "source_key": "local_notes"},
                            source_key="local_notes",
                        )
                    )
                return tuple(documents)

            add_source(
                source_key="local_notes",
                provider="local_files",
                name="Local notes",
                category=SourceCategory.LOCAL_NOTES,
                search=search_local_note_paths,
            )

        handles: list[ConnectedSourceHandle] = []
        for source_key, source_searchers in searchers.items():
            descriptor = descriptors[source_key]

            def merged_search(source_query: str, runners=tuple(source_searchers)) -> tuple[ConnectedSourceDocument, ...]:
                documents: list[ConnectedSourceDocument] = []
                for runner in runners:
                    documents.extend(runner(source_query))
                return tuple(documents)

            handles.append(
                ConnectedSourceHandle(
                    source_key=source_key,
                    provider=str(descriptor["provider"]),
                    name=str(descriptor["name"]),
                    search=merged_search,
                    scope=str(descriptor["scope"]),
                    metadata=dict(descriptor["metadata"]),
                )
            )
        return tuple(handles)


def connected_documents(
    ctx: WorkspaceRetrievalContext,
        query: str = "",
        allowed_sources: Sequence[SourceCategory] = (),
    ) -> tuple[ConnectedSourceDocument, ...]:
        documents: list[ConnectedSourceDocument] = []
        enabled_source_keys = set(ctx.config.enabled_sources)
        if not enabled_source_keys or "issue_tracker" in enabled_source_keys:
            documents.extend(ctx.config.issue_tracker_documents)
        if not enabled_source_keys or "pull_request" in enabled_source_keys:
            documents.extend(ctx.config.pull_request_documents)
        if not enabled_source_keys or "notebooklm" in enabled_source_keys:
            documents.extend(ctx.config.notebooklm_documents)
        if query and ctx.config.connected_source_adapters.get("remote_mcp", True):
            for source_config in ctx.config.remote_mcp_connected_sources:
                if not source_config.enabled:
                    continue
                if enabled_source_keys and source_config.source_key not in enabled_source_keys:
                    continue
                adapter = RemoteMCPConnectedSourceAdapter(source_config)
                try:
                    source_documents = adapter.search(query)
                except RemoteMCPConnectedSourceError as exc:
                    ctx.trace.record(
                        "remote_mcp_connected_source_failed",
                        {
                            "adapter": "remote_mcp",
                            "provider": source_config.provider,
                            "source_name": source_config.name,
                            "source_key": source_config.source_key,
                            "source_category": source_config.source_category.value,
                            "endpoint_url": source_config.endpoint_url,
                            "tool_name": source_config.query_tool_name,
                            "reason": str(exc)[:400],
                        },
                    )
                    continue
                documents.extend(source_documents)
                ctx.trace.record(
                    "remote_mcp_connected_source_searched",
                    {
                        "adapter": "remote_mcp",
                        "provider": source_config.provider,
                        "source_name": source_config.name,
                        "source_key": source_config.source_key,
                        "source_category": source_config.source_category.value,
                        "endpoint_url": source_config.endpoint_url,
                        "tool_name": source_config.query_tool_name,
                        "result_count": len(source_documents),
                        "source_refs": [document.source_id for document in source_documents],
                    },
                )
        if query and ctx.config.connected_source_adapters.get("mcp", True):
            for source_config in ctx.config.mcp_connected_sources:
                if enabled_source_keys and source_config.source_key not in enabled_source_keys:
                    continue
                adapter = LocalMCPConnectedSourceAdapter(source_config)
                try:
                    source_documents = adapter.search(query)
                except MCPConnectedSourceError as exc:
                    ctx.trace.record(
                        "mcp_connected_source_failed",
                        {
                            "adapter": "mcp",
                            "source_name": source_config.name,
                            "source_key": source_config.source_key,
                            "source_category": source_config.source_category.value,
                            "tool_name": source_config.query_tool_name,
                            "reason": str(exc)[:400],
                        },
                    )
                    continue
                documents.extend(source_documents)
                ctx.trace.record(
                    "mcp_connected_source_searched",
                    {
                        "adapter": "mcp",
                        "source_name": source_config.name,
                        "source_key": source_config.source_key,
                        "source_category": source_config.source_category.value,
                        "tool_name": source_config.query_tool_name,
                        "result_count": len(source_documents),
                        "source_refs": [document.source_id for document in source_documents],
                    },
                )
        for note_path in ctx.config.local_note_paths:
            if enabled_source_keys and "local_notes" not in enabled_source_keys:
                break
            path = Path(note_path)
            if not path.exists() or not path.is_file():
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            documents.append(
                ConnectedSourceDocument(
                    source_category=SourceCategory.LOCAL_NOTES,
                    source_id=path.as_posix(),
                    title=path.name,
                    content=content,
                    metadata={"path": path.as_posix(), "source_key": "local_notes"},
                    source_key="local_notes",
                )
            )
        return tuple(documents)


def search_obsidian_notes(
    ctx: WorkspaceRetrievalContext,
        query: str,
        allowed_sources: Sequence[SourceCategory],
    ) -> tuple[ObsidianSearchResult, ...]:
        if ctx.config.enabled_sources and "local_notes" not in ctx.config.enabled_sources:
            return ()
        if SourceCategory.LOCAL_NOTES not in allowed_sources:
            return ()
        if not ctx.config.connected_source_adapters.get("local_notes", True):
            return ()
        if not ctx.config.obsidian_vault_path:
            return ()
        vault_path = Path(ctx.config.obsidian_vault_path)
        if not vault_path.exists():
            return ()
        if ctx.config.obsidian_db_path and not Path(ctx.config.obsidian_db_path).exists():
            return ()
        adapter = ObsidianHybridSearchAdapter(
            vault_path=str(vault_path),
            command=ctx.config.obsidian_command,
            db_path=ctx.config.obsidian_db_path,
            mode=ctx.config.obsidian_search_mode,
            timeout_seconds=ctx.config.obsidian_timeout_seconds,
        )
        try:
            results = ()
            for obsidian_query in _obsidian_source_queries(query):
                results = adapter.search(obsidian_query, limit=ctx.config.obsidian_search_limit)
                if results:
                    break
        except (ObsidianSearchError, OSError, subprocess.SubprocessError) as exc:
            ctx.trace.record(
                "trusted_local_notes_search_failed",
                {
                    "adapter": "obsidian-hybrid-search",
                    "vault_path": str(vault_path),
                    "reason": str(exc)[:400],
                },
            )
            return ()
        ctx.trace.record(
            "trusted_local_notes_searched",
            {
                "adapter": "obsidian-hybrid-search",
                "vault_path": str(vault_path),
                "result_count": len(results),
                "queries": list(_obsidian_source_queries(query)),
                "results": [{"path": result.path, "title": result.title, "score": result.score} for result in results],
            },
        )
        return results


def obsidian_result_to_connected_document(ctx: WorkspaceRetrievalContext, result: ObsidianSearchResult) -> ConnectedSourceDocument:
        return ConnectedSourceDocument(
            source_category=SourceCategory.LOCAL_NOTES,
            source_id=f"obsidian:{result.path}",
            title=result.title or result.path,
            content=result.content or result.snippet,
            metadata={
                "adapter": "obsidian-hybrid-search",
                "path": result.path,
                "vault_path": str(ctx.config.obsidian_vault_path or ""),
                "score": f"{result.score:.6f}",
                "source_key": "local_notes",
                **dict(result.metadata or {}),
            },
            source_key="local_notes",
        )



def apply_obsidian_guidance(
    ctx: WorkspaceRetrievalContext,
        retrieval_plan: WorkspaceRetrievalPlan,
        results: Sequence[ObsidianSearchResult],
        index: Any,
    ) -> tuple[WorkspaceRetrievalPlan, tuple[str, ...]]:
        if not results:
            return retrieval_plan, ()
        indexed_paths = {document.chunk.path for document in index.documents}
        workspace_root = Path(ctx.config.workspace_root)
        guidance_results = tuple(result for result in results if result.score >= ctx.config.obsidian_min_guidance_score)
        if not guidance_results:
            ctx.trace.record(
                "trusted_local_notes_guidance_skipped",
                {
                    "adapter": "obsidian-hybrid-search",
                    "reason": "below_min_guidance_score",
                    "min_score": ctx.config.obsidian_min_guidance_score,
                    "scores": [result.score for result in results],
                },
            )
            return retrieval_plan, ()
        trusted_hints = tuple(
            path
            for path in trusted_file_hints_from_obsidian_results(guidance_results)
            if path in indexed_paths or (workspace_root / path).is_file()
        )
        if not trusted_hints:
            return retrieval_plan, ()
        source_priorities = merge_source_priorities(
            (SourceCategory.LOCAL_NOTES, SourceCategory.SOURCE_CODE),
            retrieval_plan.source_priorities,
        )
        updated_plan = replace(
            retrieval_plan,
            retrieval_terms=ordered_unique(
                [
                    *retrieval_plan.retrieval_terms,
                    *[Path(path).stem for path in trusted_hints],
                ]
            ),
            source_priorities=source_priorities,
            metadata={
                **dict(retrieval_plan.metadata),
                "trusted_local_notes": "obsidian-hybrid-search",
                "trusted_local_note_file_hints": list(trusted_hints),
            },
        )
        ctx.trace.record(
            "trusted_local_notes_applied",
            {
                "adapter": "obsidian-hybrid-search",
                "file_hints": list(trusted_hints),
                "note_refs": [f"obsidian:{result.path}" for result in guidance_results],
            },
        )
        return updated_plan, trusted_hints
