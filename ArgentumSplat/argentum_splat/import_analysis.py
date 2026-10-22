"""Bounded, deterministic source analysis; no host API or third-party packages."""
import itertools
import math
from . import geometry as g


def analyse(cloud, progress=None, limit=8192):
    count = len(cloud.splats)
    if not count:
        raise ValueError('Cannot frame an empty scan.')
    sample_count = min(count, limit)
    positions, radii = [], []
    for n in range(sample_count):
        if progress and n % 512 == 0:
            progress('Analyse source', n, sample_count)
        # Include both ends, without favouring the start of an ordered file.
        index = round(n*(count-1)/max(1,sample_count-1))
        splat = cloud.splats[index]
        positions.append(splat.position)
        radii.append(max(splat.scales))
    axes = [sorted(p[i] for p in positions) for i in range(3)]
    # Ignore the outer 0.5% for framing only: floaters/sky envelopes must not
    # make the main scan invisible. No records are deleted or rescaled here.
    trim = int(sample_count*.005) if sample_count >= 200 else 0
    low = [a[trim] for a in axes]
    high = [a[-trim-1] for a in axes]
    typical_radius = sorted(radii)[len(radii)//2]
    pad = max(typical_radius*3., max(b-a for a,b in zip(low,high))*.01, 1e-12)
    bounds = (tuple(v-pad for v in low), tuple(v+pad for v in high))
    eligible = cloud.metadata.get('eligible_count',cloud.total_count)
    return dict(bounds=bounds, sample_count=sample_count, retained=count,
        total=cloud.total_count, eligible=eligible, sampled=count < eligible,
        filtered=cloud.total_count-eligible,
        sh_degree=cloud.metadata.get('effective_sh_degree',cloud.metadata.get('sh_degree',0)),
        kind=cloud.metadata.get('kind','gaussian'),
        input_color_space=cloud.metadata.get('input_color_space','srgb'),
        color_space_assumed=cloud.metadata.get('color_space_assumed',True),
        typical_radius=typical_radius)


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
