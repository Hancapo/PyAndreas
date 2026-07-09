"""Stand-in for the '_pysa' builtin module when running outside the game.

Lets you import pysa for tests, tooling and editor autocompletion. Game
state is faked: memory is a sparse dict, commands succeed and return zeros.
"""

_memory = {}
_log_lines = []


def _reset():
    """Reset all offline state. Intended for tests and interactive tooling."""
    _memory.clear()
    _log_lines.clear()
    for values in _pool.values():
        values.clear()
    _ptr_to_handle.clear()
    _handle_to_ptr.clear()
    _next_handle[0] = 1
    _hooks.clear()
    _hook_ctx.clear()
    _next_hook[0] = 0


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


# Simulated pools + a consistent pointer<->handle mapping, so pool iteration
# (all_peds/all_vehicles/all_objects) can be exercised offline. Tests populate
# _pool[...] with fake pointers.
_pool = {"ped": [], "vehicle": [], "object": []}
_ptr_to_handle = {}
_handle_to_ptr = {}
_next_handle = [1]


def _handle_for(ptr):
    if not ptr:
        return -1
    if ptr not in _ptr_to_handle:
        h = _next_handle[0]
        _next_handle[0] += 1
        _ptr_to_handle[ptr] = h
        _handle_to_ptr[h] = ptr
    return _ptr_to_handle[ptr]


def player_ped():
    return _pool["ped"][0] if _pool["ped"] else 0


def ped_handle(ptr):
    return _handle_for(ptr)


def vehicle_handle(ptr):
    return _handle_for(ptr)


def object_handle(ptr):
    return _handle_for(ptr)


def ped_ptr(handle):
    return _handle_to_ptr.get(handle, 0)


def vehicle_ptr(handle):
    return _handle_to_ptr.get(handle, 0)


def object_ptr(handle):
    return _handle_to_ptr.get(handle, 0)


def peds():
    return list(_pool["ped"])


def vehicles():
    return list(_pool["vehicle"])


def objects():
    return list(_pool["object"])


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


# --- rendering -------------------------------------------------------------

def draw_rect(x1, y1, x2, y2, rgba):
    pass


def draw_sprite(name, x1, y1, x2, y2, rgba):
    pass


def load_texture(path, name=None):
    return False


def load_textures(folder):
    return False


# --- hooks -----------------------------------------------------------------

_hooks = {}
_hook_ctx = {}      # fake ctx state keyed by ctx id, for offline tests
_next_hook = [0]


def hook_install(addr, argc=0, conv=0):
    hid = _next_hook[0]
    _next_hook[0] += 1
    _hooks[hid] = (addr, argc, conv)
    return hid


def hook_remove(hid):
    _hooks.pop(hid, None)


def hook_arg(ctx, i):
    return _hook_ctx.get((ctx, "arg", i), 0)


def hook_set_arg(ctx, i, value):
    _hook_ctx[(ctx, "arg", i)] = int(value) & 0xFFFFFFFF


def hook_argf(ctx, i):
    return float(_hook_ctx.get((ctx, "argf", i), 0.0))


def hook_set_argf(ctx, i, value):
    _hook_ctx[(ctx, "argf", i)] = float(value)


def hook_reg(ctx, name):
    return _hook_ctx.get((ctx, "reg", name), 0)


def hook_set_reg(ctx, name, value):
    _hook_ctx[(ctx, "reg", name)] = int(value) & 0xFFFFFFFF


def hook_block(ctx, retval, argc, conv):
    _hook_ctx[(ctx, "blocked")] = int(retval) & 0xFFFFFFFF
