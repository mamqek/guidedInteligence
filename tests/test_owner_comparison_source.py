import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from types import SimpleNamespace

from services.retrieval.workspace.pipeline.execution_flow.owner_comparison_source import render_owner_source, prepare_owner_sources
from services.retrieval.workspace.pipeline.execution_flow.discovery_observations import DiscoveryObservation, DiscoveryProvenance, SourceHandle, RetrievedSourceView
from services.retrieval.workspace.source_ast.router import SourceAstRouter


class OwnerSourceTests(unittest.TestCase):
    def test_preparation_preserves_identity_provenance_and_repairs_renderer(self):
        from services.retrieval.workspace.pipeline.execution_flow.initial_owner_comparison import _source_view_payloads
        source='def f():\n    """Documentation."""\n    return answer()\n'
        with tempfile.TemporaryDirectory() as folder:
            Path(folder,'a.py').write_text(source,encoding='utf8')
            o=DiscoveryObservation('id',SourceHandle('a.py',1,2,node_id='function:x',full_line_start=1,full_line_end=3),
                'def f():\n    """Documentation."""',(DiscoveryProvenance('dense','query'),),
                source_views=(RetrievedSourceView('a.py',1,2,'def f():\n    """Documentation."""'),))
            for mode in ('targeted','consistent'):
                result=prepare_owner_sources((o,o),workspace_root=folder,
                    source_ast=SourceAstRouter(folder,codegraph_bridge=None),mode=mode,max_chars=512)
                self.assertEqual(result.file_reads,1)
                new=result.observations[0]
                self.assertEqual(new.id,o.id)
                self.assertEqual(new.source_views,o.source_views)
                self.assertEqual(new.provenance,o.provenance)
                self.assertIn('return answer()',_source_view_payloads(new)[0][1]['x'])

    def test_unmatched_owner_is_explicit_and_source_snapshot_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder,'a.py').write_text('def f():\n    return answer()\n',encoding='utf8')
            o=DiscoveryObservation('id',SourceHandle('a.py',1,1,node_id='function:x',full_line_start=1,full_line_end=2),
                'different source',())
            ast=SourceAstRouter(folder,codegraph_bridge=None)
            with self.assertRaisesRegex(ValueError,'snapshot_mismatch'):
                prepare_owner_sources((o,),workspace_root=folder,source_ast=ast,mode='consistent',max_chars=512)
            missing=SimpleNamespace(owner_source_layouts=lambda _:dict(status='ok',owners=[]))
            result=prepare_owner_sources((o,),workspace_root=folder,source_ast=missing,mode='consistent',max_chars=512)
            self.assertEqual(result.rows[0]['reason'],'owner_layout_identity_unmatched')
            self.assertEqual(result.observations[0],o)

    def test_complete_small_owner(self):
        lines=['def f():', '    return answer()']
        text, ranges=render_owner_source(lines,start=1,end=2,signature_end=1,body_ranges=[[2,2]],focus=(1,1),max_chars=512)
        self.assertEqual(ranges,((1,2),))
        self.assertIn('return answer()',text)
        self.assertNotIn('omitted',text)

    def test_small_owner_does_not_expand_away_from_focus(self):
        lines=['def f():'] + [f'    x = {i}' for i in range(20)]
        text, ranges=render_owner_source(lines,start=1,end=21,signature_end=1,
            body_ranges=[[2,21]],focus=(15,15),max_chars=1024)
        self.assertIn('x = 13',text)
        self.assertNotIn('x = 0\n',text)
        self.assertNotEqual(ranges,((1,21),))
        self.assertEqual(sum(b-a+1 for a,b in ranges),6)
        self.assertIn('omitted',text)

    def test_wide_hit_obeys_line_and_character_bounds(self):
        lines=['def f():'] + ['    step()']*100
        text, ranges=render_owner_source(lines,start=1,end=101,signature_end=1,
            body_ranges=[[2,101]],focus=(2,101),max_chars=1024,max_lines=10)
        self.assertLessEqual(sum(b-a+1 for a,b in ranges),10)
        self.assertLessEqual(len(text),1024)
        self.assertIn('def f():',text)
        self.assertGreater(len(ranges),1)

    def test_long_signature_leaves_body_and_marks_omission(self):
        lines=['def f(']+['    param,']*20+['):']+['    step()']*40
        text, ranges=render_owner_source(lines,start=1,end=len(lines),signature_end=22,
            body_ranges=[[23,len(lines)]],focus=(40,40),max_chars=1024)
        self.assertIn('step()',text)
        self.assertIn('def f(',text)
        self.assertIn('omitted',text)
        self.assertLessEqual(sum(b-a+1 for a,b in ranges),16)

    def test_late_focus_and_signature_have_explicit_gap(self):
        lines=['def f():'] + [f'    field_{i} = compute({i})' for i in range(100)]
        text,ranges=render_owner_source(lines,start=1,end=101,signature_end=1,body_ranges=[[2,101]],focus=(88,89),max_chars=512)
        self.assertIn('def f():',text)
        self.assertIn('field_87',text)
        self.assertIn('omitted',text)
        self.assertGreater(len(ranges),1)
        self.assertLessEqual(len(text),512)

    def test_docstring_hit_uses_real_body(self):
        lines=['def f():','    """']+['    documentation']*30+['    """','    return answer()']
        text,ranges=render_owner_source(lines,start=1,end=len(lines),signature_end=1,body_ranges=[[len(lines),len(lines)]],focus=(2,5),max_chars=200)
        self.assertIn('return answer()',text)
        self.assertLessEqual(len(text),200)
        self.assertNotIn('documentation',text)

    def test_one_line_callable_is_complete(self):
        text,ranges=render_owner_source(['const f = () => answer();'],start=1,end=1,signature_end=1,body_ranges=[[1,1]],focus=(1,1),max_chars=100)
        self.assertEqual(ranges,((1,1),))
        self.assertIn('answer()',text)

    def test_overlong_line_marked_partial(self):
        text,_=render_owner_source(['const f = () => '+ 'x'*600],start=1,end=1,signature_end=1,body_ranges=[[1,1]],focus=(1,1),max_chars=200)
        self.assertIn('clipped, partial source',text)
        self.assertEqual(len(text),200)

    def test_python_adapter_excludes_docstring(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder,'a.py').write_text('def f():\n    """Docs."""\n    return answer()\n',encoding='utf8')
            r=SourceAstRouter(folder,codegraph_bridge=None).owner_source_layouts('a.py')
        self.assertEqual(r['owners'][0]['body_ranges'],[[3,3]])

    def test_router_rejects_outside_root(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                SourceAstRouter(folder,codegraph_bridge=None).owner_source_layouts('../outside.ts')

    def test_js_assignment_and_typescript_method_layouts(self):
        module=Path(__file__).resolve().parents[1]/'services/retrieval/codegraph/source_ast.mjs'
        script=f"import {{ownerSourceLayouts}} from '{module.as_uri()}'; console.log(JSON.stringify(ownerSourceLayouts(process.argv[1],{{path:process.argv[2]}})));"
        with tempfile.TemporaryDirectory() as folder:
            Path(folder,'a.js').write_text('exports.parse = function (x) {\n  return transform(x);\n};\n',encoding='utf8')
            r=json.loads(subprocess.check_output(['node','--input-type=module','-e',script,folder,'a.js'],text=True))
            self.assertEqual(r['owners'][0]['body_ranges'],[[2,2]])
            self.assertEqual(r['owners'][0]['line_end'],3)
            Path(folder,'a.ts').write_text('class C {\n  f(x: number) {\n    return x + 1;\n  }\n}\n',encoding='utf8')
            r=json.loads(subprocess.check_output(['node','--input-type=module','-e',script,folder,'a.ts'],text=True))
            self.assertTrue(any(o['line_start']==2 and o['body_ranges']==[[3,3]] for o in r['owners']))


if __name__=='__main__':
    unittest.main()
