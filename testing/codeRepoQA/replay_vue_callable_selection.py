"""Diagnostic counterfactual: change only two malformed Vue owner views.

This exercises the real selector, not full retrieval. IDs, ranks, test views, prompt
and schema stay fixed; repaired views use already-retrieved source range portions.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from services.llm.json_completion import complete_json
from services.retrieval.workspace.pipeline.execution_flow.initial_owner_comparison import _validate_global_response
from testing.codeRepoQA.run_case import _load_project_llm_config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repair', action='store_true')
    args = parser.parse_args()
    events = [json.loads(x) for x in (args.run / 'retrieval-trace.jsonl').read_text(encoding='utf-8').splitlines()]
    event = next(e for e in events if e['event_type'] == 'llm_request_sent'
                 and e['payload'].get('stage') == 'initial_owner_comparison')
    request = copy.deepcopy(event['payload']['request_payload'])
    payload = json.loads(request['messages'][-1]['content'])
    if args.repair:
        # Specific to the frozen 234506Z fixture; fail instead of mutating another case.
        assert args.run.name == 'run-20260914T234506Z'
        assert payload['owners']['o46']['s'] == payload['owners']['o47']['s'] == 'if'
        lines = (args.root / 'src/core/util/props.js').read_text(encoding='utf-8').splitlines()
        payload['owners']['o46']['s'] = 'assertProp'
        payload['owners']['o47']['s'] = 'validateProp'
        for vid, start, end in [('v47', 100, 121), ('v48', 122, 147), ('v49', 21, 60)]:
            view = payload['views'][vid]
            assert view['p'] == 'src/core/util/props.js'
            view.update(r=[start, end], x='\n'.join(lines[start - 1:end]))
        request['messages'][-1]['content'] = json.dumps(payload, sort_keys=True)
    config = _load_project_llm_config(json.loads(Path('configs/testing/workspace.json').read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    logged = []

    def log(kind, data):
        logged.append({'event_type': kind, 'payload': data})
        args.output.with_suffix('.trace.json').write_text(json.dumps(logged), encoding='utf-8')

    response = complete_json(config, request['messages'], response_format=request['response_format'], log_event=log)
    expected = {g['id']: tuple(g['owners']) for g in payload['groups']}
    selected = _validate_global_response(response, expected, max_selected=24)
    report = {'source_run': args.run.name, 'mode': 'two_owner_view_repair' if args.repair else 'exact_saved_request',
              'request_sha256': hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest(),
              'selected_files': [g['path'] for g in payload['groups'] if g['id'] in selected],
              'selected': selected, 'tokens': sum(e['payload']['raw_response']['usage']['total_tokens']
                  for e in logged if e['event_type'] == 'llm_response_received')}
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
