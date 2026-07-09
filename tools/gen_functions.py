"""Generate pysa/functions.py - a catalog of named game functions.

plugin-sdk annotates every reversed method with a comment carrying its
convention, full typed+named signature, and address:

    // Converted from thiscall void CVehicle::InflictDamage(CEntity *damager,
    //   eWeaponType weapon,float intensity,CVector coords) 0x6D7C90

We harvest those into a catalog so hooks can target functions by name and
receive named, typed arguments instead of raw stack offsets.

Usage:  python tools/gen_functions.py [path-to-plugin-sdk]
"""
import re
import sys
from pathlib import Path

DEFAULT_SDK = r"C:\Users\vicho\Downloads\Compressed\plugin-sdk-master\plugin-sdk-master"

LINE = re.compile(
    r"//\s*Converted from\s+"
    r"(?:(thiscall|cdecl|stdcall)\s+)?"     # 1: convention hint (comment)
    r"(.+?)\s+"                              # 2: return type
    r"([A-Za-z_]\w*)::(~?[A-Za-z_]\w*)"      # 3: class  4: method
    r"\((.*)\)\s*"                           # 5: params
    r"(0x[0-9A-Fa-f]+)")                     # 6: address (function body)

# The impl cast right below the comment is the authoritative convention:
#   ((void (__thiscall *)(CVehicle*, ...))0x6D7C90)(this, ...)
CAST = re.compile(r"\(__(thiscall|cdecl|stdcall)\s*\*\)")

# by-value struct parameter sizes in 4-byte stack slots
STRUCT_SLOTS = {
    "CVector": 3, "CVector2D": 2, "CRect": 4, "CRGBA": 1, "RwRGBA": 1,
    "CMatrix": 16,
}


def split_params(params: str):
    """Split a parameter list on top-level commas."""
    params = params.strip()
    if not params or params == "void":
        return []
    out, depth, cur = [], 0, ""
    for ch in params:
        if ch in "<([":
            depth += 1
        elif ch in ">)]":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    return out


def parse_param(p: str):
    """('CEntity *damager') -> (name, type_string). None if unnamed."""
    p = p.strip()
    m = re.match(r"^(.*?)([A-Za-z_]\w*)\s*(\[\s*\d*\s*\])?$", p)
    if not m:
        return None
    type_part, name, arr = m.groups()
    type_part = type_part.strip()
    if not type_part:  # a lone identifier is a type with no name (e.g. 'void')
        return None
    ptype = type_part.replace(" ", "")
    if arr:
        ptype += "*"
    return name, ptype


def base_type(ptype: str) -> str:
    return ptype.replace("const", "").replace("*", "").replace("&", "").strip()


def main() -> None:
    sdk = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(DEFAULT_SDK)
    game = sdk / "plugin_sa" / "game_sa"

    catalog = {}
    seen = set()
    for cpp in game.rglob("*.cpp"):
        lines = cpp.read_text(encoding="utf-8", errors="replace").splitlines()
        for i, line in enumerate(lines):
            m = LINE.search(line)
            if not m:
                continue
            conv, ret, cls, method, params, addr = m.groups()
            if method.startswith("~") or method == cls or "operator" in method:
                continue  # skip dtors, ctors, operators
            key = f"{cls}::{method}"
            if key in seen:
                continue  # keep first of any overloads
            seen.add(key)

            # Prefer the impl cast's convention (authoritative); the comment
            # keyword is sometimes wrong (e.g. virtual methods labelled cdecl).
            cast_conv = None
            for look in lines[i + 1:i + 5]:
                cm = CAST.search(look)
                if cm:
                    cast_conv = cm.group(1)
                    break
            conv = cast_conv or conv or "cdecl"

            fields = []
            slot = 0
            ok = True
            for raw in split_params(params):
                parsed = parse_param(raw)
                if parsed is None:
                    ok = False
                    break
                name, ptype = parsed
                bt = base_type(ptype)
                is_ptr = "*" in ptype
                is_float = (bt == "float" and not is_ptr)
                width = 1 if is_ptr else STRUCT_SLOTS.get(bt, 1)
                wrap = None
                if is_ptr:
                    wrap = {"CPed": "ped", "CPlayerPed": "ped",
                            "CVehicle": "vehicle", "CAutomobile": "vehicle",
                            "CObject": "object"}.get(bt)
                fields.append((name, slot, is_float, wrap))
                slot += width
            if not ok:
                continue

            catalog[key] = (int(addr, 16), conv, base_type(ret), cls, slot, fields)

    out = Path(__file__).resolve().parent.parent / "python" / "pysa" / "functions.py"
    with out.open("w", encoding="utf-8") as f:
        f.write('"""Named game-function catalog (generated - do not edit).\n\n'
                "Harvested from plugin-sdk method address comments.\n"
                "FUNCTIONS[name] = (address, convention, return_type, owner_class,\n"
                "                   arg_slots, [(arg_name, slot, is_float, wrap), ...])\n"
                "wrap is 'ped'/'vehicle'/'object' for entity-pointer args, else None.\n\n"
                f"{len(catalog)} functions.\n"
                "Regenerate with: python tools/gen_functions.py\n"
                '"""\n\n')
        f.write("FUNCTIONS = {\n")
        for key in sorted(catalog):
            addr, conv, ret, cls, slots, fields = catalog[key]
            f.write(f" {key!r}: (0x{addr:06X}, {conv!r}, {ret!r}, {cls!r}, {slots}, {fields!r}),\n")
        f.write("}\n")
    print(f"Wrote {len(catalog)} functions to {out}")


if __name__ == "__main__":
    main()
