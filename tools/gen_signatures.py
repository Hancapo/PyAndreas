"""Generate pysa/signatures.py from Sanny Builder Library's sa.json.

Source data: https://library.sannybuilder.com/assets/sa/sa.json
Usage:       python tools/gen_signatures.py <path-to-sa.json>

Each supported vanilla command becomes:
    'NAME': (opcode, inspec, outspec, flags, innames, outnames, desc)

inspec:  one char per input param: i=int/handle/enum, f=float, s=string;
         trailing '*' = variadic (extra args allowed, End auto-appended)
outspec: one char per output: I=int, F=float, S=string, P=Ped, V=Vehicle, O=Object
flags:   bit 0 = condition command (sets the cond flag)
"""
import json
import sys
from pathlib import Path

STR_IN = {"string", "string128", "gxt_key", "zone_key", "GarageName", "AnimGroup"}
STR_OUT = {"string", "gxt_key"}

FLAG_COND = 1


def in_char(ptype: str) -> str:
    if ptype == "float":
        return "f"
    if ptype in STR_IN:
        return "s"
    if ptype == "arguments":
        return "*"
    return "i"


def out_char(ptype: str) -> str:
    if ptype == "float":
        return "F"
    if ptype in STR_OUT:
        return "S"
    if ptype == "Char":
        return "P"
    if ptype in ("Car", "Heli", "Plane", "Boat", "Trailer"):
        return "V"
    if ptype == "Object":
        return "O"
    return "I"


def main() -> None:
    src = Path(sys.argv[1])
    data = json.loads(src.read_text(encoding="utf-8"))
    commands = next(e for e in data["extensions"] if e["name"] == "default")["commands"]

    entries = []
    skipped = 0
    for c in sorted(commands, key=lambda c: c["name"]):
        attrs = c.get("attrs", {})
        inputs = c.get("input", [])
        outputs = c.get("output", [])
        if (attrs.get("is_unsupported") or attrs.get("is_nop")
                or attrs.get("is_branch") or attrs.get("is_segment")):
            skipped += 1
            continue
        # in-place var math (ABS_VAR_INT & co) doesn't fit the local-var scheme
        if any(p.get("source") not in (None, "var_any") for p in outputs):
            skipped += 1
            continue
        if any(p["type"] == "label" for p in inputs):  # control flow
            skipped += 1
            continue

        inspec = "".join(in_char(p["type"]) for p in inputs)
        if "*" in inspec:  # variadic must be last
            if not inspec.endswith("*") or inspec.count("*") > 1:
                skipped += 1
                continue
        outspec = "".join(out_char(p["type"]) for p in outputs)
        flags = FLAG_COND if attrs.get("is_condition") else 0
        innames = ",".join(p["name"] for p in inputs)
        outnames = ",".join(p["name"] for p in outputs)
        desc = c.get("short_desc", "")
        entries.append((c["name"], int(c["id"], 16), inspec, outspec, flags,
                        innames, outnames, desc))

    out_path = Path(__file__).resolve().parent.parent / "python" / "pysa" / "signatures.py"
    with out_path.open("w", encoding="utf-8") as f:
        f.write('"""SCM command signature database (generated - do not edit).\n\n'
                "Derived from Sanny Builder Library (https://library.sannybuilder.com),\n"
                "vanilla San Andreas commands only.\n"
                "Regenerate with: python tools/gen_signatures.py sa.json\n"
                '"""\n\n'
                "#: name -> (opcode, inspec, outspec, flags, innames, outnames, desc)\n"
                "SIGS = {\n")
        for name, opcode, inspec, outspec, flags, innames, outnames, desc in entries:
            f.write(f" {name!r}:(0x{opcode:04X},{inspec!r},{outspec!r},{flags},"
                    f"{innames!r},{outnames!r},{desc!r}),\n")
        f.write("}\n\nFLAG_COND = 1\n")
    print(f"Wrote {len(entries)} signatures ({skipped} skipped) to {out_path}")


if __name__ == "__main__":
    main()
