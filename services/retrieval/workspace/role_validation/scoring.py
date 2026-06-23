from __future__ import annotations

from pathlib import PurePosixPath
from typing import Iterable, Sequence

from services.retrieval.workspace.role_validation.base import AnchorRecord, AnchorSupport, RoleScoreBreakdown, RoleValidationContext


def normalized_path(value: str) -> str:
    return value.replace("\\", "/").strip().lower()


def path_contains_any(path: str, tokens: Iterable[str]) -> bool:
    normalized = normalized_path(path)
    return any(token and token.lower() in normalized for token in tokens)


def text_contains_any(text: str, tokens: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(token and token.lower() in lowered for token in tokens)


def shared_prefix_depth(left: str, right: str) -> int:
    left_parts = PurePosixPath(normalized_path(left)).parts
    right_parts = PurePosixPath(normalized_path(right)).parts
    depth = 0
    for left_part, right_part in zip(left_parts, right_parts):
        if left_part != right_part:
            break
        depth += 1
    return depth


def anchor_proximity_score(candidate_path: str, anchors: Sequence[AnchorRecord]) -> float:
    if not candidate_path:
        return 0.0
    best = 0.0
    for anchor in anchors:
        if not anchor.path or anchor.path == candidate_path:
            continue
        depth = shared_prefix_depth(candidate_path, anchor.path)
        if depth >= 3:
            best = max(best, 1.4)
        elif depth == 2:
            best = max(best, 0.9)
        elif depth == 1:
            best = max(best, 0.4)
    return best


def dependency_support_score(candidate_path: str, anchors: Sequence[AnchorRecord], support: AnchorSupport) -> tuple[float, tuple[str, ...]]:
    if not candidate_path:
        return 0.0, ()
    hits: list[str] = []
    score = 0.0
    for anchor in anchors:
        dependency_paths = {normalized_path(path) for path in support.dependency_paths_by_anchor.get(anchor.path, ())}
        if normalized_path(candidate_path) in dependency_paths:
            hits.append(anchor.path)
            score = max(score, 2.2)
    return score, tuple(hits)


def call_flow_score(candidate_path: str, anchors: Sequence[AnchorRecord], support: AnchorSupport) -> tuple[float, tuple[str, ...]]:
    if not candidate_path:
        return 0.0, ()
    hits: list[str] = []
    score = 0.0
    for anchor in anchors:
        call_paths = {normalized_path(path) for path in support.call_paths_by_anchor.get(anchor.path, ())}
        if normalized_path(candidate_path) in call_paths:
            hits.append(anchor.path)
            score = max(score, 1.5)
    return score, tuple(hits)


def build_breakdown(
    *,
    local_intent_score: float,
    role_path_score: float,
    dependency_support_score_value: float,
    anchor_proximity_score_value: float,
    call_flow_score_value: float,
    threshold: float,
    reasons: Sequence[str],
) -> RoleScoreBreakdown:
    total = local_intent_score + role_path_score + dependency_support_score_value + anchor_proximity_score_value + call_flow_score_value
    if dependency_support_score_value > 0:
        acceptance_source = "dependency_supported"
    elif anchor_proximity_score_value > 0 or call_flow_score_value > 0:
        acceptance_source = "anchor_boosted"
    else:
        acceptance_source = "local_only"
    return RoleScoreBreakdown(
        local_intent_score=round(local_intent_score, 3),
        role_path_score=round(role_path_score, 3),
        dependency_support_score=round(dependency_support_score_value, 3),
        anchor_proximity_score=round(anchor_proximity_score_value, 3),
        call_flow_score=round(call_flow_score_value, 3),
        total_score=round(total, 3),
        threshold=round(threshold, 3),
        acceptance_source=acceptance_source,
        reasons=tuple(reasons),
    )


def query_term_score(query: str, helper_queries: Sequence[str], *, path: str, text: str) -> float:
    lowered_text = text.lower()
    lowered_path = normalized_path(path)
    score = 0.0
    for raw in query.lower().split():
        token = raw.strip(" ?!.,:;()[]{}\"'")
        if len(token) < 4:
            continue
        if token in lowered_path:
            score += 0.7
        if token in lowered_text:
            score += 0.35
    for helper in helper_queries[1:]:
        helper_lower = helper.lower().strip()
        if helper_lower and helper_lower in lowered_text:
            score += 0.25
    return score
