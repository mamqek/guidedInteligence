"""Replay canonical Qdrant inputs through owner cards/admission and optionally real comparison."""
import argparse
from dataclasses import fields, replace, asdict
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from services.retrieval.workspace.pipeline.execution_flow import initial_owner_comparison as comparison
from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import DiscoveryObservation, DiscoveryProvenance, RetrievedSourceView, SourceHandle, _owner_aligned_result_text
from services.retrieval.workspace.pipeline.execution_flow.owner_comparison_source import prepare_owner_sources
from services.retrieval.workspace.source_ast.router import SourceAstRouter
from services.retrieval.workspace.tools.codegraph import CodeGraphBridge
from testing.codeRepoQA.run_case import _load_project_llm_config


def load_saved(directory):
    events=[json.loads(line) for line in (directory/'retrieval-trace.jsonl').open(encoding='utf8')]
    raw={}
    def collect(value):
        if isinstance(value,list):
            for item in value: collect(item)
        elif isinstance(value,dict):
            if all(k in value for k in ('path','line_start','line_end','text')):
                raw[(value['path'],value['line_start'],value['line_end'])]=value['text']
            for item in value.values():
                if isinstance(item,(list,dict)): collect(item)
    for event in events:
        if event['event_type']=='initial_snippets_canonicalized':
            canonical=event['payload']['output_snippets']
            break
        if event['event_type']=='tool_observation_created': collect(event['payload'])
    request=next(e['payload']['request_payload'] for e in events if e['event_type']=='llm_request_sent' and e['payload'].get('stage')=='initial_owner_comparison')
    user=json.loads(next(m['content'] for m in request['messages'] if m['role']=='user'))
    recorded=next(e['payload'] for e in events if e['event_type']=='initial_files_admitted')
    observations=[]
    allowed={f.name for f in fields(DiscoveryObservation)}
    for item in canonical:
        handle=SourceHandle(**item['handle'])
        provenance=tuple(DiscoveryProvenance(**{k:tuple(v) if isinstance(v,list) else v for k,v in p.items()}) for p in item['provenance'])
        views=[]
        for p in provenance:
            if p.retriever=='exact_anchor': continue
            path,a,b=p.source_key.rsplit(':',2)
            a,b=int(a),int(b)
            text=raw[(path,a,b)]
            start,end=(handle.full_line_start,handle.full_line_end) if handle.node_id else (a,b)
            rendered=_owner_aligned_result_text(text,range_start=a,range_end=b,owner_start=start,owner_end=end)
            x,y=max(a,start),min(b,end)
            if y<x: x,y=a,b
            view=RetrievedSourceView(path,x,y,rendered)
            if view not in views: views.append(view)
        values={k:tuple(v) if isinstance(v,list) else v for k,v in item.items() if k in allowed and k not in {'handle','provenance'}}
        observations.append(DiscoveryObservation(**values,handle=handle,provenance=provenance,
            observed_text=max((v.text for v in views),key=len,default=''),source_views=tuple(views)))
    prompt=next(m['content'] for m in request['messages'] if m['role']=='system')
    kwargs=dict(obligation_descriptions=user['obligations'],ranked_paths=[r['path'] for r in recorded['ranking']],
        preferred_input_chars=recorded['comparison_preferred_input_chars'],max_input_chars=recorded['comparison_input_char_budget'],
        max_files=recorded['file_limit'] or len(recorded['ranking']),
        max_selected=int(re.search(r'selecting no more than (\d+) owners globally',prompt).group(1)))
    root=next(e['payload']['workspace_root'] for e in events if e['payload'].get('workspace_root'))
    # Older runs can have an earlier packing policy: literal views must still reconstruct exactly.
    groups=comparison._candidate_groups(observations,[(p,'*') for p in recorded['admitted_paths']])
    _,_,_,aliases=comparison._payload(user['obligations'],groups)
    # Canonical provenance can outlive a contained-owner merge, so recover the exact
    # original view ranges from the literal request rather than guessing them anew.
    saved_views={}
    for alias,cid in aliases.items():
        values=[]
        for vid in user['owners'][alias]['v']:
            v=user['views'][vid]
            lines=(Path(root)/v['p']).read_text(encoding='utf8').splitlines()
            text='\n'.join(lines[v['r'][0]-1:v['r'][1]])
            choices=[candidate for candidate in (text,text.strip(),text.lstrip(),text.rstrip())
                     if comparison._compact_source_view(candidate)==v['x']]
            if not choices:
                raise ValueError(f"saved_view_snapshot_differs:{v['p']}:{v['r']}")
            text=choices[0]
            values.append(RetrievedSourceView(v['p'],*v['r'],text))
        saved_views[cid]=tuple(values)
    observations=[replace(o,source_views=saved_views[o.id]) if o.id in saved_views else o for o in observations]
    baseline=comparison.fit_initial_owner_comparison_admission(observations=observations,**kwargs)
    groups=comparison._candidate_groups(observations,[(p,'*') for p in recorded['admitted_paths']])
    reconstructed=comparison._payload(user['obligations'],groups)[0]
    # New group path metadata is derived, not source content. Historical inputs omit it.
    for actual, saved in zip(reconstructed['groups'], user['groups'], strict=True):
        if 'path' not in saved:
            actual.pop('path')
    if reconstructed!=user:
        differences={key:[(k,str(v)[:300],str(user[key].get(k))[:300]) for k,v in value.items() if user[key].get(k)!=v][:5]
                     for key,value in reconstructed.items() if isinstance(value,dict) and value!=user[key]}
        raise ValueError(f'saved_owner_payload_not_exactly_reconstructed:{differences}')
    return observations,kwargs,baseline,root,request


def run(args):
    if args.output.exists() or args.output.with_suffix('.jsonl').exists():
        raise FileExistsError(f'replay_output_already_exists:{args.output}')
    observations,kwargs,baseline,root,request=load_saved(args.run)
    bridge=CodeGraphBridge(SimpleNamespace(workspace_root=root,structural_graph_timeout_seconds=60))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.with_suffix('.jsonl').open('w',encoding='utf8') as log:
        def record(kind,payload):
            log.write(json.dumps(dict(event_type=kind,payload=payload))+'\n');log.flush()
        trace=SimpleNamespace(record=record)
        try:
            prepared=prepare_owner_sources(observations,workspace_root=root,
                source_ast=SourceAstRouter(root,codegraph_bridge=bridge),mode=args.mode,max_chars=args.chars,trace=trace)
            admission=comparison.fit_initial_owner_comparison_admission(observations=prepared.observations,**kwargs)
            result=dict(source_run=args.run.name,mode=args.mode,chars=args.chars,
                original_payload_reproduced=True,baseline=asdict(baseline),admission=asdict(admission),
                rows=prepared.rows)
            record('owner_source_replay_admission',{k:v for k,v in result.items() if k!='rows'})
            if args.llm:
                config=replace(_load_project_llm_config({}),model=request['model'])
                selected=comparison.compare_initial_owners(llm_config=config,obligation_descriptions=kwargs['obligation_descriptions'],
                    observations=prepared.observations,admitted_groups=admission.admitted_groups,
                    max_input_chars=kwargs['max_input_chars'],max_selected=kwargs['max_selected'],trace=trace)
                result['selected']=[dict(id=o.id,path=o.handle.path,symbol=o.handle.symbol) for o in selected.selected]
                result['usage']=dict(selected.usage)
            args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
            print(json.dumps(dict(run=args.run.name,mode=args.mode,chars=args.chars,
                before_files=len(baseline.admitted_paths),after_files=len(admission.admitted_paths),
                before_candidates=baseline.candidate_count,after_candidates=admission.candidate_count,
                input_chars=admission.total_input_chars,prepared=sum(r['reason']=='owner_source_prepared' for r in prepared.rows),
                usage=result.get('usage'))))
        except Exception as exc:
            record('owner_source_replay_failed',dict(error=str(exc)))
            raise
        finally:
            bridge.close()


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('run',type=Path)
    p.add_argument('--mode',choices=['targeted','consistent'],required=True)
    p.add_argument('--chars',type=int,required=True)
    p.add_argument('--llm',action='store_true')
    p.add_argument('--output',type=Path,required=True)
    run(p.parse_args())
