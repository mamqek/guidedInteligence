from __future__ import annotations

from dataclasses import dataclass
import json
import re
import time
from typing import Any, Callable, Mapping, Sequence

from services.intent.contracts import INTENT_CONTRACTS
from services.intent.logging import IntentStageResult
from services.intent.models import (
    EvidenceBoundary,
    EvidenceRole,
    EvidenceSource,
    IntentClassificationInput,
    TaskIntent,
    classification_from_mapping,
)
from services.intent.prompts import PROMPT_PATH, STAGE_GROUPS_PROMPT_PATH, STAGE_REQUIREMENTS_PROMPT_PATH
from services.intent.schema import intent_response_format, stage_group_response_format, stage_requirement_response_format
from services.llm.json_completion import complete_json


EXPLICIT_PATH_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_./\\-])"
    r"(?:[A-Za-z]:[\\/])?"
    r"(?:\.{1,2}[\\/])?"
    r"[A-Za-z0-9_@()+.-]+(?:[\\/][A-Za-z0-9_@()+.-]+)+\.[A-Za-z0-9_+-]+"
)
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*$")
NAMED_TYPE_PATTERN = re.compile(
    r"\b([A-Z][A-Za-z0-9_$]*)\s+type\b"
)
CAMEL_CALL_PATTERN = re.compile(r"\b([a-z_$][A-Za-z0-9_$]*[A-Z][A-Za-z0-9_$]*)\s*\(")

JsonCompletion = Callable[..., Mapping[str, Any]]


@dataclass(frozen=True)
class _StagePolicy:
    evidence_source: EvidenceSource = EvidenceSource.REPOSITORY
    evidence_role: EvidenceRole = EvidenceRole.ANY
    depends_on: tuple[str, ...] = ()
    requires_repository_handoff: bool = False


_STAGE_POLICIES: dict[str, _StagePolicy] = {
    "explain.subject": _StagePolicy(evidence_role=EvidenceRole.IMPLEMENTATION),
    "explain.trigger": _StagePolicy(evidence_role=EvidenceRole.IMPLEMENTATION),
    "explain.ordered_mechanism": _StagePolicy(
        evidence_role=EvidenceRole.IMPLEMENTATION,
        depends_on=("explain.trigger",),
        requires_repository_handoff=True,
    ),
    "explain.state_changes": _StagePolicy(
        evidence_role=EvidenceRole.IMPLEMENTATION,
        depends_on=("explain.ordered_mechanism",),
        requires_repository_handoff=True,
    ),
    "explain.resulting_effect": _StagePolicy(
        depends_on=("explain.state_changes",),
        requires_repository_handoff=True,
    ),
    "explain.why": _StagePolicy(
        evidence_role=EvidenceRole.IMPLEMENTATION,
        depends_on=("explain.ordered_mechanism", "explain.resulting_effect"),
        requires_repository_handoff=True,
    ),
    "debug.symptom": _StagePolicy(evidence_source=EvidenceSource.PROMPT),
    "debug.expected_actual": _StagePolicy(evidence_source=EvidenceSource.PROMPT),
    "debug.cause": _StagePolicy(
        evidence_role=EvidenceRole.IMPLEMENTATION,
        depends_on=("debug.evidence",),
        requires_repository_handoff=True,
    ),
    "verify.claim": _StagePolicy(evidence_source=EvidenceSource.PROMPT),
    "use.goal": _StagePolicy(evidence_source=EvidenceSource.PROMPT),
    "plan.goal": _StagePolicy(evidence_source=EvidenceSource.PROMPT),
    "review.scope": _StagePolicy(evidence_source=EvidenceSource.PROMPT),
    "change.affected_paths": _StagePolicy(
        depends_on=("change.change_surface",),
        requires_repository_handoff=True,
    ),
    "use.result": _StagePolicy(
        depends_on=("use.invocation",),
        requires_repository_handoff=True,
    ),
    "verify.result": _StagePolicy(
        depends_on=("verify.evidence",),
        requires_repository_handoff=True,
    ),
}


def classify_intent(
    classification_input: IntentClassificationInput,
    *,
    llm_config: Any,
    complete_json_fn: JsonCompletion = complete_json,
) -> IntentStageResult:
    started_at = time.perf_counter()
    model = str(getattr(llm_config, "model", "") or "")
    try:
        analysis = complete_json_fn(
            llm_config,
            _messages(classification_input),
            response_format=intent_response_format(),
        )
        analysis = _normalize_intent_decisions(analysis)
        analysis = _preserve_explicit_prompt_anchors(analysis, classification_input.user_prompt)
        selected_intents = _selected_intents(analysis)
        stage_ids = _selected_stage_ids(selected_intents)
        stage_response = complete_json_fn(
            llm_config,
            _stage_requirement_messages(classification_input, analysis, selected_intents),
            response_format=stage_requirement_response_format(
                stage_ids,
                symbol_candidates=_anchor_values(analysis, "symbols"),
            ),
        )
        analysis = _apply_symbol_decisions(analysis, stage_response)
        stage_groups = _self_stage_groups(stage_ids)
        if len(selected_intents) > 1:
            stage_groups = complete_json_fn(
                llm_config,
                _stage_group_messages(classification_input, selected_intents, stage_response),
                response_format=stage_group_response_format(
                    stage_ids,
                    allowed_leaders=_compatible_group_leaders(stage_ids, stage_response),
                ),
            )
        response = {
            **analysis,
            "evidence_obligations": _build_stage_obligations(
                stage_response,
                stage_groups=stage_groups,
                stage_ids=stage_ids,
                known_anchors=_known_anchors(analysis),
            ),
        }
        classification = classification_from_mapping(response)
        return IntentStageResult(
            status="success",
            classification=classification,
            error=None,
            fallback_used=False,
            latency_ms=_elapsed_ms(started_at),
            classifier_model=model,
        )
    except Exception as exc:
        return IntentStageResult(
            status="failed",
            classification=None,
            error=f"{type(exc).__name__}: {exc}",
            fallback_used=False,
            latency_ms=_elapsed_ms(started_at),
            classifier_model=model,
        )


def _messages(classification_input: IntentClassificationInput) -> Sequence[Mapping[str, str]]:
    payload = classification_input.to_dict()
    payload["intent_contracts"] = {
        intent.value: {"retrieval_description": contract.retrieval_description}
        for intent, contract in INTENT_CONTRACTS.items()
    }
    return (
        {"role": "system", "content": PROMPT_PATH.read_text(encoding="utf-8")},
        {"role": "user", "content": json.dumps(payload, sort_keys=True)},
    )


def _stage_requirement_messages(
    classification_input: IntentClassificationInput,
    analysis: Mapping[str, Any],
    selected_intents: Sequence[TaskIntent],
) -> Sequence[Mapping[str, str]]:
    payload = {
        "request": classification_input.to_dict(),
        "selected_intents": [intent.value for intent in selected_intents],
        "anchors": analysis.get("anchors", {}),
        "stages": [
            {
                "id": stage.id,
                "purpose": stage.purpose,
                "evidence_role": _STAGE_POLICIES.get(stage.id, _StagePolicy()).evidence_role.value,
                "evidence_source": _STAGE_POLICIES.get(stage.id, _StagePolicy()).evidence_source.value,
            }
            for intent in selected_intents
            for stage in INTENT_CONTRACTS[intent].stages
        ],
    }
    return (
        {"role": "system", "content": STAGE_REQUIREMENTS_PROMPT_PATH.read_text(encoding="utf-8")},
        {"role": "user", "content": json.dumps(payload, sort_keys=True)},
    )


def _stage_group_messages(
    classification_input: IntentClassificationInput,
    selected_intents: Sequence[TaskIntent],
    stage_response: Mapping[str, Any],
) -> Sequence[Mapping[str, str]]:
    requirements_value = stage_response.get("stage_requirements")
    requirements = dict(requirements_value) if isinstance(requirements_value, Mapping) else {}
    payload = {
        "request": {
            "user_prompt": classification_input.user_prompt,
            "repository_name": classification_input.repository_name,
        },
        "selected_intents": [intent.value for intent in selected_intents],
        "stages": [
            {
                "id": stage.id,
                "purpose": stage.purpose,
                "evidence_role": _STAGE_POLICIES.get(stage.id, _StagePolicy()).evidence_role.value,
                "evidence_source": _STAGE_POLICIES.get(stage.id, _StagePolicy()).evidence_source.value,
                "requirement": requirements.get(stage.id, {}),
            }
            for intent in selected_intents
            for stage in INTENT_CONTRACTS[intent].stages
        ],
    }
    return (
        {"role": "system", "content": STAGE_GROUPS_PROMPT_PATH.read_text(encoding="utf-8")},
        {"role": "user", "content": json.dumps(payload, sort_keys=True)},
    )


def _self_stage_groups(stage_ids: Sequence[str]) -> dict[str, Any]:
    return {
        "stage_groups": {
            stage_id: {"evidence_group_leader": stage_id}
            for stage_id in stage_ids
        }
    }


def _compatible_group_leaders(
    stage_ids: Sequence[str],
    stage_response: Mapping[str, Any],
) -> dict[str, list[str]]:
    requirements_value = stage_response.get("stage_requirements")
    requirements = dict(requirements_value) if isinstance(requirements_value, Mapping) else {}
    ordered_ids = list(dict.fromkeys(stage_ids))
    result: dict[str, list[str]] = {}
    for index, stage_id in enumerate(ordered_ids):
        requirement_value = requirements.get(stage_id)
        requirement = dict(requirement_value) if isinstance(requirement_value, Mapping) else {}
        compatible = []
        for candidate in ordered_ids[:index]:
            if candidate.partition(".")[0] == stage_id.partition(".")[0]:
                continue
            candidate_value = requirements.get(candidate)
            candidate_requirement = dict(candidate_value) if isinstance(candidate_value, Mapping) else {}
            try:
                _validate_group_compatibility(stage_id, candidate, requirement, candidate_requirement)
            except ValueError:
                continue
            compatible.append(candidate)
        result[stage_id] = compatible + [stage_id]
    return result


def _normalize_intent_decisions(response: Mapping[str, Any]) -> dict[str, Any]:
    decisions_value = response.get("intent_decisions")
    decisions = dict(decisions_value) if isinstance(decisions_value, Mapping) else {}
    intents: list[str] = []
    basis: list[str] = []
    for intent in TaskIntent:
        decision_value = decisions.get(intent.value)
        decision = dict(decision_value) if isinstance(decision_value, Mapping) else {}
        if bool(decision.get("selected")):
            intents.append(intent.value)
            reason = str(decision.get("reason") or "").strip()
            if reason:
                basis.append(reason)
    if not intents:
        raise ValueError("Intent classification returned no selected task intent.")
    return {
        **response,
        "intents": intents,
        "classification_basis": basis[:8],
    }


def _selected_intents(response: Mapping[str, Any]) -> tuple[TaskIntent, ...]:
    selected = {str(value) for value in response.get("intents", ())}
    return tuple(intent for intent in TaskIntent if intent.value in selected)


def _selected_stage_ids(intents: Sequence[TaskIntent]) -> tuple[str, ...]:
    return tuple(stage.id for intent in intents for stage in INTENT_CONTRACTS[intent].stages)


def _build_stage_obligations(
    response: Mapping[str, Any],
    *,
    stage_groups: Mapping[str, Any],
    stage_ids: Sequence[str],
    known_anchors: set[str],
) -> list[dict[str, Any]]:
    requirements_value = response.get("stage_requirements")
    requirements = dict(requirements_value) if isinstance(requirements_value, Mapping) else {}
    groups_value = stage_groups.get("stage_groups")
    groups = dict(groups_value) if isinstance(groups_value, Mapping) else {}
    ordered_stage_ids = tuple(stage_ids)
    stage_positions = {stage_id: index for index, stage_id in enumerate(ordered_stage_ids)}
    leaders: dict[str, str] = {}
    normalized_requirements: dict[str, dict[str, Any]] = {}
    for stage_id in ordered_stage_ids:
        requirement_value = requirements.get(stage_id)
        requirement = dict(requirement_value) if isinstance(requirement_value, Mapping) else {}
        group_value = groups.get(stage_id)
        group = dict(group_value) if isinstance(group_value, Mapping) else {}
        leader = str(group.get("evidence_group_leader") or "").strip()
        if leader not in stage_positions or stage_positions[leader] > stage_positions[stage_id]:
            raise ValueError(f"Request analysis returned invalid evidence group leader for {stage_id}.")
        normalized_requirements[stage_id] = requirement
        leaders[stage_id] = leader
    for stage_id, leader in leaders.items():
        if leaders.get(leader) != leader:
            raise ValueError(f"Request analysis returned a non-canonical evidence group for {stage_id}.")
        _validate_group_compatibility(
            stage_id,
            leader,
            normalized_requirements[stage_id],
            normalized_requirements[leader],
        )

    obligation_ids = {leader: leader.replace(".", "_") for leader in dict.fromkeys(leaders.values())}
    obligations: list[dict[str, Any]] = []
    for leader in dict.fromkeys(leaders.values()):
        member_ids = [stage_id for stage_id in ordered_stage_ids if leaders[stage_id] == leader]
        requirement = normalized_requirements[leader]
        proposition = str(requirement.get("proposition") or "").strip()
        if not proposition:
            raise ValueError(f"Request analysis omitted proposition for {leader}.")
        if len(member_ids) > 1:
            proposition = (
                f"{proposition} The same evidence must also establish: "
                + "; ".join(
                    _stage_purpose(stage_id)
                    for stage_id in member_ids
                    if stage_id != leader
                )
            )
        policies = [_STAGE_POLICIES.get(stage_id, _StagePolicy()) for stage_id in member_ids]
        boundary = _require_evidence_boundary(leader, requirement)
        dependency_leaders = {
            leaders[item]
            for policy in policies
            for item in policy.depends_on
            if item in leaders and leaders[item] != leader
        }
        dependencies = [
            obligation_ids[item]
            for item in dict.fromkeys(leaders.values())
            if item in dependency_leaders
        ]
        anchor_refs = []
        for stage_id in member_ids:
            anchor_refs.extend(
                str(value).strip()
                for value in normalized_requirements[stage_id].get("anchor_refs", ())
                if str(value).strip() in known_anchors
            )
        roles = {policy.evidence_role for policy in policies if policy.evidence_role is not EvidenceRole.ANY}
        if len(roles) > 1:
            raise ValueError(f"Request analysis grouped incompatible evidence roles under {leader}.")
        evidence_role = next(iter(roles)) if roles else EvidenceRole.ANY
        evidence_sources = {policy.evidence_source for policy in policies}
        if len(evidence_sources) != 1:
            raise ValueError(f"Request analysis grouped incompatible evidence sources under {leader}.")
        evidence_source = next(iter(evidence_sources))
        obligations.append(
            {
                "id": obligation_ids[leader],
                "description": proposition,
                "required": True,
                "depends_on": dependencies,
                "anchor_refs": list(dict.fromkeys(anchor_refs))[:12],
                "evidence_role": evidence_role.value,
                "evidence_source": evidence_source.value,
                "evidence_boundary": boundary.value,
                "stage_ids": member_ids,
                "requires_repository_handoff": bool(dependencies)
                and any(policy.requires_repository_handoff for policy in policies),
            }
        )
    return obligations


def _validate_group_compatibility(
    stage_id: str,
    leader: str,
    stage_requirement: Mapping[str, Any],
    leader_requirement: Mapping[str, Any],
) -> None:
    if stage_id != leader and stage_id.partition(".")[0] == leader.partition(".")[0]:
        raise ValueError(f"Request analysis grouped distinct stages from the same intent: {leader}, {stage_id}.")
    stage_policy = _STAGE_POLICIES.get(stage_id, _StagePolicy())
    leader_policy = _STAGE_POLICIES.get(leader, _StagePolicy())
    if stage_policy.evidence_source is not leader_policy.evidence_source:
        raise ValueError(f"Request analysis grouped incompatible evidence sources: {leader}, {stage_id}.")
    stage_boundary = _require_evidence_boundary(stage_id, stage_requirement)
    leader_boundary = _require_evidence_boundary(leader, leader_requirement)
    if stage_boundary is not leader_boundary:
        raise ValueError(f"Request analysis grouped incompatible evidence boundaries: {leader}, {stage_id}.")
    roles = {
        role
        for role in (stage_policy.evidence_role, leader_policy.evidence_role)
        if role is not EvidenceRole.ANY
    }
    if len(roles) > 1:
        raise ValueError(f"Request analysis grouped incompatible evidence roles: {leader}, {stage_id}.")


def _require_evidence_boundary(stage_id: str, requirement: Mapping[str, Any]) -> EvidenceBoundary:
    value = str(requirement.get("evidence_boundary") or "").strip()
    try:
        boundary = EvidenceBoundary(value)
    except ValueError as exc:
        raise ValueError(f"Request analysis returned invalid evidence boundary for {stage_id}.") from exc
    policy = _STAGE_POLICIES.get(stage_id, _StagePolicy())
    if policy.evidence_source is EvidenceSource.PROMPT and boundary is not EvidenceBoundary.PROMPT:
        raise ValueError(f"Request analysis changed prompt evidence boundary for {stage_id}.")
    if policy.evidence_source is EvidenceSource.REPOSITORY and boundary is EvidenceBoundary.PROMPT:
        raise ValueError(f"Request analysis changed repository evidence boundary for {stage_id}.")
    return boundary


def _stage_purpose(stage_id: str) -> str:
    for contract in INTENT_CONTRACTS.values():
        for stage in contract.stages:
            if stage.id == stage_id:
                return stage.purpose.rstrip(".")
    raise ValueError(f"Unknown intent stage: {stage_id}.")


def _apply_symbol_decisions(
    analysis: Mapping[str, Any],
    stage_response: Mapping[str, Any],
) -> dict[str, Any]:
    decisions_value = stage_response.get("symbol_decisions")
    decisions = dict(decisions_value) if isinstance(decisions_value, Mapping) else {}
    anchors_value = analysis.get("anchors")
    anchors = dict(anchors_value) if isinstance(anchors_value, Mapping) else {}
    symbols = _anchor_values(analysis, "symbols")
    primary: list[str] = []
    supporting: list[str] = []
    for symbol in symbols:
        decision_value = decisions.get(symbol)
        decision = dict(decision_value) if isinstance(decision_value, Mapping) else {}
        relevance = str(decision.get("relevance") or "").strip()
        if relevance not in {"primary", "supporting", "ignore"}:
            raise ValueError(f"Request analysis omitted a valid relevance decision for symbol {symbol!r}.")
        if relevance == "primary":
            primary.append(symbol)
        elif relevance == "supporting":
            supporting.append(symbol)
    anchors.pop("symbols", None)
    anchors["primary_symbols"] = primary
    anchors["supporting_symbols"] = supporting
    return {**analysis, "anchors": anchors}


def _preserve_explicit_prompt_anchors(response: Mapping[str, Any], user_prompt: str) -> dict[str, Any]:
    anchors_value = response.get("anchors")
    anchors = dict(anchors_value) if isinstance(anchors_value, Mapping) else {}
    anchors["paths"] = list(_explicit_prompt_paths(user_prompt))[:12]
    explicit_symbols = _explicit_prompt_symbols(user_prompt)
    model_symbols = anchors.get("symbols")
    visible_model_symbols = (
        [
            str(value).strip()
            for value in model_symbols
            if _is_visible_prompt_symbol(str(value).strip(), user_prompt, explicit_symbols)
        ]
        if isinstance(model_symbols, Sequence) and not isinstance(model_symbols, (str, bytes))
        else []
    )
    anchors["symbols"] = list(dict.fromkeys((*explicit_symbols, *visible_model_symbols)))[:16]
    return {**response, "anchors": anchors}


def _preserve_explicit_prompt_paths(response: Mapping[str, Any], user_prompt: str) -> dict[str, Any]:
    """Compatibility wrapper for callers that only expect path normalization."""
    normalized = _preserve_explicit_prompt_anchors(response, user_prompt)
    anchors = dict(normalized.get("anchors", {}))
    original = response.get("anchors")
    if isinstance(original, Mapping):
        anchors["symbols"] = list(original.get("symbols", ()))
    return {**normalized, "anchors": anchors}


def _explicit_prompt_paths(user_prompt: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(match.group(0) for match in EXPLICIT_PATH_PATTERN.finditer(user_prompt)))


def _explicit_prompt_symbols(user_prompt: str) -> tuple[str, ...]:
    candidates: list[str] = []
    for match in NAMED_TYPE_PATTERN.finditer(user_prompt):
        candidates.append(match.group(1))
    candidates.extend(match.group(1) for match in CAMEL_CALL_PATTERN.finditer(user_prompt))
    return tuple(dict.fromkeys(candidates))[:16]


def _is_visible_prompt_symbol(value: str, user_prompt: str, explicit_symbols: Sequence[str]) -> bool:
    return bool(
        value
        and value in explicit_symbols
        and value in user_prompt
        and IDENTIFIER_PATTERN.fullmatch(value)
        and not any(separator in value for separator in ("/", "\\"))
    )


def _known_anchors(response: Mapping[str, Any]) -> set[str]:
    anchors = response.get("anchors")
    if not isinstance(anchors, Mapping):
        return set()
    return {
        str(value).strip()
        for values in anchors.values()
        if isinstance(values, Sequence) and not isinstance(values, (str, bytes))
        for value in values
        if str(value).strip()
    }


def _anchor_values(response: Mapping[str, Any], key: str) -> tuple[str, ...]:
    anchors = response.get("anchors")
    if not isinstance(anchors, Mapping):
        return ()
    values = anchors.get(key)
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return ()
    return tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


def _elapsed_ms(started_at: float) -> int:
    return int(round((time.perf_counter() - started_at) * 1000))
