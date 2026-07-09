"""Direct process-memory access.

Reads and writes are SEH-guarded in the plugin: a bad address raises
ValueError instead of crashing the game. Writes to code pages need
unprotect=True.

    from pysa import memory
    gravity = memory.read_float(0x863984)
    memory.write_float(0x863984, 0.002)          # moon gravity
    memory.patch(0x969C60, b"\\x01")             # example byte patch
"""
from __future__ import annotations

import struct

try:
    import _pysa
except ImportError:
    from . import _mock as _pysa

read = _pysa.mem_read
write = _pysa.mem_write
read_u8 = _pysa.read_u8
read_u16 = _pysa.read_u16
read_u32 = _pysa.read_u32
read_int = _pysa.read_i32
read_float = _pysa.read_f32
write_u8 = _pysa.write_u8
write_u16 = _pysa.write_u16
write_u32 = _pysa.write_u32
write_float = _pysa.write_f32


def read_vec3(addr: int):
    """Read three consecutive floats (e.g. a CVector)."""
    x, y, z = struct.unpack("<fff", read(addr, 12))
    return (x, y, z)


def write_vec3(addr: int, xyz) -> None:
    x, y, z = xyz
    write(addr, struct.pack("<fff", x, y, z))


def read_str(addr: int, max_len: int = 64, encoding: str = "latin-1") -> str:
    """Read a NUL-terminated string."""
    raw = read(addr, max_len)
    return raw.split(b"\0", 1)[0].decode(encoding, errors="replace")


def patch(addr: int, data: bytes) -> bytes:
    """Overwrite code/data bytes (handles page protection). Returns the old bytes."""
    old = read(addr, len(data))
    write(addr, data, True)
    return old


def nop(addr: int, count: int) -> bytes:
    """Replace `count` bytes with x86 NOPs. Returns the old bytes."""
    return patch(addr, b"\x90" * count)
