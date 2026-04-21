from __future__ import annotations

from typing import Protocol, Sequence

from core.logging_schema import LogEvent


class LoggingStore(Protocol):
    """Readable append-only event store used for later replay and inspection."""

    def append(self, event: LogEvent) -> None:
        """Append one event to persistent or in-memory storage."""

        ...

    def list_events(self, conversation_id: str) -> Sequence[LogEvent]:
        """Return all events recorded for one conversation in storage order."""

        ...
