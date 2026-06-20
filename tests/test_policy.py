from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from core.control_layer import ControlLayer
from core.logging_schema import LogEventType
from core.models import ConversationState, EvidenceItem, RetrievalResult, TurnType, UserIntent
from core.policy import PolicyStage
from core.source_policy import DEFAULT_ALLOWED_SOURCE_CATEGORIES, SourceCategory, SourcePolicy
from core.violations import PolicyViolationType
from services.guidance.answer_evaluation import evaluate_answers
from services.guidance.questions import build_question_contexts
from services.response_generation.explanation import _classify_prompt_terms, _validate_generation_response, prompt_sources_path
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

    def test_guided_explanation_flow_creates_response_plan_with_checks(self) -> None:
        state = ConversationState(
            conversation_id="test-guided-contract",
            user_input="Explain how the policy chooses a turn.",
            intent=UserIntent.UNDERSTAND_CODE,
        )
        result = self.control_layer.run(state)

        self.assertEqual(result.turn_type, TurnType.GUIDED_EXPLANATION)
        self.assertEqual(result.response_plan.turn_type, TurnType.GUIDED_EXPLANATION)
        self.assertEqual(result.response_plan.required_sections, ("generated_explanation", "understanding_checks"))
        self.assertEqual(result.response_plan.notes["prompt_template_id"], "explanation_markdown_v2")
        self.assertEqual(len(self.retrieval.calls), 1)
        self.assertEqual(
            [event.event_type for event in self.logger.events],
            [
                LogEventType.RUN_STARTED,
                LogEventType.TURN_DECISION,
                LogEventType.RETRIEVAL_PLAN,
                LogEventType.EVIDENCE_SELECTED,
                LogEventType.RESPONSE_PLAN,
                LogEventType.PROMPT_PAYLOAD,
                LogEventType.RESPONSE_PAYLOAD,
                LogEventType.RUN_COMPLETED,
            ],
        )

    def test_missing_llm_config_returns_explicit_error_response(self) -> None:
        result = self.control_layer.run(
            ConversationState(
                conversation_id="test-missing-llm",
                user_input="Explain abstract class handling.",
                intent=UserIntent.UNDERSTAND_CODE,
            )
        )

        self.assertEqual(result.response_payload.content, "**Error**\nExplanation generation requires a configured LLM. No response LLM configuration is available.")
        self.assertEqual(result.response_payload.metadata["error"], "missing_llm_config")

    def test_guided_explanation_uses_llm_generation_when_configured(self) -> None:
        retrieval = _StubRetrievalService(_retrieval_with_role_buckets())
        logger = _InMemoryLogger()
        with _fake_llm_server(
            [
                {
                    "markdown": "# Bottom line\n\nThe checker owns the rule at [src/compiler/checker.ts:L10-L12](src/compiler/checker.ts#L10-L12).",
                    "used_evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                    "understanding_checks": [
                        {
                            "id": "q1",
                            "role": "validation_checking",
                            "question_type": "primary",
                            "question": "Why is this checker path the main place to verify the rule?",
                            "expected_answer_points": ["It contains semantic validation.", "It reports the relevant diagnostic."],
                            "hint": "Look for the code path that turns parsed declarations into an error.",
                            "evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                            "origin": "main retrieved role",
                        }
                    ],
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
                    conversation_id="test-llm-guided",
                    user_input="Explain abstract class handling.",
                    intent=UserIntent.UNDERSTAND_CODE,
                )
            )

        checks = result.response_payload.metadata["understanding_checks"]
        self.assertEqual(result.response_payload.turn_type, TurnType.GUIDED_EXPLANATION)
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0]["id"], "q1")
        self.assertEqual(
            result.response_payload.evidence_refs,
            ("repo-pre:src/compiler/checker.ts:L10-L12",),
        )
        request_payload_events = [
            event for event in logger.events if event.event_type == LogEventType.RESPONSE_GENERATION_REQUEST_PAYLOAD
        ]
        self.assertEqual(len(request_payload_events), 1)
        implementation_context = request_payload_events[0].payload["payload"]["implementation_context"]
        request_payload = request_payload_events[0].payload["payload"]
        self.assertEqual(request_payload["coverage_status"], "partial_context_coverage")
        self.assertEqual(request_payload["retrieval_coverage_status"], "partial")
        self.assertIn("not necessarily direct implementation", request_payload["coverage_meaning"])
        self.assertIn("prompt_terms", request_payload)
        self.assertEqual(implementation_context[0]["stage"], "checker")
        self.assertEqual(implementation_context[0]["path"], "src/compiler/checker.ts")
        self.assertEqual(implementation_context[0]["positive_claims"][0]["claim_strength"], "direct")
        self.assertEqual(implementation_context[0]["next_inspection_targets"][0]["claim_strength"], "inspection_target")
        self.assertIn(LogEventType.RESPONSE_GENERATION_REQUESTED, [event.event_type for event in logger.events])
        self.assertIn(LogEventType.RESPONSE_GENERATION_RECEIVED, [event.event_type for event in logger.events])

    def test_prompt_term_classification_separates_targets_examples_and_ignored_prose(self) -> None:
        terms = _classify_prompt_terms(
            "Explain the code context needed for this issue.\n\n"
            "Title: Suggestion: abstract classes\n\n"
            "Support an `abstract` keyword for classes and their methods\n\n"
            "Examples:\n\n"
            "``` TypeScript\n"
            "abstract class Base {\n"
            "    abstract getThing(): string;\n"
            "    getOtherThing() { return 'hello'; }\n"
            "}\n"
            "class Derived1 extends Base { }\n"
            "class Derived2 extends Base { getThing() { return 'hello'; } }\n"
            "```\n"
            "must either implement concrete getThing"
        )

        self.assertIn("abstract", terms["requested_target_terms"])
        self.assertIn("abstract classes", terms["requested_target_terms"])
        self.assertIn("abstract keyword", terms["requested_target_terms"])
        self.assertIn("abstract methods", terms["requested_target_terms"])
        self.assertIn("Base", terms["example_terms"])
        self.assertIn("Derived1", terms["example_terms"])
        self.assertIn("Derived2", terms["example_terms"])
        self.assertIn("getThing", terms["example_terms"])
        self.assertIn("getOtherThing", terms["example_terms"])
        self.assertIn("support", terms["prose_terms_ignored_for_grounding"])
        self.assertIn("examples", terms["prose_terms_ignored_for_grounding"])
        self.assertIn("concrete", terms["prose_terms_ignored_for_grounding"])
        self.assertIn("either", terms["prose_terms_ignored_for_grounding"])

    def test_prompt_term_classification_handles_unclosed_fenced_code(self) -> None:
        terms = _classify_prompt_terms(
            "Title: Suggestion: abstract classes\n\n"
            "Support an `abstract` keyword for classes and their methods\n\n"
            "Examples:\n\n"
            "``` TypeScript\n"
            "abstract class Base {\n"
            "    abstract getThing(): string;\n"
            "    getOtherThing() { return 'hello'; }\n"
            "}\n"
            "class Derived1 extends Base { }\n"
            "class Derived2 extends Base { getThing() { return 'hello'; } }\n"
        )

        self.assertIn("abstract keyword", terms["requested_target_terms"])
        self.assertIn("Base", terms["example_terms"])
        self.assertIn("Derived1", terms["example_terms"])
        self.assertIn("Derived2", terms["example_terms"])
        self.assertIn("getThing", terms["example_terms"])
        self.assertIn("getOtherThing", terms["example_terms"])

    def test_guided_explanation_removes_leaked_answer_key_from_visible_markdown(self) -> None:
        retrieval = _StubRetrievalService(_retrieval_with_role_buckets())
        with _fake_llm_server(
            [
                {
                    "markdown": (
                        "# Bottom line\n\n"
                        "The checker owns the rule at [src/compiler/checker.ts:L10-L12](src/compiler/checker.ts#L10-L12).\n\n"
                        "### Understanding check question\n"
                        "Why is this checker path the main place to verify the rule?\n\n"
                        "Expected answer points:\n"
                        "- It contains semantic validation.\n"
                        "- It reports the relevant diagnostic.\n"
                    ),
                    "used_evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                    "understanding_checks": [
                        {
                            "id": "q1",
                            "role": "validation_checking",
                            "question_type": "primary",
                            "question": "Why is this checker path the main place to verify the rule?",
                            "expected_answer_points": ["It contains semantic validation.", "It reports the relevant diagnostic."],
                            "hint": "Look for the code path that turns parsed declarations into an error.",
                            "evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                            "origin": "main retrieved role",
                        }
                    ],
                    "render_notes": {"title": "Bottom line", "summary": "Checker enforces abstract rules."},
                }
            ]
        ) as server_url:
            control_layer = ControlLayer(
                policy_stage=PolicyStage(),
                retrieval_stage=retrieval,
                logger=_InMemoryLogger(),
                response_llm_config=_llm_config(server_url),
            )
            result = control_layer.run(
                ConversationState(
                    conversation_id="test-llm-leaked-answer-key",
                    user_input="Explain abstract class handling.",
                    intent=UserIntent.UNDERSTAND_CODE,
                )
            )

        self.assertIn("The checker owns the rule", result.response_payload.content)
        self.assertNotIn("Understanding check", result.response_payload.content)
        self.assertNotIn("Expected answer points", result.response_payload.content)
        self.assertEqual(len(result.response_payload.metadata["understanding_checks"]), 1)

    def test_guided_explanation_dedupes_repeated_absence_caveats(self) -> None:
        retrieval = _StubRetrievalService(_retrieval_with_role_buckets())
        with _fake_llm_server(
            [
                {
                    "markdown": (
                        "# Where to inspect or add abstract support\n\n"
                        "The snippets do not show abstract handling in the current code.\n\n"
                        "## Parser\n"
                        "The parser calls a modifier pipeline. However, it does not explicitly mention abstract.\n\n"
                        "## Checker\n"
                        "The checker validates class declarations. However, it does not show abstract checks.\n\n"
                        "## What is not shown by these snippets\n"
                        "- No explicit abstract keyword handling.\n"
                    ),
                    "used_evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                    "understanding_checks": [
                        {
                            "id": "q1",
                            "role": "validation_checking",
                            "question_type": "primary",
                            "question": "What does the checker snippet prove?",
                            "expected_answer_points": ["It contains semantic validation."],
                            "hint": "Look for the validation function.",
                            "evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                            "origin": "main retrieved role",
                        }
                    ],
                    "render_notes": {"title": "Bottom line", "summary": "Checker path."},
                }
            ]
        ) as server_url:
            control_layer = ControlLayer(
                policy_stage=PolicyStage(),
                retrieval_stage=retrieval,
                logger=_InMemoryLogger(),
                response_llm_config=_llm_config(server_url),
            )
            result = control_layer.run(
                ConversationState(
                    conversation_id="test-llm-repeated-absence",
                    user_input="Explain abstract class handling.",
                    intent=UserIntent.UNDERSTAND_CODE,
                )
            )

        self.assertIn("The snippets do not show abstract handling", result.response_payload.content)
        self.assertIn("The parser calls a modifier pipeline.", result.response_payload.content)
        self.assertIn("The checker validates class declarations.", result.response_payload.content)
        self.assertNotIn("does not explicitly mention abstract", result.response_payload.content)
        self.assertNotIn("does not show abstract checks", result.response_payload.content)
        self.assertIn("No explicit abstract keyword handling", result.response_payload.content)

    def test_explanation_llm_failure_returns_error_response(self) -> None:
        logger = _InMemoryLogger()
        with _fake_llm_server(["not json"]) as server_url:
            control_layer = ControlLayer(
                policy_stage=PolicyStage(),
                retrieval_stage=_StubRetrievalService(_retrieval_with_role_buckets()),
                logger=logger,
                response_llm_config=_llm_config(server_url),
            )
            result = control_layer.run(
                ConversationState(
                    conversation_id="test-llm-error",
                    user_input="Explain the policy flow.",
                    intent=UserIntent.UNDERSTAND_CODE,
                )
            )

        self.assertIn("**Error**", result.response_payload.content)
        self.assertIn("Explanation generation failed:", result.response_payload.content)
        self.assertIn(LogEventType.RESPONSE_GENERATION_FAILED, [event.event_type for event in logger.events])
        self.assertIn("valid JSON", result.response_payload.metadata["error"])

    def test_default_policy_engine_uses_v1_default_source_categories(self) -> None:
        result = self.control_layer.run(
            ConversationState(
                conversation_id="test-default-source-policy",
                user_input="Explain this issue.",
                intent=UserIntent.UNDERSTAND_CODE,
            )
        )

        self.assertEqual(result.allowed_sources, DEFAULT_ALLOWED_SOURCE_CATEGORIES)
        self.assertEqual(result.policy_result.source_policy_name, "v1_default")

    def test_custom_source_policy_rejects_evidence_outside_policy(self) -> None:
        source_policy = SourcePolicy(
            allowed_categories=(SourceCategory.ISSUE_TRACKER, SourceCategory.SOURCE_CODE),
            policy_name="coderepoqa_guided_initial",
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
                intent=UserIntent.UNDERSTAND_CODE,
                evidence=(
                    EvidenceItem(
                        source_category=SourceCategory.PULL_REQUEST,
                        source_id="hidden:pr-3579",
                        snippet="Hidden resolution context must not be visible in the initial guided turn.",
                    ),
                ),
            ),
        )

        self.assertFalse(result.policy_result.allowed)
        self.assertEqual(result.policy_result.turn_type, TurnType.BOUNDARY)
        self.assertEqual(
            tuple(violation.violation_type for violation in result.violations),
            (PolicyViolationType.UNSUPPORTED_SOURCE_USAGE,),
        )

    def test_direct_solution_returns_boundary_without_retrieval(self) -> None:
        result = self.control_layer.run(
            ConversationState(
                conversation_id="test-direct-solution",
                user_input="Just solve it and give me the answer.",
                intent=UserIntent.UNKNOWN,
            ),
        )

        self.assertFalse(result.policy_result.allowed)
        self.assertFalse(result.policy_result.retrieval_required)
        self.assertEqual(result.response_plan.turn_type, TurnType.BOUNDARY)
        self.assertEqual(result.response_plan.required_sections, ("boundary", "violation_explanation", "choices"))
        self.assertEqual(
            tuple(violation.violation_type for violation in result.violations),
            (PolicyViolationType.DIRECT_SOLUTION_REQUEST,),
        )

    def test_existing_evidence_skips_retrieval_stage(self) -> None:
        logger = _InMemoryLogger()
        retrieval = _StubRetrievalService()
        control_layer = ControlLayer(policy_stage=PolicyStage(), retrieval_stage=retrieval, logger=logger)
        result = control_layer.run(
            ConversationState(
                conversation_id="test-existing-evidence",
                user_input="Explain this issue.",
                intent=UserIntent.UNDERSTAND_CODE,
                evidence=DEFAULT_STUB_EVIDENCE,
            ),
        )

        self.assertEqual(len(retrieval.calls), 0)
        self.assertTrue(result.retrieval_result is not None)
        self.assertEqual(result.retrieval_result.coverage_status, "state_evidence")
        retrieval_event = [event for event in logger.events if event.event_type == LogEventType.RETRIEVAL_PLAN][-1]
        self.assertEqual(retrieval_event.payload["action"], "skip_existing_evidence")

    def test_question_contexts_use_required_role_buckets_first(self) -> None:
        contexts = build_question_contexts(_retrieval_with_role_buckets())

        self.assertEqual(contexts[0].id, "q1")
        self.assertEqual(contexts[0].role, "validation_checking")
        self.assertEqual(contexts[0].question_type, "primary")
        self.assertEqual(contexts[0].origin, "main retrieved role")
        self.assertIn("primary check for validation checking", contexts[0].focus)
        self.assertIn("what data or state enters or leaves it", contexts[0].focus)
        self.assertNotIn("?", contexts[0].focus)

    def test_question_contexts_do_not_inherit_feature_specific_queries(self) -> None:
        retrieval = _retrieval_with_role_buckets(
            role="representation",
            query="Where does the compiler represent abstract classes and abstract methods in the AST or symbol table?",
        )

        contexts = build_question_contexts(retrieval)

        self.assertEqual(contexts[0].role, "representation")
        self.assertIn("primary check for representation", contexts[0].focus)
        self.assertIn("request-specific question", contexts[0].focus)
        self.assertNotIn("?", contexts[0].focus)
        self.assertNotIn("abstract", contexts[0].focus.lower())

    def test_understanding_checks_reject_retrieval_label_questions(self) -> None:
        retrieval = _retrieval_with_role_buckets()
        contexts = tuple(context.to_dict() for context in build_question_contexts(retrieval))

        with self.assertRaisesRegex(RuntimeError, "no valid understanding checks"):
            _validate_generation_response(
                {
                    "markdown": "# Bottom line\n\nThe checker owns the rule at [src/compiler/checker.ts:L10-L12](src/compiler/checker.ts#L10-L12).",
                    "used_evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                    "understanding_checks": [
                        {
                            "id": "q1",
                            "role": "validation_checking",
                            "question_type": "primary",
                            "question": "Why is the checker evidence relevant for semantic rules around classes?",
                            "expected_answer_points": ["It checks a semantic condition.", "It depends on compiler state."],
                            "hint": "Use the checker evidence to explain the role.",
                            "evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                            "origin": "main retrieved role",
                        }
                    ],
                    "render_notes": {"title": "Bottom line", "summary": "Checker enforces abstract rules."},
                },
                retrieval.evidence,
                question_contexts=contexts,
            )

    def test_answer_evaluation_uses_llm_schema(self) -> None:
        checks = [
            {
                "id": "q1",
                "question": "Why does checker matter?",
                "expected_answer_points": ["It validates semantics."],
            }
        ]
        with _fake_llm_server(
            [
                {
                    "evaluations": [
                        {
                            "question_id": "q1",
                            "status": "correct",
                            "matched_points": ["It validates semantics."],
                            "missing_points": [],
                            "feedback": "Correct.",
                            "next_turn": "deepen",
                            "repair_focus": "",
                        }
                    ]
                }
            ]
        ) as server_url:
            evaluations = evaluate_answers(
                checks=checks,
                answers={"q1": "It validates semantics."},
                llm_config=_llm_config(server_url),
            )

        self.assertEqual(evaluations[0].status, "correct")
        self.assertEqual(evaluations[0].next_turn, "deepen")

    def test_prompt_sources_note_is_checked_in(self) -> None:
        content = prompt_sources_path().read_text(encoding="utf-8")
        self.assertIn("digital.gov/guides/plain-language/principles/write-for-reader/", content)
        self.assertIn("link.springer.com/article/10.1007/s10648-010-9145-4", content)

    def test_explanation_prompt_is_implementation_context_not_case_specific(self) -> None:
        content = (prompt_sources_path().parent / "explanation.md").read_text(encoding="utf-8")

        self.assertIn("implementation-context explanation", content)
        self.assertIn("coverage of useful explanation context", content)
        self.assertIn("implementation_context", content)
        self.assertIn("prompt_terms_absent_from_evidence", content)
        self.assertIn("### <Responsibility or Stage> (<path>)", content)
        self.assertIn("Do not create a separate section just for code excerpts.", content)
        self.assertIn("from the user's problem perspective", content)
        self.assertIn("Do not summarize retrieval quality in the visible answer.", content)
        self.assertIn("\"The retrieved code provides...\"", content)
        self.assertIn("Start by answering the user's actual prompt in system-flow terms.", content)
        self.assertNotIn("snippet-grounded explanation", content)
        self.assertNotIn("Minimal code excerpts", content)
        self.assertNotIn("FORBIDDEN when exact feature tokens", content)
        self.assertNotIn("abstract", content.lower())


class ScenarioFixtureTests(unittest.TestCase):
    def test_step3_scenarios_match_policy(self) -> None:
        engine = PolicyStage()

        for scenario in SCENARIOS:
            with self.subTest(scenario_id=scenario.scenario_id):
                result = engine.decide(scenario.state)
                expected = scenario.expected_policy

                self.assertEqual(result.allowed, expected.allowed)
                self.assertEqual(result.intent, expected.intent)
                self.assertEqual(result.retrieval_required, expected.retrieval_required)
                self.assertEqual(result.turn_type, expected.turn_type)
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


def _retrieval_with_role_buckets(
    *,
    role: str = "validation_checking",
    query: str = "semantic validation rules",
) -> RetrievalResult:
    return RetrievalResult(
        evidence=(
            EvidenceItem(
                source_category=SourceCategory.SOURCE_CODE,
                source_id="repo-pre:src/compiler/checker.ts:L10-L12",
                snippet="function checkClassLikeDeclaration(node) {\n  return Diagnostics.Abstract_class;\n}",
                rank=1,
                metadata={"path": "src/compiler/checker.ts", "coverage_area": role},
            ),
        ),
        coverage_status="partial",
        sufficient=False,
        retrieval_summary={
            "required_role_buckets": [
                {
                    "role": role,
                    "query": query,
                    "role_status": "strong",
                    "accepted_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                    "satisfying_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                }
            ],
            "deterministic_coverage_gate": {"satisfied": False, "missing_roles": ["input_parsing"], "reasons": []},
        },
    )


if __name__ == "__main__":
    unittest.main()
