"""Real selector replay with a fixed saved admitted pool; not a full run."""
import argparse
import copy
import json
from pathlib import Path
from services.llm.json_completion import complete_json
from testing.codeRepoQA.unresolved_source_variant import render_unresolved_source
from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import RetrievedSourceView
from services.retrieval.workspace.pipeline.execution_flow.initial_owner_comparison import _validate_global_response
from testing.codeRepoQA.run_case import _load_project_llm_config


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--run',type=Path,required=True)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    events=[json.loads(x) for x in (args.run/'retrieval-trace.jsonl').read_text().splitlines()]
    request=copy.deepcopy(next(e['payload']['request_payload'] for e in events
        if e['event_type']=='llm_request_sent' and e['payload'].get('stage')=='initial_owner_comparison'))
    payload=json.loads(request['messages'][-1]['content'])
    rows=next(e['payload']['output_snippets'] for e in events if e['event_type']=='initial_snippets_canonicalized')
    unresolved={}
    for row in rows:
        h=row['handle']
        if not h['node_id']:
            unresolved[(h['path'],h['line_start'],h['line_end'])]=tuple(
                t for provenance in row['provenance'] for t in provenance['matched_terms'])
    changed=[]
    old_chars=len(request['messages'][-1]['content'])
    for vid,view in payload['views'].items():
        key=(view['p'],*view['r'])
        if key not in unresolved:
            continue
        path=(args.root/view['p']).resolve()
        if not path.is_relative_to(args.root.resolve()):
            raise ValueError('outside snapshot')
        lines=path.read_text(encoding='utf-8').splitlines()
        source='\n'.join(lines[view['r'][0]-1:view['r'][1]])
        view['x']=render_unresolved_source(RetrievedSourceView(view['p'],*view['r'],source),
                                          matched_terms=unresolved[key],max_chars=1024)
        changed.append(vid)
    request['messages'][-1]['content']=json.dumps(payload,sort_keys=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    events_out=[]
    def log(kind,data):
        events_out.append({'event_type':kind,'payload':data})
        args.output.with_suffix('.trace.json').write_text(json.dumps(events_out),encoding='utf-8')
    config=_load_project_llm_config(json.loads(Path('configs/testing/workspace.json').read_text()))
    response=complete_json(config,request['messages'],response_format=request['response_format'],log_event=log)
    selected=_validate_global_response(response,{g['id']:tuple(g['owners']) for g in payload['groups']},max_selected=24)
    report={'source_run':args.run.name,'fixed_pool_diagnostic':True,'changed_views':changed,
            'before_payload_chars':old_chars,'after_payload_chars':len(request['messages'][-1]['content']),
            'selected':selected,'selected_files':[g['path'] for g in payload['groups'] if g['id'] in selected],
            'tokens':sum(e['payload']['raw_response']['usage']['total_tokens'] for e in events_out if e['event_type']=='llm_response_received')}
    args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__':
    main()
