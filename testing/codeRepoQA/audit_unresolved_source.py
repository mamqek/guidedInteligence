"""Summarize recorded visibility boundaries; does not execute retrieval."""
import argparse
import json
from pathlib import Path


def audit(folder: Path) -> dict:
    events = [json.loads(line) for line in (folder / 'retrieval-trace.jsonl').read_text().splitlines()]
    by_kind = lambda kind: [event['payload'] for event in events if event['event_type'] == kind]
    requests = [p for p in by_kind('llm_request_sent') if p.get('stage') == 'initial_owner_comparison']
    comparison = json.loads(requests[0]['request_payload']['messages'][-1]['content']) if requests else {}
    canonical = by_kind('initial_snippets_canonicalized')
    rows = {r['id']: r for r in canonical[0]['output_snippets']} if canonical else {}
    selected = by_kind('initial_owner_comparison_created')
    selected_ids = [i for ids in selected[0]['selected_by_group'].values() for i in ids] if selected else []
    target = 'test/unit/features/options/props.spec.js'
    report = {
        'run': folder.name,
        'tokens': sum(p['raw_response']['usage']['total_tokens'] for p in by_kind('llm_response_received')),
        'stage_tokens': {},
        'source_repairs': [r for p in by_kind('owner_comparison_source_prepared') for r in p['rows']
                           if r['reason'] == 'hidden_request_name_restored'],
        'comparison_budget': by_kind('initial_owner_comparison_prepared'),
        'admitted_files': [g['path'] for g in comparison.get('groups', [])],
        'admitted_owner_count': len(comparison.get('owners', {})),
        'selected': [dict(id=i, handle=rows[i]['handle']) for i in selected_ids if i in rows],
        'target_views': [v for v in comparison.get('views', {}).values() if v['p'] == target],
        'target_raw': [dict(obligation=p['obligation_id'], channel=channel, result=r)
                       for p in by_kind('initial_query_channel_results')
                       for channel in ('dense_results', 'sparse_results', 'hybrid_results')
                       for r in p[channel] if r.get('path') == target],
        'target_canonical': [dict(id=i, handle=r['handle'], provenance=r['provenance'])
                             for i, r in rows.items() if r['handle']['path'] == target],
        'target_resolution': [r for p in by_kind('initial_codegraph_ranges_resolved')
                              for r in p['ranges'] if r.get('path') == target],
        'target_actions': [p for p in by_kind('controller_action_executed')
                           if target in json.dumps(p)],
        'target_qualification': [d for p in by_kind('qualification_decisions_created') for d in p['decisions']
                                 if rows.get(d['observation_id'], {}).get('handle', {}).get('path') == target],
        'final_pool_files': [p['files'] for p in by_kind('final_candidate_pool_created')],
        'target_final': [p for p in by_kind('evidence_selected') if target in json.dumps(p)],
    }
    for p in by_kind('llm_response_received'):
        stage = p.get('stage', 'unspecified')
        report['stage_tokens'][stage] = report['stage_tokens'].get(stage, 0) + p['raw_response']['usage']['total_tokens']
    if (folder / 'scorecard.json').exists():
        report['scorecard'] = json.loads((folder / 'scorecard.json').read_text())
        result = json.loads((folder / 'orchestration-result.json').read_text())['retrieval_result']
        report.update(coverage_status=result['coverage_status'], sufficient=result['sufficient'])
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    reports = [audit(folder) for folder in args.run]
    args.output.write_text(json.dumps(reports, indent=2), encoding='utf-8')
    for r in reports:
        print(r['run'], r.get('scorecard', {}).get('overlap_count'), r['tokens'],
              r['admitted_owner_count'], r.get('coverage_status'), r.get('sufficient'))


if __name__ == '__main__':
    main()
