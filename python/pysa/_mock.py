"""Stand-in for the '_pysa' builtin module when running outside the game.

Lets you import pysa for tests, tooling and editor autocompletion. Game
state is faked: memory is a sparse dict, commands succeed and return zeros.
"""

_memory = {}
_log_lines = []


def call(opcode, spec, *args):
    outs = tuple(0.0 if k == "F" else ("" if k == "S" else 0)
                 for k in spec if k in "IFS")
    return (True, outs)  # optimistic: conditions pass outside the game


def call_func(addr, conv, ret, spec, *args):
    return 0.0 if ret == "f" else (None if ret == "v" else 0)


def mem_read(addr, size):
    return bytes(_memory.get(addr + i, 0) for i in range(size))


def mem_write(addr, data, unprotect=False):
    for i, b in enumerate(bytes(data)):
        _memory[addr + i] = b


def _read_int(addr, size):
    return int.from_bytes(mem_read(addr, size), "little")


def read_u8(addr):
    return _read_int(addr, 1)


def read_u16(addr):
    return _read_int(addr, 2)


def read_u32(addr):
    return _read_int(addr, 4)


def read_i32(addr):
    v = _read_int(addr, 4)
    return v - 0x100000000 if v >= 0x80000000 else v


def read_f32(addr):
    import struct
    return struct.unpack("<f", mem_read(addr, 4))[0]


def write_u8(addr, value, unprotect=False):
    mem_write(addr, int(value).to_bytes(1, "little"))


def write_u16(addr, value, unprotect=False):
    mem_write(addr, int(value).to_bytes(2, "little"))


def write_u32(addr, value, unprotect=False):
    mem_write(addr, (int(value) & 0xFFFFFFFF).to_bytes(4, "little"))


def write_f32(addr, value, unprotect=False):
    import struct
    mem_write(addr, struct.pack("<f", float(value)))


def player_ped():
    return 0


def ped_handle(ptr):
    return -1


def vehicle_handle(ptr):
    return -1


def object_handle(ptr):
    return -1


def ped_ptr(handle):
    return 0


def vehicle_ptr(handle):
    return 0


def object_ptr(handle):
    return 0


def peds():
    return []


def vehicles():
    return []


def objects():
    return []


def help_message(text, quick=True, permanent=False):
    log(f"[help] {text}")


def message(text, time_ms=2000, flag=0):
    log(f"[msg] {text}")


def big_message(text, time_ms=4000, style=0):
    log(f"[big] {text}")


def draw_text(*args):
    pass


def screen_size():
    return (640, 448)


def key_down(vk):
    return False


def cheat_buffer():
    return ""


def clear_cheat_buffer():
    pass


def game_time():
    import time
    return int(time.monotonic() * 1000)


def time_step():
    return 1.0


def log(msg):
    _log_lines.append(str(msg))
    print(msg)


def base_dir():
    return "."
