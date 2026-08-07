from __future__ import annotations

from services.intent.contracts import get_intent_contract
from services.intent.models import IntentClassification, IntentContext, IntentFlowPlan, TaskIntent


def build_intent_context(classification: IntentClassification) -> IntentContext:
    return IntentContext(
        intents=classification.intents,
        specificity=classification.specificity,
        explicit_targets=classification.explicit_targets,
        anchors=classification.anchors,
        search_terms=classification.search_terms,
        evidence_obligations=classification.evidence_obligations,
    )


def compose_intent_flow(intents: tuple[TaskIntent, ...]) -> IntentFlowPlan:
    if not intents:
        raise ValueError("Cannot compose an intent flow without at least one intent.")
    contracts = tuple(get_intent_contract(intent) for intent in intents)
    stage_ids = tuple(stage.id for contract in contracts for stage in contract.stages)
    if len(stage_ids) != len(set(stage_ids)):
        raise RuntimeError("Composed intent flow contains duplicate stage IDs.")
    return IntentFlowPlan(intents=intents, contract_stage_ids=stage_ids, contracts=contracts)


def validate_stage_permutation(required: tuple[str, ...], ordered: tuple[str, ...]) -> tuple[str, ...]:
    missing = tuple(stage_id for stage_id in required if stage_id not in ordered)
    unknown = tuple(stage_id for stage_id in ordered if stage_id not in required)
    duplicated = tuple(sorted(stage_id for stage_id in set(ordered) if ordered.count(stage_id) > 1))
    errors: list[str] = []
    if missing:
        errors.append(f"missing stage IDs: {', '.join(missing)}")
    if unknown:
        errors.append(f"unknown stage IDs: {', '.join(unknown)}")
    if duplicated:
        errors.append(f"duplicated stage IDs: {', '.join(duplicated)}")
    if len(ordered) != len(required) and not (missing or unknown or duplicated):
        errors.append(f"expected {len(required)} stage IDs, received {len(ordered)}")
    return tuple(errors)
