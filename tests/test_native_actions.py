"""Run native-facing decision code with host doubles; no renderer emulation."""
import ast
import json
from contextlib import nullcontext
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1] / 'ArgentumSplat'
sys.path.insert(0, str(ROOT))
from argentum_splat import ids as I, loading


def function(file, name, context, cls=None):
    tree = ast.parse((ROOT/'argentum_splat'/file).read_text(encoding='utf8'))
    nodes = tree.body
    if cls:
        nodes = next(n for n in nodes if isinstance(n, ast.ClassDef) and n.name == cls).body
    node = next(n for n in nodes if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), file+':'+name, 'exec'), context)
    return context[name]


class Op(dict):
    def GetDocument(self):
        return self.doc


class NativeDecisionTests(unittest.TestCase):
    def test_emission_migration_preserves_custom_shader_source(self):
        tree = ast.parse((ROOT/'argentum_splat/materials.py').read_text(encoding='utf8'))
        assignments = [node for node in tree.body if isinstance(node,ast.Assign)
                       and any(isinstance(t,ast.Name) and t.id in
                               ('LEGACY_EMISSION_SOURCE','EMISSION_SOURCE') for t in node.targets)]
        constants = {}
        exec(compile(ast.Module(body=assignments,type_ignores=[]),'emission constants','exec'),constants)
        legacy,new = constants['LEGACY_EMISSION_SOURCE'],constants['EMISSION_SOURCE']
        self.assertNotEqual(legacy,new)
        self.assertEqual(legacy.split('(',1)[1],new.split('(',1)[1])
        for initial,expected in [(legacy,new),(legacy+'\n// user customization',legacy+'\n// user customization')]:
            port = SimpleNamespace(GetPortValue=lambda:initial,SetPortValue=Mock())
            node = SimpleNamespace(IsNullValue=lambda:False)
            context = dict(constants, OSL='osl.',_root=lambda graph:SimpleNamespace(FindChild=lambda name:node),
                           _input=lambda n,k:port,_begin_transaction=lambda *a:nullcontext(SimpleNamespace(Commit=Mock())))
            function('materials.py','_ensure_emission_node',context)(object())
            if expected==initial:
                port.SetPortValue.assert_not_called()
            else:
                port.SetPortValue.assert_called_once_with(expected)

    def test_camera_warning_is_informational_and_clears(self):
        camera, override = object(), object()
        bd = SimpleNamespace(GetSceneCamera=lambda doc: camera)
        op = Op({I.CAMERA: override, I.CAMERA_FACING: True, I.STATUS: 'Ready'})
        op.doc = SimpleNamespace(GetRenderBaseDraw=lambda: bd)
        state = SimpleNamespace(op=op, progress_message='Ready')
        refresh = function('plugin.py','refresh_status',{'I': I},'SplatObject')
        refresh(state)
        self.assertIn('Projection Camera differs', op[I.STATUS])
        self.assertIs(op[I.CAMERA], override)
        refresh(state)
        self.assertEqual(op[I.STATUS].count('Projection Camera differs'), 1)
        op[I.CAMERA] = camera
        refresh(state)
        self.assertEqual(op[I.STATUS], 'Ready')

    def test_initial_saved_status_is_not_erased(self):
        op = Op({I.STATUS: 'Choose a source', I.CAMERA: None})
        op.doc = None
        state = SimpleNamespace(op=op, progress_message='')
        function('plugin.py','refresh_status',{'I': I},'SplatObject')(state)
        self.assertEqual(op[I.STATUS], 'Choose a source')

    def test_error_status_is_not_replaced_by_stale_progress(self):
        op = Op({I.STATUS: 'Error: source missing', I.CAMERA: None})
        op.doc = None
        state = SimpleNamespace(op=op, progress_message='Ready')
        refresh = function('plugin.py','refresh_status',{'I': I},'SplatObject')
        refresh(state)
        self.assertEqual(op[I.STATUS], 'Error: source missing')
        state.progress_message = 'Retrying'
        refresh(state,force=True)
        self.assertEqual(op[I.STATUS], 'Retrying')

    def test_matrix_roundoff_does_not_dirty_generator(self):
        host = SimpleNamespace(DIRTYFLAGS_DATA=1, EXECUTIONRESULT_OK=0)
        cam = [(100., 0., -500.)]
        execute = function('plugin.py','Execute',dict(c4d=host,I=I,loading=loading,
            color_configuration_key=lambda doc: (0,), projection_camera=lambda op: cam[0],
            screen_projection=lambda op: None),
            'SplatObject')
        op = Op({I.CAMERA_FACING: True, I.PIXEL_VARIANCE: 0., I.SH_DEGREE: 0})
        op.SetDirty = Mock()
        state = SimpleNamespace(last_color_key=(0,), last_camera=loading.view_key((cam[0],None)), cloud=None)
        cam[0] = (100.00000000000003, -1e-14, -500.)
        execute(state,op,None,None,None,None)
        op.SetDirty.assert_not_called()
        cam[0] = (100.001,0.,-500.)
        execute(state,op,None,None,None,None)
        op.SetDirty.assert_called_once_with(1)

    def test_quality_applies_manual_sampling_and_preserves_stricter_values(self):
        names = ['RDATA_RENDERENGINE','UNDOTYPE_CHANGE',
            'REDSHIFT_RENDERER_MAX_TRACE_DEPTH_TRANSPARENCY',
            'REDSHIFT_RENDERER_BASIC_MAX_TRACE_DEPTH_TRANSPARENCY',
            'REDSHIFT_RENDERER_UNIFIED_MIN_SAMPLES','REDSHIFT_RENDERER_UNIFIED_MAX_SAMPLES',
            'REDSHIFT_RENDERER_ENABLE_AUTOMATIC_SAMPLING',
            'REDSHIFT_RENDERER_UNIFIED_ADAPTIVE_ERROR_THRESHOLD',
            'REDSHIFT_RENDERER_BASIC_UNIFIED_ADAPTIVE_ERROR_THRESHOLD']
        host = SimpleNamespace(**dict(zip(names,range(20,20+len(names)))), EventAdd=Mock())
        class VP(dict):
            def GetType(self): return 1036219
        vp = VP({host.REDSHIFT_RENDERER_MAX_TRACE_DEPTH_TRANSPARENCY: 200,
            host.REDSHIFT_RENDERER_BASIC_MAX_TRACE_DEPTH_TRANSPARENCY: 16,
            host.REDSHIFT_RENDERER_UNIFIED_MIN_SAMPLES: 32,
            host.REDSHIFT_RENDERER_UNIFIED_MAX_SAMPLES: 512,
            host.REDSHIFT_RENDERER_ENABLE_AUTOMATIC_SAMPLING: True,
            host.REDSHIFT_RENDERER_UNIFIED_ADAPTIVE_ERROR_THRESHOLD: .002,
            host.REDSHIFT_RENDERER_BASIC_UNIFIED_ADAPTIVE_ERROR_THRESHOLD: .1})
        rd = Op({host.RDATA_RENDERENGINE: 1036219})
        rd.GetFirstVideoPost = lambda: vp
        op = Op()
        op.doc = SimpleNamespace(GetActiveRenderData=lambda:rd,StartUndo=Mock(),
            EndUndo=Mock(),AddUndo=Mock())
        function('quality.py','prepare_redshift',dict(c4d=host,I=I))(op,source_marker='source identity')
        self.assertFalse(vp[host.REDSHIFT_RENDERER_ENABLE_AUTOMATIC_SAMPLING])
        self.assertEqual(vp[host.REDSHIFT_RENDERER_MAX_TRACE_DEPTH_TRANSPARENCY],200)
        self.assertEqual(vp[host.REDSHIFT_RENDERER_BASIC_MAX_TRACE_DEPTH_TRANSPARENCY],128)
        self.assertEqual(vp[host.REDSHIFT_RENDERER_UNIFIED_MAX_SAMPLES],512)
        self.assertEqual(vp[host.REDSHIFT_RENDERER_UNIFIED_ADAPTIVE_ERROR_THRESHOLD],.002)
        self.assertEqual(vp[host.REDSHIFT_RENDERER_BASIC_UNIFIED_ADAPTIVE_ERROR_THRESHOLD],.01)
        op.doc.EndUndo.assert_called_once()
        op.doc.StartUndo.assert_called_once()
        self.assertEqual(op[I.AUTO_PREPARED_SOURCE],'source identity')

    def test_auto_render_preparation_runs_once_per_file_and_respects_opt_out(self):
        op = Op({I.AUTO_REDSHIFT: True, I.AUTO_PREPARED_SOURCE: ''})
        op.doc = SimpleNamespace(GetActiveRenderData=lambda: {1:1036219})
        calls = []
        def prepare(op, source_marker=None):
            calls.append(source_marker)
            op[I.AUTO_PREPARED_SOURCE] = source_marker
        auto = function('quality.py','auto_prepare_redshift',dict(
            c4d=SimpleNamespace(RDATA_RENDERENGINE=1), I=I, json=json, prepare_redshift=prepare))
        source = ('city.sog',100,5000,3000000,.0039,False)
        self.assertTrue(auto(op,source))
        self.assertFalse(auto(op,source))
        self.assertFalse(auto(op,source[:3]+(1000,.1,True)))
        self.assertTrue(auto(op,('other.sog',)+source[1:]))
        self.assertEqual(len(calls),2)
        op[I.AUTO_REDSHIFT] = False
        self.assertFalse(auto(op,source))
        op[I.AUTO_REDSHIFT] = True
        op.doc.GetActiveRenderData = lambda: {1:0}
        self.assertFalse(auto(op,source))
        self.assertEqual(len(calls),2)


if __name__ == '__main__':
    unittest.main()
