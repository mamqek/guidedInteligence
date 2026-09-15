"""Paired saved-pool gate/admission replay; optional actual selector call."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

from testing.codeRepoQA.replay_unresolved_admission import replay
from testing.codeRepoQA.run_case import _load_project_llm_config
from testing.codeRepoQA.hidden_anchor_variant import prepare_hidden_anchor_source, request_code_names
from services.retrieval.workspace.pipeline.execution_flow.initial_owner_comparison import (
    _compact_source_view, fit_initial_owner_comparison_admission, compare_initial_owners,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--llm', choices=('old', 'new', 'old-on-new-admission'))
    args = parser.parse_args()
    observations, kwargs, prepared = replay(args.run, return_pool=True)
    old = [replace(o, comparison_source_views=()) if prepared[o.id]['reason'] == 'unresolved_source_prepared' else o
           for o in observations]
    orchestration = [json.loads(x) for x in (args.run/'orchestration-trace.jsonl').read_text().splitlines()]
    request = next(e['payload']['turn_request'] for e in orchestration if e['event_type'] == 'run_started')
    names = request_code_names(request)
    new, changed = [], []
    for o in old:
        result = prepare_hidden_anchor_source(o, names=names, compact=_compact_source_view)
        new.append(replace(o, comparison_source_views=result.views) if result.views else o)
        if result.views:
            changed.append(dict(id=o.id, path=o.handle.path, anchor=result.anchor, witness=result.witness_range,
                                source_chars=sum(len(v.text) for v in result.views)))
    before = fit_initial_owner_comparison_admission(observations=old, **kwargs)
    after = fit_initial_owner_comparison_admission(observations=new, **kwargs)
    by_id = {o.id:o for o in old}
    report = dict(source_run=args.run.name, original_prepared_admission_verified=True,
                  all_observations_unchanged=old == new,
                  names=names, changes=changed, old_count=before.candidate_count, new_count=after.candidate_count,
                  old_chars=before.total_input_chars, new_chars=after.total_input_chars,
                  displaced=[dict(id=i, path=by_id[i].handle.path, symbol=by_id[i].handle.symbol)
                             for i in before.admitted_ids if i not in after.admitted_ids],
                  admitted_changes=[c for c in changed if c['id'] in after.admitted_ids])
    if args.llm:
        pool, admission = ((old, before) if args.llm == 'old' else
                           (old, after) if args.llm == 'old-on-new-admission' else (new, after))
        lookup = {o.id:o for o in pool}
        events = []
        def record(kind, payload):
            events.append(dict(event_type=kind, payload=payload))
            args.output.with_suffix('.trace.json').write_text(json.dumps(events), encoding='utf-8')
        config = _load_project_llm_config(json.loads(Path('configs/testing/workspace.json').read_text()))
        result = compare_initial_owners(llm_config=config, obligation_descriptions=kwargs['obligation_descriptions'],
             observations=tuple(lookup[i] for i in admission.admitted_ids), admitted_groups=admission.admitted_groups,
             max_input_chars=kwargs['max_input_chars'], max_selected=kwargs['max_selected'], trace=SimpleNamespace(record=record))
        report.update(condition=args.llm, selected=[dict(id=o.id,path=o.handle.path,symbol=o.handle.symbol) for o in result.selected],
                      tokens=sum(e['payload']['raw_response']['usage']['total_tokens'] for e in events
                                 if e['event_type']=='llm_response_received'))
    args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('changes','displaced','admitted_changes')}))


if __name__ == '__main__':
    main()
