from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
from typing import Any, Iterable, Mapping, Sequence

from services.retrieval.workspace.bm25 import file_role


@dataclass(frozen=True)
class DiscoveryProvenance:
    retriever: str
    query_id: str
    obligation_ids: tuple[str, ...] = ()
    ranks: tuple[int, ...] = ()
    scores: tuple[float, ...] = ()
    matched_terms: tuple[str, ...] = ()
    source_key: str = ""


@dataclass(frozen=True)
class SourceHandle:
    path: str
    line_start: int
    line_end: int
    node_id: str = ""
    symbol: str = ""
    full_line_start: int = 0
    full_line_end: int = 0
    language: str = ""
    adapter: str = ""
    outer_node_id: str = ""
    outer_symbol: str = ""
    outer_line_start: int = 0
    outer_line_end: int = 0


@dataclass(frozen=True)
class RetrievedSourceView:
    path: str
    line_start: int
    line_end: int
    text: str


@dataclass(frozen=True)
class InitialAdmissionSignal:
    """Deterministic pre-comparison rank attached to a held owner.

    This is lifecycle provenance, not evidence qualification: it records whether
    the owner reached the bounded initial comparison request and where it ranked.
    """

    ranking_position: int
    decision: str
    crossed_budget: bool = False
    budget_crossing_position: int = 0
    coverage_reserved: bool = False


@dataclass(frozen=True)
class DiscoveryObservation:
    id: str
    handle: SourceHandle
    observed_text: str
    provenance: tuple[DiscoveryProvenance, ...]
    source_views: tuple[RetrievedSourceView, ...] = ()
    exact_anchor_matches: tuple[str, ...] = ()
    artifact_role: str = "other"
    recurrence: int = 1
    disclosure_status: str = "undisclosed"
    parent_observation_ids: tuple[str, ...] = ()
    relationship_direction: str = ""
    relationship_kinds: tuple[str, ...] = ()
    ambiguity_count: int = 1
    # Initial admission can keep one representative per file while retaining a
    # stronger structural alternative for a bounded later rescue.
    admission_reason: str = ""
    initial_admission: InitialAdmissionSignal | None = None
    # Comparison-only source; original Qdrant views remain unchanged provenance.
    comparison_source_views: tuple[RetrievedSourceView, ...] = ()

    @property
    def obligation_ids(self) -> tuple[str, ...]:
        return _ordered_unique(
            obligation_id
            for item in self.provenance
            for obligation_id in item.obligation_ids
        )

    @property
    def best_rank(self) -> int:
        ranks = [rank for item in self.provenance for rank in item.ranks if rank > 0]
        return min(ranks, default=10_000)

    @property
    def best_score(self) -> float:
        return max((score for item in self.provenance for score in item.scores), default=0.0)

    @property
    def support_counts(self) -> dict[str, int]:
        """Separate independent support from repeated retrieval views."""
        raw_chunk_keys = {
            item.source_key or f"unkeyed:{index}"
            for index, item in enumerate(self.provenance)
        }
        return {
            "raw_chunks": len(raw_chunk_keys),
            "query_views": len({(item.retriever, item.query_id) for item in self.provenance}),
            "obligations": len({value for item in self.provenance for value in item.obligation_ids}),
            "channels": len({_retrieval_channel(item.retriever) for item in self.provenance}),
        }

    def to_dict(self, *, include_text: bool = True) -> dict[str, Any]:
        value = asdict(self)
        if not include_text:
            value.pop("observed_text", None)
            value.pop("source_views", None)
            value.pop("comparison_source_views", None)
        value["obligation_ids"] = list(self.obligation_ids)
        value["best_rank"] = self.best_rank
        value["best_score"] = self.best_score
        value["support_counts"] = self.support_counts
        return value


def observation_from_node(
    node: Mapping[str, Any],
    *,
    retriever: str,
    query_id: str,
    obligation_ids: Sequence[str],
    score: float,
    exact_anchor: str = "",
    parent_observation_ids: Sequence[str] = (),
    relationship_direction: str = "",
    relationship_kinds: Sequence[str] = (),
) -> DiscoveryObservation | None:
    path = _path(node.get("path"))
    line_start = max(1, int(node.get("line_start") or 1))
    line_end = max(line_start, int(node.get("line_end") or line_start))
    if not path:
        return None
    handle = SourceHandle(
        path=path,
        line_start=line_start,
        line_end=line_end,
        node_id=str(node.get("id") or ""),
        symbol=str(node.get("qualified_name") or node.get("name") or ""),
        full_line_start=max(1, int(node.get("full_line_start") or line_start)),
        full_line_end=max(line_end, int(node.get("full_line_end") or line_end)),
        language=str(node.get("language") or ""),
        adapter="codegraph_node",
    )
    return DiscoveryObservation(
        id=observation_id(handle),
        handle=handle,
        observed_text="",
        provenance=(
            DiscoveryProvenance(
                retriever=retriever,
                query_id=query_id,
                obligation_ids=_ordered_unique(obligation_ids),
                scores=(float(score),),
                source_key=f"{path}:{line_start}:{line_end}",
            ),
        ),
        exact_anchor_matches=((exact_anchor,) if exact_anchor else ()),
        artifact_role=file_role(path),
        parent_observation_ids=_ordered_unique(parent_observation_ids),
        relationship_direction=relationship_direction,
        relationship_kinds=_ordered_unique(relationship_kinds),
        ambiguity_count=max(1, int(node.get("anchor_match_count") or 1)),
    )


def observation_from_result(
    result: Mapping[str, Any],
    *,
    obligation_id: str,
    query_id: str,
    rank: int,
    retriever: str,
    nodes: Sequence[Mapping[str, Any]] = (),
    exact_anchor: str = "",
) -> tuple[DiscoveryObservation, ...]:
    path = _path(result.get("path"))
    line_start = max(1, int(result.get("line_start") or 1))
    line_end = max(line_start, int(result.get("line_end") or line_start))
    if not path:
        return ()
    selected_nodes = tuple(nodes) or ({},)
    observations: list[DiscoveryObservation] = []
    for node in selected_nodes:
        node_start = max(1, int(node.get("line_start") or line_start))
        node_end = max(node_start, int(node.get("line_end") or line_end))
        visible_start = max(line_start, node_start) if node else line_start
        visible_end = min(line_end, node_end) if node else line_end
        if visible_end < visible_start:
            visible_start, visible_end = line_start, line_end
        observed_text = _owner_aligned_result_text(
            str(result.get("text") or ""),
            range_start=line_start,
            range_end=line_end,
            owner_start=node_start,
            owner_end=node_end,
        )
        handle = SourceHandle(
            path=path,
            line_start=visible_start,
            line_end=visible_end,
            node_id=str(node.get("id") or ""),
            symbol=str(node.get("qualified_name") or node.get("name") or ""),
            full_line_start=node_start,
            full_line_end=node_end,
            language=str(node.get("language") or ""),
            adapter="codegraph_node" if node else "indexed_chunk",
            outer_node_id=str(node.get("outer_node_id") or ""),
            outer_symbol=str(node.get("outer_symbol") or ""),
            outer_line_start=max(0, int(node.get("outer_line_start") or 0)),
            outer_line_end=max(0, int(node.get("outer_line_end") or 0)),
        )
        observations.append(
            DiscoveryObservation(
                id=observation_id(handle),
                handle=handle,
                observed_text=observed_text,
                provenance=(
                    DiscoveryProvenance(
                        retriever=retriever,
                        query_id=query_id,
                        obligation_ids=(obligation_id,),
                        ranks=(rank,),
                        scores=(float(result.get("score") or 0.0),),
                        matched_terms=_ordered_unique(str(value) for value in result.get("matched_terms", ()) if value),
                        source_key=f"{path}:{line_start}:{line_end}",
                    ),
                ),
                source_views=(
                    RetrievedSourceView(path, visible_start, visible_end, observed_text),
                ),
                exact_anchor_matches=((exact_anchor,) if exact_anchor else ()),
                artifact_role=str(result.get("file_role") or file_role(path)),
            )
        )
    return tuple(observations)


def _owner_aligned_result_text(
    text: str,
    *,
    range_start: int,
    range_end: int,
    owner_start: int,
    owner_end: int,
) -> str:
    """Return the visible part of one owner instead of copying a shared range.

    Qdrant text is already bounded to ``range_start``/``range_end``.  For a
    multi-owner range, slice that text to the lines intersecting this owner.
    Complete owner disclosure remains a later stage.
    """
    if not text or (owner_start <= range_start and owner_end >= range_end):
        return text
    visible_start = max(range_start, owner_start)
    visible_end = min(range_end, owner_end)
    if visible_end < visible_start:
        return text
    lines = text.splitlines()
    first = max(0, visible_start - range_start)
    last = min(len(lines), visible_end - range_start + 1)
    rendered = "\n".join(lines[first:last]).strip()
    return rendered or text


def aggregate_observations(
    observations: Iterable[DiscoveryObservation],
    *,
    limit: int,
    one_per_path: bool = False,
    max_obligation_variants_per_path: int = 1,
    one_per_obligation_per_path: bool = True,
) -> tuple[tuple[DiscoveryObservation, ...], tuple[dict[str, Any], ...]]:
    values, decisions = canonicalize_observations(observations)
    decisions = list(decisions)
    selected: list[DiscoveryObservation] = []
    selected_keys: set[str] = set()
    selected_paths: set[str] = set()
    selected_by_path: dict[str, list[DiscoveryObservation]] = {}

    def take(observation: DiscoveryObservation, *, obligation_id: str = "") -> None:
        key = _aggregation_key(observation)
        path = observation.handle.path.casefold()
        path_variants = selected_by_path.get(path, ())
        same_obligation_is_covered = one_per_obligation_per_path and bool(obligation_id) and any(
            obligation_id in item.obligation_ids for item in path_variants
        )
        path_limit_reached = one_per_path and len(path_variants) >= max_obligation_variants_per_path
        if (
            key in selected_keys
            or len(selected) >= limit
            or (one_per_path and (same_obligation_is_covered or path_limit_reached))
        ):
            return
        selected.append(observation)
        selected_keys.add(key)
        selected_paths.add(path)
        selected_by_path.setdefault(path, []).append(observation)

    for observation in values:
        if observation.exact_anchor_matches:
            take(observation)
    all_obligations = _ordered_unique(obligation_id for item in values for obligation_id in item.obligation_ids)
    for obligation_id in all_obligations:
        for observation in values:
            if obligation_id in observation.obligation_ids:
                take(observation, obligation_id=obligation_id)
                break
    for observation in values:
        take(observation)

    selected_ids = {item.id for item in selected}
    for observation in values:
        if observation.id not in selected_ids:
            reason = "outside_observation_guardrail"
            if one_per_path and observation.handle.path.casefold() in selected_paths:
                reason = "same_path_alternative"
            decisions.append(
                {
                    "observation_id": observation.id,
                    "path": observation.handle.path,
                    "symbol": observation.handle.symbol,
                    "reason": reason,
                }
            )
    return tuple(selected), tuple(decisions)


def canonicalize_observations(
    observations: Iterable[DiscoveryObservation],
) -> tuple[tuple[DiscoveryObservation, ...], tuple[dict[str, Any], ...]]:
    """Merge source identities and provenance without performing admission.

    This is the reusable identity boundary.  It deliberately has no global or
    per-file limit so callers can construct one canonical pool and make later
    lifecycle decisions as views over that pool.
    """
    merged: dict[str, DiscoveryObservation] = {}
    decisions: list[dict[str, Any]] = []
    for observation in observations:
        key = _aggregation_key(observation)
        merge_reason = "merged_same_entity"
        if not observation.handle.node_id:
            overlapping_key = next(
                (
                    existing_key
                    for existing_key, existing in merged.items()
                    if not existing.handle.node_id and _substantial_range_overlap(existing, observation)
                ),
                "",
            )
            if overlapping_key:
                key = overlapping_key
                merge_reason = "merged_overlapping_range"
        current = merged.get(key)
        if current is None:
            merged[key] = observation
            continue
        combined = _merge(current, observation)
        merged[key] = combined
        decisions.append(
            {
                "observation_id": observation.id,
                "path": observation.handle.path,
                "kept_id": combined.id,
                "reason": merge_reason,
            }
        )

    values = list(merged.values())
    values, containment_decisions = _canonicalize_contained_owners(values)
    decisions.extend(containment_decisions)
    values.sort(key=_priority_key)
    return tuple(values), tuple(decisions)


def _canonicalize_contained_owners(
    observations: Sequence[DiscoveryObservation],
) -> tuple[list[DiscoveryObservation], list[dict[str, Any]]]:
    """Keep the narrow owner as the evidence handle and retain its outer owner as context.

    Two distinct CodeGraph nodes may describe the same retrieved lines when a
    result lands in a nested callback.  They are not independent candidates:
    the inner owner carries the evidence range, while the parent is useful only
    to orient the rendered card.
    """
    remaining = list(observations)
    decisions: list[dict[str, Any]] = []
    changed = True
    while changed:
        changed = False
        for outer_index, outer in enumerate(tuple(remaining)):
            for inner_index, inner in enumerate(tuple(remaining)):
                if outer_index == inner_index:
                    continue
                if not _is_contained_owner_pair(outer, inner):
                    continue
                canonical = _merge_contained_owner_pair(outer, inner)
                remaining = [
                    item for item in remaining
                    if item.id not in {outer.id, inner.id}
                ]
                remaining.append(canonical)
                decisions.append(
                    {
                        "observation_id": outer.id,
                        "kept_id": canonical.id,
                        "path": canonical.handle.path,
                        "outer_node_id": outer.handle.node_id,
                        "inner_node_id": inner.handle.node_id,
                        "reason": "canonicalized_contained_owner",
                    }
                )
                changed = True
                break
            if changed:
                break
    return remaining, decisions


def _is_contained_owner_pair(outer: DiscoveryObservation, inner: DiscoveryObservation) -> bool:
    outer_handle = outer.handle
    inner_handle = inner.handle
    if not outer_handle.node_id or not inner_handle.node_id or outer_handle.node_id == inner_handle.node_id:
        return False
    if outer_handle.path.casefold() != inner_handle.path.casefold():
        return False
    # Preserve an exact structural anchor as its own candidate; it can be a
    # deliberately broad class/file lead rather than a duplicate of one member.
    if outer.exact_anchor_matches or inner.exact_anchor_matches:
        return False
    outer_full_start = outer_handle.full_line_start or outer_handle.line_start
    outer_full_end = outer_handle.full_line_end or outer_handle.line_end
    inner_full_start = inner_handle.full_line_start or inner_handle.line_start
    inner_full_end = inner_handle.full_line_end or inner_handle.line_end
    if not (outer_full_start <= inner_full_start and outer_full_end >= inner_full_end):
        return False
    if (outer_full_start, outer_full_end) == (inner_full_start, inner_full_end):
        return False
    # Both observations must originate from the same actual retrieved region;
    # otherwise a broad class anchor could absorb an unrelated child method.
    return _substantial_range_overlap(outer, inner)


def _merge_contained_owner_pair(outer: DiscoveryObservation, inner: DiscoveryObservation) -> DiscoveryObservation:
    merged = _merge(inner, outer)
    outer_handle = outer.handle
    return replace(
        merged,
        id=inner.id,
        observed_text=inner.observed_text,
        handle=replace(
            inner.handle,
            outer_node_id=outer_handle.node_id,
            outer_symbol=outer_handle.symbol,
            outer_line_start=outer_handle.full_line_start or outer_handle.line_start,
            outer_line_end=outer_handle.full_line_end or outer_handle.line_end,
        ),
    )


def observation_id(handle: SourceHandle) -> str:
    identity = handle.node_id or f"{handle.line_start}:{handle.line_end}"
    digest = hashlib.sha1(f"{handle.path.casefold()}\0{identity}".encode("utf-8")).hexdigest()[:16]
    return f"obs_{digest}"


def with_disclosure_status(observation: DiscoveryObservation, status: str) -> DiscoveryObservation:
    return replace(observation, disclosure_status=status)


def merge_observation_pair(left: DiscoveryObservation, right: DiscoveryObservation) -> DiscoveryObservation:
    if _aggregation_key(left) != _aggregation_key(right):
        raise ValueError("Cannot merge observations with different source identities.")
    return _merge(left, right)


def _merge(left: DiscoveryObservation, right: DiscoveryObservation) -> DiscoveryObservation:
    provenance = (*left.provenance, *right.provenance)
    query_views = {(item.retriever, item.query_id) for item in provenance}
    observed_text = left.observed_text if len(left.observed_text) >= len(right.observed_text) else right.observed_text
    return replace(
        left,
        observed_text=observed_text,
        provenance=provenance,
        source_views=_ordered_unique_source_views((*left.source_views, *right.source_views)),
        exact_anchor_matches=_ordered_unique((*left.exact_anchor_matches, *right.exact_anchor_matches)),
        recurrence=max(1, len(query_views)),
        parent_observation_ids=_ordered_unique((*left.parent_observation_ids, *right.parent_observation_ids)),
        relationship_kinds=_ordered_unique((*left.relationship_kinds, *right.relationship_kinds)),
        ambiguity_count=max(left.ambiguity_count, right.ambiguity_count),
        initial_admission=_stronger_initial_admission(left.initial_admission, right.initial_admission),
    )


def _stronger_initial_admission(
    left: InitialAdmissionSignal | None,
    right: InitialAdmissionSignal | None,
) -> InitialAdmissionSignal | None:
    if left is None:
        return right
    if right is None:
        return left
    return min(
        (left, right),
        key=lambda item: (
            0 if item.decision == "admitted" else 1,
            item.ranking_position or 10_000,
            0 if item.coverage_reserved else 1,
        ),
    )


def _ordered_unique_source_views(
    values: Iterable[RetrievedSourceView],
) -> tuple[RetrievedSourceView, ...]:
    rendered: list[RetrievedSourceView] = []
    seen: set[tuple[str, int, int, str]] = set()
    for value in values:
        key = (value.path.casefold(), value.line_start, value.line_end, value.text)
        if key in seen:
            continue
        seen.add(key)
        rendered.append(value)
    return tuple(rendered)


def _aggregation_key(observation: DiscoveryObservation) -> str:
    handle = observation.handle
    return f"node:{handle.node_id}" if handle.node_id else f"range:{handle.path.casefold()}:{handle.line_start}:{handle.line_end}"


def _priority_key(observation: DiscoveryObservation) -> tuple[Any, ...]:
    return (
        0 if observation.exact_anchor_matches else 1,
        -observation.recurrence,
        observation.best_rank,
        -observation.best_score,
        observation.handle.path.casefold(),
        observation.handle.line_start,
    )


def _substantial_range_overlap(left: DiscoveryObservation, right: DiscoveryObservation) -> bool:
    if left.handle.path.casefold() != right.handle.path.casefold():
        return False
    overlap = min(left.handle.line_end, right.handle.line_end) - max(left.handle.line_start, right.handle.line_start) + 1
    if overlap <= 0:
        return False
    smaller = min(
        left.handle.line_end - left.handle.line_start + 1,
        right.handle.line_end - right.handle.line_start + 1,
    )
    return float(overlap) / float(max(1, smaller)) >= 0.7


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _path(value: object) -> str:
    return str(value or "").strip().replace("\\", "/").removeprefix("./")


def _retrieval_channel(retriever: str) -> str:
    value = str(retriever).casefold()
    for channel in ("dense", "sparse", "exact", "bm25", "graph"):
        if channel in value:
            return channel
    return value or "unknown"
