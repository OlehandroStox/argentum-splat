"""Pure Python geometry, SH colouring and spatial normal smoothing."""
import colorsys
import math
import statistics
from . import core


def add(a, b):
    return tuple(a[i] + b[i] for i in range(3))


def sub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def mul(a, k):
    return tuple(v * k for v in a)


def dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def norm(a):
    """Normalize without losing very small vectors or overflowing large ones."""
    if len(a) != 3 or not all(math.isfinite(v) for v in a):
        raise ValueError("A finite three-component vector is required.")
    largest = max(abs(v) for v in a)
    if largest == 0:
        return (0.0, 0.0, 1.0)
    scaled = tuple(v / largest for v in a)
    length = math.hypot(*scaled)
    return mul(scaled, 1.0 / length)


def correct_color(rgb, gamma=1., contrast=.5, hue=0., saturation=1., level=1.,
                  highlight=3., color_mode=0, source_space="srgb"):
    """Contrast .5 is neutral; hue is in degrees. Output is linear sRGB.

    Mode 0 decodes the source transfer function; mode 1 treats values as linear.
    Highlight is a cap in the source RGB domain, after the other corrections.
    Values above one are retained as HDR values, including during sRGB decoding.
    """
    controls = (gamma, contrast, hue, saturation, level, highlight)
    if len(rgb) != 3 or not all(math.isfinite(float(v)) for v in (*rgb, *controls)):
        raise ValueError("RGB values and color controls must be finite.")
    if gamma <= 0 or contrast < 0 or saturation < 0 or level < 0 or highlight <= 0:
        raise ValueError("Gamma/highlight must be positive; contrast/saturation/level nonnegative.")
    if color_mode not in (0, 1):
        raise ValueError("Color mode must be 0 (source transfer) or 1 (linear).")
    rgb = tuple(max(0., float(v)) for v in rgb)
    try:
        rgb = tuple(v ** (1. / gamma) for v in rgb)
    except OverflowError as error:
        raise ValueError("Gamma correction overflow; reduce input or change gamma.") from error
    if not all(math.isfinite(v) for v in rgb):
        raise ValueError("Gamma correction overflow.")
    rgb = tuple(max(0., (v-.5)*(2.*contrast)+.5) for v in rgb)
    h, s, v = colorsys.rgb_to_hsv(*rgb)
    rgb = colorsys.hsv_to_rgb((h + hue/360.) % 1., min(1., s*saturation), v)
    rgb = tuple(min(highlight, max(0., c*level)) for c in rgb)
    if color_mode == 0:
        space = core._space(source_space)
        if space == "auto":
            raise ValueError("Color correction needs an explicit source color space.")
        if space == "srgb":
            rgb = tuple(v / 12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in rgb)
    if not all(math.isfinite(v) for v in rgb):
        raise ValueError("Color correction overflow.")
    return tuple(rgb)


def card_axes(splat, camera, global_scale, splat_scale, flip_y, camera_facing):
    axes = tuple(tuple(v) for v in core.gaussian_axes(
        splat, global_scale=global_scale, splat_scale=splat_scale, flip_y=flip_y))
    center = core.transform_position(splat.position, global_scale, flip_y)
    if not camera_facing:
        # Surface-aligned ellipse: discard only the smallest covariance eigenvalue.
        order = sorted(range(3), key=lambda i: dot(axes[i], axes[i]), reverse=True)
        u, v = axes[order[0]], axes[order[1]]
        normal = norm(cross(u, v))
        if dot(normal, sub(camera, center)) < 0:
            v = mul(v, -1.)
            normal = mul(normal, -1.)
        return center, mul(u, 3.), mul(v, 3.), normal
    # Orthographic projection of full covariance on the local camera plane.
    normal = norm(sub(camera, center))
    tangent = norm(cross((0., 1., 0.) if abs(normal[1]) < .99 else (1., 0., 0.), normal))
    bitangent = norm(cross(normal, tangent))
    projected = [(dot(a, tangent), dot(a, bitangent)) for a in axes]
    largest = max(abs(v) for pair in projected for v in pair)
    if largest == 0 or not math.isfinite(largest):
        raise ValueError("Gaussian projected axes are numerically singular or too large.")
    projected = [(x / largest, y / largest) for x, y in projected]
    xx = sum(x*x for x, y in projected)
    xy = sum(x*y for x, y in projected)
    yy = sum(y*y for x, y in projected)
    angle = .5 * math.atan2(2.*xy, xx-yy)
    delta = math.hypot(xx-yy, 2.*xy)
    major_squared = (xx+yy+delta)/2.
    # Cauchy-Binet computes det(P P^T) without subtracting near-equal terms.
    determinant = sum((projected[i][0]*projected[j][1] -
                       projected[i][1]*projected[j][0])**2
                      for i, j in ((0, 1), (0, 2), (1, 2)))
    major = largest * math.sqrt(major_squared)
    minor = largest * math.sqrt(determinant / major_squared)
    if minor <= 0 or not math.isfinite(3.*major):
        raise ValueError("Gaussian projected scales are outside the supported numeric range.")
    u = mul(add(mul(tangent, math.cos(angle)), mul(bitangent, math.sin(angle))), 3.*major)
    v = mul(add(mul(tangent, -math.sin(angle)), mul(bitangent, math.cos(angle))), 3.*minor)
    return center, u, v, normal


def smooth_normals(centers, normals, widths, passes, progress=None):
    """Spatial grid smoothing with hemisphere alignment, O(passes * N)."""
    if len(centers) != len(normals) or len(centers) != len(widths):
        raise ValueError("Normal smoothing arrays must have equal lengths.")
    if isinstance(passes, bool) or not isinstance(passes, int) or passes < 0:
        raise ValueError("Normal smoothing passes must be a nonnegative integer.")
    if not centers or not passes:
        return normals
    if any(not math.isfinite(w) or w <= 0 for w in widths):
        raise ValueError("Normal smoothing widths must be positive and finite.")
    cell = max(1e-8, statistics.median(widths) * 2.)
    keys = [tuple(math.floor(c / cell) for c in p) for p in centers]
    result = normals
    for pass_index in range(min(8, max(0, passes))):
        sums = {}
        for index, (key, n) in enumerate(zip(keys, result)):
            if progress and index % 2048 == 0:
                progress('Smooth normals', pass_index*2*len(centers)+index, 2*passes*len(centers))
            group = sums.get(key)
            if group is None:
                sums[key] = [n, n[0], n[1], n[2], 1]
            else:
                ref = group[0]
                sign = 1. if ref[0]*n[0]+ref[1]*n[1]+ref[2]*n[2] >= 0 else -1.
                group[1] += n[0]*sign
                group[2] += n[1]*sign
                group[3] += n[2]*sign
                group[4] += 1
        new = []
        for index, (key, n) in enumerate(zip(keys, result)):
            if progress and index % 2048 == 0:
                progress('Smooth normals', (pass_index*2+1)*len(centers)+index, 2*passes*len(centers))
            ax, ay, az = n[0]*2., n[1]*2., n[2]*2.
            x,y,z = key
            for neighbor in ((x,y,z),(x+1,y,z),(x-1,y,z),(x,y+1,z),(x,y-1,z),(x,y,z+1),(x,y,z-1)):
                group = sums.get(neighbor)
                if group:
                    inv = 1./group[4]
                    gx,gy,gz = group[1]*inv, group[2]*inv, group[3]*inv
                    sign = 1. if gx*n[0]+gy*n[1]+gz*n[2] >= 0 else -1.
                    ax += gx*sign
                    ay += gy*sign
                    az += gz*sign
            new.append(norm((ax,ay,az)))
        result = new
    return result


def prepare_geometry(cloud, settings, camera=(0., 0., -500.), progress=None):
    """Build spatial data independently of color and surface weights."""
    centers, u_axes, v_axes, normals, widths = [], [], [], [], []
    scale = settings.get("scale", 100.)
    flip_y = settings.get("flip_y", False)
    for index, splat in enumerate(cloud.splats):
        if progress and index % 2048 == 0:
            progress('Prepare geometry', index, len(cloud.splats))
        center, u, v, normal = card_axes(splat, camera, scale,
            settings.get("splat_scale", 1.), flip_y, settings.get("camera_facing", False))
        centers.append(center)
        u_axes.append(u)
        v_axes.append(v)
        normals.append(normal)
        widths.append(math.hypot(*u))
    normals = smooth_normals(centers, normals, widths, settings.get("smoothing", 0), progress)
    return centers, u_axes, v_axes, normals


def prepare_colors(cloud, settings, camera=(0., 0., -500.), centers=None, progress=None):
    """Evaluate only the appearance, reusing already prepared centers."""
    if centers is not None and len(centers) != len(cloud.splats):
        raise ValueError("Color preparation needs one center per splat.")
    colors = []
    scale = settings.get("scale", 100.)
    flip_y = settings.get("flip_y", False)
    degree = settings.get("sh_degree", 0)
    strength = settings.get("sh_strength", 1.)
    correction = dict(gamma=settings.get("gamma", 1.),
        contrast=settings.get("contrast", .5), hue=settings.get("hue", 0.),
        saturation=settings.get("saturation", 1.), level=settings.get("level", 1.),
        highlight=settings.get("highlight", 3.), color_mode=settings.get("color_mode", 0))
    for index, splat in enumerate(cloud.splats):
        if progress and index % 2048 == 0:
            progress('Prepare colour', index, len(cloud.splats))
        # Graphdeco convention: view direction is camera -> splat in source coordinates.
        if degree and strength and splat.sh:
            center = (centers[index] if centers is not None else
                      core.transform_position(splat.position, scale, flip_y))
            direction = sub(center, camera)
            if flip_y:
                direction = (direction[0], -direction[1], direction[2])
            rgb = core.evaluate_sh(splat, norm(direction), degree, strength)
        else:
            # SH0 files do not need a view vector or a normalization per splat.
            rgb = core.evaluate_sh(splat, (0., 0., 1.), degree, strength)
        colors.append(correct_color(rgb, **correction,
            source_space=getattr(splat, "input_color_space", "srgb")))
    return colors


def prepare(cloud, settings, camera=(0., 0., -500.)):
    """Compatibility wrapper for callers which need a complete preparation."""
    spatial = prepare_geometry(cloud, settings, camera)
    return spatial + (prepare_colors(cloud, settings, camera, spatial[0]),)
