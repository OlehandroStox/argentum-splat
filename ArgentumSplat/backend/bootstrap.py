"""Download pinned public model weights and verify the isolated runtime."""
import argparse
import json
import os
from pathlib import Path
import sys

MODEL_REPO = "VAST-AI/TripoSplat"
MODEL_REVISION = "56a96e603204ec410c4da60c13ea4fa09a2169a9"
SOURCE_REVISION = "d8db9e018b413dd9c4a9fe22463781bf98e8e68d"
WEIGHTS = (
    "background_removal/birefnet.safetensors",
    "clip_vision/dino_v3_vit_h.safetensors",
    "diffusion_models/triposplat_fp16.safetensors",
    "vae/flux2-vae.safetensors",
    "vae/triposplat_vae_decoder_fp16.safetensors",
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-dir", required=True)
    args = parser.parse_args()
    runtime = Path(args.runtime_dir).resolve()
    runtime.mkdir(parents=True, exist_ok=True)
    # Anonymous access to the public repository; no stored user token is sent.
    os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["HF_HOME"] = str(runtime / "hf-cache")
    os.environ["HF_XET_CACHE"] = str(runtime / "xet-cache")
    from huggingface_hub import model_info
    from download_models import download
    import torch
    import torchvision

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable. Install an NVIDIA driver compatible with CUDA 12.8.")
    if not torch.cuda.is_bf16_supported():
        raise RuntimeError("Local AI requires an NVIDIA Ampere-or-newer GPU with BF16 support.")
    info = model_info(MODEL_REPO, revision=MODEL_REVISION, files_metadata=True, token=False)
    expected = {}
    for item in info.siblings:
        if item.rfilename in WEIGHTS and item.lfs:
            expected[item.rfilename] = (item.size, item.lfs.sha256)
    hashes = {}
    for name in WEIGHTS:
        if name not in expected:
            raise RuntimeError("Model repository omitted SHA-256 metadata: " + name)
        hashes[name] = download(
            MODEL_REPO, MODEL_REVISION, name, runtime / "models" / name,
            expected[name][0], expected[name][1],
        )
    device = torch.cuda.get_device_properties(0)
    config = {
        "schema_version": 1,
        "python_exe": str(Path(sys.executable).resolve()),
        "runtime_dir": str(runtime),
        "checkpoint_dir": str(runtime / "models"),
        "source_revision": SOURCE_REVISION,
        "model_repo": MODEL_REPO,
        "model_revision": MODEL_REVISION,
        "model_sha256": hashes,
        "model_sizes": {name: expected[name][0] for name in WEIGHTS},
        "torch_version": torch.__version__,
        "torchvision_version": torchvision.__version__,
        "cuda_version": torch.version.cuda,
        "gpu_name": device.name,
        "gpu_vram_bytes": device.total_memory,
    }
    marker = runtime / "runtime.json"
    temporary = marker.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(config, indent=2), encoding="utf-8")
    temporary.replace(marker)
    print(json.dumps({"ok": True, "runtime_config": str(marker), "gpu": device.name}), flush=True)


if __name__ == "__main__":
    main()
