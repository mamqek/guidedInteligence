from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Mapping, Sequence

from services.retrieval.workspace.pipeline.execution_flow.evidence_qualification import QualificationDecision


@dataclass(frozen=True)
class FileTraceSeed:
    path: str
    source_path: str
    source_observation_id: str
    endpoint_observation_id: str
    endpoint_symbol: str
    action_id: str
    obligation_id: str
    relationship_direction: str
    relationship_kinds: tuple[str, ...]
    connection_summary: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class FileTraceEvidence:
    """A structural file participant, deliberately distinct from source snippets."""

    path: str
    source_path: str
    source_observation_id: str
    endpoint_observation_id: str
    endpoint_symbol: str
    source_island_id: str
    action_id: str
    obligation_id: str
    relationship_direction: str
    relationship_kinds: tuple[str, ...]
    endpoint_qualification: str
    reason: str
    connection_summary: Mapping[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def build_file_trace_evidence(
    seeds: Sequence[FileTraceSeed],
    decisions: Sequence[QualificationDecision],
    observation_to_island: Mapping[str, str],
    *,
    max_traces: int | None = None,
) -> tuple[FileTraceEvidence, ...]:
    """Retain bounded file-level provenance without admitting synthetic snippets."""
    if max_traces is not None and max_traces <= 0:
        return ()
    decision_by_id = {item.observation_id: item for item in decisions}
    traces: list[FileTraceEvidence] = []
    seen: set[tuple[str, str]] = set()
    for seed in seeds:
        path = seed.path.replace("\\", "/").lstrip("./")
        source_path = seed.source_path.replace("\\", "/").lstrip("./")
        decision = decision_by_id.get(seed.source_observation_id)
        endpoint_decision = decision_by_id.get(seed.endpoint_observation_id)
        island_id = str(observation_to_island.get(seed.source_observation_id) or "")
        if (
            not path
            or not island_id
            or decision is None
            or decision.disposition != "promote"
            or decision.support_level not in {"direct_evidence", "navigation_only"}
        ):
            continue
        key = (path.casefold(), island_id)
        if key in seen:
            continue
        seen.add(key)
        kinds = tuple(dict.fromkeys(value for value in seed.relationship_kinds if value))
        relationship = "/".join(kinds) or "structural"
        endpoint_qualification = (
            f"{endpoint_decision.disposition}/{endpoint_decision.support_level}"
            if endpoint_decision is not None
            else "not_qualified"
        )
        owner = seed.endpoint_symbol or "no exact destination owner"
        endpoint_statement = (
            f"{owner} was qualified as {endpoint_qualification}; the exact owner supporting the requested behavior remains unresolved."
            if endpoint_decision is not None
            else "CodeGraph established repeated direct file-to-file calls, but no exact destination snippet was localized."
        )
        traces.append(
            FileTraceEvidence(
                path=path,
                source_path=source_path,
                source_observation_id=seed.source_observation_id,
                endpoint_observation_id=seed.endpoint_observation_id,
                endpoint_symbol=seed.endpoint_symbol,
                source_island_id=island_id,
                action_id=seed.action_id,
                obligation_id=seed.obligation_id,
                relationship_direction=seed.relationship_direction,
                relationship_kinds=kinds,
                endpoint_qualification=endpoint_qualification,
                connection_summary=dict(seed.connection_summary),
                reason=(
                    f"{source_path or 'The qualified source file'} reaches {path} through a represented "
                    f"{seed.relationship_direction} {relationship} handoff for unresolved obligation "
                    f"{seed.obligation_id}. {endpoint_statement}"
                ),
            )
        )
        if max_traces is not None and len(traces) >= max_traces:
            break
    return tuple(traces)
