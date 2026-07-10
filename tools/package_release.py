r"""Assemble a complete copy-ready PyAndreas release and ZIP archive.

Usage:
  python tools/package_release.py
  python tools/package_release.py --runtime C:\path\to\python-embed
  python tools/package_release.py --game-dir C:\Games\GTA San Andreas
"""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import zipfile
from pathlib import Path

try:
    from .package_pysa import package as package_pysa
except ImportError:  # direct script execution
    from package_pysa import package as package_pysa


ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
DEFAULT_ASI = ROOT / "plugin" / "bin" / "GTA-SA" / "Release" / "PyAndreas.asi"
DEFAULT_RUNTIME = DIST / "PyAndreas" / "python"
STAGING = DIST / "release"
ARCHIVE_TIMESTAMP = (2020, 1, 1, 0, 0, 0)


def project_version() -> str:
    source = (ROOT / "python" / "pysa" / "_runtime.py").read_text(encoding="utf-8")
    match = re.search(r'^VERSION\s*=\s*["\']([^"\']+)', source, re.M)
    if not match:
        raise RuntimeError("could not read VERSION from pysa._runtime")
    return match.group(1)


def _validate_inputs(asi: Path, runtime: Path) -> None:
    if not asi.is_file():
        raise FileNotFoundError(f"ASI not built: {asi}")
    if not runtime.is_dir():
        raise FileNotFoundError(f"Python runtime directory missing: {runtime}")
    if not (runtime / "python3.dll").is_file():
        raise FileNotFoundError(f"python3.dll missing from runtime: {runtime}")
    if not any(runtime.glob("python3*.zip")):
        raise FileNotFoundError(f"embeddable Python standard-library ZIP missing: {runtime}")


def _safe_clear_staging() -> None:
    target = STAGING.resolve()
    dist = DIST.resolve()
    if target.parent != dist:
        raise RuntimeError(f"refusing to clear unexpected staging path: {target}")
    if target.exists():
        shutil.rmtree(target)


def _write_zip(folder: Path, output: Path) -> None:
    temporary = output.with_suffix(output.suffix + ".tmp")
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED,
                         compresslevel=9) as archive:
        for path in sorted(p for p in folder.rglob("*") if p.is_file()):
            relative = path.relative_to(folder)
            info = zipfile.ZipInfo(relative.as_posix(), ARCHIVE_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    temporary.replace(output)


def _write_checksum(output: Path) -> Path:
    checksum = output.with_suffix(output.suffix + ".sha256")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    checksum.write_text(f"{digest}  {output.name}\n", encoding="ascii")
    return checksum


def _install(stage: Path, game_dir: Path) -> None:
    game_dir = game_dir.resolve()
    if not game_dir.is_dir():
        raise FileNotFoundError(f"game directory does not exist: {game_dir}")
    shutil.copytree(stage, game_dir, dirs_exist_ok=True)

    # With --game-dir the caller explicitly requested installation. Remove
    # only the obsolete loose runtime package, never the editable scripts.
    loose = (game_dir / "PyAndreas" / "lib" / "pysa").resolve()
    expected_parent = (game_dir / "PyAndreas" / "lib").resolve()
    if loose.parent != expected_parent:
        raise RuntimeError(f"refusing to remove unexpected path: {loose}")
    if loose.is_dir():
        shutil.rmtree(loose)


def assemble(asi: Path = DEFAULT_ASI, runtime: Path = DEFAULT_RUNTIME,
             game_dir: Path | None = None) -> tuple[Path, Path]:
    asi = asi.resolve()
    runtime = runtime.resolve()
    _validate_inputs(asi, runtime)
    _safe_clear_staging()

    root = STAGING
    (root / "scripts").mkdir(parents=True)
    (root / "PyAndreas" / "lib").mkdir(parents=True)
    shutil.copy2(asi, root / "scripts" / "PyAndreas.asi")
    shutil.copytree(runtime, root / "PyAndreas" / "python")
    package_pysa(root / "PyAndreas" / "lib" / "pysa.pyz")
    shutil.copytree(ROOT / "scripts", root / "PyAndreas" / "scripts",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(ROOT / "LICENSE", root / "LICENSE")
    if (ROOT / "CHANGELOG.md").is_file():
        shutil.copy2(ROOT / "CHANGELOG.md", root / "CHANGELOG.md")

    (root / "INSTALL.txt").write_text(
        f"PyAndreas {project_version()}\n\n"
        "Requirements: GTA San Andreas PC 1.0 US and an installed ASI loader.\n"
        "Copy the contents of this folder into the GTA San Andreas game root.\n"
        "The ASI belongs in scripts\\; user Python files belong in "
        "PyAndreas\\scripts\\. Press F11 in game to reload scripts.\n",
        encoding="utf-8",
    )

    output = DIST / f"PyAndreas-{project_version()}-win32.zip"
    _write_zip(root, output)
    _write_checksum(output)
    if game_dir is not None:
        _install(root, game_dir)
    return root, output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asi", type=Path, default=DEFAULT_ASI)
    parser.add_argument("--runtime", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--game-dir", type=Path)
    args = parser.parse_args()
    folder, archive = assemble(args.asi, args.runtime, args.game_dir)
    print(f"Release folder: {folder}")
    print(f"Release archive: {archive} ({archive.stat().st_size:,} bytes)")
    print(f"SHA-256: {archive.with_suffix(archive.suffix + '.sha256')}")


if __name__ == "__main__":
    main()
