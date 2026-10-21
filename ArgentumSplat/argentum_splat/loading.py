"""Cancellable data preparation. Worker code has no Cinema 4D dependency."""
import threading
import time
from . import core, geometry


class Cancelled(Exception):
    pass


def preparation_keys(source_key, values, camera, has_sh, color_config):
    spatial_camera = camera if values['camera_facing'] else (0., 0., -500.)
    spatial = (source_key, tuple(values[k] for k in
        ('scale', 'splat_scale', 'flip_y', 'camera_facing', 'smoothing')), spatial_camera)
    color_camera = camera if has_sh and values['sh_degree'] and values['sh_strength'] else None
    color = (source_key, tuple(values[k] for k in
        ('scale', 'flip_y', 'sh_degree', 'sh_strength', 'gamma', 'contrast',
         'hue', 'saturation', 'level', 'highlight', 'color_mode')), color_camera, color_config)
    return spatial, color


class Preparation:
    """One immutable request; results become visible only after completion."""
    def __init__(self, request, cloud=None, spatial=None, colors=None, bounds=None):
        self.request = request
        self.cloud, self.spatial, self.colors, self.bounds = cloud, spatial, colors, bounds
        self.cancelled = threading.Event()
        self.done = threading.Event()
        self.result = None
        self.error = None
        self.status = ('Starting scan preparation', 0.)
        self.started = time.perf_counter()
        self.timings = {}
        self.thread = threading.Thread(target=self.run, name='Argentum scan preparation', daemon=True)

    def check(self):
        if self.cancelled.is_set():
            raise Cancelled()

    def progress(self, stage, completed, total):
        self.check()
        fraction = completed / max(1, total)
        if stage.startswith('Read') or stage.startswith('Decompress'):
            start, end = 0., .40
        elif stage == 'Decode colour':
            start, end = .40, .45
        elif stage == 'Prepare geometry':
            start, end = .45, .60
        elif stage == 'Smooth normals':
            start, end = .60, .70
        else:
            start, end = .70, .80
        amount = max(self.status[1], start+(end-start)*min(1., fraction))
        self.status = ('{}: {:,} / {:,}'.format(stage, completed, total), amount)

    def start(self):
        self.thread.start()
        return self

    def run(self):
        try:
            request = self.request
            start = time.perf_counter()
            cloud = self.cloud
            if cloud is None:
                cloud = core.load(request['path'], max_splats=request['max_splats'],
                    min_opacity=request['min_opacity'], unconverted_coordinates=request['raw_spz'],
                    progress=self.progress)
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
            start = time.perf_counter()
            spatial = self.spatial
            bounds = self.bounds
            if spatial is None:
                spatial_camera = request['camera'] if request['values']['camera_facing'] else (0.,0.,-500.)
                spatial = geometry.prepare_geometry(cloud, request['values'], spatial_camera, self.progress)
                low, high = [float('inf')]*3, [float('-inf')]*3
                for index, (p,u,v) in enumerate(zip(*spatial[:3])):
                    if index % 2048 == 0:
                        self.check()
                    for axis in range(3):
                        extent = abs(u[axis])+abs(v[axis])
                        low[axis] = min(low[axis], p[axis]-extent)
                        high[axis] = max(high[axis], p[axis]+extent)
                bounds = [((lo+hi)*.5,max(.01,(hi-lo)*.5)) for lo,hi in zip(low,high)]
            self.timings['geometry_seconds'] = time.perf_counter()-start
            start = time.perf_counter()
            colors = self.colors
            if colors is None:
                colors = geometry.prepare_colors(cloud, request['values'], request['camera'], spatial[0], self.progress)
            self.timings['color_seconds'] = time.perf_counter()-start
            self.check()
            self.status = ('Data ready; preparing Cinema 4D geometry', .80)
            self.result = dict(cloud=cloud, spatial=spatial, colors=colors, bounds=bounds,
                               colors_are_working=self.colors is not None)
        except BaseException as error:
            self.error = error
        finally:
            self.done.set()
