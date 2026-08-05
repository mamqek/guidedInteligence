from __future__ import annotations

from core.models import RetrievalHints
from services.intent.normalizer import NormalizedIntent

PRODUCT_BOUNDARY_EXPLAIN_PLAN_SUGGEST_ONLY = "explain_plan_suggest_only"


def build_retrieval_hints(normalized_intent: NormalizedIntent) -> RetrievalHints:
    classification = normalized_intent.classification
    return RetrievalHints(
        retrieval_intents=tuple(item.to_dict() for item in classification.retrieval_intents),
        response_operation=classification.response_operation.value,
        primary_expected_output=classification.primary_expected_output.value,
        expected_outputs=tuple(output.value for output in classification.expected_outputs),
        solution_pressure=classification.solution_pressure.value,
        user_goals=tuple(goal.value for goal in classification.user_goals),
        explicit_targets=tuple(target.to_dict() for target in classification.explicit_targets),
        confidence=classification.confidence,
        product_boundary=PRODUCT_BOUNDARY_EXPLAIN_PLAN_SUGGEST_ONLY,
    )
