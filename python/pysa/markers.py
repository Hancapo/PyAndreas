"""World markers: checkpoints, 3D markers and collision spheres.

    from pysa import markers, player

    cp = markers.Checkpoint(player.pos + (0, 20, 0))     # a ring on the ground
    m = markers.Marker3D(player.pos + (0, 10, 2))         # a floating arrow
    zone = markers.Sphere(player.pos, radius=15)          # an invisible trigger

    if zone.contains(player.pos):
        ...
    cp.remove(); m.remove(); zone.remove()

These wrap the create/move/remove script commands as small objects so you can
hold on to them and clean them up, instead of juggling raw handles.
"""
from __future__ import annotations

from enum import IntEnum

try:
    import _pysa
except ImportError:
    from . import _mock as _pysa

from .math3 import Vector3
from .native import cmd


class CHECKPOINT(IntEnum):
    """Checkpoint visual types (the `type` argument)."""
    TUBE_ARROW = 0
    ARROW_LARGE = 0     # backward-compatible name
    TUBE_END = 1
    ARROW_SMALL = 1     # backward-compatible name
    TUBE = 2
    TORUS = 3
    TORUS_NO_FADE = 4
    TORUS_ROTATING = 5
    TORUS_THROUGH = 6
    TORUS_UP_DOWN = 7
    TORUS_DOWN = 8


class Checkpoint:
    """A race-style checkpoint (a coloured ring/arrow marker in the world)."""

    __slots__ = ("_handle", "_pos", "_direction", "_color")

    def __init__(self, pos, kind: int = CHECKPOINT.TUBE, points_to=None,
                 radius: float = 6.0):
        x, y, z = Vector3.of(pos)
        if points_to is None:
            px, py, pz = x, y, z
        else:
            px, py, pz = Vector3.of(points_to)
        self._handle = cmd.CREATE_CHECKPOINT(kind, x, y, z, px, py, pz, radius)
        self._pos = Vector3(x, y, z)
        target = Vector3(px, py, pz)
        delta = target - self._pos
        self._direction = delta.normalized() if delta.length else Vector3(0, 1, 0)
        self._color = (255, 255, 255, 255)

    @property
    def handle(self) -> int:
        return self._handle

    @property
    def pos(self) -> Vector3:
        return self._pos

    @pos.setter
    def pos(self, value) -> None:
        x, y, z = Vector3.of(value)
        cmd.SET_CHECKPOINT_COORDS(self._handle, x, y, z)
        self._pos = Vector3(x, y, z)

    @property
    def direction(self) -> Vector3:
        return self._direction

    @direction.setter
    def direction(self, value) -> None:
        self.update_visual(direction=value)

    @property
    def color(self) -> tuple[int, int, int, int]:
        return self._color

    @color.setter
    def color(self, value) -> None:
        self.update_visual(color=value)

    def update_visual(self, pos=None, direction=None, color=None) -> bool:
        """Update position, direction and RGBA without fixed memory addresses."""
        new_pos = self._pos if pos is None else Vector3.of(pos)
        new_direction = (self._direction if direction is None
                         else Vector3.of(direction))
        if color is None:
            rgba = self._color
        else:
            values = tuple(int(v) for v in color)
            if len(values) == 3:
                values += (255,)
            if len(values) != 4:
                raise ValueError("checkpoint color must be RGB or RGBA")
            rgba = tuple(max(0, min(255, value)) for value in values)
        updated = _pysa.checkpoint_update(
            self._handle, *new_pos, *new_direction, *rgba)
        if updated:
            self._pos = new_pos
            self._direction = new_direction
            self._color = rgba
        return bool(updated)

    @property
    def heading(self):
        raise AttributeError("checkpoint heading is write-only")

    @heading.setter
    def heading(self, degrees: float) -> None:
        cmd.SET_CHECKPOINT_HEADING(self._handle, float(degrees))

    def remove(self) -> None:
        cmd.DELETE_CHECKPOINT(self._handle)

    def __repr__(self) -> str:
        return f"Checkpoint(handle={self._handle})"


class Marker3D:
    """A floating user marker (the bouncing icon used for objectives)."""

    __slots__ = ("_handle",)

    def __init__(self, pos, color: int = 0):
        x, y, z = Vector3.of(pos)
        self._handle = cmd.CREATE_USER_3D_MARKER(x, y, z, color)

    @property
    def handle(self) -> int:
        return self._handle

    def remove(self) -> None:
        cmd.REMOVE_USER_3D_MARKER(self._handle)

    def __repr__(self) -> str:
        return f"Marker3D(handle={self._handle})"


class Sphere:
    """An invisible collision/trigger sphere. Handy as an area you can test."""

    __slots__ = ("_handle", "_center", "_radius")

    def __init__(self, center, radius: float = 10.0):
        self._center = Vector3.of(center)
        self._radius = float(radius)
        x, y, z = self._center
        self._handle = cmd.ADD_SPHERE(x, y, z, self._radius)

    @property
    def handle(self) -> int:
        return self._handle

    @property
    def center(self) -> Vector3:
        return self._center

    @property
    def radius(self) -> float:
        return self._radius

    def contains(self, target) -> bool:
        """True if a position or entity is inside the sphere."""
        pos = target.pos if hasattr(target, "pos") else target
        return self._center.distance_to(pos) <= self._radius

    def remove(self) -> None:
        cmd.REMOVE_SPHERE(self._handle)

    def __contains__(self, target) -> bool:
        return self.contains(target)

    def __repr__(self) -> str:
        return f"Sphere(center={self._center}, radius={self._radius})"
