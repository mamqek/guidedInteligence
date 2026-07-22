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
    PipelineRoutingDecision,
    ROUTER_MODE_OFF,
    ROUTER_MODE_PIPELINE_ACTIVE,
    ROUTER_MODE_PIPELINE_SHADOW,
    SUPPORTED_ASSISTANCE_ROUTER_MODES,
    SUPPORTED_ROUTER_MODES,
    route_assistance_mode_shadow,
    route_pipeline_shadow,
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
    "PipelineRoutingDecision",
    "PRODUCT_BOUNDARY_EXPLAIN_PLAN_SUGGEST_ONLY",
    "ROUTER_MODE_OFF",
    "ROUTER_MODE_PIPELINE_ACTIVE",
    "ROUTER_MODE_PIPELINE_SHADOW",
    "RankedRetrievalIntent",
    "ResponseOperation",
    "RetrievalIntent",
    "SolutionPressure",
    "Specificity",
    "SUPPORTED_ROUTER_MODES",
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
    "route_pipeline_shadow",
]
