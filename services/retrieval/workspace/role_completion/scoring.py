from __future__ import annotations

from services.retrieval.workspace.role_completion.base import RoleCompletionContext, RoleCompletionScore
from services.retrieval.workspace.role_specs import role_keywords, role_path_hints, role_spec, role_support_path_hints
from services.retrieval.workspace.role_validation.scoring import anchor_proximity_score, path_contains_any, query_term_score, text_contains_any


def score_role_completion(context: RoleCompletionContext) -> RoleCompletionScore:
    spec = role_spec(context.role)
    vocabulary = query_term_score(
        context.query,
        context.helper_queries,
        path=context.candidate_path,
        text=context.candidate_text,
    )
    if text_contains_any(context.candidate_text, role_keywords(context.role)):
        vocabulary += 1.0

    path_score = 1.2 if path_contains_any(context.candidate_path, role_path_hints(context.role)) else 0.0
    if path_contains_any(context.candidate_path, role_support_path_hints(context.role)) and not path_contains_any(context.candidate_path, role_path_hints(context.role)):
        path_score -= 1.0
        vocabulary -= 0.3

    all_anchors = tuple(context.accepted_anchors)
    proximity = anchor_proximity_score(context.candidate_path, all_anchors)

    architecture, support_paths, reasons = _architecture_score(context)
    prior_score = _prior_score(context)
    total = vocabulary + path_score + proximity + architecture + prior_score
    threshold = max(spec.validator_threshold + 1.0, 4.0)
    return RoleCompletionScore(
        accepted=total >= threshold,
        total_score=total,
        threshold=threshold,
        architecture_score=architecture,
        path_score=path_score,
        vocabulary_score=vocabulary,
        anchor_proximity_score=proximity,
        prior_score=prior_score,
        source_state=context.source_state,
        support_paths=support_paths,
        reasons=reasons,
    )


def _architecture_score(context: RoleCompletionContext) -> tuple[float, tuple[str, ...], tuple[str, ...]]:
    spec = role_spec(context.role)
    support_paths: list[str] = []
    reasons: list[str] = []
    score = 0.0

    compatible_roles = tuple(role for role in spec.compatible_anchor_roles if role != context.role)
    supporting_anchors = []
    for role in compatible_roles:
        supporting_anchors.extend(context.accepted_anchors_by_role.get(role, ()))

    support_paths.extend(anchor.path for anchor in supporting_anchors if getattr(anchor, "path", ""))
    if supporting_anchors and path_contains_any(context.candidate_path, role_path_hints(context.role)):
        score += 1.8
        reasons.append("compatible_anchor_owner_path")
    elif supporting_anchors and text_contains_any(context.candidate_text, role_keywords(context.role)):
        score += 1.0
        reasons.append("compatible_anchor_keyword_support")

    if context.source_role and context.source_role != context.role and context.source_role in compatible_roles:
        score += 0.5
        reasons.append("cross_role_compatible")

    return tuple_round(score, support_paths, reasons)


def _prior_score(context: RoleCompletionContext) -> float:
    score = min(context.prior_validation_score / 4.0, 1.2)
    if context.source_state == "accepted_other_role":
        score += 0.8
    elif context.source_state == "accepted_same_role":
        score += 0.5
    elif context.source_state == "rejected":
        score += 0.1
    return score


def tuple_round(score: float, support_paths: list[str], reasons: list[str]) -> tuple[float, tuple[str, ...], tuple[str, ...]]:
    unique_support = tuple(dict.fromkeys(path for path in support_paths if path))
    return score, unique_support, tuple(reasons)

