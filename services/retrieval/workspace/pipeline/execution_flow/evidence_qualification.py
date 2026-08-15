from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from services.llm.json_completion import complete_json
from services.retrieval.workspace.pipeline.execution_flow.source_disclosure import DisclosureCard


PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "evidence_qualification.md"
VALID_COMBINATIONS = {
    ("promote", "direct_evidence"),
    ("promote", "navigation_only"),
    ("defer", "navigation_only"),
    ("defer", "insufficient"),
    ("reject", "insufficient"),
}
CLASSIFICATION_TO_DECISION = {
    "promote_direct": ("promote", "direct_evidence"),
    "promote_navigation": ("promote", "navigation_only"),
    "defer_navigation": ("defer", "navigation_only"),
    "defer_insufficient": ("defer", "insufficient"),
    "reject_insufficient": ("reject", "insufficient"),
}


@dataclass(frozen=True)
class QualificationDecision:
    observation_id: str
    disposition: str
    support_level: str
    reason: str
    visible_support: tuple[str, ...] = ()
    missing_information: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class QualificationBatch:
    decisions: tuple[QualificationDecision, ...]
    usage: Mapping[str, int]
    serialized_chars: int


def qualify_cards(
    *,
    llm_config: Any,
    user_request: str,
    cards: Sequence[DisclosureCard],
    max_input_chars: int,
    trace: Any | None = None,
    round_index: int = 0,
) -> QualificationBatch:
    if not cards:
        return QualificationBatch(decisions=(), usage={}, serialized_chars=0)
    payload = _bounded_payload(user_request, cards, max_input_chars=max_input_chars)
    serialized = json.dumps(payload, sort_keys=True)
    ids = tuple(card.observation_id for card in cards)
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def log_event(event_type: str, value: Mapping[str, Any]) -> None:
        if event_type == "llm_response_received":
            raw = value.get("raw_response", {})
            raw_usage = raw.get("usage", {}) if isinstance(raw, Mapping) else {}
            if isinstance(raw_usage, Mapping):
                for key in usage:
                    usage[key] += int(raw_usage.get(key, 0) or 0)
        if trace is not None:
            trace.record(event_type, {"stage": "evidence_qualification", "round": round_index, **dict(value)})

    if trace is not None:
        trace.record(
            "qualification_requested",
            {
                "round": round_index,
                "card_ids": list(ids),
                "serialized_chars": len(serialized),
                "input_char_budget": max_input_chars,
                "prompt": str(PROMPT_PATH),
            },
        )
    response = complete_json(
        llm_config,
        (
            {"role": "system", "content": PROMPT_PATH.read_text(encoding="utf-8")},
            {"role": "user", "content": serialized},
        ),
        response_format=_response_format(ids),
        log_event=log_event,
    )
    decisions = _validate_decisions(response, ids)
    if trace is not None:
        trace.record(
            "qualification_decisions_created",
            {"round": round_index, "decisions": [item.to_dict() for item in decisions], "usage": dict(usage)},
        )
    return QualificationBatch(decisions=decisions, usage=usage, serialized_chars=len(serialized))


def _bounded_payload(
    user_request: str,
    cards: Sequence[DisclosureCard],
    *,
    max_input_chars: int,
) -> dict[str, Any]:
    base = {"request": user_request, "observations": []}
    fixed_chars = len(json.dumps(base, sort_keys=True))
    available = max(1000, max_input_chars - fixed_chars)
    per_card = max(500, available // max(1, len(cards)))
    rendered: list[dict[str, Any]] = []
    for card in cards:
        value = card.to_dict()
        outline = list(value.get("outline_entries") or ())
        value["outline_entries"] = outline[:20]
        if len(outline) > 20:
            value["qualification_truncated"] = True
        source = str(value.get("source_text") or "")
        metadata_chars = len(json.dumps({**value, "source_text": ""}, sort_keys=True))
        source_budget = max(0, per_card - metadata_chars)
        value["source_text"] = source[:source_budget]
        if len(source) > source_budget:
            value["qualification_truncated"] = True
        rendered.append(value)
    payload = {"request": user_request, "observations": rendered}
    while len(json.dumps(payload, sort_keys=True)) > max_input_chars and any(item.get("source_text") for item in rendered):
        longest = max(rendered, key=lambda item: len(str(item.get("source_text") or "")))
        source = str(longest.get("source_text") or "")
        longest["source_text"] = source[: max(0, len(source) - 512)]
        longest["qualification_truncated"] = True
    while len(json.dumps(payload, sort_keys=True)) > max_input_chars and any(item.get("outline_entries") for item in rendered):
        longest = max(rendered, key=lambda item: len(item.get("outline_entries") or ()))
        longest["outline_entries"] = list(longest.get("outline_entries") or ())[:-1]
        longest["qualification_truncated"] = True
    if len(json.dumps(payload, sort_keys=True)) > max_input_chars:
        raise RuntimeError("qualification_input_budget_too_small_for_metadata")
    return payload


def _validate_decisions(response: Mapping[str, Any], ids: Sequence[str]) -> tuple[QualificationDecision, ...]:
    raw = response.get("decisions")
    if not isinstance(raw, Mapping):
        raise RuntimeError("qualification_response_invalid: decisions must be an object keyed by observation ID")
    expected = set(ids)
    received = {str(key) for key in raw}
    if received != expected:
        raise RuntimeError(
            f"qualification_response_invalid: decision IDs differ; missing={sorted(expected - received)} "
            f"unknown={sorted(received - expected)}"
        )
    decisions: list[QualificationDecision] = []
    for observation_id in ids:
        value = raw.get(observation_id)
        if not isinstance(value, Mapping):
            raise RuntimeError("qualification_response_invalid: decision must be an object")
        classification = str(value.get("classification") or "")
        disposition, support_level = CLASSIFICATION_TO_DECISION.get(classification, ("", ""))
        if (disposition, support_level) not in VALID_COMBINATIONS:
            raise RuntimeError(f"qualification_response_invalid: invalid decision for {observation_id}")
        reason = str(value.get("reason") or "").strip()
        if not reason:
            raise RuntimeError(f"qualification_response_invalid: missing reason for {observation_id}")
        visible_support = _strings(value.get("visible_support"), limit=6)
        if disposition == "promote" and not visible_support:
            raise RuntimeError(f"qualification_response_invalid: promotion lacks visible support for {observation_id}")
        decisions.append(
            QualificationDecision(
                observation_id=observation_id,
                disposition=disposition,
                support_level=support_level,
                reason=reason,
                visible_support=visible_support,
                missing_information=_strings(value.get("missing_information"), limit=6),
            )
        )
    return tuple(decisions)


def _strings(value: object, *, limit: int) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(str(item).strip() for item in value[:limit] if str(item).strip())


def _response_format(ids: Sequence[str]) -> dict[str, Any]:
    decision_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "classification": {"type": "string", "enum": list(CLASSIFICATION_TO_DECISION)},
            "reason": {"type": "string"},
            "visible_support": {"type": "array", "items": {"type": "string"}},
            "missing_information": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["classification", "reason", "visible_support", "missing_information"],
    }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "evidence_qualification",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "decisions": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {observation_id: decision_schema for observation_id in ids},
                        "required": list(ids),
                    }
                },
                "required": ["decisions"],
            },
        },
    }
