from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from services.llm.json_completion import complete_json
from services.retrieval.workspace.pipeline.execution_flow.source_disclosure import DisclosureCard
from services.retrieval.workspace.pipeline.execution_flow.source_disclosure import fit_cards_to_source_capacity


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
INPUT_SAFETY_RESERVE_CHARS = 512


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
    cards: tuple[DisclosureCard, ...] = ()
    input_chars: int = 0
    source_capacity: int = 0


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
    prompt_text = PROMPT_PATH.read_text(encoding="utf-8")
    return _qualify_card_batch(
        llm_config=llm_config,
        user_request=user_request,
        cards=cards,
        max_input_chars=max_input_chars,
        prompt_text=prompt_text,
        trace=trace,
        round_index=round_index,
    )


def _qualify_card_batch(
    *, llm_config: Any, user_request: str, cards: Sequence[DisclosureCard], max_input_chars: int,
    prompt_text: str, trace: Any | None, round_index: int,
) -> QualificationBatch:
    ids = tuple(card.observation_id for card in cards)
    response_format = _response_format(ids)
    payload, bounded_cards, budget = _bounded_payload(
        user_request, cards, max_input_chars=max_input_chars,
        prompt_text=prompt_text, response_format=response_format,
    )
    serialized = json.dumps(payload, sort_keys=True)
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

    empty_source_ids = tuple(item.observation_id for item in bounded_cards if not item.source_text.strip())
    empty_non_fold_ids = tuple(
        item.observation_id for item in bounded_cards if item.mode != "fold" and not item.source_text.strip()
    )
    omitted_source_ids = tuple(
        item.observation_id
        for item in bounded_cards
        if "complete source lines omitted" in item.source_text
        or item.truncation_reason == "qualification_source_budget_complete_lines"
    )

    if trace is not None:
        if empty_source_ids or omitted_source_ids:
            trace.record(
                "qualification_source_degradation_detected",
                {
                    "severity": "error" if empty_non_fold_ids else "warning",
                    "round": round_index,
                    "empty_source_card_ids": list(empty_source_ids),
                    "empty_non_fold_card_ids": list(empty_non_fold_ids),
                    "omitted_source_card_ids": list(omitted_source_ids),
                    "source_chars_by_card": {
                        item.observation_id: len(item.source_text) for item in bounded_cards
                    },
                    "source_capacity": budget["source_capacity"],
                    "fixed_input_chars": budget["fixed_input_chars"],
                    "input_char_budget": max_input_chars,
                    "message": "Qualification source was empty or owner source lines were omitted.",
                },
            )
        trace.record(
            "qualification_requested",
            {
                "round": round_index,
                "card_ids": list(ids),
                "serialized_chars": len(serialized),
                "total_input_chars": budget["total_input_chars"],
                "input_char_budget": max_input_chars,
                "fixed_input_chars": budget["fixed_input_chars"],
                "source_capacity": budget["source_capacity"],
                "source_used_chars": sum(len(item.source_text) for item in bounded_cards),
                "empty_source_card_ids": list(empty_source_ids),
                "empty_non_fold_card_ids": list(empty_non_fold_ids),
                "omitted_source_card_ids": list(omitted_source_ids),
                "safety_reserve_chars": INPUT_SAFETY_RESERVE_CHARS,
                "prompt": str(PROMPT_PATH),
            },
        )
    response = complete_json(
        llm_config,
        (
            {"role": "system", "content": prompt_text},
            {"role": "user", "content": serialized},
        ),
        response_format=response_format,
        log_event=log_event,
    )
    decisions = _validate_decisions(response, ids)
    if trace is not None:
        trace.record(
            "qualification_decisions_created",
            {"round": round_index, "decisions": [item.to_dict() for item in decisions], "usage": dict(usage)},
        )
    return QualificationBatch(decisions, usage, len(serialized), bounded_cards,
                              budget["total_input_chars"], budget["source_capacity"])


def _bounded_payload(
    user_request: str,
    cards: Sequence[DisclosureCard],
    *,
    max_input_chars: int,
    prompt_text: str | None = None,
    response_format: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], tuple[DisclosureCard, ...], dict[str, int]]:
    ids = tuple(card.observation_id for card in cards)
    system_prompt = prompt_text if prompt_text is not None else PROMPT_PATH.read_text(encoding="utf-8")
    schema = dict(response_format or _response_format(ids))
    prepared = tuple(cards)

    def fixed_input_chars(values: Sequence[DisclosureCard]) -> int:
        return _total_input_chars(system_prompt, schema, _payload(user_request, values, blank_source=True))

    fixed = fixed_input_chars(prepared)
    if fixed > max_input_chars:
        raise RuntimeError("qualification_input_budget_too_small_for_metadata")
    source_capacity = max(0, max_input_chars - fixed)
    bounded = fit_cards_to_source_capacity(prepared, source_capacity=source_capacity)
    payload = _payload(user_request, bounded)
    total = _total_input_chars(system_prompt, schema, payload)
    while total > max_input_chars and source_capacity > 0:
        source_capacity = max(0, source_capacity - (total - max_input_chars))
        bounded = fit_cards_to_source_capacity(prepared, source_capacity=source_capacity)
        payload = _payload(user_request, bounded)
        total = _total_input_chars(system_prompt, schema, payload)
    if total > max_input_chars:
        raise RuntimeError("qualification_input_budget_too_small_for_metadata")
    return payload, bounded, {"fixed_input_chars": fixed, "source_capacity": source_capacity, "total_input_chars": total}


def _payload(user_request: str, cards: Sequence[DisclosureCard], *, blank_source: bool = False) -> dict[str, Any]:
    file_ids: dict[str, str] = {}
    owner_ids: dict[tuple[object, ...], str] = {}
    file_contexts: dict[str, dict[str, Any]] = {}
    rendered: list[dict[str, Any]] = []
    for card in cards:
        path = card.handle.path
        file_id = file_ids.setdefault(path, f"file_{len(file_ids) + 1}")
        file_context = file_contexts.setdefault(file_id, {"path": path, "relevant_owners": {}})
        owner_key = (
            path,
            card.owner_kind,
            card.owner_name,
            card.owner_line_start,
            card.owner_line_end,
            card.outer_owner_line_start,
            card.outer_owner_line_end,
        )
        owner_id = owner_ids.get(owner_key)
        if owner_id is None:
            owner_id = f"owner_{len(file_context['relevant_owners']) + 1}"
            owner_ids[owner_key] = owner_id
            file_context["relevant_owners"][owner_id] = _without_empty_values(
                {
                    "kind": card.owner_kind,
                    "name": card.owner_name or card.handle.symbol,
                    "line_start": card.owner_line_start or card.handle.full_line_start or card.handle.line_start,
                    "line_end": card.owner_line_end or card.handle.full_line_end or card.handle.line_end,
                    "outer_line_start": card.outer_owner_line_start,
                    "outer_line_end": card.outer_owner_line_end,
                }
            )
        provenance = dict(card.provenance_summary or {})
        navigation_context = _without_empty_values(
            {
                "obligation_ids": list(provenance.get("obligation_ids") or ()),
                "exact_anchor_matches": list(provenance.get("exact_anchor_matches") or ()),
                "recurrence": int(provenance.get("recurrence") or 1),
                "artifact_role": str(provenance.get("artifact_role") or "other"),
                "relationship_direction": str(provenance.get("relationship_direction") or ""),
                "relationship_kinds": list(provenance.get("relationship_kinds") or ()),
            },
            defaults={"recurrence": 1, "artifact_role": "other"},
        )
        rendered.append(
            _without_empty_values({
                "observation_id": card.observation_id,
                "file_context_id": file_id,
                "owner_context_id": owner_id,
                "source_handle": _without_empty_values({
                    "line_start": card.handle.line_start,
                    "line_end": card.handle.line_end,
                    "full_line_start": card.handle.full_line_start,
                    "full_line_end": card.handle.full_line_end,
                    "node_id": card.handle.node_id,
                    "symbol": card.handle.symbol,
                }),
                "mode": card.mode,
                "source_text": "" if blank_source else card.source_text,
                "truncation_reason": card.truncation_reason,
                "navigation_context": navigation_context,
            }, preserve={"source_text"})
        )
    return {"request": user_request, "file_contexts": file_contexts, "observations": rendered}


def _without_empty_values(
    value: Mapping[str, Any],
    *,
    defaults: Mapping[str, Any] | None = None,
    preserve: set[str] | None = None,
) -> dict[str, Any]:
    default_values = defaults or {}
    preserved = preserve or set()
    return {
        key: item
        for key, item in value.items()
        if key in preserved
        or (
            item not in (None, "", 0, (), [], {})
            and item != default_values.get(key, object())
        )
    }


def _total_input_chars(prompt_text: str, response_format: Mapping[str, Any], payload: Mapping[str, Any]) -> int:
    return len(prompt_text) + len(json.dumps(response_format, sort_keys=True)) + len(json.dumps(payload, sort_keys=True)) + INPUT_SAFETY_RESERVE_CHARS


def _validate_decisions(response: Mapping[str, Any], ids: Sequence[str]) -> tuple[QualificationDecision, ...]:
    raw = response.get("decisions")
    if not isinstance(raw, Mapping):
        raise RuntimeError("qualification_response_invalid: decisions must be an object keyed by observation ID")
    expected = set(ids)
    received = {str(value) for value in raw}
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
                "$defs": {"decision": decision_schema},
                "properties": {
                    "decisions": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            observation_id: {"$ref": "#/$defs/decision"}
                            for observation_id in ids
                        },
                        "required": list(ids),
                    }
                },
                "required": ["decisions"],
            },
        },
    }
