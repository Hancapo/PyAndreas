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

from enum import IntEnum
import math

try:
    import _pysa
except ImportError:
    from . import _mock as _pysa

from .native import cmd


class BUTTON(IntEnum):
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


def pressed(button: BUTTON, pad: int = 0) -> bool:
    """True while `button` is held on controller `pad` (0 = first pad)."""
    return cmd.IS_BUTTON_PRESSED(pad, int(button))


def state(button: BUTTON, pad: int = 0) -> int:
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


class Stick:
    """An intuitive 2D stick vector where positive Y means up/forward."""

    __slots__ = ("x", "y")

    def __init__(self, x: float = 0.0, y: float = 0.0):
        self.x = float(x)
        self.y = float(y)

    def __iter__(self):
        yield self.x
        yield self.y

    @property
    def magnitude(self) -> float:
        return min(1.0, math.sqrt(self.x * self.x + self.y * self.y))

    @property
    def active(self) -> bool:
        return self.x != 0.0 or self.y != 0.0

    @property
    def angle(self) -> float:
        """Direction in degrees: 0 is right, 90 is up."""
        return math.degrees(math.atan2(self.y, self.x))

    def __repr__(self) -> str:
        return f"Stick(x={self.x:.3f}, y={self.y:.3f})"


def left_stick_direction(pad: int = 0) -> Stick:
    """Left stick with conventional coordinates (positive Y is up/forward)."""
    x, gta_y = left_stick(pad)
    return Stick(x, -gta_y)


def right_stick_direction(pad: int = 0) -> Stick:
    """Right stick with conventional coordinates (positive Y is up/forward)."""
    x, gta_y = right_stick(pad)
    return Stick(x, -gta_y)


class ButtonAction:
    """A named controller action backed by one button or a held combo."""

    __slots__ = ("buttons", "pad", "_down", "_previous", "_sample_time")

    def __init__(self, *buttons: BUTTON, pad: int = 0):
        if not buttons:
            raise ValueError("an action needs at least one button")
        self.buttons = tuple(BUTTON(button) for button in buttons)
        self.pad = int(pad)
        self._down = False
        self._previous = False
        self._sample_time = None

    def _sample(self) -> None:
        now = _pysa.game_time()
        if now == self._sample_time:
            return
        self._sample_time = now
        self._previous = self._down
        self._down = all(pressed(button, self.pad) for button in self.buttons)

    @property
    def down(self) -> bool:
        self._sample()
        return self._down

    @property
    def pressed(self) -> bool:
        self._sample()
        return self._down and not self._previous

    @property
    def released(self) -> bool:
        self._sample()
        return self._previous and not self._down

    def __bool__(self) -> bool:
        return self.down


def action(button: BUTTON, *, pad: int = 0) -> ButtonAction:
    """Create a stateful action for one controller button."""
    return ButtonAction(button, pad=pad)


def combo(*buttons: BUTTON, pad: int = 0) -> ButtonAction:
    """Create a stateful action that is down while every button is held."""
    return ButtonAction(*buttons, pad=pad)
