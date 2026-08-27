from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
import re
from types import SimpleNamespace
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


@dataclass(frozen=True)
class InitialOwnerComparisonAdmission:
    admitted_groups: tuple[tuple[str, str], ...]
    admitted_paths: tuple[str, ...]
    excluded_paths: tuple[str, ...]
    total_input_chars: int
    candidate_count: int
    stopping_reason: str
    stopped_at_path: str
    path_decisions: tuple[dict[str, object], ...]


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
    max_selected: int | None = None,
    trace: Any | None = None,
) -> InitialOwnerComparison:
    """Choose structural owners inside already-admitted file/obligation groups.

    This stage does not qualify evidence. It only prevents channel order from
    silently choosing one owner before the normal qualification LLM sees it.
    """
    groups = _candidate_groups(observations, admitted_groups)
    global_selection = max_selected is not None
    auto_selected = {} if global_selection else {
        group_id: (values[0].id,)
        for group_id, values in groups.items()
        if len(values) == 1
    }
    compared = dict(groups) if global_selection else {
        group_id: values for group_id, values in groups.items() if len(values) > 1
    }
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    selected_by_group: dict[str, tuple[str, ...]] = dict(auto_selected)
    serialized_chars = 0

    if compared:
        payload, external_groups, group_aliases, owner_aliases = _payload(
            obligation_descriptions, compared
        )
        prompt_text = _prompt_text(max_selected=max_selected)
        response_format = (
            _global_response_format(external_groups, max_selected=max_selected or 1)
            if global_selection else _response_format(external_groups)
        )
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
            "budget_policy": "append_crossing_group_then_stop",
            "budget_overshoot_chars": max(0, total_input_chars - max_input_chars),
        }
        if trace is not None:
            trace.record("initial_owner_comparison_prepared", preparation)
        if total_input_chars > max_input_chars:
            # The last admitted file may cross the threshold. A further file
            # after an already-over-budget prefix is still a contract error.
            compared_paths = {_group_key(key)[0] for key in compared}
            last_path = next(path.casefold() for path, _ in reversed(admitted_groups)
                             if path.casefold() in compared_paths)
            prefix = {key: values for key, values in compared.items()
                      if _group_key(key)[0] != last_path}
            prefix_chars = 0
            if prefix:
                prefix_payload, prefix_external, _, _ = _payload(obligation_descriptions, prefix)
                prefix_format = (
                    _global_response_format(prefix_external, max_selected=max_selected or 1)
                    if global_selection else _response_format(prefix_external)
                )
                prefix_chars = (len(prompt_text) + len(json.dumps(prefix_format, sort_keys=True))
                                + len(json.dumps(prefix_payload, sort_keys=True)))
            if prefix_chars > max_input_chars:
                raise RuntimeError(
                    "initial_owner_comparison_input_budget_exceeded:"
                    f"prefix={prefix_chars}>{max_input_chars}:groups_added_after_crossing"
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
        external_selection = (
            _validate_global_response(
                response,
                external_groups,
                max_selected=max_selected or 1,
            )
            if global_selection else _validate_response(response, external_groups)
        )
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
        selected_counts = tuple(len(value) for value in selected_by_group.values())
        max_selected_in_group = max(selected_counts, default=0)
        trace.record(
            "initial_owner_comparison_created",
            {
                "selected_by_group": {key: list(value) for key, value in selected_by_group.items()},
                "input_candidate_count": len(observations),
                "participating_candidate_count": len(participating_ids),
                "nonparticipating_candidate_count": len(observations) - len(participating_ids),
                "participating_file_count": len({
                    item.handle.path for item in observations if item.id in participating_ids
                }),
                "selected_count": len(selected),
                "selected_file_count": len({item.handle.path for item in selected}),
                "selection_contract": "grouped_primary_and_additional_owners",
                "primary_selected_count": len(selected_by_group),
                "additional_selected_count": sum(max(0, value - 1) for value in selected_counts),
                "max_selected_per_file": max_selected_in_group,
                "largest_file_selection_share": (
                    max_selected_in_group / len(selected) if selected else 0.0
                ),
                "dormant_count": len(dormant),
                "dormant_file_count": len({item.handle.path for item in dormant}),
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


def fit_initial_owner_comparison_admission(
    *,
    obligation_descriptions: Mapping[str, str],
    observations: Sequence[DiscoveryObservation],
    ranked_paths: Sequence[str],
    preferred_input_chars: int,
    max_input_chars: int,
    max_files: int,
    max_selected: int,
) -> InitialOwnerComparisonAdmission:
    """Append complete ranked groups; retain the crossing group, then stop."""
    admitted: list[str] = []
    excluded: list[str] = []
    total_input_chars = 0
    candidate_count = 0
    stopping_reason = "ranking_exhausted"
    stopped_at_path = ""
    path_decisions: list[dict[str, object]] = []
    for path in ranked_paths:
        if stopping_reason != "ranking_exhausted":
            excluded.append(path)
            path_decisions.append({"path": path, "decision": "excluded_after_budget_crossing",
                                   "crossing_path": stopped_at_path})
            continue
        if len(admitted) >= max_files:
            excluded.append(path)
            path_decisions.append({"path": path, "decision": "excluded_file_limit"})
            continue
        tentative = (*admitted, path)
        groups = _candidate_groups(
            observations,
            tuple((value.casefold(), _ALL_FILE_OBLIGATIONS) for value in tentative),
        )
        payload, external_groups, _group_aliases, _owner_aliases = _payload(
            obligation_descriptions,
            groups,
        )
        prompt_text = _prompt_text(max_selected=max_selected)
        response_format = _global_response_format(external_groups, max_selected=max_selected)
        measured = (
            len(prompt_text)
            + len(json.dumps(response_format, sort_keys=True))
            + len(json.dumps(payload, sort_keys=True))
        )
        marginal_chars = measured - total_input_chars
        admitted.append(path)
        previous_chars = total_input_chars
        total_input_chars = measured
        candidate_count = len({item.id for values in groups.values() for item in values})
        if measured > min(preferred_input_chars, max_input_chars):
            stopping_reason = ("maximum_input_threshold_crossed" if measured > max_input_chars
                               else "preferred_input_target_crossed")
            stopped_at_path = path
        path_decisions.append({
            "path": path,
            "decision": "admitted",
            "total_input_chars": measured,
            "marginal_chars": marginal_chars,
            "candidate_count": candidate_count,
            "previous_input_chars": previous_chars,
            "crossed_budget": stopping_reason != "ranking_exhausted",
            "preferred_overshoot_chars": max(0, measured - preferred_input_chars),
            "maximum_overshoot_chars": max(0, measured - max_input_chars),
        })
    return InitialOwnerComparisonAdmission(
        admitted_groups=tuple((path.casefold(), _ALL_FILE_OBLIGATIONS) for path in admitted),
        admitted_paths=tuple(admitted),
        excluded_paths=tuple(excluded),
        total_input_chars=total_input_chars,
        candidate_count=candidate_count,
        stopping_reason=stopping_reason,
        stopped_at_path=stopped_at_path,
        path_decisions=tuple(path_decisions),
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
            owner = owners.setdefault(owner_alias, _owner_payload(observation))
            view_ids = owner["v"]
            for view_key, view_payload in _source_view_payloads(observation):
                view_alias = source_view_alias_by_key.setdefault(
                    view_key,
                    f"v{len(source_view_alias_by_key) + 1}",
                )
                if view_alias not in source_views:
                    source_views[view_alias] = view_payload
                if view_alias not in view_ids:
                    view_ids.append(view_alias)
        external_groups[group_alias] = tuple(owner_ids)
        rendered_groups.append(
            {
                "id": group_alias,
                "path": path,
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


def _source_view_payloads(
    observation: DiscoveryObservation,
) -> tuple[tuple[tuple[str, int, int, str], dict[str, Any]], ...]:
    handle = observation.handle
    values = observation.comparison_source_views or observation.source_views or (
        SimpleNamespace(
            path=handle.path,
            line_start=handle.line_start,
            line_end=handle.line_end,
            text=observation.observed_text,
        ),
    )
    return tuple(
        (
            (view.path.casefold(), view.line_start, view.line_end, view.text),
            {
                "p": view.path,
                "r": [view.line_start, view.line_end],
                "x": view.text if observation.comparison_source_views else _compact_source_view(view.text),
            },
        )
        for view in values
    )


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


def _global_response_format(
    expected: Mapping[str, Sequence[str]],
    *,
    max_selected: int,
) -> dict[str, Any]:
    group_properties = {
        group_id: {
            "anyOf": [
                {"type": "null"},
                {
                    "type": "object",
                    "properties": {
                        "primary_owner_id": {"type": "string", "enum": list(owner_ids)},
                        "additional_owner_ids": {
                            "type": "array",
                            "items": {"type": "string", "enum": list(owner_ids)},
                            "maxItems": max(0, min(max_selected - 1, len(owner_ids) - 1)),
                        },
                    },
                    "required": ["primary_owner_id", "additional_owner_ids"],
                    "additionalProperties": False,
                },
            ]
        }
        for group_id, owner_ids in expected.items()
    }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "initial_owner_comparison",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "selections": {
                        "type": "object",
                        "properties": group_properties,
                        "required": list(expected),
                        "additionalProperties": False,
                    }
                },
                "required": ["selections"],
                "additionalProperties": False,
            },
        },
    }


def _validate_global_response(
    response: Mapping[str, Any],
    expected: Mapping[str, Sequence[str]],
    *,
    max_selected: int,
) -> dict[str, tuple[str, ...]]:
    rows = response.get("selections")
    if set(response) != {"selections"} or not isinstance(rows, Mapping) or set(rows) != set(expected):
        raise RuntimeError("initial_owner_comparison_invalid_global_selection")
    rendered: dict[str, tuple[str, ...]] = {}
    selected_owner_ids: set[str] = set()
    for group_id, row in rows.items():
        if row is None:
            continue
        if not isinstance(row, Mapping) or set(row) != {"primary_owner_id", "additional_owner_ids"}:
            raise RuntimeError("initial_owner_comparison_invalid_global_selection")
        primary_owner_id = row.get("primary_owner_id")
        additional = row.get("additional_owner_ids", ())
        if (
            not isinstance(primary_owner_id, str)
            or group_id in rendered
            or not isinstance(additional, list)
            or any(not isinstance(value, str) for value in additional)
        ):
            raise RuntimeError("initial_owner_comparison_invalid_global_selection")
        group_selection = (primary_owner_id, *additional)
        allowed = set(expected[group_id])
        if (
            not primary_owner_id
            or len(set(group_selection)) != len(group_selection)
            or any(value not in allowed or value in selected_owner_ids for value in group_selection)
        ):
            raise RuntimeError("initial_owner_comparison_invalid_global_selection")
        rendered[group_id] = group_selection
        selected_owner_ids.update(group_selection)
    if not selected_owner_ids or len(selected_owner_ids) > max_selected:
        raise RuntimeError("initial_owner_comparison_invalid_global_selection")
    return rendered


def _prompt_text(*, max_selected: int | None) -> str:
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    if max_selected is None:
        return prompt
    return (
        f"{prompt}\n\nGlobal round-zero selection:\n"
        f"- Return `selections`, selecting no more than {max_selected} owners globally across all groups.\n"
        "- `selections` is an object keyed by every input group ID. Use null for an unselected group; "
        "otherwise return its primary_owner_id and additional_owner_ids. IDs must belong to that group.\n"
        "- For every selected file group, name its strongest `primary_owner_id`. Add same-file "
        "`additional_owner_ids` only for distinct, nonredundant mechanism contributions.\n"
        "- Cover the listed obligations across the complete selection; a file group may receive no owner.\n"
        "- This is the final round-zero guardrail. Do not select a weaker owner merely to represent every file.\n"
    )


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
