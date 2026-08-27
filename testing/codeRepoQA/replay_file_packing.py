"""Replay file packing from recorded raw source and canonical provenance; no LLM/indexing."""
from __future__ import annotations
import argparse
import ast
from dataclasses import asdict, fields
import json
import re
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from services.retrieval.workspace.pipeline.execution_flow import initial_owner_comparison as comparison
from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import (
    DiscoveryObservation, DiscoveryProvenance, RetrievedSourceView, SourceHandle, _owner_aligned_result_text,
)


def replay(directory: Path, baseline_ref: str, recorded_policy: str = 'baseline'):
    rows = [(i, json.loads(s)) for i, s in enumerate((directory/'retrieval-trace.jsonl').read_text(encoding='utf8').splitlines(), 1)]
    raw = {}
    def collect(value):
        if isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, dict):
            if all(k in value for k in ('path', 'line_start', 'line_end', 'text')):
                raw[(value['path'], value['line_start'], value['line_end'])] = value['text']
            for item in value.values():
                if isinstance(item, (dict, list)):
                    collect(item)
    for _, row in rows:
        if row['event_type'] == 'initial_snippets_canonicalized':
            canonical = row['payload']['output_snippets']
            break
        if row['event_type'] == 'tool_observation_created':
            collect(row['payload'])
    admission_line, recorded = next((i, r['payload']) for i, r in rows if r['event_type'] == 'initial_files_admitted')
    request = next(r['payload'] for _, r in rows if r['event_type'] == 'llm_request_sent' and r['payload'].get('stage') == 'initial_owner_comparison')
    user = json.loads(next(m['content'] for m in request['request_payload']['messages'] if m['role'] == 'user'))
    observations = []
    allowed = {f.name for f in fields(DiscoveryObservation)}
    for item in canonical:
        handle = SourceHandle(**item['handle'])
        provenance = tuple(DiscoveryProvenance(**{k:tuple(v) if isinstance(v,list) else v for k,v in p.items()}) for p in item['provenance'])
        views = []
        for p in provenance:
            if p.retriever == 'exact_anchor':
                continue
            path, start, end = p.source_key.rsplit(':', 2)
            start, end = int(start), int(end)
            text = raw[(path, start, end)]
            owner_start, owner_end = (handle.full_line_start, handle.full_line_end) if handle.node_id else (start, end)
            rendered = _owner_aligned_result_text(text, range_start=start, range_end=end, owner_start=owner_start, owner_end=owner_end)
            a, b = max(start, owner_start), min(end, owner_end)
            if b < a:
                a, b = start, end
            view = RetrievedSourceView(path, a, b, rendered)
            if view not in views:
                views.append(view)
        values = {k:tuple(v) if isinstance(v,list) else v for k,v in item.items() if k in allowed and k not in {'handle','provenance'}}
        observations.append(DiscoveryObservation(**values, handle=handle, provenance=provenance,
            observed_text=max((v.text for v in views), key=len, default=''), source_views=tuple(views)))
    ranking = [item['path'] for item in recorded['ranking']]
    kwargs = dict(obligation_descriptions=user['obligations'], observations=observations, ranked_paths=ranking,
        preferred_input_chars=recorded['comparison_preferred_input_chars'], max_input_chars=recorded['comparison_input_char_budget'],
        max_files=recorded['file_limit'] or max(1, len(ranking)))
    # Schema row count can be smaller than the global owner cap; read its explicit prompt contract.
    prompt = next(m['content'] for m in request['request_payload']['messages'] if m['role'] == 'system')
    kwargs['max_selected'] = int(re.search(r'selecting no more than (\d+) owners globally', prompt).group(1))
    source = subprocess.check_output(['git','show',f'{baseline_ref}:services/retrieval/workspace/pipeline/execution_flow/initial_owner_comparison.py'], text=True, encoding='utf8')
    fn = next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name == 'fit_initial_owner_comparison_admission')
    namespace = dict(vars(comparison))
    exec(compile(ast.Module(body=[fn], type_ignores=[]), '<baseline-packing>', 'exec'), namespace)
    old = namespace['fit_initial_owner_comparison_admission'](**kwargs)
    new = comparison.fit_initial_owner_comparison_admission(**kwargs)
    expected = old if recorded_policy == 'baseline' else new
    if list(expected.admitted_paths) != recorded['admitted_paths'] or expected.total_input_chars != recorded['comparison_total_input_chars']:
        raise ValueError(f'Recorded admission mismatch paths={expected.admitted_paths}, chars={expected.total_input_chars}/{recorded["comparison_total_input_chars"]}')
    return dict(run_id=directory.name, trace_line=admission_line, baseline_ref=baseline_ref,
        recorded_policy=recorded_policy, recorded_policy_reproduced=True,
        old=asdict(old), new=asdict(new), added_paths=sorted(set(new.admitted_paths)-set(old.admitted_paths)),
        removed_paths=sorted(set(old.admitted_paths)-set(new.admitted_paths)),
        note='Saved-input deterministic packing, not a prediction of LLM choices.')


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('run_dirs', nargs='+', type=Path)
    p.add_argument('--baseline-ref', required=True)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--recorded-policy', choices=('baseline', 'current'), default='baseline')
    args=p.parse_args()
    result=[replay(d,args.baseline_ref,args.recorded_policy) for d in args.run_dirs]
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    for row in result:
        print(json.dumps(dict(run_id=row['run_id'], old_chars=row['old']['total_input_chars'], new_chars=row['new']['total_input_chars'],
            old_candidates=row['old']['candidate_count'], new_candidates=row['new']['candidate_count'], added_paths=row['added_paths']),indent=2))
