from __future__ import annotations

import json
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from services.intent.models import EvidenceObligation
from services.retrieval.workspace.pipeline.execution_flow.actions.models import (
    ExpandRelationship,
    SearchNewIsland,
)
from services.retrieval.workspace.pipeline.execution_flow.agent_planned_controller import (
    _action_from_spec,
    _validate_round,
    plan_agent_round,
    PlannerRound,
    run_agent_planned_controller,
)
from services.retrieval.workspace.pipeline.execution_flow.actions.models import ActionExecution
from services.retrieval.workspace.pipeline.execution_flow.coverage_evaluation import ObligationCoverage
from services.retrieval.workspace.pipeline.execution_flow.evidence_islands import IslandSelection
from services.retrieval.workspace.pipeline.execution_flow.evidence_qualification import QualificationDecision
from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import (
    DiscoveryObservation,
    DiscoveryProvenance,
    SourceHandle,
)
from services.retrieval.workspace.pipeline.execution_flow.source_disclosure import DisclosureBatch, DisclosureCard


def _observation() -> DiscoveryObservation:
    return DiscoveryObservation(
        id="obs_1",
        handle=SourceHandle(
            path="src/service.py", line_start=10, line_end=20,
            full_line_start=8, full_line_end=30, node_id="function:service.run", symbol="service.run",
        ),
        observed_text="def run():\n    dispatch()",
        provenance=(DiscoveryProvenance("qdrant", "q1", ("obl_1",), ranks=(1,), scores=(0.9,)),),
    )


def _action(action_type: str = "expand_relationship") -> dict[str, object]:
    return {
        "action_type": action_type,
        "obligation_id": "obl_1",
        "observation_id": "obs_1" if action_type != "search_repository" else "",
        "query": "dispatch implementation",
        "reason": "Follow the visible call.",
        "expected_signal": "The downstream implementation.",
        "direction": "outgoing",
        "edge_kinds": ["calls"],
        "line_start": 0,
        "line_end": 0,
        "sparse_anchors": ["dispatch"],
        "exact_symbol_anchors": ["dispatch"],
        "limit": 3,
    }


def _response(*, actions: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {
        "classifications": [{
            "observation_id": "obs_1",
            "classification": "promote_direct",
            "reason": "The visible owner invokes dispatch.",
            "visible_support": ["dispatch()"],
            "missing_information": ["dispatch implementation"],
            "local_follow_up": "Follow dispatch.",
        }],
        "coverage": [{
            "obligation_id": "obl_1",
            "status": "partial",
            "supporting_observation_ids": ["obs_1"],
            "missing_claim": "Need downstream behavior.",
            "suggested_need": "downstream",
        }],
        "actions": actions if actions is not None else [_action()],
        "stop": False,
        "stop_reason": "",
        "state_summary": "The trigger is visible; downstream behavior remains open.",
        "open_questions": ["What does dispatch do?"],
    }


class AgentPlannedControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.obligation = EvidenceObligation("obl_1", "Explain the dispatch path.", True)
        self.observation = _observation()

    def test_one_call_combines_classification_coverage_and_action(self) -> None:
        card = DisclosureCard(
            "obs_1", self.observation.handle, "full", self.observation.observed_text,
            complete_source_text=self.observation.observed_text,
            preview_source_text=self.observation.observed_text,
        )
        captured: dict[str, object] = {}

        def fake_complete(_config, messages, *, response_format, log_event):
            captured["payload"] = json.loads(messages[1]["content"])
            captured["schema"] = response_format
            log_event("llm_response_received", {"raw_response": {"usage": {"total_tokens": 123}}})
            return _response()

        with patch(
            "services.retrieval.workspace.pipeline.execution_flow.agent_planned_controller.complete_json",
            side_effect=fake_complete,
        ) as complete:
            result = plan_agent_round(
                llm_config=object(), user_request="Explain dispatch.", obligations=(self.obligation,),
                pending_cards=(card,), observations=(self.observation,), decisions=(),
                candidate_payloads=(), prior_coverage=(),
                action_history=({"status": "empty", "endpoint_observation_ids": []},),
                state_summary="Prior hypothesis.", open_questions=("Where is dispatch?",),
                remaining_rounds=3, remaining_actions=2, max_input_chars=30000,
            )

        self.assertEqual(complete.call_count, 1)
        self.assertEqual(result.decisions[0].support_level, "direct_evidence")
        self.assertEqual(result.coverage[0].status, "partial")
        self.assertEqual(result.action_specs[0]["action_type"], "expand_relationship")
        self.assertEqual(result.usage["total_tokens"], 123)
        self.assertEqual(captured["payload"]["planner_state"]["summary"], "Prior hypothesis.")
        self.assertEqual(captured["payload"]["recent_action_outcomes"][0]["status"], "empty")

    def test_covered_status_requires_promoted_direct_support(self) -> None:
        response = _response(actions=[])
        response["classifications"][0]["classification"] = "promote_navigation"
        response["coverage"][0]["status"] = "covered"
        with self.assertRaisesRegex(RuntimeError, "coverage_support_must_be_promoted_direct"):
            _validate_round(
                response, pending_ids=("obs_1",), observation_ids={"obs_1"},
                obligations=(self.obligation,), prior_decisions=(), max_actions=2,
            )

    def test_action_cannot_invent_an_observation(self) -> None:
        spec = _action()
        spec["observation_id"] = "obs_invented"
        with self.assertRaisesRegex(RuntimeError, "requires_known_observation"):
            _action_from_spec(
                spec, observations={"obs_1": self.observation}, cards={},
                obligation_ids={"obl_1"}, observation_to_island={}, round_index=0,
            )

    def test_typed_actions_derive_structural_identity_from_known_state(self) -> None:
        expanded = _action_from_spec(
            _action(), observations={"obs_1": self.observation}, cards={},
            obligation_ids={"obl_1"}, observation_to_island={"obs_1": "island_1"}, round_index=0,
        )
        searched = _action_from_spec(
            _action("search_repository"), observations={"obs_1": self.observation}, cards={},
            obligation_ids={"obl_1"}, observation_to_island={}, round_index=0,
        )
        self.assertIsInstance(expanded, ExpandRelationship)
        self.assertEqual(expanded.root_node_id, "function:service.run")
        self.assertEqual(expanded.scope_id, "island_1")
        self.assertIsInstance(searched, SearchNewIsland)
        self.assertEqual(searched.exact_symbol_anchors, ("dispatch",))

    def test_controller_persists_outcome_and_uses_one_planner_call_per_round(self) -> None:
        second = DiscoveryObservation(
            id="obs_2",
            handle=SourceHandle(
                path="src/dispatch.py", line_start=40, line_end=55,
                full_line_start=40, full_line_end=55, node_id="function:dispatch", symbol="dispatch",
            ),
            observed_text="def dispatch():\n    return result",
            provenance=(DiscoveryProvenance("new_island_search", "a1", ("obl_1",)),),
        )
        cards = {
            "obs_1": DisclosureCard("obs_1", self.observation.handle, "full", self.observation.observed_text),
            "obs_2": DisclosureCard("obs_2", second.handle, "full", second.observed_text),
        }

        def disclose(items, **_kwargs):
            return DisclosureBatch(tuple(cards[item.id] for item in items), 0)

        calls: list[dict[str, object]] = []

        def planner(**kwargs):
            calls.append(kwargs)
            observation_id = kwargs["pending_cards"][0].observation_id
            decision = QualificationDecision(
                observation_id, "promote", "direct_evidence", "Visible implementation.",
            )
            covered = observation_id == "obs_2"
            return PlannerRound(
                decisions=(decision,),
                coverage=(ObligationCoverage(
                    "obl_1", "covered" if covered else "partial", (observation_id,),
                    "" if covered else "Need dispatch implementation.",
                    "unknown" if covered else "downstream",
                ),),
                action_specs=(() if covered else ({**_action("search_repository")},)),
                stop=covered,
                stop_reason="complete" if covered else "",
                state_summary="Dispatch resolved." if covered else "Dispatch remains open.",
                open_questions=(() if covered else ("Where is dispatch?",)),
                usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                cards=(cards[observation_id],), input_chars=1000,
            )

        trace = SimpleNamespace(record=lambda *_args, **_kwargs: None)
        config = SimpleNamespace(
            workspace_root=".", llm_config=object(), max_agent_planner_rounds=3,
            max_exploration_rounds=3, max_agent_planner_actions_per_round=2,
            max_controller_actions_per_round=2, max_agent_planner_input_chars=30000,
            semantic_island_beam_size=4,
        )
        islands = IslandSelection((), (), (), (), 0, observation_to_island={})
        execution = ActionExecution("a1", (second,), (), 1, "ok")
        tools = {
            "structural_file_outline": object(), "structural_expand_relationships": object(),
            "structural_resolve_ranges": object(), "structural_find_exact_symbol": object(),
        }

        with (
            patch("services.retrieval.workspace.pipeline.execution_flow.agent_planned_controller.disclose_observations", side_effect=disclose),
            patch("services.retrieval.workspace.pipeline.execution_flow.agent_planned_controller.plan_agent_round", side_effect=planner),
            patch("services.retrieval.workspace.pipeline.execution_flow.agent_planned_controller._build_islands", return_value=islands),
            patch("services.retrieval.workspace.pipeline.execution_flow.agent_planned_controller.execute_action", return_value=execution) as execute,
        ):
            result = run_agent_planned_controller(
                ctx=SimpleNamespace(config=config, trace=trace), user_request="Explain dispatch.",
                obligations=(self.obligation,), initial_observations=(self.observation,),
                structural_tools=tools, qdrant_tool=object(),
                candidate_factory=lambda observation, decision, _card: {
                    "candidate_id": f"candidate_{observation.id}",
                    "observation_id": observation.id,
                    "qualification_support": decision.support_level,
                },
                candidate_payload=lambda candidate: candidate,
            )

        self.assertEqual(len(calls), 2)
        self.assertEqual(execute.call_count, 1)
        self.assertEqual(calls[1]["action_history"][0]["status"], "ok")
        self.assertEqual(calls[1]["state_summary"], "Dispatch remains open.")
        self.assertEqual(result.coverage[0].supporting_candidate_ids, ("candidate_obs_2",))
        self.assertEqual(result.planner_usage["total_tokens"], 30)


if __name__ == "__main__":
    unittest.main()
