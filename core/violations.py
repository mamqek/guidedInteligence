from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


class PolicyViolationType(str, Enum):
    """Policy failures that must be explicit and loggable in v1."""

    #: User asks the system to solve or complete the work directly.
    DIRECT_SOLUTION_REQUEST = "direct_solution_request"
    #: Response or retrieval attempts to use a source category outside v1 policy.
    UNSUPPORTED_SOURCE_USAGE = "unsupported_source_usage"
    #: Response is not grounded in project-specific evidence.
    UNGROUNDED_ANSWER = "ungrounded_answer"


@dataclass(frozen=True)
class PolicyViolation:
    """Concrete policy violation attached to a decision or response."""

    #: Machine-readable violation type for branching, logging, and evaluation.
    violation_type: PolicyViolationType
    #: Human-readable explanation of what failed.
    message: str
    #: Optional structured context, such as source IDs or policy names.
    metadata: Mapping[str, str] = field(default_factory=dict)
