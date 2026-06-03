from __future__ import annotations

from typing import Any, Mapping, Sequence

from core.source_policy import SourceCategory
from .common import (
    bounded_source_categories,
    bounded_strings,
    ordered_unique,
)
from .constants import (
    ALL_RETRIEVAL_ROLES,
    MAX_LLM_CONCEPT_TERMS,
    MAX_LLM_SUBQUERIES,
    MAX_NEGATIVE_FILTERS,
    MAX_RETRIEVAL_TERMS,
    MAX_SPECULATIVE_ENTITIES,
)
from .types import RoleDirectedSubquery


def step2_response_format() -> Mapping[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "workspace_retrieval_step2_plan",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "prompt_summary": {"type": "string"},
                    "retrieval_terms": {"type": "array", "items": {"type": "string"}},
                    "llm_concept_terms": {"type": "array", "items": {"type": "string"}},
                    "llm_subqueries": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "role": {"type": "string", "enum": list(ALL_RETRIEVAL_ROLES)},
                                "query": {"type": "string"},
                            },
                            "required": ["role", "query"],
                            "additionalProperties": False,
                        },
                    },
                    "speculative_entities": {"type": "array", "items": {"type": "string"}},
                    "source_priorities": {"type": "array", "items": {"type": "string"}},
                    "negative_filters": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "prompt_summary",
                    "retrieval_terms",
                    "llm_concept_terms",
                    "llm_subqueries",
                    "speculative_entities",
                    "source_priorities",
                    "negative_filters",
                ],
                "additionalProperties": False,
            },
        },
    }


def validate_step2_planner_response(
    response: Mapping[str, Any],
    *,
    allowed_sources: Sequence[SourceCategory],
) -> dict[str, Any]:
    llm_subqueries: list[RoleDirectedSubquery] = []
    for item in response.get("llm_subqueries", ()):
        if not isinstance(item, Mapping):
            continue
        role = str(item.get("role", "")).strip()
        query = str(item.get("query", "")).strip()
        if role not in ALL_RETRIEVAL_ROLES or not query:
            continue
        llm_subqueries.append(RoleDirectedSubquery(role=role, query=query))
        if len(llm_subqueries) >= MAX_LLM_SUBQUERIES:
            break

    source_priorities = bounded_source_categories(response.get("source_priorities"))
    if not source_priorities:
        source_priorities = tuple(
            category
            for category in allowed_sources
            if category in {SourceCategory.SOURCE_CODE, SourceCategory.DOCUMENTATION}
        ) or tuple(allowed_sources)

    return {
        "prompt_summary": str(response.get("prompt_summary", "")).strip(),
        "retrieval_terms": list(ordered_unique(bounded_strings(response.get("retrieval_terms"), limit=MAX_RETRIEVAL_TERMS))),
        "llm_concept_terms": list(ordered_unique(bounded_strings(response.get("llm_concept_terms"), limit=MAX_LLM_CONCEPT_TERMS))),
        "llm_subqueries": llm_subqueries,
        "speculative_entities": list(
            ordered_unique(bounded_strings(response.get("speculative_entities"), limit=MAX_SPECULATIVE_ENTITIES))
        ),
        "source_priorities": [category.value for category in source_priorities],
        "negative_filters": list(
            ordered_unique(bounded_strings(response.get("negative_filters"), limit=MAX_NEGATIVE_FILTERS))
        ),
    }
