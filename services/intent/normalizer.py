from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from services.intent.models import IntentClassification, TargetState


@dataclass(frozen=True)
class NormalizedIntent:
    classification: IntentClassification
    corrections: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"classification": self.classification.to_dict(), "corrections": list(self.corrections)}


def normalize_intent(
    classification: IntentClassification,
    *,
    user_prompt: str,
    active_understanding_check: bool = False,
) -> NormalizedIntent:
    del active_understanding_check
    corrections: list[str] = []
    explicit_targets = tuple(
        target for target in classification.explicit_targets if target.value.lower() in user_prompt.lower()
    )
    if len(explicit_targets) != len(classification.explicit_targets):
        corrections.append("removed_nonliteral_explicit_targets")
    target_state = classification.target_state
    if explicit_targets and target_state != TargetState.EXPLICIT:
        target_state = TargetState.EXPLICIT
        corrections.append("corrected_literal_target_state")
    if not explicit_targets and target_state == TargetState.EXPLICIT:
        target_state = TargetState.UNRESOLVED
        corrections.append("corrected_missing_explicit_target")
    normalized = replace(classification, explicit_targets=explicit_targets, target_state=target_state)
    return NormalizedIntent(classification=normalized, corrections=tuple(corrections))
