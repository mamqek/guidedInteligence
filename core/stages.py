from __future__ import annotations

from enum import Enum


class ResponseStage(str, Enum):
    """Ordered response stages allowed by the v1 scaffolded assistance policy.

    These values are intentionally small and stable because the rest of the
    orchestration contract uses them to decide transitions, templates, and logs.
    """

    #: First response stage: explain the relevant project behavior with evidence.
    EXPLAIN = "explain"
    #: Second response stage: ask a reasoning question after an explanation.
    ASK = "ask"
    #: Third response stage: provide a bounded hint after the explain/ask path.
    HINT = "hint"


# Canonical v1 stage order. There is no standalone shortcut stage in v1.
V1_STAGE_SEQUENCE: tuple[ResponseStage, ...] = (
    ResponseStage.EXPLAIN,
    ResponseStage.ASK,
    ResponseStage.HINT,
)


def stage_index(stage: ResponseStage) -> int:
    """Return the zero-based position of a stage in the v1 sequence."""

    return V1_STAGE_SEQUENCE.index(stage)


def next_stage(stage: ResponseStage) -> ResponseStage:
    """Return the next v1 stage, staying at HINT once the sequence is complete."""

    index = stage_index(stage)
    if index >= len(V1_STAGE_SEQUENCE) - 1:
        return stage
    return V1_STAGE_SEQUENCE[index + 1]
