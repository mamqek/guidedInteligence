"""Summarize measured lead lifecycle and stage usage with trace line references."""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def analyze(directory: Path):
    entries = [(line, json.loads(text)) for line, text in enumerate(
        (directory / 'retrieval-trace.jsonl').read_text(encoding='utf-8').splitlines(), 1) if text.strip()]
    stages = defaultdict(lambda: dict(calls=0, prompt_tokens=0, completion_tokens=0, total_tokens=0))
    observations, decisions, leads, actions, audits, stops = {}, defaultdict(list), [], [], [], []
    schedules, followups, indexes = [], [], []
    for line, event in entries:
        kind, payload = event['event_type'], event['payload']
        if kind == 'llm_response_received':
            stats = stages[payload.get('stage', 'unknown')]
            stats['calls'] += 1
            for key in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
                stats[key] += payload.get('raw_response', {}).get('usage', {}).get(key, 0)
        elif kind == 'disclosure_cards_created':
            for card in payload['cards']:
                observations[card['observation_id']] = card
        elif kind == 'qualification_decisions_created':
            for decision in payload['decisions']:
                decisions[decision['observation_id']].append(dict(trace_line=line, round=payload['round'], **decision))
        elif kind == 'qualified_structural_file_leads_evaluated':
            leads.extend(dict(discovery_line=line,
                source_handle=observations.get(lead['source_observation_id'], {}).get('handle'),
                **lead) for lead in payload['leads'])
            audits.append(dict(trace_line=line, **payload))
        elif kind == 'verified_leads_evaluated':
            followups.extend(dict(discovery_line=line,
                source_handle=observations.get(lead['source_observation_id'], {}).get('handle'),
                **lead) for lead in payload.get('pending_leads', ()))
        elif kind == 'verified_lead_scheduling':
            pending = payload['ranked_pending']
            previous = sorted(pending, key=lambda item: (
                not item['structural_child'], not item['qualified_target'], item['discovered_round'],
                item['source_rank'], item['target_path'].casefold(), item['target_node_id']))
            schedules.append(dict(trace_line=line, **payload,
                previous_priority_first_node=previous[0]['target_node_id'] if previous else None,
                note='Previous ordering on this same pending queue only; not a counterfactual full run.'))
        elif kind == 'workspace_index_ready':
            indexes.append(dict(trace_line=line, **payload))
        elif kind == 'controller_actions_selected':
            actions.extend(dict(trace_line=line, round=payload['round'], **action) for action in payload['actions'])
        elif kind == 'retrieval_controller_stopped':
            stops.append(dict(trace_line=line, **payload))
    evidence = json.loads((directory / 'evidence-items.json').read_text(encoding='utf-8')) if (directory / 'evidence-items.json').exists() else []
    result = json.loads((directory / 'orchestration-result.json').read_text(encoding='utf-8')) if (directory / 'orchestration-result.json').exists() else {}
    score = json.loads((directory / 'scorecard.json').read_text(encoding='utf-8')) if (directory / 'scorecard.json').exists() else {}
    for lead in [*leads, *followups]:
        target = lead['target_node_id']
        lead['actions'] = [action for action in actions if action.get('target_node_id') == target]
        target_ids = [identifier for identifier, card in observations.items() if card['handle'].get('node_id') == target]
        lead['qualification'] = [value for identifier in target_ids for value in decisions[identifier]]
        lead['final_ranks'] = [item['rank'] for item in evidence if item.get('metadata', {}).get('path') == lead['target_path']
                               and item.get('metadata', {}).get('symbol') == lead['target_symbol']]
    return dict(run_id=directory.name, coverage_status=result.get('retrieval_result', {}).get('coverage_status'),
        sufficient=result.get('retrieval_result', {}).get('sufficient'),
        implementation_oracles=score.get('implementation_overlap_count'), oracle_positions=score.get('top_k', {}).get('found_positions'),
        final_items=len(evidence), final_files=len({item.get('metadata', {}).get('path') for item in evidence}),
        retrieval_tokens=sum(value['total_tokens'] for value in stages.values()), stages=dict(stages),
        leads=leads, followups=followups, scheduling=schedules, indexes=indexes, discovery_audits=audits, controller=stops,
        final=[dict(rank=item['rank'], **{k: item.get('metadata', {}).get(k) for k in ('path','symbol','obligation_id')}) for item in evidence])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dirs', nargs='+', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--replay-priority', action='store_true', help='Replay recorded pending queues; no retrieval or LLM.')
    args = parser.parse_args()
    output = json.dumps([replay_priority(path) if args.replay_priority else analyze(path) for path in args.run_dirs], indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + '\n', encoding='utf-8')
    else:
        print(output)


def replay_priority(directory: Path):
    from services.retrieval.workspace.pipeline.execution_flow.verified_leads import (
        VerifiedLead, _select_verified_lead_actions, _inspection_request, _verified_lead_to_dict,
    )
    from services.retrieval.workspace.pipeline.execution_flow.evidence_qualification import QualificationDecision
    from dataclasses import fields
    allowed = {field.name for field in fields(QualificationDecision)}
    ranks, cards, decisions, coverage, comparisons = {}, {}, {}, [], []
    for line, text in enumerate((directory / 'retrieval-trace.jsonl').read_text(encoding='utf-8').splitlines(), 1):
        event = json.loads(text)
        kind, payload = event['event_type'], event['payload']
        if kind == 'discovery_observations_created':
            ranks.update({item['id']: item['best_rank'] for item in payload['raw_observations']})
        elif kind == 'llm_request_sent' and payload.get('stage') == 'evidence_qualification':
            prompt = json.loads(next(item['content'] for item in payload['request_payload']['messages'] if item['role'] == 'user'))
            cards.update({item['observation_id']: item for item in prompt['observations']})
        elif kind == 'qualification_decisions_created':
            decisions.update({item['observation_id']: QualificationDecision(**{k: v for k, v in item.items() if k in allowed})
                              for item in payload['decisions']})
        elif kind == 'coverage_evaluated':
            coverage = payload['coverage']
        elif kind == 'verified_leads_evaluated' and payload.get('pending_leads'):
            leads = []
            for item in payload['pending_leads']:
                identifier = item['source_observation_id']
                if identifier not in ranks:
                    # Do not invent a missing retrieval rank for exact-order replay.
                    break
                origin = item.get('origin', 'qualification_followup')
                basis, request = 'qualification_followup', item['reason']
                if origin == 'qualified_structural_file_lead':
                    decision = decisions[identifier]
                    basis, request = _inspection_request(item['target'], decision,
                        [row['missing_claim'] for row in coverage if row['obligation_id'] in decision.supported_obligation_ids],
                        cards[identifier]['source_text'])
                leads.append(VerifiedLead(identifier, item['obligation_id'], item['target'], item['target_node_id'],
                    item['target_path'], *item['target_range'], item['target_symbol'], item['reason'],
                    item['discovered_round'], ranks[identifier], '.' in item['target'] or '::' in item['target'],
                    structural_child=item['structural_child'], origin=origin, inspection_basis=basis, request_text=request))
            else:
                old = sorted(leads, key=lambda v: (not v.structural_child, not v.qualified_target, v.discovered_round,
                                                   v.source_rank, v.target_path.casefold(), v.target_node_id))
                chosen = _select_verified_lead_actions(leads, executed_count=payload['executed_count'], observation_to_island={})
                comparisons.append(dict(trace_line=line, round_completed=payload['round'], executed_count=payload['executed_count'],
                    old_first=old[0].target if payload['executed_count'] < 2 else None,
                    new_first=chosen[0].target if chosen else None, queue=[_verified_lead_to_dict(v) for v in leads]))
                continue
            comparisons.append(dict(trace_line=line, skipped='source rank not recorded; no inferred tie-breaker'))
    return dict(run_id=directory.name, queue_comparisons=comparisons,
                note='Same recorded queue replay only, before later discoveries/suppression. Not a full-run quality prediction.')


if __name__ == '__main__':
    main()
