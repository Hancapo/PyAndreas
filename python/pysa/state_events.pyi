from __future__ import annotations

from typing import Union

from .entities import Ped, Vehicle
from .math3 import Vector3
from .models import WEAPON


class PedDamageEvent:
    ped: Ped
    amount: int
    previous_health: int
    health: int


class PedDeathEvent:
    ped: Ped


class VehicleEnterEvent:
    ped: Ped
    vehicle: Vehicle
    seat: int
    @property
    def driver(self) -> bool: ...


class VehicleExitEvent(VehicleEnterEvent): ...


class WeaponChangedEvent:
    ped: Ped
    previous: Union[WEAPON, int]
    weapon: Union[WEAPON, int]


class ZoneEvent:
    name: str
    position: Vector3
