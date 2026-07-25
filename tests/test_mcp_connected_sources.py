from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core.models import ConversationState, EvidenceItem
from core.source_policy import SourceCategory
from services.retrieval.config import (
    ConnectedSourceDocument,
    MCPConnectedSourceConfig,
    RemoteMCPConnectedSourceConfig,
    RetrievalEmbeddingConfig,
    RetrievalQdrantConfig,
    RunLLMConfig,
    WorkspaceRetrievalConfig,
)
from services.retrieval.workspace.connected_context import ConnectedSourceContextResult
from services.retrieval.workspace.mcp import MCPConnectedSourceAdapter, RemoteMCPConnectedSourceAdapter
from services.retrieval.workspace.mcp.adapters import _extract_records
from services.retrieval.workspace.mcp.remote import _canonical_notion_identifier, _canonical_record_identifier
from services.retrieval.workspace.pipeline.evidence_flow import drop_unhinted_late_connected_file_evidence
from services.retrieval.server import RuntimeState
from services.retrieval.workspace import WorkspaceRetrievalStage


class MCPConnectedSourceTests(unittest.TestCase):
    def test_empty_search_envelope_does_not_become_document_record(self) -> None:
        self.assertEqual((), _extract_records({"total_count": 0, "incomplete_results": False}))

    def test_notion_identifier_ignores_ui_pvs_query_param(self) -> None:
        self.assertEqual(
            "https://app.notion.com/p/3a566dec1cfa81c6a25ed89c37fb7a1c",
            _canonical_notion_identifier("https://app.notion.com/p/3a566dec1cfa81c6a25ed89c37fb7a1c?pvs=1"),
        )
        self.assertEqual(
            "https://app.notion.com/p/page-id?v=view-id",
            _canonical_notion_identifier("https://app.notion.com/p/page-id?pvs=1&v=view-id"),
        )

    def test_notion_record_identifier_prefers_stable_page_id_over_url(self) -> None:
        self.assertEqual(
            "3a566dec-1cfa-81c6-a25e-d89c37fb7a1c",
            _canonical_record_identifier(
                "notion",
                {
                    "id": "3a566dec-1cfa-81c6-a25e-d89c37fb7a1c",
                    "url": "https://app.notion.com/p/3a566dec1cfa81c6a25ed89c37fb7a1c?pvs=1",
                },
            ),
        )
        self.assertEqual(
            "gi-notion-cert-codex-write-probe-2026-07-22",
            _canonical_record_identifier(
                "notion",
                {
                    "id": "3a566dec-1cfa-81c6-a25e-d89c37fb7a1c",
                    "url": "https://app.notion.com/p/3a566dec1cfa81c6a25ed89c37fb7a1c?pvs=1",
                },
                title="GI-NOTION-CERT Codex Write Probe 2026-07-22",
            ),
        )

    def test_unhinted_late_connected_file_evidence_is_dropped(self) -> None:
        selected = drop_unhinted_late_connected_file_evidence(
            [
                EvidenceItem(
                    source_category=SourceCategory.SOURCE_CODE,
                    source_id="repo-pre:src/runtime/notionCert.ts:L1-L6",
                    snippet="owner",
                    metadata={"path": "src/runtime/notionCert.ts", "retrieval_path": "late_accepted_file_span"},
                ),
                EvidenceItem(
                    source_category=SourceCategory.SOURCE_CODE,
                    source_id="repo-pre:src/runtime/notionNoise.ts:L1-L1",
                    snippet="noise",
                    metadata={"path": "src/runtime/notionNoise.ts", "retrieval_path": "late_accepted_file_span"},
                ),
                EvidenceItem(
                    source_category=SourceCategory.SOURCE_CODE,
                    source_id="repo-pre:src/runtime/notionNoise.ts:FILE",
                    snippet="noise file",
                    metadata={"path": "src/runtime/notionNoise.ts", "retrieval_path": "local_in_file_refinement"},
                ),
            ],
            connected_file_hints=("src/runtime/notionCert.ts",),
        )

        self.assertEqual(["repo-pre:src/runtime/notionCert.ts:L1-L6"], [item.source_id for item in selected])

    def test_adapter_normalizes_stdio_mcp_tool_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            server = _write_fake_mcp_server(Path(temp_dir))
            adapter = MCPConnectedSourceAdapter(
                MCPConnectedSourceConfig(
                    name="github",
                    source_category=SourceCategory.ISSUE_TRACKER,
                    command=sys.executable,
                    args=(str(server),),
                    query_tool_name="search_issues",
                )
            )

            documents = adapter.search("abstract parser bug")

            self.assertEqual(len(documents), 1)
            self.assertEqual(documents[0].source_category, SourceCategory.ISSUE_TRACKER)
            self.assertEqual(documents[0].source_id, "mcp:github:123")
            self.assertEqual(documents[0].title, "Parser issue")
            self.assertIn("abstract parser bug", documents[0].content)
            self.assertEqual(documents[0].metadata["adapter"], "mcp")
            self.assertEqual(documents[0].metadata["mcp_tool"], "search_issues")

    def test_remote_adapter_normalizes_http_mcp_tool_results(self) -> None:
        server = _FakeRemoteMCPServer()
        try:
            adapter = RemoteMCPConnectedSourceAdapter(
                RemoteMCPConnectedSourceConfig(
                    enabled=True,
                    name="notion-pages",
                    provider="notion",
                    source_category=SourceCategory.DOCUMENTATION,
                    endpoint_url=server.url,
                    auth_type="bearer",
                    bearer_token="token",
                    scope="workspace-a",
                    query_tool_name="search_pages",
                    min_score=0.5,
                )
            )

            documents = adapter.search("parser docs")

            self.assertEqual(len(documents), 1)
            self.assertEqual(documents[0].source_category, SourceCategory.DOCUMENTATION)
            self.assertEqual(documents[0].title, "Parser decision")
            self.assertIn("parser docs", documents[0].content)
            self.assertEqual(documents[0].metadata["adapter"], "remote_mcp")
            self.assertEqual(documents[0].metadata["provider"], "notion")
            self.assertEqual(server.last_authorization, "Bearer token")
        finally:
            server.close()

    def test_remote_adapter_initializes_session_when_required(self) -> None:
        server = _FakeRemoteMCPServer(require_session=True)
        try:
            documents = RemoteMCPConnectedSourceAdapter(
                RemoteMCPConnectedSourceConfig(
                    enabled=True,
                    name="shortcut-stories",
                    provider="shortcut",
                    source_category=SourceCategory.ISSUE_TRACKER,
                    endpoint_url=server.url,
                    auth_type="bearer",
                    bearer_token="token",
                    query_tool_name="search_remote",
                )
            ).search("parser docs")

            self.assertTrue(server.initialized)
            self.assertEqual(server.last_session_id, "test-session")
            self.assertEqual(len(documents), 2)
        finally:
            server.close()

    def test_remote_adapter_maps_github_scope_to_owner_repo_arguments(self) -> None:
        server = _FakeRemoteMCPServer()
        try:
            RemoteMCPConnectedSourceAdapter(
                RemoteMCPConnectedSourceConfig(
                    enabled=True,
                    name="github-issues",
                    provider="github",
                    source_category=SourceCategory.ISSUE_TRACKER,
                    endpoint_url=server.url,
                    scope="owner/repo",
                    query_tool_name="search_issues",
                )
            ).search("parser bug")

            self.assertEqual(server.last_arguments["owner"], "owner")
            self.assertEqual(server.last_arguments["repo"], "repo")
            self.assertEqual(server.last_arguments["mode"], "hybrid")
            self.assertEqual(server.last_arguments["query"], "parser bug is:issue")
            self.assertNotIn("scope", server.last_arguments)
        finally:
            server.close()

    def test_remote_adapter_searches_and_fetches_notion_results_by_enabled_types(self) -> None:
        server = _FakeRemoteMCPServer()
        try:
            documents = RemoteMCPConnectedSourceAdapter(
                RemoteMCPConnectedSourceConfig(
                    enabled=True,
                    name="notion-pages",
                    provider="notion",
                    source_category=SourceCategory.DOCUMENTATION,
                    endpoint_url=server.url,
                    features={"pages": True, "databases": False, "data_sources": True, "comments": False},
                    query_tool_name="notion-search",
                    fetch_tool_name="notion-fetch",
                    enrich_results=True,
                    enrich_limit=2,
                    result_limit=5,
                )
            ).search("parser requirements")

            self.assertEqual([document.title for document in documents], ["Parser PRD", "Parser source"])
            self.assertIn("Fetched Notion content for https://notion.test/parser-prd", documents[0].content)
            self.assertEqual(documents[0].metadata["notion_type"], "page")
            self.assertEqual(documents[0].metadata["enriched"], "true")
            self.assertEqual(documents[1].metadata["notion_type"], "data_source")
            self.assertEqual(server.called_tools, ["notion-search", "notion-fetch", "notion-fetch"])
            self.assertEqual(server.last_arguments["id"], "collection://parser-source")
        finally:
            server.close()

    def test_remote_adapter_builds_jira_jql_and_fetches_top_issue(self) -> None:
        server = _FakeRemoteMCPServer()
        try:
            documents = RemoteMCPConnectedSourceAdapter(
                RemoteMCPConnectedSourceConfig(
                    enabled=True,
                    name="jira-issues",
                    provider="atlassian",
                    source_category=SourceCategory.ISSUE_TRACKER,
                    endpoint_url=server.url,
                    scope="PROJ",
                    features={"issues": True, "comments": True, "linked_pages": True, "projects": False},
                    query_tool_name="searchJiraIssuesUsingJql",
                    fetch_tool_name="getJiraIssue",
                    enrich_results=True,
                    enrich_limit=1,
                    result_limit=3,
                )
            ).search("parser bug")

            self.assertEqual(len(documents), 1)
            self.assertIn('project = "PROJ"', server.called_arguments[0]["jql"])
            self.assertIn('text ~ "parser bug"', server.called_arguments[0]["jql"])
            self.assertEqual(server.called_tools, ["searchJiraIssuesUsingJql", "getJiraIssue"])
            self.assertEqual(documents[0].metadata["record_type"], "issue")
            self.assertEqual(documents[0].metadata["enriched"], "true")
        finally:
            server.close()

    def test_remote_adapter_discovers_slack_search_and_fetch_tools(self) -> None:
        server = _FakeRemoteMCPServer()
        try:
            documents = RemoteMCPConnectedSourceAdapter(
                RemoteMCPConnectedSourceConfig(
                    enabled=True,
                    name="slack-messages",
                    provider="slack",
                    source_category=SourceCategory.LOCAL_NOTES,
                    endpoint_url=server.url,
                    features={"messages": True, "files": False, "threads": True},
                    query_tool_name="",
                    fetch_tool_name="",
                    enrich_results=True,
                    enrich_limit=1,
                    result_limit=3,
                )
            ).search("release decision")

            self.assertEqual([document.title for document in documents], ["Release decision"])
            self.assertEqual(server.called_tools, ["search_messages", "read_thread"])
            self.assertEqual(documents[0].metadata["record_type"], "thread")
            self.assertEqual(documents[0].metadata["enriched"], "true")
        finally:
            server.close()

    def test_remote_adapter_sends_oauth_and_api_key_credentials(self) -> None:
        oauth_server = _FakeRemoteMCPServer()
        api_key_server = _FakeRemoteMCPServer()
        try:
            RemoteMCPConnectedSourceAdapter(
                RemoteMCPConnectedSourceConfig(
                    enabled=True,
                    name="slack-messages",
                    provider="slack",
                    source_category=SourceCategory.LOCAL_NOTES,
                    endpoint_url=oauth_server.url,
                    auth_type="oauth",
                    oauth_access_token="oauth-token",
                    query_tool_name="search_messages",
                    min_score=0.5,
                )
            ).search("decision")
            RemoteMCPConnectedSourceAdapter(
                RemoteMCPConnectedSourceConfig(
                    enabled=True,
                    name="drive-docs",
                    provider="google_drive",
                    source_category=SourceCategory.DOCUMENTATION,
                    endpoint_url=api_key_server.url,
                    auth_type="api_key",
                    api_key="drive-key",
                    api_key_header="X-Drive-Key",
                    query_tool_name="search_documents",
                    min_score=0.5,
                )
            ).search("decision")

            self.assertEqual(oauth_server.last_authorization, "Bearer oauth-token")
            self.assertEqual(api_key_server.last_api_key, "drive-key")
        finally:
            oauth_server.close()
            api_key_server.close()

    def test_remote_adapter_lists_tools_from_json_and_sse_responses(self) -> None:
        json_server = _FakeRemoteMCPServer()
        sse_server = _FakeRemoteMCPServer(use_sse=True)
        try:
            json_tools = RemoteMCPConnectedSourceAdapter(
                RemoteMCPConnectedSourceConfig(
                    enabled=True,
                    name="notion-pages",
                    provider="notion",
                    source_category=SourceCategory.DOCUMENTATION,
                    endpoint_url=json_server.url,
                    query_tool_name="search_pages",
                )
            ).list_tools()
            sse_tools = RemoteMCPConnectedSourceAdapter(
                RemoteMCPConnectedSourceConfig(
                    enabled=True,
                    name="slack-messages",
                    provider="slack",
                    source_category=SourceCategory.LOCAL_NOTES,
                    endpoint_url=sse_server.url,
                    query_tool_name="search_messages",
                )
            ).list_tools()

            self.assertEqual(json_tools[0]["name"], "search_remote")
            self.assertEqual(sse_tools[0]["name"], "search_remote")
        finally:
            json_server.close()
            sse_server.close()

    def test_remote_adapter_filters_scored_results_below_min_score(self) -> None:
        server = _FakeRemoteMCPServer()
        try:
            adapter = RemoteMCPConnectedSourceAdapter(
                RemoteMCPConnectedSourceConfig(
                    enabled=True,
                    name="notion-pages",
                    provider="notion",
                    source_category=SourceCategory.DOCUMENTATION,
                    endpoint_url=server.url,
                    query_tool_name="search_pages",
                    min_score=0.5,
                )
            )

            documents = adapter.search("parser docs")

            self.assertEqual(len(documents), 1)
            self.assertEqual(documents[0].source_id, "remote-mcp:notion:notion-pages:remote-1")
            self.assertEqual(documents[0].metadata["score"], "0.920000")
        finally:
            server.close()

    def test_runtime_state_test_connection_returns_normalized_documents(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            server = _write_fake_mcp_server(root)
            state = RuntimeState(root)

            result = state.test_connection(
                {
                    "name": "github-issues",
                    "source_category": "issue_tracker",
                    "command": sys.executable,
                    "args": [str(server)],
                    "query_tool_name": "search_issues",
                    "test_query": "policy fallback",
                }
            )

            self.assertTrue(result["ok"])
            self.assertEqual(result["name"], "github-issues")
            self.assertEqual(result["source_category"], "issue_tracker")
            self.assertEqual(result["result_count"], 1)
            documents = result["documents"]
            self.assertEqual(documents[0]["source_id"], "mcp:github-issues:123")
            self.assertIn("policy fallback", documents[0]["content"])


def _write_fake_mcp_server(root: Path) -> Path:
    server = root / "fake_mcp_server.py"
    server.write_text(
        """
import json
import sys

for line in sys.stdin:
    request = json.loads(line)
    method = request.get("method")
    request_id = request.get("id")
    if method == "notifications/initialized":
        continue
    if method == "initialize":
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fake", "version": "1"},
            },
        }
    elif method == "tools/call":
        query = request.get("params", {}).get("arguments", {}).get("query", "")
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "results": [
                                    {
                                        "id": "123",
                                        "title": "Parser issue",
                                        "body": f"GitHub issue body for {query}",
                                        "url": "https://github.test/repo/issues/123",
                                        "state": "open",
                                    }
                                ]
                            }
                        ),
                    }
                ]
            },
        }
    else:
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": "unknown method"},
        }
    sys.stdout.write(json.dumps(response) + "\\n")
    sys.stdout.flush()
""".lstrip(),
        encoding="utf-8",
    )
    return server


class _FakeRemoteMCPServer:
    def __init__(self, *, use_sse: bool = False, require_session: bool = False) -> None:
        self.last_authorization = ""
        self.last_api_key = ""
        self.last_session_id = ""
        self.last_arguments: dict[str, object] = {}
        self.called_arguments: list[dict[str, object]] = []
        self.called_tools: list[str] = []
        self.initialized = False
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length", "0") or "0")
                request = json.loads(self.rfile.read(length).decode("utf-8"))
                owner.last_authorization = self.headers.get("Authorization", "")
                owner.last_api_key = self.headers.get("X-Drive-Key", "")
                owner.last_session_id = self.headers.get("Mcp-Session-Id", "")
                if request.get("method") == "initialize":
                    owner.initialized = True
                    self._send_response(
                        {
                            "jsonrpc": "2.0",
                            "id": request.get("id"),
                            "result": {
                                "protocolVersion": "2024-11-05",
                                "capabilities": {"tools": {}},
                                "serverInfo": {"name": "fake-remote", "version": "1"},
                            },
                        },
                        session_id="test-session",
                    )
                    return
                if request.get("method") == "notifications/initialized":
                    self.send_response(202)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                if require_session and self.headers.get("Mcp-Session-Id", "") != "test-session":
                    self._send_error(request.get("id"))
                    return
                if request.get("method") == "tools/list":
                    response = {
                        "jsonrpc": "2.0",
                        "id": request.get("id"),
                        "result": {
                            "tools": [
                                {
                                    "name": "search_remote",
                                    "description": "Search remote test data.",
                                },
                                {"name": "search_messages", "description": "Search Slack messages."},
                                {"name": "read_thread", "description": "Read a Slack thread."},
                            ]
                        },
                    }
                    self._send_response(response)
                    return
                params = request.get("params", {})
                tool_name = params.get("name", "")
                if isinstance(tool_name, str) and tool_name:
                    owner.called_tools.append(tool_name)
                arguments = params.get("arguments", {})
                owner.last_arguments = dict(arguments)
                owner.called_arguments.append(dict(arguments))
                if tool_name == "notion-search":
                    self._send_response(
                        {
                            "jsonrpc": "2.0",
                            "id": request.get("id"),
                            "result": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": json.dumps(
                                            {
                                                "results": [
                                                    {
                                                        "id": "page-1",
                                                        "object": "page",
                                                        "title": "Parser PRD",
                                                        "text": "Search highlight for parser requirements.",
                                                        "url": "https://notion.test/parser-prd",
                                                    },
                                                    {
                                                        "id": "db-1",
                                                        "object": "database",
                                                        "title": "Parser database",
                                                        "text": "Should be filtered out.",
                                                        "url": "https://notion.test/parser-db",
                                                    },
                                                    {
                                                        "id": "ds-1",
                                                        "object": "data_source",
                                                        "title": "Parser source",
                                                        "text": "Data source schema.",
                                                        "url": "collection://parser-source",
                                                    },
                                                ]
                                            }
                                        ),
                                    }
                                ]
                            },
                        }
                    )
                    return
                if tool_name == "notion-fetch":
                    self._send_response(
                        {
                            "jsonrpc": "2.0",
                            "id": request.get("id"),
                            "result": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": f"Fetched Notion content for {arguments.get('id', '')}",
                                    }
                                ]
                            },
                        }
                    )
                    return
                if tool_name == "searchJiraIssuesUsingJql":
                    self._send_response(
                        {
                            "jsonrpc": "2.0",
                            "id": request.get("id"),
                            "result": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": json.dumps(
                                            {
                                                "issues": [
                                                    {
                                                        "key": "PROJ-7",
                                                        "type": "issue",
                                                        "title": "Parser bug",
                                                        "summary": "Parser bug search result.",
                                                        "score": 0.91,
                                                    }
                                                ]
                                            }
                                        ),
                                    }
                                ]
                            },
                        }
                    )
                    return
                if tool_name == "getJiraIssue":
                    self._send_response(
                        {
                            "jsonrpc": "2.0",
                            "id": request.get("id"),
                            "result": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "Fetched Jira issue with comments and linked pages.",
                                    }
                                ]
                            },
                        }
                    )
                    return
                if tool_name == "search_messages":
                    self._send_response(
                        {
                            "jsonrpc": "2.0",
                            "id": request.get("id"),
                            "result": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": json.dumps(
                                            {
                                                "results": [
                                                    {
                                                        "id": "thread-1",
                                                        "type": "thread",
                                                        "title": "Release decision",
                                                        "text": "Decision snippet.",
                                                        "thread_ts": "123.456",
                                                        "channel": "C123",
                                                    },
                                                    {
                                                        "id": "file-1",
                                                        "type": "file",
                                                        "title": "Release notes",
                                                        "text": "Should be filtered out.",
                                                    },
                                                ]
                                            }
                                        ),
                                    }
                                ]
                            },
                        }
                    )
                    return
                if tool_name == "read_thread":
                    self._send_response(
                        {
                            "jsonrpc": "2.0",
                            "id": request.get("id"),
                            "result": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "Fetched Slack thread context.",
                                    }
                                ]
                            },
                        }
                    )
                    return
                query = arguments.get("query", "")
                response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(
                                    {
                                        "results": [
                                            {
                                                "id": "remote-1",
                                                "title": "Parser decision",
                                                "body": f"Remote MCP document for {query}",
                                                "score": 0.92,
                                                "url": "https://remote.test/doc/remote-1",
                                            },
                                            {
                                                "id": "remote-2",
                                                "title": "Unrelated result",
                                                "body": "Low relevance result.",
                                                "score": 0.12,
                                                "url": "https://remote.test/doc/remote-2",
                                            }
                                        ]
                                    }
                                ),
                            }
                        ]
                    },
                }
                self._send_response(response)

            def _send_error(self, request_id: object) -> None:
                encoded = json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "error": {"code": -32000, "message": "No session ID provided for non-initialization request"},
                        "id": request_id,
                    }
                ).encode("utf-8")
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def _send_response(self, response: dict[str, object], *, session_id: str = "") -> None:
                if use_sse:
                    encoded = f"data: {json.dumps(response)}\n\n".encode("utf-8")
                    content_type = "text/event-stream"
                else:
                    encoded = json.dumps(response).encode("utf-8")
                    content_type = "application/json"
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                if session_id:
                    self.send_header("Mcp-Session-Id", session_id)
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, _format: str, *_args: object) -> None:
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.url = f"http://{host}:{port}/mcp"

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


def _llm_config() -> RunLLMConfig:
    return RunLLMConfig(
        api_style="openai_chat_completions",
        model="test-model",
        endpoint_url="http://example.test/v1/chat/completions",
        api_key="test-key",
    )


def _embedding_config() -> RetrievalEmbeddingConfig:
    return RetrievalEmbeddingConfig(
        api_style="openai_embeddings",
        model="text-embedding-3-large",
        endpoint_url="http://example.test/embeddings",
        api_key="test-key",
    )


def _qdrant_config() -> RetrievalQdrantConfig:
    return RetrievalQdrantConfig(
        url="http://example.test:6333",
        collection_name="test-retrieval",
    )


if __name__ == "__main__":
    unittest.main()
