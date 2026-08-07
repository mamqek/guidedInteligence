from __future__ import annotations

from typing import Any, Mapping

from services.intent.models import SolutionPressure, Specificity, TargetState, TargetType, TaskIntent, TurnRelation


SCHEMA_VERSION = "request_analysis_v1"


def intent_response_format() -> Mapping[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": SCHEMA_VERSION,
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "intents": {
                        "type": "array",
                        "items": {"type": "string", "enum": _values(TaskIntent)},
                        "minItems": 1,
                        "maxItems": len(TaskIntent),
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
                    "classification_basis": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
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
                    "evidence_obligations": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 8,
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "description": {"type": "string"},
                                "required": {"type": "boolean"},
                                "depends_on": _string_array(8),
                            },
                            "required": ["id", "description", "required", "depends_on"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": [
                    "intents",
                    "turn_relation",
                    "solution_pressure",
                    "specificity",
                    "target_state",
                    "explicit_targets",
                    "confidence",
                    "classification_basis",
                    "anchors",
                    "search_terms",
                    "evidence_obligations",
                ],
                "additionalProperties": False,
            },
        },
    }


def _values(enum_type: Any) -> list[str]:
    return [item.value for item in enum_type]


def _string_array(max_items: int) -> Mapping[str, Any]:
    return {"type": "array", "items": {"type": "string"}, "maxItems": max_items}
