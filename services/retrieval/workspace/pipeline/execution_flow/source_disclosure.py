from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import (
    DiscoveryObservation,
    SourceHandle,
)
from services.retrieval.workspace.tools import ToolRequest


OMISSION_MARKER = "// ... complete source lines omitted; use the stable source handle ..."
MAX_COMPLETE_OWNER_LINES = 80
MAX_QUALIFICATION_CARD_CHARS = 4000
LOCAL_CONTEXT_LINES = 12


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
    owner_kind: str = ""
    owner_name: str = ""
    owner_line_start: int = 0
    owner_line_end: int = 0
    outer_owner_line_start: int = 0
    outer_owner_line_end: int = 0
    allocated_chars: int = 0
    used_chars: int = 0
    complete_source_text: str = ""
    preview_source_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["provenance_summary"] = dict(self.provenance_summary or {})
        value.pop("complete_source_text", None)
        value.pop("preview_source_text", None)
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
    outline_cache: dict[tuple[str, int, int], tuple[OutlineEntry, ...]] = {}
    for observation in observations:
        handle = observation.handle
        hit_start, hit_end = handle.line_start, handle.line_end
        ambiguous = bool(handle.symbol and max(observation.ambiguity_count, symbol_counts.get(handle.symbol.casefold(), 0)) > 3)
        if ambiguous:
            cards.append(_fold_card(observation, reason="ambiguous_same_name"))
            continue
        lines = _safe_source_lines(workspace_root, handle.path)
        if lines is None:
            if observation.observed_text:
                preview = _bound_qualification_text(observation.observed_text)
                cards.append(DisclosureCard(
                    observation.id, handle, "preview", preview,
                    provenance_summary=_provenance_summary(observation),
                    truncation_reason="repository_source_unavailable_using_indexed_chunk",
                    complete_source_text=observation.observed_text,
                    preview_source_text=preview,
                ))
            else:
                cards.append(_fold_card(observation, reason="source_unavailable"))
            continue

        full_start = max(1, handle.full_line_start or handle.line_start)
        full_end = max(full_start, handle.full_line_end or handle.line_end)
        kind = _node_kind(handle.node_id)
        needs_outline = (
            not handle.node_id
            or full_end - full_start + 1 > 120
            or kind in {"class", "method", "constructor", "property"}
        )
        outline: tuple[OutlineEntry, ...] = ()
        if needs_outline:
            cache_key = (handle.path, handle.line_start, handle.line_end)
            outline = outline_cache.get(cache_key, ())
            if cache_key not in outline_cache:
                request = ToolRequest(
                    tool_name="structural_file_outline",
                    arguments={
                        "path": handle.path,
                        "max_entries": 80,
                        "line_start": handle.line_start,
                        "line_end": handle.line_end,
                    },
                    reason=f"Resolve the complete structural owner for {handle.path}.",
                )
                response = outline_tool.run(request)
                if trace is not None:
                    trace.record_tool(request, response, round_index=round_index)
                tool_calls += 1
                if response.status == "ok":
                    outline = tuple(_outline_entry(item) for item in response.payload.get("nodes", ()) if isinstance(item, Mapping))
                outline_cache[cache_key] = outline

        owner, outer = _resolve_owner(outline, handle, lines)
        if owner is not None:
            full_start, full_end = owner.line_start, owner.line_end
            handle = replace(
                handle,
                line_start=owner.line_start,
                line_end=owner.line_end,
                node_id=owner.node_id or handle.node_id,
                symbol=owner.qualified_name or owner.name or handle.symbol,
                full_line_start=owner.line_start,
                full_line_end=owner.line_end,
                adapter="codegraph_owner_disclosure",
            )
            kind = owner.kind
        span = full_end - full_start + 1
        complete = _range_text(lines, full_start, full_end)
        if owner is not None and outer is not None and outer.node_id != owner.node_id:
            skeleton = _bound_qualification_text(_class_member_skeleton(lines, outer, owner))
            preview = skeleton
            mode = "preview"
            reason = "class_skeleton_and_complete_member"
        elif span <= MAX_COMPLETE_OWNER_LINES and len(complete) <= MAX_QUALIFICATION_CARD_CHARS:
            preview = complete
            mode = "full"
            reason = ""
        else:
            preview = _bound_qualification_text(
                _large_owner_preview(lines, full_start, full_end, hit_start, hit_end)
            )
            mode = "preview"
            reason = "large_owner_skeleton_and_local_excerpt" if outline else "outline_unavailable_local_excerpt"
        cards.append(DisclosureCard(
            observation_id=observation.id,
            handle=handle,
            mode=mode,
            source_text=preview,
            outline_entries=outline,
            provenance_summary=_provenance_summary(observation),
            truncation_reason=reason,
            owner_kind=kind,
            owner_name=(owner.qualified_name or owner.name) if owner else handle.symbol,
            owner_line_start=full_start,
            owner_line_end=full_end,
            outer_owner_line_start=outer.line_start if outer else 0,
            outer_owner_line_end=outer.line_end if outer else 0,
            complete_source_text=complete,
            preview_source_text=preview,
            used_chars=len(preview),
        ))
    return DisclosureBatch(tuple(cards), tool_calls)


def fit_cards_to_source_capacity(
    cards: Sequence[DisclosureCard],
    *,
    source_capacity: int,
) -> tuple[DisclosureCard, ...]:
    if not cards:
        return ()
    capacity = max(0, source_capacity)
    preferred = [
        _bound_qualification_text(
            (card.complete_source_text or card.source_text)
            if card.mode == "full"
            else (card.preview_source_text or card.source_text)
        )
        for card in cards
    ]
    minima = [min(len(text), max(len(card.preview_source_text or card.source_text), len(OMISSION_MARKER))) for card, text in zip(cards, preferred)]
    allocations = _waterfill([len(text) for text in preferred], minima, capacity)
    fitted: list[DisclosureCard] = []
    for card, text, allocation in zip(cards, preferred, allocations):
        rendered, truncated = _truncate_complete_lines(text, allocation)
        reason = card.truncation_reason
        if truncated:
            reason = "qualification_source_budget_complete_lines"
        fitted.append(replace(
            card,
            source_text=rendered,
            allocated_chars=allocation,
            used_chars=len(rendered),
            truncation_reason=reason,
        ))
    return tuple(fitted)


def _waterfill(wants: Sequence[int], minima: Sequence[int], capacity: int) -> list[int]:
    allocations = [0] * len(wants)
    if capacity <= 0:
        return allocations
    minimum_total = sum(minima)
    if minimum_total >= capacity:
        share = capacity // len(wants)
        remainder = capacity % len(wants)
        return [min(want, share + (1 if i < remainder else 0)) for i, want in enumerate(wants)]
    allocations = [min(want, minimum) for want, minimum in zip(wants, minima)]
    remaining = capacity - sum(allocations)
    active = {i for i, want in enumerate(wants) if allocations[i] < want}
    while remaining and active:
        share = max(1, remaining // len(active))
        for index in tuple(active):
            added = min(share, wants[index] - allocations[index], remaining)
            allocations[index] += added
            remaining -= added
            if allocations[index] >= wants[index]:
                active.remove(index)
            if not remaining:
                break
    return allocations


def _truncate_complete_lines(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    if limit < len(OMISSION_MARKER):
        return "", True
    kept: list[str] = []
    used = len(OMISSION_MARKER)
    for line in text.splitlines():
        addition = len(line) + (1 if kept else 0)
        if used + addition > limit:
            break
        kept.append(line)
        used += addition
    if not kept:
        return OMISSION_MARKER, True
    return "\n".join((*kept, OMISSION_MARKER)), True


def _bound_qualification_text(text: str) -> str:
    lines = text.splitlines()
    if len(lines) > MAX_COMPLETE_OWNER_LINES:
        lines = [*lines[:MAX_COMPLETE_OWNER_LINES - 1], OMISSION_MARKER]
    bounded = "\n".join(lines)
    return _truncate_complete_lines(bounded, MAX_QUALIFICATION_CARD_CHARS)[0]


def _resolve_owner(
    outline: Sequence[OutlineEntry],
    handle: SourceHandle,
    lines: Sequence[str],
) -> tuple[OutlineEntry | None, OutlineEntry | None]:
    owner: OutlineEntry | None = None

    # Indexed chunks may include a few lines from an adjacent declaration. Prefer
    # the structural identity retained by the observation over the chunk edges.
    if handle.node_id:
        exact_nodes = [item for item in outline if item.node_id == handle.node_id]
        if exact_nodes:
            owner = min(exact_nodes, key=lambda item: (item.line_end - item.line_start, -item.line_start))

    if owner is None and handle.symbol:
        symbol = handle.symbol.casefold()
        exact_symbols = [
            item for item in outline
            if symbol in {item.qualified_name.casefold(), item.name.casefold()}
        ]
        if len(exact_symbols) == 1:
            owner = exact_symbols[0]

    structural_start = max(1, handle.full_line_start or handle.line_start)
    structural_end = max(structural_start, handle.full_line_end or handle.line_end)
    structural_owners = [
        item for item in outline
        if item.line_start <= structural_start and item.line_end >= structural_end
    ]
    if owner is None and structural_owners:
        owner = min(structural_owners, key=lambda item: (item.line_end - item.line_start, -item.line_start))

    overlapping = [
        item for item in outline
        if item.line_start <= handle.line_end and item.line_end >= handle.line_start
    ]
    if owner is None and overlapping:
        owner = max(
            overlapping,
            key=lambda item: (
                min(item.line_end, handle.line_end) - max(item.line_start, handle.line_start) + 1,
                -(item.line_end - item.line_start),
                item.line_start,
            ),
        )
    if owner is None:
        following = sorted((item for item in outline if item.line_start >= handle.line_end), key=lambda item: item.line_start)
        owner = following[0] if following and following[0].line_start - handle.line_end <= 12 and _comment_gap(lines, handle.line_start, following[0].line_start) else None
    if owner is None:
        return None, None
    classes = [
        item for item in outline
        if item.kind in {"class", "interface"} and item.line_start <= owner.line_start and item.line_end >= owner.line_end
    ]
    outer = min(classes, key=lambda item: item.line_end - item.line_start) if classes and owner.kind not in {"class", "interface"} else None
    return owner, outer


def _comment_gap(lines: Sequence[str], start: int, end: int) -> bool:
    text = "\n".join(lines[max(0, start - 1):max(0, end - 1)]).strip()
    if not text:
        return True
    return all(part.strip().startswith(("//", "/*", "*", "*/")) or not part.strip() for part in text.splitlines())


def _class_member_skeleton(lines: Sequence[str], outer: OutlineEntry, owner: OutlineEntry) -> str:
    header_end = min(outer.line_end, outer.line_start + 2)
    header = _range_text(lines, outer.line_start, header_end)
    member = _range_text(lines, owner.line_start, owner.line_end)
    return f"{header}\n    // ... other members omitted ...\n{member}\n}}"


def _large_owner_preview(lines: Sequence[str], start: int, end: int, hit_start: int, hit_end: int) -> str:
    signature_end = min(end, start + 2)
    local_start = max(start, hit_start - LOCAL_CONTEXT_LINES)
    local_end = min(end, hit_end + LOCAL_CONTEXT_LINES)
    signature = _range_text(lines, start, signature_end)
    local = _range_text(lines, local_start, local_end)
    if local_start > signature_end + 1:
        return f"{signature}\n// ... lines {signature_end + 1}-{local_start - 1} omitted ...\n{local}"
    return signature if local in signature else f"{signature}\n{local}"


def _fold_card(observation: DiscoveryObservation, *, reason: str) -> DisclosureCard:
    return DisclosureCard(observation.id, observation.handle, "fold", "", provenance_summary=_provenance_summary(observation), truncation_reason=reason)


def _outline_entry(value: Mapping[str, Any]) -> OutlineEntry:
    return OutlineEntry(
        str(value.get("id") or ""), str(value.get("kind") or ""), str(value.get("name") or ""),
        str(value.get("qualified_name") or value.get("name") or ""),
        max(1, int(value.get("line_start") or 1)),
        max(1, int(value.get("line_end") or value.get("line_start") or 1)),
    )


def _node_kind(node_id: str) -> str:
    return node_id.partition(":")[0].casefold() if node_id else ""


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
    return "\n".join(lines[start - 1:end])
