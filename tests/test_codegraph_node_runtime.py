from __future__ import annotations

import unittest
from unittest.mock import patch

from services.retrieval.workspace.node_runtime import (
    CodeGraphNodeRuntime,
    _version_tuple,
    resolve_codegraph_node_runtime,
)


class CodeGraphNodeRuntimeTests(unittest.TestCase):
    def test_uses_later_compatible_runtime_when_path_node_is_too_old(self) -> None:
        candidates = (("C:/Program Files/nodejs/node.exe", "PATH"), ("C:/runtime/node.exe", "bundled Codex runtime"))
        with patch(
            "services.retrieval.workspace.node_runtime._candidate_executables",
            return_value=iter(candidates),
        ), patch(
            "services.retrieval.workspace.node_runtime._probe_node",
            side_effect=((None, "Node 20.11.1 is below required 22.5"), ("24.19.0", "")),
        ):
            runtime = resolve_codegraph_node_runtime()

        self.assertEqual(
            runtime,
            CodeGraphNodeRuntime("C:/runtime/node.exe", "24.19.0", "bundled Codex runtime"),
        )

    def test_reports_all_rejected_candidates(self) -> None:
        with patch(
            "services.retrieval.workspace.node_runtime._candidate_executables",
            return_value=iter((("node", "PATH"),)),
        ), patch(
            "services.retrieval.workspace.node_runtime._probe_node",
            return_value=(None, "Node 20.11.1 is below required 22.5"),
        ):
            with self.assertRaisesRegex(RuntimeError, "Node 20.11.1"):
                resolve_codegraph_node_runtime()

    def test_version_parser_requires_major_and_minor(self) -> None:
        self.assertEqual((24, 19), _version_tuple("24.19.0"))
        self.assertIsNone(_version_tuple("24"))
        self.assertIsNone(_version_tuple("not-a-version"))


if __name__ == "__main__":
    unittest.main()
