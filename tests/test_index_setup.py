from __future__ import annotations

from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

from services.retrieval.workspace.pipeline.execution_flow import index_setup


class IndexSetupTests(unittest.TestCase):
    def test_rebuild_index_reports_reused_indexes(self) -> None:
        result = self._run_setup(bm25_rebuilt=False)

        self.assertFalse(result.rebuilt)
        self.assertEqual(result.index.documents, ("document",))

    def test_rebuild_index_reports_bm25_rebuild(self) -> None:
        result = self._run_setup(bm25_rebuilt=True)

        self.assertTrue(result.rebuilt)

    def test_rebuild_index_reports_qdrant_rebuild_explicitly(self) -> None:
        result, trace = self._run_setup_with_trace(bm25_rebuilt=False, qdrant_current=False)

        self.assertTrue(result.rebuilt)
        self.assertTrue(
            any(call.args[0] == "workspace_index_rebuilt" for call in trace.record.call_args_list)
        )

    def _run_setup(self, *, bm25_rebuilt: bool) -> index_setup.IndexSetupResult:
        result, _trace = self._run_setup_with_trace(bm25_rebuilt=bm25_rebuilt)
        return result

    def _run_setup_with_trace(
        self,
        *,
        bm25_rebuilt: bool,
        qdrant_current: bool = True,
    ) -> tuple[index_setup.IndexSetupResult, Mock]:
        with tempfile.TemporaryDirectory() as temp_dir:
            collection_name = "test_collection"
            config = SimpleNamespace(
                index_dir=temp_dir,
                workspace_root=temp_dir,
                index_exclude_paths=None,
                chunk_line_count=40,
                chunk_line_overlap=10,
                enable_indexing=True,
                qdrant_index_timeout_seconds=30,
                embedding_cache_path=None,
                qdrant_config=SimpleNamespace(collection_name=collection_name),
                embedding_config=SimpleNamespace(),
            )
            trace = Mock()
            ctx = SimpleNamespace(config=config, trace=trace)
            index = SimpleNamespace(documents=("document",))
            backend = Mock()
            backend.index_signature.return_value = "signature"
            backend.collection_exists.return_value = qdrant_current
            backend.point_count.return_value = 1
            backend.rebuild_collection.return_value = 1
            qdrant_tool = SimpleNamespace(backend=backend)
            manifests = (
                {},
                {"index_signature": "signature", "collection_name": collection_name},
            )

            with (
                patch.object(index_setup, "_load_sync_manifest", side_effect=manifests),
                patch.object(index_setup, "_reuse_or_build_bm25_index", return_value=(index, bm25_rebuilt)),
                patch.object(index_setup, "QdrantHybridSearchTool", return_value=qdrant_tool),
            ):
                return index_setup.rebuild_index(ctx), trace


if __name__ == "__main__":
    unittest.main()
