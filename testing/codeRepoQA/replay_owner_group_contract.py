"""Replay a literal saved comparison: change only group path metadata and selection contract."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from services.llm.json_completion import complete_json
from services.retrieval.workspace.pipeline.execution_flow.initial_owner_comparison import (
    _global_response_format, _validate_global_response, _prompt_text,
)
from testing.codeRepoQA.run_case import _load_project_llm_config


def run(source, output):
    events = [json.loads(line) for line in source.read_text(encoding='utf8').splitlines()]
    original = next(e['payload']['request_payload'] for e in events if e['event_type']=='llm_request_sent')
    payload = json.loads(next(m['content'] for m in original['messages'] if m['role']=='user'))
    for group in payload['groups']:
        paths = {payload['views'][v]['p'] for oid in group['owners'] for v in payload['owners'][oid]['v']}
        assert len(paths)==1, paths
        group['path'] = paths.pop()
    expected = {g['id']: tuple(g['owners']) for g in payload['groups']}
    schema = _global_response_format(expected, max_selected=24)
    messages = ({'role':'system','content':_prompt_text(max_selected=24)},
                {'role':'user','content':json.dumps(payload,sort_keys=True)})
    config = replace(_load_project_llm_config({}), model=original['model'])
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf8') as log:
        def record(kind, data):
            log.write(json.dumps({'event_type':kind,'payload':data})+'\n'); log.flush()
        record('contract_replay_started', {'source':str(source), 'candidate_count':len(payload['owners']),
            'group_count':len(expected), 'source_views_unchanged':True,
            'old_input_chars':sum(len(m['content']) for m in original['messages'])+len(json.dumps(original['response_format'],sort_keys=True)),
            'new_input_chars':sum(len(m['content']) for m in messages)+len(json.dumps(schema,sort_keys=True))})
        try:
            result=complete_json(config,messages,response_format=schema,log_event=record)
            selected=_validate_global_response(result,expected,max_selected=24)
            record('contract_replay_validated',{'selected':selected,'selected_count':sum(map(len,selected.values()))})
            print(json.dumps({'output':str(output),'selected_count':sum(map(len,selected.values()))}),flush=True)
        except Exception as exc:
            record('contract_replay_failed',{'error':str(exc)})
            raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();run(args.source,args.output)
