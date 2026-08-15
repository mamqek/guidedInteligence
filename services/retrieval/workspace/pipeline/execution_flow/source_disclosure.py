from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import (
    DiscoveryObservation,
    SourceHandle,
)
from services.retrieval.workspace.tools import ToolRequest


@dataclass(frozen=True)
class OutlineEntry:
    node_id: str
    kind: str
    name: str
    qualified_name: str
    line_start: int
    line_end: int


@dataclass(frozen=True)
class DisclosureCard:
    observation_id: str
    handle: SourceHandle
    mode: str
    source_text: str
    outline_entries: tuple[OutlineEntry, ...] = ()
    provenance_summary: Mapping[str, object] | None = None
    truncation_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["provenance_summary"] = dict(self.provenance_summary or {})
        return value


@dataclass(frozen=True)
class DisclosureBatch:
    cards: tuple[DisclosureCard, ...]
    tool_calls: int


def disclose_observations(
    observations: Sequence[DiscoveryObservation],
    *,
    workspace_root: str,
    outline_tool: Any,
    trace: Any | None = None,
    round_index: int = 0,
) -> DisclosureBatch:
    symbol_counts: dict[str, int] = {}
    for observation in observations:
        symbol = observation.handle.symbol.casefold()
        if symbol:
            symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1
    cards: list[DisclosureCard] = []
    tool_calls = 0
    outline_cache: dict[str, tuple[OutlineEntry, ...]] = {}
    for observation in observations:
        handle = observation.handle
        full_start = max(1, handle.full_line_start or handle.line_start)
        full_end = max(full_start, handle.full_line_end or handle.line_end)
        full_span = full_end - full_start + 1
        ambiguous = bool(
            handle.symbol
            and max(observation.ambiguity_count, symbol_counts.get(handle.symbol.casefold(), 0)) > 3
        )
        if ambiguous:
            cards.append(_fold_card(observation, reason="ambiguous_same_name"))
            continue
        source_lines = _safe_source_lines(workspace_root, handle.path)
        if source_lines is None:
            if observation.observed_text:
                cards.append(
                    DisclosureCard(
                        observation_id=observation.id,
                        handle=handle,
                        mode="preview",
                        source_text=observation.observed_text,
                        provenance_summary=_provenance_summary(observation),
                        truncation_reason="repository_source_unavailable_using_indexed_chunk",
                    )
                )
            else:
                cards.append(_fold_card(observation, reason="source_unavailable"))
            continue
        if handle.node_id and full_span <= 120:
            source = _range_text(source_lines, full_start, full_end)
            cards.append(
                DisclosureCard(
                    observation_id=observation.id,
                    handle=handle,
                    mode="full",
                    source_text=source,
                    provenance_summary=_provenance_summary(observation),
                )
            )
            continue
        if not handle.node_id:
            source = observation.observed_text or _range_text(source_lines, handle.line_start, handle.line_end)
            cards.append(
                DisclosureCard(
                    observation_id=observation.id,
                    handle=handle,
                    mode="preview",
                    source_text=source,
                    provenance_summary=_provenance_summary(observation),
                    truncation_reason="indexed_chunk_without_structural_owner",
                )
            )
            continue

        outline = outline_cache.get(handle.path)
        if outline is None:
            request = ToolRequest(
                tool_name="structural_file_outline",
                arguments={"path": handle.path, "max_entries": 40},
                reason=f"Create bounded structural disclosure for {handle.path}.",
            )
            response = outline_tool.run(request)
            if trace is not None:
                trace.record_tool(request, response, round_index=round_index)
            tool_calls += 1
            if response.status == "ok":
                outline = tuple(
                    _outline_entry(item)
                    for item in response.payload.get("nodes", ())
                    if isinstance(item, Mapping)
                )
            else:
                outline = ()
            outline_cache[handle.path] = outline
        local_start = max(1, handle.line_start - 12)
        local_end = min(len(source_lines), max(handle.line_end, handle.line_start + 24))
        signature_end = min(len(source_lines), full_start + 2)
        source = _range_text(source_lines, full_start, signature_end)
        local_source = _range_text(source_lines, local_start, local_end)
        if local_start > signature_end + 1:
            source = f"{source}\n// ... lines {signature_end + 1}-{local_start - 1} omitted ...\n{local_source}"
        elif local_source not in source:
            source = f"{source}\n{local_source}"
        cards.append(
            DisclosureCard(
                observation_id=observation.id,
                handle=handle,
                mode="preview",
                source_text=source,
                outline_entries=outline,
                provenance_summary=_provenance_summary(observation),
                truncation_reason="large_owner_skeleton_and_local_excerpt" if outline else "outline_unavailable_local_excerpt",
            )
        )
    return DisclosureBatch(cards=tuple(cards), tool_calls=tool_calls)


def _fold_card(observation: DiscoveryObservation, *, reason: str) -> DisclosureCard:
    return DisclosureCard(
        observation_id=observation.id,
        handle=observation.handle,
        mode="fold",
        source_text="",
        provenance_summary=_provenance_summary(observation),
        truncation_reason=reason,
    )


def _outline_entry(value: Mapping[str, Any]) -> OutlineEntry:
    return OutlineEntry(
        node_id=str(value.get("id") or ""),
        kind=str(value.get("kind") or ""),
        name=str(value.get("name") or ""),
        qualified_name=str(value.get("qualified_name") or value.get("name") or ""),
        line_start=max(1, int(value.get("line_start") or 1)),
        line_end=max(1, int(value.get("line_end") or value.get("line_start") or 1)),
    )


def _provenance_summary(observation: DiscoveryObservation) -> dict[str, object]:
    return {
        "retrievers": list(dict.fromkeys(item.retriever for item in observation.provenance)),
        "obligation_ids": list(observation.obligation_ids),
        "exact_anchor_matches": list(observation.exact_anchor_matches),
        "recurrence": observation.recurrence,
        "artifact_role": observation.artifact_role,
        "parent_observation_ids": list(observation.parent_observation_ids),
        "relationship_direction": observation.relationship_direction,
        "relationship_kinds": list(observation.relationship_kinds),
    }


def _safe_source_lines(workspace_root: str, relative_path: str) -> list[str] | None:
    root = Path(workspace_root).resolve()
    source = (root / relative_path).resolve()
    try:
        source.relative_to(root)
    except ValueError:
        return None
    if not source.is_file():
        return None
    return source.read_text(encoding="utf-8", errors="replace").splitlines()


def _range_text(lines: Sequence[str], line_start: int, line_end: int) -> str:
    start = max(1, line_start)
    end = min(len(lines), max(start, line_end))
    return "\n".join(lines[start - 1 : end])
