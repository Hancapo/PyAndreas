import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.package_pysa import package


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
        self.assertNotIn("pysa/__pycache__", "\n".join(names))
        self.assertEqual(first_hash, second_hash)


if __name__ == "__main__":
    unittest.main()
