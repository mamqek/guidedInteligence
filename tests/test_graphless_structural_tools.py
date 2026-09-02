from __future__ import annotations

import unittest

from services.retrieval.workspace.tools.contracts import ToolRequest
from services.retrieval.workspace.tools.graphless import graphless_structural_tools


class GraphlessStructuralToolsTests(unittest.TestCase):
    def test_every_structural_operation_returns_explicit_empty_results(self) -> None:
        tools = graphless_structural_tools()

        self.assertIn("structural_resolve_ranges", tools)
        self.assertIn("structural_expand_relationships", tools)
        for name, tool in tools.items():
            observation = tool.run(ToolRequest(tool_name=name, arguments={}))
            self.assertEqual("ok", observation.status)
            self.assertEqual("disabled", observation.payload["provider"])
            self.assertEqual([], observation.payload["nodes"])
            self.assertEqual([], observation.payload["edges"])

