from __future__ import annotations

import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.models import AssistanceRequestType, ConversationState, EvidenceItem, PolicyResult, TurnType
from core.source_policy import SourceCategory
from services.retrieval.config import RetrievalEmbeddingConfig, RetrievalQdrantConfig, RunLLMConfig, WorkspaceRetrievalConfig
from services.retrieval.codex.cli import resolve_codex_command
from services.retrieval.codex.provider import (
    CodexRetrievalStage,
    CodexRetrievalError,
    _artifact_trace_summary,
    _classify_artifact_path,
    _codex_path_prefixes,
    _codex_coverage_status,
    _codex_prompt,
    _evidence_conversion_from_payload,
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
            intent_context={"intents": [{"intent": "explain", "description": "Establish how or why the requested behavior works."}], "specificity": "medium", "explicit_targets": []},
        )

        self.assertIn("Select the smallest evidence set", prompt)
        self.assertNotIn("Investigation process", prompt)
        self.assertIn("Do not inspect CodeRepoQA raw issue JSON", prompt)
        self.assertIn('"intent": "explain"', prompt)
        self.assertIn("Never retrieve with the goal of producing a final fix, patch, or implementation", prompt)
        self.assertIn("Prefer source authoring files over generated/emitted files", prompt)
        self.assertIn("Do not select bundled/generated CLI output", prompt)
        self.assertIn("deterministic post-processing will audit this judgment", prompt)
        self.assertNotIn("evidence_connections", schema["required"])
        self.assertNotIn("evidence_id", schema["properties"]["evidence"]["items"]["required"])
        self.assertNotIn("Evidence connection requirements", prompt)
        self.assertIn("artifact_kind", schema["properties"]["evidence"]["items"]["properties"])

    def test_responsibility_complete_profile_owns_expanded_prompt_and_schema(self) -> None:
        template, schema = load_codex_prompt_profile("responsibility-complete")
        prompt = _codex_prompt(
            "Issue packet",
            template=template,
            intent_context={"intents": [{"intent": "change", "description": "Gather context needed to reason about a requested modification without implementing it."}], "specificity": "medium", "explicit_targets": []},
        )
        required = schema["required"]
        evidence_schema = schema["properties"]["evidence"]
        item_schema = evidence_schema["items"]

        self.assertIn("Prefer implementation owners over broad architectural files", prompt)
        self.assertIn("at least one primary item is a likely implementation owner", prompt)
        self.assertIn('"intent": "change"', prompt)
        self.assertIn("neutral outcome context, not evidence and not an Evidence Plan", prompt)
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
        self.assertNotIn("evidence_connections", required)
        self.assertNotIn("evidence_id", item_schema["required"])

    def test_unknown_profile_fails_explicitly(self) -> None:
        with self.assertRaisesRegex(CodexRetrievalError, "Unknown Codex prompt profile"):
            load_codex_prompt_profile("missing-profile")

    def test_organizer_profile_contract_allows_forty_candidates_without_changing_default_profile(self) -> None:
        template, schema = load_codex_prompt_profile("responsibility-complete", organizer_enabled=True)

        self.assertIn("later organizer replaces the normal 2-6 item target", template)
        self.assertEqual(schema["properties"]["evidence"]["maxItems"], 40)
        _, default_schema = load_codex_prompt_profile("responsibility-complete")
        self.assertEqual(default_schema["properties"]["evidence"]["maxItems"], 6)

    def test_codex_prompt_accepts_template_without_intent_context_placeholder(self) -> None:
        prompt = _codex_prompt(
            "Issue packet",
            template="Question:\n{{USER_PROMPT}}\n",
            intent_context={"intents": [{"intent": "explain"}]},
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

    def test_organizer_enabled_conversion_retains_more_than_ten_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            items = []
            for index in range(25):
                path = root / "src" / f"item_{index}.py"
                path.parent.mkdir(exist_ok=True)
                path.write_text(f"VALUE_{index} = {index}\n", encoding="utf-8")
                items.append(
                    {
                        "file": f"src/item_{index}.py",
                        "line_start": 1,
                        "line_end": 1,
                        "claim_supported": f"Item {index} exists.",
                        "why_relevant": "Candidate retention test.",
                        "coverage_area": "candidate",
                    }
                )

            candidates, conversion = _evidence_conversion_from_payload(
                {"evidence": items}, workspace_root=root, limit=40
            )
            default_evidence = _evidence_from_payload({"evidence": items}, workspace_root=root)

        self.assertEqual(len(candidates), 25)
        self.assertEqual(conversion["valid_count"], 25)
        self.assertEqual(conversion["limit_dropped_count"], 0)
        self.assertEqual(len(default_evidence), 10)

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

    def test_codex_retrieval_uses_ignore_user_config_by_default(self) -> None:
        command = self._run_codex_retrieval_and_capture_command()

        self.assertIn("--ignore-user-config", command)

    def test_codex_retrieval_can_allow_user_config(self) -> None:
        command = self._run_codex_retrieval_and_capture_command(codex_ignore_user_config=False)

        self.assertNotIn("--ignore-user-config", command)

    def _run_codex_retrieval_and_capture_command(self, *, codex_ignore_user_config: bool = True) -> list[str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "src").mkdir()
            (root / "src" / "owner.py").write_text("def owner():\n    return True\n", encoding="utf-8")
            config = WorkspaceRetrievalConfig(
                workspace_root=str(root),
                index_dir=str(root / ".index"),
                run_dir=str(root / ".runs"),
                llm_config=RunLLMConfig(
                    api_style="openai_chat_completions",
                    model="test",
                    endpoint_url="http://example.test",
                    api_key="key",
                ),
                embedding_config=RetrievalEmbeddingConfig(
                    model="unused",
                    endpoint_url="http://unused.test",
                    api_key="unused",
                ),
                qdrant_config=RetrievalQdrantConfig(
                    url="http://unused.test",
                    collection_name="unused",
                ),
                retrieval_mode="codex",
                codex_command=("codex-test",),
                codex_model="gpt-test",
                codex_ignore_user_config=codex_ignore_user_config,
            )
            stage = CodexRetrievalStage(config)
            state = ConversationState(
                conversation_id="test",
                user_input="Explain owner.",
                assistance_request=AssistanceRequestType.UNDERSTAND_CODE,
            )
            policy = PolicyResult(
                allowed=True,
                assistance_request=AssistanceRequestType.UNDERSTAND_CODE,
                retrieval_required=True,
                allowed_sources=(SourceCategory.SOURCE_CODE,),
                turn_type=TurnType.GUIDED_EXPLANATION,
                reason="allowed",
                source_policy_name="test",
            )
            captured: dict[str, list[str]] = {}

            def fake_run(command: list[str], **kwargs: object) -> object:
                captured["command"] = list(command)
                output_path = Path(command[command.index("-o") + 1])
                output_path.write_text(
                    json.dumps(
                        {
                            "evidence": [
                                {
                                    "file": "src/owner.py",
                                    "line_start": 1,
                                    "line_end": 2,
                                    "claim_supported": "owner exists",
                                    "why_relevant": "selected evidence",
                                    "coverage_area": "implementation_owner",
                                }
                            ]
                        }
                    ),
                    encoding="utf-8",
                )
                return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()

            with patch("services.retrieval.codex.provider.subprocess.run", side_effect=fake_run):
                stage.retrieve(state, policy)

            return captured["command"]


if __name__ == "__main__":
    unittest.main()

