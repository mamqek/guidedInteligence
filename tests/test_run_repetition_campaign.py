from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from testing.codeRepoQA.run_repetition_campaign import is_valid_run


def _write_run(tmp_path, *, evidence, coverage_status="partial", stop_reason=""):
    (tmp_path / "run-metadata.json").write_text(
        json.dumps(
            {
                "retrieval_mode": "codex",
                "codex_model": "gpt-5.6-luna",
                "codex_prompt_profile": "efficient",
                "adaptive_controller_enabled": False,
                "skip_response_generation": True,
                "skip_final_evidence_selection": False,
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "orchestration-result.json").write_text(
        json.dumps(
            {
                "retrieval_result": {
                    "coverage_status": coverage_status,
                    "evidence": evidence,
                    "retrieval_summary": {"stop_reason": stop_reason},
                }
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "evaluator-comparison.json").write_text("{}", encoding="utf-8")


def _ledger():
    return {
        "retrieval_mode": "codex",
        "codex_model": "gpt-5.6-luna",
        "codex_prompt_profile": "efficient",
        "adaptive_controller_enabled": False,
    }


class RunRepetitionCampaignValidityTests(unittest.TestCase):
    def test_zero_evidence_completed_artifacts_are_not_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            _write_run(
                run_dir,
                evidence=[],
                coverage_status="missing",
                stop_reason="codex_returned_no_usable_evidence",
            )

            valid, reason = is_valid_run(run_dir, _ledger())

        self.assertFalse(valid)
        self.assertEqual(
            reason,
            "retrieval returned no usable evidence "
            "(coverage_status=missing, stop_reason=codex_returned_no_usable_evidence)",
        )

    def test_nonempty_completed_retrieval_is_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            _write_run(run_dir, evidence=[{"path": "src/example.py"}])

            result = is_valid_run(run_dir, _ledger())

        self.assertEqual(result, (True, ""))

    def test_controller_setting_mismatch_is_not_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            _write_run(run_dir, evidence=[{"path": "src/example.py"}])
            metadata_path = run_dir / "run-metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["adaptive_controller_enabled"] = True
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

            valid, reason = is_valid_run(run_dir, _ledger())

        self.assertFalse(valid)
        self.assertEqual(reason, "configuration mismatch: adaptive_controller_enabled=True")


if __name__ == "__main__":
    unittest.main()
