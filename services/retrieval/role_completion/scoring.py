from __future__ import annotations

from services.retrieval.role_completion.base import RoleCompletionContext, RoleCompletionScore
from services.retrieval.role_validation.scoring import anchor_proximity_score, path_contains_any, query_term_score, text_contains_any


_ROLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "representation": ("symbol", "flags", "node", "declaration", "interface", "class"),
    "input_parsing": ("parse", "parser", "modifier", "keyword", "syntaxkind", "declaration"),
    "validation_checking": ("check", "checker", "validation", "constraint", "instantiate", "implement", "super", "abstract"),
    "diagnostics": ("diagnostic", "error", "message", "report"),
    "behavior_output": ("emit", "emitter", "runtime", "transform", "output"),
}

_ROLE_PATH_TOKENS: dict[str, tuple[str, ...]] = {
    "representation": ("types", "symbol", "binder"),
    "input_parsing": ("parser", "scanner"),
    "validation_checking": ("checker", "semantic", "binder"),
    "diagnostics": ("diagnostic",),
    "behavior_output": ("emitter", "transform", "services"),
}

_WEAK_PATH_TOKENS: dict[str, tuple[str, ...]] = {
    "representation": ("readme", "thirdpartynotice", "core.d.ts"),
    "input_parsing": ("fourslash", "harness", "json2", "es5compat"),
    "validation_checking": ("tc.ts", "services.ts", "core.ts", "commandlineparser", "readme"),
    "diagnostics": ("fourslash", "harness"),
    "behavior_output": ("tc.ts", "core.ts", "readme"),
}

_THRESHOLDS: dict[str, float] = {
    "representation": 4.2,
    "input_parsing": 4.2,
    "validation_checking": 4.6,
    "diagnostics": 3.6,
    "behavior_output": 4.2,
}


def score_role_completion(context: RoleCompletionContext) -> RoleCompletionScore:
    vocabulary = query_term_score(
        context.query,
        context.helper_queries,
        path=context.candidate_path,
        text=context.candidate_text,
    )
    if text_contains_any(context.candidate_text, _ROLE_KEYWORDS.get(context.role, ())):
        vocabulary += 1.0

    path_score = 1.2 if path_contains_any(context.candidate_path, _ROLE_PATH_TOKENS.get(context.role, ())) else 0.0
    if path_contains_any(context.candidate_path, _WEAK_PATH_TOKENS.get(context.role, ())):
        path_score -= 1.2
        vocabulary -= 0.4

    all_anchors = tuple(context.accepted_anchors)
    proximity = anchor_proximity_score(context.candidate_path, all_anchors)

    architecture, support_paths, reasons = _architecture_score(context)
    prior_score = _prior_score(context)
    total = vocabulary + path_score + proximity + architecture + prior_score
    threshold = _THRESHOLDS.get(context.role, 4.2)
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
    support_paths: list[str] = []
    reasons: list[str] = []
    score = 0.0

    by_role = context.accepted_anchors_by_role
    representation_paths = _anchor_paths(by_role.get("representation", ()))
    parsing_paths = _anchor_paths(by_role.get("input_parsing", ()))
    validation_paths = _anchor_paths(by_role.get("validation_checking", ()))

    if context.role == "validation_checking":
        if parsing_paths:
            support_paths.extend(parsing_paths[:2])
        if representation_paths:
            support_paths.extend(representation_paths[:2])
        if (parsing_paths or representation_paths) and path_contains_any(context.candidate_path, ("checker", "semantic")):
            score += 2.8
            reasons.append("pipeline_completion_checker")
        elif parsing_paths and path_contains_any(context.candidate_path, ("binder",)):
            score += 1.6
            reasons.append("pipeline_completion_binder")
        if path_contains_any(context.candidate_path, ("parser", "scanner")) and not path_contains_any(context.candidate_path, ("checker", "binder")):
            score -= 1.6
            reasons.append("parser_penalty")
        if path_contains_any(context.candidate_path, ("tc.ts", "core.ts", "services.ts", "commandlineparser")):
            score -= 1.4
            reasons.append("wiring_penalty")
    elif context.role == "representation":
        if parsing_paths:
            support_paths.extend(parsing_paths[:2])
        if validation_paths:
            support_paths.extend(validation_paths[:2])
        if (parsing_paths or validation_paths) and path_contains_any(context.candidate_path, ("types", "symbol")):
            score += 2.4
            reasons.append("pipeline_completion_types")
        elif parsing_paths and path_contains_any(context.candidate_path, ("binder",)):
            score += 1.3
            reasons.append("pipeline_completion_binder")
    elif context.role == "input_parsing":
        if representation_paths:
            support_paths.extend(representation_paths[:2])
        if validation_paths:
            support_paths.extend(validation_paths[:2])
        if (representation_paths or validation_paths) and path_contains_any(context.candidate_path, ("parser", "scanner")):
            score += 2.4
            reasons.append("pipeline_completion_parser")
        elif representation_paths and path_contains_any(context.candidate_path, ("binder",)):
            score += 0.9
            reasons.append("pipeline_completion_binder")
    elif context.role == "behavior_output":
        if representation_paths:
            support_paths.extend(representation_paths[:2])
        if validation_paths:
            support_paths.extend(validation_paths[:2])
        if (representation_paths or validation_paths or parsing_paths) and path_contains_any(context.candidate_path, ("emitter", "transform")):
            score += 2.5
            reasons.append("pipeline_completion_emitter")
    elif context.role == "diagnostics":
        if validation_paths:
            support_paths.extend(validation_paths[:2])
        if path_contains_any(context.candidate_path, ("diagnostic",)):
            score += 2.0
            reasons.append("pipeline_completion_diagnostics")

    if context.source_role and context.source_role != context.role:
        if _roles_adjacent(context.role, context.source_role):
            score += 0.5
            reasons.append("cross_role_compatible")

    return score, tuple(dict.fromkeys(path for path in support_paths if path)), tuple(reasons)


def _prior_score(context: RoleCompletionContext) -> float:
    score = min(context.prior_validation_score / 4.0, 1.2)
    if context.source_state == "accepted_other_role":
        score += 0.8
    elif context.source_state == "accepted_same_role":
        score += 0.5
    elif context.source_state == "rejected":
        score += 0.1
    return score


def _anchor_paths(anchors) -> list[str]:
    return [anchor.path for anchor in anchors if getattr(anchor, "path", "")]


def _roles_adjacent(target_role: str, source_role: str) -> bool:
    adjacency = {
        "representation": {"input_parsing", "validation_checking"},
        "input_parsing": {"representation", "validation_checking"},
        "validation_checking": {"representation", "input_parsing", "diagnostics"},
        "diagnostics": {"validation_checking"},
        "behavior_output": {"validation_checking", "representation"},
    }
    return source_role in adjacency.get(target_role, set())
