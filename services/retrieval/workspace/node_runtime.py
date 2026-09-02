"""Resolve a Node runtime that can host CodeGraph's SQLite bridge.

CodeGraph requires the built-in ``node:sqlite`` module, introduced in Node
22.5.  Launching a bare ``node`` command made structural indexing depend on
Windows PATH order: an older system Node could silently win even when a newer
runtime was available.  This module is the single boundary for that choice.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
from typing import Iterable


CODEGRAPH_NODE_EXECUTABLE_ENV = "GUIDED_INTELLIGENCE_CODEGRAPH_NODE_EXECUTABLE"
_MINIMUM_NODE_VERSION = (22, 5)


@dataclass(frozen=True)
class CodeGraphNodeRuntime:
    executable: str
    version: str
    source: str


def resolve_codegraph_node_runtime() -> CodeGraphNodeRuntime:
    """Return a verified Node executable, never an unverified PATH assumption."""
    rejected: list[str] = []
    for executable, source in _candidate_executables():
        version, reason = _probe_node(executable)
        if version is not None:
            return CodeGraphNodeRuntime(executable=executable, version=version, source=source)
        rejected.append(f"{executable} ({source}): {reason}")
    details = "; ".join(rejected) or "no Node executable candidates were found"
    raise RuntimeError(
        "CodeGraph requires Node.js 22.5+ with the built-in node:sqlite module. "
        f"No compatible runtime was found: {details}. Install Node 24 or set "
        f"{CODEGRAPH_NODE_EXECUTABLE_ENV} to a compatible node executable."
    )


def _candidate_executables() -> Iterable[tuple[str, str]]:
    seen: set[str] = set()

    def emit(value: str, source: str) -> Iterable[tuple[str, str]]:
        normalized = str(Path(value).expanduser()) if value else ""
        key = normalized.casefold() if os.name == "nt" else normalized
        if normalized and key not in seen:
            seen.add(key)
            yield normalized, source

    configured = os.environ.get(CODEGRAPH_NODE_EXECUTABLE_ENV, "").strip()
    yield from emit(configured, "environment override")
    path_node = shutil.which("node")
    if path_node:
        yield from emit(path_node, "PATH")
    if os.name == "nt":
        runtime_root = Path.home() / ".cache" / "codex-runtimes"
        if runtime_root.is_dir():
            for candidate in sorted(
                runtime_root.glob("*/dependencies/node/bin/node.exe"),
                key=lambda item: item.stat().st_mtime,
                reverse=True,
            ):
                yield from emit(str(candidate), "bundled Codex runtime")


def _probe_node(executable: str) -> tuple[str | None, str]:
    try:
        completed = subprocess.run(
            (executable, "-e", "require('node:sqlite'); process.stdout.write(process.versions.node)"),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except OSError as exc:
        return None, str(exc)
    except subprocess.TimeoutExpired:
        return None, "version probe timed out"
    version = (completed.stdout or "").strip()
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "node probe failed").strip().replace("\n", " ")
        return None, detail[:240]
    parsed = _version_tuple(version)
    if parsed is None or parsed < _MINIMUM_NODE_VERSION:
        return None, f"Node {version or 'unknown'} is below required 22.5"
    return version, ""


def _version_tuple(value: str) -> tuple[int, int] | None:
    parts = value.strip().lstrip("v").split(".")
    try:
        return int(parts[0]), int(parts[1])
    except (IndexError, ValueError):
        return None
