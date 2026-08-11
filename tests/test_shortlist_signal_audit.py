from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from testing.codeRepoQA.analyze_shortlist_signals import (
    audit_run,
    protected_implementation_pool,
    render_report,
)


class ShortlistSignalAuditTests(unittest.TestCase):
    def test_oracle_only_paths_are_not_injected_into_replay_candidates(self) -> None:
        with TemporaryDirectory() as root:
            run_dir = Path(root) / "run-test"
            run_dir.mkdir()
            (run_dir / "evaluator-comparison.json").write_text(
                json.dumps(
                    {
                        "case_id": "owner-case",
                        "oracle_implementation_files": ["src/oracle.py"],
                        "retrieved_source_files": ["src/selected.py"],
                    }
                ),
                encoding="utf-8",
            )
            (run_dir / "retrieval-plan.json").write_text(
                json.dumps(
                    {
                        "obligations": [
                            {
                                "id": "explain_why",
                                "evidence_source": "repository",
                                "evidence_boundary": "local",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            events = [
                {
                    "event_type": "tool_call_requested",
                    "payload": {
                        "tool_name": "qdrant_hybrid_search",
                        "reason": "Find conceptual anchors for evidence obligation explain_why.",
                        "arguments": {"query": "Find the mutation owner."},
                    },
                },
                {
                    "event_type": "tool_observation_created",
                    "payload": {
                        "payload": {
                            "results": [
                                {
                                    "path": "src/candidate.py",
                                    "score": 0.5,
                                    "text": "def update_state(): return True",
                                }
                            ],
                            "breakdown": {"dense": [], "sparse": []},
                        }
                    },
                },
            ]
            (run_dir / "retrieval-trace.jsonl").write_text(
                "\n".join(json.dumps(event) for event in events),
                encoding="utf-8",
            )

            audit = audit_run(run_dir)

        self.assertNotIn("src/oracle.py", audit.candidates)
        self.assertIn("src/candidate.py", audit.candidates)
        self.assertIn("src/selected.py", audit.candidates)
        self.assertEqual(audit.initial_queries["explain_why"], "Find the mutation owner.")

    def test_report_states_historical_replay_limitation(self) -> None:
        with TemporaryDirectory() as root:
            run_dir = Path(root) / "run-test"
            run_dir.mkdir()
            (run_dir / "evaluator-comparison.json").write_text(
                json.dumps(
                    {
                        "case_id": "empty-case",
                        "oracle_implementation_files": [],
                        "retrieved_source_files": [],
                    }
                ),
                encoding="utf-8",
            )
            (run_dir / "retrieval-plan.json").write_text(
                json.dumps({"obligations": []}),
                encoding="utf-8",
            )
            (run_dir / "retrieval-trace.jsonl").write_text("", encoding="utf-8")

            report = render_report((audit_run(run_dir),))

        self.assertIn("does not claim byte-for-byte replay", report)

    def test_protected_pool_uses_initial_hybrid_implementation_candidates_only(self) -> None:
        with TemporaryDirectory() as root:
            run_dir = Path(root) / "run-test"
            run_dir.mkdir()
            (run_dir / "evaluator-comparison.json").write_text(
                json.dumps(
                    {
                        "case_id": "owner-case",
                        "oracle_implementation_files": ["src/owner.py"],
                        "retrieved_source_files": [],
                    }
                ),
                encoding="utf-8",
            )
            (run_dir / "retrieval-plan.json").write_text(
                json.dumps({"obligations": []}),
                encoding="utf-8",
            )
            results = [
                {"path": "src/owner.py", "score": 0.8, "text": "def update_state(): pass"},
                {"path": "tests/test_owner.py", "score": 0.9, "text": "def test_owner(): pass"},
            ]
            events = [
                {
                    "event_type": "tool_call_requested",
                    "payload": {
                        "tool_name": "qdrant_hybrid_search",
                        "reason": "Find conceptual anchors for evidence obligation explain_why.",
                        "arguments": {"query": "Find the state owner."},
                    },
                },
                {
                    "event_type": "tool_observation_created",
                    "payload": {"payload": {"results": results, "breakdown": {}}},
                },
            ]
            (run_dir / "retrieval-trace.jsonl").write_text(
                "\n".join(json.dumps(event) for event in events),
                encoding="utf-8",
            )

            audit = audit_run(run_dir)

        self.assertEqual(protected_implementation_pool(audit), ("src/owner.py",))


if __name__ == "__main__":
    unittest.main()
