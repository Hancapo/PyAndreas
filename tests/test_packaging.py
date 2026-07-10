import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.package_pysa import package
from tools.package_release import _write_checksum, project_version


class PackagingTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
