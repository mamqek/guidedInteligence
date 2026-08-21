from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from services.retrieval.workspace.source_ast.python_adapter import PYTHON_EXTENSIONS
from services.retrieval.workspace.source_ast.python_adapter import source_owner_calls as python_source_owner_calls


TYPESCRIPT_EXTENSIONS = frozenset({".ts", ".tsx", ".js", ".jsx", ".mts", ".cts", ".mjs", ".cjs"})


class SourceAstRouter:
    """Language-neutral entry point for source-level structural operations."""

    def __init__(self, workspace_root: str | Path, *, codegraph_bridge: Any) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.codegraph_bridge = codegraph_bridge

    def source_owner_calls(self, source_node: Mapping[str, Any]) -> dict[str, Any]:
        extension = Path(str(source_node.get("path") or "")).suffix.casefold()
        if extension in PYTHON_EXTENSIONS:
            return python_source_owner_calls(self.workspace_root, source_node)
        if extension in TYPESCRIPT_EXTENSIONS:
            return dict(
                self.codegraph_bridge.request(
                    "source_owner_calls",
                    {"node_id": str(source_node.get("id") or "")},
                )
            )
        return {
            "status": "unsupported",
            "reason": "no_source_ast_adapter",
            "adapter": "unsupported",
            "source_node_id": str(source_node.get("id") or ""),
            "source_path": str(source_node.get("path") or ""),
            "calls": [],
        }
