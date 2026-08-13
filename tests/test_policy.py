from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.control_layer import ControlLayer
from core.logging_schema import LogEventType
from core.models import AssistanceRequestType, ConversationState, EvidenceItem, ResponsePayload, RetrievalResult, TurnType
from core.policy import PolicyStage
from core.source_policy import DEFAULT_ALLOWED_SOURCE_CATEGORIES, SourceCategory, SourcePolicy
from services.comprehension.followup import build_teaching_state
from services.guidance.answer_evaluation import evaluate_answers
from services.intent.logging import IntentStageResult
from services.intent.models import (
    IntentClassification,
    SolutionPressure,
    Specificity,
    TargetState,
    TaskIntent,
    TurnRelation,
)
from step3_harness_scenarios import SCENARIOS


class _StubRetrievalService:
    def __init__(self, result: RetrievalResult | None = None) -> None:
        self.calls: list[ConversationState] = []
        self.result = result or RetrievalResult(
            evidence=(EvidenceItem(SourceCategory.SOURCE_CODE, "repo:a.py:L1-L4", "def f(): pass"),),
            coverage_status="strong",
            sufficient=True,
            retrieval_summary={"source": "stub"},
        )

    def retrieve(self, state: ConversationState, _policy_result: object) -> RetrievalResult:
        self.calls.append(state)
        return self.result


class _Logger:
    def __init__(self) -> None:
        self.events: list[object] = []

    def record(self, event: object) -> None:
        self.events.append(event)


class ControlLayerPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.retrieval = _StubRetrievalService()
        self.logger = _Logger()
        self.control = ControlLayer(
            policy_stage=PolicyStage(),
            retrieval_stage=self.retrieval,
            logger=self.logger,
            intent_enabled=False,
        )

    def test_guided_request_builds_response_plan_and_retrieves(self) -> None:
        result = self.control.run(_state("Explain how the policy chooses a turn."))
        self.assertEqual(result.turn_type, TurnType.GUIDED_EXPLANATION)
        self.assertEqual(result.response_plan.required_sections, ("generated_explanation", "understanding_checks"))
        self.assertEqual(result.response_plan.notes["prompt_template_id"], "intent_composed_explanation_v5")
        self.assertEqual(len(self.retrieval.calls), 1)
        self.assertEqual(result.response_payload.metadata["error"], "missing_llm_config")

    def test_response_generation_can_be_skipped_without_skipping_retrieval_evidence(self) -> None:
        control = ControlLayer(
            policy_stage=PolicyStage(),
            retrieval_stage=self.retrieval,
            logger=self.logger,
            intent_enabled=False,
            response_generation_enabled=False,
        )
        with patch("core.control_layer._render_response") as render_response:
            result = control.run(_state("Explain how the policy chooses a turn."))

        render_response.assert_not_called()
        self.assertEqual(result.evidence, self.retrieval.result.evidence)
        self.assertEqual(result.response_payload.content, "")
        self.assertEqual(
            result.response_payload.metadata["generator"],
            "explicitly_skipped",
        )

    def test_active_intent_classification_passes_only_minimal_context_to_retrieval(self) -> None:
        classification = IntentClassification(
            intents=(TaskIntent.EXPLAIN, TaskIntent.EXPLORE),
            turn_relation=TurnRelation.NEW_TASK,
            solution_pressure=SolutionPressure.NONE,
            specificity=Specificity.MEDIUM,
            target_state=TargetState.UNRESOLVED,
            explicit_targets=(),
            confidence=0.9,
            classification_basis=("asks how and where",),
        )
        stage_result = IntentStageResult("success", classification, None, False, 1, "test")
        control = ControlLayer(
            policy_stage=PolicyStage(),
            retrieval_stage=self.retrieval,
            logger=self.logger,
            response_llm_config=object(),
            intent_enabled=True,
        )
        with patch("core.control_layer.classify_intent", return_value=stage_result), patch(
            "core.control_layer._render_response",
            return_value=ResponsePayload(TurnType.GUIDED_EXPLANATION, "ok"),
        ):
            result = control.run(_state("Show where authentication lives and explain it."))

        context = self.retrieval.calls[0].intent_context.to_dict()
        self.assertEqual([item["intent"] for item in context["intents"]], ["explain", "explore"])
        self.assertNotIn("stages", str(context))
        event_types = [event.event_type for event in self.logger.events]
        self.assertIn(LogEventType.INTENT_CLASSIFICATION, event_types)
        self.assertIn(LogEventType.INTENT_NORMALIZATION, event_types)
        self.assertEqual(result.run_trace_summary["intents"], ["explain", "explore"])

    def test_intent_classification_failure_stops_before_retrieval(self) -> None:
        failed = IntentStageResult("failed", None, "bad output", False, 1, "test")
        control = ControlLayer(
            policy_stage=PolicyStage(),
            retrieval_stage=self.retrieval,
            response_llm_config=object(),
        )
        with patch("core.control_layer.classify_intent", return_value=failed):
            with self.assertRaisesRegex(RuntimeError, "Intent classification failed"):
                control.run(_state("Explain this."))
        self.assertEqual(self.retrieval.calls, [])

    def test_direct_solution_request_returns_boundary_without_retrieval(self) -> None:
        result = self.control.run(
            ConversationState("boundary", "Implement this for me.", assistance_request=AssistanceRequestType.DIRECT_SOLUTION_REQUEST)
        )
        self.assertEqual(result.turn_type, TurnType.BOUNDARY)
        self.assertEqual(self.retrieval.calls, [])

    def test_existing_evidence_skips_retrieval(self) -> None:
        evidence = (EvidenceItem(SourceCategory.SOURCE_CODE, "repo:a.py:L1", "x = 1"),)
        state = ConversationState("existing", "Continue.", assistance_request=AssistanceRequestType.FOLLOW_UP, evidence=evidence)
        result = self.control.run(state)
        self.assertEqual(self.retrieval.calls, [])
        self.assertEqual(result.retrieval_result.evidence, evidence)

    def test_default_policy_uses_v1_source_categories(self) -> None:
        decision = PolicyStage().decide(_state("Explain this."))
        self.assertEqual(decision.allowed_sources, DEFAULT_ALLOWED_SOURCE_CATEGORIES)

    def test_teaching_state_uses_question_targets_and_actual_missing_points(self) -> None:
        state = build_teaching_state(
            answer_flow={"ordered_stage_ids": ["debug.symptom", "debug.cause"]},
            checks=({"id": "q1", "target_stage_ids": ["debug.cause"], "evidence_refs": ["repo:a.py:L1-L4"]},),
            evaluations=({"question_id": "q1", "status": "partial", "feedback": "Missing cause", "repair_focus": "cause"},),
        )
        self.assertEqual(state.current_teaching_stage, "repair")
        self.assertEqual(state.target_stage_ids, ("debug.cause",))
        self.assertEqual(state.missing_points, ("cause",))

    def test_answer_evaluation_uses_expected_points_from_new_question_shape(self) -> None:
        response = {
            "evaluations": [{
                "question_id": "q1",
                "status": "correct",
                "matched_points": ["owner"],
                "missing_points": [],
                "feedback": "Correct.",
                "next_turn": "deepen",
                "repair_focus": "",
            }]
        }
        with patch("services.guidance.answer_evaluation.complete_json", return_value=response):
            evaluations = evaluate_answers(
                checks=({"id": "q1", "expected_answer_points": ["owner"]},),
                answers={"q1": "owner"},
                llm_config=object(),
            )
        self.assertEqual(evaluations[0].status, "correct")


class ScenarioFixtureTests(unittest.TestCase):
    def test_step3_scenarios_still_match_policy_boundaries(self) -> None:
        policy = PolicyStage()
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario.scenario_id):
                result = policy.decide(scenario.state)
                self.assertEqual(result.allowed, scenario.expected_policy.allowed)
                self.assertEqual(result.turn_type, scenario.expected_policy.turn_type)


def _state(prompt: str) -> ConversationState:
    return ConversationState("test", prompt, assistance_request=AssistanceRequestType.UNDERSTAND_CODE)


if __name__ == "__main__":
    unittest.main()
