from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import DiscoveryObservation


@dataclass(frozen=True)
class InitialFileRanking:
    ranked_paths: tuple[str, ...]
    path_details: tuple[dict[str, object], ...]


def rank_initial_files(
    snippets: Sequence[DiscoveryObservation],
) -> InitialFileRanking:
    """Rank canonical snippet files once without binary coverage promotion."""
    by_path: dict[str, list[DiscoveryObservation]] = {}
    display_path: dict[str, str] = {}
    for snippet in snippets:
        key = snippet.handle.path.casefold()
        by_path.setdefault(key, []).append(snippet)
        display_path.setdefault(key, snippet.handle.path)

    def path_priority(path: str) -> tuple[object, ...]:
        values = by_path[path]
        obligations = {value for item in values for value in item.obligation_ids}
        return (
            0 if any(item.exact_anchor_matches for item in values) else 1,
            min((item.best_rank for item in values), default=10_000),
            -max((item.best_score for item in values), default=0.0),
            -len(obligations),
            -max((item.recurrence for item in values), default=1),
            path,
        )

    ordered = sorted(by_path, key=path_priority)
    ranked = tuple(ordered)
    details = tuple(
        {
            "path": display_path[path],
            "canonical_snippet_count": len(by_path[path]),
            "obligation_ids": sorted({value for item in by_path[path] for value in item.obligation_ids}),
            "exact_anchor": any(item.exact_anchor_matches for item in by_path[path]),
            "best_rank": min((item.best_rank for item in by_path[path]), default=10_000),
            "best_score": max((item.best_score for item in by_path[path]), default=0.0),
            "max_recurrence": max((item.recurrence for item in by_path[path]), default=1),
            "coverage_reserved": False,
        }
        for path in ranked
    )
    return InitialFileRanking(
        ranked_paths=tuple(display_path[path] for path in ranked),
        path_details=details,
    )
