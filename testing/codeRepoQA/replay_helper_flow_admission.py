"""Replay saved final-flow inputs; no retrieval, LLM calls, or source expansion.

The baseline selector is extracted from an explicit Git revision. Source is the
literal saved qualification payload, not a fresh read of the complete owner.
Trace scores are rounded, so baseline agreement is checked before comparison.
"""
from __future__ import annotations
import argparse
import ast
from dataclasses import fields
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from services.retrieval.workspace.pipeline.execution_flow import obligation_retrieval as flow


def replay(directory: Path, baseline_ref: str, recorded_policy: str = 'baseline'):
    rows = [(i, json.loads(s)) for i, s in enumerate((directory / 'retrieval-trace.jsonl').read_text(encoding='utf8').splitlines(), 1)]
    texts, source_scores = {}, {}
    for _, row in rows:
        p = row['payload']
        if row['event_type'] == 'discovery_observations_created':
            for item in (*p.get('raw_observations', ()), *p.get('observations', ()), *p.get('deferred_observations', ())):
                h = item['handle']
                key = f"node:{h['node_id']}" if h.get('node_id') else f"range:{h['path']}:{h['line_start']}:{h['line_end']}"
                source_scores[key] = max(source_scores.get(key, 0), item['best_score'])
        if row['event_type'] == 'llm_request_sent' and p.get('stage') == 'evidence_qualification':
            user = json.loads(next(m['content'] for m in p['request_payload']['messages'] if m['role'] == 'user'))
            for card in user['observations']:
                texts[card['observation_id']] = card['source_text']
        if row['event_type'] == 'disclosure_cards_created':
            for card in p['cards']:
                h = card['handle']
                key = f"node:{h['node_id']}" if h.get('node_id') else f"range:{h['path']}:{h['line_start']}:{h['line_end']}"
                texts[key] = texts[card['observation_id']]
    ledger_line, ledger_row = next((i, r) for i, r in rows if r['event_type'] == 'mechanism_flow_decision_ledger')
    ledger = ledger_row['payload']
    pool = next(r['payload'] for _, r in rows if r['event_type'] == 'final_candidate_pool_created')
    request = next(r['payload'] for _, r in rows if r['event_type'] == 'llm_request_sent' and r['payload'].get('stage') == 'obligation_evidence_consolidation')
    user = json.loads(next(m['content'] for m in request['request_payload']['messages'] if m['role'] == 'user'))
    states = {o['obligation_id']: flow.ObligationProgress(flow.EvidenceObligation(o['obligation_id'], o['description'], True,
              depends_on=tuple(o['depends_on']), evidence_role=flow.EvidenceRole(o['evidence_role']))) for o in user['obligations']}
    inventory = {item['candidate_id']: item for item in ledger['candidate_inventory']}
    char_counts = {item['candidate_id']: item['text_chars'] for item in pool['candidates']}
    candidate_fields = {f.name for f in fields(flow.GroundedCandidate)}
    exact_candidates = {}
    for cid, item in inventory.items():
        text = texts[cid]
        if len(text) != char_counts[cid]:
            raise ValueError(f'{cid}: saved source chars differ {len(text)} != {char_counts[cid]}')
        facts = {k: tuple(v) if isinstance(v, list) else v for k, v in item['facts'].items()}
        facts['semantic_discoveries'] = tuple(flow.SemanticDiscovery(**{**d, 'matched_terms': tuple(d['matched_terms'])}) for d in facts['semantic_discoveries'])
        facts['callable_defaults'] = tuple((v['value'], v['factory']) for v in facts['callable_defaults'])
        values = {k: tuple(v) if isinstance(v, list) else v for k, v in item.items() if k in candidate_fields and k != 'facts'}
        if cid in source_scores and round(source_scores[cid], 4) == item['score']:
            values['score'] = source_scores[cid]
            if item['base_score'] == item['score']:
                values['base_score'] = source_scores[cid]
        candidate = flow.GroundedCandidate(**values, facts=flow.CandidateFacts(**facts), text=text, file_role=flow.file_role(item['path']))
        exact_candidates[cid] = candidate
        for obligation in item['obligation_ids']:
            if obligation in states:
                states[obligation].candidates.append(candidate)
    source = subprocess.check_output(['git', 'show', f'{baseline_ref}:services/retrieval/workspace/pipeline/execution_flow/obligation_retrieval.py'], text=True, encoding='utf8')
    tree = ast.parse(source)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_select_mechanism_flows')
    namespace = dict(vars(flow))
    support_graph = (exact_candidates,
        {cid:set(item['direct_obligation_ids']) for cid,item in inventory.items()},
        {cid:set(item['inherited_obligation_ids']) for cid,item in inventory.items()})
    # Replay the logged post-support-merge boundary. Re-merging that output would
    # not recreate the original per-obligation input and can change its mapping.
    namespace['_candidate_support_graph'] = lambda _: support_graph
    exec(compile(ast.Module(body=[fn], type_ignores=[]), '<saved-baseline-selector>', 'exec'), namespace)
    kwargs = dict(expanded_edges=pool['relationships'], input_char_budget=ledger['input_char_budget'])
    old = namespace['_select_mechanism_flows'](tuple(states.values()), **kwargs)
    with patch.object(flow, '_candidate_support_graph', return_value=support_graph):
        new = flow._select_mechanism_flows(tuple(states.values()), **kwargs)
    recorded = {cid for cid, item in inventory.items() if item['selected_for_final_request']}
    expected = old if recorded_policy == 'baseline' else new
    if set(expected[0]) != recorded or (recorded_policy == 'baseline' and expected[-1]['used_chars'] != ledger['used_chars']):
        differences = {item['candidate_id']: {k:(inventory[item['candidate_id']].get(k), v) for k,v in item.items()
                       if k not in {'selected_for_final_request', 'qualified_call_neighbor_ids'} and inventory[item['candidate_id']].get(k) != v}
                       for item in expected[-1]['candidate_inventory']}
        raise ValueError(f'Recorded replay mismatch: IDs {set(expected[0]) ^ recorded}; chars {expected[-1]["used_chars"]}/{ledger["used_chars"]}; inventory differences {dict((k,v) for k,v in differences.items() if v)}')
    def describe(ids):
        return [dict(candidate_id=cid, path=inventory[cid]['path'], symbol=inventory[cid]['symbol']) for cid in sorted(ids)]
    recorded_flows = [(r['flow_id'], r['candidate_ids']) for r in user['mechanism_flows']]
    replay_flows = [(r['flow_id'], r['candidate_ids']) for r in new[3]]
    if recorded_policy == 'current' and recorded_flows != replay_flows:
        raise ValueError('Recorded flow prefix differs; cannot isolate connection serialization')
    repaired_payload = {**user, 'candidate_connections': new[4]}
    connection_chars = sum(len(json.dumps(edge, sort_keys=True)) + 2 for edge in new[4])
    return dict(run_id=directory.name, baseline_ref=baseline_ref, trace_line=ledger_line,
        recorded_policy=recorded_policy, recorded_selected_ids_reproduced=True,
        recorded_chars=ledger['used_chars'], replay_chars_delta=expected[-1]['used_chars']-ledger['used_chars'],
        replay_precision_note='Trace scores are rounded. Total delta includes changed connection metadata; literal payload sizes below replace only the connections field.',
        recorded_flow_prefix_reproduced=recorded_flows == replay_flows,
        recorded_connection_count=len(user['candidate_connections']),
        replay_connection_count=len(new[4]), replay_connection_chars=connection_chars,
        preconnection_replay_chars=new[-1]['used_chars']-connection_chars,
        recorded_literal_payload_chars=len(json.dumps(user, sort_keys=True)),
        repaired_literal_payload_chars=len(json.dumps(repaired_payload, sort_keys=True)),
        replay_connections=new[4],
        old_count=len(old[0]), new_count=len(new[0]), old_chars=old[-1]['used_chars'], new_chars=new[-1]['used_chars'],
        added=describe(set(new[0])-set(old[0])), removed=describe(set(old[0])-set(new[0])),
        new_ledger=new[-1], note='Deterministic saved-input replay only; no final LLM result predicted.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dirs', nargs='+', type=Path)
    parser.add_argument('--baseline-ref', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--recorded-policy', choices=('baseline', 'current'), default='baseline')
    args = parser.parse_args()
    result = [replay(path, args.baseline_ref, args.recorded_policy) for path in args.run_dirs]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf8')
    print(json.dumps([{k:v for k,v in r.items() if k != 'new_ledger'} for r in result], indent=2))
