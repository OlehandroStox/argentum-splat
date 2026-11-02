"""Cancellable data preparation. Worker code has no Cinema 4D dependency."""
import math
import threading
import time
from . import core, geometry, import_analysis


class Cancelled(Exception):
    pass


def view_key(value):
    """Ignore host matrix round-trip noise in cache keys, not in calculations.

    Tiny basis vectors share their scale so numerical zero stays zero without
    erasing inverse object-scale axes. Cap that shared scale at one unit: an
    absolute coordinate origin must not coarsen the other camera components.
    Larger components retain fifteen significant digits to suppress their own
    final floating-point digits without losing ordinary motion far from zero.
    User controls and source identifiers do not pass through this function.
    """
    if isinstance(value, (tuple, list)):
        if value and all(isinstance(v, (int, float)) and math.isfinite(v) for v in value):
            magnitude = min(1., max(abs(v) for v in value))
            digits = 11 - math.floor(math.log10(magnitude)) if magnitude else 12
            return tuple(float(format(round(v, digits), '.15g')) for v in value)
        return tuple(view_key(v) for v in value)
    if isinstance(value, float) and math.isfinite(value):
        return float(format(value, '.12g'))
    return value


def preparation_keys(source_key, values, camera, has_sh, color_config):
    stable_camera = view_key(camera)
    spatial_camera = stable_camera if values['camera_facing'] else (0., 0., -500.)
    projection = values.get('projection')
    if values['camera_facing'] and projection:
        spatial_camera = (stable_camera, values.get('pixel_variance', 0.),
                          tuple(sorted((key, view_key(value)) for key, value in projection.items())))
    spatial = (source_key, tuple(values[k] for k in
        ('scale', 'splat_scale', 'flip_y', 'camera_facing', 'smoothing')) +
        (bool(values.get('compact_cards', False)), int(values.get('gaussian_profile', 0))), spatial_camera)
    degree = effective_degree(values, has_sh)
    direction_override = values.get('sh_direction')
    if direction_override is None and projection and projection.get('orthographic'):
        direction_override = projection['forward']
    color_camera = (('parallel', view_key(direction_override)) if direction_override is not None
                    else stable_camera) if degree else None
    view_values = (values['scale'], values['flip_y'], degree, values['sh_strength']) if degree else (None, None, 0, 0.)
    color = (source_key, view_values + tuple(values[k] for k in
        ('gamma', 'contrast', 'hue', 'saturation', 'level', 'highlight', 'color_mode')), color_camera, color_config)
    return spatial, color


def effective_degree(values, available):
    """Unknown (True) is conservative; an integer is the stored SH degree."""
    maximum = 3 if available is True else int(available or 0)
    return min(values['sh_degree'], maximum) if values['sh_strength'] else 0


def non_view_key(request):
    """Changes to the camera alone must not throw away in-flight file reads."""
    spatial, color = request['spatial_key'], request['color_key']
    # Pixel filtering is a user control, although its value lives beside the
    # camera projection in the spatial key. Preserve it during cancellation
    # comparisons; ignore it when the projection path is inactive. Deriving it
    # from the prepared key also supports requests without a values dictionary.
    view = spatial[2]
    pixel_variance = (view[1] if isinstance(view, tuple) and len(view) == 3
                      and isinstance(view[0], tuple) and isinstance(view[2], tuple) else 0.)
    return (spatial[:2], pixel_variance, color[:2] + color[3:], request['opacity'],
            request['weights'], request['material'])


def view_only_request(request, ready_key):
    """Classify a changed view against a published request, for status only."""
    if ready_key is None or request['key'] == ready_key:
        return False
    previous = dict(zip(('spatial_key', 'color_key', 'opacity', 'weights', 'material'), ready_key))
    return (request['source_key'] == previous['spatial_key'][0] and
            non_view_key(request) == non_view_key(previous))


class Preparation:
    """One immutable request; results become visible only after completion."""
    def __init__(self, request, cloud=None, spatial=None, colors=None, bounds=None):
        self.request = request
        self.cloud, self.spatial, self.colors, self.bounds = cloud, spatial, colors, bounds
        # Live owners supply document-working colours; a cancelled worker can
        # also supply completed source-space colours. Preserve that distinction
        # so a retarget neither reevaluates them nor skips OCIO conversion.
        self.colors_are_working = bool(colors is not None and request.get('colors_are_working', True))
        self.cancelled = threading.Event()
        self.done = threading.Event()
        self.result = None
        self.error = None
        self.view_only = bool(request.get('view_only') and cloud is not None)
        self.status = ('Updating camera view — source reused' if self.view_only else
                       'Starting scan preparation', 0.)
        self.started = time.perf_counter()
        self.timings = {}
        self.phase = 'reading'
        self.analysis = None
        self.thread = threading.Thread(target=self.run, name='Argentum scan preparation', daemon=True)
        self._next_yield_at = time.monotonic() + .025

    def check(self):
        if self.cancelled.is_set():
            raise Cancelled()
        # CPU-bound Python preparation competes with the host's Python draw and
        # timer callbacks for the GIL. At existing checkpoints, briefly give
        # those callbacks an explicit scheduling opportunity. Do not alter the
        # process-wide switch interval or sleep in a main-thread caller.
        if threading.current_thread() is self.thread:
            now = time.monotonic()
            if now >= getattr(self, '_next_yield_at', 0.):
                self._next_yield_at = now + .025
                if self.cancelled.wait(.001):
                    raise Cancelled()

    def progress(self, stage, completed, total):
        self.check()
        fraction = completed / max(1, total)
        if stage.startswith('Read') or stage.startswith('Decompress'):
            start, end = 0., .40
        elif stage == 'Decode colour':
            start, end = .40, .45
        elif stage == 'Analyse source':
            start, end = .40, .45
        elif stage == 'Prepare geometry':
            start, end = .45, .60
        elif stage == 'Smooth normals':
            start, end = .60, .70
        else:
            start, end = .70, .80
        amount = max(self.status[1], start+(end-start)*min(1., fraction))
        # Keep the original stage for progress ranges and cancellation. Only
        # its display label distinguishes required view arithmetic from import.
        label = ({'Prepare geometry': 'Project Gaussians for camera',
                  'Prepare colour': 'Update view-dependent colour',
                  'Select visible cards': 'Update visible cards'}.get(stage, stage)
                 if self.view_only else stage)
        self.status = ('{}: {:,} / {:,}'.format(label, completed, total), amount)

    def start(self):
        self.thread.start()
        return self

    def run(self):
        try:
            request = self.request
            start = time.perf_counter()
            cloud = self.cloud
            if cloud is None:
                from . import import_budget
                import_budget.check_memory(import_budget.source_count(request['path']), request['max_splats'])
                cloud = core.load(request['path'], max_splats=request['max_splats'],
                    min_opacity=request['min_opacity'], unconverted_coordinates=request['raw_spz'],
                    progress=self.progress, compact=True)
                if request.get('converted_spz'):
                    from dataclasses import replace
                    from .spz import _RUB_RDF_SH_SIGNS
                    transformed = []
                    for index, splat in enumerate(cloud.splats):
                        if index % 2048 == 0:
                            self.check()
                        x,y,z = splat.position
                        w,qx,qy,qz = splat.rotation
                        dimension = len(splat.sh)//3
                        sh = tuple(v*_RUB_RDF_SH_SIGNS[i % dimension]
                                   for i,v in enumerate(splat.sh)) if dimension else ()
                        transformed.append(replace(splat, position=(x,-y,-z), rotation=(w,qx,-qy,-qz), sh=sh))
                    cloud = core.SplatCloud(transformed, cloud.total_count, dict(cloud.metadata, coordinates='RDF'))
            self.timings['read_seconds'] = time.perf_counter()-start
            if not cloud.splats:
                raise ValueError('No visible splats. Reduce Minimum Opacity or choose another scan.')
            self.check()
            analysis = request.get('analysis')
            if analysis is None:
                analysis = import_analysis.analyse(cloud, self.progress)
            if request.get('analyse_only'):
                self.result = dict(cloud=cloud, analysis=analysis, analyse_only=True)
                return
            # A camera change may cancel preparation after this checkpoint,
            # without discarding the validated source or reading it twice.
            self.cloud = cloud
            self.analysis = analysis
            self.phase = 'preparing'
            start = time.perf_counter()
            spatial = self.spatial
            bounds = self.bounds
            if spatial is None:
                spatial_camera = request['camera'] if request['values']['camera_facing'] else (0.,0.,-500.)
                spatial = geometry.prepare_geometry(cloud, request['values'], spatial_camera, self.progress)
                from . import fast_geometry
                bounds = fast_geometry.spatial_bounds(spatial, self.progress)
                if bounds is None:
                    low, high = [float('inf')]*3, [float('-inf')]*3
                    for index, (p,u,v) in enumerate(zip(*spatial[:3])):
                        if index % 2048 == 0:
                            self.check()
                        for axis in range(3):
                            extent = abs(u[axis])+abs(v[axis])
                            low[axis] = min(low[axis], p[axis]-extent)
                            high[axis] = max(high[axis], p[axis]+extent)
                    bounds = [((lo+hi)*.5,max(.01,(hi-lo)*.5)) for lo,hi in zip(low,high)]
            # A later stage may be cancelled when the camera moves. Keep only
            # complete stages for restart_view; partially populated local
            # arrays are never exposed to the next worker.
            self.spatial, self.bounds = spatial, bounds
            self.timings['geometry_seconds'] = time.perf_counter()-start
            start = time.perf_counter()
            colors = self.colors
            if colors is None:
                colors = geometry.prepare_colors(cloud, request['values'], request['camera'], spatial[0], self.progress)
            self.colors = colors
            self.timings['color_seconds'] = time.perf_counter()-start
            start = time.perf_counter()
            indices = geometry.card_indices(spatial, request['values'].get('compact_cards', False), self.progress)
            self.timings['visibility_seconds'] = time.perf_counter()-start
            self.check()
            self.status = ('View data ready; updating Cinema 4D geometry' if self.view_only else
                           'Data ready; preparing Cinema 4D geometry', .80)
            self.result = dict(cloud=cloud, spatial=spatial, colors=colors, bounds=bounds,
                               colors_are_working=self.colors_are_working, analysis=analysis,
                               card_indices=indices)
        except BaseException as error:
            # Traceback frames can retain the entire partially loaded reservoir
            # in a cycle after cancellation. Keep the error, not gigabytes of
            # abandoned records waiting for a later main-thread GC collection.
            self.error = error.with_traceback(None)
        finally:
            self.done.set()
