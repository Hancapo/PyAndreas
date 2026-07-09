"""Generate pysa/opcodes.py from plugin-sdk's ScriptCommandNames.h (GTASA section).

Usage:  python tools/gen_opcodes.py [path-to-plugin-sdk]
"""
import re
import sys
from pathlib import Path

DEFAULT_SDK = r"C:\Users\vicho\Downloads\Compressed\plugin-sdk-master\plugin-sdk-master"

HEADER = '''"""GTA San Andreas SCM opcode database (generated - do not edit by hand).

Maps script command names to their opcode ids, extracted from plugin-sdk's
shared/extensions/scripting/ScriptCommandNames.h (GTASA section).

Regenerate with:  python tools/gen_opcodes.py
"""

OPCODES = {
'''


def main() -> None:
    sdk = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(DEFAULT_SDK)
    src = sdk / "shared" / "extensions" / "scripting" / "ScriptCommandNames.h"
    text = src.read_text(encoding="utf-8", errors="replace")

    # Isolate the GTASA section: from '#elif GTASA' to the next preprocessor branch.
    start = text.index("#elif GTASA")
    rest = text[start + 1:]
    m = re.search(r"^#(elif|else|endif)", rest, re.M)
    section = rest[:m.start()]

    entries = re.findall(r"^\s*([A-Z0-9_]+)\s*=\s*0x([0-9A-Fa-f]+)\s*,?", section, re.M)
    out_path = Path(__file__).resolve().parent.parent / "python" / "pysa" / "opcodes.py"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [HEADER]
    count = 0
    for name, hexval in entries:
        opcode = int(hexval, 16) - 0x10000  # SDK enum offsets ids by 0x10000
        if opcode < 0:
            continue
        lines.append(f"    {name!r}: 0x{opcode:04X},\n")
        count += 1
    lines.append("}\n")
    out_path.write_text("".join(lines), encoding="utf-8")
    print(f"Wrote {count} opcodes to {out_path}")


if __name__ == "__main__":
    main()
