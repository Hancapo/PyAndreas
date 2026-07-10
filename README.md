# PyAndreas

Python scripting for **Grand Theft Auto: San Andreas** through a plugin-sdk ASI
bridge.

PyAndreas embeds CPython into GTA SA and exposes a Python package, `pysa`, for
writing in-game scripts with hot reload, event decorators, typed entity wrappers,
SCM opcode calls, memory helpers, HUD helpers, and raw game function calls.

> Status: v0.2 development release. This targets GTA San Andreas PC 1.0 US.
> Copy-ready ZIP releases include the ASI, Python runtime, one-file `pysa.pyz`,
> examples, install instructions, and a SHA-256 checksum.

## Highlights

- Write GTA SA scripts in Python instead of SCM/CLEO.
- Reload scripts in-game with **F11**.
- Use event decorators such as `@pysa.on_tick`, `@pysa.on_key`,
  `@pysa.on_cheat`, `@pysa.on_draw`, and game entity lifecycle hooks.
- Work with OOP wrappers for `player`, `Ped`, `Vehicle`, `GameObject`, blips,
  pickups, world state, camera, HUD, and tasks.
- Call vanilla SA script commands through `cmd.COMMAND_NAME(...)` with generated
  signatures and editor types for entities, models, weapons, and common enums.
- Keep script state with the small dictionary-like `pysa.storage` API.
- Access raw memory and raw game functions when the high-level API does not
  cover something yet.
- Install the Python package locally in editable mode for real editor
  autocomplete.

## Example

```python
import pysa
from pysa import KEY, VEHICLE, WEAPON, Vehicle, hud, player, world


@pysa.on_key(KEY.F2)
def spawn_infernus():
    car = Vehicle.spawn(VEHICLE.INFERNUS)
    player.ped.warp_into(car)
    hud.help_text("Your Infernus is ready")


@pysa.on_key(KEY.F3)
def loadout():
    player.weapons.give(WEAPON.M4, 500)
    player.weapons.give(WEAPON.DESERT_EAGLE, 100)
    player.vitals.heal()


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
```

The common path uses typed constants and plain Python values. Raw SCM commands, memory,
structs, and hooks are available as advanced escape hatches when a high-level
operation does not exist yet.

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

### Example Scripts

Each shows off a different part of the API:

| Script | Demonstrates |
| --- | --- |
| `example_quickstart.py` | beginner API: vehicle/weapon enums, healing, teleporting |
| `example_spawner.py` | cheat-word triggers, `Vehicle.spawn` |
| `example_teleport.py` | hotkeys, `Vector3`, `world.ground_z` |
| `example_godmode.py` | toggles, `cmd.*` proofs, `@pysa.on_tick(ms=...)` |
| `example_speedometer.py` | per-frame `hud.draw` |
| `example_bodyguard.py` | `@pysa.script` coroutines, `ped.tasks.*`, blips |
| `example_hud_panel.py` | `draw.rect`/`draw.bar` health/armour panel |
| `example_textures.py` | `draw.load_textures` + `draw.sprite` (with fallback) |
| `example_hook_damage.py` | game events: `on_vehicle_damage`, `on_explosion` |
| `example_infinite_ammo.py` | game event: `on_weapon_given`, rewriting a field |
| `example_checkpoint_race.py` | `Checkpoint`/`Marker3D`, `Countdown`, `entity.distance_to`, coroutine |
| `example_carnage.py` | iterating `pysa.vehicles`, `.near(...)`, `car.explode()`, `car.model_name` |
| `example_effects.py` | `fx.FxSystem.on(...)`, `fx.corona(...)`, `audio.play_sound(...)` |
| `example_gamepad.py` | `@on_button(...)`, `pad.pressed(...)` combos, `pad.left_stick()`, `pad.rumble()` |
| `example_threads.py` | background threads (GIL released between frames) |

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
<game>\scripts\PyAndreas.asi
<game>\PyAndreas\python\      32-bit embeddable Python runtime
<game>\PyAndreas\lib\pysa.pyz  the complete pysa package in one archive
<game>\PyAndreas\scripts\     your .py scripts
```

The game is a 32-bit process, so the embedded Python runtime must also be
32-bit. The ASI delay-loads `python3.dll`, allowing the Python DLLs to live under
`<game>\PyAndreas\python` instead of beside `gta_sa.exe`.

Scripts are loaded from `<game>\PyAndreas\scripts`. Press **F11** in-game to
reload all scripts without restarting the game. Errors are written to
`<game>\PyAndreas\PyAndreas.log`, and a failing handler is disabled instead of
bringing down the whole script runtime. Reload also refreshes helper modules
inside the scripts folder. If a script fails while importing, its partially
registered events, tasks, and hooks are rolled back.

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

Package the Python library into the game layout as one source archive:

```powershell
python tools\package_pysa.py
```

This creates `dist\PyAndreas\lib\pysa.pyz` and removes the obsolete generated
`dist\PyAndreas\lib\pysa` folder. Python imports directly from the archive;
user scripts remain normal editable `.py` files.

Build the ASI and assemble the complete copy-ready release in one command:

```powershell
.\tools\build_release.ps1 `
  -PluginSdkDir C:\path\to\plugin-sdk `
  -PythonX86Dir C:\path\to\pythonx86\tools
```

This produces `dist\release`, `dist\PyAndreas-<version>-win32.zip`, and its
`.sha256` checksum. Add `-GameDir C:\path\to\GTA-SA` to install the assembled
release after a successful build. By default it packages the embeddable runtime
already at `dist\PyAndreas\python`; use `-RuntimeDir` to select another one.

## Development Checks

The Python API and offline runtime have a standard-library test suite:

```powershell
python -m compileall -q python scripts tools tests
python -m unittest discover -s tests -v
```

The same checks run on Python 3.8 and 3.13 in GitHub Actions.

## Python API Overview

| Area | Examples |
| --- | --- |
| Events | `@pysa.on_tick`, `@pysa.on_tick(ms=500)`, `@pysa.on_draw`, `@pysa.on_key(KEY.F3)`, `@pysa.on_cheat("WORD")` |
| Plugin lifecycle | `@pysa.on_game_restart`, `@pysa.on_vehicle_model_changed`, `@pysa.on_device_reset`, pool/render lifecycle hooks |
| Opt-in render events | `@pysa.on_hud_draw`, `@pysa.on_vehicle_render`, `@pysa.on_ped_render` (native-to-Python dispatch is subscription-gated) |
| Gamepad | `@pysa.on_button(BUTTON.CROSS)`, `pad.pressed(BUTTON.L1)`, `pad.left_stick()`, `pad.rumble()` |
| Typed constants | `PED.BMYBOUN`, `VEHICLE.INFERNUS`, `WEAPON.M4`, `MOVE_STATE.RUN`, `CAMERA_MODE.FIXED` |
| Coroutines | `@pysa.script`, `pysa.start(generator)`, `yield 500` to wait game milliseconds |
| Player | `player.ped`, `player.pos`, `player.money`, `player.vitals.heal()`, `player.wanted.level = 0` |
| Player OOP facades | `player.weapons.give(WEAPON.M4)`, `player.controls.enabled`, `player.perks.never_tired`, `player.vehicles.current` |
| Peds | `Ped.spawn(PED.BMYBOUN, pos)`, `ped.health`, `ped.tasks.go_to(pos, MOVE_STATE.RUN)`, `ped.weapons.give(...)` |
| Vehicles | `Vehicle.spawn(VEHICLE.INFERNUS)`, `car.speed`, `car.doors[VEHICLE_DOOR.FRONT_LEFT]`, `car.ai.driving_style(DRIVING_STYLE.AVOID_CARS)` |
| Handling data | `car.handling.mass`, `.traction_multiplier`, `.center_of_mass`, `.suspension_force` (read-only shared model data) |
| Model information | `car.model_info.game_name`, `.vehicle_type`, `.door_count`, `.dimensions`, `model_info(VEHICLE.INFERNUS)` |
| World | `world.set_time(...)`, `world.force_weather(...)`, `world.ground_z(...)`, `world.explosion(...)` |
| HUD | `hud.help_text(...)`, `hud.big_text(...)`, `hud.draw(...)` |
| Camera | `camera.fix_at(...)`, `camera.point_at(...)`, `camera.restore()`, `camera.shake()` |
| Blips/pickups | `blips.add_for_char(...)`, `pickups.weapon(..., pickup_type=PICKUP_TYPE.ONCE)`, inspect active items through `world.pickups` |
| Markers | `Checkpoint(pos)`, `Marker3D(pos)`, `Sphere(pos, r)` with `pos in sphere` |
| Entity pools | `world.vehicles`, `peds`, `objects`, `buildings`, `dummies`, and live `world.pickups`; all support iteration and spatial queries |
| Pool queries | `world.vehicles.near(pos, r)`, `.nearest(pos, exclude=...)`, `.where(...)`, `.of_model("rhino")` |
| Vehicle data | `car.model`, `car.model_name` ('infernus'), `car.occupants`, `car.passengers`, `car.driver`, `car.empty` |
| Spatial | `entity.distance_to(x)`, `entity.is_near(x, r)`, `world.nearest_ped(pos)`, `world.peds_near(pos, r)` |
| Timers | `Stopwatch().seconds`, `Countdown(5000).finished`, `.fraction`, `.remaining` |
| Persistence | `state = storage.open("my_mod", {"score": 0})`, dictionary access, atomic `state.save()` and automatic shutdown flush |
| Audio | `audio.play_sound(pos, id)`, `audio.set_radio(RADIO.K_DST)`, `MissionAudio(0).load(...).play()` |
| Particle FX | `FxSystem("fire", pos).play()`, `FxSystem.on(ped, "smoke30")`, `fx.corona(pos, size, color)` |
| GXT text | `text.load_table(...)`, `text.show("KEY", x, y, number=..., color=..., align=...)` |
| SCM commands | `cmd.CREATE_CAR(...)`, `cmd.GET_PLAYER_CHAR(...)`, `pysa.find_commands("blip")` |
| Memory/raw funcs | `memory.read_float(...)`, `memory.patch(...)`, `call_func(...)` |
| Struct fields | `ped.struct.m_fHealth`, `car.struct.m_fGasPedal = 1.0`, `struct_of(x, "CPed")` |
| Drawing | `draw.rect(...)`, `draw.bar(...)`, `draw.sprite(...)`, `draw.load_textures(...)` |
| Game events | `@pysa.on_vehicle_damage`, `@pysa.on_explosion`, ...; `e.vehicle`, `e.amount *= 0.5`, `e.cancel()` |
| Function hooks | `@pysa.on_call("CVehicle::InflictDamage")`, `call.this`, `call.intensity`, `call.skip()`, `find_functions(...)` |
| Threads | `threading`/`asyncio` run between frames (GIL is released each frame) |

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
- Editor stubs retain domain types such as `Ped`, `Vehicle`, `WEAPON`,
  `VEHICLE`, `MOVE_STATE`, and `VEHICLE_DOOR` instead of collapsing them to
  untyped integers.

Commands missing from the generated signature database can still be called with
the lower-level `call()` API and explicit `Out.INT`, `Out.FLOAT`, or `Out.STR`
markers.

## Struct Field Access

Every entity exposes `.struct`, a typed view over its raw C++ object built
from plugin-sdk's `VALIDATE_OFFSET` macros (4128 fields across 379 classes,
in `pysa/offsets.py`). Inheritance is flattened, so a Ped's struct also sees
`CPhysical`/`CEntity`/`CPlaceable` fields.

```python
ped = player.ped
print(ped.struct.m_fHealth)     # float, read straight from memory
ped.struct.m_fArmour = 100.0    # typed write
car.struct.m_fGasPedal = 1.0
addr = ped.struct @ "m_fHealth" # absolute address of a field
```

For fields the generator could not type (unions, arrays, bitfields), use the
explicit readers `s.f32(off)`, `s.i32(off)`, `s.u8(off)`, `s.ptr(off)`,
`s.bytes(off, n)`.

## Drawing

`pysa.draw` queues 2D primitives that render each frame (call from an
`@pysa.on_draw` handler). Colors are `(r, g, b)`, `(r, g, b, a)`, or packed
`0xRRGGBBAA`; coordinates are pixels (`hud.screen_size()` gives the resolution).

```python
@pysa.on_draw
def overlay():
    draw.rect(20, 20, 200, 60, (0, 0, 0, 150))    # translucent panel
    draw.bar(24, 40, 192, 8, 0.7, fg=(80, 220, 80))
```

Textures are PNGs loaded once (after the game is up), then drawn by name:

```python
@pysa.on_game_start
def art():
    draw.load_textures(pysa.memory.base_dir() + r"\textures")

@pysa.on_draw
def logo():
    draw.sprite("mylogo", 10, 10, 128, 128)
```

## Plugin Lifecycle Events

Selected low-frequency plugin-sdk events are exposed without adding per-entity
render overhead. Model-change handlers receive the wrapped entity and a typed
model enum (or an integer for a custom model):

```python
@pysa.on_vehicle_model_changed
def changed(vehicle: pysa.Vehicle, model: pysa.VEHICLE | int) -> None:
    print(vehicle, model)  # model is normally a VEHICLE member
```

Available lifecycle decorators are `on_game_restart`, `on_game_reinit`,
`on_render_init`, `on_device_lost`, `on_device_reset`, `on_pools_init`,
`on_pools_shutdown`, `on_vehicle_model_changed`, and `on_ped_model_changed`.

Entity callbacks have shipped editor declarations. Annotate the callback
parameter once and VS Code/Pylance, PyCharm, and other type-aware editors can
autocomplete the complete entity API and validate the decorator signature:

```python
@pysa.on_vehicle_render
def rendering_car(car: pysa.Vehicle) -> None:
    if car.health < 300:
        print(car.model_info.game_name)

@pysa.on_ped_created
def new_ped(ped: pysa.Ped) -> None:
    ped.health = 200
```

Python type checkers cannot infer the local parameter of a newly declared
function backwards from a decorator, so the `: pysa.Vehicle`/`: pysa.Ped`
annotation is required for completion inside that function. The decorator
stubs then preserve and validate that exact callback type.

## Game Events

The friendliest way to react to things the game *does*. These read like the
lifecycle events (`on_vehicle_created` etc.), with domain-named fields:

```python
@pysa.on_vehicle_damage
def tougher_cars(e: pysa.VehicleDamageEvent) -> None:
    if e.vehicle == player.vehicle:
        e.amount *= 0.5        # take half damage (assign to rewrite)
        # e.cancel()          # or ignore the hit entirely

@pysa.on_explosion
def shield(e: pysa.ExplosionEvent) -> None:
    if e.position.distance_to(player.pos) < 5:
        e.cancel()
```

Each handler gets an event `e` with the subject (`e.vehicle`, a `Vehicle`),
named typed fields (`e.attacker` auto-wrapped to Ped/Vehicle/GameObject,
`e.amount` a float, `e.position` a `Vector3`), assignment to rewrite a value
before it happens, `e.cancel()` to stop it, and `e.raw` for the low-level hook.

Every event has a specific payload class for autocomplete:
`VehicleDamageEvent`, `VehicleExplodeEvent`, `TyreBurstEvent`,
`WeaponFireEvent`, `ExplosionEvent`, `WantedLevelChangeEvent`,
`WeaponGivenEvent`, and `ProjectileFiredEvent`. Weapon fields return `WEAPON`
members when known; `ExplosionEvent.kind` returns `EXPLOSION_KIND`. This is
distinct from `world.EXPLOSION`, whose values select SCM-created explosion
effects.

Available events: `on_vehicle_damage`, `on_vehicle_explode`, `on_tyre_burst`,
`on_weapon_fire`, `on_weapon_given`, `on_explosion`, `on_wanted_level_change`,
`on_projectile_fired` (see `pysa/game_events.py`).

## Function Hooks (advanced)

Game events are curated wrappers over the hook layer. To hook a function that
isn't a named event, target it by its catalog name and get named arguments:

```python
@pysa.on_call("CVehicle::InflictDamage")
def cushion(call):
    call.this                             # the Vehicle (owner of the method)
    call.intensity = call.intensity * 0.5 # named, typed argument
    # call.skip()                         # bypass the original

pysa.find_functions("damage")             # discover targets (2149 functions)
print(pysa.function_doc("CVehicle::InflictDamage"))
```

For a function not in the catalog, hook a raw address (low-level `Hook` with
positional stack args and registers):

```python
@pysa.on_call(0x6D7C90, args=6, convention="thiscall")
def raw(h):
    h.arg(0); h.set_argf(2, 0.0); h.reg("eax")
```

Built on safetyhook's mid-hook (conventions read from plugin-sdk's own casts,
so they're accurate). A hook that raises is removed automatically and logged.
Hooks run inside the game's own call on the game thread, so keep them fast;
addresses target the 1.0 US exe, and `skip()`/`cancel()` bypass the original
entirely - powerful, but don't cancel a function the game relies on.

## Regenerating Generated Data

Regenerate opcode names from plugin-sdk:

```powershell
python tools\gen_opcodes.py C:\path\to\plugin-sdk\plugin_sa
```

Regenerate signatures from Sanny Builder Library `sa.json`:

```powershell
python tools\gen_signatures.py C:\path\to\sa.json
```

Regenerate the struct offset database from plugin-sdk:

```powershell
python tools\gen_offsets.py C:\path\to\plugin-sdk
```

Regenerate the named-function catalog from plugin-sdk:

```powershell
python tools\gen_functions.py C:\path\to\plugin-sdk
```

Regenerate the ped-model enum from plugin-sdk:

```powershell
python tools\gen_ped_models.py C:\path\to\plugin-sdk
```

Regenerate the vehicle-model enum from plugin-sdk:

```powershell
python tools\gen_vehicle_models.py C:\path\to\plugin-sdk
```

Regenerate editor stubs:

```powershell
python tools\gen_native_stub.py
```

## Notes and Limits

- PyAndreas targets `PLUGIN_SGV_10US` (1.0 US exe). Raw addresses used by
  `hooks.on_call`, `call_func`, `memory.*` and struct offsets assume that exe.
- Script callbacks run on the game thread. Do not use blocking calls such as
  `time.sleep()` from handlers; use `@pysa.on_tick(ms=...)` or `@pysa.script`.
- The GIL is released between frames, so `threading`/`asyncio` background work
  runs. Only touch game state (commands, memory, entities) from the main game
  thread - i.e. from handlers/coroutines, not from your own threads.
- Function hooks run inside the hooked call on the game thread. Keep them fast;
  hooking a hot function with heavy Python costs FPS. `h.block()` is experimental.
- `memory.write_*` to code pages requires `unprotect=True`, or use
  `memory.patch(...)`.
- The cheat-string watcher uses the game's own cheat buffer, so avoid cheat
  words that collide with built-in cheats.

## License

MIT. See [LICENSE](LICENSE).
