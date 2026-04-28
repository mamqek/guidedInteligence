from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import cast

from core.logging_schema import LogEventType
from core.models import ConversationState, EvidenceItem, UserIntent
from core.response_contracts import ResponseTemplate
from core.source_policy import DEFAULT_ALLOWED_SOURCE_CATEGORIES, SourceCategory
from core.stages import ResponseStage
from core.violations import PolicyViolationType


class ScenarioOnlySourceCategory(str, Enum):
    """Source category used only to exercise unsupported-source scenarios."""

    EXTERNAL_WEB = "external_web"


UNSUPPORTED_SOURCE_CATEGORY = cast(
    SourceCategory,
    ScenarioOnlySourceCategory.EXTERNAL_WEB,
)


@dataclass(frozen=True)
class ExpectedDecision:
    """Expected policy fields a future Step 3 harness should assert."""

    allowed: bool
    current_stage: ResponseStage
    next_stage: ResponseStage
    intent: UserIntent
    retrieval_required: bool
    response_template_id: str
    allowed_sources: tuple[SourceCategory, ...] = DEFAULT_ALLOWED_SOURCE_CATEGORIES
    violations: tuple[PolicyViolationType, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class HarnessScenario:
    """Scenario fixture for the local framework-free harness."""

    scenario_id: str
    title: str
    purpose: str
    state: ConversationState
    expected_decision: ExpectedDecision
    expected_log_events: tuple[LogEventType, ...]
    stub_evidence_after_retrieval: tuple[EvidenceItem, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)


SOURCE_CODE_EVIDENCE = EvidenceItem(
    source_category=SourceCategory.SOURCE_CODE,
    source_id="core.policy.V1PolicyEngine",
    snippet="V1PolicyEngine selects scaffolded stages and explicit policy violations.",
    rank=1,
    metadata={"path": "core/policy.py"},
)

DOCUMENTATION_EVIDENCE = EvidenceItem(
    source_category=SourceCategory.DOCUMENTATION,
    source_id="v1_boundaries.supported_flow",
    snippet="The v1 flow is explain -> ask -> hint, with direct solutions redirected.",
    rank=2,
    metadata={"path": "v1_boundaries.md"},
)

UNSUPPORTED_EVIDENCE = EvidenceItem(
    source_category=UNSUPPORTED_SOURCE_CATEGORY,
    source_id="external_web.example",
    snippet="External web content is outside the v1 project evidence allowlist.",
    rank=1,
    metadata={"url": "https://example.invalid/out-of-scope"},
)

DEFAULT_STUB_EVIDENCE = (
    SOURCE_CODE_EVIDENCE,
    DOCUMENTATION_EVIDENCE,
)

RETRIEVAL_RESPONSE_LOGS = (
    LogEventType.STAGE_DECISION,
    LogEventType.RETRIEVAL_PLAN,
    LogEventType.EVIDENCE_SELECTED,
    LogEventType.PROMPT_PAYLOAD,
    LogEventType.RESPONSE_PAYLOAD,
)

NO_RETRIEVAL_RESPONSE_LOGS = (
    LogEventType.STAGE_DECISION,
    LogEventType.PROMPT_PAYLOAD,
    LogEventType.RESPONSE_PAYLOAD,
)


SCENARIOS: tuple[HarnessScenario, ...] = (
    HarnessScenario(
        scenario_id="normal_explanation_request",
        title="Normal explanation request",
        purpose="Initial explanation path uses allowed sources and advances to ask.",
        state=ConversationState(
            conversation_id="step3-normal-explanation",
            user_input="Can you explain how the v1 orchestration flow decides what to do next?",
            current_stage=ResponseStage.EXPLAIN,
            intent=UserIntent.UNDERSTAND_CODE,
            stage_history=(ResponseStage.EXPLAIN,),
        ),
        expected_decision=ExpectedDecision(
            allowed=True,
            current_stage=ResponseStage.EXPLAIN,
            next_stage=ResponseStage.ASK,
            intent=UserIntent.UNDERSTAND_CODE,
            retrieval_required=True,
            response_template_id=ResponseTemplate.EXPLANATION.value,
        ),
        expected_log_events=RETRIEVAL_RESPONSE_LOGS,
        stub_evidence_after_retrieval=DEFAULT_STUB_EVIDENCE,
    ),
    HarnessScenario(
        scenario_id="ask_stage_follow_up",
        title="Ask-stage follow-up",
        purpose="Ask stage produces a reasoning question and advances to hint.",
        state=ConversationState(
            conversation_id="step3-ask-follow-up",
            user_input="Can you give me more detail about that stage decision?",
            current_stage=ResponseStage.ASK,
            intent=UserIntent.FOLLOW_UP,
            stage_history=(ResponseStage.EXPLAIN, ResponseStage.ASK),
        ),
        expected_decision=ExpectedDecision(
            allowed=True,
            current_stage=ResponseStage.ASK,
            next_stage=ResponseStage.HINT,
            intent=UserIntent.FOLLOW_UP,
            retrieval_required=True,
            response_template_id=ResponseTemplate.REASONING_QUESTION.value,
        ),
        expected_log_events=RETRIEVAL_RESPONSE_LOGS,
        stub_evidence_after_retrieval=DEFAULT_STUB_EVIDENCE,
        notes=(
            "Reasoning-question contracts do not require final evidence text, "
            "but policy can still request retrieval when state has no evidence.",
        ),
    ),
    HarnessScenario(
        scenario_id="hint_stage_follow_up",
        title="Hint-stage follow-up",
        purpose="Hint stage remains terminal and provides bounded support.",
        state=ConversationState(
            conversation_id="step3-hint-follow-up",
            user_input="I still need a hint about how to read this policy behavior.",
            current_stage=ResponseStage.HINT,
            intent=UserIntent.FOLLOW_UP,
            stage_history=(
                ResponseStage.EXPLAIN,
                ResponseStage.ASK,
                ResponseStage.HINT,
            ),
        ),
        expected_decision=ExpectedDecision(
            allowed=True,
            current_stage=ResponseStage.HINT,
            next_stage=ResponseStage.HINT,
            intent=UserIntent.FOLLOW_UP,
            retrieval_required=True,
            response_template_id=ResponseTemplate.HINT.value,
        ),
        expected_log_events=RETRIEVAL_RESPONSE_LOGS,
        stub_evidence_after_retrieval=DEFAULT_STUB_EVIDENCE,
    ),
    HarnessScenario(
        scenario_id="direct_solution_request",
        title="Direct solution request",
        purpose="Direct solution requests are redirected without retrieval.",
        state=ConversationState(
            conversation_id="step3-direct-solution",
            user_input="Just solve this and write the solution for me.",
            current_stage=ResponseStage.EXPLAIN,
            intent=UserIntent.UNKNOWN,
            stage_history=(ResponseStage.EXPLAIN,),
        ),
        expected_decision=ExpectedDecision(
            allowed=False,
            current_stage=ResponseStage.ASK,
            next_stage=ResponseStage.HINT,
            intent=UserIntent.DIRECT_SOLUTION_REQUEST,
            retrieval_required=False,
            response_template_id=ResponseTemplate.BOUNDARY_CHECK_QUESTION.value,
            violations=(PolicyViolationType.DIRECT_SOLUTION_REQUEST,),
        ),
        expected_log_events=(
            LogEventType.STAGE_DECISION,
            LogEventType.POLICY_VIOLATION,
            LogEventType.PROMPT_PAYLOAD,
            LogEventType.RESPONSE_PAYLOAD,
        ),
        notes=("This scenario also covers the direct-solution keyword heuristic.",),
    ),
    HarnessScenario(
        scenario_id="stage_skipping_attempt",
        title="Stage skipping attempt",
        purpose="Jumping from explain to hint is explicit and loggable.",
        state=ConversationState(
            conversation_id="step3-stage-skip",
            user_input="I need a hint before going through the reasoning question.",
            current_stage=ResponseStage.HINT,
            intent=UserIntent.UNDERSTAND_CODE,
            stage_history=(ResponseStage.EXPLAIN,),
        ),
        expected_decision=ExpectedDecision(
            allowed=False,
            current_stage=ResponseStage.ASK,
            next_stage=ResponseStage.HINT,
            intent=UserIntent.UNDERSTAND_CODE,
            retrieval_required=False,
            response_template_id=ResponseTemplate.BOUNDARY_CHECK_QUESTION.value,
            violations=(PolicyViolationType.STAGE_SKIPPING,),
        ),
        expected_log_events=(
            LogEventType.STAGE_DECISION,
            LogEventType.POLICY_VIOLATION,
            LogEventType.PROMPT_PAYLOAD,
            LogEventType.RESPONSE_PAYLOAD,
        ),
        notes=(
            "Stage-skipping recovery now uses ASK-stage questioning instead of "
            "the skipped hint template.",
        ),
    ),
    HarnessScenario(
        scenario_id="unsupported_source_evidence",
        title="Unsupported source evidence",
        purpose="Disallowed evidence categories are explicit and loggable.",
        state=ConversationState(
            conversation_id="step3-unsupported-source",
            user_input="Can you explain this using the attached context?",
            current_stage=ResponseStage.EXPLAIN,
            intent=UserIntent.UNDERSTAND_CODE,
            evidence=(UNSUPPORTED_EVIDENCE,),
            stage_history=(ResponseStage.EXPLAIN,),
        ),
        expected_decision=ExpectedDecision(
            allowed=False,
            current_stage=ResponseStage.EXPLAIN,
            next_stage=ResponseStage.ASK,
            intent=UserIntent.UNDERSTAND_CODE,
            retrieval_required=False,
            response_template_id=ResponseTemplate.EXPLANATION.value,
            violations=(PolicyViolationType.UNSUPPORTED_SOURCE_USAGE,),
        ),
        expected_log_events=(
            LogEventType.STAGE_DECISION,
            LogEventType.POLICY_VIOLATION,
            LogEventType.PROMPT_PAYLOAD,
            LogEventType.RESPONSE_PAYLOAD,
        ),
        notes=(
            "SourceCategory currently contains only allowed v1 categories, so "
            "this fixture uses a scenario-only cast to exercise the policy path.",
        ),
    ),
    HarnessScenario(
        scenario_id="evidence_already_present",
        title="Evidence already present",
        purpose="Attached valid evidence avoids a retrieval pass.",
        state=ConversationState(
            conversation_id="step3-existing-evidence",
            user_input="Can you explain how the boundaries define v1 behavior?",
            current_stage=ResponseStage.EXPLAIN,
            intent=UserIntent.UNDERSTAND_CODE,
            evidence=DEFAULT_STUB_EVIDENCE,
            stage_history=(ResponseStage.EXPLAIN,),
        ),
        expected_decision=ExpectedDecision(
            allowed=True,
            current_stage=ResponseStage.EXPLAIN,
            next_stage=ResponseStage.ASK,
            intent=UserIntent.UNDERSTAND_CODE,
            retrieval_required=False,
            response_template_id=ResponseTemplate.EXPLANATION.value,
        ),
        expected_log_events=NO_RETRIEVAL_RESPONSE_LOGS,
    ),
    HarnessScenario(
        scenario_id="unknown_intent_heuristic",
        title="Unknown intent heuristic",
        purpose="UNKNOWN intent is classified by policy keyword rules.",
        state=ConversationState(
            conversation_id="step3-unknown-intent",
            user_input="Can you give me more detail about that transition?",
            current_stage=ResponseStage.ASK,
            intent=UserIntent.UNKNOWN,
            stage_history=(ResponseStage.EXPLAIN, ResponseStage.ASK),
        ),
        expected_decision=ExpectedDecision(
            allowed=True,
            current_stage=ResponseStage.ASK,
            next_stage=ResponseStage.HINT,
            intent=UserIntent.FOLLOW_UP,
            retrieval_required=True,
            response_template_id=ResponseTemplate.REASONING_QUESTION.value,
        ),
        expected_log_events=RETRIEVAL_RESPONSE_LOGS,
        stub_evidence_after_retrieval=DEFAULT_STUB_EVIDENCE,
        notes=("The future harness should assert policy output, not duplicate heuristics.",),
    ),
)


def scenario_ids() -> tuple[str, ...]:
    """Return stable scenario IDs for lightweight smoke checks."""

    return tuple(scenario.scenario_id for scenario in SCENARIOS)


def main() -> None:
    """List available scenarios without executing the future harness."""

    for scenario in SCENARIOS:
        print(f"{scenario.scenario_id}: {scenario.title}")


if __name__ == "__main__":
    main()
