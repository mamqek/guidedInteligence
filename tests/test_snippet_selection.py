from dataclasses import replace
import unittest

from services.retrieval.workspace.pipeline.execution_flow.snippet_selection import (
    admit_snippets, discovery_priority, discovery_selection_view, qualified_selection_view,
)
from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import (
    DiscoveryObservation, DiscoveryProvenance, SourceHandle,
)
from services.retrieval.workspace.pipeline.execution_flow.obligation_retrieval import GroundedCandidate, CandidateFacts
from services.retrieval.workspace.pipeline.execution_flow.qualification_first_retrieval import (
    _deferred_after_initial_owner_comparison,
)


def observation(identifier, *, path="a.py", rank=1, recurrence=1):
    return DiscoveryObservation(identifier, SourceHandle(path, 1, 5, node_id=identifier),
        "return important()", (DiscoveryProvenance("dense", "q", ("query_obligation",), (rank,), (0.7,)),),
        recurrence=recurrence)


class SelectionTests(unittest.TestCase):
    def test_adapter_keeps_query_association_distinct_from_support(self):
        raw = observation("a")
        initial = discovery_selection_view(raw)
        self.assertIsNone(initial.qualification)
        self.assertIsNone(initial.supported_obligations)
        self.assertIsNone(initial.connections)
        candidate = GroundedCandidate("a.py", 1, 10, "expanded source", .7,
            "qualified_navigation_evidence", node_id="a", obligation_ids=(), qualification_reason="Only a lead.",
            facts=CandidateFacts(visible_calls=("target",), full_range=(1, 30)))
        later = qualified_selection_view(candidate, identity=raw.id, discovery=raw, connections=(), eligible=False,
                                         ineligibility_reason="no_supported_obligation")
        self.assertEqual(later.id, initial.id)
        self.assertEqual(later.retrieval_obligations, ("query_obligation",))
        self.assertEqual(later.supported_obligations, ())
        self.assertEqual(later.connections, ())
        self.assertEqual(later.source_segments, ((1, 10, "expanded source"),))
        self.assertEqual(later.qualification_reason, "Only a lead.")
        self.assertEqual(later.owner_range, (1, 30))
        self.assertEqual(later.source_facts["visible_calls"], ("target",))
        self.assertIsNone(initial.source_facts)
        missing = qualified_selection_view(candidate, identity="a", eligible=True)
        self.assertIsNone(missing.recurrence)
        self.assertIsNone(missing.exact_anchors)

    def test_deterministic_ranking_and_exact_marginal_group_cost(self):
        values = [observation("a", recurrence=3), observation("b", path="b.py", recurrence=2),
                  observation("c", recurrence=1)]
        views = tuple(map(discovery_selection_view, values))
        paths = {v.id: v.path for v in views}
        def measure(ids):
            return 100 + 10*len(ids) + 30*len({paths[x] for x in ids})
        first = admit_snippets(views, priority=lambda s, _: discovery_priority(s), measure=measure, threshold=180)
        again = admit_snippets(tuple(reversed(views)), priority=lambda s, _: discovery_priority(s),
                               measure=measure, threshold=180)
        self.assertEqual(first, again)
        self.assertEqual(first.admitted_ids, ("a", "b", "c"))
        self.assertEqual([r["marginal_chars"] for r in first.decisions], [140, 40, 10])
        self.assertEqual(first.crossing_id, "c")

    def test_eligibility_and_adaptive_priority_are_stage_owned(self):
        views = [discovery_selection_view(observation(x)) for x in ("a", "b", "c")]
        views.append(replace(views[0], id="excluded", eligible=False, ineligibility_reason="unsupported"))
        def priority(s, selected):
            return (0 if s.id == "a" or (selected and s.id == "c") else 1,)
        result = admit_snippets(views, priority=priority, measure=lambda ids: len(ids)*10, threshold=15)
        self.assertEqual(result.admitted_ids, ("a", "c"))
        self.assertEqual(result.excluded_ids, ("b", "excluded"))
        self.assertEqual(result.decisions[-1]["reason"], "unsupported")

    def test_duplicate_input_and_invalid_threshold_fail(self):
        view = discovery_selection_view(observation("a"))
        for values, threshold in [([view, view], 100), ([view], 0)]:
            with self.assertRaises(ValueError):
                admit_snippets(values, priority=lambda s, _: discovery_priority(s),
                               measure=lambda ids: 1, threshold=threshold)
        empty = admit_snippets([], priority=lambda s, _: (), measure=lambda ids: 100, threshold=10)
        self.assertEqual(empty.total_input_chars, 0)

    def test_unadmitted_same_file_snippets_stay_deferred_not_dormant(self):
        selected, dormant, omitted = [observation(x) for x in ("selected", "dormant", "omitted")]
        result = _deferred_after_initial_owner_comparison(
            baseline_candidates=(selected, dormant, omitted), owner_comparison_selected=(selected,),
            round_zero_selected=(selected,), owner_comparison_dormant=(dormant,),
            guardrail_decisions=({"observation_id": "omitted", "reason": "same_path_alternative"},))
        self.assertEqual([item.id for item in result], ["omitted"])
        self.assertEqual(result[0].admission_reason, "same_path_alternative")


if __name__ == "__main__":
    unittest.main()
