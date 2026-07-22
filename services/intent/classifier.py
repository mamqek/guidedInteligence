from __future__ import annotations

import json
import time
from typing import Any, Callable, Mapping, Sequence

from services.intent.logging import IntentStageResult
from services.intent.models import IntentClassificationInput, classification_from_mapping
from services.intent.prompts import PROMPT_PATH
from services.intent.schema import intent_response_format
from services.llm.json_completion import complete_json

JsonCompletion = Callable[..., Mapping[str, Any]]


def classify_intent(
    classification_input: IntentClassificationInput,
    *,
    llm_config: Any,
    complete_json_fn: JsonCompletion = complete_json,
) -> IntentStageResult:
    started_at = time.perf_counter()
    model = str(getattr(llm_config, "model", "") or "")
    try:
        response = complete_json_fn(
            llm_config,
            _messages(classification_input),
            response_format=intent_response_format(),
        )
        classification = classification_from_mapping(response)
        return IntentStageResult(
            status="success",
            classification=classification,
            error=None,
            fallback_used=False,
            latency_ms=_elapsed_ms(started_at),
            classifier_model=model,
        )
    except Exception as exc:
        return IntentStageResult(
            status="failed",
            classification=None,
            error=f"{type(exc).__name__}: {exc}",
            fallback_used=False,
            latency_ms=_elapsed_ms(started_at),
            classifier_model=model,
        )


def _messages(classification_input: IntentClassificationInput) -> Sequence[Mapping[str, str]]:
    return (
        {"role": "system", "content": PROMPT_PATH.read_text(encoding="utf-8")},
        {"role": "user", "content": json.dumps(classification_input.to_dict(), sort_keys=True)},
    )


def _elapsed_ms(started_at: float) -> int:
    return int(round((time.perf_counter() - started_at) * 1000))
