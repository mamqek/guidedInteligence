from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from services.retrieval.workspace.source_ast.python_adapter import PYTHON_EXTENSIONS
from services.retrieval.workspace.source_ast.python_adapter import owner_source_layouts as python_owner_source_layouts
from services.retrieval.workspace.source_ast.python_adapter import resolve_source_owners as python_resolve_source_owners
from services.retrieval.workspace.source_ast.python_adapter import source_owner_calls as python_source_owner_calls


TYPESCRIPT_EXTENSIONS = frozenset({".ts", ".tsx", ".js", ".jsx", ".mts", ".cts", ".mjs", ".cjs"})


class SourceAstRouter:
    """Language-neutral entry point for source-level structural operations."""

    def __init__(self, workspace_root: str | Path, *, codegraph_bridge: Any) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.codegraph_bridge = codegraph_bridge

    def owner_source_layouts(self, path: str) -> dict[str, Any]:
        resolved = (self.workspace_root / path).resolve()
        if not resolved.is_relative_to(self.workspace_root):
            raise ValueError("owner_source_outside_workspace")
        extension = resolved.suffix.casefold()
        if extension in PYTHON_EXTENSIONS:
            return python_owner_source_layouts(self.workspace_root, path)
        if extension in TYPESCRIPT_EXTENSIONS:
            return dict(self.codegraph_bridge.request("owner_source_layouts", {"path": path}))
        return {"status": "unsupported", "reason": "no_source_ast_adapter", "owners": []}

    def source_owner_calls(self, source_node: Mapping[str, Any]) -> dict[str, Any]:
        is_source_owner = str(source_node.get("id") or "").startswith("source_owner:")
        if is_source_owner:
            source_path = (self.workspace_root / str(source_node.get("path") or "")).resolve()
            if not source_path.is_relative_to(self.workspace_root.resolve()):
                return {"status": "failed", "reason": "source_owner_outside_workspace", "calls": []}
        extension = Path(str(source_node.get("path") or "")).suffix.casefold()
        if extension in PYTHON_EXTENSIONS:
            if is_source_owner:
                resolved = self.resolve_source_owners(str(source_node.get("path") or ""),
                    int(source_node.get("line_start") or 0), int(source_node.get("line_end") or 0))
                matches = [owner for owner in resolved.get("owners", ())
                           if owner["id"] == source_node["id"]
                           and owner["line_start"] == source_node.get("line_start")
                           and owner["line_end"] == source_node.get("line_end")
                           and owner["qualified_name"] == (source_node.get("qualified_name") or source_node.get("name"))]
                if len(matches) != 1:
                    return {"status": "failed", "reason": "source_owner_identity_mismatch", "calls": []}
                source_node = matches[0]
            return python_source_owner_calls(self.workspace_root, source_node)
        if extension in TYPESCRIPT_EXTENSIONS:
            return dict(
                self.codegraph_bridge.request(
                    "source_owner_calls",
                    {"source_node": dict(source_node)} if is_source_owner else {"node_id": str(source_node.get("id") or "")},
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

    def resolve_source_owners(self, path: str, line_start: int, line_end: int) -> dict[str, Any]:
        extension = Path(path).suffix.casefold()
        if extension in PYTHON_EXTENSIONS:
            return python_resolve_source_owners(self.workspace_root, path, line_start, line_end)
        if extension in TYPESCRIPT_EXTENSIONS:
            return dict(self.codegraph_bridge.request(
                "resolve_source_owners",
                {"path": path, "line_start": line_start, "line_end": line_end},
            ))
        return {
            "status": "unsupported",
            "reason": "no_source_ast_adapter",
            "adapter": "unsupported",
            "source_path": path,
            "line_start": line_start,
            "line_end": line_end,
            "owners": [],
        }
