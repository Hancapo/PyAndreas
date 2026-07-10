"""Radar blips and map markers.

    from pysa import blips

    b = blips.add_for_coord((2488, -1666, 13.5), color=blips.COLOR.RED)
    b = blips.add_for_char(some_ped)
    b.scale = 4
    b.remove()
"""
from __future__ import annotations

from enum import IntEnum

from .enums import BLIP_SPRITE
from .math3 import Vector3
from .native import cmd


class COLOR(IntEnum):
    RED = 0
    GREEN = 1
    BLUE = 2
    WHITE = 3
    YELLOW = 4
    PURPLE = 5
    CYAN = 6


class DISPLAY(IntEnum):
    NEITHER = 0
    MARKER_ONLY = 1
    BLIP_ONLY = 2
    BOTH = 3


class Blip:
    """A radar blip handle."""

    __slots__ = ("_handle",)

    def __init__(self, handle: int):
        self._handle = int(handle)

    def __repr__(self) -> str:
        return f"Blip(handle={self._handle})"

    @property
    def handle(self) -> int:
        return self._handle

    @property
    def color(self):
        raise AttributeError("blip color is write-only")

    @color.setter
    def color(self, value: int) -> None:
        cmd.CHANGE_BLIP_COLOUR(self, value)

    @property
    def scale(self):
        raise AttributeError("blip scale is write-only")

    @scale.setter
    def scale(self, value: int) -> None:
        cmd.CHANGE_BLIP_SCALE(self, value)

    def display(self, mode: int = DISPLAY.BOTH) -> None:
        cmd.CHANGE_BLIP_DISPLAY(self, mode)

    def remove(self) -> None:
        cmd.REMOVE_BLIP(self)


def _blip(handle: int) -> Blip:
    return Blip(getattr(handle, "_handle", handle))


def add_for_coord(pos, color: int = None, scale: int = None) -> Blip:
    x, y, z = Vector3.of(pos)
    b = _blip(cmd.ADD_BLIP_FOR_COORD(x, y, z))
    if color is not None:
        b.color = color
    if scale is not None:
        b.scale = scale
    return b


def add_sprite_for_coord(pos, sprite: BLIP_SPRITE) -> Blip:
    """Add a named radar icon at a position."""
    x, y, z = Vector3.of(pos)
    return _blip(cmd.ADD_SPRITE_BLIP_FOR_COORD(x, y, z, sprite))


def add_for_char(ped) -> Blip:
    return _blip(cmd.ADD_BLIP_FOR_CHAR(ped))


def add_for_car(vehicle) -> Blip:
    return _blip(cmd.ADD_BLIP_FOR_CAR(vehicle))


def add_for_object(obj) -> Blip:
    return _blip(cmd.ADD_BLIP_FOR_OBJECT(obj))


def add_for_pickup(pickup) -> Blip:
    return _blip(cmd.ADD_BLIP_FOR_PICKUP(pickup))
