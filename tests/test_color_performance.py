"""Batch color parity, cancellation and optional representative CPU benchmark.

Run directly with --benchmark for a 262,144-splat before/after measurement.
The scalar public helpers serve as the independent rendering reference; tests
have no timing threshold and require neither Cinema 4D nor NumPy.
"""
import json
import math
from pathlib import Path
import random
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ArgentumSplat"))
from argentum_splat import core, geometry


def reference_colors(cloud, settings, camera=(0., 0., -500.), centers=None):
    """Scalar evaluation used before the batch optimization."""
    degree = settings.get("sh_degree", 0)
    strength = settings.get("sh_strength", 1.)
    scale = settings.get("scale", 100.)
    flip_y = settings.get("flip_y", False)
    correction = {key: settings.get(key, default) for key, default in (
        ("gamma", 1.), ("contrast", .5), ("hue", 0.), ("saturation", 1.),
        ("level", 1.), ("highlight", 3.), ("color_mode", 0))}
    result = []
    for index, splat in enumerate(cloud.splats):
        direction = (0., 0., 1.)
        if degree and strength and splat.sh:
            center = (centers[index] if centers is not None else
                      core.transform_position(splat.position, scale, flip_y))
            direction = geometry.sub(center, camera)
            if flip_y:
                direction = (direction[0], -direction[1], direction[2])
            direction = geometry.norm(direction)
        rgb = core.evaluate_sh(splat, direction, degree, strength)
        result.append(geometry.correct_color(rgb, **correction,
                      source_space=splat.input_color_space))
    return result


def make_splat(position=(1., 2., 3.), rgb=(.2, .4, .6), sh=(), space="srgb"):
    return core.Splat(position, rgb, .8, (.1, .1, .1), (1., 0., 0., 0.),
                      tuple(sh), tuple(rgb), space)


class ColorBatchTests(unittest.TestCase):
    def assertColorsClose(self, actual, expected):
        self.assertEqual(len(actual), len(expected))
        for a, e in zip(actual, expected):
            for component, reference in zip(a, e):
                self.assertTrue(math.isclose(component, reference, rel_tol=2e-12, abs_tol=2e-12),
                                (a, e))

    def test_mixed_sh_and_color_spaces_match_scalar_controls(self):
        rng = random.Random(4431)
        splats = []
        for index in range(96):
            size = (0, 9, 24, 45)[index % 4]
            splats.append(make_splat(
                tuple(rng.uniform(-5., 5.) for _ in range(3)),
                tuple(rng.uniform(-.2, 3.) for _ in range(3)),
                tuple(rng.uniform(-.2, .2) for _ in range(size)),
                ("srgb", "linear", "sRGB", "linearRGB")[index % 4]))
        cloud = core.SplatCloud(splats, len(splats))
        corrections = ({}, {"gamma": 1.7}, {"contrast": .8},
                       {"hue": -120.}, {"saturation": 0.},
                       {"level": 1.5, "highlight": 2.},
                       {"gamma": .7, "contrast": .2, "hue": 390.,
                        "saturation": 2., "level": .6, "highlight": .8})
        for degree in range(4):
            for correction in corrections:
                for mode in (0, 1):
                    settings = dict(correction, sh_degree=degree, color_mode=mode,
                                    sh_strength=.7, scale=2., flip_y=True)
                    with self.subTest(settings=settings):
                        self.assertColorsClose(
                            geometry.prepare_colors(cloud, settings, (4., -3., 2.)),
                            reference_colors(cloud, settings, (4., -3., 2.)))

    def test_normalization_handles_coincident_and_extreme_view_vectors(self):
        rest = tuple((i % 7 - 3) * .1 for i in range(45))
        splats = [make_splat(sh=rest) for _ in range(3)]
        cloud = core.SplatCloud(splats, len(splats))
        centers = [(0., 0., 0.), (1e300, -1e300, 1e300), (1e-300, 1e-300, -1e-300)]
        for flip in (False, True):
            settings = dict(sh_degree=3, flip_y=flip)
            self.assertColorsClose(
                geometry.prepare_colors(cloud, settings, (0., 0., 0.), centers),
                reference_colors(cloud, settings, (0., 0., 0.), centers))

    def test_zero_strength_and_dc_keep_finite_coefficient_validation(self):
        for settings in ({"sh_degree": 0}, {"sh_degree": 3, "sh_strength": 0.}):
            for splat in (make_splat(rgb=(math.nan, .2, .3)),
                          make_splat(sh=(0.,) * 8 + (math.inf,)),
                          make_splat(sh=(0.,) * 10)):
                cloud = core.SplatCloud([splat], 1)
                with self.subTest(settings=settings, splat=splat):
                    with self.assertRaises(ValueError):
                        geometry.prepare_colors(cloud, settings)

    def test_invalid_controls_are_still_rejected(self):
        cloud = core.SplatCloud([make_splat()], 1)
        for control in ("gamma", "contrast", "hue", "saturation", "level", "highlight"):
            for invalid in (math.nan, math.inf):
                with self.subTest(control=control, invalid=invalid):
                    with self.assertRaises(ValueError):
                        geometry.prepare_colors(cloud, {control: invalid})
        for settings in ({"gamma": 0.}, {"highlight": 0.}, {"contrast": -1.},
                         {"saturation": -1.}, {"level": -1.}, {"color_mode": 2},
                         {"sh_degree": True}, {"sh_degree": 4}, {"sh_strength": math.inf}):
            with self.subTest(settings=settings):
                with self.assertRaises(ValueError):
                    geometry.prepare_colors(cloud, settings)

    def test_source_space_validation_is_preserved(self):
        for space in ("auto", "not-a-color-space"):
            cloud = core.SplatCloud([make_splat(space=space)], 1)
            with self.assertRaises(ValueError):
                geometry.prepare_colors(cloud, {})
            self.assertColorsClose(geometry.prepare_colors(cloud, {"color_mode": 1}),
                                   reference_colors(cloud, {"color_mode": 1}))

    def test_gamma_overflow_is_not_hidden_by_highlight_clipping(self):
        cloud = core.SplatCloud([make_splat(rgb=(1e300, .2, .3))], 1)
        with self.assertRaisesRegex(ValueError, "Gamma correction overflow"):
            geometry.prepare_colors(cloud, {"gamma": .01})

    def test_cancellation_interrupts_the_next_batch(self):
        class Cancelled(Exception):
            pass
        cloud = core.SplatCloud([make_splat()] * 5000, 5000)
        progress_calls = []

        def progress(stage, done, total):
            progress_calls.append((stage, done, total))
            if done >= 2048:
                raise Cancelled()

        with self.assertRaises(Cancelled):
            geometry.prepare_colors(cloud, {}, progress=progress)
        self.assertEqual(progress_calls, [("Prepare colour", 0, 5000),
                                          ("Prepare colour", 2048, 5000)])

    def test_empty_cloud_remains_empty(self):
        self.assertEqual(geometry.prepare_colors(core.SplatCloud([], 0), {"gamma": 0.}), [])


def benchmark():
    count = 262144
    for degree in (0, 3):
        sh = tuple(((i*7) % 17 - 8)*.0125 for i in range(45)) if degree else ()
        splats = [make_splat(
            ((i % 511)/111., ((i//511) % 509)/107., (i % 31)/47.),
            ((i % 251)/250., (i % 193)/192., (i % 137)/136.), sh)
            for i in range(count)]
        cloud = core.SplatCloud(splats, count)
        centers = [tuple(p*100. for p in s.position) for s in splats]
        settings = {"sh_degree": degree}
        started = time.perf_counter()
        expected = reference_colors(cloud, settings, centers=centers)
        baseline = time.perf_counter()-started
        started = time.perf_counter()
        actual = geometry.prepare_colors(cloud, settings, centers=centers)
        optimized = time.perf_counter()-started
        error = max(abs(x-y) for a, e in zip(actual, expected) for x, y in zip(a, e))
        print(json.dumps(dict(count=count, degree=degree, before_seconds=baseline,
                              after_seconds=optimized, speedup=baseline/optimized,
                              max_absolute_error=error)), flush=True)


if __name__ == "__main__":
    if "--benchmark" in sys.argv:
        benchmark()
    else:
        unittest.main()
