import json
import tempfile
import unittest
from pathlib import Path

from pysa import _runtime, storage


class StorageTests(unittest.TestCase):
    def setUp(self):
        storage._stores.clear()

    def tearDown(self):
        storage._stores.clear()

    def test_store_round_trip_preserves_defaults_and_values(self):
        with tempfile.TemporaryDirectory() as folder:
            state = storage.open("example", {"enabled": True, "score": 0}, folder)
            state["score"] = 42
            state.save()
            storage._stores.clear()

            loaded = storage.open("example", {"enabled": False}, folder)

            self.assertEqual(dict(loaded), {"enabled": True, "score": 42})

    def test_shutdown_flushes_nested_mutations_atomically(self):
        with tempfile.TemporaryDirectory() as folder:
            state = storage.open("nested", {"items": []}, folder)
            state["items"].append("infernus")

            _runtime.dispatch_simple("shutdown")

            saved = json.loads(Path(folder, "nested.json").read_text(encoding="utf-8"))
            self.assertEqual(saved, {"items": ["infernus"]})
            self.assertFalse(Path(folder, "nested.json.tmp").exists())

    def test_names_cannot_escape_storage_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ("", "..", "../escape", "folder/name", "bad name"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    storage.open(name, directory=folder)


if __name__ == "__main__":
    unittest.main()
