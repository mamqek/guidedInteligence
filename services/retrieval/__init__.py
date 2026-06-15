"""Retrieval package exports.

Keep this initializer lazy so importing an individual retrieval submodule does
not pull the core control layer back into partially initialized config modules.
"""

from __future__ import annotations

from typing import Any


_CONFIG_EXPORTS = {
    "ConnectedSourceDocument",
    "MCPConnectedSourceConfig",
    "RetrievalEmbeddingConfig",
    "RetrievalQdrantConfig",
    "SourceRegistryEntry",
    "WorkspaceRetrievalConfig",
    "load_retrieval_embedding_config",
    "load_retrieval_enable_indexing",
    "load_retrieval_llm_config",
    "load_retrieval_qdrant_config",
}

__all__ = [
    *_CONFIG_EXPORTS,
    "WorkspaceRetrievalStage",
]


def __getattr__(name: str) -> Any:
    if name in _CONFIG_EXPORTS:
        from services.retrieval import config

        return getattr(config, name)
    if name == "WorkspaceRetrievalStage":
        from services.retrieval.workspace import WorkspaceRetrievalStage

        return WorkspaceRetrievalStage
    raise AttributeError(name)
