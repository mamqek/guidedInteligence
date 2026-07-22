from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from core.models import RetrievalResult, UserIntent
from services.intent.models import ExpectedOutput, IntentClassification, ResponseOperation, RetrievalIntent


@dataclass(frozen=True)
class IntentAgreement:
    top_level_primary: str | None
    workspace_primary: str | None
    codex_issue_type: str | None
    legacy_user_intent: str
    agreement: str
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "top_level_primary": self.top_level_primary,
            "workspace_primary": self.workspace_primary,
            "codex_issue_type": self.codex_issue_type,
            "legacy_user_intent": self.legacy_user_intent,
            "agreement": self.agreement,
            "notes": list(self.notes),
        }


def assess_intent_agreement(
    *,
    classification: IntentClassification,
    retrieval_result: RetrievalResult | None,
    legacy_user_intent: UserIntent,
) -> IntentAgreement:
    top_level_primary = _top_level_primary(classification)
    workspace_primary = _workspace_primary(retrieval_result)
    codex_issue_type = _codex_issue_type(retrieval_result)
    notes: list[str] = []
    if workspace_primary is None and codex_issue_type is None:
        return IntentAgreement(
            top_level_primary=top_level_primary,
            workspace_primary=None,
            codex_issue_type=None,
            legacy_user_intent=legacy_user_intent.value,
            agreement="unavailable",
            notes=("retrieval_intent_signal_unavailable",),
        )
    if top_level_primary is None:
        return IntentAgreement(
            top_level_primary=None,
            workspace_primary=workspace_primary,
            codex_issue_type=codex_issue_type,
            legacy_user_intent=legacy_user_intent.value,
            agreement="unavailable",
            notes=("top_level_retrieval_intent_unavailable",),
        )
    if workspace_primary == top_level_primary:
        notes.append("top_level_matches_workspace_primary")
        agreement = "exact"
    elif workspace_primary and _compatible(top_level_primary, workspace_primary):
        notes.append("top_level_compatible_with_workspace_primary")
        agreement = "compatible"
    elif workspace_primary:
        notes.append("top_level_conflicts_with_workspace_primary")
        agreement = "conflicting"
    else:
        if codex_issue_type and _compatible_with_codex_issue(top_level_primary, codex_issue_type, classification):
            agreement = "compatible"
            notes.append(_codex_compatibility_note(top_level_primary, codex_issue_type, classification))
        elif codex_issue_type:
            agreement = "conflicting"
            notes.append("compared_top_level_with_codex_issue_type")
        else:
            agreement = "unavailable"
            notes.append("workspace_primary_unavailable")
    if codex_issue_type:
        if _compatible_with_codex_issue(top_level_primary, codex_issue_type, classification):
            notes.append(_codex_compatibility_note(top_level_primary, codex_issue_type, classification))
        else:
            notes.append("top_level_not_explained_by_codex_issue_type")
    return IntentAgreement(
        top_level_primary=top_level_primary,
        workspace_primary=workspace_primary,
        codex_issue_type=codex_issue_type,
        legacy_user_intent=legacy_user_intent.value,
        agreement=agreement,
        notes=_dedupe(notes),
    )


def _top_level_primary(classification: IntentClassification) -> str | None:
    for item in classification.retrieval_intents:
        if item.priority == "primary":
            return item.intent.value
    return classification.retrieval_intents[0].intent.value if classification.retrieval_intents else None


def _workspace_primary(retrieval_result: RetrievalResult | None) -> str | None:
    if retrieval_result is None:
        return None
    summary = retrieval_result.retrieval_summary
    plan = summary.get("retrieval_plan") if isinstance(summary, Mapping) else None
    if isinstance(plan, Mapping):
        value = str(plan.get("primary_intent") or "").strip()
        return value or None
    return None


def _codex_issue_type(retrieval_result: RetrievalResult | None) -> str | None:
    if retrieval_result is None:
        return None
    summary = retrieval_result.retrieval_summary
    profile_output = summary.get("profile_output") if isinstance(summary, Mapping) else None
    if not isinstance(profile_output, Mapping):
        return None
    issue_analysis = profile_output.get("issue_analysis")
    if not isinstance(issue_analysis, Mapping):
        return None
    value = str(issue_analysis.get("issue_type") or "").strip()
    return value or None


def _compatible(left: str, right: str) -> bool:
    if left == right:
        return True
    compatible_pairs = {
        (RetrievalIntent.BEHAVIOR_EXPLANATION.value, RetrievalIntent.DEFECT_LOCALIZATION.value),
        (RetrievalIntent.DEFECT_LOCALIZATION.value, RetrievalIntent.BEHAVIOR_EXPLANATION.value),
        (RetrievalIntent.CHANGE_OR_IMPACT_PLANNING.value, RetrievalIntent.VERIFICATION_ANALYSIS.value),
        (RetrievalIntent.VERIFICATION_ANALYSIS.value, RetrievalIntent.CHANGE_OR_IMPACT_PLANNING.value),
    }
    return (left, right) in compatible_pairs


def _compatible_with_codex_issue(
    intent: str | None,
    issue_type: str | None,
    classification: IntentClassification,
) -> bool:
    if not intent or not issue_type:
        return False
    mapping = {
        "bug": {RetrievalIntent.DEFECT_LOCALIZATION.value, RetrievalIntent.BEHAVIOR_EXPLANATION.value},
        "feature_request": {RetrievalIntent.CHANGE_OR_IMPACT_PLANNING.value, RetrievalIntent.REPOSITORY_EXPLORATION.value},
        "behavior_question": {RetrievalIntent.BEHAVIOR_EXPLANATION.value, RetrievalIntent.API_OR_USAGE_LOOKUP.value},
        "performance": {RetrievalIntent.DEFECT_LOCALIZATION.value, RetrievalIntent.VERIFICATION_ANALYSIS.value},
        "compatibility": {
            RetrievalIntent.API_OR_USAGE_LOOKUP.value,
            RetrievalIntent.BEHAVIOR_EXPLANATION.value,
            RetrievalIntent.CHANGE_OR_IMPACT_PLANNING.value,
        },
        "refactor": {RetrievalIntent.CHANGE_OR_IMPACT_PLANNING.value, RetrievalIntent.REPOSITORY_EXPLORATION.value},
    }
    if intent in mapping.get(issue_type, set()):
        return True
    if _is_explanation_context(classification):
        if issue_type in {"bug", "feature_request"} and intent == RetrievalIntent.REPOSITORY_EXPLORATION.value:
            return True
        if issue_type == "feature_request" and intent == RetrievalIntent.BEHAVIOR_EXPLANATION.value:
            return True
    return False


def _is_explanation_context(classification: IntentClassification) -> bool:
    if classification.primary_expected_output == ExpectedOutput.PATCH:
        return False
    if classification.response_operation == ResponseOperation.PRODUCE:
        return False
    return classification.response_operation in {
        ResponseOperation.EXPLAIN,
        ResponseOperation.INVESTIGATE,
        ResponseOperation.PROPOSE,
    }


def _codex_compatibility_note(
    intent: str | None,
    issue_type: str | None,
    classification: IntentClassification,
) -> str:
    if _is_explanation_context(classification) and (
        (issue_type in {"bug", "feature_request"} and intent == RetrievalIntent.REPOSITORY_EXPLORATION.value)
        or (issue_type == "feature_request" and intent == RetrievalIntent.BEHAVIOR_EXPLANATION.value)
    ):
        return "explanation_context_compatible_with_codex_issue_type"
    return "top_level_compatible_with_codex_issue_type"


def _dedupe(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return tuple(output)
