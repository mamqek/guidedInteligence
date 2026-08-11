from __future__ import annotations

from typing import Any, Mapping, Sequence

from services.intent.models import SolutionPressure, Specificity, TargetState, TargetType, TaskIntent, TurnRelation


SCHEMA_VERSION = "request_analysis_v2"


def intent_response_format() -> Mapping[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": SCHEMA_VERSION,
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "intent_decisions": {
                        "type": "object",
                        "properties": {
                            intent.value: {
                                "type": "object",
                                "properties": {
                                    "selected": {"type": "boolean"},
                                    "reason": {"type": "string"},
                                },
                                "required": ["selected", "reason"],
                                "additionalProperties": False,
                            }
                            for intent in TaskIntent
                        },
                        "required": _values(TaskIntent),
                        "additionalProperties": False,
                    },
                    "turn_relation": {"type": "string", "enum": _values(TurnRelation)},
                    "solution_pressure": {"type": "string", "enum": _values(SolutionPressure)},
                    "specificity": {"type": "string", "enum": _values(Specificity)},
                    "target_state": {"type": "string", "enum": _values(TargetState)},
                    "explicit_targets": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "target_type": {"type": "string", "enum": _values(TargetType)},
                                "value": {"type": "string"},
                            },
                            "required": ["target_type", "value"],
                            "additionalProperties": False,
                        },
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "anchors": {
                        "type": "object",
                        "properties": {
                            "paths": _string_array(12),
                            "symbols": _string_array(16),
                            "errors": _string_array(8),
                            "literals": _string_array(12),
                            "identifiers": _string_array(16),
                        },
                        "required": ["paths", "symbols", "errors", "literals", "identifiers"],
                        "additionalProperties": False,
                    },
                    "search_terms": _string_array(16),
                },
                "required": [
                    "intent_decisions",
                    "turn_relation",
                    "solution_pressure",
                    "specificity",
                    "target_state",
                    "explicit_targets",
                    "confidence",
                    "anchors",
                    "search_terms",
                ],
                "additionalProperties": False,
            },
        },
    }


def stage_requirement_response_format(
    stage_ids: Sequence[str],
    *,
    symbol_candidates: Sequence[str] = (),
) -> Mapping[str, Any]:
    ordered_ids = list(dict.fromkeys(stage_ids))
    ordered_symbols = list(dict.fromkeys(symbol_candidates))
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "request_analysis_stage_requirements_v1",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "symbol_decisions": {
                        "type": "object",
                        "properties": {
                            symbol: {
                                "type": "object",
                                "properties": {
                                    "relevance": {
                                        "type": "string",
                                        "enum": ["primary", "supporting", "ignore"],
                                    },
                                    "reason": {"type": "string", "minLength": 1, "maxLength": 240},
                                },
                                "required": ["relevance", "reason"],
                                "additionalProperties": False,
                            }
                            for symbol in ordered_symbols
                        },
                        "required": ordered_symbols,
                        "additionalProperties": False,
                    },
                    "stage_requirements": {
                        "type": "object",
                        "properties": {
                            stage_id: {
                                "type": "object",
                                "properties": {
                                    "evidence_boundary": {
                                        "type": "string",
                                        "enum": ["prompt", "local", "local_to_external_handoff", "external"],
                                    },
                                    "proposition": {"type": "string", "minLength": 1, "maxLength": 500},
                                    "anchor_refs": _string_array(12),
                                },
                                "required": [
                                    "evidence_boundary",
                                    "proposition",
                                    "anchor_refs",
                                ],
                                "additionalProperties": False,
                            }
                            for index, stage_id in enumerate(ordered_ids)
                        },
                        "required": ordered_ids,
                        "additionalProperties": False,
                    }
                },
                "required": ["symbol_decisions", "stage_requirements"],
                "additionalProperties": False,
            },
        },
    }


def stage_group_response_format(
    stage_ids: Sequence[str],
    *,
    allowed_leaders: Mapping[str, Sequence[str]] | None = None,
) -> Mapping[str, Any]:
    ordered_ids = list(dict.fromkeys(stage_ids))
    leader_options = allowed_leaders or {}
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "request_analysis_stage_groups_v1",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "stage_groups": {
                        "type": "object",
                        "properties": {
                            stage_id: {
                                "type": "object",
                                "properties": {
                                    "evidence_group_leader": {
                                        "type": "string",
                                        "enum": list(
                                            dict.fromkeys(
                                                leader_options.get(
                                                    stage_id,
                                                    [
                                                        candidate
                                                        for candidate in ordered_ids[:index]
                                                        if candidate.partition(".")[0]
                                                        != stage_id.partition(".")[0]
                                                    ]
                                                    + [stage_id],
                                                )
                                            )
                                        ),
                                    }
                                },
                                "required": ["evidence_group_leader"],
                                "additionalProperties": False,
                            }
                            for index, stage_id in enumerate(ordered_ids)
                        },
                        "required": ordered_ids,
                        "additionalProperties": False,
                    }
                },
                "required": ["stage_groups"],
                "additionalProperties": False,
            },
        },
    }


def _values(enum_type: Any) -> list[str]:
    return [item.value for item in enum_type]


def _string_array(max_items: int) -> Mapping[str, Any]:
    return {"type": "array", "items": {"type": "string"}, "maxItems": max_items}
