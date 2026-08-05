from __future__ import annotations

from services.intent.classifier import classify_intent
from services.intent.agreement import IntentAgreement, assess_intent_agreement
from services.intent.logging import IntentStageResult
from services.intent.models import (
    ExpectedOutput,
    IntentClassification,
    IntentClassificationInput,
    RankedRetrievalIntent,
    ResponseOperation,
    RetrievalIntent,
    SolutionPressure,
    Specificity,
    TargetReference,
    TargetType,
    TurnRelation,
    UserGoal,
)
from services.intent.normalizer import NormalizedIntent, normalize_intent
from services.intent.retrieval_hints import PRODUCT_BOUNDARY_EXPLAIN_PLAN_SUGGEST_ONLY, build_retrieval_hints

__all__ = [
    "ExpectedOutput",
    "IntentClassification",
    "IntentClassificationInput",
    "IntentAgreement",
    "IntentStageResult",
    "NormalizedIntent",
    "PRODUCT_BOUNDARY_EXPLAIN_PLAN_SUGGEST_ONLY",
    "RankedRetrievalIntent",
    "ResponseOperation",
    "RetrievalIntent",
    "SolutionPressure",
    "Specificity",
    "TargetReference",
    "TargetType",
    "TurnRelation",
    "UserGoal",
    "assess_intent_agreement",
    "classify_intent",
    "build_retrieval_hints",
    "normalize_intent",
]
