"""Classic camera adapter and its contract with pure Gaussian projection."""
import math
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from test_native_actions import function
from test_color_performance import make_splat
from argentum_splat import core, geometry, loading, ids as I


class Vector(tuple):
    x = property(lambda self: self[0])
    y = property(lambda self: self[1])
    z = property(lambda self: self[2])


class Matrix:
    def __init__(self, columns=((1., 0., 0.), (0., 1., 0.), (0., 0., 1.)), inverse=None):
        self.v1, self.v2, self.v3 = (Vector(v) for v in columns)
        self.inverse = inverse

    def __invert__(self):
        return self.inverse or self

    def MulV(self, vector):
        return Vector(sum(axis[i]*value for axis, value in
                          zip((self.v1, self.v2, self.v3), vector)) for i in range(3))


class Camera(dict):
    def CheckType(self, value):
        return self.type == value

    def GetMg(self):
        return self.matrix


class Object(dict):
    def __missing__(self, key):
        return 0

    def GetDocument(self):
        return self.document

    def GetMg(self):
        return self.matrix

    def GetUp(self):
        return None


class NativeProjectionTests(unittest.TestCase):
    def setUp(self):
        symbols = ('Ocamera', 'Pperspective', 'Pparallel', 'Pfront', 'Pmilitary',
                   'CAMERA_PROJECTION', 'CAMERA_ZOOM', 'CAMERAOBJECT_FOV',
                   'RDATA_XRES', 'RDATA_YRES', 'RDATA_PIXELASPECT',
                   'CAMERAOBJECT_FILM_OFFSET_X', 'CAMERAOBJECT_FILM_OFFSET_Y',
                   'CAMERA_FOCUS', 'CAMERAOBJECT_APERTURE', 'Orscamera',
                   'RSCAMERAOBJECT_PROJECTION', 'RSCAMERAOBJECT_PROJECTION_PERSPECTIVE',
                   'RSCAMERAOBJECT_PROJECTION_ORTHOGRAPHIC', 'RSCAMERAOBJECT_SENSOR_SHIFT')
        self.host = host = SimpleNamespace(**dict(zip(symbols, range(700, 700+len(symbols)))))
        self.camera = camera = Camera({host.CAMERA_PROJECTION: host.Pparallel,
                                       host.CAMERA_ZOOM: .5, host.CAMERAOBJECT_FOV: 1.,
                                       host.CAMERAOBJECT_FILM_OFFSET_X: 0.,
                                       host.CAMERAOBJECT_FILM_OFFSET_Y: 0.,
                                       host.CAMERA_FOCUS: 35., host.CAMERAOBJECT_APERTURE: 36.})
        camera.type, camera.matrix = host.Ocamera, Matrix()
        self.render = {host.RDATA_XRES: 1920., host.RDATA_YRES: 1080., host.RDATA_PIXELASPECT: 1.}
        self.draw = SimpleNamespace(GetSceneCamera=lambda doc: camera, GetEditorCamera=lambda: camera)
        self.op = Object({I.CAMERA: camera, I.SCALE: 1., I.SPLAT_SCALE: 1.,
                          I.CAMERA_FACING: True, I.GAMMA: 1., I.CONTRAST: 1.,
                          I.SATURATION: 1., I.LEVEL: 1., I.HIGHLIGHT: 1.,
                          I.SH_DEGREE: 1, I.SH_STRENGTH: 1., I.PIXEL_VARIANCE: .075})
        self.op.matrix = Matrix()
        self.op.document = SimpleNamespace(GetRenderBaseDraw=lambda: self.draw,
                                          GetActiveRenderData=lambda: self.render)
        self.context = dict(c4d=host, I=I, math=math,
                            input_source=SimpleNamespace(coordinate_flip=lambda *args: False))
        for name in ('vector_tuple', 'orthographic_direction', 'screen_projection', 'settings'):
            function('plugin.py', name, self.context)

    def test_parallel_render_pixel_scale_uses_zoom_resolution_and_aspect(self):
        for width, height, aspect in ((1920, 1080, 1.), (1080, 1920, 1.), (1920, 1080, 2.)):
            for zoom in (.5, 2.):
                with self.subTest(width=width, height=height, aspect=aspect, zoom=zoom):
                    self.render.update({self.host.RDATA_XRES: width, self.host.RDATA_YRES: height,
                                        self.host.RDATA_PIXELASPECT: aspect})
                    self.camera[self.host.CAMERA_ZOOM] = zoom
                    result = self.context['screen_projection'](self.op)
                    self.assertTrue(result['orthographic'])
                    self.assertEqual(result['pixel_world_x'], 1024./(width*zoom))
                    self.assertEqual(result['pixel_world_y'], 1024./(width*zoom*aspect))
                    self.assertEqual((result['width'], result['height']), (width, height))
                    self.assertNotIn('focal_x', result)

    def test_editor_camera_fallback_preserves_full_affine_axes_and_ray(self):
        self.op[I.CAMERA] = None
        self.draw.GetSceneCamera = lambda doc: None
        self.camera.matrix = Matrix(((0., 0., -1.), (0., 1., 0.), (1., 0., 0.)))
        self.op.matrix = Matrix(inverse=Matrix(((.5, 0., 0.), (0., 2., 0.), (0., 0., 1.5))))
        projection = self.context['screen_projection'](self.op)
        self.assertEqual(projection['right'], (0., 0., -1.5))
        self.assertEqual(projection['up'], (0., 2., 0.))
        self.assertEqual(projection['forward'], (.5, 0., 0.))
        self.assertEqual(self.context['orthographic_direction'](self.op), (.5, 0., 0.))

    def test_parallel_adapter_drives_filtered_covariance_with_constant_plane(self):
        values = self.context['settings'](self.op)
        positions = ((3., -2., 10.), (-7., 4., 1000.))
        splats = [core.Splat(p, (.2, .4, .6), .8, (.2, .4, 2.), (.7, .2, .3, .6)) for p in positions]
        spatial = geometry.prepare_geometry(core.SplatCloud(splats, 2), values, (0., 0., 0.))
        projection = values['projection']
        pixel_x, pixel_y = projection['pixel_world_x'], projection['pixel_world_y']
        axes = core.gaussian_axes(splats[0], global_scale=1., flip_y=False)
        expected = (sum(a[0]**2 for a in axes)/pixel_x**2+.075,
                    sum(a[0]*a[1] for a in axes)/(pixel_x*pixel_y),
                    sum(a[1]**2 for a in axes)/pixel_y**2+.075)
        for index in range(2):
            u, v = spatial[1][index], spatial[2][index]
            projected = [(a[0]/(3.*pixel_x), a[1]/(3.*pixel_y)) for a in (u, v)]
            actual = (sum(a[0]**2 for a in projected), sum(a[0]*a[1] for a in projected),
                      sum(a[1]**2 for a in projected))
            for value, target in zip(actual, expected):
                self.assertAlmostEqual(value, target, places=6)
            self.assertEqual(spatial[3][index], (0., 0., -1.))
            self.assertEqual(u[2], 0.)
            self.assertEqual(v[2], 0.)
        self.assertEqual(spatial[1][0], spatial[1][1])
        self.assertEqual(spatial[2][0], spatial[2][1])

    def test_surface_cards_still_receive_parallel_sh_direction(self):
        self.op[I.CAMERA_FACING] = False
        values = self.context['settings'](self.op)
        self.assertNotIn('projection', values)
        self.assertEqual(values['sh_direction'], (0., 0., 1.))
        splats = [make_splat(p, sh=(.3, -.2, .1)*3, space='linear') for p in
                  ((-30., 20., 2.), (30., -20., 20.))]
        cloud = core.SplatCloud(splats, 2)
        first = geometry.prepare_colors(cloud, values, (0., 0., -50.))
        moved = geometry.prepare_colors(cloud, values, (100., 200., -900.))
        self.assertEqual(first[0], first[1])
        self.assertEqual(list(first), list(moved))

    def test_unverified_fixed_oblique_and_nonclassic_parallel_modes_are_not_projected(self):
        for mode, camera_type in ((self.host.Pfront, self.host.Ocamera),
                                  (self.host.Pmilitary, self.host.Ocamera),
                                  (self.host.Pparallel, -1)):
            self.camera[self.host.CAMERA_PROJECTION] = mode
            self.camera.type = camera_type
            self.assertIsNone(self.context['screen_projection'](self.op))
            self.assertIsNone(self.context['orthographic_direction'](self.op))

    def test_perspective_keeps_existing_focal_contract(self):
        self.camera[self.host.CAMERA_PROJECTION] = self.host.Pperspective
        self.render[self.host.RDATA_PIXELASPECT] = 2.
        result = self.context['screen_projection'](self.op)
        focal = 1920./(2.*math.tan(.5))
        self.assertEqual(result['focal_x'], focal)
        self.assertEqual(result['focal_y'], 2.*focal)
        self.assertNotIn('orthographic', result)
        self.assertIsNone(self.context['orthographic_direction'](self.op))

    def test_unknown_camera_uses_safe_covariance_fallback(self):
        # A third-party camera can reuse projection IDs while exposing
        # different FOV/sensor fields. Unsupported types remain safe.
        self.camera[self.host.CAMERA_PROJECTION] = self.host.Pperspective
        self.camera[self.host.CAMERAOBJECT_FOV] = None
        self.camera.type = -1
        values = self.context['settings'](self.op)
        self.assertIsNone(values['projection'])
        self.assertIsNone(values['sh_direction'])
        cloud = core.SplatCloud([make_splat((0., 0., 10.))], 1)
        spatial = geometry.prepare_geometry(cloud, values, (0., 0., 0.))
        self.assertTrue(any(value != 0. for value in spatial[1][0]))
        # A third-party camera must not be accepted merely because it happens
        # to have a value at the classic FOV parameter ID.
        self.camera[self.host.CAMERAOBJECT_FOV] = 1.
        self.assertIsNone(self.context['screen_projection'](self.op))

    def redshift(self, parallel=False):
        self.camera.type = self.host.Orscamera
        self.camera[self.host.RSCAMERAOBJECT_PROJECTION] = (
            self.host.RSCAMERAOBJECT_PROJECTION_ORTHOGRAPHIC if parallel else
            self.host.RSCAMERAOBJECT_PROJECTION_PERSPECTIVE)
        self.camera[self.host.RSCAMERAOBJECT_SENSOR_SHIFT] = Vector((0., 0., 0.))
        self.camera[self.host.CAMERAOBJECT_FOV] = None

    def test_redshift_uses_host_evaluated_aperture_for_all_sensor_fits(self):
        self.redshift()
        # These effective gates were measured via native WS after Horizontal,
        # Vertical, Crop, Fit and Square evaluation, including portrait/PA2.
        for aperture in (36., 42.666666666666664, 13.5, 85.33333333333333, 24., 32.):
            with self.subTest(aperture=aperture):
                self.camera[self.host.CAMERAOBJECT_APERTURE] = aperture
                result = self.context['screen_projection'](self.op)
                self.assertAlmostEqual(result['focal_x'], 1920.*35./aperture)
                self.assertEqual(result['focal_y'], result['focal_x'])
        self.camera[self.host.CAMERAOBJECT_FOV] = .6605947096585073
        self.camera[self.host.CAMERAOBJECT_APERTURE] = 42.666666666666664
        result = self.context['screen_projection'](self.op)
        self.assertAlmostEqual(result['focal_x'], 1575.)
        self.assertNotAlmostEqual(result['focal_x'], 1920./(2.*math.tan(.6605947096585073/2.)))

    def test_redshift_invalid_intrinsics_and_other_projections_use_fallback(self):
        self.redshift()
        for field in (self.host.CAMERA_FOCUS, self.host.CAMERAOBJECT_APERTURE):
            original = self.camera[field]
            for value in (None, 0., -1., math.nan, math.inf):
                with self.subTest(field=field, value=value):
                    self.camera[field] = value
                    self.assertIsNone(self.context['screen_projection'](self.op))
            self.camera[field] = original
        self.camera[self.host.RSCAMERAOBJECT_PROJECTION] = -123
        self.assertIsNone(self.context['screen_projection'](self.op))
        self.assertIsNone(self.context['orthographic_direction'](self.op))

    def test_redshift_parallel_uses_constant_sh_ray_with_and_without_camera_facing(self):
        self.redshift(parallel=True)
        self.camera[self.host.CAMERA_ZOOM] = 1.
        values = self.context['settings'](self.op)
        self.assertTrue(values['projection']['orthographic'])
        self.assertEqual(values['projection']['pixel_world_x'], 1024./1920.)
        self.assertEqual(values['sh_direction'], (0., 0., 1.))
        self.op[I.CAMERA_FACING] = False
        self.assertEqual(self.context['settings'](self.op)['sh_direction'], (0., 0., 1.))

    def test_classic_and_rs_shifts_use_image_fraction_and_dirty_only_projected_geometry(self):
        for redshift in (False, True):
            if redshift:
                self.redshift()
            baseline = self.context['settings'](self.op)
            self.assertNotIn('offset_x', baseline['projection'])
            self.assertNotIn('offset_y', baseline['projection'])
            if redshift:
                self.camera[self.host.RSCAMERAOBJECT_SENSOR_SHIFT] = Vector((.25, -.2, 0.))
            else:
                self.camera[self.host.CAMERAOBJECT_FILM_OFFSET_X] = .25
                self.camera[self.host.CAMERAOBJECT_FILM_OFFSET_Y] = -.2
            shifted = self.context['settings'](self.op)
            self.assertEqual(shifted['projection']['offset_x'], -480.)
            self.assertEqual(shifted['projection']['offset_y'], -216.)
            a = loading.preparation_keys(('source',), baseline, (0., 0., 0.), True, (0,))
            b = loading.preparation_keys(('source',), shifted, (0., 0., 0.), True, (0,))
            self.assertNotEqual(a[0], b[0])
            self.assertEqual(a[1], b[1])

    def test_invalid_camera_shift_uses_safe_fallback(self):
        for value in (None, math.nan, math.inf):
            self.camera[self.host.CAMERAOBJECT_FILM_OFFSET_X] = value
            self.assertIsNone(self.context['screen_projection'](self.op))
        self.redshift()
        self.camera[self.host.RSCAMERAOBJECT_SENSOR_SHIFT] = None
        self.assertIsNone(self.context['screen_projection'](self.op))

    def test_adapter_matches_all_91_recorded_cinema_2027_projection_states(self):
        fixture = json.loads((Path(__file__).parent/'fixtures/camera_projection_2027.json').read_text())
        self.assertEqual(len(fixture['cases']), 91)
        for case in fixture['cases']:
            with self.subTest(case=case['name']):
                self.setUp()
                if case['kind'] == 'redshift':
                    self.redshift(parallel=case['parallel'])
                else:
                    self.camera[self.host.CAMERA_PROJECTION] = (
                        self.host.Pparallel if case['parallel'] else self.host.Pperspective)
                for name, value in case['parameters'].items():
                    if name == 'RSCAMERAOBJECT_SENSOR_SHIFT' and value is not None:
                        value = Vector(value)
                    self.camera[getattr(self.host, name)] = value
                width, height, aspect = case['render']
                self.render.update({self.host.RDATA_XRES: width, self.host.RDATA_YRES: height,
                                    self.host.RDATA_PIXELASPECT: aspect})
                projection = self.context['screen_projection'](self.op)
                self.assertIsNotNone(projection)
                viewport_x, viewport_y = case['viewport']
                image_x = min(viewport_x, viewport_y*width*aspect/height)
                image_y = image_x/(width*aspect/height)
                if case['parallel']:
                    scale_x, scale_y = 1./projection['pixel_world_x'], 1./projection['pixel_world_y']
                    self.assertEqual(self.context['orthographic_direction'](self.op), (0., 0., 1.))
                else:
                    scale_x, scale_y = projection['focal_x'], projection['focal_y']
                scale_x, scale_y = scale_x*image_x/width, scale_y*image_y/height
                self.assertAlmostEqual(scale_x, case['native_scale'][0], places=9)
                self.assertAlmostEqual(-scale_y, case['native_scale'][1], places=9)
                # BaseDraw truncates its fitted viewport size only for film
                # shift. Render image dimensions themselves are integral.
                offset_x = projection.get('offset_x', 0.)*int(image_x)/width
                offset_y = projection.get('offset_y', 0.)*int(image_y)/height
                for point, expected in zip(case['points'], case['native_screen']):
                    x, y, z = point
                    depth = 1. if case['parallel'] else z
                    actual = (viewport_x*.5 + offset_x + x*scale_x/depth,
                              viewport_y*.5 - offset_y - y*scale_y/depth)
                    for value, target in zip(actual, expected):
                        self.assertAlmostEqual(value, target, places=8)

    def test_unavailable_or_invalid_perspective_fov_uses_safe_fallback(self):
        self.camera[self.host.CAMERA_PROJECTION] = self.host.Pperspective
        for fov in (None, 'unavailable', 0., -1., math.pi, 4., math.inf, math.nan):
            with self.subTest(fov=fov):
                self.camera[self.host.CAMERAOBJECT_FOV] = fov
                self.assertIsNone(self.context['screen_projection'](self.op))
        self.camera[self.host.CAMERA_PROJECTION] = None
        self.assertIsNone(self.context['screen_projection'](self.op))

    def test_invalid_parallel_zoom_fails_before_geometry(self):
        for zoom in (0., -1., math.inf, math.nan):
            self.camera[self.host.CAMERA_ZOOM] = zoom
            with self.assertRaisesRegex(ValueError, 'Parallel camera zoom'):
                self.context['screen_projection'](self.op)


if __name__ == '__main__':
    unittest.main()
