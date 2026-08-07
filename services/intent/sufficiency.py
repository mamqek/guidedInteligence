from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from services.intent.contracts import get_intent_contract
from services.intent.models import TaskIntent
from services.llm.json_completion import complete_json


CoverageStatus = str
ALLOWED_STATUSES = {"covered", "partial", "missing", "unclear"}


@dataclass(frozen=True)
class SufficiencyArea:
    expectation: str
    status: CoverageStatus
    evidence_refs: tuple[str, ...]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "expectation": self.expectation,
            "status": self.status,
            "evidence_refs": list(self.evidence_refs),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class IntentSufficiency:
    intent: TaskIntent
    areas: tuple[SufficiencyArea, ...]
    overall: CoverageStatus

    def to_dict(self) -> dict[str, Any]:
        return {"intent": self.intent.value, "areas": [area.to_dict() for area in self.areas], "overall": self.overall}


def evaluate_intent_sufficiency(
    *,
    intents: tuple[TaskIntent, ...],
    evidence: Sequence[Any],
    llm_config: Any,
    log_event: Callable[[str, Mapping[str, Any]], None] | None = None,
) -> tuple[IntentSufficiency, ...]:
    """Experimental, post-retrieval observation. Never use this result to control retrieval or generation."""
    payload = {
        "contracts": [
            {"intent": intent.value, "expectations": list(get_intent_contract(intent).evidence_expectations)}
            for intent in intents
        ],
        "evidence": [
            {
                "source_id": item.source_id,
                "path": str(item.metadata.get("path") or ""),
                "claim_supported": str(item.metadata.get("claim_supported") or ""),
                "snippet": item.snippet[:1600],
            }
            for item in evidence
        ],
    }
    response = complete_json(
        llm_config,
        (
            {
                "role": "system",
                "content": (
                    "Assess only whether the already retrieved evidence visibly covers each supplied expectation. "
                    "Do not recommend retrieval or judge answer correctness. Use covered, partial, missing, or unclear. "
                    "Cite only supplied source IDs and return JSON matching the schema."
                ),
            },
            {"role": "user", "content": json.dumps(payload, sort_keys=True)},
        ),
        response_format=_response_format(intents),
        log_event=log_event,
    )
    return _validate_results(response, intents=intents, evidence=evidence)


def summarize_statuses(statuses: Sequence[str]) -> str:
    normalized = tuple(status if status in ALLOWED_STATUSES else "unclear" for status in statuses)
    if normalized and all(status == "covered" for status in normalized):
        return "covered"
    if normalized and all(status == "missing" for status in normalized):
        return "missing"
    if normalized and all(status == "unclear" for status in normalized):
        return "unclear"
    return "partial"


def _validate_results(
    response: Mapping[str, Any],
    *,
    intents: tuple[TaskIntent, ...],
    evidence: Sequence[Any],
) -> tuple[IntentSufficiency, ...]:
    raw_results = response.get("results")
    if not isinstance(raw_results, list):
        raise RuntimeError("Intent sufficiency evaluator returned no results array.")
    allowed_refs = {item.source_id for item in evidence}
    by_intent = {str(item.get("intent") or ""): item for item in raw_results if isinstance(item, Mapping)}
    output: list[IntentSufficiency] = []
    for intent in intents:
        raw = by_intent.get(intent.value)
        if not isinstance(raw, Mapping):
            raise RuntimeError(f"Intent sufficiency evaluator omitted {intent.value}.")
        expected = get_intent_contract(intent).evidence_expectations
        raw_areas = raw.get("areas")
        if not isinstance(raw_areas, list):
            raise RuntimeError(f"Intent sufficiency evaluator returned invalid areas for {intent.value}.")
        by_expectation = {str(item.get("expectation") or ""): item for item in raw_areas if isinstance(item, Mapping)}
        areas: list[SufficiencyArea] = []
        for expectation in expected:
            area = by_expectation.get(expectation)
            if not isinstance(area, Mapping):
                areas.append(SufficiencyArea(expectation, "unclear", (), "The evaluator omitted this expectation."))
                continue
            status = str(area.get("status") or "unclear").strip()
            status = status if status in ALLOWED_STATUSES else "unclear"
            raw_refs = tuple(str(ref) for ref in area.get("evidence_refs", ()) if str(ref).strip())
            invalid_refs = tuple(ref for ref in raw_refs if ref not in allowed_refs)
            refs = tuple(ref for ref in raw_refs if ref in allowed_refs)
            reason = str(area.get("reason") or "").strip()
            if invalid_refs:
                status = "unclear"
                reason = f"{reason} Invalid references were removed: {', '.join(invalid_refs)}".strip()
            areas.append(SufficiencyArea(expectation, status, refs, reason[:800]))
        output.append(IntentSufficiency(intent, tuple(areas), summarize_statuses(area.status for area in areas)))
    return tuple(output)


def _response_format(intents: tuple[TaskIntent, ...]) -> Mapping[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "intent_sufficiency_observation",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "results": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "intent": {"type": "string", "enum": [intent.value for intent in intents]},
                                "areas": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "expectation": {"type": "string"},
                                            "status": {"type": "string", "enum": sorted(ALLOWED_STATUSES)},
                                            "evidence_refs": {"type": "array", "items": {"type": "string"}},
                                            "reason": {"type": "string"},
                                        },
                                        "required": ["expectation", "status", "evidence_refs", "reason"],
                                        "additionalProperties": False,
                                    },
                                },
                            },
                            "required": ["intent", "areas"],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["results"],
                "additionalProperties": False,
            },
        },
    }
