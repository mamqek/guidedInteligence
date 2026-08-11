from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core.source_policy import SourceCategory
from services.retrieval.workspace.pipeline.execution_flow.connected_sources import _handles


class ConnectedSourceAssemblyTests(unittest.TestCase):
    @patch("services.retrieval.workspace.pipeline.execution_flow.connected_sources.ObsidianHybridSearchAdapter")
    def test_obsidian_vault_is_exposed_as_local_notes_source(self, adapter_type: Mock) -> None:
        adapter_type.return_value.search.return_value = (
            SimpleNamespace(
                path="architecture.md",
                title="Architecture",
                snippet="short result",
                score=1.0,
                content="Repository flow guidance.",
                metadata={"matched_by": "fulltext"},
            ),
        )
        config = SimpleNamespace(
            enabled_sources=("local_notes",),
            issue_tracker_documents=(),
            pull_request_documents=(),
            notebooklm_documents=(),
            connected_source_adapters={"remote_mcp": False, "mcp": False},
            remote_mcp_connected_sources=(),
            mcp_connected_sources=(),
            local_note_paths=(),
            obsidian_vault_path="docs/obsidian",
            obsidian_command=("obsidian-hybrid-search",),
            obsidian_db_path="docs/obsidian/index.db",
            obsidian_search_mode="fulltext",
            obsidian_timeout_seconds=20,
            obsidian_search_limit=5,
        )

        handles = _handles(SimpleNamespace(config=config), (SourceCategory.LOCAL_NOTES,))
        documents = handles[0].search("repository flow")

        self.assertEqual(handles[0].provider, "obsidian")
        self.assertEqual(documents[0].source_id, "obsidian:architecture.md")
        self.assertEqual(documents[0].content, "Repository flow guidance.")


if __name__ == "__main__":
    unittest.main()
