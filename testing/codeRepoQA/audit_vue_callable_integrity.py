"""Exercise the real graph bridge and Python observation boundary on Vue source."""
import argparse
import json
import subprocess
from pathlib import Path

from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import observation_from_result


def audit(root: Path):
    source_path = 'src/core/util/props.js'
    lines = (root / source_path).read_text(encoding='utf-8').splitlines()
    ranges = [{'file': source_path, 'line_start': start, 'line_end': end}
              for start, end in [(20, 65), (145, 175)]]
    request = {'operation': 'resolve_ranges', 'arguments': {'ranges': ranges}}
    bridge = Path(__file__).resolve().parents[2] / 'services/retrieval/codegraph/workspace_graph.mjs'
    process = subprocess.run(['node', str(bridge), str(root)], input=json.dumps(request) + '\n',
                             capture_output=True, text=True, check=True)
    response = json.loads(process.stdout.splitlines()[0])
    if not response['ok']:
        raise RuntimeError(response)
    report = []
    for result in response['result']['results']:
        text = '\n'.join(lines[result['line_start'] - 1:result['line_end']])
        observations = observation_from_result(
            {'path': source_path, 'line_start': result['line_start'], 'line_end': result['line_end'], 'text': text},
            obligation_id='diagnostic', query_id='saved-source-probe', rank=1,
            retriever='diagnostic', nodes=result['nodes'])
        report.append({'range': [result['line_start'], result['line_end']],
                       'nodes': result['nodes'], 'rejected': result.get('structural_owner_rejections', []),
                       'observations': [{'symbol': o.handle.symbol,
                                         'visible_range': [o.handle.line_start, o.handle.line_end],
                                         'text': o.observed_text} for o in observations]})
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps([{'range': r['range'], 'owners': [(o['symbol'], o['visible_range'], len(o['text']))
                        for o in r['observations']]} for r in result]))
