"""PyAndreas - Python scripting for GTA San Andreas.

Drop .py files into <game>\\PyAndreas\\scripts and they run inside the game.
Quick tour:

    import pysa
    from pysa import player, world, hud, cmd, KEY, Vehicle

    @pysa.on_key(KEY.F2)
    def tank():
        Vehicle.spawn('rhino')

    @pysa.on_cheat("MOON")
    def moon():
        world.set_gravity(0.002)

    @pysa.script                      # coroutine: yield ms, or bare yield = 1 frame
    def welcome():
        yield 2000
        hud.big_text("PyAndreas ready")

Every one of ~1600 script commands is a normal Python function - outputs
are return values, conditions are bools, entities come back wrapped:

    x, y, z = cmd.GET_CAR_COORDINATES(car)
    driver = cmd.GET_DRIVER_OF_CAR(car)          # Ped or None
    if cmd.IS_CHAR_IN_ANY_CAR(player.ped): ...

    pysa.find_commands('blip')                    # discover commands
    help(cmd.CREATE_CAR)                          # signature + description

Press F11 in-game to hot-reload all scripts. Errors go to PyAndreas.log.
"""

from ._runtime import VERSION as __version__
from ._runtime import Task, reload_scripts, script, start
from .events import (on_button, on_cheat, on_draw, on_game_start, on_key,
                     on_object_created, on_object_destroyed, on_ped_created,
                     on_ped_destroyed, on_shutdown, on_tick,
                     on_vehicle_created, on_vehicle_destroyed)
from .entities import (Entity, GameObject, ObjectAnimation, Ped, PedTasks,
                       PedWeapons, Vehicle, VehicleAI, VehicleDamage,
                       VehicleDoor, VehicleDoors, VehicleMods, VehicleTyre,
                       VehicleTyres, all_objects, all_peds, all_vehicles,
                       load_model, release_model)
from .keys import KEY
from .math3 import Vector3
from .models import PED_TYPE, VEHICLES, WEAPON, vehicle_id
from .native import (NOT, End, Out, call, call_ex, call_func, cmd, doc,
                     find_commands, signature)
from .opcodes import OPCODES
from .player import (PLAYER_STATE, PlayerCamera, PlayerClothes, PlayerControls,
                     PlayerCoop, PlayerGroup, PlayerMissions, PlayerPerks,
                     PlayerRecords, PlayerStats, PlayerTargeting,
                     PlayerVehicles, PlayerVitals, PlayerWanted,
                     PlayerWeapons, player)
from .gamestruct import Struct, struct_of
from .hooks import Call, Hook, find_functions, function_doc, hook, on_call
from .game_events import (GameEvent, on_explosion, on_projectile_fired,
                          on_tyre_burst, on_vehicle_damage, on_vehicle_explode,
                          on_wanted_level_change, on_weapon_fire, on_weapon_given)
from .offsets import OFFSETS
from .markers import CHECKPOINT, Checkpoint, Marker3D, Sphere
from .timers import Countdown, Stopwatch
from .world import Fire
# Live, iterable views over the entity pools (also at pysa.world.*).
from .world import objects, peds, vehicles
from .audio import MissionAudio, RADIO
from .fx import FxSystem
from .pad import BUTTON
from . import (audio, blips, camera, draw, fx, game_events, hooks, hud, markers,
               memory, pad, pickups, text, timers, world)

try:
    import _pysa as _bridge
except ImportError:
    from . import _mock as _bridge

#: Write a line to PyAndreas.log.
log = _bridge.log

#: Game time in milliseconds (pauses while the game is paused).
game_time = _bridge.game_time

#: Poll a key directly: key_down(KEY.SPACE) -> bool.
key_down = _bridge.key_down

#: The <game>\PyAndreas folder (put assets like textures/ under here).
base_dir = _bridge.base_dir

__all__ = [
    "__version__", "reload_scripts",
    "on_tick", "on_draw", "on_key", "on_button", "on_cheat", "on_game_start", "on_shutdown",
    "on_vehicle_created", "on_vehicle_destroyed", "on_ped_created",
    "on_ped_destroyed", "on_object_created", "on_object_destroyed",
    "script", "start", "Task",
    "Entity", "Ped", "Vehicle", "GameObject",
    "PedTasks", "PedWeapons", "VehicleDoor", "VehicleDoors", "VehicleTyre",
    "VehicleTyres", "VehicleDamage", "VehicleMods", "VehicleAI",
    "ObjectAnimation",
    "all_peds", "all_vehicles", "all_objects", "load_model", "release_model",
    "peds", "vehicles", "objects",
    "KEY", "Vector3", "PED_TYPE", "VEHICLES", "WEAPON", "vehicle_id",
    "call", "call_ex", "call_func", "cmd", "Out", "End", "NOT", "OPCODES",
    "doc", "find_commands", "signature",
    "player", "PLAYER_STATE", "PlayerStats", "PlayerGroup", "PlayerWeapons",
    "PlayerWanted", "PlayerControls", "PlayerPerks", "PlayerClothes",
    "PlayerVitals", "PlayerVehicles", "PlayerTargeting", "PlayerRecords",
    "PlayerCamera", "PlayerCoop", "PlayerMissions",
    "Struct", "struct_of", "OFFSETS",
    "Hook", "Call", "on_call", "hook", "find_functions", "function_doc",
    "GameEvent", "on_vehicle_damage", "on_vehicle_explode", "on_tyre_burst",
    "on_weapon_fire", "on_explosion", "on_wanted_level_change",
    "on_projectile_fired", "on_weapon_given",
    "blips", "camera", "draw", "hooks", "hud", "memory", "pickups", "world",
    "game_events", "markers", "timers", "audio", "fx", "text", "pad", "BUTTON",
    "Checkpoint", "Marker3D", "Sphere", "CHECKPOINT", "Fire",
    "Stopwatch", "Countdown", "MissionAudio", "RADIO", "FxSystem",
    "log", "game_time", "key_down", "base_dir",
]
