import unittest
from dataclasses import replace
from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import DiscoveryObservation, SourceHandle
from services.retrieval.workspace.pipeline.execution_flow.evidence_qualification import QualificationDecision
from testing.codeRepoQA.owner_election_variant import elect_owner_primaries


class ElectionTests(unittest.TestCase):
    def test_raw_candidate_cannot_replace_qualified_owner(self):
        obs = {i: DiscoveryObservation(i, SourceHandle('a.py', 1, 5), '', (), exact_anchor_matches=('anchor',) if i == 'b' else ()) for i in ('a', 'b')}
        decisions = {'a': QualificationDecision('a', 'promote', 'direct_evidence', 'fact', supported_obligation_ids=('o1',))}
        self.assertEqual(elect_owner_primaries(obs, decisions)[0], {'a': 1})
        decisions['b'] = QualificationDecision('b', 'promote', 'direct_evidence', 'fact', supported_obligation_ids=('o1', 'o2'))
        counts, rows = elect_owner_primaries(obs, decisions)
        self.assertEqual(counts, {'b': 2})
        self.assertEqual(rows[0]['complements'], ['a'])
        self.assertIn('a', obs)

    def test_empty_or_rejected_support_does_not_elect(self):
        obs = {'a': DiscoveryObservation('a', SourceHandle('a.py', 1, 5), '', ())}
        for decision in (QualificationDecision('a', 'promote', 'navigation_only', 'lead'), QualificationDecision('a', 'reject', 'insufficient', 'no', supported_obligation_ids=('o1',))):
            self.assertEqual(elect_owner_primaries(obs, {'a': decision}), ({}, []))


if __name__ == '__main__':
    unittest.main()
