# PyAndreas

Python scripting for **Grand Theft Auto: San Andreas** through a plugin-sdk ASI
bridge.

PyAndreas embeds CPython into GTA SA and exposes a Python package, `pysa`, for
writing in-game scripts with hot reload, event decorators, typed entity wrappers,
SCM opcode calls, memory helpers, HUD helpers, and raw game function calls.

> Status: early source release. This targets GTA San Andreas PC 1.0 US and is
> intended for people comfortable building ASI plugins and working with
> plugin-sdk.

## Highlights

- Write GTA SA scripts in Python instead of SCM/CLEO.
- Reload scripts in-game with **F11**.
- Use event decorators such as `@pysa.on_tick`, `@pysa.on_key`,
  `@pysa.on_cheat`, `@pysa.on_draw`, and game entity lifecycle hooks.
- Work with OOP wrappers for `player`, `Ped`, `Vehicle`, `GameObject`, blips,
  pickups, world state, camera, HUD, and tasks.
- Call vanilla SA script commands through `cmd.COMMAND_NAME(...)` with generated
  signatures.
- Access raw memory and raw game functions when the high-level API does not
  cover something yet.
- Install the Python package locally in editable mode for real editor
  autocomplete.

## Example

```python
import pysa
from pysa import KEY, WEAPON, Vehicle, cmd, hud, player, world


@pysa.on_key(KEY.F2)
def spawn_infernus():
    car = Vehicle.spawn("infernus")
    player.ped.warp_into(car)
    hud.help_text("Infernus spawned")


@pysa.on_key(KEY.F3)
def loadout():
    player.weapons.give(WEAPON.M4, 500)
    player.weapons.give(WEAPON.DESERT_EAGLE, 100)
    player.perks.never_tired = True
    player.wanted.level = 0


@pysa.on_cheat("MOON")
def moon_gravity():
    world.set_gravity(0.002)


@pysa.on_draw
def overlay():
    hud.draw(f"${player.money}", 20.0, 300.0, color=(80, 220, 80))


@pysa.script
def intro():
    yield 3000
    hud.big_text("PyAndreas ready")


# Raw SCM command access is still available.
x, y, z = cmd.GET_CHAR_COORDINATES(player.ped)
```

## Repository Contents

This repository contains source code only. Built ASI files, Visual Studio object
files, packaged game folders, and bundled Python runtimes are intentionally not
committed.

```text
plugin/           C++ ASI plugin source and Visual Studio project
python/pysa/      Python API package used by scripts and editors
scripts/          Example in-game scripts
tools/            Opcode/signature/stub generation and editor install helpers
pyproject.toml    Editable Python package metadata
```

## Install for Editor Autocomplete

This is the easiest way to get `import pysa` working in VS Code, PyCharm, or any
other editor. It does not build or install the ASI plugin.

From PowerShell:

```powershell
.\tools\install_pysa_module.ps1
```

From `cmd.exe`:

```bat
tools\install_pysa_module.bat
```

Or manually:

```powershell
python -m pip install -e .
```

The install is editable, so changes under `python\pysa` are immediately visible
to your desktop Python environment. If the editor was already open, reload the
window or restart the Python language server.

Dynamic opcode autocomplete is provided by `python/pysa/native.pyi`. Regenerate
it after changing command signatures:

```powershell
python tools\gen_native_stub.py
```

## In-Game Install Layout

To run scripts inside GTA SA, the game needs the built ASI plugin and a
`PyAndreas` folder in the game root:

```text
<game>\scripts\PyAndreas.SA.asi
<game>\PyAndreas\python\      32-bit embeddable Python runtime
<game>\PyAndreas\lib\pysa\    the pysa package
<game>\PyAndreas\scripts\     your .py scripts
```

The game is a 32-bit process, so the embedded Python runtime must also be
32-bit. The ASI delay-loads `python3.dll`, allowing the Python DLLs to live under
`<game>\PyAndreas\python` instead of beside `gta_sa.exe`.

Scripts are loaded from `<game>\PyAndreas\scripts`. Press **F11** in-game to
reload all scripts without restarting the game. Errors are written to
`<game>\PyAndreas\PyAndreas.log`, and a failing handler is disabled instead of
bringing down the whole script runtime.

## Build From Source

Requirements:

- GTA San Andreas PC 1.0 US.
- An ASI loader.
- Visual Studio 2022 with the v143 C++ toolset.
- Win32/x86 build target.
- plugin-sdk built for San Andreas, including `output\lib\Plugin.lib`.
- 32-bit Python headers/libs. The `pythonx86` NuGet package is the simplest
  source for these files.

Build command:

```bat
msbuild plugin\PyAndreas.vcxproj ^
  -p:Configuration="Release GTA-SA" ^
  -p:Platform=Win32 ^
  -p:PLUGIN_SDK_DIR=C:\path\to\plugin-sdk ^
  -p:PYTHON_X86_DIR=C:\path\to\pythonx86\tools
```

If `GTA_SA_DIR` is set, the Visual Studio project follows plugin-sdk convention
and copies the ASI to `%GTA_SA_DIR%\scripts` after a successful build.

The ready-to-copy game package is expected to be produced locally under `dist/`.
That folder is ignored by git because it contains generated binaries and bundled
runtime files.

## Python API Overview

| Area | Examples |
| --- | --- |
| Events | `@pysa.on_tick`, `@pysa.on_tick(ms=500)`, `@pysa.on_draw`, `@pysa.on_key(KEY.F3)`, `@pysa.on_cheat("WORD")` |
| Coroutines | `@pysa.script`, `pysa.start(generator)`, `yield 500` to wait game milliseconds |
| Player | `player.ped`, `player.pos`, `player.money`, `player.vitals.heal()`, `player.wanted.level = 0` |
| Player OOP facades | `player.weapons.give(...)`, `player.controls.enabled`, `player.perks.never_tired`, `player.vehicles.current` |
| Peds | `Ped.spawn(...)`, `ped.health`, `ped.armour`, `ped.tasks.attack(...)`, `ped.weapons.give(...)` |
| Vehicles | `Vehicle.spawn("infernus")`, `car.health`, `car.speed`, `car.doors[0].open()`, `car.give_nitro()` |
| World | `world.set_time(...)`, `world.force_weather(...)`, `world.ground_z(...)`, `world.explosion(...)` |
| HUD | `hud.help_text(...)`, `hud.big_text(...)`, `hud.draw(...)` |
| Camera | `camera.fix_at(...)`, `camera.point_at(...)`, `camera.restore()`, `camera.shake()` |
| Blips/pickups | `blips.add_for_char(...)`, `blips.add_for_coord(...)`, `pickups.weapon(...)`, `pickups.money(...)` |
| SCM commands | `cmd.CREATE_CAR(...)`, `cmd.GET_PLAYER_CHAR(...)`, `pysa.find_commands("blip")` |
| Memory/raw funcs | `memory.read_float(...)`, `memory.patch(...)`, `call_func(...)` |

## SCM Command Rules

Every generated `cmd.*` wrapper follows the same return rules:

- Condition-only commands return `bool`.
- Commands with outputs return the output value, or a tuple for multiple
  outputs.
- Condition commands with outputs return the outputs when the condition passes,
  otherwise `None`.
- `Char`, `Car`, and `Object` outputs are wrapped as `Ped`, `Vehicle`, and
  `GameObject`.
- `-1` entity handles are returned as `None`.
- Integers are accepted where float parameters are expected.

Commands missing from the generated signature database can still be called with
the lower-level `call()` API and explicit `Out.INT`, `Out.FLOAT`, or `Out.STR`
markers.

## Regenerating Generated Data

Regenerate opcode names from plugin-sdk:

```powershell
python tools\gen_opcodes.py C:\path\to\plugin-sdk\plugin_sa
```

Regenerate signatures from Sanny Builder Library `sa.json`:

```powershell
python tools\gen_signatures.py C:\path\to\sa.json
```

Regenerate editor stubs:

```powershell
python tools\gen_native_stub.py
```

## Notes and Limits

- PyAndreas targets `PLUGIN_SGV_10US`.
- Script callbacks run on the game thread. Do not use blocking calls such as
  `time.sleep()` from handlers.
- Threads can exist, but game state should only be touched from the main game
  thread.
- `memory.write_*` to code pages requires `unprotect=True`, or use
  `memory.patch(...)`.
- The cheat-string watcher uses the game's own cheat buffer, so avoid cheat
  words that collide with built-in cheats.

## License

MIT. See [LICENSE](LICENSE).
