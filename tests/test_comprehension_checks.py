from __future__ import annotations

import unittest
from unittest.mock import patch

from core.models import ConversationState, EvidenceItem, RetrievalResult
from core.source_policy import SourceCategory
from services.intent import compose_intent_flow
from services.intent.models import IntentContext, Specificity, TaskIntent
from services.response_generation.comprehension import (
    FlowValidationError,
    _model_facing_intent_flow,
    _response_format,
    _validate_response,
    generate_comprehension_explanation,
)


class IntentComposedExplanationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.flow = compose_intent_flow((TaskIntent.DEBUG,))
        self.evidence = (
            EvidenceItem(SourceCategory.SOURCE_CODE, "repo:a.py:L1-L4", "def parse(): pass", metadata={"path": "a.py"}),
        )

    def test_valid_response_derives_answer_and_story_flow_from_one_order(self) -> None:
        response = _response(self.flow.contract_stage_ids)
        result = _validate_response(response, evidence=self.evidence, flow_plan=self.flow)
        self.assertEqual(tuple(result.answer_flow["ordered_stage_ids"]), self.flow.contract_stage_ids)
        self.assertEqual(tuple(stage["stage_id"] for stage in result.story_flow), self.flow.contract_stage_ids)
        self.assertEqual(result.understanding_checks[0].intent, TaskIntent.DEBUG)

    def test_missing_stage_is_a_blocking_structural_error(self) -> None:
        response = _response(self.flow.contract_stage_ids[:-1])
        with self.assertRaisesRegex(FlowValidationError, "missing stage IDs"):
            _validate_response(response, evidence=self.evidence, flow_plan=self.flow)

    def test_question_prerequisites_are_normalized_from_intent_contract(self) -> None:
        response = _response(self.flow.contract_stage_ids)
        response["understanding_checks"][0]["prerequisite_stage_ids"] = ["debug.symptom"]
        result = _validate_response(response, evidence=self.evidence, flow_plan=self.flow)

        self.assertEqual(
            result.understanding_checks[0].prerequisite_stage_ids,
            ("debug.symptom", "debug.evidence", "debug.cause"),
        )

    def test_at_least_one_understanding_check_is_required(self) -> None:
        response = _response(self.flow.contract_stage_ids)
        response["understanding_checks"] = []

        with self.assertRaisesRegex(FlowValidationError, "at least one"):
            _validate_response(response, evidence=self.evidence, flow_plan=self.flow)

    def test_response_schema_requires_one_to_three_understanding_checks(self) -> None:
        schema = _response_format(self.flow)["json_schema"]["schema"]
        checks = schema["properties"]["understanding_checks"]

        self.assertEqual(checks["minItems"], 1)
        self.assertEqual(checks["maxItems"], 3)

    def test_multi_intent_stage_neutralization_is_stable_and_order_neutral(self) -> None:
        flow = compose_intent_flow((TaskIntent.EXPLORE, TaskIntent.EXPLAIN))

        payload, model_stage_ids, mode = _model_facing_intent_flow(
            flow,
            user_prompt="Where is classification and how does it flow?",
            neutralize=True,
        )
        repeated = _model_facing_intent_flow(
            flow,
            user_prompt="Where is classification and how does it flow?",
            neutralize=True,
        )

        self.assertEqual(mode, "prompt_seeded_stable_permutation")
        self.assertEqual((payload, model_stage_ids, mode), repeated)
        self.assertEqual(set(model_stage_ids), set(flow.contract_stage_ids))
        self.assertNotEqual(model_stage_ids, flow.contract_stage_ids)
        self.assertTrue(all("stages" not in contract for contract in payload["contracts"]))
        self.assertEqual([stage["id"] for stage in payload["stage_definitions"]], list(model_stage_ids))
        schema = _response_format(flow, model_stage_ids=model_stage_ids)["json_schema"]["schema"]
        self.assertEqual(schema["properties"]["ordered_stage_ids"]["items"]["enum"], list(model_stage_ids))

    def test_single_intent_stage_order_remains_canonical(self) -> None:
        payload, model_stage_ids, mode = _model_facing_intent_flow(
            self.flow,
            user_prompt="Why does parsing fail?",
            neutralize=True,
        )

        self.assertEqual(mode, "canonical_contract_order")
        self.assertEqual(model_stage_ids, self.flow.contract_stage_ids)
        self.assertEqual(payload, self.flow.to_generation_dict())

    def test_distinct_stage_targets_allow_multiple_understanding_checks(self) -> None:
        response = _response(self.flow.contract_stage_ids)
        response["understanding_checks"].append(
            {
                "id": "q2",
                "intent": "debug",
                "target_stage_ids": ["debug.next_check"],
                "prerequisite_stage_ids": ["debug.symptom", "debug.evidence", "debug.cause"],
                "stem_family": "how_does_it_fail",
                "reasoning_focus": "next observation distinguishes the candidate failure path",
                "selection_reason": "The diagnostic decision is independent from identifying the cause.",
                "question": "Which next observation would distinguish this failure path?",
                "expected_answer_points": ["Inspect the next discriminating observation."],
                "hints": _hints("Use the proposed diagnostic check"),
                "evidence_refs": ["repo:a.py:L1-L4"],
            }
        )

        result = _validate_response(response, evidence=self.evidence, flow_plan=self.flow)

        self.assertEqual([check.id for check in result.understanding_checks], ["q1", "q2"])

    def test_multiple_checks_cannot_repeat_the_same_support_signature(self) -> None:
        response = _response(self.flow.contract_stage_ids)
        duplicate = dict(response["understanding_checks"][0])
        duplicate.update({"id": "q2", "question": "How is the supported cause identified?"})
        response["understanding_checks"].append(duplicate)

        with self.assertRaisesRegex(FlowValidationError, "repeats another check's intent, target stages, and evidence"):
            _validate_response(response, evidence=self.evidence, flow_plan=self.flow)

    def test_multiple_checks_cannot_repeat_question_text(self) -> None:
        response = _response(self.flow.contract_stage_ids)
        duplicate = dict(response["understanding_checks"][0])
        duplicate.update({
            "id": "q2",
            "target_stage_ids": ["debug.next_check"],
            "reasoning_focus": "next observation distinguishes the candidate failure path",
            "selection_reason": "This targets a separate diagnostic decision.",
        })
        response["understanding_checks"].append(duplicate)

        with self.assertRaisesRegex(FlowValidationError, "duplicates another question"):
            _validate_response(response, evidence=self.evidence, flow_plan=self.flow)

    def test_question_repair_replaces_only_rejected_check_and_preserves_valid_check(self) -> None:
        response = _response(self.flow.contract_stage_ids)
        original = dict(response["understanding_checks"][0])
        rejected = {
            **original,
            "id": "q2",
            "target_stage_ids": ["debug.next_check"],
            "reasoning_focus": "next observation distinguishes the candidate failure path",
            "selection_reason": "This targets a separate diagnostic decision.",
        }
        response["understanding_checks"].append(rejected)
        replacement = {
            **rejected,
            "question": "Which next observation would distinguish this failure path?",
            "hints": _hints("Identify the observation that would separate the candidate causes"),
        }
        state = ConversationState(
            conversation_id="repair-test",
            user_input="Why does parsing fail?",
            intent_context=IntentContext(intents=(TaskIntent.DEBUG,), specificity=Specificity.NARROW, explicit_targets=()),
        )
        retrieval = RetrievalResult(evidence=self.evidence, coverage_status="strong", sufficient=True)

        with patch("services.response_generation.comprehension._complete_generation", return_value=response), patch(
            "services.response_generation.comprehension.repair_understanding_checks",
            return_value=[replacement],
        ) as repair:
            result = generate_comprehension_explanation(state=state, retrieval_result=retrieval, llm_config=object())

        self.assertEqual(result.understanding_checks[0].to_dict(), {**original, "intent": "debug"})
        self.assertEqual(result.understanding_checks[1].question, replacement["question"])
        self.assertEqual(result.question_repair_attempts, 1)
        repair_context = repair.call_args.kwargs["context"]
        self.assertEqual(repair_context["accepted_questions"], [original])
        self.assertEqual(repair_context["rejected_questions"][0]["index"], 1)

    def test_overlong_hint_is_repaired_instead_of_truncated(self) -> None:
        response = _response(self.flow.contract_stage_ids)
        response["understanding_checks"][0]["hints"][0]["text"] = "x" * 501
        repaired = _hints("Use the supported relationship")
        state = ConversationState(
            conversation_id="hint-repair-test",
            user_input="Why does parsing fail?",
            intent_context=IntentContext(intents=(TaskIntent.DEBUG,), specificity=Specificity.NARROW, explicit_targets=()),
        )
        retrieval = RetrievalResult(evidence=self.evidence, coverage_status="strong", sufficient=True)

        with patch("services.response_generation.comprehension._complete_generation", return_value=response), patch(
            "services.response_generation.comprehension.repair_hint_ladders", return_value=[repaired]
        ) as repair:
            result = generate_comprehension_explanation(state=state, retrieval_result=retrieval, llm_config=object())

        self.assertEqual([hint.to_dict() for hint in result.understanding_checks[0].hints], repaired)
        self.assertEqual(result.hint_repair_attempts, 1)
        self.assertEqual(repair.call_args.kwargs["context"]["rejected_hint_ladders"][0]["question_index"], 0)

    def test_understanding_check_evidence_must_support_its_reasoning_stages(self) -> None:
        other = EvidenceItem(
            SourceCategory.SOURCE_CODE,
            "repo:b.py:L1-L2",
            "def unrelated(): pass",
            metadata={"path": "b.py"},
        )
        response = _response(self.flow.contract_stage_ids)
        response["understanding_checks"][0]["evidence_refs"] = ["repo:b.py:L1-L2"]

        with self.assertRaisesRegex(FlowValidationError, "does not support"):
            _validate_response(response, evidence=(*self.evidence, other), flow_plan=self.flow)

    def test_generation_payload_omits_legacy_concept_role_metadata(self) -> None:
        state = ConversationState(
            conversation_id="test",
            user_input="Why does parsing fail?",
            intent_context=IntentContext(intents=(TaskIntent.DEBUG,), specificity=Specificity.NARROW, explicit_targets=()),
        )
        retrieval = RetrievalResult(evidence=self.evidence, coverage_status="strong", sufficient=True)
        events: list[tuple[str, dict]] = []

        with patch(
            "services.response_generation.comprehension._complete_generation",
            return_value=_response(self.flow.contract_stage_ids),
        ):
            result = generate_comprehension_explanation(
                state=state,
                retrieval_result=retrieval,
                llm_config=object(),
                log_event=lambda event, payload: events.append((event, dict(payload))),
            )

        request = next(payload for event, payload in events if event == "comprehension_generation_request_payload")
        self.assertNotIn("comprehension_plan", request["payload"])
        self.assertEqual(request["payload"]["request_context"]["task_goal"], "Why does parsing fail?")

    def test_rich_presentation_blocks_render_as_readable_markdown(self) -> None:
        response = _response(self.flow.contract_stage_ids)
        response["presentation_sections"] = _sections(
            self.flow.contract_stage_ids,
            first_title="How the failure happens",
        )
        placement = self.flow.contract_stage_ids[-1]
        response["presentation_lists"] = [
            {
                "placement_stage_id": placement,
                "order": 1,
                "title": "What to check",
                "ordered": True,
                "items": [{"text": "Inspect the parser input.", "evidence_refs": ["repo:a.py:L1-L4"]}],
            }
        ]
        response["examples"] = [
            {
                "placement_stage_id": placement,
                "order": 2,
                "title": "Request example",
                "language": "json",
                "content": '{"value": "sample"}',
                "provenance": "conceptual_from_evidence",
                "evidence_refs": ["repo:a.py:L1-L4"],
            }
        ]
        response["comparison_tables"] = [
            {
                "placement_stage_id": placement,
                "order": 3,
                "title": "Parser outcomes",
                "columns": ["Input", "Outcome"],
                "rows": [
                    {"cells": ["valid", "accepted"], "evidence_refs": ["repo:a.py:L1-L4"]},
                    {"cells": ["invalid", "rejected"], "evidence_refs": ["repo:a.py:L1-L4"]},
                ],
            }
        ]
        response["additional_implementation_observations"] = [
            {
                "text": "The parser is implemented in one function.",
                "why_it_matters": "This keeps the parsing boundary easy to inspect.",
                "evidence_refs": ["repo:a.py:L1-L4"],
            }
        ]

        result = _validate_response(response, evidence=self.evidence, flow_plan=self.flow)

        self.assertIn("### How the failure happens", result.markdown)
        self.assertIn("1. Inspect the parser input.", result.markdown)
        self.assertIn("```json", result.markdown)
        self.assertIn("Conceptual example synthesized", result.markdown)
        self.assertIn("| Input | Outcome | Sources |", result.markdown)
        self.assertIn("### Additional implementation observations", result.markdown)
        self.assertIn("**Why it matters:**", result.markdown)

    def test_presentation_sections_must_partition_stage_order(self) -> None:
        response = _response(self.flow.contract_stage_ids)
        response["presentation_sections"][0]["stage_ids"] = list(reversed(self.flow.contract_stage_ids))
        with self.assertRaisesRegex(FlowValidationError, "partition ordered_stage_ids"):
            _validate_response(response, evidence=self.evidence, flow_plan=self.flow)


def _response(stage_ids: tuple[str, ...]) -> dict:
    return {
        "ordered_stage_ids": list(stage_ids),
        "stages": [
            {
                "stage_id": stage_id,
                "title": stage_id,
                "sentences": [
                    {
                        "text": f"Evidence addresses {stage_id}.",
                        "kind": "code_claim",
                        "evidence_refs": ["repo:a.py:L1-L4"],
                    }
                ],
            }
            for stage_id in stage_ids
        ],
        "understanding_checks": [
            {
                "id": "q1",
                "intent": "debug",
                "target_stage_ids": ["debug.cause"],
                "prerequisite_stage_ids": ["debug.symptom", "debug.evidence", "debug.cause"],
                "stem_family": "what_distinguishes",
                "reasoning_focus": "evidence identifies the supported cause",
                "selection_reason": "The causal transition is the central debugging conclusion.",
                "question": "What distinguishes the cause?",
                "expected_answer_points": ["The evidence"],
                "hints": _hints("Compare the symptom and evidence"),
                "evidence_refs": ["repo:a.py:L1-L4"],
            }
        ],
        "presentation_sections": _sections(stage_ids),
        "presentation_lists": [],
        "examples": [],
        "comparison_tables": [],
        "additional_implementation_observations": [],
        "concept_definitions": [],
        "source_attributions": [],
        "next_checks": [],
        "render_notes": {"title": "Debugging", "summary": "A grounded diagnosis."},
    }


def _hints(subject: str) -> list[dict[str, str]]:
    return [
        {"kind": "direction", "text": f"Decide what reasoning step applies: {subject}."},
        {"kind": "focus", "text": f"Focus on the relevant supported stage: {subject}."},
        {"kind": "scaffold", "text": f"Begin the connection, then complete its consequence: {subject}."},
    ]


def _sections(stage_ids: tuple[str, ...], *, first_title: str = "How it works") -> list[dict]:
    if len(stage_ids) <= 2:
        return [{"id": "opening", "title": "", "stage_ids": list(stage_ids)}]
    sections = [{"id": "opening", "title": "", "stage_ids": list(stage_ids[:1])}]
    for index, offset in enumerate(range(1, len(stage_ids), 3), start=1):
        sections.append(
            {
                "id": f"details_{index}",
                "title": first_title if index == 1 else "Result and implications",
                "stage_ids": list(stage_ids[offset : offset + 3]),
            }
        )
    return sections


if __name__ == "__main__":
    unittest.main()
