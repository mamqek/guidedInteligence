from __future__ import annotations

# Owns the bounded adaptive retrieval loop: retrieval rounds, deferred role promotion, loop stop decisions, and round summaries. Do not place index setup, Step2 planning, final evidence selection, or low-level candidate scoring here.

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from services.retrieval.workspace.pipeline.coverage import build_deterministic_coverage_gate
from services.retrieval.workspace.pipeline.execution_flow.context import WorkspaceRetrievalContext
from services.retrieval.workspace.pipeline.execution_flow.coverage_synthesis import (
    apply_protocol_relationship_bridge,
    apply_synthesis_feedback,
    focused_owner_grounded,
    owner_focus_roles as select_owner_focus_roles,
    synthesize_or_accept_deterministic,
)
from services.retrieval.workspace.pipeline.execution_flow.refinement_recovery import (
    recover_weak_role_buckets,
    refine_selected_role_buckets,
)
from services.retrieval.workspace.pipeline.execution_flow.role_retrieval import retrieve_responsibility_role_buckets
from services.retrieval.workspace.pipeline.file_level import bucket_unresolved_roles
from services.retrieval.workspace.pipeline.models import DeterministicCoverageGate, RetrievalSynthesisDecision, RoleRetrievalBucket
from services.retrieval.workspace.pipeline.objective_flow import (
    legacy_required_roles_for_objectives,
    legacy_supporting_roles_for_objectives,
)
from services.retrieval.workspace.responsibility import ResponsibilityExpansionIntent
from services.retrieval.workspace.step2 import WorkspaceRetrievalPlan
from services.retrieval.workspace.step2.common import ordered_unique
from services.retrieval.workspace.step2.constants import (
    OBJECTIVE_BEHAVIOR_PATH,
    OBJECTIVE_CONFIGURATION_CONTEXT,
    OBJECTIVE_DIAGNOSTIC_SURFACE,
    OBJECTIVE_USAGE_CONTRACT,
    OBJECTIVE_VERIFICATION_REPRO,
    ROLE_DIAGNOSTICS,
    ROLE_TESTS,
    SPECIFICITY_NARROW,
)
from services.retrieval.workspace.tools import OpenFileTool, QdrantHybridSearchTool

MAX_ADAPTIVE_ROUNDS = 3
DEFERRED_OBJECTIVE_PROMOTION_ORDER = (
    OBJECTIVE_VERIFICATION_REPRO,
    OBJECTIVE_DIAGNOSTIC_SURFACE,
    OBJECTIVE_BEHAVIOR_PATH,
    OBJECTIVE_CONFIGURATION_CONTEXT,
    OBJECTIVE_USAGE_CONTRACT,
)


@dataclass(frozen=True)
class RetrievalRoundState:
    round_index: int
    active_roles: tuple[str, ...]
    deferred_roles: tuple[str, ...]
    promoted_roles: tuple[str, ...]
    round_reason: str
    tool_calls_used: int = 0
    owner_grounded: bool = False
    acceptance_satisfied: bool = False
    stop_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_index": self.round_index,
            "active_roles": list(self.active_roles),
            "deferred_roles": list(self.deferred_roles),
            "promoted_roles": list(self.promoted_roles),
            "round_reason": self.round_reason,
            "tool_calls_used": self.tool_calls_used,
            "owner_grounded": self.owner_grounded,
            "acceptance_satisfied": self.acceptance_satisfied,
            "stop_reason": self.stop_reason,
        }


@dataclass(frozen=True)
class AdaptiveLoopResult:
    required_buckets: tuple[RoleRetrievalBucket, ...]
    supporting_buckets: tuple[RoleRetrievalBucket, ...]
    synthesis_decision: RetrievalSynthesisDecision
    deterministic_gate: DeterministicCoverageGate
    tool_call_count: int
    responsibility_intents: tuple[ResponsibilityExpansionIntent, ...]
    round_summaries: tuple[Mapping[str, Any], ...]
    promoted_roles: tuple[str, ...]
    promoted_objectives: tuple[str, ...]
    stop_reason: str
    exploration_rounds: int
    adaptive_rounds: int


def run_adaptive_retrieval_loop(
    ctx: WorkspaceRetrievalContext,
    *,
    retrieval_plan: WorkspaceRetrievalPlan,
    qdrant_tool: QdrantHybridSearchTool,
    open_file_tool: OpenFileTool,
    structural_tools: Mapping[str, Any],
    narrowed_files: Sequence[str],
    starting_tool_call_count: int,
) -> AdaptiveLoopResult:
    adaptive_enabled = _adaptive_loop_enabled(ctx, retrieval_plan)
    ctx.trace.record(
        "adaptive_loop_started",
        {
            "enabled": adaptive_enabled,
            "task_intents": list(retrieval_plan.task_intents),
            "specificity": retrieval_plan.specificity,
            "required_roles": list(retrieval_plan.required_roles),
            "supporting_roles": list(retrieval_plan.supporting_roles),
            "active_objectives": list(retrieval_plan.active_objectives),
            "deferred_objectives": list(retrieval_plan.deferred_objectives),
            "max_rounds": MAX_ADAPTIVE_ROUNDS if adaptive_enabled else 1,
        },
    )
    if not adaptive_enabled:
        result = _run_legacy_compatibility_loop(
            ctx,
            retrieval_plan=retrieval_plan,
            qdrant_tool=qdrant_tool,
            open_file_tool=open_file_tool,
            structural_tools=structural_tools,
            narrowed_files=narrowed_files,
            starting_tool_call_count=starting_tool_call_count,
        )
        return result

    required_buckets, tool_call_count, responsibility_intents = _retrieve_and_refine_roles(
        ctx,
        retrieval_plan=retrieval_plan,
        roles=retrieval_plan.required_roles,
        qdrant_tool=qdrant_tool,
        open_file_tool=open_file_tool,
        structural_tools=structural_tools,
        narrowed_files=narrowed_files,
        starting_tool_call_count=starting_tool_call_count,
        phase="required",
        round_index=0,
        round_reason="initial_active_objectives",
    )
    owner_focus_roles = select_owner_focus_roles(ctx, retrieval_plan=retrieval_plan, buckets=required_buckets)
    synthesis_decision = synthesize_or_accept_deterministic(ctx, retrieval_plan, required_buckets)
    required_buckets = apply_synthesis_feedback(
        ctx,
        buckets=required_buckets,
        decision=synthesis_decision,
        required_roles=retrieval_plan.required_roles,
    )
    required_buckets = apply_protocol_relationship_bridge(ctx, required_buckets, retrieval_plan=retrieval_plan)
    deterministic_gate = build_deterministic_coverage_gate(retrieval_plan.required_roles, required_buckets)
    owner_grounded = focused_owner_grounded(ctx, required_buckets, owner_focus_roles)
    round_summaries: list[Mapping[str, Any]] = [
        _round_summary(
            RetrievalRoundState(
                round_index=0,
                active_roles=retrieval_plan.required_roles,
                deferred_roles=retrieval_plan.supporting_roles,
                promoted_roles=(),
                round_reason="initial_active_objectives",
                tool_calls_used=tool_call_count - starting_tool_call_count,
                owner_grounded=owner_grounded,
                acceptance_satisfied=synthesis_decision.acceptance_satisfied,
                stop_reason="sufficient" if _round_sufficient(synthesis_decision, deterministic_gate) else "",
            ),
            required_buckets=required_buckets,
            supporting_buckets=(),
            deterministic_gate=deterministic_gate,
        )
    ]
    ctx.trace.record("retrieval_round_completed", dict(round_summaries[-1]))
    if _round_sufficient(synthesis_decision, deterministic_gate):
        return _adaptive_result(
            required_buckets=required_buckets,
            supporting_buckets=(),
            synthesis_decision=synthesis_decision,
            deterministic_gate=deterministic_gate,
            tool_call_count=tool_call_count,
            responsibility_intents=responsibility_intents,
            round_summaries=round_summaries,
            promoted_roles=(),
            promoted_objectives=(),
            stop_reason=synthesis_decision.stop_reason or "initial_round_sufficient",
        )

    previous_signature = _evidence_signature(required_buckets, ())
    promoted_roles: list[str] = []
    promoted_objectives: list[str] = []
    supporting_buckets: tuple[RoleRetrievalBucket, ...] = ()
    round_index = 1

    if not owner_grounded and bucket_unresolved_roles(required_buckets) and round_index < MAX_ADAPTIVE_ROUNDS:
        ctx.trace.record(
            "retrieval_round_started",
            {
                "round_index": round_index,
                "round_reason": "same_objective_owner_recovery",
                "active_roles": list(retrieval_plan.required_roles),
                "deferred_roles": list(retrieval_plan.supporting_roles),
                "promoted_roles": [],
            },
        )
        before_calls = tool_call_count
        required_buckets, tool_call_count, synthesis_decision = recover_weak_role_buckets(
            ctx,
            retrieval_plan=retrieval_plan,
            buckets=required_buckets,
            synthesis_decision=synthesis_decision,
            qdrant_tool=qdrant_tool,
            open_file_tool=open_file_tool,
            structural_tools=structural_tools,
            narrowed_files=narrowed_files,
            starting_tool_call_count=tool_call_count,
        )
        required_buckets = apply_protocol_relationship_bridge(ctx, required_buckets, retrieval_plan=retrieval_plan)
        deterministic_gate = build_deterministic_coverage_gate(retrieval_plan.required_roles, required_buckets)
        owner_grounded = focused_owner_grounded(ctx, required_buckets, owner_focus_roles)
        summary = _round_summary(
            RetrievalRoundState(
                round_index=round_index,
                active_roles=retrieval_plan.required_roles,
                deferred_roles=retrieval_plan.supporting_roles,
                promoted_roles=(),
                round_reason="same_objective_owner_recovery",
                tool_calls_used=tool_call_count - before_calls,
                owner_grounded=owner_grounded,
                acceptance_satisfied=synthesis_decision.acceptance_satisfied,
                stop_reason="sufficient" if _round_sufficient(synthesis_decision, deterministic_gate) else "",
            ),
            required_buckets=required_buckets,
            supporting_buckets=supporting_buckets,
            deterministic_gate=deterministic_gate,
        )
        round_summaries.append(summary)
        ctx.trace.record("retrieval_round_completed", dict(summary))
        round_index += 1
        new_signature = _evidence_signature(required_buckets, supporting_buckets)
        if _round_sufficient(synthesis_decision, deterministic_gate):
            return _adaptive_result(
                required_buckets=required_buckets,
                supporting_buckets=supporting_buckets,
                synthesis_decision=synthesis_decision,
                deterministic_gate=deterministic_gate,
                tool_call_count=tool_call_count,
                responsibility_intents=responsibility_intents,
                round_summaries=round_summaries,
                promoted_roles=promoted_roles,
                promoted_objectives=promoted_objectives,
                stop_reason=synthesis_decision.stop_reason or "owner_recovery_sufficient",
            )
        if new_signature == previous_signature and not owner_grounded:
            return _adaptive_result(
                required_buckets=required_buckets,
                supporting_buckets=supporting_buckets,
                synthesis_decision=synthesis_decision,
                deterministic_gate=deterministic_gate,
                tool_call_count=tool_call_count,
                responsibility_intents=responsibility_intents,
                round_summaries=round_summaries,
                promoted_roles=promoted_roles,
                promoted_objectives=promoted_objectives,
                stop_reason="partial_no_owner_gain",
            )
        previous_signature = new_signature

    while owner_grounded and not _round_sufficient(synthesis_decision, deterministic_gate) and round_index < MAX_ADAPTIVE_ROUNDS:
        objective, roles = _next_deferred_promotion(retrieval_plan, promoted_objectives=promoted_objectives, promoted_roles=promoted_roles)
        if not roles:
            break
        if not _promotion_has_executable_subquery(retrieval_plan, roles):
            promoted_objectives.extend([objective] if objective else [])
            promoted_roles.extend(roles)
            ctx.trace.record(
                "deferred_objective_promotion_skipped",
                {
                    "round_index": round_index,
                    "objective": objective,
                    "roles": list(roles),
                    "reason": "no_executable_promotion_query",
                },
            )
            continue
        promoted_objectives.extend([objective] if objective else [])
        promoted_roles.extend(roles)
        ctx.trace.record(
            "deferred_objective_promoted",
            {
                "round_index": round_index,
                "objective": objective,
                "roles": list(roles),
                "reason": "owner_grounded_stop_contract_unsatisfied",
            },
        )
        ctx.trace.record(
            "retrieval_round_started",
            {
                "round_index": round_index,
                "round_reason": "deferred_objective_promotion",
                "active_roles": list(retrieval_plan.required_roles),
                "deferred_roles": list(role for role in retrieval_plan.supporting_roles if role not in promoted_roles),
                "promoted_roles": list(promoted_roles),
            },
        )
        before_calls = tool_call_count
        supporting_buckets, tool_call_count, supporting_intents = _retrieve_and_refine_roles(
            ctx,
            retrieval_plan=retrieval_plan,
            roles=roles,
            qdrant_tool=qdrant_tool,
            open_file_tool=open_file_tool,
            structural_tools=structural_tools,
            narrowed_files=narrowed_files,
            starting_tool_call_count=tool_call_count,
            phase="supporting",
            round_index=round_index,
            round_reason="deferred_objective_promotion",
        )
        responsibility_intents = tuple((*responsibility_intents, *supporting_intents))
        synthesis_decision = synthesize_or_accept_deterministic(ctx, retrieval_plan, required_buckets + supporting_buckets)
        updated_buckets = apply_synthesis_feedback(
            ctx,
            buckets=required_buckets + supporting_buckets,
            decision=synthesis_decision,
            required_roles=retrieval_plan.required_roles,
        )
        required_buckets = tuple(bucket for bucket in updated_buckets if bucket.role in retrieval_plan.required_roles)
        supporting_buckets = tuple(bucket for bucket in updated_buckets if bucket.role in promoted_roles)
        deterministic_gate = build_deterministic_coverage_gate(retrieval_plan.required_roles, required_buckets)
        owner_grounded = focused_owner_grounded(ctx, required_buckets, owner_focus_roles)
        summary = _round_summary(
            RetrievalRoundState(
                round_index=round_index,
                active_roles=retrieval_plan.required_roles,
                deferred_roles=tuple(role for role in retrieval_plan.supporting_roles if role not in promoted_roles),
                promoted_roles=tuple(promoted_roles),
                round_reason="deferred_objective_promotion",
                tool_calls_used=tool_call_count - before_calls,
                owner_grounded=owner_grounded,
                acceptance_satisfied=synthesis_decision.acceptance_satisfied,
                stop_reason="sufficient" if _round_sufficient(synthesis_decision, deterministic_gate) else "",
            ),
            required_buckets=required_buckets,
            supporting_buckets=supporting_buckets,
            deterministic_gate=deterministic_gate,
        )
        round_summaries.append(summary)
        ctx.trace.record("retrieval_round_completed", dict(summary))
        new_signature = _evidence_signature(required_buckets, supporting_buckets)
        if new_signature == previous_signature and not _round_sufficient(synthesis_decision, deterministic_gate):
            stop_reason = "partial_no_promoted_evidence_gain"
        else:
            stop_reason = synthesis_decision.stop_reason or ("adaptive_round_sufficient" if _round_sufficient(synthesis_decision, deterministic_gate) else "adaptive_round_limit")
        return _adaptive_result(
            required_buckets=required_buckets,
            supporting_buckets=supporting_buckets,
            synthesis_decision=synthesis_decision,
            deterministic_gate=deterministic_gate,
            tool_call_count=tool_call_count,
            responsibility_intents=responsibility_intents,
            round_summaries=round_summaries,
            promoted_roles=promoted_roles,
            promoted_objectives=promoted_objectives,
            stop_reason=stop_reason,
        )

    stop_reason = synthesis_decision.stop_reason or ("partial_owner_not_grounded" if not owner_grounded else "partial_no_deferred_promotion")
    return _adaptive_result(
        required_buckets=required_buckets,
        supporting_buckets=supporting_buckets,
        synthesis_decision=synthesis_decision,
        deterministic_gate=deterministic_gate,
        tool_call_count=tool_call_count,
        responsibility_intents=responsibility_intents,
        round_summaries=round_summaries,
        promoted_roles=promoted_roles,
        promoted_objectives=promoted_objectives,
        stop_reason=stop_reason,
    )


def _run_legacy_compatibility_loop(
    ctx: WorkspaceRetrievalContext,
    *,
    retrieval_plan: WorkspaceRetrievalPlan,
    qdrant_tool: QdrantHybridSearchTool,
    open_file_tool: OpenFileTool,
    structural_tools: Mapping[str, Any],
    narrowed_files: Sequence[str],
    starting_tool_call_count: int,
) -> AdaptiveLoopResult:
    required_buckets, tool_call_count, responsibility_intents = _retrieve_and_refine_roles(
        ctx,
        retrieval_plan=retrieval_plan,
        roles=retrieval_plan.required_roles,
        qdrant_tool=qdrant_tool,
        open_file_tool=open_file_tool,
        structural_tools=structural_tools,
        narrowed_files=narrowed_files,
        starting_tool_call_count=starting_tool_call_count,
        phase="required",
        round_index=0,
        round_reason="legacy_required_roles",
    )
    owner_focus_roles = select_owner_focus_roles(ctx, retrieval_plan=retrieval_plan, buckets=required_buckets)
    synthesis_decision = synthesize_or_accept_deterministic(ctx, retrieval_plan, required_buckets)
    required_buckets = apply_synthesis_feedback(
        ctx,
        buckets=required_buckets,
        decision=synthesis_decision,
        required_roles=retrieval_plan.required_roles,
    )
    required_buckets, tool_call_count, synthesis_decision = recover_weak_role_buckets(
        ctx,
        retrieval_plan=retrieval_plan,
        buckets=required_buckets,
        synthesis_decision=synthesis_decision,
        qdrant_tool=qdrant_tool,
        open_file_tool=open_file_tool,
        structural_tools=structural_tools,
        narrowed_files=narrowed_files,
        starting_tool_call_count=tool_call_count,
    )
    required_buckets = apply_protocol_relationship_bridge(ctx, required_buckets, retrieval_plan=retrieval_plan)
    deterministic_gate = build_deterministic_coverage_gate(retrieval_plan.required_roles, required_buckets)
    supporting_buckets: tuple[RoleRetrievalBucket, ...] = ()
    owner_grounded = focused_owner_grounded(ctx, required_buckets, owner_focus_roles)
    if not synthesis_decision.acceptance_satisfied and bucket_unresolved_roles(required_buckets) and owner_grounded:
        supporting_buckets, tool_call_count, supporting_intents = _retrieve_and_refine_roles(
            ctx,
            retrieval_plan=retrieval_plan,
            roles=retrieval_plan.supporting_roles,
            qdrant_tool=qdrant_tool,
            open_file_tool=open_file_tool,
            structural_tools=structural_tools,
            narrowed_files=narrowed_files,
            starting_tool_call_count=tool_call_count,
            phase="supporting",
            round_index=0,
            round_reason="legacy_supporting_roles",
        )
        responsibility_intents = tuple((*responsibility_intents, *supporting_intents))
        synthesis_decision = synthesize_or_accept_deterministic(ctx, retrieval_plan, required_buckets + supporting_buckets)
        updated_buckets = apply_synthesis_feedback(
            ctx,
            buckets=required_buckets + supporting_buckets,
            decision=synthesis_decision,
            required_roles=retrieval_plan.required_roles,
        )
        required_buckets = tuple(bucket for bucket in updated_buckets if bucket.role in retrieval_plan.required_roles)
        supporting_buckets = tuple(bucket for bucket in updated_buckets if bucket.role in retrieval_plan.supporting_roles)
        deterministic_gate = build_deterministic_coverage_gate(retrieval_plan.required_roles, required_buckets)
    elif not owner_grounded and bucket_unresolved_roles(required_buckets):
        ctx.trace.record(
            "supporting_expansion_deferred",
            {
                "reason": "owner_not_grounded",
                "unresolved_required_roles": list(bucket_unresolved_roles(required_buckets)),
                "focused_roles": list(owner_focus_roles),
            },
        )
    summary = _round_summary(
        RetrievalRoundState(
            round_index=0,
            active_roles=retrieval_plan.required_roles,
            deferred_roles=retrieval_plan.supporting_roles,
            promoted_roles=tuple(bucket.role for bucket in supporting_buckets),
            round_reason="legacy_compatibility",
            tool_calls_used=tool_call_count - starting_tool_call_count,
            owner_grounded=owner_grounded,
            acceptance_satisfied=synthesis_decision.acceptance_satisfied,
            stop_reason=synthesis_decision.stop_reason or "legacy_compatibility_complete",
        ),
        required_buckets=required_buckets,
        supporting_buckets=supporting_buckets,
        deterministic_gate=deterministic_gate,
    )
    ctx.trace.record("retrieval_round_completed", dict(summary))
    return _adaptive_result(
        required_buckets=required_buckets,
        supporting_buckets=supporting_buckets,
        synthesis_decision=synthesis_decision,
        deterministic_gate=deterministic_gate,
        tool_call_count=tool_call_count,
        responsibility_intents=responsibility_intents,
        round_summaries=[summary],
        promoted_roles=tuple(bucket.role for bucket in supporting_buckets),
        promoted_objectives=(),
        stop_reason=synthesis_decision.stop_reason or "legacy_compatibility_complete",
        adaptive_rounds=0,
    )


def _retrieve_and_refine_roles(
    ctx: WorkspaceRetrievalContext,
    *,
    retrieval_plan: WorkspaceRetrievalPlan,
    roles: Sequence[str],
    qdrant_tool: QdrantHybridSearchTool,
    open_file_tool: OpenFileTool,
    structural_tools: Mapping[str, Any],
    narrowed_files: Sequence[str],
    starting_tool_call_count: int,
    phase: str,
    round_index: int,
    round_reason: str,
) -> tuple[tuple[RoleRetrievalBucket, ...], int, tuple[ResponsibilityExpansionIntent, ...]]:
    roles = tuple(ordered_unique(role for role in roles if role))
    ctx.trace.record(
        "retrieval_round_started",
        {
            "round_index": round_index,
            "round_reason": round_reason,
            "phase": phase,
            "active_roles": list(roles),
        },
    )
    buckets, tool_call_count, responsibility_intents = retrieve_responsibility_role_buckets(
        ctx,
        retrieval_plan=retrieval_plan,
        subquery_roles=roles,
        qdrant_tool=qdrant_tool,
        open_file_tool=open_file_tool,
        structural_tools=structural_tools,
        narrowed_files=narrowed_files,
        starting_tool_call_count=starting_tool_call_count,
        phase=phase,
    )
    focus_roles = roles if phase == "supporting" else select_owner_focus_roles(ctx, retrieval_plan=retrieval_plan, buckets=buckets)
    ctx.trace.record(
        "owner_focus_roles_selected",
        {
            "round_index": round_index,
            "required_roles": list(roles),
            "focused_roles": list(focus_roles),
        },
    )
    buckets, tool_call_count = refine_selected_role_buckets(
        ctx,
        buckets=buckets,
        rescue_roles=focus_roles,
        qdrant_tool=qdrant_tool,
        open_file_tool=open_file_tool,
        structural_tools=structural_tools,
        starting_tool_call_count=tool_call_count,
    )
    return buckets, tool_call_count, responsibility_intents


def _adaptive_loop_enabled(ctx: WorkspaceRetrievalContext, retrieval_plan: WorkspaceRetrievalPlan) -> bool:
    return (
        ctx.config.objective_role_selection_enabled
        and "debug" in retrieval_plan.task_intents
        and retrieval_plan.specificity == SPECIFICITY_NARROW
    )


def _round_sufficient(decision: RetrievalSynthesisDecision, deterministic_gate: DeterministicCoverageGate) -> bool:
    return decision.acceptance_satisfied and deterministic_gate.satisfied


def _next_deferred_promotion(
    retrieval_plan: WorkspaceRetrievalPlan,
    *,
    promoted_objectives: Sequence[str],
    promoted_roles: Sequence[str],
) -> tuple[str, tuple[str, ...]]:
    promotable_objectives = set((*retrieval_plan.active_objectives, *retrieval_plan.deferred_objectives))
    for objective in DEFERRED_OBJECTIVE_PROMOTION_ORDER:
        if objective not in promotable_objectives or objective in promoted_objectives:
            continue
        roles = tuple(
            role
            for role in ordered_unique(
                (*legacy_supporting_roles_for_objectives((objective,)), *legacy_required_roles_for_objectives((objective,)))
            )
            if role in retrieval_plan.supporting_roles and role not in promoted_roles
        )
        if objective == OBJECTIVE_DIAGNOSTIC_SURFACE and not roles and ROLE_DIAGNOSTICS in retrieval_plan.required_roles:
            roles = (ROLE_DIAGNOSTICS,)
        if objective == OBJECTIVE_VERIFICATION_REPRO and not roles and ROLE_TESTS in retrieval_plan.supporting_roles:
            roles = (ROLE_TESTS,)
        if roles:
            return objective, roles
    remaining_roles = tuple(role for role in retrieval_plan.supporting_roles if role not in promoted_roles)
    return "", remaining_roles[:1]


def _promotion_has_executable_subquery(retrieval_plan: WorkspaceRetrievalPlan, roles: Sequence[str]) -> bool:
    role_set = set(roles)
    return any(subquery.role in role_set for subquery in (*retrieval_plan.support_subqueries, *retrieval_plan.llm_subqueries))


def _evidence_signature(required_buckets: Sequence[RoleRetrievalBucket], supporting_buckets: Sequence[RoleRetrievalBucket]) -> tuple[str, ...]:
    refs: list[str] = []
    for bucket in tuple(required_buckets) + tuple(supporting_buckets):
        refs.extend(bucket.satisfying_refs)
        refs.extend(candidate.source_id for candidate in bucket.accepted_candidates)
    return tuple(ordered_unique(refs))


def _round_summary(
    state: RetrievalRoundState,
    *,
    required_buckets: Sequence[RoleRetrievalBucket],
    supporting_buckets: Sequence[RoleRetrievalBucket],
    deterministic_gate: DeterministicCoverageGate,
) -> Mapping[str, Any]:
    data = state.to_dict()
    data.update(
        {
            "required_bucket_status": {bucket.role: bucket.role_status for bucket in required_buckets},
            "supporting_bucket_status": {bucket.role: bucket.role_status for bucket in supporting_buckets},
            "deterministic_gate": deterministic_gate.to_dict(),
        }
    )
    return data


def _adaptive_result(
    *,
    required_buckets: tuple[RoleRetrievalBucket, ...],
    supporting_buckets: tuple[RoleRetrievalBucket, ...],
    synthesis_decision: RetrievalSynthesisDecision,
    deterministic_gate: DeterministicCoverageGate,
    tool_call_count: int,
    responsibility_intents: tuple[ResponsibilityExpansionIntent, ...],
    round_summaries: Sequence[Mapping[str, Any]],
    promoted_roles: Sequence[str],
    promoted_objectives: Sequence[str],
    stop_reason: str,
    adaptive_rounds: int | None = None,
) -> AdaptiveLoopResult:
    summaries = tuple(dict(item) for item in round_summaries)
    return AdaptiveLoopResult(
        required_buckets=required_buckets,
        supporting_buckets=supporting_buckets,
        synthesis_decision=synthesis_decision,
        deterministic_gate=deterministic_gate,
        tool_call_count=tool_call_count,
        responsibility_intents=responsibility_intents,
        round_summaries=summaries,
        promoted_roles=tuple(ordered_unique(promoted_roles)),
        promoted_objectives=tuple(ordered_unique(promoted_objectives)),
        stop_reason=stop_reason,
        exploration_rounds=len(summaries),
        adaptive_rounds=max(0, len(summaries) - 1) if adaptive_rounds is None else adaptive_rounds,
    )
