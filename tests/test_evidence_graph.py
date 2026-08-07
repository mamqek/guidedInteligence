from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.models import EvidenceItem, RetrievalResult
from core.source_policy import SourceCategory
from services.retrieval import evidence_graph
from services.retrieval.evidence_graph import EvidenceOrganizationError, build_evidence_graph


class EvidenceGraphTests(unittest.TestCase):
    def test_candidate_order_neutralization_is_stable_and_rank_independent(self) -> None:
        evidence = tuple(
            _evidence(f"workspace:item_{index}.py:L1-L2", f"item_{index}.py", f"item_{index}()", f"Item {index}.")
            for index in range(12)
        )

        first = evidence_graph._stable_evidence_permutation(evidence, user_prompt="Explain the flow.")
        second = evidence_graph._stable_evidence_permutation(evidence, user_prompt="Explain the flow.")

        self.assertEqual(first, second)
        self.assertEqual({item.source_id for item in first}, {item.source_id for item in evidence})
        self.assertNotEqual([item.source_id for item in first], [item.source_id for item in evidence])

    def test_candidate_graph_keeps_connections_for_selected_and_unselected_evidence(self) -> None:
        evidence = tuple(
            _evidence(f"workspace:item_{index}.py:L1-L2", f"item_{index}.py", f"item_{index}()", f"Item {index}.")
            for index in range(3)
        )
        direct_edge = {
            "source_ref": evidence[0].source_id,
            "target_ref": evidence[1].source_id,
            "edge_kind": "calls",
            "source_symbol": "item_0",
            "target_symbol": "item_1",
        }
        semantic_edge = {
            "source_ref": evidence[1].source_id,
            "target_ref": evidence[2].source_id,
            "relationship_kind": "data_flow",
            "label": "passes result",
            "description": "The result is passed to item 2.",
            "grounding": "inferred",
            "confidence": "medium",
        }
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "services.retrieval.evidence_graph._codegraph_edges",
            return_value={"direct_candidates": [direct_edge]},
        ):
            connections = evidence_graph.build_candidate_connections(
                evidence,
                workspace_root=temp_dir,
                existing_connections=[semantic_edge],
            )

        self.assertEqual(len(connections), 2)
        connected_refs = {ref for item in connections for ref in (item["source_ref"], item["target_ref"])}
        self.assertEqual(connected_refs, {item.source_id for item in evidence})

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

    def test_codex_organizer_selects_adaptive_subset_and_replaces_evidence(self) -> None:
        evidence = tuple(
            _evidence(f"workspace:item_{index}.py:L1-L2", f"item_{index}.py", f"item_{index}()", f"Item {index}.")
            for index in range(12)
        )
        retrieval = RetrievalResult(evidence=evidence, coverage_status="strong", sufficient=True)
        model_response = _organizer_response(evidence, selected_count=8)
        model_response["assessments"] = {
            item["evidence_ref"]: {key: value for key, value in item.items() if key != "evidence_ref"}
            for item in model_response["assessments"]
        }
        model_response["coverage_facets"][0]["selected_refs"] = [
            *model_response["coverage_facets"][0]["selected_refs"],
            evidence[10].source_id,
        ]
        model_response["disconnected_evidence"] = []
        events: list[tuple[str, dict]] = []

        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "services.retrieval.evidence_graph._codegraph_edges", return_value={"direct_candidates": []}
        ), patch("services.retrieval.evidence_graph.complete_json", return_value=model_response):
            result = build_evidence_graph(
                retrieval,
                workspace_root=temp_dir,
                user_prompt="Explain classification and retrieval.",
                intent_flow={"intents": ["explore", "explain"], "contracts": []},
                organizer_enabled=True,
                llm_config=object(),
                log_event=lambda event, payload: events.append((event, dict(payload))),
            )

        self.assertEqual(len(result.evidence), 8)
        self.assertEqual([item.rank for item in result.evidence], list(range(1, 9)))
        organization = result.retrieval_summary["evidence_organization"]
        self.assertEqual(organization["candidate_count"], 12)
        self.assertEqual(organization["excluded_count"], 4)
        self.assertEqual(len(organization["assessments"]), 12)
        self.assertEqual(len(organization["candidate_evidence"]), 12)
        self.assertEqual(
            [item["source_id"] for item in organization["candidate_evidence"]],
            [item.source_id for item in evidence],
        )
        self.assertNotIn(evidence[10].source_id, organization["coverage_facets"][0]["selected_refs"])
        self.assertEqual(organization["token_usage"]["request_count"], 0)
        self.assertEqual(result.retrieval_summary["evidence_connections"]["status"], "complete")
        self.assertEqual(len(result.retrieval_summary["evidence_connections"]["disconnected_evidence"]), 7)
        self.assertIn("evidence_organization_completed", [event for event, _ in events])

        response_schema = evidence_graph._organizer_response_format(
            tuple(item.source_id for item in evidence), selected_min=8, selected_max=12
        )["json_schema"]["schema"]
        self.assertEqual(response_schema["properties"]["assessments"]["type"], "object")
        self.assertEqual(
            set(response_schema["properties"]["assessments"]["required"]),
            {f"c{index}" for index in range(1, 13)},
        )

    def test_codex_organizer_records_neutralized_model_order_without_reordering_diagnostics(self) -> None:
        evidence = tuple(
            _evidence(f"workspace:item_{index}.py:L1-L2", f"item_{index}.py", f"item_{index}()", f"Item {index}.")
            for index in range(8)
        )
        retrieval = RetrievalResult(evidence=evidence, coverage_status="strong", sufficient=True)
        response = _organizer_response(evidence, selected_count=8)

        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "services.retrieval.evidence_graph._codegraph_edges", return_value={"direct_candidates": []}
        ), patch("services.retrieval.evidence_graph.complete_json", return_value=response):
            result = build_evidence_graph(
                retrieval,
                workspace_root=temp_dir,
                user_prompt="Explain the flow.",
                intent_flow={"intents": ["explain"], "contracts": []},
                organizer_enabled=True,
                neutralize_candidate_order=True,
                llm_config=object(),
            )

        organization = result.retrieval_summary["evidence_organization"]
        self.assertEqual(organization["candidate_order_mode"], "prompt_seeded_stable_permutation")
        self.assertEqual(
            [item["source_id"] for item in organization["candidate_evidence"]],
            [item.source_id for item in evidence],
        )
        self.assertNotEqual(
            [item["source_ref"] for item in organization["model_candidate_order"]],
            [item.source_id for item in evidence],
        )

    def test_codex_organizer_allows_selected_markdown_to_be_disconnected(self) -> None:
        evidence = tuple(
            _evidence(
                f"workspace:item_{index}{'.md' if index == 7 else '.py'}:L1-L2",
                f"item_{index}{'.md' if index == 7 else '.py'}",
                "contract" if index == 7 else f"item_{index}()",
                f"Item {index}.",
            )
            for index in range(8)
        )
        retrieval = RetrievalResult(evidence=evidence, coverage_status="strong", sufficient=True)
        response = _organizer_response(evidence, selected_count=8)

        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "services.retrieval.evidence_graph._codegraph_edges", return_value={"direct_candidates": []}
        ), patch("services.retrieval.evidence_graph.complete_json", return_value=response):
            result = build_evidence_graph(
                retrieval,
                workspace_root=temp_dir,
                user_prompt="Explain the contract.",
                intent_flow={"intents": ["explain"], "contracts": []},
                organizer_enabled=True,
                llm_config=object(),
            )

        disconnected = result.retrieval_summary["evidence_connections"]["disconnected_evidence"]
        self.assertIn(evidence[7].source_id, {item["evidence_ref"] for item in disconnected})

    def test_codex_organizer_repairs_once_then_fails_without_fallback(self) -> None:
        evidence = tuple(
            _evidence(f"workspace:item_{index}.py:L1-L2", f"item_{index}.py", f"item_{index}()", f"Item {index}.")
            for index in range(9)
        )
        retrieval = RetrievalResult(evidence=evidence, coverage_status="strong", sufficient=True)
        invalid = _organizer_response(evidence, selected_count=8)
        invalid["selected_refs"] = [evidence[0].source_id] * 8
        events: list[str] = []

        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "services.retrieval.evidence_graph._codegraph_edges", return_value={"direct_candidates": []}
        ), patch("services.retrieval.evidence_graph.complete_json", side_effect=[invalid, invalid]) as completion:
            with self.assertRaisesRegex(EvidenceOrganizationError, "after one repair attempt"):
                build_evidence_graph(
                    retrieval,
                    workspace_root=temp_dir,
                    user_prompt="Explain the flow.",
                    intent_flow={"intents": ["explain"], "contracts": []},
                    organizer_enabled=True,
                    llm_config=object(),
                    log_event=lambda event, payload: events.append(event),
                )

        self.assertEqual(completion.call_count, 2)
        repair_messages = completion.call_args_list[1].args[1]
        self.assertIn("REPAIR REQUIRED", repair_messages[-1]["content"])
        self.assertIn("selected_refs contains duplicates", repair_messages[-1]["content"])
        self.assertIn("evidence_organization_repair_attempted", events)
        self.assertIn("evidence_organization_failed", events)


def _evidence(source_id: str, path: str, snippet: str, claim: str) -> EvidenceItem:
    return EvidenceItem(
        source_category=SourceCategory.SOURCE_CODE,
        source_id=source_id,
        snippet=snippet,
        metadata={"path": path, "line_range": source_id.rsplit(":", 1)[-1], "claim_supported": claim},
    )


def _organizer_response(evidence: tuple[EvidenceItem, ...], *, selected_count: int) -> dict:
    selected = [item.source_id for item in evidence[:selected_count]]
    return {
        "coverage_facets": [
            {
                "id": "requested-flow",
                "description": "The requested repository flow.",
                "status": "covered",
                "selected_refs": selected,
            }
        ],
        "assessments": [
            {
                "evidence_ref": item.source_id,
                "status": "core" if item.source_id in selected else "redundant",
                "facet_ids": ["requested-flow"] if item.source_id in selected else [],
                "reason": "Supports the requested flow." if item.source_id in selected else "Repeated context.",
            }
            for item in evidence
        ],
        "selected_refs": selected,
        "root_ref": selected[0],
        "connections": [],
        "disconnected_evidence": [
            {"evidence_ref": ref, "reason": "No direct relationship is established by the fixture."}
            for ref in selected[1:]
        ],
    }


if __name__ == "__main__":
    unittest.main()
