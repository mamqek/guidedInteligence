"""Stage-neutral selection views and incremental admission, not an evidence store.

Adapters preserve the difference between retrieval association and qualified support.
Ranking, eligibility and payload rendering remain explicit stage responsibilities.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from .discovery_observations import DiscoveryObservation
    from .obligation_retrieval import GroundedCandidate


@dataclass(frozen=True)
class SnippetSelectionView:
    id: str
    path: str
    node_id: str
    symbol: str
    line_start: int
    line_end: int
    # Native source segments, not re-rendered or silently expanded source.
    source_segments: tuple[tuple[int, int, str], ...]
    file_role: str
    retrieval_obligations: tuple[str, ...]
    best_rank: int
    best_score: float
    recurrence: int | None
    exact_anchors: tuple[str, ...] | None
    retrieval_provenance: tuple[Mapping[str, Any], ...]
    owner_range: tuple[int, int] | None = None
    outer_owner_id: str = ""
    source_facts: Mapping[str, Any] | None = None
    qualification: str | None = None
    supported_obligations: tuple[str, ...] | None = None
    qualification_reason: str | None = None
    # None means not supplied/inspected, not an empty proven neighborhood.
    connections: tuple[Mapping[str, Any], ...] | None = None
    eligible: bool = True
    ineligibility_reason: str = ""


def discovery_selection_view(item: DiscoveryObservation) -> SnippetSelectionView:
    from dataclasses import asdict

    h = item.handle
    views = item.comparison_source_views or item.source_views
    segments = tuple((v.line_start, v.line_end, v.text) for v in views)
    return SnippetSelectionView(
        id=item.id, path=h.path, node_id=h.node_id, symbol=h.symbol,
        line_start=h.line_start, line_end=h.line_end,
        source_segments=segments or ((h.line_start, h.line_end, item.observed_text),),
        file_role=item.artifact_role, retrieval_obligations=item.obligation_ids,
        best_rank=item.best_rank, best_score=item.best_score, recurrence=item.recurrence,
        exact_anchors=item.exact_anchor_matches,
        retrieval_provenance=tuple(asdict(p) for p in item.provenance),
        owner_range=(h.full_line_start, h.full_line_end) if h.full_line_start else None,
        outer_owner_id=h.outer_node_id,
        connections=tuple({"source_id": parent, "target_id": item.id,
                           "direction": item.relationship_direction, "kinds": item.relationship_kinds}
                          for parent in item.parent_observation_ids) or None,
    )


def qualified_selection_view(
    item: GroundedCandidate, *, identity: str,
    discovery: DiscoveryObservation | None = None,
    connections: Sequence[Mapping[str, Any]] | None = None,
    eligible: bool, ineligibility_reason: str = "",
) -> SnippetSelectionView:
    """Expose qualified state without guessing eligibility or unavailable provenance.

    Not wired into final admission in the initial-admission experiment.
    The caller supplies its identity mapping and stage eligibility explicitly.
    """
    from dataclasses import asdict

    original = discovery_selection_view(discovery) if discovery is not None else None
    provenance = tuple(asdict(p) for p in item.facts.semantic_discoveries)
    ranks = [p.rank for p in item.facts.semantic_discoveries if p.rank > 0]
    return SnippetSelectionView(
        id=identity, path=item.path, node_id=item.node_id, symbol=item.symbol,
        line_start=item.line_start, line_end=item.line_end,
        source_segments=((item.line_start, item.line_end, item.text),),
        file_role=item.file_role,
        retrieval_obligations=(original.retrieval_obligations if original else tuple(dict.fromkeys(
            p.obligation_id for p in item.facts.semantic_discoveries))),
        best_rank=original.best_rank if original else min(ranks, default=10_000),
        best_score=original.best_score if original else item.base_score,
        recurrence=original.recurrence if original else None,
        exact_anchors=original.exact_anchors if original else None,
        retrieval_provenance=original.retrieval_provenance if original else provenance,
        owner_range=tuple(item.facts.full_range) or (original.owner_range if original else None),
        outer_owner_id=original.outer_owner_id if original else "",
        source_facts=asdict(item.facts),
        qualification=("direct_evidence" if item.origin == "qualified_direct_evidence"
                       else "navigation_only" if item.origin == "qualified_navigation_evidence" else None),
        supported_obligations=item.obligation_ids, qualification_reason=item.qualification_reason,
        connections=tuple(connections) if connections is not None else None,
        eligible=eligible, ineligibility_reason=ineligibility_reason,
    )


def discovery_priority(item: SnippetSelectionView) -> tuple[Any, ...]:
    # Same priority as canonical discovery snippets, with an explicit final ID tie-breaker.
    return (0 if item.exact_anchors else 1, -(item.recurrence or 1), item.best_rank,
            -item.best_score, item.path.casefold(), item.line_start, item.id)


@dataclass(frozen=True)
class SnippetAdmission:
    admitted_ids: tuple[str, ...]
    excluded_ids: tuple[str, ...]
    total_input_chars: int
    crossing_id: str
    decisions: tuple[dict[str, Any], ...]


def admit_snippets(
    snippets: Sequence[SnippetSelectionView], *,
    priority: Callable[[SnippetSelectionView, tuple[str, ...]], tuple[Any, ...]],
    measure: Callable[[tuple[str, ...]], int], threshold: int,
) -> SnippetAdmission:
    """Rank and append individual snippets; retain the crossing item, then stop.

    Measure the actual stage request after grouping/serialization. Priority can depend
    on selected identities (e.g. final connectivity); it is not a permanent item score.
    """
    if threshold <= 0:
        raise ValueError("snippet_admission_threshold_must_be_positive")
    if len({item.id for item in snippets}) != len(snippets):
        raise ValueError("snippet_admission_duplicate_identity")
    selected: tuple[str, ...] = ()
    excluded: list[str] = []
    decisions: list[dict[str, Any]] = []
    remaining = list(snippets)
    used_chars = 0
    crossing_id = ""
    while remaining:
        remaining.sort(key=lambda item: (*priority(item, selected), item.id))
        item = remaining.pop(0)
        key = priority(item, selected)
        row = dict(snippet_id=item.id, path=item.path, symbol=item.symbol,
                   ranking_position=len(decisions) + 1, priority=list(key),
                   exact_anchors=item.exact_anchors, recurrence=item.recurrence,
                   best_rank=item.best_rank, best_score=item.best_score,
                   retrieval_obligations=item.retrieval_obligations,
                   qualification=item.qualification, supported_obligations=item.supported_obligations,
                   previous_input_chars=used_chars)
        if not item.eligible:
            row.update(decision="ineligible", reason=item.ineligibility_reason)
            excluded.append(item.id)
        elif crossing_id:
            row.update(decision="excluded_after_budget_crossing", crossing_id=crossing_id)
            excluded.append(item.id)
        else:
            selected = (*selected, item.id)
            measured = measure(selected)
            if measured < 0:
                raise ValueError("snippet_admission_negative_request_cost")
            row.update(decision="admitted", marginal_chars=measured-used_chars,
                       total_input_chars=measured, crossed_budget=measured > threshold)
            used_chars = measured
            if measured > threshold:
                crossing_id = item.id
        decisions.append(row)
    return SnippetAdmission(selected, tuple(excluded), used_chars, crossing_id, tuple(decisions))
