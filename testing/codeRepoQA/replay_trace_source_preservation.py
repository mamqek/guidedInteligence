"""Replay deterministic final preservation from recorded real candidate pools."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace as NS

from services.retrieval.workspace.pipeline.execution_flow.qualification_first_retrieval import (
    _candidate_island_ids, _preserve_active_island_candidates,
)


def replay(directory):
    directory = Path(directory)
    events = [json.loads(line) for line in (directory / 'retrieval-trace.jsonl').read_text(encoding='utf-8').splitlines()]
    pool = [e['payload'] for e in events if e['event_type'] == 'final_candidate_pool_created'][-1]
    state = [e['payload'] for e in events if e['event_type'] == 'semantic_islands_created'][-1]
    observations = {}

    def visit(value):
        if isinstance(value, dict):
            if str(value.get('id', '')).startswith('obs_') and isinstance(value.get('handle'), dict):
                observations[value['id']] = NS(id=value['id'], handle=NS(**value['handle']))
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(events)
    candidates = {row['candidate_id']: NS(**row) for row in pool['candidates']}
    controller = NS(observations=list(observations.values()), islands=NS(
        active_root_ids=state['active_root_ids'], islands=[NS(**row) for row in pool['islands']]))
    mapping = _candidate_island_ids(candidates, controller)
    saved = json.loads((directory / 'orchestration-result.json').read_text(encoding='utf-8'))['retrieval_result']['retrieval_summary']['evidence_consolidation']
    added = set(saved.get('preserved_active_island_candidate_ids', []) + saved.get('preserved_file_trace_source_candidate_ids', []))
    initial = {**saved, 'accepted_candidate_ids': [cid for cid in saved['accepted_candidate_ids'] if cid not in added]}
    traces = [trace for e in events if e['event_type'] == 'file_trace_evidence_created' for trace in e['payload']['traces']]
    result = _preserve_active_island_candidates(initial, candidates, mapping, controller, file_traces=traces)
    return {'run': directory.name, 'mapped': len(mapping), 'pool': len(candidates),
            'initial_count': len(initial['accepted_candidate_ids']),
            'matches_saved': result['accepted_candidate_ids'] == saved['accepted_candidate_ids'],
            'added': [{'id': cid, 'path': candidates[cid].path, 'symbol': candidates[cid].symbol}
                      for cid in result['accepted_candidate_ids'] if cid not in saved['accepted_candidate_ids']],
            'removed': [cid for cid in saved['accepted_candidate_ids'] if cid not in result['accepted_candidate_ids']],
            'trace_sources': result['preserved_file_trace_source_candidate_ids']}


if __name__ == '__main__':
    for directory in sys.argv[1:]:
        print(json.dumps(replay(directory)))
