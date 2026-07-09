"""Typed access to raw game-object fields via the generated offset database.

Every wrapped entity exposes `.struct`, a live view over its C++ object:

    ped = player.ped
    print(ped.struct.m_fHealth)        # -> float, read straight from memory
    ped.struct.m_fArmour = 100.0        # writes memory (typed)
    veh.struct.m_fGasPedal = 1.0

Field names and offsets come from plugin-sdk's VALIDATE_OFFSET macros
(pysa/offsets.py). Inheritance is flattened, so a Ped's struct also sees
CPhysical/CEntity/CPlaceable fields.

For fields the generator couldn't type (unions, arrays, bitfields) use the
explicit readers: s.f32(off), s.i32(off), s.u8(off), s.ptr(off), s.bytes(off, n).
`s @ 'member'` gives the absolute address of a field.
"""
from __future__ import annotations

from . import memory
from .offsets import OFFSETS

# Flattened inheritance chains (base -> derived); offsets are absolute so we
# just merge the field maps.
_CHAINS = {
    "CPlaceable": ("CPlaceable",),
    "CEntity": ("CPlaceable", "CEntity"),
    "CPhysical": ("CPlaceable", "CEntity", "CPhysical"),
    "CPed": ("CPlaceable", "CEntity", "CPhysical", "CPed"),
    "CPlayerPed": ("CPlaceable", "CEntity", "CPhysical", "CPed", "CPlayerPed"),
    "CVehicle": ("CPlaceable", "CEntity", "CPhysical", "CVehicle"),
    "CAutomobile": ("CPlaceable", "CEntity", "CPhysical", "CVehicle", "CAutomobile"),
    "CBike": ("CPlaceable", "CEntity", "CPhysical", "CVehicle", "CBike"),
    "CObject": ("CPlaceable", "CEntity", "CPhysical", "CObject"),
}

def _read_i8(addr: int) -> int:
    v = memory.read_u8(addr)
    return v - 0x100 if v >= 0x80 else v


def _read_i16(addr: int) -> int:
    v = memory.read_u16(addr)
    return v - 0x10000 if v >= 0x8000 else v


_READERS = {
    "i8": _read_i8,
    "u8": memory.read_u8,
    "i16": _read_i16,
    "u16": memory.read_u16,
    "i32": memory.read_int,
    "u32": memory.read_u32,
    "f32": memory.read_float,
    "ptr": memory.read_u32,
}
_WRITERS = {
    "i8": memory.write_u8,
    "u8": memory.write_u8,
    "i16": memory.write_u16,
    "u16": memory.write_u16,
    "i32": memory.write_u32,
    "u32": memory.write_u32,
    "f32": memory.write_float,
    "ptr": memory.write_u32,
}


def _merged_fields(cls: str) -> dict:
    out = {}
    for base in _CHAINS.get(cls, (cls,)):
        out.update(OFFSETS.get(base, {}))
    return out


_FIELD_CACHE: dict[str, dict] = {}


class Struct:
    """A typed view over a game object at a fixed address."""

    __slots__ = ("_addr", "_cls", "_fields")

    def __init__(self, address: int, cls: str):
        object.__setattr__(self, "_addr", int(address))
        object.__setattr__(self, "_cls", cls)
        fields = _FIELD_CACHE.get(cls)
        if fields is None:
            fields = _FIELD_CACHE[cls] = _merged_fields(cls)
        object.__setattr__(self, "_fields", fields)

    @property
    def address(self) -> int:
        return self._addr

    def __getattr__(self, name: str):
        field = self._fields.get(name)
        if field is None:
            raise AttributeError(
                f"{self._cls} has no mapped field {name!r} "
                f"(try `dir()` on this struct, or an explicit reader like .f32(off))")
        off, kind = field
        reader = _READERS.get(kind)
        if reader is None:
            return self._addr + off  # untyped: hand back the address
        return reader(self._addr + off)

    def __setattr__(self, name: str, value) -> None:
        field = self._fields.get(name)
        if field is None:
            raise AttributeError(f"{self._cls} has no mapped field {name!r}")
        off, kind = field
        writer = _WRITERS.get(kind)
        if writer is None:
            raise AttributeError(f"{name!r} ({kind}) is not directly writable; "
                                 f"use an explicit writer or memory.write_*")
        writer(self._addr + off, value)

    def __matmul__(self, name: str) -> int:
        """`struct @ 'member'` -> absolute address of that field."""
        field = self._fields.get(name)
        if field is None:
            raise KeyError(name)
        return self._addr + field[0]

    def __dir__(self):
        return list(self._fields) + ["address", "f32", "i32", "u32", "u16",
                                     "u8", "ptr", "bytes"]

    def __repr__(self) -> str:
        return f"Struct({self._cls} @ 0x{self._addr:08X}, {len(self._fields)} fields)"

    # explicit typed accessors at arbitrary offsets ------------------------
    def f32(self, off: int) -> float:
        return memory.read_float(self._addr + off)

    def i32(self, off: int) -> int:
        return memory.read_int(self._addr + off)

    def u32(self, off: int) -> int:
        return memory.read_u32(self._addr + off)

    def u16(self, off: int) -> int:
        return memory.read_u16(self._addr + off)

    def u8(self, off: int) -> int:
        return memory.read_u8(self._addr + off)

    def ptr(self, off: int) -> int:
        return memory.read_u32(self._addr + off)

    def bytes(self, off: int, n: int) -> bytes:
        return memory.read(self._addr + off, n)


def struct_of(entity, cls: str = None) -> Struct:
    """Build a Struct for an entity (or raw address). `cls` defaults per type."""
    if cls is None:
        cls = type(entity).__name__
        cls = {"Ped": "CPed", "Vehicle": "CVehicle",
               "GameObject": "CObject"}.get(cls, cls)
    addr = getattr(entity, "address", entity)
    if not addr:
        raise ValueError("entity has no live address (it may not exist anymore)")
    return Struct(int(addr), cls)
