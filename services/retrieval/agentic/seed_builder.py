from __future__ import annotations

from typing import Any, Iterable

from services.retrieval.agentic.contracts import InitialLead, RetrievalView, StructuralHandle


def initial_leads_from_observations(observations: Iterable[Any]) -> tuple[InitialLead, ...]:
    """Convert workspace discovery values at the boundary without importing their types."""
    leads: dict[str, InitialLead] = {}
    for observation in observations:
        handle = observation.handle
        views = tuple(
            RetrievalView(
                channel=str(item.retriever),
                query_id=str(item.query_id),
                obligation_ids=tuple(str(value) for value in item.obligation_ids),
                ranks=tuple(int(value) for value in item.ranks),
                scores=tuple(float(value) for value in item.scores),
            )
            for item in observation.provenance
        )
        structural = ()
        if str(handle.node_id):
            structural = (
                StructuralHandle(
                    node_id=str(handle.node_id),
                    symbol=str(handle.symbol),
                    path=str(handle.path),
                    line_start=max(1, int(handle.full_line_start or handle.line_start)),
                    line_end=max(
                        int(handle.full_line_start or handle.line_start),
                        int(handle.full_line_end or handle.line_end),
                    ),
                    kind=str(handle.adapter),
                ),
            )
        lead_id = str(observation.id)
        candidate = InitialLead(
            id=lead_id,
            path=str(handle.path),
            line_start=max(1, int(handle.line_start)),
            line_end=max(int(handle.line_start), int(handle.line_end)),
            preview=str(observation.observed_text)[:1200],
            artifact_kind=str(observation.artifact_role or "other"),
            obligation_ids=tuple(str(value) for value in observation.obligation_ids),
            retrieval_views=views,
            structural_handles=structural,
        )
        previous = leads.get(lead_id)
        if previous is None:
            leads[lead_id] = candidate
            continue
        leads[lead_id] = InitialLead(
            id=previous.id,
            path=previous.path,
            line_start=min(previous.line_start, candidate.line_start),
            line_end=max(previous.line_end, candidate.line_end),
            preview=previous.preview or candidate.preview,
            artifact_kind=previous.artifact_kind,
            obligation_ids=_ordered_unique((*previous.obligation_ids, *candidate.obligation_ids)),
            retrieval_views=tuple(dict.fromkeys((*previous.retrieval_views, *candidate.retrieval_views))),
            structural_handles=tuple(dict.fromkeys((*previous.structural_handles, *candidate.structural_handles))),
        )
    return tuple(sorted(leads.values(), key=_lead_priority))


def _lead_priority(lead: InitialLead) -> tuple[int, int, str, int]:
    ranks = [rank for view in lead.retrieval_views for rank in view.ranks if rank > 0]
    return (min(ranks, default=10000), -len(lead.obligation_ids), lead.path.casefold(), lead.line_start)


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))
