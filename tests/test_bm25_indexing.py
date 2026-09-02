from dataclasses import replace
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import threading
import unittest
import urllib.error
from unittest.mock import patch

from services.retrieval.server import _index_time_estimate
from services.retrieval.config import RetrievalEmbeddingConfig, RetrievalQdrantConfig
from services.retrieval.workspace import bm25
from services.retrieval.workspace.qdrant_backend import (
    QdrantHybridBackend,
    _EmbeddingTokenRateGate,
    _estimated_embedding_tokens,
    _rate_limit_reset_seconds,
    _rate_limit_retry_delay,
)
from testing.codeRepoQA.run_case import (
    CODEREPOQA_GENERATED_PATHS_BY_REPOSITORY,
    _workspace_index_dir,
)
from services.retrieval.workspace.pipeline.execution_flow import index_setup
from services.retrieval.workspace.pipeline.execution_flow.index_setup import _scope_manifest_matches


class BM25IndexingTests(unittest.TestCase):
    def test_embedding_rate_gate_reserves_for_other_in_flight_workers(self) -> None:
        gate = _EmbeddingTokenRateGate()
        first = gate.acquire(100)
        gate.complete(
            first,
            {
                "x-ratelimit-remaining-tokens": "1000",
                "x-ratelimit-reset-tokens": "1s",
            },
        )

        first_parallel = gate.acquire(300)
        second_parallel = gate.acquire(300)
        gate.complete(
            first_parallel,
            {
                "x-ratelimit-remaining-tokens": "700",
                "x-ratelimit-reset-tokens": "1s",
            },
        )

        self.assertEqual(first_parallel, 300)
        self.assertEqual(second_parallel, 300)
        self.assertEqual(gate._remaining_tokens, 400)

    def test_embedding_token_estimate_has_safety_margin(self) -> None:
        self.assertEqual(_estimated_embedding_tokens(["a" * 400, "b" * 400]), 230)

    def test_rate_limit_reset_header_supports_compound_durations(self) -> None:
        self.assertAlmostEqual(_rate_limit_reset_seconds("1m2.5s"), 62.5)

    def test_embedding_rate_limit_delay_uses_provider_retry_hint(self) -> None:
        error = urllib.error.HTTPError(
            "https://api.openai.com/v1/embeddings",
            429,
            "rate limited",
            {},
            BytesIO(b""),
        )

        seconds = _rate_limit_retry_delay(error, "Please try again in 449ms.", fallback=8.0)

        self.assertAlmostEqual(seconds, 0.699)

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

    def test_indexable_content_signature_changes_only_for_indexed_content(self) -> None:
        with TemporaryDirectory() as root:
            workspace = Path(root)
            source = workspace / "src" / "owner.py"
            ignored = workspace / "node_modules" / "ignored.js"
            source.parent.mkdir(parents=True)
            ignored.parent.mkdir(parents=True)
            source.write_text("def owner():\n    return 1\n", encoding="utf-8")
            ignored.write_text("first", encoding="utf-8")

            original = bm25.indexable_content_signature(workspace)
            ignored.write_text("second", encoding="utf-8")
            after_ignored_change = bm25.indexable_content_signature(workspace)
            source.write_text("def owner():\n    return 2\n", encoding="utf-8")
            after_source_change = bm25.indexable_content_signature(workspace)

        self.assertEqual(original, after_ignored_change)
        self.assertNotEqual(original, after_source_change)

    def test_qdrant_signature_changes_when_embedding_model_changes(self) -> None:
        with TemporaryDirectory() as root:
            workspace = Path(root)
            (workspace / "owner.py").write_text("def owner():\n    return 1\n", encoding="utf-8")
            index = bm25.build_index_from_repo(repo_path=workspace, commit="test")

            first = QdrantHybridBackend(
                index=index,
                qdrant_config=RetrievalQdrantConfig(),
                embedding_config=RetrievalEmbeddingConfig(model="embedding-a"),
            ).index_signature()
            second = QdrantHybridBackend(
                index=index,
                qdrant_config=RetrievalQdrantConfig(),
                embedding_config=RetrievalEmbeddingConfig(model="embedding-b"),
            ).index_signature()

        self.assertNotEqual(first, second)

    def test_repeated_document_embedding_uses_persistent_cache(self) -> None:
        with TemporaryDirectory() as root:
            workspace = Path(root)
            source = workspace / "owner.py"
            source.write_text("def owner():\n    return 1\n", encoding="utf-8")
            index = bm25.build_index_from_repo(repo_path=workspace, commit="test")
            cache_path = workspace / "embedding-cache.json"
            config = RetrievalEmbeddingConfig(model="embedding-test", batch_size=32)
            first_backend = QdrantHybridBackend(
                index=index,
                qdrant_config=RetrievalQdrantConfig(),
                embedding_config=config,
                cache_path=cache_path,
            )

            with patch.object(first_backend, "_embedding_request", return_value=[[0.1, 0.2]]) as first_request:
                first_vectors = first_backend._embed_documents([index.documents[0].chunk])

            second_backend = QdrantHybridBackend(
                index=index,
                qdrant_config=RetrievalQdrantConfig(),
                embedding_config=config,
                cache_path=cache_path,
            )
            with patch.object(second_backend, "_embedding_request", side_effect=AssertionError("document was re-embedded")) as second_request:
                second_vectors = second_backend._embed_documents([index.documents[0].chunk])

        self.assertEqual(first_vectors, second_vectors)
        first_request.assert_called_once()
        second_request.assert_not_called()

    def test_repeated_document_embedding_uses_incremental_sqlite_cache(self) -> None:
        with TemporaryDirectory() as root:
            workspace = Path(root)
            source = workspace / "owner.py"
            source.write_text("def owner():\n    return 1\n", encoding="utf-8")
            index = bm25.build_index_from_repo(repo_path=workspace, commit="test")
            cache_path = workspace / "embedding-cache.sqlite3"
            config = RetrievalEmbeddingConfig(model="embedding-test", batch_size=32)
            first_backend = QdrantHybridBackend(
                index=index,
                qdrant_config=RetrievalQdrantConfig(),
                embedding_config=config,
                cache_path=cache_path,
            )

            with patch.object(first_backend, "_embedding_request", return_value=[[0.1, 0.2]]) as first_request:
                first_vectors = first_backend._embed_documents([index.documents[0].chunk])

            second_backend = QdrantHybridBackend(
                index=index,
                qdrant_config=RetrievalQdrantConfig(),
                embedding_config=config,
                cache_path=cache_path,
            )
            with patch.object(
                second_backend,
                "_embedding_request",
                side_effect=AssertionError("document was re-embedded"),
            ) as second_request:
                second_vectors = second_backend._embed_documents([index.documents[0].chunk])

        self.assertAlmostEqual(first_vectors[0][0][0], second_vectors[0][0][0], places=6)
        self.assertAlmostEqual(first_vectors[0][0][1], second_vectors[0][0][1], places=6)
        first_request.assert_called_once()
        second_request.assert_not_called()

    def test_embedding_cache_replacement_preserves_previous_file_on_write_failure(self) -> None:
        with TemporaryDirectory() as root:
            workspace = Path(root)
            (workspace / "owner.py").write_text("def owner():\n    return 1\n", encoding="utf-8")
            index = bm25.build_index_from_repo(repo_path=workspace, commit="test")
            cache_path = workspace / "embedding-cache.json"
            original_payload = '{"model":"embedding-test","entries":{"existing":[0.1]}}'
            cache_path.write_text(original_payload, encoding="utf-8")
            backend = QdrantHybridBackend(
                index=index,
                qdrant_config=RetrievalQdrantConfig(),
                embedding_config=RetrievalEmbeddingConfig(model="embedding-test"),
                cache_path=cache_path,
            )
            backend._embedding_cache["new"] = [0.2]
            original_write_text = Path.write_text

            def fail_temporary_write(path: Path, data: str, *args: object, **kwargs: object) -> int:
                original_write_text(path, "{partial", encoding="utf-8")
                raise OSError("expected cache write failure")

            with patch.object(Path, "write_text", autospec=True, side_effect=fail_temporary_write):
                with self.assertRaisesRegex(OSError, "expected cache write failure"):
                    backend._save_embedding_cache()

            self.assertEqual(cache_path.read_text(encoding="utf-8"), original_payload)
            self.assertEqual(list(workspace.glob("*.tmp")), [])

    def test_qdrant_upload_receives_a_fresh_timeout_window(self) -> None:
        with TemporaryDirectory() as root:
            workspace = Path(root)
            (workspace / "owner.py").write_text("def owner():\n    return 1\n", encoding="utf-8")
            index = bm25.build_index_from_repo(repo_path=workspace, commit="test")
            backend = QdrantHybridBackend(
                index=index,
                qdrant_config=RetrievalQdrantConfig(),
                embedding_config=RetrievalEmbeddingConfig(model="embedding-test", batch_size=32),
            )

            with patch.object(backend, "ensure_available"), patch.object(
                backend,
                "_embed_documents",
                return_value=[[[0.1, 0.2]]],
            ), patch.object(backend, "_request", return_value={}), patch(
                "services.retrieval.workspace.qdrant_backend.time.monotonic",
                side_effect=(0.0, 9.0, 9.0, 11.0),
            ):
                indexed = backend.rebuild_collection(timeout_seconds=10)

        self.assertEqual(indexed, 1)

    def test_qdrant_rebuild_streams_embedding_batches(self) -> None:
        with TemporaryDirectory() as root:
            workspace = Path(root)
            for index in range(3):
                (workspace / f"owner{index}.py").write_text(f"def owner{index}():\n    return {index}\n", encoding="utf-8")
            repository_index = bm25.build_index_from_repo(repo_path=workspace, commit="test")
            backend = QdrantHybridBackend(
                index=repository_index,
                qdrant_config=RetrievalQdrantConfig(),
                embedding_config=RetrievalEmbeddingConfig(model="embedding-test", batch_size=1),
            )

            with patch.object(backend, "ensure_available"), patch.object(
                backend,
                "_embed_documents",
                return_value=[[[0.1, 0.2]]],
            ) as embed, patch.object(backend, "_request", return_value={}):
                indexed = backend.rebuild_collection()

        self.assertEqual(indexed, 3)
        self.assertEqual(embed.call_count, 3)
        self.assertTrue(all(len(call.args[0]) == 1 for call in embed.call_args_list))

    def test_successful_parallel_embedding_is_cached_when_peer_batch_fails(self) -> None:
        with TemporaryDirectory() as root:
            workspace = Path(root)
            (workspace / "good.py").write_text("def good():\n    return 1\n", encoding="utf-8")
            (workspace / "fail.py").write_text("def fail():\n    return 2\n", encoding="utf-8")
            index = bm25.build_index_from_repo(repo_path=workspace, commit="test")
            cache_path = workspace / "embedding-cache.json"
            config = RetrievalEmbeddingConfig(model="embedding-test", batch_size=1, concurrency=2)
            backend = QdrantHybridBackend(
                index=index,
                qdrant_config=RetrievalQdrantConfig(),
                embedding_config=config,
                cache_path=cache_path,
            )
            barrier = threading.Barrier(2)

            def embedding_request(values: list[str]) -> list[list[float]]:
                barrier.wait(timeout=1)
                if "fail.py" in values[0]:
                    raise RuntimeError("expected embedding failure")
                return [[0.1, 0.2]]

            with patch.object(backend, "_embedding_request", side_effect=embedding_request):
                with self.assertRaisesRegex(RuntimeError, "expected embedding failure"):
                    backend._embed_documents([document.chunk for document in index.documents])

            cached_entries = json.loads(cache_path.read_text(encoding="utf-8"))["entries"]

        self.assertEqual(len(cached_entries), 1)

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

    def test_flat_bm25_scope_manifest_migrates_without_reindexing(self) -> None:
        expected = {
            "index_schema_version": bm25.BM25_INDEX_SCHEMA_VERSION,
            "lexical_ranking": "bm25",
            "workspace_root": "C:/repo",
        }
        legacy = {
            "index_schema_version": bm25.BM25_INDEX_SCHEMA_VERSION,
            "lexical_ranking_profile": "flat_bm25",
            "workspace_root": "C:/repo",
        }

        self.assertTrue(_scope_manifest_matches(legacy, expected))

    def test_workspace_uses_one_canonical_index_directory(self) -> None:
        workspace = Path("C:/repo")
        self.assertEqual(_workspace_index_dir(workspace), workspace / ".guided-intelligence" / "index")

    def test_typescript_lib_directory_is_explicitly_excluded(self) -> None:
        exclusions = CODEREPOQA_GENERATED_PATHS_BY_REPOSITORY[("microsoft", "typescript")]
        self.assertIn("lib", exclusions)

if __name__ == "__main__":
    unittest.main()
