"""Friendly read-only views over plugin-sdk model information records."""
from __future__ import annotations

from typing import Optional, Tuple, Union, overload

try:
    import _pysa
except ImportError:
    from . import _mock as _pysa

from . import memory
from .enums import VEHICLE_CLASS, VEHICLE_TYPE
from .gamestruct import Struct
from .math3 import Vector3
from .models import VEHICLE, vehicle_id
from .ped_models import PED


def _enum_or_int(enum_type, value: int):
    try:
        return enum_type(value)
    except ValueError:
        return value


class ModelInfo:
    """Base model metadata shared by peds, vehicles, and world objects."""

    __slots__ = ("model", "address", "_base")

    def __init__(self, model: int):
        self.model = int(model)
        self.address = int(_pysa.model_info_ptr(self.model))
        if not self.address:
            raise ValueError(f"model {self.model} has no loaded model information")
        self._base = Struct(self.address, "CBaseModelInfo")

    @property
    def key(self) -> int:
        return self._base.m_nKey

    @property
    def reference_count(self) -> int:
        return self._base.m_nRefCount

    @property
    def texture_dictionary(self) -> int:
        return self._base.m_nTxdIndex

    @property
    def alpha(self) -> int:
        return self._base.m_nAlpha

    @property
    def draw_distance(self) -> float:
        return self._base.m_fDrawDistance

    @property
    def collision_bounds(self) -> Optional[Tuple[Vector3, Vector3]]:
        collision = memory.read_u32(self.address + 0x14)
        if not collision:
            return None
        minimum = Vector3(memory.read_float(collision),
                          memory.read_float(collision + 4),
                          memory.read_float(collision + 8))
        maximum = Vector3(memory.read_float(collision + 12),
                          memory.read_float(collision + 16),
                          memory.read_float(collision + 20))
        return minimum, maximum

    @property
    def dimensions(self) -> Optional[Vector3]:
        bounds = self.collision_bounds
        return None if bounds is None else bounds[1] - bounds[0]

    def __repr__(self) -> str:
        return f"{type(self).__name__}(model={self.model}, address=0x{self.address:08X})"


class VehicleModelInfo(ModelInfo):
    """Vehicle model metadata from plugin-sdk's CVehicleModelInfo."""

    __slots__ = ("_vehicle",)

    def __init__(self, model: Union[VEHICLE, int, str]):
        super().__init__(vehicle_id(model))
        self._vehicle = Struct(self.address, "CVehicleModelInfo")

    @property
    def game_name(self) -> str:
        raw = memory.read(self.address + 0x32, 8)
        return raw.split(b"\0", 1)[0].decode("ascii", "replace")

    @property
    def vehicle_type(self) -> Union[VEHICLE_TYPE, int]:
        return _enum_or_int(VEHICLE_TYPE, memory.read_int(self.address + 0x3C))

    @property
    def vehicle_class(self) -> Union[VEHICLE_CLASS, int]:
        return _enum_or_int(VEHICLE_CLASS, self._vehicle.m_nVehicleClass)

    @property
    def front_wheel_size(self) -> float:
        return self._vehicle.m_fWheelSizeFront

    @property
    def rear_wheel_size(self) -> float:
        return self._vehicle.m_fWheelSizeRear

    @property
    def wheel_model(self) -> int:
        return self._vehicle.m_nWheelModelIndex

    @property
    def handling_id(self) -> int:
        return self._vehicle.m_nHandlingId

    @property
    def door_count(self) -> int:
        return self._vehicle.m_nNumDoors


class PedModelInfo(ModelInfo):
    """Ped model metadata from plugin-sdk's CPedModelInfo."""

    __slots__ = ("_ped",)

    def __init__(self, model: Union[PED, int]):
        super().__init__(int(model))
        self._ped = Struct(self.address, "CPedModelInfo")

    @property
    def ped_type(self) -> int:
        return self._ped.m_nPedType

    @property
    def stat_type(self) -> int:
        return self._ped.m_nStatType

    @property
    def animation_type(self) -> int:
        return self._ped.m_nAnimType

    @property
    def race(self) -> int:
        return self._ped.m_nRace


@overload
def model_info(model: VEHICLE) -> VehicleModelInfo: ...


@overload
def model_info(model: PED) -> PedModelInfo: ...


@overload
def model_info(model: str) -> VehicleModelInfo: ...


@overload
def model_info(model: int) -> ModelInfo: ...


def model_info(model: Union[VEHICLE, PED, int, str]) -> ModelInfo:
    """Return the specialized model-information view for a model id/enum."""
    if isinstance(model, str):
        return VehicleModelInfo(model)
    model_id = int(model)
    if isinstance(model, VEHICLE) or 400 <= model_id <= 611:
        return VehicleModelInfo(model)
    try:
        PED(model_id)
    except ValueError:
        pass
    else:
        return PedModelInfo(model)
    return ModelInfo(model_id)
