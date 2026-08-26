from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Mapping


PYTHON_EXTENSIONS = frozenset({".py", ".pyi"})


def resolve_source_owners(
    workspace_root: Path,
    relative_path: str,
    line_start: int,
    line_end: int,
) -> dict[str, Any]:
    normalized_path = relative_path.replace("\\", "/")
    result: dict[str, Any] = {
        "source_path": normalized_path,
        "line_start": line_start,
        "line_end": line_end,
        "adapter": "python_stdlib_ast",
        "owners": [],
    }
    try:
        source = (workspace_root / normalized_path).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=normalized_path)
    except (OSError, SyntaxError, UnicodeError) as exc:
        return {**result, "status": "failed", "reason": f"python_ast_parse_failed:{exc}"}
    owners: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        name = ""
        kind = ""
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name, kind = node.name, "function"
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if isinstance(value, ast.Lambda) and len(targets) == 1:
                name, kind = _assignment_name(targets[0]), "assigned_function"
        if not name:
            continue
        start = int(getattr(node, "lineno", 0))
        end = int(getattr(node, "end_lineno", start))
        if start > line_end or end < line_start:
            continue
        owners.append({
            "id": f"source_owner:{normalized_path}:{start}:{end}",
            "kind": kind,
            "name": name,
            "qualified_name": name,
            "path": normalized_path,
            "line_start": start,
            "line_end": end,
            "language": "python",
            "adapter": "python_stdlib_ast",
            "decision_code": "python_definition" if kind == "function" else "direct_lambda_assignment",
        })
    return {**result, "status": "ok", "owners": owners}


def _assignment_name(target: ast.AST) -> str:
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        return ast.unparse(target)
    return ""


def source_owner_calls(workspace_root: Path, source_node: Mapping[str, Any]) -> dict[str, Any]:
    relative_path = str(source_node.get("path") or "").replace("\\", "/")
    result = {
        "source_node_id": str(source_node.get("id") or ""),
        "source_path": relative_path,
        "adapter": "python_stdlib_ast",
        "calls": [],
    }
    path = workspace_root / relative_path
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=relative_path)
    except (OSError, SyntaxError, UnicodeError) as exc:
        return {**result, "status": "failed", "reason": f"python_ast_parse_failed:{exc}"}
    owner = _find_owner(tree, source_node)
    if owner is None:
        return {**result, "status": "failed", "reason": "python_owner_not_found"}
    calls: list[dict[str, Any]] = []
    visitor = _OwnerCallVisitor(owner, calls)
    for statement in getattr(owner, "body", ()):
        visitor.visit(statement)
    return {**result, "status": "ok", "calls": calls}


def _find_owner(tree: ast.AST, source_node: Mapping[str, Any]) -> ast.AST | None:
    expected_name = str(source_node.get("name") or "")
    expected_start = int(source_node.get("line_start") or 0)
    expected_end = int(source_node.get("line_end") or expected_start)
    candidates = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == expected_name
    ]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda node: (
            abs(int(getattr(node, "lineno", 0)) - expected_start)
            + abs(int(getattr(node, "end_lineno", getattr(node, "lineno", 0))) - expected_end),
            int(getattr(node, "lineno", 0)),
        ),
    )


class _OwnerCallVisitor(ast.NodeVisitor):
    def __init__(self, root: ast.AST, calls: list[dict[str, Any]]) -> None:
        self.root = root
        self.calls = calls

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node is self.root:
            self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if node is self.root:
            self.generic_visit(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def visit_Call(self, node: ast.Call) -> None:
        for name, qualifier, expression_kind in _called_names(node.func):
            self.calls.append(
                {
                    "name": name,
                    "qualifier": qualifier,
                    "expression_kind": expression_kind,
                    "expression": ast.unparse(node.func),
                    "line_start": int(getattr(node, "lineno", 0)),
                    "line_end": int(getattr(node, "end_lineno", getattr(node, "lineno", 0))),
                }
            )
        self.generic_visit(node)


def _called_names(expression: ast.AST) -> tuple[tuple[str, str, str], ...]:
    if isinstance(expression, ast.Name):
        return ((expression.id, "", "identifier"),)
    if isinstance(expression, ast.Attribute):
        return ((expression.attr, ast.unparse(expression.value), "property_access"),)
    if isinstance(expression, ast.IfExp):
        return tuple(
            (name, qualifier, f"conditional_{kind}")
            for branch in (expression.body, expression.orelse)
            for name, qualifier, kind in _called_names(branch)
        )
    return ()
