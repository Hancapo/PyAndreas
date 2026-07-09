# PyAndreas — Python scripting for GTA San Andreas

A Python layer for [plugin-sdk](https://github.com/DK22Pac/plugin-sdk), **San Andreas only** (PC 1.0 US).
Drop `.py` files into `<game>\PyAndreas\scripts\` and they run inside the game, with
hot reload, event decorators, and access to all ~2,600 SCM script commands, raw
memory, game pools and raw game functions.

```python
import pysa
from pysa import player, world, hud, cmd, KEY, Vehicle

@pysa.on_key(KEY.F2)
def tank():
    Vehicle.spawn('rhino')
    hud.help_text("Have a tank.")

@pysa.on_cheat("MOON")            # just type MOON in-game
def moon_gravity():
    world.set_gravity(0.002)

@pysa.script                      # coroutine: yield = wait
def intro():
    yield 3000
    hud.big_text("PyAndreas ready")

@pysa.on_draw
def overlay():
    hud.draw(f"${player.money}", 20.0, 300.0, color=(80, 220, 80))
```

Every script command is a plain Python function with a known signature —
outputs are return values, conditions are bools, entities come back wrapped:

```python
x, y, z = cmd.GET_CAR_COORDINATES(car)       # no output markers
car = cmd.CREATE_CAR(411, 2488, -1666, 13)   # -> Vehicle; ints coerced to floats
driver = cmd.GET_DRIVER_OF_CAR(car)          # -> Ped, or None
if cmd.IS_CHAR_IN_ANY_CAR(player.ped): ...   # -> bool

pysa.find_commands('blip')                   # discover commands by name/description
help(cmd.CREATE_CAR)                         # signature + description + opcode
```

## How it works

```
gta_sa.exe
 └─ PyAndreas.SA.asi      C++ plugin (plugin-sdk) that embeds CPython (32-bit,
    │                     stable ABI - any Python 3.8+ x86 runtime works)
    ├─ _pysa              builtin C module: SCM command runner, memory access,
    │                     raw function calls, pools, HUD, input
    └─ pysa               pure-Python package: decorators, Player/Ped/Vehicle
                          classes, opcode database, Vector3, models, keys...
```

Script commands are executed exactly the way plugin-sdk's
`scripting::CallCommandById` does it — a synthetic `CRunningScript` +
`ProcessOneCommand` — but packed at runtime, so *every* opcode is callable
from Python without recompiling anything.

## Install (into the game)

1. `scripts\PyAndreas.SA.asi` → `<game>\scripts\` (needs an ASI loader, as usual)
2. The `PyAndreas` folder → game root:
   ```
   <game>\PyAndreas\python\     32-bit embeddable Python (python3.dll, python313.dll, ...)
   <game>\PyAndreas\lib\pysa\   the pysa package
   <game>\PyAndreas\scripts\    your .py scripts
   ```
3. Start the game. `PyAndreas\PyAndreas.log` tells you what loaded.

Both pieces are produced in `dist\` by the build. The Python runtime **must be
32-bit** (the game is a 32-bit process); the bundled one is the official
python.org 3.13.5 win32 embeddable package.

- **F11** reloads all scripts in-game (edit → save → F11, no restart).
- A script that throws gets its handler disabled and the traceback logged —
  it can't take the game or other scripts down.

## Install (for editor autocomplete)

Install the `pysa` package into your desktop Python in editable mode:

```powershell
tools\install_pysa_module.ps1
```

or from `cmd.exe`:

```bat
tools\install_pysa_module.bat
```

This does **not** build or install the `.ASI`; it only adds the source package
to Python's site-packages so editors can resolve `import pysa`. Because it is an
editable install, autocomplete follows changes made under `python\pysa`.

The package includes a generated `native.pyi` stub so dynamic calls like
`cmd.CREATE_CAR(...)` and `cmd.GET_PLAYER_CHAR(...)` also show up in language
servers such as Pylance/PyCharm. Regenerate it after signature changes with:

```powershell
python tools\gen_native_stub.py
```

## The API in 60 seconds

| | |
|---|---|
| Events | `@on_tick`, `@on_tick(ms=500)`, `@on_draw`, `@on_key(KEY.F3)`, `@on_cheat("WORD")`, `@on_game_start`, `@on_shutdown`, `@on_vehicle_created`, `@on_ped_created`, ... |
| Coroutines | `@pysa.script` (auto-runs each game start) and `pysa.start(gen)`; `yield 500` waits 500ms of game time, bare `yield` waits a frame |
| Player | `player.money`, `player.wanted_level`, `player.pos`, `player.health/armour`, `player.vehicle`, `player.ped`, `player.heal()` |
| Peds | `Ped.spawn(model, pos)`, `.health/armour/money/pos/heading/velocity`, `.give_weapon(WEAPON.MINIGUN)`, `.make_proof()`, `.freeze()`, `all_peds()` |
| Ped AI | `ped.tasks.wander() / go_to(pos) / enter_vehicle(veh) / attack(target) / flee_from(target) / drive_around(veh) / play_anim(...) / clear()` |
| Vehicles | `Vehicle.spawn('infernus')`, `.pos/heading/health/speed/colours/driver/dirt_level`, `.engine_on()`, `.give_nitro()`, `.hydraulics()`, `.lock()`, `.explode()`, `all_vehicles()` |
| World | `world.set_time(0, 0)`, `world.force_weather(...)`, `world.set_gravity(0.002)`, `world.ground_z(x, y)`, `world.explosion(pos)`, `world.set_time_scale(0.3)` |
| Blips | `blips.add_for_char(ped)`, `add_for_coord(pos, color=...)`, `b.scale = 4`, `b.remove()` |
| Camera | `camera.fix_at(pos, look_at=...)`, `point_at(entity)`, `restore()`, `shake()`, `fade_out()/fade_in()`, `widescreen()` |
| Pickups | `pickups.weapon(pos, WEAPON.AK47, ammo=120)`, `pickups.money(pos, 5000)`, `p.collected` |
| HUD | `hud.help_text(...)`, `hud.text(...)`, `hud.big_text(...)`, `hud.draw(text, x, y, ...)` per frame |
| Any opcode | `cmd.ANY_OF_1616_COMMANDS(...)` with real signatures; `pysa.find_commands('...')` and `help(cmd.NAME)` to explore |
| Memory | `memory.read_float(0x863984)`, `memory.write_u8(...)`, `memory.patch(addr, b"\x90")` (SEH-guarded: bad address = ValueError, not a crash) |
| Raw funcs | `call_func(0x431950, 'c', 'v', 'i', 300)` — cdecl/stdcall/thiscall, up to 12 args |

Return rules for `cmd.*`: condition-only commands → `bool`; commands with
outputs → the value (or a tuple); condition **and** outputs → the outputs, or
`None` when the check fails; `Char`/`Car`/`Object` outputs arrive as
`Ped`/`Vehicle`/`GameObject` (or `None` for handle −1). Ints are accepted
where floats are expected. The ~1,000 commands that vanilla SA doesn't
actually implement (NOPs, control flow, var-math) are excluded from the
signature DB; raw opcodes can still be called through `call()` with
`Out.INT/FLOAT/STR` markers.

## Building from source

Requirements: VS 2022 (v143, C++ x86), plugin-sdk with `output\lib\Plugin.lib`
built for SA, and 32-bit Python headers/libs (easiest: the `pythonx86` nuget
package).

```
msbuild plugin\PyAndreas.vcxproj -p:Configuration="Release GTA-SA" -p:Platform=Win32 ^
    -p:PLUGIN_SDK_DIR=C:\path\to\plugin-sdk ^
    -p:PYTHON_X86_DIR=C:\path\to\pythonx86\tools
```

If `GTA_SA_DIR` is set, the ASI is copied to `%GTA_SA_DIR%\scripts` after the
build (plugin-sdk convention). The plugin links `python3.lib` (stable ABI) and
delay-loads `python3.dll`, so the DLLs can live in `PyAndreas\python` instead
of the game root.

Regenerate the opcode database after a plugin-sdk update with
`python tools\gen_opcodes.py <sdk-path>`, and the signature database from
Sanny Builder Library data with `python tools\gen_signatures.py sa.json`
(https://library.sannybuilder.com/assets/sa/sa.json).

## Repository layout

```
plugin/           C++ ASI plugin (VS solution)
python/pysa/      the Python package (also runs standalone via a mock bridge, for tests)
scripts/          example scripts (spawner, teleports, god mode, speedometer)
tools/            opcode database generator
dist/             ready-to-install output (ASI + PyAndreas game folder)
```

## Notes & limits

- Targets the 1.0 US executable (`PLUGIN_SGV_10US`), like most plugin-sdk mods.
- Scripts run on the game thread inside game events — don't block (no `time.sleep`);
  use `@on_tick(ms=...)` for timing. Threads are possible but must not touch
  game state off the main thread.
- `memory.write_*` to code pages needs `unprotect=True` (or use `memory.patch`).
- The cheat-string watcher shares the game's own cheat buffer; avoid words that
  collide with built-in cheats.
