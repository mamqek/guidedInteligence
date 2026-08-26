from __future__ import annotations

"""Run-scoped validation for controller actions and deterministic tool requests.

This module owns repeat detection.  The retrieval controller supplies state and
consumes decisions; it does not implement cache keys or semantic effect rules.
"""

from dataclasses import replace
import json
import re
from typing import Any, Mapping, Sequence

from services.retrieval.workspace.pipeline.execution_flow.actions.models import (
    ExpandRelationship,
    InspectDeferredObservation,
    InspectOwnerContinuation,
    InspectVerifiedLead,
    RetrievalAction,
    SearchNewIsland,
    SearchWithinFile,
)
from services.retrieval.workspace.tools.contracts import ToolObservation, ToolRequest


DETERMINISTIC_STRUCTURAL_TOOLS = frozenset(
    {
        "structural_find_exact_symbol",
        "structural_resolve_locations",
        "structural_resolve_ranges",
        "structural_file_outline",
        "structural_resolve_file_nodes",
        "structural_relationships_within_nodes",
        "structural_source_owner_calls",
        "structural_edge_capabilities",
        "structural_expand_relationships",
        "structural_expand_nodes",
        "structural_callers",
        "structural_callees",
        "structural_file_neighbors",
        "structural_qualified_references",
        "structural_relationship",
    }
)

_WORD_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_.$:]*")
_NOISE_WORDS = frozenset(
    {
        "a", "an", "and", "as", "at", "be", "by", "code", "context", "does", "for",
        "from", "how", "in", "is", "it", "of", "on", "or", "repository", "retrieve",
        "show", "that", "the", "this", "to", "what", "when", "where", "which", "why",
    }
)


def normalized_action_effect(action: RetrievalAction) -> tuple[str, ...]:
    """Return a prose-insensitive description of the search space an action opens."""

    if isinstance(action, InspectVerifiedLead):
        return ("verified_lead", action.target_node_id)
    if isinstance(action, InspectDeferredObservation):
        return ("inspect", action.observation_id, *_range_tokens(action.requested_range))
    if isinstance(action, InspectOwnerContinuation):
        return ("owner_continuation", action.observation_id, *_range_tokens(action.owner_range))
    if isinstance(action, ExpandRelationship):
        if action.seed_kind == "file":
            return (
                "file_expand",
                action.root_node_id,
                action.direction.casefold(),
                *(f"edge:{value.casefold()}" for value in sorted(set(action.edge_kinds))),
                f"cross_file:{bool(action.cross_file_only)}",
            )
        return (
            "expand",
            action.root_node_id,
            action.direction.casefold(),
            *(f"edge:{value.casefold()}" for value in sorted(set(action.edge_kinds))),
            *(f"symbol:{value.casefold()}" for value in sorted(set(action.target_symbol_anchors))),
            *(f"term:{value}" for value in _meaningful_terms(action.target_term_anchors)),
            f"cross_file:{bool(action.cross_file_only)}",
        )
    if isinstance(action, SearchWithinFile):
        anchors = _meaningful_terms((*action.sparse_anchors, action.handoff_reason))
        if not anchors:
            anchors = _meaningful_terms((action.dense_query,))
        return (
            "within_file",
            action.path.casefold(),
            action.source_observation_id,
            action.purpose.value,
            *(f"target:{value}" for value in anchors),
        )
    if isinstance(action, SearchNewIsland):
        anchors = _meaningful_terms(
            (*action.exact_symbol_anchors, *action.exact_path_anchors, *action.sparse_anchors)
        )
        if not anchors:
            anchors = _meaningful_terms((action.dense_query,))
        return ("new_island", *(f"target:{value}" for value in anchors))
    return ("stop", action.id)


def effect_is_subsumed(effect: tuple[str, ...], completed: Sequence[tuple[str, ...]]) -> bool:
    """Whether a completed effect already covered every structured target in ``effect``."""

    if not effect:
        return False
    effect_kind = effect[0]
    effect_base, effect_targets = _effect_parts(effect)
    for prior in completed:
        if not prior or prior[0] != effect_kind:
            continue
        prior_base, prior_targets = _effect_parts(prior)
        if prior_base != effect_base:
            continue
        if effect_targets <= prior_targets:
            return True
    return False


def action_suppression_reason(
    action: RetrievalAction,
    *,
    completed_effects: Sequence[tuple[str, ...]],
) -> dict[str, Any] | None:
    effect = normalized_action_effect(action)
    for prior in completed_effects:
        if effect_is_subsumed(effect, (prior,)):
            return {
                "action_id": action.id,
                "reason": "completed_effect_subsumes_action",
                "effect": list(effect),
                "covering_effect": list(prior),
            }
    return None


class RequestMemoizer:
    """Share deterministic structural results within one controller invocation."""

    def __init__(self) -> None:
        self._results: dict[str, ToolObservation] = {}

    def wrap_tools(self, tools: Mapping[str, Any]) -> dict[str, Any]:
        return {
            name: _MemoizedTool(tool, self)
            if name in DETERMINISTIC_STRUCTURAL_TOOLS
            else tool
            for name, tool in tools.items()
        }

    def run(self, tool: Any, request: ToolRequest) -> ToolObservation:
        key = _request_key(request)
        cached = self._results.get(key)
        if cached is not None:
            return replace(
                cached,
                metadata={
                    **dict(cached.metadata),
                    "cache_hit": "true",
                    "actual_tool_call": "false",
                },
            )
        result = tool.run(request)
        self._results[key] = result
        return replace(
            result,
            metadata={
                **dict(result.metadata),
                "cache_hit": "false",
                "actual_tool_call": "true",
            },
        )


class _MemoizedTool:
    def __init__(self, tool: Any, memoizer: RequestMemoizer) -> None:
        self._tool = tool
        self._memoizer = memoizer
        self.name = str(getattr(tool, "name", ""))

    def run(self, request: ToolRequest) -> ToolObservation:
        return self._memoizer.run(self._tool, request)


def _request_key(request: ToolRequest) -> str:
    return json.dumps(
        {"tool_name": request.tool_name, "arguments": _normalized_json(request.arguments)},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _normalized_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normalized_json(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_normalized_json(item) for item in value]
    return value


def _range_tokens(value: tuple[int, int]) -> tuple[str, str]:
    return (str(int(value[0])), str(int(value[1])))


def _meaningful_terms(values: Sequence[str]) -> tuple[str, ...]:
    terms: set[str] = set()
    for value in values:
        for token in _WORD_RE.findall(str(value)):
            normalized = token.casefold()
            if normalized not in _NOISE_WORDS and len(normalized) > 1:
                terms.add(normalized)
    return tuple(sorted(terms))


def _effect_parts(effect: tuple[str, ...]) -> tuple[tuple[str, ...], frozenset[str]]:
    target_prefixes = ("target:", "symbol:", "term:")
    base = tuple(value for value in effect if not value.startswith(target_prefixes))
    targets = frozenset(value for value in effect if value.startswith(target_prefixes))
    return base, targets
