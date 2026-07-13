"""Interior placement data used by the friendly player location API."""
from __future__ import annotations

from dataclasses import dataclass

from .enums import AREA
from .math3 import Vector3
from .type_aliases import AreaId, Position


@dataclass(frozen=True, init=False)
class Placement:
    """A position together with the GTA area and facing direction it needs."""

    pos: Vector3
    heading: float
    area: AREA

    def __init__(self, pos: Position, heading: float = 0.0,
                 area: AreaId = AREA.OUTSIDE):
        object.__setattr__(self, "pos", Vector3.of(pos))
        object.__setattr__(self, "heading", float(heading))
        object.__setattr__(self, "area", AREA(int(area)))


@dataclass(frozen=True)
class EntryExit:
    """The EnEx entrance used to reach the player's current interior."""

    name: str
    exterior: Placement
