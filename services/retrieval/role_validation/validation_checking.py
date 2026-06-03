from __future__ import annotations

from services.retrieval.role_validation.base import RoleValidationContext
from services.retrieval.role_validation.scoring import (
    anchor_proximity_score,
    build_breakdown,
    path_contains_any,
    query_term_score,
    text_contains_any,
)


class ValidationCheckingValidator:
    role = "validation_checking"
    compatible_anchor_roles = ("input_parsing", "representation", "validation_checking")
    keywords = ("check", "validation", "constraint", "error", "instantiate", "abstract", "semantic")
    path_tokens = ("checker", "binder", "semantic")
    enforcement_keywords = ("diagnostics.", "grammarerror", "cannot", "must", "implement", "assignable", "erroron", "errorat", "check")
    threshold = 3.2

    def score(self, context: RoleValidationContext):
        local = query_term_score(context.query, context.helper_queries, path=context.candidate_path, text=context.candidate_text)
        if text_contains_any(context.candidate_text, self.keywords):
            local += 1.0
        if text_contains_any(context.candidate_text, self.enforcement_keywords):
            local += 1.2
        role_path = 1.4 if path_contains_any(context.candidate_path, self.path_tokens) else 0.0
        if path_contains_any(context.candidate_path, ("parser", "scanner")) and not text_contains_any(context.candidate_text, self.enforcement_keywords):
            role_path -= 1.4
            local -= 0.8
        anchors = context.anchor_support.anchors_for_roles(self.compatible_anchor_roles)
        dep_hits = tuple(context.dependency_paths)
        dep_score = 2.2 if dep_hits else 0.0
        proximity = anchor_proximity_score(context.candidate_path, anchors)
        call_hits = tuple(context.call_paths)
        call_score = 1.5 if call_hits else 0.0
        reasons = list(dep_hits) + list(call_hits)
        if role_path > 0:
            reasons.append("validation_path_match")
        return build_breakdown(
            local_intent_score=local,
            role_path_score=role_path,
            dependency_support_score_value=dep_score,
            anchor_proximity_score_value=proximity,
            call_flow_score_value=call_score,
            threshold=self.threshold,
            reasons=reasons,
        )
