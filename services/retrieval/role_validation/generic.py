from __future__ import annotations

from services.retrieval.role_specs import role_spec, role_support_path_hints
from services.retrieval.role_validation.base import RoleValidationContext
from services.retrieval.role_validation.scoring import (
    anchor_proximity_score,
    build_breakdown,
    path_contains_any,
    query_term_score,
    text_contains_any,
)


class GenericRoleValidator:
    def __init__(self, role: str) -> None:
        self.spec = role_spec(role)
        self.role = role
        self.compatible_anchor_roles = self.spec.compatible_anchor_roles or (role,)
        self.keywords = self.spec.generic_keywords
        self.path_tokens = self.spec.path_hints
        self.support_path_tokens = self.spec.support_path_hints
        self.threshold = self.spec.validator_threshold
        self.allow_call_flow = self.spec.allow_call_flow

    def score(self, context: RoleValidationContext):
        local = query_term_score(context.query, context.helper_queries, path=context.candidate_path, text=context.candidate_text)
        has_keywords = text_contains_any(context.candidate_text, self.keywords)
        if has_keywords:
            local += 1.0
        role_path = 1.4 if path_contains_any(context.candidate_path, self.path_tokens) else 0.0
        if has_keywords and role_path > 0:
            local += 0.7
        if path_contains_any(context.candidate_path, self.support_path_tokens) and not has_keywords:
            role_path -= 1.0
            local -= 0.5
        anchors = context.anchor_support.anchors_for_roles(self.compatible_anchor_roles)
        dep_hits = tuple(context.dependency_paths)
        dep_score = 2.2 if dep_hits else 0.0
        proximity = anchor_proximity_score(context.candidate_path, anchors)
        call_hits = tuple(context.call_paths) if self.allow_call_flow else ()
        call_score = 1.5 if call_hits else 0.0
        reasons = list(dep_hits) + list(call_hits)
        if role_path > 0:
            reasons.append(f"{self.role}_path_match")
        return build_breakdown(
            local_intent_score=local,
            role_path_score=role_path,
            dependency_support_score_value=dep_score,
            anchor_proximity_score_value=proximity,
            call_flow_score_value=call_score,
            threshold=self.threshold,
            reasons=reasons,
        )
