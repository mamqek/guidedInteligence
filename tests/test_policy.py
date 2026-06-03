from __future__ import annotations

import unittest

from core.control_layer import ControlLayer
from core.logging_schema import LogEventType
from core.models import ConversationState, EvidenceItem, ResponseMode, RetrievalResult, UserIntent
from core.policy import PolicyStage
from core.source_policy import DEFAULT_ALLOWED_SOURCE_CATEGORIES, SourceCategory, SourcePolicy
from core.stages import ResponseStage
from core.transitions import can_transition
from core.violations import PolicyViolationType
from step3_harness_scenarios import DEFAULT_STUB_EVIDENCE, SCENARIOS


class _StubRetrievalService:
    def __init__(self, retrieval_result: RetrievalResult | None = None) -> None:
        self.calls: list[tuple[ConversationState, object]] = []
        self.retrieval_result = retrieval_result or RetrievalResult(
            evidence=DEFAULT_STUB_EVIDENCE,
            coverage_status="strong",
            sufficient=True,
            retrieval_summary={"source": "stub"},
        )

    def retrieve(self, state: ConversationState, policy_result: object) -> RetrievalResult:
        self.calls.append((state, policy_result))
        return self.retrieval_result


class _InMemoryLogger:
    def __init__(self) -> None:
        self.events: list[object] = []

    def record(self, event: object) -> None:
        self.events.append(event)


class ControlLayerPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.logger = _InMemoryLogger()
        self.retrieval = _StubRetrievalService()
        self.control_layer = ControlLayer(policy_stage=PolicyStage(), retrieval_stage=self.retrieval, logger=self.logger)

    def test_explanation_flow_creates_response_plan_with_evidence_sections(self) -> None:
        state = ConversationState(
            conversation_id="test-explanation-contract",
            user_input="Explain how the policy chooses a stage.",
            current_stage=ResponseStage.EXPLAIN,
            intent=UserIntent.UNDERSTAND_CODE,
        )
        result = self.control_layer.run(state)

        self.assertEqual(result.active_stage, ResponseStage.EXPLAIN)
        self.assertEqual(result.next_stage, ResponseStage.ASK)
        self.assertEqual(result.response_plan.mode, ResponseMode.EXPLANATION)
        self.assertEqual(
            result.response_plan.required_sections,
            (
                "summary",
                "evidence",
                "reasoning_path",
                "confirmed_from_evidence",
                "hypotheses_to_investigate",
                "knowledge_check_question",
            ),
        )
        self.assertEqual(len(self.retrieval.calls), 1)
        self.assertEqual(
            [event.event_type for event in self.logger.events],
            [
                LogEventType.RUN_STARTED,
                LogEventType.STAGE_DECISION,
                LogEventType.RETRIEVAL_PLAN,
                LogEventType.EVIDENCE_SELECTED,
                LogEventType.RESPONSE_PLAN,
                LogEventType.PROMPT_PAYLOAD,
                LogEventType.RESPONSE_PAYLOAD,
                LogEventType.RUN_COMPLETED,
            ],
        )

    def test_default_policy_engine_uses_v1_default_source_categories(self) -> None:
        state = ConversationState(
            conversation_id="test-default-source-policy",
            user_input="Explain this issue.",
            current_stage=ResponseStage.EXPLAIN,
            intent=UserIntent.UNDERSTAND_CODE,
        )

        result = self.control_layer.run(state)

        self.assertEqual(result.allowed_sources, DEFAULT_ALLOWED_SOURCE_CATEGORIES)
        self.assertEqual(result.policy_result.source_policy_name, "v1_default")

    def test_custom_source_policy_controls_allowed_sources(self) -> None:
        source_policy = SourcePolicy(
            allowed_categories=(SourceCategory.ISSUE_TRACKER, SourceCategory.SOURCE_CODE),
            policy_name="coderepoqa_explain_initial",
        )
        control_layer = ControlLayer(
            policy_stage=PolicyStage(source_policy=source_policy),
            retrieval_stage=_StubRetrievalService(),
            logger=_InMemoryLogger(),
        )

        result = control_layer.run(
            ConversationState(
                conversation_id="test-custom-source-policy",
                user_input="Explain this historical issue from the initial issue and repo snapshot.",
                current_stage=ResponseStage.EXPLAIN,
                intent=UserIntent.UNDERSTAND_CODE,
            ),
        )

        self.assertEqual(result.allowed_sources, source_policy.allowed_categories)
        self.assertEqual(result.policy_result.source_policy_name, "coderepoqa_explain_initial")

    def test_custom_source_policy_rejects_evidence_outside_policy(self) -> None:
        source_policy = SourcePolicy(
            allowed_categories=(SourceCategory.ISSUE_TRACKER, SourceCategory.SOURCE_CODE),
            policy_name="coderepoqa_explain_initial",
        )
        control_layer = ControlLayer(
            policy_stage=PolicyStage(source_policy=source_policy),
            retrieval_stage=_StubRetrievalService(),
            logger=_InMemoryLogger(),
        )

        result = control_layer.run(
            ConversationState(
                conversation_id="test-custom-source-policy-violation",
                user_input="Explain this historical issue.",
                current_stage=ResponseStage.EXPLAIN,
                intent=UserIntent.UNDERSTAND_CODE,
                evidence=(
                    EvidenceItem(
                        source_category=SourceCategory.PULL_REQUEST,
                        source_id="hidden:pr-3579",
                        snippet="Hidden resolution context must not be visible in the initial explain stage.",
                    ),
                ),
            ),
        )

        self.assertFalse(result.policy_result.allowed)
        self.assertEqual(result.allowed_sources, source_policy.allowed_categories)
        self.assertEqual(
            tuple(violation.violation_type for violation in result.violations),
            (PolicyViolationType.UNSUPPORTED_SOURCE_USAGE,),
        )

    def test_direct_solution_freezes_current_stage_with_boundary_response_mode(self) -> None:
        result = self.control_layer.run(
            ConversationState(
                conversation_id="test-direct-solution",
                user_input="Just solve it and give me the answer.",
                current_stage=ResponseStage.EXPLAIN,
                intent=UserIntent.UNKNOWN,
            ),
        )

        self.assertFalse(result.policy_result.allowed)
        self.assertEqual(result.active_stage, ResponseStage.EXPLAIN)
        self.assertEqual(result.next_stage, ResponseStage.EXPLAIN)
        self.assertFalse(result.policy_result.retrieval_required)
        self.assertEqual(result.response_plan.mode, ResponseMode.BOUNDARY)
        self.assertEqual(
            tuple(violation.violation_type for violation in result.violations),
            (PolicyViolationType.DIRECT_SOLUTION_REQUEST,),
        )
        self.assertEqual(
            result.response_plan.required_sections,
            ("boundary", "expected_current_stage", "violation_explanation", "choices"),
        )
        self.assertFalse(result.response_plan.must_include_evidence)

    def test_stage_skipping_freezes_at_last_valid_stage(self) -> None:
        result = self.control_layer.run(
            ConversationState(
                conversation_id="test-stage-skipping",
                user_input="Give me a hint now.",
                current_stage=ResponseStage.HINT,
                intent=UserIntent.UNDERSTAND_CODE,
                stage_history=(ResponseStage.EXPLAIN,),
            ),
        )

        self.assertFalse(result.policy_result.allowed)
        self.assertEqual(result.active_stage, ResponseStage.EXPLAIN)
        self.assertEqual(result.next_stage, ResponseStage.EXPLAIN)
        self.assertFalse(result.policy_result.retrieval_required)
        self.assertEqual(result.response_plan.mode, ResponseMode.BOUNDARY)
        self.assertEqual(
            tuple(violation.violation_type for violation in result.violations),
            (PolicyViolationType.STAGE_SKIPPING,),
        )

    def test_existing_evidence_skips_retrieval_stage(self) -> None:
        logger = _InMemoryLogger()
        retrieval = _StubRetrievalService()
        control_layer = ControlLayer(policy_stage=PolicyStage(), retrieval_stage=retrieval, logger=logger)
        result = control_layer.run(
            ConversationState(
                conversation_id="test-existing-evidence",
                user_input="Explain this issue.",
                current_stage=ResponseStage.EXPLAIN,
                intent=UserIntent.UNDERSTAND_CODE,
                evidence=DEFAULT_STUB_EVIDENCE,
            ),
        )

        self.assertEqual(len(retrieval.calls), 0)
        self.assertTrue(result.retrieval_result is not None)
        self.assertEqual(result.retrieval_result.coverage_status, "state_evidence")
        retrieval_event = [event for event in logger.events if event.event_type == LogEventType.RETRIEVAL_PLAN][-1]
        self.assertEqual(retrieval_event.payload["action"], "skip_existing_evidence")


class TransitionTests(unittest.TestCase):
    def test_hint_to_ask_is_disallowed(self) -> None:
        self.assertFalse(can_transition(ResponseStage.HINT, ResponseStage.ASK))

    def test_explain_to_hint_is_still_disallowed(self) -> None:
        self.assertFalse(can_transition(ResponseStage.EXPLAIN, ResponseStage.HINT))


class ScenarioFixtureTests(unittest.TestCase):
    def test_step3_scenarios_match_policy(self) -> None:
        engine = PolicyStage()

        for scenario in SCENARIOS:
            with self.subTest(scenario_id=scenario.scenario_id):
                result = engine.decide(scenario.state)
                expected = scenario.expected_policy

                self.assertEqual(result.allowed, expected.allowed)
                self.assertEqual(result.active_stage, expected.active_stage)
                self.assertEqual(result.next_stage, expected.next_stage)
                self.assertEqual(result.intent, expected.intent)
                self.assertEqual(result.retrieval_required, expected.retrieval_required)
                self.assertEqual(result.response_mode, expected.response_mode)
                self.assertEqual(result.allowed_sources, expected.allowed_sources)
                self.assertEqual(
                    tuple(violation.violation_type for violation in result.violations),
                    expected.violations,
                )


if __name__ == "__main__":
    unittest.main()
