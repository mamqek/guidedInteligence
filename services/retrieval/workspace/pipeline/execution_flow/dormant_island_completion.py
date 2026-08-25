from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence

from services.llm.json_completion import complete_json
from services.retrieval.workspace.pipeline.execution_flow.coverage_evaluation import ObligationCoverage
from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import DiscoveryObservation
from services.retrieval.workspace.pipeline.execution_flow.evidence_qualification import (
    CLASSIFICATION_TO_DECISION,
    QualificationDecision,
)
from services.retrieval.workspace.pipeline.execution_flow.source_disclosure import (
    DisclosureCard,
    fit_cards_to_source_capacity,
)
from services.retrieval.workspace.tools import ToolRequest


PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "dormant_island_completion.md"
INPUT_SAFETY_RESERVE_CHARS = 512
MAX_COMPLETIONS_PER_ISLAND = 2


def announce_dormant_completion_llm_call(
    *,
    round_index: int,
    source_observation_id: str,
    target_observation_id: str,
    relationship_kind: str,
) -> None:
    """Make the experiment's extra model cost visible in normal process output."""

    print(
        "[DORMANT-ISLAND-COMPLETION] EXTRA LLM CALL "
        f"round={round_index} source={source_observation_id} "
        f"target={target_observation_id} relationship={relationship_kind}",
        file=sys.stderr,
        flush=True,
    )


def announce_dormant_completion_promotion(
    *,
    round_index: int,
    source_observation_id: str,
    target_observation_id: str,
    support_level: str,
) -> None:
    """Make an experiment-created evidence promotion visible to operators."""

    print(
        "[DORMANT-ISLAND-COMPLETION] EXTRA PROMOTION "
        f"round={round_index} source={source_observation_id} "
        f"target={target_observation_id} support={support_level}",
        file=sys.stderr,
        flush=True,
    )


@dataclass(frozen=True)
class DormantCompletionSelection:
    source_observation_id: str
    target: DiscoveryObservation
    island_id: str
    relationship_kind: str
    matched_name: str


@dataclass(frozen=True)
class DormantCompletionAudit:
    selections: tuple[DormantCompletionSelection, ...]
    rejected: tuple[dict[str, str], ...]
    tool_calls: int


def select_dormant_island_completions(
    *,
    matured_observation_ids: Sequence[str],
    observations: Mapping[str, DiscoveryObservation],
    decisions: Mapping[str, QualificationDecision],
    completion_candidate_ids: set[str],
    attempted_target_ids: set[str],
    successful_source_ids: Sequence[str],
    observation_to_island: Mapping[str, str],
    coverage: Sequence[ObligationCoverage],
    source_calls_tool: Any | None = None,
    exact_symbol_tool: Any | None = None,
    trace: Any | None = None,
    round_index: int = 0,
) -> DormantCompletionAudit:
    """Choose at most one exact dormant owner for each new maturation result.

    This is intentionally stricter than ordinary same-file rescue. A candidate
    must already have been structurally resolved during initial owner
    comparison and be explicitly named by the matured source's
    missing-information decision. Same-file membership alone never qualifies
    it, and dormant candidates do not enter ordinary scheduling.
    """

    unresolved = {
        item.obligation_id
        for item in coverage
        if item.status not in {"covered", "external"}
    }
    successes_by_island: dict[str, int] = {}
    for source_id in successful_source_ids:
        island_id = _source_island(source_id, observations, observation_to_island)
        if island_id:
            successes_by_island[island_id] = successes_by_island.get(island_id, 0) + 1

    dormant = [
        observations[item_id]
        for item_id in sorted(completion_candidate_ids)
        if item_id in observations and item_id not in attempted_target_ids and item_id not in decisions
    ]
    selections: list[DormantCompletionSelection] = []
    rejected: list[dict[str, str]] = []
    tool_calls = 0

    for source_id in dict.fromkeys(matured_observation_ids):
        source = observations.get(source_id)
        decision = decisions.get(source_id)
        island_id = _source_island(source_id, observations, observation_to_island)
        if source is None or decision is None or decision.disposition != "promote":
            rejected.append({"source_observation_id": source_id, "reason": "source_not_promoted"})
            continue
        if not island_id:
            rejected.append({"source_observation_id": source_id, "reason": "source_not_in_island"})
            continue
        if successes_by_island.get(island_id, 0) >= MAX_COMPLETIONS_PER_ISLAND:
            rejected.append({"source_observation_id": source_id, "reason": "island_completion_cap_reached"})
            continue
        missing_text = " ".join((decision.local_follow_up, *decision.missing_information)).strip()
        if not missing_text:
            rejected.append({"source_observation_id": source_id, "reason": "no_specific_missing_information"})
            continue

        ranked: list[tuple[int, int, int, str, DormantCompletionSelection]] = []
        for target in dormant:
            if target.handle.path.casefold() != source.handle.path.casefold():
                continue
            shared = set(source.obligation_ids) & set(target.obligation_ids) & unresolved
            if not shared:
                continue
            leaf = _leaf_symbol(target.handle.symbol)
            if not leaf:
                continue
            relationship_kind = _nested_relationship(source, target)
            name_match_count = _identifier_match_count(missing_text, leaf)
            if not name_match_count and relationship_kind == "contains":
                name_match_count = _terminal_symbol_match_count(missing_text, leaf)
            if not name_match_count:
                continue
            relation_tool_calls = 0
            if not relationship_kind and source_calls_tool is not None and exact_symbol_tool is not None:
                relationship_kind, relation_tool_calls = _verified_call_relationship(
                    source,
                    target,
                    source_calls_tool=source_calls_tool,
                    exact_symbol_tool=exact_symbol_tool,
                    trace=trace,
                    round_index=round_index,
                )
            tool_calls += relation_tool_calls
            if not relationship_kind:
                continue
            ranked.append((
                0 if relationship_kind == "contains" else 1,
                -name_match_count,
                target.best_rank,
                target.id,
                DormantCompletionSelection(source_id, target, island_id, relationship_kind, leaf),
            ))
        if ranked:
            selections.append(min(ranked)[-1])

    return DormantCompletionAudit(tuple(selections), tuple(rejected), tool_calls)


def completion_observation(selection: DormantCompletionSelection) -> DiscoveryObservation:
    """Attach honest structural provenance without claiming semantic support."""

    target = selection.target
    return replace(
        target,
        parent_observation_ids=tuple(dict.fromkeys((*target.parent_observation_ids, selection.source_observation_id))),
        relationship_direction="outgoing",
        relationship_kinds=(selection.relationship_kind,),
        admission_reason="dormant_island_completion",
    )


def qualify_dormant_island_completion(
    *,
    llm_config: Any,
    user_request: str,
    source_card: DisclosureCard,
    target_card: DisclosureCard,
    source_decision: QualificationDecision,
    relationship_kind: str,
    max_input_chars: int,
    trace: Any | None = None,
    round_index: int = 0,
) -> tuple[QualificationDecision, Mapping[str, int], tuple[DisclosureCard, DisclosureCard]]:
    """Qualify the dormant target with its already-promoted source as context."""

    prompt_text = PROMPT_PATH.read_text(encoding="utf-8")
    response_format = _response_format()
    fixed_payload = _payload(
        user_request,
        source_card,
        target_card,
        source_decision,
        relationship_kind,
        blank_source=True,
    )
    fixed_chars = len(prompt_text) + len(json.dumps(response_format, sort_keys=True)) + len(json.dumps(fixed_payload, sort_keys=True)) + INPUT_SAFETY_RESERVE_CHARS
    if fixed_chars > max_input_chars:
        raise RuntimeError("dormant_island_completion_input_budget_too_small_for_metadata")
    bounded = fit_cards_to_source_capacity(
        (source_card, target_card),
        source_capacity=max_input_chars - fixed_chars,
    )
    payload = _payload(
        user_request,
        bounded[0],
        bounded[1],
        source_decision,
        relationship_kind,
    )
    serialized = json.dumps(payload, sort_keys=True)
    total_chars = len(prompt_text) + len(json.dumps(response_format, sort_keys=True)) + len(serialized) + INPUT_SAFETY_RESERVE_CHARS
    if total_chars > max_input_chars:
        raise RuntimeError("dormant_island_completion_input_budget_exceeded")
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def log_event(event_type: str, value: Mapping[str, Any]) -> None:
        if event_type == "llm_response_received":
            raw = value.get("raw_response", {})
            raw_usage = raw.get("usage", {}) if isinstance(raw, Mapping) else {}
            if isinstance(raw_usage, Mapping):
                for key in usage:
                    usage[key] += int(raw_usage.get(key, 0) or 0)
        if trace is not None:
            trace.record(event_type, {"stage": "dormant_island_completion", "round": round_index, **dict(value)})

    if trace is not None:
        trace.record(
            "dormant_island_completion_requested",
            {
                "round": round_index,
                "source_observation_id": source_card.observation_id,
                "target_observation_id": target_card.observation_id,
                "relationship_kind": relationship_kind,
                "serialized_chars": len(serialized),
                "total_input_chars": total_chars,
                "prompt": str(PROMPT_PATH),
            },
        )
    announce_dormant_completion_llm_call(
        round_index=round_index,
        source_observation_id=source_card.observation_id,
        target_observation_id=target_card.observation_id,
        relationship_kind=relationship_kind,
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
    decision = _decision(response, target_card.observation_id)
    if trace is not None:
        trace.record(
            "dormant_island_completion_decision_created",
            {"round": round_index, "decision": decision.to_dict(), "usage": dict(usage)},
        )
    return decision, usage, (bounded[0], bounded[1])


def _nested_relationship(source: DiscoveryObservation, target: DiscoveryObservation) -> str:
    source_start = source.handle.full_line_start or source.handle.line_start
    source_end = source.handle.full_line_end or source.handle.line_end
    target_start = target.handle.full_line_start or target.handle.line_start
    target_end = target.handle.full_line_end or target.handle.line_end
    if (
        source.handle.node_id
        and target.handle.node_id
        and source.handle.node_id != target.handle.node_id
        and source_start <= target_start <= target_end <= source_end
        and target.handle.symbol.startswith(f"{source.handle.symbol}::")
    ):
        return "contains"
    return ""


def _source_island(
    source_id: str,
    observations: Mapping[str, DiscoveryObservation],
    observation_to_island: Mapping[str, str],
) -> str:
    """Resolve a maturation result back to the island that produced it.

    Owner continuations normally reuse the original observation ID. Other
    maturation executors may return a child observation, so follow only the
    explicit parent chain rather than guessing from a shared file.
    """

    pending = [source_id]
    seen: set[str] = set()
    while pending:
        observation_id = pending.pop(0)
        if observation_id in seen:
            continue
        seen.add(observation_id)
        island_id = observation_to_island.get(observation_id, "")
        if island_id:
            return island_id
        observation = observations.get(observation_id)
        if observation is not None:
            pending.extend(observation.parent_observation_ids)
    return ""


def _verified_call_relationship(
    source: DiscoveryObservation,
    target: DiscoveryObservation,
    *,
    source_calls_tool: Any,
    exact_symbol_tool: Any,
    trace: Any | None,
    round_index: int,
) -> tuple[str, int]:
    leaf = _leaf_symbol(target.handle.symbol)
    if not source.handle.node_id or not target.handle.node_id or not leaf:
        return "", 0
    source_node = _node_payload(source)
    call_request = ToolRequest(
        tool_name="structural_source_owner_calls",
        arguments={"node": source_node},
        reason="Verify one dormant same-file completion call from a matured owner.",
    )
    call_response = source_calls_tool.run(call_request)
    if trace is not None:
        trace.record_tool(call_request, call_response, round_index=round_index)
    if call_response.status != "ok" or not any(
        str(item.get("name") or "") == leaf
        for item in call_response.payload.get("calls", ())
        if isinstance(item, Mapping)
    ):
        return "", 1
    exact_request = ToolRequest(
        tool_name="structural_find_exact_symbol",
        arguments={"query": leaf},
        reason="Confirm the dormant completion call resolves to its retained CodeGraph owner.",
    )
    exact_response = exact_symbol_tool.run(exact_request)
    if trace is not None:
        trace.record_tool(exact_request, exact_response, round_index=round_index)
    matches = [
        item
        for item in exact_response.payload.get("nodes", ())
        if isinstance(item, Mapping)
        and str(item.get("id") or "") == target.handle.node_id
        and str(item.get("path") or "").casefold() == target.handle.path.casefold()
    ] if exact_response.status == "ok" else []
    return ("calls" if len(matches) == 1 else ""), 2


def _node_payload(observation: DiscoveryObservation) -> dict[str, Any]:
    handle = observation.handle
    return {
        "id": handle.node_id,
        "kind": handle.node_id.partition(":")[0],
        "language": handle.language,
        "line_start": handle.full_line_start or handle.line_start,
        "line_end": handle.full_line_end or handle.line_end,
        "name": _leaf_symbol(handle.symbol),
        "qualified_name": handle.symbol,
        "path": handle.path,
    }


def _leaf_symbol(symbol: str) -> str:
    return symbol.rsplit("::", 1)[-1].strip()


def _mentions_identifier(text: str, identifier: str) -> bool:
    return bool(_identifier_match_count(text, identifier))


def _identifier_match_count(text: str, identifier: str) -> int:
    return len(re.findall(rf"(?<![A-Za-z0-9_$]){re.escape(identifier)}(?![A-Za-z0-9_$])", text, re.IGNORECASE))


def _terminal_symbol_match_count(text: str, identifier: str) -> int:
    """Match a nested helper's descriptive terminal word, including plural.

    Qualification often asks for "the scenarios" rather than repeating the
    exact helper spelling `verifyScenario`. This relaxation applies only after
    an exact containment relationship is proven; callees still require their
    complete repository identifier.
    """

    parts = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|[0-9]+", identifier)
    terminal = parts[-1].casefold() if parts else ""
    if len(terminal) < 5:
        return 0
    return len(re.findall(rf"(?<![A-Za-z0-9_$]){re.escape(terminal)}s?(?![A-Za-z0-9_$])", text, re.IGNORECASE))


def _payload(
    user_request: str,
    source_card: DisclosureCard,
    target_card: DisclosureCard,
    source_decision: QualificationDecision,
    relationship_kind: str,
    *,
    blank_source: bool = False,
) -> dict[str, Any]:
    def card(value: DisclosureCard) -> dict[str, Any]:
        return {
            "observation_id": value.observation_id,
            "path": value.handle.path,
            "symbol": value.handle.symbol,
            "line_start": value.handle.line_start,
            "line_end": value.handle.line_end,
            "mode": value.mode,
            "source_text": "" if blank_source else value.source_text,
            "truncation_reason": value.truncation_reason,
        }

    return {
        "request": user_request,
        "relationship_kind": relationship_kind,
        "promoted_source": card(source_card),
        "source_missing_information": list(source_decision.missing_information),
        "source_local_follow_up": source_decision.local_follow_up,
        "dormant_candidate": card(target_card),
    }


def _response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "dormant_island_completion",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "classification": {"type": "string", "enum": list(CLASSIFICATION_TO_DECISION)},
                    "reason": {"type": "string"},
                    "visible_support": {"type": "array", "items": {"type": "string"}},
                    "missing_information": {"type": "array", "items": {"type": "string"}},
                    "local_follow_up": {"type": "string"},
                },
                "required": ["classification", "reason", "visible_support", "missing_information", "local_follow_up"],
                "additionalProperties": False,
            },
        },
    }


def _decision(response: Mapping[str, Any], observation_id: str) -> QualificationDecision:
    classification = str(response.get("classification") or "")
    if classification not in CLASSIFICATION_TO_DECISION:
        raise RuntimeError("dormant_island_completion_invalid_response")
    disposition, support = CLASSIFICATION_TO_DECISION[classification]
    return QualificationDecision(
        observation_id=observation_id,
        disposition=disposition,
        support_level=support,
        reason=str(response.get("reason") or "").strip(),
        visible_support=tuple(str(item) for item in response.get("visible_support", ()) if str(item)),
        missing_information=tuple(str(item) for item in response.get("missing_information", ()) if str(item)),
        local_follow_up=str(response.get("local_follow_up") or "").strip(),
    )
