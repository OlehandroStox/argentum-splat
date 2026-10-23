"""Bounded, deterministic source analysis; no host API or third-party packages."""
import itertools
import math
from . import geometry as g


def capture_view_score(splats, retained, forward=(0.,0.,1.)):
    """Check whether the source origin has a detailed, filled forward view.

    A room/panorama cannot be viewed from outside its enclosing surfaces. A
    source-space candidate is accepted only when fine Gaussians cover most of
    the frame and large blurred footprints do not dominate. This bounded
    geometric estimate is deliberately conservative; it does not label objects
    by name, delete splats, or claim to recover the original capture camera.
    The caller must know the source's forward/up convention before using it.
    """
    width, height, columns, rows = 960., 540., 8, 5
    focal = height / (2. * math.tan(math.radians(30.)))
    right = (forward[2], 0., -forward[0])
    projection = g._compile_projection(dict(right=right,up=(0.,1.,0.),
        forward=forward,focal_x=focal,focal_y=focal,width=width,height=height),.075)
    cells = [0.]*(columns*rows)
    mass = coarse = 0.
    fine_mass = log_depth = 0.
    nearest = math.inf
    weight = retained/max(1,len(splats))
    for splat in splats:
        x,y,z = g.dot(splat.position,right),splat.position[1],g.dot(splat.position,forward)
        if z <= 1e-9:
            continue
        px,py=x*focal/z,y*focal/z
        if abs(px)>=width*.5 or abs(py)>=height*.5:
            continue
        _,u,v,_ = g.card_axes(splat,(0.,0.,0.),1.,1.,False,True,projection)
        major,minor=math.hypot(*u)*focal/(3*z),math.hypot(*v)*focal/(3*z)
        amount=min(width*height,max(0.,splat.opacity)*major*minor)
        mass+=amount
        if major > 8.:
            coarse+=amount
        else:
            fine_mass += amount
            log_depth += amount*math.log(z)
            column=min(columns-1,int((px+width*.5)*columns/width))
            row=min(rows-1,int((py+height*.5)*rows/height))
            cells[row*columns+column]+=amount*2*math.pi*weight/(width*height/(columns*rows))
            nearest=min(nearest,z)
    coverage=sum(value>.6 for value in cells)/len(cells)
    coarse_fraction=coarse/mass if mass else 1.
    return dict(available=coverage>=.75 and coarse_fraction<.65,
        detail_coverage=coverage,coarse_fraction=coarse_fraction,
        near=max(1e-9,nearest*.001) if math.isfinite(nearest) else 1e-9,
        detail_depth=math.exp(log_depth/fine_mass) if fine_mass else 0.,
        forward=forward)


def choose_capture_view(splats, retained):
    """For an accepted environment, avoid looking straight into a close wall.

    Keep the conservative forward-view admission test. Once accepted, compare
    the four horizontal directions at the same origin, favouring full coverage
    with small projected Gaussians. No source coordinates or geometry change.
    """
    first = capture_view_score(splats, retained)
    if not first['available']:
        return first
    candidates = [first] + [capture_view_score(splats, retained, direction)
        for direction in ((1.,0.,0.),(0.,0.,-1.),(-1.,0.,0.))]
    return max((view for view in candidates if view['available']),
               key=lambda view: view['detail_coverage']*(1.-view['coarse_fraction'])*
                   math.sqrt(view['detail_depth']/max(first['detail_depth'],1e-300)))


def analyse(cloud, progress=None, limit=8192):
    count = len(cloud.splats)
    if not count:
        raise ValueError('Cannot frame an empty scan.')
    sample_count = min(count, limit)
    positions, radii, sample = [], [], []
    for n in range(sample_count):
        if progress and n % 512 == 0:
            progress('Analyse source', n, sample_count)
        # Include both ends, without favouring the start of an ordered file.
        index = round(n*(count-1)/max(1,sample_count-1))
        splat = cloud.splats[index]
        sample.append(splat)
        positions.append(splat.position)
        radii.append(max(splat.scales))
    axes = [sorted(p[i] for p in positions) for i in range(3)]
    overview_axes = axes
    focus = 'overview'
    if sample_count >= 200:
        median = tuple(a[len(a)//2] for a in axes)
        distances = [math.dist(p,median) for p in positions]
        ordered = sorted(distances)
        middle = ordered[len(ordered)//2]
        # A captured environment can contain a long tail of background splats.
        # Fitting even its central 75% puts the camera outside the capture and
        # behind those coarse background surfaces. Detect the tail at the 95th
        # percentile (the old 90th-percentile test missed real outdoor scans)
        # and start near the dense capture region. This is framing only.
        if middle > 0 and ordered[int(.95*(sample_count-1))] > middle*8:
            radius = ordered[int(.2*(sample_count-1))]
            body = [p for p,d in zip(positions,distances) if d <= radius]
            axes = [sorted(p[i] for p in body) for i in range(3)]
            focus = 'dense central region (distant environment excluded from framing only)'
    # Ignore the outer 0.5% for framing only: floaters/sky envelopes must not
    # make the main scan invisible. No records are deleted or rescaled here.
    trim = int(len(axes[0])*.005) if len(axes[0]) >= 200 else 0
    low = [a[trim] for a in axes]
    high = [a[-trim-1] for a in axes]
    typical_radius = sorted(radii)[len(radii)//2]
    pad = max(typical_radius*3., max(b-a for a,b in zip(low,high))*.01, 1e-12)
    bounds = (tuple(v-pad for v in low), tuple(v+pad for v in high))
    eligible = cloud.metadata.get('eligible_count',cloud.total_count)
    return dict(bounds=bounds, overview_bounds=(tuple(a[0] for a in overview_axes),tuple(a[-1] for a in overview_axes)),
        frame_focus=focus, sample_count=sample_count, retained=count,
        total=cloud.total_count, eligible=eligible, sampled=count < eligible,
        filtered=cloud.total_count-eligible,
        sh_degree=cloud.metadata.get('effective_sh_degree',cloud.metadata.get('sh_degree',0)),
        kind=cloud.metadata.get('kind','gaussian'),
        input_color_space=cloud.metadata.get('input_color_space','srgb'),
        color_space_assumed=cloud.metadata.get('color_space_assumed',True),
        typical_radius=typical_radius,capture_view=choose_capture_view(sample,count))


def corners(bounds):
    return list(itertools.product(*zip(*bounds)))


def fit_camera(points, right, up, forward, horizontal_fov, aspect, margin=1.15):
    """Fit actual transformed bounding corners, preserving a chosen view direction."""
    if not points or not 0 < horizontal_fov < math.pi or not math.isfinite(aspect) or aspect <= 0:
        raise ValueError('Invalid bounds or camera projection.')
    if not all(math.isfinite(v) for p in points for v in p):
        raise ValueError('Source bounds exceed the camera range.')
    forward = g.norm(forward)
    if math.hypot(*g.cross(up,forward)) < 1e-12:
        raise ValueError('Camera up and forward directions are parallel.')
    right = g.norm(g.cross(up,forward))
    up = g.norm(g.cross(forward,right))
    center = tuple((min(p[i] for p in points)+max(p[i] for p in points))*.5 for i in range(3))
    local = [(g.dot(g.sub(p,center),right),g.dot(g.sub(p,center),up),
              g.dot(g.sub(p,center),forward)) for p in points]
    tangent = math.tan(horizontal_fov*.5)
    radius = max(math.hypot(*p) for p in local)
    distance = max(max(abs(x)/tangent,abs(y)*aspect/tangent)*margin-z
                   for x,y,z in local)
    distance = max(distance,radius*.1,1e-9)
    depths = [distance+p[2] for p in local]
    eye = g.sub(center,g.mul(forward,distance))
    return dict(eye=eye,right=right,up=up,forward=forward,target=center,
                near=max(1e-9,min(depths)*.1),far=max(depths)*10.,distance=distance)


def summary(report, scale):
    lo,hi=report['bounds']
    extent=max(b-a for a,b in zip(lo,hi))*scale
    size='small model' if extent < 10 else 'large scene' if extent > 10000 else 'model / scene'
    text='{} | {:,} / {:,} splats | SH{} | {} source colour'.format(
        size,report['retained'],report['total'],report['sh_degree'],report['input_color_space'])
    if report['sampled']:
        text+='\nImport limit reached: {:,} eligible splats; some detail is sampled.'.format(report['eligible'])
    if report['filtered']:
        text+='\nOpacity filter removed {:,} records.'.format(report['filtered'])
    if report['kind']=='point_cloud':
        text+='\nPoint-cloud PLY: original Gaussian shapes/opacity are not present.'
    if report.get('frame_warning'):
        text+='\nAutomatic camera unavailable: '+report['frame_warning']
    return text
