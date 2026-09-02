from __future__ import annotations

import unittest

from services.retrieval.workspace.pipeline.execution_flow.island_evidence_packets import (
    IslandPacketCandidate,
    select_island_evidence_packets,
)


def _candidate(
    candidate_id: str,
    island_id: str,
    *,
    direct: bool = True,
    obligation_bearing: bool | None = None,
    navigation: bool = False,
    score: float = 1.0,
    roles: tuple[str, ...] = ("supporting",),
    request_chars: int = 100,
    handoff_grounded: bool = False,
) -> IslandPacketCandidate:
    return IslandPacketCandidate(
        candidate_id=candidate_id,
        island_id=island_id,
        request_chars=request_chars,
        score=score,
        direct=direct,
        obligation_bearing=direct if obligation_bearing is None else obligation_bearing,
        navigation=navigation,
        roles=roles,
        path=f"src/{candidate_id}.py",
        handoff_grounded=handoff_grounded,
    )


class IslandEvidencePacketTests(unittest.TestCase):
    def test_grounded_unique_navigation_uses_capacity_before_seeded_sibling(self) -> None:
        connection = {
            "from_candidate_id": "seed",
            "to_candidate_id": "companion",
            "relationship": "calls",
        }
        result = select_island_evidence_packets(
            candidates=(
                _candidate("seed", "island_seed", request_chars=600),
                _candidate("companion", "island_seed", request_chars=100),
                _candidate(
                    "navigation", "island_navigation", direct=False,
                    navigation=True, handoff_grounded=True, request_chars=100,
                    roles=("controller",),
                ),
            ),
            raw_flows=(
                {"candidate_ids": ["seed", "companion"], "connections": [connection], "score": 5.0},
            ),
            connections=(connection,),
            input_char_budget=850,
            initial_used_chars=600,
            mandatory_candidate_ids=("seed",),
            mandatory_flows=(),
        )

        self.assertIn("navigation", result.candidate_ids)
        self.assertNotIn("companion", result.candidate_ids)
        self.assertTrue(any(
            item["decision"] == "selected_unique_navigation_route"
            for item in result.decisions
        ))

    def test_navigation_is_not_reserved_without_concrete_handoff(self) -> None:
        connection = {
            "from_candidate_id": "seed",
            "to_candidate_id": "companion",
            "relationship": "calls",
        }
        result = select_island_evidence_packets(
            candidates=(
                _candidate("seed", "island_seed", request_chars=600),
                _candidate("companion", "island_seed", request_chars=100),
                _candidate(
                    "navigation", "island_navigation", direct=False,
                    navigation=True, handoff_grounded=False, request_chars=100,
                ),
            ),
            raw_flows=(
                {"candidate_ids": ["seed", "companion"], "connections": [connection], "score": 5.0},
            ),
            connections=(connection,),
            input_char_budget=850,
            initial_used_chars=600,
            mandatory_candidate_ids=("seed",),
            mandatory_flows=(),
        )

        self.assertIn("companion", result.candidate_ids)
        self.assertNotIn("navigation", result.candidate_ids)

    def test_duplicate_obligation_is_not_an_admission_slot(self) -> None:
        # The packet boundary receives no consumed-obligation state: two
        # independently qualified singleton islands remain comparable even
        # when an earlier stage associates both with the same obligation.
        result = select_island_evidence_packets(
            candidates=(
                _candidate("first", "island_first", score=2.0),
                _candidate("second", "island_second", score=1.0),
            ),
            raw_flows=(),
            connections=(),
            input_char_budget=2_000,
            initial_used_chars=0,
        )

        self.assertEqual(set(result.candidate_ids), {"first", "second"})
        self.assertEqual(len(result.flows), 2)
        self.assertTrue(all(item["packet_kind"] == "singleton" for item in result.flows))

    def test_navigation_singleton_reaches_comparison(self) -> None:
        result = select_island_evidence_packets(
            candidates=(
                _candidate(
                    "navigation",
                    "island_navigation",
                    direct=False,
                    navigation=True,
                    handoff_grounded=True,
                    roles=("controller",),
                ),
            ),
            raw_flows=(),
            connections=(),
            input_char_budget=1_000,
            initial_used_chars=0,
        )

        self.assertEqual(result.candidate_ids, ("navigation",))
        self.assertTrue(result.packets[0]["contains_navigation"])

    def test_connected_island_is_admitted_as_one_multi_candidate_packet(self) -> None:
        connection = {
            "from_candidate_id": "trigger",
            "to_candidate_id": "state",
            "relationship": "calls",
        }
        result = select_island_evidence_packets(
            candidates=(
                _candidate("trigger", "island_flow", score=3.0, roles=("controller",)),
                _candidate("state", "island_flow", score=2.0, roles=("state_owner",)),
                _candidate("effect", "island_flow", score=1.0, roles=("domain_owner",)),
            ),
            raw_flows=(
                {
                    "candidate_ids": ["trigger", "state", "effect"],
                    "connections": [connection],
                    "score": 10.0,
                },
            ),
            connections=(connection,),
            input_char_budget=3_000,
            initial_used_chars=0,
        )

        self.assertEqual(len(result.flows), 1)
        self.assertEqual(result.flows[0]["packet_kind"], "connected")
        self.assertEqual(set(result.flows[0]["candidate_ids"]), {"trigger", "state", "effect"})
        self.assertEqual(result.connection_keys, (("trigger", "state", "calls"),))

    def test_mandatory_seed_survives_when_no_companion_fits(self) -> None:
        connection = {
            "from_candidate_id": "left",
            "to_candidate_id": "right",
            "relationship": "calls",
        }
        result = select_island_evidence_packets(
            candidates=(
                _candidate("left", "island_flow", request_chars=600),
                _candidate("right", "island_flow", request_chars=600),
                _candidate("singleton", "island_singleton", request_chars=100),
            ),
            raw_flows=(
                {"candidate_ids": ["left", "right"], "connections": [connection], "score": 5.0},
            ),
            connections=(connection,),
            input_char_budget=900,
            initial_used_chars=600,
            mandatory_candidate_ids=("left",),
            mandatory_flows=({"flow_id": "baseline", "candidate_ids": ["left"], "score": 5.0},),
        )

        self.assertIn("left", result.candidate_ids)
        self.assertNotIn("right", result.candidate_ids)
        self.assertIn("singleton", result.candidate_ids)
        self.assertTrue(any(
            item["decision"] == "rejected_selected_seeded_island_base_member_input_budget"
            and item["island_id"] == "island_flow"
            for item in result.decisions
        ))

    def test_independent_island_representative_precedes_seeded_sibling(self) -> None:
        connection = {
            "from_candidate_id": "seed",
            "to_candidate_id": "seed_sibling",
            "relationship": "calls",
        }
        result = select_island_evidence_packets(
            candidates=(
                _candidate("seed", "seeded", request_chars=600, score=5.0),
                _candidate("seed_sibling", "seeded", request_chars=100, score=4.0),
                _candidate("independent", "independent", request_chars=100, score=1.0),
            ),
            raw_flows=(
                {
                    "candidate_ids": ["seed", "seed_sibling"],
                    "connections": [connection],
                    "score": 9.0,
                },
            ),
            connections=(connection,),
            input_char_budget=850,
            initial_used_chars=600,
            mandatory_candidate_ids=("seed",),
            mandatory_flows=(),
        )

        self.assertIn("independent", result.candidate_ids)
        self.assertNotIn("seed_sibling", result.candidate_ids)
        self.assertEqual(
            next(item["decision"] for item in result.decisions if not item["decision"].startswith("rejected_")),
            "selected_independent_island_representative",
        )

    def test_supporting_fact_without_obligation_credit_does_not_take_independent_slot(self) -> None:
        connection = {
            "from_candidate_id": "seed",
            "to_candidate_id": "seed_sibling",
            "relationship": "calls",
        }
        result = select_island_evidence_packets(
            candidates=(
                _candidate("seed", "seeded", request_chars=600, score=5.0),
                _candidate("seed_sibling", "seeded", request_chars=100, score=4.0),
                _candidate(
                    "supporting_only",
                    "independent",
                    direct=True,
                    obligation_bearing=False,
                    request_chars=100,
                    score=1.0,
                ),
            ),
            raw_flows=(
                {
                    "candidate_ids": ["seed", "seed_sibling"],
                    "connections": [connection],
                    "score": 9.0,
                },
            ),
            connections=(connection,),
            input_char_budget=850,
            initial_used_chars=600,
            mandatory_candidate_ids=("seed",),
            mandatory_flows=(),
        )

        self.assertIn("seed_sibling", result.candidate_ids)
        self.assertNotIn("supporting_only", result.candidate_ids)

    def test_remaining_siblings_are_enriched_round_robin_across_islands(self) -> None:
        connection_a = {"from_candidate_id": "a1", "to_candidate_id": "a2", "relationship": "calls"}
        connection_b = {"from_candidate_id": "b1", "to_candidate_id": "b2", "relationship": "calls"}
        result = select_island_evidence_packets(
            candidates=(
                _candidate("a1", "island_a", score=9.0),
                _candidate("a2", "island_a", score=8.0),
                _candidate("a3", "island_a", score=7.0),
                _candidate("a4", "island_a", score=6.0),
                _candidate("a5", "island_a", score=5.0),
                _candidate("b1", "island_b", score=4.0),
                _candidate("b2", "island_b", score=3.0),
                _candidate("b3", "island_b", score=2.0),
            ),
            raw_flows=(
                {"candidate_ids": ["a1", "a2", "a3"], "connections": [connection_a], "score": 10.0},
                {"candidate_ids": ["b1", "b2", "b3"], "connections": [connection_b], "score": 6.0},
            ),
            connections=(connection_a, connection_b),
            input_char_budget=10_000,
            initial_used_chars=100,
            mandatory_candidate_ids=("a1",),
            mandatory_flows=(),
        )

        round_robin = [
            item["candidate_ids"][0]
            for item in result.decisions
            if item["decision"] == "selected_round_robin_island_member"
        ]
        self.assertEqual(round_robin[:2], ["a4", "b2"])
        self.assertLess(round_robin.index("b2"), round_robin.index("a5"))

    def test_every_mandatory_seed_is_preserved(self) -> None:
        result = select_island_evidence_packets(
            candidates=(
                _candidate("seed_a", "island_a", request_chars=400),
                _candidate("seed_b", "island_b", request_chars=400),
                _candidate("companion", "island_a", request_chars=100),
            ),
            raw_flows=(),
            connections=(),
            input_char_budget=800,
            initial_used_chars=800,
            mandatory_candidate_ids=("seed_a", "seed_b"),
            mandatory_flows=(),
        )

        self.assertEqual(set(result.candidate_ids), {"seed_a", "seed_b"})

    def test_connected_packet_reserves_one_grounded_navigation_member(self) -> None:
        connection = {
            "from_candidate_id": "direct_high",
            "to_candidate_id": "navigation",
            "relationship": "calls",
        }
        result = select_island_evidence_packets(
            candidates=(
                _candidate("direct_high", "island_flow", score=4.0),
                _candidate("direct_mid", "island_flow", score=3.0),
                _candidate("direct_low", "island_flow", score=2.0),
                _candidate(
                    "navigation",
                    "island_flow",
                    direct=False,
                    navigation=True,
                    score=1.0,
                ),
            ),
            raw_flows=(
                {
                    "candidate_ids": ["direct_high", "direct_mid", "direct_low"],
                    "connections": [connection],
                    "score": 10.0,
                },
            ),
            connections=(connection,),
            input_char_budget=3_000,
            initial_used_chars=0,
        )

        self.assertIn("navigation", result.flows[0]["candidate_ids"])
        self.assertEqual(len(result.flows[0]["candidate_ids"]), 4)
        self.assertTrue(result.packets[0]["contains_navigation"])

    def test_connected_packet_does_not_reserve_unconnected_navigation_member(self) -> None:
        connection = {
            "from_candidate_id": "direct_high",
            "to_candidate_id": "direct_mid",
            "relationship": "calls",
        }
        result = select_island_evidence_packets(
            candidates=(
                _candidate("direct_high", "island_flow", score=4.0),
                _candidate("direct_mid", "island_flow", score=3.0),
                _candidate("direct_low", "island_flow", score=2.0),
                _candidate(
                    "navigation",
                    "island_flow",
                    direct=False,
                    navigation=True,
                    score=1.0,
                ),
            ),
            raw_flows=(
                {
                    "candidate_ids": ["direct_high", "direct_mid", "direct_low"],
                    "connections": [connection],
                    "score": 10.0,
                },
            ),
            connections=(connection,),
            input_char_budget=500,
            initial_used_chars=0,
        )

        self.assertNotIn("navigation", result.candidate_ids)


if __name__ == "__main__":
    unittest.main()
