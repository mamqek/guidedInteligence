from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
import threading
import unittest
import urllib.error
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import StringIO
from pathlib import Path
import sys
from unittest.mock import patch

from core.models import ConversationState, EvidenceItem, UserIntent
from core.policy import PolicyStage
from core.source_policy import SourceCategory, SourcePolicy
from core.stages import ResponseStage
from services.retrieval import workspace_llm
from services.retrieval.config import RunLLMConfig, WorkspaceRetrievalConfig, load_retrieval_llm_config
from services.retrieval.step2 import RoleDirectedSubquery, WorkspaceRetrievalPlan
from services.retrieval.role_validation import supported_roles
from services.retrieval.tools import cgc_tool_specs, local_tool_specs
from services.retrieval.tools.cgc import CGCAnalyzeDepsTool, CGCFindCodeTool, CGCQueryGraphTool, CGCRunCliTool
from services.retrieval.tools.contracts import ToolRequest
from services.retrieval.workspace import (
    RetrievalCandidate,
    RoleCandidateEvaluation,
    RoleRetrievalBucket,
    RoleValidationResult,
    WorkspaceRetrievalStage,
    _role_retarget_queries,
    _select_diverse_completion_entries,
)


class WorkspaceRetrievalStageTests(unittest.TestCase):
    def setUp(self) -> None:
        workspace_llm._TEMPERATURE_DISABLED_MODELS.clear()

    def test_existing_state_evidence_returns_without_reindexing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, _fake_llm_server([]) as server_url:
            root = Path(temp_dir)
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(root),
                    index_dir=str(root / "index"),
                    llm_config=_llm_config(server_url),
                )
            )
            state = ConversationState(
                conversation_id="conv",
                user_input="Explain the parser.",
                current_stage=ResponseStage.EXPLAIN,
                intent=UserIntent.UNDERSTAND_CODE,
                evidence=(
                    EvidenceItem(
                        source_category=SourceCategory.SOURCE_CODE,
                        source_id="src/parser.ts:L1-L4",
                        snippet="function parseClassDeclaration() {}",
                    ),
                ),
            )

            result = stage.retrieve(state, _policy_result(state))

            self.assertTrue(result.sufficient)
            self.assertEqual(result.coverage_status, "sufficient_context")
            self.assertFalse(result.retrieval_summary["index_rebuilt"])
            self.assertFalse((root / "index" / "bm25-index.json").exists())

    def test_workspace_retrieval_config_requires_llm(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = root / "repo"
            repo.mkdir()
            with self.assertRaises(TypeError):
                WorkspaceRetrievalStage(WorkspaceRetrievalConfig(workspace_root=str(repo), index_dir=str(root / "index")))

    def test_required_role_buckets_filter_test_noise_and_keep_impl_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, _fake_llm_server(
            [
                _step2_response(
                    subqueries=[
                        ("input_parsing", "where is the abstract keyword parsed"),
                        ("validation_checking", "where are abstract class rules enforced"),
                        ("diagnostics", "where are abstract usage errors reported"),
                    ]
                ),
                _late_synthesis_response(
                    accepted_anchor_refs=[
                        "workspace:src/compiler/parser.ts:L1-L1",
                        "workspace:src/compiler/checker.ts:L1-L1",
                        "workspace:src/compiler/diagnosticMessages.json:L1-L1",
                    ],
                    missing_areas=["behavior_output", "representation"],
                ),
            ]
        ) as server_url:
            root = Path(temp_dir)
            repo = root / "repo"
            (repo / "src" / "compiler").mkdir(parents=True)
            (repo / "tests" / "cases").mkdir(parents=True)
            (repo / "src" / "compiler" / "parser.ts").write_text(
                "function parseClassDeclaration() { return 'abstract modifier'; }\n",
                encoding="utf-8",
            )
            (repo / "src" / "compiler" / "checker.ts").write_text(
                "function checkAbstractClass() { return 'cannot instantiate abstract class'; }\n",
                encoding="utf-8",
            )
            (repo / "src" / "compiler" / "diagnosticMessages.json").write_text(
                '{"Cannot instantiate abstract class": {"category": "Error"}}\n',
                encoding="utf-8",
            )
            (repo / "tests" / "cases" / "abstractTests.ts").write_text(
                "describe('abstract', () => {});\n",
                encoding="utf-8",
            )
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(repo),
                    index_dir=str(root / "index"),
                    run_dir=str(root / "run"),
                    llm_config=_llm_config(server_url),
                )
            )
            state = ConversationState(
                conversation_id="conv",
                user_input="Explain support for abstract classes and where parsing, validation, and diagnostics live.",
                current_stage=ResponseStage.EXPLAIN,
                intent=UserIntent.UNDERSTAND_CODE,
            )

            with _fake_cgc(files=[{"path": "src/compiler/parser.ts"}, {"path": "src/compiler/checker.ts"}, {"path": "src/compiler/diagnosticMessages.json"}, {"path": "tests/cases/abstractTests.ts"}]):
                result = stage.retrieve(state, _policy_result(state, allowed_sources=(SourceCategory.SOURCE_CODE,)))

            evidence_paths = [item.metadata.get("path", "") for item in result.evidence]
            self.assertIn("src/compiler/parser.ts", evidence_paths)
            self.assertIn("src/compiler/checker.ts", evidence_paths)
            self.assertIn("src/compiler/diagnosticMessages.json", evidence_paths)
            self.assertNotIn("tests/cases/abstractTests.ts", evidence_paths)
            required_buckets = result.retrieval_summary["required_role_buckets"]
            self.assertEqual([bucket["role"] for bucket in required_buckets], ["input_parsing", "validation_checking", "diagnostics"])

    def test_diagnostics_file_is_rejected_for_non_diagnostics_role(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, _fake_llm_server(
            [
                _step2_response(subqueries=[("input_parsing", "where is the abstract keyword parsed")]),
                _late_synthesis_response(missing_areas=["input_parsing"]),
                _late_synthesis_response(missing_areas=["input_parsing"]),
            ]
        ) as server_url:
            root = Path(temp_dir)
            repo = root / "repo"
            (repo / "src" / "compiler").mkdir(parents=True)
            (repo / "src" / "compiler" / "diagnosticMessages.json").write_text(
                '{"abstract keyword error": {"category": "Error"}}\n',
                encoding="utf-8",
            )
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(repo),
                    index_dir=str(root / "index"),
                    run_dir=str(root / "run"),
                    llm_config=_llm_config(server_url),
                )
            )
            state = ConversationState(
                conversation_id="conv",
                user_input="Explain where abstract parsing happens.",
                current_stage=ResponseStage.EXPLAIN,
                intent=UserIntent.UNDERSTAND_CODE,
            )

            with _fake_cgc(files=[{"path": "src/compiler/diagnosticMessages.json"}]):
                result = stage.retrieve(state, _policy_result(state, allowed_sources=(SourceCategory.SOURCE_CODE,)))

            self.assertFalse(result.sufficient)
            self.assertEqual(result.coverage_status, "missing")
            required_bucket = result.retrieval_summary["required_role_buckets"][0]
            self.assertEqual(required_bucket["role"], "input_parsing")
            self.assertEqual(required_bucket["accepted_refs"], [])

    def test_evidence_selection_prefers_distinct_roles_before_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, _fake_llm_server(
            [
                _step2_response(
                    subqueries=[
                        ("input_parsing", "where is the abstract keyword parsed"),
                        ("validation_checking", "where are abstract class rules enforced"),
                    ]
                ),
                _late_synthesis_response(
                    accepted_anchor_refs=[
                        "workspace:src/compiler/parser.ts:L1-L1",
                        "workspace:src/compiler/checker.ts:L1-L1",
                    ]
                ),
            ]
        ) as server_url:
            root = Path(temp_dir)
            repo = root / "repo"
            (repo / "src" / "compiler").mkdir(parents=True)
            (repo / "src" / "compiler" / "parser.ts").write_text(
                "function parseClassDeclaration() { return 'abstract modifier'; }\n",
                encoding="utf-8",
            )
            (repo / "src" / "compiler" / "parserHelpers.ts").write_text(
                "function parseModifierFlags() { return 'abstract'; }\n",
                encoding="utf-8",
            )
            (repo / "src" / "compiler" / "checker.ts").write_text(
                "function checkAbstractClass() { return 'cannot instantiate abstract class'; }\n",
                encoding="utf-8",
            )
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(repo),
                    index_dir=str(root / "index"),
                    run_dir=str(root / "run"),
                    llm_config=_llm_config(server_url),
                )
            )
            state = ConversationState(
                conversation_id="conv",
                user_input="Explain where abstract parsing and validation are implemented.",
                current_stage=ResponseStage.EXPLAIN,
                intent=UserIntent.UNDERSTAND_CODE,
            )

            with _fake_cgc(files=[{"path": "src/compiler/parser.ts"}, {"path": "src/compiler/parserHelpers.ts"}, {"path": "src/compiler/checker.ts"}]):
                result = stage.retrieve(state, _policy_result(state, allowed_sources=(SourceCategory.SOURCE_CODE,)))

            self.assertGreaterEqual(len(result.evidence), 2)
            self.assertEqual(result.evidence[0].metadata.get("coverage_area"), "input_parsing")
            self.assertEqual(result.evidence[1].metadata.get("coverage_area"), "validation_checking")

    def test_anchor_relative_support_promotes_representation_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, _fake_llm_server(
            [
                _step2_response(
                    subqueries=[
                        ("input_parsing", "where is the abstract keyword parsed"),
                        ("representation", "how are abstract classes and methods represented"),
                    ]
                ),
                _late_synthesis_response(
                    accepted_anchor_refs=[
                        "workspace:src/compiler/parser.ts:L1-L1",
                        "workspace:src/compiler/types.ts:L1-L1",
                    ]
                ),
            ]
        ) as server_url:
            root = Path(temp_dir)
            repo = root / "repo"
            (repo / "src" / "compiler").mkdir(parents=True)
            (repo / "src" / "compiler" / "parser.ts").write_text(
                "function parseClassDeclaration() { return SyntaxKind.AbstractKeyword; }\n",
                encoding="utf-8",
            )
            (repo / "src" / "compiler" / "types.ts").write_text(
                "interface ClassDeclaration { flags: NodeFlags; }\nenum NodeFlags { Abstract = 1 }\n",
                encoding="utf-8",
            )
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(repo),
                    index_dir=str(root / "index"),
                    run_dir=str(root / "run"),
                    llm_config=_llm_config(server_url),
                )
            )
            state = ConversationState(
                conversation_id="conv",
                user_input="Explain where abstract classes are parsed and how they are represented.",
                current_stage=ResponseStage.EXPLAIN,
                intent=UserIntent.UNDERSTAND_CODE,
            )

            with _fake_cgc(
                files_by_command={
                    ("find",): [{"path": "src/compiler/parser.ts"}, {"path": "src/compiler/types.ts"}],
                    ("analyze", "callers"): [{"path": "src/compiler/checker.ts"}],
                    ("analyze", "calls"): [{"path": "src/compiler/types.ts"}],
                },
                query_rows_by_contains={
                    "fc.relative_path = 'src\\\\compiler\\\\types.ts'": [
                        {"shared_symbol": "ClassDeclaration", "anchor_function": "parseClassDeclaration", "anchor_line": 2542}
                    ]
                },
            ):
                result = stage.retrieve(state, _policy_result(state, allowed_sources=(SourceCategory.SOURCE_CODE,)))

            representation_bucket = next(bucket for bucket in result.retrieval_summary["required_role_buckets"] if bucket["role"] == "representation")
            self.assertIn("src/compiler/types.ts", [snippet["path"] for snippet in representation_bucket["snippets"]])
            eval_entry = next(item for item in representation_bucket["evaluations"] if item["path"] == "src/compiler/types.ts")
            self.assertEqual(eval_entry["validation"]["acceptance_source"], "dependency_supported")

    def test_anchor_relative_support_recovers_validation_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, _fake_llm_server(
            [
                _step2_response(
                    subqueries=[
                        ("input_parsing", "where is the abstract keyword parsed"),
                        ("validation_checking", "where are abstract class constraints enforced"),
                    ]
                ),
                _late_synthesis_response(
                    accepted_anchor_refs=[
                        "workspace:src/compiler/parser.ts:L1-L1",
                        "workspace:src/compiler/checker.ts:L1-L1",
                    ]
                ),
            ]
        ) as server_url:
            root = Path(temp_dir)
            repo = root / "repo"
            (repo / "src" / "compiler").mkdir(parents=True)
            (repo / "src" / "compiler" / "parser.ts").write_text(
                "function parseClassDeclaration() { return SyntaxKind.AbstractKeyword; }\n",
                encoding="utf-8",
            )
            (repo / "src" / "compiler" / "checker.ts").write_text(
                "function checkAbstractClass() { return 'cannot instantiate abstract class'; }\n",
                encoding="utf-8",
            )
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(repo),
                    index_dir=str(root / "index"),
                    run_dir=str(root / "run"),
                    llm_config=_llm_config(server_url),
                )
            )
            state = ConversationState(
                conversation_id="conv",
                user_input="Explain parsing and validation for abstract classes.",
                current_stage=ResponseStage.EXPLAIN,
                intent=UserIntent.UNDERSTAND_CODE,
            )

            with _fake_cgc(
                files_by_command={
                    ("find",): [{"path": "src/compiler/parser.ts"}, {"path": "src/compiler/checker.ts"}],
                    ("analyze", "callers"): [{"path": "src/compiler/checker.ts"}],
                    ("analyze", "calls"): [{"path": "src/compiler/checker.ts"}],
                }
            ):
                result = stage.retrieve(state, _policy_result(state, allowed_sources=(SourceCategory.SOURCE_CODE,)))

            validation_bucket = next(bucket for bucket in result.retrieval_summary["required_role_buckets"] if bucket["role"] == "validation_checking")
            self.assertIn("src/compiler/checker.ts", [snippet["path"] for snippet in validation_bucket["snippets"]])

    def test_late_llm_payload_is_role_grouped(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, _fake_llm_server(
            [
                _step2_response(subqueries=[("input_parsing", "where is the abstract keyword parsed")]),
                _late_synthesis_response(accepted_anchor_refs=["workspace:src/compiler/parser.ts:L1-L1"]),
            ]
        ) as server_url:
            root = Path(temp_dir)
            repo = root / "repo"
            (repo / "src" / "compiler").mkdir(parents=True)
            (repo / "src" / "compiler" / "parser.ts").write_text(
                "function parseClassDeclaration() { return 'abstract modifier'; }\n",
                encoding="utf-8",
            )
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(repo),
                    index_dir=str(root / "index"),
                    run_dir=str(root / "run"),
                    llm_config=_llm_config(server_url),
                )
            )
            state = ConversationState(
                conversation_id="conv",
                user_input="Explain where abstract parsing is implemented.",
                current_stage=ResponseStage.EXPLAIN,
                intent=UserIntent.UNDERSTAND_CODE,
            )

            with _fake_cgc(files=[{"path": "src/compiler/parser.ts"}]):
                stage.retrieve(state, _policy_result(state, allowed_sources=(SourceCategory.SOURCE_CODE,)))

            trace = (root / "run" / "retrieval-trace.jsonl").read_text(encoding="utf-8")
            self.assertIn("role_buckets", trace)
            self.assertIn("missing_roles", trace)
            self.assertNotIn('"available_tools"', trace)

    def test_role_completion_promotes_checker_over_tc_for_validation_role(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, _fake_llm_server([_step2_response()]) as server_url:
            root = Path(temp_dir)
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(root),
                    index_dir=str(root / "index"),
                    llm_config=_llm_config(server_url),
                )
            )
            plan = _test_retrieval_plan(required_roles=("representation", "input_parsing", "validation_checking"))
            representation_bucket = _test_bucket(
                role="representation",
                accepted=[_test_candidate("src/compiler/types.ts", "flags SymbolFlags ClassDeclaration", "representation", "repo:types")],
            )
            input_bucket = _test_bucket(
                role="input_parsing",
                accepted=[_test_candidate("src/compiler/parser.ts", "function parseClassDeclaration() { return SyntaxKind.AbstractKeyword; }", "input_parsing", "repo:parser")],
            )
            validation_bucket = _test_bucket(
                role="validation_checking",
                accepted=[
                    _test_candidate("src/compiler/binder.ts", "function declareModuleMember() { if (node.flags & NodeFlags.Export) {} }", "validation_checking", "repo:binder"),
                    _test_candidate("src/compiler/tc.ts", "///<reference path=\"checker.ts\"/>", "validation_checking", "repo:tc"),
                ],
                rejected=[
                    (
                        _test_candidate("src/compiler/checker.ts", "function checkAbstractClass() { return 'cannot instantiate abstract class'; }", "validation_checking", "repo:checker"),
                        _test_validation(accepted=False, reason="insufficient_role_support", total_score=2.7),
                    )
                ],
            )

            completed = stage._complete_role_buckets(
                retrieval_plan=plan,
                buckets=(representation_bucket, input_bucket, validation_bucket),
            )

            validation_completed = next(bucket for bucket in completed if bucket.role == "validation_checking")
            accepted_paths = [candidate.path for candidate in validation_completed.accepted_candidates]
            self.assertIn("src/compiler/checker.ts", accepted_paths)
            self.assertNotIn("src/compiler/tc.ts", accepted_paths)

    def test_role_completion_preserves_rejection_history_when_recovered(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, _fake_llm_server([_step2_response()]) as server_url:
            root = Path(temp_dir)
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(root),
                    index_dir=str(root / "index"),
                    llm_config=_llm_config(server_url),
                )
            )
            plan = _test_retrieval_plan(required_roles=("representation", "input_parsing", "validation_checking"))
            completed = stage._complete_role_buckets(
                retrieval_plan=plan,
                buckets=(
                    _test_bucket(role="representation", accepted=[_test_candidate("src/compiler/types.ts", "flags SymbolFlags ClassDeclaration", "representation", "repo:types")]),
                    _test_bucket(role="input_parsing", accepted=[_test_candidate("src/compiler/parser.ts", "function parseClassDeclaration() { return SyntaxKind.AbstractKeyword; }", "input_parsing", "repo:parser")]),
                    _test_bucket(
                        role="validation_checking",
                        accepted=[_test_candidate("src/compiler/binder.ts", "function bind() { return true; }", "validation_checking", "repo:binder")],
                        rejected=[
                            (
                                _test_candidate("src/compiler/checker.ts", "function checkAbstractClass() { return 'cannot instantiate abstract class'; }", "validation_checking", "repo:checker"),
                                _test_validation(accepted=False, reason="insufficient_role_support", total_score=2.7),
                            )
                        ],
                    ),
                ),
            )

            validation_completed = next(bucket for bucket in completed if bucket.role == "validation_checking")
            checker_evals = [evaluation for evaluation in validation_completed.evaluations if evaluation.candidate.path == "src/compiler/checker.ts"]
            self.assertGreaterEqual(len(checker_evals), 2)
            self.assertTrue(any(evaluation.stage == "initial" and not evaluation.validation.accepted for evaluation in checker_evals))
            self.assertTrue(any(evaluation.stage == "role_completion" and evaluation.validation.accepted for evaluation in checker_evals))
            self.assertNotIn("repo:checker", validation_completed.rejected_refs)

    def test_diverse_completion_selection_avoids_same_directory_duplication_when_scores_are_close(self) -> None:
        checker = _test_candidate("src/compiler/checker.ts", "check abstract class diagnostics", "validation_checking", "repo:checker")
        binder = _test_candidate("src/compiler/binder.ts", "bind abstract declarations", "validation_checking", "repo:binder")
        docs = _test_candidate("docs/abstract.md", "abstract docs", "validation_checking", "repo:docs")
        entries = (
            (checker, "validation_checking", "rejected", _test_validation(accepted=True, reason="ok", total_score=5.2), 5.2),
            (binder, "validation_checking", "accepted_other_role", _test_validation(accepted=True, reason="ok", total_score=4.95), 4.95),
            (docs, "docs", "accepted_other_role", _test_validation(accepted=True, reason="ok", total_score=4.7), 4.7),
        )

        selected = _select_diverse_completion_entries(entries, limit=2)

        selected_paths = [entry[0].path for entry in selected]
        self.assertIn("src/compiler/checker.ts", selected_paths)
        self.assertNotEqual(selected_paths, ["src/compiler/checker.ts", "src/compiler/binder.ts"])

    def test_role_retarget_queries_add_role_specific_entrypoint_terms(self) -> None:
        queries = _role_retarget_queries(
            "input_parsing",
            query="How does parsing handle abstract classes?",
            helper_queries=("How does parsing handle abstract classes?", "abstract keyword parser"),
            candidate_path="src/compiler/parser.ts",
            candidate_text="function parseClassDeclaration() { return parseClassMemberDeclaration(); }",
        )

        self.assertIn("parseclassdeclaration parseclassmemberdeclaration parseandcheckmodifiers", queries)
        self.assertIn("parser How does parsing handle abstract classes?", queries)

    def test_hard_fail_when_cgc_binary_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, _fake_llm_server([_step2_response()]) as server_url:
            root = Path(temp_dir)
            repo = root / "repo"
            repo.mkdir()
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(workspace_root=str(repo), index_dir=str(root / "index"), llm_config=_llm_config(server_url))
            )
            state = ConversationState(
                conversation_id="conv",
                user_input="Explain parseClassDeclaration.",
                current_stage=ResponseStage.EXPLAIN,
                intent=UserIntent.UNDERSTAND_CODE,
            )

            with patch("services.retrieval.tools.cgc.subprocess.run", side_effect=FileNotFoundError("missing cgc")):
                result = stage.retrieve(state, _policy_result(state))

            self.assertFalse(result.sufficient)
            self.assertEqual(result.coverage_status, "failed")
            self.assertEqual(result.failures_or_fallbacks, ("cgc_index_failed",))

    def test_temperature_rejection_is_logged_and_disabled_for_rest_of_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = root / "repo"
            (repo / "src").mkdir(parents=True)
            (repo / "src" / "parser.ts").write_text("function parseClassDeclaration() { return 'parser'; }\n", encoding="utf-8")
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(repo),
                    index_dir=str(root / "index"),
                    run_dir=str(root / "run"),
                    llm_config=_llm_config("http://unused/v1/chat/completions"),
                )
            )
            state = ConversationState(
                conversation_id="conv",
                user_input="Explain parseClassDeclaration call flow.",
                current_stage=ResponseStage.EXPLAIN,
                intent=UserIntent.UNDERSTAND_CODE,
            )
            seen_payloads: list[dict[str, object]] = []
            responses = [
                _step2_response(),
                _late_synthesis_response(accepted_anchor_refs=["workspace:src/parser.ts:L1-L1"]),
            ]

            def fake_urlopen(request, timeout=0):
                payload = json.loads(request.data.decode("utf-8"))
                seen_payloads.append(payload)
                if len(seen_payloads) == 1:
                    body = json.dumps(
                        {
                            "error": {
                                "message": "Unsupported value: 'temperature' does not support 0.0 with this model. Only the default (1) value is supported.",
                                "type": "invalid_request_error",
                                "param": "temperature",
                                "code": "unsupported_value",
                            }
                        }
                    ).encode("utf-8")
                    raise urllib.error.HTTPError(request.full_url, 400, "Bad Request", hdrs=None, fp=_BytesReader(body))
                return _FakeHTTPResponse({"choices": [{"message": {"content": json.dumps(responses.pop(0))}}]})

            with _fake_cgc(files=[{"path": "src/parser.ts"}]), patch(
                "services.retrieval.workspace_llm.urllib.request.urlopen",
                side_effect=fake_urlopen,
            ):
                result = stage.retrieve(state, _policy_result(state))

            self.assertEqual(len(seen_payloads), 3)
            self.assertIn("temperature", seen_payloads[0])
            self.assertNotIn("temperature", seen_payloads[1])
            self.assertNotIn("temperature", seen_payloads[2])
            trace = (root / "run" / "retrieval-trace.jsonl").read_text(encoding="utf-8")
            self.assertIn('"event_type": "llm_request_sent"', trace)
            self.assertIn('"event_type": "llm_request_failed"', trace)
            self.assertIn('"event_type": "llm_response_received"', trace)
            self.assertIn('"event_type": "llm_request_warning"', trace)
            self.assertTrue(result.sufficient)


class CGCToolTests(unittest.TestCase):
    def test_role_registry_exposes_expected_roles(self) -> None:
        self.assertEqual(
            supported_roles(),
            ("behavior_output", "diagnostics", "input_parsing", "representation", "validation_checking"),
        )

    def test_cgc_command_prefix_override_is_used(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = WorkspaceRetrievalConfig(
                workspace_root=str(root),
                index_dir=str(root / "index"),
                llm_config=_llm_config("http://unused/v1/chat/completions"),
                cgc_command=("uvx", "codegraphcontext"),
            )
            tool = CGCFindCodeTool(config)
            calls: list[list[str]] = []

            def fake_run(command, **kwargs):
                calls.append(command)
                return _completed(stdout=_cgc_table([("parseClassDeclaration", "Function", str(root / "src" / "parser.ts:10"))]))

            with patch("services.retrieval.tools.cgc.subprocess.run", side_effect=fake_run):
                observation = tool.run(ToolRequest(tool_name="cgc_find_code", arguments={"query": "parser"}))

            self.assertEqual(calls[0][:2], ["uvx", "codegraphcontext"])
            self.assertEqual(observation.status, "ok")

    def test_cgc_run_cli_rejects_non_whitelisted_subcommands(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tool = CGCRunCliTool(
                WorkspaceRetrievalConfig(
                    workspace_root=str(root),
                    index_dir=str(root / "index"),
                    llm_config=_llm_config("http://unused/v1/chat/completions"),
                )
            )

            observation = tool.run(
                ToolRequest(
                    tool_name="cgc_run_cli",
                    arguments={"subcommand": ["delete"], "args": ["--all"]},
                )
            )

            self.assertEqual(observation.status, "rejected")
            self.assertEqual(observation.payload["reason"], "unsupported_subcommand")

    def test_cgc_timeout_returns_failed_observation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tool = CGCFindCodeTool(
                WorkspaceRetrievalConfig(
                    workspace_root=str(root),
                    index_dir=str(root / "index"),
                    llm_config=_llm_config("http://unused/v1/chat/completions"),
                )
            )

            with patch(
                "services.retrieval.tools.cgc.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd=["cgc"], timeout=10),
            ):
                observation = tool.run(ToolRequest(tool_name="cgc_find_code", arguments={"query": "parser"}))

            self.assertEqual(observation.status, "failed")

    def test_cgc_analyze_deps_tries_multiple_module_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tool = CGCAnalyzeDepsTool(
                WorkspaceRetrievalConfig(
                    workspace_root=str(root),
                    index_dir=str(root / "index"),
                    llm_config=_llm_config("http://unused/v1/chat/completions"),
                )
            )
            commands: list[list[str]] = []

            def fake_run(command, **kwargs):
                commands.append(command)
                if command[-1] == "src.compiler.parser":
                    return _completed(stdout=_cgc_table([("types", "Module", str(root / "src" / "compiler" / "types.ts"))]))
                return _completed(stdout="")

            with patch("services.retrieval.tools.cgc.subprocess.run", side_effect=fake_run):
                observation = tool.run(ToolRequest(tool_name="cgc_analyze_deps", arguments={"path": "src/compiler/parser.ts"}))

            self.assertEqual(observation.status, "ok")
            self.assertEqual(observation.payload["used_module"], "src.compiler.parser")
            self.assertGreater(len(commands), 1)

    def test_cgc_query_graph_parses_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tool = CGCQueryGraphTool(
                WorkspaceRetrievalConfig(
                    workspace_root=str(root),
                    index_dir=str(root / "index"),
                    llm_config=_llm_config("http://unused/v1/chat/completions"),
                )
            )

            def fake_run(command, **kwargs):
                return _completed(stdout='[{"shared_symbol":"ClassDeclaration","anchor_function":"parseClassDeclaration"}]')

            with patch("services.retrieval.tools.cgc.subprocess.run", side_effect=fake_run):
                observation = tool.run(ToolRequest(tool_name="cgc_query_graph", arguments={"query": "MATCH (n) RETURN n LIMIT 1"}))

            self.assertEqual(observation.status, "ok")
            self.assertEqual(observation.payload["rows"][0]["shared_symbol"], "ClassDeclaration")

    def test_cgc_analyze_deps_returns_ok_when_mapping_has_no_hits(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tool = CGCAnalyzeDepsTool(
                WorkspaceRetrievalConfig(
                    workspace_root=str(root),
                    index_dir=str(root / "index"),
                    llm_config=_llm_config("http://unused/v1/chat/completions"),
                )
            )

            with patch("services.retrieval.tools.cgc.subprocess.run", side_effect=lambda command, **kwargs: _completed(stdout="")):
                observation = tool.run(ToolRequest(tool_name="cgc_analyze_deps", arguments={"path": "src/compiler/parser.ts"}))

            self.assertEqual(observation.status, "ok")
            self.assertEqual(observation.payload["files"], [])

    def test_tool_specs_include_cgc_guidance(self) -> None:
        cgc_names = {spec.name for spec in cgc_tool_specs()}
        local_names = {spec.name for spec in local_tool_specs()}

        self.assertIn("cgc_find_code", cgc_names)
        self.assertIn("cgc_analyze_deps", cgc_names)
        self.assertIn("cgc_run_cli", cgc_names)
        self.assertIn("bm25_search", local_names)
        find_code_spec = next(spec for spec in cgc_tool_specs() if spec.name == "cgc_find_code")
        self.assertIn("Use CodeGraphContext first", find_code_spec.description)
        raw_spec = next(spec for spec in cgc_tool_specs() if spec.name == "cgc_run_cli")
        self.assertIn("not arbitrary shell execution", raw_spec.description)


class RetrievalLLMConfigTests(unittest.TestCase):
    def test_load_retrieval_llm_config_reads_documented_env_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "# retrieval config",
                        "RETRIEVAL_LLM_API_STYLE=openai_chat_completions",
                        "RETRIEVAL_LLM_ENDPOINT_URL=http://example.test/v1/chat/completions # full endpoint",
                        "RETRIEVAL_LLM_MODEL=gpt-4.1-mini",
                        "RETRIEVAL_LLM_API_KEY=test-secret",
                        "RETRIEVAL_LLM_TEMPERATURE=0",
                        "RETRIEVAL_LLM_MAX_TOKENS=1200",
                        "RETRIEVAL_LLM_TIMEOUT_SECONDS=45",
                    ]
                ),
                encoding="utf-8",
            )

            config = load_retrieval_llm_config(env_path)

            self.assertEqual(config.api_style, "openai_chat_completions")
            self.assertEqual(config.endpoint_url, "http://example.test/v1/chat/completions")
            self.assertEqual(config.model, "gpt-4.1-mini")
            self.assertEqual(config.api_key, "test-secret")
            self.assertEqual(config.temperature, 0.0)
            self.assertEqual(config.max_tokens, 1200)
            self.assertEqual(config.timeout_seconds, 45)

    def test_load_retrieval_llm_config_rejects_missing_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("# empty retrieval config\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Retrieval LLM config is missing"):
                load_retrieval_llm_config(env_path)

    def test_load_retrieval_llm_config_rejects_partial_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("RETRIEVAL_LLM_MODEL=gpt-4.1-mini\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Retrieval LLM config is incomplete"):
                load_retrieval_llm_config(env_path)

    def test_workspace_config_validation_rejects_missing_required_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "endpoint_url"):
            WorkspaceRetrievalConfig(
                workspace_root="repo",
                index_dir="index",
                llm_config=RunLLMConfig(api_style="openai_chat_completions", model="gpt-4.1-mini", api_key="secret"),
            ).validate()

    def test_workspace_config_validation_rejects_unsupported_api_style(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported retrieval LLM api_style"):
            WorkspaceRetrievalConfig(
                workspace_root="repo",
                index_dir="index",
                llm_config=RunLLMConfig(
                    api_style="custom_provider",
                    endpoint_url="http://example.test/custom",
                    model="gpt-4.1-mini",
                    api_key="secret",
                ),
            ).validate()

    def test_public_dict_redacts_api_key(self) -> None:
        payload = RunLLMConfig(
            api_style="openai_chat_completions",
            endpoint_url="http://example.test/v1/chat/completions",
            model="gpt-4.1-mini",
            api_key="secret",
        ).public_dict()

        self.assertNotIn("api_key", payload)
        self.assertTrue(payload["api_key_configured"])

    def test_complete_json_uses_exact_endpoint_and_auth_header(self) -> None:
        seen: dict[str, object] = {}

        def fake_urlopen(request, timeout=0):
            seen["url"] = request.full_url
            seen["auth"] = request.get_header("Authorization")
            seen["timeout"] = timeout
            return _FakeHTTPResponse({"choices": [{"message": {"content": json.dumps({"ok": True})}}]})

        config = RunLLMConfig(
            api_style="openai_chat_completions",
            endpoint_url="http://example.test/custom/chat/completions",
            model="gpt-4.1-mini",
            api_key="secret-token",
            timeout_seconds=12,
        )

        with patch("services.retrieval.workspace_llm.urllib.request.urlopen", side_effect=fake_urlopen):
            response = workspace_llm.complete_json(config, [{"role": "user", "content": "hi"}])

        self.assertEqual(response, {"ok": True})
        self.assertEqual(seen["url"], "http://example.test/custom/chat/completions")
        self.assertEqual(seen["auth"], "Bearer secret-token")
        self.assertEqual(seen["timeout"], 12)

    def test_run_case_help_no_longer_exposes_llm_cli_flags(self) -> None:
        module = _load_run_case_module()
        buffer = StringIO()

        with self.assertRaises(SystemExit), redirect_stdout(buffer):
            module.main(["run-case", "--help"])

        help_text = buffer.getvalue()
        self.assertNotIn("--llm-base-url", help_text)
        self.assertNotIn("--llm-model", help_text)
        self.assertNotIn("--llm-api-key-env", help_text)


def _load_run_case_module():
    module_path = Path(__file__).resolve().parents[1] / "testing" / "codeRepoQA" / "run_case.py"
    spec = importlib.util.spec_from_file_location("testing_codeRepoQA_run_case", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _llm_config(server_url: str) -> RunLLMConfig:
    return RunLLMConfig(
        api_style="openai_chat_completions",
        model="test-model",
        endpoint_url=server_url,
        api_key="test-key",
    )


def _test_retrieval_plan(*, required_roles: tuple[str, ...]) -> WorkspaceRetrievalPlan:
    return WorkspaceRetrievalPlan(
        conversation_id="conv",
        raw_prompt="Explain abstract classes.",
        raw_prompt_evidence=("abstract",),
        prompt_summary="Support abstract classes.",
        retrieval_terms=("abstract class", "abstract method"),
        grounded_entities=("abstract",),
        confirmed_entities=(),
        grounded_file_hints=(),
        confirmed_file_hints=(),
        llm_concept_terms=("abstract classes",),
        llm_subqueries=tuple(RoleDirectedSubquery(role=role, query=f"query for {role}") for role in required_roles),
        speculative_entities=("checker.ts",),
        source_priorities=(SourceCategory.SOURCE_CODE,),
        negative_filters=("harness",),
        required_roles=required_roles,
        supporting_roles=(),
        metadata={"planner": "test"},
    )


def _test_candidate(path: str, text: str, coverage_area: str, source_id: str) -> RetrievalCandidate:
    return RetrievalCandidate(
        candidate_id=source_id,
        source_category=SourceCategory.SOURCE_CODE,
        retrieval_path="bm25_search",
        text=text,
        score=10.0,
        source_id=source_id,
        path=path,
        line_range="L1-L20",
        metadata={"path": path, "coverage_area": coverage_area, "file_role": "implementation"},
    )


def _test_validation(*, accepted: bool, reason: str, total_score: float, acceptance_source: str = "local_only") -> RoleValidationResult:
    return RoleValidationResult(
        accepted=accepted,
        reason=reason,
        local_intent_score=total_score,
        role_path_score=0.0,
        dependency_support_score=0.0,
        anchor_proximity_score=0.0,
        call_flow_score=0.0,
        total_score=total_score,
        threshold=3.0,
        acceptance_source=acceptance_source,
        symbol="symbol",
        dependency_paths=(),
        call_paths=(),
        anchor_paths=(),
    )


def _test_bucket(
    *,
    role: str,
    accepted: list[RetrievalCandidate],
    rejected: list[tuple[RetrievalCandidate, RoleValidationResult]] | None = None,
) -> RoleRetrievalBucket:
    rejected = rejected or []
    evaluations = [
        RoleCandidateEvaluation(
            candidate=candidate,
            validation=_test_validation(accepted=True, reason="validated_role_candidate", total_score=4.2, acceptance_source="anchor_boosted"),
            stage="initial",
            source_role=role,
        )
        for candidate in accepted
    ]
    evaluations.extend(
        RoleCandidateEvaluation(candidate=candidate, validation=validation, stage="initial", source_role=role)
        for candidate, validation in rejected
    )
    return RoleRetrievalBucket(
        role=role,
        query=f"query for {role}",
        helper_queries=(f"query for {role}",),
        observations=(),
        evaluations=tuple(evaluations),
        accepted_candidates=tuple(accepted),
        rejected_refs=tuple(candidate.source_id for candidate, _ in rejected),
        validation_notes=tuple(validation.reason for validation in [evaluation.validation for evaluation in evaluations]),
        missing_reason="",
    )


def _step2_response(subqueries: list[tuple[str, str]] | None = None) -> dict[str, object]:
    pairs = subqueries or [
        ("input_parsing", "where is parseClassDeclaration syntax parsed"),
        ("validation_checking", "where is abstract class validation enforced"),
    ]
    return {
        "prompt_summary": "Support abstract classes and methods, including parser recognition, validation, diagnostics, and super-call restrictions.",
        "retrieval_terms": ["abstract class", "abstract method", "super call", "diagnostic message"],
        "llm_concept_terms": ["abstract class"],
        "llm_subqueries": [{"role": role, "query": query} for role, query in pairs],
        "speculative_entities": ["checkAbstractMembers"],
        "source_priorities": ["source_code"],
        "negative_filters": ["harness"],
    }


def _late_synthesis_response(
    *,
    accepted_anchor_refs: list[str] | None = None,
    rejected_anchor_refs: list[str] | None = None,
    missing_areas: list[str] | None = None,
) -> dict[str, object]:
    refs = accepted_anchor_refs or []
    return {
        "acceptance_satisfied": bool(refs),
        "stop_reason": "validated_role_buckets",
        "missing_areas": missing_areas or [],
        "accepted_anchor_refs": refs,
        "rejected_anchor_refs": rejected_anchor_refs or [],
        "snippet_assessment": [{"ref": ref, "role": "core", "reason": "validated implementation anchor"} for ref in refs],
        "follow_up_queries": [],
    }


def _policy_result(
    state: ConversationState,
    *,
    allowed_sources: tuple[SourceCategory, ...] = (
        SourceCategory.SOURCE_CODE,
        SourceCategory.DOCUMENTATION,
        SourceCategory.ISSUE_TRACKER,
        SourceCategory.PULL_REQUEST,
        SourceCategory.LOCAL_NOTES,
        SourceCategory.NOTEBOOKLM,
    ),
):
    policy = PolicyStage(SourcePolicy(allowed_categories=allowed_sources, policy_name="test"))
    return policy.decide(state)


def _completed(*, stdout: str = "", stderr: str = "", returncode: int = 0):
    class Completed:
        def __init__(self) -> None:
            self.stdout = stdout
            self.stderr = stderr
            self.returncode = returncode

    return Completed()


class _fake_cgc:
    def __init__(
        self,
        files: list[dict[str, object]] | None = None,
        fail_on: tuple[str, ...] | None = None,
        files_by_command: dict[tuple[str, ...], list[dict[str, object]]] | None = None,
        query_rows_by_contains: dict[str, list[dict[str, object]]] | None = None,
    ) -> None:
        self.files = files or [{"path": "src/parser.ts"}]
        self.fail_on = fail_on
        self.files_by_command = files_by_command or {}
        self.query_rows_by_contains = query_rows_by_contains or {}

    def __enter__(self):
        def fake_run(command, **kwargs):
            command_tail = tuple(command[1:3]) if len(command) >= 3 else tuple(command[1:])
            if self.fail_on is not None and command_tail == self.fail_on:
                return _completed(stderr="failed", returncode=1)
            if command[1] == "index":
                return _completed(stdout="indexed")
            if command[1] == "query":
                query_text = command[-1]
                for needle, rows in self.query_rows_by_contains.items():
                    if needle in query_text:
                        return _completed(stdout=json.dumps(rows))
                return _completed(stdout="[]")
            cwd = Path(str(kwargs.get("cwd", ".")))
            rows = []
            active_files = self.files_by_command.get(command_tail, self.files)
            for item in active_files:
                path = str(item["path"]).replace("/", "\\")
                rows.append(("match", "Function", str((cwd / path).resolve())))
            return _completed(stdout=_cgc_table(rows))

        self.patcher = patch("services.retrieval.tools.cgc.subprocess.run", side_effect=fake_run)
        self.patcher.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.patcher.stop()


def _cgc_table(rows: list[tuple[str, str, str]]) -> str:
    header = [
        "+--------------------------------------------------------------------------------+",
        "| Name | Type | Location |",
        "|------+------|----------|",
    ]
    body = [f"| {name} | {kind} | {location} |" for name, kind, location in rows]
    footer = ["+--------------------------------------------------------------------------------+"]
    return "\n".join(header + body + footer)


class _FakeLLMHandler(BaseHTTPRequestHandler):
    response_payloads: list[object] = []

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        content = self.response_payloads.pop(0)
        if not isinstance(content, str):
            content = json.dumps(content)
        body = json.dumps({"choices": [{"message": {"content": content}}]}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        return


class _fake_llm_server:
    def __init__(self, response_payloads: list[object]) -> None:
        self.response_payloads = response_payloads
        self.server: HTTPServer | None = None
        self.thread: threading.Thread | None = None

    def __enter__(self) -> str:
        _FakeLLMHandler.response_payloads = list(self.response_payloads)
        self.server = HTTPServer(("127.0.0.1", 0), _FakeLLMHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        return f"http://{host}:{port}/v1/chat/completions"

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        if self.thread is not None:
            self.thread.join(timeout=2)


class _BytesReader:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self, *args, **kwargs) -> bytes:
        return self._data


class _FakeHTTPResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


if __name__ == "__main__":
    unittest.main()
