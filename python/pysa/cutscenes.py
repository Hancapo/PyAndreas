"""Friendly control of GTA's named cutscene system."""
from __future__ import annotations

from .math3 import Vector3
from .native import cmd
from .type_aliases import Position


class Cutscene:
    __slots__ = ("name",)

    def __init__(self, name: str):
        self.name = str(name)

    def __repr__(self) -> str:
        return f"Cutscene({self.name!r})"

    def load(self, offset: Position | None = None) -> "Cutscene":
        cmd.LOAD_CUTSCENE(self.name)
        if offset is not None:
            self.offset = offset
        return self

    @property
    def loaded(self) -> bool:
        return bool(cmd.HAS_CUTSCENE_LOADED())

    @property
    def finished(self) -> bool:
        return bool(cmd.HAS_CUTSCENE_FINISHED())

    @property
    def skipped(self) -> bool:
        return bool(cmd.WAS_CUTSCENE_SKIPPED())

    @property
    def time(self) -> int:
        return int(cmd.GET_CUTSCENE_TIME())

    @property
    def offset(self) -> Vector3:
        return Vector3(*cmd.GET_CUTSCENE_OFFSET())

    @offset.setter
    def offset(self, value: Position) -> None:
        x, y, z = Vector3.of(value)
        cmd.SET_CUTSCENE_OFFSET(x, y, z)

    def start(self) -> None:
        cmd.START_CUTSCENE()

    def clear(self) -> None:
        cmd.CLEAR_CUTSCENE()

    def skip_to_end(self) -> None:
        cmd.SKIP_CUTSCENE_END()


def skip_requested() -> bool:
    return bool(cmd.IS_SKIP_CUTSCENE_BUTTON_PRESSED())
