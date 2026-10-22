"""Screen-space covariance, camera orientation and pixel-filter regression tests."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ArgentumSplat"))
from argentum_splat import core, geometry as g


def splat(position=(0., 0., 10.), scales=(.2, .4, .1), rotation=(1., 0., 0., 0.)):
    return core.Splat(position, (.2, .4, .6), .8, scales, rotation)


def projection(**overrides):
    values = dict(right=(1., 0., 0.), up=(0., 1., 0.), forward=(0., 0., 1.),
                  focal_x=800., focal_y=600., width=1600, height=1200)
    values.update(overrides)
    return values


def covariance_2d(axes):
    return (sum(a[0]*a[0] for a in axes), sum(a[0]*a[1] for a in axes),
            sum(a[1]*a[1] for a in axes))


def multiply(matrix, vector):
    return tuple(sum(a*b for a, b in zip(row, vector)) for row in matrix)


def screen(point, camera, camera_matrix, settings):
    p = multiply(camera_matrix, tuple(a-b for a, b in zip(point, camera)))
    if settings.get("orthographic"):
        return p[0]/settings["pixel_world_x"], p[1]/settings["pixel_world_y"]
    return settings["focal_x"]*p[0]/p[2], settings["focal_y"]*p[1]/p[2]


class ProjectedCardTests(unittest.TestCase):
    def test_pixel_ridge_matches_doubled_projection_coordinate_convention(self):
        # A shader with focal = viewport_width * projection[0][0] uses twice
        # the actual pixel focal length. Its 0.3 ridge is 0.075 pixel squared.
        source = splat(scales=(.00001,.00003,.00002))
        standard = projection()
        doubled = dict(standard, focal_x=standard['focal_x']*2,
                       focal_y=standard['focal_y']*2)
        a = g.projected_card_axes(source,(0.,0.,0.),1.,1.,False,standard,.075)
        b = g.projected_card_axes(source,(0.,0.,0.),1.,1.,False,doubled,.3)
        for actual, expected in zip(a,b):
            self.assertVector(actual,expected)

    def assertVector(self, actual, expected, places=8):
        for a, e in zip(actual, expected):
            self.assertAlmostEqual(a, e, places=places)

    def assertScreenCovariance(self, source, camera, settings, camera_matrix, variance=.3):
        center, u, v, normal = g.projected_card_axes(source, camera, 1., 1., False,
                                                    settings, variance)
        center_pixel = screen(center, camera, camera_matrix, settings)
        screen_axes = []
        for axis in (u, v):
            tip = tuple(c+a/3. for c, a in zip(center, axis))
            pixel = screen(tip, camera, camera_matrix, settings)
            screen_axes.append(tuple(a-b for a, b in zip(pixel, center_pixel)))
        actual = covariance_2d(screen_axes)

        # A finite difference of the perspective map independently recovers
        # its derivative, including covariance along camera depth off axis.
        projected_source_axes = []
        epsilon = 1e-5
        for axis in core.gaussian_axes(source, global_scale=1., flip_y=False):
            plus = screen(tuple(c+epsilon*a for c, a in zip(center, axis)),
                          camera, camera_matrix, settings)
            minus = screen(tuple(c-epsilon*a for c, a in zip(center, axis)),
                           camera, camera_matrix, settings)
            projected_source_axes.append(tuple((a-b)/(2.*epsilon) for a, b in zip(plus, minus)))
        xx, xy, yy = covariance_2d(projected_source_axes)
        for a, e in zip(actual, (xx+variance, xy, yy+variance)):
            self.assertTrue(math.isclose(a, e, rel_tol=3e-8, abs_tol=3e-7), (actual, (xx, xy, yy)))
        self.assertGreaterEqual(g.dot(normal, g.sub(camera, center)), 0.)
        self.assertAlmostEqual(math.hypot(*normal), 1.)

    def test_perspective_off_axis_depth_covariance_matches_image_jacobian(self):
        source = splat((3., -2., 10.), scales=(.2, .4, 2.), rotation=(.7, .2, .3, .6))
        self.assertScreenCovariance(source, (0., 0., 0.), projection(),
                                    ((1., 0., 0.), (0., 1., 0.), (0., 0., 1.)))

    def test_camera_roll_translation_and_direction_are_respected(self):
        settings = projection(right=(0., 0., -1.), up=(0., 1., 0.), forward=(1., 0., 0.))
        camera = (-7., 3., 4.)
        source = splat((3., -2., 1.), scales=(.2, .4, .7), rotation=(.7, .2, .3, .6))
        self.assertScreenCovariance(source, camera, settings,
                                    ((0., 0., -1.), (0., 1., 0.), (1., 0., 0.)))

    def test_full_affine_camera_basis_preserves_nonuniform_scale_and_shear(self):
        # Full inverse-transform columns, deliberately nonunit/nonorthogonal.
        settings = projection(right=(.5, 0., 0.), up=(-.3, 2., 0.),
                              forward=(.04, -4./15., 2./3.))
        world_to_camera = ((2., .3, 0.), (0., .5, .2), (0., 0., 1.5))
        source = splat((3., -2., 10.), scales=(.2, .4, .7), rotation=(.7, .2, .3, .6))
        self.assertScreenCovariance(source, (1., 1., 0.), settings, world_to_camera)

    def test_reflected_affine_frame_keeps_camera_facing_normal(self):
        settings = projection(right=(-.5, 0., 0.), up=(0., 2., 0.), forward=(0., 0., 1.))
        self.assertScreenCovariance(splat((3., -2., 10.)), (0., 0., 0.), settings,
                                    ((-2., 0., 0.), (0., .5, 0.), (0., 0., 1.)))

    def test_pixel_filter_is_resolution_and_focal_length_dependent(self):
        source = splat(scales=(.01, .01, .01))
        low = projection(focal_x=100., focal_y=100., width=200, height=200)
        high = projection(focal_x=200., focal_y=200., width=400, height=400)
        _, u1, v1, _ = g.projected_card_axes(source, (0., 0., 0.), 1., 1., False, low)
        _, u2, v2, _ = g.projected_card_axes(source, (0., 0., 0.), 1., 1., False, high)
        sigma1 = math.hypot(*u1)/3.
        sigma2 = math.hypot(*u2)/3.
        self.assertAlmostEqual(sigma1*sigma1, .01**2+.3*(10./100.)**2)
        self.assertAlmostEqual(sigma2*sigma2, .01**2+.3*(10./200.)**2)
        self.assertGreater(sigma1, sigma2)
        self.assertAlmostEqual(math.hypot(*v1), math.hypot(*u1))
        self.assertAlmostEqual(math.hypot(*v2), math.hypot(*u2))

    def test_pixel_aspect_uses_independent_horizontal_vertical_focal_lengths(self):
        settings = projection(focal_x=800., focal_y=1600.)
        self.assertScreenCovariance(splat((2., 3., 10.)), (0., 0., 0.), settings,
                                    ((1., 0., 0.), (0., 1., 0.), (0., 0., 1.)))

    def test_orthographic_covariance_and_filter_are_depth_independent(self):
        settings = projection(orthographic=True, pixel_world_x=.02, pixel_world_y=.03)
        first = splat((3., -2., 10.), rotation=(.7, .2, .3, .6))
        distant = splat((3., -2., 1000.), rotation=(.7, .2, .3, .6))
        self.assertScreenCovariance(first, (0., 0., 0.), settings,
                                    ((1., 0., 0.), (0., 1., 0.), (0., 0., 1.)))
        first_axes = g.projected_card_axes(first, (0., 0., 0.), 1., 1., False, settings)[1:]
        distant_axes = g.projected_card_axes(distant, (0., 0., 0.), 1., 1., False, settings)[1:]
        self.assertEqual(first_axes, distant_axes)

    def test_behind_or_near_camera_uses_finite_legacy_fallback(self):
        for depth in (0., 1e-20, -1., -100.):
            source = splat((0., 0., depth))
            actual = g.projected_card_axes(source, (0., 0., 0.), 1., 1., False, projection())
            expected = g.card_axes(source, (0., 0., 0.), 1., 1., False, True)
            self.assertEqual(actual, expected)
            self.assertTrue(all(math.isfinite(v) for vector in actual for v in vector))

    def test_zero_variance_or_missing_projection_keeps_legacy_path_exactly(self):
        source = splat((2., -3., 10.))
        camera = (0., 0., 0.)
        old = g.card_axes(source, camera, 1., 1., False, True)
        self.assertEqual(g.projected_card_axes(source, camera, 1., 1., False, {}, 0.), old)
        cloud = core.SplatCloud([source], 1)
        original = g.prepare_geometry(cloud, dict(scale=1., camera_facing=True), camera)
        self.assertEqual(g.prepare_geometry(cloud, dict(scale=1., camera_facing=True,
                                                       projection={}, pixel_variance=0.), camera), original)
        self.assertEqual(g.prepare_geometry(cloud, dict(scale=1., camera_facing=True,
                                                       pixel_variance=.3), camera), original)

    def test_surface_aligned_cards_ignore_optional_projection(self):
        cloud = core.SplatCloud([splat()], 1)
        original = g.prepare_geometry(cloud, dict(scale=1., camera_facing=False))
        self.assertEqual(g.prepare_geometry(cloud, dict(scale=1., camera_facing=False,
                                                       projection={}, pixel_variance=.3)), original)

    def test_preparation_uses_projection_and_preserves_progress(self):
        cloud = core.SplatCloud([splat()], 1)
        progress = []
        prepared = g.prepare_geometry(cloud, dict(scale=1., camera_facing=True,
            projection=projection(), pixel_variance=.3), (0., 0., 0.),
            lambda *args: progress.append(args))
        expected = g.projected_card_axes(cloud.splats[0], (0., 0., 0.), 1., 1., False, projection())
        for component, scalar in zip(prepared, expected):
            self.assertEqual(component, [scalar])
        self.assertEqual(progress, [("Prepare geometry", 0, 1)])

    def test_invalid_projection_inputs_are_rejected(self):
        for invalid in (projection(forward=(0., 0., 0.)), projection(focal_x=0.),
                        projection(width=0.), projection(up=(math.nan, 1., 0.)),
                        projection(orthographic=True, pixel_world_x=-1., pixel_world_y=.1)):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    g.projected_card_axes(splat(), (0., 0., 0.), 1., 1., False, invalid)
        for variance in (-.1, math.nan, math.inf):
            with self.assertRaises(ValueError):
                g.projected_card_axes(splat(), (0., 0., 0.), 1., 1., False, projection(), variance)


if __name__ == "__main__":
    unittest.main()
