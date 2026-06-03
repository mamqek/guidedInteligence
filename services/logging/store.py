from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from core.logging_schema import LogEvent, LogEventType


class JsonlLogger:
    """Simple JSONL-backed logging store for orchestration events."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def record(self, event: LogEvent) -> None:
        self.append(event)

    def append(self, event: LogEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict(), sort_keys=True) + "\n")

    def list_events(self, conversation_id: str) -> Sequence[LogEvent]:
        if not self.path.exists():
            return ()
        output: list[LogEvent] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            data = json.loads(line)
            if data.get("conversation_id") != conversation_id:
                continue
            output.append(
                LogEvent(
                    event_type=LogEventType(str(data["event_type"])),
                    conversation_id=str(data["conversation_id"]),
                    payload=dict(data.get("payload", {})),
                )
            )
        return tuple(output)
