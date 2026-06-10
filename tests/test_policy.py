from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from core.control_layer import ControlLayer
from core.logging_schema import LogEventType
from core.models import ConversationState, EvidenceItem, ResponseMode, RetrievalResult, UserIntent
from core.policy import PolicyStage
from core.source_policy import DEFAULT_ALLOWED_SOURCE_CATEGORIES, SourceCategory, SourcePolicy
from core.stages import ResponseStage
from core.transitions import can_transition
from core.violations import PolicyViolationType
from services.response_generation.explanation import prompt_sources_path
from services.retrieval.config import RunLLMConfig
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
        self.assertEqual(result.response_plan.required_sections, ("generated_explanation",))
        self.assertEqual(result.response_plan.notes["prompt_template_id"], "explanation_markdown_v2")
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

    def test_explanation_response_renders_linked_evidence_sections(self) -> None:
        retrieval = _StubRetrievalService(
            RetrievalResult(
                evidence=(
                    EvidenceItem(
                        source_category=SourceCategory.SOURCE_CODE,
                        source_id="repo-pre:src/compiler/checker.ts:L4242-L4321",
                        snippet="function checkClassLikeDeclaration(node) {\n  return Diagnostics.Abstract_class;\n}",
                        rank=1,
                        metadata={
                            "path": "src/compiler/checker.ts",
                            "coverage_area": "validation_checking",
                            "retrieval_path": "direct_owner_file",
                        },
                    ),
                ),
                coverage_status="partial",
                sufficient=False,
                retrieval_summary={
                    "deterministic_coverage_gate": {
                        "satisfied": False,
                        "missing_roles": ["input_parsing"],
                        "reasons": ["input_parsing:no_strong_satisfying_candidate"],
                    }
                },
            )
        )
        control_layer = ControlLayer(policy_stage=PolicyStage(), retrieval_stage=retrieval, logger=_InMemoryLogger())

        result = control_layer.run(
            ConversationState(
                conversation_id="test-linked-response",
                user_input="Explain abstract class handling.",
                current_stage=ResponseStage.EXPLAIN,
                intent=UserIntent.UNDERSTAND_CODE,
            )
        )

        content = result.response_payload.content
        self.assertEqual(content, "**Error**\nExplanation generation requires a configured LLM. No response LLM configuration is available.")
        self.assertEqual(result.response_payload.metadata["error"], "missing_llm_config")

    def test_explanation_mode_uses_llm_generation_when_configured(self) -> None:
        retrieval = _StubRetrievalService(
            RetrievalResult(
                evidence=(
                    EvidenceItem(
                        source_category=SourceCategory.SOURCE_CODE,
                        source_id="repo-pre:src/compiler/checker.ts:L4242-L4321",
                        snippet="function checkClassLikeDeclaration(node) {\n  return Diagnostics.Abstract_class;\n}",
                        rank=1,
                        metadata={"path": "src/compiler/checker.ts", "coverage_area": "validation_checking"},
                    ),
                ),
                coverage_status="partial",
                sufficient=False,
                retrieval_summary={"deterministic_coverage_gate": {"satisfied": False, "missing_roles": ["input_parsing"], "reasons": []}},
            )
        )
        logger = _InMemoryLogger()
        with _fake_llm_server(
            [
                {
                    "markdown": "# Bottom line\n\nThe main enforcement point is [src/compiler/checker.ts:L4242-L4321](src/compiler/checker.ts#L4242-L4321).",
                    "used_evidence_refs": ["repo-pre:src/compiler/checker.ts:L4242-L4321"],
                    "render_notes": {"title": "Bottom line", "summary": "Checker enforces abstract rules."},
                }
            ]
        ) as server_url:
            control_layer = ControlLayer(
                policy_stage=PolicyStage(),
                retrieval_stage=retrieval,
                logger=logger,
                response_llm_config=_llm_config(server_url),
            )

            result = control_layer.run(
                ConversationState(
                    conversation_id="test-llm-explanation",
                    user_input="Explain abstract class handling.",
                    current_stage=ResponseStage.EXPLAIN,
                    intent=UserIntent.UNDERSTAND_CODE,
                )
            )

        self.assertEqual(result.response_payload.content, "# Bottom line\n\nThe main enforcement point is [src/compiler/checker.ts:L4242-L4321](src/compiler/checker.ts#L4242-L4321).")
        self.assertEqual(
            result.response_payload.evidence_refs,
            ("repo-pre:src/compiler/checker.ts:L4242-L4321",),
        )
        self.assertEqual(result.response_payload.metadata["generator"], "llm_explanation")
        self.assertIn(LogEventType.RESPONSE_GENERATION_REQUESTED, [event.event_type for event in logger.events])
        self.assertIn(LogEventType.RESPONSE_GENERATION_RECEIVED, [event.event_type for event in logger.events])

    def test_explanation_llm_failure_returns_error_response(self) -> None:
        retrieval = _StubRetrievalService()
        logger = _InMemoryLogger()
        with _fake_llm_server(["not json"]) as server_url:
            control_layer = ControlLayer(
                policy_stage=PolicyStage(),
                retrieval_stage=retrieval,
                logger=logger,
                response_llm_config=_llm_config(server_url),
            )
            result = control_layer.run(
                ConversationState(
                    conversation_id="test-llm-error",
                    user_input="Explain the policy flow.",
                    current_stage=ResponseStage.EXPLAIN,
                    intent=UserIntent.UNDERSTAND_CODE,
                )
            )

        self.assertIn("**Error**", result.response_payload.content)
        self.assertIn("Explanation generation failed:", result.response_payload.content)
        self.assertIn(LogEventType.RESPONSE_GENERATION_FAILED, [event.event_type for event in logger.events])
        self.assertIn("valid JSON", result.response_payload.metadata["error"])

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

    def test_reasoning_question_mode_stays_deterministic_when_llm_configured(self) -> None:
        logger = _InMemoryLogger()
        with _fake_llm_server([]) as server_url:
            control_layer = ControlLayer(
                policy_stage=PolicyStage(),
                retrieval_stage=_StubRetrievalService(),
                logger=logger,
                response_llm_config=_llm_config(server_url),
            )
            result = control_layer.run(
                ConversationState(
                    conversation_id="test-ask-deterministic",
                    user_input="What should I inspect next?",
                    current_stage=ResponseStage.ASK,
                    intent=UserIntent.UNDERSTAND_CODE,
                    evidence=DEFAULT_STUB_EVIDENCE,
                    stage_history=(ResponseStage.EXPLAIN, ResponseStage.ASK),
                )
            )

        self.assertEqual(result.response_plan.mode, ResponseMode.REASONING_QUESTION)
        self.assertIn("**Question**", result.response_payload.content)
        self.assertNotIn(LogEventType.RESPONSE_GENERATION_REQUESTED, [event.event_type for event in logger.events])

    def test_prompt_sources_note_is_checked_in(self) -> None:
        content = prompt_sources_path().read_text(encoding="utf-8")
        self.assertIn("digital.gov/guides/plain-language/principles/write-for-reader/", content)
        self.assertIn("link.springer.com/article/10.1007/s10648-010-9145-4", content)


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

class _FakeLLMHandler(BaseHTTPRequestHandler):
    response_payloads: list[object] = []

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        content = self.response_payloads.pop(0)
        if not isinstance(content, str):
            content = json.dumps(content)
        body = json.dumps({"choices": [{"message": {"content": content}}]}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        return


class _fake_llm_server:
    def __init__(self, response_payloads: list[object]) -> None:
        self.response_payloads = response_payloads
        self.server: HTTPServer | None = None
        self.thread: threading.Thread | None = None

    def __enter__(self) -> str:
        _FakeLLMHandler.response_payloads = list(self.response_payloads)
        self.server = HTTPServer(("127.0.0.1", 0), _FakeLLMHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        return f"http://{host}:{port}/v1/chat/completions"

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        if self.thread is not None:
            self.thread.join(timeout=2)


def _llm_config(server_url: str) -> RunLLMConfig:
    return RunLLMConfig(
        api_style="openai_chat_completions",
        model="test-model",
        endpoint_url=server_url,
        api_key="test-key",
    )


if __name__ == "__main__":
    unittest.main()
