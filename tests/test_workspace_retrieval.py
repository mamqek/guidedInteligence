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
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import StringIO
from pathlib import Path
import sys
from unittest.mock import patch

from core.models import ConversationState, EvidenceItem, UserIntent
from core.policy import PolicyStage
from core.source_policy import SourceCategory, SourcePolicy
from core.stages import ResponseStage
from services.retrieval.bm25 import build_index_from_repo, save_index
from services.retrieval import workspace_llm
from services.retrieval.bm25 import BM25SearchResult
from services.retrieval.config import (
    RetrievalEmbeddingConfig,
    RetrievalQdrantConfig,
    RunLLMConfig,
    WorkspaceRetrievalConfig,
    load_retrieval_embedding_config,
    load_retrieval_llm_config,
    load_retrieval_qdrant_config,
)
from services.retrieval.qdrant_backend import QdrantSearchResult
from services.retrieval.responsibility import profile_candidate, score_responsibility
from services.retrieval.step2 import RoleDirectedSubquery, WorkspaceRetrievalPlan
from services.retrieval.role_validation import AnchorSupport, supported_roles
from services.retrieval.tools import cgc_tool_specs, local_tool_specs, qdrant_tool_specs
from services.retrieval.tools.local import OpenFileTool
from services.retrieval.tools.qdrant import QdrantHybridSearchTool
from services.retrieval.tools.cgc import CGCAnalyzeDepsTool, CGCFindCodeTool, CGCQueryGraphTool, CGCRunCliTool
from services.retrieval.tools.contracts import ToolObservation, ToolRequest
from services.retrieval.workspace import (
    PreparedRoleBucket,
    RetrievalCandidate,
    RetrievalSynthesisDecision,
    RoleCandidateEvaluation,
    RoleRetrievalBucket,
    RoleValidationResult,
    WorkspaceRetrievalStage,
    _extract_explicit_reference_paths,
    _iterative_code_context_queries,
    _resolve_explicit_reference_path,
    _role_scoped_narrowed_files,
    _role_retarget_queries,
    _select_diverse_completion_entries,
)
from services.retrieval.obsidian import ObsidianSearchResult


class WorkspaceRetrievalStageFixture(unittest.TestCase):
    def setUp(self) -> None:
        workspace_llm._TEMPERATURE_DISABLED_MODELS.clear()
        def fake_ensure_available(_backend):
            return None

        def fake_rebuild_collection(backend, log_event=None):
            return len(backend.index.documents)

        def fake_collection_exists(_backend):
            return True

        def fake_index_signature(backend):
            return f"sig:{len(backend.index.documents)}"

        def fake_point_count(backend):
            return len(backend.index.documents)

        def fake_hybrid_search(
            backend,
            query,
            *,
            limit,
            path="",
            paths=(),
            min_score=0.0,
            source_category="",
            file_role="",
        ):
            results = backend.index.search(query, limit=len(backend.index.documents))
            if path:
                normalized = path.replace("\\", "/")
                results = tuple(result for result in results if result.chunk.path == normalized)
            if paths:
                normalized_paths = {str(item).replace("\\", "/") for item in paths}
                results = tuple(result for result in results if result.chunk.path in normalized_paths)
            if source_category:
                results = tuple(result for result in results if result.chunk.source_category.value == source_category)
            if file_role:
                results = tuple(result for result in results if str(result.chunk.metadata.get("file_role", "")) == file_role)
            results = tuple(result for result in results if result.score >= min_score)[:limit]
            return tuple(
                QdrantSearchResult(
                    chunk=result.chunk,
                    score=result.score,
                    matched_terms=result.matched_terms,
                )
                for result in results
            )

        self.qdrant_patches = [
            patch("services.retrieval.qdrant_backend.QdrantHybridBackend.ensure_available", new=fake_ensure_available),
            patch("services.retrieval.qdrant_backend.QdrantHybridBackend.rebuild_collection", new=fake_rebuild_collection),
            patch("services.retrieval.qdrant_backend.QdrantHybridBackend.collection_exists", new=fake_collection_exists),
            patch("services.retrieval.qdrant_backend.QdrantHybridBackend.index_signature", new=fake_index_signature),
            patch("services.retrieval.qdrant_backend.QdrantHybridBackend.point_count", new=fake_point_count),
            patch("services.retrieval.qdrant_backend.QdrantHybridBackend.search", new=fake_hybrid_search),
        ]
        for patcher in self.qdrant_patches:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(getattr(self, "qdrant_patches", [])):
            patcher.stop()


class BM25IndexBuildTests(unittest.TestCase):
    def test_structure_aware_chunking_prefers_declaration_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            (root / "src").mkdir(parents=True)
            (root / "src" / "example.ts").write_text(
                "\n".join(
                    [
                        "import { x } from './x';",
                        "",
                        "function parseClassDeclaration() {",
                        "  return 'abstract';",
                        "}",
                        "",
                        "function checkAbstractClass() {",
                        "  return 'cannot instantiate abstract class';",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )

            index = build_index_from_repo(repo_path=root, commit="test", chunk_line_count=40, chunk_line_overlap=10)

            file_docs = [document for document in index.documents if document.chunk.path == "src/example.ts"]
            self.assertEqual(len(file_docs), 3)
            self.assertIn("parseClassDeclaration", file_docs[1].chunk.text)
            self.assertNotIn("checkAbstractClass", file_docs[1].chunk.text)
            self.assertIn("checkAbstractClass", file_docs[2].chunk.text)

    def test_generated_bin_files_are_skipped_from_indexing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            (root / "src" / "compiler").mkdir(parents=True)
            (root / "bin").mkdir(parents=True)
            (root / "src" / "compiler" / "parser.ts").write_text(
                "function parseClassDeclaration() { return 'abstract'; }\n",
                encoding="utf-8",
            )
            (root / "bin" / "services.js").write_text(
                "function generated() { return 'noise'; }\n",
                encoding="utf-8",
            )

            index = build_index_from_repo(repo_path=root, commit="test", chunk_line_count=40, chunk_line_overlap=10)

            indexed_paths = {document.chunk.path for document in index.documents}
            self.assertIn("src/compiler/parser.ts", indexed_paths)
            self.assertNotIn("bin/services.js", indexed_paths)

    def test_utf16_source_files_are_indexed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            (root / "src" / "compiler").mkdir(parents=True)
            (root / "src" / "compiler" / "checker.ts").write_text(
                "export function createTypeChecker() { return 'semantic checker'; }\n",
                encoding="utf-16",
            )

            index = build_index_from_repo(repo_path=root, commit="test", chunk_line_count=40, chunk_line_overlap=10)

            indexed_paths = {document.chunk.path for document in index.documents}
            self.assertIn("src/compiler/checker.ts", indexed_paths)

    def test_cp1252_source_files_do_not_fall_through_to_utf16_mojibake(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            (root / "src" / "compiler").mkdir(parents=True)
            (root / "src" / "compiler" / "checker.ts").write_text(
                "/// <reference path=\"types.ts\"/>\nexport function checkAbstractClass() { return 'can\u2019t instantiate'; }\n",
                encoding="cp1252",
            )

            index = build_index_from_repo(repo_path=root, commit="test", chunk_line_count=40, chunk_line_overlap=10)

            checker_chunks = [document.chunk.text for document in index.documents if document.chunk.path == "src/compiler/checker.ts"]
            self.assertTrue(checker_chunks)
            self.assertIn("checkAbstractClass", "\n".join(checker_chunks))


class WorkspaceRetrievalStageTests(WorkspaceRetrievalStageFixture):
    def test_existing_state_evidence_returns_without_reindexing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, _fake_llm_server([]) as server_url:
            root = Path(temp_dir)
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(root),
                    index_dir=str(root / "index"),
                    llm_config=_llm_config(server_url),
                    embedding_config=_embedding_config(),
                    qdrant_config=_qdrant_config(),
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
                WorkspaceRetrievalStage(
                    WorkspaceRetrievalConfig(
                        workspace_root=str(repo),
                        index_dir=str(root / "index"),
                        embedding_config=_embedding_config(),
                        qdrant_config=_qdrant_config(),
                    )
                )

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
                    embedding_config=_embedding_config(),
                    qdrant_config=_qdrant_config(),
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
                    embedding_config=_embedding_config(),
                    qdrant_config=_qdrant_config(),
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
                    embedding_config=_embedding_config(),
                    qdrant_config=_qdrant_config(),
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

    def test_responsibility_profile_demotes_diagnostics_catalog_outside_diagnostics_role(self) -> None:
        profile = profile_candidate(
            "validation_checking",
            path="src/compiler/diagnosticMessages.json",
            text='{"Cannot instantiate abstract class": {"category": "Error"}}',
            file_role="implementation",
        )

        self.assertTrue(profile.support_only)
        self.assertFalse(profile.noise)
        self.assertIn("diagnostics_catalog", profile.reasons)

        diagnostics_profile = profile_candidate(
            "diagnostics",
            path="src/compiler/diagnosticMessages.json",
            text='{"Cannot instantiate abstract class": {"category": "Error"}}',
            file_role="implementation",
        )

        self.assertEqual(diagnostics_profile.classification, "likely_owner")

    def test_responsibility_score_prefers_checker_over_parser_for_validation_role(self) -> None:
        parser_score = score_responsibility(
            "validation_checking",
            path="src/compiler/parser.ts",
            text="function parseClassDeclaration() { return SyntaxKind.AbstractKeyword; }",
            retrieval_score=10.0,
            validation_score=1.0,
            file_role="implementation",
        )
        checker_score = score_responsibility(
            "validation_checking",
            path="src/compiler/checker.ts",
            text="function checkAbstractClass() { errorCannotInstantiateAbstractClass(); return diagnostics; }",
            retrieval_score=6.0,
            validation_score=2.0,
            file_role="implementation",
        )

        self.assertTrue(parser_score.profile.support_only)
        self.assertGreater(checker_score.total_score, parser_score.total_score)
        self.assertEqual(checker_score.profile.classification, "likely_owner")

    def test_responsibility_score_demotes_low_level_datetime_below_public_api_owner(self) -> None:
        low_level_score = score_responsibility(
            "representation",
            path="pandas/src/datetime/np_datetime.c",
            text="static int convert_datetime_to_tsobject(void) { return 0; }",
            retrieval_score=10.0,
            validation_score=1.0,
            file_role="implementation",
        )
        public_score = score_responsibility(
            "representation",
            path="pandas/core/indexes/datetimes.py",
            text="class DatetimeIndex: public API for datetime data",
            retrieval_score=6.0,
            validation_score=1.5,
            file_role="implementation",
        )

        self.assertTrue(low_level_score.profile.support_only)
        self.assertGreater(public_score.total_score, low_level_score.total_score)

    def test_extract_explicit_reference_paths_and_resolution(self) -> None:
        text = '/// <reference path="checker.ts"/>\n/// <reference path="..\\\\compiler\\\\checker.ts"/>'

        references = _extract_explicit_reference_paths(text)

        self.assertEqual(references, ("checker.ts", "..\\\\compiler\\\\checker.ts"))
        self.assertEqual(_resolve_explicit_reference_path("src/compiler/tc.ts", "checker.ts"), "src/compiler/checker.ts")
        self.assertEqual(
            _resolve_explicit_reference_path("src/services/services.ts", "..\\\\compiler\\\\checker.ts"),
            "src/compiler/checker.ts",
        )

    def test_converging_references_inject_checker_and_block_generic_hubs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, _fake_llm_server([_step2_response()]) as server_url:
            root = Path(temp_dir)
            repo = root / "repo"
            (repo / "src" / "compiler").mkdir(parents=True)
            (repo / "src" / "services").mkdir(parents=True)
            (repo / "src" / "compiler" / "checker.ts").write_text(
                "export function createTypeChecker() { return 'semantic'; }\n",
                encoding="utf-8",
            )
            (repo / "src" / "compiler" / "types.ts").write_text(
                "export interface TypeChecker {}\n",
                encoding="utf-8",
            )
            (repo / "src" / "compiler" / "tc.ts").write_text(
                "\n".join(
                    [
                        '/// <reference path="types.ts"/>',
                        '/// <reference path="checker.ts"/>',
                        "module ts {",
                        "  function run(program: Program) {",
                        "    var checker = program.getTypeChecker();",
                        "    return checker.getDiagnostics();",
                        "  }",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            (repo / "src" / "services" / "services.ts").write_text(
                "\n".join(
                    [
                        '/// <reference path="..\\\\compiler\\\\types.ts"/>',
                        '/// <reference path="..\\\\compiler\\\\checker.ts"/>',
                        "module ts.Services {",
                        "  class SignatureObject {",
                        "    checker: TypeChecker;",
                        "  }",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(repo),
                    index_dir=str(root / "index"),
                    llm_config=_llm_config(server_url),
                    embedding_config=_embedding_config(),
                    qdrant_config=_qdrant_config(),
                )
            )
            index = build_index_from_repo(repo_path=repo, commit="workspace")
            open_file_tool = OpenFileTool(index)

            converged_targets, tool_calls = stage._collect_converging_reference_targets(
                role="validation_checking",
                candidates=(
                    _test_candidate("src/services/services.ts", "checker: TypeChecker; class SignatureObject {}", "validation_checking", "repo:services"),
                    _test_candidate("src/compiler/tc.ts", "var checker = program.getTypeChecker(); checker.getDiagnostics();", "validation_checking", "repo:tc"),
                ),
                open_file_tool=open_file_tool,
            )

            self.assertEqual(converged_targets, ("src/compiler/checker.ts",))
            self.assertEqual(tool_calls, 2)

    def test_single_reference_source_does_not_inject_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, _fake_llm_server([_step2_response()]) as server_url:
            root = Path(temp_dir)
            repo = root / "repo"
            (repo / "src" / "compiler").mkdir(parents=True)
            (repo / "src" / "services").mkdir(parents=True)
            (repo / "src" / "compiler" / "checker.ts").write_text(
                "export function createTypeChecker() { return 'semantic'; }\n",
                encoding="utf-8",
            )
            (repo / "src" / "services" / "services.ts").write_text(
                '/// <reference path="..\\\\compiler\\\\checker.ts"/>\nclass SignatureObject { checker: TypeChecker; }\n',
                encoding="utf-8",
            )
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(repo),
                    index_dir=str(root / "index"),
                    llm_config=_llm_config(server_url),
                    embedding_config=_embedding_config(),
                    qdrant_config=_qdrant_config(),
                )
            )
            index = build_index_from_repo(repo_path=repo, commit="workspace")
            open_file_tool = OpenFileTool(index)

            converged_targets, _tool_calls = stage._collect_converging_reference_targets(
                role="validation_checking",
                candidates=(
                    _test_candidate("src/services/services.ts", "checker: TypeChecker; class SignatureObject {}", "validation_checking", "repo:services"),
                ),
                open_file_tool=open_file_tool,
            )

            self.assertEqual(converged_targets, ())

    def test_single_reference_source_injects_target_when_owner_layer_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, _fake_llm_server([_step2_response()]) as server_url:
            root = Path(temp_dir)
            repo = root / "repo"
            (repo / "src" / "compiler").mkdir(parents=True)
            (repo / "src" / "compiler" / "checker.ts").write_text(
                "export function createTypeChecker() { return 'semantic'; }\n",
                encoding="utf-8",
            )
            (repo / "src" / "compiler" / "tc.ts").write_text(
                '/// <reference path="checker.ts"/>\nvar checker = program.getTypeChecker();\n',
                encoding="utf-8",
            )
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(repo),
                    index_dir=str(root / "index"),
                    llm_config=_llm_config(server_url),
                    embedding_config=_embedding_config(),
                    qdrant_config=_qdrant_config(),
                )
            )
            index = build_index_from_repo(repo_path=repo, commit="workspace")
            open_file_tool = OpenFileTool(index)

            converged_targets, _tool_calls = stage._collect_converging_reference_targets(
                role="validation_checking",
                candidates=(
                    _test_candidate("src/compiler/tc.ts", "var checker = program.getTypeChecker();", "validation_checking", "repo:tc"),
                ),
                open_file_tool=open_file_tool,
                min_votes=1,
            )

            self.assertEqual(converged_targets, ("src/compiler/checker.ts",))

    def test_reference_expansion_sources_are_path_diverse(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, _fake_llm_server([_step2_response()]) as server_url:
            root = Path(temp_dir)
            repo = root / "repo"
            repo.mkdir(parents=True)
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(repo),
                    index_dir=str(root / "index"),
                    llm_config=_llm_config(server_url),
                    embedding_config=_embedding_config(),
                    qdrant_config=_qdrant_config(),
                )
            )
            candidates = tuple(
                _test_candidate("src/compiler/binder.ts", "check diagnostics binder", "validation_checking", f"repo:binder:{index}")
                for index in range(6)
            ) + (
                _test_candidate("src/compiler/tc.ts", "var checker = program.getTypeChecker();", "validation_checking", "repo:tc"),
                _test_candidate("src/services/services.ts", "checker: TypeChecker; class SignatureObject {}", "validation_checking", "repo:services"),
            )
            bucket = PreparedRoleBucket(
                role="validation_checking",
                query="where are abstract class constraints enforced",
                helper_queries=(),
                observations=(),
                candidates=candidates,
            )

            sources = stage._reference_expansion_source_candidates(
                role="validation_checking",
                prepared_bucket=bucket,
                prepared_buckets=(bucket,),
            )

            self.assertEqual(
                [candidate.path for candidate in sources],
                ["src/compiler/binder.ts", "src/compiler/tc.ts", "src/services/services.ts"],
            )

    def test_iterative_code_context_query_uses_first_pass_identifiers(self) -> None:
        queries = _iterative_code_context_queries(
            role="validation_checking",
            query="where are abstract class constraints enforced",
            candidates=(
                _test_candidate(
                    "src/services/services.ts",
                    "class SignatureObject { checker: TypeChecker; getReturnType() { return this.checker.getReturnTypeOfSignature(this); } }",
                    "validation_checking",
                    "repo:services",
                ),
            ),
        )

        self.assertEqual(len(queries), 1)
        self.assertIn("TypeChecker", queries[0])
        self.assertIn("checker", queries[0])

    def test_direct_owner_candidate_targets_large_unindexed_owner_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, _fake_llm_server([_step2_response()]) as server_url:
            root = Path(temp_dir)
            repo = root / "repo"
            (repo / "src" / "compiler").mkdir(parents=True)
            (repo / "src" / "compiler" / "checker.ts").write_text(
                "\n".join(
                    [
                        "module ts {",
                        *[f"  var filler{index} = {index};" for index in range(120)],
                        "  function getDeclaredTypeOfClass(symbol: Symbol): InterfaceType {",
                        "    var declaration = <ClassDeclaration>getDeclarationOfKind(symbol, SyntaxKind.ClassDeclaration);",
                        "    if (declaration.baseType) {",
                        "      error(declaration.baseType, Diagnostics.A_class_may_only_extend_another_class);",
                        "    }",
                        "  }",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(repo),
                    index_dir=str(root / "index"),
                    llm_config=_llm_config(server_url),
                    embedding_config=_embedding_config(),
                    qdrant_config=_qdrant_config(),
                )
            )

            candidate = stage._direct_owner_candidate_from_path(
                role="validation_checking",
                target_path="src/compiler/checker.ts",
                query="where class declarations and base class constraints are checked",
            )

            self.assertIsNotNone(candidate)
            self.assertEqual(candidate.path, "src/compiler/checker.ts")
            self.assertIn("getDeclaredTypeOfClass", candidate.text)
            self.assertIn("A_class_may_only_extend_another_class", candidate.text)

    def test_local_in_file_refinement_prefers_role_specific_declaration_span(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, _fake_llm_server([_step2_response()]) as server_url:
            root = Path(temp_dir)
            repo = root / "repo"
            (repo / "src").mkdir(parents=True)
            (repo / "src" / "owner.ts").write_text(
                "\n".join(
                    [
                        "function helper() { return true; }",
                        *[f"var filler{index} = {index};" for index in range(90)],
                        "function checkConstructorRules(node: ConstructorDeclaration) {",
                        "  if (containsSuperCall(node.body)) {",
                        "    error(node, Diagnostics.Constructors_for_derived_classes_must_contain_a_super_call);",
                        "  }",
                        "}",
                        *[f"var middle{index} = {index};" for index in range(90)],
                        "function checkClassDeclaration(node: ClassDeclaration) {",
                        "  checkTypeReference(node.baseType);",
                        "  checkTypeAssignableTo(type, baseType, node.name, Diagnostics.Class_0_incorrectly_extends_base_class_1);",
                        "  checkTypeAssignableTo(type, implementedType, node.name, Diagnostics.Class_0_incorrectly_implements_interface_1);",
                        "  checkKindsOfPropertyMemberOverrides(type, baseType);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(repo),
                    index_dir=str(root / "index"),
                    llm_config=_llm_config(server_url),
                    embedding_config=_embedding_config(),
                    qdrant_config=_qdrant_config(),
                )
            )
            candidate = _test_candidate(
                "src/owner.ts",
                "function helper() { return true; }",
                "validation_checking",
                "repo:src/owner.ts:L1-L1",
            )

            refined = stage._refine_candidate_with_local_file_search(
                role="validation_checking",
                query="where are class extends and implements validation rules enforced",
                helper_queries=("class declaration base class implements diagnostics",),
                candidate=candidate,
                search_terms=("abstract class", "must implement inherited members", "base class", "super"),
            )

            self.assertIsNotNone(refined)
            assert refined is not None
            self.assertIn("checkClassDeclaration", refined.text)
            self.assertIn("Class_0_incorrectly_implements_interface_1", refined.text)
            self.assertNotIn("checkConstructorRules", refined.text)

    def test_direct_owner_candidate_reads_utf16_owner_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, _fake_llm_server([_step2_response()]) as server_url:
            root = Path(temp_dir)
            repo = root / "repo"
            (repo / "src" / "compiler").mkdir(parents=True)
            (repo / "src" / "compiler" / "checker.ts").write_text(
                "\n".join(
                    [
                        "module ts {",
                        "  function getDeclaredTypeOfClass(symbol: Symbol): InterfaceType {",
                        "    var declaration = <ClassDeclaration>getDeclarationOfKind(symbol, SyntaxKind.ClassDeclaration);",
                        "    if (declaration.baseType) {",
                        "      error(declaration.baseType, Diagnostics.A_class_may_only_extend_another_class);",
                        "    }",
                        "  }",
                        "}",
                    ]
                ),
                encoding="utf-16",
            )
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(repo),
                    index_dir=str(root / "index"),
                    llm_config=_llm_config(server_url),
                    embedding_config=_embedding_config(),
                    qdrant_config=_qdrant_config(),
                )
            )

            candidate = stage._direct_owner_candidate_from_path(
                role="validation_checking",
                target_path="src/compiler/checker.ts",
                query="where class declarations and base class constraints are checked",
            )

            self.assertIsNotNone(candidate)
            self.assertIn("getDeclaredTypeOfClass", candidate.text)

    def test_direct_owner_candidate_reads_cp1252_owner_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, _fake_llm_server([_step2_response()]) as server_url:
            root = Path(temp_dir)
            repo = root / "repo"
            (repo / "src" / "compiler").mkdir(parents=True)
            (repo / "src" / "compiler" / "checker.ts").write_text(
                "\n".join(
                    [
                        "/// <reference path=\"types.ts\"/>",
                        "module ts {",
                        "  function getDeclaredTypeOfClass(symbol: Symbol): InterfaceType {",
                        "    var declaration = <ClassDeclaration>getDeclarationOfKind(symbol, SyntaxKind.ClassDeclaration);",
                        "    if (declaration.baseType) {",
                        "      error(declaration.baseType, Diagnostics.A_class_may_only_extend_another_class);",
                        "    }",
                        "  }",
                        "  var apostrophe = 'can\u2019t instantiate abstract class';",
                        "}",
                    ]
                ),
                encoding="cp1252",
            )
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(repo),
                    index_dir=str(root / "index"),
                    llm_config=_llm_config(server_url),
                    embedding_config=_embedding_config(),
                    qdrant_config=_qdrant_config(),
                )
            )

            candidate = stage._direct_owner_candidate_from_path(
                role="validation_checking",
                target_path="src/compiler/checker.ts",
                query="where class declarations and base class constraints are checked",
            )

            self.assertIsNotNone(candidate)
            self.assertIn("getDeclaredTypeOfClass", candidate.text)
            self.assertNotIn("\u2f2f", candidate.text)

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
                    embedding_config=_embedding_config(),
                    qdrant_config=_qdrant_config(),
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
                    embedding_config=_embedding_config(),
                    qdrant_config=_qdrant_config(),
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

    def test_reference_convergence_promotes_checker_to_top_validation_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, _fake_llm_server(
            [
                _step2_response(subqueries=[("validation_checking", "where are abstract class constraints enforced")]),
                _late_synthesis_response(accepted_anchor_refs=["workspace:src/compiler/checker.ts:L1-L1"]),
            ]
        ) as server_url:
            root = Path(temp_dir)
            repo = root / "repo"
            (repo / "src" / "compiler").mkdir(parents=True)
            (repo / "src" / "services").mkdir(parents=True)
            (repo / "src" / "compiler" / "checker.ts").write_text(
                "\n".join(
                    [
                        "module ts {",
                        "  export function createTypeChecker(program: Program): TypeChecker {",
                        "    return undefined;",
                        "  }",
                        "  function checkAbstractClass() {",
                        "    return 'cannot instantiate abstract class';",
                        "  }",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            (repo / "src" / "compiler" / "tc.ts").write_text(
                "\n".join(
                    [
                        '/// <reference path="types.ts"/>',
                        '/// <reference path="checker.ts"/>',
                        "module ts {",
                        "  function run(program: Program) {",
                        "    var checker = program.getTypeChecker();",
                        "    return checker.getDiagnostics();",
                        "  }",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            (repo / "src" / "services" / "services.ts").write_text(
                "\n".join(
                    [
                        '/// <reference path="..\\\\compiler\\\\types.ts"/>',
                        '/// <reference path="..\\\\compiler\\\\checker.ts"/>',
                        "module ts.Services {",
                        "  class SignatureObject {",
                        "    checker: TypeChecker;",
                        "    declaration: SignatureDeclaration;",
                        "  }",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            (repo / "src" / "compiler" / "types.ts").write_text(
                "export interface TypeChecker { getDiagnostics(): Diagnostic[]; }\n",
                encoding="utf-8",
            )
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(repo),
                    index_dir=str(root / "index"),
                    run_dir=str(root / "run"),
                    llm_config=_llm_config(server_url),
                    embedding_config=_embedding_config(),
                    qdrant_config=_qdrant_config(),
                )
            )
            state = ConversationState(
                conversation_id="conv",
                user_input="Explain where abstract class constraints are enforced.",
                current_stage=ResponseStage.EXPLAIN,
                intent=UserIntent.UNDERSTAND_CODE,
            )

            with _fake_cgc(files=[{"path": "src/compiler/checker.ts"}, {"path": "src/compiler/tc.ts"}, {"path": "src/services/services.ts"}]):
                result = stage.retrieve(state, _policy_result(state, allowed_sources=(SourceCategory.SOURCE_CODE,)))

            validation_bucket = next(bucket for bucket in result.retrieval_summary["required_role_buckets"] if bucket["role"] == "validation_checking")
            self.assertGreaterEqual(len(validation_bucket["accepted_refs"]), 1)
            self.assertEqual(validation_bucket["snippets"][0]["path"], "src/compiler/checker.ts")
            self.assertIn("src/compiler/checker.ts", validation_bucket["accepted_refs"][0])

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
                    embedding_config=_embedding_config(),
                    qdrant_config=_qdrant_config(),
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

    def test_late_role_rescue_specs_prioritize_follow_up_queries_without_path_filter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, _fake_llm_server([_step2_response()]) as server_url:
            root = Path(temp_dir)
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(root),
                    index_dir=str(root / "index"),
                    llm_config=_llm_config(server_url),
                    embedding_config=_embedding_config(),
                    qdrant_config=_qdrant_config(),
                )
            )
            bucket = _test_bucket(
                role="validation_checking",
                accepted=[_test_candidate("src/compiler/binder.ts", "function declareModuleMember() {}", "validation_checking", "repo:binder")],
            )
            all_buckets = (
                _test_bucket(role="representation", accepted=[_test_candidate("src/compiler/types.ts", "flags SymbolFlags", "representation", "repo:types")]),
                _test_bucket(role="input_parsing", accepted=[_test_candidate("src/compiler/parser.ts", "function parseClassDeclaration() {}", "input_parsing", "repo:parser")]),
                bucket,
            )

            specs = stage._late_role_rescue_specs(
                bucket=bucket,
                follow_up_queries=("path:src/compiler/checker.ts checkClassLikeDeclaration checkNewExpression",),
                narrowed_files=("src/compiler/binder.ts", "src/compiler/checker.ts"),
                all_buckets=all_buckets,
            )

            self.assertGreaterEqual(len(specs), 1)
            self.assertEqual(specs[0]["query"], "path:src/compiler/checker.ts checkClassLikeDeclaration checkNewExpression")
            self.assertEqual(tuple(specs[0]["paths"]), ())
            self.assertTrue(all(tuple(spec["paths"]) == () for spec in specs))

    def test_role_completion_promotes_checker_over_tc_for_validation_role(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, _fake_llm_server([_step2_response()]) as server_url:
            root = Path(temp_dir)
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(root),
                    index_dir=str(root / "index"),
                    llm_config=_llm_config(server_url),
                    embedding_config=_embedding_config(),
                    qdrant_config=_qdrant_config(),
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
                    embedding_config=_embedding_config(),
                    qdrant_config=_qdrant_config(),
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

    def test_late_assessment_downgrades_noise_bucket(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, _fake_llm_server([_step2_response()]) as server_url:
            root = Path(temp_dir)
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(root),
                    index_dir=str(root / "index"),
                    llm_config=_llm_config(server_url),
                    embedding_config=_embedding_config(),
                    qdrant_config=_qdrant_config(),
                )
            )
            bucket = _test_bucket(
                role="validation_checking",
                accepted=[_test_candidate("src/compiler/binder.ts", "function bind(node) { return true; }", "validation_checking", "repo:binder")],
            )
            updated = stage._apply_synthesis_feedback(
                buckets=(bucket,),
                decision=RetrievalSynthesisDecision(
                    acceptance_satisfied=False,
                    missing_areas=("validation_checking",),
                    accepted_anchor_refs=(),
                    rejected_anchor_refs=("repo:binder",),
                    snippet_assessment=({"ref": "repo:binder", "role": "noise", "reason": "binder plumbing"},),
                    stop_reason="missing checker logic",
                    follow_up_queries=({"role": "validation_checking", "query": "semantic checker diagnostics", "reason": "missing enforcement"},),
                ),
                required_roles=("validation_checking",),
            )
            self.assertEqual(updated[0].role_status, "missing")
            self.assertEqual(updated[0].satisfying_refs, ())

    def test_recovery_pass_is_single_and_promotes_stronger_qdrant_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, _fake_llm_server([_step2_response()]) as server_url:
            root = Path(temp_dir)
            repo = root / "repo"
            (repo / "src" / "compiler").mkdir(parents=True)
            (repo / "src" / "compiler" / "binder.ts").write_text(
                "function bind(node) { return node.flags; }\n",
                encoding="utf-8",
            )
            (repo / "src" / "compiler" / "checker.ts").write_text(
                "function checkAbstractClass() { return 'cannot instantiate abstract class'; }\n",
                encoding="utf-8",
            )
            index = build_index_from_repo(repo_path=repo, commit="test")
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(repo),
                    index_dir=str(root / "index"),
                    llm_config=_llm_config(server_url),
                    embedding_config=_embedding_config(),
                    qdrant_config=_qdrant_config(),
                )
            )
            bucket = RoleRetrievalBucket(
                role="validation_checking",
                query="where are abstract class rules enforced",
                helper_queries=("where are abstract class rules enforced",),
                observations=(),
                retrieved_candidates=(
                    _test_candidate("src/compiler/binder.ts", "function bind(node) { return node.flags; }", "validation_checking", "repo:binder"),
                ),
                evaluations=(
                    RoleCandidateEvaluation(
                        candidate=_test_candidate("src/compiler/binder.ts", "function bind(node) { return node.flags; }", "validation_checking", "repo:binder"),
                        validation=_test_validation(accepted=True, reason="validated_role_candidate", total_score=4.2),
                    ),
                ),
                accepted_candidates=(
                    _test_candidate("src/compiler/binder.ts", "function bind(node) { return node.flags; }", "validation_checking", "repo:binder"),
                ),
                rejected_refs=(),
                validation_notes=("validated_role_candidate",),
                missing_reason="late_assessment_downgraded",
                role_status="weak",
                satisfying_refs=("repo:binder",),
                snippet_assessment=({"ref": "repo:binder", "role": "secondary", "reason": "adjacent only"},),
                satisfaction_source="late_assessment",
            )
            qdrant_tool = QdrantHybridSearchTool(
                index,
                qdrant_config=_qdrant_config(),
                embedding_config=_embedding_config(),
            )
            open_file_tool = OpenFileTool(index)
            decision = RetrievalSynthesisDecision(
                acceptance_satisfied=False,
                missing_areas=("validation_checking",),
                accepted_anchor_refs=(),
                rejected_anchor_refs=(),
                snippet_assessment=(),
                stop_reason="missing checker",
                follow_up_queries=({"role": "validation_checking", "query": "cannot instantiate abstract class semantic checker", "reason": "missing checker"},),
            )

            with _fake_cgc(files=[{"path": "src/compiler/checker.ts"}]):
                updated_buckets, _, _ = stage._recover_weak_role_buckets(
                    retrieval_plan=_test_retrieval_plan(required_roles=("validation_checking",)),
                    buckets=(bucket,),
                    synthesis_decision=decision,
                    qdrant_tool=qdrant_tool,
                    open_file_tool=open_file_tool,
                    cgc_tools=stage._cgc_tools(),
                    narrowed_files=("src/compiler/binder.ts", "src/compiler/checker.ts"),
                    starting_tool_call_count=0,
                )

            accepted_paths = [candidate.path for candidate in updated_buckets[0].accepted_candidates]
            self.assertIn("src/compiler/checker.ts", accepted_paths)
            self.assertTrue(any(evaluation.stage == "role_rescue_late_recovery" for evaluation in updated_buckets[0].evaluations))

    def test_obsidian_source_truth_guides_retrieval_to_checker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, _fake_llm_server(
            [
                _step2_response(subqueries=[("validation_checking", "where are abstract class constraints enforced")]),
                _late_synthesis_response(accepted_anchor_refs=["workspace:src/compiler/checker.ts:L1-L3"]),
            ]
        ) as server_url:
            root = Path(temp_dir)
            repo = root / "repo"
            vault = root / "obsidian"
            index_dir = root / "index"
            (repo / "src" / "compiler").mkdir(parents=True)
            vault.mkdir()
            (vault / ".obsidian-hybrid-search.db").write_text("", encoding="utf-8")
            (repo / "src" / "compiler" / "parser.ts").write_text(
                "function parseClassDeclaration() { return 'abstract class syntax'; }\n",
                encoding="utf-8",
            )
            (repo / "src" / "compiler" / "checker.ts").write_text(
                "\n".join(
                    [
                        "function checkAbstractClass(node) {",
                        "  return 'abstract class cannot be instantiated and members must be implemented';",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            index = build_index_from_repo(repo_path=repo, commit="workspace", chunk_line_count=40, chunk_line_overlap=10)
            save_index(index, index_dir)
            (index_dir / "qdrant-sync-manifest.json").write_text(
                json.dumps(
                    {
                        "collection_name": "test-retrieval",
                        "document_count": len(index.documents),
                        "index_signature": f"sig:{len(index.documents)}",
                    }
                ),
                encoding="utf-8",
            )
            note_result = ObsidianSearchResult(
                path="Project retrieval source of truth.md",
                title="Project retrieval source of truth",
                snippet="canonical_file: `src/compiler/checker.ts`",
                score=1.0,
                content="For abstract class behavior, canonical_file: `src/compiler/checker.ts`.",
            )
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(repo),
                    index_dir=str(index_dir),
                    run_dir=str(root / "run"),
                    llm_config=_llm_config(server_url),
                    embedding_config=_embedding_config(),
                    qdrant_config=_qdrant_config(),
                    enable_indexing=False,
                    obsidian_vault_path=str(vault),
                    obsidian_db_path=str(vault / ".obsidian-hybrid-search.db"),
                    obsidian_command=("obsidian-hybrid-search",),
                )
            )
            state = ConversationState(
                conversation_id="conv",
                user_input="Explain TypeScript abstract class behavior.",
                current_stage=ResponseStage.EXPLAIN,
                intent=UserIntent.UNDERSTAND_CODE,
            )

            with patch(
                "services.retrieval.workspace.ObsidianHybridSearchAdapter.search",
                return_value=(note_result,),
            ), patch("services.retrieval.tools.cgc.CGCFindCodeTool.run") as fake_cgc_find:
                fake_cgc_find.return_value = ToolObservation(
                    tool_name="cgc_find_code",
                    status="ok",
                    payload={"files": []},
                    metadata={"result_count": "0"},
                )
                result = stage.retrieve(state, _policy_result(state))

            self.assertIn("src/compiler/checker.ts", result.retrieval_summary["trusted_local_note_file_hints"])
            self.assertNotIn("src/compiler/checker.ts", result.retrieval_summary["retrieval_plan"]["confirmed_file_hints"])
            self.assertIn("src/compiler/checker.ts", result.retrieval_summary["retrieval_plan"]["metadata"]["trusted_local_note_file_hints"])
            selected_paths = {item.metadata.get("path") for item in result.evidence}
            self.assertIn("src/compiler/checker.ts", selected_paths)

    def test_obsidian_file_hints_are_role_scoped_not_global_narrowing(self) -> None:
        plan = _test_retrieval_plan(required_roles=("validation_checking",))
        plan = replace(
            plan,
            metadata={**dict(plan.metadata), "trusted_local_note_file_hints": ["src/compiler/checker.ts"]},
        )

        self.assertIn(
            "src/compiler/checker.ts",
            _role_scoped_narrowed_files(plan, "validation_checking", ()),
        )
        self.assertNotIn(
            "src/compiler/checker.ts",
            _role_scoped_narrowed_files(plan, "input_parsing", ()),
        )

    def test_retarget_uses_shared_role_rescue_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, _fake_llm_server([_step2_response()]) as server_url:
            root = Path(temp_dir)
            repo = root / "repo"
            (repo / "src" / "compiler").mkdir(parents=True)
            parser_path = repo / "src" / "compiler" / "parser.ts"
            parser_path.write_text(
                "\n".join(
                    [
                        "function parsingContextErrors() { return Diagnostics.Statement_expected; }",
                        "function parseAndCheckModifiers() { return SyntaxKind.AbstractKeyword; }",
                        "function parseClassDeclaration() { return parseAndCheckModifiers(); }",
                    ]
                ),
                encoding="utf-8",
            )
            index = build_index_from_repo(repo_path=repo, commit="test")
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(repo),
                    index_dir=str(root / "index"),
                    llm_config=_llm_config(server_url),
                    embedding_config=_embedding_config(),
                    qdrant_config=_qdrant_config(),
                )
            )
            bucket = RoleRetrievalBucket(
                role="input_parsing",
                query="where is abstract parsed",
                helper_queries=("where is abstract parsed",),
                observations=(),
                retrieved_candidates=(
                    _test_candidate("src/compiler/parser.ts", "function parsingContextErrors() { return Diagnostics.Statement_expected; }", "input_parsing", "repo:parser-noise"),
                ),
                evaluations=(
                    RoleCandidateEvaluation(
                        candidate=_test_candidate("src/compiler/parser.ts", "function parsingContextErrors() { return Diagnostics.Statement_expected; }", "input_parsing", "repo:parser-noise"),
                        validation=_test_validation(accepted=True, reason="validated_role_candidate", total_score=4.2),
                    ),
                ),
                accepted_candidates=(
                    _test_candidate("src/compiler/parser.ts", "function parsingContextErrors() { return Diagnostics.Statement_expected; }", "input_parsing", "repo:parser-noise"),
                ),
                rejected_refs=(),
                validation_notes=("validated_role_candidate",),
                missing_reason="",
                role_status="strong",
                satisfying_refs=("repo:parser-noise",),
                snippet_assessment=({"ref": "repo:parser-noise", "role": "secondary", "reason": "generic parser helper"},),
                satisfaction_source="first_pass",
            )
            qdrant_tool = QdrantHybridSearchTool(index, qdrant_config=_qdrant_config(), embedding_config=_embedding_config())
            open_file_tool = OpenFileTool(index)

            updated_bucket, _ = stage._retarget_role_bucket(
                bucket=bucket,
                anchor_support=AnchorSupport(accepted_anchors={}, dependency_paths_by_anchor={}, call_paths_by_anchor={}),
                qdrant_tool=qdrant_tool,
                open_file_tool=open_file_tool,
                cgc_tools=stage._cgc_tools(),
            )

            self.assertTrue(any(evaluation.stage == "role_rescue_retarget" for evaluation in updated_bucket.evaluations))
            accepted_text = "\n".join(candidate.text for candidate in updated_bucket.accepted_candidates)
            self.assertIn("parseAndCheckModifiers", accepted_text)

    def test_supporting_roles_do_not_enter_rescue_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, _fake_llm_server([_step2_response()]) as server_url:
            root = Path(temp_dir)
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(root),
                    index_dir=str(root / "index"),
                    llm_config=_llm_config(server_url),
                    embedding_config=_embedding_config(),
                    qdrant_config=_qdrant_config(),
                )
            )
            docs_bucket = RoleRetrievalBucket(
                role="docs",
                query="docs",
                helper_queries=("docs",),
                observations=(),
                retrieved_candidates=(_test_candidate("docs/abstract.md", "abstract docs", "docs", "repo:docs"),),
                evaluations=(
                    RoleCandidateEvaluation(
                        candidate=_test_candidate("docs/abstract.md", "abstract docs", "docs", "repo:docs"),
                        validation=_test_validation(accepted=True, reason="validated_role_candidate", total_score=4.2),
                    ),
                ),
                accepted_candidates=(_test_candidate("docs/abstract.md", "abstract docs", "docs", "repo:docs"),),
                rejected_refs=(),
                validation_notes=("validated_role_candidate",),
                missing_reason="",
                role_status="strong",
                satisfying_refs=("repo:docs",),
                snippet_assessment=(),
                satisfaction_source="first_pass",
            )

            updated_buckets, _ = stage._retarget_role_buckets(
                buckets=(docs_bucket,),
                rescue_roles=("representation", "input_parsing", "validation_checking", "diagnostics", "behavior_output"),
                qdrant_tool=QdrantHybridSearchTool(build_index_from_repo(repo_path=root, commit="test"), qdrant_config=_qdrant_config(), embedding_config=_embedding_config()),
                open_file_tool=OpenFileTool(build_index_from_repo(repo_path=root, commit="test")),
                cgc_tools=stage._cgc_tools(),
                starting_tool_call_count=0,
            )

            self.assertEqual(updated_buckets[0].accepted_candidates[0].source_id, "repo:docs")
            self.assertFalse(any(evaluation.stage.startswith("role_rescue_") for evaluation in updated_buckets[0].evaluations))

    def test_hard_fail_when_cgc_binary_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, _fake_llm_server([_step2_response()]) as server_url:
            root = Path(temp_dir)
            repo = root / "repo"
            repo.mkdir()
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(repo),
                    index_dir=str(root / "index"),
                    llm_config=_llm_config(server_url),
                    embedding_config=_embedding_config(),
                    qdrant_config=_qdrant_config(),
                )
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
                    embedding_config=_embedding_config(),
                    qdrant_config=_qdrant_config(),
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
                _step2_response(subqueries=[("input_parsing", "where is parseClassDeclaration syntax parsed")]),
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
                "services.llm.json_completion.urllib.request.urlopen",
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
            self.assertFalse(result.sufficient)
            self.assertIn("deterministic_coverage_gate", result.retrieval_summary)


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
                embedding_config=_embedding_config(),
                qdrant_config=_qdrant_config(),
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
                    embedding_config=_embedding_config(),
                    qdrant_config=_qdrant_config(),
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
                    embedding_config=_embedding_config(),
                    qdrant_config=_qdrant_config(),
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
                    embedding_config=_embedding_config(),
                    qdrant_config=_qdrant_config(),
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
                    embedding_config=_embedding_config(),
                    qdrant_config=_qdrant_config(),
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
                    embedding_config=_embedding_config(),
                    qdrant_config=_qdrant_config(),
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
        hybrid_names = {spec.name for spec in qdrant_tool_specs()}
        self.assertIn("qdrant_hybrid_search", hybrid_names)
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
                        "RETRIEVAL_LLM_CONTINUITY_ENABLED=true",
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
            self.assertTrue(config.continuity_enabled)

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

    def test_load_retrieval_embedding_config_reads_documented_env_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "RETRIEVAL_EMBEDDING_API_STYLE=openai_embeddings",
                        "RETRIEVAL_EMBEDDING_ENDPOINT_URL=http://example.test/embeddings",
                        "RETRIEVAL_EMBEDDING_MODEL=text-embedding-3-large",
                        "RETRIEVAL_EMBEDDING_API_KEY=test-secret",
                        "RETRIEVAL_EMBEDDING_TIMEOUT_SECONDS=45",
                        "RETRIEVAL_EMBEDDING_BATCH_SIZE=16",
                        "RETRIEVAL_EMBEDDING_CONCURRENCY=4",
                    ]
                ),
                encoding="utf-8",
            )

            config = load_retrieval_embedding_config(env_path)

            self.assertEqual(config.api_style, "openai_embeddings")
            self.assertEqual(config.endpoint_url, "http://example.test/embeddings")
            self.assertEqual(config.model, "text-embedding-3-large")
            self.assertEqual(config.api_key, "test-secret")
            self.assertEqual(config.timeout_seconds, 45)
            self.assertEqual(config.batch_size, 16)
            self.assertEqual(config.concurrency, 4)

    def test_load_retrieval_qdrant_config_reads_documented_env_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "RETRIEVAL_QDRANT_URL=http://localhost:6333",
                        "RETRIEVAL_QDRANT_COLLECTION=test-retrieval",
                        "RETRIEVAL_QDRANT_TIMEOUT_SECONDS=45",
                    ]
                ),
                encoding="utf-8",
            )

            config = load_retrieval_qdrant_config(env_path)

            self.assertEqual(config.url, "http://localhost:6333")
            self.assertEqual(config.collection_name, "test-retrieval")
            self.assertEqual(config.timeout_seconds, 45)

    def test_workspace_config_validation_rejects_missing_required_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "endpoint_url"):
            WorkspaceRetrievalConfig(
                workspace_root="repo",
                index_dir="index",
                llm_config=RunLLMConfig(api_style="openai_chat_completions", model="gpt-4.1-mini", api_key="secret"),
                embedding_config=_embedding_config(),
                qdrant_config=_qdrant_config(),
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
                embedding_config=_embedding_config(),
                qdrant_config=_qdrant_config(),
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

        with patch("services.llm.json_completion.urllib.request.urlopen", side_effect=fake_urlopen):
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


def _embedding_config() -> RetrievalEmbeddingConfig:
    return RetrievalEmbeddingConfig(
        api_style="openai_embeddings",
        model="text-embedding-3-large",
        endpoint_url="http://example.test/embeddings",
        api_key="test-key",
        timeout_seconds=30,
        batch_size=8,
        concurrency=4,
    )


def _qdrant_config() -> RetrievalQdrantConfig:
    return RetrievalQdrantConfig(
        url="http://example.test:6333",
        collection_name="test-retrieval",
        timeout_seconds=30,
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
        retrieved_candidates=tuple(accepted + [candidate for candidate, _ in rejected]),
        evaluations=tuple(evaluations),
        accepted_candidates=tuple(accepted),
        rejected_refs=tuple(candidate.source_id for candidate, _ in rejected),
        validation_notes=tuple(validation.reason for validation in [evaluation.validation for evaluation in evaluations]),
        missing_reason="",
        role_status="strong" if accepted else "missing",
        satisfying_refs=tuple(candidate.source_id for candidate in accepted),
        snippet_assessment=tuple({"ref": candidate.source_id, "role": "core", "reason": "accepted"} for candidate in accepted),
        satisfaction_source="test",
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
    snippet_assessment: list[dict[str, str]] | None = None,
    follow_up_queries: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    refs = accepted_anchor_refs or []
    return {
        "acceptance_satisfied": bool(refs),
        "stop_reason": "validated_role_buckets",
        "missing_areas": missing_areas or [],
        "accepted_anchor_refs": refs,
        "rejected_anchor_refs": rejected_anchor_refs or [],
        "snippet_assessment": snippet_assessment or [{"ref": ref, "role": "core", "reason": "validated implementation anchor"} for ref in refs],
        "follow_up_queries": follow_up_queries or [],
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
