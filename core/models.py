from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from core.source_policy import SourceCategory
from core.stages import ResponseStage
from core.violations import PolicyViolation


class UserIntent(str, Enum):
    """Small v1 intent set used by policy before model-heavy classification exists."""

    #: User wants to understand code or project behavior.
    UNDERSTAND_CODE = "understand_code"
    #: User asks for the answer, solution, or completed work directly.
    DIRECT_SOLUTION_REQUEST = "direct_solution_request"
    #: User is continuing an existing explanation path.
    FOLLOW_UP = "follow_up"
    #: Intent has not been classified yet.
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ConversationMessage:
    """One message already exchanged in a conversation."""

    #: Message author, such as "user", "assistant", or a later runtime role.
    role: str
    #: Raw message text.
    content: str
    #: Response stage associated with the message, when known.
    stage: ResponseStage | None = None


@dataclass(frozen=True)
class EvidenceItem:
    """One retrieved project artifact snippet used to ground a response."""

    #: Category of project artifact the evidence came from.
    source_category: SourceCategory
    #: Stable identifier for citation, replay, or later retrieval inspection.
    source_id: str
    #: Bounded text excerpt passed downstream as evidence.
    snippet: str
    #: Optional retrieval/reranking position, where lower values are stronger.
    rank: int | None = None
    #: Optional structured details, such as file path, URL, line number, or author.
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ConversationState:
    """Full policy-facing state for deciding the next orchestration action."""

    #: Stable ID used to join decisions, retrieval events, responses, and logs.
    conversation_id: str
    #: Current user input that policy is deciding how to handle.
    user_input: str
    #: Stage currently allowed for the next assistant response.
    current_stage: ResponseStage = ResponseStage.EXPLAIN
    #: Classified user intent, or UNKNOWN when policy should infer it cheaply.
    intent: UserIntent = UserIntent.UNKNOWN
    #: Prior messages needed for later follow-up behavior and replay.
    history: tuple[ConversationMessage, ...] = field(default_factory=tuple)
    #: Grounded evidence already attached to the state, if retrieval has run.
    evidence: tuple[EvidenceItem, ...] = field(default_factory=tuple)
    #: Ordered stage history used to detect stage skipping.
    stage_history: tuple[ResponseStage, ...] = field(default_factory=lambda: (ResponseStage.EXPLAIN,))


@dataclass(frozen=True)
class OrchestratorDecision:
    """Policy output that tells the rest of the system what is allowed next."""

    #: Whether the requested action may continue without violation handling.
    allowed: bool
    #: Stage used for the current decision.
    current_stage: ResponseStage
    #: Stage the conversation should move to after a successful response.
    next_stage: ResponseStage
    #: Intent policy used to make this decision.
    intent: UserIntent
    #: Whether retrieval should run before response construction.
    retrieval_required: bool
    #: Source categories retrieval and response generation may use.
    allowed_sources: tuple[SourceCategory, ...]
    #: Response template identifier selected by policy.
    response_template_id: str
    #: Human-readable reason for logs and debugging.
    reason: str
    #: Violations detected during policy evaluation.
    violations: tuple[PolicyViolation, ...] = field(default_factory=tuple)
    #: Optional structured details for future policy extensions.
    metadata: Mapping[str, str] = field(default_factory=dict)
