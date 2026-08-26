from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path

from services.retrieval.config import (
    RetrievalEmbeddingConfig,
    RetrievalQdrantConfig,
    RunLLMConfig,
    WorkspaceRetrievalConfig,
)
from services.retrieval.workspace.tools.codegraph import (
    CodeGraphResolveRangesTool,
    close_codegraph_bridge,
    codegraph_tools,
)
from services.retrieval.workspace.tools.contracts import ToolRequest


class _ConcurrentRangeBridge:
    active = 0
    max_active = 0
    lock = threading.Lock()

    def __init__(self, config: object = None) -> None:
        self.config = config or object()

    def request(self, operation: str, arguments: object = None) -> dict[str, object]:
        if operation == "resolve_source_owners":
            return {"status": "ok", "owners": []}
        self.assert_operation(operation)
        ranges = list((arguments or {}).get("ranges", ()))  # type: ignore[union-attr]
        with self.lock:
            type(self).active += 1
            type(self).max_active = max(type(self).max_active, type(self).active)
        time.sleep(0.02)
        with self.lock:
            type(self).active -= 1
        return {"results": [{**item, "nodes": []} for item in ranges]}

    def close(self) -> None:
        return None

    @staticmethod
    def assert_operation(operation: str) -> None:
        if operation != "resolve_ranges":
            raise AssertionError(operation)


class CodeGraphRangeBatchTests(unittest.TestCase):
    def test_resolves_every_range_in_parallel_batches_and_preserves_order(self) -> None:
        _ConcurrentRangeBridge.active = 0
        _ConcurrentRangeBridge.max_active = 0
        bridge = _ConcurrentRangeBridge()
        tool = CodeGraphResolveRangesTool(bridge, bridge_factory=_ConcurrentRangeBridge)
        ranges = [
            {"file": f"src/{index}.ts", "line_start": index + 1, "line_end": index + 2}
            for index in range(172)
        ]

        result = tool.run(_request("structural_resolve_ranges", ranges=ranges))

        self.assertEqual(result.status, "ok", result.payload)
        self.assertEqual([item["file"] for item in result.payload["results"]], [item["file"] for item in ranges])
        self.assertEqual(result.payload["batch_diagnostics"]["batch_range_counts"], [80, 80, 12])
        self.assertEqual(result.payload["batch_diagnostics"]["processed_range_count"], 172)
        self.assertTrue(result.payload["batch_diagnostics"]["complete"])
        self.assertGreater(_ConcurrentRangeBridge.max_active, 1)


class CodeGraphToolsIntegrationTests(unittest.TestCase):
    def test_index_exact_symbol_calls_and_file_relationships(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "src").mkdir()
            (root / "src" / "a.ts").write_text(
                "export function target() { return 1; }\n"
                "export function ModuleResolutionEngine() { return target(); }\n"
                "export function caller() { return target(); }\n"
                "export function verifyTscWatch() { return target(); }\n",
                encoding="utf-8",
            )
            (root / "src" / "b.ts").write_text(
                "import { caller, verifyTscWatch } from './a';\n"
                "export const value = caller();\n"
                "export const watched = verifyTscWatch();\n",
                encoding="utf-8",
            )
            (root / "src" / "nested.ts").write_text(
                "export function nestedTarget() { return 1; }\n"
                "export function outerOwner() {\n"
                "  const callback = () => nestedTarget();\n"
                "  return callback();\n"
                "}\n"
                "describe('anonymous-only', () => { nestedTarget(); });\n",
                encoding="utf-8",
            )
            (root / "src" / "builderState.ts").write_text(
                "export function affectedLeaf() { return []; }\n"
                "export function otherLeaf() { return []; }\n"
                "export function getFilesAffectedBy(flag = false) { return (flag ? otherLeaf : affectedLeaf)(); }\n"
                "export function create() { return {}; }\n",
                encoding="utf-8",
            )
            (root / "src" / "builder.ts").write_text(
                "import * as BuilderState from './builderState';\n"
                "export function getNextAffectedFile() { return BuilderState.getFilesAffectedBy(); }\n"
                "export const state = BuilderState.create();\n",
                encoding="utf-8",
            )
            (root / "src" / "project.ts").write_text(
                "import * as BuilderState from './builderState';\n"
                "export const affected = BuilderState.getFilesAffectedBy();\n",
                encoding="utf-8",
            )
            (root / "src" / "py_state.py").write_text(
                "def affected_leaf():\n"
                "    return []\n\n"
                "def other_leaf():\n"
                "    return []\n\n"
                "def get_files_affected_by(flag=False):\n"
                "    return (other_leaf if flag else affected_leaf)()\n",
                encoding="utf-8",
            )
            (root / "src" / "py_builder.py").write_text(
                "import py_state\n\n"
                "def get_next_affected_file():\n"
                "    return py_state.get_files_affected_by()\n",
                encoding="utf-8",
            )
            config = _config(root)
            tools, _bridge = codegraph_tools(config)
            try:
                indexed = tools["structural_index_repo"].run(_request("structural_index_repo"))
                self.assertEqual(indexed.status, "ok", indexed.payload)
                exact = tools["structural_find_exact_symbol"].run(
                    _request("structural_find_exact_symbol", query="target")
                )
                conceptual = tools["structural_find_exact_symbol"].run(
                    _request("structural_find_exact_symbol", query="target behavior")
                )
                callers = tools["structural_callers"].run(
                    _request("structural_callers", file="src/a.ts", line=1)
                )
                nested_exact = tools["structural_find_exact_symbol"].run(
                    _request("structural_find_exact_symbol", query="nestedTarget")
                )
                self.assertEqual(nested_exact.status, "ok", nested_exact.payload)
                self.assertTrue(nested_exact.payload.get("nodes"), nested_exact.payload)
                expanded_nested = tools["structural_expand_nodes"].run(
                    _request(
                        "structural_expand_nodes",
                        node_ids=[nested_exact.payload["nodes"][0]["id"]],
                        depth=1,
                        limit=100,
                    )
                )
                ranges = tools["structural_resolve_ranges"].run(
                    _request(
                        "structural_resolve_ranges",
                        ranges=[{"file": "src/a.ts", "line_start": 1, "line_end": 2}],
                    )
                )
                neighbors = tools["structural_file_neighbors"].run(
                    _request("structural_file_neighbors", paths=["src/b.ts"], limit=10)
                )
                relation = tools["structural_relationship"].run(
                    _request("structural_relationship", source_path="src/b.ts", target_path="src/a.ts")
                )
                qualified = tools["structural_qualified_references"].run(
                    _request(
                        "structural_qualified_references",
                        paths=["src/builder.ts", "src/project.ts"],
                    )
                )
                caller_exact = tools["structural_find_exact_symbol"].run(
                    _request("structural_find_exact_symbol", query="caller")
                )
                target_id = exact.payload["nodes"][0]["id"]
                caller_id = caller_exact.payload["nodes"][0]["id"]
                outline = tools["structural_file_outline"].run(
                    _request("structural_file_outline", path="src/a.ts", max_entries=20)
                )
                file_nodes = tools["structural_resolve_file_nodes"].run(
                    _request("structural_resolve_file_nodes", paths=["src/a.ts", "src/b.ts"])
                )
                b_file_id = next(node["id"] for node in file_nodes.payload["nodes"] if node["path"] == "src/b.ts")
                file_capabilities = tools["structural_edge_capabilities"].run(
                    _request("structural_edge_capabilities", node_ids=[b_file_id])
                )
                file_calls = tools["structural_expand_relationships"].run(
                    _request(
                        "structural_expand_relationships",
                        node_ids=[b_file_id],
                        direction="outgoing",
                        edge_kinds=["calls"],
                        target_symbols=["caller"],
                        cross_file_only=True,
                        limit=3,
                    )
                )
                ranked_file_calls = tools["structural_expand_relationships"].run(
                    _request(
                        "structural_expand_relationships",
                        node_ids=[b_file_id],
                        direction="outgoing",
                        edge_kinds=["calls"],
                        target_symbols=["notPresent"],
                        target_terms=["watch mode"],
                        cross_file_only=True,
                        limit=1,
                    )
                )
                closed = tools["structural_relationships_within_nodes"].run(
                    _request(
                        "structural_relationships_within_nodes",
                        node_ids=[target_id, caller_id],
                        edge_kinds=["calls"],
                    )
                )
                next_affected = tools["structural_find_exact_symbol"].run(
                    _request("structural_find_exact_symbol", query="getNextAffectedFile")
                )
                affected_leaf = tools["structural_find_exact_symbol"].run(
                    _request("structural_find_exact_symbol", query="affectedLeaf")
                )
                connector_closed = tools["structural_relationships_within_nodes"].run(
                    _request(
                        "structural_relationships_within_nodes",
                        node_ids=[
                            next_affected.payload["nodes"][0]["id"],
                            affected_leaf.payload["nodes"][0]["id"],
                        ],
                        connector_edge_kinds=["calls"],
                    )
                )
                next_affected_calls = tools["structural_source_owner_calls"].run(
                    _request(
                        "structural_source_owner_calls",
                        node=next_affected.payload["nodes"][0],
                    )
                )
                files_affected = tools["structural_find_exact_symbol"].run(
                    _request("structural_find_exact_symbol", query="getFilesAffectedBy")
                )
                files_affected_calls = tools["structural_source_owner_calls"].run(
                    _request(
                        "structural_source_owner_calls",
                        node=files_affected.payload["nodes"][0],
                    )
                )
                py_next = tools["structural_find_exact_symbol"].run(
                    _request("structural_find_exact_symbol", query="get_next_affected_file")
                )
                py_files = tools["structural_find_exact_symbol"].run(
                    _request("structural_find_exact_symbol", query="get_files_affected_by")
                )
                py_next_calls = tools["structural_source_owner_calls"].run(
                    _request("structural_source_owner_calls", node=py_next.payload["nodes"][0])
                )
                py_files_calls = tools["structural_source_owner_calls"].run(
                    _request("structural_source_owner_calls", node=py_files.payload["nodes"][0])
                )
                capabilities = tools["structural_edge_capabilities"].run(
                    _request("structural_edge_capabilities", node_ids=[target_id])
                )
                incoming = tools["structural_expand_relationships"].run(
                    _request(
                        "structural_expand_relationships",
                        node_ids=[target_id],
                        direction="incoming",
                        edge_kinds=["calls"],
                        limit=3,
                    )
                )
            finally:
                close_codegraph_bridge(config)

            self.assertEqual(indexed.status, "ok")
            self.assertFalse((root / "codegraph.json").exists())
            self.assertEqual(exact.source_refs, ("src/a.ts",))
            self.assertEqual(exact.payload["match_count"], 1)
            self.assertEqual(connector_closed.payload["connector_paths"], [])
            self.assertEqual(next_affected_calls.status, "ok")
            self.assertEqual(next_affected_calls.payload["adapter"], "typescript_compiler_api")
            self.assertIn(
                ("getFilesAffectedBy", "BuilderState"),
                {
                    (call["name"], call["qualifier"])
                    for call in next_affected_calls.payload["calls"]
                },
            )
            self.assertEqual(files_affected_calls.status, "ok")
            self.assertIn(
                "affectedLeaf",
                {call["name"] for call in files_affected_calls.payload["calls"]},
            )
            self.assertEqual(py_next_calls.payload["adapter"], "python_stdlib_ast")
            self.assertIn(
                ("get_files_affected_by", "py_state"),
                {(call["name"], call["qualifier"]) for call in py_next_calls.payload["calls"]},
            )
            self.assertEqual(
                {call["name"] for call in py_files_calls.payload["calls"]},
                {"affected_leaf", "other_leaf"},
            )
            localizations = [
                edge["file_call_localization"]
                for edge in expanded_nested.payload["edges"]
                if edge.get("file_call_localization")
                and edge["file_call_localization"].get("target_symbol") == "nestedTarget"
            ]
            self.assertEqual(len(localizations), 1)
            self.assertEqual(localizations[0]["status"], "localized")
            self.assertEqual(localizations[0]["selected"]["owner"]["qualified_name"], "outerOwner")
            self.assertIn(
                "rejected_no_named_outer_executable",
                {item["decision_code"] for item in localizations[0]["considered"]},
            )
            self.assertEqual(conceptual.source_refs, ())
            self.assertIn("src/a.ts", callers.source_refs)
            self.assertEqual(ranges.status, "ok")
            self.assertEqual(
                {node["name"] for node in ranges.payload["results"][0]["nodes"]},
                {"target", "ModuleResolutionEngine"},
            )
            self.assertIn("src/a.ts", neighbors.source_refs)
            self.assertTrue(relation.payload["related"])
            self.assertTrue(
                any(edge["edge_kind"] in {"calls", "imports"} for edge in relation.payload["edges"])
            )
            affected = next(
                node for node in qualified.payload["nodes"] if node["name"] == "getFilesAffectedBy"
            )
            self.assertEqual(affected["path"], "src/builderState.ts")
            self.assertEqual(affected["qualifier"], "BuilderState")
            self.assertEqual(affected["source_count"], 2)
            self.assertEqual(
                affected["source_paths"],
                ["src/builder.ts", "src/project.ts"],
            )
            self.assertEqual(outline.status, "ok")
            self.assertIn("caller", {node["name"] for node in outline.payload["nodes"]})
            self.assertTrue(all(node["kind"] == "file" for node in file_nodes.payload["nodes"]))
            self.assertTrue(
                any(item["kind"] == "calls" for item in file_capabilities.payload["nodes"][0]["outgoing"])
            )
            self.assertIn("caller", {node["name"] for node in file_calls.payload["nodes"]})
            self.assertEqual([node["name"] for node in ranked_file_calls.payload["nodes"]], ["verifyTscWatch"])
            self.assertTrue(all(edge["kind"] == "calls" for edge in closed.payload["edges"]))
            self.assertTrue(
                any(item["kind"] == "calls" for item in capabilities.payload["nodes"][0]["incoming"])
            )
            self.assertEqual(incoming.payload["direction"], "incoming")
            self.assertTrue(incoming.payload["nodes"])
            self.assertTrue(all(edge["kind"] == "calls" for edge in incoming.payload["edges"]))


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
