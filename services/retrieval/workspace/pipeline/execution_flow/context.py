from __future__ import annotations

# Owns immutable run-scoped dependencies passed between workspace execution-flow functions. Do not place retrieval logic, tracing implementation, or config mutation here.

from dataclasses import dataclass

from services.retrieval.config import WorkspaceRetrievalConfig
from services.retrieval.workspace.pipeline.execution_flow.tracing import RetrievalTrace


@dataclass(frozen=True)
class WorkspaceRetrievalContext:
    config: WorkspaceRetrievalConfig
    trace: RetrievalTrace

    @classmethod
    def from_config(cls, config: WorkspaceRetrievalConfig) -> "WorkspaceRetrievalContext":
        return cls(
            config=config,
            trace=RetrievalTrace(run_dir=config.run_dir),
        )
