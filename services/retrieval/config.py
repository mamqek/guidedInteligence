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
from core.stages import ResponseStage


WORKSPACE_REINDEX_POLICY_ALWAYS = "always"
SUPPORTED_RETRIEVAL_LLM_API_STYLES = ("openai_chat_completions",)


def _default_cgc_command() -> tuple[str, ...]:
    root = Path(__file__).resolve().parents[2]
    scripts_dir = root / ".venv" / ("Scripts" if os.name == "nt" else "bin")
    executable_name = "cgc.exe" if os.name == "nt" else "cgc"
    return (str(scripts_dir / executable_name),)


def _default_cgc_db_path() -> str:
    root = Path(__file__).resolve().parents[2]
    return str(root / ".codegraphcontext" / "db" / "kuzudb")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_retrieval_env_path() -> Path:
    return _repo_root() / ".env"


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


def load_retrieval_llm_config(env_path: str | Path | None = None) -> "RunLLMConfig":
    values = _parse_env_file(Path(env_path) if env_path is not None else _default_retrieval_env_path())
    api_style = values.get("RETRIEVAL_LLM_API_STYLE", "").strip()
    model = values.get("RETRIEVAL_LLM_MODEL", "").strip()
    endpoint_url = values.get("RETRIEVAL_LLM_ENDPOINT_URL", "").strip()
    api_key = values.get("RETRIEVAL_LLM_API_KEY", "").strip()
    configured_values = (api_style, model, endpoint_url, api_key)
    if not any(configured_values):
        raise ValueError(
            "Retrieval LLM config is missing. "
            "Set RETRIEVAL_LLM_API_STYLE, RETRIEVAL_LLM_MODEL, RETRIEVAL_LLM_ENDPOINT_URL, and RETRIEVAL_LLM_API_KEY."
        )
    if not all(configured_values):
        raise ValueError(
            "Retrieval LLM config is incomplete. "
            "Set RETRIEVAL_LLM_API_STYLE, RETRIEVAL_LLM_MODEL, RETRIEVAL_LLM_ENDPOINT_URL, and RETRIEVAL_LLM_API_KEY."
        )
    temperature_raw = values.get("RETRIEVAL_LLM_TEMPERATURE", "0").strip() or "0"
    max_tokens_raw = values.get("RETRIEVAL_LLM_MAX_TOKENS", "800").strip() or "800"
    timeout_raw = values.get("RETRIEVAL_LLM_TIMEOUT_SECONDS", "30").strip() or "30"
    try:
        temperature = float(temperature_raw)
    except ValueError as exc:
        raise ValueError("RETRIEVAL_LLM_TEMPERATURE must be a number.") from exc
    try:
        max_tokens = int(max_tokens_raw)
    except ValueError as exc:
        raise ValueError("RETRIEVAL_LLM_MAX_TOKENS must be an integer.") from exc
    try:
        timeout_seconds = int(timeout_raw)
    except ValueError as exc:
        raise ValueError("RETRIEVAL_LLM_TIMEOUT_SECONDS must be an integer.") from exc
    return RunLLMConfig(
        api_style=api_style,
        model=model,
        endpoint_url=endpoint_url,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
    )


@dataclass(frozen=True)
class ConnectedSourceDocument:
    """One optional external or attached source visible to workspace retrieval."""

    source_category: SourceCategory
    source_id: str
    title: str
    content: str
    metadata: Mapping[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "source_category": self.source_category.value,
            "source_id": self.source_id,
            "title": self.title,
            "content": self.content,
            "metadata": dict(self.metadata),
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

    def to_dict(self) -> dict[str, object]:
        return {
            "category": self.category.value,
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
    run_dir: str | None = None
    chunk_line_count: int = 40
    chunk_line_overlap: int = 10
    max_exploration_rounds: int = 3
    max_tool_calls_per_round: int = 5
    cgc_enabled: bool = True
    cgc_command: tuple[str, ...] = field(default_factory=_default_cgc_command)
    cgc_repo_path: str | None = None
    cgc_db_path: str = field(default_factory=_default_cgc_db_path)
    cgc_force_reindex_each_request: bool = True
    cgc_timeout_seconds: int = 60
    cgc_max_files_for_bm25: int = 20
    enabled_source_categories: tuple[SourceCategory, ...] = DEFAULT_ALLOWED_SOURCE_CATEGORIES
    reindex_policy: str = WORKSPACE_REINDEX_POLICY_ALWAYS
    retrieval_model_settings: Mapping[str, str] = field(default_factory=dict)
    issue_tracker_documents: tuple[ConnectedSourceDocument, ...] = field(default_factory=tuple)
    pull_request_documents: tuple[ConnectedSourceDocument, ...] = field(default_factory=tuple)
    notebooklm_documents: tuple[ConnectedSourceDocument, ...] = field(default_factory=tuple)
    local_note_paths: tuple[str, ...] = field(default_factory=tuple)
    connected_source_adapters: Mapping[str, bool] = field(
        default_factory=lambda: {
            "issue_tracker": True,
            "pull_request": True,
            "local_notes": True,
            "notebooklm": True,
        }
    )

    def source_registry(self) -> tuple[SourceRegistryEntry, ...]:
        return (
            SourceRegistryEntry(
                category=SourceCategory.SOURCE_CODE,
                enabled=SourceCategory.SOURCE_CODE in self.enabled_source_categories,
                indexed=True,
                queryable=True,
                adapter_name="codegraphcontext+bm25",
                note="CGC narrows files first; BM25 searches only inside those narrowed files.",
            ),
            SourceRegistryEntry(
                category=SourceCategory.DOCUMENTATION,
                enabled=SourceCategory.DOCUMENTATION in self.enabled_source_categories,
                indexed=True,
                queryable=True,
                adapter_name="codegraphcontext+bm25",
                note="Workspace docs participate in the same CGC-first narrowing flow.",
            ),
            SourceRegistryEntry(
                category=SourceCategory.ISSUE_TRACKER,
                enabled=SourceCategory.ISSUE_TRACKER in self.enabled_source_categories
                and self.connected_source_adapters.get("issue_tracker", True),
                indexed=False,
                queryable=bool(self.issue_tracker_documents),
                adapter_name="connected_documents",
                note="Issue tracker context is supplied as connected documents in v1.",
            ),
            SourceRegistryEntry(
                category=SourceCategory.PULL_REQUEST,
                enabled=SourceCategory.PULL_REQUEST in self.enabled_source_categories
                and self.connected_source_adapters.get("pull_request", True),
                indexed=False,
                queryable=bool(self.pull_request_documents),
                adapter_name="connected_documents",
                note="Pull request context is supplied as connected documents in v1.",
            ),
            SourceRegistryEntry(
                category=SourceCategory.LOCAL_NOTES,
                enabled=SourceCategory.LOCAL_NOTES in self.enabled_source_categories
                and self.connected_source_adapters.get("local_notes", True),
                indexed=False,
                queryable=bool(self.local_note_paths),
                adapter_name="local_note_files",
                note="Local notes are read directly from configured paths in v1.",
            ),
            SourceRegistryEntry(
                category=SourceCategory.NOTEBOOKLM,
                enabled=SourceCategory.NOTEBOOKLM in self.enabled_source_categories
                and self.connected_source_adapters.get("notebooklm", True),
                indexed=False,
                queryable=bool(self.notebooklm_documents),
                adapter_name="connected_documents",
                note="NotebookLM context is attached as provided text snippets in v1.",
            ),
        )

    def validate(self) -> None:
        if self.reindex_policy != WORKSPACE_REINDEX_POLICY_ALWAYS:
            raise ValueError("Workspace retrieval currently supports only reindex_policy='always'.")
        if self.max_exploration_rounds <= 0:
            raise ValueError("max_exploration_rounds must be greater than zero.")
        if self.max_tool_calls_per_round <= 0:
            raise ValueError("max_tool_calls_per_round must be greater than zero.")
        if not self.cgc_enabled:
            raise ValueError("Workspace retrieval requires cgc_enabled=True.")
        if not self.cgc_command:
            raise ValueError("Workspace retrieval requires a non-empty cgc_command.")
        if self.cgc_timeout_seconds <= 0:
            raise ValueError("cgc_timeout_seconds must be greater than zero.")
        if self.cgc_max_files_for_bm25 <= 0:
            raise ValueError("cgc_max_files_for_bm25 must be greater than zero.")
        if self.chunk_line_count <= 0:
            raise ValueError("chunk_line_count must be greater than zero.")
        if self.chunk_line_overlap < 0 or self.chunk_line_overlap >= self.chunk_line_count:
            raise ValueError("chunk_line_overlap must be between zero and chunk_line_count - 1.")
        RunConfigController().validate_llm_config(self.llm_config)


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

    api_style: str = "openai_chat_completions"
    model: str = ""
    endpoint_url: str = ""
    api_key: str = ""
    temperature: float = 0.0
    max_tokens: int = 800
    timeout_seconds: int = 30
    planner_strategy: str = "issue_repo_sketch_v1"

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
        }


@dataclass(frozen=True)
class RunConfig:
    """Configuration that ties source policy, retrieval, and logging to one run."""

    run_id: str
    case_id: str
    stage: ResponseStage
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
        if llm_config.api_style not in SUPPORTED_RETRIEVAL_LLM_API_STYLES:
            raise ValueError(
                f"Unsupported retrieval LLM api_style: {llm_config.api_style}. "
                f"Supported values: {', '.join(SUPPORTED_RETRIEVAL_LLM_API_STYLES)}."
            )
        if not llm_config.model:
            raise ValueError("Retrieval LLM config requires model.")
        if not llm_config.endpoint_url:
            raise ValueError("Retrieval LLM config requires endpoint_url.")
        if not llm_config.api_key:
            raise ValueError("Retrieval LLM config requires api_key.")


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
        stage=ResponseStage.EXPLAIN,
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
