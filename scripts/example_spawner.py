"""Vehicle spawner: type any vehicle name in-game (like a cheat code).

Type "RHINO", "INFERNUS", "HYDRA", ... and it appears in front of you.
Press F2 for a quick Infernus.
"""
import pysa
from pysa import KEY, VEHICLES, Vehicle, hud


def _spawn(name):
    try:
        veh = Vehicle.spawn(name)
        veh.colours = (1, 0)
        hud.help_text(f"{name.upper()} spawned")
    except Exception as e:
        hud.help_text(f"~r~Could not spawn {name}: {e}")


# One cheat word per vehicle name.
for _name in VEHICLES:
    pysa.on_cheat(_name)(lambda n=_name: _spawn(n))


@pysa.on_key(KEY.F2)
def quick_infernus():
    _spawn("infernus")
