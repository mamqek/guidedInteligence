from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from services.retrieval.server import _index_time_estimate
from services.retrieval.config import RetrievalEmbeddingConfig, RetrievalQdrantConfig
from services.retrieval.workspace import bm25
from services.retrieval.workspace.qdrant_backend import QdrantHybridBackend
from services.retrieval.workspace.pipeline.execution_flow import index_setup


class BM25IndexingTests(unittest.TestCase):
    def test_test_directory_role_handles_camel_case_and_conventional_names(self) -> None:
        self.assertEqual(bm25.file_role("src/testRunner/unittests/tsbuild/watchMode.ts"), "test")
        self.assertEqual(bm25.file_role("src/unitTests/watchMode.ts"), "test")
        self.assertEqual(bm25.file_role("src/test-cases/watchMode.ts"), "test")
        self.assertEqual(bm25.file_role("src/compiler/nodeTests.ts"), "implementation")

    def test_code_in_nonstandard_source_directory_is_implementation(self) -> None:
        self.assertEqual(bm25.file_role("services/intent/classifier.py"), "implementation")
        self.assertEqual(bm25.file_role("custom-layout/engine.ts"), "implementation")

    def test_built_bundle_names_are_generated_artifacts(self) -> None:
        self.assertEqual(bm25.file_role("packages/renderer/build.dev.js"), "baseline_or_generated")
        self.assertEqual(bm25.file_role("packages/renderer/build.prod.js"), "baseline_or_generated")
        self.assertEqual(bm25.file_role("dist/runtime.js"), "baseline_or_generated")
        self.assertEqual(bm25.file_role("src/compiler/builder.ts"), "implementation")

    def test_generated_artifacts_are_not_semantically_indexed(self) -> None:
        with TemporaryDirectory() as root:
            workspace = Path(root)
            source = workspace / "src" / "renderer.js"
            bundle = workspace / "packages" / "renderer" / "build.dev.js"
            source.parent.mkdir(parents=True)
            bundle.parent.mkdir(parents=True)
            source.write_text("export function renderNode () {}\n", encoding="utf-8")
            bundle.write_text("function renderNode () {}\n", encoding="utf-8")

            estimate = bm25.estimate_indexing_scope(workspace)
            index = bm25.build_index_from_repo(repo_path=workspace, commit="test")

        self.assertEqual(estimate["file_count"], 1)
        self.assertEqual({document.chunk.path for document in index.documents}, {"src/renderer.js"})

    def test_oversized_files_are_excluded_from_index_and_estimate(self) -> None:
        with TemporaryDirectory() as root:
            workspace = Path(root)
            (workspace / "small.py").write_text("def owner():\n    return 1\n", encoding="utf-8")
            (workspace / "large-source.js").write_text("x" * 101, encoding="utf-8")

            with patch.object(bm25, "MAX_INDEXED_FILE_CHARACTERS", 100):
                estimate = bm25.estimate_indexing_scope(workspace)
                index = bm25.build_index_from_repo(repo_path=workspace, commit="test")

            self.assertEqual(estimate["file_count"], 1)
            self.assertEqual(estimate["oversized_file_count"], 1)
            self.assertEqual(estimate["oversized_sample_paths"], ["large-source.js"])
            self.assertEqual({document.chunk.path for document in index.documents}, {"small.py"})

    def test_large_estimate_emits_interactive_scope_warning(self) -> None:
        estimate = _index_time_estimate(
            {
                "file_count": 10_000,
                "estimated_chunks": 100_000,
                "oversized_file_count": 3,
            }
        )

        self.assertTrue(any("15 minutes" in note for note in estimate["index_estimate_notes"]))
        self.assertTrue(any("per-file character limit" in note for note in estimate["index_estimate_notes"]))

    def test_qdrant_signature_changes_when_file_role_metadata_changes(self) -> None:
        with TemporaryDirectory() as root:
            workspace = Path(root)
            source = workspace / "src" / "testRunner" / "case.ts"
            source.parent.mkdir(parents=True)
            source.write_text("export const value = 1\n", encoding="utf-8")
            index = bm25.build_index_from_repo(repo_path=workspace, commit="test")
            original_document = index.documents[0]
            changed_chunk = replace(
                original_document.chunk,
                metadata={**original_document.chunk.metadata, "file_role": "implementation"},
            )
            changed_index = replace(index, documents=(replace(original_document, chunk=changed_chunk),))

            original_signature = QdrantHybridBackend(
                index=index,
                qdrant_config=RetrievalQdrantConfig(),
                embedding_config=RetrievalEmbeddingConfig(),
            ).index_signature()
            changed_signature = QdrantHybridBackend(
                index=changed_index,
                qdrant_config=RetrievalQdrantConfig(),
                embedding_config=RetrievalEmbeddingConfig(),
            ).index_signature()

        self.assertNotEqual(original_signature, changed_signature)

    def test_bm25_scope_signature_tracks_indexing_schema_version(self) -> None:
        ctx = SimpleNamespace(
            config=SimpleNamespace(
                workspace_root="C:/repo",
                index_exclude_paths=("build",),
                chunk_line_count=40,
                chunk_line_overlap=10,
            )
        )

        signature = index_setup._index_scope_signature(ctx)

        self.assertEqual(signature["index_schema_version"], bm25.BM25_INDEX_SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
