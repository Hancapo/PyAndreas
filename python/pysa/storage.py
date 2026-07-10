"""Simple persistent JSON state for scripts.

    state = storage.open("my_mod", {"enabled": True, "score": 0})
    state["score"] += 1
    state.save()  # also flushed automatically on reload/game shutdown
"""
from __future__ import annotations

import json
import re
from collections.abc import MutableMapping
from pathlib import Path

try:
    import _pysa
except ImportError:
    from . import _mock as _pysa


_VALID_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")
_stores = {}


def _directory() -> Path:
    return Path(_pysa.base_dir()) / "data"


def path(name: str, directory=None) -> Path:
    """Return the safe JSON path for a store name."""
    name = str(name)
    if not name or not _VALID_NAME.fullmatch(name) or name in (".", ".."):
        raise ValueError("storage name may contain only letters, numbers, '.', '-' and '_'")
    root = Path(directory) if directory is not None else _directory()
    return root / f"{name}.json"


class Store(MutableMapping):
    """Dictionary-like state backed by one atomic JSON file."""

    __slots__ = ("name", "file", "_data", "dirty")

    def __init__(self, name: str, defaults=None, directory=None):
        self.name = str(name)
        self.file = path(name, directory)
        self._data = dict(defaults or {})
        self.dirty = False
        self.reload()

    def reload(self) -> None:
        if not self.file.is_file():
            return
        try:
            loaded = json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            _pysa.log(f"[pysa] could not load storage {self.name!r}: {exc}")
            return
        if not isinstance(loaded, dict):
            _pysa.log(f"[pysa] ignored non-object storage {self.name!r}")
            return
        self._data.update(loaded)
        self.dirty = False

    def save(self) -> None:
        self.file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.file.with_suffix(self.file.suffix + ".tmp")
        payload = json.dumps(self._data, indent=2, ensure_ascii=False,
                             sort_keys=True, allow_nan=False) + "\n"
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(self.file)
        self.dirty = False

    def reset(self, defaults=None) -> None:
        self._data.clear()
        self._data.update(defaults or {})
        self.dirty = True

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value) -> None:
        self._data[key] = value
        self.dirty = True

    def __delitem__(self, key) -> None:
        del self._data[key]
        self.dirty = True

    def __iter__(self):
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return f"Store({self.name!r}, {self._data!r})"


def open(name: str, defaults=None, directory=None) -> Store:
    """Open or return a cached named store."""
    file = path(name, directory).resolve()
    store = _stores.get(file)
    if store is None:
        store = _stores[file] = Store(name, defaults, directory)
    return store


def flush_all() -> None:
    """Atomically save every open store, including nested-value mutations."""
    for store in tuple(_stores.values()):
        try:
            store.save()
        except (OSError, TypeError, ValueError) as exc:
            _pysa.log(f"[pysa] could not save storage {store.name!r}: {exc}")


def close_all() -> None:
    """Flush and forget cached stores (primarily useful in tests/tools)."""
    flush_all()
    _stores.clear()
