from __future__ import annotations

import re
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
                    "surface_context_terms": {"type": "array", "items": {"type": "string"}},
                    "owner_artifact_terms": {"type": "array", "items": {"type": "string"}},
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
                    "owner_subqueries": {
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
                    "support_subqueries": {
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
                    "surface_context_terms",
                    "owner_artifact_terms",
                    "llm_concept_terms",
                    "llm_subqueries",
                    "owner_subqueries",
                    "support_subqueries",
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
    owner_subqueries = _validated_subqueries(response.get("owner_subqueries", ()))
    support_subqueries = _validated_subqueries(response.get("support_subqueries", ()))

    source_priorities = bounded_source_categories(response.get("source_priorities"))
    if not source_priorities:
        source_priorities = tuple(
            category
            for category in allowed_sources
            if category in {SourceCategory.SOURCE_CODE, SourceCategory.DOCUMENTATION}
        ) or tuple(allowed_sources)

    retrieval_terms = list(ordered_unique(bounded_strings(response.get("retrieval_terms"), limit=MAX_RETRIEVAL_TERMS)))
    owner_artifact_terms = list(
        ordered_unique(
            tuple(bounded_strings(response.get("owner_artifact_terms"), limit=MAX_RETRIEVAL_TERMS))
            + _derived_owner_artifact_terms(
                tuple(retrieval_terms)
                + tuple(bounded_strings(response.get("owner_artifact_terms"), limit=MAX_RETRIEVAL_TERMS))
                + tuple(bounded_strings(response.get("llm_concept_terms"), limit=MAX_LLM_CONCEPT_TERMS))
            )
        )
    )[:MAX_RETRIEVAL_TERMS]

    return {
        "prompt_summary": str(response.get("prompt_summary", "")).strip(),
        "retrieval_terms": retrieval_terms,
        "surface_context_terms": list(ordered_unique(bounded_strings(response.get("surface_context_terms"), limit=MAX_RETRIEVAL_TERMS))),
        "owner_artifact_terms": owner_artifact_terms,
        "llm_concept_terms": list(ordered_unique(bounded_strings(response.get("llm_concept_terms"), limit=MAX_LLM_CONCEPT_TERMS))),
        "llm_subqueries": llm_subqueries,
        "owner_subqueries": list(owner_subqueries),
        "support_subqueries": list(support_subqueries),
        "speculative_entities": list(
            ordered_unique(bounded_strings(response.get("speculative_entities"), limit=MAX_SPECULATIVE_ENTITIES))
        ),
        "source_priorities": [category.value for category in source_priorities],
        "negative_filters": list(
            ordered_unique(bounded_strings(response.get("negative_filters"), limit=MAX_NEGATIVE_FILTERS))
        ),
    }


def _validated_subqueries(values: object) -> tuple[RoleDirectedSubquery, ...]:
    subqueries: list[RoleDirectedSubquery] = []
    for item in values if isinstance(values, Sequence) and not isinstance(values, (str, bytes)) else ():
        if not isinstance(item, Mapping):
            continue
        role = str(item.get("role", "")).strip()
        query = str(item.get("query", "")).strip()
        if role not in ALL_RETRIEVAL_ROLES or not query:
            continue
        subqueries.append(RoleDirectedSubquery(role=role, query=query))
        if len(subqueries) >= MAX_LLM_SUBQUERIES:
            break
    return tuple(subqueries)


def _derived_owner_artifact_terms(values: Sequence[str]) -> tuple[str, ...]:
    derived: list[str] = []
    non_artifact_heads = {"error", "warning", "message", "exception", "failure", "failed"}
    for value in values:
        lowered = str(value).lower()
        for match in re.finditer(r"\b(?:parse|parsing|parsed)\s+([a-z][a-z0-9_-]{2,})\b", lowered):
            artifact = match.group(1)
            if artifact not in non_artifact_heads:
                derived.append(f"{artifact} parser")
        for match in re.finditer(r"\b([a-z][a-z0-9_-]{2,})\s+(?:parse|parser|parsing|parsed)\b", lowered):
            artifact = match.group(1)
            if artifact not in non_artifact_heads:
                derived.append(f"{artifact} parser")
    return ordered_unique(derived)
