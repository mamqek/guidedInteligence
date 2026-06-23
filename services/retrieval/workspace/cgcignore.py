from __future__ import annotations

import re
from pathlib import Path


CGCIGNORE_START = "# BEGIN guided-intelligence managed excludes"
CGCIGNORE_END = "# END guided-intelligence managed excludes"


def sync_cgcignore(workspace_root: Path, exclude_paths: tuple[str, ...]) -> None:
    cgcignore_path = workspace_root / ".cgcignore"
    existing = cgcignore_path.read_text(encoding="utf-8") if cgcignore_path.exists() else ""
    cleaned = remove_managed_cgcignore_block(existing).rstrip()
    managed_lines = [CGCIGNORE_START]
    for path in normalize_cgcignore_excludes(exclude_paths):
        managed_lines.append(path)
    managed_lines.append(CGCIGNORE_END)
    next_text = "\n".join(part for part in (cleaned, "\n".join(managed_lines)) if part).rstrip() + "\n"
    if next_text != existing:
        cgcignore_path.write_text(next_text, encoding="utf-8")


def remove_managed_cgcignore_block(text: str) -> str:
    pattern = re.compile(
        rf"(^|\n){re.escape(CGCIGNORE_START)}\n.*?\n{re.escape(CGCIGNORE_END)}\n?",
        re.DOTALL,
    )
    return pattern.sub("\n", text).strip("\n")


def normalize_cgcignore_excludes(exclude_paths: tuple[str, ...]) -> tuple[str, ...]:
    output: list[str] = []
    for value in exclude_paths:
        item = value.strip().replace("\\", "/").strip("/")
        if not item:
            continue
        if "." in Path(item).name:
            pattern = item
        else:
            pattern = item.rstrip("/") + "/"
        if pattern not in output:
            output.append(pattern)
    return tuple(output)
