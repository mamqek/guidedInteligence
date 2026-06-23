from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from services.retrieval.codex.provider import (
    CodexRetrievalError,
    _codex_prompt,
    _evidence_from_payload,
    load_codex_prompt_profile,
)


class CodexProviderTests(unittest.TestCase):
    def test_efficient_profile_restores_compact_prompt_and_schema(self) -> None:
        template, schema = load_codex_prompt_profile("efficient")
        prompt = _codex_prompt("Explain the code context needed for this issue.\n\nTitle: Broken behavior", template=template)

        self.assertIn("Select the smallest evidence set", prompt)
        self.assertNotIn("Investigation process", prompt)
        self.assertIn("Do not inspect CodeRepoQA raw issue JSON", prompt)
        self.assertEqual(
            schema["required"],
            ["prompt_summary", "relevant_files", "evidence", "uncertainties"],
        )

    def test_responsibility_complete_profile_owns_expanded_prompt_and_schema(self) -> None:
        template, schema = load_codex_prompt_profile("responsibility-complete")
        prompt = _codex_prompt("Issue packet", template=template)
        required = schema["required"]
        evidence_schema = schema["properties"]["evidence"]
        item_schema = evidence_schema["items"]

        self.assertIn("Prefer implementation owners over broad architectural files", prompt)
        self.assertIn("at least one primary item is a likely implementation owner", prompt)
        self.assertIn("issue_analysis", required)
        self.assertIn("coverage_gaps", required)
        self.assertEqual(evidence_schema["maxItems"], 6)
        self.assertIn("file_role", item_schema["required"])
        self.assertIn("relevance", item_schema["required"])
        self.assertIn("confidence", item_schema["required"])
        self.assertIn("implementation_owner", item_schema["properties"]["file_role"]["enum"])

    def test_unknown_profile_fails_explicitly(self) -> None:
        with self.assertRaisesRegex(CodexRetrievalError, "Unknown Codex prompt profile"):
            load_codex_prompt_profile("missing-profile")

    def test_evidence_mapping_preserves_schema_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "src" / "owner.ts"
            source.parent.mkdir()
            source.write_text("function ownsBehavior() {\n  return true;\n}\n", encoding="utf-8")
            payload = {
                "evidence": [
                    {
                        "file": "src/owner.ts",
                        "line_start": 1,
                        "line_end": 3,
                        "symbol": "ownsBehavior",
                        "file_role": "implementation_owner",
                        "relevance": "primary",
                        "confidence": "high",
                        "claim_supported": "The function owns the behavior.",
                        "why_relevant": "It directly controls the result.",
                        "coverage_area": "implementation_owner",
                    }
                ]
            }

            evidence = _evidence_from_payload(payload, workspace_root=root)

        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0].metadata["symbol"], "ownsBehavior")
        self.assertEqual(evidence[0].metadata["file_role"], "implementation_owner")
        self.assertEqual(evidence[0].metadata["relevance"], "primary")
        self.assertEqual(evidence[0].metadata["confidence"], "high")


if __name__ == "__main__":
    unittest.main()

