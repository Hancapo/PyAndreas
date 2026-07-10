"""Vehicle spawner: type any vehicle name in-game (like a cheat code).

Type "RHINO", "INFERNUS", "HYDRA", ... and it appears in front of you.
Press F2 for a quick Infernus.
"""
import pysa
from pysa import KEY, VEHICLE, Vehicle, hud


def _spawn(model: VEHICLE):
    try:
        veh = Vehicle.spawn(model)
        veh.colours = (1, 0)
        hud.help_text(f"{model.name} spawned")
    except Exception as e:
        hud.help_text(f"~r~Could not spawn {model.name}: {e}")


# One cheat word per vehicle name.
for _model in VEHICLE:
    pysa.on_cheat(_model.name)(lambda model=_model: _spawn(model))


@pysa.on_key(KEY.F2)
def quick_infernus():
    _spawn(VEHICLE.INFERNUS)
