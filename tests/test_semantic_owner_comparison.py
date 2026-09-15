import unittest
from unittest.mock import patch

from testing.codeRepoQA.semantic_owner_comparison import compare


class SemanticOwnerComparisonTests(unittest.TestCase):
    def payload(self):
        return {"question": "How does a signature change propagate?",
                "incumbent": {"source_text": "return references.get(path);"},
                "challenger": {"source_text": "if (changed) queue.push(dependent);"}}

    def result(self):
        return {"outcome": "replace", "incumbent_behavior": "lookup",
                "incumbent_limitation": "no propagation", "incumbent_quote": "L1",
                "challenger_behavior": "conditional queueing", "challenger_limitation": "no consumer",
                "challenger_quote": "L1", "reason": "shows propagation",
                "gain": "conditional queueing", "lost_behavior": "lookup details"}

    @patch("testing.codeRepoQA.semantic_owner_comparison.complete_json")
    def test_all_outcomes_and_source_only_payload(self, complete):
        for outcome in ("replace", "complementary", "no_clear_improvement"):
            complete.return_value = {**self.result(), "outcome": outcome}
            self.assertEqual(compare(object(), self.payload())["outcome"], outcome)
        self.assertNotIn("ranking_key", str(complete.call_args))

    @patch("testing.codeRepoQA.semantic_owner_comparison.complete_json")
    def test_quoted_code_uses_line_ids_not_code_in_schema(self, complete):
        complete.return_value = self.result()
        payload = self.payload()
        payload["incumbent"]["source_text"] = 'return references.get("path");'
        result = compare(object(), payload)
        schema = complete.call_args.kwargs["response_format"]["json_schema"]["schema"]
        self.assertEqual(schema["properties"]["incumbent_quote"]["enum"], ["L1"])
        self.assertEqual(result["incumbent_quote"], 'return references.get("path");')

    @patch("testing.codeRepoQA.semantic_owner_comparison.complete_json")
    def test_invalid_receipts_fail_without_fallback(self, complete):
        complete.return_value = {**self.result(), "challenger_quote": "imaginary"}
        with self.assertRaisesRegex(ValueError, "Unverifiable"):
            compare(object(), self.payload())

    @patch("testing.codeRepoQA.semantic_owner_comparison.complete_json")
    def test_llm_failure_is_explicit(self, complete):
        complete.side_effect = RuntimeError("provider unavailable")
        with self.assertRaisesRegex(RuntimeError, "provider unavailable"):
            compare(object(), self.payload())

    def test_missing_question_fails_before_llm(self):
        with self.assertRaises(ValueError):
            compare(object(), {**self.payload(), "question": ""})
