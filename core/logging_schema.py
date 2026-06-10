from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


class LogEventType(str, Enum):
    """Minimum structured events needed for v1 auditability and replay."""

    #: Orchestration run has started.
    RUN_STARTED = "run_started"
    #: Policy selected or rejected a response stage.
    STAGE_DECISION = "stage_decision"
    #: Retrieval decided which source categories to consult and in what order.
    RETRIEVAL_PLAN = "retrieval_plan"
    #: Retrieval or context building selected concrete evidence items.
    EVIDENCE_SELECTED = "evidence_selected"
    #: Control layer produced a structured response plan.
    RESPONSE_PLAN = "response_plan"
    #: Model or response builder input payload was created.
    PROMPT_PAYLOAD = "prompt_payload"
    #: Explanation LLM request payload was sent.
    RESPONSE_GENERATION_REQUESTED = "response_generation_requested"
    #: Explanation LLM response payload was received.
    RESPONSE_GENERATION_RECEIVED = "response_generation_received"
    #: Explanation LLM generation failed.
    RESPONSE_GENERATION_FAILED = "response_generation_failed"
    #: Final structured response payload was produced.
    RESPONSE_PAYLOAD = "response_payload"
    #: Model configuration was used for a model-backed step.
    MODEL_SETTINGS = "model_settings"
    #: Policy violation was detected and handled.
    POLICY_VIOLATION = "policy_violation"
    #: Orchestration run has completed.
    RUN_COMPLETED = "run_completed"


@dataclass(frozen=True)
class LogEvent:
    """One append-only audit event for orchestration analysis."""

    #: Machine-readable event kind.
    event_type: LogEventType
    #: Conversation this event belongs to.
    conversation_id: str
    #: Event-specific structured data.
    payload: Mapping[str, Any]
    #: UTC creation timestamp.
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Serialize the event to primitives for JSONL, replay, or inspection."""

        return {
            "event_type": self.event_type.value,
            "conversation_id": self.conversation_id,
            "payload": dict(self.payload),
            "created_at": self.created_at.isoformat(),
        }
