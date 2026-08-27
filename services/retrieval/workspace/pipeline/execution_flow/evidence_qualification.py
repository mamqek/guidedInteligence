from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
import hashlib
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
    local_follow_up: str = ""
    supported_obligation_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class QualificationReuseCache:
    """Run-local validated judgments, independent of retrieval recurrence and batch aliases."""

    def __init__(self) -> None:
        self.entries: dict[tuple[str, str], tuple[QualificationDecision, int]] = {}
        self.proofs: dict[tuple[str, str], tuple[QualificationDecision, int, DisclosureCard]] = {}

    @classmethod
    def proof_context(cls, payload: Mapping[str, Any], observation: Mapping[str, Any], *,
                      card: DisclosureCard, prompt_text: str, model_context: Mapping[str, Any]) -> str:
        # Ignore presentation only. Full backing and stable owner location still participate.
        item = dict(observation)
        for field in ("mode", "source_text", "truncation_reason"):
            item.pop(field, None)
        return cls.fingerprint(payload, {**item, "backing_source": card.complete_source_text},
                               prompt_text=prompt_text, model_context=model_context)

    @staticmethod
    def is_crop_of(card: DisclosureCard, proof: DisclosureCard) -> bool:
        if not card.complete_source_text or card.complete_source_text != proof.complete_source_text:
            return False
        # Omission markers do not constitute new source. Preserve line order, including duplicates.
        lines = [line for line in card.source_text.splitlines()
                 if line.strip() and "complete source lines omitted" not in line]
        original = iter(proof.source_text.splitlines())
        return bool(lines) and all(any(line == old for old in original) for line in lines)

    @staticmethod
    def fingerprint(payload: Mapping[str, Any], observation: Mapping[str, Any], *,
                    prompt_text: str, model_context: Mapping[str, Any]) -> str:
        # Resolve shared aliases; a different batch position is not a semantic change.
        item = dict(observation)
        context = payload["file_contexts"][item.pop("file_context_id")]
        owner = context["relevant_owners"][item.pop("owner_context_id")]
        item.pop("observation_id", None)
        navigation = item.pop("navigation_context", {})
        handle = dict(item.get("source_handle", {}))
        if item.get("mode") == "full" and handle.get("full_line_start") and handle.get("full_line_end"):
            # The hit window may move on rediscovery; full-body identity/location
            # is already defined by full bounds, owner context and exact text.
            handle.pop("line_start", None)
            handle.pop("line_end", None)
            item["source_handle"] = handle
        semantic = {
            "request": payload["request"], "obligations": payload["obligations"],
            "path": context["path"], "owner": owner, "source": item,
            "artifact_role": navigation.get("artifact_role", "other"),
            "prompt": prompt_text, "model_context": dict(model_context),
        }
        return hashlib.sha256(json.dumps(semantic, sort_keys=True).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class QualificationBatch:
    decisions: tuple[QualificationDecision, ...]
    usage: Mapping[str, int]
    serialized_chars: int
    cards: tuple[DisclosureCard, ...] = ()
    input_chars: int = 0
    source_capacity: int = 0


@dataclass(frozen=True)
class QualificationPreparation:
    cards: tuple[DisclosureCard, ...]
    payload: Mapping[str, Any]
    serialized_chars: int
    input_chars: int
    fixed_input_chars: int
    source_capacity: int


def prepare_qualification_request(
    *,
    user_request: str,
    cards: Sequence[DisclosureCard],
    max_input_chars: int,
    obligations: Sequence[Any] = (),
) -> QualificationPreparation:
    """Build the exact bounded request that qualification would receive.

    This is used by the explicit pre-qualification diagnostic mode.  It does
    not call an LLM and therefore cannot be mistaken for a qualification
    decision or a deterministic substitute for one.
    """
    if not cards:
        return QualificationPreparation((), {}, 0, 0, 0, 0)
    prompt_text = PROMPT_PATH.read_text(encoding="utf-8")
    ids = tuple(card.observation_id for card in cards)
    payload, bounded_cards, budget = _bounded_payload(
        user_request,
        cards,
        obligations=obligations,
        max_input_chars=max_input_chars,
        prompt_text=prompt_text,
        response_format=_response_format(ids),
    )
    serialized = json.dumps(payload, sort_keys=True)
    return QualificationPreparation(
        cards=bounded_cards,
        payload=payload,
        serialized_chars=len(serialized),
        input_chars=budget["total_input_chars"],
        fixed_input_chars=budget["fixed_input_chars"],
        source_capacity=budget["source_capacity"],
    )


def qualify_cards(
    *,
    llm_config: Any,
    user_request: str,
    cards: Sequence[DisclosureCard],
    max_input_chars: int,
    obligations: Sequence[Any] = (),
    trace: Any | None = None,
    round_index: int = 0,
    reuse_cache: QualificationReuseCache | None = None,
) -> QualificationBatch:
    if not cards:
        return QualificationBatch(decisions=(), usage={}, serialized_chars=0)
    prompt_text = PROMPT_PATH.read_text(encoding="utf-8")
    return _qualify_card_batch(
        llm_config=llm_config,
        user_request=user_request,
        cards=cards,
        obligations=obligations,
        max_input_chars=max_input_chars,
        prompt_text=prompt_text,
        trace=trace,
        round_index=round_index,
        reuse_cache=reuse_cache,
    )


def _qualify_card_batch(
    *, llm_config: Any, user_request: str, cards: Sequence[DisclosureCard], max_input_chars: int,
    obligations: Sequence[Any], prompt_text: str, trace: Any | None, round_index: int,
    reuse_cache: QualificationReuseCache | None = None,
) -> QualificationBatch:
    ids = tuple(card.observation_id for card in cards)
    response_format = _response_format(ids)
    payload, bounded_cards, budget = _bounded_payload(
        user_request, cards, obligations=obligations, max_input_chars=max_input_chars,
        prompt_text=prompt_text, response_format=response_format,
    )
    all_cards = bounded_cards
    reused: dict[str, QualificationDecision] = {}
    fingerprints: dict[str, str] = {}
    proof_keys: dict[str, str] = {}
    # Hidden continuity messages can change semantic context outside this stage.
    if reuse_cache is not None and not getattr(llm_config, "continuity_enabled", False):
        model_context = {key: getattr(llm_config, key, None) for key in
                         ("api_style", "model", "endpoint_url", "temperature")}
        cards_by_id = {card.observation_id: card for card in all_cards}
        for item in payload["observations"]:
            observation_id = item["observation_id"]
            card = cards_by_id[observation_id]
            fingerprint = reuse_cache.fingerprint(
                payload, {**item, "backing_source": card.complete_source_text},
                prompt_text=prompt_text, model_context=model_context,
            )
            fingerprints[observation_id] = fingerprint
            entry = reuse_cache.entries.get((observation_id, fingerprint))
            proof_key = reuse_cache.proof_context(payload, item, card=card,
                                                 prompt_text=prompt_text, model_context=model_context)
            proof_keys[observation_id] = proof_key
            proof = reuse_cache.proofs.get((observation_id, proof_key))
            reason = "unchanged_direct_proof" if entry is not None else "no_reusable_direct_proof"
            if entry is None and proof is not None and reuse_cache.is_crop_of(card, proof[2]):
                entry = (proof[0], proof[1])
                cards_by_id[observation_id] = replace(proof[2], provenance_summary=card.provenance_summary)
                reason = "retained_prior_direct_source_over_crop"
            if entry is not None:
                reused[observation_id] = entry[0]
            if trace is not None:
                trace.record("qualification_reuse_evaluated", {
                    "round": round_index, "observation_id": observation_id,
                    "fingerprint": fingerprint, "reused": entry is not None,
                    "source_chars": len(item["source_text"]),
                    "retained_source_chars": len(cards_by_id[observation_id].source_text),
                    "previous_round": entry[1] if entry is not None else None,
                    "decision": entry[0].to_dict() if entry is not None else None,
                    "reason": reason,
                })
        all_cards = tuple(cards_by_id[card.observation_id] for card in all_cards)
        bounded_cards = tuple(card for card in all_cards if card.observation_id not in reused)
        ids = tuple(card.observation_id for card in bounded_cards)
        response_format = _response_format(ids)
        # Do not redistribute freed source capacity: retain the exact fitted source.
        payload = _payload(user_request, bounded_cards, obligations=obligations)
        budget["total_input_chars"] = _total_input_chars(prompt_text, response_format, payload)
        budget["fixed_input_chars"] = _total_input_chars(
            prompt_text, response_format,
            _payload(user_request, bounded_cards, obligations=obligations, blank_source=True),
        )
    if not bounded_cards:
        return QualificationBatch(tuple(reused[card.observation_id] for card in all_cards),
                                  {}, 0, all_cards, 0, budget["source_capacity"])
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
    known_obligation_ids = tuple(
        str(getattr(item, "id", ""))
        for item in obligations
        if str(getattr(item, "id", ""))
    )
    allowed_obligations = {
        card.observation_id: known_obligation_ids
        for card in bounded_cards
    }
    decisions = _validate_decisions(response, ids, allowed_obligations)
    if reuse_cache is not None:
        for decision in decisions:
            fingerprint = fingerprints.get(decision.observation_id)
            if fingerprint is not None and decision.support_level == "direct_evidence":
                reuse_cache.entries[(decision.observation_id, fingerprint)] = (decision, round_index)
                card = next(card for card in all_cards if card.observation_id == decision.observation_id)
                reuse_cache.proofs[(decision.observation_id, proof_keys[decision.observation_id])] = (
                    decision, round_index, card,
                )
    if trace is not None:
        trace.record(
            "qualification_decisions_created",
            {"round": round_index, "decisions": [item.to_dict() for item in decisions], "usage": dict(usage)},
        )
    combined = {**reused, **{item.observation_id: item for item in decisions}}
    return QualificationBatch(tuple(combined[card.observation_id] for card in all_cards), usage, len(serialized), all_cards,
                              budget["total_input_chars"], budget["source_capacity"])


def _bounded_payload(
    user_request: str,
    cards: Sequence[DisclosureCard],
    *,
    obligations: Sequence[Any] = (),
    max_input_chars: int,
    prompt_text: str | None = None,
    response_format: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], tuple[DisclosureCard, ...], dict[str, int]]:
    ids = tuple(card.observation_id for card in cards)
    system_prompt = prompt_text if prompt_text is not None else PROMPT_PATH.read_text(encoding="utf-8")
    schema = dict(response_format or _response_format(ids))
    prepared = tuple(cards)

    def fixed_input_chars(values: Sequence[DisclosureCard]) -> int:
        return _total_input_chars(
            system_prompt,
            schema,
            _payload(user_request, values, obligations=obligations, blank_source=True),
        )

    fixed = fixed_input_chars(prepared)
    if fixed > max_input_chars:
        raise RuntimeError("qualification_input_budget_too_small_for_metadata")
    source_capacity = max(0, max_input_chars - fixed)
    bounded = fit_cards_to_source_capacity(prepared, source_capacity=source_capacity)
    payload = _payload(user_request, bounded, obligations=obligations)
    total = _total_input_chars(system_prompt, schema, payload)
    while total > max_input_chars and source_capacity > 0:
        source_capacity = max(0, source_capacity - (total - max_input_chars))
        bounded = fit_cards_to_source_capacity(prepared, source_capacity=source_capacity)
        payload = _payload(user_request, bounded, obligations=obligations)
        total = _total_input_chars(system_prompt, schema, payload)
    if total > max_input_chars:
        raise RuntimeError("qualification_input_budget_too_small_for_metadata")
    return payload, bounded, {"fixed_input_chars": fixed, "source_capacity": source_capacity, "total_input_chars": total}


def _payload(
    user_request: str,
    cards: Sequence[DisclosureCard],
    *,
    obligations: Sequence[Any] = (),
    blank_source: bool = False,
) -> dict[str, Any]:
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
    rendered_obligations = [
        {
            "obligation_id": str(getattr(item, "id", "")),
            "description": str(getattr(item, "description", "")),
            "evidence_role": str(getattr(getattr(item, "evidence_role", ""), "value", getattr(item, "evidence_role", ""))),
        }
        for item in obligations
        if str(getattr(item, "id", ""))
    ]
    return {
        "request": user_request,
        "obligations": rendered_obligations,
        "file_contexts": file_contexts,
        "observations": rendered,
    }


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


def _validate_decisions(
    response: Mapping[str, Any],
    ids: Sequence[str],
    allowed_obligations: Mapping[str, Sequence[str]] | None = None,
) -> tuple[QualificationDecision, ...]:
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
        supported_obligation_ids = _strings(value.get("supported_obligation_ids"), limit=12)
        allowed = set((allowed_obligations or {}).get(observation_id, ()))
        unknown_obligations = set(supported_obligation_ids) - allowed
        if unknown_obligations:
            raise RuntimeError(
                "qualification_response_invalid: unsupported obligation IDs for "
                f"{observation_id}: {sorted(unknown_obligations)}"
            )
        if support_level == "direct_evidence" and not supported_obligation_ids:
            raise RuntimeError(
                f"qualification_response_invalid: direct evidence lacks supported obligations for {observation_id}"
            )
        decisions.append(
            QualificationDecision(
                observation_id=observation_id,
                disposition=disposition,
                support_level=support_level,
                reason=reason,
                visible_support=visible_support,
                missing_information=_strings(value.get("missing_information"), limit=6),
                local_follow_up=str(value.get("local_follow_up") or "").strip()[:500],
                supported_obligation_ids=supported_obligation_ids,
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
            "local_follow_up": {"type": "string"},
            "supported_obligation_ids": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "classification",
            "reason",
            "visible_support",
            "missing_information",
            "local_follow_up",
            "supported_obligation_ids",
        ],
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
