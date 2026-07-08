from __future__ import annotations

# Owns objective-to-legacy-role compatibility mapping. Do not place intent classification, retrieval execution, or synthesis policy here.

from typing import Sequence

from services.retrieval.workspace.step2.common import ordered_unique
from services.retrieval.workspace.step2.constants import (
    OBJECTIVE_BEHAVIOR_PATH,
    OBJECTIVE_CONFIGURATION_CONTEXT,
    OBJECTIVE_CONSTRAINTS_VALIDATION,
    OBJECTIVE_DATA_STATE,
    OBJECTIVE_DIAGNOSTIC_SURFACE,
    OBJECTIVE_EFFECTS_OUTPUT,
    OBJECTIVE_IMPLEMENTATION_OWNER,
    OBJECTIVE_INTERFACE_ENTRY,
    OBJECTIVE_USAGE_CONTRACT,
    OBJECTIVE_VERIFICATION_REPRO,
    ROLE_BEHAVIOR_OUTPUT,
    ROLE_CONFIG,
    ROLE_DIAGNOSTICS,
    ROLE_DOCS,
    ROLE_INPUT_PARSING,
    ROLE_REPRESENTATION,
    ROLE_TESTS,
    ROLE_VALIDATION_CHECKING,
)


def legacy_required_roles_for_objectives(objectives: Sequence[str]) -> tuple[str, ...]:
    roles: list[str] = []
    for objective in objectives:
        if objective == OBJECTIVE_IMPLEMENTATION_OWNER:
            roles.extend((ROLE_BEHAVIOR_OUTPUT, ROLE_VALIDATION_CHECKING))
        elif objective == OBJECTIVE_INTERFACE_ENTRY:
            roles.append(ROLE_INPUT_PARSING)
        elif objective == OBJECTIVE_BEHAVIOR_PATH:
            roles.extend((ROLE_BEHAVIOR_OUTPUT, ROLE_REPRESENTATION))
        elif objective == OBJECTIVE_DATA_STATE:
            roles.append(ROLE_REPRESENTATION)
        elif objective == OBJECTIVE_CONSTRAINTS_VALIDATION:
            roles.append(ROLE_VALIDATION_CHECKING)
        elif objective == OBJECTIVE_EFFECTS_OUTPUT:
            roles.append(ROLE_BEHAVIOR_OUTPUT)
        elif objective == OBJECTIVE_DIAGNOSTIC_SURFACE:
            roles.append(ROLE_DIAGNOSTICS)
    return tuple(ordered_unique(roles))


def legacy_supporting_roles_for_objectives(objectives: Sequence[str]) -> tuple[str, ...]:
    roles: list[str] = []
    for objective in objectives:
        if objective == OBJECTIVE_VERIFICATION_REPRO:
            roles.append(ROLE_TESTS)
        elif objective == OBJECTIVE_CONFIGURATION_CONTEXT:
            roles.append(ROLE_CONFIG)
        elif objective == OBJECTIVE_USAGE_CONTRACT:
            roles.append(ROLE_DOCS)
    return tuple(ordered_unique(roles))
