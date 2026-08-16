from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from services.intent.models import EvidenceObligation
from services.retrieval.workspace.pipeline.execution_flow.coverage_evaluation import (
    CoverageBatch,
    ObligationCoverage,
    evaluate_coverage,
)
from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import (
    DiscoveryObservation,
    DiscoveryProvenance,
    SourceHandle,
    aggregate_observations,
    observation_from_result,
)
from services.retrieval.workspace.pipeline.execution_flow.evidence_islands import build_semantic_islands
from services.retrieval.workspace.pipeline.execution_flow.evidence_qualification import (
    QualificationDecision,
    qualify_cards,
)
from services.retrieval.workspace.pipeline.execution_flow.retrieval_actions import (
    ExpandRelationship,
    SearchNewIsland,
    SearchWithinFile,
    enumerate_actions,
    execute_action,
)
from services.retrieval.workspace.pipeline.execution_flow.retrieval_controller import run_retrieval_controller
from services.retrieval.workspace.pipeline.execution_flow.retrieval_controller import (
    _action_effect,
    _latest_changed_observations,
    _select_actions,
)
from services.retrieval.workspace.pipeline.execution_flow.evidence_qualification import QualificationBatch
from services.retrieval.workspace.pipeline.execution_flow.source_disclosure import (
    DisclosureCard,
    MAX_COMPLETE_OWNER_LINES,
    MAX_QUALIFICATION_CARD_CHARS,
    OutlineEntry,
    disclose_observations,
    fit_cards_to_source_capacity,
)
from services.retrieval.workspace.pipeline.execution_flow.structural_components import build_structural_components
from services.retrieval.workspace.pipeline.execution_flow.qualification_first_retrieval import (
    _preserve_active_island_candidates,
)
from services.retrieval.workspace.tools import ToolObservation


class QualificationFirstRetrievalTests(unittest.TestCase):
    def test_observation_guardrail_merges_entities_and_is_role_neutral(self) -> None:
        first = observation_from_result(
            {"path": "tests/watch.ts", "line_start": 1, "line_end": 20, "text": "watch", "score": 0.5, "file_role": "test"},
            obligation_id="trigger",
            query_id="q1",
            rank=2,
            retriever="qdrant_hybrid",
            nodes=({"id": "function:watch", "name": "watch", "path": "tests/watch.ts", "line_start": 1, "line_end": 30},),
        )[0]
        repeated = observation_from_result(
            {"path": "tests/watch.ts", "line_start": 10, "line_end": 25, "text": "watch body", "score": 0.8, "file_role": "test"},
            obligation_id="effect",
            query_id="q2",
            rank=1,
            retriever="qdrant_hybrid",
            nodes=({"id": "function:watch", "name": "watch", "path": "tests/watch.ts", "line_start": 1, "line_end": 30},),
        )[0]
        implementation = _observation("obs_impl", "src/builder.ts", "function:builder", ("trigger",), role="implementation")

        selected, decisions = aggregate_observations((first, repeated, implementation), limit=2)

        self.assertEqual(len(selected), 2)
        merged = next(item for item in selected if item.handle.node_id == "function:watch")
        self.assertEqual(merged.recurrence, 2)
        self.assertEqual(set(merged.obligation_ids), {"trigger", "effect"})
        self.assertEqual({item.artifact_role for item in selected}, {"test", "implementation"})
        self.assertIn("merged_same_entity", {item["reason"] for item in decisions})

    def test_disclosure_retains_full_owner_handle_for_later_inspection(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "src" / "large.ts"
            source.parent.mkdir()
            source.write_text("\n".join(f"line {index}" for index in range(1, 181)), encoding="utf-8")
            observation = DiscoveryObservation(
                id="obs_large",
                handle=SourceHandle(
                    path="src/large.ts",
                    line_start=80,
                    line_end=100,
                    node_id="function:large",
                    symbol="large",
                    full_line_start=1,
                    full_line_end=180,
                    language="typescript",
                    adapter="codegraph_node",
                ),
                observed_text="line 80",
                provenance=(DiscoveryProvenance("qdrant_hybrid", "q", ("owner",), (1,), (1.0,)),),
            )
            outline_tool = _Tool(
                "structural_file_outline",
                {"nodes": [{"id": "function:large", "kind": "function", "name": "large", "qualified_name": "large", "line_start": 1, "line_end": 180}]},
            )

            batch = disclose_observations((observation,), workspace_root=str(root), outline_tool=outline_tool)

        self.assertEqual(batch.cards[0].mode, "preview")
        self.assertEqual(batch.cards[0].handle.full_line_end, 180)
        self.assertEqual(batch.cards[0].outline_entries[0].node_id, "function:large")
        self.assertIn("line 80", batch.cards[0].source_text)

    def test_disclosure_folds_ambiguous_names_without_fetching_outlines(self) -> None:
        observations = tuple(
            DiscoveryObservation(
                id=f"obs_{index}",
                handle=SourceHandle(
                    path=f"src/{index}.ts",
                    line_start=1,
                    line_end=20,
                    node_id=f"function:render:{index}",
                    symbol="render",
                    full_line_start=1,
                    full_line_end=200,
                ),
                observed_text="function render() {}",
                provenance=(DiscoveryProvenance("exact_symbol", "render", ("owner",), (index,), (1.0,)),),
            )
            for index in range(4)
        )

        batch = disclose_observations(observations, workspace_root=".", outline_tool=_FailTool())

        self.assertEqual({card.mode for card in batch.cards}, {"fold"})
        self.assertEqual({card.truncation_reason for card in batch.cards}, {"ambiguous_same_name"})
        self.assertEqual(batch.tool_calls, 0)

    def test_comment_only_hit_discloses_the_adjacent_complete_owner(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "src" / "owner.ts"
            source.parent.mkdir()
            source.write_text("// explains owner\nfunction owner() {\n  return 1;\n}\n", encoding="utf-8")
            observation = DiscoveryObservation(
                id="obs_comment",
                handle=SourceHandle("src/owner.ts", 1, 1, adapter="indexed_chunk"),
                observed_text="// explains owner",
                provenance=(DiscoveryProvenance("qdrant_hybrid", "q"),),
            )
            outline = _Tool("structural_file_outline", {"nodes": [{
                "id": "function:owner", "kind": "function", "name": "owner",
                "qualified_name": "owner", "line_start": 2, "line_end": 4,
            }]})
            card = disclose_observations((observation,), workspace_root=str(root), outline_tool=outline).cards[0]
        self.assertEqual((card.handle.line_start, card.handle.line_end), (2, 4))
        self.assertIn("return 1", card.source_text)

    def test_disclosure_prefers_structural_identity_when_chunk_overlaps_preceding_method(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "pandas" / "core" / "series.py"
            source.parent.mkdir(parents=True)
            source.write_text(
                "class Series:\n"
                "    def append(self, other):\n"
                "        return concat(self, other)\n"
                "\n"
                "    def _binop(self, other, func):\n"
                "        result = func(self.values, other.values)\n"
                "        name = _maybe_match_name(self, other)\n"
                "        return Series(result, name=name)\n",
                encoding="utf-8",
            )
            observation = DiscoveryObservation(
                id="obs_binop",
                handle=SourceHandle(
                    "pandas/core/series.py", 3, 7,
                    node_id="method:binop", symbol="Series::_binop",
                    full_line_start=5, full_line_end=8,
                    language="python", adapter="codegraph_node",
                ),
                observed_text="return concat(self, other)\n\n    def _binop(self, other, func):",
                provenance=(DiscoveryProvenance("qdrant_hybrid", "q"),),
            )
            outline = _Tool("structural_file_outline", {"nodes": [
                {
                    "id": "class:series", "kind": "class", "name": "Series",
                    "qualified_name": "Series", "line_start": 1, "line_end": 8,
                },
                {
                    "id": "method:append", "kind": "method", "name": "append",
                    "qualified_name": "Series::append", "line_start": 2, "line_end": 3,
                },
                {
                    "id": "method:binop", "kind": "method", "name": "_binop",
                    "qualified_name": "Series::_binop", "line_start": 5, "line_end": 8,
                },
            ]})

            card = disclose_observations(
                (observation,), workspace_root=str(root), outline_tool=outline,
            ).cards[0]

        self.assertEqual(card.owner_name, "Series::_binop")
        self.assertEqual(card.handle.node_id, "method:binop")
        self.assertEqual((card.handle.line_start, card.handle.line_end), (5, 8))
        self.assertIn("name = _maybe_match_name(self, other)", card.source_text)

    def test_large_owner_keeps_bounded_hit_preview_even_with_spare_capacity(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "src" / "large.ts"
            source.parent.mkdir()
            lines = ["function largeOwner() {"]
            lines.extend(
                f'  const value_{line} = "{"x" * 48}";'
                for line in range(2, 194)
            )
            lines.append("}")
            source.write_text("\n".join(lines), encoding="utf-8")
            observation = DiscoveryObservation(
                id="obs_large",
                handle=SourceHandle(
                    "src/large.ts", 100, 123,
                    node_id="function:large", symbol="largeOwner",
                    full_line_start=1, full_line_end=194,
                ),
                observed_text="\n".join(lines[99:123]),
                provenance=(DiscoveryProvenance("within_file_search", "q"),),
            )
            outline = _Tool("structural_file_outline", {"nodes": [{
                "id": "function:large", "kind": "function", "name": "largeOwner",
                "qualified_name": "largeOwner", "line_start": 1, "line_end": 194,
            }]})
            card = disclose_observations(
                (observation,), workspace_root=str(root), outline_tool=outline,
            ).cards[0]

        self.assertEqual(card.mode, "preview")
        self.assertLessEqual(len(card.source_text), MAX_QUALIFICATION_CARD_CHARS)
        self.assertLessEqual(len(card.source_text.splitlines()), MAX_COMPLETE_OWNER_LINES)
        self.assertIn("function largeOwner", card.source_text)
        self.assertIn("value_100", card.source_text)
        self.assertIn("value_123", card.source_text)
        self.assertNotIn("value_50", card.source_text)
        fitted = fit_cards_to_source_capacity((card,), source_capacity=100_000)[0]
        self.assertEqual(fitted.source_text, card.preview_source_text)
        self.assertNotIn("value_50", fitted.source_text)

    def test_spare_capacity_does_not_expand_repeated_large_owner_previews(self) -> None:
        preview = "function largeOwner() {\n// ... omitted ...\n  relevant();\n}"
        complete = preview + ("\n  unrelated();" * 300)
        cards = tuple(
            DisclosureCard(
                f"obs_{index}", SourceHandle("src/large.ts", 90 + index, 110 + index),
                "preview", preview,
                complete_source_text=complete,
                preview_source_text=preview,
                truncation_reason="large_owner_skeleton_and_local_excerpt",
            )
            for index in range(2)
        )

        fitted = fit_cards_to_source_capacity(cards, source_capacity=100_000)

        self.assertEqual([card.source_text for card in fitted], [preview, preview])
        self.assertTrue(all(len(card.source_text) <= MAX_QUALIFICATION_CARD_CHARS for card in fitted))

    def test_qualification_source_budget_never_slices_a_partial_line(self) -> None:
        text = "function owner() {\n" + ("  const value = 1;\n" * 20) + "}"
        card = DisclosureCard("obs", SourceHandle("src/a.ts", 1, 22), "full", text,
                              complete_source_text=text, preview_source_text="function owner() {\n}")
        fitted = fit_cards_to_source_capacity((card,), source_capacity=120)[0]
        self.assertLessEqual(len(fitted.source_text), 120)
        self.assertTrue(fitted.source_text.endswith("stable source handle ..."))
        self.assertNotIn("const valu\n", fitted.source_text)

    def test_qualification_requires_every_known_id_and_valid_combination(self) -> None:
        card = DisclosureCard("obs_a", SourceHandle("src/a.ts", 1, 2), "preview", "function a() {}")
        response = {
            "decisions": {
                "obs_a": {
                    "classification": "promote_direct",
                    "reason": "Defines the requested behavior.",
                    "visible_support": ["Defines a()."],
                    "missing_information": [],
                }
            }
        }
        with patch(
            "services.retrieval.workspace.pipeline.execution_flow.evidence_qualification.complete_json",
            return_value=response,
        ):
            batch = qualify_cards(
                llm_config=SimpleNamespace(),
                user_request="Explain a",
                cards=(card,),
                max_input_chars=4000,
            )
        self.assertEqual(batch.decisions[0].support_level, "direct_evidence")

        invalid = {"decisions": {"obs_a": {**response["decisions"]["obs_a"], "classification": "invented"}}}
        with patch(
            "services.retrieval.workspace.pipeline.execution_flow.evidence_qualification.complete_json",
            return_value=invalid,
        ):
            with self.assertRaisesRegex(RuntimeError, "qualification_response_invalid"):
                qualify_cards(
                    llm_config=SimpleNamespace(),
                    user_request="Explain a",
                    cards=(card,),
                    max_input_chars=4000,
                )

        mismatched = {"decisions": {"obs_unknown": response["decisions"]["obs_a"]}}
        with patch(
            "services.retrieval.workspace.pipeline.execution_flow.evidence_qualification.complete_json",
            return_value=mismatched,
        ):
            with self.assertRaisesRegex(RuntimeError, "decision IDs differ"):
                qualify_cards(
                    llm_config=SimpleNamespace(),
                    user_request="Explain a",
                    cards=(card,),
                    max_input_chars=4000,
                )

    def test_qualification_shares_file_context_but_decides_each_observation(self) -> None:
        outline = (
            OutlineEntry("class:project", "class", "Project", "Project", 1, 100),
            OutlineEntry("method:first", "method", "first", "Project::first", 10, 20),
        )
        cards = (
            DisclosureCard(
                "obs_first",
                SourceHandle("src/project.ts", 10, 20, node_id="method:first", symbol="Project::first"),
                "full",
                "first() { return 1; }",
                outline_entries=outline,
                owner_kind="method",
                owner_name="Project::first",
                owner_line_start=10,
                owner_line_end=20,
                outer_owner_line_start=1,
                outer_owner_line_end=100,
                allocated_chars=999,
                used_chars=21,
            ),
            DisclosureCard(
                "obs_second",
                SourceHandle("src/project.ts", 30, 40, node_id="method:second", symbol="Project::second"),
                "full",
                "second() { return 2; }",
                outline_entries=outline,
                owner_kind="method",
                owner_name="Project::second",
                owner_line_start=30,
                owner_line_end=40,
                outer_owner_line_start=1,
                outer_owner_line_end=100,
                allocated_chars=999,
                used_chars=22,
            ),
        )
        captured: dict[str, object] = {}

        def respond(_config, messages, **_kwargs):
            payload = json.loads(messages[1]["content"])
            captured.update(payload)
            return {"decisions": {
                "obs_first": {
                    "classification": "promote_direct", "reason": "First is relevant.",
                    "visible_support": ["Returns one."], "missing_information": [],
                },
                "obs_second": {
                    "classification": "reject_insufficient", "reason": "Second is unrelated.",
                    "visible_support": [], "missing_information": ["relevant behavior"],
                },
            }}

        with patch("services.retrieval.workspace.pipeline.execution_flow.evidence_qualification.complete_json",
                   side_effect=respond) as completion:
            batch = qualify_cards(llm_config=SimpleNamespace(), user_request="Explain first",
                                  cards=cards, max_input_chars=12000)

        self.assertEqual(completion.call_count, 1)
        self.assertEqual(len(captured["file_contexts"]), 1)
        observations = captured["observations"]
        self.assertEqual({item["file_context_id"] for item in observations}, {"file_1"})
        self.assertEqual([item["observation_id"] for item in observations], ["obs_first", "obs_second"])
        self.assertNotEqual(observations[0]["owner_context_id"], observations[1]["owner_context_id"])
        serialized = json.dumps(captured)
        self.assertNotIn("outline_entries", serialized)
        self.assertNotIn("allocated_chars", serialized)
        self.assertNotIn("used_chars", serialized)
        self.assertEqual([item.support_level for item in batch.decisions], ["direct_evidence", "insufficient"])

    def test_empty_qualification_source_emits_loud_trace_event(self) -> None:
        card = DisclosureCard("obs_empty", SourceHandle("src/a.ts", 1, 1), "preview", "")
        response = {"decisions": {"obs_empty": {
            "classification": "reject_insufficient", "reason": "No source is visible.",
            "visible_support": [], "missing_information": ["source"],
        }}}
        trace = _Trace()
        with patch("services.retrieval.workspace.pipeline.execution_flow.evidence_qualification.complete_json",
                   return_value=response):
            qualify_cards(llm_config=SimpleNamespace(), user_request="Explain a", cards=(card,),
                          max_input_chars=8000, trace=trace)

        event = next(value for event_type, value in trace.events
                     if event_type == "qualification_source_degradation_detected")
        self.assertEqual(event["severity"], "error")
        self.assertEqual(event["empty_non_fold_card_ids"], ["obs_empty"])

    def test_qualification_overflow_fails_instead_of_splitting_calls(self) -> None:
        cards = tuple(
            DisclosureCard(f"obs_{index}_{'x' * 80}", SourceHandle(f"src/{index}_{'y' * 80}.ts", 1, 2),
                           "preview", f"function value{index}() {{}}")
            for index in range(12)
        )
        with patch("services.retrieval.workspace.pipeline.execution_flow.evidence_qualification.complete_json") as completion:
            with self.assertRaisesRegex(RuntimeError, "qualification_input_budget_too_small_for_metadata"):
                qualify_cards(llm_config=SimpleNamespace(), user_request="Explain values",
                              cards=cards, max_input_chars=4000)
        completion.assert_not_called()

    def test_coverage_rejects_unknown_candidate_citations(self) -> None:
        obligation = EvidenceObligation("owner", "Find the behavior owner.", True)
        response = {
            "obligations": [
                {
                    "obligation_id": "owner",
                    "status": "covered",
                    "supporting_candidate_ids": ["candidate:invented"],
                    "missing_claim": "",
                    "suggested_need": "unknown",
                }
            ]
        }
        with patch(
            "services.retrieval.workspace.pipeline.execution_flow.coverage_evaluation.complete_json",
            return_value=response,
        ):
            with self.assertRaisesRegex(RuntimeError, "unknown candidate"):
                evaluate_coverage(
                    llm_config=SimpleNamespace(),
                    user_request="Explain the owner",
                    obligations=(obligation,),
                    candidates=({"candidate_id": "candidate:real", "snippet": "source"},),
                    max_input_chars=4000,
                )

    def test_disconnected_promoted_roots_survive_as_separate_islands(self) -> None:
        left = _observation("obs_left", "src/builder.ts", "function:builder", ("owner",))
        right = _observation("obs_right", "tests/watch.ts", "function:watch", ("trigger",), role="test")
        decisions = (
            QualificationDecision("obs_left", "promote", "direct_evidence", "owner", ("owner",)),
            QualificationDecision("obs_right", "promote", "direct_evidence", "trigger", ("trigger",)),
        )
        tool = _Tool("structural_relationships_within_nodes", {"edges": []})

        result = _build_test_islands((left, right), decisions, relationship_tool=tool)

        self.assertEqual(len(result.islands), 2)
        self.assertEqual(set(result.active_root_ids), {"obs_left", "obs_right"})

    def test_root_beam_ranks_islands_by_qualification_not_hashed_id(self) -> None:
        observations = tuple(
            _observation(f"obs_{name}", f"src/{name}.ts", f"function:{name}", ("owner",))
            for name in ("weak_a", "weak_b", "weak_c", "weak_d", "direct")
        )
        decisions = tuple(
            QualificationDecision(
                observation.id,
                "promote",
                "direct_evidence" if observation.id == "obs_direct" else "navigation_only",
                "qualified",
                ("visible",),
            )
            for observation in observations
        )

        result = _build_test_islands(
            observations,
            decisions,
            relationship_tool=_Tool("structural_relationships_within_nodes", {"edges": []}),
            beam_size=4,
        )

        self.assertIn("obs_direct", result.active_root_ids)
        self.assertEqual(len(result.active_root_ids), 4)

    def test_root_beam_preserves_recurrent_navigation_island(self) -> None:
        recurrent = replace(
            _observation("obs_watch", "tests/watch.ts", "function:watch", ("owner", "why"), role="test"),
            recurrence=3,
        )
        direct = tuple(
            _observation(f"obs_direct_{index}", f"src/direct_{index}.ts", f"function:direct_{index}", ("owner",))
            for index in range(4)
        )
        observations = (recurrent, *direct)
        decisions = (
            QualificationDecision("obs_watch", "promote", "navigation_only", "credible island", ("visible",)),
            *(
                QualificationDecision(item.id, "promote", "direct_evidence", "direct", ("visible",))
                for item in direct
            ),
        )

        result = _build_test_islands(
            observations,
            decisions,
            relationship_tool=_Tool("structural_relationships_within_nodes", {"edges": []}),
            beam_size=4,
        )

        self.assertIn("obs_watch", result.active_root_ids)

    def test_semantic_island_core_combines_promoted_direct_and_navigation_but_not_deferred(self) -> None:
        direct = _observation("obs_direct", "src/project.ts", "method:update", ("owner",))
        navigation = _observation("obs_navigation", "src/project.ts", "method:worker", ("owner",))
        deferred = _observation("obs_deferred", "src/project.ts", "method:helper", ("owner",))
        decisions = (
            QualificationDecision(direct.id, "promote", "direct_evidence", "direct"),
            QualificationDecision(navigation.id, "promote", "navigation_only", "navigation"),
            QualificationDecision(deferred.id, "defer", "navigation_only", "deferred"),
        )
        cards = tuple(
            DisclosureCard(
                item.id, item.handle, "preview", "source",
                owner_kind="class", owner_name="Project", owner_line_start=1, owner_line_end=100,
            )
            for item in (direct, navigation, deferred)
        )

        result = _build_test_islands(
            (direct, navigation, deferred), decisions, cards=cards,
            relationship_tool=_Tool("structural_relationships_within_nodes", {"edges": []}),
        )

        self.assertEqual(len(result.islands), 1)
        self.assertEqual(set(result.islands[0].observation_ids), {direct.id, navigation.id})
        self.assertNotIn(deferred.id, result.observation_to_island)

    def test_broad_search_provenance_does_not_merge_cross_file_observations(self) -> None:
        left = replace(
            _observation("obs_left", "src/a.ts", "function:a", ("owner",)),
            provenance=(DiscoveryProvenance("new_island_search", "action_shared", ("owner",), (1,), (0.8,)),),
        )
        right = replace(
            _observation("obs_right", "src/b.ts", "function:b", ("owner",)),
            provenance=(DiscoveryProvenance("new_island_search", "action_shared", ("owner",), (2,), (0.7,)),),
        )
        decisions = tuple(
            QualificationDecision(item.id, "promote", "navigation_only", "navigation")
            for item in (left, right)
        )

        result = _build_test_islands(
            (left, right), decisions,
            relationship_tool=_Tool("structural_relationships_within_nodes", {"edges": []}),
        )

        self.assertEqual(len(result.islands), 2)

    def test_range_only_observations_in_one_file_have_distinct_island_ids(self) -> None:
        left = replace(
            _observation("obs_left", "src/shared.ts", "", ("owner",)),
            handle=SourceHandle("src/shared.ts", 10, 20),
        )
        right = replace(
            _observation("obs_right", "src/shared.ts", "", ("owner",)),
            handle=SourceHandle("src/shared.ts", 80, 90),
        )
        decisions = tuple(
            QualificationDecision(item.id, "promote", "navigation_only", "navigation")
            for item in (left, right)
        )

        result = _build_test_islands(
            (left, right), decisions,
            relationship_tool=_Tool("structural_relationships_within_nodes", {"edges": []}),
        )

        self.assertEqual(len(result.islands), 2)
        self.assertEqual(len({item.id for item in result.islands}), 2)

    def test_bounded_cross_file_parent_handoff_merges_observations(self) -> None:
        parent = _observation("obs_parent", "src/a.ts", "function:a", ("owner",))
        child = replace(
            _observation("obs_child", "src/b.ts", "function:b", ("owner",)),
            parent_observation_ids=(parent.id,),
            provenance=(DiscoveryProvenance("graph_action", "action_edge", ("owner",), (1,), (0.0,)),),
        )
        decisions = tuple(
            QualificationDecision(item.id, "promote", "direct_evidence", "direct")
            for item in (parent, child)
        )

        result = _build_test_islands(
            (parent, child), decisions,
            relationship_tool=_Tool("structural_relationships_within_nodes", {"edges": []}),
        )

        self.assertEqual(len(result.islands), 1)
        self.assertEqual(set(result.islands[0].normalized_files), {"src/a.ts", "src/b.ts"})

    def test_island_id_is_retained_when_one_new_member_joins(self) -> None:
        root = _observation("obs_root", "src/a.ts", "function:a", ("owner",))
        decisions = (QualificationDecision(root.id, "promote", "direct_evidence", "direct"),)
        previous = _build_test_islands(
            (root,), decisions,
            relationship_tool=_Tool("structural_relationships_within_nodes", {"edges": []}),
        )
        child = replace(
            _observation("obs_child", "src/b.ts", "function:b", ("owner",)),
            parent_observation_ids=(root.id,),
        )
        current = _build_test_islands(
            (root, child),
            (*decisions, QualificationDecision(child.id, "promote", "navigation_only", "navigation")),
            previous=previous,
            relationship_tool=_Tool("structural_relationships_within_nodes", {"edges": []}),
        )

        self.assertEqual(current.islands[0].id, previous.islands[0].id)

    def test_action_slots_are_spread_across_scopes_before_returning_to_one(self) -> None:
        first = SearchWithinFile("first", "owner", "root_a", "src/a.ts", "Find owner", scope_id="island_a")
        second_same = ExpandRelationship(
            "second_same", "owner", "root_b", "function:b", "outgoing", ("calls",), "downstream",
            scope_id="island_a",
        )
        other = SearchWithinFile("other", "state", "root_c", "src/c.ts", "Find state", scope_id="island_b")

        selected = _select_actions(
            (first, second_same, other), ("root_a", "root_b", "root_c"), 2,
            scope_order=("island_a", "island_b"),
        )

        self.assertEqual(tuple(item.scope_id for item in selected), ("island_a", "island_b"))

    def test_deferred_actions_share_one_bounded_obligation_frontier(self) -> None:
        left = _observation("obs_left", "src/a.ts", "function:a", ("owner",))
        right = _observation("obs_right", "src/b.ts", "function:b", ("owner",))

        catalogue = enumerate_actions(
            user_request="Find owner",
            obligations=(EvidenceObligation("owner", "Find owner", True),),
            coverage=(ObligationCoverage("owner", "missing", (), "owner missing", "new_island"),),
            observations=(left, right),
            decisions=(),
            cards=(),
            active_root_ids=(),
            edge_capabilities_tool=_FailTool(),
            attempted_fingerprints=set(),
        )

        inspections = [item for item in catalogue.actions if type(item).__name__ == "InspectDeferredObservation"]
        searches = [item for item in catalogue.actions if isinstance(item, SearchNewIsland)]
        self.assertEqual(len(inspections), 1)
        self.assertEqual(len(searches), 1)
        self.assertEqual(inspections[0].scope_id, searches[0].scope_id)

    def test_actions_use_reported_directional_capabilities_or_new_island_search(self) -> None:
        root = _observation("obs_root", "src/root.ts", "function:root", ("trigger",))
        decision = QualificationDecision("obs_root", "promote", "direct_evidence", "root", ("root",))
        obligations = (EvidenceObligation("trigger", "Find the triggering caller.", True),)
        coverage = (ObligationCoverage("trigger", "missing", (), "Caller is missing", "trigger"),)
        capabilities = _Tool(
            "structural_edge_capabilities",
            {"nodes": [{"node_id": "function:root", "incoming": [{"kind": "calls", "count": 2}], "outgoing": []}]},
        )

        catalogue = enumerate_actions(
            user_request="Find the triggering caller.",
            obligations=obligations,
            coverage=coverage,
            observations=(root,),
            decisions=(decision,),
            cards=(),
            active_root_ids=(root.id,),
            edge_capabilities_tool=capabilities,
            attempted_fingerprints=set(),
        )

        expansion = next(item for item in catalogue.actions if isinstance(item, ExpandRelationship))
        self.assertEqual(expansion.direction, "incoming")
        self.assertEqual(expansion.edge_kinds, ("calls",))
        self.assertFalse(any(isinstance(item, SearchNewIsland) for item in catalogue.actions))

        no_edges = _Tool(
            "structural_edge_capabilities",
            {"nodes": [{"node_id": "function:root", "incoming": [], "outgoing": []}]},
        )
        catalogue = enumerate_actions(
            user_request="Find the triggering caller.",
            obligations=obligations,
            coverage=coverage,
            observations=(root,),
            decisions=(decision,),
            cards=(),
            active_root_ids=(root.id,),
            edge_capabilities_tool=no_edges,
            attempted_fingerprints=set(),
        )
        self.assertTrue(any(isinstance(item, SearchNewIsland) for item in catalogue.actions))

    def test_learned_source_identifier_can_create_exact_search_alongside_graph_action(self) -> None:
        root = _observation("obs_root", "src/root.py", "function:root", ("effect",))
        decision = QualificationDecision("obs_root", "promote", "navigation_only", "root", ("root",))
        card = DisclosureCard("obs_root", root.handle, "full", "return left._binop(right, op)")
        obligation = EvidenceObligation("effect", "Find the downstream arithmetic owner.", True)
        capabilities = _Tool(
            "structural_edge_capabilities",
            {"nodes": [{"node_id": "function:root", "incoming": [], "outgoing": [{"kind": "calls", "count": 1}]}]},
        )

        catalogue = enumerate_actions(
            user_request="Explain Series arithmetic.",
            obligations=(obligation,),
            coverage=(ObligationCoverage("effect", "missing", (), "Owner missing", "downstream"),),
            observations=(root,),
            decisions=(decision,),
            cards=(card,),
            active_root_ids=(root.id,),
            edge_capabilities_tool=capabilities,
            attempted_fingerprints=set(),
        )

        self.assertTrue(any(isinstance(item, ExpandRelationship) for item in catalogue.actions))
        exact = next(item for item in catalogue.actions if isinstance(item, SearchNewIsland))
        self.assertIn("_binop", exact.exact_symbol_anchors)

    def test_rejected_recurrent_hit_remains_a_navigation_hypothesis(self) -> None:
        hit = replace(
            _observation("obs_watch", "tests/watch.ts", "function:watch", ("why",), role="test"),
            recurrence=2,
            provenance=(DiscoveryProvenance("qdrant_hybrid", "watch", ("why",), (2,), (0.5,)),),
        )
        decision = QualificationDecision("obs_watch", "reject", "insufficient", "snippet is incomplete")
        obligation = EvidenceObligation("why", "Find the watch-mode mechanism.", True)

        catalogue = enumerate_actions(
            user_request="Explain why watch mode misses the changed export.",
            obligations=(obligation,),
            coverage=(ObligationCoverage("why", "missing", (), "Mechanism missing", "implementation"),),
            observations=(hit,),
            decisions=(decision,),
            cards=(),
            active_root_ids=(),
            edge_capabilities_tool=_FailTool(),
            attempted_fingerprints=set(),
        )

        refinement = next(item for item in catalogue.actions if isinstance(item, SearchWithinFile))
        self.assertEqual(refinement.path, "tests/watch.ts")

    def test_relationship_execution_preserves_exact_direction_kind_and_limit(self) -> None:
        action = ExpandRelationship(
            id="expand-owner",
            obligation_id="owner",
            root_observation_id="obs_root",
            root_node_id="function:root",
            direction="outgoing",
            edge_kinds=("calls",),
            need="downstream",
            max_results=3,
        )
        tool = _RecordingTool(
            "structural_expand_relationships",
            {
                "nodes": [
                    {
                        "id": "function:target",
                        "name": "target",
                        "path": "src/target.ts",
                        "line_start": 5,
                        "line_end": 12,
                    }
                ],
                "edges": [{"source": "function:root", "target": "function:target", "kind": "calls"}],
            },
        )

        result = execute_action(
            action,
            observations=(),
            relationship_tool=tool,
            qdrant_tool=_FailTool(),
            resolve_ranges_tool=_FailTool(),
            exact_symbol_tool=_Tool("structural_find_exact_symbol", {"nodes": []}),
        )

        self.assertEqual(tool.requests[0].arguments["direction"], "outgoing")
        self.assertEqual(tool.requests[0].arguments["edge_kinds"], ["calls"])
        self.assertEqual(tool.requests[0].arguments["limit"], 3)
        self.assertEqual(result.observations[0].parent_observation_ids, ("obs_root",))
        self.assertEqual(result.observations[0].relationship_kinds, ("calls",))

    def test_new_island_search_keeps_dense_obligation_and_expands_sparse_identifiers(self) -> None:
        action = SearchNewIsland(
            id="search-owner",
            obligation_id="owner",
            dense_query="Find how Series arithmetic chooses the result name.",
            sparse_anchors=("test_binop_maybe_preserve_name",),
        )
        qdrant = _RecordingTool("qdrant_hybrid_search", {"results": []})

        execute_action(
            action,
            observations=(),
            relationship_tool=_FailTool(),
            qdrant_tool=qdrant,
            resolve_ranges_tool=_FailTool(),
            exact_symbol_tool=_FailTool(),
        )

        arguments = qdrant.requests[0].arguments
        self.assertEqual(arguments["query"], action.dense_query)
        self.assertIn("test_binop_maybe_preserve_name", arguments["sparse_query"])
        self.assertIn("binop", arguments["sparse_query"].split())
        self.assertIn("preserve", arguments["sparse_query"].split())

    def test_within_file_search_is_path_scoped_and_bounded(self) -> None:
        action = SearchWithinFile(
            id="within-owner",
            obligation_id="owner",
            source_observation_id="obs_file",
            path="pandas/core/series.py",
            dense_query="Find the arithmetic result-name owner.",
            sparse_anchors=("test_binop_maybe_preserve_name",),
            result_limit=3,
        )
        qdrant = _RecordingTool("qdrant_hybrid_search", {"results": []})

        execute_action(
            action,
            observations=(),
            relationship_tool=_FailTool(),
            qdrant_tool=qdrant,
            resolve_ranges_tool=_FailTool(),
            exact_symbol_tool=_FailTool(),
        )

        arguments = qdrant.requests[0].arguments
        self.assertEqual(arguments["path"], "pandas/core/series.py")
        self.assertEqual(arguments["limit"], 3)
        self.assertEqual(arguments["max_per_path"], 0)

    def test_action_selection_does_not_spend_two_slots_on_same_inspection(self) -> None:
        duplicate_left = _inspect_action("inspect-left", "obligation-a")
        duplicate_right = _inspect_action("inspect-right", "obligation-b")
        expansion = ExpandRelationship(
            id="expand",
            obligation_id="obligation-b",
            root_observation_id="root",
            root_node_id="function:root",
            direction="outgoing",
            edge_kinds=("calls",),
            need="downstream",
        )

        selected = _select_actions((duplicate_left, duplicate_right, expansion), ("root",), 2)

        self.assertEqual(len(selected), 2)
        self.assertEqual(sum(type(item).__name__ == "InspectDeferredObservation" for item in selected), 1)
        self.assertIn(expansion, selected)

    def test_action_selection_reserves_a_slot_for_disconnected_search(self) -> None:
        inspection = _inspect_action("inspect", "owner")
        expansion = ExpandRelationship(
            id="expand",
            obligation_id="owner",
            root_observation_id="root",
            root_node_id="function:root",
            direction="outgoing",
            edge_kinds=("calls",),
            need="downstream",
        )
        search = SearchNewIsland("search", "other", "Find the disconnected owner.")

        selected = _select_actions((inspection, expansion, search), ("root",), 2)

        self.assertEqual(selected, (inspection, search))

    def test_distinct_file_hypotheses_use_both_action_slots(self) -> None:
        first = SearchWithinFile("first", "owner", "root_a", "src/a.py", "Find owner.", priority=1)
        second = SearchWithinFile("second", "state", "root_b", "src/b.py", "Find state.", priority=2)
        deferred = replace(_inspect_action("deferred", "owner"), deferred_pool=True)

        selected = _select_actions((first, second, deferred), ("root_a", "root_b"), 2)

        self.assertEqual(selected, (first, second))

    def test_same_file_cannot_consume_both_action_slots(self) -> None:
        first = SearchWithinFile("first", "owner", "root_a", "src/a.py", "Find owner.", priority=1)
        duplicate = SearchWithinFile("duplicate", "state", "root_b", "src/a.py", "Find state.", priority=2)
        expansion = ExpandRelationship("expand", "state", "root_c", "function:c", "outgoing", ("calls",), "state")

        selected = _select_actions((first, duplicate, expansion), ("root_a", "root_b", "root_c"), 2)

        self.assertEqual(selected, (first, expansion))

    def test_later_round_reserves_one_slot_for_capability_checked_expansion(self) -> None:
        first = SearchWithinFile("first", "owner", "root_a", "src/a.py", "Find owner.", priority=1)
        second = SearchWithinFile("second", "state", "root_b", "src/b.py", "Find state.", priority=2)
        expansion = ExpandRelationship("expand", "state", "root_c", "function:c", "outgoing", ("calls",), "state")

        selected = _select_actions(
            (first, second, expansion),
            ("root_a", "root_b", "root_c"),
            2,
            prefer_relationship=True,
        )

        self.assertEqual(selected, (first, expansion))

    def test_relationship_effect_does_not_repeat_under_another_obligation(self) -> None:
        repeated = ExpandRelationship("repeat", "effect", "root", "function:root", "outgoing", ("calls",), "downstream")
        fresh = ExpandRelationship("fresh", "mechanism", "other", "function:other", "outgoing", ("calls",), "downstream")

        selected = _select_actions(
            (repeated, fresh),
            ("root", "other"),
            1,
            attempted_effects={_action_effect(repeated)},
        )

        self.assertEqual(selected, (fresh,))

    def test_generic_exact_search_does_not_displace_relationship_followup(self) -> None:
        within = SearchWithinFile("within", "owner", "root_a", "src/a.ts", "Find owner.", priority=1)
        generic = SearchNewIsland("generic", "owner", "Find owner.", exact_symbol_anchors=("build", "clean"))
        expansion = ExpandRelationship("expand", "owner", "root_b", "function:b", "outgoing", ("calls",), "downstream")

        selected = _select_actions(
            (within, generic, expansion),
            ("root_a", "root_b"),
            2,
            prefer_relationship=True,
        )

        self.assertEqual(selected, (within, expansion))

    def test_qualified_file_refinement_outranks_deferred_inspection(self) -> None:
        inspection = _inspect_action("inspect", "owner")
        within = SearchWithinFile(
            id="within",
            obligation_id="owner",
            source_observation_id="obs_owner",
            path="src/owner.py",
            dense_query="Find the exact owner method.",
        )

        selected = _select_actions((inspection, within), (), 1)

        self.assertEqual(selected, (within,))

    def test_file_refinement_uses_active_source_root_order(self) -> None:
        active = SearchWithinFile("active", "owner", "root_active", "src/active.py", "Find owner.")
        inactive = SearchWithinFile("inactive", "owner", "root_inactive", "src/inactive.py", "Find owner.")

        selected = _select_actions((inactive, active), ("root_active",), 1)

        self.assertEqual(selected, (active,))

    def test_file_refinement_does_not_repeat_a_path_across_rounds(self) -> None:
        repeated = SearchWithinFile("repeat", "owner", "root_a", "src/repeated.py", "Find owner.")
        fresh = SearchWithinFile("fresh", "owner", "root_b", "src/fresh.py", "Find owner.")

        selected = _select_actions(
            (repeated, fresh),
            ("root_a", "root_b"),
            1,
            refined_paths={"src/repeated.py"},
        )

        self.assertEqual(selected, (fresh,))

    def test_requalification_batches_each_stable_observation_id_once(self) -> None:
        first = _observation("obs_shared", "src/shared.ts", "function:shared", ("owner",))
        merged = replace(first, recurrence=2)

        selected = _latest_changed_observations((first, merged), {merged.id: merged})

        self.assertEqual(selected, (merged,))

    def test_controller_stops_after_qualified_required_coverage_without_expansion(self) -> None:
        observation = _observation("obs_root", "src/root.ts", "function:root", ("owner",))
        obligation = EvidenceObligation("owner", "Find the behavior owner.", True)
        config = SimpleNamespace(
            workspace_root=".",
            llm_config=SimpleNamespace(),
            max_qualification_input_chars=4000,
            max_exploration_rounds=3,
            max_controller_actions_per_round=2,
        )
        trace = SimpleNamespace(record=lambda *args, **kwargs: None, record_tool=lambda *args, **kwargs: None)
        ctx = SimpleNamespace(config=config, trace=trace)
        tools = {
            "structural_file_outline": _Tool("structural_file_outline", {"nodes": []}),
            "structural_relationships_within_nodes": _Tool("structural_relationships_within_nodes", {"edges": []}),
            "structural_edge_capabilities": _FailTool(),
            "structural_expand_relationships": _FailTool(),
            "structural_resolve_ranges": _FailTool(),
        }
        qualification = QualificationBatch(
            decisions=(QualificationDecision("obs_root", "promote", "direct_evidence", "owner", ("Defines root.",)),),
            usage={},
            serialized_chars=100,
        )
        covered = CoverageBatch(
            coverage=(ObligationCoverage("owner", "covered", ("candidate:root",), "", "unknown"),),
            usage={},
        )
        candidate = {"candidate_id": "candidate:root", "observation_id": "obs_root", "snippet": "source"}
        with patch(
            "services.retrieval.workspace.pipeline.execution_flow.retrieval_controller.qualify_cards",
            return_value=qualification,
        ), patch(
            "services.retrieval.workspace.pipeline.execution_flow.retrieval_controller.evaluate_coverage",
            return_value=covered,
        ), patch(
            "services.retrieval.workspace.pipeline.execution_flow.retrieval_controller.disclose_observations",
            return_value=SimpleNamespace(
                cards=(DisclosureCard("obs_root", observation.handle, "preview", "source"),),
                tool_calls=0,
            ),
        ):
            result = run_retrieval_controller(
                ctx=ctx,
                user_request="Explain root",
                obligations=(obligation,),
                initial_observations=(observation,),
                structural_tools=tools,
                qdrant_tool=_FailTool(),
                candidate_factory=lambda *_args: candidate,
                candidate_payload=lambda value: value,
            )

        self.assertEqual(result.stop_reason, "all_required_obligations_covered")
        self.assertEqual(result.rounds, 0)
        self.assertEqual(result.candidates, (candidate,))

    def test_active_island_guardrail_preserves_one_qualified_candidate_per_island(self) -> None:
        from services.retrieval.workspace.pipeline.execution_flow.evidence_islands import EvidenceIsland, IslandSelection
        from services.retrieval.workspace.pipeline.execution_flow.obligation_retrieval import GroundedCandidate

        candidates = {
            "builder": GroundedCandidate("src/builder.ts", 1, 5, "builder", 0.8, "qualified_direct_evidence"),
            "watch": GroundedCandidate("tests/watch.ts", 1, 5, "watch", 0.5, "qualified_navigation_evidence"),
        }
        controller = SimpleNamespace(
            islands=IslandSelection(
                islands=(EvidenceIsland("island_builder", ("obs_builder",)), EvidenceIsland("island_watch", ("obs_watch",))),
                active_root_ids=("obs_builder", "obs_watch"),
                inactive_promoted_ids=(),
                edges=(),
                tool_calls=0,
            )
        )

        result = _preserve_active_island_candidates(
            {"accepted_candidate_ids": ["builder"]},
            candidates,
            {"builder": "island_builder", "watch": "island_watch"},
            controller,
        )

        self.assertEqual(result["accepted_candidate_ids"], ["builder", "watch"])
        self.assertEqual(result["preserved_active_island_candidate_ids"], ["watch"])


def _build_test_islands(
    observations: tuple[DiscoveryObservation, ...],
    decisions: tuple[QualificationDecision, ...],
    *,
    relationship_tool: object,
    beam_size: int = 3,
    cards: tuple[DisclosureCard, ...] = (),
    coverage: tuple[ObligationCoverage, ...] | None = None,
    previous: object | None = None,
):
    structural = build_structural_components(
        observations,
        decisions,
        relationship_tool=relationship_tool,
    )
    if coverage is None:
        obligation_ids = tuple(dict.fromkeys(value for item in observations for value in item.obligation_ids))
        coverage = tuple(ObligationCoverage(value, "missing", (), "missing", "unknown") for value in obligation_ids)
    return build_semantic_islands(
        observations,
        decisions,
        cards,
        coverage,
        structural,
        beam_size=beam_size,
        previous=previous,
    )


class _Tool:
    def __init__(self, name: str, payload: dict[str, object]) -> None:
        self.name = name
        self.payload = payload

    def run(self, request):
        return ToolObservation(tool_name=self.name, status="ok", payload=self.payload)


class _RecordingTool(_Tool):
    def __init__(self, name: str, payload: dict[str, object]) -> None:
        super().__init__(name, payload)
        self.requests = []

    def run(self, request):
        self.requests.append(request)
        return super().run(request)


class _FailTool:
    def run(self, request):
        raise AssertionError(f"Unexpected tool call: {request.tool_name}")


class _Trace:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def record(self, event_type: str, payload: dict[str, object]) -> None:
        self.events.append((event_type, payload))


def _observation(
    observation_id: str,
    path: str,
    node_id: str,
    obligation_ids: tuple[str, ...],
    *,
    role: str = "implementation",
) -> DiscoveryObservation:
    return DiscoveryObservation(
        id=observation_id,
        handle=SourceHandle(path, 1, 20, node_id=node_id, symbol=node_id.split(":")[-1], full_line_start=1, full_line_end=20),
        observed_text="source",
        provenance=(DiscoveryProvenance("qdrant_hybrid", observation_id, obligation_ids, (1,), (1.0,)),),
        artifact_role=role,
    )


def _inspect_action(action_id: str, obligation_id: str):
    from services.retrieval.workspace.pipeline.execution_flow.retrieval_actions import InspectDeferredObservation

    return InspectDeferredObservation(
        id=action_id,
        observation_id="obs_folded",
        requested_range=(1, 20),
        reason=obligation_id,
    )


if __name__ == "__main__":
    unittest.main()
