from __future__ import annotations

# Owns persistent index sync metadata for deciding when workspace indexes are current. Do not place retrieval execution, role planning, or candidate ranking here.

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


def load_sync_manifest(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, Mapping) else {}


def sync_manifest_scope_matches(manifest: Mapping[str, Any], expected_scope: Mapping[str, Any]) -> bool:
    return {key: manifest.get(key) for key in expected_scope} == dict(expected_scope)


def save_sync_manifest(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    output = dict(payload)
    output["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(output, indent=2, sort_keys=True), encoding="utf-8")
