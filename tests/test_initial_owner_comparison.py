from __future__ import annotations

from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import (
    DiscoveryObservation,
    DiscoveryProvenance,
    SourceHandle,
)
from services.retrieval.workspace.pipeline.execution_flow.initial_owner_comparison import (
    _candidate_groups,
    _compact_source_view,
    compare_initial_owners,
    fit_initial_owner_comparison_admission,
    select_range_candidate_owners,
)


def _observation(identifier: str, symbol: str, start: int, text: str) -> DiscoveryObservation:
    return DiscoveryObservation(
        id=identifier,
        handle=SourceHandle(
            path="pandas/core/series.py",
            line_start=start,
            line_end=start + 39,
            node_id=f"method:{symbol}",
            symbol=f"Series::{symbol}",
            full_line_start=start,
            full_line_end=start + 50,
        ),
        observed_text=text,
        provenance=(
            DiscoveryProvenance(
                retriever="qdrant_dense_file_group",
                query_id="q:ordered",
                obligation_ids=("ordered",),
                ranks=(1,),
                scores=(0.4,),
                matched_terms=("Series", "operation"),
            ),
        ),
    )


class InitialOwnerComparisonTests(unittest.TestCase):
    def test_group_keyed_schema_and_validation(self) -> None:
        from services.retrieval.workspace.pipeline.execution_flow.initial_owner_comparison import (
            _global_response_format, _validate_global_response, _payload,
        )
        expected = {"g1": ("o1", "o2"), "g2": ("o3",)}
        props = _global_response_format(expected, max_selected=2)["json_schema"]["schema"]["properties"]["selections"]
        self.assertEqual(props["required"], ["g1", "g2"])
        self.assertFalse(props["additionalProperties"])
        for gid, ids in expected.items():
            schema = props["properties"][gid]["anyOf"][1]["properties"]
            self.assertEqual(schema["primary_owner_id"]["enum"], list(ids))
            self.assertEqual(schema["additional_owner_ids"]["items"]["enum"], list(ids))
        primary = {"primary_owner_id": "o1", "additional_owner_ids": []}
        self.assertEqual(_validate_global_response({"selections": {"g1": primary, "g2": None}},
                         expected, max_selected=2), {"g1": ("o1",)})
        invalid = [
            {"g1": primary}, {"g1": primary, "g2": None, "g3": None},
            {"g1": None, "g2": None},
            {"g1": {**primary, "additional_owner_ids": ["o1"]}, "g2": None},
            {"g1": {**primary, "additional_owner_ids": ["o3"]}, "g2": None},
            {"g1": {**primary, "additional_owner_ids": [""]}, "g2": None},
            {"g1": {**primary, "additional_owner_ids": ["o2"]},
             "g2": {"primary_owner_id": "o3", "additional_owner_ids": []}},
        ]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                _validate_global_response({"selections": value}, expected, max_selected=2)
        item = _observation("a", "first", 1, "return first()")
        payload = _payload({}, _candidate_groups((item,), ((item.handle.path, "*"),)))[0]
        self.assertEqual(payload["groups"][0]["path"], item.handle.path)

    def test_global_selection_is_the_only_round_zero_limit(self) -> None:
        first = _observation("first", "first", 100, "function first() { return build(); }")
        second = _observation("second", "second", 200, "function second() { return update(); }")
        second = DiscoveryObservation(
            **{
                **second.__dict__,
                "handle": SourceHandle(
                    path="pandas/core/ops.py",
                    line_start=200,
                    line_end=239,
                    node_id="method:second",
                    symbol="Ops::second",
                    full_line_start=200,
                    full_line_end=250,
                ),
            }
        )
        with patch(
            "services.retrieval.workspace.pipeline.execution_flow.initial_owner_comparison.complete_json",
            return_value={
                "selections": {
                    "g1": {"primary_owner_id": "o1", "additional_owner_ids": []},
                    "g2": {"primary_owner_id": "o2", "additional_owner_ids": []},
                }
            },
        ):
            result = compare_initial_owners(
                llm_config=object(),
                obligation_descriptions={"ordered": "Explain the mechanism."},
                observations=(first, second),
                admitted_groups=(("pandas/core/series.py", "*"), ("pandas/core/ops.py", "*")),
                max_input_chars=40_000,
                max_selected=2,
            )

        self.assertEqual([item.id for item in result.selected], ["first", "second"])
        self.assertEqual(result.dormant, ())
        self.assertEqual(result.auto_selected_group_count, 0)

    def test_global_selection_accepts_distinct_additional_owners_from_one_file(self) -> None:
        values = tuple(
            _observation(str(index), f"owner_{index}", index * 100, f"function owner_{index}() {{}}")
            for index in range(1, 4)
        )
        with patch(
            "services.retrieval.workspace.pipeline.execution_flow.initial_owner_comparison.complete_json",
            return_value={
                "selections": {
                    "g1": {
                        "primary_owner_id": "o1",
                        "additional_owner_ids": ["o2", "o3"],
                    }
                }
            },
        ):
            result = compare_initial_owners(
                llm_config=object(),
                obligation_descriptions={"ordered": "Explain the mechanism."},
                observations=values,
                admitted_groups=(("pandas/core/series.py", "*"),),
                max_input_chars=40_000,
                max_selected=3,
            )

        self.assertEqual(tuple(item.id for item in result.selected), ("1", "2", "3"))
        self.assertEqual(result.dormant, ())

    def test_global_selection_rejects_owner_outside_declared_group(self) -> None:
        first = _observation("first", "first", 100, "function first() {}")
        second = DiscoveryObservation(
            **{
                **_observation("second", "second", 200, "function second() {}").__dict__,
                "handle": SourceHandle(
                    path="pandas/core/ops.py",
                    line_start=200,
                    line_end=239,
                    node_id="method:second",
                    symbol="Ops::second",
                    full_line_start=200,
                    full_line_end=250,
                ),
            }
        )
        with patch(
            "services.retrieval.workspace.pipeline.execution_flow.initial_owner_comparison.complete_json",
            return_value={
                "selections": {
                    "g1": {"primary_owner_id": "o2", "additional_owner_ids": []}, "g2": None
                }
            },
        ), self.assertRaisesRegex(RuntimeError, "initial_owner_comparison_invalid_global_selection"):
            compare_initial_owners(
                llm_config=object(),
                obligation_descriptions={"ordered": "Explain the mechanism."},
                observations=(first, second),
                admitted_groups=(("pandas/core/series.py", "*"), ("pandas/core/ops.py", "*")),
                max_input_chars=40_000,
                max_selected=2,
            )

    def test_file_admission_uses_exact_serialized_comparison_budget(self) -> None:
        values = (
            _observation("first", "first", 100, "function first() { return build(); }"),
            _observation("second", "second", 200, "function second() { return update(); }"),
        )
        admission = fit_initial_owner_comparison_admission(
            obligation_descriptions={"ordered": "Explain the mechanism."},
            observations=values,
            ranked_paths=("pandas/core/series.py",),
            preferred_input_chars=30_000,
            max_input_chars=40_000,
            max_files=24,
            max_selected=24,
        )

        self.assertEqual(admission.admitted_paths, ("pandas/core/series.py",))
        self.assertEqual(admission.candidate_count, 2)
        self.assertGreater(admission.total_input_chars, 0)

    def test_file_admission_keeps_crossing_group_and_stops_without_backfill(self) -> None:
        first = _observation("first", "first", 100, "function first() { return build(); }")
        second = _observation("second", "second", 200, "function second() { return update(); }")
        third = _observation("third", "third", 300, "function third() { return check(); }")
        second = DiscoveryObservation(**{
            **second.__dict__,
            "handle": replace(second.handle, path="pandas/core/large.py"),
            "observed_text": "x" * 4_000,
        })
        third = DiscoveryObservation(**{
            **third.__dict__,
            "handle": replace(third.handle, path="pandas/core/small.py"),
        })
        unconstrained = fit_initial_owner_comparison_admission(
            obligation_descriptions={"ordered": "Explain the mechanism."},
            observations=(first, second, third),
            ranked_paths=("pandas/core/series.py", "pandas/core/large.py", "pandas/core/small.py"),
            preferred_input_chars=40_000,
            max_input_chars=40_000,
            max_files=24,
            max_selected=24,
        )
        second_total = int(unconstrained.path_decisions[1]["total_input_chars"])

        admission = fit_initial_owner_comparison_admission(
            obligation_descriptions={"ordered": "Explain the mechanism."},
            observations=(first, second, third),
            ranked_paths=("pandas/core/series.py", "pandas/core/large.py", "pandas/core/small.py"),
            preferred_input_chars=second_total - 1,
            max_input_chars=40_000,
            max_files=24,
            max_selected=24,
        )

        self.assertEqual(admission.admitted_paths, ("pandas/core/series.py", "pandas/core/large.py"))
        self.assertEqual(
            admission.excluded_paths,
            ("pandas/core/small.py",),
        )
        self.assertEqual(admission.stopping_reason, "preferred_input_target_crossed")
        self.assertEqual(admission.stopped_at_path, "pandas/core/large.py")
        self.assertTrue(admission.path_decisions[1]["crossed_budget"])
        self.assertEqual(admission.path_decisions[2]["decision"], "excluded_after_budget_crossing")
        self.assertEqual(admission.total_input_chars, second_total)

        # Equality is not overflow: the next complete group is still admitted.
        equal = fit_initial_owner_comparison_admission(
            obligation_descriptions={"ordered": "Explain the mechanism."},
            observations=(first, second, third),
            ranked_paths=("pandas/core/series.py", "pandas/core/large.py", "pandas/core/small.py"),
            preferred_input_chars=second_total, max_input_chars=40_000,
            max_files=24, max_selected=24)
        self.assertEqual(len(equal.admitted_paths), 3)
        self.assertEqual(equal.stopped_at_path, "pandas/core/small.py")

    def test_first_group_may_cross_maximum_but_no_following_group_is_added(self) -> None:
        small = _observation("small", "small", 10, "return read();")
        large = [replace(_observation(str(i), str(i), 100+i*60, "x"*80),
                         handle=replace(small.handle, path="large.py", node_id=f"function:{i}", line_start=i*60+1)) for i in range(15)]
        kwargs = dict(obligation_descriptions={"ordered": "Explain work."}, max_selected=24, max_files=24,
                      preferred_input_chars=100_000, max_input_chars=100_000)
        measured = fit_initial_owner_comparison_admission(observations=[small], ranked_paths=[small.handle.path], **kwargs)
        kwargs['max_input_chars'] = measured.total_input_chars
        result = fit_initial_owner_comparison_admission(observations=[*large, small], ranked_paths=['large.py', small.handle.path], **kwargs)
        self.assertEqual(result.admitted_paths, ('large.py',))
        self.assertEqual(result.path_decisions[0]['decision'], 'admitted')
        self.assertGreater(result.total_input_chars, measured.total_input_chars)
        self.assertEqual(result.excluded_paths, (small.handle.path,))
        self.assertEqual(result.stopping_reason, 'maximum_input_threshold_crossed')

    def test_file_cap_still_applies(self) -> None:
        first = _observation('first', 'first', 10, 'return read();')
        second = replace(first, id='second', handle=replace(first.handle, path='second.py'))
        result = fit_initial_owner_comparison_admission(obligation_descriptions={'ordered': 'Explain.'},
            observations=[first,second], ranked_paths=[first.handle.path,second.handle.path],
            preferred_input_chars=100_000, max_input_chars=100_000, max_files=1, max_selected=24)
        self.assertEqual(result.admitted_paths, (first.handle.path,))
        self.assertEqual(result.path_decisions[1]['decision'], 'excluded_file_limit')

    def test_file_admission_allows_first_file_above_preferred_but_below_hard_ceiling(self) -> None:
        value = _observation("first", "first", 100, "function first() { return build(); }")

        admission = fit_initial_owner_comparison_admission(
            obligation_descriptions={"ordered": "Explain the mechanism."},
            observations=(value,),
            ranked_paths=("pandas/core/series.py",),
            preferred_input_chars=1,
            max_input_chars=40_000,
            max_files=24,
            max_selected=24,
        )

        self.assertEqual(admission.admitted_paths, ("pandas/core/series.py",))
        self.assertEqual(admission.stopping_reason, "preferred_input_target_crossed")

    def test_resolves_sibling_methods_and_keeps_class_as_outer_context(self) -> None:
        nodes = (
            {"id": "series", "kind": "class", "qualified_name": "Series", "line_start": 84, "line_end": 2550},
            {"id": "append", "kind": "method", "qualified_name": "Series::append", "line_start": 1443, "line_end": 1464},
            {"id": "binop", "kind": "method", "qualified_name": "Series::_binop", "line_start": 1466, "line_end": 1511},
        )

        selected = select_range_candidate_owners(nodes, line_start=1434, line_end=1473)

        self.assertEqual([item["id"] for item in selected], ["append", "binop"])
        self.assertEqual({item["outer_node_id"] for item in selected}, {"series"})

    def test_support_counts_distinguish_repeated_views_from_independent_support(self) -> None:
        value = _observation("binop", "_binop", 300, "def _binop(): pass")
        value = DiscoveryObservation(
            **{
                **value.__dict__,
                "provenance": (
                    DiscoveryProvenance(
                        "qdrant_dense_file_group", "q:ordered", ("ordered",), (1,), (0.4,), source_key="series.py:1:40"
                    ),
                    DiscoveryProvenance(
                        "qdrant_dense_file_group", "q:trigger", ("trigger",), (2,), (0.3,), source_key="series.py:1:40"
                    ),
                    DiscoveryProvenance(
                        "qdrant_sparse_file_group", "q:trigger", ("trigger",), (3,), (0.2,), source_key="series.py:31:70"
                    ),
                ),
            }
        )
        self.assertEqual(
            value.support_counts,
            {"raw_chunks": 2, "query_views": 3, "obligations": 2, "channels": 2},
        )

    def test_compares_every_owner_and_can_select_third_ranked_owner(self) -> None:
        values = (
            _observation("reduce", "_reduce", 100, "def _reduce(...):\n    return name"),
            _observation("to_string", "to_string", 200, "def to_string(...):\n    return name"),
            _observation("binop", "_binop", 300, "def _binop(other, func):\n    result = func(this_vals, other_vals)"),
        )
        response = {"groups": {"g1": ["o3"]}}
        with patch(
            "services.retrieval.workspace.pipeline.execution_flow.initial_owner_comparison.complete_json",
            return_value=response,
        ) as completion:
            result = compare_initial_owners(
                llm_config=object(),
                obligation_descriptions={"ordered": "Find the binary operation path."},
                observations=values,
                admitted_groups=(("pandas/core/series.py", "ordered"),),
                max_input_chars=40_000,
            )

        payload = completion.call_args.args[1][1]["content"]
        payload_value = json.loads(payload)
        self.assertTrue(all(f'"o{index}"' in payload for index in (1, 2, 3)))
        self.assertIn("Series::_binop", payload)
        self.assertIn("views", payload_value)
        self.assertTrue(all("x" not in owner for owner in payload_value["owners"].values()))
        self.assertEqual(tuple(item.id for item in result.selected), ("binop",))
        self.assertEqual({item.id for item in result.dormant}, {"reduce", "to_string"})

    def test_held_owner_remains_in_its_file_obligation_group(self) -> None:
        """A file's third obligation must not disappear before comparison.

        The global qualification guardrail may later retain only two obligation
        variants per path.  Owner comparison runs before that boundary and must
        still see every owner in each independently admitted file/obligation
        group.
        """
        reduce = _observation("reduce", "_reduce", 2058, "def _reduce(...): return name")
        reduce = DiscoveryObservation(
            **{
                **reduce.__dict__,
                "provenance": (
                    DiscoveryProvenance(
                        "qdrant_file_group_dense",
                        "qdrant_file_group_dense:explain_trigger",
                        ("explain_trigger",),
                        (1,),
                        (0.6,),
                        source_key="pandas/core/series.py:2058:2097",
                    ),
                ),
            }
        )
        binop = _observation(
            "binop",
            "_binop",
            1434,
            "def _binop(other, func):\n    result = func(this_vals, other_vals)",
        )
        binop = DiscoveryObservation(
            **{
                **binop.__dict__,
                "provenance": (
                    DiscoveryProvenance(
                        "qdrant_file_group_dense",
                        "qdrant_file_group_dense:explain_trigger",
                        ("explain_trigger",),
                        (2,),
                        (0.6,),
                        source_key="pandas/core/series.py:1434:1473",
                    ),
                ),
            }
        )

        groups = _candidate_groups(
            (reduce, binop),
            (("pandas/core/series.py", "explain_trigger"),),
        )

        self.assertEqual(len(groups), 1)
        self.assertEqual(
            {item.handle.symbol for item in next(iter(groups.values()))},
            {"Series::_reduce", "Series::_binop"},
        )

    def test_file_group_combines_owners_found_by_different_obligations(self) -> None:
        reduce = _observation("reduce", "_reduce", 2058, "def _reduce(...): return name")
        binop = _observation("binop", "_binop", 1434, "def _binop(...): return result")
        binop = DiscoveryObservation(
            **{
                **binop.__dict__,
                "provenance": (
                    DiscoveryProvenance(
                        "qdrant_file_group_dense",
                        "ordered",
                        ("explain_ordered_mechanism",),
                        (2,),
                        (0.5,),
                    ),
                ),
            }
        )

        groups = _candidate_groups(
            (reduce, binop),
            (("pandas/core/series.py", "ordered"),),
        )

        self.assertEqual(len(groups), 1)
        self.assertEqual(
            {item.handle.symbol for item in next(iter(groups.values()))},
            {"Series::_reduce", "Series::_binop"},
        )

    def test_source_view_prioritizes_executable_call_over_owner_name_assignment(self) -> None:
        excerpt = _compact_source_view(
            "def flex_wrapper(self, other, op):\n"
            "    flex_wrapper.__name__ = name\n"
            "    return self._binop(other, op, level=level, fill_value=fill_value)\n"
        )

        self.assertIn("return self._binop", excerpt)
        self.assertNotIn("flex_wrapper.__name__", excerpt)

    def test_single_owner_group_is_selected_without_llm(self) -> None:
        value = _observation("binop", "_binop", 300, "def _binop(other, func): pass")
        unrelated = DiscoveryObservation(
            id="unrelated",
            handle=SourceHandle(path="pandas/other.py", line_start=1, line_end=2, node_id="other"),
            observed_text="other",
            provenance=(DiscoveryProvenance("dense", "q", ("ordered",)),),
        )
        with patch(
            "services.retrieval.workspace.pipeline.execution_flow.initial_owner_comparison.complete_json"
        ) as completion:
            result = compare_initial_owners(
                llm_config=object(),
                obligation_descriptions={"ordered": "obligation"},
                observations=(value, unrelated),
                admitted_groups=(("pandas/core/series.py", "ordered"),),
                max_input_chars=40_000,
            )
        completion.assert_not_called()
        self.assertEqual(tuple(item.id for item in result.selected), ("binop",))
        self.assertEqual(result.dormant, ())
        self.assertEqual(result.auto_selected_group_count, 1)

    def test_comparison_allows_one_crossing_group(self) -> None:
        value = _observation("binop", "_binop", 300, "def _binop(): pass")
        with patch("services.retrieval.workspace.pipeline.execution_flow.initial_owner_comparison.complete_json",
                   return_value={"selections": {"g1": {"primary_owner_id": "o1",
                                                 "additional_owner_ids": []}}}) as completion:
            compare_initial_owners(llm_config=object(), obligation_descriptions={"ordered": "obligation"},
                observations=(value,), admitted_groups=((value.handle.path, "*"),),
                max_input_chars=10, max_selected=24)
        completion.assert_called_once()

    def test_fails_when_another_group_follows_already_over_budget_prefix(self) -> None:
        values = (
            _observation("reduce", "_reduce", 100, "def _reduce(): pass"),
            replace(_observation("binop", "_binop", 300, "def _binop(): pass"),
                    handle=replace(_observation("binop", "_binop", 300, "").handle, path="other.py")),
        )
        with self.assertRaisesRegex(RuntimeError, "initial_owner_comparison_input_budget_exceeded"):
            compare_initial_owners(
                llm_config=object(),
                obligation_descriptions={"ordered": "obligation"},
                observations=values,
                admitted_groups=(("pandas/core/series.py", "ordered"), ("other.py", "ordered")),
                max_input_chars=10,
                max_selected=24,
            )


if __name__ == "__main__":
    unittest.main()
