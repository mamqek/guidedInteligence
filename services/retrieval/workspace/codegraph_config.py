from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


CODEGRAPH_CONFIG_PATH = Path("codegraph.json")


@dataclass(frozen=True)
class CodeGraphConfigSnapshot:
    path: Path
    existed: bool
    original_content: bytes
    installed_content: bytes


def install_temporary_codegraph_excludes(
    workspace_root: Path,
    exclude_paths: tuple[str, ...],
) -> CodeGraphConfigSnapshot:
    config_path = workspace_root / CODEGRAPH_CONFIG_PATH
    existed = config_path.exists()
    original_content = config_path.read_bytes() if existed else b""
    config = _read_object(config_path)
    merged = _ordered_unique((*_string_list(config.get("exclude")), *normalize_codegraph_excludes(exclude_paths)))
    if merged:
        config["exclude"] = merged
    else:
        config.pop("exclude", None)
    installed_content = (json.dumps(config, indent=2, sort_keys=True) + "\n").encode("utf-8")
    config_path.write_bytes(installed_content)
    return CodeGraphConfigSnapshot(
        path=config_path,
        existed=existed,
        original_content=original_content,
        installed_content=installed_content,
    )


def restore_codegraph_config(snapshot: CodeGraphConfigSnapshot) -> None:
    if not snapshot.path.exists() or snapshot.path.read_bytes() != snapshot.installed_content:
        return
    if snapshot.existed:
        snapshot.path.write_bytes(snapshot.original_content)
    else:
        snapshot.path.unlink()


def normalize_codegraph_excludes(exclude_paths: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        _ordered_unique(
            normalized
            for value in exclude_paths
            if (normalized := str(value).strip().replace("\\", "/").strip("/"))
        )
    )


def _read_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must contain a JSON object.")
    return dict(value)


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if str(item).strip())


def _ordered_unique(values: Iterable[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output
