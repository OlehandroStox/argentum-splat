import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from test_native_actions import function, Op, I


class SceneSetupPolicyTests(unittest.TestCase):
    def context(self):
        op=Op({I.CAMERA:None,I.IMPORT_CAMERA:None,I.IMPORT_CAMERA_STATE:'saved',
               I.AUTO_FRAME:True,I.AUTO_FRAME_SOURCE:''})
        op.GetUp=lambda:None
        op.GetDown=lambda:None
        bd=SimpleNamespace(GetSceneCamera=lambda doc:None,GetEditorCamera=lambda:None)
        op.doc=SimpleNamespace(GetRenderBaseDraw=lambda:bd,GetObjects=lambda:[op])
        context=dict(I=I,json=json,camera_state=lambda cam:'saved')
        available=function('scene_setup.py','automatic_available',context)
        function('scene_setup.py','source_marker',context)
        needs=function('scene_setup.py','needs_initial_analysis',context)
        return op,bd,context,available,needs

    def test_empty_scene_and_untouched_owned_camera_are_eligible(self):
        op,bd,ctx,available,needs=self.context()
        self.assertTrue(available(op))
        editor=object();bd.GetSceneCamera=lambda doc:editor;bd.GetEditorCamera=lambda:editor
        self.assertTrue(available(op))
        owned=object();op[I.IMPORT_CAMERA]=owned
        bd.GetSceneCamera=lambda doc:owned
        op.doc.GetObjects=lambda:[op,owned]
        self.assertTrue(available(op))
        self.assertTrue(needs(op,('scan',1,2,3000000)))
        op[I.AUTO_FRAME_SOURCE]=json.dumps(('scan',1,2))
        self.assertFalse(needs(op,('scan',1,2,1000)))
        self.assertTrue(needs(op,('other',1,2,1000)))

    def test_user_camera_override_other_content_and_parent_block_automatic_reframing(self):
        op,bd,ctx,available,needs=self.context()
        bd.GetSceneCamera=lambda doc:object()
        self.assertFalse(available(op))
        bd.GetSceneCamera=lambda doc:None
        op[I.CAMERA]=object()
        self.assertFalse(available(op))
        op[I.CAMERA]=None
        op.doc.GetObjects=lambda:[op,object()]
        self.assertFalse(available(op))
        op.doc.GetObjects=lambda:[op]
        op.GetUp=lambda:object()
        self.assertFalse(available(op))
        op.GetUp=lambda:None
        op.GetDown=lambda:object()
        self.assertFalse(available(op))

    def test_editing_generated_camera_or_disabling_auto_is_respected(self):
        op,bd,ctx,available,needs=self.context()
        owned=object();op[I.IMPORT_CAMERA]=owned
        bd.GetSceneCamera=lambda doc:owned
        op.doc.GetObjects=lambda:[op,owned]
        ctx['camera_state']=lambda cam:'user edited'
        self.assertFalse(available(op))
        bd.GetSceneCamera=lambda doc:None
        self.assertFalse(available(op))
        op[I.AUTO_FRAME]=False
        self.assertFalse(needs(op,('scan',1,2)))

    def test_adjacent_ai_metadata_must_match_the_actual_source(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'house.ply'
            metadata=Path(folder)/'generation.json'
            metadata.write_text(json.dumps(dict(ply_path=str(source),source_camera={'available':True})))
            op=Op({I.FILE:str(source)})
            reader=function('quality.py','source_camera_data',dict(Path=Path,json=json,I=I,
                assets=SimpleNamespace(resolve_path=lambda op,path:path)))
            self.assertTrue(reader(op,require_match=True)['available'])
            op[I.FILE]=str(Path(folder)/'unrelated.ply')
            with self.assertRaisesRegex(ValueError,'another source'):
                reader(op,require_match=True)

    def test_summary_refreshes_when_limit_changes_without_reframing(self):
        from unittest.mock import Mock
        from argentum_splat import import_analysis
        report=dict(bounds=((0,0,0),(1,1,1)),retained=10,total=100,eligible=100,
                    sampled=True,filtered=0,sh_degree=3,input_color_space='srgb',kind='gaussian')
        op=Op({I.AUTO_FRAME_SOURCE:json.dumps(('file',1,2)),I.SOURCE_INFO:'old',I.AUTO_FRAME:False,I.SCALE:100})
        op.doc=SimpleNamespace(StartUndo=Mock(),EndUndo=Mock(),AddUndo=Mock())
        ctx=dict(json=json,I=I,import_analysis=import_analysis,c4d=SimpleNamespace(UNDOTYPE_CHANGE=1))
        function('scene_setup.py','source_marker',ctx)
        finish=function('scene_setup.py','finish_import',ctx)
        finish(op,('file',1,2,10),report)
        self.assertIn('10 / 100',op[I.SOURCE_INFO])
        op.doc.StartUndo.assert_called_once()
        finish(op,('file',1,2,10),report)
        op.doc.StartUndo.assert_called_once()


if __name__=='__main__':unittest.main()
