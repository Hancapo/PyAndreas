# Changelog

## 0.2.0 - 2026-07-09

- Added a complete release builder with a copy-ready game layout, deterministic
  ZIP archive, and SHA-256 checksum.
- Added integer enums for ped bones, gangs, vehicle classes/types, animation
  flags, and radar sprites; weapon and vehicle APIs consistently accept enums.
- Added friendly read-only model information for generic, vehicle, and ped
  models.
- Added atomic JSON persistence through `pysa.storage` with automatic shutdown
  and hot-reload flushing.
- Added read-only `Building` and `Dummy` entities and live
  `world.buildings`/`world.dummies` collections.
- Added opt-in HUD/radar/menu/fade and entity-render events. High-frequency
  native events do not enter Python unless a handler is registered.
- Improved SCM documentation and editor stubs with entity, weapon, model, and
  enum parameter types.
- Added typed declarations for all core event decorators, including exact
  `Vehicle`, `Ped`, `GameObject`, and model-change callback signatures.
- Added specific high-level game-event payload classes, typed weapon fields,
  and the plugin-sdk-derived `EXPLOSION_KIND` enum.
- Added the complete `PICKUP_TYPE` enum, corrected the former swapped
  once/respawning constants, and exposed active pickups through
  `world.pickups` with friendly model/type/ammo/position properties.
- Added the MSPARK CLEO test port and the reusable API it exposed as missing:
  safe checkpoint visual updates, ped-local offsets, vehicle-to-object
  attachment, mission-audio cleanup/slot enums, and smoke/light/corona helpers.
- Added ped animation clips, vehicle/camera conveniences, automatic
  `ScriptSession` resource ownership, typed world raycasts with complete
  surface enums, intuitive controller actions, simple menus, safe game-thread
  scheduling, and subscription-gated gameplay state events.
- Expanded transactional hot reload, lifecycle/model events, offline tests,
  and source-archive packaging.

## 0.1.0

- Initial source release.
