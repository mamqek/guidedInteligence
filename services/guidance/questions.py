from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class UnderstandingCheck:
    id: str
    role: str
    question_type: str
    question: str
    expected_answer_points: tuple[str, ...]
    hint: str
    evidence_refs: tuple[str, ...]
    origin: str
    tested_concepts: tuple[str, ...] = ()
    answer_point_map: tuple[Mapping[str, str], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "question_type": self.question_type,
            "question": self.question,
            "expected_answer_points": list(self.expected_answer_points),
            "hint": self.hint,
            "evidence_refs": list(self.evidence_refs),
            "origin": self.origin,
            "tested_concepts": list(self.tested_concepts),
            "answer_point_map": [dict(item) for item in self.answer_point_map],
        }
