"""Generate pysa/ped_models.py from plugin-sdk's ePedModel.h.

Usage:  python tools/gen_ped_models.py [path-to-plugin-sdk]
"""
import re
import sys
from pathlib import Path


DEFAULT_SDK = r"C:\Users\vicho\Downloads\Compressed\plugin-sdk-master\plugin-sdk-master"
MEMBER = re.compile(r"^\s*MODEL_([A-Z0-9_]+)\s*(?:=\s*(-?(?:0x)?[0-9A-Fa-f]+))?\s*,", re.M)


def main() -> None:
    sdk = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(DEFAULT_SDK)
    source = sdk / "plugin_sa" / "game_sa" / "enums" / "ePedModel.h"
    text = source.read_text(encoding="utf-8", errors="replace")

    value = -1
    members = []
    for name, explicit in MEMBER.findall(text):
        value = int(explicit, 0) if explicit else value + 1
        members.append((name, value))

    target = Path(__file__).resolve().parent.parent / "python" / "pysa" / "ped_models.py"
    lines = [
        '"""Ped model ids generated from plugin-sdk ePedModel.h.\n\n',
        "Regenerate with: python tools/gen_ped_models.py [path-to-plugin-sdk]\n",
        '"""\n',
        "from enum import IntEnum\n\n\n",
        "class PED(IntEnum):\n",
        '    """GTA San Andreas ped model ids."""\n',
    ]
    lines.extend(f"    {name} = {model}\n" for name, model in members)
    target.write_text("".join(lines), encoding="utf-8")
    print(f"Wrote {len(members)} ped models to {target}")


if __name__ == "__main__":
    main()
