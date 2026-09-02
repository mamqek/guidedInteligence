from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import re
from typing import Any, Mapping, Sequence

from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import DiscoveryObservation
from services.retrieval.workspace.pipeline.execution_flow.evidence_qualification import QualificationDecision


MAX_CHALLENGERS_PER_FILE = 3
_TERM_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*")
_CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_NOISE_TERMS = frozenset({
    "actual", "arith", "code", "comp", "concrete", "evidence", "file", "flex",
    "function", "information", "method", "missing", "owner", "repository",
    "show", "source", "that", "the", "this", "what", "where", "which", "with",
    "wrapper",
})


@dataclass(frozen=True)
class OwnerRepresentationGroup:
    id: str
    path: str
    obligation_id: str
    primary_observation_id: str
    complementary_observation_ids: tuple[str, ...]
    challenger_observation_ids: tuple[str, ...]
    rejected_observation_ids: tuple[str, ...]
    election_reason: str
    previous_primary_observation_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OwnerChallengerBatch:
    path: str
    obligation_ids: tuple[str, ...]
    primary_observation_ids: tuple[str, ...]
    challenger_observation_ids: tuple[str, ...]
    priority: int


@dataclass(frozen=True)
class OwnerRepresentationSelection:
    groups: tuple[OwnerRepresentationGroup, ...]
    primary_counts: Mapping[str, int]
    challenger_batches: tuple[OwnerChallengerBatch, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "groups": [item.to_dict() for item in self.groups],
            "primary_counts": dict(self.primary_counts),
            "challenger_batches": [asdict(item) for item in self.challenger_batches],
        }


def build_owner_representations(
    observations: Sequence[DiscoveryObservation],
    decisions: Sequence[QualificationDecision],
    *,
    previous: OwnerRepresentationSelection | None = None,
) -> OwnerRepresentationSelection:
    """Elect qualified file/obligation owners and nominate undisclosed challengers.

    Retrieval obligation IDs can nominate a challenger, but only qualification
    contributions can elect a primary. No evidence is removed by this stage.
    """

    observation_by_id = {item.id: item for item in observations}
    decision_by_id = {item.observation_id: item for item in decisions}
    previous_primary = {
        (item.path.casefold(), item.obligation_id): item.primary_observation_id
        for item in (previous.groups if previous is not None else ())
    }
    qualified_groups: dict[tuple[str, str], list[str]] = {}
    for observation_id, decision in decision_by_id.items():
        observation = observation_by_id.get(observation_id)
        if observation is None or not observation.handle.path or not decision.assessment.is_retained:
            continue
        for obligation_id in decision.assessment.contributing_obligation_ids:
            qualified_groups.setdefault(
                (observation.handle.path.casefold(), obligation_id), []
            ).append(observation_id)

    groups: list[OwnerRepresentationGroup] = []
    for (normalized_path, obligation_id), qualified_ids in sorted(qualified_groups.items()):
        ordered_qualified = tuple(sorted(
            dict.fromkeys(qualified_ids),
            key=lambda value: _qualified_owner_key(
                observation_by_id[value], decision_by_id[value], obligation_id
            ),
        ))
        primary = ordered_qualified[0]
        primary_observation = observation_by_id[primary]
        primary_decision = decision_by_id[primary]
        lead_terms = _terms(" ".join((
            primary_observation.handle.symbol,
            primary_decision.rationale.local_follow_up,
            *primary_decision.rationale.missing_information,
        )))
        challengers = tuple(
            item.id
            for item in sorted(
                (
                    item
                    for item in observations
                    if item.handle.path.casefold() == normalized_path
                    and obligation_id in item.obligation_ids
                    and item.id not in decision_by_id
                    and bool(item.handle.node_id and item.handle.symbol)
                    and item.artifact_role == "implementation"
                    and _challenger_relevance(item, lead_terms) > 0
                ),
                key=lambda item: _challenger_key(item, lead_terms),
            )[:MAX_CHALLENGERS_PER_FILE]
        )
        rejected = tuple(sorted(
            item.id
            for item in observations
            if item.handle.path.casefold() == normalized_path
            and obligation_id in item.obligation_ids
            and (decision := decision_by_id.get(item.id)) is not None
            and decision.assessment.is_rejected
        ))
        path = observation_by_id[primary].handle.path
        prior = previous_primary.get((normalized_path, obligation_id), "")
        groups.append(OwnerRepresentationGroup(
            id=_group_id(normalized_path, obligation_id),
            path=path,
            obligation_id=obligation_id,
            primary_observation_id=primary,
            complementary_observation_ids=ordered_qualified[1:],
            challenger_observation_ids=challengers,
            rejected_observation_ids=rejected,
            election_reason=(
                "qualified_challenger_replaced_primary"
                if prior and prior != primary
                else "qualified_primary_preserved"
                if prior == primary
                else "initial_qualified_primary"
            ),
            previous_primary_observation_id=prior,
        ))

    primary_counts: dict[str, int] = {}
    for group in groups:
        primary_counts[group.primary_observation_id] = primary_counts.get(group.primary_observation_id, 0) + 1

    batches_by_path: dict[str, dict[str, Any]] = {}
    for group in groups:
        if not group.challenger_observation_ids:
            continue
        value = batches_by_path.setdefault(group.path.casefold(), {
            "path": group.path,
            "obligations": [],
            "primaries": [],
            "challengers": [],
        })
        value["obligations"].append(group.obligation_id)
        value["primaries"].append(group.primary_observation_id)
        value["challengers"].extend(group.challenger_observation_ids)

    batches: list[OwnerChallengerBatch] = []
    for value in batches_by_path.values():
        challenger_ids = tuple(dict.fromkeys(value["challengers"]))[:MAX_CHALLENGERS_PER_FILE]
        if not challenger_ids:
            continue
        best = min((observation_by_id[item] for item in challenger_ids), key=_challenger_key)
        batches.append(OwnerChallengerBatch(
            path=value["path"],
            obligation_ids=tuple(dict.fromkeys(value["obligations"])),
            primary_observation_ids=tuple(dict.fromkeys(value["primaries"])),
            challenger_observation_ids=challenger_ids,
            priority=_challenger_priority(best, len(set(value["obligations"]))),
        ))
    batches.sort(key=lambda item: (item.priority, item.path.casefold()))
    return OwnerRepresentationSelection(
        groups=tuple(groups),
        primary_counts=primary_counts,
        challenger_batches=tuple(batches),
    )


def _qualified_owner_key(
    observation: DiscoveryObservation,
    decision: QualificationDecision,
    obligation_id: str,
) -> tuple[Any, ...]:
    assessment = decision.assessment
    return (
        0 if obligation_id in assessment.individually_established_obligation_ids else 1,
        0 if assessment.is_direct_fact else 1,
        0 if observation.exact_anchor_matches else 1,
        -len(assessment.contributing_obligation_ids),
        -observation.recurrence,
        observation.best_rank,
        -observation.best_score,
        observation.handle.line_start,
        observation.id,
    )


def _challenger_key(
    observation: DiscoveryObservation,
    lead_terms: set[str] | None = None,
) -> tuple[Any, ...]:
    return (
        0 if observation.exact_anchor_matches else 1,
        -_challenger_relevance(observation, lead_terms or set()),
        0 if observation.admission_reason == "same_path_alternative" else 1,
        -observation.recurrence,
        observation.best_rank,
        -observation.best_score,
        observation.handle.line_start,
        observation.id,
    )


def _challenger_relevance(observation: DiscoveryObservation, lead_terms: set[str]) -> int:
    if observation.exact_anchor_matches:
        return 100 + len(observation.exact_anchor_matches)
    return len(_terms(observation.handle.symbol) & lead_terms)


def _challenger_priority(observation: DiscoveryObservation, obligation_count: int) -> int:
    return (
        (0 if observation.exact_anchor_matches else 10_000)
        + max(observation.best_rank, 1) * 100
        - min(observation.recurrence, 9) * 10
        - min(obligation_count, 9)
    )


def _group_id(path: str, obligation_id: str) -> str:
    digest = hashlib.sha1(f"{path}\0{obligation_id}".encode("utf-8")).hexdigest()[:16]
    return f"owner_representation_{digest}"


def _terms(value: str) -> set[str]:
    expanded = _CAMEL_RE.sub(" ", value.replace("_", " ").replace("::", " "))
    return {
        term
        for token in _TERM_RE.findall(expanded)
        if (term := token.casefold().rstrip("s")) and term not in _NOISE_TERMS
    }
