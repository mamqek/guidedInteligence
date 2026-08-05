from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


class LogEventType(str, Enum):
    """Minimum structured events needed for v1 auditability and replay."""

    #: Orchestration run has started.
    RUN_STARTED = "run_started"
    #: Policy selected or rejected a guided turn.
    TURN_DECISION = "turn_decision"
    #: Shadow semantic intent classification was attempted.
    INTENT_CLASSIFICATION = "intent_classification"
    #: Shadow semantic intent classification was normalized.
    INTENT_NORMALIZATION = "intent_normalization"
    #: Shadow semantic intent was compared with retrieval-side intent signals.
    INTENT_AGREEMENT = "intent_agreement"
    #: Shadow or active intent router produced a pipeline decision.
    INTENT_ROUTING_DECISION = "intent_routing_decision"
    #: Retrieval decided which source categories to consult and in what order.
    RETRIEVAL_PLAN = "retrieval_plan"
    #: Retrieval or context building selected concrete evidence items.
    EVIDENCE_SELECTED = "evidence_selected"
    #: Post-retrieval evidence graph generation has started.
    EVIDENCE_GRAPH_GENERATION_STARTED = "evidence_graph_generation_started"
    #: A cached post-retrieval evidence graph was reused.
    EVIDENCE_GRAPH_CACHE_HIT = "evidence_graph_cache_hit"
    #: Post-retrieval evidence graph generation completed.
    EVIDENCE_GRAPH_GENERATION_COMPLETED = "evidence_graph_generation_completed"
    #: Post-retrieval evidence graph generation failed explicitly.
    EVIDENCE_GRAPH_GENERATION_FAILED = "evidence_graph_generation_failed"
    #: Control layer produced a structured response plan.
    RESPONSE_PLAN = "response_plan"
    #: Model or response builder input payload was created.
    PROMPT_PAYLOAD = "prompt_payload"
    #: Explanation LLM request payload was sent.
    RESPONSE_GENERATION_REQUESTED = "response_generation_requested"
    #: Explanation LLM response payload was received.
    RESPONSE_GENERATION_RECEIVED = "response_generation_received"
    #: Explanation generation request payload was sent to the response model.
    RESPONSE_GENERATION_REQUEST_PAYLOAD = "response_generation_request_payload"
    #: Explanation generation response payload was received from the response model.
    RESPONSE_GENERATION_RESPONSE_PAYLOAD = "response_generation_response_payload"
    #: Explanation LLM generation failed.
    RESPONSE_GENERATION_FAILED = "response_generation_failed"
    #: Low-level LLM request was sent.
    LLM_REQUEST_SENT = "llm_request_sent"
    #: Low-level LLM response was received.
    LLM_RESPONSE_RECEIVED = "llm_response_received"
    #: Low-level LLM request failed.
    LLM_REQUEST_FAILED = "llm_request_failed"
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
