"""Generate pysa/offsets.py from plugin-sdk's VALIDATE_OFFSET(...) macros.

plugin-sdk annotates every mapped game-class field with a hand-verified
    VALIDATE_OFFSET(CPed, m_fHealth, 0x540);
line. We harvest all of them (4000+ across ~380 classes) plus a best-effort
read of each field's C++ type, and emit a database Python can use for typed
struct access off any entity address.

Usage:  python tools/gen_offsets.py [path-to-plugin-sdk]
"""
import re
import sys
from pathlib import Path

DEFAULT_SDK = r"C:\Users\vicho\Downloads\Compressed\plugin-sdk-master\plugin-sdk-master"

VALIDATE = re.compile(r"VALIDATE_OFFSET\(\s*([A-Za-z_]\w*)\s*,\s*([A-Za-z_]\w*)\s*,\s*(0x[0-9A-Fa-f]+|\d+)\s*\)")

# member declaration: <type...> name ([array])? (: bits)? ;
DECL = re.compile(r"^\s*([A-Za-z_][\w:<>,\s\*&]*?)\s+([A-Za-z_]\w*)\s*(\[[^\]]*\])?\s*(:\s*\d+)?\s*;")


def type_kind(ctype: str, is_array: bool, is_bitfield: bool):
    """Map a C++ type string to a read kind, or None if we shouldn't guess."""
    if is_bitfield or is_array:
        return None  # flags/inline arrays: let the caller read raw
    t = ctype.replace("const", "").strip()
    if "*" in t:
        return "ptr"
    t = re.sub(r"\s+", " ", t).strip()
    table = {
        "float": "f32", "double": "f64",
        "bool": "u8",
        "char": "i8", "signed char": "i8", "int8_t": "i8",
        "unsigned char": "u8", "uint8_t": "u8", "BYTE": "u8", "byte": "u8",
        "short": "i16", "signed short": "i16", "int16_t": "i16",
        "unsigned short": "u16", "uint16_t": "u16", "WORD": "u16",
        "int": "i32", "signed int": "i32", "long": "i32", "int32_t": "i32",
        "unsigned": "u32", "unsigned int": "u32", "uint32_t": "u32",
        "unsigned long": "u32", "DWORD": "u32", "uint": "u32",
    }
    return table.get(t)


def main() -> None:
    sdk = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(DEFAULT_SDK)
    game = sdk / "plugin_sa" / "game_sa"
    classes: dict[str, dict[str, tuple]] = {}

    for header in game.rglob("*.h"):
        text = header.read_text(encoding="utf-8", errors="replace")

        # member name -> type kind, within this file (good enough: names are
        # unique per header in practice for the validated fields)
        member_types: dict[str, str] = {}
        for line in text.splitlines():
            m = DECL.match(line)
            if not m:
                continue
            ctype, name, arr, bits = m.groups()
            if ctype.strip() in ("return", "case", "else"):
                continue
            kind = type_kind(ctype, bool(arr), bool(bits))
            if kind:
                member_types.setdefault(name, kind)

        for cls, member, off in VALIDATE.findall(text):
            classes.setdefault(cls, {})[member] = (
                int(off, 16) if off.lower().startswith("0x") else int(off),
                member_types.get(member),
            )

    out = Path(__file__).resolve().parent.parent / "python" / "pysa" / "offsets.py"
    total = sum(len(v) for v in classes.values())
    with out.open("w", encoding="utf-8") as f:
        f.write('"""Game struct field offsets (generated - do not edit).\n\n'
                "Harvested from plugin-sdk VALIDATE_OFFSET(...) macros.\n"
                "OFFSETS[class][member] = (byte_offset, kind) where kind is one of\n"
                "'i8','u8','i16','u16','i32','u32','f32','f64','ptr' or None (raw).\n\n"
                f"{total} fields across {len(classes)} classes.\n"
                "Regenerate with: python tools/gen_offsets.py\n"
                '"""\n\n')
        f.write("OFFSETS = {\n")
        for cls in sorted(classes):
            fields = classes[cls]
            f.write(f" {cls!r}: {{\n")
            for member in sorted(fields, key=lambda m: fields[m][0]):
                off, kind = fields[member]
                f.write(f"  {member!r}: (0x{off:X}, {kind!r}),\n")
            f.write(" },\n")
        f.write("}\n")
    print(f"Wrote {total} offsets across {len(classes)} classes to {out}")


if __name__ == "__main__":
    main()
