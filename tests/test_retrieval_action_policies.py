from __future__ import annotations

import json
import unittest

from services.retrieval.workspace.pipeline.execution_flow.actions.policy import (
    ACTION_POOLS,
    ActionPool,
    ActionPurpose,
    action_pool,
    partition_actions_by_pool,
)
from services.retrieval.workspace.pipeline.execution_flow.actions.catalogue_and_execution import (
    ExpandRelationship,
    InspectDeferredObservation,
    InspectOwnerContinuation,
    InspectVerifiedLead,
    SearchNewIsland,
    SearchWithinFile,
    StopRetrieval,
    action_to_dict,
)
from services.retrieval.workspace.pipeline.execution_flow.actions.scheduler import (
    schedule_round_actions,
)
from services.retrieval.workspace.pipeline.execution_flow.actions.pending_file_handoffs import (
    PendingFileHandoff,
    reconcile_pending_file_handoffs,
    retain_pending_file_handoffs,
)
from services.retrieval.workspace.pipeline.execution_flow.coverage_evaluation import ObligationCoverage
from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import (
    DiscoveryObservation,
    DiscoveryProvenance,
    SourceHandle,
)
from services.retrieval.workspace.pipeline.execution_flow.evidence_qualification import QualificationDecision
from services.retrieval.workspace.pipeline.execution_flow.action_novelty import (
    RequestMemoizer,
    normalized_action_effect,
)
from services.retrieval.workspace.tools.contracts import ToolObservation, ToolRequest


def _action_for(purpose: ActionPurpose):
    if purpose in {
        ActionPurpose.INSPECT_DEFERRED_DISCOVERY,
        ActionPurpose.DISCLOSE_DEFERRED_OWNER,
    }:
        return InspectDeferredObservation("inspect", "obs", (1, 2), "Inspect.", purpose=purpose)
    if purpose in {ActionPurpose.OWNER_CONTINUATION, ActionPurpose.OWNER_MATURATION}:
        return InspectOwnerContinuation(
            "continuation", "why", "obs", (3, 4), (1, 10), "Continue.", purpose=purpose
        )
    if purpose is ActionPurpose.RELATIONSHIP_EXPANSION:
        return ExpandRelationship(
            "expand", "why", "obs", "function:owner", "outgoing", ("calls",), "downstream"
        )
    if purpose in {
        ActionPurpose.WITHIN_FILE_SEARCH,
        ActionPurpose.HANDOFF_COMPLETION,
        ActionPurpose.DEFERRED_FILE_RESCUE,
        ActionPurpose.TEST_SCENARIO_MATURATION,
    }:
        return SearchWithinFile("search", "why", "obs", "src/a.ts", "Find code.", purpose=purpose)
    if purpose is ActionPurpose.NEW_ISLAND_SEARCH:
        return SearchNewIsland("new", "why", "Find another mechanism.")
    if purpose in {ActionPurpose.VERIFIED_SOURCE_LEAD, ActionPurpose.STRUCTURAL_CHILD_HANDOFF}:
        return InspectVerifiedLead(
            "verified", "why", "obs", "helper", "function:helper", "src/helper.ts",
            10, 20, "helper", "Inspect exact helper.", 1, purpose=purpose,
        )
    if purpose is ActionPurpose.STOP:
        return StopRetrieval("stop", "complete")
    raise AssertionError(f"missing test fixture for {purpose}")


class RetrievalActionPolicyTests(unittest.TestCase):
    @staticmethod
    def _file_handoff(action_id: str, root: str, scope: str) -> ExpandRelationship:
        return ExpandRelationship(
            action_id,
            "obligation",
            root,
            f"file:{root}",
            "outgoing",
            ("calls",),
            "downstream",
            scope_id=scope,
            handoff_reason="Follow a verified cross-file call.",
            seed_kind="file",
            cross_file_only=True,
        )

    @staticmethod
    def _observation(observation_id: str, role: str = "test") -> DiscoveryObservation:
        return DiscoveryObservation(
            id=observation_id,
            handle=SourceHandle(f"{role}/{observation_id}.ts", 1, 10, node_id=f"node:{observation_id}"),
            observed_text="source",
            provenance=(DiscoveryProvenance("dense", "query", ("obligation",)),),
            artifact_role=role,
        )

    def test_every_action_purpose_has_one_runtime_pool(self) -> None:
        self.assertEqual(set(ACTION_POOLS), set(ActionPurpose))

    def test_every_action_purpose_enters_exactly_its_documented_pool(self) -> None:
        actions = tuple(_action_for(purpose) for purpose in ActionPurpose)
        grouped = partition_actions_by_pool(actions)

        self.assertEqual(sum(len(items) for items in grouped.values()), len(ActionPurpose))
        for action in actions:
            self.assertIn(action, grouped[action_pool(action.purpose)])
            self.assertEqual(
                sum(action in items for items in grouped.values()),
                1,
                action.purpose.value,
            )

    def test_action_trace_exposes_only_structured_policy_fields(self) -> None:
        for purpose in ActionPurpose:
            payload = action_to_dict(_action_for(purpose))
            self.assertEqual(payload["purpose"], purpose.value)
            self.assertEqual(payload["pool"], action_pool(purpose).value)
            self.assertNotIn("policy", payload)
            json.dumps(payload)

    def test_round_scheduler_preserves_each_independent_pool(self) -> None:
        normal = SearchWithinFile(
            "normal", "why", "root_normal", "src/normal.ts", "Find normal code.",
            scope_id="island_normal",
        )
        deferred = SearchWithinFile(
            "deferred", "why", "root_deferred", "src/deferred.ts", "Rescue held code.",
            scope_id="frontier_deferred", purpose=ActionPurpose.DEFERRED_FILE_RESCUE,
        )
        maturation = SearchWithinFile(
            "maturation", "why", "root_maturation", "src/maturation.ts", "Improve owner.",
            scope_id="island_maturation", purpose=ActionPurpose.OWNER_MATURATION,
        )
        test_maturation = SearchWithinFile(
            "test", "why", "root_test", "tests/watch.ts", "Find assertion.",
            scope_id="island_test", purpose=ActionPurpose.TEST_SCENARIO_MATURATION,
        )
        verified = _action_for(ActionPurpose.VERIFIED_SOURCE_LEAD)

        schedule = schedule_round_actions(
            (normal, deferred, maturation, test_maturation),
            active_root_ids=("root_normal", "root_maturation", "root_test"),
            active_island_ids=("island_normal", "island_maturation", "island_test"),
            normal_limit=2,
            round_index=1,
            refined_paths=set(),
            attempted_action_ids=set(),
            attempted_effects=set(),
            pending_maturation_child_roots=set(),
            blocked_maturation_root_ids=set(),
            verified_lead_actions=(verified,),
        )

        self.assertEqual(schedule.normal, (normal,))
        self.assertEqual(schedule.deferred_file_rescue, (deferred,))
        self.assertEqual(schedule.owner_maturation, (maturation,))
        self.assertEqual(schedule.test_maturation, (test_maturation,))
        self.assertEqual(schedule.verified_lead, (verified,))
        self.assertEqual(len(schedule.selected), 5)

    def test_repeated_action_is_suppressed_before_slots_and_novel_action_backfills(self) -> None:
        repeated = SearchWithinFile(
            "repeat", "why", "root_repeat", "src/repeat.ts", "Changed prose.",
            sparse_anchors=("targetMethod",), scope_id="island_repeat",
        )
        novel = SearchWithinFile(
            "novel", "why", "root_novel", "src/novel.ts", "Find novel code.",
            sparse_anchors=("novelMethod",), scope_id="island_novel",
        )
        prior = SearchWithinFile(
            "prior", "subject", "root_repeat", "src/repeat.ts", "Original prose.",
            sparse_anchors=("targetMethod",), scope_id="island_repeat",
        )
        from services.retrieval.workspace.pipeline.execution_flow.action_novelty import normalized_action_effect

        schedule = schedule_round_actions(
            (repeated, novel),
            active_root_ids=("root_repeat", "root_novel"),
            active_island_ids=("island_repeat", "island_novel"),
            normal_limit=1,
            round_index=1,
            refined_paths=set(),
            attempted_action_ids={"prior"},
            attempted_effects={normalized_action_effect(prior)},
            pending_maturation_child_roots=set(),
            blocked_maturation_root_ids=set(),
            verified_lead_actions=(),
        )

        self.assertEqual(schedule.normal, (novel,))
        self.assertEqual(len(schedule.suppressed), 1)
        self.assertEqual(schedule.suppressed[0]["action_id"], "repeat")

    def test_pending_file_handoff_uses_one_existing_slot_only_after_discovery_round(self) -> None:
        pending_action = self._file_handoff("pending", "watch", "watch_island")
        other = SearchWithinFile(
            "other", "obligation", "builder", "src/builder.ts", "Inspect builder.",
            scope_id="builder_island",
        )
        pending = (PendingFileHandoff(pending_action, discovered_round=1, catalogue_rank=3),)

        first = schedule_round_actions(
            (other,), active_root_ids=("builder",), active_island_ids=("builder_island",),
            normal_limit=2, round_index=1, refined_paths=set(), attempted_action_ids=set(),
            attempted_effects=set(), pending_maturation_child_roots=set(),
            blocked_maturation_root_ids=set(), verified_lead_actions=(),
            pending_file_handoffs=pending,
        )
        second = schedule_round_actions(
            (other,), active_root_ids=("builder",), active_island_ids=("builder_island",),
            normal_limit=2, round_index=2, refined_paths=set(), attempted_action_ids=set(),
            attempted_effects=set(), pending_maturation_child_roots=set(),
            blocked_maturation_root_ids=set(), verified_lead_actions=(),
            pending_file_handoffs=pending,
        )

        self.assertEqual(first.normal, (other,))
        self.assertEqual(first.pending_file_handoff, ())
        self.assertEqual(second.normal, (other, pending_action))
        self.assertEqual(second.pending_file_handoff, (pending_action,))
        self.assertEqual(len(second.normal), 2)

    def test_pending_file_handoff_deduplicates_naturally_selected_effect(self) -> None:
        action = self._file_handoff("pending", "watch", "watch_island")
        pending = (PendingFileHandoff(action, discovered_round=1, catalogue_rank=0),)
        schedule = schedule_round_actions(
            (action,), active_root_ids=("watch",), active_island_ids=("watch_island",),
            normal_limit=2, round_index=2, refined_paths=set(), attempted_action_ids=set(),
            attempted_effects=set(), pending_maturation_child_roots=set(),
            blocked_maturation_root_ids=set(), verified_lead_actions=(),
            pending_file_handoffs=pending,
        )

        self.assertEqual(schedule.normal, (action,))
        self.assertEqual(schedule.pending_file_handoff, (action,))
        self.assertEqual(schedule.selected.count(action), 1)

    def test_pending_file_handoff_retention_is_test_only_bounded_and_one_per_island(self) -> None:
        watch = self._file_handoff("watch", "watch", "watch_island")
        watch_second = self._file_handoff("watch_second", "watch_second", "watch_island")
        scenario = self._file_handoff("scenario", "scenario", "scenario_island")
        implementation = self._file_handoff("implementation", "compiler", "compiler_island")
        observations = {
            "watch": self._observation("watch"),
            "watch_second": self._observation("watch_second"),
            "scenario": self._observation("scenario"),
            "compiler": self._observation("compiler", "implementation"),
        }
        decisions = {
            key: QualificationDecision(key, "promote", "navigation_only", "useful", supported_obligation_ids=("obligation",))
            for key in observations
        }
        retained = retain_pending_file_handoffs(
            (), (watch, watch_second, scenario, implementation), (), round_index=1,
            observations=observations, decisions=decisions,
            coverage=(ObligationCoverage("obligation", "partial", (), "missing", "downstream"),),
            observation_to_island={
                "watch": "watch_island", "watch_second": "watch_island",
                "scenario": "scenario_island", "compiler": "compiler_island",
            },
            active_island_ids=("watch_island", "scenario_island", "compiler_island"),
            attempted_effects=set(),
        )

        self.assertEqual([item.action.id for item in retained], ["watch", "scenario"])

    def test_pending_file_handoff_lifecycle_drops_covered_inactive_attempted_and_expired(self) -> None:
        action = self._file_handoff("watch", "watch", "watch_island")
        pending = (PendingFileHandoff(action, discovered_round=1, catalogue_rank=0),)
        observations = {"watch": self._observation("watch")}
        decisions = {"watch": QualificationDecision("watch", "promote", "navigation_only", "useful")}
        common = dict(
            pending=pending, round_index=2, observations=observations, decisions=decisions,
            observation_to_island={"watch": "watch_island"}, active_island_ids=("watch_island",),
            attempted_effects=set(),
        )
        partial = reconcile_pending_file_handoffs(
            coverage=(ObligationCoverage("obligation", "partial", (), "missing", "downstream"),),
            **common,
        )
        covered = reconcile_pending_file_handoffs(
            coverage=(ObligationCoverage("obligation", "covered", (), "", "unknown"),),
            **common,
        )
        inactive = reconcile_pending_file_handoffs(
            coverage=(ObligationCoverage("obligation", "partial", (), "missing", "downstream"),),
            **{**common, "active_island_ids": ()},
        )
        attempted = reconcile_pending_file_handoffs(
            coverage=(ObligationCoverage("obligation", "partial", (), "missing", "downstream"),),
            **{**common, "attempted_effects": {normalized_action_effect(action)}},
        )
        expired = reconcile_pending_file_handoffs(
            coverage=(ObligationCoverage("obligation", "partial", (), "missing", "downstream"),),
            **{**common, "round_index": 4},
        )

        self.assertEqual(partial, pending)
        self.assertEqual(covered, ())
        self.assertEqual(inactive, ())
        self.assertEqual(attempted, ())
        self.assertEqual(expired, ())

    def test_request_memoizer_reuses_normalized_deterministic_request(self) -> None:
        class FakeTool:
            name = "structural_find_exact_symbol"

            def __init__(self) -> None:
                self.calls = 0

            def run(self, request: ToolRequest) -> ToolObservation:
                self.calls += 1
                return ToolObservation(
                    tool_name=self.name,
                    status="ok",
                    payload={"query": request.arguments["query"]},
                    source_refs=("src/a.ts:1:2",),
                )

        tool = FakeTool()
        wrapped = RequestMemoizer().wrap_tools({tool.name: tool})[tool.name]
        first = wrapped.run(ToolRequest(tool.name, {"query": "target"}, "First reason"))
        second = wrapped.run(ToolRequest(tool.name, {"query": "target"}, "Changed reason"))

        self.assertEqual(tool.calls, 1)
        self.assertEqual(first.metadata["cache_hit"], "false")
        self.assertEqual(second.metadata["cache_hit"], "true")
        self.assertEqual(first.payload, second.payload)


if __name__ == "__main__":
    unittest.main()
