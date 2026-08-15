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


@dataclass(frozen=True)
class DiscoveryObservation:
    id: str
    handle: SourceHandle
    observed_text: str
    provenance: tuple[DiscoveryProvenance, ...]
    exact_anchor_matches: tuple[str, ...] = ()
    artifact_role: str = "other"
    recurrence: int = 1
    disclosure_status: str = "undisclosed"
    parent_observation_ids: tuple[str, ...] = ()
    relationship_direction: str = ""
    relationship_kinds: tuple[str, ...] = ()
    ambiguity_count: int = 1

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

    def to_dict(self, *, include_text: bool = True) -> dict[str, Any]:
        value = asdict(self)
        if not include_text:
            value.pop("observed_text", None)
        value["obligation_ids"] = list(self.obligation_ids)
        value["best_rank"] = self.best_rank
        value["best_score"] = self.best_score
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
        handle = SourceHandle(
            path=path,
            line_start=line_start,
            line_end=line_end,
            node_id=str(node.get("id") or ""),
            symbol=str(node.get("qualified_name") or node.get("name") or ""),
            full_line_start=node_start,
            full_line_end=node_end,
            language=str(node.get("language") or ""),
            adapter="codegraph_node" if node else "indexed_chunk",
        )
        observations.append(
            DiscoveryObservation(
                id=observation_id(handle),
                handle=handle,
                observed_text=str(result.get("text") or ""),
                provenance=(
                    DiscoveryProvenance(
                        retriever=retriever,
                        query_id=query_id,
                        obligation_ids=(obligation_id,),
                        ranks=(rank,),
                        scores=(float(result.get("score") or 0.0),),
                        matched_terms=_ordered_unique(str(value) for value in result.get("matched_terms", ()) if value),
                    ),
                ),
                exact_anchor_matches=((exact_anchor,) if exact_anchor else ()),
                artifact_role=str(result.get("file_role") or file_role(path)),
            )
        )
    return tuple(observations)


def aggregate_observations(
    observations: Iterable[DiscoveryObservation],
    *,
    limit: int,
) -> tuple[tuple[DiscoveryObservation, ...], tuple[dict[str, Any], ...]]:
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
    values.sort(key=_priority_key)
    selected: list[DiscoveryObservation] = []
    selected_keys: set[str] = set()

    def take(observation: DiscoveryObservation) -> None:
        key = _aggregation_key(observation)
        if key in selected_keys or len(selected) >= limit:
            return
        selected.append(observation)
        selected_keys.add(key)

    for observation in values:
        if observation.exact_anchor_matches:
            take(observation)
    all_obligations = _ordered_unique(obligation_id for item in values for obligation_id in item.obligation_ids)
    for obligation_id in all_obligations:
        for observation in values:
            if obligation_id in observation.obligation_ids:
                take(observation)
                break
    for observation in values:
        take(observation)

    selected_ids = {item.id for item in selected}
    for observation in values:
        if observation.id not in selected_ids:
            decisions.append(
                {
                    "observation_id": observation.id,
                    "path": observation.handle.path,
                    "symbol": observation.handle.symbol,
                    "reason": "outside_observation_guardrail",
                }
            )
    return tuple(selected), tuple(decisions)


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
        exact_anchor_matches=_ordered_unique((*left.exact_anchor_matches, *right.exact_anchor_matches)),
        recurrence=max(1, len(query_views)),
        parent_observation_ids=_ordered_unique((*left.parent_observation_ids, *right.parent_observation_ids)),
        relationship_kinds=_ordered_unique((*left.relationship_kinds, *right.relationship_kinds)),
        ambiguity_count=max(left.ambiguity_count, right.ambiguity_count),
    )


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
