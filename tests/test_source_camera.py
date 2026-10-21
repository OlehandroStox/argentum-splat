"""Reference-camera behavior independent of Torch, CUDA and Cinema 4D."""
import json
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ArgentumSplat" / "backend"))
from source_camera import camera_metadata, decode_camera_token


class SourceCameraTests(unittest.TestCase):
    def assertVector(self, actual, expected):
        for a, b in zip(actual, expected):
            self.assertAlmostEqual(a, b)
        self.assertEqual(len(actual), len(expected))

    def test_perspective_matches_independent_camera_parameters(self):
        distance = 2.5
        half_extent = distance * math.tan(math.radians(50.0) / 2.0)
        result = decode_camera_token([3.0, 4.0, 0.0, 1.0 / distance, half_extent])
        self.assertEqual(result["projection"], "perspective")
        self.assertAlmostEqual(result["fov_degrees"], 50.0)
        self.assertAlmostEqual(result["camera_distance"], distance)
        self.assertVector(result["source"]["eye"], [1.5, 2.0, 0.0])
        self.assertIsNone(result["orthographic_scale"])

    def test_exported_and_cinema_frames_transform_eye_and_up(self):
        result = decode_camera_token([1.0, 2.0, 2.0, 0.5, 0.8])
        self.assertVector(result["source"]["eye"], [2.0 / 3, 4.0 / 3, 4.0 / 3])
        self.assertVector(result["exported_ply"]["eye"], [2.0 / 3, -4.0 / 3, 4.0 / 3])
        self.assertVector(result["c4d_flip_y"]["eye"], [2.0 / 3, 4.0 / 3, 4.0 / 3])
        self.assertVector(result["source"]["up"], [0, 0, 1])
        self.assertVector(result["exported_ply"]["up"], [0, -1, 0])
        self.assertVector(result["c4d_flip_y"]["up"], [0, 1, 0])
        for frame in ("source", "exported_ply", "c4d_flip_y"):
            self.assertVector(result[frame]["target"], [0, 0, 0])

    def test_orthographic_prediction_retains_original_scale(self):
        for reciprocal in (0.0, 0.000999, -0.001):
            result = decode_camera_token([0, -2, 0, reciprocal, 0.8])
            self.assertEqual(result["projection"], "orthographic")
            self.assertVector(result["source"]["eye"], [0, -1000, 0])
            self.assertAlmostEqual(result["orthographic_scale"], 1.6)
            self.assertAlmostEqual(result["fov_radians"], 2 * math.atan(0.8 / 1000))

    def test_exact_orthographic_threshold_is_perspective(self):
        result = decode_camera_token([1, 0, 0, 0.001, 0.8])
        self.assertEqual(result["projection"], "perspective")
        self.assertEqual(result["camera_distance"], 1000.0)

    def test_view_direction_is_normalized_without_changing_raw_token(self):
        token = [100.0, 100.0, 0.0, 0.5, 0.5]
        result = decode_camera_token(token)
        self.assertAlmostEqual(math.hypot(*result["source"]["eye"]), 2.0)
        self.assertEqual(result["raw_token"], token)
        self.assertIsNot(result["raw_token"], token)

    def test_bad_tokens_do_not_abort_a_valid_gaussian_job(self):
        cases = (
            None, [], [1, 2, 3], [1, 2, 3, 4, 5, 6],
            [0, 0, 0, 0.5, 0.5], [0, 0, 1, 0.5, 0.5],
            [0, 0, -1, 0.5, 0.5], [1, 0, 0, 0.5, 0],
            [1, 0, 0, 0.5, -0.5], [1, 0, 0, math.inf, 0.5],
            [math.nan, 0, 0, 0.5, 0.5], [True, 0, 0, 0.5, 0.5],
            ["1", 0, 0, 0.5, 0.5], [1, 0, 0, 0.5, 1e308],
            [1, 0, 0, 0.5, 1e-308],
        )
        for token in cases:
            with self.subTest(token=token):
                metadata = camera_metadata(token)
                self.assertFalse(metadata["available"])
                self.assertTrue(metadata["reason"])
                json.dumps(metadata, allow_nan=False)

    def test_decoder_rejects_singular_inputs_explicitly(self):
        with self.assertRaisesRegex(ValueError, "direction"):
            decode_camera_token([0, 0, 0, 0.5, 0.5])
        with self.assertRaisesRegex(ValueError, "up vector"):
            decode_camera_token([0, 0, 1, 0.5, 0.5])

    def test_success_is_json_safe_and_identifies_estimate_reference(self):
        result = camera_metadata([1, 1, 0, 0.5, 0.8])
        roundtrip = json.loads(json.dumps(result, allow_nan=False))
        self.assertTrue(roundtrip["available"])
        self.assertTrue(roundtrip["is_estimate"])
        self.assertIn("prepared_image_path", roundtrip["image_reference"])
        self.assertEqual(roundtrip["schema_version"], 1)


if __name__ == "__main__":
    unittest.main()
