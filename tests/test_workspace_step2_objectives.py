from __future__ import annotations

import unittest

from core.source_policy import SourceCategory
from services.retrieval.workspace.step2.constants import (
    DEFAULT_REQUIRED_RETRIEVAL_ROLES,
    INTENT_DEFECT_LOCALIZATION,
    OBJECTIVE_BEHAVIOR_PATH,
    OBJECTIVE_CONFIGURATION_CONTEXT,
    OBJECTIVE_DIAGNOSTIC_SURFACE,
    OBJECTIVE_EFFECTS_OUTPUT,
    OBJECTIVE_IMPLEMENTATION_OWNER,
    OBJECTIVE_USAGE_CONTRACT,
    OBJECTIVE_VERIFICATION_REPRO,
    SPECIFICITY_NARROW,
)
from services.retrieval.workspace.step2.schema import validate_step2_planner_response
from services.retrieval.workspace.step2.step2 import _normalize_objectives, _prompt_signal_flags
from services.retrieval.workspace.step2.types import PromptEvidence, WorkspaceRetrievalPlan
from services.retrieval.workspace.stage import (
    _legacy_required_roles_for_objectives,
    _legacy_supporting_roles_for_objectives,
)


class WorkspaceStep2ObjectiveTests(unittest.TestCase):
    def test_validator_preserves_planner_metadata_without_changing_legacy_roles(self) -> None:
        response = _planner_response(
            active_objectives=[OBJECTIVE_IMPLEMENTATION_OWNER, OBJECTIVE_DIAGNOSTIC_SURFACE],
            deferred_objectives=[OBJECTIVE_BEHAVIOR_PATH],
        )

        validated = validate_step2_planner_response(
            response,
            allowed_sources=(SourceCategory.SOURCE_CODE,),
        )

        self.assertEqual(validated["primary_intent"], INTENT_DEFECT_LOCALIZATION)
        self.assertEqual(validated["specificity"], SPECIFICITY_NARROW)
        self.assertEqual(
            validated["active_objectives"],
            [OBJECTIVE_IMPLEMENTATION_OWNER, OBJECTIVE_DIAGNOSTIC_SURFACE],
        )
        self.assertEqual(validated["deferred_objectives"], [OBJECTIVE_BEHAVIOR_PATH])

        plan = WorkspaceRetrievalPlan(
            conversation_id="conv",
            raw_prompt="Bug with wrong SSR output.",
            raw_prompt_evidence=("wrong SSR output",),
            prompt_summary=validated["prompt_summary"],
            retrieval_terms=tuple(validated["retrieval_terms"]),
            surface_context_terms=tuple(validated["surface_context_terms"]),
            owner_artifact_terms=tuple(validated["owner_artifact_terms"]),
            grounded_entities=(),
            confirmed_entities=(),
            grounded_file_hints=(),
            confirmed_file_hints=(),
            llm_concept_terms=tuple(validated["llm_concept_terms"]),
            llm_subqueries=tuple(validated["llm_subqueries"]),
            owner_subqueries=tuple(validated["owner_subqueries"]),
            support_subqueries=tuple(validated["support_subqueries"]),
            speculative_entities=tuple(validated["speculative_entities"]),
            source_priorities=(SourceCategory.SOURCE_CODE,),
            negative_filters=tuple(validated["negative_filters"]),
            required_roles=DEFAULT_REQUIRED_RETRIEVAL_ROLES,
            supporting_roles=(),
            primary_intent=validated["primary_intent"],
            specificity=validated["specificity"],
            active_objectives=tuple(validated["active_objectives"]),
            deferred_objectives=tuple(validated["deferred_objectives"]),
        )

        self.assertEqual(plan.required_roles, DEFAULT_REQUIRED_RETRIEVAL_ROLES)
        self.assertEqual(plan.to_dict()["active_objectives"], [OBJECTIVE_IMPLEMENTATION_OWNER, OBJECTIVE_DIAGNOSTIC_SURFACE])

    def test_prompt_signal_flags_detect_native_repro_and_wrong_output(self) -> None:
        evidence = PromptEvidence(
            raw_prompt_evidence=("vue/test/ssr/ssr-string.spec.js", "<textarea>null</textarea>"),
            grounded_entities=(),
            grounded_file_hints=(),
            source_priorities=(SourceCategory.SOURCE_CODE,),
        )

        flags = _prompt_signal_flags(
            "What is expected? <textarea></textarea>\nWhat is actually happening? <textarea>null</textarea>\nexpect(result).toContain(...)",
            evidence,
        )

        self.assertTrue(flags["has_wrong_output"])
        self.assertFalse(flags["has_diagnostic_surface"])
        self.assertTrue(flags["has_output_symptom"])
        self.assertTrue(flags["has_native_repro"])

    def test_narrow_defect_normalization_defers_unproven_diagnostic_and_repro(self) -> None:
        active, deferred = _normalize_objectives(
            primary_intent=INTENT_DEFECT_LOCALIZATION,
            specificity=SPECIFICITY_NARROW,
            active_objectives=(
                OBJECTIVE_IMPLEMENTATION_OWNER,
                OBJECTIVE_DIAGNOSTIC_SURFACE,
                OBJECTIVE_VERIFICATION_REPRO,
                OBJECTIVE_CONFIGURATION_CONTEXT,
            ),
            deferred_objectives=(),
            prompt_signal_flags={
                "has_diagnostic_surface": False,
                "has_output_symptom": False,
                "has_native_repro": False,
                "mentions_config": False,
            },
        )

        self.assertEqual(active, (OBJECTIVE_IMPLEMENTATION_OWNER,))
        self.assertIn(OBJECTIVE_DIAGNOSTIC_SURFACE, deferred)
        self.assertIn(OBJECTIVE_VERIFICATION_REPRO, deferred)
        self.assertIn(OBJECTIVE_CONFIGURATION_CONTEXT, deferred)
        self.assertIn(OBJECTIVE_BEHAVIOR_PATH, deferred)
        self.assertIn(OBJECTIVE_USAGE_CONTRACT, deferred)

    def test_narrow_defect_wrong_output_uses_effects_not_diagnostics(self) -> None:
        active, deferred = _normalize_objectives(
            primary_intent=INTENT_DEFECT_LOCALIZATION,
            specificity=SPECIFICITY_NARROW,
            active_objectives=(OBJECTIVE_IMPLEMENTATION_OWNER, OBJECTIVE_DIAGNOSTIC_SURFACE),
            deferred_objectives=(),
            prompt_signal_flags={
                "has_diagnostic_surface": False,
                "has_output_symptom": True,
                "has_native_repro": False,
                "mentions_config": False,
            },
        )

        self.assertEqual(active, (OBJECTIVE_IMPLEMENTATION_OWNER, OBJECTIVE_EFFECTS_OUTPUT))
        self.assertIn(OBJECTIVE_DIAGNOSTIC_SURFACE, deferred)

    def test_objective_role_selection_maps_owner_to_minimal_legacy_owner_roles(self) -> None:
        required_roles = _legacy_required_roles_for_objectives((OBJECTIVE_IMPLEMENTATION_OWNER,))
        supporting_roles = _legacy_supporting_roles_for_objectives(
            (OBJECTIVE_VERIFICATION_REPRO, OBJECTIVE_CONFIGURATION_CONTEXT, OBJECTIVE_USAGE_CONTRACT)
        )

        self.assertEqual(required_roles, ("behavior_output", "validation_checking"))
        self.assertEqual(supporting_roles, ("tests", "config", "docs"))


def _planner_response(*, active_objectives: list[str], deferred_objectives: list[str]) -> dict[str, object]:
    return {
        "prompt_summary": "Wrong SSR textarea output.",
        "retrieval_terms": ["SSR textarea domProps"],
        "surface_context_terms": ["SSR textarea"],
        "owner_artifact_terms": ["domProps"],
        "llm_concept_terms": ["SSR"],
        "llm_subqueries": [{"role": "behavior_output", "query": "Where is SSR textarea output generated?"}],
        "owner_subqueries": [{"role": "behavior_output", "query": "Where is SSR textarea output generated?"}],
        "support_subqueries": [],
        "speculative_entities": [],
        "source_priorities": ["source_code"],
        "negative_filters": ["harness"],
        "primary_intent": INTENT_DEFECT_LOCALIZATION,
        "secondary_intents": [],
        "specificity": SPECIFICITY_NARROW,
        "active_objectives": active_objectives,
        "deferred_objectives": deferred_objectives,
        "preferred_relations": ["implemented_by"],
        "stop_contract": {
            "required": ["credible_owner"],
            "one_of": ["observable_behavior"],
            "sufficient_when": "owner explains symptom",
        },
        "expansion_policy": {
            "on_missing_owner": ["broaden_structured_code_fields"],
            "on_missing_causal_path": ["promote:behavior_path"],
            "on_missing_expected_behavior": ["promote:verification_repro"],
            "on_low_query_specificity": ["reduce_noise_terms"],
        },
    }


if __name__ == "__main__":
    unittest.main()
