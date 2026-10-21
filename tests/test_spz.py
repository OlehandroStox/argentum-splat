"""SPZ decoding fixtures from the published Niantic wire-format specification."""
import gzip
import math
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ArgentumSplat"))
from argentum_splat.core import SplatFormatError, evaluate_sh, load
from argentum_splat.spz import decode_spz, coordinate_metadata


def fixed24(number, bits=12):
    return (round(number * (1 << bits)) & 0xFFFFFF).to_bytes(3, "little")


def fixture(version=3, positions=((1, 2, -3),), alphas=None, rotations=None, sh=(), degree=0,
            flags=0, bits=12, color=(128, 192, 64)):
    count = len(positions)
    header = struct.pack("<IIIBBBB", 0x5053474E, version, count, degree, bits, flags, 0)
    # v3 word 0xC0000000 means xyzw=(0,0,0,1), exact identity.
    default_rotation = bytes((128, 128, 128)) if version == 2 else b"\0\0\0\xc0"
    arrays = b"".join(fixed24(v, bits) for p in positions for v in p)
    arrays += bytes(alphas if alphas is not None else [255] * count)
    arrays += bytes(color) * count
    arrays += bytes((160, 176, 144)) * count  # sigma=(1,e,1/e)
    arrays += b"".join(rotations) if rotations is not None else default_rotation * count
    arrays += bytes(sh) * count
    return gzip.compress(header + arrays)


class SpzTests(unittest.TestCase):
    def test_v3_exact_identity_colors_alpha_and_scales(self):
        cloud = decode_spz(fixture(alphas=[127]), color_space="linear")
        splat = cloud.splats[0]
        self.assertEqual(splat.position, (1, -2, 3))
        self.assertEqual(splat.rotation, (1, 0, 0, 0))
        self.assertAlmostEqual(splat.scales[1], math.e)
        self.assertAlmostEqual(splat.scales[2], 1 / math.e)
        self.assertAlmostEqual(splat.opacity, 127 / 255)
        self.assertAlmostEqual(splat.raw_color[0], .5 + .28209479177387814 * ((128 / 255 - .5) / .15))
        self.assertEqual(cloud.metadata["coordinates"], "RDF")

    def test_unconverted_means_rotation_and_sh(self):
        # v2 +X=1, Y/Z quantized near zero; demonstrates the normalization.
        data = fixture(version=2, rotations=[bytes((255, 128, 128))],
                       degree=1, sh=(160, 192, 224, 144, 176, 208, 136, 152, 168))
        native = decode_spz(data, unconverted_coordinates=True).splats[0]
        converted = decode_spz(data).splats[0]
        self.assertEqual(native.position, (1, 2, -3))
        self.assertEqual(converted.position, (1, -2, 3))
        self.assertEqual(converted.rotation, (native.rotation[0], native.rotation[1],
                                              -native.rotation[2], -native.rotation[3]))
        self.assertEqual(native.sh, (.25, .125, .0625, .5, .375, .1875, .75, .625, .3125))
        self.assertEqual(converted.sh, (-.25, -.125, .0625, -.5, -.375, .1875, -.75, -.625, .3125))

    def test_sh_color_is_invariant_under_coordinate_conversion(self):
        wire = tuple(128 + ((i * 17) % 113) for i in range(45))
        data = fixture(degree=3, sh=wire)
        a = decode_spz(data, unconverted_coordinates=True).splats[0]
        b = decode_spz(data).splats[0]
        ca = evaluate_sh(a, (.3, .5, .7), degree=3)
        cb = evaluate_sh(b, (.3, -.5, -.7), degree=3)
        for left, right in zip(ca, cb):
            self.assertAlmostEqual(left, right, places=12)

    def test_v3_non_identity_smallest_three_signed_magnitudes(self):
        # Largest component is x. Stored y=-100, z=200, w=-300 (9-bit magnitudes).
        word = ((512 + 100) << 20) | (200 << 10) | (512 + 300)
        data = fixture(rotations=[struct.pack("<I", word)])
        q = decode_spz(data, unconverted_coordinates=True).splats[0].rotation
        self.assertAlmostEqual(q[0], -math.sqrt(.5) * 300 / 511)
        self.assertAlmostEqual(q[2], -math.sqrt(.5) * 100 / 511)
        self.assertAlmostEqual(q[3], math.sqrt(.5) * 200 / 511)
        self.assertAlmostEqual(sum(x*x for x in q), 1.0)

    def test_filtering_and_deterministic_whole_file_sampling(self):
        positions = tuple((float(i), 0, 0) for i in range(100))
        data = fixture(positions=positions, alphas=[0] * 50 + [255] * 50)
        a = decode_spz(data, max_splats=5)
        b = decode_spz(data, max_splats=5)
        self.assertEqual(a, b)
        self.assertEqual(a.metadata["filtered_count"], 50)
        self.assertEqual(a.metadata["eligible_count"], 50)
        self.assertEqual(len(a.splats), 5)
        self.assertTrue(all(s.position[0] >= 50 for s in a.splats))
        self.assertEqual(a.metadata["bounds"], ((0, 0, 0), (99, 0, 0)))

    def test_gzip_crc_truncation_and_array_truncation(self):
        valid = fixture()
        for data in (valid[:-2], valid[:-8] + b"\xff" * 8, gzip.compress(gzip.decompress(valid)[:-1])):
            with self.subTest(data=data[-8:]):
                with self.assertRaises(SplatFormatError):
                    decode_spz(data)

    def test_trailing_data_and_unknown_flags_rejected(self):
        for data in (gzip.compress(gzip.decompress(fixture()) + b"extra"), fixture(flags=2), fixture(flags=4)):
            with self.assertRaises(SplatFormatError):
                decode_spz(data)

    def test_unsupported_formats_are_clear(self):
        with self.assertRaisesRegex(SplatFormatError, "ZSTD"):
            decode_spz(b"NGSP" + struct.pack("<I", 4) + b"\0" * 24)
        raw = bytearray(gzip.decompress(fixture()))
        raw[4:8] = struct.pack("<I", 1)
        with self.assertRaisesRegex(SplatFormatError, "version 1"):
            decode_spz(gzip.compress(raw))
        raw[4:8] = struct.pack("<I", 3)
        raw[12] = 4
        with self.assertRaisesRegex(SplatFormatError, "degree 4"):
            decode_spz(gzip.compress(raw))

    def test_bounded_decompression_and_malformed_quaternion(self):
        with patch("argentum_splat.spz.MAX_DECOMPRESSED_BYTES", 10):
            with self.assertRaisesRegex(SplatFormatError, "limit"):
                decode_spz(fixture())
        with self.assertRaisesRegex(SplatFormatError, "quaternion"):
            decode_spz(fixture(version=2, rotations=[b"\xff\xff\xff"]))
        with self.assertRaisesRegex(SplatFormatError, "quaternion"):
            decode_spz(fixture(rotations=[b"\xff\xff\xff\xff"]))

    def test_core_dispatch_and_color_assumption(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "test.spz"
            path.write_bytes(fixture())
            cloud = load(path, unconverted_coordinates=True)
            self.assertEqual(cloud.splats[0].position, (1, 2, -3))
            self.assertTrue(cloud.metadata["color_space_assumed"])
            self.assertEqual(cloud.metadata["input_color_space"], "srgb")
            self.assertEqual(cloud.metadata["source"], str(path.resolve()))
            self.assertEqual(coordinate_metadata(2)["rotation_encoding"], "xyz8")
            self.assertEqual(coordinate_metadata(3)["rotation_encoding"], "smallest-three32")


if __name__ == "__main__":
    unittest.main()
