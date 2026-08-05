from __future__ import annotations

import unittest

from services.comprehension.models import ComprehensionPlan, DepthPolicy
from services.response_generation.comprehension import _collect_checks_from_response


class UnderstandingCheckContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = ComprehensionPlan(
            task_goal="Explain Parser behavior.",
            answer_scope="Parser behavior.",
            relevant_artifacts=(),
            concepts=(),
            concept_dependencies=(),
            explanation_sequence=(),
            depth_policy=DepthPolicy(mode="default", assumption_statement=""),
            understanding_check=None,
        )
        self.answer_flow = {
            "symptom": "Parser rejects the input.",
            "evidence": "`parseInput` checks the token.",
            "cause": "The token is unsupported.",
            "tested_concepts": ["Parser"],
        }
        self.check = {
            "id": "custom-id",
            "role": "reader",
            "question_type": "why",
            "question": "Why does Parser reject this input?",
            "expected_answer_points": [
                "Parser rejects the input.",
                "`parseInput` checks the token.",
                "The token is unsupported.",
            ],
            "hint": "Follow the token check.",
            "evidence_refs": ["repo:parser.py:L1-L4"],
            "origin": "model_generated",
            "tested_concepts": ["Parser"],
            "answer_point_map": [
                {"kind": "symptom", "point": "Parser rejects the input."},
                {"kind": "evidence", "point": "`parseInput` checks the token."},
                {"kind": "cause", "point": "The token is unsupported."},
            ],
        }

    def collect(self, checks):
        return _collect_checks_from_response(
            checks,
            markdown="Parser rejects the input because parseInput checks an unsupported token.",
            plan=self.plan,
            allowed_refs={"repo:parser.py:L1-L4"},
            answer_flow=self.answer_flow,
        )

    def test_preserves_every_accepted_model_field(self) -> None:
        checks, rejected, raw_count = self.collect([self.check])

        self.assertEqual(raw_count, 1)
        self.assertEqual(rejected, [])
        self.assertEqual(checks[0].to_dict(), self.check)

    def test_rejects_missing_fields_instead_of_inventing_defaults(self) -> None:
        invalid = dict(self.check)
        invalid.pop("id")

        checks, rejected, _ = self.collect([invalid])

        self.assertEqual(checks, ())
        self.assertEqual(rejected[0]["reason"], "missing_required_fields")

    def test_rejects_mismatched_answer_points_instead_of_overwriting_them(self) -> None:
        invalid = dict(self.check)
        invalid["expected_answer_points"] = ["A replacement value."]

        checks, rejected, _ = self.collect([invalid])

        self.assertEqual(checks, ())
        self.assertEqual(rejected[0]["reason"], "expected_answer_points_do_not_match_answer_flow")

    def test_rejects_excess_checks_instead_of_truncating_them(self) -> None:
        checks, rejected, raw_count = self.collect([self.check, self.check, self.check, self.check])

        self.assertEqual(raw_count, 4)
        self.assertEqual(checks, ())
        self.assertEqual(rejected[0]["reason"], "too_many_understanding_checks")


if __name__ == "__main__":
    unittest.main()
