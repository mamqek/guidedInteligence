from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.intent.models import TaskIntent


@dataclass(frozen=True)
class UnderstandingHint:
    kind: str
    text: str

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "text": self.text}


@dataclass(frozen=True)
class UnderstandingCheck:
    id: str
    intent: TaskIntent
    target_stage_ids: tuple[str, ...]
    prerequisite_stage_ids: tuple[str, ...]
    stem_family: str
    reasoning_focus: str
    selection_reason: str
    question: str
    expected_answer_points: tuple[str, ...]
    hints: tuple[UnderstandingHint, ...]
    evidence_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "intent": self.intent.value,
            "target_stage_ids": list(self.target_stage_ids),
            "prerequisite_stage_ids": list(self.prerequisite_stage_ids),
            "stem_family": self.stem_family,
            "reasoning_focus": self.reasoning_focus,
            "selection_reason": self.selection_reason,
            "question": self.question,
            "expected_answer_points": list(self.expected_answer_points),
            "hints": [hint.to_dict() for hint in self.hints],
            "evidence_refs": list(self.evidence_refs),
        }
