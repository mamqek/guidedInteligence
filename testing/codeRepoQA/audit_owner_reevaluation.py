"""Summarize exact live owner-election records; never executes a model."""
import argparse
from collections import Counter
import json
from pathlib import Path


def audit(root):
    events = [json.loads(line) for line in (root/'retrieval-trace.jsonl').read_text(encoding='utf-8').splitlines()]
    elections = [dict(row, round=e['payload']['round']) for e in events
                 if e['event_type'] == 'owner_reevaluation_audited' for row in e['payload']['elections']]
    opportunities = [row for row in elections if row['new_owner_competition'] or row['kind'] in ('replaced', 'merge')]
    summary = {'run': root.name, 'counts': dict(Counter(row['kind'] for row in elections)),
               'new_owner_competitions': sum(row['new_owner_competition'] for row in elections),
               'opportunities': opportunities,
               'tokens': sum(e['payload']['raw_response']['usage']['total_tokens'] for e in events
                             if e['event_type'] == 'llm_response_received')}
    summary['actions'] = [dict(round=e['payload'].get('round'), **{
        key: action.get(key) for key in ('id', 'type', 'path', 'root_observation_id',
                                        'source_observation_id', 'obligation_id', 'handoff_reason')})
        for e in events if e['event_type'] == 'controller_actions_selected'
        for action in e['payload']['actions']]
    summary['final_pool'] = [{key: c.get(key) for key in ('candidate_id', 'node_id', 'path', 'symbol', 'origin')}
        for e in events if e['event_type'] == 'final_candidate_pool_created'
        for c in e['payload']['candidates']]
    previous_groups = {}
    file_competitions = []
    file_totals = Counter()
    for e in events:
        if e['event_type'] != 'owner_reevaluation_audited':
            continue
        members = {c['id']: c for row in e['payload']['elections'] for c in row['candidates']}
        for group in e['payload'].get('primary_elections', []):
            key = (group['path'], group['obligation_id'])
            old = previous_groups.get(key)
            ids = {group['primary'], *group['complements']}
            file_totals['initial' if old is None else 'preserved' if old['primary'] == group['primary'] else 'replaced'] += 1
            new = ids - {old['primary'], *old['complements']} if old else set()
            if old and (new or old['primary'] != group['primary']):
                file_competitions.append(dict(group, round=e['payload']['round'],
                    previous=old['primary'], new=sorted(new), candidates=[members[oid] for oid in sorted(ids)]))
            previous_groups[key] = group
    summary['file_election_counts'] = dict(file_totals)
    summary['file_competitions'] = file_competitions
    if (root/'scorecard.json').exists():
        score = json.loads((root/'scorecard.json').read_text())
        result = json.loads((root/'orchestration-result.json').read_text())['retrieval_result']
        summary.update(overlap=score['overlap_count'], final_files=score['top_k']['found_positions'],
                       coverage=result['coverage_status'], sufficient=result['sufficient'])
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', action='append', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    reports = [audit(root) for root in args.run]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(reports, indent=2), encoding='utf-8')
    for r in reports:
        print(json.dumps({k: v for k, v in r.items() if k not in ('opportunities', 'actions', 'final_pool', 'file_competitions')}))
        for row in r['opportunities']:
            print('ROUND', row['round'], row['kind'], 'active', row['active'], 'WINNER', row['winner'])
            for c in row['candidates']:
                d = c['qualification']
                print(c['id'], c['handle']['path'], c['handle']['symbol'], c['ranking_key'],
                      d['support_level'], d['supported_obligation_ids'], d['reason'])


if __name__ == '__main__':
    main()
