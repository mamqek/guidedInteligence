from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class RetrievalRoleSpec:
    role: str
    description: str
    generic_keywords: tuple[str, ...]
    path_hints: tuple[str, ...]
    support_path_hints: tuple[str, ...] = ()
    query_hints: tuple[str, ...] = ()
    validator_threshold: float = 3.0
    compatible_anchor_roles: tuple[str, ...] = ()
    allow_call_flow: bool = False

    def compact_dict(self) -> dict[str, object]:
        return {
            "role": self.role,
            "description": self.description,
            "generic_keywords": list(self.generic_keywords),
            "path_hints": list(self.path_hints),
            "support_path_hints": list(self.support_path_hints),
            "query_hints": list(self.query_hints),
        }


_ROLE_SPECS: Mapping[str, RetrievalRoleSpec] = {
    "representation": RetrievalRoleSpec(
        role="representation",
        description="How the system models or declares structures, entities, metadata, and internal shapes.",
        generic_keywords=("model", "schema", "type", "symbol", "node", "declaration", "structure", "metadata"),
        path_hints=("types", "symbols", "ast", "nodes", "schema", "model"),
        support_path_hints=("parser", "checker", "binder"),
        query_hints=("type declaration model", "symbol node metadata"),
        validator_threshold=3.0,
        compatible_anchor_roles=("input_parsing", "validation_checking", "representation"),
    ),
    "input_parsing": RetrievalRoleSpec(
        role="input_parsing",
        description="How input text or source syntax is tokenized, parsed, or recognized into structured declarations.",
        generic_keywords=("parse", "parser", "parsing", "scanner", "syntax", "token", "modifier", "keyword", "grammar", "declaration"),
        path_hints=("parser", "scanner", "syntax"),
        support_path_hints=("checker", "binder", "resolver"),
        query_hints=("parser syntax tokens", "declaration grammar parsing"),
        validator_threshold=3.0,
        compatible_anchor_roles=("representation", "input_parsing"),
    ),
    "validation_checking": RetrievalRoleSpec(
        role="validation_checking",
        description="Where rules, semantic checks, constraints, and enforcement logic validate inputs or declarations.",
        generic_keywords=("check", "checker", "validation", "constraint", "rule", "semantic", "verify", "error", "diagnostic", "enforce"),
        path_hints=("checker", "semantic", "validator", "validate", "resolver", "rules"),
        support_path_hints=("parser", "scanner", "types", "binder"),
        query_hints=("semantic validation rules", "constraint error checking"),
        validator_threshold=3.2,
        compatible_anchor_roles=("input_parsing", "representation", "validation_checking"),
        allow_call_flow=True,
    ),
    "diagnostics": RetrievalRoleSpec(
        role="diagnostics",
        description="Where user-visible failure messages, error descriptions, or reporting logic are defined.",
        generic_keywords=("diagnostic", "diagnostics", "error", "message", "report", "failure"),
        path_hints=("diagnostic", "diagnostics", "message", "messages", "error"),
        support_path_hints=("checker", "parser"),
        query_hints=("diagnostic error messages", "failure reporting diagnostics"),
        validator_threshold=2.5,
        compatible_anchor_roles=("input_parsing", "validation_checking", "diagnostics"),
    ),
    "behavior_output": RetrievalRoleSpec(
        role="behavior_output",
        description="How validated structures are emitted, rendered, transformed, executed, or turned into output.",
        generic_keywords=("emit", "output", "runtime", "render", "transform", "serialize", "generate", "behavior"),
        path_hints=("emitter", "emit", "runtime", "transform", "renderer", "output"),
        support_path_hints=("parser", "syntax", "checker"),
        query_hints=("runtime output transform", "emit render generation"),
        validator_threshold=3.1,
        compatible_anchor_roles=("input_parsing", "validation_checking", "behavior_output"),
        allow_call_flow=True,
    ),
    "docs": RetrievalRoleSpec(
        role="docs",
        description="Documentation or user-facing guidance.",
        generic_keywords=("docs", "documentation", "guide", "readme", "usage"),
        path_hints=("docs", "documentation", "readme", "guide", "handbook"),
        query_hints=("feature documentation", "usage guide"),
    ),
    "config": RetrievalRoleSpec(
        role="config",
        description="Configuration, settings, and options that control feature behavior.",
        generic_keywords=("config", "configuration", "setting", "option", "options"),
        path_hints=("config", "settings", "options"),
        query_hints=("configuration settings", "feature options"),
    ),
    "tests": RetrievalRoleSpec(
        role="tests",
        description="Tests and verification cases.",
        generic_keywords=("test", "tests", "case", "cases", "coverage", "verification"),
        path_hints=("test", "tests", "spec", "cases", "fixtures"),
        query_hints=("test coverage", "behavior cases"),
    ),
}


def role_spec(role: str) -> RetrievalRoleSpec:
    return _ROLE_SPECS[role]


def supported_role_specs() -> tuple[RetrievalRoleSpec, ...]:
    return tuple(_ROLE_SPECS[name] for name in sorted(_ROLE_SPECS))


def role_keywords(role: str) -> tuple[str, ...]:
    return role_spec(role).generic_keywords


def role_path_hints(role: str) -> tuple[str, ...]:
    return role_spec(role).path_hints


def role_support_path_hints(role: str) -> tuple[str, ...]:
    return role_spec(role).support_path_hints


def role_query_hints(role: str) -> tuple[str, ...]:
    return role_spec(role).query_hints


def role_generic_terms(role: str) -> tuple[str, ...]:
    spec = role_spec(role)
    values = [*spec.generic_keywords, *spec.path_hints, *spec.support_path_hints]
    seen: list[str] = []
    for value in values:
        normalized = value.strip().lower()
        if normalized and normalized not in seen:
            seen.append(normalized)
    return tuple(seen)


def role_compact_payload(role: str) -> Mapping[str, object]:
    return role_spec(role).compact_dict()


def role_phrase_from_spec(role: str, *, max_terms: int = 4) -> str:
    spec = role_spec(role)
    terms = list(spec.query_hints[:1])
    if terms:
        return terms[0]
    return " ".join(spec.generic_keywords[:max_terms]).strip()


def text_matches_role_keywords(role: str, text: str, *, minimum_hits: int = 1) -> bool:
    lowered = text.lower()
    hits = sum(1 for token in role_generic_terms(role) if token in lowered)
    return hits >= minimum_hits


def path_matches_role(role: str, path: str) -> bool:
    lowered = path.replace("\\", "/").lower()
    return any(token in lowered for token in role_path_hints(role))


def path_matches_role_support(role: str, path: str) -> bool:
    lowered = path.replace("\\", "/").lower()
    return any(token in lowered for token in role_support_path_hints(role))

