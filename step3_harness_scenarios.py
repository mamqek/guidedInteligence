from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import cast

from core.logging_schema import LogEventType
from core.models import ConversationState, EvidenceItem, TurnType, UserIntent
from core.source_policy import DEFAULT_ALLOWED_SOURCE_CATEGORIES, SourceCategory
from core.violations import PolicyViolationType


class ScenarioOnlySourceCategory(str, Enum):
    EXTERNAL_WEB = "external_web"


UNSUPPORTED_SOURCE_CATEGORY = cast(SourceCategory, ScenarioOnlySourceCategory.EXTERNAL_WEB)


@dataclass(frozen=True)
class ExpectedPolicyResult:
    allowed: bool
    intent: UserIntent
    retrieval_required: bool
    turn_type: TurnType
    allowed_sources: tuple[SourceCategory, ...] = DEFAULT_ALLOWED_SOURCE_CATEGORIES
    violations: tuple[PolicyViolationType, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class HarnessScenario:
    scenario_id: str
    title: str
    purpose: str
    state: ConversationState
    expected_policy: ExpectedPolicyResult
    expected_log_events: tuple[LogEventType, ...]
    stub_evidence_after_retrieval: tuple[EvidenceItem, ...] = field(default_factory=tuple)


SOURCE_CODE_EVIDENCE = EvidenceItem(
    source_category=SourceCategory.SOURCE_CODE,
    source_id="core.policy.PolicyStage",
    snippet="PolicyStage selects guided explanation turns and explicit policy violations.",
    rank=1,
    metadata={"path": "core/policy.py", "coverage_area": "policy_gate"},
)

DOCUMENTATION_EVIDENCE = EvidenceItem(
    source_category=SourceCategory.DOCUMENTATION,
    source_id="docs.guided_turn_model",
    snippet="The guided turn explains code, asks checks, and keeps hints hidden until requested.",
    rank=2,
    metadata={"path": "guided_explanation_turn_model.md", "coverage_area": "turn_contract"},
)

UNSUPPORTED_EVIDENCE = EvidenceItem(
    source_category=UNSUPPORTED_SOURCE_CATEGORY,
    source_id="external_web.example",
    snippet="External web content is outside the project evidence allowlist.",
    rank=1,
    metadata={"url": "https://example.invalid/out-of-scope"},
)

DEFAULT_STUB_EVIDENCE = (SOURCE_CODE_EVIDENCE, DOCUMENTATION_EVIDENCE)

CONTROL_LAYER_RETRIEVAL_LOGS = (
    LogEventType.RUN_STARTED,
    LogEventType.TURN_DECISION,
    LogEventType.RETRIEVAL_PLAN,
    LogEventType.EVIDENCE_SELECTED,
    LogEventType.RESPONSE_PLAN,
    LogEventType.PROMPT_PAYLOAD,
    LogEventType.RESPONSE_PAYLOAD,
    LogEventType.RUN_COMPLETED,
)


SCENARIOS: tuple[HarnessScenario, ...] = (
    HarnessScenario(
        scenario_id="normal_guided_explanation_request",
        title="Normal guided explanation request",
        purpose="Initial request uses allowed sources and produces a guided explanation turn.",
        state=ConversationState(
            conversation_id="step3-normal-guided-explanation",
            user_input="Can you explain how the orchestration flow decides what to do next?",
            intent=UserIntent.UNDERSTAND_CODE,
        ),
        expected_policy=ExpectedPolicyResult(
            allowed=True,
            intent=UserIntent.UNDERSTAND_CODE,
            retrieval_required=True,
            turn_type=TurnType.GUIDED_EXPLANATION,
        ),
        expected_log_events=CONTROL_LAYER_RETRIEVAL_LOGS,
        stub_evidence_after_retrieval=DEFAULT_STUB_EVIDENCE,
    ),
    HarnessScenario(
        scenario_id="direct_solution_request",
        title="Direct solution request",
        purpose="Direct solution requests are rejected without retrieval.",
        state=ConversationState(
            conversation_id="step3-direct-solution",
            user_input="Just solve this and write the solution for me.",
            intent=UserIntent.UNKNOWN,
        ),
        expected_policy=ExpectedPolicyResult(
            allowed=False,
            intent=UserIntent.DIRECT_SOLUTION_REQUEST,
            retrieval_required=False,
            turn_type=TurnType.BOUNDARY,
            violations=(PolicyViolationType.DIRECT_SOLUTION_REQUEST,),
        ),
        expected_log_events=(
            LogEventType.RUN_STARTED,
            LogEventType.TURN_DECISION,
            LogEventType.POLICY_VIOLATION,
            LogEventType.RETRIEVAL_PLAN,
            LogEventType.RESPONSE_PLAN,
            LogEventType.PROMPT_PAYLOAD,
            LogEventType.RESPONSE_PAYLOAD,
            LogEventType.RUN_COMPLETED,
        ),
    ),
    HarnessScenario(
        scenario_id="unsupported_source_evidence",
        title="Unsupported source evidence",
        purpose="Disallowed evidence categories are explicit and loggable.",
        state=ConversationState(
            conversation_id="step3-unsupported-source",
            user_input="Can you explain this using the attached context?",
            intent=UserIntent.UNDERSTAND_CODE,
            evidence=(UNSUPPORTED_EVIDENCE,),
        ),
        expected_policy=ExpectedPolicyResult(
            allowed=False,
            intent=UserIntent.UNDERSTAND_CODE,
            retrieval_required=False,
            turn_type=TurnType.BOUNDARY,
            violations=(PolicyViolationType.UNSUPPORTED_SOURCE_USAGE,),
        ),
        expected_log_events=(
            LogEventType.RUN_STARTED,
            LogEventType.TURN_DECISION,
            LogEventType.POLICY_VIOLATION,
            LogEventType.RETRIEVAL_PLAN,
            LogEventType.RESPONSE_PLAN,
            LogEventType.PROMPT_PAYLOAD,
            LogEventType.RESPONSE_PAYLOAD,
            LogEventType.RUN_COMPLETED,
        ),
    ),
    HarnessScenario(
        scenario_id="evidence_already_present",
        title="Evidence already present",
        purpose="Attached valid evidence avoids a retrieval pass.",
        state=ConversationState(
            conversation_id="step3-existing-evidence",
            user_input="Can you explain how the guided turn works?",
            intent=UserIntent.UNDERSTAND_CODE,
            evidence=DEFAULT_STUB_EVIDENCE,
        ),
        expected_policy=ExpectedPolicyResult(
            allowed=True,
            intent=UserIntent.UNDERSTAND_CODE,
            retrieval_required=False,
            turn_type=TurnType.GUIDED_EXPLANATION,
        ),
        expected_log_events=CONTROL_LAYER_RETRIEVAL_LOGS,
    ),
)


def scenario_ids() -> tuple[str, ...]:
    return tuple(scenario.scenario_id for scenario in SCENARIOS)


def main() -> None:
    for scenario in SCENARIOS:
        print(f"{scenario.scenario_id}: {scenario.title}")


if __name__ == "__main__":
    main()
