"""Calling SCM script commands (opcodes) from Python.

Every vanilla script command is callable through `cmd` (or `call`) with a
known signature - no output markers, no int/float footguns:

    from pysa import cmd

    x, y, z = cmd.GET_CAR_COORDINATES(car)        # outputs just come back
    car = cmd.CREATE_CAR(411, 2488, -1666, 13)    # ints ok where floats expected
    if cmd.IS_CHAR_IN_ANY_CAR(ped):               # conditions return bool
        driver = cmd.GET_DRIVER_OF_CAR(car)       # entity outputs -> Ped/Vehicle

    help(cmd.CREATE_CAR)                          # signature + description
    pysa.find_commands('blip')                    # discover commands

Return value rules:
    condition, no outputs   -> bool
    outputs, no condition   -> single value, or tuple of values
    condition + outputs     -> outputs if the condition passed, else None
    neither                 -> None

Commands unknown to the signature database (custom/raw opcodes) can still be
called with explicit Out markers:

    ok = call(0x0123, arg, Out.FLOAT)
"""
from __future__ import annotations

try:
    import _pysa
except ImportError:  # outside the game (tests, editors)
    from . import _mock as _pysa

from .opcodes import OPCODES
from .signatures import FLAG_COND, PARAM_TYPES, SIGS


_FRIENDLY_PARAM_TYPES = {
    "bool": "bool", "Char": "Ped", "Car": "Vehicle", "Heli": "Vehicle",
    "Plane": "Vehicle", "Boat": "Vehicle", "Train": "Vehicle",
    "Trailer": "Vehicle", "Object": "GameObject", "WeaponType": "WEAPON",
    "model_vehicle": "VEHICLE", "model_char": "PED", "PedType": "PED_TYPE",
    "MoveState": "MOVE_STATE", "CarDoor": "VEHICLE_DOOR",
    "CarMission": "CAR_MISSION", "CameraMode": "CAMERA_MODE",
    "CarLock": "DOOR_LOCK", "EntityStatus": "ENTITY_STATUS",
    "FightStyle": "FIGHT_STYLE", "PedBone": "PED_BONE",
    "PedBoneId": "PED_BONE", "GangType": "GANG", "RadarSprite": "BLIP_SPRITE",
    "WheelId": "VEHICLE_WHEEL",
    "ExplosionType": "world.EXPLOSION",
    "PickupType": "PICKUP_TYPE",
    "MissionAudioSlot": "MISSION_AUDIO_SLOT",
}


class _OutMarker:
    __slots__ = ("kind", "_name")

    def __init__(self, kind: str, name: str):
        self.kind = kind
        self._name = name

    def __repr__(self):
        return f"Out.{self._name}"


class Out:
    """Explicit output markers - only needed for commands not in pysa.signatures."""

    INT = _OutMarker("I", "INT")
    FLOAT = _OutMarker("F", "FLOAT")
    STR = _OutMarker("S", "STR")


class _EndMarker:
    def __repr__(self):
        return "End"


#: Variadic-arguments terminator (only needed in manual Out-marker calls).
End = _EndMarker()

#: Bitwise-OR this into a raw opcode to invert a condition (SCM NOT flag).
NOT = 0x8000


def signature(name: str) -> str:
    """Human-readable signature, e.g. 'GET_CAR_COORDINATES(self) -> x, y, z'."""
    sig = SIGS.get(name.upper())
    if sig is None:
        return f"{name.upper()}(...) [no signature - use Out markers]"
    _, inspec, outspec, flags, innames, outnames, _ = sig
    names = innames.split(",") if innames else []
    source_types = PARAM_TYPES.get(name.upper(), ())
    typed_params = []
    for index, param in enumerate(names):
        source = source_types[index] if index < len(source_types) else ""
        friendly = _FRIENDLY_PARAM_TYPES.get(source)
        typed_params.append(f"{param}: {friendly}" if friendly else param)
    params = ", ".join(typed_params)
    if inspec.endswith("*"):
        params = (params + ", *args") if params else "*args"
    out = outnames.replace(",", ", ") if outnames else ("bool" if flags & FLAG_COND else "None")
    if outnames and flags & FLAG_COND:
        out += " | None"
    return f"{name.upper()}({params}) -> {out}"


def doc(name: str) -> str:
    """Signature plus description for a command (also try help(cmd.NAME))."""
    sig = SIGS.get(name.upper())
    line = signature(name)
    if sig and sig[6]:
        line += "\n" + sig[6]
    opcode = sig[0] if sig else OPCODES.get(name.upper())
    if opcode is not None:
        line += f"\n(opcode 0x{opcode:04X})"
    return line


def find_commands(pattern: str, limit: int = 40) -> list:
    """Search command names (and descriptions) - returns signature strings."""
    p = pattern.upper()
    hits = [n for n in SIGS if p in n]
    if len(hits) < limit:
        hits += [n for n in SIGS
                 if n not in hits and p.lower() in SIGS[n][6].lower()]
    return [signature(n) for n in hits[:limit]]


# ---------------------------------------------------------------------------
# Argument packing
# ---------------------------------------------------------------------------

def _as_int(value, name: str, cmd_name: str) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    handle = getattr(value, "_handle", None)
    if handle is not None:
        return int(handle)
    raise TypeError(f"{cmd_name}: parameter '{name}' expects an int/handle, "
                    f"got {type(value).__name__}")


def _as_float(value, name: str, cmd_name: str) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    raise TypeError(f"{cmd_name}: parameter '{name}' expects a number, "
                    f"got {type(value).__name__}")


def _pack_auto(value):
    """Type an extra (variadic) argument from its Python type."""
    if isinstance(value, bool):
        return "i", int(value)
    if isinstance(value, int):
        return "i", value
    if isinstance(value, float):
        return "f", value
    if isinstance(value, str):
        return "s", value
    handle = getattr(value, "_handle", None)
    if handle is not None:
        return "i", int(handle)
    raise TypeError(f"cannot pass {type(value).__name__} to a script command")


def _wrap_out(kind: str, raw):
    if kind in "IFS":
        return raw
    if raw == -1:
        return None
    from . import entities  # deferred: entities imports this module

    cls = {"P": entities.Ped, "V": entities.Vehicle, "O": entities.GameObject}[kind]
    return cls(raw)


def _invoke(name: str, sig, args):
    opcode, inspec, outspec, flags, innames, outnames, _ = sig
    variadic = inspec.endswith("*")
    base = inspec[:-1] if variadic else inspec
    if len(args) < len(base) or (not variadic and len(args) > len(base)):
        raise TypeError(f"bad argument count for {signature(name)}: got {len(args)}")

    names = innames.split(",") if innames else []
    spec = []
    values = []
    for i, k in enumerate(base):
        pname = names[i] if i < len(names) else f"arg{i}"
        a = args[i]
        if k == "f":
            values.append(_as_float(a, pname, name))
        elif k == "s":
            values.append(str(a))
        else:
            values.append(_as_int(a, pname, name))
        spec.append(k)
    if variadic:
        for a in args[len(base):]:
            k, v = _pack_auto(a)
            spec.append(k)
            values.append(v)
        spec.append("e")
    for k in outspec:
        spec.append("I" if k in "PVO" else k)

    cond, raw_outs = _pysa.call(opcode, "".join(spec), *values)

    if not outspec:
        return cond if flags & FLAG_COND else None
    if flags & FLAG_COND and not cond:
        return None
    outs = tuple(_wrap_out(k, raw) for k, raw in zip(outspec, raw_outs))
    return outs[0] if len(outs) == 1 else outs


# ---------------------------------------------------------------------------
# Manual path (raw opcodes / commands without signatures)
# ---------------------------------------------------------------------------

def _call_manual(opcode: int, args):
    spec = []
    values = []
    for a in args:
        if isinstance(a, _OutMarker):
            spec.append(a.kind)
        elif a is End:
            spec.append("e")
        else:
            k, v = _pack_auto(a)
            spec.append(k)
            values.append(v)
    return _pysa.call(opcode, "".join(spec), *values)


def call_ex(command, *args):
    """Low-level: returns (condition_flag, outputs_tuple), no signature smarts.

    Inputs are typed from their Python type (float vs int matters!) and
    outputs need Out markers. Prefer `cmd` / `call` unless you know why not.
    """
    if isinstance(command, str):
        name = command.upper()
        opcode = SIGS[name][0] if name in SIGS else OPCODES.get(name)
        if opcode is None:
            raise ValueError(f"unknown script command {command!r}")
    else:
        opcode = int(command)
    return _call_manual(opcode, args)


def call(command, *args):
    """Run a script command by name or opcode.

    Names with a known signature behave like `cmd.NAME(*args)` (no Out
    markers, coercion, wrapped outputs). Raw opcodes - or any call containing
    an explicit Out marker - use the manual typed path.
    """
    manual = any(isinstance(a, _OutMarker) or a is End for a in args)
    if isinstance(command, str) and not manual:
        name = command.upper()
        sig = SIGS.get(name)
        if sig is not None:
            return _invoke(name, sig, args)
        if name in OPCODES:
            raise ValueError(
                f"{name} has no signature (unsupported by vanilla SA or "
                f"control-flow only); call it with explicit Out markers if "
                f"you know its parameters")
        raise ValueError(f"unknown script command {command!r}")

    cond, outs = call_ex(command, *args)
    if not outs:
        return cond
    return outs[0] if len(outs) == 1 else outs


class _CommandNamespace:
    """cmd.NAME(...) for every script command. help(cmd.NAME) shows the docs."""

    def __getattr__(self, name: str):
        upper = name.upper()
        sig = SIGS.get(upper)
        if sig is None and upper not in OPCODES:
            raise AttributeError(f"unknown script command {name!r} "
                                 f"(try pysa.find_commands({name.lower()!r}))")

        def invoke(*args, _n=upper):
            return call(_n, *args)

        invoke.__name__ = name.lower()
        invoke.__qualname__ = f"cmd.{upper}"
        invoke.__doc__ = doc(upper)
        setattr(self, name, invoke)  # cache
        return invoke

    def __dir__(self):
        return list(SIGS)


cmd = _CommandNamespace()

#: Call a raw game function: call_func(addr, conv='c'|'s'|'t', ret='i'|'f'|'v', spec, *args)
call_func = _pysa.call_func
