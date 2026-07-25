from __future__ import annotations

from services.intent.classifier import classify_intent
from services.intent.agreement import IntentAgreement, assess_intent_agreement
from services.intent.logging import IntentStageResult
from services.intent.models import (
    AssistanceMode,
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
from services.intent.router import (
    ASSISTANCE_MODE_ROUTER_ACTIVE,
    ASSISTANCE_MODE_ROUTER_OFF,
    ASSISTANCE_MODE_ROUTER_SHADOW,
    AssistanceModeDecision,
    ROUTER_MODE_OFF,
    SUPPORTED_ASSISTANCE_ROUTER_MODES,
    route_assistance_mode_shadow,
)

__all__ = [
    "AssistanceMode",
    "ASSISTANCE_MODE_ROUTER_ACTIVE",
    "ASSISTANCE_MODE_ROUTER_OFF",
    "ASSISTANCE_MODE_ROUTER_SHADOW",
    "AssistanceModeDecision",
    "ExpectedOutput",
    "IntentClassification",
    "IntentClassificationInput",
    "IntentAgreement",
    "IntentStageResult",
    "NormalizedIntent",
    "PRODUCT_BOUNDARY_EXPLAIN_PLAN_SUGGEST_ONLY",
    "ROUTER_MODE_OFF",
    "RankedRetrievalIntent",
    "ResponseOperation",
    "RetrievalIntent",
    "SolutionPressure",
    "Specificity",
    "SUPPORTED_ASSISTANCE_ROUTER_MODES",
    "TargetReference",
    "TargetType",
    "TurnRelation",
    "UserGoal",
    "assess_intent_agreement",
    "classify_intent",
    "build_retrieval_hints",
    "normalize_intent",
    "route_assistance_mode_shadow",
]
