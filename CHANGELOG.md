# Changelog

All notable changes to `PyAndreas` are documented in this file.

The changelog is release-oriented and uses a small fixed set of categories:
`Breaking Changes`, `Added`, `Changed`, `Fixed`, and `Performance`.

## [Unreleased]

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
- Weapon, vehicle, ped, pickup, checkpoint, explosion, and common SCM domains now consistently accept typed enums while preserving integer compatibility.
- SCM discovery, documentation, runtime signatures, and generated editor stubs now retain entity, model, weapon, and enum types instead of collapsing them to raw integers.
- Script reloads now refresh local helper modules and transactionally roll back handlers, tasks, hooks, and game events created by failed imports.
- The ASI now discovers its Python runtime, library, and scripts relative to its actual loaded location, enabling Mod Loader installations while preserving traditional game-root installs.

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
