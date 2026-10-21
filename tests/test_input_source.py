import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ArgentumSplat"))
from argentum_splat.input_source import classify, sequence_frame, validate_frame
from argentum_splat.job_progress import read_updates


class InputSourceTests(unittest.TestCase):
    def test_images(self):
        for ext in ('PNG', 'jpg', 'jpeg', 'webp', 'tif', 'tiff', 'bmp', 'tga', 'gif'):
            self.assertEqual(classify('photo.' + ext), 'image')

    def test_splats(self):
        for ext in ('ply', 'sog', 'splat', 'spz', 'ksplat'):
            self.assertEqual(classify('scan.' + ext), 'splat')

    def test_video(self):
        for ext in ('mp4', 'mov', 'avi', 'webm', 'mkv', 'mts', 'm2ts', 'mpeg', 'mpg', 'm4v'):
            self.assertEqual(classify('clip.' + ext), 'video')

    def test_unsupported(self):
        for name in ('scene.c4d', 'script.py', 'data.json', 'image.exr'):
            with self.assertRaises(ValueError):
                classify(name)

    def test_sequence_rejects_video_and_splat(self):
        for name in ('clip.mp4', 'scan.ply'):
            with self.assertRaises(ValueError):
                classify(name, 1)

    def test_invalid_mode(self):
        with self.assertRaises(ValueError):
            classify('photo.png', 2)

    def test_frame_range(self):
        for value in (-1, 100000, .5, True):
            with self.assertRaises(ValueError):
                validate_frame(value)
        self.assertEqual(validate_frame(99999), 99999)

    def test_sequence_offset_from_selected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'shot_v2_0041.PNG'
            expected = path.with_name('shot_v2_0043.PNG')
            expected.touch()
            self.assertEqual(sequence_frame(path, 2), expected)

    def test_sequence_hole_is_error(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'shot0001.png'
            path.touch()
            path.with_name('shot0003.png').touch()
            with self.assertRaisesRegex(ValueError, '0002'):
                sequence_frame(path, 1)

    def test_sequence_requires_number(self):
        with self.assertRaises(ValueError):
            sequence_frame('image.png', 0)


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
