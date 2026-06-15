from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from services.retrieval.server import RuntimeState, _safe_run_id


class RetrievalServerStateTests(unittest.TestCase):
    def test_health_reports_default_workspace_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state = RuntimeState(Path(temp_dir))

            health = state.public_health()

            self.assertEqual(health["status"], "ok")
            self.assertEqual(health["workspace_root"], str(Path(temp_dir).resolve()))
            self.assertFalse(health["config_exists"])
            self.assertFalse(health["env_exists"])

    def test_update_config_persists_non_secret_project_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state = RuntimeState(root)

            config = state.update_config(
                {
                    "enabled_source_categories": ["source_code", "issue_tracker"],
                    "connections": {
                        "mcp_sources": [
                            {
                                "name": "github-issues",
                                "source_category": "issue_tracker",
                                "command": "example-mcp",
                                "query_tool_name": "search_issues",
                            }
                        ]
                    },
                }
            )

            self.assertTrue((root / ".guided-intelligence" / "config.json").exists())
            self.assertEqual(config["enabled_source_categories"], ["source_code", "issue_tracker"])
            self.assertEqual(config["connections"]["mcp_sources"][0]["name"], "github-issues")

    def test_run_listing_reads_existing_run_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state = RuntimeState(root)
            run_dir = root / ".guided-intelligence" / "runs" / "run-1"
            run_dir.mkdir(parents=True)
            (run_dir / "orchestration-result.json").write_text(
                """
{
  "retrieval_result": {
    "coverage_status": "partial",
    "sufficient": false,
    "evidence": [{"source_id": "repo-pre:src/a.ts:L1-L4"}],
    "retrieval_summary": {
      "stop_reason": "late_synthesis_complete",
      "retrieval_plan": {"raw_prompt": "Explain parser behavior."}
    }
  },
  "response_payload": {"content": "Parser behavior explanation."}
}
""".strip(),
                encoding="utf-8",
            )

            runs = state.list_runs()

            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0]["run_id"], "run-1")
            self.assertEqual(runs[0]["coverage_status"], "partial")
            self.assertEqual(runs[0]["selected_count"], 1)

    def test_safe_run_id_removes_path_characters(self) -> None:
        self.assertEqual(_safe_run_id("../bad run"), "bad-run")


if __name__ == "__main__":
    unittest.main()
