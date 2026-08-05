"""Retrieval package exports.

Keep this initializer lazy so importing an individual retrieval submodule does
not pull the core control layer back into partially initialized config modules.
"""

from __future__ import annotations

from typing import Any


_CONFIG_EXPORTS = {
    "ConnectedSourceDocument",
    "MCPConnectedSourceConfig",
    "RemoteMCPConnectedSourceConfig",
    "RetrievalEmbeddingConfig",
    "RetrievalQdrantConfig",
    "SourceRegistryEntry",
    "WorkspaceRetrievalConfig",
    "load_retrieval_embedding_config",
    "load_retrieval_enable_indexing",
    "load_retrieval_qdrant_config",
}

__all__ = [
    *_CONFIG_EXPORTS,
    "WorkspaceRetrievalStage",
    "tools",
    "workspace_llm",
]


def __getattr__(name: str) -> Any:
    if name in _CONFIG_EXPORTS:
        from services.retrieval import config

        return getattr(config, name)
    if name == "WorkspaceRetrievalStage":
        from services.retrieval.workspace import WorkspaceRetrievalStage

        return WorkspaceRetrievalStage
    if name == "tools":
        from services.retrieval.workspace import tools

        return tools
    if name == "workspace_llm":
        from services.retrieval.workspace import llm as workspace_llm

        return workspace_llm
    raise AttributeError(name)
