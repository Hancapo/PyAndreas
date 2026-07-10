# Release checklist

1. Run `python -m compileall -q python examples tools tests`.
2. Run `python -m unittest discover -s tests -v`.
3. Build and package with `tools\build_release.ps1` using the supported Win32
   Python runtime and plugin-sdk build.
4. Confirm the native build has zero warnings and errors.
5. Test a clean install on GTA San Andreas PC 1.0 US with an ASI loader:
   startup, F11 reload, a spawned vehicle, drawing, persistence, and shutdown.
6. Verify the ZIP using the adjacent `.sha256` file.
7. Confirm bundled examples are under `PyAndreas\examples` and that
   `PyAndreas\scripts` contains no automatically enabled `.py` files.
8. Update `CHANGELOG.md`, then tag the exact version reported by
   `pysa.__version__`.
