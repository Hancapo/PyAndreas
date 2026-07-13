"""Reusable public annotations for common PyAndreas scripting values.

These aliases are primarily for script authors who want to annotate their own
helpers without spelling out every accepted enum/value form.
"""
from __future__ import annotations

from typing import Sequence, Union

from .enums import AREA
from .math3 import Vector3
from .models import VEHICLE, WEAPON
from .ped_models import PED


# ``Sequence`` keeps tuples and lists convenient for ordinary scripts while
# Vector3 preserves completion for the API's native vector object.
Position = Union[Vector3, Sequence[float]]
AreaId = Union[AREA, int]
VehicleModel = Union[VEHICLE, int, str]
PedModel = Union[PED, int]
WeaponId = Union[WEAPON, int]
