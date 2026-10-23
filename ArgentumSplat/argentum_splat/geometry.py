"""Pure Python geometry, SH colouring and spatial normal smoothing."""
from array import array
import colorsys
import math
import operator
import statistics
from . import core


class Vec3Buffer:
    """Contiguous float64 vectors without retaining one Python tuple per point.

    Reading a vector creates a temporary tuple. Slices are independent buffers,
    with the same bounds/negative-step behavior as a list. Only complete triples
    are appended, including after a failed append. The buffer owns its storage
    and contains no NumPy or host-application objects.
    """
    __slots__ = ("_values",)

    def __init__(self, vectors=()):
        self._values = array('d')
        self.extend(vectors)

    def __len__(self):
        return len(self._values)//3

    def __iter__(self):
        values = self._values
        for index in range(0, len(values), 3):
            yield values[index], values[index+1], values[index+2]

    def __getitem__(self, key):
        if isinstance(key, slice):
            start, stop, step = key.indices(len(self))
            result = Vec3Buffer()
            if step == 1:
                result._values = self._values[3*start:3*stop]
            else:
                result.extend(self[index] for index in range(start, stop, step))
            return result
        index = operator.index(key)
        if index < 0:
            index += len(self)
        if not 0 <= index < len(self):
            raise IndexError("Vec3Buffer index out of range")
        index *= 3
        values = self._values
        return values[index], values[index+1], values[index+2]

    def append(self, vector):
        x, y, z = vector
        # Convert all components before mutation so an invalid value cannot
        # leave a partial vector in the flat array.
        self._values.extend((float(x), float(y), float(z)))

    def extend(self, vectors):
        if isinstance(vectors, Vec3Buffer):
            self._values.extend(vectors._values)
        else:
            append = self.append
            for vector in vectors:
                append(vector)

    @property
    def nbytes(self):
        """Payload bytes, excluding allocator capacity and object overhead."""
        return len(self._values)*self._values.itemsize

    def __repr__(self):
        return "Vec3Buffer({} vectors, {} bytes)".format(len(self), self.nbytes)


def add(a, b):
    return tuple(a[i] + b[i] for i in range(3))


def sub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def mul(a, k):
    return tuple(v * k for v in a)


def dot(a, b):
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]


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


def _batch_color_corrector(correction):
    """Compile constant LOOK controls once, for already validated source RGB.

    The public scalar helpers still validate all their inputs. In a cloud pass,
    evaluate_sh has already checked each RGB value, and every splat shares the
    same correction settings. Avoid repeating that setup, and avoid an RGB/HSV
    round trip when hue and saturation are neutral. The latter is particularly
    useful for large SH0 clouds, whose color does not depend on the camera.
    """
    correct_color((0., 0., 0.), source_space="linear", **correction)
    gamma = correction["gamma"]
    contrast = correction["contrast"]
    hue = correction["hue"]
    saturation = correction["saturation"]
    level = correction["level"]
    highlight = correction["highlight"]
    inverse_gamma = 1. / gamma
    contrast_scale = 2. * contrast
    hue_offset = hue / 360.
    use_hsv = hue != 0. or saturation != 1.
    transfer = correction["color_mode"] == 0
    source_spaces = {}
    finite = math.isfinite

    def apply(rgb, source_space):
        r, g, b = rgb
        r, g, b = max(0., float(r)), max(0., float(g)), max(0., float(b))
        if gamma != 1.:
            try:
                r, g, b = r ** inverse_gamma, g ** inverse_gamma, b ** inverse_gamma
            except OverflowError as error:
                raise ValueError("Gamma correction overflow; reduce input or change gamma.") from error
            if not (finite(r) and finite(g) and finite(b)):
                raise ValueError("Gamma correction overflow.")
        if contrast != .5:
            r = max(0., (r-.5)*contrast_scale+.5)
            g = max(0., (g-.5)*contrast_scale+.5)
            b = max(0., (b-.5)*contrast_scale+.5)
        if use_hsv:
            h, s, v = colorsys.rgb_to_hsv(r, g, b)
            r, g, b = colorsys.hsv_to_rgb((h+hue_offset) % 1., min(1., s*saturation), v)
        r = min(highlight, max(0., r*level))
        g = min(highlight, max(0., g*level))
        b = min(highlight, max(0., b*level))
        if transfer:
            # Files ordinarily contain one source space. Cache normalized aliases
            # as well, while retaining mixed-space cloud and validation support.
            key = str(source_space)
            decode = source_spaces.get(key)
            if decode is None:
                space = core._space(source_space)
                if space == "auto":
                    raise ValueError("Color correction needs an explicit source color space.")
                decode = space == "srgb"
                source_spaces[key] = decode
            if decode:
                r = r / 12.92 if r <= .04045 else ((r+.055)/1.055)**2.4
                g = g / 12.92 if g <= .04045 else ((g+.055)/1.055)**2.4
                b = b / 12.92 if b <= .04045 else ((b+.055)/1.055)**2.4
        if not (finite(r) and finite(g) and finite(b)):
            raise ValueError("Color correction overflow.")
        return r, g, b

    return apply


def _compile_projection(projection, pixel_variance):
    """Validate camera data once and prepare its local-to-camera dual basis.

    right/up/forward are camera basis vectors expressed in object coordinates.
    Keep their full inverse object transform: normalizing them independently
    would break nonuniformly scaled or sheared objects. Unit orthogonal vectors
    also work. Focal lengths are in pixels; orthographic pixel_world_x/y use the
    same camera-coordinate units as those basis vectors. width/height describe
    the image for which focal lengths and pixel scales were calculated.
    """
    if not math.isfinite(pixel_variance) or pixel_variance < 0.:
        raise ValueError("Projected Gaussian pixel variance must be nonnegative and finite.")
    basis = []
    for key in ("right", "up", "forward"):
        vector = tuple(float(v) for v in projection[key])
        if len(vector) != 3 or not all(math.isfinite(v) for v in vector):
            raise ValueError("Projection camera basis must contain finite three-component vectors.")
        basis.append(vector)
    for key in ("width", "height"):
        if not math.isfinite(projection[key]) or projection[key] <= 0.:
            raise ValueError("Projection image dimensions must be positive and finite.")

    # Scale before finding the inverse so large/small object transforms cannot
    # overflow the cross products. Rows of the inverse basis give camera XYZ.
    largest = max(abs(v) for vector in basis for v in vector)
    if largest == 0.:
        raise ValueError("Projection camera basis is singular.")
    r, u, f = (tuple(v/largest for v in vector) for vector in basis)
    uf, fr, ru = cross(u, f), cross(f, r), cross(r, u)
    determinant = dot(r, uf)
    if determinant == 0. or not math.isfinite(determinant):
        raise ValueError("Projection camera basis is singular.")
    try:
        inverse = tuple(tuple((v/determinant)/largest for v in vector)
                        for vector in (uf, fr, ru))
    except (OverflowError, ZeroDivisionError) as error:
        raise ValueError("Projection camera basis cannot be inverted safely.") from error
    if not all(math.isfinite(v) for vector in inverse for v in vector):
        raise ValueError("Projection camera basis cannot be inverted safely.")
    orthographic = bool(projection.get("orthographic", False))
    scale_keys = (("pixel_world_x", "pixel_world_y") if orthographic else
                  ("focal_x", "focal_y"))
    scale_x, scale_y = (float(projection[key]) for key in scale_keys)
    if not all(math.isfinite(v) and v > 0. for v in (scale_x, scale_y)):
        raise ValueError("Projection focal lengths or pixel scales must be positive and finite.")
    normal = norm(cross(norm(basis[0]), norm(basis[1])))
    if dot(normal, basis[2]) > 0.:
        normal = mul(normal, -1.)
    hidden = ((0., 0., 0.), (0., 0., 0.), normal)
    return (basis[0], basis[1], inverse, orthographic, scale_x, scale_y, pixel_variance,
            float(projection['width']), float(projection['height']), hidden)


def _projected_axes(axes, center, camera, projection):
    """EWA first-order perspective covariance, plus an image-space low-pass.

    Cards lie in a plane parallel to the image, so the ellipse defined by the
    perspective Jacobian maps back to its pixel covariance without an additional
    oblique-card approximation. This does not turn cards into a rasterizer.
    Hidden/singular projections collapse in place, preserving source indices.
    Never fall back to a tilted card behind the projection camera: a large
    background Gaussian can then intersect rays in front of that camera.
    """
    right, up, inverse, orthographic, scale_x, scale_y, pixel_variance, width, height, hidden = projection
    relative = (center[0]-camera[0], center[1]-camera[1], center[2]-camera[2])
    x, y, z = (dot(row, relative) for row in inverse)
    if not all(math.isfinite(v) for v in (x, y, z)) or z <= 1e-8:
        return hidden
    # Bound support in pixel space, including when the camera is inside a scan.
    # A distant centre close to the eye plane must not grow a kilometre-wide
    # card through the whole image. The cap scales with the output dimensions.
    sigma_limit = min(1024., width, height) / math.sqrt(8.)
    support_limit = 3. * math.sqrt(2.) * sigma_limit
    if orthographic:
        world_pixel_x, world_pixel_y = scale_x, scale_y
        projected = [(dot(inverse[0], a)/scale_x, dot(inverse[1], a)/scale_y)
                     for a in axes]
    else:
        world_pixel_x, world_pixel_y = z/scale_x, z/scale_y
        if (abs(x) > (width*.5 + support_limit)*world_pixel_x or
                abs(y) > (height*.5 + support_limit)*world_pixel_y):
            return hidden
        slope_x, slope_y = x/z, y/z
        projected = []
        for axis in axes:
            ax, ay, az = (dot(row, axis) for row in inverse)
            projected.append(((ax-slope_x*az)/world_pixel_x,
                              (ay-slope_y*az)/world_pixel_y))
    if not all(math.isfinite(v) for pair in projected for v in pair):
        return hidden

    # Work at normalized magnitude, retaining the small eigenvalue through the
    # Cauchy-Binet determinant instead of subtracting nearly equal eigenvalues.
    largest = max(math.sqrt(pixel_variance), max(abs(v) for pair in projected for v in pair))
    if largest == 0.:
        return hidden
    projected = [(px/largest, py/largest) for px, py in projected]
    ridge = (math.sqrt(pixel_variance)/largest)**2
    xx = sum(px*px for px, py in projected)
    xy = sum(px*py for px, py in projected)
    yy = sum(py*py for px, py in projected)
    determinant = sum((projected[i][0]*projected[j][1] -
                       projected[i][1]*projected[j][0])**2
                      for i, j in ((0, 1), (0, 2), (1, 2)))
    determinant += ridge*(xx+yy) + ridge*ridge
    major_squared = (xx+yy+2.*ridge+math.hypot(xx-yy, 2.*xy))/2.
    if major_squared <= 0. or determinant <= 0.:
        return hidden
    major = min(sigma_limit, largest*math.sqrt(major_squared))
    minor = min(sigma_limit, largest*math.sqrt(determinant/major_squared))
    angle = .5*math.atan2(2.*xy, xx-yy)
    cosine, sine = math.cos(angle), math.sin(angle)
    half_x = 3.*(major*abs(cosine) + minor*abs(sine))
    half_y = 3.*(major*abs(sine) + minor*abs(cosine))
    if (abs(x/world_pixel_x) - half_x > width*.5 or
            abs(y/world_pixel_y) - half_y > height*.5):
        return hidden
    u = tuple(3.*major*(right[i]*(cosine*world_pixel_x) + up[i]*(sine*world_pixel_y))
              for i in range(3))
    v = tuple(3.*minor*(right[i]*(-sine*world_pixel_x) + up[i]*(cosine*world_pixel_y))
              for i in range(3))
    if not all(math.isfinite(value) for vector in (u, v) for value in vector):
        return hidden
    # Normalize each axis first to avoid overflowing a cross product when a
    # finite but large object transform is involved. Reflection is supported.
    normal = norm(cross(norm(u), norm(v)))
    if dot(normal, relative) > 0.:
        v = mul(v, -1.)
        normal = mul(normal, -1.)
    return u, v, normal


def projected_card_axes(splat, camera, global_scale, splat_scale, flip_y,
                        projection, pixel_variance=.075):
    """Perspective/orthographic cards; zero disables only the low-pass filter.

    ``pixel_variance`` is the added variance in pixel squared, not a world-space
    radius. The default uses actual pixel coordinates. Camera and
    projection basis must be expressed in the same local frame as the cloud.
    """
    compiled = _compile_projection(projection, pixel_variance) if projection else None
    return card_axes(splat, camera, global_scale, splat_scale, flip_y, True, compiled)


def card_axes(splat, camera, global_scale, splat_scale, flip_y, camera_facing, _projection=None):
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
    if _projection is not None:
        projected = _projected_axes(axes, center, camera, _projection)
        if projected is not None:
            return (center,) + projected
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
    """Build spatial data independently of color and surface weights.

    settings['compact_buffers'] opts into float64 Vec3Buffer outputs. Otherwise
    return the existing lists. Both modes use the same geometry calculations.
    """
    compact = bool(settings.get("compact_buffers", False))
    vector_container = Vec3Buffer if compact else list
    centers, u_axes, v_axes, normals = (vector_container() for _ in range(4))
    widths = array('d') if compact else []
    scale = settings.get("scale", 100.)
    flip_y = settings.get("flip_y", False)
    camera_facing = settings.get("camera_facing", False)
    projection = settings.get("projection")
    pixel_variance = settings.get("pixel_variance", 0.)
    projection = (_compile_projection(projection, pixel_variance)
                  if camera_facing and projection else None)
    for index, splat in enumerate(core.iter_attributes(cloud, 'geometry')):
        if progress and index % 2048 == 0:
            progress('Prepare geometry', index, len(cloud.splats))
        center, u, v, normal = card_axes(splat, camera, scale,
            settings.get("splat_scale", 1.), flip_y, camera_facing, projection)
        centers.append(center)
        u_axes.append(u)
        v_axes.append(v)
        normals.append(normal)
        # Invisible zero-area cards still keep one normal/index per source.
        widths.append(max(1e-8, math.hypot(*u)))
    # Projected cards share one image plane; smoothing identical normals adds
    # no information and can allocate a huge spatial grid for city scans.
    if projection is None:
        normals = smooth_normals(centers, normals, widths, settings.get("smoothing", 0), progress)
    if compact and not isinstance(normals, Vec3Buffer):
        normals = Vec3Buffer(normals)
    return centers, u_axes, v_axes, normals


def prepare_colors(cloud, settings, camera=(0., 0., -500.), centers=None, progress=None):
    """Evaluate appearance, optionally returning a compact float64 buffer."""
    if centers is not None and len(centers) != len(cloud.splats):
        raise ValueError("Color preparation needs one center per splat.")
    colors = Vec3Buffer() if settings.get("compact_buffers", False) else []
    if not cloud.splats:
        return colors
    scale = settings.get("scale", 100.)
    flip_y = settings.get("flip_y", False)
    degree = settings.get("sh_degree", 0)
    strength = settings.get("sh_strength", 1.)
    correction = dict(gamma=settings.get("gamma", 1.),
        contrast=settings.get("contrast", .5), hue=settings.get("hue", 0.),
        saturation=settings.get("saturation", 1.), level=settings.get("level", 1.),
        highlight=settings.get("highlight", 3.), color_mode=settings.get("color_mode", 0))
    correct = _batch_color_corrector(correction)
    evaluate_sh = core.evaluate_sh
    append = colors.append
    for index, splat in enumerate(core.iter_attributes(cloud, 'appearance')):
        if progress and index % 2048 == 0:
            progress('Prepare colour', index, len(cloud.splats))
        # Graphdeco convention: view direction is camera -> splat in source coordinates.
        if degree and strength and splat.sh:
            center = (centers[index] if centers is not None else
                      core.transform_position(splat.position, scale, flip_y))
            direction = (center[0]-camera[0], center[1]-camera[1], center[2]-camera[2])
            if flip_y:
                direction = (direction[0], -direction[1], direction[2])
            # evaluate_sh already performs robust normalization. Preserve the
            # previous fallback when the camera coincides with this center.
            if direction == (0., 0., 0.):
                direction = (0., 0., 1.)
            rgb = evaluate_sh(splat, direction, degree, strength)
        else:
            # SH0 files do not need a view vector or a normalization per splat.
            rgb = evaluate_sh(splat, (0., 0., 1.), degree, strength)
        append(correct(rgb, getattr(splat, "input_color_space", "srgb")))
    return colors


def prepare(cloud, settings, camera=(0., 0., -500.)):
    """Compatibility wrapper for callers which need a complete preparation."""
    spatial = prepare_geometry(cloud, settings, camera)
    return spatial + (prepare_colors(cloud, settings, camera, spatial[0]),)


def gaussian_support(opacity):
    """Half-width relative to the 3-sigma card, excluding shader-zero tails.

    The shader discards alpha below 1/255. Keeping those transparent polygons
    still consumes Redshift's transparency depth. Shrink the card and its UV
    interval together, so every visible Gaussian sample keeps its position and
    opacity. A small outward tolerance protects the cutoff against roundoff.
    """
    alpha = min(1., max(0., float(opacity)))
    if alpha <= 1./255.:
        return 0.
    return min(1., math.sqrt(2.*math.log(alpha*255.)/9.) + 1e-6)


def card_indices(spatial, compact=False):
    """Only omit zero-area projected cards; retain the immutable source arrays.

    This is not density sampling or opacity pruning. Excluded cards could not
    contribute to this camera. Disable compaction in a hierarchy (MoGraph) to
    preserve one polygon per source and stable effector indexing.
    """
    if not compact:
        return range(len(spatial[0]))
    return array('I', (i for i, u in enumerate(spatial[1]) if any(u)))
