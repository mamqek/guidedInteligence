"""Audit append-crossing boundaries in actual traces; no retrieval or LLM calls."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from testing.codeRepoQA.analyze_qualified_file_leads import analyze


def audit(directory: Path):
    rows = [(i, json.loads(line)) for i, line in enumerate(
        (directory / 'retrieval-trace.jsonl').read_text(encoding='utf8').splitlines(), 1)]
    def last(kind):
        return next(((i, row['payload']) for i, row in reversed(rows)
                     if row['event_type'] == kind), (None, {}))

    metrics = analyze(directory)
    result = {key: metrics[key] for key in ('run_id', 'coverage_status', 'sufficient',
        'implementation_oracles', 'final_items', 'final_files', 'retrieval_tokens', 'stages', 'indexes', 'final')}
    result['completed_result_exists'] = (directory / 'orchestration-result.json').exists()
    result['final_llm_responses'] = []
    admission_line, admission = last('initial_files_admitted')
    canonical_line, canonical = last('initial_snippets_canonicalized')
    comparison_line, comparison = last('initial_owner_comparison_created')
    cross = next((r for r in admission.get('path_decisions', []) if r.get('crossed_budget')), {})
    crossing_snippets = [s for s in canonical.get('output_snippets', [])
                         if s['handle']['path'] == cross.get('path')]
    dormant = comparison.get('dormant_owners', [])
    selected_ids = {identifier for identifiers in comparison.get('selected_by_group', {}).values()
                    for identifier in identifiers}
    result['initial'] = dict(trace_line=admission_line, canonical_line=canonical_line,
        comparison_line=comparison_line,
        **{key: admission.get(key) for key in ('admission_limit', 'admitted_file_count',
            'participating_candidate_count', 'comparison_total_input_chars', 'admitted_paths',
            'comparison_preferred_input_chars', 'comparison_input_char_budget', 'stopping_reason')},
        crossing=cross,
        crossing_snippets=[dict(id=s['id'], **s['handle']) for s in crossing_snippets],
        crossing_selected=[dict(id=s['id'], **s['handle']) for s in crossing_snippets
                           if s['id'] in selected_ids],
        comparison_selected_groups=comparison.get('selected_by_group', {}),
        crossing_dormant=[s for s in dormant if s.get('path') == cross.get('path')])
    ledger_line, ledger = last('mechanism_flow_decision_ledger')
    budget_line, budget = last('mechanism_flow_request_budget')
    selected = [r for r in ledger.get('flow_decisions', []) if r['decision'] == 'selected']
    flow_crossings = [r for r in selected if r.get('crossed_budget')]
    inventory = {r['candidate_id']: r for r in ledger.get('candidate_inventory', [])}
    seen = set()
    for row in selected:
        new_ids = set(row['candidate_ids']) - seen
        if row in flow_crossings:
            row['new_snippets'] = [inventory[i] for i in sorted(new_ids)]
        seen.update(row['candidate_ids'])
    result['final_admission'] = dict(trace_line=ledger_line, budget_line=budget_line,
        budget=budget, selected_flow_count=len(selected), crossing_flows=flow_crossings,
        **{key: ledger.get(key) for key in ('budget_policy', 'used_chars', 'input_char_budget',
            'budget_overshoot_chars', 'eligible_connection_count', 'selected_connection_count',
            'budget_excluded_connection_count')},
        stopped_flow_count=sum(r['decision'] == 'rejected_after_input_budget_crossing'
                               for r in ledger.get('flow_decisions', [])))
    for line, row in rows:
        p = row['payload']
        if row['event_type'] == 'llm_response_received' and p.get('stage') == 'obligation_evidence_consolidation':
            raw = p['raw_response']
            result['final_llm_responses'].append(dict(trace_line=line, usage=raw.get('usage', {}),
                choices=[dict(finish_reason=c.get('finish_reason'),
                              content_chars=len(c.get('message', {}).get('content') or ''))
                         for c in raw.get('choices', [])]))
        if row['event_type'] == 'llm_request_sent' and p.get('stage') == 'obligation_evidence_consolidation':
            request = p['request_payload']
            result['final_admission']['llm_request'] = dict(trace_line=line,
                message_chars=sum(len(m['content']) for m in request['messages']),
                schema_chars=len(json.dumps(request.get('response_format', {}), sort_keys=True)))
    # These assertions check policy, not evidence quality or stochastic selections.
    if cross:
        assert cross['path'] == admission['admitted_paths'][-1]
        assert cross['total_input_chars'] == admission['comparison_total_input_chars']
        assert len([r for r in admission['path_decisions'] if r.get('crossed_budget')]) == 1
    if flow_crossings:
        assert len(flow_crossings) == 1 and flow_crossings[0] is selected[-1]
        assert set(flow_crossings[0]['candidate_ids']).issubset(seen)
        assert flow_crossings[0]['previous_used_chars'] <= ledger['input_char_budget']
    result['policy_assertions_passed'] = True
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dirs', nargs='+', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    results = [audit(directory) for directory in args.run_dirs]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + '\n', encoding='utf8')
    for row in results:
        print(json.dumps({key: row[key] for key in ('run_id', 'coverage_status', 'sufficient',
            'implementation_oracles', 'retrieval_tokens', 'policy_assertions_passed')}))
