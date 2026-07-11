"""Whole-game state and interface controls."""
from __future__ import annotations

from enum import IntEnum
from typing import Union

from .native import cmd


class LANGUAGE(IntEnum):
    ENGLISH = 0
    FRENCH = 1
    GERMAN = 2
    ITALIAN = 3
    SPANISH = 4


def language() -> Union[LANGUAGE, int]:
    value = int(cmd.GET_CURRENT_LANGUAGE())
    try:
        return LANGUAGE(value)
    except ValueError:
        return value


def language_changed() -> bool:
    return bool(cmd.HAS_LANGUAGE_CHANGED())


def show_hud(visible: bool = True) -> None:
    cmd.DISPLAY_HUD(visible)


def show_radar(visible: bool = True) -> None:
    cmd.DISPLAY_RADAR(visible)


def set_radar_zoom(zoom: int) -> None:
    """Set radar zoom, clamped to the useful 0..170 range."""
    cmd.SET_RADAR_ZOOM(max(0, min(170, int(zoom))))


def open_save_menu() -> None:
    cmd.ACTIVATE_SAVE_MENU()


def save_finished() -> bool:
    return bool(cmd.HAS_SAVE_GAME_FINISHED())
