from __future__ import annotations

from typing import Any, Mapping

from services.intent.models import (
    ExpectedOutput,
    ResponseOperation,
    RetrievalIntent,
    SolutionPressure,
    Specificity,
    TargetType,
    TurnRelation,
    UserGoal,
)

SCHEMA_VERSION = "intent_classification_v1"


def intent_response_format() -> Mapping[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": SCHEMA_VERSION,
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "user_goals": {"type": "array", "items": {"type": "string", "enum": _values(UserGoal)}},
                    "response_operation": {"type": "string", "enum": _values(ResponseOperation)},
                    "turn_relation": {"type": "string", "enum": _values(TurnRelation)},
                    "solution_pressure": {"type": "string", "enum": _values(SolutionPressure)},
                    "retrieval_intents": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "intent": {"type": "string", "enum": _values(RetrievalIntent)},
                                "priority": {"type": "string", "enum": ["primary", "secondary"]},
                            },
                            "required": ["intent", "priority"],
                            "additionalProperties": False,
                        },
                    },
                    "primary_expected_output": {"type": "string", "enum": _values(ExpectedOutput)},
                    "expected_outputs": {"type": "array", "items": {"type": "string", "enum": _values(ExpectedOutput)}},
                    "specificity": {"type": "string", "enum": _values(Specificity)},
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
                    "classification_basis": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "user_goals",
                    "response_operation",
                    "turn_relation",
                    "solution_pressure",
                    "retrieval_intents",
                    "primary_expected_output",
                    "expected_outputs",
                    "specificity",
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
