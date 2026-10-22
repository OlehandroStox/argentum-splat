"""Cache and scheduling regressions without a Cinema 4D installation.

The native host is intentionally a small stub. The production request, queue,
cancellation and publication methods run unchanged; no renderer is simulated.
"""
import ast
import importlib.util
from copy import deepcopy
import os
from pathlib import Path
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import Mock, patch


PLUGIN_ROOT = Path(__file__).resolve().parents[1] / "ArgentumSplat"
sys.path.insert(0, str(PLUGIN_ROOT))
import argentum_splat
from argentum_splat import ids as I, loading


VALUES = dict(scale=100., splat_scale=1., flip_y=False, camera_facing=False,
    smoothing=2, sh_degree=1, sh_strength=1., gamma=1., contrast=.5,
    hue=0., saturation=1., level=1., highlight=3., color_mode=0,
    emission_weight=1., diffuse_weight=0., subsurface_weight=0.)
CAMERA_A = (0., 0., -500.)
CAMERA_B = (120., 30., -450.)
PROJECTION = dict(right=(1., 0., 0.), up=(0., 1., 0.), forward=(0., 0., 1.),
    focal_x=1000., focal_y=1000., width=1920., height=1080.)


def request(values=None, camera=CAMERA_A, degree=3, source=("scan",),
            color_config=(0,), opacity=1., material="material", weights=None):
    values = dict(VALUES if values is None else values)
    spatial, color = loading.preparation_keys(source, values, camera, degree, color_config)
    weights = weights or tuple(values[k] for k in
        ("emission_weight", "diffuse_weight", "subsurface_weight"))
    return dict(source_key=source, values=values, camera=camera,
        spatial_key=spatial, color_key=color, opacity=opacity, weights=weights,
        material=material, key=(spatial, color, opacity, weights, material))


class PreparationKeyTests(unittest.TestCase):
    def test_native_matrix_roundtrip_noise_reuses_prepared_arrays(self):
        projection = dict(PROJECTION,
            right=(.1201368379573916, 0., -.9927573420356051),
            up=(.6381320883339479, -.7660444689420768, .07722246720874705),
            forward=(.7604962708680126, .6427875789117672, .09203016023345037))
        restored = dict(projection,
            right=(.12013683795739186, 0., -.9927573420356051),
            up=(.6381320883339479, -.7660444689420768, .07722246720874722),
            forward=(.7604962708680126, .6427875789117672, .09203016023345056))
        values = dict(VALUES, camera_facing=True, pixel_variance=.3, projection=projection)
        original = deepcopy(values)
        a = request(values, camera=(-259.70237255096436, -269.5059537887573, -31.427440047264067))
        b = request(dict(values, projection=restored),
                    camera=(-259.7023725509644, -269.5059537887573, -31.4274400472641))
        self.assertEqual(a['key'], b['key'])
        self.assertEqual(values, original)

    def test_real_small_camera_changes_still_invalidate(self):
        values = dict(VALUES, camera_facing=True, pixel_variance=.3, projection=dict(PROJECTION))
        a = request(values)
        b = request(values, camera=(.00001, 0., -500.))
        self.assertNotEqual(a['spatial_key'], b['spatial_key'])
        self.assertNotEqual(a['color_key'], b['color_key'])
        changed = dict(PROJECTION, focal_x=1000.00001)
        self.assertNotEqual(a['spatial_key'], request(dict(values, projection=changed))['spatial_key'])

    def test_view_key_preserves_tiny_affine_bases_and_suppresses_axis_noise(self):
        self.assertEqual(loading.view_key((1e-15, 0., 0.)),
                         loading.view_key((1e-15, 2e-31, -1e-31)))
        self.assertNotEqual(loading.view_key((1e-15, 0., 0.)), (0., 0., 0.))
        self.assertNotEqual(loading.view_key((1e-15, 0., 0.)),
                            loading.view_key((1.001e-15, 0., 0.)))

    def test_user_controls_are_not_quantized_with_view_keys(self):
        a = request()
        b = request(dict(VALUES, gamma=1.0000000000001))
        self.assertNotEqual(a['color_key'], b['color_key'])

    def test_sh0_ignores_camera_and_inactive_sh_controls(self):
        a = request(degree=0)
        b = request(dict(VALUES, scale=700., flip_y=True, sh_degree=3,
                         sh_strength=4.), camera=CAMERA_B, degree=0)
        self.assertEqual(a["color_key"], b["color_key"])
        self.assertNotEqual(a["spatial_key"], b["spatial_key"])

    def test_zero_strength_ignores_view_scale_flip_and_requested_degree(self):
        a = request(dict(VALUES, sh_strength=0.), degree=3)
        b = request(dict(VALUES, scale=200., flip_y=True, sh_degree=3,
                         sh_strength=0.), camera=CAMERA_B, degree=3)
        self.assertEqual(a["color_key"], b["color_key"])

    def test_requested_degree_is_capped_at_stored_degree(self):
        a = request(dict(VALUES, sh_degree=1), degree=1)
        b = request(dict(VALUES, sh_degree=3), degree=1)
        self.assertEqual(a["key"], b["key"])

    def test_boolean_unknown_sh_preserves_requested_degree(self):
        a = request(dict(VALUES, sh_degree=1), degree=True)
        b = request(dict(VALUES, sh_degree=3), degree=True)
        self.assertNotEqual(a["color_key"], b["color_key"])

    def test_camera_only_change_has_same_non_view_key(self):
        for facing in (False, True):
            values = dict(VALUES, camera_facing=facing)
            a = request(values, camera=CAMERA_A)
            b = request(values, camera=CAMERA_B)
            with self.subTest(camera_facing=facing):
                self.assertNotEqual(a["key"], b["key"])
                self.assertEqual(loading.non_view_key(a), loading.non_view_key(b))

    def test_non_view_key_retains_all_static_changes(self):
        baseline = request()
        changed = {
            "source": request(source=("other",)),
            "scale": request(dict(VALUES, scale=101.)),
            "splat_scale": request(dict(VALUES, splat_scale=1.1)),
            "flip": request(dict(VALUES, flip_y=True)),
            "facing": request(dict(VALUES, camera_facing=True)),
            "smoothing": request(dict(VALUES, smoothing=3)),
            "SH": request(dict(VALUES, sh_degree=2)),
            "strength": request(dict(VALUES, sh_strength=.8)),
            "gamma": request(dict(VALUES, gamma=1.1)),
            "contrast": request(dict(VALUES, contrast=.6)),
            "hue": request(dict(VALUES, hue=10.)),
            "saturation": request(dict(VALUES, saturation=.8)),
            "level": request(dict(VALUES, level=.7)),
            "highlight": request(dict(VALUES, highlight=2.)),
            "color_mode": request(dict(VALUES, color_mode=1)),
            "document_colour": request(color_config=(2, "ACEScg")),
            "opacity": request(opacity=.5),
            "weights": request(weights=(.8, .2, .1)),
            "material": request(material="other material"),
        }
        for name, value in changed.items():
            with self.subTest(change=name):
                self.assertNotEqual(loading.non_view_key(baseline), loading.non_view_key(value))

    def test_projection_changes_invalidate_geometry_without_recolouring_sh0(self):
        values = dict(VALUES, camera_facing=True, pixel_variance=.3,
                      projection=dict(PROJECTION))
        baseline = request(values, degree=0)
        changes = {
            "camera_rotation": dict(PROJECTION, right=(0., 0., -1.), forward=(1., 0., 0.)),
            "field_of_view": dict(PROJECTION, focal_x=1500., focal_y=1500.),
            "resolution": dict(PROJECTION, width=3840., height=2160., focal_x=2000., focal_y=2000.),
            "pixel_aspect": dict(PROJECTION, focal_y=2000.),
            "object_scale": dict(PROJECTION, right=(.5, 0., 0.), up=(0., .25, 0.)),
            "object_shear": dict(PROJECTION, right=(1., .2, 0.)),
        }
        for name, projection in changes.items():
            changed = request(dict(values, projection=projection), degree=0)
            with self.subTest(change=name):
                self.assertNotEqual(baseline["spatial_key"], changed["spatial_key"])
                self.assertEqual(baseline["color_key"], changed["color_key"])
                self.assertEqual(loading.non_view_key(baseline), loading.non_view_key(changed))

    def test_pixel_variance_invalidates_only_geometry(self):
        values = dict(VALUES, camera_facing=True, pixel_variance=.3,
                      projection=dict(PROJECTION))
        baseline = request(values, degree=0)
        for variance in (0., .5, 1.):
            changed = request(dict(values, pixel_variance=variance), degree=0)
            with self.subTest(variance=variance):
                self.assertNotEqual(baseline["spatial_key"], changed["spatial_key"])
                self.assertEqual(baseline["color_key"], changed["color_key"])
                self.assertNotEqual(loading.non_view_key(baseline), loading.non_view_key(changed))

    def test_non_view_pixel_filter_comparison_needs_no_values_dictionary(self):
        a = request(dict(VALUES, camera_facing=True, pixel_variance=.3, projection=dict(PROJECTION)))
        b = request(dict(VALUES, camera_facing=True, pixel_variance=.6, projection=dict(PROJECTION)))
        del a["values"], b["values"]
        self.assertNotEqual(loading.non_view_key(a), loading.non_view_key(b))

    def test_pixel_filter_without_projection_is_inactive(self):
        a = request(dict(VALUES, camera_facing=True, pixel_variance=0., projection=None))
        b = request(dict(VALUES, camera_facing=True, pixel_variance=.6, projection=None))
        self.assertEqual(a["key"], b["key"])
        self.assertEqual(loading.non_view_key(a), loading.non_view_key(b))

    def test_inactive_projection_does_not_invalidate_legacy_geometry(self):
        for camera_facing, variance in ((False, .3), (False, 0.)):
            values = dict(VALUES, camera_facing=camera_facing, pixel_variance=variance,
                          projection=dict(PROJECTION))
            changed = dict(values, projection=dict(PROJECTION, focal_x=2000.))
            with self.subTest(camera_facing=camera_facing, variance=variance):
                self.assertEqual(request(values)["key"], request(changed)["key"])

    def test_zero_filter_still_tracks_projection(self):
        values = dict(VALUES, camera_facing=True, pixel_variance=0., projection=dict(PROJECTION))
        changed = dict(values, projection=dict(PROJECTION, focal_x=2000.))
        self.assertNotEqual(request(values)['spatial_key'], request(changed)['spatial_key'])
        self.assertEqual(request(values, degree=0)['color_key'], request(changed, degree=0)['color_key'])

    def test_projection_key_is_an_immutable_snapshot(self):
        projection = dict(PROJECTION)
        values = dict(VALUES, camera_facing=True, pixel_variance=.3, projection=projection)
        baseline = request(values)
        saved = deepcopy(baseline["spatial_key"])
        projection["focal_x"] = 2000.
        self.assertEqual(baseline["spatial_key"], saved)
        self.assertNotEqual(request(values)["spatial_key"], saved)


class FakeWorker:
    def __init__(self, request, cloud=None, spatial=None, colors=None, bounds=None):
        self.request = request
        self.cloud, self.spatial, self.colors, self.bounds = cloud, spatial, colors, bounds
        self.cancelled = threading.Event()
        self.done = threading.Event()
        self.error = None
        self.result = None
        self.timings = {}
        self.status = ("Preparing", .5)
        self.started = False
        self.phase = 'reading'
        self.analysis = None

    def start(self):
        self.started = True
        return self


class FakeObject(dict):
    def __init__(self, source):
        super().__init__(I.DEFAULTS)
        self[I.AUTO_FRAME] = False  # These tests exercise an existing framed scene.
        self[I.FILE] = str(source)
        self[I.MATERIAL] = "material"
        self.values = dict(VALUES)
        self.camera = CAMERA_A
        self.document = object()
        self.dirty = []

    def __getitem__(self, key):
        return self.get(key)

    def GetDocument(self):
        return self.document

    def SetDirty(self, flag):
        self.dirty.append(flag)


class InteractiveSchedulingTests(unittest.TestCase):
    def start_patch(self, context):
        value = context.start()
        self.addCleanup(context.stop)
        return value

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        source = Path(self.tmp.name) / "scan.splat"
        source.write_bytes(b"fixture: parser replaced by FakeWorker")
        self.op = FakeObject(source)
        self.plugin = types.ModuleType("argentum_splat.plugin")
        self.plugin.JOBS = set()
        self.plugin.CLOUD_CACHE = {}
        # Production settings() builds fresh projection data for every snapshot.
        self.plugin.settings = lambda op: deepcopy(op.values)
        self.plugin.projection_camera = lambda op: op.camera
        self.plugin.color_configuration_key = lambda doc: (0,)
        self.plugin.is_open_document = lambda doc: True
        self.plugin.converter = lambda: types.SimpleNamespace(needs_conversion=lambda path: False)
        self.host = types.SimpleNamespace(StopAllThreads=lambda: None, DIRTYFLAGS_DATA=1)
        self.assets = types.SimpleNamespace(resolve_path=lambda op, path: str(path or ""))
        self.start_patch(patch.dict(sys.modules, {"c4d": self.host,
            "argentum_splat.plugin": self.plugin}))
        self.start_patch(patch.object(argentum_splat, "plugin", self.plugin, create=True))
        self.start_patch(patch.object(argentum_splat, "assets", self.assets, create=True))
        self.quality = types.SimpleNamespace(auto_prepare_redshift=Mock(return_value=False))
        self.start_patch(patch.dict(sys.modules, {'argentum_splat.quality': self.quality}))
        self.setup = types.SimpleNamespace(needs_initial_analysis=Mock(return_value=False),
            frame_scan=Mock(), finish_import=Mock())
        self.start_patch(patch.dict(sys.modules, {'argentum_splat.scene_setup': self.setup}))
        self.start_patch(patch.object(argentum_splat,'scene_setup',self.setup,create=True))
        spec = importlib.util.spec_from_file_location("argentum_splat._scheduling_test",
            PLUGIN_ROOT / "argentum_splat" / "scene_jobs.py")
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.start_patch(patch.object(self.module.loading, "Preparation", FakeWorker))

        class Harness(self.module.InteractiveScan):
            def __init__(self, op):
                self.op = op
                self.job = None
                self.cloud = None
                self.load_key = None
                self.spatial = self.colors = self.bounds = None
                self.spatial_key = self.color_key = None
                self.progress_amount = None
                self.progress_message = ""
                self.shown = self.closed = 0
                self.scan_state()

            def show_progress(self):
                self.shown += 1

            def close_progress(self):
                self.closed += 1

            def set_progress(self, message, amount=None):
                self.progress_message, self.progress_amount = message, amount

        self.instance = Harness(self.op)

    def source_loader(self, live_instances, cache, reader):
        """Run the real loader method without importing C4D's native SDK types."""
        tree = ast.parse((PLUGIN_ROOT / "argentum_splat" / "plugin.py").read_text(encoding="utf8"))
        object_class = next(node for node in tree.body
                            if isinstance(node, ast.ClassDef) and node.name == "SplatObject")
        method = next(node for node in object_class.body
                      if isinstance(node, ast.FunctionDef) and node.name == "ensure_loaded")
        isolated = ast.Module(body=[method], type_ignores=[])
        context = dict(document_path=self.assets.resolve_path, converter=self.plugin.converter,
            os=os, Path=Path, I=I, CLOUD_CACHE=cache, INSTANCES=live_instances,
            core=types.SimpleNamespace(load=reader))
        exec(compile(isolated, "plugin.py:ensure_loaded", "exec"), context)
        return context["ensure_loaded"]

    def install_ready_cloud(self, degree=3):
        instance = self.instance
        instance.cloud = types.SimpleNamespace(metadata={"sh_degree": degree}, splats=[object()], total_count=1)
        instance.load_key = instance.source_key(self.op)
        instance.spatial = ([(0., 0., 0.)], [(1., 0., 0.)], [(0., 1., 0.)], [(0., 0., 1.)])
        instance.colors = [(1., .5, .1)]
        instance.bounds = [(0., 1.)] * 3
        snapshot = instance.request_snapshot()
        instance.spatial_key, instance.color_key = snapshot["spatial_key"], snapshot["color_key"]
        instance.ready_request = snapshot["key"]
        instance.mesh_template = object()
        return snapshot

    def test_automatic_camera_update_is_silent_and_reuses_source_and_geometry(self):
        self.install_ready_cloud()
        self.op.camera = CAMERA_B
        self.instance.start_scan()
        job = self.instance.job
        self.assertIsNotNone(job)
        self.assertFalse(job["foreground"])
        self.assertEqual(self.instance.shown, 0)
        self.assertTrue(job["worker"].started)
        self.assertIs(job["worker"].cloud, self.instance.cloud)
        self.assertIs(job["worker"].spatial, self.instance.spatial)
        self.assertIsNone(job["worker"].colors)

    def test_initial_analysis_transitions_without_reading_or_publishing_twice(self):
        self.setup.needs_initial_analysis.return_value=True
        self.instance.start_scan(explicit=True)
        job=self.instance.job
        first=job['worker']
        self.assertTrue(first.request['analyse_only'])
        source=object();report={'retained':2}
        first.result=dict(cloud=source,analysis=report,analyse_only=True)
        first.timings={'read_seconds':2.5}
        first.done.set()
        self.setup.frame_scan.side_effect=lambda *a,**k:setattr(self.op,'camera',CAMERA_B)
        self.instance.poll_scan()
        second=job['worker']
        self.assertIsNot(second,first)
        self.assertIs(second.cloud,source)
        self.assertIs(second.request['analysis'],report)
        self.assertFalse(second.request['analyse_only'])
        self.assertEqual(second.request['camera'],CAMERA_B)
        self.assertTrue(second.started)
        self.assertIsNone(self.instance.mesh_template)

    def test_camera_assistance_failure_does_not_abort_valid_scan(self):
        self.setup.needs_initial_analysis.return_value=True
        self.setup.frame_scan.side_effect=ValueError('camera unavailable')
        self.instance.start_scan()
        first=self.instance.job['worker']
        first.result=dict(cloud=object(),analysis={},analyse_only=True)
        first.done.set()
        self.instance.poll_scan()
        next_worker=self.instance.job['worker']
        self.assertTrue(next_worker.started)
        self.assertIn('camera unavailable',next_worker.request['analysis']['frame_warning'])

    def test_render_clone_reuses_live_cloud_evicted_by_two_other_scans(self):
        source_key = self.instance.source_key(self.op)
        cloud = object()
        other_keys = [("scan-b",) + source_key[1:], ("scan-c",) + source_key[1:]]
        other_clouds = [object(), object()]
        cache = dict(zip(other_keys, other_clouds))
        owners = [types.SimpleNamespace(load_key=source_key, cloud=cloud)]
        owners.extend(types.SimpleNamespace(load_key=key, cloud=value)
                      for key, value in zip(other_keys, other_clouds))
        reader = Mock(side_effect=AssertionError("A retained live scan must not be read again"))
        ensure_loaded = self.source_loader(owners, cache, reader)
        self.assertIs(ensure_loaded(self.instance, self.op), cloud)
        self.assertIs(self.instance.cloud, cloud)
        self.assertEqual(self.instance.load_key, source_key)
        self.assertEqual(len(cache), 2)
        reader.assert_not_called()

    def test_force_source_reload_bypasses_live_cloud_reuse(self):
        source_key = self.instance.source_key(self.op)
        live_cloud, replacement = object(), object()
        owners = [types.SimpleNamespace(load_key=source_key, cloud=live_cloud)]
        reader = Mock(return_value=replacement)
        ensure_loaded = self.source_loader(owners, {source_key: live_cloud}, reader)
        self.assertIs(ensure_loaded(self.instance, self.op, force=True), replacement)
        self.assertEqual(reader.call_count, 1)

    def test_live_cloud_with_different_source_signature_is_not_reused(self):
        source_key = self.instance.source_key(self.op)
        outdated = (source_key[0], source_key[1] - 1, *source_key[2:])
        owners = [types.SimpleNamespace(load_key=outdated, cloud=object())]
        replacement = object()
        reader = Mock(return_value=replacement)
        ensure_loaded = self.source_loader(owners, {}, reader)
        self.assertIs(ensure_loaded(self.instance, self.op), replacement)
        self.assertEqual(reader.call_count, 1)

    def test_zero_padded_sh_metadata_prevents_camera_followup(self):
        self.install_ready_cloud(degree=3)
        self.instance.cloud.metadata["effective_sh_degree"] = 0
        prepared = self.instance.request_snapshot()
        self.instance.ready_request = prepared["key"]
        self.op.camera = CAMERA_B
        self.assertEqual(prepared["key"], self.instance.request_snapshot()["key"])
        self.instance.start_scan()
        self.assertIsNone(self.instance.job)
        self.assertEqual(self.instance.shown, 0)

    def test_surface_weight_change_reuses_all_prepared_arrays(self):
        self.install_ready_cloud()
        self.op.values["emission_weight"] = .4
        self.instance.start_scan()
        worker = self.instance.job["worker"]
        self.assertIs(worker.cloud, self.instance.cloud)
        self.assertIs(worker.spatial, self.instance.spatial)
        self.assertIs(worker.colors, self.instance.colors)
        self.assertEqual(self.instance.shown, 0)

    def test_explicit_changed_request_keeps_progress_dialog(self):
        self.install_ready_cloud()
        self.op.camera = CAMERA_B
        self.instance.start_scan(explicit=True)
        self.assertTrue(self.instance.job["foreground"])
        self.assertEqual(self.instance.shown, 1)

    def test_new_source_has_foreground_progress(self):
        self.install_ready_cloud()
        changed = Path(self.tmp.name) / "replacement.splat"
        changed.write_bytes(b"replacement")
        self.op[I.FILE] = str(changed)
        self.instance.start_scan()
        self.assertTrue(self.instance.job["foreground"])
        self.assertEqual(self.instance.shown, 1)
        self.assertIsNone(self.instance.job["worker"].cloud)

    def test_camera_motion_does_not_cancel_initial_source_read(self):
        self.instance.start_scan()
        job = self.instance.job
        self.assertTrue(job["foreground"])
        for camera in (CAMERA_B, (130., 40., -410.), (140., 45., -405.)):
            self.op.camera = camera
            self.instance.poll_scan()
            self.assertIs(self.instance.job, job)
            self.assertFalse(job["worker"].cancelled.is_set())
            self.assertIsNone(job["cancel_reason"])
        self.assertEqual(self.instance.shown, 1)

    def test_static_change_cancels_obsolete_work(self):
        self.install_ready_cloud()
        self.op.camera = CAMERA_B
        self.instance.start_scan()
        job = self.instance.job
        self.op.values["gamma"] = 1.4
        self.instance.poll_scan()
        self.assertTrue(job["worker"].cancelled.is_set())
        self.assertEqual(job["cancel_reason"], "superseded")
        self.assertEqual(self.instance.queued_request["key"], self.instance.request_snapshot()["key"])

    def test_active_pixel_filter_change_cancels_obsolete_geometry(self):
        self.op.values.update(camera_facing=True, pixel_variance=.3,
                              projection=dict(PROJECTION))
        self.install_ready_cloud(degree=0)
        self.op.camera = CAMERA_B
        self.instance.start_scan()
        job = self.instance.job
        self.op.values["pixel_variance"] = .6
        self.instance.poll_scan()
        self.assertTrue(job["worker"].cancelled.is_set())
        self.assertEqual(job["cancel_reason"], "superseded")
        self.assertEqual(self.instance.queued_request["key"], self.instance.request_snapshot()["key"])

    def test_publish_retains_computed_camera_and_queues_latest_view(self):
        self.install_ready_cloud()
        self.op.camera = CAMERA_B
        self.instance.start_scan()
        job = self.instance.job
        computed_key = job["request"]["key"]
        latest = (250., 80., -300.)
        self.op.camera = latest
        data = dict(cloud=self.instance.cloud, spatial=self.instance.spatial,
                    colors=self.instance.colors, bounds=self.instance.bounds)
        self.instance.publish_scan(job, types.SimpleNamespace(GetPolygonCount=lambda:1), data)
        self.assertEqual(self.instance.ready_request, computed_key)
        self.assertNotEqual(self.instance.ready_request, self.instance.request_snapshot()["key"])
        self.assertEqual(self.instance.queued_request["key"], self.instance.request_snapshot()["key"])
        self.assertIsNone(self.instance.job)

    def test_first_sh0_publication_does_not_schedule_followup_for_camera(self):
        self.instance.start_scan()
        job = self.instance.job
        self.op.camera = CAMERA_B
        data = dict(cloud=types.SimpleNamespace(metadata={"sh_degree": 0}, splats=[object()], total_count=1),
            spatial=([(0., 0., 0.)], [(1., 0., 0.)], [(0., 1., 0.)], [(0., 0., 1.)]),
            colors=[(1., .5, .1)], bounds=[(0., 1.)] * 3)
        self.instance.publish_scan(job, types.SimpleNamespace(GetPolygonCount=lambda:1), data)
        self.assertEqual(self.instance.ready_request, self.instance.request_snapshot()["key"])
        self.assertIsNone(self.instance.queued_request)
        self.assertIsNone(self.instance.job)

    def test_projection_publication_keeps_calculated_fov_and_queues_latest(self):
        self.op.values.update(camera_facing=True, pixel_variance=.3,
                              projection=dict(PROJECTION))
        self.install_ready_cloud(degree=0)
        self.op.values["projection"]["focal_x"] = 1500.
        self.instance.start_scan()
        job = self.instance.job
        computed_key = job["request"]["key"]
        self.op.values["projection"]["focal_x"] = 2000.
        self.instance.poll_scan()
        self.assertFalse(job["worker"].cancelled.is_set())
        self.assertEqual(job["request"]["values"]["projection"]["focal_x"], 1500.)
        data = dict(cloud=self.instance.cloud, spatial=self.instance.spatial,
                    colors=self.instance.colors, bounds=self.instance.bounds)
        self.instance.publish_scan(job, types.SimpleNamespace(GetPolygonCount=lambda:1), data)
        self.assertEqual(self.instance.ready_request, computed_key)
        current = self.instance.request_snapshot()
        self.assertNotEqual(self.instance.ready_request[0], current["spatial_key"])
        self.assertEqual(self.instance.color_key, current["color_key"])
        self.assertEqual(self.instance.queued_request["key"], current["key"])

    def test_settled_camera_cancels_only_arithmetic_and_reuses_source(self):
        self.install_ready_cloud()
        self.op.camera=CAMERA_B
        self.instance.start_scan()
        job=self.instance.job;old=job['worker']
        old.phase='preparing';old.analysis={'count':1}
        cloud=old.cloud
        self.op.camera=(250.,80.,-300.)
        self.instance.poll_scan()
        self.assertFalse(old.cancelled.is_set())
        job['view_changed_at']-=1.
        self.instance.poll_scan()
        self.assertTrue(old.cancelled.is_set())
        old.error=loading.Cancelled();old.done.set()
        self.instance.poll_scan()
        new=job['worker']
        self.assertIsNot(new,old)
        self.assertIs(new.cloud,cloud)
        self.assertEqual(new.request['camera'],self.op.camera)
        self.assertIs(new.request['analysis'],old.analysis)
        self.assertTrue(new.started)
        self.assertEqual(job['view_restarts'],1)
        self.assertNotEqual(self.instance.ready_request,job['request']['key'])

    def test_completed_obsolete_view_is_not_assembled_or_published(self):
        self.install_ready_cloud()
        self.op.camera=CAMERA_B
        self.instance.start_scan()
        job=self.instance.job;old=job['worker']
        old.result=dict(cloud=old.cloud,analysis={},spatial=self.instance.spatial,
                        colors=self.instance.colors,bounds=self.instance.bounds)
        old.done.set()
        self.instance.assemble_scan=Mock(side_effect=AssertionError('obsolete view'))
        self.op.camera=(250.,80.,-300.)
        self.instance.poll_scan()
        job['view_changed_at']-=1.
        self.instance.poll_scan()
        self.instance.assemble_scan.assert_not_called()
        self.assertIsNot(job['worker'],old)
        self.assertEqual(job['request']['camera'],self.op.camera)

    def test_returning_to_original_view_resets_settling_timer(self):
        self.install_ready_cloud()
        self.op.camera=CAMERA_B
        self.instance.start_scan()
        job=self.instance.job;old=job['worker'];old.phase='preparing'
        self.op.camera=(250.,80.,-300.)
        self.instance.poll_scan()
        self.op.camera=CAMERA_B
        self.instance.poll_scan()
        self.assertNotIn('view_changed_at',job)
        self.op.camera=(250.,80.,-300.)
        self.instance.poll_scan()
        self.assertFalse(old.cancelled.is_set())


if __name__ == "__main__":
    unittest.main()
