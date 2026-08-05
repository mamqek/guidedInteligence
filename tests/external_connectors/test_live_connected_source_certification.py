from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
import re
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from core.models import ConversationState, ResponsePlan, TurnType, UserIntent
from core.policy import PolicyStage
from core.response_builder import render_response
from core.source_policy import SourceCategory, SourcePolicy
from services.retrieval.config import (
    RetrievalEmbeddingConfig,
    RetrievalQdrantConfig,
    RunLLMConfig,
    WorkspaceRetrievalConfig,
    load_retrieval_embedding_config,
)
from services.retrieval.server import _configured_remote_mcp_sources
from services.retrieval.workspace import WorkspaceRetrievalStage
from services.retrieval.workspace.bm25 import build_index_from_repo, save_index
from tests.test_workspace_retrieval import WorkspaceRetrievalStageFixture, _fake_structural


def _enabled() -> bool:
    return os.environ.get("GI_LIVE_CONNECTED_SOURCE_CERT") == "1"


def _obsidian_enabled() -> bool:
    return os.environ.get("GI_LIVE_OBSIDIAN_CERT") == "1"


def _project_llm_config(root: Path) -> RunLLMConfig:
    config_path = root / ".guided-intelligence" / "config.json"
    secrets_path = root / ".guided-intelligence" / "secrets.json"
    if not config_path.exists():
        raise ValueError("LLM config is missing. Configure it in the Workspace tab first.")
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    secrets = json.loads(secrets_path.read_text(encoding="utf-8-sig")) if secrets_path.exists() else {}
    connections = config.get("connections") if isinstance(config.get("connections"), dict) else {}
    generation = config.get("generation") if isinstance(config.get("generation"), dict) else {}
    api_llm = connections.get("api_llm") if isinstance(connections.get("api_llm"), dict) else {}
    secret_api_llm = secrets.get("api_llm") if isinstance(secrets.get("api_llm"), dict) else {}
    model = str(generation.get("api_model") or api_llm.get("model") or "").strip()
    endpoint_url = str(api_llm.get("endpoint_url") or "").strip()
    api_key = str(secret_api_llm.get("api_key") or "").strip()
    if not model or not endpoint_url or not api_key:
        raise ValueError("OpenAI-compatible API connection requires endpoint URL, API key, and model. Configure it in the Workspace tab first.")
    return RunLLMConfig(
        api_style=str(api_llm.get("api_style") or "openai_chat_completions").strip() or "openai_chat_completions",
        endpoint_url=endpoint_url,
        model=model,
        api_key=api_key,
        temperature=float(api_llm.get("temperature") if api_llm.get("temperature") is not None else 0.0),
        max_tokens=int(generation.get("max_tokens") or api_llm.get("max_tokens") or 800),
        timeout_seconds=int(generation.get("timeout_seconds") or api_llm.get("timeout_seconds") or 30),
    )


def _notion_enabled() -> bool:
    return os.environ.get("GI_LIVE_NOTION_CERT") == "1"


def _github_enabled() -> bool:
    return os.environ.get("GI_LIVE_GITHUB_CERT") == "1"


def _load_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError(f"{path} must contain a JSON object.")
    return payload


def _source_text(candidate: dict[str, object]) -> str:
    fields = [
        str(candidate.get("source_id", "")),
        str(candidate.get("title", "")),
        str(candidate.get("content", "")),
        json.dumps(candidate.get("metadata", {}), sort_keys=True),
    ]
    return "\n".join(fields).casefold()


def _extract_note_owner_signal(candidate: dict[str, object]) -> tuple[str, str]:
    text = _source_text(candidate)
    file_match = re.search(r"(?:canonical_file|owner file)\s*:\s*`?([a-z0-9_./\\-]+\.[a-z0-9_]+)`?", text)
    symbol_match = re.search(r"(?:symbol|owner function)\s*:\s*`?([a-z0-9_./\\-]+)`?", text)
    return (
        file_match.group(1).replace("\\", "/") if file_match else "",
        symbol_match.group(1) if symbol_match else "",
    )


def _policy_result(state: ConversationState):
    policy = PolicyStage(
        SourcePolicy(
            allowed_categories=(
                SourceCategory.SOURCE_CODE,
                SourceCategory.ISSUE_TRACKER,
                SourceCategory.PULL_REQUEST,
                SourceCategory.DOCUMENTATION,
                SourceCategory.LOCAL_NOTES,
            ),
            policy_name="live-certification",
        )
    )
    return policy.decide(state)


def _response_request_payloads(events: list[tuple[str, dict[str, object]]]) -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []
    for event_type, payload in events:
        if event_type == "response_generation_request_payload":
            raw_payload = payload.get("payload")
            if isinstance(raw_payload, dict):
                payloads.append(raw_payload)
        if event_type != "prompt_payload":
            continue
        wrapped_event_type = payload.get("event_type")
        wrapped_payload = payload.get("payload")
        if wrapped_event_type in {"response_generation_request_payload", "comprehension_generation_request_payload"} and isinstance(wrapped_payload, dict):
            raw_payload = wrapped_payload.get("payload")
            if isinstance(raw_payload, dict):
                payloads.append(raw_payload)
    return payloads


def _payload_contains_evidence_ref(payloads: list[dict[str, object]], evidence_ref: str) -> bool:
    for payload in payloads:
        for item in payload.get("evidence", ()):
            if isinstance(item, dict) and item.get("ref") == evidence_ref:
                return True
        citation_rules = payload.get("citation_rules")
        if isinstance(citation_rules, dict) and evidence_ref in citation_rules.get("allowed_refs", ()):
            return True
    return False


def _write_certification_artifact(
    *,
    name: str,
    response_content: str,
    retrieval_summary: dict[str, object],
    response_metadata: object,
) -> Path | None:
    output_dir = os.environ.get("GI_CONNECTOR_CERT_OUTPUT_DIR", "").strip()
    if not output_dir:
        return None
    artifact_dir = Path(output_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    path = artifact_dir / f"{name}.md"
    path.write_text(
        "\n\n".join(
            [
                "# Connector Certification Response",
                "## Response",
                response_content,
                "## Response Metadata",
                "```json\n" + json.dumps(response_metadata, indent=2, sort_keys=True, default=str) + "\n```",
                "## Retrieval Summary",
                "```json\n" + json.dumps(retrieval_summary, indent=2, sort_keys=True, default=str) + "\n```",
            ]
        ),
        encoding="utf-8",
    )
    return path


class _DynamicLiveCertificationLLMHandler(BaseHTTPRequestHandler):
    query: str = ""
    expected_terms: tuple[str, ...] = ()
    source_key: str = ""
    file_hint: str = ""
    symbol_hint: str = ""
    accepted_ids: list[str] = []
    rejected_ids: list[str] = []

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        request_payload = json.loads(self.rfile.read(length).decode("utf-8"))
        schema_name = (
            request_payload.get("response_format", {})
            .get("json_schema", {})
            .get("name", "")
        )
        if schema_name == "connected_source_query_plan":
            content = {
                "queries": [
                    {
                        "source_key": self.source_key,
                        "query": self.query,
                        "reason": "Live certification query for the configured connected source.",
                        "should_query": True,
                    }
                ]
            }
        elif schema_name == "connected_source_context_analysis":
            content = self._connected_source_analysis(request_payload)
        elif schema_name == "workspace_retrieval_step2_plan":
            content = {
                "prompt_summary": "Live external-source certification prompt.",
                "retrieval_terms": [self.symbol_hint, Path(self.file_hint).stem],
                "llm_concept_terms": [self.symbol_hint],
                "llm_subqueries": [
                    {
                        "role": "behavior_output",
                        "query": f"where is {self.symbol_hint} implemented or declared",
                    }
                ],
                "speculative_entities": [],
                "source_priorities": ["source_code"],
                "negative_filters": [],
            }
        else:
            content = {
                "acceptance_satisfied": True,
                "stop_reason": "live_connected_source_certification",
                "missing_areas": [],
                "accepted_anchor_refs": [f"repo-pre:{self.file_hint}:L1-L8"],
                "rejected_anchor_refs": [],
                "snippet_assessment": [
                    {
                        "ref": f"repo-pre:{self.file_hint}:L1-L8",
                        "role": "core",
                        "reason": "Owner source selected from live external-source hint.",
                    }
                ],
                "follow_up_queries": [],
            }
        body = json.dumps({"choices": [{"message": {"content": json.dumps(content)}}]}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _connected_source_analysis(self, request_payload: dict[str, object]) -> dict[str, object]:
        messages = request_payload.get("messages", [])
        user_message = messages[-1] if isinstance(messages, list) and messages else {}
        payload = json.loads(str(user_message.get("content", "{}"))) if isinstance(user_message, dict) else {}
        candidates = payload.get("candidates", [])
        if not isinstance(candidates, list):
            candidates = []
        selected_id = ""
        selected_file_hint = self.file_hint
        selected_symbol_hint = self.symbol_hint
        decisions = []
        type(self).accepted_ids = []
        type(self).rejected_ids = []
        for index, candidate in enumerate(candidate for candidate in candidates if isinstance(candidate, dict)):
            source_id = str(candidate.get("source_id", "")).strip()
            text = _source_text(candidate)
            owner_file, owner_symbol = _extract_note_owner_signal(candidate)
            has_expected_terms = all(term.casefold() in text for term in self.expected_terms if term)
            has_owner_signal = bool(owner_file and owner_symbol)
            explicitly_disclaims_owner = "do not use this as source-owner guidance" in text
            matches = bool(source_id) and (
                (has_owner_signal and not explicitly_disclaims_owner)
                or has_expected_terms
            )
            if matches and not selected_id:
                selected_id = source_id
                selected_file_hint = owner_file or self.file_hint
                selected_symbol_hint = owner_symbol or self.symbol_hint
                type(self).accepted_ids.append(source_id)
                decisions.append(
                    {
                        "source_id": source_id,
                        "relevance_score": 1.0,
                        "decision": "accept",
                        "reason": "Live result contains the configured expected terms.",
                        "contribution_type": "file",
                        "adds_code_retrieval_signal": True,
                        "currentness": "current",
                        "confidence": "high",
                        "context_use": True,
                        "evidence_use": True,
                    }
                )
            else:
                if source_id:
                    type(self).rejected_ids.append(source_id)
                decisions.append(
                    {
                        "source_id": source_id or f"missing-source-id-{index}",
                        "relevance_score": 0.0,
                        "decision": "reject",
                        "reason": "Live result does not contain all configured expected terms.",
                        "contribution_type": "terminology_only",
                        "adds_code_retrieval_signal": False,
                        "currentness": "current",
                        "confidence": "low",
                        "context_use": False,
                        "evidence_use": False,
                    }
                )
        if not selected_id:
            raise AssertionError(
                "Live connected source returned no candidate with owner evidence or expected terms: "
                + ", ".join(self.expected_terms)
            )
        return {
            "ranked_documents": decisions,
            "signals": {
                "retrieval_terms": [
                    {"value": selected_symbol_hint, "source_ids": [selected_id]},
                ],
                "file_hints": [
                    {"value": selected_file_hint, "source_ids": [selected_id]},
                ],
                "symbol_hints": [
                    {"value": selected_symbol_hint, "source_ids": [selected_id]},
                ],
                "suggested_subqueries": [
                    {
                        "value": f"Where is {selected_symbol_hint} implemented or declared?",
                        "source_ids": [selected_id],
                    }
                ],
            },
            "facts": [
                {
                    "text": f"The live connected source points retrieval toward {selected_file_hint}.",
                    "source_ids": [selected_id],
                }
            ],
            "conflicts": [],
        }

    def log_message(self, format: str, *args) -> None:
        return


class _dynamic_llm_server:
    def __init__(self, *, query: str, expected_terms: tuple[str, ...], source_key: str, file_hint: str, symbol_hint: str) -> None:
        self.query = query
        self.expected_terms = expected_terms
        self.source_key = source_key
        self.file_hint = file_hint
        self.symbol_hint = symbol_hint
        self.server: HTTPServer | None = None
        self.thread: threading.Thread | None = None

    def __enter__(self) -> str:
        _DynamicLiveCertificationLLMHandler.query = self.query
        _DynamicLiveCertificationLLMHandler.expected_terms = self.expected_terms
        _DynamicLiveCertificationLLMHandler.source_key = self.source_key
        _DynamicLiveCertificationLLMHandler.file_hint = self.file_hint
        _DynamicLiveCertificationLLMHandler.symbol_hint = self.symbol_hint
        _DynamicLiveCertificationLLMHandler.accepted_ids = []
        _DynamicLiveCertificationLLMHandler.rejected_ids = []
        self.server = HTTPServer(("127.0.0.1", 0), _DynamicLiveCertificationLLMHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        return f"http://{host}:{port}/v1/chat/completions"

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        if self.thread is not None:
            self.thread.join(timeout=2)


class LiveConnectedSourceCertificationTests(WorkspaceRetrievalStageFixture):
    def test_live_github_source_is_used_as_context_evidence_and_guides_owner_resolution(self) -> None:
        if not _github_enabled():
            self.skipTest("Set GI_LIVE_GITHUB_CERT=1 to run live GitHub connected-source certification.")

        root = Path(__file__).resolve().parents[2]
        app_config = _load_json(root / ".guided-intelligence" / "config.json")
        provider_auth = _load_json(root / ".guided-intelligence" / "provider-auth.json")
        sources = _configured_remote_mcp_sources(app_config, provider_auth)
        issue_source = next(
            (
                item
                for item in sources
                if item.provider == "github"
                and (item.name == "github-issues" or item.source_key == "github_issues")
            ),
            None,
        )
        pr_source = next(
            (
                item
                for item in sources
                if item.provider == "github"
                and (item.name == "github-prs" or item.source_key == "github_pull_requests")
            ),
            None,
        )
        if issue_source is None:
            self.fail("No enabled live hosted GitHub MCP issue source found in .guided-intelligence/config.json.")
        if pr_source is None:
            self.fail("No enabled live hosted GitHub MCP PR source found in .guided-intelligence/config.json.")
        self.assertEqual("https://api.githubcopilot.com/mcp/", issue_source.endpoint_url)
        self.assertEqual("https://api.githubcopilot.com/mcp/", pr_source.endpoint_url)
        self.assertEqual("oauth", issue_source.auth_type)
        self.assertEqual("oauth", pr_source.auth_type)
        self.assertEqual("search_issues", issue_source.query_tool_name)
        self.assertEqual("search_pull_requests", pr_source.query_tool_name)
        if not issue_source.oauth_access_token or not pr_source.oauth_access_token:
            self.fail("Live GitHub source requires an OAuth access token in .guided-intelligence/provider-auth.json.")

        marker = "GI-GITHUB-CERT-CODEX-WRITE-PROBE"
        fixture_repo = "mamqek/guided-intelligence-retrieval-fixtures"
        good_issue_title = "GI-GITHUB-CERT Good Owner Probe 2026-07-23"
        bad_issue_title = "GI-GITHUB-CERT Stale Wrong Owner Probe 2026-07-23"
        good_pr_title = "GI-GITHUB-PR-CERT Good Owner Probe 2026-07-23"
        bad_pr_title = "GI-GITHUB-PR-CERT Stale Wrong Owner Behavior Probe 2026-07-23"
        file_hint = "src/runtime/githubCert.ts"
        symbol_hint = "resolveGitHubCertification"
        bad_file_hint = "src/runtime/githubLegacyCert.ts"
        bad_symbol_hint = "resolveLegacyGitHubCertification"
        noise_file = "src/runtime/githubNoise.ts"
        noise_symbol = "resolveUnrelatedGitHubBehavior"
        self.assertEqual(fixture_repo, issue_source.scope)
        self.assertEqual(fixture_repo, pr_source.scope)
        cert_issue_source = replace(
            issue_source,
            result_limit=max(issue_source.result_limit, 10),
            static_tool_arguments={
                **dict(issue_source.static_tool_arguments),
                "mode": "hybrid",
            },
        )
        cert_pr_source = replace(
            pr_source,
            result_limit=max(pr_source.result_limit, 10),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            repo = temp_root / "repo"
            source_file = repo / file_hint
            source_file.parent.mkdir(parents=True)
            source_file.write_text(
                "\n".join(
                    [
                        "export function resolveGitHubCertification(state) {",
                        "  if (state.hostedMcpRetrievedProbe && state.ownerHintResolved) {",
                        "    return 'certified';",
                        "  }",
                        "  return 'pending';",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            (repo / noise_file).write_text(
                f"export function {noise_symbol}() {{ return 'ignore'; }}\n",
                encoding="utf-8",
            )
            index_dir = temp_root / "index"
            index = build_index_from_repo(repo_path=repo, commit="github-cert", chunk_line_count=40, chunk_line_overlap=10)
            save_index(index, index_dir)
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(repo),
                    index_dir=str(index_dir),
                    run_dir=str(temp_root / "run"),
                    llm_config=_project_llm_config(root),
                    embedding_config=load_retrieval_embedding_config(root / ".env"),
                    qdrant_config=RetrievalQdrantConfig(
                        url="http://example.test:6333",
                        collection_name="github-connected-source-cert",
                    ),
                    enable_indexing=False,
                    enabled_sources=("source_code", cert_issue_source.source_key, cert_pr_source.source_key),
                    remote_mcp_connected_sources=(cert_issue_source, cert_pr_source),
                    connected_context_timeout_seconds=max(60, issue_source.timeout_seconds + 30, pr_source.timeout_seconds + 30),
                    obsidian_vault_path=None,
                )
            )
            (index_dir / "qdrant-sync-manifest.json").write_text(
                json.dumps(
                    {
                        "collection_name": stage.config.qdrant_config.collection_name,
                        "document_count": len(index.documents),
                        "index_signature": f"sig:{len(index.documents)}",
                    }
                ),
                encoding="utf-8",
            )
            state = ConversationState(
                conversation_id="live-github-source-cert",
                user_input=f"Explain {marker} owner behavior.",
                intent=UserIntent.UNDERSTAND_CODE,
            )

            result = stage.retrieve(state, _policy_result(state))

            self.assertIn(
                "connected_source_context",
                result.retrieval_summary,
                msg=json.dumps(result.retrieval_summary, indent=2, sort_keys=True),
            )
            connected = result.retrieval_summary["connected_source_context"]
            github_documents = [
                document
                for document in connected["documents"]
                if document.get("provider") == "github" or document.get("source_id", "").startswith("remote-mcp:github:")
            ]
            self.assertTrue(
                all(document.get("metadata", {}).get("mcp_tool") in {"search_issues", "search_pull_requests"} for document in github_documents),
                msg=json.dumps(github_documents, indent=2, sort_keys=True),
            )
            issue_documents = [
                document
                for document in github_documents
                if document.get("metadata", {}).get("mcp_tool") == "search_issues"
            ]
            pr_documents = [
                document
                for document in github_documents
                if document.get("metadata", {}).get("mcp_tool") == "search_pull_requests"
            ]
            self.assertTrue(issue_documents, msg=json.dumps(github_documents, indent=2, sort_keys=True))
            self.assertTrue(pr_documents, msg=json.dumps(github_documents, indent=2, sort_keys=True))
            good_documents = [
                document
                for document in github_documents
                if good_issue_title.casefold() in _source_text(document)
                or good_pr_title.casefold() in _source_text(document)
                or file_hint.casefold() in _source_text(document)
                or symbol_hint.casefold() in _source_text(document)
            ]
            bad_documents = [
                document
                for document in github_documents
                if bad_issue_title.casefold() in _source_text(document)
                or bad_pr_title.casefold() in _source_text(document)
                or bad_file_hint.casefold() in _source_text(document)
                or bad_symbol_hint.casefold() in _source_text(document)
            ]
            self.assertTrue(good_documents, msg=json.dumps(connected, indent=2, sort_keys=True))
            self.assertTrue(bad_documents, msg=json.dumps(connected, indent=2, sort_keys=True))
            self.assertTrue(
                any(good_issue_title.casefold() in _source_text(document) for document in good_documents),
                msg=json.dumps(good_documents, indent=2, sort_keys=True),
            )
            self.assertTrue(
                any(good_pr_title.casefold() in _source_text(document) for document in good_documents),
                msg=json.dumps(good_documents, indent=2, sort_keys=True),
            )
            self.assertTrue(
                any(bad_issue_title.casefold() in _source_text(document) for document in bad_documents),
                msg=json.dumps(bad_documents, indent=2, sort_keys=True),
            )
            self.assertTrue(
                any(bad_pr_title.casefold() in _source_text(document) for document in bad_documents),
                msg=json.dumps(bad_documents, indent=2, sort_keys=True),
            )
            good_ids = {str(document["source_id"]) for document in good_documents}
            bad_ids = {str(document["source_id"]) for document in bad_documents}
            selected_context_ids = set(connected["selected_context_ids"])
            selected_evidence_ids = set(connected["selected_evidence_ids"])
            self.assertTrue(good_ids & selected_context_ids, msg=json.dumps(connected, indent=2, sort_keys=True))
            self.assertTrue(good_ids & selected_evidence_ids, msg=json.dumps(connected, indent=2, sort_keys=True))
            self.assertFalse(bad_ids & selected_context_ids, msg=json.dumps(connected, indent=2, sort_keys=True))
            self.assertFalse(bad_ids & selected_evidence_ids, msg=json.dumps(connected, indent=2, sort_keys=True))
            self.assertIn(file_hint, connected.get("file_hints", ()), msg=json.dumps(connected, indent=2, sort_keys=True))
            self.assertIn(symbol_hint, connected.get("symbol_hints", ()), msg=json.dumps(connected, indent=2, sort_keys=True))
            self.assertNotIn(bad_file_hint, connected.get("file_hints", ()), msg=json.dumps(connected, indent=2, sort_keys=True))
            self.assertNotIn(bad_symbol_hint, connected.get("symbol_hints", ()), msg=json.dumps(connected, indent=2, sort_keys=True))

            evidence_ids = {item.source_id for item in result.evidence}
            evidence_paths = {item.metadata.get("path") for item in result.evidence}
            selected_github_ref = next(iter(good_ids & evidence_ids), "")
            self.assertTrue(selected_github_ref, msg=json.dumps([item.to_dict() for item in result.evidence], indent=2, sort_keys=True))
            self.assertFalse(bad_ids & evidence_ids, msg=json.dumps([item.to_dict() for item in result.evidence], indent=2, sort_keys=True))
            self.assertNotIn(noise_file, evidence_paths, msg=json.dumps([item.to_dict() for item in result.evidence], indent=2, sort_keys=True))

            response_events: list[tuple[str, dict[str, object]]] = []

            def record_response_event(event_type, payload) -> None:
                response_events.append((str(getattr(event_type, "value", event_type)), dict(payload)))

            policy_result = _policy_result(state)
            response = render_response(
                policy_result,
                result,
                ResponsePlan(
                    turn_type=policy_result.turn_type,
                    required_sections=("generated_explanation", "understanding_checks"),
                    must_include_evidence=True,
                    notes={
                        "coverage_status": result.coverage_status,
                        "retrieval_sufficient": result.sufficient,
                    },
                ),
                state=state,
                llm_config=_project_llm_config(root),
                log_event=record_response_event,
            )

            self.assertNotIn("Explanation generation failed", response.content, msg=response.content)
            used_evidence_refs = tuple(response.metadata.get("used_evidence_refs", ()))
            self.assertIn(selected_github_ref, used_evidence_refs, msg=response.content)
            self.assertFalse(bad_ids.intersection(used_evidence_refs), msg=response.content)
            self.assertFalse(any(noise_file in ref for ref in used_evidence_refs), msg=response.content)
            self.assertIn(file_hint, response.content, msg=response.content)
            self.assertIn(symbol_hint, response.content, msg=response.content)
            self.assertNotIn(noise_file, response.content, msg=response.content)
            self.assertNotIn(noise_symbol, response.content, msg=response.content)
            self.assertNotIn(bad_file_hint, response.content, msg=response.content)
            self.assertNotIn(bad_symbol_hint, response.content, msg=response.content)
            response_request_payloads = _response_request_payloads(response_events)
            self.assertTrue(response_request_payloads, msg=json.dumps(response_events, indent=2, default=str))
            self.assertTrue(
                _payload_contains_evidence_ref(response_request_payloads, selected_github_ref),
                msg=json.dumps(response_request_payloads, indent=2, sort_keys=True),
            )
            _write_certification_artifact(
                name="github_latest_response",
                response_content=response.content,
                retrieval_summary=dict(result.retrieval_summary),
                response_metadata=response.metadata,
            )

    def test_live_notion_source_is_used_as_context_evidence_and_guides_owner_resolution(self) -> None:
        if not _notion_enabled():
            self.skipTest("Set GI_LIVE_NOTION_CERT=1 to run live Notion connected-source certification.")

        root = Path(__file__).resolve().parents[2]
        app_config = _load_json(root / ".guided-intelligence" / "config.json")
        provider_auth = _load_json(root / ".guided-intelligence" / "provider-auth.json")
        sources = _configured_remote_mcp_sources(app_config, provider_auth)
        source = next(
            (
                item
                for item in sources
                if item.provider == "notion"
                and (item.name == "notion-pages" or item.source_key == "notion")
            ),
            None,
        )
        if source is None:
            self.fail("No enabled live hosted Notion MCP source found in .guided-intelligence/config.json.")
        self.assertEqual("https://mcp.notion.com/mcp", source.endpoint_url)
        self.assertEqual("oauth", source.auth_type)
        if not source.oauth_access_token:
            self.fail("Live Notion source requires an OAuth access token in .guided-intelligence/provider-auth.json.")

        marker = "GI-NOTION-CERT-CODEX-WRITE-PROBE"
        title = "GI-NOTION-CERT Codex Write Probe 2026-07-22"
        page_url = "https://app.notion.com/p/3a566dec1cfa81c6a25ed89c37fb7a1c"
        page_id = "3a566dec-1cfa-81c6-a25e-d89c37fb7a1c"
        file_hint = "src/runtime/notionCert.ts"
        symbol_hint = "resolveNotionCertification"
        bad_title = "GI-NOTION-CERT Stale Wrong Owner Probe 2026-07-22"
        bad_page_id = "3a666dec-1cfa-8120-8695-ce95def934bd"
        bad_file_hint = "src/runtime/notionLegacyCert.ts"
        bad_symbol_hint = "resolveLegacyNotionCertification"
        noise_file = "src/runtime/notionNoise.ts"
        noise_symbol = "resolveUnrelatedNotionBehavior"
        cert_source = replace(
            source,
            result_limit=max(source.result_limit, 10),
            enrich_limit=max(source.enrich_limit, 10),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            repo = temp_root / "repo"
            source_file = repo / file_hint
            source_file.parent.mkdir(parents=True)
            source_file.write_text(
                "\n".join(
                    [
                        "export function resolveNotionCertification(state) {",
                        "  if (state.hostedMcpRetrievedProbe && state.ownerHintResolved) {",
                        "    return 'certified';",
                        "  }",
                        "  return 'pending';",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            (repo / noise_file).write_text(
                f"export function {noise_symbol}() {{ return 'ignore'; }}\n",
                encoding="utf-8",
            )
            index_dir = temp_root / "index"
            index = build_index_from_repo(repo_path=repo, commit="notion-cert", chunk_line_count=40, chunk_line_overlap=10)
            save_index(index, index_dir)
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(repo),
                    index_dir=str(index_dir),
                    run_dir=str(temp_root / "run"),
                    llm_config=_project_llm_config(root),
                    embedding_config=load_retrieval_embedding_config(root / ".env"),
                    qdrant_config=RetrievalQdrantConfig(
                        url="http://example.test:6333",
                        collection_name="notion-connected-source-cert",
                    ),
                    enable_indexing=False,
                    enabled_sources=("source_code", cert_source.source_key),
                    remote_mcp_connected_sources=(cert_source,),
                    connected_context_timeout_seconds=max(60, source.timeout_seconds + 30),
                    obsidian_vault_path=None,
                )
            )
            (index_dir / "qdrant-sync-manifest.json").write_text(
                json.dumps(
                    {
                        "collection_name": stage.config.qdrant_config.collection_name,
                        "document_count": len(index.documents),
                        "index_signature": f"sig:{len(index.documents)}",
                    }
                ),
                encoding="utf-8",
            )
            state = ConversationState(
                conversation_id="live-notion-source-cert",
                user_input=f"Explain {marker} owner behavior.",
                intent=UserIntent.UNDERSTAND_CODE,
            )

            result = stage.retrieve(state, _policy_result(state))

            self.assertIn(
                "connected_source_context",
                result.retrieval_summary,
                msg=json.dumps(result.retrieval_summary, indent=2, sort_keys=True),
            )
            connected = result.retrieval_summary["connected_source_context"]
            self.assertGreaterEqual(
                len(connected["documents"]),
                1,
                msg=json.dumps(connected, indent=2, sort_keys=True),
            )
            notion_documents = [
                document
                for document in connected["documents"]
                if document.get("provider") == "notion" or document.get("source_id", "").startswith("remote-mcp:notion:")
            ]
            good_documents = [
                document
                for document in notion_documents
                if title.casefold() in _source_text(document)
                or page_id.casefold() in _source_text(document)
                or page_id.replace("-", "").casefold() in _source_text(document)
                or file_hint.casefold() in _source_text(document)
                or symbol_hint.casefold() in _source_text(document)
            ]
            self.assertTrue(good_documents, msg=json.dumps(connected, indent=2, sort_keys=True))
            bad_documents = [
                document
                for document in notion_documents
                if bad_title.casefold() in _source_text(document)
                or bad_page_id.casefold() in _source_text(document)
                or bad_page_id.replace("-", "").casefold() in _source_text(document)
                or bad_file_hint.casefold() in _source_text(document)
                or bad_symbol_hint.casefold() in _source_text(document)
            ]
            self.assertTrue(bad_documents, msg=json.dumps(connected, indent=2, sort_keys=True))
            good_ids = {str(document["source_id"]) for document in good_documents}
            bad_ids = {str(document["source_id"]) for document in bad_documents}
            selected_context_ids = set(connected["selected_context_ids"])
            selected_evidence_ids = set(connected["selected_evidence_ids"])
            self.assertTrue(good_ids & selected_context_ids, msg=json.dumps(connected, indent=2, sort_keys=True))
            self.assertTrue(good_ids & selected_evidence_ids, msg=json.dumps(connected, indent=2, sort_keys=True))
            self.assertFalse(bad_ids & selected_context_ids, msg=json.dumps(connected, indent=2, sort_keys=True))
            self.assertFalse(bad_ids & selected_evidence_ids, msg=json.dumps(connected, indent=2, sort_keys=True))
            self.assertIn(file_hint, connected.get("file_hints", ()), msg=json.dumps(connected, indent=2, sort_keys=True))
            self.assertIn(symbol_hint, connected.get("symbol_hints", ()), msg=json.dumps(connected, indent=2, sort_keys=True))
            self.assertNotIn(bad_file_hint, connected.get("file_hints", ()), msg=json.dumps(connected, indent=2, sort_keys=True))
            self.assertNotIn(bad_symbol_hint, connected.get("symbol_hints", ()), msg=json.dumps(connected, indent=2, sort_keys=True))

            evidence_ids = {item.source_id for item in result.evidence}
            evidence_paths = {item.metadata.get("path") for item in result.evidence}
            selected_notion_ref = next(iter(good_ids & evidence_ids), "")
            self.assertTrue(selected_notion_ref, msg=json.dumps([item.to_dict() for item in result.evidence], indent=2, sort_keys=True))
            self.assertFalse(bad_ids & evidence_ids, msg=json.dumps([item.to_dict() for item in result.evidence], indent=2, sort_keys=True))
            self.assertNotIn(noise_file, evidence_paths, msg=json.dumps([item.to_dict() for item in result.evidence], indent=2, sort_keys=True))
            plan_file_hints = result.retrieval_summary.get("retrieval_plan", {}).get("confirmed_file_hints", ())
            self.assertTrue(
                file_hint in plan_file_hints or file_hint in evidence_paths,
                msg=json.dumps(
                    {
                        "evidence": [item.to_dict() for item in result.evidence],
                        "retrieval_summary": result.retrieval_summary,
                    },
                    indent=2,
                    sort_keys=True,
                ),
            )

            response_events: list[tuple[str, dict[str, object]]] = []

            def record_response_event(event_type, payload) -> None:
                response_events.append((str(getattr(event_type, "value", event_type)), dict(payload)))

            policy_result = _policy_result(state)
            response = render_response(
                policy_result,
                result,
                ResponsePlan(
                    turn_type=policy_result.turn_type,
                    required_sections=("generated_explanation", "understanding_checks"),
                    must_include_evidence=True,
                    notes={
                        "coverage_status": result.coverage_status,
                        "retrieval_sufficient": result.sufficient,
                    },
                ),
                state=state,
                llm_config=_project_llm_config(root),
                log_event=record_response_event,
            )

            self.assertNotIn("Explanation generation failed", response.content, msg=response.content)
            used_evidence_refs = tuple(response.metadata.get("used_evidence_refs", ()))
            self.assertIn(selected_notion_ref, used_evidence_refs, msg=response.content)
            self.assertFalse(bad_ids.intersection(used_evidence_refs), msg=response.content)
            self.assertFalse(any(noise_file in ref for ref in used_evidence_refs), msg=response.content)
            self.assertIn(file_hint, response.content, msg=response.content)
            self.assertIn(symbol_hint, response.content, msg=response.content)
            self.assertNotIn(noise_file, response.content, msg=response.content)
            self.assertNotIn(noise_symbol, response.content, msg=response.content)
            self.assertNotIn(bad_file_hint, response.content, msg=response.content)
            self.assertNotIn(bad_symbol_hint, response.content, msg=response.content)
            response_request_payloads = _response_request_payloads(response_events)
            self.assertTrue(response_request_payloads, msg=json.dumps(response_events, indent=2, default=str))
            self.assertTrue(
                _payload_contains_evidence_ref(response_request_payloads, selected_notion_ref),
                msg=json.dumps(response_request_payloads, indent=2, sort_keys=True),
            )
            _write_certification_artifact(
                name="notion_latest_response",
                response_content=response.content,
                retrieval_summary=dict(result.retrieval_summary),
                response_metadata=response.metadata,
            )

    def test_live_obsidian_source_is_used_as_context_evidence_and_filters_noise(self) -> None:
        if not _obsidian_enabled():
            self.skipTest("Set GI_LIVE_OBSIDIAN_CERT=1 to run live Obsidian connected-source certification.")

        root = Path(__file__).resolve().parents[2]
        vault = root / "docs" / "obsidian"
        db_path = vault / ".obsidian-hybrid-search.db"
        if not vault.exists():
            self.fail(f"Obsidian vault is missing: {vault}")
        if not db_path.exists():
            self.fail(f"Obsidian search DB is missing: {db_path}. Run `npm run obsidian:index` first.")

        file_hint = "src/runtime/checkout.ts"
        symbol_hint = "resolveCheckoutConfirmation"

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            repo = temp_root / "repo"
            source_file = repo / file_hint
            source_file.parent.mkdir(parents=True)
            source_file.write_text(
                "\n".join(
                    [
                        "export function resolveCheckoutConfirmation(state) {",
                        "  if (state.paymentAuthorized && state.inventoryReserved) {",
                        "    return 'confirmed';",
                        "  }",
                        "  return 'pending';",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            index_dir = temp_root / "index"
            index = build_index_from_repo(repo_path=repo, commit="obsidian-cert", chunk_line_count=40, chunk_line_overlap=10)
            save_index(index, index_dir)
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(repo),
                    index_dir=str(index_dir),
                    run_dir=str(temp_root / "run"),
                    llm_config=_project_llm_config(root),
                    embedding_config=load_retrieval_embedding_config(root / ".env"),
                    qdrant_config=RetrievalQdrantConfig(
                        url="http://example.test:6333",
                        collection_name="obsidian-connected-source-cert",
                    ),
                    enable_indexing=False,
                    enabled_sources=("source_code", "local_notes"),
                    obsidian_vault_path=str(vault),
                    obsidian_db_path=str(db_path),
                    obsidian_command=("npx.cmd" if os.name == "nt" else "npx", "obsidian-hybrid-search"),
                    obsidian_search_mode="fulltext",
                    obsidian_search_limit=5,
                )
            )
            (index_dir / "qdrant-sync-manifest.json").write_text(
                json.dumps(
                    {
                        "collection_name": stage.config.qdrant_config.collection_name,
                        "document_count": len(index.documents),
                        "index_signature": f"sig:{len(index.documents)}",
                    }
                ),
                encoding="utf-8",
            )
            state = ConversationState(
                conversation_id="live-obsidian-source-cert",
                user_input="Explain GI-OBSIDIAN-CERT checkout confirmation owner behavior.",
                intent=UserIntent.UNDERSTAND_CODE,
            )

            result = stage.retrieve(state, _policy_result(state))

            self.assertIn(
                "connected_source_context",
                result.retrieval_summary,
                msg=json.dumps(result.retrieval_summary, indent=2, sort_keys=True),
            )
            connected = result.retrieval_summary["connected_source_context"]
            document_ids = {document["source_id"] for document in connected["documents"]}
            good_id = "obsidian:Connection certification good.md"
            noise_id = "obsidian:Connection certification noise.md"
            self.assertIn(good_id, document_ids, msg=json.dumps(connected, indent=2, sort_keys=True))
            self.assertIn(noise_id, document_ids)
            self.assertEqual([good_id], connected["selected_context_ids"])
            self.assertEqual([good_id], connected["selected_evidence_ids"])
            self.assertNotIn(noise_id, connected["selected_context_ids"])
            self.assertNotIn(noise_id, connected["selected_evidence_ids"])
            self.assertIn(file_hint, connected["file_hints"])
            self.assertIn(symbol_hint, connected["symbol_hints"])

            evidence_ids = {item.source_id for item in result.evidence}
            evidence_paths = {item.metadata.get("path") for item in result.evidence}
            self.assertIn(good_id, evidence_ids)
            self.assertNotIn(noise_id, evidence_ids)
            self.assertIn(file_hint, result.retrieval_summary["retrieval_plan"]["confirmed_file_hints"])
            self.assertIn(file_hint, evidence_paths)

            response_events: list[tuple[str, dict[str, object]]] = []

            def record_response_event(event_type, payload) -> None:
                response_events.append((str(getattr(event_type, "value", event_type)), dict(payload)))

            policy_result = _policy_result(state)
            response = render_response(
                policy_result,
                result,
                ResponsePlan(
                    turn_type=policy_result.turn_type,
                    required_sections=("generated_explanation", "understanding_checks"),
                    must_include_evidence=True,
                    notes={
                        "coverage_status": result.coverage_status,
                        "retrieval_sufficient": result.sufficient,
                    },
                ),
                state=state,
                llm_config=_project_llm_config(root),
                log_event=record_response_event,
            )

            self.assertNotIn("Explanation generation failed", response.content, msg=response.content)
            self.assertIn(good_id, response.metadata.get("used_evidence_refs", ()), msg=response.content)
            self.assertIn(file_hint, response.content, msg=response.content)
            self.assertIn(symbol_hint, response.content, msg=response.content)
            response_request_payloads = _response_request_payloads(response_events)
            self.assertTrue(response_request_payloads, msg=json.dumps(response_events, indent=2, default=str))
            self.assertTrue(
                _payload_contains_evidence_ref(response_request_payloads, good_id),
                msg=json.dumps(response_request_payloads, indent=2, sort_keys=True),
            )
            _write_certification_artifact(
                name="obsidian_latest_response",
                response_content=response.content,
                retrieval_summary=dict(result.retrieval_summary),
                response_metadata=response.metadata,
            )

    def test_live_obsidian_conflicting_owner_notes_surface_conflict(self) -> None:
        if not _obsidian_enabled():
            self.skipTest("Set GI_LIVE_OBSIDIAN_CERT=1 to run live Obsidian connected-source certification.")

        root = Path(__file__).resolve().parents[2]
        vault = root / "docs" / "obsidian"
        db_path = vault / ".obsidian-hybrid-search.db"
        if not vault.exists():
            self.fail(f"Obsidian vault is missing: {vault}")
        if not db_path.exists():
            self.fail(f"Obsidian search DB is missing: {db_path}. Run `npm run obsidian:index` first.")

        current_file = "src/runtime/shipping.ts"
        current_symbol = "resolveShipmentConfirmation"
        stale_file = "src/runtime/legacyShipping.ts"
        stale_symbol = "resolveLegacyShipmentConfirmation"
        current_id = "obsidian:Connection certification conflict current.md"
        stale_id = "obsidian:Connection certification conflict stale.md"

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            repo = temp_root / "repo"
            current_source = repo / current_file
            current_source.parent.mkdir(parents=True)
            current_source.write_text(
                "\n".join(
                    [
                        "export function resolveShipmentConfirmation(state) {",
                        "  if (state.labelPurchased && state.carrierAccepted) {",
                        "    return 'ready_to_ship';",
                        "  }",
                        "  return 'waiting';",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            stale_source = repo / stale_file
            stale_source.parent.mkdir(parents=True, exist_ok=True)
            stale_source.write_text(
                "\n".join(
                    [
                        "export function resolveLegacyShipmentConfirmation(state) {",
                        "  return state.ready ? 'ready_to_ship' : 'waiting';",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            index_dir = temp_root / "index"
            index = build_index_from_repo(repo_path=repo, commit="obsidian-conflict-cert", chunk_line_count=40, chunk_line_overlap=10)
            save_index(index, index_dir)
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(repo),
                    index_dir=str(index_dir),
                    run_dir=str(temp_root / "run"),
                    llm_config=_project_llm_config(root),
                    embedding_config=load_retrieval_embedding_config(root / ".env"),
                    qdrant_config=RetrievalQdrantConfig(
                        url="http://example.test:6333",
                        collection_name="obsidian-connected-source-conflict-cert",
                    ),
                    enable_indexing=False,
                    enabled_sources=("source_code", "local_notes"),
                    obsidian_vault_path=str(vault),
                    obsidian_db_path=str(db_path),
                    obsidian_command=("npx.cmd" if os.name == "nt" else "npx", "obsidian-hybrid-search"),
                    obsidian_search_mode="fulltext",
                    obsidian_search_limit=5,
                )
            )
            (index_dir / "qdrant-sync-manifest.json").write_text(
                json.dumps(
                    {
                        "collection_name": stage.config.qdrant_config.collection_name,
                        "document_count": len(index.documents),
                        "index_signature": f"sig:{len(index.documents)}",
                    }
                ),
                encoding="utf-8",
            )
            state = ConversationState(
                conversation_id="live-obsidian-source-conflict-cert",
                user_input="Explain GI-OBSIDIAN-CONFLICT shipment confirmation owner behavior.",
                intent=UserIntent.UNDERSTAND_CODE,
            )

            result = stage.retrieve(state, _policy_result(state))

            self.assertIn(
                "connected_source_context",
                result.retrieval_summary,
                msg=json.dumps(result.retrieval_summary, indent=2, sort_keys=True),
            )
            connected = result.retrieval_summary["connected_source_context"]
            document_ids = {document["source_id"] for document in connected["documents"]}
            self.assertIn(current_id, document_ids, msg=json.dumps(connected, indent=2, sort_keys=True))
            self.assertIn(stale_id, document_ids, msg=json.dumps(connected, indent=2, sort_keys=True))
            conflict_source_sets = [
                set(conflict.get("source_ids", ()))
                for conflict in connected.get("conflicts", ())
                if isinstance(conflict, dict)
            ]
            self.assertTrue(
                any({current_id, stale_id}.issubset(source_ids) for source_ids in conflict_source_sets),
                msg=json.dumps(connected, indent=2, sort_keys=True),
            )
            self.assertFalse(
                current_file in connected.get("file_hints", ()) and stale_file in connected.get("file_hints", ()),
                msg="Conflicting owner files should not both be promoted as clean file hints: "
                + json.dumps(connected, indent=2, sort_keys=True),
            )

            policy_result = _policy_result(state)
            response = render_response(
                policy_result,
                result,
                ResponsePlan(
                    turn_type=policy_result.turn_type,
                    required_sections=("generated_explanation", "understanding_checks"),
                    must_include_evidence=True,
                    notes={
                        "coverage_status": result.coverage_status,
                        "retrieval_sufficient": result.sufficient,
                    },
                ),
                state=state,
                llm_config=_project_llm_config(root),
            )
            self.assertNotIn("Explanation generation failed", response.content, msg=response.content)
            self.assertTrue(
                any(term in response.content for term in ("conflict", "contradict", "different owner", "not shown", "needs verification")),
                msg=response.content,
            )
            _write_certification_artifact(
                name="obsidian_conflict_response",
                response_content=response.content,
                retrieval_summary=dict(result.retrieval_summary),
                response_metadata=response.metadata,
            )

    def test_live_remote_source_is_used_as_context_evidence_and_filters_noise(self) -> None:
        if not _enabled():
            self.skipTest("Set GI_LIVE_CONNECTED_SOURCE_CERT=1 to run live connected-source certification.")

        root = Path(__file__).resolve().parents[2]
        app_config = _load_json(root / ".guided-intelligence" / "config.json")
        provider_auth = _load_json(root / ".guided-intelligence" / "provider-auth.json")
        sources = _configured_remote_mcp_sources(app_config, provider_auth)
        provider = os.environ.get("GI_LIVE_CONNECTED_SOURCE_PROVIDER", "github")
        source_name = os.environ.get("GI_LIVE_CONNECTED_SOURCE_NAME", "github-issues")
        source = next(
            (
                item
                for item in sources
                if item.provider == provider
                and (item.name == source_name or item.source_key == source_name or item.source_key == source_name.replace("-", "_"))
            ),
            None,
        )
        if source is None:
            self.fail(f"No enabled live remote MCP source found for provider={provider!r}, name={source_name!r}.")
        if source.auth_type == "oauth" and not source.oauth_access_token:
            self.fail(f"Live source {source.name!r} requires an OAuth access token.")
        if source.auth_type == "bearer" and not source.bearer_token:
            self.fail(f"Live source {source.name!r} requires a bearer token.")
        if source.auth_type == "api_key" and not source.api_key:
            self.fail(f"Live source {source.name!r} requires an API key.")

        owner = os.environ.get("GI_LIVE_CONNECTED_SOURCE_OWNER", "microsoft")
        repo_name = os.environ.get("GI_LIVE_CONNECTED_SOURCE_REPO", "TypeScript")
        issue_number = os.environ.get("GI_LIVE_CONNECTED_SOURCE_ISSUE_NUMBER", "2953")
        noise_issue_number = os.environ.get("GI_LIVE_CONNECTED_SOURCE_NOISE_ISSUE_NUMBER", "1")
        query = os.environ.get("GI_LIVE_CONNECTED_SOURCE_QUERY", f"{owner}/{repo_name} issue {issue_number}")
        expected_terms = tuple(
            term.strip()
            for term in os.environ.get("GI_LIVE_CONNECTED_SOURCE_EXPECT", "DataView,ArrayBuffer").split(",")
            if term.strip()
        )
        file_hint = os.environ.get("GI_LIVE_CONNECTED_SOURCE_FILE_HINT", "src/lib/extensions.d.ts")
        symbol_hint = os.environ.get("GI_LIVE_CONNECTED_SOURCE_SYMBOL_HINT", "DataView")
        relevant_live_source = replace(
            source,
            query_tool_name=os.environ.get("GI_LIVE_CONNECTED_SOURCE_TOOL", "issue_read"),
            limit_argument_name="",
            result_limit=1,
            static_tool_arguments={
                "method": "get",
                "owner": owner,
                "repo": repo_name,
                "issue_number": issue_number,
            },
        )
        wrong_live_source = replace(
            source,
            query_tool_name=os.environ.get("GI_LIVE_CONNECTED_SOURCE_TOOL", "issue_read"),
            limit_argument_name="",
            result_limit=1,
            static_tool_arguments={
                "method": "get",
                "owner": owner,
                "repo": repo_name,
                "issue_number": noise_issue_number,
            },
        )

        with tempfile.TemporaryDirectory() as temp_dir, _dynamic_llm_server(
            query=query,
            expected_terms=expected_terms,
            source_key=source.source_key,
            file_hint=file_hint,
            symbol_hint=symbol_hint,
        ) as server_url:
            temp_root = Path(temp_dir)
            repo = temp_root / "repo"
            source_file = repo / file_hint
            source_file.parent.mkdir(parents=True)
            source_file.write_text(
                "\n".join(
                    [
                        "interface ArrayBuffer {",
                        "  readonly byteLength: number;",
                        "}",
                        "interface DataView {",
                        "  getInt16(byteOffset: number, littleEndian?: boolean): number;",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            (repo / "src" / "lib" / "noise.d.ts").write_text(
                "interface CheckoutRoadmap { planned: boolean; }\n",
                encoding="utf-8",
            )
            index_dir = temp_root / "index"
            index = build_index_from_repo(repo_path=repo, commit="live-cert", chunk_line_count=40, chunk_line_overlap=10)
            save_index(index, index_dir)
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(repo),
                    index_dir=str(index_dir),
                    run_dir=str(temp_root / "run"),
                    llm_config=RunLLMConfig(
                        api_style="openai_chat_completions",
                        model="dynamic-live-cert",
                        endpoint_url=server_url,
                        api_key="test-key",
                    ),
                    embedding_config=RetrievalEmbeddingConfig(
                        api_style="openai_embeddings",
                        model="text-embedding-3-large",
                        endpoint_url="http://example.test/embeddings",
                        api_key="test-key",
                    ),
                    qdrant_config=RetrievalQdrantConfig(
                        url="http://example.test:6333",
                        collection_name="live-connected-source-cert",
                    ),
                    enable_indexing=False,
                    enabled_sources=("source_code", source.source_key),
                    remote_mcp_connected_sources=(relevant_live_source, wrong_live_source),
                    connected_context_timeout_seconds=max(45, source.timeout_seconds + 15),
                    obsidian_vault_path=None,
                )
            )
            (index_dir / "qdrant-sync-manifest.json").write_text(
                json.dumps(
                    {
                        "collection_name": stage.config.qdrant_config.collection_name,
                        "document_count": len(index.documents),
                        "index_signature": f"sig:{len(index.documents)}",
                    }
                ),
                encoding="utf-8",
            )
            state = ConversationState(
                conversation_id="live-connected-source-cert",
                user_input="Explain the live connected-source issue context for DataView and ArrayBuffer.",
                intent=UserIntent.UNDERSTAND_CODE,
            )

            with _fake_structural(files=[{"path": file_hint}]):
                result = stage.retrieve(state, _policy_result(state))

            self.assertIn(
                "connected_source_context",
                result.retrieval_summary,
                msg=json.dumps(result.retrieval_summary, indent=2, sort_keys=True),
            )
            connected = result.retrieval_summary["connected_source_context"]
            self.assertGreaterEqual(
                len(connected["documents"]),
                1,
                msg=json.dumps(connected, indent=2, sort_keys=True),
            )
            self.assertEqual(_DynamicLiveCertificationLLMHandler.accepted_ids, connected["selected_context_ids"])
            self.assertEqual(_DynamicLiveCertificationLLMHandler.accepted_ids, connected["selected_evidence_ids"])
            for rejected_id in _DynamicLiveCertificationLLMHandler.rejected_ids:
                self.assertNotIn(rejected_id, connected["selected_context_ids"])
                self.assertNotIn(rejected_id, connected["selected_evidence_ids"])

            evidence_ids = {item.source_id for item in result.evidence}
            evidence_paths = {item.metadata.get("path") for item in result.evidence}
            self.assertTrue(set(_DynamicLiveCertificationLLMHandler.accepted_ids).issubset(evidence_ids))
            self.assertFalse(set(_DynamicLiveCertificationLLMHandler.rejected_ids) & evidence_ids)
            self.assertIn(file_hint, result.retrieval_summary["retrieval_plan"]["confirmed_file_hints"])
            self.assertIn(
                file_hint,
                evidence_paths,
                msg=json.dumps(
                    {
                        "evidence": [item.to_dict() for item in result.evidence],
                        "retrieval_summary": result.retrieval_summary,
                    },
                    indent=2,
                    sort_keys=True,
                ),
            )
            self.assertNotIn("src/lib/noise.d.ts", evidence_paths)


if __name__ == "__main__":
    unittest.main()
