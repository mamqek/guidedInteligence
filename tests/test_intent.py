from __future__ import annotations

import unittest

from services.intent.classifier import (
    _explicit_prompt_paths,
    _explicit_prompt_symbols,
    _preserve_explicit_prompt_anchors,
    _preserve_explicit_prompt_paths,
)

from services.intent import (
    INTENT_CONTRACTS,
    EvidenceBoundary,
    IntentClassification,
    IntentClassificationInput,
    EvidenceRole,
    EvidenceSource,
    SolutionPressure,
    Specificity,
    TargetReference,
    TargetState,
    TargetType,
    TaskIntent,
    TurnRelation,
    build_intent_context,
    classify_intent,
    classification_from_mapping,
    compose_intent_flow,
    normalize_intent,
    summarize_statuses,
    validate_contract_registry,
    validate_stage_permutation,
)
from services.intent.schema import intent_response_format


class _Config:
    model = "test-intent-model"


class IntentSystemTests(unittest.TestCase):
    def test_explicit_prompt_paths_are_preserved_without_model_reinterpretation(self) -> None:
        prompt = "Change src/pure/session.ts, then inspect src/main/index.ts."
        response = {
            "anchors": {
                "paths": ["src/server/session.ts", "src/pure/session.ts"],
                "symbols": ["Session"],
            }
        }

        preserved = _preserve_explicit_prompt_paths(response, prompt)

        self.assertEqual(preserved["anchors"]["paths"], ["src/pure/session.ts", "src/main/index.ts"])
        self.assertEqual(preserved["anchors"]["symbols"], ["Session"])

    def test_explicit_prompt_path_parser_handles_repo_and_windows_paths(self) -> None:
        self.assertEqual(
            _explicit_prompt_paths("See `services/intent/classifier.py` and C:\\repo\\src\\main.ts."),
            ("services/intent/classifier.py", "C:\\repo\\src\\main.ts"),
        )

    def test_prompt_symbols_are_conservative_and_identifier_shaped(self) -> None:
        prompt = (
            "Add a field to the Session type, then call renderVmWithOptions({ value: null }). "
            "The interface type should produce a type error."
        )

        self.assertEqual(_explicit_prompt_symbols(prompt), ("Session", "renderVmWithOptions"))

        response = {
            "anchors": {
                "paths": [],
                "symbols": ["Session", "project references", "unmentionedSymbol"],
                "errors": [],
                "literals": [],
                "identifiers": [],
            }
        }
        normalized = _preserve_explicit_prompt_anchors(response, prompt)
        self.assertEqual(normalized["anchors"]["symbols"], ["Session", "renderVmWithOptions"])

    def test_prompt_symbols_keep_literal_pascal_and_lowercase_api_names(self) -> None:
        prompt = "Series arithmetic differs from Series.add when calling add(s2)."
        response = {
            "anchors": {
                "paths": [],
                "symbols": ["Series", "add", "Series.add", "inventedOwner"],
                "errors": [],
                "literals": [],
                "identifiers": [],
            }
        }

        normalized = _preserve_explicit_prompt_anchors(response, prompt)

        self.assertEqual(normalized["anchors"]["symbols"], ["Series", "add", "Series.add"])

    def test_registry_has_one_complete_contract_per_intent(self) -> None:
        validate_contract_registry()
        self.assertEqual(set(INTENT_CONTRACTS), set(TaskIntent))

    def test_change_affected_paths_contract_requires_proportionate_impact(self) -> None:
        stage = next(stage for stage in INTENT_CONTRACTS[TaskIntent.CHANGE].stages if stage.id == "change.affected_paths")
        self.assertIn("plausible for the requested kind of change", stage.purpose)
        self.assertTrue(all(contract.stages and contract.question.stem_families for contract in INTENT_CONTRACTS.values()))

    def test_classifier_schema_contains_only_new_task_intent_shape(self) -> None:
        schema = intent_response_format()["json_schema"]["schema"]
        decisions = schema["properties"]["intent_decisions"]
        self.assertEqual(set(decisions["properties"]), {intent.value for intent in TaskIntent})
        self.assertNotIn("intents", schema["properties"])
        self.assertNotIn("evidence_obligations", schema["properties"])
        self.assertNotIn("user_goals", schema["properties"])
        self.assertNotIn("response_operation", schema["properties"])
        self.assertNotIn("retrieval_intents", schema["properties"])
        self.assertNotIn("expected_outputs", schema["properties"])
        self.assertNotIn("uniqueItems", decisions)

    def test_duplicate_intents_are_rejected_after_schema_parsing(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate TaskIntent"):
            classification_from_mapping(
                {
                    "intents": ["explore", "explore"],
                    "turn_relation": "new_task",
                    "solution_pressure": "none",
                    "specificity": "medium",
                    "target_state": "unresolved",
                    "explicit_targets": [],
                    "confidence": 0.9,
                    "classification_basis": ["test"],
                }
            )

    def test_classifier_preserves_multiple_requested_outcomes_without_priority(self) -> None:
        calls = 0

        def complete_json_fn(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                return _analysis_response((TaskIntent.DEBUG, TaskIntent.CHANGE))
            if calls == 2:
                return _stage_response((TaskIntent.DEBUG, TaskIntent.CHANGE))
            return _group_response((TaskIntent.DEBUG, TaskIntent.CHANGE))

        result = classify_intent(
            IntentClassificationInput(user_prompt="Explain why saveUser fails and fix it."),
            llm_config=_Config(),
            complete_json_fn=complete_json_fn,
        )

        self.assertEqual(result.status, "success")
        self.assertEqual(result.classification.intents, (TaskIntent.DEBUG, TaskIntent.CHANGE))
        self.assertEqual(calls, 3)

    def test_classifier_derives_causal_owner_role_without_repair(self) -> None:
        calls = 0

        def complete_json_fn(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                return _analysis_response((TaskIntent.DEBUG,))
            return _stage_response((TaskIntent.DEBUG,))

        result = classify_intent(
            IntentClassificationInput(user_prompt="Why does this fail?"),
            llm_config=_Config(),
            complete_json_fn=complete_json_fn,
        )

        self.assertEqual(result.status, "success")
        self.assertEqual(calls, 2)
        cause = next(item for item in result.classification.evidence_obligations if item.stage_ids == ("debug.cause",))
        self.assertEqual(cause.evidence_role, EvidenceRole.IMPLEMENTATION)

    def test_classifier_applies_constrained_symbol_relevance(self) -> None:
        calls = 0

        def complete_json_fn(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                response = _analysis_response((TaskIntent.EXPLAIN,))
                response["anchors"]["symbols"] = ["renderVmWithOptions", "toContain"]
                return response
            response = _stage_response((TaskIntent.EXPLAIN,), symbols=("renderVmWithOptions", "toContain"))
            response["symbol_decisions"]["toContain"] = {
                "relevance": "ignore",
                "reason": "Only checks the rendered result.",
            }
            return response

        result = classify_intent(
            IntentClassificationInput(
                user_prompt="Explain renderVmWithOptions({ value: null }); expect(html).toContain('null')."
            ),
            llm_config=_Config(),
            complete_json_fn=complete_json_fn,
        )

        self.assertEqual(result.status, "success")
        self.assertEqual(result.classification.anchors.primary_symbols, ("renderVmWithOptions",))
        self.assertEqual(result.classification.anchors.supporting_symbols, ())

    def test_classifier_preserves_supporting_symbols_separately(self) -> None:
        calls = 0

        def complete_json_fn(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                response = _analysis_response((TaskIntent.EXPLAIN,))
                response["anchors"]["symbols"] = ["isNaN"]
                return response
            response = _stage_response((TaskIntent.EXPLAIN,), symbols=("isNaN",))
            response["symbol_decisions"]["isNaN"] = {
                "relevance": "supporting",
                "reason": "Appears only in the reported workaround.",
            }
            return response

        result = classify_intent(
            IntentClassificationInput(user_prompt="The workaround calls isNaN(path). Explain the underlying behavior."),
            llm_config=_Config(),
            complete_json_fn=complete_json_fn,
        )

        self.assertEqual(result.status, "success")
        self.assertEqual(result.classification.anchors.primary_symbols, ())
        self.assertEqual(result.classification.anchors.supporting_symbols, ("isNaN",))

    def test_classifier_merges_compatible_stage_requirements(self) -> None:
        calls = 0

        def complete_json_fn(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                return _analysis_response((TaskIntent.EXPLAIN, TaskIntent.USE))
            if calls == 2:
                return _stage_response((TaskIntent.EXPLAIN, TaskIntent.USE))
            response = _group_response((TaskIntent.EXPLAIN, TaskIntent.USE))
            response["stage_groups"]["use.contract"]["evidence_group_leader"] = "explain.subject"
            response["stage_groups"]["use.invocation"]["evidence_group_leader"] = "explain.subject"
            return response

        result = classify_intent(
            IntentClassificationInput(user_prompt="Explain the interface and show how to use it."),
            llm_config=_Config(),
            complete_json_fn=complete_json_fn,
        )

        self.assertEqual(result.status, "success")
        grouped = next(
            obligation
            for obligation in result.classification.evidence_obligations
            if "use.contract" in obligation.stage_ids
        )
        self.assertEqual(grouped.stage_ids, ("explain.subject", "use.contract", "use.invocation"))

    def test_classifier_keeps_repository_stage_when_boundary_is_external(self) -> None:
        calls = 0

        def complete_json_fn(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                return _analysis_response((TaskIntent.EXPLAIN,))
            response = _stage_response((TaskIntent.EXPLAIN,))
            response["stage_requirements"]["explain.ordered_mechanism"]["evidence_boundary"] = (
                "local_to_external_handoff"
            )
            response["stage_requirements"]["explain.why"]["evidence_boundary"] = "external"
            return response

        result = classify_intent(
            IntentClassificationInput(
                user_prompt="Explain how pandas hands this operation to PyTables.",
                repository_name="pandas",
            ),
            llm_config=_Config(),
            complete_json_fn=complete_json_fn,
        )

        self.assertEqual(result.status, "success")
        handoff = next(
            obligation
            for obligation in result.classification.evidence_obligations
            if "explain.ordered_mechanism" in obligation.stage_ids
        )
        external = next(
            obligation
            for obligation in result.classification.evidence_obligations
            if "explain.why" in obligation.stage_ids
        )
        self.assertEqual(handoff.evidence_boundary, EvidenceBoundary.LOCAL_TO_EXTERNAL_HANDOFF)
        self.assertEqual(handoff.evidence_source, EvidenceSource.REPOSITORY)
        self.assertEqual(external.evidence_boundary, EvidenceBoundary.EXTERNAL)
        self.assertEqual(external.evidence_source, EvidenceSource.REPOSITORY)
        self.assertTrue(external.requires_repository_handoff)

    def test_classifier_failure_is_explicit_and_has_no_fallback(self) -> None:
        result = classify_intent(
            IntentClassificationInput(user_prompt="Explain this."),
            llm_config=_Config(),
            complete_json_fn=lambda *_args, **_kwargs: _analysis_response(()),
        )
        self.assertEqual(result.status, "failed")
        self.assertIsNone(result.classification)
        self.assertFalse(result.fallback_used)

    def test_request_analysis_preserves_exact_anchor_refs_and_evidence_role(self) -> None:
        classification = classification_from_mapping(
            {
                "intents": ["explain"],
                "turn_relation": "new_task",
                "solution_pressure": "none",
                "specificity": "narrow",
                "target_state": "explicit",
                "explicit_targets": [],
                "confidence": 0.9,
                "classification_basis": ["test"],
                "anchors": {
                    "paths": ["test/ssr.spec.js"],
                    "primary_symbols": ["renderDOMProps"],
                    "supporting_symbols": [],
                    "errors": [],
                    "literals": [],
                    "identifiers": [],
                },
                "search_terms": ["textarea SSR"],
                "evidence_obligations": [
                    {
                        "id": "runtime_path",
                        "description": "Trace textarea SSR rendering.",
                        "required": True,
                        "depends_on": [],
                        "anchor_refs": ["renderDOMProps", "invented"],
                        "evidence_role": "implementation",
                        "evidence_source": "repository",
                    }
                ],
            }
        )

        obligation = classification.evidence_obligations[0]
        self.assertEqual(obligation.anchor_refs, ("renderDOMProps",))
        self.assertEqual(obligation.evidence_role, EvidenceRole.IMPLEMENTATION)
        self.assertEqual(obligation.evidence_source, EvidenceSource.REPOSITORY)
        self.assertEqual(obligation.evidence_boundary, EvidenceBoundary.LOCAL)

    def test_unknown_and_forward_obligation_dependencies_are_discarded_without_failing_analysis(self) -> None:
        classification = classification_from_mapping(
            {
                "intents": ["explain"],
                "turn_relation": "new_task",
                "solution_pressure": "none",
                "specificity": "narrow",
                "target_state": "unresolved",
                "explicit_targets": [],
                "confidence": 0.9,
                "classification_basis": ["test"],
                "anchors": {
                    "paths": [],
                    "primary_symbols": [],
                    "supporting_symbols": [],
                    "errors": [],
                    "literals": [],
                    "identifiers": [],
                },
                "search_terms": [],
                "evidence_obligations": [
                    {
                        "id": "trigger",
                        "description": "Establish the trigger.",
                        "required": True,
                        "depends_on": ["mechanism", "missing"],
                        "anchor_refs": [],
                        "evidence_role": "implementation",
                    },
                    {
                        "id": "mechanism",
                        "description": "Trace the mechanism.",
                        "required": True,
                        "depends_on": ["trigger", "missing"],
                        "anchor_refs": [],
                        "evidence_role": "implementation",
                    },
                ],
            }
        )

        self.assertEqual(classification.evidence_obligations[0].depends_on, ())
        self.assertEqual(classification.evidence_obligations[1].depends_on, ("trigger",))

    def test_impossible_handoff_flags_are_normalized(self) -> None:
        classification = classification_from_mapping(
            {
                "intents": ["explain"],
                "turn_relation": "new_task",
                "solution_pressure": "none",
                "specificity": "narrow",
                "target_state": "unresolved",
                "explicit_targets": [],
                "confidence": 0.9,
                "classification_basis": ["test"],
                "anchors": {
                    "paths": [],
                    "primary_symbols": [],
                    "supporting_symbols": [],
                    "errors": [],
                    "literals": [],
                    "identifiers": [],
                },
                "search_terms": [],
                "evidence_obligations": [
                    {
                        "id": "reported_behavior",
                        "description": "Record the behavior reported by the user.",
                        "required": True,
                        "depends_on": [],
                        "anchor_refs": [],
                        "evidence_role": "implementation",
                        "evidence_source": "prompt",
                        "stage_ids": ["explain.subject"],
                        "requires_repository_handoff": True,
                    }
                ],
            }
        )

        obligation = classification.evidence_obligations[0]
        self.assertEqual(obligation.evidence_role, EvidenceRole.ANY)
        self.assertFalse(obligation.requires_repository_handoff)

    def test_minimal_retrieval_context_excludes_flow_and_evidence_contracts(self) -> None:
        classification = _classification((TaskIntent.EXPLAIN, TaskIntent.EXPLORE))
        value = build_intent_context(classification).to_dict()

        self.assertEqual([item["intent"] for item in value["intents"]], ["explain", "explore"])
        serialized = str(value)
        self.assertNotIn("stages", serialized)
        self.assertNotIn("evidence_expectations", serialized)
        self.assertNotIn("question", serialized)

    def test_normalizer_removes_invented_literal_target(self) -> None:
        classification = IntentClassification(
            **{
                **_classification((TaskIntent.EXPLAIN,)).__dict__,
                "target_state": TargetState.EXPLICIT,
                "explicit_targets": (TargetReference(TargetType.FUNCTION, "missingFunction"),),
            }
        )
        normalized = normalize_intent(classification, user_prompt="How does authentication work?")
        self.assertEqual(normalized.classification.explicit_targets, ())
        self.assertEqual(normalized.classification.target_state, TargetState.UNRESOLVED)

    def test_composer_unions_all_fixed_stages_without_merging(self) -> None:
        flow = compose_intent_flow((TaskIntent.DEBUG, TaskIntent.CHANGE))
        expected = tuple(
            stage.id
            for intent in (TaskIntent.DEBUG, TaskIntent.CHANGE)
            for stage in INTENT_CONTRACTS[intent].stages
        )
        self.assertEqual(flow.contract_stage_ids, expected)
        self.assertEqual(len(flow.contract_stage_ids), len(set(flow.contract_stage_ids)))

    def test_flow_validation_accepts_only_an_exact_permutation(self) -> None:
        required = ("debug.symptom", "debug.evidence", "debug.cause")
        self.assertEqual(validate_stage_permutation(required, tuple(reversed(required))), ())
        errors = validate_stage_permutation(required, ("debug.symptom", "debug.symptom", "invented"))
        self.assertTrue(any("missing" in error for error in errors))
        self.assertTrue(any("unknown" in error for error in errors))
        self.assertTrue(any("duplicated" in error for error in errors))

    def test_sufficiency_summary_is_deterministic(self) -> None:
        self.assertEqual(summarize_statuses(("covered", "covered")), "covered")
        self.assertEqual(summarize_statuses(("missing", "missing")), "missing")
        self.assertEqual(summarize_statuses(("unclear", "unclear")), "unclear")
        self.assertEqual(summarize_statuses(("covered", "missing")), "partial")


def _classification(intents: tuple[TaskIntent, ...]) -> IntentClassification:
    return IntentClassification(
        intents=intents,
        turn_relation=TurnRelation.NEW_TASK,
        solution_pressure=SolutionPressure.NONE,
        specificity=Specificity.MEDIUM,
        target_state=TargetState.UNRESOLVED,
        explicit_targets=(),
        confidence=0.9,
        classification_basis=("test",),
    )


def _obligation(obligation_id: str, stage_ids: tuple[str, ...]) -> dict[str, object]:
    return {
        "id": obligation_id,
        "description": f"Establish {obligation_id}.",
        "required": True,
        "depends_on": [],
        "anchor_refs": [],
        "evidence_role": "implementation",
        "evidence_source": "repository",
        "stage_ids": list(stage_ids),
        "requires_repository_handoff": False,
    }


def _analysis_response(intents: tuple[TaskIntent, ...]) -> dict[str, object]:
    selected = set(intents)
    return {
        "intent_decisions": {
            intent.value: {
                "selected": intent in selected,
                "reason": f"{intent.value} decision",
            }
            for intent in TaskIntent
        },
        "turn_relation": "new_task",
        "solution_pressure": "none",
        "specificity": "medium",
        "target_state": "unresolved",
        "explicit_targets": [],
        "confidence": 0.9,
        "anchors": {"paths": [], "symbols": [], "errors": [], "literals": [], "identifiers": []},
        "search_terms": [],
    }


def _stage_response(
    intents: tuple[TaskIntent, ...],
    *,
    symbols: tuple[str, ...] = (),
) -> dict[str, object]:
    return {
        "symbol_decisions": {
            symbol: {"relevance": "primary", "reason": "Directly relevant."}
            for symbol in symbols
        },
        "stage_requirements": {
            stage.id: {
                "evidence_boundary": (
                    "prompt"
                    if stage.id in {"debug.symptom", "debug.expected_actual", "use.goal", "verify.claim", "plan.goal", "review.scope"}
                    else "local"
                ),
                "proposition": f"Establish {stage.id}.",
                "anchor_refs": [],
            }
            for intent in intents
            for stage in INTENT_CONTRACTS[intent].stages
        }
    }


def _group_response(intents: tuple[TaskIntent, ...]) -> dict[str, object]:
    return {
        "stage_groups": {
            stage.id: {"evidence_group_leader": stage.id}
            for intent in intents
            for stage in INTENT_CONTRACTS[intent].stages
        }
    }


if __name__ == "__main__":
    unittest.main()
