from __future__ import annotations

from services.retrieval.role_validation.base import RoleValidationContext
from services.retrieval.role_validation.scoring import (
    anchor_proximity_score,
    build_breakdown,
    path_contains_any,
    query_term_score,
    text_contains_any,
)


class BehaviorOutputValidator:
    role = "behavior_output"
    compatible_anchor_roles = ("input_parsing", "validation_checking", "behavior_output")
    keywords = ("emit", "transform", "runtime", "behavior", "output", "typecheck")
    path_tokens = ("emitter", "transform", "runtime")
    threshold = 3.1

    def score(self, context: RoleValidationContext):
        local = query_term_score(context.query, context.helper_queries, path=context.candidate_path, text=context.candidate_text)
        if text_contains_any(context.candidate_text, self.keywords):
            local += 1.0
        role_path = 1.3 if path_contains_any(context.candidate_path, self.path_tokens) else 0.0
        anchors = context.anchor_support.anchors_for_roles(self.compatible_anchor_roles)
        dep_hits = tuple(context.dependency_paths)
        dep_score = 2.2 if dep_hits else 0.0
        proximity = anchor_proximity_score(context.candidate_path, anchors)
        call_hits = tuple(context.call_paths)
        call_score = 1.5 if call_hits else 0.0
        reasons = list(dep_hits) + list(call_hits)
        if role_path > 0:
            reasons.append("behavior_path_match")
        return build_breakdown(
            local_intent_score=local,
            role_path_score=role_path,
            dependency_support_score_value=dep_score,
            anchor_proximity_score_value=proximity,
            call_flow_score_value=call_score,
            threshold=self.threshold,
            reasons=reasons,
        )
