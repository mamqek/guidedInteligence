"""Audit saved controller islands and exact candidate serialization; no LLM or runtime changes."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from services.retrieval.workspace.bm25 import file_role
from services.retrieval.workspace.pipeline.execution_flow.obligation_retrieval import MAX_CONSOLIDATION_SNIPPET_CHARS


def audit(directory):
    texts, handles, decisions, source_lines = {}, {}, {}, {}
    pool = ledger = request = None
    for line, raw in enumerate((directory / 'retrieval-trace.jsonl').open(encoding='utf8'), 1):
        event = json.loads(raw)
        kind, p = event['event_type'], event['payload']
        if kind == 'llm_request_sent':
            stage = p.get('stage')
            if stage in {'evidence_qualification', 'obligation_evidence_consolidation'}:
                data = json.loads(next(m['content'] for m in p['request_payload']['messages'] if m['role'] == 'user'))
                if stage == 'evidence_qualification':
                    for card in data['observations']:
                        texts[card['observation_id']] = card['source_text']
                        source_lines[card['observation_id']] = line
                else:
                    request = data
        elif kind == 'disclosure_cards_created':
            handles.update({c['observation_id']: c['handle'] for c in p['cards']})
        elif kind == 'qualification_decisions_created':
            decisions.update({d['observation_id']: d for d in p['decisions']})
        elif kind == 'qualification_reuse_evaluated' and p['reused']:
            decisions[p['observation_id']] = p['decision']
        elif kind == 'final_candidate_pool_created':
            pool, pool_line = p, line
        elif kind == 'mechanism_flow_decision_ledger':
            ledger, ledger_line = p, line
    if pool is None or ledger is None or request is None:
        return dict(run_id=directory.name, error='no_completed_final_input')
    by_candidate = {}
    for oid, h in handles.items():
        cid = f"node:{h['node_id']}" if h.get('node_id') else f"range:{h['path']}:{h['line_start']}:{h['line_end']}"
        by_candidate[cid] = oid
    inventory = {c['candidate_id']: c for c in ledger['candidate_inventory']}
    actual = {c['candidate_id']: c for c in request['candidates']}
    island_by_observation = {oid: i['id'] for i in pool['islands'] for oid in i['observation_ids']}
    members, unmatched = {}, []
    for c in pool['candidates']:
        cid = c['candidate_id']
        oid = by_candidate.get(cid)
        if not oid or oid not in island_by_observation:
            unmatched.append(dict(candidate_id=cid, path=c['path'], symbol=c['symbol'], reason='no_disclosed_island_member'))
            continue
        source = texts[oid]
        if len(source) != c['text_chars']:
            raise ValueError(f"{directory.name}/{cid}: source reconstruction mismatch")
        island = island_by_observation[oid]
        inv = inventory.get(cid)
        rendered = None
        if inv:
            rendered = dict(candidate_id=cid, path=c['path'], line_start=c['line_start'], line_end=c['line_end'],
                symbol=c['symbol'], file_role=file_role(c['path']), retrieval_origin=c['origin'],
                discovery_island_id=island, semantic_score=round(inv['score'], 4),
                direct_obligation_ids=sorted(inv['direct_obligation_ids']),
                inherited_obligation_ids=sorted(inv['inherited_obligation_ids']),
                covered_concepts=inv['covered_concepts'], source_paths=inv['source_paths'],
                relationship_types=inv['relationship_types'], facts=inv['facts'],
                snippet=source[:MAX_CONSOLIDATION_SNIPPET_CHARS])
            if cid in actual and rendered != actual[cid]:
                raise ValueError(f"{directory.name}/{cid}: literal final candidate differs: "
                    f"{[(k,rendered[k],actual[cid].get(k)) for k in rendered if rendered[k] != actual[cid].get(k)]}")
        members.setdefault(island, []).append(dict(candidate_id=cid, observation_id=oid,
            path=c['path'], symbol=c['symbol'], support=decisions[oid]['support_level'],
            source_chars=len(source), final_capped_source_chars=len(source[:MAX_CONSOLIDATION_SNIPPET_CHARS]),
            source_trace_line=source_lines[oid], in_flow_inventory=bool(inv), in_final_input=cid in actual,
            candidate_payload=rendered))
    rows = []
    for island in pool['islands']:
        values = members.get(island['id'], [])
        counts = Counter(v['support'] for v in values)
        payloads = [v['candidate_payload'] for v in values if v['candidate_payload'] is not None]
        rows.append(dict(island_id=island['id'], files=island['normalized_files'],
            promoted_observation_count=len(island['observation_ids']), final_pool_count=len(values),
            direct=counts['direct_evidence'], navigation=counts['navigation_only'],
            source_chars=sum(v['source_chars'] for v in values),
            capped_source_chars=sum(v['final_capped_source_chars'] for v in values),
            candidate_array_chars=len(json.dumps(payloads, sort_keys=True)),
            serializable_flow_candidates=len(payloads),
            direct_missing_final=[v['symbol'] for v in values if v['support']=='direct_evidence' and not v['in_final_input']],
            members=[{k:v for k,v in item.items() if k!='candidate_payload'} for item in values]))
    rows.sort(key=lambda r: (-r['direct'], -r['final_pool_count'], r['island_id']))
    return dict(run_id=directory.name, trace_pool_line=pool_line, trace_ledger_line=ledger_line,
        pool_candidates=pool['candidate_count'], island_count=len(rows),
        total_direct=sum(r['direct'] for r in rows), top_two_direct=sum(r['direct'] for r in rows[:2]),
        top_two_source_chars=sum(r['source_chars'] for r in rows[:2]),
        top_two_candidate_arrays_chars=sum(r['candidate_array_chars'] for r in rows[:2]),
        more_than_three_direct_islands=sum(r['direct']>3 for r in rows),
        direct_majority_islands=sum(r['direct']>r['navigation'] for r in rows),
        actual_final_input_chars=len(json.dumps(request, sort_keys=True)),
        cost_scope='Candidate arrays use the current final schema and source cap; excludes prompt/schema/flows/connections. Not an island-policy LLM input.',
        unmatched=unmatched, islands=rows)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('runs', type=Path, nargs='+')
    parser.add_argument('--output', type=Path, required=True)
    args=parser.parse_args()
    results=[audit(p) for p in args.runs]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results,indent=2)+'\n',encoding='utf8')
    for r in results:
        print(json.dumps({k:v for k,v in r.items() if k not in {'islands','unmatched','cost_scope'}}))
