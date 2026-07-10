"""Event decorators - the heart of a PyAndreas script.

    import pysa
    from pysa import KEY

    @pysa.on_tick                 # every frame
    def frame(): ...

    @pysa.on_tick(ms=1000)        # every second of game time
    def second(): ...

    @pysa.on_draw                 # 2D drawing stage (use pysa.hud.draw here)
    def overlay(): ...

    @pysa.on_key(KEY.F2)          # key edge (also: trigger='down'/'released')
    def pressed_f2(): ...

    @pysa.on_cheat("PYTHON")      # typed cheat word
    def typed_python(): ...

    @pysa.on_vehicle_created      # game spawned a vehicle (receives Vehicle)
    def new_car(vehicle: pysa.Vehicle) -> None: ...

    @pysa.on_game_start           # new game / save loaded / scripts reloaded
    def session(): ...

    @pysa.on_vehicle_model_changed
    def reskinned(vehicle: pysa.Vehicle,
                  model: pysa.VEHICLE | int) -> None: ...
"""
from __future__ import annotations

from . import _runtime


def _simple(event: str):
    def decorator(fn):
        return _runtime.register(event, fn)
    decorator.__name__ = f"on_{event}"
    return decorator


def on_tick(fn=None, *, ms: int = None):
    """Run every frame, or every `ms` milliseconds of game time."""
    if fn is not None:
        return _runtime.register("tick", fn)

    def decorator(f):
        if ms is None:
            return _runtime.register("tick", f)
        return _runtime.register("tick", f, ms=int(ms))
    return decorator


def on_key(vk: int, trigger: str = "pressed"):
    """Run on a key event. trigger: 'pressed' (edge), 'released', or 'down' (held)."""
    if trigger not in ("pressed", "released", "down"):
        raise ValueError("trigger must be 'pressed', 'released' or 'down'")

    def decorator(fn):
        return _runtime.register("key", fn, vk=int(vk), trigger=trigger)
    return decorator


def on_button(button: int, trigger: str = "pressed", pad: int = 0):
    """Run on a controller button event (see pysa.pad.BUTTON).

    trigger: 'pressed' (edge), 'released', or 'down' (held). pad = which
    controller (0 = first).
    """
    if trigger not in ("pressed", "released", "down"):
        raise ValueError("trigger must be 'pressed', 'released' or 'down'")

    def decorator(fn):
        return _runtime.register("button", fn, button=int(button),
                                 pad=int(pad), trigger=trigger)
    return decorator


def on_cheat(word: str):
    """Run when the player types `word` (like a cheat code)."""
    if not word or not word.isalnum():
        raise ValueError("cheat word must be alphanumeric")

    def decorator(fn):
        return _runtime.register("cheat", fn, word=word)
    return decorator


on_draw = _simple("draw")
on_game_start = _simple("game_start")
on_game_restart = _simple("game_restart")
on_game_reinit = _simple("game_reinit")
on_shutdown = _simple("shutdown")
on_render_init = _simple("render_init")
on_device_lost = _simple("device_lost")
on_device_reset = _simple("device_reset")
on_pools_init = _simple("pools_init")
on_pools_shutdown = _simple("pools_shutdown")
on_vehicle_created = _simple("vehicle_created")
on_vehicle_destroyed = _simple("vehicle_destroyed")
on_vehicle_model_changed = _simple("vehicle_model_changed")
on_ped_created = _simple("ped_created")
on_ped_destroyed = _simple("ped_destroyed")
on_ped_model_changed = _simple("ped_model_changed")
on_object_created = _simple("object_created")
on_object_destroyed = _simple("object_destroyed")
on_hud_draw = _simple("hud_draw")
on_radar_draw = _simple("radar_draw")
on_after_fade_draw = _simple("after_fade_draw")
on_menu_draw = _simple("menu_draw")
on_vehicle_render = _simple("vehicle_render")
on_ped_render = _simple("ped_render")
on_object_render = _simple("object_render")
