"""Concrete orchestration primitives for Guided Intelligence."""

from __future__ import annotations

from typing import Any


_EXPORT_MODULES = {
    "ControlLayer": "core.control_layer",
    "ConversationMessage": "core.models",
    "ConversationState": "core.models",
    "EvidenceItem": "core.models",
    "LogEvent": "core.logging_schema",
    "LogEventType": "core.logging_schema",
    "OrchestrationResult": "core.models",
    "PolicyResult": "core.models",
    "PolicyStage": "core.policy",
    "PolicyViolation": "core.violations",
    "PolicyViolationType": "core.violations",
    "ResponsePayload": "core.models",
    "ResponsePlan": "core.models",
    "RetrievalResult": "core.models",
    "TurnType": "core.models",
    "DEFAULT_SOURCE_POLICY": "core.source_policy",
    "SourceCategory": "core.source_policy",
    "SourcePolicy": "core.source_policy",
    "AssistanceRequestType": "core.models",
}

__all__ = list(_EXPORT_MODULES)


def __getattr__(name: str) -> Any:
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(name)
    module = __import__(module_name, fromlist=[name])
    return getattr(module, name)
