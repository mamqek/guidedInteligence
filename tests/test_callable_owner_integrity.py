from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import observation_from_result
from services.retrieval.workspace.pipeline.execution_flow.initial_owner_comparison import select_range_candidate_owners


class CallableOwnerIntegrityTests(unittest.TestCase):
    def replay(self, source: str, script: str) -> dict:
        node = shutil.which('node')
        if not node:
            self.skipTest('Node is unavailable')
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'owners.js').write_text(source, encoding='utf-8')
            imports = (
                f"import {{reconcileCallableOwners,validateStructuralResult}} from {json.dumps((root/'services/retrieval/codegraph/callable_owners.mjs').as_uri())};\n"
                f"import {{sourceOwnerCalls}} from {json.dumps((root/'services/retrieval/codegraph/source_ast.mjs').as_uri())};\n"
                "const root=process.argv[1];\n"
            )
            completed = subprocess.run([node, '--input-type=module', '-e', imports + script, directory],
                                       capture_output=True, text=True, check=True)
            return json.loads(completed.stdout)

    def test_false_if_recovers_outer_and_keeps_its_body_and_call(self):
        source = ('export function validateProp(value: any, vm?: Component): any {\n'
                  '  if (value) {\n    value = false;\n  }\n'
                  '  assertProp(value);\n  return value;\n}\n')
        result = self.replay(source, '''
const bad={id:'function:bad',kind:'function',name:'if',path:'owners.js',line_start:2,line_end:4};
const resolved=reconcileCallableOwners(root,'owners.js',1,7,[bad]);
console.log(JSON.stringify({resolved,calls:sourceOwnerCalls(null,root,resolved.nodes[0]),
  rejectedCalls:sourceOwnerCalls(null,root,bad),
  rejectedRoot:validateStructuralResult(root,{source:bad}),
  otherEntries:validateStructuralResult(root,{nodes:[bad],edges:[{source:bad,target:bad}],
    connector_paths:[{source:bad,connector:bad,target:bad}],capabilities:[{node:bad}]})}));
''')
        owner = result['resolved']['nodes'][0]
        self.assertEqual((owner['name'], owner['line_start'], owner['line_end']), ('validateProp', 1, 7))
        self.assertTrue(owner['id'].startswith('source_owner:'))
        self.assertEqual([c['name'] for c in result['calls']['calls']], ['assertProp'])
        self.assertEqual(result['rejectedCalls']['status'], 'failed')
        self.assertEqual(len(result['rejectedRoot']['structural_owner_rejections']), 1)
        for key in ['nodes', 'edges', 'connector_paths', 'capabilities']:
            self.assertEqual(result['otherEntries'][key], [])
        self.assertEqual(len(result['otherEntries']['structural_owner_rejections']), 1)
        observation = observation_from_result({'path': 'owners.js', 'line_start': 1, 'line_end': 7, 'text': source},
                                             obligation_id='why', query_id='q', rank=1, retriever='dense', nodes=[owner])[0]
        self.assertIn('assertProp(value)', observation.observed_text)

    def test_type_declaration_end_is_replaced_by_executable_end(self):
        result = self.replay('function assertType(value: any): { valid: boolean; } {\n  return check(value);\n}\n', '''
const bad={id:'function:bad',kind:'function',name:'assertType',path:'owners.js',line_start:1,line_end:1};
const resolved=reconcileCallableOwners(root,'owners.js',1,3,[bad]);
console.log(JSON.stringify({resolved,calls:sourceOwnerCalls(null,root,resolved.nodes[0])}));
''')
        self.assertEqual(result['resolved']['nodes'][0]['line_end'], 3)
        self.assertEqual([c['name'] for c in result['calls']['calls']], ['check'])

    def test_nested_function_retains_outer_context_and_calls_do_not_leak(self):
        result = self.replay('function outer(value: any) {\n  function inner() {\n    child();\n  }\n  outerOnly();\n}\n', '''
const bad={id:'function:bad',kind:'function',name:'if',path:'owners.js',line_start:3,line_end:3};
const resolved=reconcileCallableOwners(root,'owners.js',2,4,[bad]);
console.log(JSON.stringify({resolved,calls:resolved.nodes.map(n=>sourceOwnerCalls(null,root,n))}));
''')
        nodes = result['resolved']['nodes']
        selected = select_range_candidate_owners(nodes, line_start=2, line_end=4)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]['name'], 'inner')
        self.assertEqual(selected[0]['outer_symbol'], 'outer')
        self.assertEqual([[c['name'] for c in r['calls']] for r in result['calls']], [['outerOnly'], ['child']])

    def test_healthy_graph_identity_unchanged_and_parse_failure_is_explicit(self):
        result = self.replay('function valid() { return 1; }\n', '''
const good={id:'function:good',kind:'function',name:'valid',path:'owners.js',line_start:1,line_end:1};
console.log(JSON.stringify(reconcileCallableOwners(root,'owners.js',1,1,[good])));
''')
        self.assertEqual(result['nodes'][0]['id'], 'function:good')
        self.assertEqual(result['rejected'], [])
        result = self.replay('function broken( {\n', '''
const bad={id:'function:bad',kind:'function',name:'broken',path:'owners.js',line_start:1,line_end:1};
console.log(JSON.stringify(reconcileCallableOwners(root,'owners.js',1,1,[bad])));
''')
        self.assertEqual(result['nodes'], [])
        self.assertEqual(result['rejected'][0]['reason'], 'source_ast_parse_failed')
        original = 'function broken( {\n'
        observations = observation_from_result(
            {'path': 'owners.js', 'line_start': 1, 'line_end': 1, 'text': original},
            obligation_id='why', query_id='q', rank=1, retriever='dense', nodes=result['nodes'])
        self.assertEqual(observations[0].observed_text.strip(), original.strip())
        self.assertEqual(observations[0].handle.node_id, '')

    def test_recovered_handle_cannot_claim_a_different_function_or_range(self):
        result = self.replay('function owner(value: any) { return consume(value); }\n', '''
const bad={id:'function:bad',kind:'function',name:'if',path:'owners.js',line_start:1,line_end:1};
const owner=reconcileCallableOwners(root,'owners.js',1,1,[bad]).nodes[0];
console.log(JSON.stringify({results:[{line_end:2},{qualified_name:'other'},{id:owner.id+'x'}]
  .map(change=>sourceOwnerCalls(null,root,{...owner,...change}))}));
''')
        self.assertTrue(all(r['status'] == 'failed' for r in result['results']))

    def test_named_expression_keeps_graph_name_and_assignment_identity(self):
        result = self.replay('module.exports = function wrapper() {\n  const Component = function Inner() {};\n  obj.get = function getter() {};\n};\n', '''
const nodes=[['wrapper',1,4],['Inner',2,2],['getter',3,3]].map(([name,start,end])=>
  ({id:'function:'+name,kind:'function',name,path:'owners.js',line_start:start,line_end:end}));
console.log(JSON.stringify(reconcileCallableOwners(root,'owners.js',1,4,nodes)));
''')
        self.assertEqual(result['rejected'], [])
        self.assertEqual([n['id'] for n in result['nodes']],
                         ['function:wrapper', 'function:Inner', 'function:getter'])

    def test_unrelated_flow_predicate_does_not_discard_a_real_owner(self):
        source = ('export function isUndef(v: any): boolean %checks { return v === undefined; }\n'
                  'function useful(value) {\n  return consume(value);\n}\n')
        result = self.replay(source, '''
const good={id:'function:useful',kind:'function',name:'useful',path:'owners.js',line_start:2,line_end:4};
console.log(JSON.stringify(reconcileCallableOwners(root,'owners.js',2,4,[good])));
''')
        self.assertEqual(result['rejected'], [])
        self.assertEqual(result['nodes'][0]['id'], 'function:useful')


if __name__ == '__main__':
    unittest.main()
