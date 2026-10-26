"""Behavioral tests for editable Gaussian geometry and every color control."""
import math
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ArgentumSplat"))
from argentum_splat import core, geometry as g


def splat(position=(0., 0., 0.), scales=(2., 1., .1),
          rotation=(1., 0., 0., 0.), color=(.4, .2, .1), sh=(), space="linear"):
    return core.Splat(position, core.source_to_linear(color, space), .8,
                      scales, rotation, tuple(sh), color, space)


def covariance(axes):
    return [[sum(a[i]*a[j] for a in axes) for j in range(3)] for i in range(3)]


class GeometryTests(unittest.TestCase):
    def assertVector(self, actual, expected, places=10):
        self.assertEqual(len(actual), len(expected))
        for a, e in zip(actual, expected):
            self.assertAlmostEqual(a, e, places=places)

    def test_color_neutral_and_linear_transfer_mode(self):
        color = (.25, .5, .75)
        self.assertVector(g.correct_color(color, source_space="linear"), color)
        decoded = (.05087608817155679, .21404114048223255, .5225215539683921)
        self.assertVector(g.correct_color(color, source_space="srgb"), decoded)
        self.assertVector(g.correct_color(color, color_mode=1, source_space="srgb"), color)
        self.assertVector(g.correct_color((.04045, 0., 1.)), (.04045/12.92, 0., 1.))

    def test_gamma_is_functional_and_neutral_at_one(self):
        self.assertVector(g.correct_color((.25, .25, .25), gamma=2., color_mode=1),
                          (.5, .5, .5))
        self.assertVector(g.correct_color((.5, .5, .5), gamma=.5, color_mode=1),
                          (.25, .25, .25))

    def test_contrast_pivots_about_middle_gray(self):
        self.assertVector(g.correct_color((.25, .5, .75), contrast=1., color_mode=1),
                          (0., .5, 1.))
        self.assertVector(g.correct_color((.1, .3, .9), contrast=0., color_mode=1),
                          (.5, .5, .5))

    def test_hue_rotates_red_to_green_and_wraps(self):
        self.assertVector(g.correct_color((1., 0., 0.), hue=120., color_mode=1), (0., 1., 0.))
        self.assertVector(g.correct_color((1., 0., 0.), hue=-120., color_mode=1), (0., 0., 1.))
        self.assertVector(g.correct_color((.9, .3, .2), hue=360., color_mode=1), (.9, .3, .2))

    def test_saturation_zero_and_boost(self):
        self.assertVector(g.correct_color((.8, .4, .4), saturation=0., color_mode=1),
                          (.8, .8, .8))
        self.assertVector(g.correct_color((.8, .4, .4), saturation=2., color_mode=1),
                          (.8, 0., 0.))

    def test_level_zero_and_multiplication(self):
        self.assertVector(g.correct_color((.2, .4, .6), level=0., color_mode=1), (0., 0., 0.))
        self.assertVector(g.correct_color((.2, .4, .6), level=2., color_mode=1), (.4, .8, 1.2))

    def test_highlight_limit_above_one_works_in_default_mode(self):
        # The source-domain cap must survive source-to-linear conversion.
        rgb = g.correct_color((2., 1.5, .5), highlight=1.5)
        self.assertAlmostEqual(rgb[0], ((1.5+.055)/1.055)**2.4)
        self.assertEqual(rgb[0], rgb[1])
        self.assertGreater(rgb[0], 1.)
        limited = g.correct_color((2., 1.5, .5), highlight=.6, source_space="linear")
        self.assertVector(limited, (.6, .6, .5))

    def test_color_controls_reject_nan_infinity_and_invalid_ranges(self):
        for key in ("gamma", "contrast", "hue", "saturation", "level", "highlight"):
            for bad in (math.nan, math.inf):
                with self.subTest(key=key, bad=bad):
                    with self.assertRaises(ValueError):
                        g.correct_color((.1, .2, .3), **{key: bad})
        for key in ("gamma", "contrast", "saturation", "level", "highlight"):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    g.correct_color((.1, .2, .3), **{key: -1.})
        with self.assertRaises(ValueError):
            g.correct_color((math.nan, .1, .2))

    def test_surface_cards_follow_largest_gaussian_axes(self):
        s = splat(position=(1., 2., 3.))
        center, u, v, normal = g.card_axes(s, (0., 0., -20.), 10., 2., True, False)
        self.assertVector(center, (10., -20., 30.))
        self.assertAlmostEqual(math.hypot(*u), 120.)  # 3 sigma * scale * splat_scale
        self.assertAlmostEqual(math.hypot(*v), 60.)
        self.assertAlmostEqual(g.dot(u, v), 0.)
        self.assertGreater(g.dot(normal, g.sub((0., 0., -20.), center)), 0.)
        self.assertVector(g.norm(g.cross(u, v)), normal)

    def test_surface_quaternion_rotates_ellipse(self):
        angle = math.pi/4
        s = splat(rotation=(math.cos(angle/2), 0., 0., math.sin(angle/2)))
        _, u, _, _ = g.card_axes(s, (0., 0., 20.), 1., 1., False, False)
        self.assertVector(u, (6./math.sqrt(2), 6./math.sqrt(2), 0.))

    def test_camera_facing_axes_perpendicular_to_view(self):
        s = splat(position=(1., 2., 3.), rotation=(.7, .2, .3, .6))
        camera = (9., -4., -12.)
        center, u, v, normal = g.card_axes(s, camera, 1., 1., False, True)
        view = g.norm(g.sub(camera, center))
        self.assertVector(normal, view)
        self.assertAlmostEqual(g.dot(u, view), 0.)
        self.assertAlmostEqual(g.dot(v, view), 0.)
        self.assertAlmostEqual(g.dot(u, v), 0.)
        self.assertVector(g.norm(g.cross(u, v)), normal)

    def test_camera_facing_preserves_full_projected_covariance(self):
        # Independent 3x3 projection P C P, including off-diagonal covariance.
        s = splat(scales=(3., .7, .2), rotation=(.7, .2, .3, .6))
        camera = (3., 5., -8.)
        for flip in (False, True):
            with self.subTest(flip=flip):
                center, u, v, normal = g.card_axes(s, camera, 2., 1.3, flip, True)
                native = covariance(core.gaussian_axes(s, 2., 1.3, flip))
                p = [[(1. if i == j else 0.)-normal[i]*normal[j] for j in range(3)]
                     for i in range(3)]
                expected = [[sum(p[i][a]*native[a][b]*p[b][j]
                                 for a in range(3) for b in range(3))
                             for j in range(3)] for i in range(3)]
                actual = covariance((g.mul(u, 1./3), g.mul(v, 1./3)))
                for i in range(3):
                    self.assertVector(actual[i], expected[i], places=9)

    def test_projected_tiny_and_highly_anisotropic_scales_are_not_inflated(self):
        s = splat(scales=(1e4, 1e-5, 1e-6))
        _, u, v, _ = g.card_axes(s, (0., 0., -20.), 1., 1., False, True)
        self.assertAlmostEqual(math.hypot(*u), 3e4)
        self.assertAlmostEqual(math.hypot(*v)/3e-5, 1., places=9)
        tiny = splat(scales=(2e-12, 1e-12, 1e-13))
        _, u, v, _ = g.card_axes(tiny, (0., 0., -20.), 1., 1., False, True)
        self.assertAlmostEqual(math.hypot(*u)/6e-12, 1., places=9)
        self.assertAlmostEqual(math.hypot(*v)/3e-12, 1., places=9)

    def test_camera_on_center_is_finite_and_camera_movement_changes_cards(self):
        s = splat()
        at_center = g.card_axes(s, (0., 0., 0.), 1., 1., False, True)
        self.assertTrue(all(math.isfinite(v) for vec in at_center for v in vec))
        front = g.card_axes(s, (0., 0., -20.), 1., 1., False, True)
        side = g.card_axes(s, (20., 0., 0.), 1., 1., False, True)
        self.assertNotEqual(front[1:3], side[1:3])
        self.assertAlmostEqual(math.hypot(*side[1]), 3.)
        self.assertAlmostEqual(math.hypot(*side[2]), .3)

    def test_smoothing_reduces_neighbor_normal_angle_and_keeps_unit_length(self):
        centers = [(0., 0., 0.), (.1, 0., 0.)]
        normals = [(0., 0., 1.), (math.sqrt(.5), 0., math.sqrt(.5))]
        original_dot = g.dot(*normals)
        once = g.smooth_normals(centers, normals, [1., 1.], 1)
        twice = g.smooth_normals(centers, normals, [1., 1.], 2)
        self.assertGreater(g.dot(*once), original_dot)
        self.assertGreater(g.dot(*twice), g.dot(*once))
        self.assertEqual(g.smooth_normals(centers, normals, [1., 1.], 0), normals)
        for n in twice:
            self.assertAlmostEqual(math.hypot(*n), 1.)

    def test_smoothing_does_not_cancel_opposite_hemispheres_or_join_distant_points(self):
        centers = [(0., 0., 0.), (.1, 0., 0.)]
        normals = [(0., 0., 1.), (0., 0., -1.)]
        self.assertEqual(g.smooth_normals(centers, normals, [1., 1.], 3), normals)
        distant = [(0., 0., 0.), (1000., 0., 0.)]
        tilted = [(0., 0., 1.), (1., 0., 0.)]
        self.assertEqual(g.smooth_normals(distant, tilted, [1., 1.], 3), tilted)

    def test_smoothing_empty_and_mismatched_arrays(self):
        self.assertEqual(g.smooth_normals([], [], [], 2), [])
        with self.assertRaises(ValueError):
            g.smooth_normals([(0, 0, 0)], [], [], 2)

    def test_prepare_sh_degree_strength_camera_and_flip_y(self):
        rest = [0.] * 45
        rest[0] = .2  # red l1: -C1 * y
        rest[15+5] = .2  # green l2: C2 * (2zz-xx-yy)
        rest[30+11] = .2  # blue l3: C3 * z*(2zz-3xx-3yy)
        s = splat(position=(0., 1., 1.), sh=rest)
        cloud = core.SplatCloud([s], 1)
        settings = dict(scale=1., sh_degree=0, color_mode=1)
        baseline = g.prepare(cloud, settings, camera=(0., 0., 0.))[4][0]
        self.assertVector(baseline, s.raw_color)
        colors = []
        for degree in (1, 2, 3):
            settings["sh_degree"] = degree
            colors.append(g.prepare(cloud, settings, camera=(0., 0., 0.))[4][0])
        self.assertNotEqual(colors[0][0], baseline[0])
        self.assertAlmostEqual(colors[0][1], baseline[1])
        self.assertNotEqual(colors[1][1], colors[0][1])
        self.assertAlmostEqual(colors[1][2], colors[0][2])
        self.assertNotEqual(colors[2][2], colors[1][2])
        settings["sh_strength"] = 0.
        self.assertVector(g.prepare(cloud, settings, camera=(0., 0., 0.))[4][0], baseline)
        settings.update(sh_strength=1., flip_y=True)
        flipped = g.prepare(cloud, settings, camera=(0., 0., 0.))[4][0]
        self.assertVector(flipped, colors[2])
        settings["flip_y"] = False
        moved = g.prepare(cloud, settings, camera=(0., 3., 0.))[4][0]
        self.assertNotEqual(moved, colors[2])

    def test_prepare_smoothing_changes_shading_normals_but_not_geometry(self):
        a = splat(position=(0., 0., 0.))
        angle = math.pi/4
        b = splat(position=(.1, 0., 0.),
                  rotation=(math.cos(angle/2), math.sin(angle/2), 0., 0.))
        cloud = core.SplatCloud([a, b], 2)
        settings = dict(scale=1., smoothing=0)
        raw = g.prepare(cloud, settings)
        settings["smoothing"] = 2
        smooth = g.prepare(cloud, settings)
        self.assertEqual(raw[:3], smooth[:3])
        self.assertEqual(raw[4], smooth[4])
        self.assertNotEqual(raw[3], smooth[3])
        self.assertGreater(g.dot(*smooth[3]), g.dot(*raw[3]))

    def test_robust_normalization(self):
        self.assertVector(g.norm((1e300, 1e300, 0.)), (math.sqrt(.5), math.sqrt(.5), 0.))
        self.assertVector(g.norm((1e-300, 0., 0.)), (1., 0., 0.))

    def test_color_pass_reuses_centers_without_rebuilding_spatial_data(self):
        cloud = core.SplatCloud([splat(), splat(position=(1., 2., 3.))], 2)
        settings = dict(scale=1., camera_facing=True, smoothing=2, gamma=1.)
        spatial = g.prepare_geometry(cloud, settings)
        with mock.patch.object(g, "card_axes", side_effect=AssertionError("axes rebuilt")), \
                mock.patch.object(g, "smooth_normals", side_effect=AssertionError("normals rebuilt")):
            neutral = g.prepare_colors(cloud, settings, centers=spatial[0])
            changed = g.prepare_colors(cloud, dict(settings, gamma=2.), centers=spatial[0])
        self.assertNotEqual(neutral, changed)
        self.assertEqual(spatial, g.prepare_geometry(cloud, dict(settings, gamma=2.)))

    def test_separate_preparation_keeps_sh_direction_and_corrected_color(self):
        rest = [.2, -.1, .3, -.2, .1, .2, .1, .2, -.1]
        cloud = core.SplatCloud([splat(position=(1., 2., 3.), sh=rest, space="srgb")], 1)
        settings = dict(scale=2., flip_y=True, sh_degree=1, sh_strength=.7, gamma=1.4)
        camera = (-3., -1., 8.)
        spatial = g.prepare_geometry(cloud, settings, camera)
        cached = g.prepare_colors(cloud, settings, camera, spatial[0])
        uncached = g.prepare_colors(cloud, settings, camera)
        self.assertEqual(cached, uncached)
        center = core.transform_position(cloud.splats[0].position, 2., True)
        direction = g.sub(center, camera)
        direction = (direction[0], -direction[1], direction[2])
        expected = g.correct_color(core.evaluate_sh(cloud.splats[0], direction, 1, .7),
                                   gamma=1.4, source_space="srgb")
        self.assertVector(cached[0], expected)

    def test_sh0_color_preparation_needs_no_camera_geometry(self):
        cloud = core.SplatCloud([splat()], 1)
        with mock.patch.object(core, "transform_position",
                               side_effect=AssertionError("unnecessary position transform")), \
                mock.patch.object(g, "norm", side_effect=AssertionError("unnecessary view normalization")):
            result = g.prepare_colors(cloud, dict(sh_degree=3), camera=(4., 5., 6.))
        self.assertVector(result[0], cloud.splats[0].raw_color)

    def test_color_pass_rejects_mismatched_cached_centers(self):
        with self.assertRaises(ValueError):
            g.prepare_colors(core.SplatCloud([splat()], 1), {}, centers=[])

    def test_support_boundary_retains_normalized_shader_cutoff(self):
        # Evaluate the shader's forward expression, independently of the
        # inverse used to size geometry. The outward tolerance must retain the
        # last visible sample without keeping a meaningful transparent border.
        def shader_alpha(opacity, x, y=0.):
            floor = math.exp(-4.)
            falloff = max(0., (math.exp(-4.5*(x*x+y*y))-floor)/(1.-floor))
            return min(1., max(0., opacity))*falloff

        for opacity in (.004, .01, .5, 1.):
            with self.subTest(opacity=opacity):
                support = g.gaussian_support(opacity)
                self.assertGreater(shader_alpha(opacity, support-2e-6), 1./255.)
                self.assertLess(shader_alpha(opacity, support), 1./255.)
                # The cut is the bounding square of a radial field: an edge
                # or corner outside it cannot contain any visible sample.
                for y in (0., support*.5, support, 1.):
                    self.assertLess(shader_alpha(opacity, support+1e-8, y), 1./255.)
                old = min(1., math.sqrt(2.*math.log(opacity*255.)/9.)+1e-6)
                self.assertLess(support, old)

    def test_support_zero_area_cutoff_clamping_and_tighter_opaque_bound(self):
        for opacity in (-1., 0., 1./255.-1e-12, 1./255.):
            self.assertEqual(g.gaussian_support(opacity), 0.)
        self.assertGreater(g.gaussian_support(1./255.+1e-12), 0.)
        self.assertEqual(g.gaussian_support(2.), g.gaussian_support(1.))
        # Fully opaque cards lose over 15% of their empty bounding-square area
        # compared with the old full 3-sigma extent.
        self.assertLess(g.gaussian_support(1.)**2, .85)


if __name__ == "__main__":
    unittest.main()
