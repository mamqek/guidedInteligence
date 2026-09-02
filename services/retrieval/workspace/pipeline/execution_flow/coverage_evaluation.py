from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from services.intent.models import EvidenceObligation
from services.llm.json_completion import complete_json


PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "retrieval_coverage.md"
STATUSES = ("covered", "partial", "missing", "contradictory", "external")
NEEDS = ("trigger", "downstream", "implementation", "dependency", "state", "registration", "contract", "new_island", "unknown")


@dataclass(frozen=True)
class ObligationCoverage:
    obligation_id: str
    status: str
    supporting_candidate_ids: tuple[str, ...]
    missing_claim: str
    suggested_need: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CoverageBatch:
    coverage: tuple[ObligationCoverage, ...]
    usage: Mapping[str, int]

    @property
    def all_required_covered(self) -> bool:
        return all(item.status == "covered" for item in self.coverage)


def evaluate_coverage(
    *,
    llm_config: Any,
    user_request: str,
    obligations: Sequence[EvidenceObligation],
    candidates: Sequence[Mapping[str, Any]],
    max_input_chars: int = 40000,
    trace: Any | None = None,
    round_index: int = 0,
) -> CoverageBatch:
    if not obligations:
        return CoverageBatch(coverage=(), usage={})
    fixed_payload = {
        "request": user_request,
        "obligations": [item.to_dict() for item in obligations],
        "direct_evidence": [],
    }
    fixed_chars = len(json.dumps(fixed_payload, sort_keys=True))
    if fixed_chars >= max_input_chars:
        raise RuntimeError("coverage_input_budget_too_small_for_request")
    bounded_candidates = _bounded_candidates(
        candidates,
        max_input_chars=max_input_chars - fixed_chars,
    )
    candidate_ids = tuple(
        str(item.get("candidate_id") or "")
        for item in bounded_candidates
        if item.get("candidate_id")
    )
    payload = {**fixed_payload, "direct_evidence": bounded_candidates}
    if len(json.dumps(payload, sort_keys=True)) > max_input_chars:
        raise RuntimeError("coverage_input_budget_too_small_for_metadata")
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def log_event(event_type: str, value: Mapping[str, Any]) -> None:
        if event_type == "llm_response_received":
            raw = value.get("raw_response", {})
            raw_usage = raw.get("usage", {}) if isinstance(raw, Mapping) else {}
            if isinstance(raw_usage, Mapping):
                for key in usage:
                    usage[key] += int(raw_usage.get(key, 0) or 0)
        if trace is not None:
            trace.record(event_type, {"stage": "retrieval_coverage", "round": round_index, **dict(value)})

    response = complete_json(
        llm_config,
        (
            {"role": "system", "content": PROMPT_PATH.read_text(encoding="utf-8")},
            {"role": "user", "content": json.dumps(payload, sort_keys=True)},
        ),
        response_format=_response_format(tuple(item.id for item in obligations), candidate_ids),
        log_event=log_event,
    )
    coverage = _validate(response, obligations, candidate_ids)
    if trace is not None:
        trace.record(
            "coverage_evaluated",
            {"round": round_index, "coverage": [item.to_dict() for item in coverage], "usage": dict(usage)},
        )
    return CoverageBatch(coverage=coverage, usage=usage)


def _bounded_candidates(candidates: Sequence[Mapping[str, Any]], *, max_input_chars: int) -> list[dict[str, Any]]:
    per_candidate = max(0, (max_input_chars - 2) // max(1, len(candidates)))
    values: list[dict[str, Any]] = []
    for candidate in candidates:
        snippet = str(candidate.get("snippet") or "")
        assessment = candidate.get("qualification_assessment")
        compact_assessment = (
            {
                "evidence_kind": str(assessment.get("evidence_kind") or ""),
                "contributing_obligation_ids": list(
                    assessment.get("contributing_obligation_ids") or ()
                ),
                "individually_established_obligation_ids": list(
                    assessment.get("individually_established_obligation_ids") or ()
                ),
            }
            if isinstance(assessment, Mapping)
            else None
        )
        # Coverage needs identity, location, qualification, and visible source.
        # Controller-only handles and line metadata add no coverage semantics
        # and previously allowed metadata alone to exceed the request budget.
        value = {
            "candidate_id": str(candidate.get("candidate_id") or ""),
            "path": str(candidate.get("path") or ""),
            "symbol": str(candidate.get("symbol") or ""),
            "qualification_reason": str(candidate.get("qualification_reason") or "")[:240],
            "qualification_assessment": compact_assessment,
            "obligation_ids": list(candidate.get("obligation_ids") or ()),
            "snippet": "",
        }
        metadata_chars = len(json.dumps({**value, "snippet": ""}, sort_keys=True))
        truncation_marker_reserve = 48
        snippet_budget = max(0, per_candidate - metadata_chars - truncation_marker_reserve)
        value["snippet"] = snippet[:snippet_budget]
        if len(snippet) > snippet_budget:
            value["coverage_truncated"] = True
        values.append(value)
    return values


def _validate(
    response: Mapping[str, Any],
    obligations: Sequence[EvidenceObligation],
    candidate_ids: Sequence[str],
) -> tuple[ObligationCoverage, ...]:
    raw = response.get("obligations")
    if not isinstance(raw, list):
        raise RuntimeError("coverage_response_invalid: obligations must be a list")
    expected = {item.id for item in obligations}
    allowed_candidates = set(candidate_ids)
    values: dict[str, ObligationCoverage] = {}
    for item in raw:
        if not isinstance(item, Mapping):
            raise RuntimeError("coverage_response_invalid: coverage item must be an object")
        obligation_id = str(item.get("obligation_id") or "")
        status = str(item.get("status") or "")
        if obligation_id not in expected or obligation_id in values or status not in STATUSES:
            raise RuntimeError(f"coverage_response_invalid: invalid obligation {obligation_id}")
        supporting = tuple(dict.fromkeys(str(value) for value in item.get("supporting_candidate_ids", ()) if str(value)))
        if any(value not in allowed_candidates for value in supporting):
            raise RuntimeError(f"coverage_response_invalid: unknown candidate for {obligation_id}")
        if status in {"covered", "partial"} and not supporting:
            raise RuntimeError(f"coverage_response_invalid: {status} lacks support for {obligation_id}")
        need = str(item.get("suggested_need") or "unknown")
        if need not in NEEDS:
            raise RuntimeError(f"coverage_response_invalid: unknown need {need}")
        values[obligation_id] = ObligationCoverage(
            obligation_id=obligation_id,
            status=status,
            supporting_candidate_ids=supporting,
            missing_claim=str(item.get("missing_claim") or "").strip(),
            suggested_need=need,
        )
    if set(values) != expected:
        raise RuntimeError(f"coverage_response_invalid: missing obligations {sorted(expected - set(values))}")
    return tuple(values[item.id] for item in obligations)


def _response_format(obligation_ids: Sequence[str], candidate_ids: Sequence[str]) -> dict[str, Any]:
    candidate_schema: dict[str, Any] = {"type": "string"}
    if candidate_ids:
        candidate_schema["enum"] = list(candidate_ids)
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "retrieval_coverage",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "obligations": {
                        "type": "array",
                        "minItems": len(obligation_ids),
                        "maxItems": len(obligation_ids),
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "obligation_id": {"type": "string", "enum": list(obligation_ids)},
                                "status": {"type": "string", "enum": list(STATUSES)},
                                "supporting_candidate_ids": {"type": "array", "items": candidate_schema},
                                "missing_claim": {"type": "string"},
                                "suggested_need": {"type": "string", "enum": list(NEEDS)},
                            },
                            "required": ["obligation_id", "status", "supporting_candidate_ids", "missing_claim", "suggested_need"],
                        },
                    }
                },
                "required": ["obligations"],
            },
        },
    }
