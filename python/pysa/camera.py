"""Camera control and screen fades.

    from pysa import camera

    camera.fix_at((2488, -1666, 20), look_at=(2495, -1668, 13))
    camera.point_at(some_ped)
    camera.shake(200)
    camera.fade_out(500); ...; camera.fade_in(500)
    camera.restore()
"""
from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING, Optional, Union

from .enums import CAMERA_MODE
from .math3 import Vector3
from .native import cmd
from .type_aliases import Position

if TYPE_CHECKING:
    from .entities import Ped, Vehicle

CameraEntity = Union["Ped", "Vehicle"]


class SWITCH(IntEnum):
    NONE = 0
    SMOOTH = 1
    JUMP_CUT = 2


def fix_at(pos, look_at=None) -> None:
    """Place the camera at a fixed world position (optionally aimed at a point)."""
    x, y, z = Vector3.of(pos)
    cmd.SET_FIXED_CAMERA_POSITION(x, y, z, 0.0, 0.0, 0.0)
    if look_at is not None:
        lx, ly, lz = Vector3.of(look_at)
        cmd.POINT_CAMERA_AT_POINT(lx, ly, lz, 2)


def point_at(entity, mode: CAMERA_MODE = CAMERA_MODE.FIXED) -> None:
    """Aim the camera at a ped or vehicle using a CAMERA_MODE."""
    from .entities import Ped, Vehicle

    if isinstance(entity, Ped):
        cmd.POINT_CAMERA_AT_CHAR(entity, mode, 2)
    elif isinstance(entity, Vehicle):
        cmd.POINT_CAMERA_AT_CAR(entity, mode, 2)
    else:
        raise TypeError("point_at expects a Ped or Vehicle")


def attach_to(entity: CameraEntity, offset: Position = (0, 0, 0),
              rotation: Position = (0, 0, 0), *,
              look_at: Optional[CameraEntity] = None, tilt: float = 0.0,
              switch: SWITCH = SWITCH.JUMP_CUT) -> None:
    """Attach the camera to a ped/vehicle, optionally looking at another one."""
    from .entities import Ped, Vehicle
    ox, oy, oz = Vector3.of(offset)
    if look_at is None:
        rx, ry, rz = Vector3.of(rotation)
        if isinstance(entity, Ped):
            cmd.ATTACH_CAMERA_TO_CHAR(entity, ox, oy, oz, rx, ry, rz, tilt, switch)
        elif isinstance(entity, Vehicle):
            cmd.ATTACH_CAMERA_TO_VEHICLE(entity, ox, oy, oz, rx, ry, rz, tilt, switch)
        else:
            raise TypeError("attach_to expects a Ped or Vehicle")
        return
    if isinstance(entity, Ped) and isinstance(look_at, Ped):
        cmd.ATTACH_CAMERA_TO_CHAR_LOOK_AT_CHAR(entity, ox, oy, oz, look_at, tilt, switch)
    elif isinstance(entity, Ped) and isinstance(look_at, Vehicle):
        cmd.ATTACH_CAMERA_TO_CHAR_LOOK_AT_VEHICLE(entity, ox, oy, oz, look_at, tilt, switch)
    elif isinstance(entity, Vehicle) and isinstance(look_at, Ped):
        cmd.ATTACH_CAMERA_TO_VEHICLE_LOOK_AT_CHAR(entity, ox, oy, oz, look_at, tilt, switch)
    elif isinstance(entity, Vehicle) and isinstance(look_at, Vehicle):
        cmd.ATTACH_CAMERA_TO_VEHICLE_LOOK_AT_VEHICLE(entity, ox, oy, oz, look_at, tilt, switch)
    else:
        raise TypeError("entity and look_at must be Ped or Vehicle instances")


def restore(instantly: bool = True) -> None:
    """Return the camera to the player."""
    if instantly:
        cmd.RESTORE_CAMERA_JUMPCUT()
    else:
        cmd.RESTORE_CAMERA()


def behind_player() -> None:
    """Put the gameplay camera directly behind the player."""
    cmd.SET_CAMERA_BEHIND_PLAYER()


def position() -> Vector3:
    """Current active camera position."""
    return Vector3(*cmd.GET_ACTIVE_CAMERA_COORDINATES())


def target() -> Vector3:
    """World position at which the active camera is pointing."""
    return Vector3(*cmd.GET_ACTIVE_CAMERA_POINT_AT())


def move(start: Position, end: Position, ms: int, ease: bool = True) -> None:
    sx, sy, sz = Vector3.of(start)
    ex, ey, ez = Vector3.of(end)
    cmd.CAMERA_SET_VECTOR_MOVE(sx, sy, sz, ex, ey, ez, ms, ease)


def track(start: Position, end: Position, ms: int, ease: bool = True) -> None:
    sx, sy, sz = Vector3.of(start)
    ex, ey, ez = Vector3.of(end)
    cmd.CAMERA_SET_VECTOR_TRACK(sx, sy, sz, ex, ey, ez, ms, ease)


def is_moving() -> bool:
    return bool(cmd.CAMERA_IS_VECTOR_MOVE_RUNNING())


def is_tracking() -> bool:
    return bool(cmd.CAMERA_IS_VECTOR_TRACK_RUNNING())


def fov() -> float:
    return float(cmd.GET_CAMERA_FOV())


def interpolate_fov(start: float, end: float, ms: int, ease: bool = True) -> None:
    cmd.CAMERA_SET_LERP_FOV(start, end, ms, ease)


def persist(*, position: bool = False, target: bool = False,
            fov: bool = False) -> None:
    cmd.CAMERA_PERSIST_POS(position)
    cmd.CAMERA_PERSIST_TRACK(target)
    cmd.CAMERA_PERSIST_FOV(fov)


def reset_animations() -> None:
    cmd.CAMERA_RESET_NEW_SCRIPTABLES()


def allow_collision(enabled: bool = True) -> None:
    cmd.ALLOW_FIXED_CAMERA_COLLISION(enabled)


def cinema(enabled: bool = True) -> None:
    cmd.SET_CINEMA_CAMERA(enabled)


def in_front_of(entity: Optional["Ped"] = None) -> None:
    if entity is None:
        cmd.SET_CAMERA_IN_FRONT_OF_PLAYER()
    else:
        from .entities import Ped
        if not isinstance(entity, Ped):
            raise TypeError("in_front_of expects a Ped or no argument")
        cmd.SET_CAMERA_IN_FRONT_OF_CHAR(entity)


def shake(intensity: int = 100) -> None:
    cmd.SHAKE_CAM(intensity)


def fade_out(ms: int = 500) -> None:
    cmd.DO_FADE(float(ms), 0)


def fade_in(ms: int = 500) -> None:
    cmd.DO_FADE(float(ms), 1)


def is_fading() -> bool:
    return cmd.GET_FADING_STATUS()


def widescreen(enabled: bool = True) -> None:
    """Cinematic letterbox bars."""
    cmd.SWITCH_WIDESCREEN(enabled)
