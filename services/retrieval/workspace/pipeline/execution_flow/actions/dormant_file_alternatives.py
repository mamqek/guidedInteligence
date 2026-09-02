from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Sequence

from services.retrieval.workspace.pipeline.execution_flow.actions.models import (
    DormantFileHypothesisStrength,
    InspectDormantFileAlternatives,
)
from services.retrieval.workspace.pipeline.execution_flow.coverage_evaluation import ObligationCoverage
from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import DiscoveryObservation
from services.retrieval.workspace.pipeline.execution_flow.evidence_qualification import QualificationDecision


MAX_DORMANT_FILE_OWNERS = 5
MIN_TITLE_INDEPENDENT_STRUCTURAL_OWNERS = 3
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*")


@dataclass(frozen=True)
class DormantFileQualificationGain:
    retained_observation_ids: tuple[str, ...]
    credited_observation_ids: tuple[str, ...]
    credited_obligation_ids: tuple[str, ...]

    @property
    def productive(self) -> bool:
        return bool(self.credited_observation_ids)

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "productive": self.productive}


def evaluate_dormant_file_qualification_gain(
    action: InspectDormantFileAlternatives,
    *,
    decisions: Sequence[QualificationDecision],
    unresolved_obligation_ids: set[str],
) -> DormantFileQualificationGain:
    """Measure semantic payoff without interpreting qualification prose."""

    by_id = {item.observation_id: item for item in decisions}
    retained: list[str] = []
    credited: list[str] = []
    obligations: list[str] = []
    for observation_id in action.observation_ids:
        decision = by_id.get(observation_id)
        if decision is None or not decision.assessment.is_retained:
            continue
        retained.append(observation_id)
        supported = tuple(
            value
            for value in decision.assessment.individually_established_obligation_ids
            if value in unresolved_obligation_ids
        )
        if supported:
            credited.append(observation_id)
            obligations.extend(supported)
    return DormantFileQualificationGain(
        retained_observation_ids=tuple(retained),
        credited_observation_ids=tuple(credited),
        credited_obligation_ids=tuple(dict.fromkeys(obligations)),
    )


def build_dormant_file_alternatives_action(
    *,
    user_request: str,
    observations: Sequence[DiscoveryObservation],
    decisions: Sequence[QualificationDecision],
    coverage: Sequence[ObligationCoverage],
    attempted_action_ids: set[str],
    action_id_factory: Any,
) -> tuple[InspectDormantFileAlternatives | None, tuple[dict[str, Any], ...]]:
    """Return the best bounded zero-qualified file inspection and its audit."""

    unresolved = {
        item.obligation_id for item in coverage if item.status not in {"covered", "external"}
    }
    decision_by_id = {item.observation_id: item for item in decisions}
    retained_paths = {
        observation.handle.path.casefold()
        for observation in observations
        if observation.handle.path
        and (decision := decision_by_id.get(observation.id)) is not None
        and decision.assessment.is_retained
    }
    grouped: dict[str, list[DiscoveryObservation]] = {}
    for observation in observations:
        path = observation.handle.path
        if not path or path.casefold() in retained_paths:
            continue
        decision = decision_by_id.get(observation.id)
        if decision is not None and decision.assessment.is_retained:
            continue
        if not (set(observation.obligation_ids) & unresolved):
            continue
        grouped.setdefault(path.casefold(), []).append(observation)

    request_terms = _terms(user_request)
    title_terms = _title_terms(user_request)
    ranked_files: list[
        tuple[tuple[Any, ...], str, list[DiscoveryObservation], dict[str, Any]]
    ] = []
    audit: list[dict[str, Any]] = []
    for normalized_path, members in grouped.items():
        distinct = _distinct_owners(members)
        obligations = {value for item in distinct for value in item.obligation_ids if value in unresolved}
        exact = any(item.exact_anchor_matches for item in distinct)
        request_support = max(
            (len(_terms(item.handle.symbol) & request_terms) for item in distinct),
            default=0,
        )
        path_support = len(_terms(normalized_path) & request_terms)
        title_owner_support = max(
            (len(_terms(item.handle.symbol) & title_terms) for item in distinct),
            default=0,
        )
        title_path_support = len(_terms(normalized_path) & title_terms)
        structural_owner_count = sum(
            bool(item.handle.node_id and item.handle.symbol) for item in distinct
        )
        admitted_members = [
            item for item in distinct
            if item.initial_admission is not None
            and item.initial_admission.decision == "admitted"
        ]
        initial_positions = [
            item.initial_admission.ranking_position
            for item in distinct
            if item.initial_admission is not None and item.initial_admission.ranking_position > 0
        ]
        crossing_positions = [
            item.initial_admission.budget_crossing_position
            for item in distinct
            if item.initial_admission is not None
            and item.initial_admission.budget_crossing_position > 0
        ]
        test_artifact = all(
            item.artifact_role == "test" or "/test" in f"/{item.handle.path.casefold()}"
            for item in distinct
        )
        # A compact set of independently retrieved structural owners is itself a
        # grounded file hypothesis. Request/title overlap can ground a smaller
        # two-owner hypothesis, but its absence must not veto stronger retrieval
        # evidence such as the BuilderState cluster seen in TypeScript 35468.
        retrieval_grounded_support = (
            structural_owner_count >= MIN_TITLE_INDEPENDENT_STRUCTURAL_OWNERS
        )
        lexical_owner_support = title_owner_support > 0 or request_support >= 2
        grounded_owner_support = retrieval_grounded_support or lexical_owner_support
        eligible = (
            len(distinct) >= 2
            and (len(obligations) >= 2 or exact)
            and grounded_owner_support
        )
        action_id = action_id_factory("dormant_file_alternatives", normalized_path)
        reason = (
            "eligible"
            if eligible and action_id not in attempted_action_ids
            else "already_attempted"
            if action_id in attempted_action_ids
            else "insufficient_distinct_owner_or_query_support"
        )
        audit_record = {
            "path": distinct[0].handle.path if distinct else normalized_path,
            "distinct_owner_count": len(distinct),
            "unresolved_obligation_count": len(obligations),
            "exact_anchor": exact,
            "request_term_support": request_support,
            "path_term_support": path_support,
            "title_owner_support": title_owner_support,
            "title_path_support": title_path_support,
            "structural_owner_count": structural_owner_count,
            "initial_admitted_owner_count": len(admitted_members),
            "best_initial_ranking_position": min(initial_positions, default=0),
            "budget_crossing_position": min(crossing_positions, default=0),
            "coverage_reserved_owner_count": sum(
                bool(item.initial_admission and item.initial_admission.coverage_reserved)
                for item in distinct
            ),
            "retrieval_grounded_support": retrieval_grounded_support,
            "lexical_owner_support": lexical_owner_support,
            "test_artifact": test_artifact,
            "grounded_owner_support": grounded_owner_support,
            "decision": reason,
            "action_id": action_id,
        }
        audit.append(audit_record)
        if not eligible or action_id in attempted_action_ids:
            continue
        # Grounding and ranking are deliberately separate. Exact anchors are the
        # strongest hypotheses, independently grounded structural clusters come
        # next, and smaller lexically grounded hypotheses come last. Within a
        # grounding tier all available evidence remains visible. This prevents a
        # two-owner lexical hypothesis from categorically outranking a recurrent
        # structural cluster while retaining lexical disambiguation between two
        # otherwise small hypotheses.
        grounding_tier = 0 if retrieval_grounded_support else 1
        if retrieval_grounded_support:
            within_tier_rank = (
                -min(structural_owner_count, MAX_DORMANT_FILE_OWNERS),
                -len(obligations),
                -sum(
                    sorted((min(item.recurrence, 3) for item in distinct), reverse=True)[
                        :MAX_DORMANT_FILE_OWNERS
                    ]
                ),
                min((item.best_rank for item in distinct), default=10_000),
                -max((item.best_score for item in distinct), default=0.0),
                -title_owner_support,
                -request_support,
            )
        else:
            within_tier_rank = (
                -title_owner_support,
                -request_support,
                min((item.best_rank for item in distinct), default=10_000),
                -max((item.best_score for item in distinct), default=0.0),
                -len(obligations),
                -min(structural_owner_count, MAX_DORMANT_FILE_OWNERS),
            )
        ranked_files.append((
            (
                0 if exact else 1,
                1 if test_artifact else 0,
                grounding_tier,
                *within_tier_rank,
                -title_path_support,
                -path_support,
                normalized_path,
            ),
            action_id,
            distinct,
            audit_record,
        ))
    if not ranked_files:
        return None, tuple(audit)

    winner = min(ranked_files, key=lambda item: item[0])
    winner = _admission_consistency_challenger(winner, ranked_files)
    _rank, action_id, members, selected_audit = winner
    selected_audit["selected"] = True
    selected = _select_owners(
        members,
        request_terms=request_terms,
        unresolved=unresolved,
    )
    return InspectDormantFileAlternatives(
        id=action_id,
        path=selected[0].handle.path,
        observation_ids=tuple(item.id for item in selected),
        reason=f"Inspect {len(selected)} already-retrieved owners from one zero-qualified file.",
        priority=-1000,
        scope_id=f"dormant_file:{selected[0].handle.path.casefold()}",
        hypothesis_strength=DormantFileHypothesisStrength(
            title_owner_support=int(selected_audit["title_owner_support"]),
            request_owner_support=int(selected_audit["request_term_support"]),
            structural_owner_count=int(selected_audit["structural_owner_count"]),
        ),
    ), tuple(audit)


def _admission_consistency_challenger(
    winner: tuple[tuple[Any, ...], str, list[DiscoveryObservation], dict[str, Any]],
    ranked_files: Sequence[
        tuple[tuple[Any, ...], str, list[DiscoveryObservation], dict[str, Any]]
    ],
) -> tuple[tuple[Any, ...], str, list[DiscoveryObservation], dict[str, Any]]:
    """Correct a narrow contradiction between initial admission and dormant rank.

    A zero-admitted metadata winner may yield to an earlier, admitted structural
    hypothesis only when the challenger is at least as well grounded and is not
    lexically weaker. This preserves the original rank unless pre-comparison
    admission provides concrete contradictory evidence.
    """

    winner_audit = winner[3]
    if int(winner_audit.get("initial_admitted_owner_count") or 0) > 0:
        return winner
    winner_position = int(winner_audit.get("best_initial_ranking_position") or 0) or 10_000
    eligible = [
        item
        for item in ranked_files
        if item is not winner
        and int(item[3].get("initial_admitted_owner_count") or 0) > 0
        and 0 < int(item[3].get("best_initial_ranking_position") or 0) < winner_position
        and int(item[3].get("structural_owner_count") or 0)
        >= int(winner_audit.get("structural_owner_count") or 0)
        and int(item[3].get("title_owner_support") or 0)
        >= int(winner_audit.get("title_owner_support") or 0)
        and int(item[3].get("request_term_support") or 0)
        >= int(winner_audit.get("request_term_support") or 0)
        and (
            int(item[3].get("title_owner_support") or 0)
            > int(winner_audit.get("title_owner_support") or 0)
            or int(item[3].get("request_term_support") or 0)
            > int(winner_audit.get("request_term_support") or 0)
        )
    ]
    if not eligible:
        return winner
    selected = min(
        eligible,
        key=lambda item: (
            -int(item[3].get("title_owner_support") or 0),
            -int(item[3].get("request_term_support") or 0),
            -int(item[3].get("structural_owner_count") or 0),
            int(item[3].get("best_initial_ranking_position") or 10_000),
            str(item[3].get("path") or "").casefold(),
        ),
    )
    selected[3]["selection_adjustment"] = "initial_admission_consistency_challenger"
    selected[3]["displaced_path"] = str(winner_audit.get("path") or "")
    return selected


def _distinct_owners(members: Sequence[DiscoveryObservation]) -> list[DiscoveryObservation]:
    result: dict[tuple[str, int, int], DiscoveryObservation] = {}
    for item in members:
        key = (
            item.handle.node_id or item.handle.symbol or item.id,
            item.handle.full_line_start or item.handle.line_start,
            item.handle.full_line_end or item.handle.line_end,
        )
        previous = result.get(key)
        if previous is None or _observation_rank(item, set()) < _observation_rank(previous, set()):
            result[key] = item
    return list(result.values())


def _select_owners(
    members: Sequence[DiscoveryObservation],
    *,
    request_terms: set[str],
    unresolved: set[str],
    limit: int = MAX_DORMANT_FILE_OWNERS,
) -> list[DiscoveryObservation]:
    remaining = sorted(members, key=lambda item: _observation_rank(item, request_terms))
    selected: list[DiscoveryObservation] = []
    represented: set[str] = set()
    while remaining and len(selected) < limit:
        remaining.sort(key=lambda item: (
            -len((set(item.obligation_ids) & unresolved) - represented),
            *_observation_rank(item, request_terms),
        ))
        item = remaining.pop(0)
        selected.append(item)
        represented.update(set(item.obligation_ids) & unresolved)
    return selected


def _observation_rank(item: DiscoveryObservation, request_terms: set[str]) -> tuple[Any, ...]:
    symbol_terms = _terms(item.handle.symbol)
    span = (item.handle.full_line_end or item.handle.line_end) - (
        item.handle.full_line_start or item.handle.line_start
    ) + 1
    return (
        0 if item.exact_anchor_matches else 1,
        -len(symbol_terms & request_terms),
        item.best_rank,
        -item.best_score,
        -min(span, 120),
        item.handle.line_start,
        item.id,
    )


def _terms(value: str) -> set[str]:
    terms: set[str] = set()
    for token in _WORD_RE.findall(value.replace("_", " ")):
        normalized = token.casefold().rstrip("s")
        if normalized:
            terms.add(normalized)
        if normalized.endswith("op"):
            terms.add("op")
    return terms


def _title_terms(user_request: str) -> set[str]:
    match = re.search(r"(?im)^\s*Title:\s*(.+)$", user_request)
    if match is not None:
        return _terms(match.group(1))
    first_nonempty = next((line for line in user_request.splitlines() if line.strip()), user_request)
    return _terms(first_nonempty)
