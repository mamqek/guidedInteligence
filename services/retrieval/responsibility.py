from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Mapping, Sequence

from services.retrieval.role_specs import (
    path_matches_role,
    path_matches_role_support,
    role_keywords,
    role_path_hints,
    role_phrase_from_spec,
    role_support_path_hints,
)


@dataclass(frozen=True)
class FileResponsibilityProfile:
    role: str
    path: str
    classification: str
    reasons: tuple[str, ...]
    support_only: bool
    noise: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "role": self.role,
            "path": self.path,
            "classification": self.classification,
            "reasons": list(self.reasons),
            "support_only": self.support_only,
            "noise": self.noise,
        }


@dataclass(frozen=True)
class ResponsibilityScore:
    total_score: float
    base_score: float
    owner_score: float
    support_penalty: float
    graph_score: float
    profile: FileResponsibilityProfile
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "total_score": round(self.total_score, 3),
            "base_score": round(self.base_score, 3),
            "owner_score": round(self.owner_score, 3),
            "support_penalty": round(self.support_penalty, 3),
            "graph_score": round(self.graph_score, 3),
            "profile": self.profile.to_dict(),
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class ResponsibilityExpansionIntent:
    role: str
    query: str
    reason: str
    source_paths: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "role": self.role,
            "query": self.query,
            "reason": self.reason,
            "source_paths": list(self.source_paths),
        }


NOISE_PATH_TOKENS = (
    "/test/",
    "/tests/",
    "/fixture",
    "/fixtures/",
    "/baseline",
    "/generated/",
    "/node_modules/",
)

DIAGNOSTIC_PATH_TOKENS = role_path_hints("diagnostics")
HELPER_PATH_TOKENS = ("helper", "helpers", "util", "utils", "utilities", "common")
PLUMBING_PATH_TOKENS = ("commandline", "services", "server", "project", "config", "options", "watch")
LOW_LEVEL_PATH_TOKENS = ("src/datetime", "np_datetime", "npdatetime", "conversion", "convert")
PUBLIC_API_PATH_TOKENS = ("api", "indexes", "index", "arrays", "series", "frame", "timestamp", "datetimes")
ROLE_OWNER_PATH_TOKENS: Mapping[str, tuple[str, ...]] = {
    "validation_checking": role_path_hints("validation_checking"),
    "behavior_output": role_path_hints("behavior_output"),
    "input_parsing": role_path_hints("input_parsing"),
    "representation": role_path_hints("representation"),
    "diagnostics": role_path_hints("diagnostics"),
}


def profile_candidate(role: str, *, path: str, text: str, file_role: str = "") -> FileResponsibilityProfile:
    normalized_path = _normalized_path(path)
    lowered_text = text.lower()
    reasons: list[str] = []

    if file_role in {"test", "baseline_or_generated"} or any(token in normalized_path for token in NOISE_PATH_TOKENS):
        return FileResponsibilityProfile(role, path, "noise", ("test_or_generated_path",), support_only=True, noise=True)

    if _is_diagnostics_catalog(normalized_path, lowered_text) and role != "diagnostics":
        return FileResponsibilityProfile(role, path, "support_only", ("diagnostics_catalog",), support_only=True, noise=False)

    owner_score = _owner_signal_score(role, normalized_path, lowered_text, reasons)
    support_score = _support_signal_score(role, normalized_path, lowered_text, reasons)

    if any(token in normalized_path for token in HELPER_PATH_TOKENS):
        support_score += 2.0
        reasons.append("helper_path")
    if any(token in normalized_path for token in PLUMBING_PATH_TOKENS) and role not in {"config", "docs"}:
        support_score += 1.8
        reasons.append("plumbing_path")
    if any(token in normalized_path for token in LOW_LEVEL_PATH_TOKENS):
        support_score += 2.3
        reasons.append("low_level_leaf")
    if _matches_other_role_owner_path(role, normalized_path):
        support_score += 3.0
        reasons.append("cross_role_owner_path")

    if owner_score >= support_score + 1.2:
        classification = "likely_owner"
        support_only = False
    elif owner_score >= 2.0:
        classification = "possible_owner"
        support_only = False
    elif support_score > 0:
        classification = "support_only"
        support_only = True
    else:
        classification = "possible_owner"
        support_only = False
        reasons.append("neutral_implementation_file")

    return FileResponsibilityProfile(
        role=role,
        path=path,
        classification=classification,
        reasons=tuple(dict.fromkeys(reasons)),
        support_only=support_only,
        noise=False,
    )


def score_responsibility(
    role: str,
    *,
    path: str,
    text: str,
    retrieval_score: float,
    validation_score: float = 0.0,
    graph_paths: Sequence[str] = (),
    file_role: str = "",
) -> ResponsibilityScore:
    profile = profile_candidate(role, path=path, text=text, file_role=file_role)
    normalized_path = _normalized_path(path)
    lowered_text = text.lower()
    reasons = list(profile.reasons)

    base_score = min(float(retrieval_score), 8.0) + min(float(validation_score), 5.0)
    owner_score = _owner_signal_score(role, normalized_path, lowered_text, reasons)
    graph_score = 2.0 if _normalized_path(path) in {_normalized_path(item) for item in graph_paths} else 0.0
    support_penalty = 0.0
    if profile.noise:
        support_penalty = 10.0
    elif profile.support_only:
        support_penalty = 5.0
    if profile.classification == "likely_owner":
        owner_score += 2.0
    elif profile.classification == "possible_owner":
        owner_score += 0.8

    total = base_score + owner_score + graph_score - support_penalty
    return ResponsibilityScore(
        total_score=total,
        base_score=base_score,
        owner_score=owner_score,
        support_penalty=support_penalty,
        graph_score=graph_score,
        profile=profile,
        reasons=tuple(dict.fromkeys(reasons)),
    )


def infer_expansion_intents(
    *,
    required_roles: Sequence[str],
    prompt_summary: str,
    candidates_by_role: Mapping[str, Sequence[tuple[str, str, FileResponsibilityProfile]]],
) -> tuple[ResponsibilityExpansionIntent, ...]:
    intents: list[ResponsibilityExpansionIntent] = []
    prompt = prompt_summary.strip()
    for role in required_roles:
        entries = list(candidates_by_role.get(role, ()))
        paths = tuple(path for path, _text, _profile in entries[:4])
        support_count = sum(1 for _path, _text, profile in entries if profile.support_only)
        likely_count = sum(1 for _path, _text, profile in entries if profile.classification == "likely_owner")
        all_paths = " ".join(path.lower() for path, _text, _profile in entries)

        if role == "validation_checking" and likely_count == 0:
            if any(token in all_paths for token in role_support_path_hints(role)) or support_count:
                intents.append(
                    ResponsibilityExpansionIntent(
                        role=role,
                        query=_join_query(prompt, role_phrase_from_spec(role)),
                        reason="parser_or_representation_without_validation_owner",
                        source_paths=paths,
                    )
                )
        if role == "behavior_output" and likely_count == 0:
            if any(token in all_paths for token in role_support_path_hints(role)) or support_count:
                intents.append(
                    ResponsibilityExpansionIntent(
                        role=role,
                        query=_join_query(prompt, role_phrase_from_spec(role)),
                        reason="syntax_without_behavior_owner",
                        source_paths=paths,
                    )
                )
        if any(profile.support_only and "low_level_leaf" in profile.reasons for _path, _text, profile in entries):
            intents.append(
                ResponsibilityExpansionIntent(
                    role=role,
                    query=_join_query(prompt, "public API type owner high level user visible"),
                    reason="low_level_leaf_without_public_owner",
                    source_paths=paths,
                )
            )
    return tuple(_dedupe_intents(intents))


def _owner_signal_score(role: str, path: str, text: str, reasons: list[str]) -> float:
    score = 0.0
    if path_matches_role(role, path):
        score += 3.0
        reasons.append(f"{role}_owner_path")
    if any(token in text for token in role_keywords(role)):
        score += 2.2
        reasons.append(f"{role}_text")

    if any(token in path for token in PUBLIC_API_PATH_TOKENS):
        score += 1.4
        reasons.append("public_api_path")
    if any(token in text for token in ("export class", "export function", "public ", "__all__", "api")):
        score += 1.2
        reasons.append("public_surface_text")
    return score


def _support_signal_score(role: str, path: str, text: str, reasons: list[str]) -> float:
    score = 0.0
    if path_matches_role_support(role, path):
        score += 2.5
        reasons.append(f"adjacent_{role}_support_layer")
    if role != "diagnostics" and "diagnostic" in text and not any(token in text for token in role_keywords(role)):
        score += 1.5
        reasons.append("diagnostic_text_without_enforcement")
    return score


def _is_diagnostics_catalog(path: str, text: str) -> bool:
    basename = PurePosixPath(path).name
    return any(token in path for token in DIAGNOSTIC_PATH_TOKENS) or (
        basename.endswith(".json") and any(token in text for token in ("diagnostic", "error", "message"))
    )


def _join_query(prompt: str, suffix: str) -> str:
    return f"{prompt} {suffix}".strip() if prompt else suffix


def _dedupe_intents(intents: Sequence[ResponsibilityExpansionIntent]) -> tuple[ResponsibilityExpansionIntent, ...]:
    selected: list[ResponsibilityExpansionIntent] = []
    seen: set[tuple[str, str]] = set()
    for intent in intents:
        key = (intent.role, intent.query.lower())
        if key in seen:
            continue
        seen.add(key)
        selected.append(intent)
    return tuple(selected)


def _normalized_path(value: str) -> str:
    return value.replace("\\", "/").strip().lower()


def _matches_other_role_owner_path(role: str, path: str) -> bool:
    current_tokens = ROLE_OWNER_PATH_TOKENS.get(role, ())
    if any(token in path for token in current_tokens):
        return False
    return any(
        token in path
        for other_role, tokens in ROLE_OWNER_PATH_TOKENS.items()
        if other_role != role
        for token in tokens
    )
