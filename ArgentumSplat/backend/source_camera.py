"""Decode TripoSplat's predicted reference camera without Torch or Cinema 4D.

The five camera values follow the upstream decoder:
https://github.com/runjie-yan/TripoSplat-Training/blob/master/deg/utils/render_utils.py

This camera refers to the square, background-removed conditioning image. It is
an estimate, not calibrated photogrammetry; the model can misestimate its scale
and distance. Preserving it does not add image projection or detail refinement.
"""
import math
from numbers import Real


SCHEMA_VERSION = 1
ORTHO_THRESHOLD = 1e-3
ORTHO_CAMERA_DISTANCE = 1000.0
EXPORT_TRANSFORM = ((1, 0, 0), (0, 0, -1), (0, 1, 0))
TOKEN_LAYOUT = (
    "eye_direction_x", "eye_direction_y", "eye_direction_z",
    "reciprocal_distance", "distance_times_tan_half_fov",
)


def _finite_token(raw_token):
    if not isinstance(raw_token, (list, tuple)) or len(raw_token) != 5:
        raise ValueError("The predicted source camera must contain five numbers.")
    if any(isinstance(value, bool) or not isinstance(value, Real)
           or not math.isfinite(value) for value in raw_token):
        raise ValueError("The predicted source camera contains non-finite or invalid numbers.")
    return [float(value) for value in raw_token]


def _transform(vector):
    return [sum(row[i] * vector[i] for i in range(3)) for row in EXPORT_TRANSFORM]


def _frame(eye, up):
    return {"eye": list(eye), "target": [0.0, 0.0, 0.0], "up": list(up)}


def decode_camera_token(raw_token):
    """Return JSON-safe camera metadata, or raise for an unusable prediction.

    Positions and orthographic scale use the model's units. Apply the splat
    object's Global Scale and object transform when creating a scene camera.
    The field of view is horizontal and vertical for the square input image.
    """
    token = _finite_token(raw_token)
    length = math.hypot(*token[:3])
    if not math.isfinite(length) or length < 1e-6:
        raise ValueError("The predicted source camera has a zero or singular direction.")
    direction = [value / length for value in token[:3]]
    # Upstream assumes a Z-up camera with no roll. At a pole, that look-at
    # orientation is undefined; avoid silently inventing an arbitrary roll.
    if math.hypot(direction[0], direction[1]) < 1e-6:
        raise ValueError("The predicted source camera direction is parallel to its up vector.")
    reciprocal_distance, half_extent = token[3:]
    if half_extent <= 0.0:
        raise ValueError("The predicted source camera has a non-positive image scale.")
    orthographic = reciprocal_distance < ORTHO_THRESHOLD
    distance = ORTHO_CAMERA_DISTANCE if orthographic else 1.0 / reciprocal_distance
    if not math.isfinite(distance) or distance <= 0.0:
        raise ValueError("The predicted source camera distance is singular.")
    # atan2 avoids overflow in half_extent * reciprocal_distance.
    fov = 2.0 * math.atan2(half_extent, distance)
    if not 1e-9 < fov < math.pi - 1e-9:
        raise ValueError("The predicted source camera field of view is singular.")
    eye = [value * distance for value in direction]
    ply_eye = _transform(eye)
    ply_up = _transform((0.0, 0.0, 1.0))
    c4d_eye = [ply_eye[0], -ply_eye[1], ply_eye[2]]
    c4d_up = [ply_up[0], -ply_up[1], ply_up[2]]
    ortho_scale = 2.0 * half_extent if orthographic else None
    if ortho_scale is not None and not math.isfinite(ortho_scale):
        raise ValueError("The predicted source camera orthographic scale is singular.")
    return {
        "schema_version": SCHEMA_VERSION,
        "available": True,
        "raw_token": token,
        "token_layout": list(TOKEN_LAYOUT),
        "projection": "orthographic" if orthographic else "perspective",
        "fov_radians": fov,
        "fov_degrees": math.degrees(fov),
        "camera_distance": distance,
        "orthographic_scale": ortho_scale,
        "source": _frame(eye, (0.0, 0.0, 1.0)),
        "exported_ply": _frame(ply_eye, ply_up),
        "c4d_flip_y": _frame(c4d_eye, c4d_up),
        "coordinate_frames": {
            "source": "TripoSplat model coordinates, Z-up",
            "exported_ply": "Standard export transform applied; up axis is -Y",
            "c4d_flip_y": "Exported PLY followed by Flip Y; up axis is +Y",
            "units": "Raw model/PLY units; apply object Global Scale and transform",
            "export_transform": [list(row) for row in EXPORT_TRANSFORM],
        },
        "image_reference": "prepared_image_path, square conditioning image",
        "fov_axes": "horizontal and vertical for the square conditioning image",
        "is_estimate": True,
        "limitation": "Predicted scale and distance may require adjustment to match the input.",
    }


def camera_metadata(raw_token):
    """Keep valid Gaussian output usable when its optional camera is invalid."""
    if raw_token is None:
        return {"schema_version": SCHEMA_VERSION, "available": False,
                "reason": "The model did not return a source camera.", "raw_token": None}
    try:
        return decode_camera_token(raw_token)
    except ValueError as error:
        try:
            safe_token = _finite_token(raw_token)
        except ValueError:
            safe_token = None
        return {"schema_version": SCHEMA_VERSION, "available": False,
                "reason": str(error), "raw_token": safe_token}
