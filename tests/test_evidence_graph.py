from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.models import EvidenceItem, RetrievalResult
from core.source_policy import SourceCategory
from services.retrieval import evidence_graph
from services.retrieval.evidence_graph import build_evidence_graph


class EvidenceGraphTests(unittest.TestCase):
    def test_hybrid_graph_uses_selected_refs_and_caps_inferred_confidence(self) -> None:
        evidence = (
            _evidence("workspace:a.py:L1-L3", "a.py", "def start():\n    finish()", "Starts the flow."),
            _evidence("workspace:b.ts:L4-L8", "b.ts", "export function finish() {}", "Finishes the flow."),
        )
        retrieval = RetrievalResult(evidence=evidence, coverage_status="strong", sufficient=True)
        model_response = {
            "root_ref": evidence[0].source_id,
            "connections": [
                {
                    "source_ref": evidence[0].source_id,
                    "target_ref": evidence[1].source_id,
                    "relationship_kind": "data_flow",
                    "label": "passes result",
                    "description": "The Python result is serialized before the TypeScript consumer reads it; the transport is omitted.",
                    "grounding": "inferred",
                    "confidence": "high",
                }
            ],
            "disconnected_evidence": [],
        }
        structural = {"direct_candidates": []}

        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "services.retrieval.evidence_graph._codegraph_edges", return_value=structural
        ), patch("services.retrieval.evidence_graph.complete_json", return_value=model_response):
            result = build_evidence_graph(
                retrieval,
                workspace_root=temp_dir,
                user_prompt="How does the flow cross languages?",
                llm_config=object(),
            )

        graph = result.retrieval_summary["evidence_connections"]
        self.assertEqual(graph["status"], "complete")
        self.assertEqual(graph["connections"][0]["confidence"], "medium")
        self.assertEqual(graph["generation"]["codegraph_candidate_count"], 0)
        self.assertEqual(graph["generation"]["structural_provider"], "codegraph")

    def test_graph_failure_is_explicit_and_does_not_return_structural_fallback(self) -> None:
        evidence = (
            _evidence("workspace:a.py:L1-L2", "a.py", "a()", "A."),
            _evidence("workspace:b.py:L1-L2", "b.py", "b()", "B."),
        )
        retrieval = RetrievalResult(evidence=evidence, coverage_status="strong", sufficient=True)
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "services.retrieval.evidence_graph._codegraph_edges",
            return_value={"direct_candidates": [{"source_ref": evidence[0].source_id, "target_ref": evidence[1].source_id}]},
        ), patch("services.retrieval.evidence_graph.complete_json", side_effect=RuntimeError("model unavailable")):
            result = build_evidence_graph(
                retrieval,
                workspace_root=temp_dir,
                user_prompt="Explain the flow.",
                llm_config=object(),
            )

        graph = result.retrieval_summary["evidence_connections"]
        self.assertEqual(graph["status"], "error")
        self.assertEqual(graph["connections"], [])
        self.assertIn("model unavailable", graph["error"])

    def test_connected_evidence_is_not_reported_as_disconnected(self) -> None:
        evidence = (
            _evidence("a", "a.py", "a()", "A."),
            _evidence("b", "b.py", "b()", "B."),
        )
        response = {
            "root_ref": "a",
            "disconnected_evidence": [{"evidence_ref": "b", "reason": "Model contradiction."}],
        }

        root_ref, disconnected, connected = evidence_graph._graph_coverage(
            response,
            connections=[{"source_ref": "a", "target_ref": "b"}],
            evidence=evidence,
        )

        self.assertEqual(root_ref, "a")
        self.assertEqual(disconnected, [])
        self.assertEqual(connected, {"a", "b"})

    def test_structural_candidates_are_kept_as_direct_backbone_edges(self) -> None:
        connections = evidence_graph._structural_connections(
            codegraph_edges=[
                {
                    "source_ref": "a",
                    "target_ref": "b",
                    "edge_kind": "calls",
                    "source_symbol": "start",
                    "target_symbol": "finish",
                }
            ],
            document_reference_edges=[
                {
                    "source_ref": "b",
                    "target_ref": "doc",
                    "path_constant": "PROMPT_PATH",
                    "document": "contract.md",
                }
            ],
        )

        self.assertEqual(len(connections), 2)
        self.assertEqual(connections[0]["grounding"], "direct")
        self.assertEqual(connections[0]["relationship_kind"], "control_flow")
        self.assertEqual(connections[1]["label"], "loads contract.md")


def _evidence(source_id: str, path: str, snippet: str, claim: str) -> EvidenceItem:
    return EvidenceItem(
        source_category=SourceCategory.SOURCE_CODE,
        source_id=source_id,
        snippet=snippet,
        metadata={"path": path, "line_range": source_id.rsplit(":", 1)[-1], "claim_supported": claim},
    )


if __name__ == "__main__":
    unittest.main()
