from __future__ import annotations

from dataclasses import dataclass

from core.stages import ResponseStage


@dataclass(frozen=True)
class StageTransition:
    """A recorded movement between two response stages."""

    #: Stage the conversation was in before the transition.
    from_stage: ResponseStage
    #: Stage the conversation moved to after the transition.
    to_stage: ResponseStage
    #: Human-readable explanation for audit logs and replay.
    reason: str


# Legal forward transitions for v1. Remaining in the same stage is also allowed.
ALLOWED_STAGE_TRANSITIONS: tuple[tuple[ResponseStage, ResponseStage], ...] = (
    (ResponseStage.EXPLAIN, ResponseStage.ASK),
    (ResponseStage.ASK, ResponseStage.HINT),
)


def can_transition(from_stage: ResponseStage, to_stage: ResponseStage) -> bool:
    """Check whether a stage movement respects the frozen v1 sequence."""

    return from_stage == to_stage or (from_stage, to_stage) in ALLOWED_STAGE_TRANSITIONS
