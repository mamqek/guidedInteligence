import unittest
from types import SimpleNamespace as N
from services.retrieval.workspace.pipeline.execution_flow.owner_reevaluation_audit import audit_owner_elections
from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import DiscoveryObservation, SourceHandle
from services.retrieval.workspace.pipeline.execution_flow.evidence_qualification import QualificationDecision


class OwnerAuditTests(unittest.TestCase):
    def test_island_output_identical_with_and_without_trace(self):
        from services.retrieval.workspace.pipeline.execution_flow.evidence_islands import build_semantic_islands
        from services.retrieval.workspace.pipeline.execution_flow.structural_components import StructuralComponentSelection
        obs = DiscoveryObservation('a', SourceHandle('a.py', 1, 2), '', ())
        decision = QualificationDecision('a', 'promote', 'direct_evidence', 'visible fact')
        args = ((obs,), (decision,), (), (), StructuralComponentSelection((), (), 0))
        records = []
        trace = N(record=lambda kind, payload: records.append((kind, payload)))
        plain = build_semantic_islands(*args)
        traced = build_semantic_islands(*args, trace=trace)
        self.assertEqual(plain, traced)
        self.assertEqual(records[0][0], 'owner_reevaluation_audited')

    def test_records_new_competitor_without_mutation(self):
        obs = {i: DiscoveryObservation(i, SourceHandle('a.py', 1, 2), '', ()) for i in ('a', 'b')}
        decisions = {i: QualificationDecision(i, 'promote', 'direct_evidence', 'visible fact') for i in obs}
        old = N(islands=[N(observation_ids=('a',), representative_observation_id='a')])
        result = N(islands=[N(id='island', observation_ids=('a', 'b'), representative_observation_id='b')], active_island_ids=('island',))
        before = repr((result, obs, decisions))
        rows = audit_owner_elections(result, old, obs, decisions, {}, lambda o, d: (o.id,))
        self.assertEqual(rows[0]['kind'], 'replaced')
        self.assertEqual(rows[0]['newly_promoted_ids'], ['b'])
        self.assertTrue(rows[0]['new_owner_competition'])
        self.assertEqual(before, repr((result, obs, decisions)))

    def test_initial_not_counted_as_challenge(self):
        obs = {'a': DiscoveryObservation('a', SourceHandle('a.py', 1, 2), '', ())}
        decisions = {'a': QualificationDecision('a', 'promote', 'direct_evidence', 'fact')}
        result = N(islands=[N(id='i', observation_ids=('a',), representative_observation_id='a')], active_island_ids=())
        row = audit_owner_elections(result, None, obs, decisions, {}, lambda o, d: (0,))[0]
        self.assertEqual(row['kind'], 'initial')
        self.assertFalse(row['new_owner_competition'])


if __name__ == '__main__':
    unittest.main()
