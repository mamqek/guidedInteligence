from __future__ import annotations

from services.retrieval.role_validation.base import RoleValidator
from services.retrieval.role_validation.behavior_output import BehaviorOutputValidator
from services.retrieval.role_validation.diagnostics import DiagnosticsValidator
from services.retrieval.role_validation.input_parsing import InputParsingValidator
from services.retrieval.role_validation.representation import RepresentationValidator
from services.retrieval.role_validation.validation_checking import ValidationCheckingValidator


_VALIDATORS: dict[str, RoleValidator] = {
    "representation": RepresentationValidator(),
    "input_parsing": InputParsingValidator(),
    "validation_checking": ValidationCheckingValidator(),
    "diagnostics": DiagnosticsValidator(),
    "behavior_output": BehaviorOutputValidator(),
}


def validator_for_role(role: str) -> RoleValidator:
    return _VALIDATORS[role]


def supported_roles() -> tuple[str, ...]:
    return tuple(sorted(_VALIDATORS))
