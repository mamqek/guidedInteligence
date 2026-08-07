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
    ALL_RETRIEVAL_OBJECTIVES,
    MAX_LLM_CONCEPT_TERMS,
    MAX_LLM_SUBQUERIES,
    MAX_NEGATIVE_FILTERS,
    MAX_RETRIEVAL_TERMS,
    MAX_SPECULATIVE_ENTITIES,
    OBJECTIVE_BEHAVIOR_PATH,
    OBJECTIVE_CONFIGURATION_CONTEXT,
    OBJECTIVE_DIAGNOSTIC_SURFACE,
    OBJECTIVE_EFFECTS_OUTPUT,
    OBJECTIVE_EXAMPLE_USAGE,
    OBJECTIVE_IMPLEMENTATION_OWNER,
    OBJECTIVE_INTERFACE_ENTRY,
    OBJECTIVE_USAGE_CONTRACT,
    OBJECTIVE_VERIFICATION_REPRO,
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
                    "active_objectives": {"type": "array", "items": {"type": "string", "enum": list(ALL_RETRIEVAL_OBJECTIVES)}},
                    "deferred_objectives": {"type": "array", "items": {"type": "string", "enum": list(ALL_RETRIEVAL_OBJECTIVES)}},
                    "preferred_relations": {"type": "array", "items": {"type": "string"}},
                    "stop_contract": {
                        "type": "object",
                        "properties": {
                            "required": {"type": "array", "items": {"type": "string"}},
                            "one_of": {"type": "array", "items": {"type": "string"}},
                            "sufficient_when": {"type": "string"},
                        },
                        "required": ["required", "one_of", "sufficient_when"],
                        "additionalProperties": False,
                    },
                    "expansion_policy": {
                        "type": "object",
                        "properties": {
                            "on_missing_owner": {"type": "array", "items": {"type": "string"}},
                            "on_missing_causal_path": {"type": "array", "items": {"type": "string"}},
                            "on_missing_expected_behavior": {"type": "array", "items": {"type": "string"}},
                            "on_low_query_specificity": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": [
                            "on_missing_owner",
                            "on_missing_causal_path",
                            "on_missing_expected_behavior",
                            "on_low_query_specificity",
                        ],
                        "additionalProperties": False,
                    },
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
                    "active_objectives",
                    "deferred_objectives",
                    "preferred_relations",
                    "stop_contract",
                    "expansion_policy",
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

    active_objectives = _validated_objectives(response.get("active_objectives"))
    deferred_objectives = tuple(
        objective
        for objective in _validated_objectives(response.get("deferred_objectives"))
        if objective not in active_objectives
    )
    if not active_objectives:
        active_objectives, deferred_objectives = _default_objectives()

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
        "active_objectives": list(active_objectives),
        "deferred_objectives": list(deferred_objectives),
        "preferred_relations": list(ordered_unique(bounded_strings(response.get("preferred_relations"), limit=8))),
        "stop_contract": _validated_contract(response.get("stop_contract")),
        "expansion_policy": _validated_expansion_policy(response.get("expansion_policy")),
    }


def _sequence(value: object) -> tuple[object, ...]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(value)
    return ()


def _validated_objectives(values: object) -> tuple[str, ...]:
    objectives: list[str] = []
    for value in _sequence(values):
        objective = str(value or "").strip()
        if objective in ALL_RETRIEVAL_OBJECTIVES and objective not in objectives:
            objectives.append(objective)
    return tuple(objectives)


def _default_objectives() -> tuple[tuple[str, ...], tuple[str, ...]]:
    return (
        (OBJECTIVE_INTERFACE_ENTRY, OBJECTIVE_BEHAVIOR_PATH, OBJECTIVE_EFFECTS_OUTPUT),
        (OBJECTIVE_IMPLEMENTATION_OWNER, OBJECTIVE_DIAGNOSTIC_SURFACE, OBJECTIVE_VERIFICATION_REPRO),
    )


def _validated_contract(value: object) -> dict[str, object]:
    mapping = value if isinstance(value, Mapping) else {}
    return {
        "required": list(ordered_unique(bounded_strings(mapping.get("required"), limit=8))),
        "one_of": list(ordered_unique(bounded_strings(mapping.get("one_of"), limit=8))),
        "sufficient_when": str(mapping.get("sufficient_when", "")).strip(),
    }


def _validated_expansion_policy(value: object) -> dict[str, list[str]]:
    mapping = value if isinstance(value, Mapping) else {}
    keys = (
        "on_missing_owner",
        "on_missing_causal_path",
        "on_missing_expected_behavior",
        "on_low_query_specificity",
    )
    return {
        key: list(ordered_unique(bounded_strings(mapping.get(key), limit=8)))
        for key in keys
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
