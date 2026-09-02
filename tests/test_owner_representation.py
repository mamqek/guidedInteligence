from __future__ import annotations

import unittest

from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import (
    DiscoveryObservation,
    DiscoveryProvenance,
    SourceHandle,
)
from services.retrieval.workspace.pipeline.execution_flow.owner_representation import (
    build_owner_representations,
)
from services.retrieval.workspace.pipeline.execution_flow.actions.models import (
    ExpandWithinFileHandoff,
    InspectOwnerChallengers,
)
from services.retrieval.workspace.pipeline.execution_flow.actions.policy import ActionPurpose
from services.retrieval.workspace.pipeline.execution_flow.actions.scheduler import (
    _select_deferred_file_seed_actions,
)
from tests.qualification_test_support import QualificationDecision


def _observation(
    observation_id: str,
    symbol: str,
    obligations: tuple[str, ...],
    *,
    rank: int,
    recurrence: int = 1,
    line_start: int = 1,
) -> DiscoveryObservation:
    return DiscoveryObservation(
        id=observation_id,
        handle=SourceHandle(
            path="src/compiler/builderState.ts",
            line_start=line_start,
            line_end=line_start + 10,
            full_line_start=line_start,
            full_line_end=line_start + 30,
            node_id=f"function:{observation_id}",
            symbol=symbol,
        ),
        observed_text="",
        provenance=(DiscoveryProvenance(
            retriever="qdrant_dense",
            query_id=obligations[0],
            obligation_ids=obligations,
            ranks=(rank,),
            scores=(1 / max(rank, 1),),
            source_key=observation_id,
        ),),
        recurrence=recurrence,
        artifact_role="implementation",
        admission_reason="same_path_alternative",
    )


class OwnerRepresentationTests(unittest.TestCase):
    def test_undisclosed_owner_is_challenger_not_replacement(self) -> None:
        primary = _observation("primary", "weakScope", ("state",), rank=4, recurrence=3)
        challenger = _observation("challenger", "updateShapeSignature", ("state",), rank=2, line_start=40)
        decision = QualificationDecision(
            "primary", "promote", "direct_evidence", "visible state choice",
            local_follow_up="Which owner updates the shape signature state?",
            supported_obligation_ids=("state",),
        )

        result = build_owner_representations((primary, challenger), (decision,))

        self.assertEqual(len(result.groups), 1)
        group = result.groups[0]
        self.assertEqual(group.primary_observation_id, "primary")
        self.assertEqual(group.challenger_observation_ids, ("challenger",))
        self.assertEqual(result.challenger_batches[0].challenger_observation_ids, ("challenger",))

    def test_qualified_challenger_can_replace_and_preserves_complement(self) -> None:
        primary = _observation("primary", "weakScope", ("state",), rank=4, recurrence=3)
        challenger = _observation(
            "challenger", "updateShapeSignature", ("state", "mechanism"), rank=2, line_start=40
        )
        first = build_owner_representations(
            (primary, challenger),
            (QualificationDecision(
                "primary", "promote", "direct_evidence", "visible state choice",
                local_follow_up="Which owner updates the shape signature state?",
                supported_obligation_ids=("state",),
            ),),
        )

        updated = build_owner_representations(
            (primary, challenger),
            (
                QualificationDecision(
                    "primary", "promote", "direct_evidence", "visible state choice",
                    supported_obligation_ids=("state",),
                ),
                QualificationDecision(
                    "challenger", "promote", "direct_evidence", "visible update mechanism",
                    supported_obligation_ids=("state", "mechanism"),
                ),
            ),
            previous=first,
        )

        state = next(item for item in updated.groups if item.obligation_id == "state")
        self.assertEqual(state.primary_observation_id, "challenger")
        self.assertEqual(state.complementary_observation_ids, ("primary",))
        self.assertEqual(state.election_reason, "qualified_challenger_replaced_primary")

    def test_rejected_owner_is_recorded_and_never_challenges(self) -> None:
        primary = _observation("primary", "weakScope", ("state",), rank=4)
        rejected = _observation("rejected", "genericHelper", ("state",), rank=1, line_start=50)
        result = build_owner_representations(
            (primary, rejected),
            (
                QualificationDecision(
                    "primary", "promote", "direct_evidence", "visible state choice",
                    supported_obligation_ids=("state",),
                ),
                QualificationDecision("rejected", "reject", "insufficient", "generic helper"),
            ),
        )

        group = result.groups[0]
        self.assertEqual(group.primary_observation_id, "primary")
        self.assertFalse(group.challenger_observation_ids)
        self.assertEqual(group.rejected_observation_ids, ("rejected",))
        self.assertFalse(result.challenger_batches)

    def test_unchanged_primary_is_stable_across_rounds(self) -> None:
        primary = _observation("primary", "stateOwner", ("state",), rank=2)
        decision = QualificationDecision(
            "primary", "promote", "direct_evidence", "visible state",
            supported_obligation_ids=("state",),
        )
        first = build_owner_representations((primary,), (decision,))
        second = build_owner_representations((primary,), (decision,), previous=first)

        self.assertEqual(second.groups[0].primary_observation_id, "primary")
        self.assertEqual(second.groups[0].election_reason, "qualified_primary_preserved")

    def test_challengers_require_distinctive_owner_or_follow_up_overlap(self) -> None:
        primary = _observation(
            "primary", "_arith_method_SERIES::wrapper", ("mechanism",), rank=4
        )
        series = _observation(
            "series", "_arith_method_SERIES::na_op", ("mechanism",), rank=7
        )
        panel = _observation(
            "panel", "_arith_method_PANEL::na_op", ("mechanism",), rank=2
        )
        frame = _observation(
            "frame", "_comp_method_FRAME::f", ("mechanism",), rank=1
        )
        decision = QualificationDecision(
            "primary", "promote", "direct_evidence", "Series arithmetic wrapper",
            local_follow_up="Which Series result constructor selects the result name?",
            supported_obligation_ids=("mechanism",),
        )

        result = build_owner_representations(
            (primary, series, panel, frame), (decision,)
        )

        self.assertEqual(result.groups[0].challenger_observation_ids, ("series",))

    def test_direct_challenger_disclosure_precedes_same_file_search_rescue(self) -> None:
        challenger = InspectOwnerChallengers(
            id="challenger_action",
            path="src/compiler/builderState.ts",
            observation_ids=("challenger",),
            primary_observation_ids=("primary",),
            obligation_ids=("state",),
            reason="inspect challenger",
            priority=100,
        )
        search = ExpandWithinFileHandoff(
            id="search_action",
            obligation_id="state",
            source_observation_id="primary",
            path="src/compiler/builderState.ts",
            dense_query="find another owner",
            purpose=ActionPurpose.DEFERRED_FILE_RESCUE,
        )

        selected = _select_deferred_file_seed_actions(
            (search, challenger),
            attempted_effects=set(),
            refined_paths=set(),
            normal_selected=(),
        )

        self.assertEqual(selected, (challenger,))


if __name__ == "__main__":
    unittest.main()
