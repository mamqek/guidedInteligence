from __future__ import annotations

from services.intent.models import IntentContract, IntentQuestionContract, IntentStage, TaskIntent


def _stages(intent: TaskIntent, values: tuple[tuple[str, str, str], ...]) -> tuple[IntentStage, ...]:
    return tuple(IntentStage(id=f"{intent.value}.{suffix}", label=label, purpose=purpose) for suffix, label, purpose in values)


INTENT_CONTRACTS: dict[TaskIntent, IntentContract] = {
    TaskIntent.EXPLORE: IntentContract(
        intent=TaskIntent.EXPLORE,
        retrieval_description="Locate and orient the user within the relevant repository area and its major relationships.",
        stages=_stages(TaskIntent.EXPLORE, (
            ("what_it_is", "what it is", "Identify the requested repository subject and its responsibility."),
            ("owners_users", "owners and users", "Locate the main owners and important consumers."),
            ("major_relationships", "major relationships", "Map how the important pieces relate."),
            ("boundaries", "boundaries", "State the relevant subsystem or responsibility boundaries."),
            ("entry_points", "entry points", "Give focused places from which the user can continue navigating."),
        )),
        evidence_expectations=("scope anchors", "owners", "entry points", "boundaries", "major relations"),
        stop_condition="Stop when ownership, navigation, and major relationships are clear.",
        question=IntentQuestionContract(
            prerequisite_stage_ids=("explore.what_it_is", "explore.owners_users", "explore.major_relationships"),
            stem_families=("what", "where", "which"),
            stem_descriptions={
                "what": "Test the responsibility or meaning of the repository subject.",
                "where": "Test where ownership or an important boundary is located.",
                "which": "Test which entry point or relationship matters for the user's navigation goal.",
            },
        ),
        constrained_assistance="Show where to investigate and why each entry point matters without doing the user's task.",
    ),
    TaskIntent.EXPLAIN: IntentContract(
        intent=TaskIntent.EXPLAIN,
        retrieval_description="Establish how or why the requested behavior works.",
        stages=_stages(TaskIntent.EXPLAIN, (
            ("subject", "subject", "Identify the behavior or mechanism being explained."),
            ("trigger", "trigger", "Establish what starts or enables the behavior."),
            ("ordered_mechanism", "ordered mechanism", "Follow the relevant execution or causal path."),
            ("state_changes", "state changes", "Explain meaningful state or representation changes."),
            ("resulting_effect", "resulting effect", "Connect the mechanism to its observable outcome."),
            ("why", "why", "State why the established path produces that outcome."),
        )),
        evidence_expectations=("trigger or entry", "relevant state", "ordered behavior path", "constraints", "observable effect"),
        stop_condition="Stop when the requested mechanism is supported from trigger to effect, or the missing link is explicit.",
        question=IntentQuestionContract(
            prerequisite_stage_ids=("explain.trigger", "explain.ordered_mechanism", "explain.resulting_effect"),
            stem_families=("how", "why", "what_causes"),
            stem_descriptions={
                "how": "Test an important mechanism or handoff from trigger to effect.",
                "why": "Test why a supported relationship produces its stated outcome.",
                "what_causes": "Test the supported cause of a behavior or state change.",
            },
        ),
        constrained_assistance="Explain the mechanism and ask the user to reason over a key transition.",
    ),
    TaskIntent.USE: IntentContract(
        intent=TaskIntent.USE,
        retrieval_description="Establish how an existing interface is invoked, configured, or integrated.",
        stages=_stages(TaskIntent.USE, (
            ("goal", "goal", "State the outcome the interface is used to achieve."),
            ("prerequisites", "prerequisites", "Establish required setup, state, or inputs."),
            ("contract", "contract", "Explain the public interface and its guarantees."),
            ("invocation", "invocation", "Show how the interface is called or configured."),
            ("result", "result", "Describe the expected result."),
            ("constraints", "common constraints", "State important usage constraints and failure conditions."),
        )),
        evidence_expectations=("interface", "inputs", "preconditions", "configuration", "expected result"),
        stop_condition="Stop when correct usage and its expected outcome are clear without unnecessary internals.",
        question=IntentQuestionContract(
            prerequisite_stage_ids=("use.prerequisites", "use.contract", "use.invocation", "use.result"),
            stem_families=("how", "what_is_required", "when"),
            stem_descriptions={
                "how": "Test how to invoke or configure the interface correctly.",
                "what_is_required": "Test a prerequisite, required input, or setup condition.",
                "when": "Test when the interface or constraint applies.",
            },
        ),
        constrained_assistance="Teach the contract and guide the next usage step without completing prohibited work.",
    ),
    TaskIntent.DEBUG: IntentContract(
        intent=TaskIntent.DEBUG,
        retrieval_description="Investigate the reported abnormal behavior and its likely cause.",
        stages=_stages(TaskIntent.DEBUG, (
            ("symptom", "symptom", "State the observed abnormal behavior."),
            ("expected_actual", "expected versus actual", "Contrast expected and observed behavior."),
            ("evidence", "diagnostic evidence", "Present the evidence that localizes or discriminates the failure."),
            ("cause", "cause", "Connect the evidence to the supported cause or unresolved causal boundary."),
            ("next_check", "next diagnostic check", "Give the next observation that would confirm or distinguish the cause."),
        )),
        evidence_expectations=("expected and actual behavior", "diagnostic surface", "implementation owner", "causal path", "relevant constraint"),
        stop_condition="Stop when the cause is supported or the unresolved diagnostic gap is precise.",
        question=IntentQuestionContract(
            prerequisite_stage_ids=("debug.symptom", "debug.evidence", "debug.cause"),
            stem_families=("why", "where", "how_does_it_fail", "what_distinguishes"),
            stem_descriptions={
                "why": "Test the supported causal link between the symptom and its cause.",
                "where": "Test where expected and actual behavior first diverge.",
                "how_does_it_fail": "Test the failure mechanism along the relevant execution path.",
                "what_distinguishes": "Test which next observation separates competing explanations.",
            },
        ),
        constrained_assistance="Guide diagnosis and the next discriminating check without silently producing a complete fix.",
    ),
    TaskIntent.CHANGE: IntentContract(
        intent=TaskIntent.CHANGE,
        retrieval_description="Gather context needed to reason about a requested modification without implementing it.",
        stages=_stages(TaskIntent.CHANGE, (
            ("current_behavior", "current behavior", "Establish the current behavior or limitation."),
            ("change_surface", "change surface", "Identify the relevant modification points."),
            ("constraints", "constraints", "State invariants and restrictions the change must preserve."),
            (
                "affected_paths",
                "affected paths",
                "Identify affected locations and only the dependents or consequences that are plausible for the requested kind of change.",
            ),
            ("validation", "validation", "Describe how the proposed direction would be checked."),
        )),
        evidence_expectations=("current owner and behavior", "change points", "constraints", "affected dependents", "validation surface"),
        stop_condition="Stop at the assistance boundary chosen by policy after the change surface and consequences are clear.",
        question=IntentQuestionContract(
            prerequisite_stage_ids=("change.current_behavior", "change.change_surface", "change.constraints"),
            stem_families=("what_must_change", "where", "how_would_this_affect"),
            stem_descriptions={
                "what_must_change": "Test the behavior or contract that must be modified.",
                "where": "Test the correct modification point or responsibility boundary.",
                "how_would_this_affect": "Test an important consequence for a dependent path or invariant.",
            },
        ),
        constrained_assistance="Identify change points, trade-offs, and a next reasoning step; withhold a complete patch when required.",
    ),
    TaskIntent.PLAN: IntentContract(
        intent=TaskIntent.PLAN,
        retrieval_description="Gather context needed to propose an ordered future approach.",
        stages=_stages(TaskIntent.PLAN, (
            ("goal", "goal", "Define the desired future outcome."),
            ("dependencies", "dependencies", "Establish prerequisites and ordering constraints."),
            ("ordered_steps", "ordered steps", "Lay out the proposed implementation sequence."),
            ("risks", "risks", "Identify material risks and trade-offs."),
            ("validation_points", "validation points", "Define checks for important milestones and the final outcome."),
        )),
        evidence_expectations=("goal", "current state", "dependencies", "constraints", "risks", "validation points"),
        stop_condition="Stop when step outcomes, ordering dependencies, risks, and validation are explicit.",
        question=IntentQuestionContract(
            prerequisite_stage_ids=("plan.dependencies", "plan.ordered_steps", "plan.validation_points"),
            stem_families=("what_comes_first", "why_this_order", "what_must_be_verified"),
            stem_descriptions={
                "what_comes_first": "Test the first step required by the dependencies.",
                "why_this_order": "Test the reason one planned step must precede another.",
                "what_must_be_verified": "Test the evidence needed at an important milestone.",
            },
        ),
        constrained_assistance="Provide a grounded plan while leaving execution to the user.",
    ),
    TaskIntent.REVIEW: IntentContract(
        intent=TaskIntent.REVIEW,
        retrieval_description="Gather context needed to assess an artifact or approach against relevant criteria.",
        stages=_stages(TaskIntent.REVIEW, (
            ("scope", "scope", "Identify the artifact and limits of the review."),
            ("criteria", "criteria", "State the standards used for judgment."),
            ("findings", "findings", "Present supported strengths, weaknesses, or comparisons."),
            ("consequences", "consequences", "Explain why the findings matter."),
            ("improvement_directions", "improvement directions", "Suggest bounded directions for improvement."),
        )),
        evidence_expectations=("reviewed artifact", "criteria", "observed evidence", "alternatives", "consequences"),
        stop_condition="Stop when every judgment names its criterion and supporting evidence.",
        question=IntentQuestionContract(
            prerequisite_stage_ids=("review.criteria", "review.findings", "review.consequences"),
            stem_families=("should", "which_is_better", "what_is_the_risk", "why_is_this_preferable"),
            stem_descriptions={
                "should": "Test a judgment against the stated review criteria.",
                "which_is_better": "Test a comparison using the relevant criteria and evidence.",
                "what_is_the_risk": "Test the consequence of a supported weakness or trade-off.",
                "why_is_this_preferable": "Test why one approach better satisfies the stated criteria.",
            },
        ),
        constrained_assistance="Surface issues and improvement directions without automatically rewriting the artifact.",
    ),
    TaskIntent.VERIFY: IntentContract(
        intent=TaskIntent.VERIFY,
        retrieval_description="Gather context needed to determine whether a concrete claim is supported.",
        stages=_stages(TaskIntent.VERIFY, (
            ("claim", "claim", "State the concrete claim under examination."),
            ("observable_condition", "observable condition", "Define what would confirm or refute it."),
            ("evidence", "verification evidence", "Present relevant tests, assertions, or observations."),
            ("result", "result", "Classify the claim as supported, refuted, or unverified."),
            ("remaining_uncertainty", "remaining uncertainty", "State gaps, counterevidence, or confidence limits."),
        )),
        evidence_expectations=("claim", "observable condition", "test or assertion", "result", "gaps or counterevidence"),
        stop_condition="Stop with a supported, refuted, or explicitly unverified result.",
        question=IntentQuestionContract(
            prerequisite_stage_ids=("verify.claim", "verify.observable_condition", "verify.evidence"),
            stem_families=("does", "is", "what_proves", "how_is_it_tested"),
            stem_descriptions={
                "does": "Test whether the evidence supports the concrete behavioral claim.",
                "is": "Test whether a stated condition or classification is supported.",
                "what_proves": "Test which observation or assertion establishes the claim.",
                "how_is_it_tested": "Test how the claim is checked in the repository.",
            },
        ),
        constrained_assistance="Show how confidence is established and identify missing proof without fabricating verification.",
    ),
}


def get_intent_contract(intent: TaskIntent) -> IntentContract:
    return INTENT_CONTRACTS[intent]


def validate_contract_registry() -> None:
    if set(INTENT_CONTRACTS) != set(TaskIntent):
        missing = sorted(intent.value for intent in set(TaskIntent) - set(INTENT_CONTRACTS))
        extra = sorted(str(intent) for intent in set(INTENT_CONTRACTS) - set(TaskIntent))
        raise RuntimeError(f"Intent contract registry mismatch; missing={missing}, extra={extra}.")
    stage_ids: set[str] = set()
    for intent, contract in INTENT_CONTRACTS.items():
        if contract.intent is not intent or not contract.retrieval_description.strip() or not contract.stages:
            raise RuntimeError(f"Incomplete intent contract: {intent.value}.")
        if not contract.evidence_expectations or not contract.question.stem_families:
            raise RuntimeError(f"Intent contract lacks evidence or question contract: {intent.value}.")
        if set(contract.question.stem_descriptions) != set(contract.question.stem_families):
            raise RuntimeError(f"Intent question descriptions do not match stem families: {intent.value}.")
        current_ids = {stage.id for stage in contract.stages}
        if len(current_ids) != len(contract.stages) or any(not stage_id.startswith(f"{intent.value}.") for stage_id in current_ids):
            raise RuntimeError(f"Invalid stage IDs for intent: {intent.value}.")
        if stage_ids.intersection(current_ids):
            raise RuntimeError(f"Duplicate stage ID across intent contracts: {intent.value}.")
        if not set(contract.question.prerequisite_stage_ids).issubset(current_ids):
            raise RuntimeError(f"Question prerequisites reference unknown stages: {intent.value}.")
        stage_ids.update(current_ids)


validate_contract_registry()
