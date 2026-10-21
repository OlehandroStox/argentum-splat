import importlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

PLUGIN_ROOT = Path(__file__).resolve().parents[1] / "ArgentumSplat"
sys.path.insert(0, str(PLUGIN_ROOT))
from argentum_splat import ids as I


class Document:
    def __init__(self, root):
        self.root = root

    def GetDocumentPath(self):
        return str(self.root)


class Object(dict):
    def __init__(self, root):
        super().__init__()
        self.document = Document(root)

    def __getitem__(self, key):
        return self.get(key)

    def GetDocument(self):
        return self.document


class AssetsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stub = types.SimpleNamespace(MSG_GETALLASSETS=100,
            MSG_MULTI_CLEARSUGGESTEDFOLDER=101, ASSETDATA_FLAG_TEXTURESONLY=1)
        with patch.dict(sys.modules, {"c4d": cls.stub}):
            cls.assets = importlib.import_module("argentum_splat.assets")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.op = Object(self.root)
        self.source = self.root / "source.sog"
        self.source.write_bytes(b"test source")
        self.cached = self.root / "converted-unique.ply"
        self.cached.write_bytes(b"test converted")
        self.op[I.FILE] = str(self.source)
        self.op[I.CACHE_FILE] = str(self.cached)
        stat = self.source.stat()
        self.op[I.CACHE_SOURCE] = json.dumps([str(self.source.resolve()), stat.st_mtime_ns, stat.st_size])

    def tearDown(self):
        self.temp.cleanup()

    def test_collects_source_image_and_hidden_cache(self):
        self.op[I.IMAGE] = str(self.root / "input.png")
        data = {"flags": 0, "assets": []}
        self.assets.handle_message(self.op, 100, data)
        self.assertEqual({Path(item["filename"]).name for item in data["assets"]},
                         {"source.sog", "input.png", "converted-unique.ply"})
        self.assertTrue(all(item["bl"] is self.op and not item["netRequestOnDemand"] for item in data["assets"]))
        textures = {"flags": 1, "assets": []}
        self.assets.handle_message(self.op, 100, textures)
        self.assertEqual(len(textures["assets"]), 1)

    def test_save_assets_relocation_accepts_same_content_new_timestamp(self):
        self.assets.handle_message(self.op, 101, None)
        destination = self.root / "packed"
        (destination / "tex").mkdir(parents=True)
        relocated = destination / "tex" / self.source.name
        shutil.copyfile(self.source, relocated)
        shutil.copyfile(self.cached, destination / "tex" / self.cached.name)
        os.utime(relocated, (12345678, 12345678))
        self.op.document.root = destination
        path = self.assets.resolve_path(self.op, self.op[I.FILE])
        self.assertEqual(path, str(relocated))
        self.assertTrue(self.assets.cache_source_matches(path, self.op[I.CACHE_SOURCE]))
        self.assertTrue(Path(self.assets.resolve_path(self.op, self.op[I.CACHE_FILE])).is_file())
        relocated.write_bytes(b"evil source")
        self.assertFalse(self.assets.cache_source_matches(path, self.op[I.CACHE_SOURCE]))

    def test_invalid_cache_is_not_revalidated_by_save(self):
        self.source.write_bytes(b"changed and longer source")
        self.assets.handle_message(self.op, 101, None)
        self.assertFalse(self.assets.cache_source_matches(str(self.source), self.op[I.CACHE_SOURCE]))

    def test_missing_absolute_path_resolves_collected_basename(self):
        self.op[I.FILE] = str(self.root / "old_machine" / self.source.name)
        self.assertEqual(self.assets.resolve_path(self.op, self.op[I.FILE]), str(self.source))

    def test_unrelated_message_has_no_effect(self):
        before = dict(self.op)
        self.assertFalse(self.assets.handle_message(self.op, 99, {}))
        self.assertEqual(before, self.op)


if __name__ == "__main__":
    unittest.main()
