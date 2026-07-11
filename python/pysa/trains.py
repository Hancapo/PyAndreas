"""Mission train spawning and control."""
from __future__ import annotations

from typing import Optional

from .entities import Vehicle
from .math3 import Vector3
from .native import cmd
from .type_aliases import Position


class Train(Vehicle):
    __slots__ = ()

    @property
    def clockwise(self) -> bool:
        return bool(cmd.FIND_TRAIN_DIRECTION(self))

    @property
    def derailed(self) -> bool:
        return bool(cmd.HAS_TRAIN_DERAILED(self))

    @property
    def caboose(self) -> Optional[Vehicle]:
        return cmd.GET_TRAIN_CABOOSE(self)

    def carriage(self, index: int) -> Optional[Vehicle]:
        return cmd.GET_TRAIN_CARRIAGE(self, index)

    def set_speed(self, speed: float, *, cruise: bool = True) -> None:
        if cruise:
            cmd.SET_TRAIN_CRUISE_SPEED(self, speed)
        cmd.SET_TRAIN_SPEED(self, speed)

    def stop_at_stations(self, enabled: bool = True) -> None:
        cmd.SET_TRAIN_FORCED_TO_SLOW_DOWN(self, enabled)

    def move_to(self, pos: Position) -> None:
        x, y, z = Vector3.of(pos)
        cmd.SET_MISSION_TRAIN_COORDINATES(self, x, y, z)

    def release(self) -> None:
        cmd.MARK_MISSION_TRAIN_AS_NO_LONGER_NEEDED(self)

    def delete(self) -> None:
        cmd.DELETE_MISSION_TRAIN(self)


def spawn(train_type: int, pos: Position, clockwise: bool = True) -> Train:
    x, y, z = Vector3.of(pos)
    return Train(int(cmd.CREATE_MISSION_TRAIN(train_type, x, y, z, clockwise)))


def delete_all() -> None:
    cmd.DELETE_MISSION_TRAINS()


def release_all() -> None:
    cmd.MARK_MISSION_TRAINS_AS_NO_LONGER_NEEDED()
