from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from services.retrieval.config import (
    RetrievalEmbeddingConfig,
    RetrievalQdrantConfig,
    RunLLMConfig,
    WorkspaceRetrievalConfig,
)
from services.retrieval.workspace.tools.codegraph import close_codegraph_bridge, codegraph_tools
from services.retrieval.workspace.tools.contracts import ToolRequest


class CodeGraphToolsIntegrationTests(unittest.TestCase):
    def test_index_exact_symbol_calls_and_file_relationships(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "src").mkdir()
            (root / "src" / "a.ts").write_text(
                "export function target() { return 1; }\n"
                "export function caller() { return target(); }\n",
                encoding="utf-8",
            )
            (root / "src" / "b.ts").write_text(
                "import { caller } from './a';\nexport const value = caller();\n",
                encoding="utf-8",
            )
            config = _config(root)
            tools, _bridge = codegraph_tools(config)
            try:
                indexed = tools["structural_index_repo"].run(_request("structural_index_repo"))
                exact = tools["structural_find_exact_symbol"].run(
                    _request("structural_find_exact_symbol", query="target")
                )
                conceptual = tools["structural_find_exact_symbol"].run(
                    _request("structural_find_exact_symbol", query="target behavior")
                )
                callers = tools["structural_callers"].run(
                    _request("structural_callers", file="src/a.ts", line=1)
                )
                relation = tools["structural_relationship"].run(
                    _request("structural_relationship", source_path="src/b.ts", target_path="src/a.ts")
                )
            finally:
                close_codegraph_bridge(config)

            self.assertEqual(indexed.status, "ok")
            self.assertFalse((root / "codegraph.json").exists())
            self.assertEqual(exact.source_refs, ("src/a.ts",))
            self.assertEqual(conceptual.source_refs, ())
            self.assertIn("src/a.ts", callers.source_refs)
            self.assertTrue(relation.payload["related"])
            self.assertTrue(
                any(edge["edge_kind"] in {"calls", "imports"} for edge in relation.payload["edges"])
            )


def _config(root: Path) -> WorkspaceRetrievalConfig:
    return WorkspaceRetrievalConfig(
        workspace_root=str(root),
        index_dir=str(root / ".guided-intelligence" / "index"),
        llm_config=RunLLMConfig(model="test", endpoint_url="http://unused", api_key="test"),
        embedding_config=RetrievalEmbeddingConfig(model="test", endpoint_url="http://unused", api_key="test"),
        qdrant_config=RetrievalQdrantConfig(url="http://unused", collection_name="test"),
        index_exclude_paths=(".guided-intelligence",),
    )


def _request(tool_name: str, **arguments: object) -> ToolRequest:
    return ToolRequest(tool_name=tool_name, arguments=arguments)


if __name__ == "__main__":
    unittest.main()
