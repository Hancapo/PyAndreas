"""3D vector math for game coordinates."""
from __future__ import annotations

import math


class Vector3:
    """A simple 3D vector. Supports +, -, * (scalar), /, ==, iteration and unpacking."""

    __slots__ = ("x", "y", "z")

    def __init__(self, x: float = 0.0, y: float = 0.0, z: float = 0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    @classmethod
    def of(cls, value) -> "Vector3":
        """Coerce a Vector3, tuple or list into a Vector3."""
        if isinstance(value, Vector3):
            return value
        return cls(*value)

    def __iter__(self):
        yield self.x
        yield self.y
        yield self.z

    def __add__(self, other) -> "Vector3":
        o = Vector3.of(other)
        return Vector3(self.x + o.x, self.y + o.y, self.z + o.z)

    def __sub__(self, other) -> "Vector3":
        o = Vector3.of(other)
        return Vector3(self.x - o.x, self.y - o.y, self.z - o.z)

    def __mul__(self, k: float) -> "Vector3":
        return Vector3(self.x * k, self.y * k, self.z * k)

    __rmul__ = __mul__

    def __truediv__(self, k: float) -> "Vector3":
        return Vector3(self.x / k, self.y / k, self.z / k)

    def __neg__(self) -> "Vector3":
        return Vector3(-self.x, -self.y, -self.z)

    def __eq__(self, other) -> bool:
        try:
            o = Vector3.of(other)
        except (TypeError, ValueError):
            return NotImplemented
        return (self.x, self.y, self.z) == (o.x, o.y, o.z)

    def __repr__(self) -> str:
        return f"Vector3({self.x:.3f}, {self.y:.3f}, {self.z:.3f})"

    @property
    def length(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)

    def distance_to(self, other) -> float:
        return (self - Vector3.of(other)).length

    def normalized(self) -> "Vector3":
        l = self.length
        return Vector3() if l == 0 else self / l
