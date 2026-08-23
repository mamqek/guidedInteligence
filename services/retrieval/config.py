from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from core.source_policy import (
    DEFAULT_ALLOWED_SOURCE_CATEGORIES,
    DEFAULT_SOURCE_POLICY,
    SourceCategory,
    SourcePolicy,
)
from core.models import TurnType


WORKSPACE_REINDEX_POLICY_ALWAYS = "always"
RETRIEVAL_MODE_WORKSPACE = "workspace"
RETRIEVAL_MODE_AGENT_PLANNED = "agent_planned"
RETRIEVAL_MODE_CODEX = "codex"
SUPPORTED_RETRIEVAL_MODES = (
    RETRIEVAL_MODE_WORKSPACE,
    RETRIEVAL_MODE_AGENT_PLANNED,
    RETRIEVAL_MODE_CODEX,
)
DEFAULT_CODEX_PROMPT_PROFILE = "efficient"
DEFAULT_CONNECTED_CONTEXT_DISCLAIMER_REQUIRED_TERMS = ("do not use",)
DEFAULT_CONNECTED_CONTEXT_STALE_BLOCK_TERMS = ("stale", "superseded", "outdated", "deprecated")
SUPPORTED_CODEX_PROMPT_PROFILES = (DEFAULT_CODEX_PROMPT_PROFILE, "responsibility-complete")
LLM_API_STYLE_OPENAI_CHAT = "openai_chat_completions"
LLM_API_STYLE_CODEX_CLI = "codex_cli"
SUPPORTED_LLM_API_STYLES = (LLM_API_STYLE_OPENAI_CHAT, LLM_API_STYLE_CODEX_CLI)
SUPPORTED_RETRIEVAL_EMBEDDING_API_STYLES = ("openai_embeddings",)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_retrieval_env_path() -> Path:
    return _repo_root() / ".env"


def _default_obsidian_vault_path() -> str:
    return str(_repo_root() / "docs" / "obsidian")


def _default_obsidian_db_path() -> str:
    return str(Path(_default_obsidian_vault_path()) / ".obsidian-hybrid-search.db")


def _default_obsidian_command() -> tuple[str, ...]:
    root = _repo_root()
    executable = "obsidian-hybrid-search.cmd" if os.name == "nt" else "obsidian-hybrid-search"
    local_bin = root / "node_modules" / ".bin" / executable
    if local_bin.exists():
        return (str(local_bin),)
    return ("npx.cmd" if os.name == "nt" else "npx", "obsidian-hybrid-search")


def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        value = raw_value.strip()
        if not key:
            continue
        if value and value[0] in {'"', "'"} and value[-1:] == value[0]:
            value = value[1:-1]
        else:
            comment_index = value.find(" #")
            if comment_index >= 0:
                value = value[:comment_index].rstrip()
        values[key] = value
    return values


def _parse_bool_env(values: Mapping[str, str], key: str, default: bool) -> bool:
    raw_value = values.get(key, "").strip().lower()
    if not raw_value:
        return default
    if raw_value in {"1", "true", "yes", "on"}:
        return True
    if raw_value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{key} must be a boolean-like value.")


def load_retrieval_embedding_config(env_path: str | Path | None = None) -> "RetrievalEmbeddingConfig":
    values = _parse_env_file(Path(env_path) if env_path is not None else _default_retrieval_env_path())
    api_style = values.get("RETRIEVAL_EMBEDDING_API_STYLE", "").strip()
    model = values.get("RETRIEVAL_EMBEDDING_MODEL", "").strip()
    endpoint_url = values.get("RETRIEVAL_EMBEDDING_ENDPOINT_URL", "").strip()
    api_key = values.get("RETRIEVAL_EMBEDDING_API_KEY", "").strip()
    configured_values = (api_style, model, endpoint_url, api_key)
    if not any(configured_values):
        raise ValueError(
            "Retrieval embedding config is missing. "
            "Set RETRIEVAL_EMBEDDING_API_STYLE, RETRIEVAL_EMBEDDING_MODEL, RETRIEVAL_EMBEDDING_ENDPOINT_URL, and RETRIEVAL_EMBEDDING_API_KEY."
        )
    if not all(configured_values):
        raise ValueError(
            "Retrieval embedding config is incomplete. "
            "Set RETRIEVAL_EMBEDDING_API_STYLE, RETRIEVAL_EMBEDDING_MODEL, RETRIEVAL_EMBEDDING_ENDPOINT_URL, and RETRIEVAL_EMBEDDING_API_KEY."
        )
    timeout_raw = values.get("RETRIEVAL_EMBEDDING_TIMEOUT_SECONDS", "30").strip() or "30"
    batch_size_raw = values.get("RETRIEVAL_EMBEDDING_BATCH_SIZE", "32").strip() or "32"
    concurrency_raw = values.get("RETRIEVAL_EMBEDDING_CONCURRENCY", "1").strip() or "1"
    try:
        timeout_seconds = int(timeout_raw)
    except ValueError as exc:
        raise ValueError("RETRIEVAL_EMBEDDING_TIMEOUT_SECONDS must be an integer.") from exc
    try:
        batch_size = int(batch_size_raw)
    except ValueError as exc:
        raise ValueError("RETRIEVAL_EMBEDDING_BATCH_SIZE must be an integer.") from exc
    try:
        concurrency = int(concurrency_raw)
    except ValueError as exc:
        raise ValueError("RETRIEVAL_EMBEDDING_CONCURRENCY must be an integer.") from exc
    return RetrievalEmbeddingConfig(
        api_style=api_style,
        model=model,
        endpoint_url=endpoint_url,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
        batch_size=batch_size,
        concurrency=concurrency,
    )


def load_retrieval_qdrant_config(env_path: str | Path | None = None) -> "RetrievalQdrantConfig":
    values = _parse_env_file(Path(env_path) if env_path is not None else _default_retrieval_env_path())
    url = values.get("RETRIEVAL_QDRANT_URL", "").strip()
    collection_name = values.get("RETRIEVAL_QDRANT_COLLECTION", "").strip()
    if not any((url, collection_name)):
        raise ValueError(
            "Retrieval Qdrant config is missing. "
            "Set RETRIEVAL_QDRANT_URL and RETRIEVAL_QDRANT_COLLECTION."
        )
    if not all((url, collection_name)):
        raise ValueError(
            "Retrieval Qdrant config is incomplete. "
            "Set RETRIEVAL_QDRANT_URL and RETRIEVAL_QDRANT_COLLECTION."
        )
    timeout_raw = values.get("RETRIEVAL_QDRANT_TIMEOUT_SECONDS", "30").strip() or "30"
    try:
        timeout_seconds = int(timeout_raw)
    except ValueError as exc:
        raise ValueError("RETRIEVAL_QDRANT_TIMEOUT_SECONDS must be an integer.") from exc
    return RetrievalQdrantConfig(url=url, collection_name=collection_name, timeout_seconds=timeout_seconds)


def load_retrieval_enable_indexing(env_path: str | Path | None = None) -> bool:
    values = _parse_env_file(Path(env_path) if env_path is not None else _default_retrieval_env_path())
    return _parse_bool_env(values, "RETRIEVAL_ENABLE_INDEXING", True)


@dataclass(frozen=True)
class ConnectedSourceDocument:
    """One optional external or attached source visible to workspace retrieval."""

    source_category: SourceCategory
    source_id: str
    title: str
    content: str
    metadata: Mapping[str, str] = field(default_factory=dict)
    source_key: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "source_category": self.source_category.value,
            "source_key": self.source_key,
            "source_id": self.source_id,
            "title": self.title,
            "content": self.content,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class MCPConnectedSourceConfig:
    """One MCP-backed connected source queried during retrieval planning."""

    name: str
    source_category: SourceCategory
    command: str
    source_key: str = ""
    args: tuple[str, ...] = field(default_factory=tuple)
    env: Mapping[str, str] = field(default_factory=dict)
    cwd: str | None = None
    query_tool_name: str = ""
    query_argument_name: str = "query"
    limit_argument_name: str = "limit"
    result_limit: int = 5
    timeout_seconds: int = 20
    static_tool_arguments: Mapping[str, str] = field(default_factory=dict)
    id_fields: tuple[str, ...] = ("source_id", "id", "url", "html_url", "number")
    title_fields: tuple[str, ...] = ("title", "name", "subject")
    content_fields: tuple[str, ...] = ("content", "body", "text", "description", "summary")

    def public_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "source_category": self.source_category.value,
            "source_key": self.source_key,
            "command": self.command,
            "args": list(self.args),
            "cwd": self.cwd or "",
            "query_tool_name": self.query_tool_name,
            "query_argument_name": self.query_argument_name,
            "limit_argument_name": self.limit_argument_name,
            "result_limit": self.result_limit,
            "timeout_seconds": self.timeout_seconds,
            "static_tool_arguments": dict(self.static_tool_arguments),
            "id_fields": list(self.id_fields),
            "title_fields": list(self.title_fields),
            "content_fields": list(self.content_fields),
            "env_configured": sorted(self.env),
        }


@dataclass(frozen=True)
class RemoteMCPConnectedSourceConfig:
    """One hosted MCP connected source queried over HTTP."""

    name: str
    provider: str
    source_category: SourceCategory
    endpoint_url: str
    source_key: str = ""
    enabled: bool = True
    auth_type: str = "none"
    bearer_token: str = ""
    oauth_access_token: str = ""
    api_key: str = ""
    api_key_header: str = ""
    oauth_authorize_url: str = ""
    headers: Mapping[str, str] = field(default_factory=dict)
    scope: str = ""
    features: Mapping[str, bool] = field(default_factory=dict)
    query_tool_name: str = ""
    fetch_tool_name: str = ""
    query_argument_name: str = "query"
    limit_argument_name: str = "limit"
    result_limit: int = 5
    enrich_results: bool = False
    enrich_limit: int = 3
    timeout_seconds: int = 20
    min_score: float = 0.0
    static_tool_arguments: Mapping[str, str] = field(default_factory=dict)
    score_fields: tuple[str, ...] = ("score", "relevance", "rank_score", "_score")
    id_fields: tuple[str, ...] = ("source_id", "id", "url", "html_url", "key", "number")
    title_fields: tuple[str, ...] = ("title", "name", "summary", "subject")
    content_fields: tuple[str, ...] = ("content", "body", "text", "description", "summary")

    def public_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "name": self.name,
            "provider": self.provider,
            "source_category": self.source_category.value,
            "source_key": self.source_key,
            "endpoint_url": self.endpoint_url,
            "auth_type": self.auth_type,
            "oauth_authorize_url": self.oauth_authorize_url,
            "headers": dict(self.headers),
            "scope": self.scope,
            "features": dict(self.features),
            "query_tool_name": self.query_tool_name,
            "fetch_tool_name": self.fetch_tool_name,
            "query_argument_name": self.query_argument_name,
            "limit_argument_name": self.limit_argument_name,
            "result_limit": self.result_limit,
            "enrich_results": self.enrich_results,
            "enrich_limit": self.enrich_limit,
            "timeout_seconds": self.timeout_seconds,
            "min_score": self.min_score,
            "static_tool_arguments": dict(self.static_tool_arguments),
            "score_fields": list(self.score_fields),
            "id_fields": list(self.id_fields),
            "title_fields": list(self.title_fields),
            "content_fields": list(self.content_fields),
            "bearer_token_configured": bool(self.bearer_token),
            "oauth_access_token_configured": bool(self.oauth_access_token),
            "api_key_configured": bool(self.api_key),
            "api_key_header": self.api_key_header,
        }


@dataclass(frozen=True)
class SourceRegistryEntry:
    """Explicit source-capability declaration for one retrieval category."""

    category: SourceCategory
    enabled: bool
    indexed: bool
    queryable: bool
    adapter_name: str
    note: str = ""
    source_key: str = ""
    provider: str = ""
    title: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "category": self.category.value,
            "source_key": self.source_key or self.category.value,
            "provider": self.provider,
            "title": self.title,
            "enabled": self.enabled,
            "indexed": self.indexed,
            "queryable": self.queryable,
            "adapter_name": self.adapter_name,
            "note": self.note,
        }


@dataclass(frozen=True)
class WorkspaceRetrievalConfig:
    """Concrete runtime config for workspace-first retrieval."""

    workspace_root: str
    index_dir: str
    llm_config: "RunLLMConfig"
    embedding_config: "RetrievalEmbeddingConfig"
    qdrant_config: "RetrievalQdrantConfig"
    repository_name: str = ""
    repository_owner: str = ""
    retrieval_mode: str = RETRIEVAL_MODE_WORKSPACE
    codex_command: tuple[str, ...] = ("codex",)
    codex_model: str = "gpt-5.4-mini"
    codex_prompt_profile: str = DEFAULT_CODEX_PROMPT_PROFILE
    codex_timeout_seconds: int = 900
    codex_ignore_user_config: bool = True
    codex_evidence_organizer_enabled: bool = True
    final_evidence_selection_enabled: bool = True
    run_dir: str | None = None
    chunk_line_count: int = 40
    chunk_line_overlap: int = 10
    lexical_ranking_profile: str = "flat_bm25"
    max_exploration_rounds: int = 4
    max_tool_calls_per_round: int = 5
    max_controller_actions_per_round: int = 2
    semantic_island_beam_size: int = 4
    max_discovery_observations: int = 24
    max_qualification_input_chars: int = 40000
    max_agent_planner_input_chars: int = 30000
    max_agent_planner_rounds: int = 3
    max_agent_planner_actions_per_round: int = 2
    max_initial_owner_comparison_input_chars: int = 100000
    max_final_selection_input_chars: int = 50000
    structural_graph_enabled: bool = True
    enable_indexing: bool = True
    structural_graph_timeout_seconds: int = 900
    structural_graph_max_files: int = 20
    qdrant_index_timeout_seconds: int = 600
    embedding_cache_path: str | None = None
    index_exclude_paths: tuple[str, ...] | None = None
    enabled_source_categories: tuple[SourceCategory, ...] = DEFAULT_ALLOWED_SOURCE_CATEGORIES
    enabled_sources: tuple[str, ...] = ()
    reindex_policy: str = WORKSPACE_REINDEX_POLICY_ALWAYS
    retrieval_model_settings: Mapping[str, str] = field(default_factory=dict)
    issue_tracker_documents: tuple[ConnectedSourceDocument, ...] = field(default_factory=tuple)
    pull_request_documents: tuple[ConnectedSourceDocument, ...] = field(default_factory=tuple)
    notebooklm_documents: tuple[ConnectedSourceDocument, ...] = field(default_factory=tuple)
    mcp_connected_sources: tuple[MCPConnectedSourceConfig, ...] = field(default_factory=tuple)
    remote_mcp_connected_sources: tuple[RemoteMCPConnectedSourceConfig, ...] = field(default_factory=tuple)
    local_note_paths: tuple[str, ...] = field(default_factory=tuple)
    obsidian_vault_path: str | None = field(default_factory=_default_obsidian_vault_path)
    obsidian_db_path: str | None = field(default_factory=_default_obsidian_db_path)
    obsidian_command: tuple[str, ...] = field(default_factory=_default_obsidian_command)
    obsidian_search_mode: str = "fulltext"
    obsidian_search_limit: int = 5
    obsidian_min_guidance_score: float = 0.0
    obsidian_timeout_seconds: int = 20
    connected_context_enabled: bool = True
    connected_context_max_sources: int = 8
    connected_context_max_calls: int = 8
    connected_context_max_candidates_per_source: int = 5
    connected_context_max_candidates_total: int = 20
    connected_context_max_candidate_chars: int = 2400
    connected_context_max_candidate_chars_total: int = 24000
    connected_context_max_selected_context: int = 4
    connected_context_max_selected_evidence: int = 2
    connected_context_timeout_seconds: int = 45
    connected_context_disclaimer_required_terms: tuple[str, ...] = DEFAULT_CONNECTED_CONTEXT_DISCLAIMER_REQUIRED_TERMS
    connected_context_stale_block_terms: tuple[str, ...] = DEFAULT_CONNECTED_CONTEXT_STALE_BLOCK_TERMS
    connected_source_adapters: Mapping[str, bool] = field(
        default_factory=lambda: {
            "issue_tracker": True,
            "pull_request": True,
            "local_notes": True,
            "notebooklm": True,
            "mcp": True,
        }
    )

    def source_registry(self) -> tuple[SourceRegistryEntry, ...]:
        mcp_categories = {
            source.source_category
            for source in self.mcp_connected_sources
            if self.connected_source_adapters.get("mcp", True)
        }
        remote_mcp_categories = {
            source.source_category
            for source in self.remote_mcp_connected_sources
            if source.enabled and self.connected_source_adapters.get("remote_mcp", True)
        }
        entries: list[SourceRegistryEntry] = [
            SourceRegistryEntry(
                category=SourceCategory.SOURCE_CODE,
                enabled=SourceCategory.SOURCE_CODE in self.enabled_source_categories,
                indexed=True,
                queryable=True,
                adapter_name="codegraph+qdrant-hybrid",
                note="CodeGraph resolves exact symbols and structural relationships; Qdrant hybrid retrieval handles conceptual code search.",
                source_key="source_code",
                title="Source code",
            ),
            SourceRegistryEntry(
                category=SourceCategory.DOCUMENTATION,
                enabled=SourceCategory.DOCUMENTATION in self.enabled_source_categories,
                indexed=True,
                queryable=True,
                adapter_name="qdrant-hybrid",
                note="Repository documentation is retrieved semantically; CodeGraph is reserved for supported source-code structure.",
                source_key="repo_docs",
                title="Repository docs",
            ),
            SourceRegistryEntry(
                category=SourceCategory.ISSUE_TRACKER,
                enabled=SourceCategory.ISSUE_TRACKER in self.enabled_source_categories
                and self.connected_source_adapters.get("issue_tracker", True),
                indexed=False,
                queryable=bool(self.issue_tracker_documents)
                or SourceCategory.ISSUE_TRACKER in mcp_categories
                or SourceCategory.ISSUE_TRACKER in remote_mcp_categories,
                adapter_name="connected_documents+mcp+remote_mcp",
                note="Issue tracker context is supplied as connected documents or MCP-backed query results.",
            ),
            SourceRegistryEntry(
                category=SourceCategory.PULL_REQUEST,
                enabled=SourceCategory.PULL_REQUEST in self.enabled_source_categories
                and self.connected_source_adapters.get("pull_request", True),
                indexed=False,
                queryable=bool(self.pull_request_documents)
                or SourceCategory.PULL_REQUEST in mcp_categories
                or SourceCategory.PULL_REQUEST in remote_mcp_categories,
                adapter_name="connected_documents+mcp+remote_mcp",
                note="Pull request context is supplied as connected documents or MCP-backed query results.",
            ),
            SourceRegistryEntry(
                category=SourceCategory.LOCAL_NOTES,
                enabled=SourceCategory.LOCAL_NOTES in self.enabled_source_categories
                and self.connected_source_adapters.get("local_notes", True),
                indexed=False,
                queryable=bool(self.local_note_paths) or bool(self.obsidian_vault_path),
                adapter_name="obsidian-hybrid-search+local_note_files",
                note=(
                    "Obsidian owns local-note indexing; workspace retrieval consumes matching note results as "
                    "trusted source guidance without adding them to Qdrant."
                ),
                source_key="local_notes",
                title="Local notes",
            ),
            SourceRegistryEntry(
                category=SourceCategory.NOTEBOOKLM,
                enabled=SourceCategory.NOTEBOOKLM in self.enabled_source_categories
                and self.connected_source_adapters.get("notebooklm", True),
                indexed=False,
                queryable=bool(self.notebooklm_documents)
                or SourceCategory.NOTEBOOKLM in mcp_categories
                or SourceCategory.NOTEBOOKLM in remote_mcp_categories,
                adapter_name="connected_documents+remote_mcp+mcp",
                note="NotebookLM context is attached as provided text snippets or remote/local MCP results.",
                source_key="notebooklm",
                title="NotebookLM",
            ),
        ]
        for source in self.remote_mcp_connected_sources:
            if not source.enabled or not self.connected_source_adapters.get("remote_mcp", True):
                continue
            entries.append(
                SourceRegistryEntry(
                    category=source.source_category,
                    enabled=(not self.enabled_sources or source.source_key in self.enabled_sources),
                    indexed=False,
                    queryable=True,
                    adapter_name="remote_mcp",
                    note="Remote MCP provider source queried live during retrieval.",
                    source_key=source.source_key,
                    provider=source.provider,
                    title=source.name,
                )
            )
        for source in self.mcp_connected_sources:
            if not self.connected_source_adapters.get("mcp", True):
                continue
            entries.append(
                SourceRegistryEntry(
                    category=source.source_category,
                    enabled=(not self.enabled_sources or source.source_key in self.enabled_sources),
                    indexed=False,
                    queryable=True,
                    adapter_name="mcp",
                    note="Local MCP provider source queried live during retrieval.",
                    source_key=source.source_key,
                    title=source.name,
                )
            )
        return tuple(entries)

    def validate(self) -> None:
        if self.retrieval_mode not in SUPPORTED_RETRIEVAL_MODES:
            raise ValueError(
                f"Unsupported retrieval_mode: {self.retrieval_mode}. "
                f"Supported values: {', '.join(SUPPORTED_RETRIEVAL_MODES)}."
            )
        if self.retrieval_mode == RETRIEVAL_MODE_CODEX:
            if not self.codex_command:
                raise ValueError("Codex retrieval mode requires a non-empty codex_command.")
            if not self.codex_model.strip():
                raise ValueError("Codex retrieval mode requires codex_model.")
            if self.codex_prompt_profile not in SUPPORTED_CODEX_PROMPT_PROFILES:
                raise ValueError(
                    f"Unsupported Codex prompt profile: {self.codex_prompt_profile}. "
                    f"Supported profiles: {', '.join(SUPPORTED_CODEX_PROMPT_PROFILES)}."
                )
            if self.codex_timeout_seconds <= 0:
                raise ValueError("Codex retrieval mode requires codex_timeout_seconds > 0.")
            RunConfigController().validate_llm_config(self.llm_config)
            return
        if self.reindex_policy != WORKSPACE_REINDEX_POLICY_ALWAYS:
            raise ValueError("Workspace retrieval currently supports only reindex_policy='always'.")
        if self.max_exploration_rounds <= 0:
            raise ValueError("max_exploration_rounds must be greater than zero.")
        if self.max_tool_calls_per_round <= 0:
            raise ValueError("max_tool_calls_per_round must be greater than zero.")
        if self.max_controller_actions_per_round <= 0:
            raise ValueError("max_controller_actions_per_round must be greater than zero.")
        if self.semantic_island_beam_size <= 0:
            raise ValueError("semantic_island_beam_size must be greater than zero.")
        if self.max_discovery_observations <= 0:
            raise ValueError("max_discovery_observations must be greater than zero.")
        if self.max_qualification_input_chars <= 0:
            raise ValueError("max_qualification_input_chars must be greater than zero.")
        if self.max_agent_planner_input_chars <= 0:
            raise ValueError("max_agent_planner_input_chars must be greater than zero.")
        if self.max_agent_planner_rounds <= 0:
            raise ValueError("max_agent_planner_rounds must be greater than zero.")
        if self.max_agent_planner_actions_per_round <= 0:
            raise ValueError("max_agent_planner_actions_per_round must be greater than zero.")
        if self.max_initial_owner_comparison_input_chars <= 0:
            raise ValueError("max_initial_owner_comparison_input_chars must be greater than zero.")
        if self.max_final_selection_input_chars <= 0:
            raise ValueError("max_final_selection_input_chars must be greater than zero.")
        if not self.structural_graph_enabled:
            raise ValueError("Workspace retrieval requires structural_graph_enabled=True.")
        if self.structural_graph_timeout_seconds <= 0:
            raise ValueError("structural_graph_timeout_seconds must be greater than zero.")
        if self.structural_graph_max_files <= 0:
            raise ValueError("structural_graph_max_files must be greater than zero.")
        if self.qdrant_index_timeout_seconds <= 0:
            raise ValueError("qdrant_index_timeout_seconds must be greater than zero.")
        index_exclude_paths = self.index_exclude_paths or ()
        if any(Path(path).is_absolute() for path in index_exclude_paths):
            raise ValueError("Index exclude paths must be workspace-relative.")
        if self.chunk_line_count <= 0:
            raise ValueError("chunk_line_count must be greater than zero.")
        if self.chunk_line_overlap < 0 or self.chunk_line_overlap >= self.chunk_line_count:
            raise ValueError("chunk_line_overlap must be between zero and chunk_line_count - 1.")
        if self.lexical_ranking_profile not in {"flat_bm25", "bm25f_v1", "bm25f_v2"}:
            raise ValueError(f"Unsupported lexical_ranking_profile: {self.lexical_ranking_profile}.")
        if self.obsidian_search_limit <= 0:
            raise ValueError("obsidian_search_limit must be greater than zero.")
        if self.obsidian_min_guidance_score < 0:
            raise ValueError("obsidian_min_guidance_score must be zero or greater.")
        if self.obsidian_timeout_seconds <= 0:
            raise ValueError("obsidian_timeout_seconds must be greater than zero.")
        if self.connected_context_max_sources <= 0:
            raise ValueError("connected_context_max_sources must be greater than zero.")
        if self.connected_context_max_calls <= 0:
            raise ValueError("connected_context_max_calls must be greater than zero.")
        if self.connected_context_max_candidates_per_source <= 0:
            raise ValueError("connected_context_max_candidates_per_source must be greater than zero.")
        if self.connected_context_max_candidates_total <= 0:
            raise ValueError("connected_context_max_candidates_total must be greater than zero.")
        if self.connected_context_max_candidate_chars <= 0:
            raise ValueError("connected_context_max_candidate_chars must be greater than zero.")
        if self.connected_context_max_candidate_chars_total <= 0:
            raise ValueError("connected_context_max_candidate_chars_total must be greater than zero.")
        if self.connected_context_max_selected_context <= 0:
            raise ValueError("connected_context_max_selected_context must be greater than zero.")
        if self.connected_context_max_selected_evidence <= 0:
            raise ValueError("connected_context_max_selected_evidence must be greater than zero.")
        if self.connected_context_timeout_seconds <= 0:
            raise ValueError("connected_context_timeout_seconds must be greater than zero.")
        for source in self.mcp_connected_sources:
            if not source.name.strip():
                raise ValueError("MCP connected source requires name.")
            if not source.command.strip():
                raise ValueError(f"MCP connected source {source.name!r} requires command.")
            if not source.query_tool_name.strip():
                raise ValueError(f"MCP connected source {source.name!r} requires query_tool_name.")
            if source.result_limit <= 0:
                raise ValueError(f"MCP connected source {source.name!r} requires result_limit > 0.")
            if source.timeout_seconds <= 0:
                raise ValueError(f"MCP connected source {source.name!r} requires timeout_seconds > 0.")
        for source in self.remote_mcp_connected_sources:
            if not source.name.strip():
                raise ValueError("Remote MCP connected source requires name.")
            if not source.provider.strip():
                raise ValueError(f"Remote MCP connected source {source.name!r} requires provider.")
            if not source.endpoint_url.strip():
                raise ValueError(f"Remote MCP connected source {source.name!r} requires endpoint_url.")
            if not source.query_tool_name.strip():
                raise ValueError(f"Remote MCP connected source {source.name!r} requires query_tool_name.")
            if source.result_limit <= 0:
                raise ValueError(f"Remote MCP connected source {source.name!r} requires result_limit > 0.")
            if source.timeout_seconds <= 0:
                raise ValueError(f"Remote MCP connected source {source.name!r} requires timeout_seconds > 0.")
        RunConfigController().validate_llm_config(self.llm_config)
        RunConfigController().validate_embedding_config(self.embedding_config)
        RunConfigController().validate_qdrant_config(self.qdrant_config)


CODEREPOQA_STAGE1_POLICY_NAME = "coderepoqa_explain_initial"
CODEREPOQA_STAGE1_ALLOWED_CATEGORIES = (
    SourceCategory.ISSUE_TRACKER,
    SourceCategory.SOURCE_CODE,
)


@dataclass(frozen=True)
class RunSourceConfig:
    """Run-controlled source settings for one retrieval run."""

    policy_name: str
    allowed_categories: tuple[SourceCategory, ...]
    visibility_scope: str
    snapshot_scope: str
    allow_generated_orientation: bool = False


@dataclass(frozen=True)
class RunLLMConfig:
    """Optional model settings for retrieval intent planning."""

    api_style: str = LLM_API_STYLE_OPENAI_CHAT
    model: str = ""
    endpoint_url: str = ""
    api_key: str = ""
    temperature: float = 0.0
    max_tokens: int = 800
    timeout_seconds: int = 30
    planner_strategy: str = "issue_repo_sketch_v1"
    continuity_enabled: bool = False
    codex_command: tuple[str, ...] = ("codex",)
    codex_ignore_user_config: bool = True

    def public_dict(self) -> dict[str, object]:
        return {
            "api_style": self.api_style,
            "model": self.model,
            "endpoint_url": self.endpoint_url,
            "api_key_configured": bool(self.api_key),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout_seconds": self.timeout_seconds,
            "planner_strategy": self.planner_strategy,
            "continuity_enabled": self.continuity_enabled,
            "codex_command": list(self.codex_command),
            "codex_ignore_user_config": self.codex_ignore_user_config,
        }


@dataclass(frozen=True)
class RetrievalEmbeddingConfig:
    api_style: str = "openai_embeddings"
    model: str = ""
    endpoint_url: str = ""
    api_key: str = ""
    timeout_seconds: int = 30
    batch_size: int = 32
    concurrency: int = 1

    def public_dict(self) -> dict[str, object]:
        return {
            "api_style": self.api_style,
            "model": self.model,
            "endpoint_url": self.endpoint_url,
            "api_key_configured": bool(self.api_key),
            "timeout_seconds": self.timeout_seconds,
            "batch_size": self.batch_size,
            "concurrency": self.concurrency,
        }


@dataclass(frozen=True)
class RetrievalQdrantConfig:
    url: str = ""
    collection_name: str = ""
    timeout_seconds: int = 30

    def public_dict(self) -> dict[str, object]:
        return {
            "url": self.url,
            "collection_name": self.collection_name,
            "timeout_seconds": self.timeout_seconds,
        }


@dataclass(frozen=True)
class RunConfig:
    """Configuration that ties source policy, retrieval, and logging to one run."""

    run_id: str
    case_id: str
    turn_type: TurnType
    source_config: RunSourceConfig
    llm_config: RunLLMConfig
    retrieval_config: Mapping[str, str] = field(default_factory=dict)
    logging_config: Mapping[str, str] = field(default_factory=dict)


class RunConfigController:
    """Resolve run configuration into core policy objects."""

    def source_policy_for(self, config: RunConfig) -> SourcePolicy:
        self.validate(config)
        return SourcePolicy(
            allowed_categories=config.source_config.allowed_categories,
            policy_name=config.source_config.policy_name,
        )

    def validate(self, config: RunConfig) -> None:
        if config.source_config.allowed_categories == DEFAULT_SOURCE_POLICY.allowed_categories:
            raise ValueError("CodeRepoQA Stage 1 must not use DEFAULT_SOURCE_POLICY.")

        if config.source_config.policy_name == DEFAULT_SOURCE_POLICY.policy_name:
            raise ValueError("CodeRepoQA Stage 1 must use an evaluation-specific source policy name.")

        if config.source_config.allowed_categories != CODEREPOQA_STAGE1_ALLOWED_CATEGORIES:
            raise ValueError(
                "CodeRepoQA Stage 1 must allow exactly ISSUE_TRACKER and SOURCE_CODE."
            )

        if config.source_config.visibility_scope != "visible_initial":
            raise ValueError("CodeRepoQA Stage 1 visibility_scope must be visible_initial.")

        if config.source_config.snapshot_scope != "pre_resolution":
            raise ValueError("CodeRepoQA Stage 1 snapshot_scope must be pre_resolution.")

        self.validate_llm_config(config.llm_config)

    def validate_llm_config(self, llm_config: RunLLMConfig) -> None:
        if llm_config.api_style not in SUPPORTED_LLM_API_STYLES:
            raise ValueError(
                f"Unsupported retrieval LLM api_style: {llm_config.api_style}. "
                f"Supported values: {', '.join(SUPPORTED_LLM_API_STYLES)}."
            )
        if not llm_config.model:
            raise ValueError("Retrieval LLM config requires model.")
        if llm_config.api_style == LLM_API_STYLE_CODEX_CLI:
            if not llm_config.codex_command:
                raise ValueError("Codex CLI LLM config requires codex_command.")
            if llm_config.timeout_seconds <= 0:
                raise ValueError("Codex CLI LLM config requires timeout_seconds > 0.")
            return
        if not llm_config.endpoint_url:
            raise ValueError("Retrieval LLM config requires endpoint_url.")
        if not llm_config.api_key:
            raise ValueError("Retrieval LLM config requires api_key.")

    def validate_embedding_config(self, embedding_config: RetrievalEmbeddingConfig) -> None:
        if embedding_config.api_style not in SUPPORTED_RETRIEVAL_EMBEDDING_API_STYLES:
            raise ValueError(
                f"Unsupported retrieval embedding api_style: {embedding_config.api_style}. "
                f"Supported values: {', '.join(SUPPORTED_RETRIEVAL_EMBEDDING_API_STYLES)}."
            )
        if not embedding_config.model:
            raise ValueError("Retrieval embedding config requires model.")
        if not embedding_config.endpoint_url:
            raise ValueError("Retrieval embedding config requires endpoint_url.")
        if not embedding_config.api_key:
            raise ValueError("Retrieval embedding config requires api_key.")
        if embedding_config.timeout_seconds <= 0:
            raise ValueError("Retrieval embedding config requires timeout_seconds > 0.")
        if embedding_config.batch_size <= 0:
            raise ValueError("Retrieval embedding config requires batch_size > 0.")
        if embedding_config.concurrency <= 0:
            raise ValueError("Retrieval embedding config requires concurrency > 0.")

    def validate_qdrant_config(self, qdrant_config: RetrievalQdrantConfig) -> None:
        if not qdrant_config.url:
            raise ValueError("Retrieval Qdrant config requires url.")
        if not qdrant_config.collection_name:
            raise ValueError("Retrieval Qdrant config requires collection_name.")
        if qdrant_config.timeout_seconds <= 0:
            raise ValueError("Retrieval Qdrant config requires timeout_seconds > 0.")


def coderepoqa_stage1_run_config(
    *,
    run_id: str,
    case_id: str,
    index_dir: str,
    run_dir: str,
    llm_config: RunLLMConfig,
) -> RunConfig:
    return RunConfig(
        run_id=run_id,
        case_id=case_id,
        turn_type=TurnType.GUIDED_EXPLANATION,
        source_config=RunSourceConfig(
            policy_name=CODEREPOQA_STAGE1_POLICY_NAME,
            allowed_categories=CODEREPOQA_STAGE1_ALLOWED_CATEGORIES,
            visibility_scope="visible_initial",
            snapshot_scope="pre_resolution",
            allow_generated_orientation=False,
        ),
        retrieval_config={"index_dir": index_dir},
        logging_config={"run_dir": run_dir},
        llm_config=llm_config,
    )


def source_categories_from_strings(values: tuple[str, ...]) -> tuple[SourceCategory, ...]:
    categories: list[SourceCategory] = []
    for value in values:
        try:
            categories.append(SourceCategory(value))
        except ValueError as exc:
            raise ValueError(f"Unknown SourceCategory value: {value}") from exc
    return tuple(categories)
