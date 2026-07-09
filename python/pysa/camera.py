"""Camera control and screen fades.

    from pysa import camera

    camera.fix_at((2488, -1666, 20), look_at=(2495, -1668, 13))
    camera.point_at(some_ped)
    camera.shake(200)
    camera.fade_out(500); ...; camera.fade_in(500)
    camera.restore()
"""
from __future__ import annotations

from .math3 import Vector3
from .native import cmd


def fix_at(pos, look_at=None) -> None:
    """Place the camera at a fixed world position (optionally aimed at a point)."""
    x, y, z = Vector3.of(pos)
    cmd.SET_FIXED_CAMERA_POSITION(x, y, z, 0.0, 0.0, 0.0)
    if look_at is not None:
        lx, ly, lz = Vector3.of(look_at)
        cmd.POINT_CAMERA_AT_POINT(lx, ly, lz, 2)


def point_at(entity, mode: int = 15) -> None:
    """Aim the camera at a ped or vehicle (mode 15 = fixed, 4 = follow)."""
    from .entities import Ped, Vehicle

    if isinstance(entity, Ped):
        cmd.POINT_CAMERA_AT_CHAR(entity, mode, 2)
    elif isinstance(entity, Vehicle):
        cmd.POINT_CAMERA_AT_CAR(entity, mode, 2)
    else:
        raise TypeError("point_at expects a Ped or Vehicle")


def restore(instantly: bool = True) -> None:
    """Return the camera to the player."""
    if instantly:
        cmd.RESTORE_CAMERA_JUMPCUT()
    else:
        cmd.RESTORE_CAMERA()


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
