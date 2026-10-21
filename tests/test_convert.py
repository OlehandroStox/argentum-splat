"""Format helper tests; no Node process or network is needed."""
import importlib.util
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / "ArgentumSplat/backend/convert_splat.py"
spec = importlib.util.spec_from_file_location("convert_splat_test", MODULE)
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


class ConvertTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.package = self.root / "packages-3.10.1"
        self.module = self.package / "node_modules/@playcanvas/splat-transform"
        self.module.joinpath("bin").mkdir(parents=True)
        self.cli = self.module / "bin/cli.mjs"
        self.cli.write_text("// fixture only", encoding="utf8")
        self.module.joinpath("package.json").write_text('{"version":"3.10.1"}', encoding="utf8")
        self.package.joinpath("package-lock.json").write_text("{}", encoding="utf8")
        self.node = self.root / "node.exe"
        self.node.write_bytes(b"fixture, never executed")
        self.manifest = self.root / "formats.json"
        self.data = dict(version="3.10.1", node_exe=str(self.node), cli_js=str(self.cli),
                         package_root=str(self.package),
                         package_lock_sha256=hashlib.sha256(b"{}").hexdigest())
        self.manifest.write_text(json.dumps(self.data), encoding="utf8")

    def tearDown(self):
        self.temp.cleanup()

    def file(self, name, data=b"fixture"):
        path = self.root / name
        path.write_bytes(data)
        return path

    def test_format_detection_uses_headers(self):
        self.assertTrue(c.needs_conversion(self.file("a.sog")))
        self.assertTrue(c.needs_conversion(self.file("b.ksplat")))
        self.assertFalse(c.needs_conversion(self.file("c.splat")))
        self.assertTrue(c.needs_conversion(self.file("d.spz", b"NGSP" + struct.pack("<I", 4))))
        self.assertFalse(c.needs_conversion(self.file("e.spz", b"\x1f\x8b" + b"x"*30)))
        self.assertFalse(c.needs_conversion(self.file("f.spz", b"NG")))
        self.assertTrue(c.needs_conversion(self.file("g.ply", b"ply\nformat binary_little_endian 1.0\nelement chunk 1\n")))
        self.assertTrue(c.needs_conversion(self.file("h.ply", b"ply\nformat binary_little_endian 1.0\nproperty uint packed_position\n")))
        self.assertFalse(c.needs_conversion(self.file("i.ply", b"ply\nformat ascii 1.0\nelement vertex 1\nproperty float x\nend_header\n")))

    def test_command_preserves_file_arguments_and_has_no_processing_actions(self):
        source = self.file("a & b.sog")
        output = self.root / "result.ply"
        argv = c.conversion_command(source, output, self.manifest)
        self.assertEqual(argv, [str(self.node), "--max-old-space-size=8192", str(self.cli),
                                "--gpu", "cpu", "--no-tty", str(source), str(output)])
        self.assertFalse(output.exists())

    def test_existing_output_and_script_input_refused(self):
        source = self.file("source.sog")
        for output in (source, self.file("existing.ply"), self.root/"bad.compressed.ply"):
            with self.subTest(output=output):
                with self.assertRaises(c.ConversionError):
                    c.conversion_command(source, output, self.manifest)
        with self.assertRaises(c.ConversionError):
            c.conversion_command(self.file("code.mjs"), self.root/"out.ply", self.manifest)

    def test_unavailable_or_changed_runtime_refused(self):
        with self.assertRaises(c.ConversionError):
            c.read_runtime(self.root / "missing.json")
        self.package.joinpath("package-lock.json").write_text('{"changed":true}', encoding="utf8")
        with self.assertRaisesRegex(c.ConversionError, "mismatch"):
            c.read_runtime(self.manifest)

    def test_empty_converted_output_refused(self):
        fields = ["x", "y", "z", "f_dc_0", "f_dc_1", "f_dc_2", "opacity",
                  "scale_0", "scale_1", "scale_2", "rot_0", "rot_1", "rot_2", "rot_3"]
        data = ("ply\nformat ascii 1.0\nelement vertex 0\n" +
                "".join("property float "+f+"\n" for f in fields) + "end_header\n").encode()
        with self.assertRaisesRegex(c.ConversionError, "empty"):
            c.validate_converted(self.file("empty.ply", data))


if __name__ == "__main__":
    unittest.main()
