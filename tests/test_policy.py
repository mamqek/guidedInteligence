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
from services.comprehension import build_comprehension_plan
from services.comprehension.followup import build_comprehension_state
from services.guidance.answer_evaluation import evaluate_answers
from services.response_generation.comprehension import (
    _next_check_requirement,
    _next_checks_from_response,
    _sanitize_comprehension_markdown,
    _validate_response,
)
from services.retrieval.config import RunLLMConfig
from step3_harness_scenarios import DEFAULT_STUB_EVIDENCE, SCENARIOS


class _StubRetrievalService:
    def __init__(self, retrieval_result: RetrievalResult | tuple[RetrievalResult, ...] | None = None) -> None:
        self.calls: list[tuple[ConversationState, object]] = []
        default_result = RetrievalResult(
            evidence=DEFAULT_STUB_EVIDENCE,
            coverage_status="strong",
            sufficient=True,
            retrieval_summary={"source": "stub"},
        )
        if isinstance(retrieval_result, tuple):
            self.retrieval_results = list(retrieval_result)
            self.retrieval_result = self.retrieval_results[-1] if self.retrieval_results else default_result
        else:
            self.retrieval_result = retrieval_result or default_result
            self.retrieval_results = []

    def retrieve(self, state: ConversationState, policy_result: object) -> RetrievalResult:
        self.calls.append((state, policy_result))
        if self.retrieval_results:
            return self.retrieval_results.pop(0)
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
        self.assertEqual(result.response_plan.notes["prompt_template_id"], "comprehension_plan_explanation_v1")
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

    def test_sanitize_comprehension_markdown_removes_inline_understanding_check_leak(self) -> None:
        markdown = (
            "The explanation teaches the code path.\n\n"
            "This paragraph should stay.\n\n"
            "---\n\n"
            "Understanding check: Why does this behavior happen?"
        )

        sanitized = _sanitize_comprehension_markdown(markdown)

        self.assertEqual(sanitized, "The explanation teaches the code path.\n\nThis paragraph should stay.")

    def test_next_checks_from_response_keeps_structured_items_without_text_bucketing(self) -> None:
        checks = _next_checks_from_response(
            [
                {
                    "scenario": "reported environment",
                    "action": "Reproduce the sample with the exact Python, pandas, and PyTables versions from the issue.",
                    "if_result": "It only fails with those versions.",
                    "then_interpretation": "This points to a version compatibility issue.",
                },
                {
                    "scenario": "dependency version",
                    "action": "Run the same sample with a newer PyTables version.",
                    "if_result": "The sample passes.",
                    "then_interpretation": "The likely root cause is PyTables behavior fixed later.",
                },
                {
                    "scenario": "dependency version",
                    "action": "Try another newer PyTables release.",
                    "if_result": "The sample passes.",
                    "then_interpretation": "This repeats the same scenario and should be ignored.",
                },
                {
                    "scenario": "public API path",
                    "action": "Run the sample with format='table' explicitly and compare it with append=False.",
                    "if_result": "The error still occurs or is avoided depending on format specification.",
                    "then_interpretation": "The structured parser should not classify or reject based on this wording.",
                },
                {
                    "scenario": "Inspect HDFStore append metadata initialization",
                    "action": "Add debug prints or logs in HDFStore.append to verify metadata setup before calling PyTables.",
                    "if_result": "Metadata is correctly initialized before PyTables calls.",
                    "then_interpretation": "This is too low-level for a normal next check and should be ignored.",
                },
                {
                    "scenario": "Verify extension probing call counts",
                    "action": "Modify module resolution code to log or count statSync calls for each extension.",
                    "if_result": "The logs show which extensions were checked.",
                    "then_interpretation": "This is instrumentation rather than a normal user-facing check.",
                },
                {
                    "scenario": "Measure stat calls from implementation changes",
                    "action": "Modify the resolver to measure statSync calls while resolving node_modules.",
                    "if_result": "The measured calls decrease.",
                    "then_interpretation": "This is an internal measurement change rather than a normal check.",
                },
            ]
        )

        self.assertEqual(
            [check["action"] for check in checks],
            [
                "Reproduce the sample with the exact Python, pandas, and PyTables versions from the issue.",
                "Run the same sample with a newer PyTables version.",
                "Run the sample with format='table' explicitly and compare it with append=False.",
            ],
        )
        self.assertEqual(
            [check["scenario"] for check in checks],
            ["reported environment", "dependency version", "public API path"],
        )

    def test_next_check_requirement_uses_answer_blocking_uncertainty(self) -> None:
        retrieval_result = RetrievalResult(
            evidence=DEFAULT_STUB_EVIDENCE,
            coverage_status="strong",
            sufficient=True,
            retrieval_summary={"answer_blocking_uncertainties": ["External dependency behavior was not covered by selected source evidence."]},
        )
        plan = build_comprehension_plan(
            user_prompt="Explain the external handoff.",
            retrieval_result=retrieval_result,
        )

        requirement = _next_check_requirement(plan=plan, retrieval_result=retrieval_result)

        self.assertTrue(requirement["required"])
        self.assertEqual(requirement["mode"], "bounded_inference")
        self.assertEqual(requirement["min_checks"], 1)
        self.assertEqual(requirement["target_checks"], 2)

    def test_next_check_requirement_ignores_scope_notes_when_retrieval_is_sufficient(self) -> None:
        retrieval_result = RetrievalResult(
            evidence=DEFAULT_STUB_EVIDENCE,
            coverage_status="strong",
            sufficient=True,
            retrieval_summary={
                "scope_notes": [
                    "The upstream producer of a diagnostic field was not inspected, but the selected consumer evidence answers the prompt."
                ]
            },
        )
        plan = build_comprehension_plan(
            user_prompt="Explain direct evidence with a non-blocking scope note.",
            retrieval_result=retrieval_result,
        )

        requirement = _next_check_requirement(plan=plan, retrieval_result=retrieval_result)

        self.assertFalse(requirement["required"])
        self.assertEqual(requirement["mode"], "direct")
        self.assertEqual(requirement["min_checks"], 0)
        self.assertEqual(requirement["signals"]["scope_notes"][0], retrieval_result.retrieval_summary["scope_notes"][0])

    def test_next_check_requirement_is_empty_for_direct_sufficient_retrieval(self) -> None:
        retrieval_result = RetrievalResult(
            evidence=DEFAULT_STUB_EVIDENCE,
            coverage_status="strong",
            sufficient=True,
            retrieval_summary={"source": "stub"},
        )
        plan = build_comprehension_plan(
            user_prompt="Explain direct evidence.",
            retrieval_result=retrieval_result,
        )

        requirement = _next_check_requirement(plan=plan, retrieval_result=retrieval_result)

        self.assertFalse(requirement["required"])
        self.assertEqual(requirement["mode"], "direct")
        self.assertEqual(requirement["min_checks"], 0)

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

    def test_response_metadata_includes_artifact_trace_summary(self) -> None:
        retrieval = _StubRetrievalService(
            RetrievalResult(
                evidence=DEFAULT_STUB_EVIDENCE,
                coverage_status="partial",
                sufficient=True,
                retrieval_summary={
                    "source": "stub",
                    "artifact_trace": {
                        "selected_count": 1,
                        "built_or_generated_count": 1,
                        "all_selected_built_or_generated": True,
                    },
                },
            )
        )
        control_layer = ControlLayer(policy_stage=PolicyStage(), retrieval_stage=retrieval, logger=self.logger)

        result = control_layer.run(
            ConversationState(
                conversation_id="test-artifact-trace-metadata",
                user_input="Explain built library behavior.",
                intent=UserIntent.UNDERSTAND_CODE,
            )
        )

        self.assertEqual(result.response_payload.metadata["artifact_trace"]["built_or_generated_count"], 1)

    def test_shadow_intent_classification_logs_failure_without_routing_change(self) -> None:
        control_layer = ControlLayer(
            policy_stage=PolicyStage(),
            retrieval_stage=self.retrieval,
            logger=self.logger,
            intent_shadow_enabled=True,
        )

        result = control_layer.run(
            ConversationState(
                conversation_id="test-shadow-intent",
                user_input="do it for me",
                intent=UserIntent.UNKNOWN,
            )
        )

        self.assertEqual(result.turn_type, TurnType.BOUNDARY)
        intent_events = [event for event in self.logger.events if event.event_type == LogEventType.INTENT_CLASSIFICATION]
        self.assertEqual(len(intent_events), 1)
        self.assertEqual(intent_events[0].payload["status"], "failed")
        self.assertFalse(intent_events[0].payload["fallback_used"])

    def test_shadow_intent_success_logs_normalization_and_agreement(self) -> None:
        retrieval = _StubRetrievalService(
            RetrievalResult(
                evidence=DEFAULT_STUB_EVIDENCE,
                coverage_status="strong",
                sufficient=True,
                retrieval_summary={
                    "source": "stub",
                    "retrieval_plan": {"primary_intent": "defect_localization"},
                },
            )
        )
        logger = _InMemoryLogger()
        with _fake_llm_server(
            [
                {
                    "user_goals": ["understand", "debug"],
                    "response_operation": "explain",
                    "turn_relation": "new_task",
                    "solution_pressure": "none",
                    "retrieval_intents": [{"intent": "behavior_explanation", "priority": "primary"}],
                    "primary_expected_output": "explanation",
                    "expected_outputs": ["explanation"],
                    "specificity": "medium",
                    "explicit_targets": [],
                    "confidence": 0.9,
                    "classification_basis": ["User asks why behavior occurs."],
                },
                {
                    "markdown": "# Bottom line\n\nThe checker owns the behavior at [src/compiler/checker.ts:L10-L12](src/compiler/checker.ts#L10-L12).",
                    "used_evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                    "understanding_checks": [
                        {
                            "id": "q1",
                            "role": "validation_checking",
                            "question_type": "primary",
                            "question": "Why is this checker path relevant?",
                            "expected_answer_points": ["It validates the behavior."],
                            "hint": "Look at the validation responsibility.",
                            "evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                            "origin": "main retrieved role",
                        }
                    ],
                    "render_notes": {"title": "Bottom line", "summary": "Checker enforces behavior."},
                },
            ]
        ) as server_url:
            control_layer = ControlLayer(
                policy_stage=PolicyStage(),
                retrieval_stage=retrieval,
                logger=logger,
                response_llm_config=_llm_config(server_url),
                intent_shadow_enabled=True,
            )
            result = control_layer.run(
                ConversationState(
                    conversation_id="test-shadow-intent-success",
                    user_input="Explain why this behavior fails.",
                    intent=UserIntent.UNKNOWN,
                )
            )

        self.assertNotIn("response_pipeline", result.response_plan.notes)
        event_types = [event.event_type for event in logger.events]
        self.assertIn(LogEventType.INTENT_CLASSIFICATION, event_types)
        self.assertIn(LogEventType.INTENT_NORMALIZATION, event_types)
        self.assertIn(LogEventType.INTENT_AGREEMENT, event_types)
        agreement = [event for event in logger.events if event.event_type == LogEventType.INTENT_AGREEMENT][0]
        self.assertEqual(agreement.payload["agreement"], "compatible")
        self.assertEqual(agreement.payload["top_level_primary"], "behavior_explanation")
        self.assertEqual(agreement.payload["workspace_primary"], "defect_localization")

    def test_guided_explanation_uses_llm_generation_when_configured(self) -> None:
        retrieval = _StubRetrievalService(_retrieval_with_role_buckets())
        logger = _InMemoryLogger()
        with _fake_llm_server(
            [
                {
                    "markdown": "# Bottom line\n\nThe checker owns the rule in `checkClassLikeDeclaration` at [src/compiler/checker.ts:L10-L12](src/compiler/checker.ts#L10-L12). After the parser creates a class declaration, `checkClassLikeDeclaration` applies the semantic rule and reports the diagnostic.",
                    "used_evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                    "understanding_checks": [
                        {
                            "id": "q1",
                            "role": "validation_checking",
                            "question_type": "primary",
                            "question": "Why does `checkClassLikeDeclaration` explain the diagnostic after the parser creates the class declaration?",
                            "expected_answer_points": ["The parser creates the class declaration.", "`checkClassLikeDeclaration` reports the diagnostic."],
                            "hint": "Connect the parser-created declaration to `checkClassLikeDeclaration`.",
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
            event
            for event in logger.events
            if event.event_type == LogEventType.PROMPT_PAYLOAD
            and event.payload.get("event_type") == "comprehension_generation_request_payload"
        ]
        self.assertEqual(len(request_payload_events), 1)
        request_payload = request_payload_events[0].payload["payload"]["payload"]
        self.assertEqual(request_payload["coverage_status"], "partial")
        self.assertFalse(request_payload["retrieval_sufficient"])
        self.assertIn("comprehension_plan", request_payload)
        self.assertEqual(request_payload["comprehension_plan"]["concepts"][0]["id"], "validation_checking")
        self.assertEqual(request_payload["evidence"][0]["path"], "src/compiler/checker.ts")
        self.assertIn("src/compiler/checker.ts", request_payload["concept_definition_targets"])
        self.assertIn(LogEventType.RESPONSE_GENERATION_REQUESTED, [event.event_type for event in logger.events])
        self.assertIn(LogEventType.RESPONSE_GENERATION_RECEIVED, [event.event_type for event in logger.events])

    def test_comprehension_plan_builder_uses_evidence_and_gaps(self) -> None:
        retrieval = _retrieval_with_role_buckets()
        plan = build_comprehension_plan(
            user_prompt="Explain abstract class handling.",
            retrieval_result=retrieval,
        )

        self.assertEqual(plan.concepts[0].id, "validation_checking")
        self.assertEqual(plan.concepts[0].status, "grounded")
        self.assertEqual(plan.concepts[0].suggested_depth, "full")
        self.assertEqual(plan.coverage_gaps[0].concept_id, "input_parsing")
        self.assertTrue(plan.coverage_gaps[0].retrieval_allowed)
        self.assertTrue(plan.explanation_sequence)
        self.assertIsNone(plan.understanding_check)

    def test_comprehension_plan_persists_plan(self) -> None:
        retrieval = _StubRetrievalService(_retrieval_with_role_buckets())
        logger = _InMemoryLogger()
        with _fake_llm_server(
            [
                {
                    "markdown": "# Plan-based answer\n\nThe library declaration shape is grounded at [src/compiler/checker.ts:L10-L12](src/compiler/checker.ts#L10-L12). The visible abstract-class failure appears only after parsing creates a declaration and the checker interprets that parsed declaration with semantic information. That is why the checker stage, not parsing alone, explains the failure.\n\n---\n\n### Concept Definitions\n\n- **checker**: leaked glossary.\n\n---\n\n### Understanding Check\n\nWhy does the main implementation behavior part matter?",
                    "used_evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                    "understanding_checks": [
                        {
                            "id": "q1",
                            "role": "comprehension_plan",
                            "question_type": "primary",
                            "question": "Why would the abstract-class failure only appear after the checker interprets the parsed declaration?",
                            "expected_answer_points": [
                                "The parser creates the declaration shape.",
                                "The checker applies semantic rules to that declaration.",
                            ],
                            "hint": "Connect the visible error to the stage that has enough semantic information to produce it.",
                            "evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                            "origin": "model_generated",
                        }
                    ],
                    "render_notes": {"title": "Plan-based answer", "summary": "Plan route used."},
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
                    conversation_id="test-comprehension-plan-pipeline",
                    user_input="Explain abstract class handling.",
                    intent=UserIntent.UNDERSTAND_CODE,
                )
            )

        metadata = result.response_payload.metadata
        self.assertNotIn("response_pipeline", metadata)
        self.assertEqual(metadata["comprehension_plan"]["concepts"][0]["id"], "validation_checking")
        self.assertIn("Plan-based answer", result.response_payload.content)
        self.assertIn("library declaration shape", result.response_payload.content)
        self.assertNotIn("state or representation", result.response_payload.content.lower())
        self.assertNotIn("Concept Definitions", result.response_payload.content)
        self.assertNotIn("Understanding Check", result.response_payload.content)
        self.assertEqual(metadata["understanding_checks"][0]["origin"], "model_generated")
        requested = [
            event
            for event in logger.events
            if event.event_type == LogEventType.RESPONSE_GENERATION_REQUESTED
        ]
        self.assertNotIn("response_pipeline", requested[0].payload)

    def test_comprehension_plan_rejects_retrieval_label_check_without_fallback(self) -> None:
        retrieval = _StubRetrievalService(_retrieval_with_role_buckets())
        with _fake_llm_server(
            [
                {
                    "markdown": "# Plan-based answer\n\nThe state or representation is visible at [src/compiler/checker.ts:L10-L12](src/compiler/checker.ts#L10-L12).",
                    "used_evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                    "understanding_checks": [
                        {
                            "id": "q1",
                            "role": "comprehension_plan",
                            "question_type": "primary",
                            "question": "Why does the main implementation behavior part matter for answering this codebase question?",
                            "expected_answer_points": ["It identifies the role.", "It connects retrieved evidence."],
                            "hint": "Use the cited file and line range to explain what this part proves.",
                            "evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                            "origin": "comprehension plan",
                        }
                    ],
                    "render_notes": {"title": "Plan-based answer", "summary": "Plan route used."},
                    "concept_definitions": [],
                },
                {
                    "understanding_checks": [
                        {
                            "id": "q1",
                            "role": "comprehension_plan",
                            "question_type": "primary",
                            "question": "Why does the main implementation behavior part matter here?",
                            "expected_answer_points": ["It connects retrieved evidence."],
                            "hint": "Use the retrieved evidence role.",
                            "evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                            "origin": "model_repaired",
                        }
                    ]
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
                    conversation_id="test-comprehension-plan-check-filter",
                    user_input="Explain abstract class handling.",
                    intent=UserIntent.UNDERSTAND_CODE,
                )
            )

        self.assertIn("Explanation generation failed", result.response_payload.content)
        self.assertIn("no valid model-generated understanding checks", result.response_payload.metadata["error"])
        self.assertNotIn("understanding_checks", result.response_payload.metadata)
        self.assertNotIn("state or representation", result.response_payload.content.lower())
        self.assertNotIn("Concept Definitions", result.response_payload.content)
        self.assertNotIn("Understanding Check", result.response_payload.content)

    def test_comprehension_plan_rejects_check_not_taught_by_explanation(self) -> None:
        retrieval = _StubRetrievalService(_retrieval_with_role_buckets())
        with _fake_llm_server(
            [
                {
                    "markdown": "# Plan-based answer\n\nThe checker validates abstract class rules at [src/compiler/checker.ts:L10-L12](src/compiler/checker.ts#L10-L12).",
                    "used_evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                    "answer_flow": {
                        "symptom": "The issue asks about abstract class rules.",
                        "evidence": "The checker validates abstract class rules.",
                        "cause": "The checker is the relevant implementation point for this explanation.",
                        "tested_concepts": ["checker", "abstract class rules"],
                        "evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                    },
                    "understanding_checks": [
                        {
                            "id": "q1",
                            "role": "learner",
                            "question_type": "why",
                            "question": "Why would DataView fail under the default library target but work when ES6 is selected?",
                            "expected_answer_points": [
                                "The default library target uses lib.d.ts.",
                                "DataView is declared in lib.es6.d.ts.",
                                "Selecting ES6 changes the library declarations loaded by the compiler.",
                            ],
                            "hint": "Compare the default library target with the ES6 library target.",
                            "evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                            "origin": "model_generated",
                            "tested_concepts": ["DataView", "default library target", "ES6 library"],
                            "answer_point_map": [
                                {"kind": "symptom", "point": "The default library target uses lib.d.ts."},
                                {"kind": "evidence", "point": "DataView is declared in lib.es6.d.ts."},
                                {"kind": "cause", "point": "Selecting ES6 changes the library declarations loaded by the compiler."},
                            ],
                        }
                    ],
                    "render_notes": {"title": "Plan-based answer", "summary": "Plan route used."},
                    "concept_definitions": [],
                },
                {
                    "understanding_checks": [
                        {
                            "id": "q1",
                            "role": "learner",
                            "question_type": "why",
                            "question": "Why would DataView fail under the default library target but work when ES6 is selected?",
                            "expected_answer_points": [
                                "The default library target uses lib.d.ts.",
                                "DataView is declared in lib.es6.d.ts.",
                            ],
                            "hint": "Compare the default library target with the ES6 library target.",
                            "evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                            "origin": "model_repaired",
                            "tested_concepts": ["DataView", "default library target", "ES6 library"],
                            "answer_point_map": [
                                {"kind": "symptom", "point": "The default library target uses lib.d.ts."},
                                {"kind": "evidence", "point": "DataView is declared in lib.es6.d.ts."},
                                {"kind": "cause", "point": "DataView is declared in lib.es6.d.ts."},
                            ],
                        }
                    ]
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
                    conversation_id="test-comprehension-plan-check-needs-taught-answer-path",
                    user_input="Explain abstract class handling.",
                    intent=UserIntent.UNDERSTAND_CODE,
                )
            )

        self.assertIn("Explanation generation failed", result.response_payload.content)
        self.assertIn("no valid model-generated understanding checks", result.response_payload.metadata["error"])

    def test_comprehension_plan_repairs_invalid_check_without_rewriting_explanation(self) -> None:
        retrieval = _StubRetrievalService(_retrieval_with_role_buckets())
        logger = _InMemoryLogger()
        with _fake_llm_server(
            [
                {
                    "markdown": (
                        "# Plan-based answer\n\n"
                        "The parser creates the class declaration, then `checkClassLikeDeclaration` validates "
                        "the declaration and reports the diagnostic at "
                        "[src/compiler/checker.ts:L10-L12](src/compiler/checker.ts#L10-L12)."
                    ),
                    "used_evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                    "answer_flow": {
                        "symptom": "The parser creates the class declaration.",
                        "evidence": "`checkClassLikeDeclaration` validates the declaration.",
                        "cause": "`checkClassLikeDeclaration` reports the diagnostic.",
                        "tested_concepts": ["checkClassLikeDeclaration", "class declaration"],
                        "evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                    },
                    "understanding_checks": [
                        {
                            "id": "q1",
                            "role": "comprehension_plan",
                            "question_type": "primary",
                            "question": "Why does the main implementation behavior part matter here?",
                            "expected_answer_points": ["It identifies the role.", "It connects retrieved evidence."],
                            "hint": "Use the cited file and line range.",
                            "evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                            "origin": "model_generated",
                        }
                    ],
                    "render_notes": {"title": "Plan-based answer", "summary": "Plan route used."},
                    "concept_definitions": [],
                },
                {
                    "understanding_checks": [
                        {
                            "id": "q1",
                            "role": "learner",
                            "question_type": "why",
                            "question": "Why does `checkClassLikeDeclaration` explain the diagnostic after the parser creates the class declaration?",
                            "expected_answer_points": [
                                "The parser creates the class declaration.",
                                "`checkClassLikeDeclaration` validates the declaration.",
                                "`checkClassLikeDeclaration` reports the diagnostic.",
                            ],
                            "hint": "Connect the parser-created declaration to `checkClassLikeDeclaration`.",
                            "evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                            "origin": "model_repaired",
                            "tested_concepts": ["checkClassLikeDeclaration", "class declaration"],
                            "answer_point_map": [
                                {"kind": "symptom", "point": "The parser creates the class declaration."},
                                {"kind": "evidence", "point": "`checkClassLikeDeclaration` validates the declaration."},
                                {"kind": "cause", "point": "`checkClassLikeDeclaration` reports the diagnostic."},
                            ],
                        }
                    ]
                },
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
                    conversation_id="test-comprehension-plan-check-repair",
                    user_input="Explain abstract class handling.",
                    intent=UserIntent.UNDERSTAND_CODE,
                )
            )

        self.assertIn("Plan-based answer", result.response_payload.content)
        self.assertEqual(result.response_payload.metadata["understanding_checks"][0]["origin"], "model_repaired")
        self.assertIn("checkClassLikeDeclaration", result.response_payload.metadata["understanding_checks"][0]["question"])
        event_types = [event.payload.get("event_type") for event in logger.events if event.event_type == LogEventType.PROMPT_PAYLOAD]
        self.assertIn("comprehension_understanding_check_repair_requested", event_types)
        self.assertIn("comprehension_understanding_check_repair_received", event_types)

    def test_comprehension_gap_retrieval_is_bounded_when_enabled(self) -> None:
        initial = _retrieval_with_role_buckets()
        gap_result = RetrievalResult(
            evidence=(
                EvidenceItem(
                    source_category=SourceCategory.SOURCE_CODE,
                    source_id="repo-pre:src/compiler/parser.ts:L20-L24",
                    snippet="function parseClassMemberDeclaration() {\n  return parseModifiers();\n}",
                    rank=1,
                    metadata={"path": "src/compiler/parser.ts", "coverage_area": "input_parsing"},
                ),
            ),
            coverage_status="partial",
            sufficient=False,
            retrieval_summary={"retriever": "stub-gap", "selected_count": 1},
        )
        retrieval = _StubRetrievalService((initial, gap_result))
        control_layer = ControlLayer(
            policy_stage=PolicyStage(),
            retrieval_stage=retrieval,
            logger=_InMemoryLogger(),
            max_gap_retrieval_passes=1,
        )

        result = control_layer.run(
            ConversationState(
                conversation_id="test-comprehension-gap",
                user_input="Explain abstract class handling.",
                intent=UserIntent.UNDERSTAND_CODE,
            )
        )

        self.assertEqual(len(retrieval.calls), 2)
        self.assertIn("Bounded follow-up retrieval", retrieval.calls[1][0].user_input)
        self.assertEqual(len(result.retrieval_result.evidence), 2)
        gap_summary = result.retrieval_result.retrieval_summary["comprehension_gap_retrieval"]
        self.assertTrue(gap_summary["performed"])
        self.assertEqual(gap_summary["requested_gaps"], ["input_parsing"])

    def test_comprehension_state_marks_partial_answer_for_repair(self) -> None:
        plan = build_comprehension_plan(
            user_prompt="Explain abstract class handling.",
            retrieval_result=_retrieval_with_role_buckets(),
        )
        state = build_comprehension_state(
            plan=plan,
            checks=[
                {
                    "id": "q1",
                    "evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                }
            ],
            evaluations=[
                {
                    "question_id": "q1",
                    "status": "partial",
                    "feedback": "You identified validation but missed why it depends on adjacent responsibilities.",
                    "next_turn": "repair",
                    "repair_focus": "adjacent validation responsibility",
                }
            ],
        )

        familiarity = {item.concept_id: item.level for item in state.concept_familiarity}
        self.assertEqual(state.current_teaching_stage, "repair")
        self.assertEqual(familiarity["validation_checking"], "partial")
        self.assertIsNotNone(state.repair_plan)

    def test_guided_explanation_removes_leaked_answer_key_from_visible_markdown(self) -> None:
        retrieval = _StubRetrievalService(_retrieval_with_role_buckets())
        with _fake_llm_server(
            [
                {
                    "markdown": (
                        "# Bottom line\n\n"
                        "The checker owns the rule in `checkClassLikeDeclaration` at [src/compiler/checker.ts:L10-L12](src/compiler/checker.ts#L10-L12). After the parser creates a class declaration, `checkClassLikeDeclaration` applies the semantic rule and reports the diagnostic.\n\n"
                        "### Understanding check question\n"
                        "Why does `checkClassLikeDeclaration` explain the diagnostic after the parser creates the class declaration?\n\n"
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
                            "question": "Why does `checkClassLikeDeclaration` explain the diagnostic after the parser creates the class declaration?",
                            "expected_answer_points": ["The parser creates the class declaration.", "`checkClassLikeDeclaration` reports the diagnostic."],
                            "hint": "Connect the parser-created declaration to `checkClassLikeDeclaration`.",
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
                        "The parser calls a modifier pipeline before `checkClassLikeDeclaration`. However, it does not explicitly mention abstract.\n\n"
                        "## Checker\n"
                        "The checker validates the class declaration in `checkClassLikeDeclaration`. However, it does not show abstract checks.\n\n"
                        "## What is not shown by these snippets\n"
                        "- No explicit abstract keyword handling.\n"
                    ),
                    "used_evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                    "understanding_checks": [
                        {
                            "id": "q1",
                            "role": "validation_checking",
                            "question_type": "primary",
                            "question": "Why would abstract handling need a checker change after parsing creates the class declaration?",
                            "expected_answer_points": ["The parser creates the class declaration.", "`checkClassLikeDeclaration` validates class declarations."],
                            "hint": "Connect the parser-created declaration to `checkClassLikeDeclaration`.",
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
        self.assertIn("The parser calls a modifier pipeline before `checkClassLikeDeclaration`.", result.response_payload.content)
        self.assertIn("The checker validates the class declaration in `checkClassLikeDeclaration`.", result.response_payload.content)
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

    def test_understanding_checks_reject_retrieval_label_questions(self) -> None:
        retrieval = _retrieval_with_role_buckets()

        with self.assertRaisesRegex(RuntimeError, "no valid model-generated understanding checks"):
            plan = build_comprehension_plan(
                user_prompt="Explain abstract class handling.",
                retrieval_result=retrieval,
            )
            _validate_response(
                {
                    "markdown": "# Bottom line\n\nThe checker owns the rule at [src/compiler/checker.ts:L10-L12](src/compiler/checker.ts#L10-L12).",
                    "used_evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                    "answer_flow": {
                        "symptom": "The issue asks where semantic class rules are handled.",
                        "evidence": "The checker owns the relevant rule.",
                        "cause": "The checker is the implementation point for the semantic rule.",
                        "tested_concepts": ["checker", "semantic class rules"],
                        "evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                    },
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
                plan,
            )

    def test_understanding_check_validator_ignores_connective_words_in_answer_key(self) -> None:
        retrieval = RetrievalResult(
            evidence=(
                EvidenceItem(
                    source_category=SourceCategory.SOURCE_CODE,
                    source_id="workspace:packages/vue-server-renderer/types/index.d.ts:L1-L44",
                    snippet="export declare function createRenderer(options?: RendererOptions): Renderer;",
                    rank=1,
                    metadata={
                        "path": "packages/vue-server-renderer/types/index.d.ts",
                        "coverage_area": "published TypeScript declarations",
                    },
                ),
                EvidenceItem(
                    source_category=SourceCategory.SOURCE_CODE,
                    source_id="workspace:src/server/webpack-plugin/client.js:L1-L69",
                    snippet="export default class VueSSRClientPlugin { apply (compiler) {} }",
                    rank=2,
                    metadata={
                        "path": "src/server/webpack-plugin/client.js",
                        "coverage_area": "runtime client plugin implementation",
                    },
                ),
                EvidenceItem(
                    source_category=SourceCategory.SOURCE_CODE,
                    source_id="workspace:build/config.js:L131-L135",
                    snippet="dest: resolve('packages/vue-server-renderer/client-plugin.js')",
                    rank=3,
                    metadata={"path": "build/config.js", "coverage_area": "build pipeline and emitted package path"},
                ),
            ),
            coverage_status="strong",
            sufficient=True,
        )
        plan = build_comprehension_plan(
            user_prompt="Explain the code context for vue-server-renderer/client-plugin declarations.",
            retrieval_result=retrieval,
        )

        result = _validate_response(
            {
                "markdown": (
                    "The symptom is that TypeScript users lack type declarations for "
                    "`vue-server-renderer/client-plugin`. The observed evidence is that "
                    "`types/index.d.ts` does not declare the `client-plugin` subpath, while "
                    "`client-plugin` exists as runtime code and build output. The cause is that "
                    "the published TypeScript declaration file does not include declarations for "
                    "that subpath."
                ),
                "used_evidence_refs": [
                    "workspace:packages/vue-server-renderer/types/index.d.ts:L1-L44",
                    "workspace:src/server/webpack-plugin/client.js:L1-L69",
                    "workspace:build/config.js:L131-L135",
                ],
                "answer_flow": {
                    "symptom": "TypeScript users lack declarations for `vue-server-renderer/client-plugin`.",
                    "evidence": "The package's published declaration file `types/index.d.ts` does not declare any exports for the `client-plugin` subpath.",
                    "cause": "Because the published TypeScript declaration file does not include declarations for the `client-plugin` subpath, even though the runtime code and build output exist.",
                    "tested_concepts": [
                        "published TypeScript declarations",
                        "vue-server-renderer/client-plugin",
                        "client-plugin subpath",
                    ],
                    "evidence_refs": [
                        "workspace:packages/vue-server-renderer/types/index.d.ts:L1-L44",
                        "workspace:src/server/webpack-plugin/client.js:L1-L69",
                        "workspace:build/config.js:L131-L135",
                    ],
                },
                "understanding_checks": [
                    {
                        "id": "check1",
                        "role": "learner",
                        "question_type": "why",
                        "question": (
                            "Why do TypeScript users currently lack type declarations for the "
                            "`vue-server-renderer/client-plugin` subpath, despite it being a built "
                            "and used part of the package?"
                        ),
                        "expected_answer_points": [
                            "TypeScript users lack declarations for `vue-server-renderer/client-plugin`.",
                            "The package's published declaration file `types/index.d.ts` does not declare any exports for the `client-plugin` subpath.",
                            "Because the published TypeScript declaration file does not include declarations for the `client-plugin` subpath, even though the runtime code and build output exist.",
                        ],
                        "hint": "Compare the published declarations with the runtime module and build output.",
                        "evidence_refs": [
                            "workspace:packages/vue-server-renderer/types/index.d.ts:L1-L44",
                            "workspace:src/server/webpack-plugin/client.js:L1-L69",
                            "workspace:build/config.js:L131-L135",
                        ],
                        "origin": "model_generated",
                        "tested_concepts": [
                            "published TypeScript declarations",
                            "vue-server-renderer/client-plugin",
                            "client-plugin subpath",
                        ],
                        "answer_point_map": [
                            {
                                "kind": "symptom",
                                "point": "TypeScript users lack declarations for `vue-server-renderer/client-plugin`.",
                            },
                            {
                                "kind": "evidence",
                                "point": "The package's published declaration file `types/index.d.ts` does not declare any exports for the `client-plugin` subpath.",
                            },
                            {
                                "kind": "cause",
                                "point": "Because the published TypeScript declaration file does not include declarations for the `client-plugin` subpath, even though the runtime code and build output exist.",
                            },
                        ],
                    }
                ],
                "render_notes": {"title": "Client plugin declarations", "summary": "Explains the missing subpath type."},
                "concept_definitions": [],
            },
            retrieval.evidence,
            plan,
        )

        self.assertEqual(result.understanding_checks[0].question_type, "why")

    def test_understanding_checks_reject_generic_question_not_derived_from_answer_flow(self) -> None:
        retrieval = _retrieval_with_role_buckets()
        plan = build_comprehension_plan(
            user_prompt="Explain abstract class handling.",
            retrieval_result=retrieval,
        )

        with self.assertRaisesRegex(RuntimeError, "no valid model-generated understanding checks"):
            _validate_response(
                {
                    "markdown": (
                        "The symptom is an abstract class diagnostic. The checker evidence shows "
                        "`checkClassLikeDeclaration` validates the declaration. The cause is that "
                        "`checkClassLikeDeclaration` reports the diagnostic."
                    ),
                    "used_evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                    "answer_flow": {
                        "symptom": "The issue reports an abstract class diagnostic.",
                        "evidence": "`checkClassLikeDeclaration` validates the class declaration.",
                        "cause": "`checkClassLikeDeclaration` reports the diagnostic.",
                        "tested_concepts": ["checkClassLikeDeclaration", "class declaration"],
                        "evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                    },
                    "understanding_checks": [
                        {
                            "id": "q1",
                            "role": "learner",
                            "question_type": "why",
                            "question": "Why does the reported behavior happen?",
                            "expected_answer_points": [
                                "The issue reports an abstract class diagnostic.",
                                "`checkClassLikeDeclaration` validates the class declaration.",
                                "`checkClassLikeDeclaration` reports the diagnostic.",
                            ],
                            "hint": "Connect the class declaration validation to the diagnostic.",
                            "evidence_refs": ["repo-pre:src/compiler/checker.ts:L10-L12"],
                            "origin": "model_generated",
                            "tested_concepts": ["checkClassLikeDeclaration", "class declaration"],
                            "answer_point_map": [
                                {"kind": "symptom", "point": "The issue reports an abstract class diagnostic."},
                                {"kind": "evidence", "point": "`checkClassLikeDeclaration` validates the class declaration."},
                                {"kind": "cause", "point": "`checkClassLikeDeclaration` reports the diagnostic."},
                            ],
                        }
                    ],
                    "render_notes": {"title": "Abstract class diagnostic", "summary": "Explains checker validation."},
                    "concept_definitions": [],
                    "source_attributions": [],
                    "next_checks": [],
                },
                retrieval.evidence,
                plan,
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

    def test_comprehension_prompt_is_checked_in(self) -> None:
        from services.response_generation.comprehension import _compose_generation_prompt

        content = _compose_generation_prompt(next_check_requirement={"required": True})
        direct_content = _compose_generation_prompt(next_check_requirement={"required": False})

        self.assertIn("generate a codebase explanation", content)
        self.assertIn("symptom -> evidence -> cause", content)
        self.assertIn("Do not add a visible \"Answer path\" section", content)
        self.assertIn("not about evidence mechanics", content)
        self.assertIn("Use this object shape", content)
        self.assertIn('"answer_point_map"', content)
        self.assertIn('"then_interpretation"', content)
        self.assertNotIn("Next checks:", direct_content)
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
        if not self.response_payloads:
            body = json.dumps({"error": "No fake LLM response payload queued."}).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        content = self.response_payloads.pop(0)
        if isinstance(content, dict) and "markdown" in content:
            content.setdefault("concept_definitions", [])
            _add_test_check_grounding(content)
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


def _add_test_check_grounding(content: dict[str, object]) -> None:
    checks = content.get("understanding_checks")
    if not isinstance(checks, list):
        return
    first_points: list[str] = []
    first_refs: list[str] = []
    first_concepts: list[str] = []
    for check in checks:
        if not isinstance(check, dict):
            continue
        check.setdefault("tested_concepts", ["checker"])
        points = check.get("expected_answer_points")
        if not isinstance(points, list) or not points:
            continue
        mapped_points = [str(point) for point in points if str(point).strip()]
        if not mapped_points:
            continue
        while len(mapped_points) < 3:
            mapped_points.append(mapped_points[-1])
        check.setdefault(
            "answer_point_map",
            [
                {"kind": "symptom", "point": mapped_points[0]},
                {"kind": "evidence", "point": mapped_points[1]},
                {"kind": "cause", "point": mapped_points[2]},
            ],
        )
        if not first_points:
            first_points = mapped_points[:3]
            refs = check.get("evidence_refs")
            if isinstance(refs, list):
                first_refs = [str(ref) for ref in refs if str(ref).strip()]
            concepts = check.get("tested_concepts")
            if isinstance(concepts, list):
                first_concepts = [str(concept) for concept in concepts if str(concept).strip()]
    if first_points and first_refs:
        content.setdefault(
            "answer_flow",
            {
                "symptom": first_points[0],
                "evidence": first_points[1],
                "cause": first_points[2],
                "tested_concepts": first_concepts or ["checker"],
                "evidence_refs": first_refs,
            },
        )


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
