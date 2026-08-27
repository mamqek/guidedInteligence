from __future__ import annotations

import tempfile
import unittest
import json
import shutil
import subprocess
from pathlib import Path

from services.retrieval.workspace.source_ast import SourceAstRouter


class SourceAstRouterTests(unittest.TestCase):
    def test_python_ast_owner_validates_identity_and_calls_lambda_body(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / 'owners.py').write_text('exports.parse = lambda value: Tools.clean(value, lambda: hidden())\ndef next_owner():\n    sibling()\n', encoding='utf-8')
            router = SourceAstRouter(root, codegraph_bridge=_FailBridge())
            owner = router.resolve_source_owners('owners.py', 1, 1)['owners'][0]
            result = router.source_owner_calls(owner)
            self.assertEqual(result['source_kind'], 'assigned_function')
            self.assertEqual([call['name'] for call in result['calls']], ['clean'])
            for change in ({'name': 'wrong', 'qualified_name': 'wrong'}, {'line_end': 2}, {'id': owner['id'] + '0'}, {'path': '../outside.py'}):
                self.assertEqual(router.source_owner_calls({**owner, **change})['status'], 'failed')
            ordinary = router.resolve_source_owners('owners.py', 2, 3)['owners'][0]
            self.assertEqual([call['name'] for call in router.source_owner_calls(ordinary)['calls']], ['sibling'])

    def test_javascript_ast_owner_calls_without_graph_and_rejects_spoofed_handles(self) -> None:
        node = shutil.which('node')
        if not node:
            self.skipTest('Node is unavailable')
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / 'repo'
            root.mkdir()
            (Path(temp_dir) / 'outside.js').write_text('exports.parse = () => External.secret();', encoding='utf-8')
            (root / 'owners.js').write_text(
                'exports.parse = function(value) {\n  const nested = () => Hidden.call();\n  Tools.clean(value);\n};\n'
                'exports.next = () => Other.run();\nconst notCallable = 1;\n', encoding='utf-8')
            module = (Path(__file__).resolve().parents[1] / 'services/retrieval/codegraph/source_ast.mjs').as_uri()
            script = '''
import {resolveSourceOwners, sourceOwnerCalls} from MODULE;
const root = process.argv[1];
const owners = resolveSourceOwners(root, {path:'owners.js', line_start:1, line_end:6}).owners;
const owner = owners[0];
const changed = [{line_end:5}, {name:'wrong', qualified_name:'wrong'}, {id:owner.id+'0'}, {path:'../outside.js'}];
console.log(JSON.stringify({owners, calls:owners.map(o=>sourceOwnerCalls(null,root,o)),
 invalid:changed.map(c=>sourceOwnerCalls(null,root,{...owner,...c})),
 noncallable:sourceOwnerCalls(null,root,{id:'source_owner:owners.js:6:6',path:'owners.js',line_start:6,line_end:6,name:'notCallable'})}));
'''.replace('MODULE', json.dumps(module))
            completed = subprocess.run([node, '--input-type=module', '-e', script, str(root)], capture_output=True, text=True, check=True)
            result = json.loads(completed.stdout)
            self.assertEqual([[call['name'] for call in row['calls']] for row in result['calls']], [['clean'], ['run']])
            self.assertTrue(all(row['source_kind'] == 'assigned_function' for row in result['calls']))
            self.assertTrue(all(row['status'] == 'failed' for row in result['invalid']))
            self.assertEqual(result['invalid'][3]['reason'], 'source_owner_outside_workspace')
            self.assertEqual(result['noncallable']['status'], 'failed')

    def test_typescript_ast_handle_is_passed_to_adapter_not_graph_id_lookup(self) -> None:
        bridge = _RecordingBridge({'status': 'ok', 'calls': [], 'source_kind': 'assigned_function'})
        router = SourceAstRouter(Path.cwd(), codegraph_bridge=bridge)
        owner = {'id':'source_owner:owners.js:1:3', 'path':'owners.js', 'name':'exports.parse', 'line_start':1, 'line_end':3}
        router.source_owner_calls(owner)
        self.assertEqual(bridge.requests, [('source_owner_calls', {'source_node': owner})])

    def test_python_owner_calls_use_python_adapter_and_skip_nested_owners(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "builder.py"
            source.write_text(
                "def left():\n"
                "    return []\n\n"
                "def right():\n"
                "    return []\n\n"
                "def get_files(flag=False):\n"
                "    helper = lambda: ignored()\n"
                "    def nested():\n"
                "        nested_only()\n"
                "    return (left if flag else right)()\n",
                encoding="utf-8",
            )
            router = SourceAstRouter(root, codegraph_bridge=_FailBridge())

            result = router.source_owner_calls(
                {
                    "id": "function:get_files",
                    "path": "builder.py",
                    "name": "get_files",
                    "line_start": 7,
                    "line_end": 11,
                }
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["adapter"], "python_stdlib_ast")
        self.assertEqual({call["name"] for call in result["calls"]}, {"left", "right"})

    def test_typescript_owner_calls_are_routed_to_codegraph_adapter(self) -> None:
        bridge = _RecordingBridge(
            {
                "status": "ok",
                "adapter": "typescript_compiler_api",
                "calls": [{"name": "target", "qualifier": "Module"}],
            }
        )
        router = SourceAstRouter(Path.cwd(), codegraph_bridge=bridge)

        result = router.source_owner_calls(
            {"id": "function:caller", "path": "src/caller.ts", "name": "caller"}
        )

        self.assertEqual(result["adapter"], "typescript_compiler_api")
        self.assertEqual(
            bridge.requests,
            [("source_owner_calls", {"node_id": "function:caller"})],
        )

    def test_typescript_source_owner_resolution_is_routed(self) -> None:
        bridge = _RecordingBridge({"status": "ok", "adapter": "typescript_compiler_api", "owners": []})
        router = SourceAstRouter(Path.cwd(), codegraph_bridge=bridge)

        router.resolve_source_owners("src/parser.js", 103, 142)

        self.assertEqual(bridge.requests, [(
            "resolve_source_owners",
            {"path": "src/parser.js", "line_start": 103, "line_end": 142},
        )])

    def test_python_source_owner_resolution_includes_defs_and_lambda_assignments(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "owners.py").write_text(
                "def ordinary():\n    return 1\n\nexports = object()\nexports.parse = lambda value: value\n",
                encoding="utf-8",
            )
            result = SourceAstRouter(root, codegraph_bridge=_FailBridge()).resolve_source_owners(
                "owners.py", 1, 5,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual({owner["name"] for owner in result["owners"]}, {"ordinary", "exports.parse"})

    def test_unsupported_language_has_normalized_result(self) -> None:
        result = SourceAstRouter(Path.cwd(), codegraph_bridge=_FailBridge()).source_owner_calls(
            {"id": "function:main", "path": "main.go", "name": "main"}
        )

        self.assertEqual(result["status"], "unsupported")
        self.assertEqual(result["calls"], [])



class _RecordingBridge:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.requests: list[tuple[str, dict[str, object]]] = []

    def request(self, operation: str, arguments: dict[str, object]) -> dict[str, object]:
        self.requests.append((operation, arguments))
        return self.response


class _FailBridge:
    def request(self, operation: str, arguments: dict[str, object]) -> dict[str, object]:
        raise AssertionError(f"Unexpected bridge request: {operation} {arguments}")


if __name__ == "__main__":
    unittest.main()
