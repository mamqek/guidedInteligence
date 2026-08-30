from __future__ import annotations

import unittest

from services.retrieval.workspace.pipeline.execution_flow.actions.catalogue_and_execution import (
    ExpandRelationship,
    InspectDeferredObservation,
    SearchNewIsland,
    SearchWithinFile,
)
from services.retrieval.workspace.pipeline.execution_flow.actions.scheduler import schedule_round_actions
from services.retrieval.workspace.pipeline.execution_flow.coverage_evaluation import ObligationCoverage
from services.retrieval.workspace.pipeline.execution_flow.evidence_islands import EvidenceIsland, IslandSelection
from services.retrieval.workspace.pipeline.execution_flow.evidence_qualification import QualificationDecision
from services.retrieval.workspace.pipeline.execution_flow.island_frontiers import IslandFrontierLedger


def _coverage(status: str = "partial") -> tuple[ObligationCoverage, ...]:
    return (ObligationCoverage("why", status, (), "missing mechanism", "follow calls"),)


def _islands(island_id: str, *, active: bool = True) -> IslandSelection:
    island = EvidenceIsland(
        id=island_id,
        observation_ids=("watch",),
        obligation_ids=("why",),
        unresolved_obligation_ids=("why",),
        representative_observation_id="watch",
    )
    return IslandSelection(
        islands=(island,),
        active_root_ids=("watch",) if active else (),
        inactive_promoted_ids=() if active else ("watch",),
        edges=(),
        tool_calls=0,
        active_island_ids=(island_id,) if active else (),
        observation_to_island={"watch": island_id},
    )


class IslandFrontierProjectionTests(unittest.TestCase):
    def test_known_continuation_survives_catalogue_loss_and_island_identity_change(self) -> None:
        action = ExpandRelationship(
            "watch-file-expand",
            "why",
            "watch",
            "file:watchMode.ts",
            "outgoing",
            ("calls",),
            "follow cross-file calls",
            seed_kind="file",
            cross_file_only=True,
            scope_id="island_old",
        )
        decision = QualificationDecision("watch", "promote", "navigation_only", "route")
        ledger = IslandFrontierLedger()

        first = ledger.observe_catalogue(
            (action,),
            islands=_islands("island_old"),
            decisions={"watch": decision},
            coverage=_coverage(),
            round_index=1,
        )
        second = ledger.observe_catalogue(
            (),
            islands=_islands("island_merged"),
            decisions={"watch": decision},
            coverage=_coverage(),
            round_index=2,
        )

        self.assertEqual(first[0].continuations[0].frontier_id, "island_old")
        retained = next(
            item for frontier in second for item in frontier.continuations
            if item.continuation_id == "continuation_1"
        )
        self.assertEqual(retained.frontier_id, "island_merged")
        self.assertFalse(retained.present_in_catalogue)
        self.assertEqual(retained.state, "available")

    def test_every_action_family_maps_without_inventing_a_deferred_gap(self) -> None:
        relationship = ExpandRelationship(
            "expand", "why", "watch", "owner:watch", "outgoing", ("calls",), "follow"
        )
        deferred = InspectDeferredObservation("deferred", "held", (1, 20), "inspect held owner")
        discovery = SearchNewIsland("discover", "why", "find another mechanism")
        ledger = IslandFrontierLedger()

        ledger.observe_catalogue(
            (relationship, deferred, discovery),
            islands=_islands("island_watch"),
            decisions={"watch": QualificationDecision("watch", "promote", "direct_evidence", "proof")},
            coverage=_coverage(),
            round_index=1,
        )

        self.assertEqual(ledger.continuation_for_action("expand").frontier_id, "island_watch")
        self.assertEqual(ledger.continuation_for_action("discover").frontier_kind, "new_island_discovery")
        deferred_projection = ledger.continuation_for_action("deferred")
        self.assertEqual(deferred_projection.frontier_kind, "grounded_unassigned")
        self.assertEqual(deferred_projection.gap_id, "")

    def test_only_absent_ordinary_actions_enter_the_additive_scheduler_memory(self) -> None:
        persisted = SearchWithinFile(
            "persisted", "why", "watch", "watchMode.ts", "follow WatchMode",
            scope_id="island_watch",
        )
        current = SearchWithinFile(
            "current", "why", "builder", "builder.ts", "current Builder search",
            scope_id="island_watch",
        )
        ledger = IslandFrontierLedger()
        ledger.observe_catalogue(
            (persisted,), islands=_islands("island_watch"), decisions={}, coverage=_coverage(), round_index=1
        )
        ledger.observe_catalogue(
            (current,), islands=_islands("island_watch"), decisions={}, coverage=_coverage(), round_index=2
        )

        self.assertEqual(ledger.persisted_available_ordinary_actions(), (persisted,))

    def test_execution_state_and_completed_gap_are_projected_without_scheduling(self) -> None:
        action = ExpandRelationship(
            "expand", "why", "watch", "owner:watch", "outgoing", ("calls",), "follow"
        )
        ledger = IslandFrontierLedger()
        ledger.observe_catalogue(
            (action,),
            islands=_islands("island_watch"),
            decisions={"watch": QualificationDecision("watch", "promote", "direct_evidence", "proof")},
            coverage=_coverage(),
            round_index=1,
        )
        ledger.record_execution("expand", produced_result=False)
        frontiers = ledger.refresh(
            islands=_islands("island_watch"),
            decisions={"watch": QualificationDecision("watch", "promote", "direct_evidence", "proof")},
            coverage=_coverage("covered"),
        )

        continuation = frontiers[0].continuations[0]
        self.assertEqual(continuation.state, "attempted_empty")
        self.assertEqual(frontiers[0].completed_gap_ids, ("why",))
        self.assertEqual(frontiers[0].established_evidence_ids, ("watch",))

    def test_frontier_override_can_schedule_a_persisted_ordinary_island(self) -> None:
        persisted = SearchWithinFile(
            "persisted", "why", "watch", "watchMode.ts", "follow WatchMode",
            scope_id="island_watch",
        )
        current = SearchWithinFile(
            "current", "why", "builder", "builder.ts", "follow Builder",
            scope_id="island_builder",
        )
        common = {
            "active_root_ids": ("watch", "builder"),
            "active_island_ids": ("island_watch", "island_builder"),
            "normal_limit": 1,
            "round_index": 2,
            "refined_paths": set(),
            "attempted_action_ids": set(),
            "attempted_effects": set(),
            "pending_maturation_child_roots": set(),
            "blocked_maturation_root_ids": set(),
            "verified_lead_actions": (),
        }

        baseline = schedule_round_actions((current,), **common)
        frontier = schedule_round_actions(
            (current,), ordinary_actions=(persisted, current), **common
        )

        self.assertEqual(baseline.normal, (current,))
        self.assertEqual(frontier.normal, (persisted,))


if __name__ == "__main__":
    unittest.main()
