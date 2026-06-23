from __future__ import annotations

from services.retrieval.workspace.role_validation.base import RoleValidationContext
from services.retrieval.workspace.role_validation.scoring import (
    anchor_proximity_score,
    build_breakdown,
    path_contains_any,
    query_term_score,
    text_contains_any,
)


class RepresentationValidator:
    role = "representation"
    compatible_anchor_roles = ("input_parsing", "validation_checking", "representation")
    keywords = ("represent", "symbol", "node", "declaration", "flag", "type", "syntaxkind")
    path_tokens = ("types", "symbol", "ast", "binder")
    threshold = 3.0

    def score(self, context: RoleValidationContext):
        local = query_term_score(context.query, context.helper_queries, path=context.candidate_path, text=context.candidate_text)
        if text_contains_any(context.candidate_text, self.keywords):
            local += 1.0
        role_path = 1.3 if path_contains_any(context.candidate_path, self.path_tokens) else 0.0
        anchors = context.anchor_support.anchors_for_roles(self.compatible_anchor_roles)
        dep_hits = tuple(context.dependency_paths)
        dep_score = 2.2 if dep_hits else 0.0
        proximity = anchor_proximity_score(context.candidate_path, anchors)
        reasons = list(dep_hits)
        if role_path > 0:
            reasons.append("representation_path_match")
        return build_breakdown(
            local_intent_score=local,
            role_path_score=role_path,
            dependency_support_score_value=dep_score,
            anchor_proximity_score_value=proximity,
            call_flow_score_value=0.0,
            threshold=self.threshold,
            reasons=reasons,
        )
