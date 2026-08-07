from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Mapping

from services.llm.json_completion import complete_json


PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "hints.md"


def repair_hint_ladders(
    *,
    llm_config: Any,
    context: Mapping[str, Any],
    response_format: Mapping[str, Any],
    log_warning: Callable[[Mapping[str, Any]], None] | None = None,
    log_event: Callable[[str, Mapping[str, Any]], None] | None = None,
) -> list[list[Mapping[str, Any]]]:
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
    ladders = response.get("hint_ladders")
    if not isinstance(ladders, list):
        raise RuntimeError("Hint repair returned an invalid hint_ladders array.")
    return [list(ladder) for ladder in ladders if isinstance(ladder, list)]
