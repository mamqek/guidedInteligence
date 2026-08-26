from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.models import EvidenceItem, ResponsePayload, RetrievalResult, TurnType
from core.source_policy import SourceCategory
from services.retrieval.config import RunLLMConfig
from services.intent.logging import IntentStageResult
from services.intent.models import IntentClassification, SolutionPressure, Specificity, TargetState, TaskIntent, TurnRelation
from services.retrieval.workspace.bm25 import DEFAULT_EXCLUDED_PATHS, indexable_content_signature, load_index
from testing.codeRepoQA.run_case import (
    _coderepoqa_exclude_paths,
    main,
    evaluate_case,
    prepare_index,
    resolve_repo_pre_snapshot,
    run_case,
    SnapshotResolution,
    _build_evaluator_oracle,
    _hidden_comment_refs,
)


class CodeRepoQAHarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        _RecordingWorkspaceRetrievalStage.instances = []
        _RecordingWorkspaceRetrievalStage.captured_states = []

    def test_case_loader_splits_visible_and_hidden_fields(self) -> None:
        from services.retrieval.cases import load_coderepoqa_case

        issue_json = Path("testing/codeRepoQA/6.json")
        visible, hidden = load_coderepoqa_case(issue_json, repo_pre_path="repo-pre", repo_pre_commit="abc123")

        self.assertEqual(visible.repo_owner, "microsoft")
        self.assertEqual(visible.repo_name, "TypeScript")
        self.assertIn("abstract class Base", visible.initial_body)
        self.assertIn("comments_details", hidden.hidden_fields)
        self.assertNotIn("comments_details", visible.to_dict())

    def test_coderepoqa_excludes_repository_generated_outputs(self) -> None:
        from services.retrieval.cases import load_coderepoqa_case

        visible, _hidden = load_coderepoqa_case(
            Path("testing/codeRepoQA/6.json"),
            repo_pre_path="repo-pre",
            repo_pre_commit="abc123",
        )

        excludes = _coderepoqa_exclude_paths(visible, additional=("custom-output",))

        self.assertIn("tests/baselines/reference", excludes)
        self.assertIn("tests/baselines/local", excludes)
        self.assertIn("lib", excludes)
        self.assertIn("custom-output", excludes)
        self.assertNotIn("tests/cases", excludes)

    def test_evaluate_batch_stops_at_explicit_testcase_ceiling(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "batch.json"
            config_path.write_text(
                json.dumps({"cases": ["case/issue.json"], "case_timeout_seconds": 7}),
                encoding="utf-8",
            )
            with patch(
                "testing.codeRepoQA.run_case.subprocess.run",
                side_effect=subprocess.TimeoutExpired(["python"], timeout=7),
            ):
                with self.assertRaisesRegex(RuntimeError, "explicit 7s wall-clock ceiling"):
                    main(["evaluate-batch", "--run-config", str(config_path)])

    def test_prepare_index_supports_overlapping_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = root / "repo-pre"
            repo.mkdir()
            (repo / "src").mkdir()
            (repo / "src" / "many.ts").write_text(
                "\n".join(f"const line{index} = {index};" for index in range(1, 16)),
                encoding="utf-8",
            )
            index_dir = root / "index"

            prepare_index(
                repo_pre_path=repo,
                repo_pre_commit="abc123",
                index_dir=index_dir,
                chunk_line_count=10,
                chunk_line_overlap=5,
            )
            scope_manifest = json.loads((index_dir / "bm25-scope-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(scope_manifest["workspace_root"], str(repo.resolve()))
            self.assertEqual(scope_manifest["exclude_paths"], list(DEFAULT_EXCLUDED_PATHS))
            self.assertEqual(scope_manifest["content_signature"], indexable_content_signature(repo))
            index = load_index(index_dir)

            self.assertEqual([document.chunk.line_start for document in index.documents], [1, 6, 11])

    def test_run_case_uses_workspace_retrieval_and_visible_prompt_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "testing.codeRepoQA.run_case.WorkspaceRetrievalStage",
            _RecordingWorkspaceRetrievalStage,
        ), patch("core.control_layer.classify_intent", return_value=_intent_result()), patch(
            "core.control_layer._render_response",
            return_value=ResponsePayload(TurnType.GUIDED_EXPLANATION, "test explanation"),
        ):
            root = Path(temp_dir)
            repo = root / "repo-pre"
            repo.mkdir()
            issue_json = root / "issue.json"
            issue_json.write_text(
                json.dumps(
                    {
                        "repository_url": "https://api.github.com/repos/example/repo",
                        "number": 6,
                        "title": "Suggestion: abstract classes",
                        "created_at": "2014-07-15T16:45:03Z",
                        "body": "Support an `abstract` keyword for classes and their methods",
                        "comments_details": [
                            {"body": "Later discussion mentions src/compiler/parser.ts and secret hidden guidance."}
                        ],
                        "fixed_by": [],
                    }
                ),
                encoding="utf-8",
            )

            result = run_case(
                issue_json=issue_json,
                repo_pre_path=repo,
                repo_pre_commit="abc123",
                index_dir=root / "index",
                run_dir=root / "run",
                run_id="unit",
                llm_config=_llm_config(),
                index_exclude_paths=("lib", "tests/cases"),
            )

            self.assertTrue(result.evidence)
            self.assertEqual(len(_RecordingWorkspaceRetrievalStage.instances), 1)
            config = _RecordingWorkspaceRetrievalStage.instances[0].config
            self.assertEqual(config.enabled_source_categories, (SourceCategory.LOCAL_NOTES, SourceCategory.SOURCE_CODE))
            self.assertIn("lib", config.index_exclude_paths)
            self.assertIn("tests/cases", config.index_exclude_paths)
            self.assertFalse(config.dormant_island_completion_enabled)
            prompt = _RecordingWorkspaceRetrievalStage.captured_states[0].user_input
            self.assertIn("Title: Suggestion: abstract classes", prompt)
            self.assertIn("Support an `abstract` keyword", prompt)
            self.assertNotIn("secret hidden guidance", prompt)
            self.assertTrue((root / "run" / "retrieval-plan.json").exists())
            self.assertTrue((root / "run" / "evaluator-comparison.json").exists())
            self.assertTrue((root / "run" / "scorecard.json").exists())

    def test_hidden_comment_refs_extract_explicit_paths_and_symbols_conservatively(self) -> None:
        file_refs, symbol_refs = _hidden_comment_refs(
            [
                {"body": "Look at `AbstractGreeter` and src/compiler/parser.ts for the initial implementation."},
                {"body": "No inference please."},
            ]
        )

        self.assertEqual(file_refs, ("src/compiler/parser.ts",))
        self.assertIn("AbstractGreeter", symbol_refs)

    def test_evaluator_oracle_prefers_fixed_by_changed_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = root / "repo"
            repo.mkdir()
            self._git(repo, "init")
            self._git(repo, "config", "user.name", "Test User")
            self._git(repo, "config", "user.email", "test@example.com")
            (repo / "src").mkdir()
            (repo / "src" / "parser.ts").write_text("const parser = 1;\n", encoding="utf-8")
            self._git(repo, "add", ".")
            self._git_commit(repo, "pre issue", "2014-07-10T12:00:00Z")
            (repo / "src" / "parser.ts").write_text("const parser = 2;\n", encoding="utf-8")
            self._git(repo, "add", ".")
            self._git_commit(repo, "fix", "2014-07-20T12:00:00Z")
            fixed_commit = self._git(repo, "rev-parse", "HEAD").strip()

            hidden_case = _hidden_case(
                fixed_by=[{"commit": fixed_commit}],
                comments_details=[{"body": "also mentions src/other.ts"}],
            )
            oracle = _build_evaluator_oracle(
                hidden_case=hidden_case,
                origin_repo_dir=repo,
                resolution=SnapshotResolution(
                    repo_pre_commit=fixed_commit,
                    strategy="fixed_by_parent",
                    confidence="test",
                    details={},
                ),
            )

            self.assertIn("src/parser.ts", oracle["files"])
            self.assertIn("src/other.ts", oracle["files"])
            self.assertTrue(oracle["source"]["fixed_by_changed_files"])

    def test_evaluate_case_writes_comparison_artifacts_from_workspace_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "testing.codeRepoQA.run_case.WorkspaceRetrievalStage",
            _RecordingWorkspaceRetrievalStage,
        ), patch("core.control_layer.classify_intent", return_value=_intent_result()), patch(
            "core.control_layer._render_response",
            return_value=ResponsePayload(TurnType.GUIDED_EXPLANATION, "test explanation"),
        ):
            root = Path(temp_dir)
            source_repo = root / "source-repo"
            issue_json = root / "issue.json"
            test_root = root / "test-runs"
            source_repo.mkdir()
            self._git(source_repo, "init")
            self._git(source_repo, "config", "user.name", "Test User")
            self._git(source_repo, "config", "user.email", "test@example.com")
            (source_repo / "src").mkdir()
            (source_repo / "src" / "parser.ts").write_text("const parser = 1;\n", encoding="utf-8")
            self._git(source_repo, "add", ".")
            self._git_commit(source_repo, "pre issue", "2014-07-10T12:00:00Z")
            (source_repo / "src" / "parser.ts").write_text("const parser = 2;\n", encoding="utf-8")
            self._git(source_repo, "add", ".")
            self._git_commit(source_repo, "fix", "2014-07-20T12:00:00Z")
            fixed_commit = self._git(source_repo, "rev-parse", "HEAD").strip()

            issue_json.write_text(
                json.dumps(
                    {
                        "repository_url": "https://api.github.com/repos/example/repo",
                        "number": 6,
                        "title": "Suggestion: abstract classes",
                        "created_at": "2014-07-15T16:45:03Z",
                        "body": "Support an `abstract` keyword for classes and their methods",
                        "fixed_by": [{"commit": fixed_commit}],
                        "comments_details": [{"body": "parser discussion: src/parser.ts"}],
                    }
                ),
                encoding="utf-8",
            )

            run_dir = evaluate_case(issue_json=issue_json, test_root=test_root, clone_url=str(source_repo), llm_config=_llm_config())
            metadata = json.loads((run_dir / "run-metadata.json").read_text(encoding="utf-8"))
            comparison = json.loads((run_dir / "evaluator-comparison.json").read_text(encoding="utf-8"))
            scorecard = json.loads((run_dir / "scorecard.json").read_text(encoding="utf-8"))

            expected_index_dir = Path(metadata["repo_pre_path"]) / ".guided-intelligence" / "index"
            self.assertEqual(Path(metadata["index_dir"]), expected_index_dir)
            self.assertTrue((expected_index_dir / "bm25-index.json").exists())
            self.assertIn("src/parser.ts", comparison["retrieved_source_files"])
            self.assertIn("src/parser.ts", comparison["oracle_files"])
            self.assertIn("src/parser.ts", comparison["overlap_files"])
            self.assertEqual(scorecard["overlap_count"], 1)
            self.assertTrue((run_dir / "evaluator-comparison.md").exists())

    def test_resolve_repo_pre_snapshot_uses_fixed_by_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = root / "repo"
            repo.mkdir()
            self._git(repo, "init")
            self._git(repo, "config", "user.name", "Test User")
            self._git(repo, "config", "user.email", "test@example.com")
            (repo / "src").mkdir()
            (repo / "src" / "parser.ts").write_text("const parser = 1;\n", encoding="utf-8")
            self._git(repo, "add", ".")
            self._git_commit(repo, "pre issue", "2014-07-10T12:00:00Z")
            repo_pre_commit = self._git(repo, "rev-parse", "HEAD").strip()
            (repo / "src" / "parser.ts").write_text("const parser = 2;\n", encoding="utf-8")
            self._git(repo, "add", ".")
            self._git_commit(repo, "fix", "2014-07-20T12:00:00Z")
            fixed_commit = self._git(repo, "rev-parse", "HEAD").strip()
            issue_json = root / "issue.json"
            issue_json.write_text(
                json.dumps(
                    {
                        "repository_url": "https://api.github.com/repos/example/repo",
                        "number": 6,
                        "title": "Suggestion: abstract classes",
                        "created_at": "2014-07-15T16:45:03Z",
                        "body": "Support an `abstract` keyword for classes and their methods",
                        "fixed_by": [{"commit": fixed_commit}],
                    }
                ),
                encoding="utf-8",
            )

            resolution = resolve_repo_pre_snapshot(issue_json, repo)

            self.assertEqual(resolution.repo_pre_commit, repo_pre_commit)
            self.assertEqual(resolution.strategy, "fixed_by_parent")

    def test_resolve_repo_pre_snapshot_falls_back_to_earliest_commit_when_issue_predates_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = root / "repo"
            repo.mkdir()
            self._git(repo, "init")
            self._git(repo, "config", "user.name", "Test User")
            self._git(repo, "config", "user.email", "test@example.com")
            (repo / "src").mkdir()
            (repo / "src" / "parser.ts").write_text("const parser = 1;\n", encoding="utf-8")
            self._git(repo, "add", ".")
            self._git_commit(repo, "initial", "2014-07-10T12:00:00Z")
            earliest_commit = self._git(repo, "rev-parse", "HEAD").strip()
            issue_json = root / "issue.json"
            issue_json.write_text(
                json.dumps(
                    {
                        "repository_url": "https://api.github.com/repos/example/repo",
                        "number": 242,
                        "title": "Directive method calls don't support object params",
                        "created_at": "2014-04-16T14:47:51Z",
                        "body": "Parser issue.",
                    }
                ),
                encoding="utf-8",
            )

            resolution = resolve_repo_pre_snapshot(issue_json, repo)

            self.assertEqual(resolution.repo_pre_commit, earliest_commit)
            self.assertEqual(resolution.strategy, "earliest_available_commit")

    def _git(self, cwd: Path, *args: str) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
        return completed.stdout

    def _git_commit(self, cwd: Path, message: str, timestamp: str) -> None:
        completed = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=str(cwd),
            text=True,
            capture_output=True,
            check=False,
            env={
                **os.environ,
                "GIT_AUTHOR_DATE": timestamp,
                "GIT_COMMITTER_DATE": timestamp,
            },
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())


class _RecordingWorkspaceRetrievalStage:
    instances: list["_RecordingWorkspaceRetrievalStage"] = []
    captured_states = []

    def __init__(self, config) -> None:
        self.config = config
        type(self).instances.append(self)

    def retrieve(self, state, policy_result):
        type(self).captured_states.append(state)
        return RetrievalResult(
            evidence=(
                EvidenceItem(
                    source_category=SourceCategory.SOURCE_CODE,
                    source_id="repo-pre:src/parser.ts:L1-L3",
                    snippet="function parseClassDeclaration() {}",
                    rank=1,
                    metadata={"path": "src/parser.ts", "retrieval_path": "bm25_search", "file_role": "implementation"},
                ),
            ),
            coverage_status="strong",
            sufficient=True,
            retrieval_summary={
                "retrieval_plan": {
                    "conversation_id": state.conversation_id,
                    "raw_prompt": state.user_input,
                    "raw_prompt_evidence": ["parseClassDeclaration"],
                    "prompt_summary": "Explain parseClassDeclaration implementation context.",
                    "retrieval_terms": ["parseClassDeclaration parser"],
                    "grounded_entities": ["parseClassDeclaration"],
                    "confirmed_entities": ["parseClassDeclaration"],
                    "grounded_file_hints": [],
                    "confirmed_file_hints": ["src/parser.ts"],
                    "llm_concept_terms": ["abstract class"],
                    "llm_subqueries": [{"role": "input_parsing", "query": "where is parseClassDeclaration parsed"}],
                    "speculative_entities": [],
                    "source_priorities": ["source_code"],
                    "negative_filters": ["harness"],
                    "required_roles": ["representation", "input_parsing"],
                    "supporting_roles": ["tests"],
                    "metadata": {"planner": "test"},
                }
            },
        )


def _hidden_case(*, fixed_by, comments_details):
    from services.retrieval.cases import HiddenCodeRepoQACase

    return HiddenCodeRepoQACase(
        case_id="example-repo-6",
        hidden_fields={"fixed_by": fixed_by, "comments_details": comments_details},
    )


def _llm_config() -> RunLLMConfig:
    return RunLLMConfig(
        api_style="openai_chat_completions",
        endpoint_url="http://example.test/v1/chat/completions",
        model="test-model",
        api_key="test-key",
    )


def _intent_result() -> IntentStageResult:
    return IntentStageResult(
        status="success",
        classification=IntentClassification(
            intents=(TaskIntent.CHANGE,),
            turn_relation=TurnRelation.NEW_TASK,
            solution_pressure=SolutionPressure.GUIDANCE,
            specificity=Specificity.MEDIUM,
            target_state=TargetState.UNRESOLVED,
            explicit_targets=(),
            confidence=0.9,
            classification_basis=("test",),
        ),
        error=None,
        fallback_used=False,
        latency_ms=1,
        classifier_model="test",
    )


if __name__ == "__main__":
    unittest.main()

