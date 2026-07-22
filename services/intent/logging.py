from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.intent.models import IntentClassification
from services.intent.prompts import PROMPT_TEMPLATE_ID
from services.intent.schema import SCHEMA_VERSION


@dataclass(frozen=True)
class IntentStageResult:
    status: str
    classification: IntentClassification | None
    error: str | None
    fallback_used: bool
    latency_ms: int
    classifier_model: str
    classifier_prompt_version: str = PROMPT_TEMPLATE_ID
    classifier_schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "classification": self.classification.to_dict() if self.classification is not None else None,
            "error": self.error,
            "fallback_used": self.fallback_used,
            "latency_ms": self.latency_ms,
            "classifier_model": self.classifier_model,
            "classifier_prompt_version": self.classifier_prompt_version,
            "classifier_schema_version": self.classifier_schema_version,
        }
