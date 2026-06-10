from __future__ import annotations

from services.retrieval.role_validation.base import RoleValidator
from services.retrieval.role_validation.generic import GenericRoleValidator


_VALIDATORS: dict[str, RoleValidator] = {
    "representation": GenericRoleValidator("representation"),
    "input_parsing": GenericRoleValidator("input_parsing"),
    "validation_checking": GenericRoleValidator("validation_checking"),
    "diagnostics": GenericRoleValidator("diagnostics"),
    "behavior_output": GenericRoleValidator("behavior_output"),
}


def validator_for_role(role: str) -> RoleValidator:
    return _VALIDATORS[role]


def supported_roles() -> tuple[str, ...]:
    return tuple(sorted(_VALIDATORS))
