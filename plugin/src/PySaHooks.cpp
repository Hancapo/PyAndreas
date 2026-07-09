// PyAndreas - function hook factory.
//
// Lets Python intercept any game function. We use safetyhook's mid-hook
// (which saves/restores full CPU context and resumes the original), so we
// don't have to match each target's calling convention. The only trick is
// carrying a per-hook id into a single shared dispatcher:
//
//   target --safetyhook--> thunk[id] (mov ecx,id; jmp commonMid) --> commonMid
//        --> HookDispatchC(id, ctx) --> Python pysa._runtime._dispatch_hook
//
// From Python the callback reads/writes arguments (stack at esp+4+i*4),
// the thiscall 'this' (ecx), and CPU registers, and may optionally block the
// original call and force a return value.

#include "PySaModule.h"

#include <windows.h>
#include <safetyhook.hpp>

#include <cstdint>
#include <cstring>
#include <memory>
#include <vector>

namespace pysa {

namespace {

// PyExc_* are data imports, incompatible with /DELAYLOAD:python3.dll - resolve
// the exception types from builtins at runtime (same trick as PySaModule.cpp).
PyObject *BuiltinExc(const char *name) {
    PyObject *b = PyImport_ImportModule("builtins");
    PyObject *e = b ? PyObject_GetAttrString(b, name) : nullptr;
    Py_XDECREF(b);
    return e;
}
PyObject *PyValueError() { static PyObject *e = BuiltinExc("ValueError"); return e; }
PyObject *PyRuntimeError() { static PyObject *e = BuiltinExc("RuntimeError"); return e; }

struct HookEntry {
    int id = -1;
    int argc = 0;
    int conv = 0;               // 0 cdecl, 1 stdcall, 2 thiscall
    bool active = false;
    void *thunk = nullptr;      // 16-byte exec stub carrying the id
    safetyhook::MidHook mid;
};

std::vector<std::unique_ptr<HookEntry>> g_hooks;
PyObject *g_dispatcher = nullptr;   // pysa._runtime._dispatch_hook (cached)

// Executable memory pool for id-thunks (16 bytes each).
unsigned char *g_pool = nullptr;
size_t g_poolUsed = 0;
const size_t POOL_SIZE = 0x10000;   // room for ~4000 hooks

}  // namespace

// cdecl so inline asm can call it by an unmangled name.
extern "C" void __cdecl PysaHookDispatch(int id, safetyhook::Context32 *ctx) {
    if (id < 0 || id >= static_cast<int>(g_hooks.size()))
        return;
    HookEntry *h = g_hooks[id].get();
    if (!h || !h->active || !Py_IsInitialized())
        return;

    PyGILState_STATE gil = PyGILState_Ensure();
    if (!g_dispatcher) {
        PyObject *rt = PyImport_ImportModule("pysa._runtime");
        if (rt) {
            g_dispatcher = PyObject_GetAttrString(rt, "_dispatch_hook");
            Py_DECREF(rt);
        }
        if (!g_dispatcher)
            PyErr_Clear();
    }
    if (g_dispatcher) {
        PyObject *r = PyObject_CallFunction(
            g_dispatcher, "(kk)",
            static_cast<unsigned long>(id),
            static_cast<unsigned long>(reinterpret_cast<uintptr_t>(ctx)));
        if (!r)
            PyErr_Print();
        else
            Py_DECREF(r);
    }
    PyGILState_Release(gil);
}

namespace {

// ecx = id, [esp+4] = Context32*. Forward to PysaHookDispatch(id, ctx).
__declspec(naked) void commonMid() {
    __asm {
        mov eax, [esp + 4]      // Context32*
        push eax                // arg2: ctx
        push ecx                // arg1: id
        call PysaHookDispatch
        add esp, 8
        ret
    }
}

void *AllocThunk(int id) {
    if (!g_pool) {
        g_pool = static_cast<unsigned char *>(
            VirtualAlloc(nullptr, POOL_SIZE, MEM_COMMIT | MEM_RESERVE,
                         PAGE_EXECUTE_READWRITE));
        if (!g_pool)
            return nullptr;
    }
    if (g_poolUsed + 16 > POOL_SIZE)
        return nullptr;
    unsigned char *t = g_pool + g_poolUsed;
    g_poolUsed += 16;

    // B9 <id>            mov ecx, id
    // E9 <rel32>         jmp commonMid
    t[0] = 0xB9;
    *reinterpret_cast<int *>(t + 1) = id;
    t[5] = 0xE9;
    intptr_t rel = reinterpret_cast<intptr_t>(&commonMid) - reinterpret_cast<intptr_t>(t + 10);
    *reinterpret_cast<int *>(t + 6) = static_cast<int>(rel);
    return t;
}

safetyhook::Context32 *CtxFrom(PyObject *arg) {
    unsigned long v = PyLong_AsUnsignedLongMask(arg);
    return reinterpret_cast<safetyhook::Context32 *>(static_cast<uintptr_t>(v));
}

uintptr_t *RegPtr(safetyhook::Context32 *c, const char *name) {
    struct { const char *n; uintptr_t *p; } regs[] = {
        {"eax", &c->eax}, {"ebx", &c->ebx}, {"ecx", &c->ecx}, {"edx", &c->edx},
        {"esi", &c->esi}, {"edi", &c->edi}, {"ebp", &c->ebp}, {"esp", &c->esp},
        {"eip", &c->eip}, {"eflags", &c->eflags},
    };
    for (auto &r : regs)
        if (strcmp(r.n, name) == 0)
            return r.p;
    return nullptr;
}

// ------------------------------------------------------------------ methods

PyObject *py_hook_install(PyObject *, PyObject *args) {
    unsigned long addr;
    int argc = 0, conv = 0;
    if (!PyArg_ParseTuple(args, "k|ii", &addr, &argc, &conv))
        return nullptr;
    if (!addr) {
        PyErr_SetString(PyValueError(), "hook_install: null address");
        return nullptr;
    }
    int id = static_cast<int>(g_hooks.size());
    auto entry = std::make_unique<HookEntry>();
    entry->id = id;
    entry->argc = argc;
    entry->conv = conv;
    entry->thunk = AllocThunk(id);
    if (!entry->thunk) {
        PyErr_SetString(PyRuntimeError(), "hook_install: thunk pool exhausted");
        return nullptr;
    }
    entry->mid = safetyhook::create_mid(
        reinterpret_cast<void *>(addr),
        reinterpret_cast<safetyhook::MidHookFn>(entry->thunk));
    if (!entry->mid) {
        PyErr_Format(PyRuntimeError(), "hook_install: safetyhook failed at 0x%08lX", addr);
        return nullptr;
    }
    entry->active = true;
    g_hooks.push_back(std::move(entry));
    return PyLong_FromLong(id);
}

PyObject *py_hook_remove(PyObject *, PyObject *args) {
    int id;
    if (!PyArg_ParseTuple(args, "i", &id))
        return nullptr;
    if (id >= 0 && id < static_cast<int>(g_hooks.size()) && g_hooks[id]) {
        g_hooks[id]->active = false;
        g_hooks[id]->mid = {};   // unhook (restores original bytes)
    }
    return Py_BuildValue("");
}

PyObject *py_hook_arg(PyObject *, PyObject *args) {
    PyObject *ctxObj;
    int i;
    if (!PyArg_ParseTuple(args, "Oi", &ctxObj, &i))
        return nullptr;
    safetyhook::Context32 *c = CtxFrom(ctxObj);
    unsigned int v = *reinterpret_cast<unsigned int *>(c->esp + 4 + i * 4);
    return PyLong_FromUnsignedLong(v);
}

PyObject *py_hook_set_arg(PyObject *, PyObject *args) {
    PyObject *ctxObj;
    int i;
    unsigned long v;
    if (!PyArg_ParseTuple(args, "Oik", &ctxObj, &i, &v))
        return nullptr;
    safetyhook::Context32 *c = CtxFrom(ctxObj);
    *reinterpret_cast<unsigned int *>(c->esp + 4 + i * 4) = v;
    return Py_BuildValue("");
}

PyObject *py_hook_argf(PyObject *, PyObject *args) {
    PyObject *ctxObj;
    int i;
    if (!PyArg_ParseTuple(args, "Oi", &ctxObj, &i))
        return nullptr;
    safetyhook::Context32 *c = CtxFrom(ctxObj);
    float f = *reinterpret_cast<float *>(c->esp + 4 + i * 4);
    return PyFloat_FromDouble(f);
}

PyObject *py_hook_set_argf(PyObject *, PyObject *args) {
    PyObject *ctxObj;
    int i;
    double v;
    if (!PyArg_ParseTuple(args, "Oid", &ctxObj, &i, &v))
        return nullptr;
    safetyhook::Context32 *c = CtxFrom(ctxObj);
    *reinterpret_cast<float *>(c->esp + 4 + i * 4) = static_cast<float>(v);
    return Py_BuildValue("");
}

PyObject *py_hook_reg(PyObject *, PyObject *args) {
    PyObject *ctxObj;
    const char *name;
    if (!PyArg_ParseTuple(args, "Os", &ctxObj, &name))
        return nullptr;
    uintptr_t *p = RegPtr(CtxFrom(ctxObj), name);
    if (!p) {
        PyErr_Format(PyValueError(), "hook_reg: unknown register %s", name);
        return nullptr;
    }
    return PyLong_FromUnsignedLong(static_cast<unsigned long>(*p));
}

PyObject *py_hook_set_reg(PyObject *, PyObject *args) {
    PyObject *ctxObj;
    const char *name;
    unsigned long v;
    if (!PyArg_ParseTuple(args, "Osk", &ctxObj, &name, &v))
        return nullptr;
    uintptr_t *p = RegPtr(CtxFrom(ctxObj), name);
    if (!p) {
        PyErr_Format(PyValueError(), "hook_set_reg: unknown register %s", name);
        return nullptr;
    }
    *p = v;
    return Py_BuildValue("");
}

// Skip the original function and force a return value (experimental).
PyObject *py_hook_block(PyObject *, PyObject *args) {
    PyObject *ctxObj;
    unsigned long retval;
    int argc, conv;
    if (!PyArg_ParseTuple(args, "Okii", &ctxObj, &retval, &argc, &conv))
        return nullptr;
    safetyhook::Context32 *c = CtxFrom(ctxObj);
    unsigned int retAddr = *reinterpret_cast<unsigned int *>(c->esp);
    c->eax = retval;
    c->eip = retAddr;
    // cdecl: caller cleans args (pop only return addr). stdcall/thiscall:
    // callee cleans, so also pop argc dwords.
    unsigned int pop = 4 + ((conv == 0) ? 0 : argc * 4);
    c->trampoline_esp = c->esp + pop;
    return Py_BuildValue("");
}

}  // namespace

// Exposed to PySaModule.cpp for method-table assembly.
PyMethodDef pysa_hook_methods[] = {
    {"hook_install", py_hook_install, METH_VARARGS,
     "hook_install(addr, argc=0, conv=0) -> id  (conv 0 cdecl,1 stdcall,2 thiscall)"},
    {"hook_remove", py_hook_remove, METH_VARARGS, "hook_remove(id)"},
    {"hook_arg", py_hook_arg, METH_VARARGS, "hook_arg(ctx, i) -> int stack arg"},
    {"hook_set_arg", py_hook_set_arg, METH_VARARGS, "hook_set_arg(ctx, i, value)"},
    {"hook_argf", py_hook_argf, METH_VARARGS, "hook_argf(ctx, i) -> float stack arg"},
    {"hook_set_argf", py_hook_set_argf, METH_VARARGS, "hook_set_argf(ctx, i, value)"},
    {"hook_reg", py_hook_reg, METH_VARARGS, "hook_reg(ctx, name) -> register value"},
    {"hook_set_reg", py_hook_set_reg, METH_VARARGS, "hook_set_reg(ctx, name, value)"},
    {"hook_block", py_hook_block, METH_VARARGS,
     "hook_block(ctx, retval, argc, conv) - skip original, force return (experimental)"},
    {nullptr, nullptr, 0, nullptr},
};

void ShutdownHooks() {
    for (auto &h : g_hooks) {
        if (h) {
            h->active = false;
            h->mid = {};
        }
    }
    g_hooks.clear();
    Py_XDECREF(g_dispatcher);
    g_dispatcher = nullptr;
    // g_pool intentionally left mapped: thunks may still be referenced by
    // in-flight unwinds; it is freed when the process exits.
}

}  // namespace pysa
