from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from services.retrieval.workspace.pipeline.execution_flow.coverage_evaluation import ObligationCoverage
from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import (
    DiscoveryObservation,
    DiscoveryProvenance,
    SourceHandle,
)
from services.retrieval.workspace.pipeline.execution_flow.dormant_island_completion import (
    completion_observation,
    qualify_dormant_island_completion,
    select_dormant_island_completions,
)
from services.retrieval.workspace.pipeline.execution_flow.evidence_qualification import QualificationDecision
from services.retrieval.workspace.pipeline.execution_flow.source_disclosure import DisclosureCard


PATH = "src/testRunner/unittests/tsbuild/watchMode.ts"


def observation(
    observation_id: str,
    symbol: str,
    start: int,
    end: int,
    *,
    reason: str = "",
    parent_ids: tuple[str, ...] = (),
) -> DiscoveryObservation:
    return DiscoveryObservation(
        id=observation_id,
        handle=SourceHandle(
            path=PATH,
            line_start=start,
            line_end=end,
            full_line_start=start,
            full_line_end=end,
            node_id=f"function:{observation_id}",
            symbol=symbol,
            language="typescript",
        ),
        observed_text=f"source for {symbol}",
        provenance=(DiscoveryProvenance("dense", "q1", ("explain_test",), (3,), (0.8,)),),
        admission_reason=reason,
        parent_observation_ids=parent_ids,
    )


def promoted_navigation(observation_id: str, missing: str) -> QualificationDecision:
    return QualificationDecision(
        observation_id=observation_id,
        disposition="promote",
        support_level="navigation_only",
        reason="Relevant test setup, but its focused assertion is still missing.",
        missing_information=(missing,),
        local_follow_up=missing,
    )


def promoted_direct(observation_id: str, missing: str) -> QualificationDecision:
    return QualificationDecision(
        observation_id=observation_id,
        disposition="promote",
        support_level="direct_evidence",
        reason="Directly proves setup while naming the missing assertion helper.",
        missing_information=(missing,),
        local_follow_up=missing,
    )


class DormantIslandCompletionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parent = observation("parent", "verifyTransitiveReferences", 770, 1064)
        self.helper = observation(
            "helper",
            "verifyTransitiveReferences::verifyScenario",
            876,
            1003,
            reason="same_path_alternative",
        )
        self.coverage = (
            ObligationCoverage("explain_test", "partial", ("parent",), "Missing edit and assertion", "implementation"),
        )

    def select(self, **overrides):
        values = dict(
            matured_observation_ids=("parent",),
            observations={"parent": self.parent, "helper": self.helper},
            decisions={"parent": promoted_navigation("parent", "Inspect verifyScenario for the edit and assertion.")},
            completion_candidate_ids={"helper"},
            attempted_target_ids=set(),
            successful_source_ids=(),
            observation_to_island={"parent": "island_watch"},
            coverage=self.coverage,
        )
        values.update(overrides)
        return select_dormant_island_completions(**values)

    def test_selects_explicitly_named_nested_owner(self) -> None:
        audit = self.select()
        self.assertEqual([(item.target.id, item.relationship_kind) for item in audit.selections], [("helper", "contains")])

    def test_direct_source_can_complete_a_distinct_missing_step(self) -> None:
        audit = self.select(
            decisions={"parent": promoted_direct("parent", "Inspect verifyScenario for the missing assertion.")},
        )
        self.assertEqual([item.target.id for item in audit.selections], ["helper"])

    def test_nested_helper_matches_descriptive_plural_from_qualification(self) -> None:
        audit = self.select(
            decisions={"parent": promoted_navigation("parent", "Retrieve the complete scenarios and assertion.")},
        )
        self.assertEqual([item.target.id for item in audit.selections], ["helper"])

    def test_does_not_reopen_arbitrary_same_file_alternative(self) -> None:
        audit = self.select(
            decisions={"parent": promoted_navigation("parent", "Find the concrete edit and assertion.")},
        )
        self.assertEqual(audit.selections, ())

    def test_requires_membership_in_resolved_dormant_owner_set(self) -> None:
        audit = self.select(completion_candidate_ids=set())
        self.assertEqual(audit.selections, ())

    def test_owner_comparison_rejection_does_not_block_exact_completion(self) -> None:
        dormant = observation("helper", "verifyTransitiveReferences::verifyScenario", 876, 1003)
        audit = self.select(observations={"parent": self.parent, "helper": dormant})
        self.assertEqual([item.target.id for item in audit.selections], ["helper"])

    def test_obeys_per_island_success_cap_through_parent_chain(self) -> None:
        child_one = observation("child_one", "childOne", 800, 810, parent_ids=("parent",))
        child_two = observation("child_two", "childTwo", 811, 820, parent_ids=("parent",))
        observations = {"parent": self.parent, "helper": self.helper, "child_one": child_one, "child_two": child_two}
        audit = self.select(
            observations=observations,
            successful_source_ids=("child_one", "child_two"),
        )
        self.assertEqual(audit.selections, ())
        self.assertEqual(audit.rejected[0]["reason"], "island_completion_cap_reached")

    def test_completion_observation_keeps_structural_not_semantic_claim(self) -> None:
        selection = self.select().selections[0]
        completed = completion_observation(selection)
        self.assertEqual(completed.parent_observation_ids, ("parent",))
        self.assertEqual(completed.relationship_kinds, ("contains",))
        self.assertEqual(completed.admission_reason, "dormant_island_completion")

    @patch("services.retrieval.workspace.pipeline.execution_flow.dormant_island_completion.complete_json")
    def test_paired_qualification_sends_promoted_source_and_target(self, complete_json) -> None:
        captured = {}

        def answer(_config, messages, **kwargs):
            captured["payload"] = json.loads(messages[1]["content"])
            kwargs["log_event"]("llm_response_received", {"raw_response": {"usage": {"total_tokens": 123}}})
            return {
                "classification": "promote_direct",
                "reason": "The helper shows the edit and assertion missing from the parent.",
                "visible_support": ["edits a referenced file", "checks the resulting diagnostic"],
                "missing_information": [],
                "local_follow_up": "",
            }

        complete_json.side_effect = answer
        source_card = DisclosureCard("parent", self.parent.handle, "complete_owner", "parent source")
        target_card = DisclosureCard("helper", self.helper.handle, "complete_owner", "helper source")
        decision, usage, bounded = qualify_dormant_island_completion(
            llm_config=object(),
            user_request="Explain the watch regression.",
            source_card=source_card,
            target_card=target_card,
            source_decision=promoted_navigation("parent", "Inspect verifyScenario."),
            relationship_kind="contains",
            max_input_chars=40_000,
        )
        self.assertEqual(decision.support_level, "direct_evidence")
        self.assertEqual(usage["total_tokens"], 123)
        self.assertEqual([bounded[0].observation_id, bounded[1].observation_id], ["parent", "helper"])
        self.assertEqual(captured["payload"]["promoted_source"]["observation_id"], "parent")
        self.assertEqual(captured["payload"]["dormant_candidate"]["observation_id"], "helper")


if __name__ == "__main__":
    unittest.main()
