from __future__ import annotations

# Owns run-level outcome helpers: failure result construction and plan-level objective role selection. Do not place retrieval execution, candidate handling, or synthesis scoring here.

from dataclasses import replace

from core.models import RetrievalResult
from services.retrieval.workspace.pipeline.execution_flow.context import WorkspaceRetrievalContext
from services.retrieval.workspace.pipeline.objective_flow import (
    legacy_required_roles_for_objectives as _legacy_required_roles_for_objectives,
    legacy_supporting_roles_for_objectives as _legacy_supporting_roles_for_objectives,
)
from services.retrieval.workspace.step2 import WorkspaceRetrievalPlan
from services.retrieval.workspace.step2.constants import (
    INTENT_DEFECT_LOCALIZATION,
    ROLE_BEHAVIOR_OUTPUT,
    ROLE_VALIDATION_CHECKING,
    SPECIFICITY_NARROW,
)
from services.retrieval.workspace.tools import ToolObservation


def apply_objective_role_selection(
    ctx: WorkspaceRetrievalContext,
    retrieval_plan: WorkspaceRetrievalPlan,
) -> WorkspaceRetrievalPlan:
    if not ctx.config.objective_role_selection_enabled:
        return retrieval_plan
    if retrieval_plan.primary_intent != INTENT_DEFECT_LOCALIZATION or retrieval_plan.specificity != SPECIFICITY_NARROW:
        ctx.trace.record(
            "objective_role_selection_skipped",
            {
                "primary_intent": retrieval_plan.primary_intent,
                "specificity": retrieval_plan.specificity,
                "reason": "only_narrow_defect_supported",
            },
        )
        return retrieval_plan

    required_roles = _legacy_required_roles_for_objectives(retrieval_plan.active_objectives)
    supporting_roles = _legacy_supporting_roles_for_objectives(
        tuple(retrieval_plan.active_objectives) + tuple(retrieval_plan.deferred_objectives)
    )
    if not required_roles:
        required_roles = (ROLE_BEHAVIOR_OUTPUT, ROLE_VALIDATION_CHECKING)
    updated = replace(
        retrieval_plan,
        required_roles=required_roles,
        supporting_roles=supporting_roles,
        metadata={
            **dict(retrieval_plan.metadata),
            "objective_role_selection": "enabled_narrow_defect_v1",
            "legacy_required_roles_before_objectives": list(retrieval_plan.required_roles),
            "legacy_supporting_roles_before_objectives": list(retrieval_plan.supporting_roles),
        },
    )
    ctx.trace.record(
        "objective_role_selection_applied",
        {
            "primary_intent": updated.primary_intent,
            "specificity": updated.specificity,
            "active_objectives": list(updated.active_objectives),
            "deferred_objectives": list(updated.deferred_objectives),
            "required_roles": list(updated.required_roles),
            "supporting_roles": list(updated.supporting_roles),
        },
    )
    return updated


def failed_result(
    ctx: WorkspaceRetrievalContext,
    retrieval_plan: WorkspaceRetrievalPlan | None,
    *,
    failure: str,
    observation: ToolObservation,
) -> RetrievalResult:
    ctx.trace.record(
        "retrieval_failed",
        {
            "failure": failure,
            "tool_name": observation.tool_name,
            "status": observation.status,
            "payload": dict(observation.payload),
        },
    )
    return RetrievalResult(
        evidence=(),
        coverage_status="failed",
        sufficient=False,
        retrieval_summary={
            "retriever": "workspace",
            **({"retrieval_plan": retrieval_plan.to_dict()} if retrieval_plan is not None else {}),
            "source_registry": [entry.to_dict() for entry in ctx.config.source_registry()],
            "structural_graph_provider": "codegraph",
            "failure": failure,
            "failure_reason": str(observation.payload.get("reason", "")),
        },
        failures_or_fallbacks=(failure,),
    )
