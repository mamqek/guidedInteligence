from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tests.test_qualification_first_retrieval import _observation, _Tool
from services.retrieval.workspace.pipeline.execution_flow.verified_leads import (
    discover_qualified_file_leads, _select_verified_lead_actions,
    retain_verified_lead, _inspection_request,
)
from services.retrieval.workspace.pipeline.execution_flow.evidence_qualification import QualificationDecision
from services.retrieval.workspace.pipeline.execution_flow.source_disclosure import DisclosureCard
from services.retrieval.workspace.pipeline.execution_flow.coverage_evaluation import ObligationCoverage
from services.retrieval.workspace.pipeline.execution_flow.actions.scheduler import schedule_round_actions
from services.retrieval.workspace.pipeline.execution_flow.action_novelty import normalized_action_effect


class QualifiedFileLeadTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = 'function build() {\n  State.update();\n}\n'
        Path(self.temp.name, 'builder.ts').write_text(self.source, encoding='utf-8')
        self.obs = _observation('source', 'builder.ts', 'function:build', ('retrieval_only',))
        self.target = dict(id='function:update', name='update', qualified_name='State.update',
                           path='state.ts', line_start=1, line_end=5, kind='function')
        self.decision = QualificationDecision('source', 'promote', 'direct_evidence', 'Visible state transition.',
                                               supported_obligation_ids=('semantic',))
        self.card = DisclosureCard('source', self.obs.handle, 'complete_owner', self.source,
                                   owner_kind='function', owner_name='build', owner_line_start=1, owner_line_end=3)
        self.nodes = [self.target]
        self.caps = [dict(node_id=self.target['id'], incoming=[dict(kind='calls', count=2)])]

    def run_discovery(self, **overrides):
        args = dict(round_index=0, changed_observation_ids=('source',), observations={'source': self.obs},
                    decisions={'source': self.decision}, cards={'source': self.card},
                    coverage=(ObligationCoverage('semantic', 'partial', (), 'Target mechanism missing.', 'implementation'),),
                    pending_node_ids=set(), executed_node_ids=set(), workspace_root=self.temp.name, trace=None,
                    structural_tools={
                        'structural_source_owner_calls': _Tool('structural_source_owner_calls', {'calls': [
                            dict(name='update', qualifier='State', line_start=2)]}),
                        'structural_find_exact_symbol': _Tool('structural_find_exact_symbol', {'nodes': self.nodes}),
                        'structural_edge_capabilities': _Tool('structural_edge_capabilities', {'nodes': self.caps}),
                    })
        args.update(overrides)
        return discover_qualified_file_leads(**args)

    def test_direct_visible_call_produces_lead_not_evidence_and_is_repeatable(self):
        first = self.run_discovery()
        self.assertEqual(first, self.run_discovery())
        leads, audit, calls = first
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0].obligation_id, 'semantic')
        self.assertEqual(leads[0].source_call_line, 2)
        self.assertEqual(calls, 3)
        self.assertEqual(audit[-1]['status'], 'accepted')
        self.assertEqual(self.obs.obligation_ids, ('retrieval_only',))

    def test_hidden_call_does_not_resolve_symbol(self):
        leads, audit, calls = self.run_discovery(cards={'source': replace(self.card, source_text='function build() {')})
        self.assertEqual(leads, ())
        self.assertEqual(calls, 1)
        self.assertEqual(audit[-1]['reason'], 'call_not_in_fitted_source')

    def test_ast_owner_requires_validated_callable_kind_and_keeps_provenance(self):
        from services.retrieval.workspace.tools.codegraph import SourceOwnerCallsTool
        from services.retrieval.config import WorkspaceRetrievalConfig
        (Path(self.temp.name) / 'owners.py').write_text('exports.parse = lambda value: State.update(value)\n', encoding='utf-8')
        source_id = 'source_owner:owners.py:1:1'
        observation = replace(self.obs, handle=replace(self.obs.handle, path='owners.py', node_id=source_id, symbol='exports.parse'))
        card = replace(self.card, handle=observation.handle, owner_kind='source_owner', owner_name='exports.parse',
                       owner_line_start=1, owner_line_end=1, source_text='exports.parse = lambda value: State.update(value)')
        config = WorkspaceRetrievalConfig(self.temp.name, '', None, None, None)
        tool = SourceOwnerCallsTool(config, None)
        leads, audit, _ = self.run_discovery(observations={'source':observation}, cards={'source':card}, structural_tools={
            'structural_source_owner_calls':tool,
            'structural_find_exact_symbol':_Tool('structural_find_exact_symbol', {'nodes':self.nodes}),
            'structural_edge_capabilities':_Tool('structural_edge_capabilities', {'nodes':self.caps})})
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0].source_callable_kind, 'assigned_function')
        self.assertEqual(audit[-1]['source_callable_kind'], 'assigned_function')
        self.assertEqual(card.owner_kind, 'source_owner')  # Qualification payload is unchanged.

    def test_deferred_canonical_target_is_eligible_but_qualified_target_is_not(self):
        target = _observation('target', 'state.ts', self.target['id'], ('retrieval_only',))
        observations = {'source': self.obs, 'target': target}
        leads, audit, _ = self.run_discovery(observations=observations)
        self.assertEqual(len(leads), 1)
        self.assertTrue(audit[-1]['target_previously_canonical'])
        self.assertEqual(self.run_discovery(observations=observations, decisions={
            'source': self.decision, 'target': replace(self.decision, observation_id='target', disposition='reject'),
        })[0], ())

    def test_ambiguous_or_saturated_symbol_results_are_not_unique(self):
        self.nodes.append({**self.target, 'id': 'other'})
        self.assertEqual(self.run_discovery()[1][-1]['reason'], 'target_not_unique')
        self.nodes = [{**self.target, 'id': str(i)} for i in range(20)]
        self.assertEqual(self.run_discovery()[1][-1]['reason'], 'symbol_result_limit_cannot_prove_unique')

    def test_utilities_or_missing_capabilities_rejected(self):
        self.caps[0]['incoming'][0]['count'] = 13
        self.assertEqual(self.run_discovery()[1][-1]['reason'], 'high_static_call_indegree')
        self.caps = []
        self.assertEqual(self.run_discovery()[1][-1]['reason'], 'utility_metrics_unavailable')

    def test_only_qualified_semantic_support_and_unresolved_obligations(self):
        for decision in (replace(self.decision, support_level='navigation_only'),
                         replace(self.decision, disposition='reject'),
                         replace(self.decision, supported_obligation_ids=('retrieval_only',))):
            self.assertEqual(self.run_discovery(decisions={'source': decision})[2], 0)
        self.assertEqual(self.run_discovery(coverage=(ObligationCoverage('semantic', 'covered', (), '', 'implementation'),))[2], 0)
        self.assertEqual(len(self.run_discovery(observations={'source': replace(self.obs, artifact_role='test')})[0]), 1)

    def test_pending_and_executed_targets_rejected(self):
        for field in ('pending_node_ids', 'executed_node_ids'):
            self.assertEqual(self.run_discovery(**{field: {self.target['id']}})[0], ())

    def test_source_local_repetition_blocks_utility_even_with_sparse_graph_edges(self):
        Path(self.temp.name, 'builder.ts').write_text(self.source + '\nState.update();' * 12, encoding='utf-8')
        leads, audit, calls = self.run_discovery()
        self.assertEqual(leads, ())
        self.assertEqual(audit[-1]['source_file_literal_calls'], 13)
        self.assertEqual(audit[-1]['reason'], 'high_source_file_call_repetition')
        self.assertEqual(calls, 1)

    def test_reserved_repeat_does_not_consume_slot_or_starve_next_lead(self):
        lead = self.run_discovery()[0][0]
        other = replace(lead, target_node_id='function:second', source_rank=2)
        actions = _select_verified_lead_actions((lead, other), executed_count=0, observation_to_island={}, limit=2)
        schedule = schedule_round_actions((), active_root_ids=(), active_island_ids=(), normal_limit=2,
            round_index=1, refined_paths=set(), attempted_action_ids=set(),
            attempted_effects={normalized_action_effect(actions[0])}, pending_maturation_child_roots=set(),
            blocked_maturation_root_ids=set(), verified_lead_actions=actions)
        self.assertEqual(schedule.verified_lead, (actions[1],))
        self.assertEqual(len(schedule.suppressed), 1)
        self.assertEqual(_select_verified_lead_actions((lead,), executed_count=2, observation_to_island={}), ())

    def test_explicit_request_precedes_earlier_high_rank_structural_child(self):
        incidental = self.run_discovery()[0][0]
        requested = replace(incidental, target_node_id='requested', structural_child=False,
                            qualified_target=False, source_rank=100, discovered_round=3,
                            origin='qualification_followup', inspection_basis='qualification_followup')
        actions = _select_verified_lead_actions((incidental, requested), executed_count=0, observation_to_island={})
        self.assertEqual(actions[0].target_node_id, 'requested')
        self.assertEqual(_select_verified_lead_actions((incidental,), executed_count=0, observation_to_island={})[0].target_node_id,
                         incidental.target_node_id)

    def test_qualified_source_can_itself_request_target(self):
        for text in ('Inspect State.update to establish invalidation.', 'Inspect update next.'):
            lead = self.run_discovery(decisions={'source': replace(self.decision, local_follow_up=text)})[0][0]
            self.assertEqual(lead.inspection_basis, 'qualification_followup')
            self.assertEqual(lead.request_text, text)
        self.assertEqual(_inspection_request('State.update', replace(self.decision, local_follow_up='Inspect Other.update'),
                                             (), self.source)[0], 'incidental_visible_call')
        self.assertEqual(_inspection_request('State.update', self.decision, ('Missing State.update behavior.',), self.source)[0],
                         'missing_information')

    def test_pending_incidental_can_upgrade_without_duplicate_or_downgrade(self):
        old = self.run_discovery()[0][0]
        pending = {old.target_node_id: old}
        leads, audit, _ = self.run_discovery(pending_node_ids=set(pending), pending_leads=pending,
            decisions={'source': replace(self.decision, local_follow_up='Inspect State.update.')})
        self.assertEqual(audit[-1]['reason'], 'pending_lead_priority_upgraded')
        retain_verified_lead(pending, leads[0])
        retain_verified_lead(pending, old)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[old.target_node_id].inspection_basis, 'qualification_followup')
        self.assertEqual(self.run_discovery(pending_node_ids=set(pending), pending_leads=pending,
            executed_node_ids=set(pending), decisions={'source': replace(self.decision, local_follow_up='Inspect State.update.')})[0], ())


if __name__ == '__main__':
    unittest.main()
