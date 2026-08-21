from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from core.models import ConversationState, PolicyResult, RetrievalResult
from services.retrieval.config import WorkspaceRetrievalConfig
from services.retrieval.workspace.pipeline.execution_flow import WorkspaceRetrievalContext
from services.retrieval.workspace.pipeline.execution_flow.retrieval import run_workspace_retrieval
from services.retrieval.workspace.pipeline.index_flow import repo_scoped_collection_name as _repo_scoped_collection_name
from services.retrieval.workspace.tools.codegraph import close_codegraph_bridge


class WorkspaceRetrievalStage:
    """Workspace retrieval driven by shared request-analysis obligations."""

    def __init__(self, config: WorkspaceRetrievalConfig) -> None:
        config.validate()
        resolved_qdrant = replace(
            config.qdrant_config,
            collection_name=_repo_scoped_collection_name(
                base_collection_name=_lexical_collection_base_name(
                    config.qdrant_config.collection_name,
                    config.lexical_ranking_profile,
                ),
                workspace_root=Path(config.workspace_root),
            ),
        )
        self.config = replace(config, qdrant_config=resolved_qdrant)
        self.context = WorkspaceRetrievalContext.from_config(self.config)

    def retrieve(self, state: ConversationState, policy_result: PolicyResult) -> RetrievalResult:
        try:
            return run_workspace_retrieval(self.context, state, policy_result)
        finally:
            close_codegraph_bridge(self.config)


def _lexical_collection_base_name(base_name: str, lexical_ranking_profile: str) -> str:
    if lexical_ranking_profile == "flat_bm25":
        return base_name
    return f"{base_name}__{lexical_ranking_profile}"
