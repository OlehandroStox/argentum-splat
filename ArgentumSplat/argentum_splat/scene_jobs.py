"""Interactive scan pipeline: pure data in a worker, bounded UI-thread commits.

The visible generator cache is never edited in place. It keeps the last complete
model until a validated replacement is ready, including throughout cancellation.
Offline render documents still use the synchronous generator path.
"""
import os
from pathlib import Path
import time
import c4d
from . import assets, loading, ids as I


def resolved_request(request, cloud):
    """Replace conservative pre-read SH keys with the decoded source degree.

    Do not change the camera/values used for the calculation. Before a first
    publication no live cloud is available to request_snapshot(), so it assumes
    SH3. Resolving both requests avoids treating discovered SH0/SH1 as a user
    edit or restarting camera-independent work during an orbit.
    """
    if cloud is None:
        return request
    degree = cloud.metadata.get('effective_sh_degree', cloud.metadata.get('sh_degree', 0))
    spatial, color = loading.preparation_keys(request['source_key'], request['values'],
        request['camera'], degree, request['color_key'][3])
    # Assembly holds this same dictionary across UI yields and adds the newly
    # created material. Replacing it on a later timer tick detaches that write,
    # making the next poll mistake our own material for an external user edit.
    request.update(spatial_key=spatial, color_key=color,
        key=(spatial, color, request['opacity'], request['weights'], request['material']))
    return request


class InteractiveScan:
    def scan_state(self):
        if hasattr(self, 'ready_request'):
            return
        self.ready_request = None
        self.blocked_request = None
        self.cancelled_non_view = None
        self.queued_request = None
        self.queued_at = 0.
        self.mesh_template = None
        self.ready_card_indices = None
        self.display_key = None
        self.last_scan_metrics = {}
        self.source_analysis = None

    def source_key(self, op):
        path = assets.resolve_path(op, op[I.FILE])
        if not path:
            return None
        stat = os.stat(path)
        return (str(Path(path).resolve()), stat.st_mtime_ns, stat.st_size,
                int(op[I.MAX_SPLATS]), float(op[I.MIN_OPACITY]), bool(op[I.SPZ_RAW]))

    def request_snapshot(self):
        from . import plugin
        op = self.op
        source_key = self.source_key(op)
        values = plugin.settings(op)
        same_source = source_key == self.load_key and self.cloud is not None
        has_sh = self.cloud.metadata.get('effective_sh_degree', self.cloud.metadata.get('sh_degree', 0)) if same_source else True
        camera = plugin.projection_camera(op) if (values['camera_facing'] or
            (has_sh and values['sh_degree'] and values['sh_strength'])) else (0.,0.,-500.)
        color_config = plugin.color_configuration_key(op.GetDocument())
        spatial, color = loading.preparation_keys(source_key, values, camera, has_sh, color_config)
        opacity = float(op[I.OPACITY])
        weights = tuple(values[k] for k in ('emission_weight','diffuse_weight','subsurface_weight'))
        return dict(source_key=source_key, values=values, camera=camera,
                    spatial_key=spatial, color_key=color, opacity=opacity,
                    weights=weights, material=op[I.MATERIAL],
                    key=(spatial, color, opacity, weights, op[I.MATERIAL]))

    def interactive_cache(self, op):
        """No parsing, SH evaluation, smoothing or card construction in GVO."""
        from . import plugin
        self.scan_state()
        self.op = op
        try:
            request = self.request_snapshot()
            if request['source_key'] is None:
                self.queued_request = None
                self.cancelled_non_view = None
                return c4d.BaseObject(c4d.Onull)
            cancelled = getattr(self, 'cancelled_non_view', None)
            same_cancelled_controls = cancelled is not None and cancelled == loading.non_view_key(request)
            if cancelled is not None and not same_cancelled_controls:
                self.cancelled_non_view = None
            if not same_cancelled_controls and request['key'] not in (self.ready_request, self.blocked_request):
                if self.queued_request is None or self.queued_request['key'] != request['key']:
                    self.queued_request = request
                    self.queued_at = time.monotonic()
            else:
                self.queued_request = None
            cached = op.GetCache()
            if self.mesh_template is None:
                return cached if cached is not None else c4d.BaseObject(c4d.Onull)
            point_preview = bool(op[I.POINT_PREVIEW])
            display_key = (self.ready_request, point_preview)
            if display_key == self.display_key and cached is not None:
                return cached
            mesh = self.mesh_template.GetClone(c4d.COPYFLAGS_NONE)
            if point_preview:
                root = c4d.BaseObject(c4d.Onull)
                root.SetName('Gaussian Preview')
                mesh.SetEditorMode(c4d.MODE_OFF)
                mesh.InsertUnder(root)
                result = root
            else:
                mesh.SetEditorMode(c4d.MODE_UNDEF)
                result = mesh
            self.display_key = display_key
            return result
        except Exception as error:
            self.error = str(error)
            self.queued_request = None
            cached = op.GetCache()
            return cached if cached is not None else c4d.BaseObject(c4d.Onull)

    def start_scan(self, explicit=False):
        from . import plugin
        self.scan_state()
        if self.job:
            return
        if any(x.job for x in plugin.JOBS):
            if explicit:
                raise RuntimeError('Another Argentum job is running. Finish or cancel it first.')
            return
        try:
            request = self.request_snapshot()
        except Exception:
            self.queued_request = None
            raise
        key = request['source_key']
        if key is None:
            self.queued_request = None
            self.cancelled_non_view = None
            if explicit:
                raise ValueError('Choose a local Gaussian PLY, SPLAT, SOG, SPZ or KSPLAT file first.')
            return
        if not explicit:
            if (request['key'] == self.blocked_request or
                    loading.non_view_key(request) == getattr(self, 'cancelled_non_view', None)):
                self.queued_request = None
                return
        self.cancelled_non_view = None
        self.blocked_request = None
        self.error = self.reported_error = ''
        source = key[0]
        try:
            from . import import_choice
            if import_choice.offer(self, request):
                self.queued_request = None
                return
            owners = [self] + [other for other in list(getattr(plugin, 'INSTANCES', ()))
                if other is not self and getattr(other, 'load_key', None) == key]
            cloud = self.cloud if self.load_key == key else plugin.CLOUD_CACHE.get(key)
            if cloud is None:
                cloud = next((other.cloud for other in owners
                    if getattr(other, 'load_key', None) == key and getattr(other, 'cloud', None) is not None), None)
            if cloud is None:
                from . import import_budget
                import_budget.check_memory(import_budget.source_count(source), key[3])
            request = resolved_request(request, cloud)
            converted = plugin.converter().needs_conversion(source)
            if converted:
                cached = assets.resolve_path(self.op, self.op[I.CACHE_FILE])
                if (not assets.cache_source_matches(source, self.op[I.CACHE_SOURCE])
                        or not cached or not Path(cached).is_file()):
                    self.queued_request = None
                    self.start_conversion(source)
                    return
                path = cached
            else:
                path = source
            from .quality import auto_prepare_redshift
            auto_prepare_redshift(self.op, key)
            if request['key'] == self.ready_request and self.mesh_template is not None:
                self.queued_request = None
                self.set_progress('Ready — source unchanged; using the prepared scan.', 1.)
                self.close_progress()
                return
            spatial = self.spatial if self.spatial_key == request['spatial_key'] else None
            colors = self.colors if self.color_key == request['color_key'] else None
            bounds = self.bounds if spatial is not None else None
            analysis = None
            # An open generator can outlive the small global source cache.
            # Reuse its immutable buffers, as the synchronous render path does.
            for other in owners:
                if getattr(other, 'cloud', None) is not cloud or cloud is None:
                    continue
                if analysis is None:
                    analysis = getattr(other, 'source_analysis', None)
                    if analysis is not None and other is not self:
                        # Source measurements can be shared; framing outcomes
                        # belong to one object/document and are mutated later.
                        analysis = {key: value for key, value in analysis.items()
                                    if key not in ('framing', 'frame_warning')}
                if spatial is None and getattr(other, 'spatial_key', None) == request['spatial_key']:
                    spatial, bounds = other.spatial, other.bounds
                if colors is None and getattr(other, 'color_key', None) == request['color_key']:
                    colors = other.colors
            source_reused = cloud is not None
            view_only = (source_reused and self.mesh_template is not None and
                         loading.view_only_request(request, self.ready_request))
            worker_request = dict(path=path, max_splats=key[3], min_opacity=key[4], raw_spz=key[5],
                values=request['values'], camera=request['camera'],
                view_only=view_only,
                converted_spz=converted and source.lower().endswith('.spz') and not key[5])
            from . import scene_setup
            worker_request['analysis'] = analysis
            worker_request['analyse_only'] = scene_setup.needs_initial_analysis(self.op,key)
            worker = loading.Preparation(worker_request, cloud, spatial, colors,
                                         bounds)
            self.job = dict(kind='scan', worker=worker, request=request, dir=Path(path).parent,
                            started=time.perf_counter(), builder=None, last_progress=0.,
                            source_reused=source_reused, view_only=view_only,
                            cancel_reason=None, max_slice_seconds=0.,
                            foreground=explicit or self.mesh_template is None or key != self.load_key)
            self.queued_request = None
            plugin.JOBS.add(self)
            same_ready_source = self.ready_request is not None and self.ready_request[0][0] == key
            self.set_progress('Updating camera view — source reused' if view_only else
                              'Updating scan settings' if source_reused and same_ready_source else
                              'Preparing scan — source reused' if source_reused else 'Reading scan', 0.)
            if self.job['foreground']:
                self.show_progress()
            worker.start()
        except Exception:
            self.blocked_request = request['key']
            self.queued_request = None
            raise

    def cancel_scan(self, notify=True, superseded=False):
        if not self.job or self.job.get('kind') != 'scan':
            return
        self.job['worker'].cancelled.set()
        self.job['cancel_reason'] = 'superseded' if superseded else 'user'
        if not superseded:
            try:
                request = self.request_snapshot()
            except (OSError, ReferenceError):
                request = self.job['request']
            self.blocked_request = request['key']
            self.cancelled_non_view = loading.non_view_key(request)
            self.queued_request = None
        if notify and self.op and plugin_document_open(self.op):
            self.set_progress('Cancelling… keeping the previous complete model.', None)

    def report_failure(self, error):
        self.scan_state()
        if not self.job:
            self.close_progress()
            try:
                self.blocked_request = self.request_snapshot()['key']
            except (OSError, ValueError, ReferenceError):
                self.blocked_request = None
            self.queued_request = None
        self.error = self.reported_error = str(error)
        self.set_progress('Error: ' + str(error), None)

    def release_scan(self):
        from . import plugin
        job = self.job
        if job and job.get('builder') is not None:
            job['builder'].close()
        self.job = None
        plugin.JOBS.discard(self)
        self.close_progress()
        return job

    def poll_scan(self):
        from . import plugin
        job = self.job
        worker = job['worker']
        try:
            current = self.request_snapshot()
        except (OSError, ValueError):
            current = None
        # The reader may have learned the actual SH degree since the request
        # began. Resolve keys before deciding whether any work is obsolete.
        data = worker.result or {}
        cloud = data.get('cloud', worker.cloud)
        if cloud is not None:
            job['request'] = resolved_request(job['request'], cloud)
            if current is not None and current['source_key'] == job['request']['source_key']:
                current = resolved_request(current, cloud)
        if not job['cancel_reason'] and (current is None or
                loading.non_view_key(current) != loading.non_view_key(job['request'])):
            self.cancel_scan(notify=False, superseded=True)
            if current is not None:
                self.queued_request = current
                self.queued_at = time.monotonic()
        if job['cancel_reason']:
            if worker.done.is_set():
                reason = job['cancel_reason']
                self.release_scan()
                if reason == 'user':
                    self.set_progress('Cancelled. Previous complete model preserved.', None)
                else:
                    self.set_progress('Waiting for changes to settle…', None)
            return
        # A real failure must not be swallowed by camera retargeting. Only our
        # deliberate preparation cancellation is eligible for a view restart.
        if worker.done.is_set() and worker.error is not None and not (
                job.get('retargeting') and isinstance(worker.error, loading.Cancelled)):
            self.blocked_request = current['key'] if current is not None else job['request']['key']
            self.queued_request = None
            self.release_scan()
            if not isinstance(worker.error, loading.Cancelled):
                raise RuntimeError(str(worker.error))
            return
        # Never publish camera-dependent cards as Ready for a different view.
        # Let file reading finish, then cancel obsolete arithmetic once the
        # camera has settled. Reuse the validated cloud across restarts.
        view_changed = current is not None and current['key'] != job['request']['key']
        if view_changed:
            if job.get('latest_view_key') != current['key']:
                job['latest_view_key'] = current['key']
                job['view_changed_at'] = time.monotonic()
            settled = time.monotonic()-job['view_changed_at'] >= .35
            if settled and getattr(worker, 'phase', '') == 'preparing':
                worker.cancelled.set()
                job['retargeting'] = True
        elif not job.get('retargeting'):
            job.pop('latest_view_key', None)
            job.pop('view_changed_at', None)
        if job.get('retargeting'):
            if not worker.done.is_set():
                return
            if view_changed and time.monotonic()-job['view_changed_at'] < .35:
                return
            self.restart_view(current)
            return
        if not worker.done.is_set():
            if time.monotonic()-job['last_progress'] >= .15:
                self.set_progress(*worker.status)
                job['last_progress'] = time.monotonic()
            return
        if worker.result.get('analyse_only'):
            from . import scene_setup
            # Recheck the live scene: a camera the user created during reading
            # takes priority over automatic framing. Reuse the parsed source.
            data=worker.result
            try:
                scene_setup.frame_scan(self.op,data['analysis'],automatic=True)
            except Exception as error:
                # Camera assistance must not make an otherwise valid scan fail.
                data['analysis']['frame_warning']=str(error)
            job['request']=self.request_snapshot()
            next_request=dict(worker.request, values=job['request']['values'],
                camera=job['request']['camera'],analyse_only=False,analysis=data['analysis'])
            job['analysis_read_seconds']=worker.timings.get('read_seconds',0.)
            job['worker']=loading.Preparation(next_request,cloud=data['cloud']).start()
            return
        if view_changed:
            if time.monotonic()-job['view_changed_at'] >= .35:
                self.restart_view(current)
            return
        try:
            if job['builder'] is None:
                job['builder'] = self.assemble_scan(job)
            started = time.perf_counter()
            # Spend at most a short UI slice per timer, shared by active jobs.
            # The old 12 ms / 40 ms cadence spent most assembly time idle.
            budget = max(.002, .020 / max(1, len(plugin.JOBS)))
            while time.perf_counter()-started < budget:
                message, amount = next(job['builder'])
                self.progress_message = message
                self.progress_amount = max(self.progress_amount or 0., amount)
            job['max_slice_seconds'] = max(job['max_slice_seconds'], time.perf_counter()-started)
            if time.monotonic()-job['last_progress'] >= .15:
                self.set_progress(self.progress_message, self.progress_amount)
                job['last_progress'] = time.monotonic()
        except StopIteration as finished:
            job['max_slice_seconds'] = max(job['max_slice_seconds'], time.perf_counter()-started)
            mesh, data = finished.value
            self.publish_scan(job, mesh, data)
        except Exception:
            self.blocked_request = job['request']['key']
            self.queued_request = None
            self.release_scan()
            raise

    def restart_view(self, request):
        """Replace an obsolete view pass, keeping its parsed immutable source."""
        job = self.job
        old = job['worker']
        assert old.done.is_set()
        if job['builder'] is not None:
            job['builder'].close()
        data = old.result or {}
        cloud = data.get('cloud', old.cloud)
        analysis = data.get('analysis', old.analysis)
        new_request = dict(old.request, values=request['values'], camera=request['camera'],
                           analysis=analysis, analyse_only=False)
        same_spatial = request['spatial_key'] == job['request']['spatial_key']
        same_colors = request['color_key'] == job['request']['color_key']
        spatial = data.get('spatial', old.spatial) if same_spatial else None
        colors = data.get('colors', old.colors) if same_colors else None
        new_request['colors_are_working'] = bool(colors is not None and
            data.get('colors_are_working', getattr(old, 'colors_are_working', old.colors is not None)))
        job['request'] = request
        job['builder'] = None
        job['retargeting'] = False
        job['view_restarts'] = job.get('view_restarts', 0)+1
        job['analysis_read_seconds'] = job.get('analysis_read_seconds', 0.)+old.timings.get('read_seconds', 0.)
        job.pop('latest_view_key', None)
        job['worker'] = loading.Preparation(new_request, cloud, spatial, colors,
                                           data.get('bounds', old.bounds) if spatial is not None else None)
        self.set_progress('Updating latest camera view — previous view is temporary.', 0.)
        job['worker'].start()

    def assemble_scan(self, job):
        from . import plugin
        request, data = job['request'], job['worker'].result
        cloud, spatial, colors = data['cloud'], data['spatial'], data['colors']
        if not data['colors_are_working']:
            working = plugin.geometry.Vec3Buffer() if request['values'].get('compact_buffers') else []
            count = len(colors)
            for start in range(0, count, 4096):
                working.extend(plugin.working_colors(self.op.GetDocument(), colors[start:start+4096]))
                yield ('Convert document colours: {:,} / {:,}'.format(min(start+4096,count),count),
                       .80+.04*min(start+4096,count)/max(1,count))
            colors = working
        data['colors'] = colors
        data['colors_are_working'] = True
        yield ('Prepare material', .84)
        self.sync_material()
        request['material'] = self.op[I.MATERIAL]
        request['key'] = (*request['key'][:-1], request['material'])
        prepared = spatial+(colors,)
        previous_indices = getattr(self, 'ready_card_indices', None)
        current_indices = data.get('card_indices')
        same_mapping = (previous_indices is not None and current_indices is not None
                        and previous_indices == current_indices)
        view_refresh = (self.ready_request is not None and
                        self.ready_request[0][0] == request['source_key'] and same_mapping)
        if (self.mesh_template is not None and self.ready_request is not None
                and (request['spatial_key'] == self.ready_request[0] or view_refresh)):
            # Attribute-only updates still allocate an owned mesh and a later
            # display copy. Admit them against current free RAM just like new
            # geometry, before entering the indivisible native clone call.
            from . import import_budget
            import_budget.check_card_memory(self.mesh_template.GetPolygonCount())
            mesh = self.mesh_template.GetClone(c4d.COPYFLAGS_NONE)
            previous = self.ready_request
            weights = tuple(name for index,name in enumerate(
                ('emission_weight','diffuse_weight','subsurface_weight'))
                if previous[3][index] != request['weights'][index])
            steps = plugin.update_mesh_steps(mesh, cloud, prepared, request['opacity'], request['values'],
                update_colors=previous[1] != request['color_key'],
                update_opacity=previous[2] != request['opacity'], update_weights=weights,
                material=request['material'], update_material=previous[4] != request['material'],
                indices=current_indices,
                update_geometry=previous[0] != request['spatial_key'])
        else:
            steps = plugin.build_mesh_steps(cloud, prepared, request['material'],
                                             request['opacity'], request['values'],
                                             indices=data.get('card_indices'))
        while True:
            try:
                stage, done, count = next(steps)
                if job.get('view_only'):
                    stage = {'Build Gaussian cards': 'Update visible camera cards',
                             'Allocate Gaussian cards': 'Allocate updated camera view'}.get(stage, stage)
                yield ('{}: {:,} / {:,}'.format(stage,done,count), .84+.15*done/max(1,count))
            except StopIteration as finished:
                return finished.value, data

    def publish_scan(self, job, mesh, data):
        from . import plugin
        # Only the final atomic publication changes generator-visible state.
        c4d.StopAllThreads()
        self.cloud, self.load_key = data['cloud'], job['request']['source_key']
        self.source_analysis = data.get('analysis')
        self.spatial, self.colors, self.bounds = data['spatial'], data['colors'], data['bounds']
        # Label results with the camera that was actually calculated, not the
        # camera that happens to be current when this asynchronous job finishes.
        request = dict(job['request'])
        degree = self.cloud.metadata.get('effective_sh_degree', self.cloud.metadata.get('sh_degree', 0))
        request['spatial_key'], request['color_key'] = loading.preparation_keys(
            self.load_key, request['values'], request['camera'], degree,
            request['color_key'][3])
        request['key'] = (request['spatial_key'], request['color_key'],
                          request['opacity'], request['weights'], request['material'])
        self.spatial_key, self.color_key = request['spatial_key'], request['color_key']
        self.prepared = self.spatial+(self.colors,)
        self.prepare_key = (self.spatial_key,self.color_key)
        self.cache_key = None
        self.mesh_template = mesh
        self.ready_card_indices = data.get('card_indices')
        self.ready_request = request['key']
        self.display_key = None
        self.queued_request = None
        self.blocked_request = None
        self.error = self.reported_error = ''
        plugin.CLOUD_CACHE[self.load_key] = self.cloud
        while len(plugin.CLOUD_CACHE) > 2:
            plugin.CLOUD_CACHE.pop(next(iter(plugin.CLOUD_CACHE)))
        self.last_scan_metrics = dict(job['worker'].timings,
            total_seconds=time.perf_counter()-job['started'],
            max_ui_slice_seconds=job['max_slice_seconds'],
            retained=len(self.cloud.splats), total=self.cloud.total_count)
        self.last_scan_metrics.update(render_cards=mesh.GetPolygonCount(), view_restarts=job.get('view_restarts',0),
                                      source_reused=bool(job.get('source_reused')), view_only=bool(job.get('view_only')))
        if 'analysis_read_seconds' in job:
            self.last_scan_metrics['read_seconds'] += job['analysis_read_seconds']
        if self.source_analysis is not None:
            from . import scene_setup
            scene_setup.finish_import(self.op,self.load_key,self.source_analysis)
        self.release_scan()
        current = self.request_snapshot()
        if current['key'] != self.ready_request:
            self.queued_request = current
            self.queued_at = time.monotonic()
        self.op.SetDirty(c4d.DIRTYFLAGS_DATA)
        retained, total = len(self.cloud.splats), self.cloud.total_count
        eligible = self.cloud.metadata.get('eligible_count', total)
        detail = (' · Sampled source' if retained < eligible else
                  ' · Opacity-filtered only' if retained < total else ' · Full source')
        if self.queued_request is not None:
            detail += (' · Latest view pending' if loading.view_only_request(current, self.ready_request) else
                       ' · Latest changes pending')
        label = 'View updated' if job.get('view_only') else 'Ready'
        self.set_progress('{}: {:,} / {:,} splats ({:.1f}%) · {:.1f}s · SH {}{}'.format(
            label, retained, total, 100.*retained/max(1,total), self.last_scan_metrics['total_seconds'],
            self.cloud.metadata.get('sh_degree',0),
            detail), 1.)


def plugin_document_open(op):
    from .plugin import is_open_document
    try:
        return is_open_document(op.GetDocument())
    except ReferenceError:
        return False
