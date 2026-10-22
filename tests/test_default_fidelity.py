"""New-object quality, retained source data, and opt-in migration contracts."""
import ast
import math
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from test_native_actions import function, I, Op, ROOT
from test_core import ROW, ply_header
from argentum_splat import core


class DefaultFidelityTests(unittest.TestCase):
    def new_object(self):
        op = Op()
        init = function('plugin.py', 'Init', {'I': I}, 'SplatObject')
        self.assertTrue(init(SimpleNamespace(), op))
        return op

    def test_new_object_keeps_dense_faint_source_records(self):
        op = self.new_object()
        # Just over the old cap, with alpha below the old 0.02 threshold.
        # Losing either density or faint records breaks the import regression.
        count = 262145
        row = list(ROW)
        row[6] = math.log(.01 / .99)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'dense-faint.ply'
            path.write_bytes(ply_header(count, 'binary_little_endian') +
                             struct.pack('<14f', *row) * count)
            cloud = core.load(path, max_splats=op[I.MAX_SPLATS],
                              min_opacity=op[I.MIN_OPACITY], compact=True)
        self.assertEqual(cloud.total_count, count)
        self.assertEqual(len(cloud.splats), count)
        self.assertAlmostEqual(cloud.splats[-1].opacity, .01, places=6)

    def test_new_objects_use_captured_colour_and_valid_projection(self):
        op = self.new_object()
        self.assertEqual([op[k] for k in (I.EMISSION, I.DIFFUSE, I.SUBSURFACE)],
                         [1., 0., 0.])
        self.assertTrue(op[I.CAMERA_FACING])
        self.assertEqual(op[I.SH_DEGREE], 3)
        self.assertEqual(op[I.PIXEL_VARIANCE], .075)
        self.assertEqual(op[I.SMOOTHING], 0)
        self.assertEqual(op[I.COLOR_MODE], 0)
        self.assertTrue(op[I.POINT_PREVIEW])
        self.assertEqual(op[I.PREVIEW_COUNT], 10000)
        self.assertEqual(op[I.NUM_GAUSSIANS], 65536)

    def test_clone_init_preserves_custom_values_and_links(self):
        op = self.new_object()
        op.update({I.DIFFUSE: .7, I.EMISSION: .2, I.MAX_SPLATS: 8000,
                   I.MIN_OPACITY: .15, I.PIXEL_VARIANCE: 0.,
                   I.GAMMA: 1.7, I.CAMERA: object(), I.MATERIAL: object()})
        before = dict(op)
        function('plugin.py', 'Init', {'I': I}, 'SplatObject')(
            SimpleNamespace(), op, isCloneInit=True)
        self.assertEqual(op, before)

    def test_explicit_preset_preserves_artistic_edits_and_higher_retention(self):
        op = self.new_object()
        op.update({I.MIN_OPACITY: .001, I.COLOR_MODE: 1, I.GAMMA: 1.4,
                   I.HUE: 25., I.SCALE: 137., I.FLIP_Y: True,
                   I.DIFFUSE: .5, I.CAMERA: object(), I.MATERIAL: object()})
        doc = SimpleNamespace(StartUndo=Mock(), AddUndo=Mock(), EndUndo=Mock())
        state = SimpleNamespace(start_scan=Mock())
        op.doc = doc
        op.GetNodeData = lambda: state
        op.SetDirty = Mock()
        material = SimpleNamespace(update_material=Mock())
        host = SimpleNamespace(UNDOTYPE_CHANGE=1, DIRTYFLAGS_DATA=2, EventAdd=Mock())
        mx = SimpleNamespace(nodes=SimpleNamespace(UNDO_MODE=SimpleNamespace(ADD=1)))
        function('quality.py', 'apply_detail_preset',
                 dict(I=I, c4d=host, maxon=mx, materials=material))(op)
        self.assertEqual(op[I.MIN_OPACITY], .001)
        self.assertEqual([op[k] for k in (I.COLOR_MODE,I.GAMMA,I.HUE,I.SCALE,I.FLIP_Y)],
                         [1,1.4,25.,137.,True])
        for key, value in I.SOURCE_FIDELITY.items():
            if key != I.MIN_OPACITY:
                self.assertEqual(op[key], value)
        self.assertIsNone(op[I.CAMERA])
        state.start_scan.assert_called_once_with()
        doc.StartUndo.assert_called_once_with()
        doc.EndUndo.assert_called_once_with()
        self.assertEqual(doc.AddUndo.call_count, 2)
        self.assertEqual(material.update_material.call_args.args[1],
                         dict(emission_weight=1., diffuse_weight=0., subsurface_weight=0.))

    def test_new_material_fallbacks_match_new_object_weights(self):
        tree = ast.parse((ROOT/'argentum_splat/materials.py').read_text(encoding='utf8'))
        assignment = next(n for n in tree.body if isinstance(n, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == 'DEFAULTS'
                                  for t in n.targets))
        context = {'I': I}
        exec(compile(ast.Module(body=[assignment], type_ignores=[]), 'defaults', 'exec'), context)
        weights = function('materials.py', '_weights', dict(DEFAULTS=context['DEFAULTS'],
            _setting=function('materials.py', '_setting', dict(DEFAULTS=context['DEFAULTS'],
                math=math, MaterialError=ValueError))))
        self.assertEqual(weights({}), dict(emission_weight=1., diffuse_weight=0., subsurface_weight=0.))
        # Explicit weights from an old scene still win over the new fallback.
        old = dict(emission_weight=.64, diffuse_weight=1., subsurface_weight=.4)
        self.assertEqual(weights(old), old)


if __name__ == '__main__':
    unittest.main()
