from __future__ import annotations

import unittest

from tests.qualification_test_support import QualificationDecision
from services.retrieval.workspace.pipeline.execution_flow.file_trace_evidence import (
    FileTraceSeed,
    build_file_trace_evidence,
)


class FileTraceEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.promoted = QualificationDecision(
            "source", "promote", "navigation_only", "The test entry point is useful.", ("Visible handoff.",),
        )
        self.endpoint = QualificationDecision(
            "endpoint", "promote", "navigation_only", "The worker is a useful handoff.", (), ("Find the worker.",),
        )
        self.seed = FileTraceSeed(
            path="src/testRunner/unittests/tscWatch/helpers.ts",
            source_path="src/testRunner/unittests/tsbuild/watchMode.ts",
            source_observation_id="source",
            endpoint_observation_id="endpoint",
            endpoint_symbol="checkOutputErrorsInitial",
            action_id="file-action",
            obligation_id="ordered_mechanism",
            relationship_direction="outgoing",
            relationship_kinds=("calls",),
            obligation_ids=("ordered_mechanism", "why"),
            connection_summary={
                "direct_call_site_count": 5,
                "destination_symbols": [
                    {"symbol": "checkOutputErrorsInitial", "call_site_count": 2, "call_lines": [145, 575]},
                    {"symbol": "checkOutputErrorsIncremental", "call_site_count": 3, "call_lines": [641, 883, 890]},
                ],
                "localized_source_owners": ["createSolutionAndWatchModeOfProject"],
            },
        )

    def test_serializes_structural_participant_without_source_snippet(self) -> None:
        traces = build_file_trace_evidence((self.seed,), (self.promoted, self.endpoint), {"source": "island_watch"})

        self.assertEqual(len(traces), 1)
        trace = traces[0].to_dict()
        self.assertEqual(trace["path"], "src/testRunner/unittests/tscWatch/helpers.ts")
        self.assertEqual(trace["source_path"], "src/testRunner/unittests/tsbuild/watchMode.ts")
        self.assertEqual(trace["source_island_id"], "island_watch")
        self.assertEqual(trace["relationship_kinds"], ("calls",))
        self.assertEqual(trace["obligation_ids"], ("ordered_mechanism", "why"))
        self.assertEqual(trace["connection_summary"]["direct_call_site_count"], 5)
        self.assertNotIn("snippet", trace)
        self.assertNotIn("line_start", trace)

    def test_requires_promoted_source_and_island_provenance_but_not_endpoint_support(self) -> None:
        rejected = QualificationDecision("source", "reject", "insufficient", "irrelevant", ())
        unsupported = QualificationDecision("source", "defer", "insufficient", "incomplete", ())

        rejected_endpoint = QualificationDecision("endpoint", "reject", "insufficient", "irrelevant", ())

        self.assertEqual(build_file_trace_evidence((self.seed,), (rejected, self.endpoint), {"source": "island_watch"}), ())
        self.assertEqual(build_file_trace_evidence((self.seed,), (unsupported, self.endpoint), {"source": "island_watch"}), ())
        self.assertEqual(build_file_trace_evidence((self.seed,), (self.promoted, self.endpoint), {}), ())
        retained = build_file_trace_evidence((self.seed,), (self.promoted, rejected_endpoint), {"source": "island_watch"})
        self.assertEqual(len(retained), 1)
        self.assertEqual(retained[0].endpoint_qualification, "reject/insufficient")

    def test_retains_repeated_file_participation_without_an_exact_destination_snippet(self) -> None:
        structural_only = FileTraceSeed(
            path="src/testRunner/unittests/tscWatch/helpers.ts",
            source_path="src/testRunner/unittests/tsbuild/watchMode.ts",
            source_observation_id="source",
            endpoint_observation_id="",
            endpoint_symbol="",
            action_id="structural-file-participation",
            obligation_id="ordered_mechanism",
            relationship_direction="outgoing",
            relationship_kinds=("calls",),
            connection_summary={"direct_call_site_count": 18, "localized_source_owners": ["one", "two"]},
        )

        trace = build_file_trace_evidence((structural_only,), (self.promoted,), {"source": "island_watch"})[0]

        self.assertEqual(trace.endpoint_qualification, "not_qualified")
        self.assertIn("repeated direct file-to-file calls", trace.reason)

    def test_deduplicates_file_island_pair_and_collects_all_by_default(self) -> None:
        duplicate = FileTraceSeed(
            path="src/testRunner/unittests/tscWatch/helpers.ts",
            source_path="src/testRunner/unittests/tsbuild/watchMode.ts",
            source_observation_id="source",
            endpoint_observation_id="endpoint",
            endpoint_symbol="checkOutputErrorsInitial",
            action_id="second-action",
            obligation_id="effect",
            relationship_direction="outgoing",
            relationship_kinds=("calls",),
        )
        other = FileTraceSeed(
            path="src/compiler/builder.ts",
            source_path="src/compiler/builderState.ts",
            source_observation_id="other-source",
            endpoint_observation_id="other-endpoint",
            endpoint_symbol="updateProgram",
            action_id="other-action",
            obligation_id="effect",
            relationship_direction="outgoing",
            relationship_kinds=("calls",),
        )
        other_decision = QualificationDecision("other-source", "promote", "direct_evidence", "Relevant", ("Visible.",))
        other_endpoint = QualificationDecision("other-endpoint", "promote", "navigation_only", "Handoff", (), ("Find caller.",))
        islands = {"source": "island_watch", "other-source": "island_builder"}

        all_traces = build_file_trace_evidence((self.seed, duplicate, other), (self.promoted, self.endpoint, other_decision, other_endpoint), islands)
        one = build_file_trace_evidence((self.seed, duplicate, other), (self.promoted, self.endpoint, other_decision, other_endpoint), islands, max_traces=1)

        self.assertEqual(len(one), 1)
        self.assertEqual(len(all_traces), 2)
        self.assertEqual([item.path for item in all_traces], [self.seed.path, other.path])


if __name__ == "__main__":
    unittest.main()
