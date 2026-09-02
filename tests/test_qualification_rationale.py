from dataclasses import replace
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from services.intent.models import EvidenceObligation
from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import DiscoveryObservation, SourceHandle
from services.retrieval.workspace.pipeline.execution_flow.source_disclosure import DisclosureCard
from services.retrieval.workspace.pipeline.execution_flow.evidence_qualification import (
    QualificationReuseCache, qualify_cards, _validate_decisions, _response_format,
    prepare_qualification_request,
)
from tests.qualification_test_support import QualificationDecision
from services.retrieval.workspace.pipeline.execution_flow.qualification_first_retrieval import (
    _candidate_from_qualified, _controller_candidate_payload,
)
from services.retrieval.workspace.pipeline.execution_flow.obligation_retrieval import (
    ObligationProgress, _evidence_item, _candidate_trace_item, _consolidate_obligation_evidence,
    _select_mechanism_flows,
)
from services.retrieval.workspace.pipeline.execution_flow.coverage_evaluation import _bounded_candidates
from testing.codeRepoQA.qualification_trace_adapter import qualification_decision_from_trace

MODULE = 'services.retrieval.workspace.pipeline.execution_flow.evidence_qualification'


class QualificationRationaleTests(unittest.TestCase):
    def setUp(self):
        self.obligations = (EvidenceObligation('state', 'Explain invalidation state.', True),)
        self.card = DisclosureCard('owner', SourceHandle('src/state.ts', 1, 3, node_id='function:state', symbol='state'),
                                   'full', 'function state() {\n cache.clear();\n}', owner_name='state', owner_kind='function')
        self.reason = 'Clears cached state after invalidation; downstream emission is not shown.'
        self.decision = QualificationDecision('owner', 'promote', 'direct_evidence', self.reason,
            ('Clears cache.',), ('Emission is not shown.',), '', ('state',))
        self.prior = dict(reason=self.reason, support_level='direct_evidence', disposition='promote',
                          supported_obligation_ids=['state'])

    def response(self, classification='promote_direct', reason=None):
        direct = classification == 'promote_direct'
        return {'decisions': {'owner': {
            'assessment': {
                'disposition': 'retain',
                'evidence_kind': 'direct_fact' if direct else 'navigation_lead',
                'contributing_obligation_ids': ['state'] if direct else [],
                'individually_established_obligation_ids': ['state'] if direct else [],
            },
            'rationale': {
                'reason': reason or self.reason,
                'visible_support': ['cache.clear()'],
                'missing_information': [],
                'local_follow_up': '',
            },
        }}}

    def qualify(self, card, cache):
        return qualify_cards(llm_config=SimpleNamespace(model='fixed'), user_request='Explain invalidation',
            cards=(card,), obligations=self.obligations, max_input_chars=40000, reuse_cache=cache)

    def candidate(self):
        observation = DiscoveryObservation('owner', self.card.handle, self.card.source_text, (), artifact_role='implementation')
        return _candidate_from_qualified(observation, self.decision, self.card)

    def test_reason_bound_is_schema_and_runtime_enforced_without_truncation(self):
        schema = (_response_format(('owner',))['json_schema']['schema']['$defs']['decision']
                  ['properties']['rationale']['properties']['reason'])
        self.assertEqual(schema['maxLength'], 400)
        valid = self.response(reason='x' * 400)
        self.assertEqual(
            len(_validate_decisions(valid, ('owner',), {'owner': ('state',)})[0].rationale.reason),
            400,
        )
        for reason in [' ', 'x' * 401]:
            with self.assertRaises(RuntimeError):
                _validate_decisions(self.response(reason=reason), ('owner',), {'owner': ('state',)})

    def test_prior_rationale_does_not_invalidate_positive_reuse(self):
        cache = QualificationReuseCache()
        with patch(MODULE + '.complete_json', return_value=self.response()) as llm:
            first = self.qualify(self.card, cache)
            second = self.qualify(replace(self.card, previous_qualification=self.prior), cache)
        self.assertEqual(llm.call_count, 1)
        self.assertEqual(first.decisions, second.decisions)

    def test_changed_source_receives_prior_reason_and_can_correct_direct_judgment(self):
        cache = QualificationReuseCache()
        with patch(MODULE + '.complete_json', side_effect=[self.response(), self.response('promote_navigation',
            'This replacement only names the cache; it no longer clears state.')]) as llm:
            self.qualify(self.card, cache)
            result = self.qualify(replace(self.card, source_text='const cacheName = "cache";',
                                         previous_qualification=self.prior), cache)
        payload = json.loads(llm.call_args.args[1][1]['content'])
        self.assertEqual(payload['observations'][0]['previous_qualification'], self.prior)
        self.assertTrue(result.decisions[0].assessment.is_navigation)

    def test_previous_negative_judgment_is_not_frozen(self):
        prior = {**self.prior, 'support_level': 'insufficient', 'disposition': 'reject',
                 'reason': 'No state transition was visible.', 'supported_obligation_ids': []}
        with patch(MODULE + '.complete_json', return_value=self.response()) as llm:
            result = self.qualify(replace(self.card, previous_qualification=prior), QualificationReuseCache())
        self.assertTrue(result.decisions[0].assessment.is_direct_fact)
        self.assertEqual(json.loads(llm.call_args.args[1][1]['content'])['observations'][0]['previous_qualification'], prior)

    def test_partial_direct_fact_is_retained_without_manufacturing_complete_obligation_support(self):
        response = self.response()
        assessment = response['decisions']['owner']['assessment']
        assessment['individually_established_obligation_ids'] = []
        decision = _validate_decisions(response, ('owner',), {'owner': ('state',)})[0]
        observation = DiscoveryObservation(
            'owner', self.card.handle, self.card.source_text, (), artifact_role='implementation'
        )
        candidate = _candidate_from_qualified(observation, decision, self.card)
        states = (ObligationProgress(self.obligations[0], candidates=[candidate]),)

        candidate_by_id, direct, inherited, flows, _, ledger = _select_mechanism_flows(
            states, expanded_edges=()
        )
        candidate_id = next(iter(candidate_by_id))

        self.assertTrue(decision.assessment.is_direct_fact)
        self.assertEqual(decision.assessment.contributing_obligation_ids, ('state',))
        self.assertEqual(decision.assessment.individually_established_obligation_ids, ())
        self.assertEqual(direct[candidate_id], set())
        self.assertEqual(inherited[candidate_id], set())
        self.assertTrue(any(candidate_id in flow['candidate_ids'] for flow in flows))
        inventory = next(item for item in ledger['candidate_inventory'] if item['candidate_id'] == candidate_id)
        self.assertTrue(inventory['selected_for_final_request'])

    def test_offline_trace_adapter_reads_nested_and_historical_decisions(self):
        self.assertEqual(qualification_decision_from_trace(self.decision.to_dict()), self.decision)
        historical = {
            'observation_id': 'owner', 'disposition': 'promote',
            'support_level': 'direct_evidence', 'reason': self.reason,
            'visible_support': ['Clears cache.'], 'missing_information': ['Emission is not shown.'],
            'local_follow_up': '', 'supported_obligation_ids': ['state'],
        }
        restored = qualification_decision_from_trace(historical)
        self.assertEqual(restored.assessment.individually_established_obligation_ids, ('state',))
        self.assertEqual(restored.rationale.reason, self.reason)

    def test_prior_metadata_is_accounted_in_qualification_budget(self):
        args = dict(user_request='Explain invalidation', max_input_chars=40000, obligations=self.obligations)
        old = prepare_qualification_request(cards=(self.card,), **args)
        new = prepare_qualification_request(cards=(replace(self.card, previous_qualification=self.prior),), **args)
        self.assertGreater(new.fixed_input_chars, old.fixed_input_chars)
        self.assertLess(new.source_capacity, old.source_capacity)

    def test_reason_survives_candidate_coverage_trace_and_returned_evidence(self):
        candidate = self.candidate()
        payload = _controller_candidate_payload(candidate)
        self.assertEqual(payload['qualification_reason'], self.reason)
        self.assertEqual(_bounded_candidates((payload,), max_input_chars=40000)[0]['qualification_reason'], self.reason)
        self.assertEqual(_candidate_trace_item(candidate)['qualification_reason'], self.reason)
        self.assertEqual(_evidence_item(candidate, obligation_id='state', rank=1).metadata['qualification_reason'], self.reason)

    def test_coverage_candidates_fit_metadata_and_source_inside_the_supplied_budget(self):
        candidate = self.candidate()
        payloads = []
        for index in range(40):
            payload = _controller_candidate_payload(candidate)
            payload['candidate_id'] = f'candidate:{index}'
            payload['observation_id'] = f'observation:{index}'
            payload['snippet'] = 'source line\n' * 1000
            payloads.append(payload)

        bounded = _bounded_candidates(tuple(payloads), max_input_chars=24000)

        self.assertEqual(len(bounded), 40)
        self.assertLessEqual(len(json.dumps(bounded, sort_keys=True)), 24000)
        self.assertNotIn('observation_id', bounded[0])

    def test_final_payload_and_budget_include_reason(self):
        candidate = self.candidate()
        states = (ObligationProgress(self.obligations[0], candidates=[candidate]),)
        old_states = (ObligationProgress(self.obligations[0], candidates=[replace(candidate, qualification_reason='')]),)
        old = _select_mechanism_flows(old_states, expanded_edges=())[-1]
        new = _select_mechanism_flows(states, expanded_edges=())[-1]
        self.assertGreater(new['used_chars'], old['used_chars'])
        ctx = SimpleNamespace(config=SimpleNamespace(llm_config=SimpleNamespace()),
                              trace=SimpleNamespace(record=lambda *args: None))
        with patch('services.retrieval.workspace.pipeline.execution_flow.obligation_retrieval.complete_json',
                   side_effect=RuntimeError('captured request')) as llm:
            with self.assertRaisesRegex(RuntimeError, 'captured request'):
                _consolidate_obligation_evidence(ctx, states, expanded_edges=())
        payload = json.loads(llm.call_args.args[1][1]['content'])
        self.assertEqual(payload['candidates'][0]['qualification_reason'], self.reason)


if __name__ == '__main__':
    unittest.main()
