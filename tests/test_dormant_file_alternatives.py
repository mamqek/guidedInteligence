from __future__ import annotations

import unittest

from services.retrieval.workspace.pipeline.execution_flow.actions.dormant_file_alternatives import (
    build_dormant_file_alternatives_action,
    evaluate_dormant_file_qualification_gain,
)
from services.retrieval.workspace.pipeline.execution_flow.coverage_evaluation import ObligationCoverage
from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import (
    DiscoveryObservation,
    DiscoveryProvenance,
    InitialAdmissionSignal,
    SourceHandle,
)
from tests.qualification_test_support import QualificationDecision


def _observation(
    observation_id: str,
    symbol: str,
    obligations: tuple[str, ...],
    *,
    rank: int,
    line_start: int,
    path: str = "pandas/core/series.py",
    exact_anchor_matches: tuple[str, ...] = (),
    admission_position: int = 0,
    admitted: bool = False,
) -> DiscoveryObservation:
    return DiscoveryObservation(
        id=observation_id,
        handle=SourceHandle(
            path=path,
            line_start=line_start,
            line_end=line_start + 7,
            full_line_start=line_start,
            full_line_end=line_start + 45,
            node_id=f"method:{observation_id}",
            symbol=symbol,
        ),
        observed_text="",
        provenance=(DiscoveryProvenance(
            retriever="qdrant_dense",
            query_id=obligations[0],
            obligation_ids=obligations,
            ranks=(rank,),
            scores=(0.24,),
            source_key=f"series.py:{line_start}",
        ),),
        exact_anchor_matches=exact_anchor_matches,
        initial_admission=(
            InitialAdmissionSignal(
                ranking_position=admission_position,
                decision="admitted" if admitted else "excluded_after_budget_crossing",
                budget_crossing_position=60,
            )
            if admission_position else None
        ),
    )


class DormantFileAlternativesTests(unittest.TestCase):
    def test_second_opportunity_requires_credited_unresolved_obligation(self) -> None:
        action, _audit = build_dormant_file_alternatives_action(
            user_request="Series arithmetic",
            observations=(
                _observation("sparse_one", "SparseSeries::__array_wrap__", ("mechanism",), rank=1, line_start=10),
                _observation("sparse_two", "SparseSeries::__array_finalize__", ("state",), rank=2, line_start=30),
                _observation("sparse_three", "SparseSeries::_reduce", ("why",), rank=3, line_start=50),
            ),
            decisions=(),
            coverage=tuple(
                ObligationCoverage(value, "missing", (), "missing", "unknown")
                for value in ("mechanism", "state", "why")
            ),
            attempted_action_ids=set(),
            action_id_factory=lambda *parts: "action:" + ":".join(parts),
        )
        self.assertIsNotNone(action)
        assert action is not None
        uncredited = tuple(
            QualificationDecision(
                observation_id, "promote", "direct_evidence", "Related but not the requested path.",
            )
            for observation_id in action.observation_ids
        )

        gain = evaluate_dormant_file_qualification_gain(
            action,
            decisions=uncredited,
            unresolved_obligation_ids={"mechanism", "state", "why"},
        )

        self.assertFalse(gain.productive)
        self.assertEqual(set(gain.retained_observation_ids), set(action.observation_ids))
        self.assertEqual(gain.credited_observation_ids, ())

        established = (
            QualificationDecision(
                action.observation_ids[0],
                "promote",
                "direct_evidence",
                "Establishes the requested mechanism.",
                supported_obligation_ids=("mechanism",),
            ),
        )
        productive = evaluate_dormant_file_qualification_gain(
            action,
            decisions=established,
            unresolved_obligation_ids={"mechanism", "state", "why"},
        )
        self.assertTrue(productive.productive)
        self.assertEqual(productive.credited_obligation_ids, ("mechanism",))

    def test_initial_admission_corrects_zero_admitted_metadata_winner(self) -> None:
        misleading = tuple(
            _observation(
                f"comment_{index}",
                f"CommentVisitor::helper{index}",
                ("subject", "mechanism", "effect"),
                rank=1 + index,
                line_start=20 + index * 10,
                path="doc/sphinxext/numpydoc/comment_eater.py",
                admission_position=100 + index,
            )
            for index in range(5)
        )
        core = tuple(
            _observation(
                f"series_{index}",
                "Series::_binop" if index == 0 else f"Series::helper{index}",
                ("mechanism", "effect"),
                rank=20 + index,
                line_start=1400 + index * 20,
                admission_position=20 + index,
                admitted=index < 4,
            )
            for index in range(5)
        )
        coverage = tuple(
            ObligationCoverage(value, "missing", (), "missing", "unknown")
            for value in ("subject", "mechanism", "effect")
        )

        action, audit = build_dormant_file_alternatives_action(
            user_request="Title: Series arithmetic add does not preserve the result name",
            observations=(*misleading, *core),
            decisions=(),
            coverage=coverage,
            attempted_action_ids=set(),
            action_id_factory=lambda *parts: "action:" + ":".join(parts),
        )

        self.assertIsNotNone(action)
        assert action is not None
        self.assertEqual(action.path, "pandas/core/series.py")
        selected = next(item for item in audit if item.get("selected"))
        self.assertEqual(selected["selection_adjustment"], "initial_admission_consistency_challenger")
        self.assertEqual(selected["displaced_path"], "doc/sphinxext/numpydoc/comment_eater.py")

    def test_batches_distinct_owners_and_keeps_semantic_binop(self) -> None:
        observations = (
            _observation("repr", "Series::_repr_footer", ("subject", "mechanism"), rank=7, line_start=900),
            _observation("string", "Series::to_string", ("subject", "effect"), rank=7, line_start=930),
            _observation("append", "Series::append", ("mechanism",), rank=8, line_start=1443),
            _observation("binop", "Series::_binop", ("mechanism",), rank=8, line_start=1466),
            _observation("reduce", "Series::_reduce", ("state",), rank=7, line_start=2061),
            _observation("apply", "Series::apply", ("effect",), rank=7, line_start=2013),
        )
        coverage = tuple(
            ObligationCoverage(value, "missing", (), "missing", "unknown")
            for value in ("subject", "mechanism", "state", "effect")
        )

        action, audit = build_dormant_file_alternatives_action(
            user_request="Series arithmetic ops inconsistently preserve names for a binary operation",
            observations=observations,
            decisions=(),
            coverage=coverage,
            attempted_action_ids=set(),
            action_id_factory=lambda *parts: "action:" + ":".join(parts),
        )

        self.assertIsNotNone(action)
        assert action is not None
        self.assertLessEqual(len(action.observation_ids), 5)
        self.assertIn("binop", action.observation_ids)
        self.assertEqual(audit[0]["decision"], "eligible")

    def test_file_with_retained_observation_is_ineligible(self) -> None:
        observations = (
            _observation("qualified", "Series::_binop", ("mechanism",), rank=1, line_start=1466),
            _observation("other", "Series::append", ("mechanism", "effect"), rank=2, line_start=1443),
        )
        decision = QualificationDecision(
            "qualified", "promote", "direct_evidence", "relevant", supported_obligation_ids=("mechanism",),
        )
        action, _audit = build_dormant_file_alternatives_action(
            user_request="Series arithmetic",
            observations=observations,
            decisions=(decision,),
            coverage=(ObligationCoverage("mechanism", "missing", (), "missing", "unknown"),),
            attempted_action_ids=set(),
            action_id_factory=lambda *parts: "action:" + ":".join(parts),
        )

        self.assertIsNone(action)

    def test_request_supported_file_outranks_broad_unrelated_file(self) -> None:
        observations = (
            _observation("binop", "Series::_binop", ("mechanism", "effect"), rank=8, line_start=1466),
            _observation("combine", "Series::combine", ("subject", "state"), rank=9, line_start=1513),
            _observation(
                "index_one", "Index::_binop", ("subject", "mechanism", "state"),
                rank=8, line_start=10, path="pandas/core/index.py",
            ),
            _observation(
                "index_two", "Index::name", ("state", "effect"),
                rank=9, line_start=30, path="pandas/core/index.py",
            ),
        )
        coverage = tuple(
            ObligationCoverage(value, "missing", (), "missing", "unknown")
            for value in ("subject", "mechanism", "state", "effect")
        )

        action, _audit = build_dormant_file_alternatives_action(
            user_request=(
                "Explain the code context.\n\n"
                "Title: Series arithmetic ops inconsistently hold names\n\n"
                "Based on Index behavior, inspect Series binary operation name handling in _binop."
            ),
            observations=observations,
            decisions=(),
            coverage=coverage,
            attempted_action_ids=set(),
            action_id_factory=lambda *parts: "action:" + ":".join(parts),
        )

        self.assertIsNotNone(action)
        assert action is not None
        self.assertEqual(action.path, "pandas/core/series.py")

    def test_structural_cluster_keeps_lexical_support_when_ranked_against_small_file(self) -> None:
        series_owners = tuple(
            _observation(
                f"series_{index}",
                symbol,
                obligations,
                rank=rank,
                line_start=900 + index * 100,
            )
            for index, (symbol, obligations, rank) in enumerate((
                ("Series::_repr_footer", ("subject", "mechanism"), 5),
                ("Series::to_string", ("subject", "effect"), 5),
                ("_sanitize_array", ("mechanism", "state"), 5),
                ("TimeSeries", ("subject", "state"), 5),
                ("Series::append", ("mechanism",), 8),
                ("Series::_binop", ("mechanism",), 8),
            ))
        )
        index_owners = (
            _observation(
                "index_evaluate",
                "Index::_evaluate_with_datetime_like",
                ("subject", "mechanism"),
                rank=9,
                line_start=100,
                path="pandas/core/index.py",
            ),
            _observation(
                "index_compare",
                "Index::_add_comparison_methods::_make_compare::_evaluate_compare",
                ("state", "effect"),
                rank=9,
                line_start=200,
                path="pandas/core/index.py",
            ),
        )
        coverage = tuple(
            ObligationCoverage(value, "missing", (), "missing", "unknown")
            for value in ("subject", "mechanism", "state", "effect")
        )

        action, audit = build_dormant_file_alternatives_action(
            user_request=(
                "Title: BUG/API: Series arithmetic ops inconsistently hold names\n"
                "Based on Index behavior, inspect Series binary operation name handling."
            ),
            observations=(*series_owners, *index_owners),
            decisions=(),
            coverage=coverage,
            attempted_action_ids=set(),
            action_id_factory=lambda *parts: "action:" + ":".join(parts),
        )

        self.assertIsNotNone(action)
        assert action is not None
        self.assertEqual(action.path, "pandas/core/series.py")
        self.assertIn("series_5", action.observation_ids)
        series_audit = next(item for item in audit if item["path"] == "pandas/core/series.py")
        self.assertEqual(series_audit["structural_owner_count"], 6)
        self.assertEqual(series_audit["title_owner_support"], 2)

    def test_attempted_file_is_not_repeated(self) -> None:
        observations = (
            _observation("one", "Series::_binop", ("mechanism",), rank=1, line_start=1466),
            _observation("two", "Series::append", ("effect",), rank=2, line_start=1443),
        )
        action_id = "action:dormant_file_alternatives:pandas/core/series.py"
        action, audit = build_dormant_file_alternatives_action(
            user_request="Series arithmetic",
            observations=observations,
            decisions=(),
            coverage=(
                ObligationCoverage("mechanism", "missing", (), "missing", "unknown"),
                ObligationCoverage("effect", "missing", (), "missing", "unknown"),
            ),
            attempted_action_ids={action_id},
            action_id_factory=lambda *parts: "action:" + ":".join(parts),
        )

        self.assertIsNone(action)
        self.assertEqual(audit[0]["decision"], "already_attempted")

    def test_shared_path_word_without_owner_support_does_not_trigger(self) -> None:
        observations = (
            _observation(
                "one", "render", ("mechanism",), rank=1, line_start=10,
                path="src/directives/repeat.js",
            ),
            _observation(
                "two", "update", ("effect",), rank=2, line_start=30,
                path="src/directives/repeat.js",
            ),
        )
        action, audit = build_dormant_file_alternatives_action(
            user_request="Title: event directive handler parsing\nExplain expression parsing.",
            observations=observations,
            decisions=(),
            coverage=(
                ObligationCoverage("mechanism", "missing", (), "missing", "unknown"),
                ObligationCoverage("effect", "missing", (), "missing", "unknown"),
            ),
            attempted_action_ids=set(),
            action_id_factory=lambda *parts: "action:" + ":".join(parts),
        )

        self.assertIsNone(action)
        self.assertFalse(audit[0]["grounded_owner_support"])

    def test_structural_owner_cluster_is_grounded_without_title_or_request_match(self) -> None:
        observations = tuple(
            _observation(
                f"builder_{index}",
                symbol,
                ("state", "mechanism") if index == 0 else (("state",) if index < 4 else ("mechanism",)),
                rank=2 + index,
                line_start=100 + index * 20,
                path="src/compiler/builderState.ts",
            )
            for index, symbol in enumerate((
                "updateSignaturesFromCache",
                "updateShapeSignature",
                "updateExportedFilesMapFromCache",
                "getFilesAffectedBy",
                "getFilesAffectedByUpdatedShapeWhenModuleEmit",
                "getFilesAffectedByUpdatedShapeWhenNonModuleEmit",
            ))
        ) + tuple(
            _observation(
                f"project_{index}",
                f"Project::helper{index}",
                ("subject", "mechanism") if index == 0 else (("subject",) if index < 4 else ("mechanism",)),
                rank=8 + index,
                line_start=400 + index * 20,
                path="src/server/project.ts",
            )
            for index in range(8)
        )
        coverage = tuple(
            ObligationCoverage(value, "missing", (), "missing", "unknown")
            for value in ("subject", "mechanism", "state")
        )

        action, audit = build_dormant_file_alternatives_action(
            user_request=(
                "Title: Project references fail to report an error\n"
                "Explain watch-mode wildcard re-export invalidation."
            ),
            observations=observations,
            decisions=(),
            coverage=coverage,
            attempted_action_ids=set(),
            action_id_factory=lambda *parts: "action:" + ":".join(parts),
        )

        self.assertIsNotNone(action)
        assert action is not None
        self.assertEqual(action.path, "src/compiler/builderState.ts")
        builder_audit = next(item for item in audit if item["path"] == action.path)
        self.assertEqual(builder_audit["structural_owner_count"], 6)
        self.assertTrue(builder_audit["retrieval_grounded_support"])
        self.assertFalse(builder_audit["lexical_owner_support"])
        self.assertEqual(builder_audit["decision"], "eligible")

if __name__ == "__main__":
    unittest.main()
