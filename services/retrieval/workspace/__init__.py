from __future__ import annotations

from services.retrieval.workspace import stage as _stage
from services.retrieval.workspace.pipeline.file_level import (
    extract_explicit_reference_paths as _extract_explicit_reference_paths,
    iterative_code_context_queries as _iterative_code_context_queries,
    resolve_explicit_reference_path as _resolve_explicit_reference_path,
    role_scoped_narrowed_files as _role_scoped_narrowed_files,
    select_diverse_completion_entries as _select_diverse_completion_entries,
)
from services.retrieval.workspace.pipeline.execution_flow.refinement_recovery import role_retarget_queries as _role_retarget_queries
from services.retrieval.workspace.pipeline.models import (
    PreparedRoleBucket,
    RetrievalCandidate,
    RetrievalSynthesisDecision,
    RoleCandidateEvaluation,
    RoleRetrievalBucket,
    RoleValidationResult,
)

__all__ = [name for name in dir(_stage) if not name.startswith("__")]
__all__.extend(
    [
        "PreparedRoleBucket",
        "RetrievalCandidate",
        "RetrievalSynthesisDecision",
        "RoleCandidateEvaluation",
        "RoleRetrievalBucket",
        "RoleValidationResult",
        "_extract_explicit_reference_paths",
        "_iterative_code_context_queries",
        "_resolve_explicit_reference_path",
        "_role_retarget_queries",
        "_role_scoped_narrowed_files",
        "_select_diverse_completion_entries",
    ]
)

for _name in __all__:
    if _name not in globals():
        globals()[_name] = getattr(_stage, _name)
