from __future__ import annotations

import argparse
import json
import os
import traceback
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TOOL_ENV_PATH = ROOT / ".env"

from core.control_layer import ControlLayer
from core.models import AssistanceRequestType, ConversationState, OrchestrationResult
from core.policy import PolicyStage
from core.source_policy import SourceCategory, SourcePolicy
from services.logging.store import JsonlLogger
from services.retrieval.workspace.bm25 import (
    DEFAULT_EXCLUDED_PATHS,
    LEXICAL_RANKING_FLAT_BM25,
    build_index_from_repo,
    bm25_index_schema_version,
    indexable_content_signature,
    save_index,
)
from services.retrieval.workspace.pipeline.index_flow import save_sync_manifest
from services.retrieval.cases import HiddenCodeRepoQACase, VisibleCodeRepoQACase, load_coderepoqa_case
from services.retrieval.config import (
    DEFAULT_CODEX_PROMPT_PROFILE,
    INITIAL_SELECTION_SEMANTIC_OWNER_COMPARISON,
    RETRIEVAL_MODE_CODEX,
    RETRIEVAL_MODE_WORKSPACE,
    SUPPORTED_CODEX_PROMPT_PROFILES,
    SUPPORTED_INITIAL_SELECTION_MODES,
    SUPPORTED_RETRIEVAL_MODES,
    RetrievalEmbeddingConfig,
    RetrievalQdrantConfig,
    RunLLMConfig,
    WorkspaceRetrievalConfig,
    load_retrieval_embedding_config,
    load_retrieval_enable_indexing,
    load_retrieval_qdrant_config,
)
from services.retrieval.codex.cli import resolve_codex_command
from services.retrieval.codex.provider import CodexRetrievalStage
from services.retrieval.workspace import WorkspaceRetrievalStage


DEFAULT_TEST_ROOT = Path(r"C:\Programming\guidedInteligence_testcases")
BATCH_RUNS_ROOT = ROOT / "testing" / "codeRepoQA" / "batch-runs"
CORPUS_CASES_ROOT = ROOT / "testing" / "codeRepoQA" / "corpus" / "cases"
WORKSPACE_STATE_DIR = ".guided-intelligence"
CODE_PATH_PATTERN = re.compile(r"\b(?:[\w.-]+/)+[\w.-]+\.(?:[A-Za-z0-9]+)\b|\b[\w.-]+\.(?:ts|tsx|js|jsx|py|java|go|rs|cs|cpp|c|h|json|md|txt)\b")
IDENTIFIER_PATTERN = re.compile(r"`([A-Za-z_][A-Za-z0-9_]*)`|\b([A-Z][A-Za-z0-9_]{2,})\b")
CODE_REPOQA_STRUCTURAL_INDEX_TIMEOUT_SECONDS = int(os.environ.get("CODEREPOQA_STRUCTURAL_INDEX_TIMEOUT_SECONDS", "900"))
CODE_REPOQA_QDRANT_INDEX_TIMEOUT_SECONDS = 900
CODEREPOQA_GENERATED_PATHS_BY_REPOSITORY: dict[tuple[str, str], tuple[str, ...]] = {
    # TypeScript checks in generated reference output for its compiler tests. The
    # corresponding tests/cases inputs remain searchable because they are authored
    # testcase source and can be relevant evidence.
    ("microsoft", "typescript"): (
        "tests/baselines/reference",
        "tests/baselines/local",
        # The TypeScript lib directory is generated distribution and declaration
        # material, not repository-local implementation evidence for CodeRepoQA.
        # Exclude it as one prefix so BM25, Qdrant, and CodeGraph share the scope.
        "lib",
    ),
}


@dataclass(frozen=True)
class SnapshotResolution:
    repo_pre_commit: str
    strategy: str
    confidence: str
    details: Mapping[str, str]


@dataclass(frozen=True)
class CasePaths:
    case_root: Path
    raw_dir: Path
    repo_dir: Path
    origin_repo_dir: Path
    snapshots_dir: Path
    indexes_dir: Path
    runs_dir: Path


@dataclass(frozen=True)
class BatchRunResult:
    case_id: str
    retrieval_mode: str
    issue_json: str
    status: str
    run_dir: str | None = None
    batch_artifact_dir: str | None = None
    elapsed_seconds: float | None = None
    error: str | None = None


def prepare_index(
    *,
    repo_pre_path: str | Path,
    repo_pre_commit: str,
    index_dir: str | Path,
    chunk_line_count: int = 40,
    chunk_line_overlap: int = 10,
    exclude_paths: Sequence[str] | None = None,
    lexical_ranking_profile: str = LEXICAL_RANKING_FLAT_BM25,
) -> None:
    workspace_root = Path(repo_pre_path).resolve()
    effective_exclude_paths = DEFAULT_EXCLUDED_PATHS if exclude_paths is None else tuple(exclude_paths)
    index = build_index_from_repo(
        repo_path=workspace_root,
        commit=repo_pre_commit,
        chunk_line_count=chunk_line_count,
        chunk_line_overlap=chunk_line_overlap,
        snapshot="pre_resolution",
        visibility="visible_initial",
        origin="coderepoqa_snapshot",
        exclude_paths=exclude_paths,
        lexical_ranking_profile=lexical_ranking_profile,
    )
    save_index(index, index_dir)
    save_sync_manifest(
        Path(index_dir) / "bm25-scope-manifest.json",
        {
            "index_schema_version": bm25_index_schema_version(lexical_ranking_profile),
            "lexical_ranking_profile": lexical_ranking_profile,
            "workspace_root": str(workspace_root),
            "content_signature": indexable_content_signature(
                workspace_root,
                exclude_paths=tuple(effective_exclude_paths),
            ),
            "exclude_paths": list(effective_exclude_paths),
            "chunk_line_count": chunk_line_count,
            "chunk_line_overlap": chunk_line_overlap,
        },
    )


def _remove_structural_index_artifacts(workspace_root: Path) -> None:
    codegraph_dir = workspace_root / ".codegraph"
    if codegraph_dir.exists():
        shutil.rmtree(codegraph_dir)


def run_case(
    *,
    issue_json: str | Path,
    repo_pre_path: str | Path,
    repo_pre_commit: str,
    index_dir: str | Path,
    run_dir: str | Path,
    run_id: str,
    llm_config: RunLLMConfig,
    verification_json: str | Path | None = None,
    origin_repo_dir: str | Path | None = None,
    resolution: SnapshotResolution | None = None,
    retrieval_mode: str = RETRIEVAL_MODE_WORKSPACE,
    codex_command: Sequence[str] = ("codex",),
    codex_model: str = "gpt-5.4-mini",
    codex_prompt_profile: str = DEFAULT_CODEX_PROMPT_PROFILE,
    codex_timeout_seconds: int = 900,
    codex_ignore_user_config: bool = True,
    index_exclude_paths: Sequence[str] | None = None,
    skip_response_generation: bool = False,
    skip_final_evidence_selection: bool = False,
    stop_before_round_zero_qualification: bool = False,
    dormant_island_completion_enabled: bool = False,
    island_frontier_ordinary_scheduling_enabled: bool = False,
    island_frontier_fold_owner_maturation_enabled: bool = False,
    initial_selection_mode: str = INITIAL_SELECTION_SEMANTIC_OWNER_COMPARISON,
    semantic_island_beam_size: int = 4,
    embedding_batch_size: int | None = None,
    embedding_concurrency: int | None = None,
    embedding_cache_path: str | Path | None = None,
    lexical_ranking_profile: str = LEXICAL_RANKING_FLAT_BM25,
) -> OrchestrationResult:
    visible_case, hidden_case = load_coderepoqa_case(
        issue_json,
        repo_pre_path=repo_pre_path,
        repo_pre_commit=repo_pre_commit,
    )
    exclude_paths = _coderepoqa_exclude_paths(visible_case, additional=index_exclude_paths)
    source_policy = SourcePolicy(
        allowed_categories=(SourceCategory.LOCAL_NOTES, SourceCategory.SOURCE_CODE),
        policy_name="coderepoqa_workspace_initial",
    )
    state = ConversationState(
        conversation_id=f"{visible_case.case_id}:{run_id}",
        user_input=_user_prompt(visible_case.title, visible_case.initial_body),
        assistance_request=AssistanceRequestType.UNDERSTAND_CODE,
    )
    workspace_root = Path(repo_pre_path)
    output_dir = Path(run_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    logger = JsonlLogger(output_dir / "orchestration-trace.jsonl")
    retrieval_config = _workspace_retrieval_config_for_case(
        retrieval_mode=retrieval_mode,
        workspace_root=workspace_root,
        index_dir=Path(index_dir),
        run_dir=output_dir,
        repository_name=visible_case.repo_name,
        repository_owner=visible_case.repo_owner,
        llm_config=llm_config,
        exclude_paths=exclude_paths,
        codex_command=codex_command,
        codex_model=codex_model,
        codex_prompt_profile=codex_prompt_profile,
        codex_timeout_seconds=codex_timeout_seconds,
        codex_ignore_user_config=codex_ignore_user_config,
        final_evidence_selection_enabled=not skip_final_evidence_selection,
        stop_before_round_zero_qualification=stop_before_round_zero_qualification,
        dormant_island_completion_enabled=dormant_island_completion_enabled,
        island_frontier_ordinary_scheduling_enabled=island_frontier_ordinary_scheduling_enabled,
        island_frontier_fold_owner_maturation_enabled=island_frontier_fold_owner_maturation_enabled,
        initial_selection_mode=initial_selection_mode,
        semantic_island_beam_size=semantic_island_beam_size,
        embedding_batch_size=embedding_batch_size,
        embedding_concurrency=embedding_concurrency,
        embedding_cache_path=str(embedding_cache_path) if embedding_cache_path is not None else None,
        lexical_ranking_profile=lexical_ranking_profile,
    )
    retrieval_stage = CodexRetrievalStage(retrieval_config) if retrieval_config.retrieval_mode == RETRIEVAL_MODE_CODEX else WorkspaceRetrievalStage(retrieval_config)
    control_layer = ControlLayer(
        policy_stage=PolicyStage(source_policy=source_policy),
        retrieval_stage=retrieval_stage,
        logger=logger,
        response_llm_config=llm_config,
        intent_enabled=True,
        response_generation_enabled=not skip_response_generation,
    )
    result = control_layer.run(state)
    if not result.policy_result.allowed:
        raise RuntimeError(f"Policy result rejected run-case: {result.policy_result.reason}")
    if not result.policy_result.retrieval_required:
        raise RuntimeError("run-case expected retrieval_required=True for Stage 1.")
    if result.retrieval_result is None:
        raise RuntimeError("run-case expected retrieval_result to be present.")
    retrieval_plan = result.retrieval_result.retrieval_summary.get("retrieval_plan", {})
    (output_dir / "retrieval-plan.json").write_text(
        json.dumps(retrieval_plan, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_dir / "evidence-items.json").write_text(
        json.dumps([item.to_dict() for item in result.evidence], indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_dir / "orchestration-result.json").write_text(
        json.dumps(result.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    _write_evaluation_artifacts(
        run_dir=output_dir,
        visible_case=visible_case,
        hidden_case=hidden_case,
        result=result,
        verification=load_verification(verification_json),
        origin_repo_dir=Path(origin_repo_dir) if origin_repo_dir is not None else None,
        resolution=resolution
        or SnapshotResolution(
            repo_pre_commit=repo_pre_commit,
            strategy="explicit_run_case",
            confidence="explicit",
            details={},
        ),
    )
    return result


def evaluate_case(
    *,
    issue_json: str | Path,
    test_root: str | Path = DEFAULT_TEST_ROOT,
    clone_url: str | None = None,
    chunk_line_count: int = 40,
    chunk_line_overlap: int = 10,
    rebuild_index: bool = False,
    verification_json: str | Path | None = None,
    shared_repo_root: str | Path | None = None,
    llm_config: RunLLMConfig,
    retrieval_mode: str = RETRIEVAL_MODE_WORKSPACE,
    codex_command: Sequence[str] = ("codex",),
    codex_model: str = "gpt-5.4-mini",
    codex_prompt_profile: str = DEFAULT_CODEX_PROMPT_PROFILE,
    codex_timeout_seconds: int = 900,
    codex_ignore_user_config: bool = True,
    index_exclude_paths: Sequence[str] | None = None,
    skip_response_generation: bool = False,
    skip_final_evidence_selection: bool = False,
    stop_before_round_zero_qualification: bool = False,
    dormant_island_completion_enabled: bool = False,
    island_frontier_ordinary_scheduling_enabled: bool = False,
    island_frontier_fold_owner_maturation_enabled: bool = False,
    initial_selection_mode: str = INITIAL_SELECTION_SEMANTIC_OWNER_COMPARISON,
    semantic_island_beam_size: int = 4,
    embedding_batch_size: int | None = None,
    embedding_concurrency: int | None = None,
    shared_embedding_cache_root: str | Path | None = None,
    lexical_ranking_profile: str = LEXICAL_RANKING_FLAT_BM25,
) -> Path:
    issue_path = Path(issue_json)
    verification_path = Path(verification_json) if verification_json is not None else _default_verification_path(issue_path)
    verification = load_verification(verification_path)
    seed_case, _hidden_case = load_coderepoqa_case(
        issue_path,
        repo_pre_path="pending",
        repo_pre_commit="pending",
    )
    exclude_paths = _coderepoqa_exclude_paths(seed_case, additional=index_exclude_paths)
    case_paths = _ensure_case_paths(test_root, seed_case.case_id)
    case_paths.raw_dir.mkdir(parents=True, exist_ok=True)
    case_paths.repo_dir.mkdir(parents=True, exist_ok=True)
    case_paths.snapshots_dir.mkdir(parents=True, exist_ok=True)
    case_paths.runs_dir.mkdir(parents=True, exist_ok=True)
    target_issue_path = case_paths.raw_dir / "issue.json"
    if issue_path.resolve() != target_issue_path.resolve():
        shutil.copy2(issue_path, target_issue_path)
    target_verification_path = case_paths.case_root / "verification.json"
    if verification_path is not None and verification_path.exists() and verification_path.resolve() != target_verification_path.resolve():
        shutil.copy2(verification_path, target_verification_path)

    repo_clone_url = clone_url or _default_clone_url(seed_case)
    origin_repo_dir = _origin_repo_dir(case_paths=case_paths, visible_case=seed_case, shared_repo_root=shared_repo_root)
    _clone_or_fetch_repo(repo_clone_url, origin_repo_dir)
    resolution = resolve_repo_pre_snapshot(issue_path, origin_repo_dir, verification=verification)
    snapshot_dir = case_paths.snapshots_dir / resolution.repo_pre_commit[:12]
    if not snapshot_dir.exists():
        _materialize_snapshot(origin_repo_dir, resolution.repo_pre_commit, snapshot_dir)

    _remove_legacy_snapshot_index(snapshot_dir)
    index_dir = _workspace_index_dir(snapshot_dir, lexical_ranking_profile=lexical_ranking_profile)
    if rebuild_index:
        _remove_structural_index_artifacts(snapshot_dir)
    if retrieval_mode != RETRIEVAL_MODE_CODEX and (rebuild_index or not (index_dir / "bm25-index.json").exists()):
        prepare_index(
            repo_pre_path=snapshot_dir,
            repo_pre_commit=resolution.repo_pre_commit,
            index_dir=index_dir,
            chunk_line_count=chunk_line_count,
            chunk_line_overlap=chunk_line_overlap,
            exclude_paths=exclude_paths,
            lexical_ranking_profile=lexical_ranking_profile,
        )

    visible_case, _hidden = load_coderepoqa_case(
        issue_path,
        repo_pre_path=snapshot_dir,
        repo_pre_commit=resolution.repo_pre_commit,
    )
    run_dir = case_paths.runs_dir / _next_run_id(case_paths.runs_dir)
    embedding_cache_path = None
    if shared_embedding_cache_root is not None and retrieval_mode != RETRIEVAL_MODE_CODEX:
        cache_name = f"{visible_case.repo_owner.lower()}__{visible_case.repo_name.lower()}.sqlite3"
        embedding_cache_path = Path(shared_embedding_cache_root) / cache_name
    run_case(
        issue_json=issue_path,
        repo_pre_path=snapshot_dir,
        repo_pre_commit=resolution.repo_pre_commit,
        index_dir=index_dir,
        run_dir=run_dir,
        run_id=run_dir.name,
        llm_config=llm_config,
        verification_json=target_verification_path if target_verification_path.exists() else verification_path,
        origin_repo_dir=origin_repo_dir,
        resolution=resolution,
        retrieval_mode=retrieval_mode,
        codex_command=codex_command,
        codex_model=codex_model,
        codex_prompt_profile=codex_prompt_profile,
        codex_timeout_seconds=codex_timeout_seconds,
        codex_ignore_user_config=codex_ignore_user_config,
        index_exclude_paths=exclude_paths,
        skip_response_generation=skip_response_generation,
        skip_final_evidence_selection=skip_final_evidence_selection,
        stop_before_round_zero_qualification=stop_before_round_zero_qualification,
        dormant_island_completion_enabled=dormant_island_completion_enabled,
        island_frontier_ordinary_scheduling_enabled=island_frontier_ordinary_scheduling_enabled,
        island_frontier_fold_owner_maturation_enabled=island_frontier_fold_owner_maturation_enabled,
        initial_selection_mode=initial_selection_mode,
        semantic_island_beam_size=semantic_island_beam_size,
        embedding_batch_size=embedding_batch_size,
        embedding_concurrency=embedding_concurrency,
        embedding_cache_path=embedding_cache_path,
        lexical_ranking_profile=lexical_ranking_profile,
    )
    _write_run_metadata(
        run_dir=run_dir,
        issue_path=issue_path,
        visible_case=visible_case,
        snapshot_dir=snapshot_dir,
        index_dir=index_dir,
        clone_url=repo_clone_url,
        resolution=resolution,
        verification_path=target_verification_path if target_verification_path.exists() else verification_path,
        origin_repo_dir=origin_repo_dir,
        llm_config=llm_config,
        index_exclude_paths=exclude_paths,
        retrieval_mode=retrieval_mode,
        codex_model=codex_model,
        codex_prompt_profile=codex_prompt_profile,
        skip_response_generation=skip_response_generation,
        skip_final_evidence_selection=skip_final_evidence_selection,
        stop_before_round_zero_qualification=stop_before_round_zero_qualification,
        dormant_island_completion_enabled=dormant_island_completion_enabled,
        island_frontier_ordinary_scheduling_enabled=island_frontier_ordinary_scheduling_enabled,
        island_frontier_fold_owner_maturation_enabled=island_frontier_fold_owner_maturation_enabled,
        initial_selection_mode=initial_selection_mode,
        embedding_cache_path=embedding_cache_path,
        lexical_ranking_profile=lexical_ranking_profile,
    )
    return run_dir


def resolve_repo_pre_snapshot(
    issue_json: str | Path,
    repo_dir: str | Path,
    verification: Mapping[str, Any] | None = None,
) -> SnapshotResolution:
    issue_data = json.loads(Path(issue_json).read_text(encoding="utf-8"))
    verified_commit = _verification_pre_resolution_commit(verification)
    if verified_commit:
        _git(repo_dir, "cat-file", "-e", f"{verified_commit}^{{commit}}")
        return SnapshotResolution(
            repo_pre_commit=verified_commit,
            strategy="verification_base_commit",
            confidence="high",
            details={"source": "verification_json"},
        )
    fixed_by = issue_data.get("fixed_by", [])
    created_at = str(issue_data.get("created_at", ""))

    fixed_commit = _extract_fixed_commit(fixed_by)
    if fixed_commit:
        parent_commit = _git(repo_dir, "rev-parse", f"{fixed_commit}^").strip()
        return SnapshotResolution(
            repo_pre_commit=parent_commit,
            strategy="fixed_by_parent",
            confidence="high",
            details={"fixed_commit": fixed_commit},
        )
    event_commit = _extract_event_commit(issue_data.get("events"))
    if event_commit and not _commit_exists(repo_dir, event_commit):
        event_commit = None

    if not created_at:
        if event_commit:
            parent_commit = _git(repo_dir, "rev-parse", f"{event_commit}^").strip()
            return SnapshotResolution(
                repo_pre_commit=parent_commit,
                strategy="event_commit_parent",
                confidence="medium",
                details={"event_commit": event_commit, "reason": "missing_created_at"},
            )
        raise ValueError("Issue JSON is missing created_at, so repo-pre cannot be resolved.")

    repo_pre_commit = _git(repo_dir, "rev-list", "-1", f"--before={created_at}", "HEAD").strip()
    if repo_pre_commit and event_commit and not _is_ancestor(repo_dir, repo_pre_commit, event_commit):
        parent_commit = _git(repo_dir, "rev-parse", f"{event_commit}^").strip()
        return SnapshotResolution(
            repo_pre_commit=parent_commit,
            strategy="event_commit_parent",
            confidence="medium",
            details={
                "event_commit": event_commit,
                "created_at": created_at,
                "discarded_timestamp_commit": repo_pre_commit,
                "reason": "timestamp_commit_not_ancestor_of_event_commit",
            },
        )
    if not repo_pre_commit:
        if event_commit:
            parent_commit = _git(repo_dir, "rev-parse", f"{event_commit}^").strip()
            return SnapshotResolution(
                repo_pre_commit=parent_commit,
                strategy="event_commit_parent",
                confidence="medium",
                details={"event_commit": event_commit, "created_at": created_at, "reason": "no_commit_before_created_at"},
            )
        root_commits = [line.strip() for line in _git(repo_dir, "rev-list", "--max-parents=0", "HEAD").splitlines() if line.strip()]
        if not root_commits:
            raise RuntimeError(f"No commit found before issue created_at {created_at}.")
        return SnapshotResolution(
            repo_pre_commit=root_commits[0],
            strategy="earliest_available_commit",
            confidence="lower",
            details={"created_at": created_at},
        )
    return SnapshotResolution(
        repo_pre_commit=repo_pre_commit,
        strategy="latest_commit_before_created_at",
        confidence="lower",
        details={"created_at": created_at},
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run CodeRepoQA cases through the workspace retrieval pipeline.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare-index")
    prepare_parser.add_argument("--repo-pre-path", required=True)
    prepare_parser.add_argument("--repo-pre-commit", required=True)
    prepare_parser.add_argument("--index-dir", required=True)
    prepare_parser.add_argument("--chunk-lines", type=int, default=40)
    prepare_parser.add_argument("--chunk-overlap", type=int, default=10)
    prepare_parser.add_argument("--exclude-path", action="append", default=[])

    run_parser = subparsers.add_parser("run-case")
    run_parser.add_argument("--issue-json", required=True)
    run_parser.add_argument("--repo-pre-path", required=True)
    run_parser.add_argument("--repo-pre-commit", required=True)
    run_parser.add_argument("--index-dir", required=True)
    run_parser.add_argument("--run-dir", required=True)
    run_parser.add_argument("--run-id", default="local")
    run_parser.add_argument("--verification-json")
    run_parser.add_argument("--run-config")
    run_parser.add_argument("--retrieval-mode", choices=SUPPORTED_RETRIEVAL_MODES)
    run_parser.add_argument("--codex-command", action="append", default=None)
    run_parser.add_argument("--codex-model")
    run_parser.add_argument("--codex-prompt-profile", choices=SUPPORTED_CODEX_PROMPT_PROFILES)
    run_parser.add_argument("--codex-timeout-seconds", type=int)
    run_parser.add_argument("--exclude-path", action="append", default=[])
    run_parser.add_argument("--skip-response-generation", action="store_true")
    run_parser.add_argument("--skip-final-evidence-selection", action="store_true")
    run_parser.add_argument("--stop-before-round-zero-qualification", action="store_true")
    run_parser.add_argument(
        "--dormant-island-completion",
        dest="dormant_island_completion_enabled",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    run_parser.add_argument(
        "--island-frontier-ordinary-scheduling",
        dest="island_frontier_ordinary_scheduling_enabled",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    run_parser.add_argument(
        "--island-frontier-fold-owner-maturation",
        dest="island_frontier_fold_owner_maturation_enabled",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    run_parser.add_argument("--semantic-island-beam-size", type=int)
    run_parser.add_argument("--initial-selection-mode", choices=SUPPORTED_INITIAL_SELECTION_MODES)
    evaluate_parser = subparsers.add_parser("evaluate-case")
    evaluate_parser.add_argument("--issue-json", required=True)
    evaluate_parser.add_argument("--run-config")
    evaluate_parser.add_argument("--test-root")
    evaluate_parser.add_argument("--clone-url")
    evaluate_parser.add_argument("--chunk-lines", type=int)
    evaluate_parser.add_argument("--chunk-overlap", type=int)
    evaluate_parser.add_argument("--rebuild-index", action="store_true")
    evaluate_parser.add_argument("--verification-json")
    evaluate_parser.add_argument("--shared-repo-root")
    evaluate_parser.add_argument("--retrieval-mode", choices=SUPPORTED_RETRIEVAL_MODES)
    evaluate_parser.add_argument("--codex-command", action="append", default=None)
    evaluate_parser.add_argument("--codex-model")
    evaluate_parser.add_argument("--codex-prompt-profile", choices=SUPPORTED_CODEX_PROMPT_PROFILES)
    evaluate_parser.add_argument("--codex-timeout-seconds", type=int)
    evaluate_parser.add_argument("--exclude-path", action="append", default=[])
    evaluate_parser.add_argument("--skip-response-generation", action="store_true")
    evaluate_parser.add_argument("--skip-final-evidence-selection", action="store_true")
    evaluate_parser.add_argument("--stop-before-round-zero-qualification", action="store_true")
    evaluate_parser.add_argument(
        "--dormant-island-completion",
        dest="dormant_island_completion_enabled",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    evaluate_parser.add_argument(
        "--island-frontier-ordinary-scheduling",
        dest="island_frontier_ordinary_scheduling_enabled",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    evaluate_parser.add_argument(
        "--island-frontier-fold-owner-maturation",
        dest="island_frontier_fold_owner_maturation_enabled",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    evaluate_parser.add_argument("--semantic-island-beam-size", type=int)
    evaluate_parser.add_argument("--initial-selection-mode", choices=SUPPORTED_INITIAL_SELECTION_MODES)
    batch_parser = subparsers.add_parser("evaluate-batch")
    batch_parser.add_argument("--run-config", required=True)
    batch_parser.add_argument("--issue-json", action="append", default=[])
    batch_parser.add_argument("--test-root")
    batch_parser.add_argument("--clone-url")
    batch_parser.add_argument("--chunk-lines", type=int)
    batch_parser.add_argument("--chunk-overlap", type=int)
    batch_parser.add_argument("--rebuild-index", action="store_true")
    batch_parser.add_argument("--semantic-island-beam-size", type=int)
    batch_parser.add_argument("--initial-selection-mode", choices=SUPPORTED_INITIAL_SELECTION_MODES)
    batch_parser.add_argument(
        "--island-frontier-ordinary-scheduling",
        dest="island_frontier_ordinary_scheduling_enabled",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    batch_parser.add_argument(
        "--island-frontier-fold-owner-maturation",
        dest="island_frontier_fold_owner_maturation_enabled",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    batch_parser.add_argument("--shared-repo-root")
    batch_parser.add_argument("--retrieval-mode", choices=SUPPORTED_RETRIEVAL_MODES)
    batch_parser.add_argument("--codex-command", action="append", default=None)
    batch_parser.add_argument("--codex-model")
    batch_parser.add_argument("--codex-prompt-profile", choices=SUPPORTED_CODEX_PROMPT_PROFILES)
    batch_parser.add_argument("--codex-timeout-seconds", type=int)
    compare_batch_parser = subparsers.add_parser("evaluate-compare-batch")
    compare_batch_parser.add_argument("cases", nargs="+")
    compare_batch_parser.add_argument("--workspace-run-config", default="configs/testing/workspace.json")
    compare_batch_parser.add_argument("--codex-run-config", default="configs/testing/codex.json")
    compare_batch_parser.add_argument("--test-root")
    compare_batch_parser.add_argument("--clone-url")
    compare_batch_parser.add_argument("--chunk-lines", type=int)
    compare_batch_parser.add_argument("--chunk-overlap", type=int)
    compare_batch_parser.add_argument("--rebuild-index", action="store_true")
    compare_batch_parser.add_argument("--shared-repo-root")
    compare_batch_parser.add_argument("--codex-command", action="append", default=None)
    compare_batch_parser.add_argument("--codex-model")
    compare_batch_parser.add_argument("--codex-prompt-profile", choices=SUPPORTED_CODEX_PROMPT_PROFILES)
    compare_batch_parser.add_argument("--codex-timeout-seconds", type=int)

    args = parser.parse_args(argv)
    if args.command == "prepare-index":
        prepare_index(
            repo_pre_path=args.repo_pre_path,
            repo_pre_commit=args.repo_pre_commit,
            index_dir=args.index_dir,
            chunk_line_count=args.chunk_lines,
            chunk_line_overlap=args.chunk_overlap,
            exclude_paths=tuple(args.exclude_path) if args.exclude_path else None,
        )
        return 0

    if args.command == "run-case":
        run_config = _load_test_run_config(args.run_config)
        run_case(
            issue_json=args.issue_json,
            repo_pre_path=args.repo_pre_path,
            repo_pre_commit=args.repo_pre_commit,
            index_dir=args.index_dir,
            run_dir=args.run_dir,
            run_id=args.run_id,
            verification_json=args.verification_json,
            llm_config=_load_project_llm_config(run_config),
            retrieval_mode=_config_value(args, run_config, "retrieval_mode", RETRIEVAL_MODE_WORKSPACE),
            codex_command=_codex_command(args, run_config),
            codex_model=_config_value(args, run_config, "codex_model", "gpt-5.4-mini"),
            codex_prompt_profile=_config_value(
                args, run_config, "codex_prompt_profile", DEFAULT_CODEX_PROMPT_PROFILE
            ),
            codex_timeout_seconds=int(_config_value(args, run_config, "codex_timeout_seconds", 900)),
            codex_ignore_user_config=_config_bool(run_config, "codex_ignore_user_config", True),
            index_exclude_paths=tuple(args.exclude_path) if args.exclude_path else None,
            skip_response_generation=bool(
                args.skip_response_generation
                or run_config.get("skip_response_generation", False)
            ),
            skip_final_evidence_selection=bool(
                args.skip_final_evidence_selection
                or run_config.get("skip_final_evidence_selection", False)
            ),
            stop_before_round_zero_qualification=bool(
                args.stop_before_round_zero_qualification
                or run_config.get("stop_before_round_zero_qualification", False)
            ),
            dormant_island_completion_enabled=_config_bool_override(
                args,
                run_config,
                "dormant_island_completion_enabled",
                False,
            ),
            island_frontier_ordinary_scheduling_enabled=_config_bool_override(
                args,
                run_config,
                "island_frontier_ordinary_scheduling_enabled",
                False,
            ),
            island_frontier_fold_owner_maturation_enabled=_config_bool_override(
                args,
                run_config,
                "island_frontier_fold_owner_maturation_enabled",
                False,
            ),
            initial_selection_mode=str(_config_value(
                args,
                run_config,
                "initial_selection_mode",
                INITIAL_SELECTION_SEMANTIC_OWNER_COMPARISON,
            )),
            semantic_island_beam_size=int(
                _config_value(args, run_config, "semantic_island_beam_size", 4)
            ),
            embedding_batch_size=_config_optional_int(run_config, "embedding_batch_size"),
            embedding_concurrency=_config_optional_int(run_config, "embedding_concurrency"),
            embedding_cache_path=run_config.get("embedding_cache_path"),
            lexical_ranking_profile=str(run_config.get("lexical_ranking_profile") or LEXICAL_RANKING_FLAT_BM25),
        )
        return 0

    if args.command == "evaluate-case":
        run_config = _load_test_run_config(args.run_config)
        run_dir = evaluate_case(
            issue_json=args.issue_json,
            test_root=_config_value(args, run_config, "test_root", str(DEFAULT_TEST_ROOT)),
            clone_url=_config_value(args, run_config, "clone_url", None),
            chunk_line_count=int(_config_value(args, run_config, "chunk_lines", 40)),
            chunk_line_overlap=int(_config_value(args, run_config, "chunk_overlap", 10)),
            rebuild_index=bool(args.rebuild_index or run_config.get("rebuild_index", False)),
            verification_json=args.verification_json,
            shared_repo_root=_config_value(args, run_config, "shared_repo_root", None),
            llm_config=_load_project_llm_config(run_config),
            retrieval_mode=_config_value(args, run_config, "retrieval_mode", RETRIEVAL_MODE_WORKSPACE),
            codex_command=_codex_command(args, run_config),
            codex_model=_config_value(args, run_config, "codex_model", "gpt-5.4-mini"),
            codex_prompt_profile=_config_value(
                args, run_config, "codex_prompt_profile", DEFAULT_CODEX_PROMPT_PROFILE
            ),
            codex_timeout_seconds=int(_config_value(args, run_config, "codex_timeout_seconds", 900)),
            codex_ignore_user_config=_config_bool(run_config, "codex_ignore_user_config", True),
            index_exclude_paths=tuple(args.exclude_path) if args.exclude_path else None,
            skip_response_generation=bool(
                args.skip_response_generation
                or run_config.get("skip_response_generation", False)
            ),
            skip_final_evidence_selection=bool(
                args.skip_final_evidence_selection
                or run_config.get("skip_final_evidence_selection", False)
            ),
            stop_before_round_zero_qualification=bool(
                args.stop_before_round_zero_qualification
                or run_config.get("stop_before_round_zero_qualification", False)
            ),
            dormant_island_completion_enabled=_config_bool_override(
                args,
                run_config,
                "dormant_island_completion_enabled",
                False,
            ),
            island_frontier_ordinary_scheduling_enabled=_config_bool_override(
                args,
                run_config,
                "island_frontier_ordinary_scheduling_enabled",
                False,
            ),
            island_frontier_fold_owner_maturation_enabled=_config_bool_override(
                args,
                run_config,
                "island_frontier_fold_owner_maturation_enabled",
                False,
            ),
            initial_selection_mode=str(_config_value(
                args,
                run_config,
                "initial_selection_mode",
                INITIAL_SELECTION_SEMANTIC_OWNER_COMPARISON,
            )),
            semantic_island_beam_size=int(
                _config_value(args, run_config, "semantic_island_beam_size", 4)
            ),
            embedding_batch_size=_config_optional_int(run_config, "embedding_batch_size"),
            embedding_concurrency=_config_optional_int(run_config, "embedding_concurrency"),
            shared_embedding_cache_root=run_config.get("shared_embedding_cache_root"),
            lexical_ranking_profile=str(run_config.get("lexical_ranking_profile") or LEXICAL_RANKING_FLAT_BM25),
        )
        print(str(run_dir))
        return 0

    if args.command == "evaluate-batch":
        run_config = _load_test_run_config(args.run_config)
        cases = tuple(args.issue_json or _string_sequence(run_config.get("cases")))
        if not cases:
            raise ValueError("evaluate-batch requires --issue-json or a non-empty `cases` array in --run-config.")
        case_timeout_seconds = int(run_config.get("case_timeout_seconds", 1800))
        if case_timeout_seconds <= 0:
            raise ValueError("case_timeout_seconds must be greater than zero.")
        for issue_json in cases:
            command = _evaluate_case_subprocess_command(args, issue_json)
            print(f"Starting {issue_json} with a {case_timeout_seconds}s testcase ceiling.", flush=True)
            try:
                subprocess.run(
                    command,
                    cwd=ROOT,
                    check=True,
                    timeout=case_timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(
                    f"Batch stopped: testcase {issue_json} exceeded the explicit "
                    f"{case_timeout_seconds}s wall-clock ceiling."
                ) from exc
            except subprocess.CalledProcessError as exc:
                raise RuntimeError(
                    f"Batch stopped: testcase {issue_json} failed with exit code {exc.returncode}."
                ) from exc
        return 0

    if args.command == "evaluate-compare-batch":
        workspace_run_config = _load_test_run_config(args.workspace_run_config)
        codex_run_config = _load_test_run_config(args.codex_run_config)
        cases = _resolve_compare_batch_cases(args.cases)
        batch_dir = _create_batch_run_dir(BATCH_RUNS_ROOT)
        batch_log_path = batch_dir / "batch-log.jsonl"
        batch_results: list[BatchRunResult] = []
        _write_batch_log(
            batch_log_path,
            "batch_started",
            {
                "cases": list(cases),
                "workspace_run_config": str(args.workspace_run_config),
                "codex_run_config": str(args.codex_run_config),
            },
        )
        for case_issue_json in cases:
            for retrieval_mode, run_config in (
                (RETRIEVAL_MODE_WORKSPACE, workspace_run_config),
                (RETRIEVAL_MODE_CODEX, codex_run_config),
            ):
                started_at = datetime.now(timezone.utc)
                _write_batch_log(
                    batch_log_path,
                    "case_run_started",
                    {
                        "issue_json": case_issue_json,
                        "retrieval_mode": retrieval_mode,
                    },
                )
                try:
                    run_dir = evaluate_case(
                        issue_json=case_issue_json,
                        test_root=_config_value(args, run_config, "test_root", str(DEFAULT_TEST_ROOT)),
                        clone_url=_config_value(args, run_config, "clone_url", None),
                        chunk_line_count=int(_config_value(args, run_config, "chunk_lines", 40)),
                        chunk_line_overlap=int(_config_value(args, run_config, "chunk_overlap", 10)),
                        rebuild_index=bool(args.rebuild_index or run_config.get("rebuild_index", False)),
                        shared_repo_root=_config_value(args, run_config, "shared_repo_root", None),
                        llm_config=_load_project_llm_config(run_config),
                        retrieval_mode=retrieval_mode,
                        codex_command=_codex_command(args, run_config),
                        codex_model=_config_value(args, run_config, "codex_model", "gpt-5.4-mini"),
                        codex_prompt_profile=_config_value(
                            args, run_config, "codex_prompt_profile", DEFAULT_CODEX_PROMPT_PROFILE
                        ),
                        codex_timeout_seconds=int(_config_value(args, run_config, "codex_timeout_seconds", 900)),
                        codex_ignore_user_config=_config_bool(run_config, "codex_ignore_user_config", True),
                    )
                    artifact_dir = _copy_batch_artifacts(batch_dir, case_issue_json, retrieval_mode, run_dir)
                    elapsed_seconds = (datetime.now(timezone.utc) - started_at).total_seconds()
                    result = BatchRunResult(
                        case_id=Path(case_issue_json).parent.name,
                        retrieval_mode=retrieval_mode,
                        issue_json=str(case_issue_json),
                        status="ok",
                        run_dir=str(run_dir),
                        batch_artifact_dir=str(artifact_dir),
                        elapsed_seconds=elapsed_seconds,
                    )
                    batch_results.append(result)
                    _write_batch_log(
                        batch_log_path,
                        "case_run_completed",
                        {
                            "case_id": result.case_id,
                            "retrieval_mode": retrieval_mode,
                            "run_dir": result.run_dir,
                            "batch_artifact_dir": result.batch_artifact_dir,
                            "elapsed_seconds": elapsed_seconds,
                        },
                    )
                    print(f"{result.case_id} [{retrieval_mode}] -> {result.run_dir}")
                except Exception as exc:
                    elapsed_seconds = (datetime.now(timezone.utc) - started_at).total_seconds()
                    result = BatchRunResult(
                        case_id=Path(case_issue_json).parent.name,
                        retrieval_mode=retrieval_mode,
                        issue_json=str(case_issue_json),
                        status="error",
                        elapsed_seconds=elapsed_seconds,
                        error="".join(traceback.format_exception_only(type(exc), exc)).strip(),
                    )
                    batch_results.append(result)
                    _write_batch_log(
                        batch_log_path,
                        "case_run_failed",
                        {
                            "case_id": result.case_id,
                            "retrieval_mode": retrieval_mode,
                            "elapsed_seconds": elapsed_seconds,
                            "error": result.error,
                            "traceback": traceback.format_exc(),
                        },
                    )
                    print(f"{result.case_id} [{retrieval_mode}] -> ERROR: {result.error}")
        _write_batch_summary(
            batch_dir=batch_dir,
            cases=cases,
            workspace_run_config=str(args.workspace_run_config),
            codex_run_config=str(args.codex_run_config),
            results=batch_results,
        )
        _write_batch_log(
            batch_log_path,
            "batch_completed",
            {
                "result_count": len(batch_results),
                "error_count": sum(1 for item in batch_results if item.status != "ok"),
                "summary_path": str(batch_dir / "summary.json"),
            },
        )
        print(str(batch_dir))
        return 0 if all(item.status == "ok" for item in batch_results) else 1

    raise ValueError(f"Unsupported command: {args.command}")


def _load_test_run_config(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    config_path = Path(path)
    data = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError(f"Test run config must be a JSON object: {config_path}")
    return dict(data)


def _load_project_llm_config(run_config: Mapping[str, Any]) -> RunLLMConfig:
    config_path = ROOT / WORKSPACE_STATE_DIR / "config.json"
    secrets_path = ROOT / WORKSPACE_STATE_DIR / "secrets.json"
    if not config_path.exists():
        raise ValueError("LLM config is missing. Configure it in the Workspace tab first.")
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    secrets = json.loads(secrets_path.read_text(encoding="utf-8-sig")) if secrets_path.exists() else {}
    if not isinstance(config, Mapping):
        raise ValueError(f"Project config must be a JSON object: {config_path}")
    if not isinstance(secrets, Mapping):
        secrets = {}
    generation = config.get("generation") if isinstance(config.get("generation"), Mapping) else {}
    connections = config.get("connections") if isinstance(config.get("connections"), Mapping) else {}
    provider = str(run_config.get("generation_provider") or generation.get("provider") or "api").strip()
    if provider == "codex":
        codex = connections.get("codex") if isinstance(connections.get("codex"), Mapping) else {}
        command = codex.get("command", run_config.get("codex_command", ["codex"]))
        if isinstance(command, str):
            command = [command]
        return RunLLMConfig(
            api_style="codex_cli",
            model=str(run_config.get("generation_codex_model") or generation.get("codex_model") or run_config.get("codex_model") or "gpt-5.4-mini").strip(),
            max_tokens=int(generation["max_tokens"]) if generation.get("max_tokens") is not None else None,
            timeout_seconds=int(generation.get("timeout_seconds") or codex.get("timeout_seconds") or 30),
            codex_command=tuple(resolve_codex_command(tuple(str(part) for part in command if str(part).strip()))),
            codex_ignore_user_config=bool(codex.get("ignore_user_config", run_config.get("codex_ignore_user_config", True))),
        )
    api_llm = connections.get("api_llm") if isinstance(connections.get("api_llm"), Mapping) else {}
    secret_api_llm = secrets.get("api_llm") if isinstance(secrets.get("api_llm"), Mapping) else {}
    model = str(run_config.get("generation_api_model") or generation.get("api_model") or api_llm.get("model") or "").strip()
    endpoint_url = str(api_llm.get("endpoint_url") or "").strip()
    api_key = str(secret_api_llm.get("api_key") or "").strip()
    if not model or not endpoint_url or not api_key:
        raise ValueError("OpenAI-compatible API connection requires endpoint URL, API key, and model. Configure it in the Workspace tab first.")
    return RunLLMConfig(
        api_style=str(api_llm.get("api_style") or "openai_chat_completions").strip() or "openai_chat_completions",
        model=model,
        endpoint_url=endpoint_url,
        api_key=api_key,
        temperature=float(api_llm.get("temperature") if api_llm.get("temperature") is not None else 0.0),
        max_tokens=int(generation["max_tokens"]) if generation.get("max_tokens") is not None else None,
        timeout_seconds=int(generation.get("timeout_seconds") or api_llm.get("timeout_seconds") or 30),
        continuity_enabled=False,
    )


def _config_value(args: argparse.Namespace, config: Mapping[str, Any], key: str, default: Any) -> Any:
    value = getattr(args, key, None)
    if value is not None:
        return value
    return config.get(key, default)


def _config_bool(config: Mapping[str, Any], key: str, default: bool) -> bool:
    value = config.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def _config_bool_override(
    args: argparse.Namespace,
    config: Mapping[str, Any],
    key: str,
    default: bool,
) -> bool:
    value = getattr(args, key, None)
    if value is not None:
        return bool(value)
    return _config_bool(config, key, default)


def _config_optional_int(config: Mapping[str, Any], key: str) -> int | None:
    value = config.get(key)
    if value in (None, ""):
        return None
    parsed = int(value)
    if parsed <= 0:
        raise ValueError(f"{key} must be greater than zero.")
    return parsed


def _evaluate_case_subprocess_command(args: argparse.Namespace, issue_json: str) -> list[str]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "evaluate-case",
        "--issue-json",
        str(issue_json),
        "--run-config",
        str(args.run_config),
    ]
    value_options = (
        ("test_root", "--test-root"),
        ("clone_url", "--clone-url"),
        ("chunk_lines", "--chunk-lines"),
        ("chunk_overlap", "--chunk-overlap"),
        ("shared_repo_root", "--shared-repo-root"),
        ("retrieval_mode", "--retrieval-mode"),
        ("codex_model", "--codex-model"),
        ("codex_prompt_profile", "--codex-prompt-profile"),
        ("codex_timeout_seconds", "--codex-timeout-seconds"),
        ("semantic_island_beam_size", "--semantic-island-beam-size"),
        ("initial_selection_mode", "--initial-selection-mode"),
    )
    for attribute, option in value_options:
        value = getattr(args, attribute, None)
        if value is not None:
            command.extend((option, str(value)))
    for token in getattr(args, "codex_command", None) or ():
        command.extend(("--codex-command", str(token)))
    if getattr(args, "rebuild_index", False):
        command.append("--rebuild-index")
    frontier_override = getattr(args, "island_frontier_ordinary_scheduling_enabled", None)
    if frontier_override is not None:
        command.append(
            "--island-frontier-ordinary-scheduling"
            if frontier_override
            else "--no-island-frontier-ordinary-scheduling"
        )
    owner_fold_override = getattr(args, "island_frontier_fold_owner_maturation_enabled", None)
    if owner_fold_override is not None:
        command.append(
            "--island-frontier-fold-owner-maturation"
            if owner_fold_override
            else "--no-island-frontier-fold-owner-maturation"
        )
    return command


def _codex_command(args: argparse.Namespace, config: Mapping[str, Any]) -> tuple[str, ...]:
    if args.codex_command:
        return resolve_codex_command(args.codex_command)
    configured = config.get("codex_command")
    if isinstance(configured, Sequence) and not isinstance(configured, (str, bytes)):
        values = tuple(str(item) for item in configured if str(item).strip())
        if values:
            return resolve_codex_command(values)
    return resolve_codex_command(("codex",))


def _ensure_case_paths(test_root: str | Path, case_id: str) -> CasePaths:
    case_root = Path(test_root) / case_id
    return CasePaths(
        case_root=case_root,
        raw_dir=case_root / "raw",
        repo_dir=case_root / "repo",
        origin_repo_dir=case_root / "repo" / "origin",
        snapshots_dir=case_root / "s",
        indexes_dir=case_root / "indexes",
        runs_dir=case_root / "runs",
    )


def _origin_repo_dir(
    *,
    case_paths: CasePaths,
    visible_case: VisibleCodeRepoQACase,
    shared_repo_root: str | Path | None,
) -> Path:
    if shared_repo_root is None:
        return case_paths.origin_repo_dir
    repo_name = f"{visible_case.repo_owner}-{visible_case.repo_name}"
    return Path(shared_repo_root) / repo_name / "origin"


def _default_verification_path(issue_path: Path) -> Path | None:
    candidate = issue_path.parent.parent / "verification.json"
    if candidate.exists():
        return candidate
    candidate = issue_path.parent / "verification.json"
    if candidate.exists():
        return candidate
    return None


def load_verification(verification_json: str | Path | None) -> Mapping[str, Any] | None:
    if verification_json is None:
        return None
    verification_path = Path(verification_json)
    if not verification_path.exists():
        return None
    data = json.loads(verification_path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError(f"Verification JSON must be an object: {verification_path}")
    return data


def _verification_pre_resolution_commit(verification: Mapping[str, Any] | None) -> str | None:
    if not verification:
        return None
    resolution_artifacts = verification.get("resolution_artifacts")
    if not isinstance(resolution_artifacts, Mapping):
        return None
    github_prs = resolution_artifacts.get("github_prs")
    if not isinstance(github_prs, list):
        return None
    for pr in github_prs:
        if not isinstance(pr, Mapping):
            continue
        base_sha = str(pr.get("base_sha", "")).strip()
        if base_sha:
            return base_sha
    return None


def _next_run_id(runs_dir: Path) -> str:
    base = datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")
    candidate = base
    suffix = 1
    while (runs_dir / candidate).exists():
        suffix += 1
        candidate = f"{base}-{suffix:02d}"
    return candidate


def _default_clone_url(visible_case: VisibleCodeRepoQACase) -> str:
    return f"https://github.com/{visible_case.repo_owner}/{visible_case.repo_name}.git"


def _coderepoqa_exclude_paths(
    visible_case: VisibleCodeRepoQACase,
    *,
    additional: Sequence[str] | None = None,
) -> tuple[str, ...]:
    repository_paths = CODEREPOQA_GENERATED_PATHS_BY_REPOSITORY.get(
        (visible_case.repo_owner.lower(), visible_case.repo_name.lower()),
        (),
    )
    return tuple(dict.fromkeys((*DEFAULT_EXCLUDED_PATHS, *repository_paths, *(additional or ()))))


def _clone_or_fetch_repo(clone_url: str, repo_dir: Path) -> None:
    if repo_dir.exists():
        _git(repo_dir, "config", "core.longpaths", "true")
        _git(repo_dir, "fetch", "--all", "--tags", "--prune")
        return
    repo_dir.parent.mkdir(parents=True, exist_ok=True)
    _git(repo_dir.parent, "clone", "--no-checkout", clone_url, repo_dir.name)
    _git(repo_dir, "config", "core.longpaths", "true")


def _materialize_snapshot(origin_repo_dir: Path, commit: str, snapshot_dir: Path) -> None:
    snapshot_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        _git(snapshot_dir.parent, "clone", "--local", "--no-checkout", str(origin_repo_dir), snapshot_dir.name)
        _git(snapshot_dir, "config", "core.longpaths", "true")
        _git(snapshot_dir, "checkout", "--detach", commit)
    except Exception:
        if snapshot_dir.exists():
            shutil.rmtree(snapshot_dir, ignore_errors=True)
        raise


def _remove_legacy_snapshot_index(snapshot_dir: Path) -> None:
    legacy_index_dir = snapshot_dir / "index"
    if (legacy_index_dir / "bm25-index.json").exists():
        shutil.rmtree(legacy_index_dir, ignore_errors=True)


def _workspace_index_dir(
    workspace_root: Path,
    *,
    lexical_ranking_profile: str = LEXICAL_RANKING_FLAT_BM25,
) -> Path:
    suffix = "index" if lexical_ranking_profile == LEXICAL_RANKING_FLAT_BM25 else f"index-{lexical_ranking_profile.replace('_', '-')}"
    return workspace_root / WORKSPACE_STATE_DIR / suffix


def _write_run_metadata(
    *,
    run_dir: Path,
    issue_path: Path,
    visible_case: VisibleCodeRepoQACase,
    snapshot_dir: Path,
    index_dir: Path,
    clone_url: str,
    resolution: SnapshotResolution,
    verification_path: Path | None,
    origin_repo_dir: Path,
    llm_config: RunLLMConfig,
    index_exclude_paths: Sequence[str],
    retrieval_mode: str,
    codex_model: str,
    codex_prompt_profile: str,
    skip_response_generation: bool,
    skip_final_evidence_selection: bool,
    stop_before_round_zero_qualification: bool,
    dormant_island_completion_enabled: bool,
    island_frontier_ordinary_scheduling_enabled: bool,
    island_frontier_fold_owner_maturation_enabled: bool,
    initial_selection_mode: str,
    embedding_cache_path: Path | None = None,
    lexical_ranking_profile: str = LEXICAL_RANKING_FLAT_BM25,
) -> None:
    metadata = {
        "case_id": visible_case.case_id,
        "issue_json": str(issue_path),
        "clone_url": clone_url,
        "origin_repo_dir": str(origin_repo_dir),
        "verification_json": str(verification_path) if verification_path is not None and verification_path.exists() else "",
        "repo_pre_commit": visible_case.repo_pre_commit,
        "repo_pre_path": str(snapshot_dir),
        "index_dir": str(index_dir),
        "index_exclude_paths": list(index_exclude_paths),
        "retrieval_mode": retrieval_mode,
        "codex_model": codex_model if retrieval_mode == RETRIEVAL_MODE_CODEX else "",
        "codex_prompt_profile": codex_prompt_profile if retrieval_mode == RETRIEVAL_MODE_CODEX else "",
        "skip_response_generation": skip_response_generation,
        "skip_final_evidence_selection": skip_final_evidence_selection,
        "stop_before_round_zero_qualification": stop_before_round_zero_qualification,
        "dormant_island_completion_enabled": dormant_island_completion_enabled,
        "island_frontier_ordinary_scheduling_enabled": island_frontier_ordinary_scheduling_enabled,
        "island_frontier_fold_owner_maturation_enabled": island_frontier_fold_owner_maturation_enabled,
        "initial_selection_mode": initial_selection_mode,
        "embedding_cache_path": str(embedding_cache_path) if embedding_cache_path is not None else "",
        "lexical_ranking_profile": lexical_ranking_profile,
        "intent_system": "request_analysis_obligations_v1",
        "resolution": {
            "strategy": resolution.strategy,
            "confidence": resolution.confidence,
            "details": dict(resolution.details),
        },
        "llm_config": llm_config.public_dict(),
        "created_at": visible_case.created_at,
        "run_created_at": datetime.now(timezone.utc).isoformat(),
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run-metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _write_evaluation_artifacts(
    *,
    run_dir: Path,
    visible_case: VisibleCodeRepoQACase,
    hidden_case: HiddenCodeRepoQACase,
    result: OrchestrationResult,
    verification: Mapping[str, Any] | None,
    origin_repo_dir: Path | None,
    resolution: SnapshotResolution,
) -> None:
    oracle = _build_evaluator_oracle(
        hidden_case=hidden_case,
        verification=verification,
        origin_repo_dir=origin_repo_dir,
        resolution=resolution,
    )
    comparison = _build_evaluator_comparison(
        visible_case=visible_case,
        result=result,
        verification=verification,
        oracle=oracle,
    )
    (run_dir / "evaluator-comparison.json").write_text(
        json.dumps(comparison, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (run_dir / "scorecard.json").write_text(
        json.dumps(
            {
                "case_id": visible_case.case_id,
                "oracle_file_count": len(comparison["oracle_files"]),
                "retrieved_source_file_count": len(comparison["retrieved_source_files"]),
                "overlap_count": len(comparison["overlap_files"]),
                "implementation_overlap_count": len(comparison["implementation_overlap_files"]),
                "top_retrieved_files": comparison["retrieved_source_files"][:5],
                "top_k": comparison["top_k"],
                "verification_json_used": bool(verification),
                "oracle_source": comparison["oracle_source"],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (run_dir / "evaluator-comparison.md").write_text(
        _comparison_markdown(comparison),
        encoding="utf-8",
    )


def _build_evaluator_oracle(
    *,
    hidden_case: HiddenCodeRepoQACase,
    origin_repo_dir: Path | None,
    resolution: SnapshotResolution,
    verification: Mapping[str, Any] | None = None,
) -> dict[str, object]:
    if verification:
        oracle = verification.get("oracle")
        if isinstance(oracle, Mapping):
            implementation_files = _normalize_path_sequence(oracle.get("implementation_files"))
            test_files = _normalize_path_sequence(oracle.get("test_or_validation_files"))
            documentation_files = _normalize_path_sequence(oracle.get("documentation_files"))
            thread_files = _normalize_path_sequence(oracle.get("thread_file_refs"))
            files = tuple(_ordered_unique((*implementation_files, *test_files, *documentation_files)))
            return {
                "files": list(files),
                "implementation_files": list(implementation_files),
                "test_or_validation_files": list(test_files),
                "documentation_files": list(documentation_files),
                "symbols": _string_sequence(oracle.get("symbols_or_apis")),
                "source": {
                    "verification_json": True,
                    "verification_case_id": str(verification.get("case_id", "")),
                    "verification_group": str(verification.get("primary_group", "")),
                    "thread_file_refs": bool(thread_files),
                    "subsystem": str(oracle.get("subsystem", "")),
                    "responsibility_summary": str(oracle.get("responsibility_summary", "")),
                    "hidden_resolution_summary": str(oracle.get("hidden_resolution_summary", "")),
                },
            }
    hidden_fields = hidden_case.hidden_fields
    fixed_commit = _extract_fixed_commit(hidden_fields.get("fixed_by"))
    event_commit = ""
    if not fixed_commit and resolution.strategy == "event_commit_parent":
        event_commit = _extract_event_commit(hidden_fields.get("events")) or ""
    oracle_commit = fixed_commit or event_commit
    fixed_by_files = _oracle_files_from_commit(oracle_commit, origin_repo_dir)
    comment_file_refs, comment_symbol_refs = _hidden_comment_refs(hidden_fields.get("comments_details"))
    oracle_files = tuple(_ordered_unique((*fixed_by_files, *comment_file_refs)))
    return {
        "files": list(oracle_files),
        "implementation_files": list(oracle_files),
        "test_or_validation_files": [],
        "documentation_files": [],
        "symbols": list(comment_symbol_refs),
        "source": {
            "verification_json": False,
            "fixed_by_changed_files": bool(fixed_by_files),
            "fixed_by_commit": bool(fixed_commit),
            "event_commit": bool(event_commit),
            "hidden_comment_file_refs": bool(comment_file_refs),
            "hidden_comment_symbol_refs": bool(comment_symbol_refs),
        },
    }


def _build_evaluator_comparison(
    *,
    visible_case: VisibleCodeRepoQACase,
    result: OrchestrationResult,
    verification: Mapping[str, Any] | None,
    oracle: Mapping[str, object],
) -> dict[str, object]:
    retrieved_source_files = _retrieved_source_files(result)
    oracle_files = tuple(str(item) for item in oracle.get("files", ()))
    implementation_files = tuple(str(item) for item in oracle.get("implementation_files", ()))
    test_files = tuple(str(item) for item in oracle.get("test_or_validation_files", ()))
    documentation_files = tuple(str(item) for item in oracle.get("documentation_files", ()))
    overlap = tuple(path for path in retrieved_source_files if path in oracle_files)
    implementation_overlap = tuple(path for path in retrieved_source_files if path in implementation_files)
    retrieved_only = tuple(path for path in retrieved_source_files if path not in oracle_files)
    oracle_only = tuple(path for path in oracle_files if path not in retrieved_source_files)
    top_k = _top_k_summary(retrieved_source_files, implementation_files or oracle_files)
    return {
        "case_id": visible_case.case_id,
        "prompt_title": visible_case.title,
        "verification_case_id": str(verification.get("case_id", "")) if verification else "",
        "retrieved_source_files": list(retrieved_source_files),
        "oracle_files": list(oracle_files),
        "oracle_implementation_files": list(implementation_files),
        "oracle_test_or_validation_files": list(test_files),
        "oracle_documentation_files": list(documentation_files),
        "oracle_symbols": list(oracle.get("symbols", ())),
        "overlap_files": list(overlap),
        "implementation_overlap_files": list(implementation_overlap),
        "retrieved_only_files": list(retrieved_only),
        "oracle_only_files": list(oracle_only),
        "top_k": top_k,
        "oracle_source": dict(oracle.get("source", {})),
    }


def _top_k_summary(retrieved_files: Sequence[str], oracle_files: Sequence[str]) -> dict[str, object]:
    positions: dict[str, int] = {}
    for oracle_file in oracle_files:
        try:
            positions[oracle_file] = retrieved_files.index(oracle_file) + 1
        except ValueError:
            continue
    return {
        "k_values": [5, 10, 20],
        "found_positions": positions,
        "found_within_5": any(position <= 5 for position in positions.values()),
        "found_within_10": any(position <= 10 for position in positions.values()),
        "found_within_20": any(position <= 20 for position in positions.values()),
    }


def _oracle_files_from_commit(commit: str | None, origin_repo_dir: Path | None) -> tuple[str, ...]:
    if origin_repo_dir is None or not origin_repo_dir.exists():
        return ()
    if not commit:
        return ()
    parent_commit = _git(origin_repo_dir, "rev-parse", f"{commit}^").strip()
    changed = _git(origin_repo_dir, "diff", "--name-only", parent_commit, commit).splitlines()
    return tuple(_normalize_path(line) for line in changed if line.strip())


def _hidden_comment_refs(comments_details: object) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if not isinstance(comments_details, list):
        return (), ()
    file_refs: list[str] = []
    symbol_refs: list[str] = []
    for item in comments_details:
        if not isinstance(item, Mapping):
            continue
        body = str(item.get("body", ""))
        for match in CODE_PATH_PATTERN.findall(body):
            file_refs.append(_normalize_path(match))
        for backticked, capitalized in IDENTIFIER_PATTERN.findall(body):
            token = backticked or capitalized
            if token and "/" not in token and "." not in token:
                symbol_refs.append(token)
    return tuple(_ordered_unique(file_refs)), tuple(_ordered_unique(symbol_refs))


def _retrieved_source_files(result: OrchestrationResult) -> tuple[str, ...]:
    files: list[str] = []
    for item in result.evidence:
        if item.source_category != SourceCategory.SOURCE_CODE:
            continue
        path = item.metadata.get("path", "")
        if not path:
            path = _path_from_source_id(item.source_id)
        if path:
            files.append(_normalize_path(path))
    return tuple(_ordered_unique(files))


def _path_from_source_id(source_id: str) -> str:
    if source_id.startswith("repo-pre:"):
        without_prefix = source_id[len("repo-pre:") :]
        return without_prefix.split(":L", 1)[0]
    return source_id


def _comparison_markdown(comparison: Mapping[str, object]) -> str:
    def _section(title: str, items: Sequence[str]) -> str:
        if not items:
            return f"## {title}\n\n- none\n"
        return "## " + title + "\n\n" + "\n".join(f"- {item}" for item in items) + "\n"

    top_k = comparison.get("top_k", {})
    top_k_lines: list[str] = []
    if isinstance(top_k, Mapping):
        found_positions = top_k.get("found_positions", {})
        top_k_lines = [
            f"- found within 5: {bool(top_k.get('found_within_5'))}",
            f"- found within 10: {bool(top_k.get('found_within_10'))}",
            f"- found within 20: {bool(top_k.get('found_within_20'))}",
        ]
        if isinstance(found_positions, Mapping) and found_positions:
            top_k_lines.extend(f"- {path}: rank {rank}" for path, rank in found_positions.items())
    top_k_section = "## Top K\n\n" + ("\n".join(top_k_lines) if top_k_lines else "- none") + "\n"

    return (
        f"# Evaluator Comparison\n\n"
        f"Case: `{comparison['case_id']}`\n\n"
        + _section("Retrieved Source Files", tuple(str(item) for item in comparison.get("retrieved_source_files", ())))
        + "\n"
        + _section("Oracle Implementation Files", tuple(str(item) for item in comparison.get("oracle_implementation_files", ())))
        + "\n"
        + _section("Oracle Files", tuple(str(item) for item in comparison.get("oracle_files", ())))
        + "\n"
        + _section("Overlap Files", tuple(str(item) for item in comparison.get("overlap_files", ())))
        + "\n"
        + _section("Implementation Overlap Files", tuple(str(item) for item in comparison.get("implementation_overlap_files", ())))
        + "\n"
        + top_k_section
        + "\n"
        + _section("Retrieved Only Files", tuple(str(item) for item in comparison.get("retrieved_only_files", ())))
        + "\n"
        + _section("Oracle Only Files", tuple(str(item) for item in comparison.get("oracle_only_files", ())))
    )


def _extract_fixed_commit(fixed_by: object) -> str | None:
    if not isinstance(fixed_by, list):
        return None
    for item in fixed_by:
        if not isinstance(item, dict):
            continue
        for key in ("commit", "commit_sha", "sha"):
            value = item.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def _extract_event_commit(events: object) -> str | None:
    if not isinstance(events, list):
        return None
    for item in events:
        if not isinstance(item, Mapping):
            continue
        event_type = str(item.get("event", "")).strip().lower()
        raw_commit_id = item.get("commit_id")
        commit_id = raw_commit_id.strip() if isinstance(raw_commit_id, str) else ""
        if event_type in {"referenced", "closed"} and commit_id:
            return commit_id
    return None


def _is_ancestor(repo_dir: str | Path, ancestor: str, descendant: str) -> bool:
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=str(repo_dir),
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.returncode == 0


def _commit_exists(repo_dir: str | Path, commit: str) -> bool:
    completed = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
        cwd=str(repo_dir),
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.returncode == 0


def _git(cwd: str | Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed in {cwd}: {completed.stderr.strip() or completed.stdout.strip()}"
        )
    return completed.stdout


def _user_prompt(title: str, body: str) -> str:
    return f"Explain the code context needed for this issue.\n\nTitle: {title}\n\n{body}"


def _workspace_retrieval_config_for_case(
    *,
    retrieval_mode: str,
    workspace_root: Path,
    index_dir: Path,
    run_dir: Path,
    repository_name: str = "",
    repository_owner: str = "",
    llm_config: RunLLMConfig,
    exclude_paths: Sequence[str],
    codex_command: Sequence[str],
    codex_model: str,
    codex_prompt_profile: str,
    codex_timeout_seconds: int,
    codex_ignore_user_config: bool,
    final_evidence_selection_enabled: bool = True,
    stop_before_round_zero_qualification: bool = False,
    dormant_island_completion_enabled: bool = False,
    island_frontier_ordinary_scheduling_enabled: bool = False,
    island_frontier_fold_owner_maturation_enabled: bool = False,
    initial_selection_mode: str = INITIAL_SELECTION_SEMANTIC_OWNER_COMPARISON,
    semantic_island_beam_size: int = 4,
    embedding_batch_size: int | None = None,
    embedding_concurrency: int | None = None,
    embedding_cache_path: str | None = None,
    lexical_ranking_profile: str = LEXICAL_RANKING_FLAT_BM25,
) -> WorkspaceRetrievalConfig:
    # Shared boundary: both testcase retrieval modes receive the same sanitized
    # ConversationState.user_input built by _user_prompt(title, initial_body).
    if retrieval_mode == RETRIEVAL_MODE_CODEX:
        embedding_config = RetrievalEmbeddingConfig(
            model="codex-not-used",
            endpoint_url="http://codex-not-used",
            api_key="codex-not-used",
        )
        qdrant_config = RetrievalQdrantConfig(
            url="http://codex-not-used",
            collection_name="codex_not_used",
        )
    else:
        loaded_embedding_config = load_retrieval_embedding_config(TOOL_ENV_PATH)
        embedding_config = RetrievalEmbeddingConfig(
            api_style=loaded_embedding_config.api_style,
            model=loaded_embedding_config.model,
            endpoint_url=loaded_embedding_config.endpoint_url,
            api_key=loaded_embedding_config.api_key,
            timeout_seconds=loaded_embedding_config.timeout_seconds,
            batch_size=embedding_batch_size or loaded_embedding_config.batch_size,
            concurrency=embedding_concurrency or loaded_embedding_config.concurrency,
        )
        qdrant_config = load_retrieval_qdrant_config(TOOL_ENV_PATH)
    return WorkspaceRetrievalConfig(
        workspace_root=str(workspace_root),
        index_dir=str(index_dir),
        run_dir=str(run_dir),
        repository_name=repository_name,
        repository_owner=repository_owner,
        llm_config=llm_config,
        embedding_config=embedding_config,
        qdrant_config=qdrant_config,
        embedding_cache_path=embedding_cache_path,
        lexical_ranking_profile=lexical_ranking_profile,
        retrieval_mode=retrieval_mode,
        codex_command=tuple(codex_command) or ("codex",),
        codex_model=codex_model,
        codex_prompt_profile=codex_prompt_profile,
        codex_timeout_seconds=codex_timeout_seconds,
        codex_ignore_user_config=codex_ignore_user_config,
        final_evidence_selection_enabled=final_evidence_selection_enabled,
        stop_before_round_zero_qualification=stop_before_round_zero_qualification,
        dormant_island_completion_enabled=dormant_island_completion_enabled,
        island_frontier_ordinary_scheduling_enabled=island_frontier_ordinary_scheduling_enabled,
        island_frontier_fold_owner_maturation_enabled=island_frontier_fold_owner_maturation_enabled,
        initial_selection_mode=initial_selection_mode,
        semantic_island_beam_size=semantic_island_beam_size,
        enable_indexing=load_retrieval_enable_indexing(TOOL_ENV_PATH) if retrieval_mode != RETRIEVAL_MODE_CODEX else False,
        structural_graph_timeout_seconds=CODE_REPOQA_STRUCTURAL_INDEX_TIMEOUT_SECONDS,
        qdrant_index_timeout_seconds=CODE_REPOQA_QDRANT_INDEX_TIMEOUT_SECONDS,
        index_exclude_paths=tuple(exclude_paths),
        enabled_source_categories=(SourceCategory.LOCAL_NOTES, SourceCategory.SOURCE_CODE),
    )


def _normalize_path(value: str) -> str:
    return value.strip().replace("\\", "/").strip("/")


def _normalize_path_sequence(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(_ordered_unique([_normalize_path(str(item)) for item in value if str(item).strip()]))


def _string_sequence(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [str(item) for item in value if str(item).strip()]


def _resolve_compare_batch_cases(values: Sequence[str]) -> tuple[str, ...]:
    normalized = [str(value).strip() for value in values if str(value).strip()]
    if not normalized:
        raise ValueError("evaluate-compare-batch requires at least one case id, issue.json path, or `all`.")
    if any(value.lower() == "all" for value in normalized):
        if len(normalized) != 1:
            raise ValueError("Use either `all` or an explicit case list, not both.")
        return tuple(
            str(path)
            for path in sorted(CORPUS_CASES_ROOT.glob("*/issue.json"), key=lambda item: item.parent.name.lower())
        )
    resolved: list[str] = []
    for value in normalized:
        candidate = Path(value)
        if candidate.exists():
            if candidate.is_dir():
                issue_path = candidate / "issue.json"
            else:
                issue_path = candidate
        else:
            issue_path = CORPUS_CASES_ROOT / value / "issue.json"
        if not issue_path.exists():
            raise ValueError(f"Batch case not found: {value}")
        resolved.append(str(issue_path))
    return _ordered_unique(tuple(resolved))


def _create_batch_run_dir(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    numbers: list[int] = []
    for item in root.iterdir():
        if not item.is_dir():
            continue
        prefix = item.name.split("-", 1)[0]
        if prefix.isdigit():
            numbers.append(int(prefix))
    next_number = max(numbers, default=0) + 1
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    batch_dir = root / f"{next_number:03d}-{timestamp}"
    batch_dir.mkdir(parents=True, exist_ok=False)
    return batch_dir


def _copy_batch_artifacts(batch_dir: Path, issue_json: str, retrieval_mode: str, run_dir: Path) -> Path:
    case_id = Path(issue_json).parent.name
    destination = batch_dir / case_id / retrieval_mode / run_dir.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(run_dir, destination)
    return destination


def _write_batch_log(path: Path, event_type: str, payload: Mapping[str, Any]) -> None:
    event = {
        "event_type": event_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "payload": dict(payload),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def _write_batch_summary(
    *,
    batch_dir: Path,
    cases: Sequence[str],
    workspace_run_config: str,
    codex_run_config: str,
    results: Sequence[BatchRunResult],
) -> None:
    summary = {
        "cases": list(cases),
        "workspace_run_config": workspace_run_config,
        "codex_run_config": codex_run_config,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "result_count": len(results),
        "error_count": sum(1 for item in results if item.status != "ok"),
        "results": [
            {
                "case_id": item.case_id,
                "retrieval_mode": item.retrieval_mode,
                "issue_json": item.issue_json,
                "status": item.status,
                "run_dir": item.run_dir,
                "batch_artifact_dir": item.batch_artifact_dir,
                "elapsed_seconds": item.elapsed_seconds,
                "error": item.error,
            }
            for item in results
        ],
    }
    (batch_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        f"# Batch Run {batch_dir.name}",
        "",
        f"- Cases: {len(cases)}",
        f"- Result count: {len(results)}",
        f"- Error count: {summary['error_count']}",
        f"- Workspace config: `{workspace_run_config}`",
        f"- Codex config: `{codex_run_config}`",
        "",
        "| Case | Mode | Status | Elapsed (s) | Run Dir | Batch Copy |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for item in results:
        lines.append(
            "| {case_id} | {mode} | {status} | {elapsed} | {run_dir} | {artifact_dir} |".format(
                case_id=item.case_id,
                mode=item.retrieval_mode,
                status=item.status,
                elapsed=f"{item.elapsed_seconds:.3f}" if item.elapsed_seconds is not None else "",
                run_dir=item.run_dir or "",
                artifact_dir=item.batch_artifact_dir or "",
            )
        )
    (batch_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _ordered_unique(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return tuple(ordered)




if __name__ == "__main__":
    raise SystemExit(main())

