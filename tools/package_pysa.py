"""Package the pure-Python runtime as one source-based ``pysa.pyz`` archive.

The game imports directly from the archive. Editor installations continue to
use the source tree through ``pip install -e .``.

Usage:  python tools/package_pysa.py [output.pyz]
"""
from __future__ import annotations

import shutil
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "python" / "pysa"
DEFAULT_OUTPUT = ROOT / "dist" / "PyAndreas" / "lib" / "pysa.pyz"
INCLUDE_SUFFIXES = {".py", ".pyi", ".typed"}
ARCHIVE_TIMESTAMP = (2020, 1, 1, 0, 0, 0)


def package(output: Path) -> tuple[int, int]:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")

    files = sorted(path for path in SOURCE.rglob("*")
                   if path.is_file() and path.suffix in INCLUDE_SUFFIXES)
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED,
                         compresslevel=9) as archive:
        for path in files:
            relative = Path("pysa") / path.relative_to(SOURCE)
            info = zipfile.ZipInfo(relative.as_posix(), ARCHIVE_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())

    temporary.replace(output)

    # Remove only the obsolete loose package beside the archive. Resolve and
    # verify the exact location before recursively deleting generated output.
    loose = (output.parent / "pysa").resolve()
    expected = (DEFAULT_OUTPUT.parent / "pysa").resolve()
    if output == DEFAULT_OUTPUT.resolve() and loose == expected and loose.is_dir():
        shutil.rmtree(loose)

    return len(files), output.stat().st_size


def main() -> None:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    count, size = package(output)
    print(f"Packed {count} files into {output.resolve()} ({size:,} bytes)")


if __name__ == "__main__":
    main()
