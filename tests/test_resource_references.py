from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from services.retrieval.resource_references import resource_reference_between_files


class ResourceReferenceTests(unittest.TestCase):
    def test_resolves_exact_relative_resource_literal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "src" / "loader.py"
            target = root / "src" / "prompts" / "contract.md"
            target.parent.mkdir(parents=True)
            source.write_text('PROMPT = Path(__file__).parent / "prompts/contract.md"\n', encoding="utf-8")
            target.write_text("Contract", encoding="utf-8")

            reference = resource_reference_between_files(root, "src/loader.py", "src/prompts/contract.md")

        self.assertIsNotNone(reference)
        self.assertEqual(reference["edge_kind"], "resource_reference")
        self.assertEqual(reference["literal"], "prompts/contract.md")

    def test_resolves_unique_descendant_for_basename_literal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "services" / "loader.py"
            target = root / "services" / "prompts" / "contract.md"
            target.parent.mkdir(parents=True)
            source.write_text('PROMPT_PATH.parent / "contract.md"\n', encoding="utf-8")
            target.write_text("Contract", encoding="utf-8")

            reference = resource_reference_between_files(root, "services/loader.py", "services/prompts/contract.md")

        self.assertIsNotNone(reference)
        self.assertEqual(reference["target_path"], "services/prompts/contract.md")

    def test_rejects_ambiguous_basename_literal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "services" / "loader.py"
            first = root / "services" / "prompts" / "contract.md"
            second = root / "services" / "templates" / "contract.md"
            first.parent.mkdir(parents=True)
            second.parent.mkdir(parents=True)
            source.write_text('PROMPT_PATH.parent / "contract.md"\n', encoding="utf-8")
            first.write_text("First", encoding="utf-8")
            second.write_text("Second", encoding="utf-8")

            reference = resource_reference_between_files(root, "services/loader.py", "services/prompts/contract.md")

        self.assertIsNone(reference)


if __name__ == "__main__":
    unittest.main()
