from __future__ import annotations

from pathlib import Path
import re
from typing import Any


RESOURCE_EXTENSIONS = {".md", ".json", ".yaml", ".yml", ".toml"}
RESOURCE_LITERAL_PATTERN = re.compile(
    r'''["'`]([^"'`\r\n]+\.(?:md|json|ya?ml|toml))["'`]''',
    re.IGNORECASE,
)


def resource_reference_between_files(
    workspace_root: str | Path,
    left_path: str,
    right_path: str,
) -> dict[str, Any] | None:
    root = Path(workspace_root).resolve()
    for source_path, target_path in ((left_path, right_path), (right_path, left_path)):
        target = _workspace_file(root, target_path)
        if target is None or target.suffix.lower() not in RESOURCE_EXTENSIONS or not target.is_file():
            continue
        source = _workspace_file(root, source_path)
        if source is None or not source.is_file() or source.suffix.lower() in RESOURCE_EXTENSIONS:
            continue
        literal = _matching_literal(root, source, target)
        if literal:
            return {
                "source_path": _relative_path(root, source),
                "target_path": _relative_path(root, target),
                "edge_kind": "resource_reference",
                "provenance": "exact_resource_literal",
                "literal": literal,
            }
    return None


def _matching_literal(root: Path, source: Path, target: Path) -> str:
    try:
        text = source.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""
    for literal in RESOURCE_LITERAL_PATTERN.findall(text):
        normalized = literal.replace("\\", "/").strip()
        for base in (source.parent, root):
            try:
                resolved = (base / normalized).resolve()
            except OSError:
                continue
            if resolved == target:
                return literal
        if "/" not in normalized and Path(normalized).name.casefold() == target.name.casefold():
            matches = _matching_descendants(source.parent, target.name)
            if matches == (target.resolve(),):
                return literal
    return ""


def _matching_descendants(directory: Path, basename: str) -> tuple[Path, ...]:
    matches: list[Path] = []
    try:
        for candidate in directory.rglob(basename):
            if candidate.is_file():
                matches.append(candidate.resolve())
                if len(matches) > 1:
                    break
    except OSError:
        return ()
    return tuple(matches)


def _workspace_file(root: Path, value: str) -> Path | None:
    normalized = str(value).strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if not normalized or Path(normalized).is_absolute():
        return None
    candidate = (root / normalized).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def _relative_path(root: Path, value: Path) -> str:
    try:
        return value.resolve().relative_to(root).as_posix()
    except (OSError, ValueError):
        return value.as_posix()
