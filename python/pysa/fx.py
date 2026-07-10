"""Particle effects: fire, smoke, explosions, water splashes, and coronas.

    from pysa import fx, player

    smoke = fx.FxSystem("cigarette", player.pos)
    smoke.play()
    ...
    smoke.remove()

    # attach an effect to an entity so it follows them:
    flames = fx.FxSystem.on(player.ped, "flamethrower", offset=(0, 0, 1))
    flames.play()

    # a light corona each frame (call from on_draw):
    @pysa.on_draw
    def glow():
        fx.corona(player.pos + (0, 0, 3), size=2.0, color=(255, 120, 0))

Effect names are the game's particle names (e.g. "explosion_large", "fire",
"smoke30", "water_splash"). See any SA effects.fxp name list.
"""
from __future__ import annotations

from enum import IntEnum

from .math3 import Vector3
from .native import cmd


class FX:
    """A few common particle effect names."""
    FIRE = "fire"
    SMOKE = "smoke30"
    EXPLOSION_LARGE = "explosion_large"
    EXPLOSION_SMALL = "explosion_small"
    WATER_SPLASH = "water_splash"
    BLOOD = "blood_heli"
    SPARKS = "spark"
    CIGARETTE = "cigarette"


class CORONA(IntEnum):
    NORMAL = 0
    STAR = 1
    MOON = 2
    REFLECTION = 3
    HEADLIGHT = 4
    NONE = 5
    RING = 9


class FLARE(IntEnum):
    NONE = 0
    SUN = 1
    HEADLIGHTS = 2


class FxSystem:
    """A particle system instance. Create it, `play()`, then `remove()`."""

    __slots__ = ("_handle",)

    def __init__(self, name: str, pos, ignore_bounds: bool = False, handle: int = None):
        if handle is not None:
            self._handle = handle
        else:
            x, y, z = Vector3.of(pos)
            self._handle = cmd.CREATE_FX_SYSTEM(str(name), x, y, z, int(ignore_bounds))

    @classmethod
    def on(cls, entity, name: str, offset=(0, 0, 0), ignore_bounds: bool = False):
        """Create an effect attached to a ped, vehicle or object."""
        from .entities import GameObject, Ped, Vehicle
        ox, oy, oz = Vector3.of(offset)
        if isinstance(entity, Ped):
            h = cmd.CREATE_FX_SYSTEM_ON_CHAR(str(name), entity, ox, oy, oz, int(ignore_bounds))
        elif isinstance(entity, Vehicle):
            h = cmd.CREATE_FX_SYSTEM_ON_CAR(str(name), entity, ox, oy, oz, int(ignore_bounds))
        elif isinstance(entity, GameObject):
            h = cmd.CREATE_FX_SYSTEM_ON_OBJECT(str(name), entity, ox, oy, oz, int(ignore_bounds))
        else:
            raise TypeError("FxSystem.on expects a Ped, Vehicle or GameObject")
        return cls(name, None, handle=h)

    @property
    def handle(self) -> int:
        return self._handle

    def play(self) -> None:
        cmd.PLAY_FX_SYSTEM(self._handle)

    def stop(self) -> None:
        cmd.STOP_FX_SYSTEM(self._handle)

    def remove(self, immediate: bool = False) -> None:
        if immediate:
            cmd.KILL_FX_SYSTEM_NOW(self._handle)
        else:
            cmd.KILL_FX_SYSTEM(self._handle)

    def __repr__(self) -> str:
        return f"FxSystem(handle={self._handle})"


def corona(pos, size: float = 1.0, color=(255, 255, 255),
           corona_type: int = CORONA.NORMAL, flare: int = FLARE.NONE) -> None:
    """Draw a glowing corona for one frame (call from an on_draw handler)."""
    x, y, z = Vector3.of(pos)
    r, g, b = color[0], color[1], color[2]
    cmd.DRAW_CORONA(x, y, z, float(size), int(corona_type), int(flare),
                    int(r), int(g), int(b))


def weaponshop_corona(pos, size: float = 1.0, color=(255, 255, 255),
                      corona_type: int = CORONA.NORMAL,
                      flare: int = FLARE.NONE) -> None:
    """Draw the short-range corona variant used by weapon shops."""
    x, y, z = Vector3.of(pos)
    r, g, b = color[0], color[1], color[2]
    cmd.DRAW_WEAPONSHOP_CORONA(x, y, z, float(size), int(corona_type),
                               int(flare), int(r), int(g), int(b))


def light(pos, radius: float = 10.0, color=(255, 255, 255)) -> None:
    """Draw a colored dynamic light for the current frame."""
    x, y, z = Vector3.of(pos)
    r, g, b = color[0], color[1], color[2]
    cmd.DRAW_LIGHT_WITH_RANGE(x, y, z, int(r), int(g), int(b), float(radius))


def smoke_particle(pos, velocity=(0, 0, 0), color=(1.0, 1.0, 1.0),
                   alpha: float = 1.0, size: float = 0.5,
                   fade: float = 0.025) -> None:
    """Create one legacy smoke particle with velocity and opacity."""
    x, y, z = Vector3.of(pos)
    vx, vy, vz = Vector3.of(velocity)
    r, g, b = color[0], color[1], color[2]
    cmd.ADD_SMOKE_PARTICLE(x, y, z, vx, vy, vz, float(r), float(g),
                           float(b), float(alpha), float(size), float(fade))
