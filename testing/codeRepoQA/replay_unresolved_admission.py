"""Exact recorded prepared-pool admission counterfactual, with no LLM calls."""
import argparse
from dataclasses import fields, replace
import json
from pathlib import Path

from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import (
    DiscoveryObservation, DiscoveryProvenance, RetrievedSourceView, SourceHandle,
    _owner_aligned_result_text,
)
from services.retrieval.workspace.pipeline.execution_flow.initial_owner_comparison import (
    fit_initial_owner_comparison_admission, _candidate_groups, _payload,
)
from testing.codeRepoQA.unresolved_source_variant import render_unresolved_source


def replay(run: Path, *, return_pool: bool = False):
    events = [json.loads(line) for line in (run / 'retrieval-trace.jsonl').read_text().splitlines()]
    get = lambda kind: next(e['payload'] for e in events if e['event_type'] == kind)
    root = Path(next(e['payload']['workspace_root'] for e in events if e['payload'].get('workspace_root')))
    canonical = get('initial_snippets_canonicalized')['output_snippets']
    prepared = {r['observation_id']: r for r in get('owner_comparison_source_prepared')['rows']}
    admitted = get('initial_files_admitted')
    request = next(e['payload']['request_payload'] for e in events if e['event_type'] == 'llm_request_sent'
                   and e['payload'].get('stage') == 'initial_owner_comparison')
    payload = json.loads(request['messages'][-1]['content'])
    allowed = {f.name for f in fields(DiscoveryObservation)} - {'handle', 'provenance'}
    raw = {}
    def collect(value):
        if isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, dict):
            if all(k in value for k in ('path', 'line_start', 'line_end', 'text')):
                raw[(value['path'], value['line_start'], value['line_end'])] = value['text']
            for item in value.values():
                if isinstance(item, (list, dict)):
                    collect(item)
    for event in events:
        if event['event_type'] == 'initial_snippets_canonicalized':
            break
        if event['event_type'] == 'tool_observation_created':
            collect(event['payload'])
    observations = []
    for row in canonical:
        p = prepared[row['id']]
        handle = SourceHandle(**row['handle'])
        if p['reason'] == 'unresolved_source_prepared':
            views = tuple(RetrievedSourceView(**v) for v in p['source_views'])
            original = []
            for v in views:
                path = (root / v.path).resolve()
                if not path.is_relative_to(root.resolve()):
                    raise ValueError('source_outside_snapshot')
                key = (v.path, v.line_start, v.line_end)
                if key in raw:
                    text = raw[key]
                else:
                    candidates = [(a, b, text) for (name, a, b), text in raw.items()
                                  if name == v.path and a <= v.line_start and b >= v.line_end]
                    if not candidates:
                        raise ValueError('missing_recorded_raw_view:' + str(key))
                    a, b, text = min(candidates, key=lambda x: x[1]-x[0])
                    text = _owner_aligned_result_text(text, range_start=a, range_end=b,
                               owner_start=v.line_start, owner_end=v.line_end)
                source_view = replace(v, text=text)
                terms = tuple(t for source in row['provenance'] for t in source['matched_terms'])
                if render_unresolved_source(source_view, matched_terms=terms, max_chars=p['max_chars']) != v.text:
                    raise ValueError('recorded_unresolved_source_not_exactly_reconstructed')
                original.append(source_view)
        elif p['reason'] == 'owner_source_prepared':
            views = (RetrievedSourceView(handle.path, *p['owner_range'], p['source_text']),)
            original = []  # Not used by either condition; exact prepared named-owner view stays fixed.
        else:
            views, original = (), []
            for source in row['provenance']:
                path, a, b = source['source_key'].rsplit(':', 2)
                a, b = int(a), int(b)
                text, start, end = raw[(path, a, b)], a, b
                if handle.node_id:
                    text = _owner_aligned_result_text(text, range_start=a, range_end=b,
                                owner_start=handle.full_line_start, owner_end=handle.full_line_end)
                    start, end = max(a, handle.full_line_start), min(b, handle.full_line_end)
                    if end < start:
                        start, end = a, b
                view = RetrievedSourceView(path, start, end, text)
                if view not in original:
                    original.append(view)
        values = {k: tuple(v) if isinstance(v, list) else v for k, v in row.items() if k in allowed}
        provenance = tuple(DiscoveryProvenance(**{
            k: tuple(v) if isinstance(v, list) else v for k, v in p.items()
        }) for p in row['provenance'])
        observations.append(DiscoveryObservation(**values, handle=handle, provenance=provenance,
                            observed_text='', source_views=tuple(original), comparison_source_views=views))
    kwargs = dict(obligation_descriptions=payload['obligations'],
                  preferred_input_chars=admitted['comparison_preferred_input_chars'],
                  max_input_chars=admitted['comparison_input_char_budget'], max_selected=24)
    current = fit_initial_owner_comparison_admission(observations=observations, **kwargs)
    if list(current.admitted_ids) != admitted['admitted_snippet_ids'] or current.total_input_chars != admitted['comparison_total_input_chars']:
        lookup = {o.id:o for o in observations}
        actual = _payload(payload['obligations'], _candidate_groups(
            [lookup[i] for i in admitted['admitted_snippet_ids']], current.admitted_groups))[0]
        differences = [(k, v, payload['views'].get(k)) for k,v in actual['views'].items() if v != payload['views'].get(k)]
        raise ValueError(f'current_admission_not_exactly_reconstructed: chars={current.total_input_chars}/{admitted["comparison_total_input_chars"]}, ids_equal={list(current.admitted_ids) == admitted["admitted_snippet_ids"]}, views={differences[:3]}')
    if return_pool:
        return observations, kwargs, prepared
    old = fit_initial_owner_comparison_admission(observations=[
        replace(o, comparison_source_views=()) if prepared[o.id]['reason'] == 'unresolved_source_prepared' else o
        for o in observations], **kwargs)
    by_id = {o.id: o for o in observations}
    return dict(run=run.name, current_exact=True, current_count=current.candidate_count, old_count=old.candidate_count,
                current_chars=current.total_input_chars, old_chars=old.total_input_chars,
                current_ids=list(current.admitted_ids), old_ids=list(old.admitted_ids),
                additionally_admitted_with_old_renderer=[dict(id=i, path=by_id[i].handle.path, symbol=by_id[i].handle.symbol,
                    lines=[by_id[i].handle.line_start, by_id[i].handle.line_end])
                    for i in old.admitted_ids if i not in current.admitted_ids])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    reports = [replay(run) for run in args.run]
    args.output.write_text(json.dumps(reports, indent=2), encoding='utf-8')
    for report in reports:
        print(report['run'], report['current_exact'], report['current_count'], report['old_count'])


if __name__ == '__main__':
    main()
