from __future__ import annotations

import argparse
import json
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

from core.control_layer import ControlLayer
from core.models import ConversationState, OrchestrationResult, UserIntent
from core.policy import PolicyStage
from core.source_policy import SourceCategory, SourcePolicy
from core.stages import ResponseStage
from services.logging.store import JsonlLogger
from services.retrieval.bm25 import build_index_from_repo, save_index
from services.retrieval.cases import HiddenCodeRepoQACase, VisibleCodeRepoQACase, load_coderepoqa_case
from services.retrieval.config import (
    RunLLMConfig,
    WorkspaceRetrievalConfig,
    load_retrieval_embedding_config,
    load_retrieval_enable_indexing,
    load_retrieval_llm_config,
    load_retrieval_qdrant_config,
)
from services.retrieval.workspace import WorkspaceRetrievalStage


DEFAULT_TEST_ROOT = Path(r"C:\Programming\guidedInteligence_testcases")
CODE_PATH_PATTERN = re.compile(r"\b(?:[\w.-]+/)+[\w.-]+\.(?:[A-Za-z0-9]+)\b|\b[\w.-]+\.(?:ts|tsx|js|jsx|py|java|go|rs|cs|cpp|c|h|json|md|txt)\b")
IDENTIFIER_PATTERN = re.compile(r"`([A-Za-z_][A-Za-z0-9_]*)`|\b([A-Z][A-Za-z0-9_]{2,})\b")


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


def prepare_index(
    *,
    repo_pre_path: str | Path,
    repo_pre_commit: str,
    index_dir: str | Path,
    chunk_line_count: int = 40,
    chunk_line_overlap: int = 10,
) -> None:
    index = build_index_from_repo(
        repo_path=repo_pre_path,
        commit=repo_pre_commit,
        chunk_line_count=chunk_line_count,
        chunk_line_overlap=chunk_line_overlap,
        snapshot="pre_resolution",
        visibility="visible_initial",
        origin="coderepoqa_snapshot",
    )
    save_index(index, index_dir)


def run_case(
    *,
    issue_json: str | Path,
    repo_pre_path: str | Path,
    repo_pre_commit: str,
    index_dir: str | Path,
    run_dir: str | Path,
    run_id: str,
    llm_config: RunLLMConfig,
    origin_repo_dir: str | Path | None = None,
    resolution: SnapshotResolution | None = None,
) -> OrchestrationResult:
    visible_case, hidden_case = load_coderepoqa_case(
        issue_json,
        repo_pre_path=repo_pre_path,
        repo_pre_commit=repo_pre_commit,
    )
    source_policy = SourcePolicy(
        allowed_categories=(SourceCategory.LOCAL_NOTES, SourceCategory.SOURCE_CODE),
        policy_name="coderepoqa_workspace_initial",
    )
    state = ConversationState(
        conversation_id=f"{visible_case.case_id}:{run_id}",
        user_input=_user_prompt(visible_case.title, visible_case.initial_body),
        current_stage=ResponseStage.EXPLAIN,
        intent=UserIntent.UNDERSTAND_CODE,
    )
    workspace_root = Path(repo_pre_path)
    cgc_repo_path = workspace_root / "src" if (workspace_root / "src").is_dir() else workspace_root
    cgc_db_path = Path(index_dir) / ("cgc-src-kuzu" if cgc_repo_path != workspace_root else "cgc-kuzu")
    output_dir = Path(run_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    logger = JsonlLogger(output_dir / "orchestration-trace.jsonl")
    control_layer = ControlLayer(
        policy_stage=PolicyStage(source_policy=source_policy),
        retrieval_stage=WorkspaceRetrievalStage(
            WorkspaceRetrievalConfig(
                workspace_root=str(workspace_root),
                index_dir=str(index_dir),
                run_dir=str(run_dir),
                llm_config=llm_config,
                embedding_config=load_retrieval_embedding_config(),
                qdrant_config=load_retrieval_qdrant_config(),
                cgc_repo_path=str(cgc_repo_path),
                cgc_db_path=str(cgc_db_path),
                cgc_force_reindex_each_request=False,
                enable_indexing=load_retrieval_enable_indexing(),
                cgc_timeout_seconds=180,
                enabled_source_categories=(SourceCategory.LOCAL_NOTES, SourceCategory.SOURCE_CODE),
            )
        ),
        logger=logger,
        response_llm_config=llm_config,
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
    llm_config: RunLLMConfig,
) -> Path:
    issue_path = Path(issue_json)
    seed_case, _hidden_case = load_coderepoqa_case(
        issue_path,
        repo_pre_path="pending",
        repo_pre_commit="pending",
    )
    case_paths = _ensure_case_paths(test_root, seed_case.case_id)
    case_paths.raw_dir.mkdir(parents=True, exist_ok=True)
    case_paths.repo_dir.mkdir(parents=True, exist_ok=True)
    case_paths.snapshots_dir.mkdir(parents=True, exist_ok=True)
    case_paths.indexes_dir.mkdir(parents=True, exist_ok=True)
    case_paths.runs_dir.mkdir(parents=True, exist_ok=True)
    target_issue_path = case_paths.raw_dir / "issue.json"
    if issue_path.resolve() != target_issue_path.resolve():
        shutil.copy2(issue_path, target_issue_path)

    repo_clone_url = clone_url or _default_clone_url(seed_case)
    _clone_or_fetch_repo(repo_clone_url, case_paths.origin_repo_dir)
    resolution = resolve_repo_pre_snapshot(issue_path, case_paths.origin_repo_dir)
    snapshot_dir = case_paths.snapshots_dir / resolution.repo_pre_commit[:12]
    if not snapshot_dir.exists():
        _materialize_snapshot(case_paths.origin_repo_dir, resolution.repo_pre_commit, snapshot_dir)

    _remove_legacy_snapshot_index(snapshot_dir)
    index_dir = case_paths.indexes_dir / resolution.repo_pre_commit[:12]
    if rebuild_index or not (index_dir / "bm25-index.json").exists():
        prepare_index(
            repo_pre_path=snapshot_dir,
            repo_pre_commit=resolution.repo_pre_commit,
            index_dir=index_dir,
            chunk_line_count=chunk_line_count,
            chunk_line_overlap=chunk_line_overlap,
        )

    visible_case, _hidden = load_coderepoqa_case(
        issue_path,
        repo_pre_path=snapshot_dir,
        repo_pre_commit=resolution.repo_pre_commit,
    )
    run_dir = case_paths.runs_dir / _next_run_id(case_paths.runs_dir)
    run_case(
        issue_json=issue_path,
        repo_pre_path=snapshot_dir,
        repo_pre_commit=resolution.repo_pre_commit,
        index_dir=index_dir,
        run_dir=run_dir,
        run_id=run_dir.name,
        llm_config=llm_config,
        origin_repo_dir=case_paths.origin_repo_dir,
        resolution=resolution,
    )
    _write_run_metadata(
        run_dir=run_dir,
        issue_path=issue_path,
        visible_case=visible_case,
        snapshot_dir=snapshot_dir,
        index_dir=index_dir,
        clone_url=repo_clone_url,
        resolution=resolution,
        llm_config=llm_config,
    )
    return run_dir


def resolve_repo_pre_snapshot(
    issue_json: str | Path,
    repo_dir: str | Path,
) -> SnapshotResolution:
    issue_data = json.loads(Path(issue_json).read_text(encoding="utf-8"))
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

    run_parser = subparsers.add_parser("run-case")
    run_parser.add_argument("--issue-json", required=True)
    run_parser.add_argument("--repo-pre-path", required=True)
    run_parser.add_argument("--repo-pre-commit", required=True)
    run_parser.add_argument("--index-dir", required=True)
    run_parser.add_argument("--run-dir", required=True)
    run_parser.add_argument("--run-id", default="local")
    evaluate_parser = subparsers.add_parser("evaluate-case")
    evaluate_parser.add_argument("--issue-json", required=True)
    evaluate_parser.add_argument("--test-root", default=str(DEFAULT_TEST_ROOT))
    evaluate_parser.add_argument("--clone-url")
    evaluate_parser.add_argument("--chunk-lines", type=int, default=40)
    evaluate_parser.add_argument("--chunk-overlap", type=int, default=10)
    evaluate_parser.add_argument("--rebuild-index", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "prepare-index":
        prepare_index(
            repo_pre_path=args.repo_pre_path,
            repo_pre_commit=args.repo_pre_commit,
            index_dir=args.index_dir,
            chunk_line_count=args.chunk_lines,
            chunk_line_overlap=args.chunk_overlap,
        )
        return 0

    if args.command == "run-case":
        run_case(
            issue_json=args.issue_json,
            repo_pre_path=args.repo_pre_path,
            repo_pre_commit=args.repo_pre_commit,
            index_dir=args.index_dir,
            run_dir=args.run_dir,
            run_id=args.run_id,
            llm_config=load_retrieval_llm_config(),
        )
        return 0

    if args.command == "evaluate-case":
        run_dir = evaluate_case(
            issue_json=args.issue_json,
            test_root=args.test_root,
            clone_url=args.clone_url,
            chunk_line_count=args.chunk_lines,
            chunk_line_overlap=args.chunk_overlap,
            rebuild_index=args.rebuild_index,
            llm_config=load_retrieval_llm_config(),
        )
        print(str(run_dir))
        return 0

    raise ValueError(f"Unsupported command: {args.command}")


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


def _write_run_metadata(
    *,
    run_dir: Path,
    issue_path: Path,
    visible_case: VisibleCodeRepoQACase,
    snapshot_dir: Path,
    index_dir: Path,
    clone_url: str,
    resolution: SnapshotResolution,
    llm_config: RunLLMConfig,
) -> None:
    metadata = {
        "case_id": visible_case.case_id,
        "issue_json": str(issue_path),
        "clone_url": clone_url,
        "repo_pre_commit": visible_case.repo_pre_commit,
        "repo_pre_path": str(snapshot_dir),
        "index_dir": str(index_dir),
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
    origin_repo_dir: Path | None,
    resolution: SnapshotResolution,
) -> None:
    oracle = _build_evaluator_oracle(hidden_case=hidden_case, origin_repo_dir=origin_repo_dir, resolution=resolution)
    comparison = _build_evaluator_comparison(
        visible_case=visible_case,
        result=result,
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
                "top_retrieved_files": comparison["retrieved_source_files"][:5],
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
) -> dict[str, object]:
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
        "symbols": list(comment_symbol_refs),
        "source": {
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
    oracle: Mapping[str, object],
) -> dict[str, object]:
    retrieved_source_files = _retrieved_source_files(result)
    oracle_files = tuple(str(item) for item in oracle.get("files", ()))
    overlap = tuple(path for path in retrieved_source_files if path in oracle_files)
    retrieved_only = tuple(path for path in retrieved_source_files if path not in oracle_files)
    oracle_only = tuple(path for path in oracle_files if path not in retrieved_source_files)
    return {
        "case_id": visible_case.case_id,
        "prompt_title": visible_case.title,
        "retrieved_source_files": list(retrieved_source_files),
        "oracle_files": list(oracle_files),
        "oracle_symbols": list(oracle.get("symbols", ())),
        "overlap_files": list(overlap),
        "retrieved_only_files": list(retrieved_only),
        "oracle_only_files": list(oracle_only),
        "oracle_source": dict(oracle.get("source", {})),
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

    return (
        f"# Evaluator Comparison\n\n"
        f"Case: `{comparison['case_id']}`\n\n"
        + _section("Retrieved Source Files", tuple(str(item) for item in comparison.get("retrieved_source_files", ())))
        + "\n"
        + _section("Oracle Files", tuple(str(item) for item in comparison.get("oracle_files", ())))
        + "\n"
        + _section("Overlap Files", tuple(str(item) for item in comparison.get("overlap_files", ())))
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
        commit_id = str(item.get("commit_id", "")).strip()
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


def _normalize_path(value: str) -> str:
    return value.strip().replace("\\", "/").strip("/")


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
