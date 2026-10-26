"""Parallel-ray appearance, cancellable visibility and safe RAM admission."""
import math
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from test_native_actions import function
from test_color_performance import make_splat
from test_scan_scheduling import VALUES, request
from argentum_splat import core, geometry, import_budget, loading


class OrthographicAppearanceTests(unittest.TestCase):
    def test_parallel_rays_preserve_colour_across_positions_and_camera_pan(self):
        sh = (.3, -.2, .1) * 3
        splats = [make_splat(p, sh=sh, space='linear') for p in
                  ((-30., 20., 2.), (0., 0., 5.), (30., -20., 20.))]
        cloud = core.SplatCloud(splats, len(splats))
        for flip in (False, True):
            for options in ({'sh_direction': (.4, -.2, 2.)},
                            {'projection': {'orthographic': True, 'forward': (.4, -.2, 2.)}}):
                settings = dict(scale=12., flip_y=flip, sh_degree=3, **options)
                direction = (.4, .2 if flip else -.2, 2.)
                expected = geometry.correct_color(core.evaluate_sh(splats[0], direction, 3), source_space='linear')
                for camera in ((0., 0., -50.), (100., 200., -900.)):
                    actual = geometry.prepare_colors(cloud, settings, camera)
                    self.assertEqual(actual, [actual[0]]*len(splats))
                    for value, target in zip(actual[0], expected):
                        self.assertAlmostEqual(value, target, places=14)

    def test_parallel_ray_colour_updates_on_rotation_but_not_translation(self):
        values = dict(VALUES, sh_direction=(0., 0., 2.))
        before = request(values)
        pan = request(values, camera=(100., 20., -2.))
        rotated = request(dict(values, sh_direction=(1., 0., 0.)))
        perspective = request(VALUES)
        self.assertEqual(before['color_key'], pan['color_key'])
        self.assertNotEqual(before['color_key'], rotated['color_key'])
        self.assertNotEqual(before['color_key'], perspective['color_key'])
        self.assertEqual(loading.non_view_key(before), loading.non_view_key(rotated))
        self.assertEqual(request(values, degree=0)['color_key'],
                         request(VALUES, degree=0)['color_key'])

    def test_orthographic_projection_fallback_uses_forward_in_cache_key(self):
        values = dict(VALUES, projection={'orthographic': True, 'forward': (0., 1., 0.)})
        first = request(values)
        self.assertEqual(first['color_key'], request(values, camera=(12., 4., -3.))['color_key'])
        changed = dict(values, projection={'orthographic': True, 'forward': (1., 0., 0.)})
        self.assertNotEqual(first['color_key'], request(changed)['color_key'])

    def test_invalid_parallel_directions_fail_and_perspective_remains_position_dependent(self):
        cloud = core.SplatCloud([make_splat(sh=(.2, .3, .4)*3)], 1)
        for direction in ((0., 0., 0.), (math.inf, 0., 1.), (0., 1.)):
            with self.assertRaisesRegex(ValueError, 'Orthographic SH direction'):
                geometry.prepare_colors(cloud, dict(sh_degree=1, sh_direction=direction))
        settings = dict(sh_degree=1)
        self.assertNotEqual(geometry.prepare_colors(cloud, settings, (0., 0., -5.)),
                            geometry.prepare_colors(cloud, settings, (3., 0., -5.)))


class WorkerVisibilityTests(unittest.TestCase):
    def test_cancelled_quality_choice_stays_cancelled_when_camera_moves(self):
        original = request()
        owner = SimpleNamespace(request_snapshot=lambda:original, set_progress=Mock(), queued_request=original)
        dialog = SimpleNamespace(owner=lambda:owner, finish=Mock())
        cancel = function('import_choice.py', 'cancel', {'loading':loading}, 'ImportDialog')
        cancel(dialog)
        self.assertEqual(owner.cancelled_non_view, loading.non_view_key(request(camera=(100.,2.,-5.))))
        self.assertIsNone(owner.queued_request)
        dialog.finish.assert_called_once()

    def test_sparse_indices_are_built_before_worker_publication(self):
        cloud = core.SplatCloud([make_splat()]*3, 3)
        spatial = ([(0., 0., 0.)]*3, [(0., 0., 0.), (1., 0., 0.), (0., 0., 0.)],
                   [(0., 1., 0.)]*3, [(0., 0., 1.)]*3)
        req = dict(values=dict(VALUES, compact_cards=True), camera=(0., 0., -5.), analysis={})
        worker = loading.Preparation(req, cloud, spatial, [(1., 0., 0.)]*3, [(0., 1.)]*3).start()
        self.assertTrue(worker.done.wait(5))
        self.assertIsNone(worker.error)
        self.assertEqual(list(worker.result['card_indices']), [1])
        self.assertIn('visibility_seconds', worker.timings)

    def test_visibility_pass_cancels_without_publishing_partial_indices(self):
        count = 5000
        spatial = ([(0., 0., 0.)]*count, [(1., 0., 0.)]*count)
        calls = []
        def progress(stage, done, total):
            calls.append((stage, done, total))
            if done >= 2048:
                raise loading.Cancelled()
        with self.assertRaises(loading.Cancelled):
            geometry.card_indices(spatial, True, progress)
        self.assertEqual(calls[-1], ('Select visible cards', 2048, count))

    def test_staged_memory_guard_counts_visible_cards_after_preparation(self):
        # A city scan with offscreen Gaussians may fit despite the deliberately
        # broad upper estimate. Recheck actual native geometry when its CPU
        # source/buffers already consume RAM, before allocating millions of cards.
        import_budget.check_memory(9_975_598, 0, available=14.5*2**30)
        import_budget.check_card_memory(4_655_185, available=8*2**30)
        with self.assertRaisesRegex(MemoryError, 'never silently reduced'):
            import_budget.check_card_memory(9_975_598, available=8*2**30)
        count = 1_000_000
        needed = count*1024+2**30
        with self.assertRaises(MemoryError):
            import_budget.check_card_memory(count, available=needed-1)
        import_budget.check_card_memory(count, available=needed)
        import_budget.check_card_memory(0, available=0)
        for invalid in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                import_budget.check_card_memory(invalid, available=needed)
        self.assertEqual(import_budget.retained_upper_bound(9_975_598, 0), 9_975_598)


if __name__ == '__main__':
    unittest.main()
