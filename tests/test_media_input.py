from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ArgentumSplat" / "backend"))
from media_input import load_source
try:
    from PIL import Image
    MEDIA_AVAILABLE = True
except ImportError:
    MEDIA_AVAILABLE = False


@unittest.skipUnless(MEDIA_AVAILABLE, 'Run with the plugin AI runtime (Pillow).')
class MediaInputTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)

    def tearDown(self):
        self.folder.cleanup()

    def test_video_is_rejected(self):
        for suffix in ('.mp4', '.mov', '.webm'):
            path = self.root/('clip'+suffix)
            path.write_bytes(b'video placeholder')
            with self.assertRaisesRegex(ValueError, 'still'):
                load_source(path)

    def test_still_preserves_alpha(self):
        path = self.root/'still.png'
        Image.new('RGBA', (32, 24), (20, 40, 80, 110)).save(path)
        image, meta = load_source(path)
        self.assertEqual(image.getpixel((0, 0)), (20, 40, 80, 110))
        self.assertEqual(meta['selected_path'], str(path.resolve()))
        self.assertEqual(meta['kind'], 'image')
        self.assertEqual(meta['resolution'], {'width': 32, 'height': 24})

    def test_sequence_is_rejected(self):
        path = self.root/'shot_0001.png'
        Image.new('RGB', (32, 32), 'red').save(path)
        with self.assertRaisesRegex(ValueError, 'one still picture'):
            load_source(path, mode=1)

    def test_still_image_wrong_frame(self):
        path = self.root/'still.jpg'
        Image.new('RGB', (32, 32), 'red').save(path)
        with self.assertRaises(ValueError):
            load_source(path, frame_index=1)

    def test_animated_gif_frame(self):
        path = self.root/'animated.gif'
        Image.new('RGB', (32, 32), 'red').save(path, save_all=True,
            append_images=[Image.new('RGB', (32, 32), 'blue')], duration=100)
        with self.assertRaisesRegex(ValueError, 'animated or multipage'):
            load_source(path)

    def test_splat_is_never_sent_to_image_decoder(self):
        path = self.root/'scan.ply'
        path.touch()
        with self.assertRaisesRegex(ValueError, 'SCAN > Splat File'):
            load_source(path)
