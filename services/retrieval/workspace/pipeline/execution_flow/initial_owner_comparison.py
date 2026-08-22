from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from services.llm.json_completion import complete_json
from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import (
    DiscoveryObservation,
    DiscoveryProvenance,
)


PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "initial_owner_comparison.md"
MAX_SOURCE_VIEW_CHARS = 80
_ALL_FILE_OBLIGATIONS = "*"
_STRUCTURAL_OWNER_KINDS = {
    "class",
    "constructor",
    "enum",
    "function",
    "interface",
    "method",
    "type",
}
_TOP_LEVEL_VALUE_KINDS = {"constant", "variable"}


@dataclass(frozen=True)
class InitialOwnerComparison:
    selected: tuple[DiscoveryObservation, ...]
    dormant: tuple[DiscoveryObservation, ...]
    usage: Mapping[str, int]
    serialized_chars: int
    compared_group_count: int
    auto_selected_group_count: int
    selected_by_group: Mapping[str, tuple[str, ...]]


def select_range_candidate_owners(
    nodes: Sequence[Mapping[str, Any]],
    *,
    line_start: int,
    line_end: int,
) -> tuple[dict[str, Any], ...]:
    """Return distinct structural owners crossing one retrieved range.

    A containing class or outer callable is attached as context instead of
    competing with its narrower member. Source remains the original retrieved
    range here; complete-owner disclosure happens only after comparison.
    """
    overlapping = [dict(node) for node in nodes if _overlaps(node, line_start, line_end)]
    structural = [node for node in overlapping if _kind(node) in _STRUCTURAL_OWNER_KINDS]
    candidates = [
        node
        for node in structural
        if not any(_strictly_contains(node, other) for other in structural)
    ]
    candidates.extend(
        node
        for node in overlapping
        if _kind(node) in _TOP_LEVEL_VALUE_KINDS
        and not any(_strictly_contains(owner, node) for owner in structural)
    )
    if not candidates:
        candidates = overlapping

    rendered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in sorted(candidates, key=_node_order):
        identity = str(candidate.get("id") or "") or json.dumps(
            [candidate.get("path"), candidate.get("line_start"), candidate.get("line_end")]
        )
        if identity in seen:
            continue
        seen.add(identity)
        outers = [node for node in structural if _strictly_contains(node, candidate)]
        if outers:
            outer = min(outers, key=_span)
            candidate.update(
                {
                    "outer_node_id": str(outer.get("id") or ""),
                    "outer_symbol": str(outer.get("qualified_name") or outer.get("name") or ""),
                    "outer_line_start": int(outer.get("line_start") or 0),
                    "outer_line_end": int(outer.get("line_end") or 0),
                }
            )
        rendered.append(candidate)
    return tuple(rendered)


def compare_initial_owners(
    *,
    llm_config: Any,
    obligation_descriptions: Mapping[str, str],
    observations: Sequence[DiscoveryObservation],
    admitted_groups: Sequence[tuple[str, str]],
    max_input_chars: int,
    trace: Any | None = None,
) -> InitialOwnerComparison:
    """Choose structural owners inside already-admitted file/obligation groups.

    This stage does not qualify evidence. It only prevents channel order from
    silently choosing one owner before the normal qualification LLM sees it.
    """
    groups = _candidate_groups(observations, admitted_groups)
    auto_selected = {
        group_id: (values[0].id,)
        for group_id, values in groups.items()
        if len(values) == 1
    }
    compared = {group_id: values for group_id, values in groups.items() if len(values) > 1}
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    selected_by_group: dict[str, tuple[str, ...]] = dict(auto_selected)
    serialized_chars = 0

    if compared:
        payload, external_groups, group_aliases, owner_aliases = _payload(
            obligation_descriptions, compared
        )
        prompt_text = PROMPT_PATH.read_text(encoding="utf-8")
        response_format = _response_format(external_groups)
        serialized = json.dumps(payload, sort_keys=True)
        serialized_chars = len(serialized)
        schema_chars = len(json.dumps(response_format, sort_keys=True))
        total_input_chars = len(prompt_text) + schema_chars + serialized_chars
        preparation = {
            "compared_group_count": len(compared),
            "auto_selected_group_count": len(auto_selected),
            "candidate_count": len({item.id for values in compared.values() for item in values}),
            "serialized_chars": serialized_chars,
            "schema_chars": schema_chars,
            "prompt_chars": len(prompt_text),
            "total_input_chars": total_input_chars,
            "input_char_budget": max_input_chars,
        }
        if trace is not None:
            trace.record("initial_owner_comparison_prepared", preparation)
        if total_input_chars > max_input_chars:
            raise RuntimeError(
                "initial_owner_comparison_input_budget_exceeded:"
                f"{total_input_chars}>{max_input_chars}:"
                f"owners={preparation['candidate_count']}:groups={len(compared)}"
            )

        def log_event(event_type: str, value: Mapping[str, Any]) -> None:
            if event_type == "llm_response_received":
                raw = value.get("raw_response", {})
                raw_usage = raw.get("usage", {}) if isinstance(raw, Mapping) else {}
                if isinstance(raw_usage, Mapping):
                    for key in usage:
                        usage[key] += int(raw_usage.get(key, 0) or 0)
            if trace is not None:
                trace.record(event_type, {"stage": "initial_owner_comparison", **dict(value)})

        if trace is not None:
            trace.record(
                "initial_owner_comparison_requested",
                {
                    **preparation,
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
        external_selection = _validate_response(response, external_groups)
        selected_by_group.update(
            {
                group_aliases[group_id]: tuple(owner_aliases[owner_id] for owner_id in owner_ids)
                for group_id, owner_ids in external_selection.items()
            }
        )

    selected_group_keys = {
        group_id: _group_key(group_id)
        for group_id in groups
    }
    selected_groups_by_observation: dict[str, set[tuple[str, str]]] = {}
    for group_id, owner_ids in selected_by_group.items():
        for owner_id in owner_ids:
            selected_groups_by_observation.setdefault(owner_id, set()).add(selected_group_keys[group_id])

    participating_ids = {item.id for values in groups.values() for item in values}
    selected: list[DiscoveryObservation] = []
    dormant: list[DiscoveryObservation] = []
    for observation in observations:
        if observation.id not in participating_ids:
            continue
        chosen_groups = selected_groups_by_observation.get(observation.id, set())
        restricted = _restrict_to_groups(observation, chosen_groups)
        if restricted is not None:
            selected.append(restricted)
        else:
            dormant.append(observation)

    if trace is not None:
        trace.record(
            "initial_owner_comparison_created",
            {
                "selected_by_group": {key: list(value) for key, value in selected_by_group.items()},
                "selected_count": len(selected),
                "dormant_count": len(dormant),
                "dormant_owners": [_owner_trace(item) for item in dormant],
                "usage": dict(usage),
            },
        )
    return InitialOwnerComparison(
        selected=tuple(selected),
        dormant=tuple(dormant),
        usage=usage,
        serialized_chars=serialized_chars,
        compared_group_count=len(compared),
        auto_selected_group_count=len(auto_selected),
        selected_by_group=selected_by_group,
    )


def _candidate_groups(
    observations: Sequence[DiscoveryObservation],
    admitted_groups: Sequence[tuple[str, str]],
) -> dict[str, tuple[DiscoveryObservation, ...]]:
    admitted_paths = {path.casefold() for path, _obligation_id in admitted_groups}
    grouped: dict[tuple[str, str], list[DiscoveryObservation]] = {}
    for observation in observations:
        path = observation.handle.path.casefold()
        if path in admitted_paths:
            grouped.setdefault((path, _ALL_FILE_OBLIGATIONS), []).append(observation)
    rendered: dict[str, tuple[DiscoveryObservation, ...]] = {}
    for key, values in grouped.items():
        by_id: dict[str, DiscoveryObservation] = {}
        for item in values:
            by_id.setdefault(item.id, item)
        rendered[_group_id(key)] = tuple(by_id.values())
    return rendered


def _payload(
    obligation_descriptions: Mapping[str, str],
    groups: Mapping[str, Sequence[DiscoveryObservation]],
) -> tuple[dict[str, Any], dict[str, tuple[str, ...]], dict[str, str], dict[str, str]]:
    owner_alias_by_id: dict[str, str] = {}
    owner_id_by_alias: dict[str, str] = {}
    owners: dict[str, dict[str, Any]] = {}
    source_views: dict[str, dict[str, Any]] = {}
    source_view_alias_by_key: dict[tuple[str, int, int, str], str] = {}
    rendered_groups: list[dict[str, Any]] = []
    external_groups: dict[str, tuple[str, ...]] = {}
    group_id_by_alias: dict[str, str] = {}
    used_obligations: dict[str, str] = {}
    for group_index, (group_id, observations) in enumerate(groups.items(), start=1):
        path, obligation_id = _group_key(group_id)
        group_alias = f"g{group_index}"
        group_id_by_alias[group_alias] = group_id
        obligation_ids = tuple(dict.fromkeys(
            value
            for observation in observations
            for value in observation.obligation_ids
        ))
        for value in obligation_ids:
            used_obligations[value] = obligation_descriptions.get(value, "")
        owner_ids: list[str] = []
        for observation in observations:
            owner_alias = owner_alias_by_id.setdefault(observation.id, f"o{len(owner_alias_by_id) + 1}")
            owner_id_by_alias[owner_alias] = observation.id
            owner_ids.append(owner_alias)
            view_key = _source_view_key(observation)
            view_alias = source_view_alias_by_key.setdefault(view_key, f"v{len(source_view_alias_by_key) + 1}")
            if view_alias not in source_views:
                source_views[view_alias] = _source_view_payload(observation)
            owner = owners.setdefault(owner_alias, _owner_payload(observation))
            view_ids = owner["v"]
            if view_alias not in view_ids:
                view_ids.append(view_alias)
        external_groups[group_alias] = tuple(owner_ids)
        rendered_groups.append(
            {
                "id": group_alias,
                "obligations": list(obligation_ids),
                "owners": owner_ids,
            }
        )
    return (
        {
            "obligations": used_obligations,
            "views": source_views,
            "owners": owners,
            "groups": rendered_groups,
        },
        external_groups,
        group_id_by_alias,
        owner_id_by_alias,
    )


def _owner_payload(observation: DiscoveryObservation) -> dict[str, Any]:
    handle = observation.handle
    return {
        "s": handle.symbol,
        "u": handle.outer_symbol,
        "v": [],
        "c": list(observation.support_counts.values()),
        "r": observation.best_rank,
    }


def _source_view_key(observation: DiscoveryObservation) -> tuple[str, int, int, str]:
    handle = observation.handle
    return (
        handle.path.casefold(),
        handle.line_start,
        handle.line_end,
        observation.observed_text,
    )


def _source_view_payload(observation: DiscoveryObservation) -> dict[str, Any]:
    handle = observation.handle
    return {
        "p": handle.path,
        "r": [handle.line_start, handle.line_end],
        "x": _compact_source_view(observation.observed_text),
    }


def _compact_source_view(text: str) -> str:
    """Keep the executable repository lead ahead of labels and signatures.

    The compact comparison stage is allowed only a small source view. It must
    not let an owner-name assignment crowd out a visible call/return that can
    lead to another exact repository owner.
    """
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    executable = [
        line for line in lines
        if re.search(
            r"\b(?:return|yield|await)\b[^\n]*[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*\s*\("
            r"|\b[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)+\s*\(",
            line,
        )
    ]
    semantic = [
        line for line in lines
        if re.search(r"\b(class|def|function|operator|binary|add|update|build|watch|name)\b", line, re.I)
    ]
    chosen = list(dict.fromkeys((*executable[:2], *semantic[:1], *lines[:1])))
    rendered = "\n".join(chosen)
    if len(rendered) <= MAX_SOURCE_VIEW_CHARS:
        return rendered
    complete_lines: list[str] = []
    used = 0
    for line in chosen:
        additional = len(line) + (1 if complete_lines else 0)
        if complete_lines and used + additional > MAX_SOURCE_VIEW_CHARS:
            break
        if not complete_lines and len(line) > MAX_SOURCE_VIEW_CHARS:
            return line
        complete_lines.append(line)
        used += additional
    return "\n".join(complete_lines)


def _response_format(expected: Mapping[str, Sequence[str]]) -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "initial_owner_comparison",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "groups": {
                        "type": "object",
                        "properties": {
                            group_id: {
                                "type": "array",
                                "items": {"type": "string", "enum": list(owner_ids)},
                                "minItems": 1,
                            }
                            for group_id, owner_ids in expected.items()
                        },
                        "required": list(expected),
                        "additionalProperties": False,
                    }
                },
                "required": ["groups"],
                "additionalProperties": False,
            },
        },
    }


def _validate_response(
    response: Mapping[str, Any],
    expected: Mapping[str, Sequence[str]],
) -> dict[str, tuple[str, ...]]:
    rows = response.get("groups", {})
    if not isinstance(rows, Mapping):
        raise RuntimeError("initial_owner_comparison_invalid_response")
    parsed: dict[str, tuple[str, ...]] = {}
    for raw_group_id, raw_selected in rows.items():
        group_id = str(raw_group_id)
        if group_id not in expected or group_id in parsed:
            raise RuntimeError(f"initial_owner_comparison_unknown_group:{group_id}")
        allowed = set(expected[group_id])
        if not isinstance(raw_selected, Sequence) or isinstance(raw_selected, (str, bytes)):
            raise RuntimeError(f"initial_owner_comparison_invalid_selection:{group_id}")
        selected = tuple(dict.fromkeys(str(value) for value in raw_selected if value))
        if not selected or any(value not in allowed for value in selected):
            raise RuntimeError(f"initial_owner_comparison_invalid_selection:{group_id}")
        parsed[group_id] = selected
    missing = set(expected) - set(parsed)
    if missing:
        raise RuntimeError(f"initial_owner_comparison_missing_groups:{','.join(sorted(missing))}")
    return parsed


def _restrict_to_groups(
    observation: DiscoveryObservation,
    groups: set[tuple[str, str]],
) -> DiscoveryObservation | None:
    if not groups:
        return None
    path = observation.handle.path.casefold()
    if (path, _ALL_FILE_OBLIGATIONS) in groups:
        return observation
    provenance: list[DiscoveryProvenance] = []
    for item in observation.provenance:
        obligation_ids = tuple(
            obligation_id for obligation_id in item.obligation_ids
            if (path, obligation_id) in groups
        )
        if obligation_ids:
            provenance.append(replace(item, obligation_ids=obligation_ids))
    return replace(observation, provenance=tuple(provenance)) if provenance else None


def _owner_trace(observation: DiscoveryObservation) -> dict[str, Any]:
    return {
        "observation_id": observation.id,
        "path": observation.handle.path,
        "node_id": observation.handle.node_id,
        "symbol": observation.handle.symbol,
        "line_start": observation.handle.line_start,
        "line_end": observation.handle.line_end,
        "obligation_ids": list(observation.obligation_ids),
        "support": observation.support_counts,
    }


def _group_id(key: tuple[str, str]) -> str:
    return json.dumps(key, separators=(",", ":"))


def _group_key(group_id: str) -> tuple[str, str]:
    value = json.loads(group_id)
    if not isinstance(value, list) or len(value) != 2:
        raise RuntimeError(f"initial_owner_comparison_invalid_group_id:{group_id}")
    return str(value[0]), str(value[1])


def _input_chars(prompt: str, response_format: Mapping[str, Any], serialized_payload: str) -> int:
    return len(prompt) + len(json.dumps(response_format, sort_keys=True)) + len(serialized_payload)


def _kind(node: Mapping[str, Any]) -> str:
    return str(node.get("kind") or "").casefold()


def _node_range(node: Mapping[str, Any]) -> tuple[int, int]:
    start = int(node.get("line_start") or 0)
    return start, max(start, int(node.get("line_end") or start))


def _span(node: Mapping[str, Any]) -> int:
    start, end = _node_range(node)
    return max(0, end - start)


def _overlaps(node: Mapping[str, Any], line_start: int, line_end: int) -> bool:
    start, end = _node_range(node)
    return start > 0 and start <= line_end and end >= line_start


def _strictly_contains(outer: Mapping[str, Any], inner: Mapping[str, Any]) -> bool:
    if str(outer.get("id") or "") == str(inner.get("id") or ""):
        return False
    outer_start, outer_end = _node_range(outer)
    inner_start, inner_end = _node_range(inner)
    return (
        outer_start > 0
        and outer_start <= inner_start
        and outer_end >= inner_end
        and (outer_start, outer_end) != (inner_start, inner_end)
    )


def _node_order(node: Mapping[str, Any]) -> tuple[int, int, str]:
    start, end = _node_range(node)
    return start, end, str(node.get("id") or "")
