from __future__ import annotations

import unittest

from core.models import ConversationState, UserIntent
from core.policy import V1PolicyEngine
from core.response_contracts import ResponseTemplate, contract_for_decision
from core.stages import ResponseStage
from core.transitions import can_transition
from core.violations import PolicyViolationType
from step3_harness_scenarios import SCENARIOS


class PolicyContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = V1PolicyEngine()

    def test_explanation_contract_ends_with_knowledge_check_question(self) -> None:
        decision = self.engine.decide(
            ConversationState(
                conversation_id="test-explanation-contract",
                user_input="Explain how the policy chooses a stage.",
                current_stage=ResponseStage.EXPLAIN,
                intent=UserIntent.UNDERSTAND_CODE,
            )
        )

        contract = contract_for_decision(decision)

        self.assertEqual(decision.current_stage, ResponseStage.EXPLAIN)
        self.assertEqual(decision.next_stage, ResponseStage.ASK)
        self.assertEqual(contract.template, ResponseTemplate.EXPLANATION)
        self.assertIn("knowledge_check_question", contract.required_sections)

    def test_direct_solution_recovers_through_ask_stage_questioning(self) -> None:
        decision = self.engine.decide(
            ConversationState(
                conversation_id="test-direct-solution",
                user_input="Just solve it and give me the answer.",
                current_stage=ResponseStage.EXPLAIN,
                intent=UserIntent.UNKNOWN,
            )
        )

        contract = contract_for_decision(decision)

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.current_stage, ResponseStage.ASK)
        self.assertEqual(decision.next_stage, ResponseStage.HINT)
        self.assertFalse(decision.retrieval_required)
        self.assertEqual(decision.response_template_id, ResponseTemplate.BOUNDARY_CHECK_QUESTION.value)
        self.assertEqual(
            tuple(violation.violation_type for violation in decision.violations),
            (PolicyViolationType.DIRECT_SOLUTION_REQUEST,),
        )
        self.assertEqual(contract.template, ResponseTemplate.BOUNDARY_CHECK_QUESTION)
        self.assertEqual(contract.required_sections, ("boundary", "knowledge_check_question"))
        self.assertFalse(contract.must_include_evidence)

    def test_stage_skipping_recovers_through_ask_stage_questioning(self) -> None:
        decision = self.engine.decide(
            ConversationState(
                conversation_id="test-stage-skipping",
                user_input="Give me a hint now.",
                current_stage=ResponseStage.HINT,
                intent=UserIntent.UNDERSTAND_CODE,
                stage_history=(ResponseStage.EXPLAIN,),
            )
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.current_stage, ResponseStage.ASK)
        self.assertEqual(decision.next_stage, ResponseStage.HINT)
        self.assertFalse(decision.retrieval_required)
        self.assertEqual(decision.response_template_id, ResponseTemplate.BOUNDARY_CHECK_QUESTION.value)
        self.assertEqual(
            tuple(violation.violation_type for violation in decision.violations),
            (PolicyViolationType.STAGE_SKIPPING,),
        )


class TransitionTests(unittest.TestCase):
    def test_hint_to_ask_recovery_is_allowed(self) -> None:
        self.assertTrue(can_transition(ResponseStage.HINT, ResponseStage.ASK))

    def test_explain_to_hint_is_still_disallowed(self) -> None:
        self.assertFalse(can_transition(ResponseStage.EXPLAIN, ResponseStage.HINT))


class ScenarioFixtureTests(unittest.TestCase):
    def test_step3_scenarios_match_policy(self) -> None:
        engine = V1PolicyEngine()

        for scenario in SCENARIOS:
            with self.subTest(scenario_id=scenario.scenario_id):
                decision = engine.decide(scenario.state)
                expected = scenario.expected_decision

                self.assertEqual(decision.allowed, expected.allowed)
                self.assertEqual(decision.current_stage, expected.current_stage)
                self.assertEqual(decision.next_stage, expected.next_stage)
                self.assertEqual(decision.intent, expected.intent)
                self.assertEqual(decision.retrieval_required, expected.retrieval_required)
                self.assertEqual(decision.response_template_id, expected.response_template_id)
                self.assertEqual(decision.allowed_sources, expected.allowed_sources)
                self.assertEqual(
                    tuple(violation.violation_type for violation in decision.violations),
                    expected.violations,
                )


if __name__ == "__main__":
    unittest.main()
