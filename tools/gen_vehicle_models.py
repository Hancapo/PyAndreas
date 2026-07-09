"""Generate pysa/vehicle_models.py from plugin-sdk's eModelID.h.

Usage:  python tools/gen_vehicle_models.py [path-to-plugin-sdk]
"""
import re
import sys
from pathlib import Path


DEFAULT_SDK = r"C:\Users\vicho\Downloads\Compressed\plugin-sdk-master\plugin-sdk-master"
MEMBER = re.compile(r"^\s*MODEL_([A-Z0-9_]+)\s*(?:=\s*(-?(?:0x)?[0-9A-Fa-f]+))?\s*,", re.M)


def main() -> None:
    sdk = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(DEFAULT_SDK)
    source = sdk / "plugin_sa" / "game_sa" / "enums" / "eModelID.h"
    text = source.read_text(encoding="utf-8", errors="replace")

    value = -1
    members = []
    for name, explicit in MEMBER.findall(text):
        value = int(explicit, 0) if explicit else value + 1
        if 400 <= value <= 611:
            members.append((name, value))

    if len(members) != 212:
        raise RuntimeError(f"expected 212 vehicle models, found {len(members)}")

    target = Path(__file__).resolve().parent.parent / "python" / "pysa" / "vehicle_models.py"
    lines = [
        '"""Vehicle model ids generated from plugin-sdk eModelID.h.\n\n',
        "Regenerate with: python tools/gen_vehicle_models.py [path-to-plugin-sdk]\n",
        '"""\n',
        "from enum import IntEnum\n\n\n",
        "class VEHICLE(IntEnum):\n",
        '    """GTA San Andreas vehicle model ids."""\n',
    ]
    lines.extend(f"    {name} = {model}\n" for name, model in members)
    target.write_text("".join(lines), encoding="utf-8")
    print(f"Wrote {len(members)} vehicle models to {target}")


if __name__ == "__main__":
    main()
