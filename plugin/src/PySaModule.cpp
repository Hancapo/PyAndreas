// PyAndreas - the embedded '_pysa' builtin module.
//
// This is the low-level bridge between Python and GTA San Andreas. Everything
// user-friendly lives in the pure-Python 'pysa' package; this module only
// exposes primitives:
//   - call():       run any SCM script command by opcode (runtime-packed,
//                   same encoding as plugin-sdk's scripting::ScriptCode)
//   - call_func():  call a raw game function (cdecl/stdcall/thiscall)
//   - memory read/write with SEH guards
//   - pools, player, handle<->pointer translation
//   - HUD messages and queued 2D text drawing
//   - input, timers, cheat-string buffer, logging

#include "PySaModule.h"

#include "plugin.h"
#include "CRunningScript.h"
#include "CPools.h"
#include "CPickups.h"
#include "CModelInfo.h"
#include "CHud.h"
#include "CMessages.h"
#include "CTimer.h"
#include "CFont.h"
#include "CCheat.h"
#include "common.h"

#include <cstdarg>
#include <cstdio>
#include <ctime>

using namespace plugin;

namespace pysa {

std::vector<DrawItem> g_drawQueue;

static std::string s_baseDir;

void SetBaseDir(const std::string &dir) { s_baseDir = dir; }
const std::string &BaseDir() { return s_baseDir; }

void Log(const char *fmt, ...) {
    char msg[2048];
    va_list va;
    va_start(va, fmt);
    vsnprintf(msg, sizeof(msg), fmt, va);
    va_end(va);

    std::string path = s_baseDir.empty() ? "PyAndreas.log" : s_baseDir + "\\PyAndreas.log";
    if (FILE *f = fopen(path.c_str(), "a")) {
        time_t now = time(nullptr);
        tm t;
        localtime_s(&t, &now);
        fprintf(f, "[%02d:%02d:%02d] %s\n", t.tm_hour, t.tm_min, t.tm_sec, msg);
        fclose(f);
    }
    OutputDebugStringA(msg);
    OutputDebugStringA("\n");
}

// ---------------------------------------------------------------------------
// Exception helpers. PyExc_* are data imports, which /DELAYLOAD:python3.dll
// forbids - so resolve the exception types from builtins at runtime instead.
// ---------------------------------------------------------------------------

static PyObject *BuiltinExc(const char *name) {
    PyObject *builtins = PyImport_ImportModule("builtins");
    PyObject *exc = builtins ? PyObject_GetAttrString(builtins, name) : nullptr;
    Py_XDECREF(builtins);
    return exc;  // deliberately kept alive for the process lifetime
}

static PyObject *TypeError() {
    static PyObject *exc = BuiltinExc("TypeError");
    return exc;
}

static PyObject *ValueError() {
    static PyObject *exc = BuiltinExc("ValueError");
    return exc;
}

// ---------------------------------------------------------------------------
// SEH-guarded memory copy (no C++ objects allowed in functions using __try)
// ---------------------------------------------------------------------------

static bool SafeCopy(void *dst, const void *src, size_t n) {
    __try {
        memcpy(dst, src, n);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

// ---------------------------------------------------------------------------
// Runtime SCM command invocation.
// Mirrors plugin-sdk shared/extensions/ScriptCommands.cpp (GTASA branch), but
// packs parameters at runtime from a spec string instead of C++ templates.
// ---------------------------------------------------------------------------

namespace {

struct ScmOutVar {
    char kind;                 // 'I', 'F' or 'S'
    unsigned short varIndex;   // index into CRunningScript::m_aLocalVars
};

class ScmCode {
public:
    std::vector<unsigned char> buf;
    std::vector<ScmOutVar> outs;
    unsigned short varIndex = 0;

    explicit ScmCode(unsigned short opcode) {
        push(&opcode, 2);
    }
    void push(const void *bytes, size_t n) {
        const unsigned char *p = static_cast<const unsigned char *>(bytes);
        buf.insert(buf.end(), p, p + n);
    }
    void pushByte(unsigned char b) { push(&b, 1); }

    void addInt(int v) {
        pushByte(SCRIPTPARAM_STATIC_INT_32BITS);
        push(&v, 4);
    }
    void addFloat(float v) {
        pushByte(SCRIPTPARAM_STATIC_FLOAT);
        push(&v, 4);
    }
    bool addString(const char *s) {
        size_t len = strlen(s);
        if (len > 127)
            return false;
        pushByte(SCRIPTPARAM_STATIC_PASCAL_STRING);
        pushByte(static_cast<unsigned char>(len));
        push(s, len);
        return true;
    }
    void addEnd() { pushByte(SCRIPTPARAM_END_OF_ARGUMENTS); }

    bool addNumberOut(char kind) {  // 'I' or 'F'
        if (varIndex >= 31)
            return false;
        pushByte(SCRIPTPARAM_LOCAL_NUMBER_VARIABLE);
        push(&varIndex, 2);
        outs.push_back({kind, varIndex});
        varIndex += 1;
        return true;
    }
    bool addStringOut() {  // 16-byte long-string local (occupies 4 var slots)
        if (varIndex >= 28)
            return false;
        pushByte(SCRIPTPARAM_LOCAL_LONG_STRING_VARIABLE);
        push(&varIndex, 2);
        outs.push_back({'S', varIndex});
        varIndex += 4;
        return true;
    }
};

}  // namespace

// _pysa.call(opcode, spec, *args) -> (cond_result, outputs_tuple)
//
// spec chars: 'i' int-in, 'f' float-in, 's' str-in,
//             'I' int-out, 'F' float-out, 'S' str-out (max 15 chars),
//             'e' variadic-arguments terminator (no value consumed).
static PyObject *py_call(PyObject *, PyObject *args) {
    Py_ssize_t nargs = PyTuple_Size(args);
    if (nargs < 2) {
        PyErr_SetString(TypeError(), "call(opcode, spec, *args) needs at least 2 arguments");
        return nullptr;
    }
    long opcode = PyLong_AsLong(PyTuple_GetItem(args, 0));
    if (opcode == -1 && PyErr_Occurred())
        return nullptr;
    PyObject *specObj = PyTuple_GetItem(args, 1);
    PyObject *specBytes = PyUnicode_AsUTF8String(specObj);
    if (!specBytes)
        return nullptr;
    std::string spec(PyBytes_AsString(specBytes));
    Py_DECREF(specBytes);

    ScmCode code(static_cast<unsigned short>(opcode & 0xFFFF));
    bool ok = true;
    Py_ssize_t argPos = 2;

    for (char k : spec) {
        switch (k) {
        case 'i': case 'f': case 's': {
            if (argPos >= nargs) {
                PyErr_SetString(TypeError(), "call(): not enough values for spec");
                ok = false;
                break;
            }
            PyObject *v = PyTuple_GetItem(args, argPos++);
            if (k == 'i') {
                PyObject *num = PyNumber_Long(v);
                if (!num) { ok = false; break; }
                code.addInt(static_cast<int>(PyLong_AsLong(num)));
                Py_DECREF(num);
            } else if (k == 'f') {
                double d = PyFloat_AsDouble(v);
                if (d == -1.0 && PyErr_Occurred()) { ok = false; break; }
                code.addFloat(static_cast<float>(d));
            } else {
                PyObject *b = PyUnicode_AsUTF8String(v);
                if (!b) { ok = false; break; }
                if (!code.addString(PyBytes_AsString(b))) {
                    PyErr_SetString(ValueError(), "call(): string argument too long (max 127)");
                    ok = false;
                }
                Py_DECREF(b);
            }
            break;
        }
        case 'I': case 'F':
            if (!code.addNumberOut(k)) {
                PyErr_SetString(ValueError(), "call(): too many output variables");
                ok = false;
            }
            break;
        case 'S':
            if (!code.addStringOut()) {
                PyErr_SetString(ValueError(), "call(): too many output variables");
                ok = false;
            }
            break;
        case 'e':
            code.addEnd();
            break;
        default:
            PyErr_Format(ValueError(), "call(): unknown spec char '%c'", k);
            ok = false;
        }
        if (!ok)
            break;
    }
    if (ok && argPos != nargs) {
        PyErr_SetString(TypeError(), "call(): too many values for spec");
        ok = false;
    }
    if (!ok)
        return nullptr;

    // Execute exactly like scripting::CallCommandById does. Stack-local (not
    // static): a command can fire a ctor/dtor event whose Python handler runs
    // another command before this one returns.
    CRunningScript script;
    memset(&script, 0, sizeof(CRunningScript));
    script.Init();
    strcpy_s(script.m_szName, "pysa");
    script.m_bIsMission = false;
    script.m_bUseMissionCleanup = false;
    script.m_bNotFlag = (opcode >> 15) & 1;
    script.m_pBaseIP = script.m_pCurrentIP = code.buf.data();
    script.ProcessOneCommand();

    PyObject *outs = PyTuple_New(static_cast<Py_ssize_t>(code.outs.size()));
    if (!outs)
        return nullptr;
    for (size_t i = 0; i < code.outs.size(); ++i) {
        const ScmOutVar &o = code.outs[i];
        PyObject *val = nullptr;
        if (o.kind == 'I')
            val = PyLong_FromLong(script.m_aLocalVars[o.varIndex].iParam);
        else if (o.kind == 'F')
            val = PyFloat_FromDouble(script.m_aLocalVars[o.varIndex].fParam);
        else {  // 'S'
            char text[17];
            memcpy(text, &script.m_aLocalVars[o.varIndex], 16);
            text[16] = '\0';
            val = PyUnicode_FromString(text);
            if (!val) {  // non-UTF8 garbage: fall back to empty string
                PyErr_Clear();
                val = PyUnicode_FromString("");
            }
        }
        if (!val) {
            Py_DECREF(outs);
            return nullptr;
        }
        PyTuple_SetItem(outs, static_cast<Py_ssize_t>(i), val);  // steals ref
    }
    PyObject *result = Py_BuildValue("(NN)",
        PyBool_FromLong(script.m_bCondResult ? 1 : 0), outs);
    return result;
}

// ---------------------------------------------------------------------------
// Raw function calling (x86, 32-bit): cdecl / stdcall / thiscall
// ---------------------------------------------------------------------------

typedef unsigned int u32;

#define PYSA_ARGS_0
#define PYSA_ARGS_1  a[0]
#define PYSA_ARGS_2  PYSA_ARGS_1, a[1]
#define PYSA_ARGS_3  PYSA_ARGS_2, a[2]
#define PYSA_ARGS_4  PYSA_ARGS_3, a[3]
#define PYSA_ARGS_5  PYSA_ARGS_4, a[4]
#define PYSA_ARGS_6  PYSA_ARGS_5, a[5]
#define PYSA_ARGS_7  PYSA_ARGS_6, a[6]
#define PYSA_ARGS_8  PYSA_ARGS_7, a[7]
#define PYSA_ARGS_9  PYSA_ARGS_8, a[8]
#define PYSA_ARGS_10 PYSA_ARGS_9, a[9]
#define PYSA_ARGS_11 PYSA_ARGS_10, a[10]
#define PYSA_ARGS_12 PYSA_ARGS_11, a[11]

#define PYSA_SIG_0
#define PYSA_SIG_1  u32
#define PYSA_SIG_2  u32, u32
#define PYSA_SIG_3  u32, u32, u32
#define PYSA_SIG_4  u32, u32, u32, u32
#define PYSA_SIG_5  u32, u32, u32, u32, u32
#define PYSA_SIG_6  u32, u32, u32, u32, u32, u32
#define PYSA_SIG_7  u32, u32, u32, u32, u32, u32, u32
#define PYSA_SIG_8  u32, u32, u32, u32, u32, u32, u32, u32
#define PYSA_SIG_9  u32, u32, u32, u32, u32, u32, u32, u32, u32
#define PYSA_SIG_10 u32, u32, u32, u32, u32, u32, u32, u32, u32, u32
#define PYSA_SIG_11 u32, u32, u32, u32, u32, u32, u32, u32, u32, u32, u32
#define PYSA_SIG_12 u32, u32, u32, u32, u32, u32, u32, u32, u32, u32, u32, u32

template <typename R>
static R CallCdecl(u32 addr, const u32 *a, int n) {
#define C(N) case N: return ((R(__cdecl *)(PYSA_SIG_##N))addr)(PYSA_ARGS_##N);
    switch (n) { C(0) C(1) C(2) C(3) C(4) C(5) C(6) C(7) C(8) C(9) C(10) C(11) C(12) }
#undef C
    return R();
}

template <typename R>
static R CallStdcall(u32 addr, const u32 *a, int n) {
#define C(N) case N: return ((R(__stdcall *)(PYSA_SIG_##N))addr)(PYSA_ARGS_##N);
    switch (n) { C(0) C(1) C(2) C(3) C(4) C(5) C(6) C(7) C(8) C(9) C(10) C(11) C(12) }
#undef C
    return R();
}

// thiscall: 'this' in ecx. Emulated via __fastcall with a dummy edx parameter.
template <typename R>
static R CallThiscall(u32 addr, const u32 *a, int n) {
    switch (n) {
    case 1:  return ((R(__fastcall *)(u32, u32))addr)(a[0], 0);
    case 2:  return ((R(__fastcall *)(u32, u32, u32))addr)(a[0], 0, a[1]);
    case 3:  return ((R(__fastcall *)(u32, u32, u32, u32))addr)(a[0], 0, a[1], a[2]);
    case 4:  return ((R(__fastcall *)(u32, u32, u32, u32, u32))addr)(a[0], 0, a[1], a[2], a[3]);
    case 5:  return ((R(__fastcall *)(u32, u32, u32, u32, u32, u32))addr)(a[0], 0, a[1], a[2], a[3], a[4]);
    case 6:  return ((R(__fastcall *)(u32, u32, u32, u32, u32, u32, u32))addr)(a[0], 0, a[1], a[2], a[3], a[4], a[5]);
    case 7:  return ((R(__fastcall *)(u32, u32, u32, u32, u32, u32, u32, u32))addr)(a[0], 0, a[1], a[2], a[3], a[4], a[5], a[6]);
    case 8:  return ((R(__fastcall *)(u32, u32, u32, u32, u32, u32, u32, u32, u32))addr)(a[0], 0, a[1], a[2], a[3], a[4], a[5], a[6], a[7]);
    case 9:  return ((R(__fastcall *)(u32, u32, u32, u32, u32, u32, u32, u32, u32, u32))addr)(a[0], 0, a[1], a[2], a[3], a[4], a[5], a[6], a[7], a[8]);
    case 10: return ((R(__fastcall *)(u32, u32, u32, u32, u32, u32, u32, u32, u32, u32, u32))addr)(a[0], 0, a[1], a[2], a[3], a[4], a[5], a[6], a[7], a[8], a[9]);
    case 11: return ((R(__fastcall *)(u32, u32, u32, u32, u32, u32, u32, u32, u32, u32, u32, u32))addr)(a[0], 0, a[1], a[2], a[3], a[4], a[5], a[6], a[7], a[8], a[9], a[10]);
    case 12: return ((R(__fastcall *)(u32, u32, u32, u32, u32, u32, u32, u32, u32, u32, u32, u32, u32))addr)(a[0], 0, a[1], a[2], a[3], a[4], a[5], a[6], a[7], a[8], a[9], a[10], a[11]);
    }
    return R();
}

// _pysa.call_func(addr, conv, ret, spec, *args) -> int | float | None
//   conv: 'c' cdecl, 's' stdcall, 't' thiscall (first arg = this)
//   ret:  'i' int, 'f' float, 'v' void
//   spec: one char per arg: 'i' int/pointer, 'f' float
static PyObject *py_call_func(PyObject *, PyObject *args) {
    Py_ssize_t nargs = PyTuple_Size(args);
    if (nargs < 4) {
        PyErr_SetString(TypeError(), "call_func(addr, conv, ret, spec, *args)");
        return nullptr;
    }
    unsigned long addr = PyLong_AsUnsignedLongMask(PyTuple_GetItem(args, 0));

    char conv = 0, ret = 0;
    std::string spec;
    {
        PyObject *b1 = PyUnicode_AsUTF8String(PyTuple_GetItem(args, 1));
        PyObject *b2 = PyUnicode_AsUTF8String(PyTuple_GetItem(args, 2));
        PyObject *b3 = PyUnicode_AsUTF8String(PyTuple_GetItem(args, 3));
        if (b1 && b2 && b3) {
            conv = PyBytes_AsString(b1)[0];
            ret = PyBytes_AsString(b2)[0];
            spec = PyBytes_AsString(b3);
        }
        Py_XDECREF(b1); Py_XDECREF(b2); Py_XDECREF(b3);
        if (PyErr_Occurred())
            return nullptr;
    }

    int n = static_cast<int>(spec.size());
    if (n > 12 || nargs - 4 != n) {
        PyErr_SetString(TypeError(), "call_func(): spec/arg count mismatch (max 12 args)");
        return nullptr;
    }
    if (!addr) {
        PyErr_SetString(ValueError(), "call_func(): null address");
        return nullptr;
    }
    if (conv == 't' && n < 1) {
        PyErr_SetString(TypeError(), "call_func(): thiscall needs 'this' as first argument");
        return nullptr;
    }

    u32 a[12] = {0};
    for (int i = 0; i < n; ++i) {
        PyObject *v = PyTuple_GetItem(args, 4 + i);
        if (spec[i] == 'f') {
            float f = static_cast<float>(PyFloat_AsDouble(v));
            if (PyErr_Occurred())
                return nullptr;
            memcpy(&a[i], &f, 4);
        } else {
            a[i] = static_cast<u32>(PyLong_AsUnsignedLongMask(v));
            if (PyErr_Occurred())
                return nullptr;
        }
    }

    if (ret == 'f') {
        float r = 0.0f;
        if (conv == 'c') r = CallCdecl<float>(addr, a, n);
        else if (conv == 's') r = CallStdcall<float>(addr, a, n);
        else r = CallThiscall<float>(addr, a, n);
        return PyFloat_FromDouble(r);
    }
    u32 r = 0;
    if (conv == 'c') r = CallCdecl<u32>(addr, a, n);
    else if (conv == 's') r = CallStdcall<u32>(addr, a, n);
    else r = CallThiscall<u32>(addr, a, n);
    if (ret == 'v')
        return Py_BuildValue("");
    return PyLong_FromUnsignedLong(r);
}

// ---------------------------------------------------------------------------
// Memory access
// ---------------------------------------------------------------------------

static PyObject *py_mem_read(PyObject *, PyObject *args) {
    unsigned long addr;
    unsigned long size;
    if (!PyArg_ParseTuple(args, "kk", &addr, &size))
        return nullptr;
    if (size > 0x100000) {
        PyErr_SetString(ValueError(), "mem_read(): size too large");
        return nullptr;
    }
    std::vector<unsigned char> tmp(size);
    if (size && !SafeCopy(tmp.data(), reinterpret_cast<void *>(addr), size)) {
        PyErr_Format(ValueError(), "mem_read(): access violation at 0x%08lX", addr);
        return nullptr;
    }
    return PyBytes_FromStringAndSize(reinterpret_cast<char *>(tmp.data()), size);
}

static bool WriteGuarded(unsigned long addr, const void *src, size_t n, bool unprotect) {
    DWORD old = 0;
    if (unprotect)
        VirtualProtect(reinterpret_cast<void *>(addr), n, PAGE_EXECUTE_READWRITE, &old);
    bool ok = SafeCopy(reinterpret_cast<void *>(addr), src, n);
    if (unprotect)
        VirtualProtect(reinterpret_cast<void *>(addr), n, old, &old);
    return ok;
}

static PyObject *py_mem_write(PyObject *, PyObject *args) {
    unsigned long addr;
    const char *buf;
    Py_ssize_t len;
    int unprotect = 0;
    if (!PyArg_ParseTuple(args, "ky#|i", &addr, &buf, &len, &unprotect))
        return nullptr;
    bool ok = WriteGuarded(addr, buf, static_cast<size_t>(len), unprotect != 0);
    if (!ok) {
        PyErr_Format(ValueError(), "mem_write(): access violation at 0x%08lX", addr);
        return nullptr;
    }
    return Py_BuildValue("");
}

template <typename T>
static PyObject *ReadScalar(PyObject *args, bool isFloat) {
    unsigned long addr;
    if (!PyArg_ParseTuple(args, "k", &addr))
        return nullptr;
    T v{};
    if (!SafeCopy(&v, reinterpret_cast<void *>(addr), sizeof(T))) {
        PyErr_Format(ValueError(), "read: access violation at 0x%08lX", addr);
        return nullptr;
    }
    if (isFloat)
        return PyFloat_FromDouble(static_cast<double>(v));
    return PyLong_FromLong(static_cast<long>(v));
}

static PyObject *py_read_u8(PyObject *, PyObject *a)  { return ReadScalar<unsigned char>(a, false); }
static PyObject *py_read_u16(PyObject *, PyObject *a) { return ReadScalar<unsigned short>(a, false); }
static PyObject *py_read_i32(PyObject *, PyObject *a) { return ReadScalar<int>(a, false); }
static PyObject *py_read_f32(PyObject *, PyObject *a) { return ReadScalar<float>(a, true); }

static PyObject *py_read_u32(PyObject *, PyObject *args) {
    unsigned long addr;
    if (!PyArg_ParseTuple(args, "k", &addr))
        return nullptr;
    unsigned int v = 0;
    if (!SafeCopy(&v, reinterpret_cast<void *>(addr), 4)) {
        PyErr_Format(ValueError(), "read_u32: access violation at 0x%08lX", addr);
        return nullptr;
    }
    return PyLong_FromUnsignedLong(v);
}

template <typename T>
static PyObject *WriteScalar(PyObject *args, bool isFloat) {
    unsigned long addr;
    int unprotect = 0;
    T v{};
    if (isFloat) {
        double d;
        if (!PyArg_ParseTuple(args, "kd|i", &addr, &d, &unprotect))
            return nullptr;
        v = static_cast<T>(d);
    } else {
        unsigned long l;
        if (!PyArg_ParseTuple(args, "kk|i", &addr, &l, &unprotect))
            return nullptr;
        v = static_cast<T>(l);
    }
    if (!WriteGuarded(addr, &v, sizeof(T), unprotect != 0)) {
        PyErr_Format(ValueError(), "write: access violation at 0x%08lX", addr);
        return nullptr;
    }
    return Py_BuildValue("");
}

static PyObject *py_write_u8(PyObject *, PyObject *a)  { return WriteScalar<unsigned char>(a, false); }
static PyObject *py_write_u16(PyObject *, PyObject *a) { return WriteScalar<unsigned short>(a, false); }
static PyObject *py_write_u32(PyObject *, PyObject *a) { return WriteScalar<unsigned int>(a, false); }
static PyObject *py_write_f32(PyObject *, PyObject *a) { return WriteScalar<float>(a, true); }

// ---------------------------------------------------------------------------
// Player, pools, handles
// ---------------------------------------------------------------------------

static PyObject *py_player_ped(PyObject *, PyObject *) {
    return PyLong_FromUnsignedLong(reinterpret_cast<unsigned long>(FindPlayerPed(-1)));
}

static PyObject *py_ped_handle(PyObject *, PyObject *args) {
    unsigned long p;
    if (!PyArg_ParseTuple(args, "k", &p)) return nullptr;
    return PyLong_FromLong(p ? CPools::GetPedRef(reinterpret_cast<CPed *>(p)) : -1);
}
static PyObject *py_vehicle_handle(PyObject *, PyObject *args) {
    unsigned long p;
    if (!PyArg_ParseTuple(args, "k", &p)) return nullptr;
    return PyLong_FromLong(p ? CPools::GetVehicleRef(reinterpret_cast<CVehicle *>(p)) : -1);
}
static PyObject *py_object_handle(PyObject *, PyObject *args) {
    unsigned long p;
    if (!PyArg_ParseTuple(args, "k", &p)) return nullptr;
    return PyLong_FromLong(p ? CPools::GetObjectRef(reinterpret_cast<CObject *>(p)) : -1);
}
static PyObject *py_ped_ptr(PyObject *, PyObject *args) {
    long h;
    if (!PyArg_ParseTuple(args, "l", &h)) return nullptr;
    return PyLong_FromUnsignedLong(h == -1 ? 0 : reinterpret_cast<unsigned long>(CPools::GetPed(h)));
}
static PyObject *py_vehicle_ptr(PyObject *, PyObject *args) {
    long h;
    if (!PyArg_ParseTuple(args, "l", &h)) return nullptr;
    return PyLong_FromUnsignedLong(h == -1 ? 0 : reinterpret_cast<unsigned long>(CPools::GetVehicle(h)));
}
static PyObject *py_object_ptr(PyObject *, PyObject *args) {
    long h;
    if (!PyArg_ParseTuple(args, "l", &h)) return nullptr;
    return PyLong_FromUnsignedLong(h == -1 ? 0 : reinterpret_cast<unsigned long>(CPools::GetObject(h)));
}

static PyObject *py_model_info_ptr(PyObject *, PyObject *args) {
    int model;
    if (!PyArg_ParseTuple(args, "i", &model))
        return nullptr;
    CBaseModelInfo *info = model >= 0 ? CModelInfo::GetModelInfo(model) : nullptr;
    return PyLong_FromUnsignedLong(
        static_cast<unsigned long>(reinterpret_cast<uintptr_t>(info)));
}

template <typename PoolT>
static PyObject *ListPool(PoolT *pool) {
    PyObject *list = PyList_New(0);
    if (!list)
        return nullptr;
    if (pool) {
        for (auto entity : *pool) {
            PyObject *v = PyLong_FromUnsignedLong(reinterpret_cast<unsigned long>(entity));
            if (!v || PyList_Append(list, v) < 0) {
                Py_XDECREF(v);
                Py_DECREF(list);
                return nullptr;
            }
            Py_DECREF(v);
        }
    }
    return list;
}

static PyObject *py_peds(PyObject *, PyObject *)     { return ListPool(CPools::ms_pPedPool); }
static PyObject *py_vehicles(PyObject *, PyObject *) { return ListPool(CPools::ms_pVehiclePool); }
static PyObject *py_objects(PyObject *, PyObject *)  { return ListPool(CPools::ms_pObjectPool); }
static PyObject *py_buildings(PyObject *, PyObject *) { return ListPool(CPools::ms_pBuildingPool); }
static PyObject *py_dummies(PyObject *, PyObject *)   { return ListPool(CPools::ms_pDummyPool); }

static PyObject *py_pickup_handles(PyObject *, PyObject *) {
    PyObject *list = PyList_New(0);
    if (!list)
        return nullptr;
    if (CPickups::aPickUps) {
        for (unsigned int i = 0; i < MAX_NUM_PICKUPS; ++i) {
            if (CPickups::aPickUps[i].m_nPickupType == PICKUP_NONE)
                continue;
            PyObject *value = PyLong_FromLong(CPickups::GetUniquePickupIndex(i));
            if (!value || PyList_Append(list, value) < 0) {
                Py_XDECREF(value);
                Py_DECREF(list);
                return nullptr;
            }
            Py_DECREF(value);
        }
    }
    return list;
}

static PyObject *py_pickup_info(PyObject *, PyObject *args) {
    int handle;
    if (!PyArg_ParseTuple(args, "i", &handle))
        return nullptr;
    if (!CPickups::aPickUps || handle < 0)
        return Py_BuildValue("");
    int index = CPickups::GetActualPickupIndex(handle);
    if (index < 0 || static_cast<unsigned int>(index) >= MAX_NUM_PICKUPS)
        return Py_BuildValue("");
    CPickup &pickup = CPickups::aPickUps[index];
    if (pickup.m_nPickupType == PICKUP_NONE)
        return Py_BuildValue("");
    CVector pos = pickup.GetPosn();
    unsigned int flags = *reinterpret_cast<unsigned char *>(&pickup.m_nFlags);
    return Py_BuildValue("(iiiiffffI)", pickup.m_nModelIndex,
                         pickup.m_nPickupType, pickup.m_nAmmo,
                         pickup.m_nMoneyPerDay, pickup.m_fRevenueValue,
                         pos.x, pos.y, pos.z, flags);
}

// ---------------------------------------------------------------------------
// HUD messages and 2D text drawing
// ---------------------------------------------------------------------------

static PyObject *py_help_message(PyObject *, PyObject *args) {
    const char *text;
    int quick = 1, permanent = 0;
    if (!PyArg_ParseTuple(args, "s|ii", &text, &quick, &permanent))
        return nullptr;
    CHud::SetHelpMessage(text, quick != 0, permanent != 0, false);
    return Py_BuildValue("");
}

static PyObject *py_message(PyObject *, PyObject *args) {
    const char *text;
    unsigned long timeMs = 2000;
    unsigned int flag = 0;
    if (!PyArg_ParseTuple(args, "s|kI", &text, &timeMs, &flag))
        return nullptr;
    CMessages::AddMessageJumpQ(text, timeMs, static_cast<unsigned short>(flag), false);
    return Py_BuildValue("");
}

static PyObject *py_big_message(PyObject *, PyObject *args) {
    const char *text;
    unsigned long timeMs = 4000;
    unsigned int style = 0;
    if (!PyArg_ParseTuple(args, "s|kI", &text, &timeMs, &style))
        return nullptr;
    CMessages::AddBigMessage(text, timeMs, static_cast<unsigned short>(style));
    return Py_BuildValue("");
}

static PyObject *py_draw_text(PyObject *, PyObject *args) {
    DrawItem d{};
    const char *text;
    d.sx = 0.6f; d.sy = 1.2f;
    d.rgba = 0xFFFFFFFF;
    d.font = 1;         // FONT_SUBTITLES
    d.align = 1;        // left
    d.shadow = 1;
    d.dropRgba = 0x000000FF;
    d.proportional = 1;
    d.wrapx = 0.0f;
    if (!PyArg_ParseTuple(args, "sff|ffIiiiIif", &text, &d.x, &d.y, &d.sx, &d.sy,
                          &d.rgba, &d.font, &d.align, &d.shadow, &d.dropRgba,
                          &d.proportional, &d.wrapx))
        return nullptr;
    d.text = text;
    g_drawQueue.push_back(std::move(d));
    return Py_BuildValue("");
}

void FlushDrawQueue() {
    if (g_drawQueue.empty())
        return;
    for (const DrawItem &d : g_drawQueue) {
        CFont::SetBackground(false, false);
        CFont::SetProportional(d.proportional != 0);
        CFont::SetFontStyle(static_cast<short>(d.font));
        CFont::SetOrientation(static_cast<eFontAlignment>(d.align));
        float screenW = *reinterpret_cast<int *>(0xC17044) * 1.0f;  // RsGlobal.maximumWidth
        CFont::SetWrapx(d.wrapx > 0.0f ? d.wrapx : screenW);
        CFont::SetScale(d.sx, d.sy);
        CFont::SetColor(CRGBA((d.rgba >> 24) & 0xFF, (d.rgba >> 16) & 0xFF,
                              (d.rgba >> 8) & 0xFF, d.rgba & 0xFF));
        CFont::SetEdge(0);
        if (d.shadow > 0) {
            CFont::SetDropShadowPosition(static_cast<short>(d.shadow));
            CFont::SetDropColor(CRGBA((d.dropRgba >> 24) & 0xFF, (d.dropRgba >> 16) & 0xFF,
                                      (d.dropRgba >> 8) & 0xFF, d.dropRgba & 0xFF));
        } else {
            CFont::SetDropShadowPosition(0);
        }
        CFont::PrintString(d.x, d.y, d.text.c_str());
    }
    g_drawQueue.clear();
}

static PyObject *py_screen_size(PyObject *, PyObject *) {
    int w = *reinterpret_cast<int *>(0xC17044);  // RsGlobal.maximumWidth
    int h = *reinterpret_cast<int *>(0xC17048);  // RsGlobal.maximumHeight
    return Py_BuildValue("(ii)", w, h);
}

// ---------------------------------------------------------------------------
// Input, timers, misc
// ---------------------------------------------------------------------------

static PyObject *py_key_down(PyObject *, PyObject *args) {
    int vk;
    if (!PyArg_ParseTuple(args, "i", &vk))
        return nullptr;
    return PyBool_FromLong((GetKeyState(vk) & 0x8000) ? 1 : 0);
}

static PyObject *py_cheat_buffer(PyObject *, PyObject *) {
    // CCheat::m_CheatString holds recently typed characters, most recent first.
    char buf[31];
    memcpy(buf, CCheat::m_CheatString, 30);
    buf[30] = '\0';
    return PyUnicode_FromString(buf);
}

static PyObject *py_clear_cheat_buffer(PyObject *, PyObject *) {
    CCheat::m_CheatString[0] = '\0';
    return Py_BuildValue("");
}

static PyObject *py_game_time(PyObject *, PyObject *) {
    return PyLong_FromUnsignedLong(CTimer::m_snTimeInMilliseconds);
}

static PyObject *py_time_step(PyObject *, PyObject *) {
    return PyFloat_FromDouble(CTimer::ms_fTimeStep);
}

static PyObject *py_log(PyObject *, PyObject *args) {
    const char *msg;
    if (!PyArg_ParseTuple(args, "s", &msg))
        return nullptr;
    Log("%s", msg);
    return Py_BuildValue("");
}

static PyObject *py_base_dir(PyObject *, PyObject *) {
    return PyUnicode_FromString(BaseDir().c_str());
}

static PyObject *py_set_event_enabled(PyObject *, PyObject *args) {
    const char *name;
    int enabled;
    if (!PyArg_ParseTuple(args, "sp", &name, &enabled))
        return nullptr;
    if (!SetEventEnabled(name, enabled != 0)) {
        PyErr_Format(ValueError(), "unsupported native event: %s", name);
        return nullptr;
    }
    return Py_BuildValue("");
}

// ---------------------------------------------------------------------------
// Module definition
// ---------------------------------------------------------------------------

static PyMethodDef s_methods[] = {
    {"call", py_call, METH_VARARGS,
     "call(opcode, spec, *args) -> (cond, outputs)\n"
     "Run an SCM script command. spec: i/f/s inputs, I/F/S outputs, e = end marker."},
    {"call_func", py_call_func, METH_VARARGS,
     "call_func(addr, conv, ret, spec, *args) -> result\n"
     "Call a game function. conv c/s/t, ret i/f/v, spec i/f per argument."},
    {"mem_read", py_mem_read, METH_VARARGS, "mem_read(addr, size) -> bytes"},
    {"mem_write", py_mem_write, METH_VARARGS, "mem_write(addr, data, unprotect=False)"},
    {"read_u8", py_read_u8, METH_VARARGS, "read_u8(addr) -> int"},
    {"read_u16", py_read_u16, METH_VARARGS, "read_u16(addr) -> int"},
    {"read_u32", py_read_u32, METH_VARARGS, "read_u32(addr) -> int"},
    {"read_i32", py_read_i32, METH_VARARGS, "read_i32(addr) -> int"},
    {"read_f32", py_read_f32, METH_VARARGS, "read_f32(addr) -> float"},
    {"write_u8", py_write_u8, METH_VARARGS, "write_u8(addr, value, unprotect=False)"},
    {"write_u16", py_write_u16, METH_VARARGS, "write_u16(addr, value, unprotect=False)"},
    {"write_u32", py_write_u32, METH_VARARGS, "write_u32(addr, value, unprotect=False)"},
    {"write_f32", py_write_f32, METH_VARARGS, "write_f32(addr, value, unprotect=False)"},
    {"player_ped", py_player_ped, METH_NOARGS, "player_ped() -> CPed* address (0 if none)"},
    {"ped_handle", py_ped_handle, METH_VARARGS, "ped_handle(ptr) -> SCM handle"},
    {"vehicle_handle", py_vehicle_handle, METH_VARARGS, "vehicle_handle(ptr) -> SCM handle"},
    {"object_handle", py_object_handle, METH_VARARGS, "object_handle(ptr) -> SCM handle"},
    {"ped_ptr", py_ped_ptr, METH_VARARGS, "ped_ptr(handle) -> address (0 if invalid)"},
    {"vehicle_ptr", py_vehicle_ptr, METH_VARARGS, "vehicle_ptr(handle) -> address (0 if invalid)"},
    {"object_ptr", py_object_ptr, METH_VARARGS, "object_ptr(handle) -> address (0 if invalid)"},
    {"model_info_ptr", py_model_info_ptr, METH_VARARGS,
     "model_info_ptr(model) -> CBaseModelInfo* address (0 if unavailable)"},
    {"peds", py_peds, METH_NOARGS, "peds() -> list of CPed* addresses"},
    {"vehicles", py_vehicles, METH_NOARGS, "vehicles() -> list of CVehicle* addresses"},
    {"objects", py_objects, METH_NOARGS, "objects() -> list of CObject* addresses"},
    {"buildings", py_buildings, METH_NOARGS, "buildings() -> list of CBuilding* addresses"},
    {"dummies", py_dummies, METH_NOARGS, "dummies() -> list of CDummy* addresses"},
    {"pickup_handles", py_pickup_handles, METH_NOARGS,
     "pickup_handles() -> list of active pickup handles"},
    {"pickup_info", py_pickup_info, METH_VARARGS,
     "pickup_info(handle) -> model,type,ammo,money,revenue,x,y,z,flags or None"},
    {"help_message", py_help_message, METH_VARARGS, "help_message(text, quick=True, permanent=False)"},
    {"message", py_message, METH_VARARGS, "message(text, time_ms=2000, flag=0)"},
    {"big_message", py_big_message, METH_VARARGS, "big_message(text, time_ms=4000, style=0)"},
    {"draw_text", py_draw_text, METH_VARARGS,
     "draw_text(text, x, y, sx, sy, rgba, font, align, shadow, drop_rgba, proportional, wrapx)"},
    {"screen_size", py_screen_size, METH_NOARGS, "screen_size() -> (width, height)"},
    {"key_down", py_key_down, METH_VARARGS, "key_down(vk) -> bool"},
    {"cheat_buffer", py_cheat_buffer, METH_NOARGS, "cheat_buffer() -> recently typed chars (reversed)"},
    {"clear_cheat_buffer", py_clear_cheat_buffer, METH_NOARGS, "clear_cheat_buffer()"},
    {"game_time", py_game_time, METH_NOARGS, "game_time() -> game time in ms (pauses with game)"},
    {"time_step", py_time_step, METH_NOARGS, "time_step() -> frame time step (game speed scaled)"},
    {"log", py_log, METH_VARARGS, "log(message) -> write to PyAndreas.log"},
    {"base_dir", py_base_dir, METH_NOARGS, "base_dir() -> <game>\\PyAndreas"},
    {"set_event_enabled", py_set_event_enabled, METH_VARARGS,
     "set_event_enabled(name, enabled) -> None (internal event subscription gate)"},
    {nullptr, nullptr, 0, nullptr},
};

// Assembled at init from the core + render + hook tables.
static std::vector<PyMethodDef> s_allMethods;

static PyModuleDef s_moduleDef = {
    PyModuleDef_HEAD_INIT, "_pysa",
    "Low-level bridge into GTA San Andreas (PyAndreas plugin).",
    -1, nullptr, nullptr, nullptr, nullptr, nullptr,
};

static void AppendMethods(const PyMethodDef *table) {
    for (const PyMethodDef *m = table; m->ml_name; ++m)
        s_allMethods.push_back(*m);
}

}  // namespace pysa

extern "C" PyObject *PyInit__pysa(void) {
    using namespace pysa;
    s_allMethods.clear();
    AppendMethods(s_methods);
    AppendMethods(pysa_render_methods);
    AppendMethods(pysa_hook_methods);
    s_allMethods.push_back({nullptr, nullptr, 0, nullptr});  // sentinel
    s_moduleDef.m_methods = s_allMethods.data();
    return PyModule_Create(&s_moduleDef);
}
