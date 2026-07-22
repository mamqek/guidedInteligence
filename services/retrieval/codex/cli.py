from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Sequence


def resolve_codex_command(command: Sequence[str] | None = None) -> tuple[str, ...]:
    values = tuple(str(item) for item in (command or ()) if str(item).strip())
    if not values:
        return (_preferred_codex_executable(),)
    if len(values) != 1:
        return values
    executable = values[0].strip()
    if not executable:
        return (_preferred_codex_executable(),)
    if executable.lower() != "codex":
        return values
    return (_preferred_codex_executable(),)


def _preferred_codex_executable() -> str:
    candidates = []
    configured_path = os.environ.get("CODEX_CLI_PATH")
    if configured_path:
        candidates.append(Path(configured_path))
    home = Path.home()
    local_app_data = os.environ.get("LOCALAPPDATA")
    if os.name == "nt" and local_app_data:
        codex_bin = Path(local_app_data) / "OpenAI" / "Codex" / "bin"
        if codex_bin.is_dir():
            candidates.extend(
                path / "codex.exe"
                for path in sorted(codex_bin.iterdir(), key=lambda path: path.stat().st_mtime, reverse=True)
                if path.is_dir() and (path / "codex.exe").is_file()
            )
    if os.name == "nt":
        candidates.append(home / ".codex" / ".sandbox-bin" / "codex.exe")
    else:
        candidates.append(home / ".codex" / ".sandbox-bin" / "codex")
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    discovered = shutil.which("codex")
    if discovered:
        return discovered
    return "codex"
