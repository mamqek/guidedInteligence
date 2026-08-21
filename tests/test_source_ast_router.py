from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from services.retrieval.workspace.source_ast import SourceAstRouter


class SourceAstRouterTests(unittest.TestCase):
    def test_python_owner_calls_use_python_adapter_and_skip_nested_owners(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "builder.py"
            source.write_text(
                "def left():\n"
                "    return []\n\n"
                "def right():\n"
                "    return []\n\n"
                "def get_files(flag=False):\n"
                "    helper = lambda: ignored()\n"
                "    def nested():\n"
                "        nested_only()\n"
                "    return (left if flag else right)()\n",
                encoding="utf-8",
            )
            router = SourceAstRouter(root, codegraph_bridge=_FailBridge())

            result = router.source_owner_calls(
                {
                    "id": "function:get_files",
                    "path": "builder.py",
                    "name": "get_files",
                    "line_start": 7,
                    "line_end": 11,
                }
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["adapter"], "python_stdlib_ast")
        self.assertEqual({call["name"] for call in result["calls"]}, {"left", "right"})

    def test_typescript_owner_calls_are_routed_to_codegraph_adapter(self) -> None:
        bridge = _RecordingBridge(
            {
                "status": "ok",
                "adapter": "typescript_compiler_api",
                "calls": [{"name": "target", "qualifier": "Module"}],
            }
        )
        router = SourceAstRouter(Path.cwd(), codegraph_bridge=bridge)

        result = router.source_owner_calls(
            {"id": "function:caller", "path": "src/caller.ts", "name": "caller"}
        )

        self.assertEqual(result["adapter"], "typescript_compiler_api")
        self.assertEqual(
            bridge.requests,
            [("source_owner_calls", {"node_id": "function:caller"})],
        )

    def test_unsupported_language_has_normalized_result(self) -> None:
        result = SourceAstRouter(Path.cwd(), codegraph_bridge=_FailBridge()).source_owner_calls(
            {"id": "function:main", "path": "main.go", "name": "main"}
        )

        self.assertEqual(result["status"], "unsupported")
        self.assertEqual(result["calls"], [])


class _RecordingBridge:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.requests: list[tuple[str, dict[str, object]]] = []

    def request(self, operation: str, arguments: dict[str, object]) -> dict[str, object]:
        self.requests.append((operation, arguments))
        return self.response


class _FailBridge:
    def request(self, operation: str, arguments: dict[str, object]) -> dict[str, object]:
        raise AssertionError(f"Unexpected bridge request: {operation} {arguments}")


if __name__ == "__main__":
    unittest.main()
