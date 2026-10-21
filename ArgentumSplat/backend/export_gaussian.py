"""Finite 3DGS PLY export without a lossy sigmoid/logit round trip.

TripoSplat's upstream exporter inverts its activated opacity. Half-precision
sigmoid can round to exactly one, making the inverse infinite. PLY stores the
logit, so export the original pre-activation value instead.
"""
from pathlib import Path


def save_finite_ply(gaussian, path):
    import numpy as np
    import torch

    xyz, rotation = gaussian._transformed_xyz_rot()
    xyz = np.asarray(xyz, dtype=np.float32)
    rotation = np.asarray(rotation, dtype=np.float32)
    dc = gaussian._features_dc.detach().float().transpose(1, 2).flatten(
        start_dim=1
    ).contiguous().cpu().numpy()
    logits = (gaussian._opacity.detach().float()
              + gaussian.opacity_bias_val.detach().float()).cpu().numpy()
    scales = gaussian.get_scaling.detach().float()
    if not bool((torch.isfinite(scales) & (scales > 0)).all().item()):
        raise ValueError("Cannot export non-finite or non-positive Gaussian scales.")
    log_scales = torch.log(scales).cpu().numpy()
    columns = np.concatenate((
        xyz, np.zeros_like(xyz), dc, logits, log_scales, rotation
    ), axis=1).astype("<f4")
    names = gaussian.construct_list_of_attributes()
    if columns.shape[1] != len(names):
        raise ValueError("Unexpected Gaussian PLY schema.")
    if not np.isfinite(columns).all():
        invalid = [name for i, name in enumerate(names) if not np.isfinite(columns[:, i]).all()]
        raise ValueError("Non-finite serialized PLY fields: " + ", ".join(invalid))
    if np.any(np.linalg.norm(rotation, axis=1) <= 0):
        raise ValueError("Cannot export a zero Gaussian quaternion.")
    elements = np.empty(len(columns), dtype=[(name, "<f4") for name in names])
    for index, name in enumerate(names):
        elements[name] = columns[:, index]
    header = "ply\nformat binary_little_endian 1.0\n"
    header += "element vertex %d\n" % len(elements)
    header += "".join("property float %s\n" % name for name in names)
    header += "end_header\n"
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as stream:
        stream.write(header.encode("ascii"))
        stream.write(elements.tobytes())
    temporary.replace(path)
    return {
        "opacity_encoding": "original pre-sigmoid logits plus bias, float32",
        "opacity_logit_min": float(logits.min()),
        "opacity_logit_max": float(logits.max()),
        "all_serialized_fields_finite": True,
    }


def validate_native_ply(path, expected_count):
    """Use the same strict parser as Cinema 4D, without loading Cinema 4D."""
    import sys
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from argentum_splat import core
    # The strict reader validates every record before reservoir sampling.
    cloud = core.load(path, max_splats=1, min_opacity=0.0)
    if cloud.total_count != expected_count or len(cloud.splats) != min(1, expected_count):
        raise ValueError("Exported PLY did not pass the native parser count check.")
    return {"native_parser_validated_count": cloud.total_count}
