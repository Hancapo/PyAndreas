import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.package_pysa import package
from tools.package_release import _install, _write_checksum, project_version


class PackagingTests(unittest.TestCase):
    def test_examples_are_opt_in_and_not_live_scripts(self):
        root = Path(__file__).parents[1]
        self.assertFalse(list((root / "scripts").glob("*.py")))
        self.assertTrue((root / "examples" / "example_quickstart.py").is_file())
        self.assertTrue((root / "examples" / "mspark.py").is_file())

    def test_source_archive_is_complete_and_reproducible(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder, "pysa.pyz")
            count, _ = package(output)
            first_hash = hashlib.sha256(output.read_bytes()).digest()
            package(output)
            second_hash = hashlib.sha256(output.read_bytes()).digest()

            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()

        self.assertGreater(count, 30)
        self.assertIn("pysa/__init__.py", names)
        self.assertIn("pysa/_runtime.py", names)
        self.assertIn("pysa/native.pyi", names)
        self.assertIn("pysa/events.pyi", names)
        self.assertIn("pysa/game_events.pyi", names)
        self.assertIn("pysa/type_aliases.py", names)
        self.assertIn("pysa/py.typed", names)
        self.assertNotIn("pysa/__pycache__", "\n".join(names))
        self.assertEqual(first_hash, second_hash)

    def test_release_checksum_and_version_are_machine_verifiable(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder, "release.zip")
            archive.write_bytes(b"release payload")
            checksum = _write_checksum(archive)

            expected = hashlib.sha256(archive.read_bytes()).hexdigest()
            self.assertEqual(checksum.read_text(encoding="ascii"),
                             f"{expected}  release.zip\n")
        self.assertRegex(project_version(), r"^\d+\.\d+\.\d+$")

    def test_install_migrates_only_unmodified_examples_out_of_live_scripts(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            stage = root / "stage"
            game = root / "game"
            examples = stage / "PyAndreas" / "examples"
            examples.mkdir(parents=True)
            (stage / "PyAndreas" / "lib").mkdir(parents=True)
            scripts = game / "PyAndreas" / "scripts"
            scripts.mkdir(parents=True)

            (examples / "same.py").write_text("example", encoding="utf-8")
            (examples / "edited.py").write_text("example", encoding="utf-8")
            (scripts / "same.py").write_text("example", encoding="utf-8")
            (scripts / "edited.py").write_text("user edit", encoding="utf-8")

            _install(stage, game)

            self.assertFalse((scripts / "same.py").exists())
            self.assertEqual((scripts / "edited.py").read_text(encoding="utf-8"),
                             "user edit")
            self.assertTrue((game / "PyAndreas" / "examples" / "same.py").is_file())


if __name__ == "__main__":
    unittest.main()
