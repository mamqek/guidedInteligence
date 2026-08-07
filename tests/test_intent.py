from __future__ import annotations

import unittest

from services.intent import (
    INTENT_CONTRACTS,
    IntentClassification,
    IntentClassificationInput,
    SolutionPressure,
    Specificity,
    TargetReference,
    TargetState,
    TargetType,
    TaskIntent,
    TurnRelation,
    build_intent_context,
    classify_intent,
    classification_from_mapping,
    compose_intent_flow,
    normalize_intent,
    summarize_statuses,
    validate_contract_registry,
    validate_stage_permutation,
)
from services.intent.schema import intent_response_format


class _Config:
    model = "test-intent-model"


class IntentSystemTests(unittest.TestCase):
    def test_registry_has_one_complete_contract_per_intent(self) -> None:
        validate_contract_registry()
        self.assertEqual(set(INTENT_CONTRACTS), set(TaskIntent))
        self.assertTrue(all(contract.stages and contract.question.stem_families for contract in INTENT_CONTRACTS.values()))

    def test_classifier_schema_contains_only_new_task_intent_shape(self) -> None:
        schema = intent_response_format()["json_schema"]["schema"]
        self.assertEqual(set(schema["properties"]["intents"]["items"]["enum"]), {intent.value for intent in TaskIntent})
        self.assertNotIn("user_goals", schema["properties"])
        self.assertNotIn("response_operation", schema["properties"])
        self.assertNotIn("retrieval_intents", schema["properties"])
        self.assertNotIn("expected_outputs", schema["properties"])
        self.assertNotIn("uniqueItems", schema["properties"]["intents"])

    def test_duplicate_intents_are_rejected_after_schema_parsing(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate TaskIntent"):
            classification_from_mapping(
                {
                    "intents": ["explore", "explore"],
                    "turn_relation": "new_task",
                    "solution_pressure": "none",
                    "specificity": "medium",
                    "target_state": "unresolved",
                    "explicit_targets": [],
                    "confidence": 0.9,
                    "classification_basis": ["test"],
                }
            )

    def test_classifier_preserves_multiple_requested_outcomes_without_priority(self) -> None:
        def complete_json_fn(*_args, **_kwargs):
            return {
                "intents": ["debug", "change"],
                "turn_relation": "new_task",
                "solution_pressure": "complete_solution",
                "specificity": "narrow",
                "target_state": "explicit",
                "explicit_targets": [{"target_type": "function", "value": "saveUser"}],
                "confidence": 0.95,
                "classification_basis": ["asks why it fails", "asks to fix it"],
            }

        result = classify_intent(
            IntentClassificationInput(user_prompt="Explain why saveUser fails and fix it."),
            llm_config=_Config(),
            complete_json_fn=complete_json_fn,
        )

        self.assertEqual(result.status, "success")
        self.assertEqual(result.classification.intents, (TaskIntent.DEBUG, TaskIntent.CHANGE))

    def test_classifier_failure_is_explicit_and_has_no_fallback(self) -> None:
        result = classify_intent(
            IntentClassificationInput(user_prompt="Explain this."),
            llm_config=_Config(),
            complete_json_fn=lambda *_args, **_kwargs: {"intents": []},
        )
        self.assertEqual(result.status, "failed")
        self.assertIsNone(result.classification)
        self.assertFalse(result.fallback_used)

    def test_minimal_retrieval_context_excludes_flow_and_evidence_contracts(self) -> None:
        classification = _classification((TaskIntent.EXPLAIN, TaskIntent.EXPLORE))
        value = build_intent_context(classification).to_dict()

        self.assertEqual([item["intent"] for item in value["intents"]], ["explain", "explore"])
        serialized = str(value)
        self.assertNotIn("stages", serialized)
        self.assertNotIn("evidence_expectations", serialized)
        self.assertNotIn("question", serialized)

    def test_normalizer_removes_invented_literal_target(self) -> None:
        classification = IntentClassification(
            **{
                **_classification((TaskIntent.EXPLAIN,)).__dict__,
                "target_state": TargetState.EXPLICIT,
                "explicit_targets": (TargetReference(TargetType.FUNCTION, "missingFunction"),),
            }
        )
        normalized = normalize_intent(classification, user_prompt="How does authentication work?")
        self.assertEqual(normalized.classification.explicit_targets, ())
        self.assertEqual(normalized.classification.target_state, TargetState.UNRESOLVED)

    def test_composer_unions_all_fixed_stages_without_merging(self) -> None:
        flow = compose_intent_flow((TaskIntent.DEBUG, TaskIntent.CHANGE))
        expected = tuple(
            stage.id
            for intent in (TaskIntent.DEBUG, TaskIntent.CHANGE)
            for stage in INTENT_CONTRACTS[intent].stages
        )
        self.assertEqual(flow.contract_stage_ids, expected)
        self.assertEqual(len(flow.contract_stage_ids), len(set(flow.contract_stage_ids)))

    def test_flow_validation_accepts_only_an_exact_permutation(self) -> None:
        required = ("debug.symptom", "debug.evidence", "debug.cause")
        self.assertEqual(validate_stage_permutation(required, tuple(reversed(required))), ())
        errors = validate_stage_permutation(required, ("debug.symptom", "debug.symptom", "invented"))
        self.assertTrue(any("missing" in error for error in errors))
        self.assertTrue(any("unknown" in error for error in errors))
        self.assertTrue(any("duplicated" in error for error in errors))

    def test_sufficiency_summary_is_deterministic(self) -> None:
        self.assertEqual(summarize_statuses(("covered", "covered")), "covered")
        self.assertEqual(summarize_statuses(("missing", "missing")), "missing")
        self.assertEqual(summarize_statuses(("unclear", "unclear")), "unclear")
        self.assertEqual(summarize_statuses(("covered", "missing")), "partial")


def _classification(intents: tuple[TaskIntent, ...]) -> IntentClassification:
    return IntentClassification(
        intents=intents,
        turn_relation=TurnRelation.NEW_TASK,
        solution_pressure=SolutionPressure.NONE,
        specificity=Specificity.MEDIUM,
        target_state=TargetState.UNRESOLVED,
        explicit_targets=(),
        confidence=0.9,
        classification_basis=("test",),
    )


if __name__ == "__main__":
    unittest.main()
