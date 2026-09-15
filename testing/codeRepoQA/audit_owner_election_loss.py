"""Audit target paths through saved boundaries; no retrieval or model execution."""
import argparse
import json
from pathlib import Path


def audit(root, target):
    events = [json.loads(line) for line in (root/'retrieval-trace.jsonl').read_text().splitlines()]
    payloads = lambda kind: [e['payload'] for e in events if e['event_type'] == kind]
    canonical = {c['id']: c for p in payloads('initial_snippets_canonicalized') for c in p['output_snippets']}
    initial = [c for c in canonical.values() if c['handle']['path'] == target]
    selected = [oid for p in payloads('initial_owner_comparison_created')
                for ids in p['selected_by_group'].values() for oid in ids
                if canonical.get(oid, {}).get('handle', {}).get('path') == target]
    requests = [p for p in payloads('llm_request_sent') if p.get('stage') == 'initial_owner_comparison']
    comparison = json.loads(requests[0]['request_payload']['messages'][-1]['content']) if requests else {}
    qualifications = [dict(round=p['round'], **c) for p in payloads('owner_reevaluation_audited')
                      for row in p['elections'] for c in row['candidates'] if c['handle']['path'] == target]
    actions = [dict(round=p.get('round'), **a) for p in payloads('controller_actions_selected')
               for a in p['actions'] if target in json.dumps(a)]
    return {'run': root.name, 'target': target,
        'raw': {channel: sum(r.get('path') == target for p in payloads('initial_query_channel_results')
                            for r in p[channel]) for channel in ('dense_results', 'sparse_results', 'hybrid_results')},
        'canonical': [dict(id=c['id'], handle=c['handle']) for c in initial],
        'admitted': [g for g in comparison.get('groups', []) if g['path'].casefold() == target.casefold()],
        'initial_selected_ids': selected,
        'qualification_decisions': [dict(round=p.get('round'), **d)
            for p in payloads('qualification_decisions_created') for d in p['decisions']
            if canonical.get(d['observation_id'], {}).get('handle', {}).get('path') == target],
        'promoted_history': [dict(id=c['id'], round=c['round'], handle=c['handle'], qualification=c['qualification']) for c in qualifications],
        'selected_actions': actions,
        'final_pool': [c for p in payloads('final_candidate_pool_created') for c in p['candidates'] if c['path'] == target]}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--path', action='append', required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    results = [audit(args.run, path) for path in args.path]
    args.output.write_text(json.dumps(results, indent=2))
    for r in results:
        print(r['target'], r['raw'], 'canonical', len(r['canonical']), 'admitted', len(r['admitted']),
              'selected', r['initial_selected_ids'], 'promoted', len(r['promoted_history']),
              'actions', len(r['selected_actions']), 'pool', len(r['final_pool']))


if __name__ == '__main__':
    main()
