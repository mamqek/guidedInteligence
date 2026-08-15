from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from testing.codeRepoQA import generate_retrieval_statistics as statistics


class RetrievalStatisticsSelectionTests(unittest.TestCase):
    def test_native_selection_keeps_first_valid_campaign_run(self) -> None:
        with TemporaryDirectory() as temp_dir:
            test_root = Path(temp_dir)
            case_id = "example-case"
            first = self._write_valid_run(test_root, case_id, "run-20260815T120000Z")
            self._write_valid_run(test_root, case_id, "run-20260815T130000Z")

            with patch.object(statistics, "TEST_ROOT", test_root):
                selected = statistics.select_native(case_id)

        self.assertIsNotNone(selected)
        self.assertEqual(selected.run_id, first.name)

    @staticmethod
    def _write_valid_run(test_root: Path, case_id: str, run_id: str) -> Path:
        run_dir = test_root / case_id / "runs" / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "run-metadata.json").write_text(
            json.dumps({"retrieval_mode": "workspace", "llm_config": {"model": "gpt-5.6-luna"}}),
            encoding="utf-8",
        )
        (run_dir / "evaluator-comparison.json").write_text("{}", encoding="utf-8")
        (run_dir / "orchestration-result.json").write_text(
            json.dumps(
                {
                    "retrieval_result": {
                        "coverage_status": "strong",
                        "sufficient": True,
                        "evidence": [{"path": "owner.py"}],
                    }
                }
            ),
            encoding="utf-8",
        )
        return run_dir


if __name__ == "__main__":
    unittest.main()
