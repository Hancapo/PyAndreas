# Changelog

All notable changes to `PyAndreas` are documented in this file.

The changelog is release-oriented and uses a small fixed set of categories:
`Breaking Changes`, `Added`, `Changed`, `Fixed`, and `Performance`.

## [Unreleased]

### Added
- Public `Position`, `PedModel`, `VehicleModel`, and `WeaponId` aliases for annotating ordinary scripts with the same friendly value forms accepted by PyAndreas.
- A strict editor-facing Pyright contract that prevents callback declarations and common chained API types from silently regressing.
- A built-in F10 developer console with Python evaluation, captured `print()` output, layout-aware text input, cursor editing, history, tab completion, script reload commands, and live test output.
- A native PyAndreas settings page inside GTA's Options menu and a matching persistent `PyAndreas.ini` Developer Mode setting.
- `@dev_test` and `run_tests()` for isolated in-game smoke tests, including generator tests that wait in game milliseconds.
- Mouse-driven console caret placement, drag selection, selection repositioning, and Ctrl+A/C/X/V clipboard editing while the console is open.
- `blips.waypoint()` for retrieving the player's map marker as a `Vector3`.
- Expanded radar helpers with live `Blip.exists`, friendly/zoom/appearance controls, short-range icons, contact points, interior-level visibility, and frontend hiding.
- Smooth and attached camera APIs for position/target/FOV animation, persistence, collision, cinematic mode, and ped/vehicle look-at combinations.
- High-level `game` controls for HUD/radar visibility, radar zoom, typed language detection, and the normal save menu.
- OOP `Cutscene` and `Train` APIs covering named cutscene playback and mission-train spawning, movement, speed, stations, carriages, cleanup, and state.
- World date and stored-clock helpers, typed straight-road lookup results, and script roadblock management.
- Expression-aware in-game completion for built-ins, console commands, namespace names, nested attributes, indexed values, and typed function results such as `blips.waypoint().x`.
- A bounded completion popup navigated with Up/Down, accepted with Enter, and dismissed with Esc replaces completion text dumped into console history.
- Holding Up or Down now repeats completion-menu navigation after a normal keyboard delay.
- Tab now opens the completion popup even for a single partial match and, like Enter, accepts the highlighted suggestion when the popup is already open.
- Completion results now remain visible and update live during typing, paste, Backspace, and Delete, closing automatically only when no candidate remains.
- The console now provides automatic member suggestions after `.`, Ctrl+Space invocation, selected-item signature/type details, PageUp/PageDown navigation, paired brackets and quotes, Ctrl+Left/Right word movement, and Ctrl+L clearing.
- Completion entries now highlight on mouse hover, accept on click, and navigate with the wheel; the wheel also scrolls console history, and clicking an earlier `>>>` command recalls it for editing.
- Console history now eases smoothly between wheel targets using fractional row movement and a compact visual scrollbar instead of jumping three lines at once.
- Monospace text supports native Direct3D scissor rectangles so partially visible history rows animate cleanly at console boundaries without bleeding into the header or input bar.
- The history scrollbar supports thumb dragging and track clicks; output text supports cross-line mouse selection and Ctrl+C copying, while double-clicking `>>>` commands recalls them for editing.
- Console diagnostics now warn before assignments to read-only properties and mutations of returned `Vector3` snapshots that cannot propagate back to game entities, with a write-back example.
- Call signature help now tracks the active argument inside multi-parameter functions, shows its annotation/default and documentation, and lets Ctrl+Space complete unused named parameters.
- Python syntax highlighting now colors keywords, strings, numbers, comments, operators, built-ins, calls, and attributes in both the live editor and executed `>>>` history lines.
- The same semantic palette now covers returned values, wrapped history, completion names and type details, and call signatures while preserving dedicated diagnostic/status colors.
- Completion entries now use explicit kind colors for properties, methods, enums, classes, modules, strings, numbers, and other values; property annotations use concise names such as `PlayerCamera` instead of raw `<class 'module.Type'>` representations.
- The main console code/history surface is translucent, with `ConsoleBackgroundOpacity` expressed as `0.0`-`1.0`; the input strip remains slightly stronger for readability.
- A clickable console `SETTINGS` page now controls UI scale, opacity, history capacity, and automatic IntelliSense with immediate INI persistence, alongside a clickable header X close button.
- Common PyAndreas modules such as `blips`, `camera`, `game`, `trains`, and `cutscenes` are now directly available in the console namespace.
- Console output wrapping and caret-following horizontal input scrolling keep all text inside the panel.
- Completion popups reserve their screen area from console history rendering, preventing batched output text from painting over the suggestion box.
- The completion popup now spans most of the console width so long API names remain visible.

### Changed
- Plain `print(...)` output from user mods now appears as an in-game subtitle while remaining mirrored in `PyAndreas.log`.
- Console text now loads a real configurable TrueType monospace font file and renders through Direct3D instead of emulating fixed-width text with GTA's bitmap fonts.
- The native host was separated into focused host, event, menu, font, render, and hook translation units; `Main.cpp` now contains only plugin composition.
- Live world collections now retain their concrete member type through iteration, indexing, filtering, proximity searches, and nearest-entity queries.
- Script sessions, player vehicle relationships, vehicle occupants, model information, controller sticks, and menu callbacks now expose precise return and parameter types for editor completion.
- Generated SCM command stubs now recognize pickup, blip, checkpoint, fire, sphere, marker, particle, controller, weather, radio, checkpoint-style, corona, flare, and driving-style domains instead of presenting them as generic integers.
- Ped and player weapon facades now expose `WEAPON` enum values while continuing to accept raw integer ids.

### Fixed
- Member completion now reopens after Backspace/Delete repairs a temporary no-match fragment such as `player.pez` back to `player.pe`, without requiring the entire member name to be erased.
- `player.clothes.set_model(...)` now streams and validates ped models before `SET_PLAYER_MODEL`, preventing crashes caused by unloaded RenderWare clumps, and releases the streaming reference afterward.
- The developer console now renders in GTA's late draw stage above the HUD, and its independently drawn caret no longer makes the full input line flash.
- Opening GTA's front end now closes the developer console, restores controls immediately and repeats that restoration on the first gameplay tick instead of invisibly reopening the console.
- Held Backspace/Delete and cursor keys now repeat normally, and the TrueType caret advances over trailing whitespace by fixed font cells.
- Developer-console input capture now suppresses GTA keyboard, mouse, and controller actions—including camera-mode switching—while preserving raw input for console editing.
- Vehicle, ped, and object creation callbacks now wait until GTA has assigned a valid pool handle and model, and other lifecycle callbacks reject unusable wrappers, so entity properties no longer report constructor-time sentinel values such as `-1`.
- Freed GTA pool references are now rejected by entity wrappers, command packing, and the native pointer bridge instead of being passed to game functions as stale objects.

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
