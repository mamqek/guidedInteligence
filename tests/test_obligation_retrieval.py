from __future__ import annotations

import unittest

from services.intent.models import EvidenceObligation
from services.retrieval.workspace.pipeline.execution_flow.obligation_retrieval import (
    GroundedCandidate,
    ObligationProgress,
    _edge_index,
    _obligation_query,
    _distinctive_terms,
    _semantic_support_score,
    _transition_from_edges,
)


class ObligationRetrievalTests(unittest.TestCase):
    def test_direct_graph_edge_supports_declared_transition(self) -> None:
        source = ObligationProgress(
            EvidenceObligation("trigger", "Establish the trigger.", True),
            candidates=[_candidate("a", "src/a.py")],
        )
        target = ObligationProgress(
            EvidenceObligation("effect", "Establish the effect.", True, ("trigger",)),
            candidates=[_candidate("b", "src/b.py")],
        )
        edges = _edge_index(({"kind": "calls", "source": {"id": "a"}, "target": {"id": "b"}},))

        transition = _transition_from_edges(source, target, edges)

        self.assertEqual(transition, {"from": "trigger", "status": "supported", "relationship": "calls"})

    def test_unconnected_nodes_do_not_claim_a_transition(self) -> None:
        source = ObligationProgress(
            EvidenceObligation("trigger", "Establish the trigger.", True),
            candidates=[_candidate("a", "src/a.py")],
        )
        target = ObligationProgress(
            EvidenceObligation("effect", "Establish the effect.", True, ("trigger",)),
            candidates=[_candidate("b", "src/b.py")],
        )

        self.assertIsNone(_transition_from_edges(source, target, {}))

    def test_obligation_query_does_not_mix_global_search_terms(self) -> None:
        self.assertEqual(
            _obligation_query("Identify validation tests."),
            "Identify validation tests.",
        )

    def test_unresolved_symbols_only_enrich_related_obligations(self) -> None:
        query = _obligation_query(
            "Show how textarea domProps values are serialized.",
            ("domProps.value", "renderVmWithOptions", "unrelatedSymbol"),
        )

        self.assertIn("domProps.value", query)
        self.assertNotIn("renderVmWithOptions", query)
        self.assertNotIn("unrelatedSymbol", query)

    def test_semantic_candidate_requires_obligation_specific_terms(self) -> None:
        expected = {"tests", "instrumentation", "validation", "filesystem", "probes"}

        unrelated = _semantic_support_score(
            expected,
            {"matched_terms": ["filesystem"]},
        )
        related = _semantic_support_score(
            expected,
            {"matched_terms": ["filesystem", "tests", "validation"]},
        )

        self.assertEqual(unrelated, 0.0)
        self.assertGreater(related, 0.0)

    def test_hyphenated_obligation_terms_match_repository_words(self) -> None:
        terms = _distinctive_terms("find module-resolution and web-host boundaries")

        self.assertIn("module", terms)
        self.assertIn("resolution", terms)
        self.assertIn("host", terms)


def _candidate(node_id: str, path: str) -> GroundedCandidate:
    return GroundedCandidate(
        path=path,
        line_start=1,
        line_end=2,
        text="pass",
        score=1.0,
        origin="test",
        node_id=node_id,
    )


if __name__ == "__main__":
    unittest.main()
