"""Static payload and decorator types for high-level game events."""
from __future__ import annotations

from typing import Any, Callable, TypeVar, Union

from .entities import GameObject, Ped, Vehicle
from .enums import EXPLOSION_KIND
from .hooks import Hook
from .math3 import Vector3
from .models import WEAPON
from .pickups import Pickup


EventEntity = Union[Ped, Vehicle, GameObject, int, None]


class GameEvent:
    @property
    def raw(self) -> Hook: ...
    def cancel(self, value: int = 0) -> None: ...


class VehicleDamageEvent(GameEvent):
    @property
    def vehicle(self) -> Vehicle: ...
    attacker: EventEntity
    weapon: WEAPON | int
    amount: float


class VehicleExplodeEvent(GameEvent):
    @property
    def vehicle(self) -> Vehicle: ...
    attacker: EventEntity


class TyreBurstEvent(GameEvent):
    @property
    def vehicle(self) -> Vehicle: ...
    tyre: int


class WeaponFireEvent(GameEvent):
    shooter: EventEntity
    target: EventEntity


class ExplosionEvent(GameEvent):
    victim: EventEntity
    creator: EventEntity
    kind: EXPLOSION_KIND | int
    @property
    def position(self) -> Vector3: ...


class WantedLevelChangeEvent(GameEvent):
    @property
    def player(self) -> Ped: ...
    level: int


class WeaponGivenEvent(GameEvent):
    @property
    def ped(self) -> Ped: ...
    weapon: WEAPON | int
    ammo: int


class ProjectileFiredEvent(GameEvent):
    shooter: EventEntity
    weapon: WEAPON | int
    @property
    def position(self) -> Vector3: ...
    target: EventEntity


class PickupCollectedEvent(GameEvent):
    @property
    def pickup(self) -> Pickup: ...


_VehicleDamageHandler = TypeVar(
    "_VehicleDamageHandler", bound=Callable[[VehicleDamageEvent], Any]
)
_VehicleExplodeHandler = TypeVar(
    "_VehicleExplodeHandler", bound=Callable[[VehicleExplodeEvent], Any]
)
_TyreBurstHandler = TypeVar(
    "_TyreBurstHandler", bound=Callable[[TyreBurstEvent], Any]
)
_WeaponFireHandler = TypeVar(
    "_WeaponFireHandler", bound=Callable[[WeaponFireEvent], Any]
)
_ExplosionHandler = TypeVar(
    "_ExplosionHandler", bound=Callable[[ExplosionEvent], Any]
)
_WantedHandler = TypeVar(
    "_WantedHandler", bound=Callable[[WantedLevelChangeEvent], Any]
)
_WeaponGivenHandler = TypeVar(
    "_WeaponGivenHandler", bound=Callable[[WeaponGivenEvent], Any]
)
_ProjectileHandler = TypeVar(
    "_ProjectileHandler", bound=Callable[[ProjectileFiredEvent], Any]
)
_PickupHandler = TypeVar(
    "_PickupHandler", bound=Callable[[PickupCollectedEvent], Any]
)


def on_vehicle_damage(fn: _VehicleDamageHandler, /) -> _VehicleDamageHandler: ...
def on_vehicle_explode(fn: _VehicleExplodeHandler, /) -> _VehicleExplodeHandler: ...
def on_tyre_burst(fn: _TyreBurstHandler, /) -> _TyreBurstHandler: ...
def on_weapon_fire(fn: _WeaponFireHandler, /) -> _WeaponFireHandler: ...
def on_explosion(fn: _ExplosionHandler, /) -> _ExplosionHandler: ...
def on_wanted_level_change(fn: _WantedHandler, /) -> _WantedHandler: ...
def on_weapon_given(fn: _WeaponGivenHandler, /) -> _WeaponGivenHandler: ...
def on_projectile_fired(fn: _ProjectileHandler, /) -> _ProjectileHandler: ...
def on_pickup_collected(fn: _PickupHandler, /) -> _PickupHandler: ...

def entity_from_ptr(ptr: int) -> EventEntity: ...
def events() -> list[str]: ...
