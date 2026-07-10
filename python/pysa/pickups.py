"""Pickups: weapons, money, health and item spawns.

    from pysa import pickups
    from pysa.models import WEAPON

    p = pickups.weapon((2495, -1668, 13.5), WEAPON.AK47, ammo=120)
    money = pickups.money(player.pos + (2, 0, 0), 5000)
    if p.collected:
        ...
"""
from __future__ import annotations

try:
    import _pysa
except ImportError:
    from . import _mock as _pysa

from .entities import load_model, release_model
from .enums import PICKUP_TYPE
from .math3 import Vector3
from .native import cmd

# Backward-compatible module name; values now match plugin-sdk's ePickupType.
TYPE = PICKUP_TYPE


class Pickup:
    __slots__ = ("_handle",)

    def __init__(self, handle):
        self._handle = int(getattr(handle, "_handle", handle))

    def __repr__(self) -> str:
        return f"Pickup(handle={self._handle})"

    def __eq__(self, other) -> bool:
        return isinstance(other, Pickup) and self._handle == other._handle

    def __hash__(self) -> int:
        return hash((Pickup, self._handle))

    @property
    def handle(self) -> int:
        return self._handle

    def _info(self):
        info = _pysa.pickup_info(self._handle)
        if info is None:
            raise ValueError(f"pickup {self._handle} no longer exists")
        return info

    @property
    def exists(self) -> bool:
        return _pysa.pickup_info(self._handle) is not None

    @property
    def model(self) -> int:
        return self._info()[0]

    @property
    def type(self):
        value = self._info()[1]
        try:
            return PICKUP_TYPE(value)
        except ValueError:
            return value

    @property
    def ammo(self) -> int:
        return self._info()[2]

    @property
    def money_per_day(self) -> int:
        return self._info()[3]

    @property
    def revenue(self) -> float:
        return self._info()[4]

    @property
    def pos(self) -> Vector3:
        return Vector3(*self._info()[5:8])

    @property
    def disabled(self) -> bool:
        return bool(self._info()[8] & 0x01)

    @property
    def visible(self) -> bool:
        return bool(self._info()[8] & 0x08)

    @property
    def collected(self) -> bool:
        return cmd.HAS_PICKUP_BEEN_COLLECTED(self)

    def remove(self) -> None:
        cmd.REMOVE_PICKUP(self)

    def add_blip(self):
        from . import blips
        return blips.add_for_pickup(self)


def create(model: int, pos,
           pickup_type: PICKUP_TYPE = PICKUP_TYPE.RESPAWNS) -> Pickup:
    """Generic pickup from any object/weapon model."""
    if not load_model(model):
        raise RuntimeError(f"pickup model {model} failed to load")
    x, y, z = Vector3.of(pos)
    p = Pickup(cmd.CREATE_PICKUP(model, pickup_type, x, y, z))
    release_model(model)
    return p


def weapon(pos, weapon_id: int, ammo: int = 100,
           pickup_type: PICKUP_TYPE = PICKUP_TYPE.ONCE) -> Pickup:
    model = cmd.GET_WEAPONTYPE_MODEL(weapon_id)
    if not load_model(model):
        raise RuntimeError(f"weapon model {model} failed to load")
    x, y, z = Vector3.of(pos)
    p = Pickup(cmd.CREATE_PICKUP_WITH_AMMO(model, pickup_type, ammo, x, y, z))
    release_model(model)
    return p


def money(pos, amount: int, permanent: bool = True) -> Pickup:
    """A cash pile at pos."""
    x, y, z = Vector3.of(pos)
    return Pickup(cmd.CREATE_MONEY_PICKUP(x, y, z, amount, permanent))


def all_pickups() -> list[Pickup]:
    """A snapshot of every active pickup in the game."""
    return [Pickup(handle) for handle in _pysa.pickup_handles()]
