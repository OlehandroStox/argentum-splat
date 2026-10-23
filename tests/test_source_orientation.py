import unittest
from test_native_actions import I, function
from types import SimpleNamespace
from unittest.mock import Mock
from argentum_splat.input_source import coordinate_flip


class OrientationTests(unittest.TestCase):
    def test_new_sog_is_y_up_and_manual_flip_overrides(self):
        self.assertTrue(I.DEFAULTS[I.AUTO_SOG_ORIENTATION])
        self.assertTrue(coordinate_flip('Model.SOG', auto_sog=True))
        self.assertFalse(coordinate_flip('Model.sog', flip_y=True, auto_sog=True))

    def test_legacy_scenes_keep_saved_orientation(self):
        for flip in (False, True):
            self.assertEqual(coordinate_flip('old.sog', flip_y=flip), flip)

    def test_read_migrates_old_disk_level_after_init(self):
        read = function('plugin.py','Read',{'I':I},'SplatObject')
        op={I.AUTO_SOG_ORIENTATION:True}
        hf=SimpleNamespace(ReadInt32=Mock(return_value=1))
        self.assertTrue(read(None,op,hf,0))
        self.assertFalse(op[I.AUTO_SOG_ORIENTATION])
        hf.ReadInt32.assert_not_called()
        for value in (True,False):
            op[I.AUTO_SOG_ORIENTATION]=value
            self.assertTrue(read(None,op,hf,1))
            self.assertEqual(op[I.AUTO_SOG_ORIENTATION],value)

    def test_spz_raw_and_normal_frames_are_unchanged(self):
        for auto in (False, True):
            for manual in (False, True):
                self.assertEqual(coordinate_flip('m.spz', manual, False, auto), not manual)
                self.assertEqual(coordinate_flip('m.spz', manual, True, auto), manual)

    def test_image_ply_and_other_formats_are_not_flipped_twice(self):
        for suffix in ('.ply', '.splat', '.ksplat', ''):
            for manual in (False, True):
                self.assertEqual(coordinate_flip('m'+suffix, manual, auto_sog=True), manual)
