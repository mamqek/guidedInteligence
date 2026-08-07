from __future__ import annotations

from typing import Any, Mapping

from services.intent.models import SolutionPressure, Specificity, TargetState, TargetType, TaskIntent, TurnRelation


SCHEMA_VERSION = "intent_classification_v2"


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
                ],
                "additionalProperties": False,
            },
        },
    }


def _values(enum_type: Any) -> list[str]:
    return [item.value for item in enum_type]
