from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Mapping

from services.llm.json_completion import complete_json


PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "questions.md"


def repair_understanding_checks(
    *,
    llm_config: Any,
    context: Mapping[str, Any],
    response_format: Mapping[str, Any],
    log_warning: Callable[[Mapping[str, Any]], None] | None = None,
    log_event: Callable[[str, Mapping[str, Any]], None] | None = None,
) -> list[Mapping[str, Any]]:
    response = complete_json(
        llm_config,
        (
            {"role": "system", "content": PROMPT_PATH.read_text(encoding="utf-8")},
            {"role": "user", "content": json.dumps(context, sort_keys=True)},
        ),
        response_format=response_format,
        log_warning=log_warning,
        log_event=log_event,
    )
    checks = response.get("understanding_checks")
    if not isinstance(checks, list) or not all(isinstance(item, Mapping) for item in checks):
        raise RuntimeError("Question repair returned an invalid understanding_checks array.")
    return checks
