from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.models import ConversationState
from core.source_policy import SourceCategory
from core.stages import ResponseStage
from services.retrieval.config import (
    ConnectedSourceDocument,
    MCPConnectedSourceConfig,
    RetrievalEmbeddingConfig,
    RetrievalQdrantConfig,
    RunLLMConfig,
    WorkspaceRetrievalConfig,
)
from services.retrieval.mcp import MCPConnectedSourceAdapter
from services.retrieval.workspace import WorkspaceRetrievalStage


class MCPConnectedSourceTests(unittest.TestCase):
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

    def test_workspace_collects_mcp_connected_documents_for_allowed_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            server = _write_fake_mcp_server(root)
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(root / "repo"),
                    index_dir=str(root / "index"),
                    run_dir=str(root / "run"),
                    llm_config=_llm_config(),
                    embedding_config=_embedding_config(),
                    qdrant_config=_qdrant_config(),
                    mcp_connected_sources=(
                        MCPConnectedSourceConfig(
                            name="github",
                            source_category=SourceCategory.ISSUE_TRACKER,
                            command=sys.executable,
                            args=(str(server),),
                            query_tool_name="search_issues",
                        ),
                    ),
                )
            )
            state = ConversationState(
                conversation_id="conv",
                user_input="Explain an abstract parser bug.",
                current_stage=ResponseStage.EXPLAIN,
            )

            documents = stage._connected_documents(state.user_input, (SourceCategory.ISSUE_TRACKER,))

            self.assertEqual([document.source_id for document in documents], ["mcp:github:123"])
            trace = (root / "run" / "retrieval-trace.jsonl").read_text(encoding="utf-8")
            self.assertIn("mcp_connected_source_searched", trace)
            registry = stage.config.source_registry()
            issue_entry = next(entry for entry in registry if entry.category == SourceCategory.ISSUE_TRACKER)
            self.assertTrue(issue_entry.queryable)
            self.assertEqual(issue_entry.adapter_name, "connected_documents+mcp")

    def test_workspace_skips_mcp_sources_blocked_by_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            server = _write_fake_mcp_server(root)
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(root / "repo"),
                    index_dir=str(root / "index"),
                    llm_config=_llm_config(),
                    embedding_config=_embedding_config(),
                    qdrant_config=_qdrant_config(),
                    mcp_connected_sources=(
                        MCPConnectedSourceConfig(
                            name="github",
                            source_category=SourceCategory.ISSUE_TRACKER,
                            command=sys.executable,
                            args=(str(server),),
                            query_tool_name="search_issues",
                        ),
                    ),
                )
            )

            documents = stage._connected_documents("parser bug", (SourceCategory.SOURCE_CODE,))

            self.assertEqual(documents, ())

    def test_workspace_can_promote_connected_documents_to_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            stage = WorkspaceRetrievalStage(
                WorkspaceRetrievalConfig(
                    workspace_root=str(root / "repo"),
                    index_dir=str(root / "index"),
                    llm_config=_llm_config(),
                    embedding_config=_embedding_config(),
                    qdrant_config=_qdrant_config(),
                )
            )
            document = ConnectedSourceDocument(
                source_category=SourceCategory.ISSUE_TRACKER,
                source_id="mcp:github:123",
                title="Parser issue",
                content="Issue body with reproduction details.",
                metadata={"adapter": "mcp"},
            )

            evidence = stage._append_connected_source_evidence(
                [],
                connected_documents=(document,),
                retrieval_plan=SimpleNamespace(source_priorities=(SourceCategory.ISSUE_TRACKER,)),
                source_policy=(SourceCategory.ISSUE_TRACKER,),
            )

            self.assertEqual(len(evidence), 1)
            self.assertEqual(evidence[0].source_id, "mcp:github:123")
            self.assertEqual(evidence[0].source_category, SourceCategory.ISSUE_TRACKER)
            self.assertEqual(evidence[0].metadata["retrieval_path"], "connected_source")


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
