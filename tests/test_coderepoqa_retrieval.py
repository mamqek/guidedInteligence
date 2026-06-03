from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.models import EvidenceItem, RetrievalResult
from core.source_policy import SourceCategory
from services.retrieval.config import RunLLMConfig
from services.retrieval.bm25 import load_index
from testing.codeRepoQA.run_case import (
    evaluate_case,
    prepare_index,
    resolve_repo_pre_snapshot,
    run_case,
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
            index = load_index(index_dir)

            self.assertEqual([document.chunk.line_start for document in index.documents], [1, 6, 11])

    def test_run_case_uses_workspace_retrieval_and_visible_prompt_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "testing.codeRepoQA.run_case.WorkspaceRetrievalStage",
            _RecordingWorkspaceRetrievalStage,
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
            )

            self.assertTrue(result.evidence)
            self.assertEqual(len(_RecordingWorkspaceRetrievalStage.instances), 1)
            config = _RecordingWorkspaceRetrievalStage.instances[0].config
            self.assertEqual(config.enabled_source_categories, (SourceCategory.SOURCE_CODE,))
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
            oracle = _build_evaluator_oracle(hidden_case=hidden_case, origin_repo_dir=repo)

            self.assertIn("src/parser.ts", oracle["files"])
            self.assertIn("src/other.ts", oracle["files"])
            self.assertTrue(oracle["source"]["fixed_by_changed_files"])

    def test_evaluate_case_writes_comparison_artifacts_from_workspace_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "testing.codeRepoQA.run_case.WorkspaceRetrievalStage",
            _RecordingWorkspaceRetrievalStage,
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
            comparison = json.loads((run_dir / "evaluator-comparison.json").read_text(encoding="utf-8"))
            scorecard = json.loads((run_dir / "scorecard.json").read_text(encoding="utf-8"))

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


if __name__ == "__main__":
    unittest.main()
