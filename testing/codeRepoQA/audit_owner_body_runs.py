"""Join body-card preparation, admission, semantic qualification and final selections in real traces."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from testing.codeRepoQA.analyze_qualified_file_leads import analyze


def audit(directory):
    result=analyze(directory)
    decisions,handles,rows,raw_paths={},{},{},Counter()
    selected=set()
    line_refs={}
    admission={}
    initial_done=False
    for line,raw in enumerate((directory/'retrieval-trace.jsonl').open(encoding='utf8'),1):
        e=json.loads(raw);p=e['payload'];kind=e['event_type']
        if kind=='initial_snippets_canonicalized':initial_done=True
        if not initial_done and kind=='tool_observation_created' and p.get('tool_name')=='qdrant_hybrid_search':
            for channel,values in p.get('payload',{}).get('breakdown',{}).items():
                for v in values:
                    if isinstance(v,dict) and v.get('path'):raw_paths[(v['path'].casefold(),channel)]+=1
        if kind in {'initial_codegraph_ranges_resolved','initial_snippets_canonicalized','owner_comparison_source_prepared',
                    'initial_files_admitted','initial_owner_comparison_created','final_candidate_pool_created','mechanism_flow_decision_ledger'}:
            line_refs[kind]=line
        if kind=='owner_comparison_source_prepared':rows={r['observation_id']:r for r in p['rows']}
        elif kind=='initial_files_admitted':admission=p
        elif kind=='initial_owner_comparison_created':selected={oid for ids in p['selected_by_group'].values() for oid in ids}
        elif kind=='disclosure_cards_created':handles.update({c['observation_id']:c['handle'] for c in p['cards']})
        elif kind=='qualification_decisions_created':
            decisions.update({d['observation_id']:dict(trace_line=line,round=p['round'],**d) for d in p['decisions']})
        elif kind=='qualification_reuse_evaluated' and p['reused']:
            decisions[p['observation_id']]=dict(trace_line=line,round=p['round'],**p['decision'])
    final={(r['path'],r['symbol']):r['rank'] for r in result['final']}
    for oid,r in rows.items():
        r['selected_by_comparison']=oid in selected
        r['last_qualification']=decisions.get(oid)
        r['final_rank']=final.get((r['path'],r['symbol']))
    result.update(trace_lines=line_refs,admission=admission,preparation_counts=dict(Counter(r['reason'] for r in rows.values())),
        prepared_selected=sum(r['reason']=='owner_source_prepared' and oid in selected for oid,r in rows.items()),
        prepared_selected_previously_bodyless=[r for oid,r in rows.items() if oid in selected and r['reason']=='owner_source_prepared' and not r['old_body_visible']],
        file_boundaries=[dict(path=r['path'],canonical_count=r['canonical_snippet_count'],best_rank=r['best_rank'],
            dense_hits=raw_paths[(r['path'].casefold(),'dense')],sparse_hits=raw_paths[(r['path'].casefold(),'sparse')],
            admitted=r['path'] in admission['admitted_paths'],
            comparison_selected=[v['symbol'] for v in rows.values() if v['path']==r['path'] and v['selected_by_comparison']],
            qualified=[dict(symbol=h.get('symbol'),decision=decisions[oid]) for oid,h in handles.items() if h['path']==r['path'] and oid in decisions],
            final=[v for v in result['final'] if v['path']==r['path']]) for r in admission['ranking']])
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('runs',nargs='+',type=Path);p.add_argument('--output',required=True,type=Path)
    args=p.parse_args();results=[audit(d) for d in args.runs]
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(results,indent=2)+'\n',encoding='utf8')
    for r in results:
        print(json.dumps({k:r[k] for k in ['run_id','coverage_status','sufficient','implementation_oracles','retrieval_tokens','prepared_selected','trace_lines']}))
        print(json.dumps([(v['symbol'],v['last_qualification']['support_level'] if v['last_qualification'] else None,v['final_rank']) for v in r['prepared_selected_previously_bodyless']]))
