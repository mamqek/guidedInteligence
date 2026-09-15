"""Deterministic fixed-island priority counterfactual, not a full pipeline run."""
import argparse
import json
from pathlib import Path
from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import DiscoveryObservation, DiscoveryProvenance, SourceHandle
from services.retrieval.workspace.pipeline.execution_flow.evidence_qualification import QualificationDecision
from testing.codeRepoQA.owner_election_variant import elect_owner_primaries


def replay(root):
    events = [json.loads(line) for line in (root/'retrieval-trace.jsonl').read_text().splitlines()]
    changes = []
    checked = 0
    for event in events:
        if event['event_type'] != 'owner_reevaluation_audited':
            continue
        rows = event['payload']['elections']
        candidates = {c['id']: c for row in rows for c in row['candidates']}
        observations = {}
        decisions = {}
        for oid, c in candidates.items():
            key = c['ranking_key']
            observations[oid] = DiscoveryObservation(oid, SourceHandle(**c['handle']), c['source_text'],
                (DiscoveryProvenance('saved', 'saved', ranks=(key[3],)),),
                exact_anchor_matches=('saved-anchor',) if key[0] == 0 else (), recurrence=-key[1])
            d = dict(c['qualification'])
            for field in ('visible_support', 'missing_information', 'supported_obligation_ids'):
                d[field] = tuple(d[field])
            decisions[oid] = QualificationDecision(**d)
        counts, elections = elect_owner_primaries(observations, decisions)
        for row in rows:
            checked += 1
            new = min(row['candidates'], key=lambda c: (-counts.get(c['id'], 0), *c['ranking_key']))['id']
            if new != row['winner']:
                changes.append({'round': event['payload']['round'], 'island_id': row['island_id'],
                    'old': row['winner'], 'new': new, 'counts': counts,
                    'old_symbol': candidates[row['winner']]['handle'], 'new_symbol': candidates[new]['handle']})
    return {'run': root.name, 'checked': checked, 'changes': changes}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run', type=Path, action='append', required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    result = [replay(root) for root in args.run]
    assert result == [replay(root) for root in args.run]
    args.output.write_text(json.dumps(result, indent=2))
    for r in result:
        print(r['run'], 'checked', r['checked'], 'changed', len(r['changes']))
        for c in r['changes']:
            print(c['round'], c['old_symbol']['symbol'], '->', c['new_symbol']['symbol'])


if __name__ == '__main__':
    main()
