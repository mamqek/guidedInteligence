from __future__ import annotations

# Owns stable repository identity helpers used to scope index resources. Do not place index execution, retrieval, or candidate logic here.

import hashlib
import re
from pathlib import Path


def repo_scoped_collection_name(*, base_collection_name: str, workspace_root: Path) -> str:
    identity = repo_identity(workspace_root)
    slug = re.sub(r"[^a-z0-9]+", "_", identity.lower()).strip("_") or "workspace"
    digest = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:8]
    candidate = f"{base_collection_name}__{slug}__{digest}"
    return candidate[:180]


def repo_identity(workspace_root: Path) -> str:
    resolved = workspace_root.resolve()
    parts = resolved.parts
    if len(parts) >= 3 and parts[-2].lower() == "s":
        return parts[-3]

    git_root = git_root_for_path(resolved)
    if git_root is not None:
        identity = git_root.name.strip() or "repo"
        digest = hashlib.sha1(str(git_root).lower().encode("utf-8")).hexdigest()[:8]
        return f"{identity}:{digest}"

    identity = resolved.name.strip() or "workspace"
    digest = hashlib.sha1(str(resolved).lower().encode("utf-8")).hexdigest()[:8]
    return f"{identity}:{digest}"


def git_root_for_path(start: Path) -> Path | None:
    current = start
    while True:
        if (current / ".git").exists():
            return current
        if current.parent == current:
            return None
        current = current.parent
