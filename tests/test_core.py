"""Run: python -m unittest discover -s tests -p test_core.py -v"""
import dataclasses
import math
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ArgentumSplat"))
from argentum_splat.core import (
    Splat, SplatFormatError, evaluate_sh, gaussian_axes, load,
    source_to_linear, transform_position,
)


FIELDS = ["x", "y", "z", "f_dc_0", "f_dc_1", "f_dc_2", "opacity",
          "scale_0", "scale_1", "scale_2", "rot_0", "rot_1", "rot_2", "rot_3"]
ROW = [1, 2, 3, 0, 0, 0, 0, 0, math.log(2), math.log(3), 1, 0, 0, 0]


def ply_header(count=1, fmt="ascii", extra="", fields=FIELDS, comments=""):
    properties = "".join(f"property float {name}\n" for name in fields)
    return (f"ply\nformat {fmt} 1.0\n{comments}element vertex {count}\n"
            f"{properties}{extra}end_header\n").encode("ascii")


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def file(self, data, suffix=".ply"):
        path = self.folder / ("cloud" + suffix)
        path.write_bytes(data)
        return path

    def ascii(self, rows, extra="", trailer=b"", fields=FIELDS, comments=""):
        data = ply_header(len(rows), extra=extra, fields=fields, comments=comments)
        data += "".join(" ".join(map(str, row)) + "\n" for row in rows).encode("ascii")
        return self.file(data + trailer)

    def test_ascii_gaussian_native_data(self):
        cloud = load(self.ascii([ROW]), color_space="linear")
        splat = cloud.splats[0]
        self.assertEqual(cloud.total_count, 1)
        self.assertEqual(splat.position, (1, 2, 3))
        self.assertEqual(splat.color, (.5, .5, .5))
        self.assertEqual(splat.opacity, .5)
        self.assertAlmostEqual(splat.scales[1], 2)
        self.assertAlmostEqual(splat.scales[2], 3)
        self.assertEqual(splat.rotation, (1, 0, 0, 0))

    def test_binary_both_byte_orders_and_metadata_after_vertices(self):
        for fmt, endian in [("binary_little_endian", "<"), ("binary_big_endian", ">")]:
            with self.subTest(fmt=fmt):
                extra = "element color_space 1\nproperty uchar color_space\n"
                data = ply_header(fmt=fmt, extra=extra) + struct.pack(endian + "14f", *ROW) + b"\x00"
                cloud = load(self.file(data))
                self.assertAlmostEqual(cloud.splats[0].scales[1], 2, places=6)
                self.assertAlmostEqual(cloud.splats[0].color[0], .21404114048223255)
                self.assertFalse(cloud.metadata["color_space_assumed"])

    def test_linear_metadata_is_not_decoded_twice(self):
        extra = "element color_space 1\nproperty uchar color_space\n"
        cloud = load(self.ascii([ROW], extra=extra, trailer=b"1\n"))
        self.assertEqual(cloud.splats[0].color, (.5, .5, .5))
        cloud = load(self.ascii([ROW], comments="comment color_space linearRGB\n"))
        self.assertEqual(cloud.splats[0].color, (.5, .5, .5))

    def test_metadata_conflict(self):
        extra = "element color_space 1\nproperty uchar color_space\n"
        with self.assertRaisesRegex(SplatFormatError, "Conflicting"):
            load(self.ascii([ROW], extra=extra, trailer=b"0\n",
                            comments="comment color_space linearRGB\n"))

    def test_ascii_other_element_list_is_validated(self):
        extra = "element face 1\nproperty list uchar int vertex_indices\n"
        cloud = load(self.ascii([ROW], extra=extra, trailer=b"3 0 0 0\n"))
        self.assertEqual(len(cloud.splats), 1)
        with self.assertRaisesRegex(SplatFormatError, "truncated list"):
            load(self.ascii([ROW], extra=extra, trailer=b"3 0 0\n"))

    def test_binary_list_before_vertex(self):
        prefix = b"ply\nformat binary_big_endian 1.0\nelement face 1\nproperty list uchar int indices\n"
        vertex = b"element vertex 1\n" + b"".join(f"property float {k}\n".encode() for k in FIELDS)
        path = self.file(prefix + vertex + b"end_header\n" +
                         struct.pack(">Biii14f", 3, 0, 1, 2, *ROW))
        self.assertEqual(load(path).splats[0].position, (1, 2, 3))

    def test_truncation_and_trailing_binary(self):
        data = ply_header(fmt="binary_little_endian") + struct.pack("<14f", *ROW)
        for bad in (data[:-1], data + b"x"):
            with self.subTest(size=len(bad)):
                with self.assertRaises(SplatFormatError):
                    load(self.file(bad))
        with self.assertRaises(SplatFormatError):
            load(self.file(ply_header(count=2) + b" ".join(str(v).encode() for v in ROW) + b"\n"))

    def test_nan_infinity_zero_quaternion_scale_overflow_and_underflow(self):
        for index, value in [(0, math.nan), (2, math.inf), (7, 1000), (7, -1000), (10, 0)]:
            row = ROW.copy()
            row[index] = value
            with self.subTest(index=index, value=value):
                with self.assertRaises(SplatFormatError):
                    load(self.ascii([row]))

    def test_validate_unselected_and_transparent_records(self):
        rows = [ROW.copy() for _ in range(50)]
        rows[-1][6] = -1000  # filtered, still invalid and must be checked
        rows[-1][1] = math.nan
        with self.assertRaises(SplatFormatError):
            load(self.ascii(rows), max_splats=1)

    def test_deterministic_bounded_sample_covers_whole_file(self):
        rows = []
        for i in range(1000):
            row = ROW.copy()
            row[0] = i
            rows.append(row)
        path = self.ascii(rows)
        a = load(path, max_splats=20)
        b = load(path, max_splats=20)
        self.assertEqual(a.splats, b.splats)
        self.assertEqual(len(a.splats), 20)
        self.assertEqual(a.total_count, 1000)
        self.assertGreater(max(s.position[0] for s in a.splats), 800)
        self.assertLess(min(s.position[0] for s in a.splats), 200)
        self.assertEqual(a.metadata["bounds"], ((0, 2, 3), (999, 2, 3)))

    def test_opacity_filter_before_sampling(self):
        rows = []
        for i in range(100):
            row = ROW.copy()
            row[0] = i
            row[6] = -1000 if i < 90 else 1000
            rows.append(row)
        cloud = load(self.ascii(rows), max_splats=10)
        self.assertEqual(len(cloud.splats), 10)
        self.assertEqual(cloud.metadata["eligible_count"], 10)
        self.assertTrue(all(s.position[0] >= 90 for s in cloud.splats))

    def test_point_cloud_explicit_radius(self):
        header = (b"ply\nformat ascii 1.0\nelement vertex 1\nproperty float x\n"
                  b"property float y\nproperty float z\nproperty uchar red\n"
                  b"property uchar green\nproperty uchar blue\nend_header\n")
        cloud = load(self.file(header + b"1 2 3 255 128 0\n"), point_radius=.25)
        self.assertEqual(cloud.splats[0].scales, (.25,) * 3)
        self.assertEqual(cloud.splats[0].color[0], 1)
        self.assertAlmostEqual(cloud.splats[0].color[1], .21586050011389926)
        self.assertEqual(cloud.metadata["kind"], "point_cloud")

    def test_partial_gaussian_not_silently_treated_as_point_cloud(self):
        fields = ["x", "y", "z", "f_dc_0"]
        with self.assertRaisesRegex(SplatFormatError, "Incomplete"):
            load(self.ascii([[1, 2, 3, 0]], fields=fields))

    def test_compressed_ply_error_is_actionable(self):
        with self.assertRaisesRegex(SplatFormatError, "PlayCanvas.*uncompressed"):
            load(self.file(ply_header(fields=["packed_position"])))

    def test_splat_layout_and_validation(self):
        data = struct.pack("<6f8B", 1, 2, 3, 1, 2, 3, 255, 128, 0, 128, 255, 128, 128, 128)
        cloud = load(self.file(data, ".splat"))
        self.assertEqual(cloud.splats[0].position, (1, 2, 3))
        self.assertEqual(cloud.splats[0].scales, (1, 2, 3))
        self.assertEqual(cloud.splats[0].rotation, (1, 0, 0, 0))
        self.assertAlmostEqual(cloud.splats[0].opacity, 128 / 255)
        with self.assertRaisesRegex(SplatFormatError, "multiple of 32"):
            load(self.file(data[:-1], ".splat"))
        with self.assertRaisesRegex(SplatFormatError, "NaN"):
            load(self.file(struct.pack("<f", math.nan) + data[4:], ".splat"))
        with self.assertRaisesRegex(SplatFormatError, "zero quaternion"):
            load(self.file(data[:-4] + b"\x80" * 4, ".splat"))

    def test_limits_and_invalid_header(self):
        with self.assertRaises(SplatFormatError):
            load(self.file(ply_header(count=-1)))
        with self.assertRaises(SplatFormatError):
            load(self.file(ply_header(count=100_000_001)))
        with self.assertRaises(ValueError):
            load(self.ascii([ROW]), max_splats=0)
        with self.assertRaises(ValueError):
            load(self.ascii([ROW]), min_opacity=math.nan)
        with self.assertRaises(SplatFormatError):
            load(self.file(ply_header(fields=["x", "x"])))

    def test_empty_cloud(self):
        cloud = load(self.file(ply_header(count=0)))
        self.assertEqual(cloud.total_count, 0)
        self.assertEqual(cloud.splats, [])
        self.assertIsNone(cloud.metadata["bounds"])

    def test_hand_calculated_axes_and_position(self):
        q = math.sqrt(.5)
        splat = Splat((1, 2, 3), (.5,) * 3, .5, (1, 2, 3), (q, 0, 0, q))
        axes = gaussian_axes(splat, global_scale=10, splat_scale=2, flip_y=True)
        expected = ((0, -20, 0), (-40, 0, 0), (0, 0, -60))
        for actual, target in zip(axes, expected):
            for value, wanted in zip(actual, target):
                self.assertAlmostEqual(value, wanted, places=10)
        self.assertEqual(transform_position(splat.position, 10), (10, -20, 30))
        # Positive scalar triple product: proper basis despite Y reflection.
        a, b, c = axes
        determinant = (a[0]*(b[1]*c[2]-b[2]*c[1]) -
                       b[0]*(a[1]*c[2]-a[2]*c[1]) +
                       c[0]*(a[1]*b[2]-a[2]*b[1]))
        self.assertAlmostEqual(determinant, 20*40*60)

    def test_reflected_full_covariance(self):
        q = (.7, .2, .3, .6)
        splat = Splat((0, 0, 0), (.5,) * 3, 1, (1, 2, 4), q)
        before = gaussian_axes(splat, 1, 1, False)
        after = gaussian_axes(splat, 1, 1, True)
        for i in range(3):
            for j in range(3):
                covariance = sum(v[i]*v[j] for v in before)
                reflected = sum(v[i]*v[j] for v in after)
                sign = (-1 if i == 1 else 1) * (-1 if j == 1 else 1)
                self.assertAlmostEqual(reflected, sign * covariance)

    def test_sh0_and_hand_calculated_sh1_channel_major(self):
        rest = [0.0] * 9
        rest[2] = 1  # red: -C1*x
        rest[4] = 2  # green: +C1*z
        rest[6] = 3  # blue: -C1*y
        fields = FIELDS + [f"f_rest_{i}" for i in range(9)]
        cloud = load(self.ascii([ROW + rest], fields=fields), color_space="linear")
        splat = cloud.splats[0]
        self.assertEqual(cloud.metadata["sh_degree"], 1)
        self.assertEqual(evaluate_sh(splat, (1, 0, 0), degree=0), (.5,) * 3)
        self.assertAlmostEqual(evaluate_sh(splat, (1, 0, 0))[0], .5 - .4886025119029199)
        self.assertAlmostEqual(evaluate_sh(splat, (0, 0, 1))[1], .5 + 2*.4886025119029199)
        self.assertAlmostEqual(evaluate_sh(splat, (0, 1, 0))[2], .5 - 3*.4886025119029199)
        self.assertEqual(evaluate_sh(splat, (1, 0, 0), strength=0), (.5,) * 3)

    def test_sh2_sh3_axis_reference(self):
        rest = [0.] * 45
        rest[5] = 1.  # channel red, l2 m0
        rest[15 + 11] = 1.  # channel green, l3 m0
        splat = Splat((0, 0, 1), (.5,) * 3, 1, (1,) * 3, (1, 0, 0, 0),
                      tuple(rest), (.5,) * 3)
        self.assertAlmostEqual(evaluate_sh(splat, (0, 0, 1), degree=2)[0],
                               .5 + 2*.31539156525252005)
        self.assertEqual(evaluate_sh(splat, (0, 0, 1), degree=2)[1], .5)
        self.assertAlmostEqual(evaluate_sh(splat, (0, 0, 1), degree=3)[1],
                               .5 + 2*.3731763325901154)
        with self.assertRaises(ValueError):
            evaluate_sh(splat, (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
