import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ArgentumSplat"))
from argentum_splat.input_source import classify, classify_media, validate_frame
from argentum_splat.job_progress import read_updates


class InputSourceTests(unittest.TestCase):
    def test_image_panel_directs_scans_to_scan_panel(self):
        self.assertEqual(classify_media('photo.PNG'), 'image')
        for suffix in ('PLY', 'SOG', 'SPLAT', 'SPZ', 'KSPLAT'):
            for mode in (0, 1):
                with self.assertRaisesRegex(ValueError, 'SCAN > Splat File'):
                    classify_media('scan.' + suffix, mode)

    def test_images(self):
        for ext in ('PNG', 'jpg', 'jpeg', 'webp', 'tif', 'tiff', 'bmp', 'tga', 'gif'):
            self.assertEqual(classify('photo.' + ext), 'image')

    def test_splats(self):
        for ext in ('ply', 'sog', 'splat', 'spz', 'ksplat'):
            self.assertEqual(classify('scan.' + ext), 'splat')

    def test_removed_video_formats_are_rejected(self):
        for ext in ('mp4', 'mov', 'avi', 'webm', 'mkv', 'mts', 'm2ts', 'mpeg', 'mpg', 'm4v'):
            with self.assertRaises(ValueError):
                classify('clip.' + ext)

    def test_unsupported(self):
        for name in ('scene.c4d', 'script.py', 'data.json', 'image.exr'):
            with self.assertRaises(ValueError):
                classify(name)

    def test_removed_sequence_mode_is_rejected(self):
        for name in ('photo.png', 'clip.mp4', 'scan.ply'):
            for mode in (1, 2):
                with self.assertRaises(ValueError):
                    classify(name, mode)

    def test_only_default_frame_is_accepted(self):
        self.assertEqual(validate_frame(0), 0)
        for value in (-1, 1, 99999, .5, True):
            with self.assertRaises(ValueError):
                validate_frame(value)


class ProgressReaderTests(unittest.TestCase):
    def test_partial_utf8_json_write_retained(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'generation.log'
            data = json.dumps({'message': 'Генерация', 'progress': .4}, ensure_ascii=False).encode('utf8') + b'\n'
            path.write_bytes(data[:19])
            items, offset, pending = read_updates(path)
            self.assertEqual(items, [])
            with path.open('ab') as handle:
                handle.write(data[19:])
            items, offset, pending = read_updates(path, offset, pending)
            self.assertEqual(items[0]['message'], 'Генерация')
            self.assertEqual(items[0]['progress'], .4)
            self.assertEqual(pending, b'')
            self.assertEqual(read_updates(path, offset)[0], [])

    def test_noise_and_nonfinite_progress(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'generation.log'
            path.write_text('warning\n[]\n{"message":"hello","progress":NaN}\n', encoding='utf8')
            items, _, _ = read_updates(path)
            self.assertEqual(len(items), 1)
            self.assertIsNone(items[0]['progress'])

    def test_progress_clamped(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'generation.log'
            path.write_text('{"message":"hello","progress":2}\n', encoding='utf8')
            self.assertEqual(read_updates(path)[0][0]['progress'], 1.)

    def test_bounded_read(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'generation.log'
            path.write_bytes(b'x'*1_000_000)
            _, offset, _ = read_updates(path)
            self.assertEqual(offset, 262144)
