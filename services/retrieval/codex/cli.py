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
    home = Path.home()
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
