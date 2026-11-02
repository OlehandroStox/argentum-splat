"""Local Photos -> COLMAP cameras -> Brush Gaussian reconstruction worker.

Runs outside Cinema 4D. Source pictures are read-only. Cancel kills the owned
worker/process tree. Runtime installation and reconstruction never upload images.
"""
import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from argentum_splat import photos


def progress(stage, amount, message):
    print(json.dumps(dict(stage=stage, progress=amount, message=message)), flush=True)


def atomic_json(path, data):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf8')
    temporary.replace(path)


def prepare_images(files, destination, resolution):
    from PIL import Image, ImageOps, ImageCms
    from io import BytesIO
    destination.mkdir(parents=True, exist_ok=False)
    manifest, seen = [], set()
    for index, source in enumerate(files):
        checksum = photos.digest(source)
        if checksum in seen:
            raise ValueError('Duplicate photo: %s. Each view must be a different photograph.' % source.name)
        seen.add(checksum)
        with Image.open(source) as raw:
            if getattr(raw, 'n_frames', 1) != 1:
                raise ValueError('Photos accepts single still images only: ' + source.name)
            if raw.width * raw.height > 80_000_000 or min(raw.size) < 64:
                raise ValueError('Photo dimensions must be at least 64 pixels and at most 80 megapixels: ' + source.name)
            image = ImageOps.exif_transpose(raw)
            exif = image.getexif()
            icc = raw.info.get('icc_profile')
            if icc:
                image = ImageCms.profileToProfile(image, ImageCms.ImageCmsProfile(BytesIO(icc)),
                    ImageCms.createProfile('sRGB'), outputMode='RGB')
            image.thumbnail((resolution, resolution), Image.Resampling.LANCZOS)
            exif[274] = 1
            name = 'photo_%05d.png' % index
            image.convert('RGB').save(destination / name, format='PNG', exif=exif)
            manifest.append(dict(source=str(source), sha256=checksum, prepared=name,
                                 width=image.width, height=image.height))
        progress('photos', .05 + .1*(index+1)/len(files), 'Preparing photo %d / %d' % (index+1, len(files)))
    return manifest


def source_view(reconstruction, image=None):
    """Use an actual calibrated input camera, retaining COLMAP world coordinates."""
    import numpy as np
    image = image or min(reconstruction.images.values(), key=lambda x: x.name)
    camera = reconstruction.cameras[image.camera_id]
    pose = image.cam_from_world().inverse()
    rotation = pose.rotation.matrix()
    eye = np.asarray(pose.translation)
    forward, up = rotation[:, 2], -rotation[:, 1]
    points = np.array([p.xyz for p in reconstruction.points3D.values()])
    distance = max(.01, float(np.median(np.linalg.norm(points-eye, axis=1))))
    return dict(available=True, is_estimate=True, origin='photos_colmap',
        projection='perspective', image_name=image.name,
        width=camera.width, height=camera.height,
        fov_radians=2*math.atan(camera.width/(2*camera.focal_length_x)),
        camera_distance=distance,
        exported_ply=dict(eye=eye.tolist(), target=(eye+forward*distance).tolist(), up=up.tolist()),
        limitation='Calibrated input view. Scale is arbitrary; output aspect and lens center may differ.')


def run_job(request):
    started = time.monotonic()
    if not isinstance(request, dict):
        raise ValueError('Request must be an object.')
    files = photos.image_files(request.get('photos_folder', ''))
    initial_signature = photos.signature(request['photos_folder'])
    values = photos.settings(request)
    output = Path(request['output_dir']).resolve()
    runtime = Path(request['runtime_dir']).resolve()
    config = json.loads((runtime/'photos-runtime.json').read_text(encoding='utf8'))
    executable = Path(config['brush_exe'])
    if (config.get('brush_archive_sha256') != photos.BRUSH_SHA256 or
            photos.digest(executable) != config.get('brush_sha256')):
        raise RuntimeError('Photos trainer changed or is incomplete. Run Set Up Photos again.')
    import pycolmap as colmap
    if colmap.__version__ != photos.PYCOLMAP_VERSION:
        raise RuntimeError('Photos runtime version mismatch; run setup again.')
    output.mkdir(parents=True, exist_ok=True)
    work = output/'photos-work'
    work.mkdir(exist_ok=False)
    images = work/'images'
    manifest = prepare_images(files, images, values['resolution'])
    atomic_json(output/'photos-manifest.json', manifest)
    threads = min(8, max(1, (os.cpu_count() or 2)-1))
    database = work/'database.db'
    progress('features', None, 'Finding common details in %d photos' % len(files))
    colmap.extract_features(database, images,
        extraction_options=dict(num_threads=threads, max_image_size=values['resolution']),
        device=colmap.Device.cpu)
    progress('matching', None, 'Matching overlapping photos')
    colmap.match_exhaustive(database, matching_options=dict(num_threads=threads), device=colmap.Device.cpu)
    progress('cameras', None, 'Solving camera positions and scene structure')
    sparse = work/'sparse'; sparse.mkdir()
    maps = colmap.incremental_mapping(database, images, sparse,
        options=dict(num_threads=threads, min_model_size=3, random_seed=values['seed'], max_runtime_seconds=3600))
    if not maps:
        raise ValueError('No connected reconstruction. Use overlapping, sharp photos of a stationary subject.')
    model = max(maps.values(), key=lambda r: r.num_reg_images())
    names = {im.name for im in model.images.values()}
    registered = photos.registration_check(len(files), names)
    if model.num_points3D() < 100:
        raise ValueError('Too few reliable scene points. Add textured overlapping views and remove blurred images.')
    chosen = work/'aligned'; chosen.mkdir(); model.write(chosen)
    registration = dict(requested=len(files), registered=registered,
        points=model.num_points3D(), mean_reprojection_error=model.compute_mean_reprojection_error(),
        used=[m['source'] for m in manifest if m['prepared'] in names],
        unused=[m['source'] for m in manifest if m['prepared'] not in names])
    atomic_json(output/'alignment.json', registration)
    progress('undistort', .4, 'Aligned %d / %d photos; correcting lens distortion' % (registered, len(files)))
    dataset = work/'dataset'
    colmap.undistort_images(dataset, chosen, images,
        undistort_options=dict(max_image_size=values['resolution']), num_threads=threads)
    # Brush reads original COLMAP coordinates and exports them unchanged.
    undistorted = colmap.Reconstruction(dataset/'sparse')
    camera = source_view(undistorted)
    cameras = [source_view(undistorted, im) for im in sorted(undistorted.images.values(), key=lambda im: im.name)]
    atomic_json(output/'capture-cameras.json', dict(schema=1, cameras=cameras,
        note='Only photographed surfaces are reconstructed. These are calibrated capture views, not full scene coverage.'))
    progress('training', None, 'Training one scene from %d aligned photos' % registered)
    log_path = output/'trainer.log'
    from photo_color import linear_dataset, mark_ply
    training_dataset = linear_dataset(dataset, colmap, progress) if values['training_color']=='linear' else dataset
    command = photos.brush_command(executable, training_dataset, output, values)
    with log_path.open('wb') as log:
        process = subprocess.Popen(command, cwd=str(work), stdout=log, stderr=subprocess.STDOUT,
            shell=False, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        training_started = time.monotonic()
        try:
            while process.poll() is None:
                elapsed = time.monotonic()-training_started
                if elapsed > 6*3600:
                    raise RuntimeError('Photos training exceeded six hours; see trainer.log.')
                progress('training', None, 'Training %d photos · %d:%02d elapsed · target %d steps' %
                         (registered, elapsed//60, elapsed%60, values['steps']))
                time.sleep(2.)
            if process.returncode != 0:
                raise RuntimeError('Gaussian training failed. Check GPU memory/driver and trainer.log.')
        finally:
            if process.poll() is None:
                process.terminate(); process.wait(timeout=10)
    generated = output/'reconstruction.ply'
    if not generated.is_file():
        raise RuntimeError('Training ended without a Gaussian PLY. See trainer.log.')
    mark_ply(generated, values['training_color']=='linear')
    progress('validation', .98, 'Validating the reconstructed Gaussian scan')
    from argentum_splat import core
    cloud = core.load(str(generated), max_splats=1, min_opacity=0.)
    if cloud.total_count < 1:
        raise ValueError('Reconstruction contains no Gaussians.')
    ply = output/('ArgentumPhotos_' + output.name + '.ply')
    generated.replace(ply)
    try:
        source_changed = initial_signature != photos.signature(request['photos_folder'])
    except (OSError, ValueError):
        source_changed = True
    result = dict(ok=True, kind='photos', ply_path=str(ply), gaussian_count=cloud.total_count,
        settings=values, alignment=registration, source_changed=source_changed,
        source_camera=camera, capture_cameras_file='capture-cameras.json', recommended_c4d_flip_y=True,
        elapsed_seconds=time.monotonic()-started, brush_version=photos.BRUSH_VERSION,
        pycolmap_version=colmap.__version__, input_manifest=str(output/'photos-manifest.json'))
    atomic_json(output/'generation.json', result)
    progress('complete', 1., 'Reconstructed %s Gaussians from %d / %d photos' %
             (format(cloud.total_count, ','), registered, len(files)))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', required=True); parser.add_argument('--result', required=True)
    args = parser.parse_args()
    try:
        result = run_job(json.loads(Path(args.request).read_text(encoding='utf-8-sig')))
    except Exception as error:
        traceback.print_exc()
        result = dict(ok=False, error=str(error))
    atomic_json(args.result, result)
    sys.exit(0 if result['ok'] else 1)
