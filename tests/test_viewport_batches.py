"""Native-facing streaming and preview regressions without rendering emulation."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from test_native_actions import function
from test_scan_scheduling import VALUES
from argentum_splat import core, geometry, ids as I, loading


class Vector(tuple):
    def __new__(cls, *values):
        return tuple.__new__(cls, values)

    def __add__(self, other):
        return Vector(*(a+b for a,b in zip(self, other)))

    def __sub__(self, other):
        return Vector(*(a-b for a,b in zip(self, other)))

    def __mul__(self, scalar):
        return Vector(*(v*scalar for v in self))


class Tag:
    def __init__(self, *args):
        self.values = {}

    def SetName(self, name): self.name = name
    def SetPerPointMode(self, enabled): pass
    def GetDataAddressW(self): return self.values
    def SetSlow(self, index, **values): self.values[index] = values
    def SetAllHighlevelData(self, values): self.values = values
    @staticmethod
    def SetPoint(data, _a, _b, index, value): data[index] = value
    @staticmethod
    def Set(data, index, value): data[index] = value


class Mesh:
    def __init__(self, points, polygons):
        self.points = [None]*points
        self.polygons = [None]*polygons
        self.tags = []

    def SetName(self, name): self.name = name
    def InsertTag(self, tag): self.tags.append(tag)
    def MakeTag(self, kind): pass
    def SetPoint(self, index, point): self.points[index] = point
    def SetPolygon(self, index, polygon): self.polygons[index] = polygon
    def Message(self, message): pass


class ViewportBatchTests(unittest.TestCase):
    def test_assembly_streams_selected_source_points_in_bounded_batches(self):
        clock = [0.]
        def elapsed():
            clock[0] += .001
            return clock[0]
        host = SimpleNamespace(Vector=Vector, Vector4d=Vector, PolygonObject=Mesh,
            UVWTag=Tag, VertexColorTag=Tag, VariableTag=Tag, NormalTag=Tag,
            Tvertexmap=1, Tphong=2, MSG_UPDATE=3, CPolygon=lambda *v:v)
        compile_indices = Mock(side_effect=AssertionError('indices must come from worker'))
        context = dict(c4d=host, core=core,
            geometry=SimpleNamespace(card_indices=compile_indices, gaussian_support=geometry.gaussian_support),
            time=SimpleNamespace(perf_counter=elapsed),__package__='argentum_splat')
        context['gaussian_uv_corners'] = function('plugin.py','gaussian_uv_corners', context)
        build = function('plugin.py','build_mesh_steps',context)
        count = 700
        splats = [core.Splat((i,0,0),(.5,.4,.3),.8,(1,1,1),(1,0,0,0)) for i in range(count)]
        cloud = core.SplatCloud(splats,count)
        prepared = ([s.position for s in splats], [(1,0,0)]*count, [(0,1,0)]*count,
                    [(0,0,1)]*count, [(1,.5,.25)]*count)
        indices = list(range(0,count,2))
        iterator = build(cloud,prepared,None,weights=VALUES,indices=indices)
        progress = []
        while True:
            try: progress.append(next(iterator))
            except StopIteration as finished:
                mesh = finished.value
                break
        compile_indices.assert_not_called()
        steps = [done for stage,done,total in progress if stage == 'Build Gaussian cards']
        self.assertTrue(all(b-a <= 256 for a,b in zip(steps,steps[1:]+[len(indices)])))
        self.assertEqual(len(mesh.points),len(indices)*4)
        self.assertTrue(all(point is not None for point in mesh.points))
        support = geometry.gaussian_support(.8)
        for card,index in enumerate(indices):
            self.assertEqual(mesh.points[card*4],(index-support,-support,0.))
            self.assertEqual(mesh.polygons[card],tuple(range(card*4,card*4+4)))

    def test_camera_updates_reuse_preview_vectors_and_sh0_colours(self):
        vector = Mock(side_effect=lambda *v:tuple(v))
        host = SimpleNamespace(DRAWPASS_OBJECT=1,DRAWRESULT_SKIP=0,DRAWRESULT_OK=2,Vector=vector)
        draw = function('plugin.py','Draw',dict(c4d=host,I=I),'SplatObject')
        spatial,color = loading.preparation_keys(('source',),VALUES,(0,0,-5),0,(0,))
        state = SimpleNamespace(prepared=([(1,2,3),(4,5,6)],[],[],[],[(1,0,0),(0,1,0)]),
            spatial_key=spatial,color_key=color,load_key=('source',),draw_key=None,draw_data=None)
        op = {I.FILE:'scan.splat',I.POINT_PREVIEW:True,I.PREVIEW_COUNT:2}
        bd = SimpleNamespace(SetMatrix_Matrix=Mock(),DrawPoints=Mock())
        bh = SimpleNamespace(GetMg=lambda:None)
        draw(state,op,1,bd,bh)
        original = state.draw_data
        state.spatial_key = (spatial[0],spatial[1],(3.,4.,-5.))
        draw(state,op,1,bd,bh)
        self.assertEqual(vector.call_count,2)
        self.assertIs(state.draw_data[0],original[0])
        self.assertIs(state.draw_data[1],original[1])
        state.color_key = ('new SH colours',)
        state.prepared = state.prepared[:-1]+([(0,0,1),(1,1,0)],)
        draw(state,op,1,bd,bh)
        self.assertEqual(vector.call_count,2)
        self.assertIs(state.draw_data[0],original[0])
        self.assertEqual(state.draw_data[1],[0,0,1,1,1,0])

    def test_parallel_sh_rotation_dirties_generator_without_camera_translation(self):
        direction = [(0.,0.,1.)]
        host = SimpleNamespace(DIRTYFLAGS_DATA=1,EXECUTIONRESULT_OK=0)
        execute = function('plugin.py','Execute',dict(c4d=host,I=I,loading=loading,
            color_configuration_key=lambda doc:(0,),projection_camera=lambda op:(0.,0.,-500.),
            orthographic_direction=lambda op:direction[0]),'SplatObject')
        class Op(dict):
            SetDirty = Mock()
        op = Op({I.CAMERA_FACING:False,I.SH_DEGREE:3,I.SH_STRENGTH:1})
        state = SimpleNamespace(cloud=SimpleNamespace(metadata={'sh_degree':3}),
            last_color_key=(0,),last_camera=('parallel',direction[0]))
        execute(state,op,None,None,None,None)
        op.SetDirty.assert_not_called()
        direction[0] = (1.,0.,0.)
        execute(state,op,None,None,None,None)
        op.SetDirty.assert_called_once_with(1)


if __name__ == '__main__': unittest.main()
