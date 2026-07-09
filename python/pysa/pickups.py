"""Pickups: weapons, money, health and item spawns.

    from pysa import pickups
    from pysa.models import WEAPON

    p = pickups.weapon((2495, -1668, 13.5), WEAPON.AK47, ammo=120)
    money = pickups.money(player.pos + (2, 0, 0), 5000)
    if p.collected:
        ...
"""
from __future__ import annotations

from .entities import load_model, release_model
from .math3 import Vector3
from .native import cmd


class TYPE:
    ONCE = 2            # disappears on pickup
    RESPAWNS = 3        # in-place respawning (weapons style)
    ONCE_TIMEOUT = 1


class Pickup:
    __slots__ = ("_handle",)

    def __init__(self, handle):
        self._handle = int(getattr(handle, "_handle", handle))

    def __repr__(self) -> str:
        return f"Pickup(handle={self._handle})"

    @property
    def handle(self) -> int:
        return self._handle

    @property
    def collected(self) -> bool:
        return cmd.HAS_PICKUP_BEEN_COLLECTED(self)

    def remove(self) -> None:
        cmd.REMOVE_PICKUP(self)


def create(model: int, pos, pickup_type: int = TYPE.RESPAWNS) -> Pickup:
    """Generic pickup from any object/weapon model."""
    if not load_model(model):
        raise RuntimeError(f"pickup model {model} failed to load")
    x, y, z = Vector3.of(pos)
    p = Pickup(cmd.CREATE_PICKUP(model, pickup_type, x, y, z))
    release_model(model)
    return p


def weapon(pos, weapon_id: int, ammo: int = 100,
           pickup_type: int = TYPE.ONCE) -> Pickup:
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
