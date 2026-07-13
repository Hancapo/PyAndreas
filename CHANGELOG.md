# Changelog

All notable changes to `PyAndreas` are documented in this file.

The changelog is release-oriented and uses a small fixed set of categories:
`Breaking Changes`, `Added`, `Changed`, `Fixed`, and `Performance`.

## [Unreleased]

### Fixed
- Moving the mouse over autocomplete results no longer changes the active
  keyboard selection or repositions the suggestion list; clicking still
  selects and accepts the hovered result.

## [0.3.0] - 2026-07-13

### Added
- A built-in F10 developer console with live Python evaluation, command history, script reload commands, and test execution.
- Extensible slash commands with aliases, typed arguments, usage help, typo suggestions, argument completion, and automatic removal during script reloads.
- Console autocomplete for PyAndreas APIs, nested attributes, enums, and function results, with parameter hints, syntax highlighting, and assignment warnings.
- Mouse editing for console input and history, including text selection, clipboard shortcuts, clickable suggestions, smooth scrolling, and scrollbar dragging.
- A native **Options > PyAndreas** menu for Developer Mode and console settings for scale, opacity, history size, font, and autocomplete.
- Map waypoint access through `blips.waypoint()`, plus short-range blips, contact points, friendly markers, and additional visibility and appearance controls.
- Typed world/interior areas and structured EnEx entrance data, with player teleporting that keeps CJ, his vehicle, world visibility, heading, and collision loading synchronized.
- Camera movement, tracking, FOV transitions, entity attachment, collision control, persistent positions, and cinematic views.
- High-level controls for HUD and radar visibility, radar zoom, game language, and the save menu.
- `Cutscene` and `Train` APIs for cutscene playback and train spawning, movement, speed, stations, carriages, and cleanup.
- World date and clock state helpers, road and pedestrian-path controls, straight-road queries, and script roadblocks.
- `@pysa.dev_test` and `pysa.run_tests()` for in-game tests, including tests that wait for game time.
- Reusable sliders, buttons, toggles, themes, and hitboxes for custom interfaces.
- Expanded editor type information for entity collections, events, player state, vehicles, models, controllers, menus, and callbacks.

### Changed
- Plain `print(...)` output from user mods appears as an in-game subtitle while remaining mirrored in `PyAndreas.log`.
- Weapon and common SCM values use named enums in autocomplete while retaining integer compatibility.
- Console text input follows the active Windows keyboard layout, including Shift and AltGr combinations.
- Gameplay keyboard, mouse, controller, and camera actions are suppressed while the console is open.

### Fixed
- Player skin changes no longer crash when the requested model is not already loaded.
- Entity creation callbacks no longer expose vehicles, pedestrians, or objects before their model and handle are valid.
- Deleted entities are rejected instead of being reused through stale Python objects.
- Console autocomplete recovers after correcting a partial name and updates continuously while typing.
- Console text, suggestions, parameter hints, history, selections, and scrollbars remain clipped to their panels at different resolutions and UI scales.
- Held Backspace, Delete, arrow keys, and suggestion navigation repeat correctly.
- Opening the pause menu while the console is active no longer leaves player controls disabled after returning to the game.
- Console text and caret rendering remain aligned above the HUD, including whitespace and long input lines.
- EnEx entrance headings are converted to the degree-based heading used by the rest of PyAndreas before teleporting the player.
- Developer-console autocomplete and parameter hints work correctly when the editor package is installed with Python 3.8.

## [0.2.0] - 2026-07-09

### Added
- Integer enums for ped bones, gangs, vehicle classes and types, animation flags, radar sprites, mission-audio slots, checkpoint styles, explosion kinds, pickup types, and collision surfaces.
- Friendly read-only model information for generic, vehicle, and ped models, including vehicle handling data.
- Atomic JSON persistence through `pysa.storage`, with automatic shutdown and hot-reload flushing.
- Read-only `Building` and `Dummy` wrappers and live spatial collections for buildings, dummies, vehicles, peds, objects, and pickups.
- Typed lifecycle, model-change, draw-stage, and entity-render events, including exact callback declarations for editor autocomplete.
- High-level game-event payloads for vehicle damage and explosions, tyre bursts, weapon fire and grants, wanted-level changes, projectiles, and pickup collection, with cancellation or argument rewriting where the underlying hook supports it.
- Ped animation clips, vehicle and camera conveniences, ped-local offsets, vehicle-to-object attachment, safe checkpoint visual updates, mission-audio cleanup, and smoke, light, and corona helpers.
- `ScriptSession` ownership for spawned entities, markers, mission audio, camera overrides, and player-control cleanup across normal exit, errors, cancellation, and hot reload.
- Typed native world raycasts with collision position, normal, entity, material, lighting, piece, and depth information.
- Intuitive controller stick directions, reusable button actions and combos, and a simple keyboard/controller `ui.Menu` with actions, toggles, and choices.
- Subscription-gated ped damage and death, vehicle enter and exit, weapon-change, and zone-transition events.
- `run_on_game_thread()` for safely handing background-thread results back to GTA's game thread.

### Changed
- Weapon, vehicle, ped, pickup, checkpoint, explosion, and common SCM domains consistently accept typed enums while preserving integer compatibility.
- SCM discovery, documentation, runtime signatures, and generated editor stubs retain entity, model, weapon, and enum types instead of collapsing them to raw integers.
- Script reloads refresh local helper modules and transactionally roll back handlers, tasks, hooks, and game events created by failed imports.
- The ASI discovers its Python runtime, library, and scripts relative to its actual loaded location, enabling Mod Loader installations while preserving traditional game-root installs.

### Fixed
- Corrected swapped once-only and respawning pickup constants to match plugin-sdk's `ePickupType` values.
- Script task cleanup continues across individual cleanup failures instead of abandoning the remaining resources.
- Failed script imports no longer leak partially registered callbacks, hooks, tasks, or local helper modules.

### Performance
- High-frequency HUD, radar, menu, fade, vehicle-render, ped-render, and object-render events enter Python only while subscribed.
- Polled gameplay state events remain dormant until a matching handler is registered.
- CPython releases the GIL between game frames so ordinary `threading` and `asyncio` workers can continue running.

## [0.1.0] - 2026-07-09

### Added
- Initial release of the GTA San Andreas 1.0 US ASI bridge and Python scripting API.
- Embedded CPython runtime hosting, hot-reloaded scripts, SCM opcode calls, typed entity wrappers, HUD helpers, memory access, game-structure fields, and raw function hooks.
