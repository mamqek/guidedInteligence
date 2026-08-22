from __future__ import annotations

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

    def test_fails_explicitly_when_compact_comparison_exceeds_budget(self) -> None:
        values = (
            _observation("reduce", "_reduce", 100, "def _reduce(): pass"),
            _observation("binop", "_binop", 300, "def _binop(): pass"),
        )
        with self.assertRaisesRegex(RuntimeError, "initial_owner_comparison_input_budget_exceeded"):
            compare_initial_owners(
                llm_config=object(),
                obligation_descriptions={"ordered": "obligation"},
                observations=values,
                admitted_groups=(("pandas/core/series.py", "ordered"),),
                max_input_chars=10,
            )


if __name__ == "__main__":
    unittest.main()
