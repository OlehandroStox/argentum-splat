from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ArgentumSplat" / "backend"))
from media_input import load_source
try:
    import av
    from PIL import Image
    MEDIA_AVAILABLE = True
except ImportError:
    MEDIA_AVAILABLE = False


@unittest.skipUnless(MEDIA_AVAILABLE, 'Run with the plugin AI runtime (PyAV and Pillow).')
class MediaInputTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)

    def tearDown(self):
        self.folder.cleanup()

    def video(self, name):
        path = self.root/name
        with av.open(str(path), 'w') as container:
            stream = container.add_stream('mpeg4', rate=24)
            stream.width = stream.height = 64
            stream.pix_fmt = 'yuv420p'
            for color in ('red', 'lime', 'blue'):
                frame = av.VideoFrame.from_image(Image.new('RGB', (64, 64), color))
                for packet in stream.encode(frame):
                    container.mux(packet)
            for packet in stream.encode():
                container.mux(packet)
        return path

    def test_mp4_exact_second_frame(self):
        image, meta = load_source(self.video('тест.mp4'), frame_index=1)
        pixel = image.getpixel((32, 32))
        self.assertGreater(pixel[1], 240)
        self.assertLess(pixel[0], 10)
        self.assertEqual(meta['kind'], 'video')
        self.assertAlmostEqual(meta['timestamp_seconds'], 1/24, places=4)

    def test_mov_third_frame(self):
        image, _ = load_source(self.video('video.mov'), frame_index=2)
        self.assertGreater(image.getpixel((32, 32))[2], 240)

    def test_video_out_of_range(self):
        with self.assertRaises(ValueError):
            load_source(self.video('video.mp4'), frame_index=3)

    def test_corrupt_video_is_error(self):
        path = self.root/'broken.mp4'
        path.write_bytes(b'not a video')
        with self.assertRaises(Exception):
            load_source(path)

    def test_sequence_preserves_alpha(self):
        first = self.root/'shot_0010.png'
        Image.new('RGBA', (32, 32), (20, 40, 80, 110)).save(first)
        target = self.root/'shot_0012.png'
        Image.new('RGBA', (32, 32), (80, 40, 20, 70)).save(target)
        image, meta = load_source(first, mode=1, frame_index=2)
        self.assertEqual(image.getpixel((0, 0)), (80, 40, 20, 70))
        self.assertEqual(meta['selected_path'], str(target))

    def test_still_image_wrong_frame(self):
        path = self.root/'still.jpg'
        Image.new('RGB', (32, 32), 'red').save(path)
        with self.assertRaises(ValueError):
            load_source(path, frame_index=1)

    def test_animated_gif_frame(self):
        path = self.root/'animated.gif'
        Image.new('RGB', (32, 32), 'red').save(path, save_all=True,
            append_images=[Image.new('RGB', (32, 32), 'blue')], duration=100)
        image, _ = load_source(path, frame_index=1)
        self.assertEqual(image.getpixel((0, 0))[:3], (0, 0, 255))

    def test_splat_is_never_sent_to_image_decoder(self):
        path = self.root/'scan.ply'
        path.touch()
        with self.assertRaisesRegex(ValueError, 'loaded directly'):
            load_source(path)
