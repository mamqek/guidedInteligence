from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.models import EvidenceItem
from services.retrieval.codex.cli import resolve_codex_command
from services.retrieval.codex.provider import (
    CodexRetrievalError,
    _artifact_trace_summary,
    _classify_artifact_path,
    _codex_path_prefixes,
    _codex_coverage_status,
    _codex_prompt,
    _evidence_connections_from_payload,
    _evidence_from_payload,
    _enrich_codex_evidence_artifacts,
    load_codex_prompt_profile,
)


class CodexProviderTests(unittest.TestCase):
    def test_efficient_profile_restores_compact_prompt_and_schema(self) -> None:
        template, schema = load_codex_prompt_profile("efficient")
        prompt = _codex_prompt(
            "Explain the code context needed for this issue.\n\nTitle: Broken behavior",
            template=template,
            retrieval_hints={"recommended_assistance_mode": "teach", "product_boundary": "explain_plan_suggest_only"},
        )

        self.assertIn("Select the smallest evidence set", prompt)
        self.assertNotIn("Investigation process", prompt)
        self.assertIn("Do not inspect CodeRepoQA raw issue JSON", prompt)
        self.assertIn('"recommended_assistance_mode": "teach"', prompt)
        self.assertIn("Never retrieve with the goal of producing a final fix, patch, or implementation", prompt)
        self.assertIn("Prefer source authoring files over generated/emitted files", prompt)
        self.assertIn("Do not select bundled/generated CLI output", prompt)
        self.assertIn("deterministic post-processing will audit this judgment", prompt)
        self.assertIn("evidence_connections", schema["required"])
        self.assertIn("evidence_id", schema["properties"]["evidence"]["items"]["required"])
        self.assertIn("Evidence connection requirements", prompt)
        self.assertIn("artifact_kind", schema["properties"]["evidence"]["items"]["properties"])

    def test_responsibility_complete_profile_owns_expanded_prompt_and_schema(self) -> None:
        template, schema = load_codex_prompt_profile("responsibility-complete")
        prompt = _codex_prompt(
            "Issue packet",
            template=template,
            retrieval_hints={"recommended_assistance_mode": "work", "product_boundary": "explain_plan_suggest_only"},
        )
        required = schema["required"]
        evidence_schema = schema["properties"]["evidence"]
        item_schema = evidence_schema["items"]

        self.assertIn("Prefer implementation owners over broad architectural files", prompt)
        self.assertIn("at least one primary item is a likely implementation owner", prompt)
        self.assertIn('"recommended_assistance_mode": "work"', prompt)
        self.assertIn("Treat these hints as planning metadata, not evidence", prompt)
        self.assertIn("include a coverage_gaps or answer_blocking_uncertainties entry explaining that limitation", prompt)
        self.assertIn("Do not select bundled/generated CLI output", prompt)
        self.assertIn("deterministic post-processing will audit this judgment", prompt)
        self.assertIn("issue_analysis", required)
        self.assertIn("coverage_gaps", required)
        self.assertEqual(evidence_schema["maxItems"], 6)
        self.assertIn("file_role", item_schema["required"])
        self.assertIn("relevance", item_schema["required"])
        self.assertIn("confidence", item_schema["required"])
        self.assertIn("implementation_owner", item_schema["properties"]["file_role"]["enum"])
        self.assertIn("evidence_connections", required)
        self.assertIn("evidence_id", item_schema["required"])

    def test_evidence_connections_are_remapped_to_selected_source_refs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "src" / "flow.py"
            source.parent.mkdir()
            source.write_text("first()\nsecond()\n", encoding="utf-8")
            payload = {
                "evidence": [
                    {
                        "evidence_id": "entry",
                        "file": "src/flow.py",
                        "line_start": 1,
                        "line_end": 1,
                        "claim_supported": "The flow starts here.",
                        "why_relevant": "Entry point.",
                        "coverage_area": "entry",
                    },
                    {
                        "evidence_id": "target",
                        "file": "src/flow.py",
                        "line_start": 2,
                        "line_end": 2,
                        "claim_supported": "The flow continues here.",
                        "why_relevant": "Target.",
                        "coverage_area": "target",
                    },
                ],
                "evidence_connections": [
                    {
                        "source_evidence_id": "entry",
                        "target_evidence_id": "target",
                        "relationship_kind": "control_flow",
                        "label": "calls",
                        "description": "The entry invokes the target.",
                        "grounding": "direct",
                        "confidence": "high",
                    }
                ],
            }
            evidence = _evidence_from_payload(payload, workspace_root=root)
            graph = _evidence_connections_from_payload(payload, evidence=evidence)

        self.assertEqual(graph["version"], 1)
        self.assertEqual(graph["connections"][0]["source_ref"], "workspace:src/flow.py:L1-L1")
        self.assertEqual(graph["connections"][0]["target_ref"], "workspace:src/flow.py:L2-L2")

    def test_evidence_connections_drop_dangling_self_and_duplicate_edges(self) -> None:
        evidence = (
            EvidenceItem(
                source_category="source_code",
                source_id="workspace:a.py:L1-L2",
                snippet="a()",
                metadata={"evidence_id": "a"},
            ),
            EvidenceItem(
                source_category="source_code",
                source_id="workspace:b.py:L1-L2",
                snippet="b()",
                metadata={"evidence_id": "b"},
            ),
        )
        valid = {
            "source_evidence_id": "a",
            "target_evidence_id": "b",
            "relationship_kind": "data_flow",
            "label": "passes data",
            "description": "A passes structured data to B.",
            "grounding": "inferred",
            "confidence": "high",
        }
        payload = {
            "evidence_connections": [
                valid,
                dict(valid),
                {**valid, "target_evidence_id": "a"},
                {**valid, "target_evidence_id": "missing"},
            ]
        }

        graph = _evidence_connections_from_payload(payload, evidence=evidence)

        self.assertEqual(len(graph["connections"]), 1)
        self.assertEqual(graph["connections"][0]["confidence"], "medium")

    def test_unknown_profile_fails_explicitly(self) -> None:
        with self.assertRaisesRegex(CodexRetrievalError, "Unknown Codex prompt profile"):
            load_codex_prompt_profile("missing-profile")

    def test_codex_prompt_accepts_old_template_without_hints_placeholder(self) -> None:
        prompt = _codex_prompt(
            "Issue packet",
            template="Question:\n{{USER_PROMPT}}\n",
            retrieval_hints={"recommended_assistance_mode": "teach"},
        )

        self.assertEqual(prompt, "Question:\nIssue packet\n")

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

    def test_deterministic_artifact_classification_marks_bin_lib_as_built(self) -> None:
        classification = _classify_artifact_path("bin/lib.d.ts")

        self.assertEqual(classification["deterministic_file_role"], "baseline_or_generated")
        self.assertEqual(classification["deterministic_artifact_kind"], "built_or_distribution_artifact")
        self.assertIn("path_contains_bin", classification["reasons"])

    def test_deterministic_artifact_classification_marks_src_lib_as_source(self) -> None:
        classification = _classify_artifact_path("src/lib/extensions.d.ts")

        self.assertEqual(classification["deterministic_file_role"], "implementation")
        self.assertEqual(classification["deterministic_artifact_kind"], "source_authoring_file")

    def test_built_artifact_snippet_traces_to_typescript_source_library_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "bin").mkdir()
            (root / "src" / "lib").mkdir(parents=True)
            (root / "Jakefile.js").write_text(
                'var libraryDirectory = "src/lib/";\n'
                'var librarySourceMap = [\n'
                '  { target: "lib.d.ts", sources: ["core.d.ts", "extensions.d.ts"] },\n'
                "];\n",
                encoding="utf-8",
            )
            snippet = "interface ArrayBuffer {\n    byteLength: number;\n}\n"
            (root / "bin" / "lib.d.ts").write_text("header\n" + snippet, encoding="utf-8")
            (root / "src" / "lib" / "core.d.ts").write_text("interface Object {}\n", encoding="utf-8")
            (root / "src" / "lib" / "extensions.d.ts").write_text(snippet, encoding="utf-8")
            payload = {
                "evidence": [
                    {
                        "file": "bin/lib.d.ts",
                        "line_start": 2,
                        "line_end": 4,
                        "file_role": "implementation_owner",
                        "claim_supported": "ArrayBuffer is present.",
                        "why_relevant": "It is the selected built surface.",
                        "coverage_area": "state_or_representation",
                    }
                ]
            }

            evidence = _evidence_from_payload(payload, workspace_root=root)
            enriched, trace = _enrich_codex_evidence_artifacts(evidence, workspace_root=root)

        self.assertEqual(enriched[0].metadata["deterministic_file_role"], "baseline_or_generated")
        self.assertEqual(enriched[0].metadata["artifact_role_agreement"], "mismatch")
        self.assertEqual(enriched[0].metadata["source_trace"]["status"], "found")
        self.assertEqual(
            enriched[0].metadata["source_trace"]["matched_source_files"][0]["file"],
            "src/lib/extensions.d.ts",
        )
        self.assertEqual(trace[0]["source_trace"]["status"], "found")

    def test_built_artifact_trace_not_found_is_explicit_and_does_not_drop_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "bin").mkdir()
            (root / "src" / "lib").mkdir(parents=True)
            (root / "Jakefile.js").write_text(
                'var libraryDirectory = "src/lib/";\n'
                'var librarySourceMap = [{ target: "lib.d.ts", sources: ["core.d.ts"] }];\n',
                encoding="utf-8",
            )
            (root / "bin" / "lib.d.ts").write_text("function selectedOnly() {}\n", encoding="utf-8")
            (root / "src" / "lib" / "core.d.ts").write_text("interface Object {}\n", encoding="utf-8")
            payload = {
                "evidence": [
                    {
                        "file": "bin/lib.d.ts",
                        "line_start": 1,
                        "line_end": 1,
                        "claim_supported": "Selected text exists.",
                        "why_relevant": "It is selected.",
                        "coverage_area": "supporting_context",
                    }
                ]
            }

            evidence = _evidence_from_payload(payload, workspace_root=root)
            enriched, trace = _enrich_codex_evidence_artifacts(evidence, workspace_root=root)

        self.assertEqual(len(enriched), 1)
        self.assertEqual(enriched[0].metadata["source_trace"]["status"], "not_found")
        self.assertEqual(trace[0]["source_trace"]["reason"], "build_mapping_found_but_no_matching_source_text")

    def test_only_built_evidence_without_source_trace_downgrades_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "bin").mkdir()
            (root / "bin" / "lib.d.ts").write_text("declare var Missing: unknown;\n", encoding="utf-8")
            payload = {
                "evidence": [
                    {
                        "file": "bin/lib.d.ts",
                        "line_start": 1,
                        "line_end": 1,
                        "claim_supported": "Missing exists.",
                        "why_relevant": "It is selected.",
                        "coverage_area": "supporting_context",
                    }
                ]
            }

            evidence = _evidence_from_payload(payload, workspace_root=root)
            enriched, trace = _enrich_codex_evidence_artifacts(evidence, workspace_root=root)

        self.assertEqual(_artifact_trace_summary(trace)["built_or_generated_count"], 1)
        self.assertEqual(_codex_coverage_status(enriched, trace), "partial")

    def test_old_codex_payload_without_artifact_fields_still_enriches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "src" / "owner.ts"
            source.parent.mkdir()
            source.write_text("function owner() {}\n", encoding="utf-8")
            payload = {
                "evidence": [
                    {
                        "file": "src/owner.ts",
                        "line_start": 1,
                        "line_end": 1,
                        "claim_supported": "Owner exists.",
                        "why_relevant": "It owns behavior.",
                        "coverage_area": "implementation_owner",
                    }
                ]
            }

            evidence = _evidence_from_payload(payload, workspace_root=root)
            enriched, trace = _enrich_codex_evidence_artifacts(evidence, workspace_root=root)

        self.assertEqual(enriched[0].metadata["deterministic_file_role"], "implementation")
        self.assertEqual(enriched[0].metadata["source_trace"]["status"], "not_applicable")
        self.assertEqual(trace[0]["artifact_role_agreement"], "unknown")

    def test_codex_path_prefixes_include_project_venv_and_helper_dirs(self) -> None:
        prefixes = _codex_path_prefixes((str(Path.home() / ".codex" / ".sandbox-bin" / "codex.exe"),))

        self.assertTrue(any(value.endswith(r".venv\Scripts") for value in prefixes))
        if (Path.home() / ".codex" / "plugins" / ".plugin-appserver").is_dir():
            self.assertIn(str(Path.home() / ".codex" / "plugins" / ".plugin-appserver"), prefixes)

    def test_resolve_codex_command_prefers_configured_cli_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            codex_path = Path(temp_dir) / "codex.exe"
            codex_path.write_text("", encoding="utf-8")

            with patch.dict(os.environ, {"CODEX_CLI_PATH": str(codex_path)}):
                self.assertEqual(resolve_codex_command(("codex",)), (str(codex_path),))


if __name__ == "__main__":
    unittest.main()

