"""Gamepad / controller input.

    from pysa import pad
    from pysa.pad import BUTTON

    @pysa.on_button(BUTTON.CROSS)          # like @on_key, for the controller
    def jump_pressed():
        ...

    if pad.pressed(BUTTON.R1):
        ...
    x, y = pad.left_stick()                # each axis -1.0 .. 1.0
    pad.rumble(400, 200)                    # vibrate 400ms

Button ids are the game's eButtonID. PlayStation names are the primary
constants; Xbox aliases (A/B/X/Y) are provided too.
"""
from __future__ import annotations

from .native import cmd


class BUTTON:
    """Controller button ids (eButtonID)."""
    LEFT_STICK_X = 0
    LEFT_STICK_Y = 1
    RIGHT_STICK_X = 2
    RIGHT_STICK_Y = 3
    L1 = 4
    L2 = 5
    R1 = 6
    R2 = 7
    DPAD_UP = 8
    DPAD_DOWN = 9
    DPAD_LEFT = 10
    DPAD_RIGHT = 11
    START = 12
    SELECT = 13
    SQUARE = 14
    TRIANGLE = 15
    CROSS = 16
    CIRCLE = 17
    L3 = 18
    R3 = 19

    # Xbox aliases
    A = 16   # cross
    B = 17   # circle
    X = 14   # square
    Y = 15   # triangle


#: Analog magnitude below which a stick axis reads as centered.
DEADZONE = 0.15


def pressed(button: int, pad: int = 0) -> bool:
    """True while `button` is held on controller `pad` (0 = first pad)."""
    return cmd.IS_BUTTON_PRESSED(pad, int(button))


def state(button: int, pad: int = 0) -> int:
    """Raw state of a button/axis (buttons ~0..255, sticks ~-128..128)."""
    return cmd.GET_PAD_STATE(pad, int(button))


def using_joypad() -> bool:
    """True if the player is currently using a controller (not keyboard)."""
    return cmd.IS_PC_USING_JOYPAD()


def rumble(ms: int = 300, intensity: int = 200, pad: int = 0) -> None:
    """Vibrate the controller."""
    cmd.SHAKE_PAD(pad, int(ms), int(intensity))


def _axis(button: int, pad: int) -> float:
    v = state(button, pad) / 128.0
    if -DEADZONE < v < DEADZONE:
        return 0.0
    return max(-1.0, min(1.0, v))


def left_stick(pad: int = 0) -> tuple:
    """Left stick as (x, y), each -1.0 .. 1.0 (deadzone applied)."""
    return (_axis(BUTTON.LEFT_STICK_X, pad), _axis(BUTTON.LEFT_STICK_Y, pad))


def right_stick(pad: int = 0) -> tuple:
    """Right stick as (x, y), each -1.0 .. 1.0 (deadzone applied)."""
    return (_axis(BUTTON.RIGHT_STICK_X, pad), _axis(BUTTON.RIGHT_STICK_Y, pad))
