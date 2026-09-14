from __future__ import annotations

from pathlib import Path

PROMPT_ID = "request_analysis"
PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "intent_classification.md"
STAGE_REQUIREMENTS_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "request_analysis_stage_requirements.md"
STAGE_GROUPS_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "request_analysis_stage_groups.md"
