"""Friendly slash commands for the built-in developer console.

Commands are intentionally a small convenience layer over the normal API.
Scripts can add their own commands with ``@pysa.console_command``.
"""
from __future__ import annotations

import inspect
import shlex
import types
from dataclasses import dataclass
from enum import Enum
from typing import (TYPE_CHECKING, Any, Callable, Iterable, Optional, TypeVar,
                    Union, get_args, get_origin, get_type_hints, overload)

if TYPE_CHECKING:
    from typing import ParamSpec
else:
    try:
        from typing import ParamSpec
    except ImportError:  # Python 3.8 runtime; annotations are postponed.
        ParamSpec = TypeVar


P = ParamSpec("P")
R = TypeVar("R")
_UNION_ORIGINS = ((Union, types.UnionType)
                  if hasattr(types, "UnionType") else (Union,))


def _without_leading_slash(value: str) -> str:
    return value[1:] if value.startswith("/") else value


class CommandError(ValueError):
    """A readable command invocation error."""


@dataclass(frozen=True)
class Command:
    name: str
    handler: Callable[..., Any]
    description: str
    usage: str
    aliases: tuple[str, ...]
    legacy: bool
    pass_context: bool
    completer: Optional[Callable[["CommandContext", int, str], list[str]]]


@dataclass(frozen=True)
class CommandCompletion:
    start: int
    end: int
    candidates: list[str]
    labels: list[str]
    details: list[str]


class CommandContext:
    """Console access and ownership for a slash-command invocation."""

    __slots__ = ("console", "_resources")

    def __init__(self, console: Any):
        self.console = console
        self._resources: list[tuple[Any, Callable[[], Any]]] = []

    def write(self, message: Any) -> None:
        self.console.write(message)

    def track(self, resource: Any,
              cleanup: Optional[Callable[[], Any]] = None) -> Any:
        if cleanup is None:
            for name in ("delete", "remove", "clear", "close", "stop"):
                candidate = getattr(resource, name, None)
                if callable(candidate):
                    cleanup = candidate
                    break
        if not callable(cleanup):
            raise TypeError("command resource needs a cleanup method")
        self._resources.append((resource, cleanup))
        return resource

    def cleanup(self) -> int:
        count = 0
        while self._resources:
            _, cleanup = self._resources.pop()
            try:
                cleanup()
                count += 1
            except Exception as exc:
                self.write(f"Cleanup warning: {exc}")
        return count


_commands: dict[str, Command] = {}
_aliases: dict[str, str] = {}
_builtins: set[str] = set()


def _normalize(name: str) -> str:
    name = _without_leading_slash(str(name).strip().lower())
    if (not name or
            (name != "?" and not name.replace("-", "_").isidentifier())):
        raise ValueError(f"invalid console command name {name!r}")
    return name


def _register(command: Command, *, builtin: bool = False) -> None:
    names = (command.name, *command.aliases)
    for name in names:
        owner = _aliases.get(name)
        if owner is not None and owner != command.name:
            raise ValueError(f"console command name /{name} is already used")
    previous = _commands.get(command.name)
    if previous is not None:
        for name in (previous.name, *previous.aliases):
            if _aliases.get(name) == command.name:
                _aliases.pop(name, None)
    _commands[command.name] = command
    for name in names:
        _aliases[name] = command.name
    if builtin:
        _builtins.add(command.name)


@overload
def console_command(handler: Callable[P, R], /
                    ) -> Callable[P, R]: ...


@overload
def console_command(name: Optional[str] = None, *,
                    aliases: Iterable[str] = (), description: str = "",
                    usage: str = ""
                    ) -> Callable[[Callable[P, R]], Callable[P, R]]: ...


def console_command(name: Optional[str] | Callable[..., Any] = None, *,
                    aliases: Iterable[str] = (), description: str = "",
                    usage: str = "") -> Any:
    """Register a slash command from an ordinary user script.

    The decorated function's annotations and defaults define argument
    conversion and help. Returning a value prints its ``repr`` in the console.
    """
    def decorate(handler: Callable[P, R]) -> Callable[P, R]:
        command_name = _normalize(name or handler.__name__)
        command_aliases = tuple(_normalize(value) for value in aliases)
        _register(Command(
            command_name, handler,
            description or (inspect.getdoc(handler) or "").split("\n", 1)[0],
            usage, command_aliases, False, False, None))
        return handler
    if callable(name):
        handler = name
        name = None
        return decorate(handler)
    return decorate


def command_names(*, aliases: bool = False) -> list[str]:
    """Return registered command names for help and tooling."""
    return sorted(_aliases if aliases else _commands)


def resolve(name: str) -> Optional[Command]:
    canonical = _aliases.get(_without_leading_slash(str(name).lower()))
    return _commands.get(canonical) if canonical else None


def _signature(command: Command) -> inspect.Signature:
    signature = inspect.signature(command.handler)
    if not command.pass_context:
        return signature
    parameters = list(signature.parameters.values())[1:]
    return signature.replace(parameters=parameters)


def _usage(command: Command) -> str:
    if command.usage:
        return f"/{command.name} {command.usage}".rstrip()
    parts = []
    for parameter in _signature(command).parameters.values():
        if parameter.kind == inspect.Parameter.VAR_POSITIONAL:
            parts.append(f"[{parameter.name} ...]")
        elif parameter.default is inspect.Parameter.empty:
            parts.append(f"<{parameter.name}>")
        else:
            parts.append(f"[{parameter.name}]")
    return " ".join((f"/{command.name}", *parts))


def command_help(command: Command) -> str:
    aliases = (f"  aliases: {', '.join('/' + value for value in command.aliases)}"
               if command.aliases else "")
    return f"{_usage(command)}  {command.description}{aliases}".rstrip()


def _convert(value: str, annotation: Any) -> Any:
    if annotation is inspect.Parameter.empty or annotation is str:
        return value
    origin = get_origin(annotation)
    if origin in _UNION_ORIGINS:
        options = [item for item in get_args(annotation) if item is not type(None)]
        if value.lower() in ("none", "null") and type(None) in get_args(annotation):
            return None
        errors = []
        for option in options:
            try:
                return _convert(value, option)
            except (TypeError, ValueError) as exc:
                errors.append(str(exc))
        raise ValueError(errors[-1] if errors else f"invalid value {value!r}")
    if annotation is bool:
        lowered = value.lower()
        if lowered in ("1", "true", "yes", "on", "enable", "enabled"):
            return True
        if lowered in ("0", "false", "no", "off", "disable", "disabled"):
            return False
        raise ValueError(f"expected on or off, got {value!r}")
    if annotation is int:
        return int(value, 0)
    if annotation is float:
        return float(value)
    if inspect.isclass(annotation) and issubclass(annotation, Enum):
        key = value.upper().replace("-", "_").replace(" ", "_")
        try:
            return annotation[key]
        except KeyError:
            try:
                return annotation(int(value, 0))
            except (ValueError, TypeError):
                raise ValueError(
                    f"unknown {annotation.__name__} value {value!r}") from None
    return annotation(value)


def _invoke(command: Command, context: CommandContext,
            arguments: list[str]) -> Any:
    signature = _signature(command)
    parameters = list(signature.parameters.values())
    try:
        hints = get_type_hints(command.handler)
    except Exception:
        hints = {}
    converted = []
    index = 0
    for parameter in parameters:
        if parameter.kind == inspect.Parameter.VAR_POSITIONAL:
            annotation = hints.get(parameter.name, parameter.annotation)
            converted.extend(_convert(value, annotation)
                             for value in arguments[index:])
            index = len(arguments)
            break
        if index >= len(arguments):
            if parameter.default is inspect.Parameter.empty:
                raise CommandError(f"Missing {parameter.name}. Usage: {_usage(command)}")
            continue
        annotation = hints.get(parameter.name, parameter.annotation)
        try:
            converted.append(_convert(arguments[index], annotation))
        except (TypeError, ValueError) as exc:
            raise CommandError(
                f"Invalid {parameter.name}: {exc}. Usage: {_usage(command)}") from None
        index += 1
    if index < len(arguments):
        raise CommandError(f"Too many arguments. Usage: {_usage(command)}")
    call_arguments = ([context] if command.pass_context else []) + converted
    return command.handler(*call_arguments)


def execute(context: CommandContext, source: str, *, slash: bool) -> Any:
    try:
        parts = shlex.split(source, posix=True)
    except ValueError as exc:
        raise CommandError(str(exc)) from None
    if not parts:
        return None
    command = resolve(parts[0])
    if command is None:
        if slash:
            suggestions = _nearest(parts[0])
            hint = f" Did you mean {' or '.join('/' + x for x in suggestions)}?" if suggestions else ""
            raise CommandError(f"Unknown command /{parts[0]}.{hint}")
        return NotImplemented
    if not slash and not command.legacy:
        return NotImplemented
    return _invoke(command, context, parts[1:])


def _nearest(name: str) -> list[str]:
    import difflib
    return difflib.get_close_matches(
        _without_leading_slash(str(name).lower()), command_names(aliases=True),
        n=2, cutoff=0.55)


def _enum_suggestions(annotation: Any) -> list[str]:
    origin = get_origin(annotation)
    if origin in _UNION_ORIGINS:
        for option in get_args(annotation):
            values = _enum_suggestions(option)
            if values:
                return values
    if annotation is bool:
        return ["on", "off"]
    if inspect.isclass(annotation) and issubclass(annotation, Enum):
        return [item.name.lower() for item in annotation]
    return []


def complete(context: CommandContext, source: str,
             cursor: int) -> Optional[CommandCompletion]:
    before = source[:cursor]
    if not before.startswith("/"):
        return None
    body = before[1:]
    if not body or not any(char.isspace() for char in body):
        prefix = body.lower()
        names = [name for name in command_names()
                 if name.startswith(prefix)]
        return CommandCompletion(
            0, cursor, [f"/{name} " for name in names],
            [f"/{name}" for name in names],
            [command_help(_commands[name]) for name in names]) if names else None

    command_name = body.split(None, 1)[0]
    command = resolve(command_name)
    if command is None:
        return None
    token_match = __import__("re").search(r"([^\s]*)$", before)
    token_start = token_match.start(1) if token_match else cursor
    prefix = before[token_start:cursor]
    completed_text = before[len(command_name) + 2:token_start]
    try:
        prior = shlex.split(completed_text, posix=True) if completed_text.strip() else []
    except ValueError:
        prior = completed_text.split()
    argument_index = len(prior)
    suggestions: list[str] = []
    if command.completer is not None:
        suggestions = command.completer(context, argument_index, prefix)
    else:
        parameters = list(_signature(command).parameters.values())
        if parameters:
            parameter = parameters[min(argument_index, len(parameters) - 1)]
            try:
                hints = get_type_hints(command.handler)
            except Exception:
                hints = {}
            suggestions = _enum_suggestions(
                hints.get(parameter.name, parameter.annotation))
    suggestions = [value for value in suggestions
                   if value.lower().startswith(prefix.lower())]
    if not suggestions:
        return None
    detail = command_help(command)
    return CommandCompletion(token_start, cursor, suggestions, suggestions,
                             [detail for _ in suggestions])


def call_hint(source: str, cursor: int
              ) -> Optional[tuple[Command, inspect.Signature, int]]:
    """Return command signature metadata for the live hint panel."""
    before = source[:cursor]
    if not before.startswith("/") or " " not in before:
        return None
    try:
        parts = shlex.split(before[1:], posix=True)
    except ValueError:
        parts = before[1:].split()
    if not parts:
        return None
    command = resolve(parts[0])
    if command is None:
        return None
    parameters = list(_signature(command).parameters.values())
    active = max(0, len(parts) - 2)
    if before[-1:].isspace():
        active += 1
    if parameters:
        active = min(active, len(parameters) - 1)
    else:
        active = 0
    return command, _signature(command), active


def can_execute_without_arguments(source: str) -> bool:
    """Whether an exact command name is complete without opening arguments."""
    if not source.startswith("/") or any(char.isspace() for char in source):
        return False
    command = resolve(source[1:])
    if command is None:
        return False
    return all(parameter.default is not inspect.Parameter.empty or
               parameter.kind in (inspect.Parameter.VAR_POSITIONAL,
                                  inspect.Parameter.VAR_KEYWORD)
               for parameter in _signature(command).parameters.values())


def _builtin(name: str, *, aliases=(), description: str = "",
             usage: str = "", legacy: bool = False, completer=None):
    def decorate(handler):
        command = Command(
            _normalize(name), handler, description, usage,
            tuple(_normalize(value) for value in aliases), legacy, True,
            completer)
        _register(command, builtin=True)
        return handler
    return decorate


def _models(enum_type) -> list[str]:
    return [item.name.lower() for item in enum_type]


def _vehicle_complete(_context, index: int, _prefix: str) -> list[str]:
    if index:
        return []
    from .models import VEHICLES
    return sorted(VEHICLES)


def _ped_complete(_context, index: int, _prefix: str) -> list[str]:
    if index:
        return []
    from .ped_models import PED
    return _models(PED)


def _weapon_complete(_context, index: int, _prefix: str) -> list[str]:
    if index:
        return []
    from .models import WEAPON
    return _models(WEAPON)


def _weather_complete(_context, index: int, _prefix: str) -> list[str]:
    if index:
        return []
    from .world import WEATHER
    return _models(WEATHER)


@_builtin("help", aliases=("?",), description="List commands or describe one.",
          usage="[command]", legacy=True,
          completer=lambda _c, _i, _p: command_names())
def _help(context: CommandContext, name: str = "") -> None:
    if name:
        command = resolve(name)
        if command is None:
            raise CommandError(f"Unknown command /{name}")
        context.write(command_help(command))
        return
    context.write("Slash commands:")
    for command in sorted(_commands.values(), key=lambda item: item.name):
        context.write(f"  /{command.name:<10} {command.description}")
    context.write("Use /help <command> for usage; Python expressions still work directly.")


@_builtin("clear", description="Clear console output.", legacy=True)
def _clear(context: CommandContext) -> None:
    context.console.clear()


@_builtin("close", description="Close the console.", legacy=True)
def _close(context: CommandContext) -> None:
    context.console.close()


@_builtin("reload", aliases=("restart",), description="Reload user scripts.",
          legacy=True)
def _reload(context: CommandContext) -> None:
    from . import _runtime
    context.write("Script reload queued...")
    _runtime.request_reload()


@_builtin("scripts", description="List active user scripts.", legacy=True)
def _scripts(context: CommandContext) -> None:
    from . import _runtime
    if not _runtime._scripts:
        context.write("No active user scripts")
    for module, path in _runtime._scripts:
        import os
        context.write(f"{module}: {os.path.basename(path)}")


@_builtin("history", description="Show console command history.", legacy=True)
def _history(context: CommandContext) -> None:
    for index, source in enumerate(context.console.history, 1):
        context.write(f"{index:>3}: {source}")


@_builtin("tests", aliases=("test",), description="Run registered in-game tests.",
          usage="[filter]", legacy=True)
def _tests(context: CommandContext, pattern: str = "") -> None:
    from . import testing
    context.console.last_test_run = testing.run_tests(
        pattern or None, context.write)


@_builtin("status", description="Show the current test status.", legacy=True)
def _status(context: CommandContext) -> None:
    run = context.console.last_test_run
    if run is None:
        context.write("No test run started")
    elif run.running:
        context.write(f"Tests running: {run.passed} passed, {run.failed} failed")
    else:
        context.write(f"Tests finished: {run.passed} passed, {run.failed} failed")


@_builtin("settings", description="Open console settings.")
def _settings(context: CommandContext) -> None:
    context.console.settings_visible = True


@_builtin("where", aliases=("pos",), description="Show the player's position.")
def _where(context: CommandContext) -> None:
    from .player import player
    pos = player.pos
    context.write(f"Position: {pos.x:.3f}, {pos.y:.3f}, {pos.z:.3f}")


@_builtin("copypos", description="Copy the player's position to the clipboard.")
def _copypos(context: CommandContext) -> None:
    from . import _mock as fallback
    from .player import player
    try:
        import _pysa as native
    except ImportError:
        native = fallback
    pos = player.pos
    text = f"({pos.x:.3f}, {pos.y:.3f}, {pos.z:.3f})"
    native.clipboard_set(text)
    context.write(f"Copied {text}")


@_builtin("heal", description="Restore player health and armour.")
def _heal(context: CommandContext) -> None:
    from .player import player
    player.heal(True)
    context.write("Player healed")


@_builtin("armour", description="Set player armour.", usage="[amount]")
def _armour(context: CommandContext, amount: int = 100) -> None:
    from .player import player
    player.armour = amount
    context.write(f"Armour set to {amount}")


@_builtin("wanted", description="Set the wanted level.", usage="<level>")
def _wanted(context: CommandContext, level: int) -> None:
    from .player import player
    player.wanted_level = max(0, min(6, level))
    context.write(f"Wanted level set to {player.wanted_level}")


@_builtin("vehicle", aliases=("car",), description="Spawn a vehicle nearby.",
          usage="<model>", completer=_vehicle_complete)
def _vehicle(context: CommandContext, model: str) -> None:
    from .entities import Vehicle
    vehicle = context.track(Vehicle.spawn(model))
    context.write(f"Spawned {model} (handle {vehicle.handle})")


@_builtin("skin", description="Change the player model.", usage="<model>",
          completer=_ped_complete)
def _skin(context: CommandContext, model: str) -> None:
    from .ped_models import PED
    from .player import player
    try:
        value = PED[model.upper()]
    except KeyError:
        try:
            value = int(model, 0)
        except ValueError:
            raise CommandError(f"Unknown ped model {model!r}") from None
    player.clothes.set_model(value)
    context.write(f"Player model set to {value.name if isinstance(value, PED) else value}")


@_builtin("weapon", aliases=("gun",), description="Give and equip a weapon.",
          usage="<weapon> [ammo]", completer=_weapon_complete)
def _weapon(context: CommandContext, weapon: str, ammo: int = 500) -> None:
    from .models import WEAPON
    from .player import player
    key = weapon.upper().replace("-", "_")
    try:
        value = WEAPON[key]
    except KeyError:
        try:
            value = WEAPON(int(weapon, 0))
        except (ValueError, TypeError):
            raise CommandError(f"Unknown weapon {weapon!r}") from None
    player.weapons.give(value, ammo, equip=True)
    context.write(f"Gave {value.name} with {ammo} ammo")


@_builtin("tp", aliases=("teleport",), description="Teleport to coordinates or the map waypoint.",
          usage="<waypoint | x y z>",
          completer=lambda _c, i, _p: ["waypoint"] if i == 0 else [])
def _tp(context: CommandContext, *destination: str) -> None:
    from . import blips
    from .enums import AREA
    from .player import player
    if len(destination) == 1 and destination[0].lower() == "waypoint":
        pos = blips.waypoint()
        if pos is None:
            raise CommandError("No map waypoint is set")
        area = AREA.OUTSIDE
    elif len(destination) == 3:
        try:
            pos = tuple(float(value) for value in destination)
        except ValueError:
            raise CommandError("Coordinates must be numbers") from None
        area = None
    else:
        raise CommandError("Usage: /tp <waypoint | x y z>")
    player.location.teleport(pos, area=area)
    context.write(f"Teleported to {player.pos}")


@_builtin("time", description="Set the game clock.", usage="<HH:MM>")
def _time(context: CommandContext, value: str) -> None:
    from . import world
    try:
        hours, minutes = (int(part) for part in value.split(":", 1))
    except (ValueError, TypeError):
        raise CommandError("Time must use HH:MM") from None
    if not 0 <= hours <= 23 or not 0 <= minutes <= 59:
        raise CommandError("Time must be between 00:00 and 23:59")
    world.set_time(hours, minutes)
    context.write(f"Time set to {hours:02d}:{minutes:02d}")


@_builtin("weather", description="Force a weather type.", usage="<weather>",
          completer=_weather_complete)
def _weather(context: CommandContext, value: str) -> None:
    from . import world
    key = value.upper().replace("-", "_")
    try:
        weather = world.WEATHER[key]
    except KeyError:
        try:
            weather = world.WEATHER(int(value, 0))
        except (ValueError, TypeError):
            raise CommandError(f"Unknown weather {value!r}") from None
    world.force_weather(weather)
    context.write(f"Weather set to {weather.name}")


@_builtin("repair", aliases=("fixcar",), description="Repair the current vehicle.")
def _repair(context: CommandContext) -> None:
    from .player import player
    vehicle = player.vehicle
    if vehicle is None:
        raise CommandError("The player is not in a vehicle")
    vehicle.fix()
    context.write("Vehicle repaired")


@_builtin("launch", description="Launch the player upward.", usage="[speed]")
def _launch(context: CommandContext, speed: float = 1.5) -> None:
    from .player import player
    velocity = player.ped.velocity
    player.ped.velocity = (velocity.x, velocity.y, speed)
    context.write(f"Launched player at {speed:.2f}")


@_builtin("explode", aliases=("boom",), description="Explode the current vehicle.")
def _explode(context: CommandContext) -> None:
    from .player import player
    vehicle = player.vehicle
    if vehicle is None:
        raise CommandError("The player is not in a vehicle")
    vehicle.explode()
    context.write("Boom")


@_builtin("gravity", description="Set gravity in metres per second squared.",
          usage="<m/s^2>")
def _gravity(context: CommandContext, value: float) -> None:
    from . import world
    internal = value * (world.DEFAULT_GRAVITY / 9.81)
    world.set_gravity(internal)
    context.write(
        f"Gravity set to {value:g} m/s^2 (game value {internal:.6f})")


@_builtin("cleanup", description="Delete resources spawned by console commands.")
def _cleanup(context: CommandContext) -> None:
    context.write(f"Cleaned up {context.cleanup()} resource(s)")


def _checkpoint() -> tuple[dict[str, Command], dict[str, str]]:
    return dict(_commands), dict(_aliases)


def _rollback(checkpoint: tuple[dict[str, Command], dict[str, str]]) -> None:
    commands, aliases = checkpoint
    _commands.clear()
    _commands.update(commands)
    _aliases.clear()
    _aliases.update(aliases)


def _clear_user_commands() -> None:
    for name in list(_commands):
        if name not in _builtins:
            _commands.pop(name, None)
    _aliases.clear()
    for command in _commands.values():
        for name in (command.name, *command.aliases):
            _aliases[name] = command.name
