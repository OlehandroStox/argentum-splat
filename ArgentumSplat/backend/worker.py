"""Local image-to-Gaussian job worker. Never imports Cinema 4D or runs shell input.

Invocation: runtime-python worker.py --request job.json --result result.json
Progress: one JSON object per stdout line.
Cancellation: terminate this worker process; inference uses no child workers.
"""
import argparse
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent))
from media_input import load_source
from argentum_splat.input_source import classify, validate_frame


def progress(stage, amount, message):
    print(json.dumps({"stage": stage, "progress": amount, "message": message}), flush=True)


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def integer(request, name, default, low, high):
    value = request.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError("%s must be an integer in [%d, %d]." % (name, low, high))
    return value


def number(request, name, default, low, high):
    value = request.get(name, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(name + " must be a number.")
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(name + " is outside the supported range.")
    return value


def validate_request(request):
    if not isinstance(request, dict):
        raise ValueError("Request must be a JSON object.")
    image = Path(request.get("image_path", "")).expanduser().resolve()
    if not image.is_file():
        raise ValueError("Input image does not exist.")
    mode = integer(request, 'input_mode', 0, 0, 0)
    validate_frame(request.get('source_frame', 0))
    if classify(image, mode) == 'splat':
        raise ValueError('Load this splat file directly in Cinema 4D.')
    output_value = request.get("output_dir")
    if not isinstance(output_value, str) or not output_value.strip():
        raise ValueError("output_dir is required.")
    output = Path(output_value).expanduser().resolve()
    count = integer(request, "num_gaussians", 65536, 32768, 1048576)
    if count % 32:
        raise ValueError("num_gaussians must be a multiple of 32.")
    steps = integer(request, "steps", 20, 1, 100)
    seed = integer(request, "seed", 42, 0, 2**32 - 1)
    erosion = integer(request, "erode_radius", 1, 0, 8)
    guidance = number(request, "guidance_scale", 3.0, 0.0, 20.0)
    shift = number(request, "shift", 3.0, 0.1, 10.0)
    runtime_value = request.get("runtime_dir")
    if runtime_value is None:
        local = os.environ.get("LOCALAPPDATA")
        if not local:
            raise ValueError("runtime_dir is required outside Windows.")
        runtime_value = str(Path(local) / "ArgentumSplat" / "runtime")
    runtime = Path(runtime_value).expanduser().resolve()
    return image, output, runtime, count, steps, seed, erosion, guidance, shift


def release_cuda(torch):
    gc.collect()
    torch.cuda.empty_cache()


def output_basename(image, output):
    """Avoid same-named scene assets when Cinema 4D collects multiple jobs."""
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", image.stem).strip("_")[:32] or "image"
    job = hashlib.sha256(str(output).casefold().encode("utf-8")).hexdigest()[:12]
    return "ArgentumSplat_%s_%s" % (stem, job)


def run_job(request):
    started = time.monotonic()
    image, output, runtime, count, steps, seed, erosion, guidance, shift = validate_request(request)
    output.mkdir(parents=True, exist_ok=True)
    basename = output_basename(image, output)
    outputs = {name: output / filename for name, filename in (
        ("ply_path", basename + ".ply"), ("splat_path", basename + ".splat"),
        ("prepared_image_path", "prepared.png"), ("metadata_path", "generation.json"),
        ("input_frame_path", "input_frame.png"),
    )}
    if any(path.exists() for path in outputs.values()):
        raise ValueError("Output directory already contains a generation. Choose a new job directory.")
    progress('image', 0., 'Reading input image')
    source, source_media = load_source(image, request.get('input_mode', 0), request.get('source_frame', 0))
    source.save(outputs['input_frame_path'])
    if request.get('preview_only'):
        progress('complete', 1., 'Image preview ready')
        return {'ok': True, 'preview_only': True,
                'input_frame_path': str(outputs['input_frame_path']), 'source_media': source_media}
    marker = runtime / "runtime.json"
    if not marker.is_file():
        raise RuntimeError("Backend is not installed. Run setup_backend.ps1 first.")
    config = json.loads(marker.read_text(encoding="utf-8-sig"))
    model_root = Path(config["checkpoint_dir"])
    vendor = Path(__file__).resolve().parent / "vendor"
    sys.path.insert(0, str(vendor))
    # This job never downloads or uploads files. The setup script handles weights.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    progress("initializing", 0.01, "Loading the local CUDA runtime")
    import torch
    from PIL import Image, ImageOps
    import triposplat
    if not torch.cuda.is_available():
        raise RuntimeError("NVIDIA CUDA is unavailable in the configured Python environment.")
    if not torch.cuda.is_bf16_supported():
        raise RuntimeError("This backend requires an NVIDIA GPU supporting bfloat16 (Ampere or newer).")
    paths = {
        "rmbg": model_root / "background_removal/birefnet.safetensors",
        "dino": model_root / "clip_vision/dino_v3_vit_h.safetensors",
        "vae": model_root / "vae/flux2-vae.safetensors",
        "flow": model_root / "diffusion_models/triposplat_fp16.safetensors",
        "decoder": model_root / "vae/triposplat_vae_decoder_fp16.safetensors",
    }
    for path in paths.values():
        if not path.is_file():
            raise RuntimeError("Missing model checkpoint: " + str(path))
    input_resolution = {"width": source.width, "height": source.height}
    if source.width < 16 or source.height < 16:
        raise ValueError("Input image must be at least 16 x 16 pixels.")
    if source.getchannel("A").getextrema()[1] == 0:
        raise ValueError("Input image is fully transparent.")
    # Limit extreme image dimensions before the model's 1024px preprocessing.
    if max(source.size) / min(source.size) > 8:
        raise ValueError("Crop the input image to an aspect ratio smaller than 8:1.")
    generator = torch.Generator(device="cuda").manual_seed(seed)
    torch.cuda.reset_peak_memory_stats()
    # Load only the active stage onto the GPU. This keeps headroom for Cinema 4D.
    with torch.inference_mode():
        progress("background", 0.07, "Preparing the image and removing its background")
        if source.getchannel("A").getextrema()[0] < 255:
            prepared = triposplat.preprocess_image(source, None, erode_radius=erosion)
        else:
            rmbg = triposplat.load_rmbg(str(paths["rmbg"]), device="cuda", dtype=torch.float16)
            prepared = triposplat.preprocess_image(source, rmbg, erode_radius=erosion)
            del rmbg
            release_cuda(torch)
        prepared.save(outputs["prepared_image_path"])
        progress("encoding", 0.16, "Encoding the reference image")
        dino = triposplat.load_dinov3(str(paths["dino"]), device="cuda", dtype=torch.bfloat16)
        vae = triposplat.load_vae_encoder(str(paths["vae"]), device="cuda", dtype=torch.bfloat16)
        conditioning = triposplat.encode_image(prepared, dino, vae, generator=generator)
        del dino, vae
        release_cuda(torch)
        progress("sampling", 0.28, "Generating the 3D representation")
        flow = triposplat.load_flow_model(str(paths["flow"]), device="cuda", dtype=torch.float16)
        sampled = triposplat.sample_latent(
            flow, conditioning, steps=steps, guidance_scale=guidance, shift=shift,
            generator=generator, show_progress=False,
            callback=lambda step, total: progress(
                "sampling", 0.28 + 0.49 * step / total, "Generation step %d / %d" % (step, total)
            ),
        )
        from source_camera import camera_metadata
        camera_tensor = sampled.get("camera")
        raw_camera = (camera_tensor.detach().float().cpu().reshape(-1).tolist()
                      if camera_tensor is not None else None)
        source_camera = camera_metadata(raw_camera)
        del camera_tensor
        del flow, conditioning
        release_cuda(torch)
        progress("decoding", 0.80, "Decoding %s Gaussian splats" % format(count, ","))
        decoder = triposplat.load_decoder(str(paths["decoder"]), device="cuda", dtype=torch.float16)
        # Upstream octree sampling uses the global RNG rather than the generator.
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        gaussian = decoder.decode(sampled["latent"], num_gaussians=count)
        del decoder, sampled
        release_cuda(torch)
        actual_count = int(gaussian.get_xyz.shape[0])
        if actual_count != count:
            raise RuntimeError("Decoder returned an unexpected number of Gaussians.")
        for field in (gaussian.get_xyz, gaussian.get_scaling, gaussian.get_opacity,
                      gaussian._rotation, gaussian._features_dc):
            if not bool(torch.isfinite(field).all().item()):
                raise RuntimeError("The model produced non-finite Gaussian values.")
        if not bool((gaussian.get_scaling > 0).all().item()):
            raise RuntimeError("The model produced invalid Gaussian scales.")
        progress("exporting", 0.93, "Writing standard 3DGS PLY and SPLAT files")
        from export_gaussian import save_finite_ply, validate_native_ply
        export_validation = save_finite_ply(gaussian, outputs["ply_path"])
        gaussian.save_splat(str(outputs["splat_path"]))
        peak_bytes = torch.cuda.max_memory_allocated()
        peak_reserved = torch.cuda.max_memory_reserved()
        del gaussian
        release_cuda(torch)
    export_validation.update(validate_native_ply(outputs["ply_path"], actual_count))
    result = {
        "ok": True, **{key: str(value) for key, value in outputs.items()},
        "gaussian_count": actual_count,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "peak_vram_bytes": peak_bytes,
        "peak_reserved_vram_bytes": peak_reserved,
        "source_revision": config.get("source_revision"),
        "model_revision": config.get("model_revision"),
        "gpu_name": torch.cuda.get_device_name(0),
        "settings": {"num_gaussians": count, "steps": steps, "seed": seed,
                     "guidance_scale": guidance, "shift": shift, "erode_radius": erosion},
        "input_resolution": input_resolution,
        "prepared_resolution": {"width": prepared.width, "height": prepared.height},
        "source_camera": source_camera,
        "source_media": source_media,
        "representation": "3D Gaussian Splat, spherical harmonics degree 0",
        "coordinate_system": "TripoSplat standard PLY export; upstream default transform applied",
        "export_transform": [[1, 0, 0], [0, 0, -1], [0, 1, 0]],
        "prepared_image_is_reference": True,
        "output_basename": basename,
        "up_axis": "-Y",
        "recommended_c4d_flip_y": True,
        "export_validation": export_validation,
    }
    atomic_json(outputs["metadata_path"], result)
    progress("complete", 1.0, "Generation complete")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--result", required=True)
    args = parser.parse_args()
    result_path = Path(args.result).resolve()
    try:
        request_path = Path(args.request).resolve()
        if request_path.stat().st_size > 1024 * 1024:
            raise ValueError("Request JSON is too large.")
        request = json.loads(request_path.read_text(encoding="utf-8-sig"))
        result = run_job(request)
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        result = {"ok": False, "error": str(exc), "error_type": type(exc).__name__}
        progress("error", 0, str(exc))
    atomic_json(result_path, result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
