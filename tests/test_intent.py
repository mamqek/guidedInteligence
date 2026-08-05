from __future__ import annotations

import unittest
from dataclasses import dataclass
from typing import Any, Mapping

from services.intent import IntentClassificationInput, build_retrieval_hints, classify_intent
from services.intent.agreement import assess_intent_agreement
from services.intent.models import (
    ExpectedOutput,
    IntentClassification,
    RankedRetrievalIntent,
    ResponseOperation,
    RetrievalIntent,
    SolutionPressure,
    Specificity,
    TargetReference,
    TargetType,
    TurnRelation,
    UserGoal,
)
from services.intent.normalizer import normalize_intent
from services.intent.schema import intent_response_format
from core.models import RetrievalResult, UserIntent


@dataclass(frozen=True)
class _LLMConfig:
    model: str = "test-intent-model"


class IntentClassifierTests(unittest.TestCase):
    def test_schema_requires_primary_and_mixed_expected_outputs(self) -> None:
        schema = intent_response_format()["json_schema"]["schema"]

        self.assertIn("primary_expected_output", schema["required"])
        self.assertIn("expected_outputs", schema["required"])
        self.assertEqual(
            schema["properties"]["turn_relation"]["enum"],
            ["new_task", "clarify", "continue", "mode_change", "answer_to_check"],
        )

    def test_classifier_returns_successful_stage_result(self) -> None:
        def completion(_config: Any, _messages: object, **_kwargs: object) -> Mapping[str, Any]:
            return {
                "user_goals": ["debug", "understand", "change"],
                "response_operation": "produce",
                "turn_relation": "new_task",
                "solution_pressure": "complete_solution",
                "retrieval_intents": [
                    {"intent": "defect_localization", "priority": "primary"},
                    {"intent": "behavior_explanation", "priority": "secondary"},
                ],
                "primary_expected_output": "patch",
                "expected_outputs": ["diagnosis", "explanation", "patch"],
                "specificity": "medium",
                "explicit_targets": [{"target_type": "function", "value": "saveUser"}],
                "confidence": 0.83,
                "classification_basis": ["User asks for a bug fix and explanation."],
            }

        result = classify_intent(
            IntentClassificationInput(user_prompt="Find why saveUser fails, explain it, and patch it."),
            llm_config=_LLMConfig(),
            complete_json_fn=completion,
        )

        self.assertEqual(result.status, "success")
        self.assertFalse(result.fallback_used)
        self.assertIsNotNone(result.classification)
        assert result.classification is not None
        self.assertEqual(result.classification.primary_expected_output.value, "patch")
        self.assertEqual([output.value for output in result.classification.expected_outputs], ["diagnosis", "explanation", "patch"])
        self.assertEqual(result.classification.retrieval_intents[0].intent.value, "defect_localization")

    def test_classifier_failure_is_explicit_without_fallback(self) -> None:
        def completion(_config: Any, _messages: object, **_kwargs: object) -> Mapping[str, Any]:
            raise RuntimeError("classifier unavailable")

        result = classify_intent(
            IntentClassificationInput(user_prompt="Why?"),
            llm_config=_LLMConfig(),
            complete_json_fn=completion,
        )

        self.assertEqual(result.status, "failed")
        self.assertIsNone(result.classification)
        self.assertFalse(result.fallback_used)
        self.assertIn("classifier unavailable", result.error or "")

    def test_build_retrieval_hints_from_normalized_intent(self) -> None:
        normalized = normalize_intent(
            IntentClassification(
                user_goals=(UserGoal.UNDERSTAND, UserGoal.PLAN),
                response_operation=ResponseOperation.EXPLAIN,
                turn_relation=TurnRelation.NEW_TASK,
                solution_pressure=SolutionPressure.GUIDANCE,
                retrieval_intents=(RankedRetrievalIntent(RetrievalIntent.BEHAVIOR_EXPLANATION, "primary"),),
                primary_expected_output=ExpectedOutput.EXPLANATION,
                expected_outputs=(ExpectedOutput.EXPLANATION, ExpectedOutput.IMPLEMENTATION_PLAN),
                specificity=Specificity.MEDIUM,
                explicit_targets=(TargetReference(TargetType.FILE, "src/compiler/checker.ts"),),
                confidence=0.84,
                classification_basis=("User asks for code context.",),
            ),
            user_prompt="Explain src/compiler/checker.ts.",
        )

        hints = build_retrieval_hints(normalized)

        self.assertEqual(hints.product_boundary, "explain_plan_suggest_only")
        self.assertEqual(hints.retrieval_intents[0]["intent"], "behavior_explanation")
        self.assertEqual(hints.response_operation, "explain")
        self.assertEqual(hints.primary_expected_output, "explanation")
        self.assertEqual(hints.expected_outputs, ("explanation", "implementation_plan"))
        self.assertEqual(hints.explicit_targets[0]["value"], "src/compiler/checker.ts")

    def test_normalizer_records_structural_corrections(self) -> None:
        classification = IntentClassification(
            user_goals=(UserGoal.UNDERSTAND, UserGoal.UNDERSTAND),
            response_operation=ResponseOperation.PRODUCE,
            turn_relation=TurnRelation.ANSWER_TO_CHECK,
            solution_pressure=SolutionPressure.NONE,
            retrieval_intents=(
                RankedRetrievalIntent(RetrievalIntent.BEHAVIOR_EXPLANATION, "primary"),
                RankedRetrievalIntent(RetrievalIntent.BEHAVIOR_EXPLANATION, "secondary"),
            ),
            primary_expected_output=ExpectedOutput.EXPLANATION,
            expected_outputs=(ExpectedOutput.EXPLANATION, ExpectedOutput.EXPLANATION),
            specificity=Specificity.MEDIUM,
            explicit_targets=(
                TargetReference(TargetType.FILE, "src/real.ts"),
                TargetReference(TargetType.FILE, "src/invented.ts"),
            ),
            confidence=0.7,
            classification_basis=("User asks for explanation.",),
        )

        normalized = normalize_intent(
            classification,
            user_prompt="Explain src/real.ts.",
            active_understanding_check=False,
        )

        self.assertEqual(normalized.classification.response_operation, ResponseOperation.EXPLAIN)
        self.assertEqual(normalized.classification.turn_relation, TurnRelation.CLARIFY)
        self.assertEqual([target.value for target in normalized.classification.explicit_targets], ["src/real.ts"])
        self.assertIn("corrected_produce_without_producible_primary_output", normalized.corrections)
        self.assertIn("corrected_answer_to_check_without_active_check", normalized.corrections)
        self.assertIn("removed_nonliteral_explicit_targets", normalized.corrections)
        self.assertIn("deduplicated_retrieval_intents", normalized.corrections)

    def test_agreement_marks_behavior_explanation_and_defect_localization_compatible(self) -> None:
        classification = IntentClassification(
            user_goals=(UserGoal.UNDERSTAND, UserGoal.DEBUG),
            response_operation=ResponseOperation.EXPLAIN,
            turn_relation=TurnRelation.NEW_TASK,
            solution_pressure=SolutionPressure.NONE,
            retrieval_intents=(RankedRetrievalIntent(RetrievalIntent.BEHAVIOR_EXPLANATION, "primary"),),
            primary_expected_output=ExpectedOutput.EXPLANATION,
            expected_outputs=(ExpectedOutput.EXPLANATION,),
            specificity=Specificity.MEDIUM,
            explicit_targets=(),
            confidence=0.9,
            classification_basis=("User asks why behavior occurs.",),
        )
        retrieval_result = RetrievalResult(
            evidence=(),
            coverage_status="missing",
            sufficient=False,
            retrieval_summary={"retrieval_plan": {"primary_intent": "defect_localization"}},
        )

        agreement = assess_intent_agreement(
            classification=classification,
            retrieval_result=retrieval_result,
            legacy_user_intent=UserIntent.UNDERSTAND_CODE,
        )

        self.assertEqual(agreement.agreement, "compatible")
        self.assertEqual(agreement.top_level_primary, "behavior_explanation")
        self.assertEqual(agreement.workspace_primary, "defect_localization")

    def test_agreement_uses_codex_issue_analysis_when_workspace_intent_absent(self) -> None:
        classification = IntentClassification(
            user_goals=(UserGoal.UNDERSTAND,),
            response_operation=ResponseOperation.EXPLAIN,
            turn_relation=TurnRelation.NEW_TASK,
            solution_pressure=SolutionPressure.NONE,
            retrieval_intents=(RankedRetrievalIntent(RetrievalIntent.BEHAVIOR_EXPLANATION, "primary"),),
            primary_expected_output=ExpectedOutput.EXPLANATION,
            expected_outputs=(ExpectedOutput.EXPLANATION,),
            specificity=Specificity.MEDIUM,
            explicit_targets=(),
            confidence=0.9,
            classification_basis=("User asks to understand compatibility behavior.",),
        )
        retrieval_result = RetrievalResult(
            evidence=(),
            coverage_status="missing",
            sufficient=False,
            retrieval_summary={"profile_output": {"issue_analysis": {"issue_type": "compatibility"}}},
        )

        agreement = assess_intent_agreement(
            classification=classification,
            retrieval_result=retrieval_result,
            legacy_user_intent=UserIntent.UNDERSTAND_CODE,
        )

        self.assertEqual(agreement.agreement, "compatible")
        self.assertEqual(agreement.codex_issue_type, "compatibility")
        self.assertIn("top_level_compatible_with_codex_issue_type", agreement.notes)

    def test_agreement_treats_repository_exploration_bug_as_compatible_for_explanation_context(self) -> None:
        classification = IntentClassification(
            user_goals=(UserGoal.UNDERSTAND,),
            response_operation=ResponseOperation.EXPLAIN,
            turn_relation=TurnRelation.NEW_TASK,
            solution_pressure=SolutionPressure.NONE,
            retrieval_intents=(RankedRetrievalIntent(RetrievalIntent.REPOSITORY_EXPLORATION, "primary"),),
            primary_expected_output=ExpectedOutput.EXPLANATION,
            expected_outputs=(ExpectedOutput.EXPLANATION,),
            specificity=Specificity.MEDIUM,
            explicit_targets=(),
            confidence=0.95,
            classification_basis=("User asks for code context for a bug.",),
        )
        retrieval_result = RetrievalResult(
            evidence=(),
            coverage_status="missing",
            sufficient=False,
            retrieval_summary={"profile_output": {"issue_analysis": {"issue_type": "bug"}}},
        )

        agreement = assess_intent_agreement(
            classification=classification,
            retrieval_result=retrieval_result,
            legacy_user_intent=UserIntent.UNDERSTAND_CODE,
        )

        self.assertEqual(agreement.agreement, "compatible")
        self.assertIn("explanation_context_compatible_with_codex_issue_type", agreement.notes)

    def test_agreement_keeps_repository_exploration_bug_conflicting_for_patch_context(self) -> None:
        classification = IntentClassification(
            user_goals=(UserGoal.CHANGE,),
            response_operation=ResponseOperation.PRODUCE,
            turn_relation=TurnRelation.NEW_TASK,
            solution_pressure=SolutionPressure.COMPLETE_SOLUTION,
            retrieval_intents=(RankedRetrievalIntent(RetrievalIntent.REPOSITORY_EXPLORATION, "primary"),),
            primary_expected_output=ExpectedOutput.PATCH,
            expected_outputs=(ExpectedOutput.PATCH,),
            specificity=Specificity.MEDIUM,
            explicit_targets=(),
            confidence=0.9,
            classification_basis=("User asks for a patch.",),
        )
        retrieval_result = RetrievalResult(
            evidence=(),
            coverage_status="missing",
            sufficient=False,
            retrieval_summary={"profile_output": {"issue_analysis": {"issue_type": "bug"}}},
        )

        agreement = assess_intent_agreement(
            classification=classification,
            retrieval_result=retrieval_result,
            legacy_user_intent=UserIntent.UNDERSTAND_CODE,
        )

        self.assertEqual(agreement.agreement, "conflicting")
        self.assertIn("top_level_not_explained_by_codex_issue_type", agreement.notes)

    def test_agreement_treats_behavior_explanation_feature_request_as_compatible(self) -> None:
        classification = IntentClassification(
            user_goals=(UserGoal.UNDERSTAND,),
            response_operation=ResponseOperation.EXPLAIN,
            turn_relation=TurnRelation.NEW_TASK,
            solution_pressure=SolutionPressure.NONE,
            retrieval_intents=(RankedRetrievalIntent(RetrievalIntent.BEHAVIOR_EXPLANATION, "primary"),),
            primary_expected_output=ExpectedOutput.EXPLANATION,
            expected_outputs=(ExpectedOutput.EXPLANATION,),
            specificity=Specificity.MEDIUM,
            explicit_targets=(),
            confidence=0.9,
            classification_basis=("User asks for code context for a feature request.",),
        )
        retrieval_result = RetrievalResult(
            evidence=(),
            coverage_status="missing",
            sufficient=False,
            retrieval_summary={"profile_output": {"issue_analysis": {"issue_type": "feature_request"}}},
        )

        agreement = assess_intent_agreement(
            classification=classification,
            retrieval_result=retrieval_result,
            legacy_user_intent=UserIntent.UNDERSTAND_CODE,
        )

        self.assertEqual(agreement.agreement, "compatible")
        self.assertIn("explanation_context_compatible_with_codex_issue_type", agreement.notes)

if __name__ == "__main__":
    unittest.main()
