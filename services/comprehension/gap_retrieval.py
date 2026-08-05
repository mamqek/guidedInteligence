from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from core.models import ConversationState, EvidenceItem, PolicyResult, RetrievalResult
from services.comprehension.builder import build_comprehension_plan
from services.comprehension.models import CoverageGap


@dataclass(frozen=True)
class GapRetrievalDecision:
    performed: bool
    requested_gaps: tuple[str, ...]
    reason: str
    passes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "performed": self.performed,
            "requested_gaps": list(self.requested_gaps),
            "reason": self.reason,
            "passes": self.passes,
        }


def retrieve_with_bounded_gap_pass(
    *,
    retrieval_stage: Any,
    state: ConversationState,
    policy_result: PolicyResult,
    initial_result: RetrievalResult,
    max_gap_retrieval_passes: int,
) -> RetrievalResult:
    if max_gap_retrieval_passes <= 0:
        return _with_gap_summary(
            initial_result,
            GapRetrievalDecision(performed=False, requested_gaps=(), reason="disabled"),
        )
    plan = build_comprehension_plan(
        user_prompt=state.user_input,
        retrieval_result=initial_result,
    )
    gaps = _retrievable_gaps(plan.coverage_gaps)
    if not gaps:
        return _with_gap_summary(
            initial_result,
            GapRetrievalDecision(performed=False, requested_gaps=(), reason="no_retrievable_gaps"),
        )
    selected_gaps = gaps[:3]
    gap_state = ConversationState(
        conversation_id=f"{state.conversation_id}:comprehension-gap-1",
        user_input=_gap_prompt(state.user_input, selected_gaps),
        intent=state.intent,
        history=state.history,
        evidence=(),
    )
    gap_result = retrieval_stage.retrieve(gap_state, policy_result)
    merged = _merge_results(initial_result, gap_result)
    decision = GapRetrievalDecision(
        performed=True,
        requested_gaps=tuple(gap.concept_id for gap in selected_gaps),
        reason="retrieved_missing_core_or_bridge_concepts",
        passes=1,
    )
    return _with_gap_summary(merged, decision, gap_result=gap_result)


def _retrievable_gaps(gaps: tuple[CoverageGap, ...]) -> tuple[CoverageGap, ...]:
    return tuple(
        gap
        for gap in gaps
        if gap.retrieval_allowed and gap.severity in {"core", "bridge"} and gap.concept_id.strip()
    )


def _gap_prompt(original_prompt: str, gaps: tuple[CoverageGap, ...]) -> str:
    gap_lines = "\n".join(
        f"- {gap.concept_id}: {gap.description}"
        for gap in gaps
    )
    return (
        f"{original_prompt.strip()}\n\n"
        "Bounded follow-up retrieval for the comprehension-plan response mode.\n"
        "Find only evidence for these missing core or bridge concepts. Do not expand into assumed or boundary concepts.\n"
        f"{gap_lines}"
    )


def _merge_results(initial: RetrievalResult, gap_result: RetrievalResult) -> RetrievalResult:
    evidence = _dedupe_evidence((*initial.evidence, *gap_result.evidence))
    summary = dict(initial.retrieval_summary)
    summary["initial_retrieval_summary"] = _safe_summary(initial.retrieval_summary)
    summary["gap_retrieval_summary"] = _safe_summary(gap_result.retrieval_summary)
    summary["selected_count_before_gap"] = len(initial.evidence)
    summary["selected_count_after_gap"] = len(evidence)
    return RetrievalResult(
        evidence=evidence,
        coverage_status=_merged_coverage_status(initial, gap_result, evidence),
        sufficient=initial.sufficient or gap_result.sufficient or len(evidence) > len(initial.evidence),
        retrieval_summary=summary,
        failures_or_fallbacks=tuple(dict.fromkeys((*initial.failures_or_fallbacks, *gap_result.failures_or_fallbacks))),
    )


def _with_gap_summary(
    result: RetrievalResult,
    decision: GapRetrievalDecision,
    *,
    gap_result: RetrievalResult | None = None,
) -> RetrievalResult:
    summary = dict(result.retrieval_summary)
    summary["comprehension_gap_retrieval"] = decision.to_dict()
    if gap_result is not None:
        summary["gap_selected_count"] = len(gap_result.evidence)
    return RetrievalResult(
        evidence=result.evidence,
        coverage_status=result.coverage_status,
        sufficient=result.sufficient,
        retrieval_summary=summary,
        failures_or_fallbacks=result.failures_or_fallbacks,
    )


def _dedupe_evidence(items: tuple[EvidenceItem, ...]) -> tuple[EvidenceItem, ...]:
    output: list[EvidenceItem] = []
    seen: set[str] = set()
    for item in items:
        if item.source_id in seen:
            continue
        seen.add(item.source_id)
        output.append(item)
    return tuple(output)


def _merged_coverage_status(initial: RetrievalResult, gap_result: RetrievalResult, evidence: tuple[EvidenceItem, ...]) -> str:
    if initial.coverage_status in {"strong", "sufficient_context"} or gap_result.coverage_status in {"strong", "sufficient_context"}:
        return "strong"
    if len(evidence) > len(initial.evidence):
        return "gap_augmented"
    return initial.coverage_status


def _safe_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key in ("retriever", "model", "prompt_profile", "coverage_status", "stop_reason", "selected_count", "prompt_summary"):
        if key in summary:
            output[key] = summary[key]
    return output
