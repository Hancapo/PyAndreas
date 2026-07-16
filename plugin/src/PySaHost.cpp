// Embedded CPython lifetime, installation discovery and event dispatch.

#include "PySaHost.h"
#include "PySaMenu.h"
#include "PySaModule.h"

#include "CHud.h"

#include <windows.h>

#include <cstdio>
#include <string>
#include <vector>

namespace pysa::host {
namespace {

enum class State { NotStarted, Running, Failed };

State g_state = State::NotStarted;
PyObject *g_dispatch = nullptr;
bool g_pendingGameStart = false;
PyThreadState *g_savedState = nullptr;

std::string ParentDir(const std::string &path) {
    size_t slash = path.find_last_of("\\/");
    return slash == std::string::npos ? std::string() : path.substr(0, slash);
}

std::string ExeDir() {
    char path[MAX_PATH];
    GetModuleFileNameA(nullptr, path, MAX_PATH);
    return ParentDir(path);
}

std::string AsiDir() {
    HMODULE module = nullptr;
    if (!GetModuleHandleExA(
            GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
                GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
            reinterpret_cast<LPCSTR>(&AsiDir), &module))
        return {};
    char path[MAX_PATH];
    return GetModuleFileNameA(module, path, MAX_PATH) ? ParentDir(path)
                                                      : std::string();
}

bool DirExists(const std::string &dir) {
    DWORD attrs = GetFileAttributesA(dir.c_str());
    return attrs != INVALID_FILE_ATTRIBUTES &&
           (attrs & FILE_ATTRIBUTE_DIRECTORY);
}

bool LooksLikeBaseDir(const std::string &dir) {
    return DirExists(dir) &&
           (DirExists(dir + "\\lib") || DirExists(dir + "\\python") ||
            DirExists(dir + "\\scripts"));
}

std::string ResolveBaseDir() {
    std::vector<std::string> candidates;
    std::string asiDir = AsiDir();
    if (!asiDir.empty()) {
        std::string parent = ParentDir(asiDir);
        if (!parent.empty())
            candidates.push_back(parent + "\\PyAndreas");
        candidates.push_back(asiDir + "\\PyAndreas");
        candidates.push_back(asiDir);
    }
    candidates.push_back(ExeDir() + "\\PyAndreas");
    for (const std::string &candidate : candidates) {
        if (LooksLikeBaseDir(candidate))
            return candidate;
    }
    return ExeDir() + "\\PyAndreas";
}

bool LoadPythonRuntime(const std::string &pyHome, bool bundled) {
    if (bundled) {
        SetDllDirectoryA(pyHome.c_str());
        WIN32_FIND_DATAA fd;
        HANDLE find = FindFirstFileA((pyHome + "\\python3*.dll").c_str(), &fd);
        if (find != INVALID_HANDLE_VALUE) {
            do {
                LoadLibraryA((pyHome + "\\" + fd.cFileName).c_str());
            } while (FindNextFileA(find, &fd));
            FindClose(find);
        }
    } else {
        LoadLibraryA("python3.dll");
    }
    return GetModuleHandleA("python3.dll") != nullptr;
}

bool RunString(const char *code) {
    PyObject *main = PyImport_AddModule("__main__");
    if (!main)
        return false;
    PyObject *dict = PyModule_GetDict(main);
    PyObject *compiled = Py_CompileString(code, "<pyandreas>", Py_file_input);
    if (!compiled) {
        PyErr_Print();
        return false;
    }
    PyObject *result = PyEval_EvalCode(compiled, dict, dict);
    Py_DECREF(compiled);
    if (!result) {
        PyErr_Print();
        return false;
    }
    Py_DECREF(result);
    return true;
}

void Fail(const char *why) {
    g_state = State::Failed;
    pysa::Log("PyAndreas disabled: %s", why);
    CHud::SetHelpMessage("PyAndreas failed to start - see PyAndreas.log",
                         true, false, false);
}

void Initialize() {
    std::string base = ResolveBaseDir();
    pysa::SetBaseDir(base);
    if (!pysa::InstallInputCaptureHook())
        pysa::Log("PyAndreas input capture hook failed");
    pysa::menu::Install(base);
    pysa::Log("PyAndreas starting (base: %s)", base.c_str());

    if (!DirExists(base)) {
        Fail("could not locate PyAndreas data beside the ASI or gta_sa.exe");
        return;
    }

    std::string pyHome = base + "\\python";
    bool bundled = DirExists(pyHome);
    if (!LoadPythonRuntime(pyHome, bundled)) {
        Fail(bundled ? "could not load python3.dll from PyAndreas\\python"
                     : "no bundled or system-wide 32-bit Python runtime");
        return;
    }

    if (bundled)
        SetEnvironmentVariableA("PYTHONHOME", pyHome.c_str());
    SetEnvironmentVariableA("PYTHONDONTWRITEBYTECODE", "1");
    SetEnvironmentVariableA("PYTHONIOENCODING", "utf-8");
    if (PyImport_AppendInittab("_pysa", PyInit__pysa) < 0) {
        Fail("PyImport_AppendInittab failed");
        return;
    }
    Py_InitializeEx(0);
    if (!Py_IsInitialized()) {
        Fail("Py_Initialize failed");
        return;
    }

    char boot[2048];
    snprintf(boot, sizeof(boot),
             "import os, sys\n"
             "_pysa_archive = r'%s\\lib\\pysa.pyz'\n"
             "sys.path.insert(0, r'%s\\scripts')\n"
             "sys.path.insert(0, _pysa_archive if os.path.isfile(_pysa_archive) "
             "else r'%s\\lib')\n"
             "sys.stdout = sys.stderr = open(r'%s\\PyAndreas.log', 'a', "
             "buffering=1, encoding='utf-8', errors='replace')\n",
             base.c_str(), base.c_str(), base.c_str(), base.c_str());
    if (!RunString(boot)) {
        Fail("bootstrap path setup failed");
        return;
    }

    PyObject *runtime = PyImport_ImportModule("pysa._runtime");
    if (!runtime) {
        PyErr_Print();
        Fail("could not import pysa._runtime");
        return;
    }
    g_dispatch = PyObject_GetAttrString(runtime, "dispatch");
    PyObject *result = PyObject_CallMethod(
        runtime, "bootstrap", "s", (base + "\\scripts").c_str());
    Py_DECREF(runtime);
    if (!result || !g_dispatch) {
        Py_XDECREF(result);
        PyErr_Print();
        Fail("pysa._runtime.bootstrap() raised - see log");
        return;
    }
    Py_DECREF(result);

    g_state = State::Running;
    pysa::Log("PyAndreas ready (%s)", Py_GetVersion());
    g_savedState = PyEval_SaveThread();
}

}  // namespace

bool Running() { return g_state == State::Running; }

void ProcessTick() {
    if (g_state == State::NotStarted) {
        Initialize();
        if (Running())
            g_pendingGameStart = true;
    }
    if (g_pendingGameStart) {
        g_pendingGameStart = false;
        Dispatch("game_start");
    }
    Dispatch("tick");
}

void Dispatch(const char *event) {
    if (!Running() || !g_dispatch)
        return;
    PyGILState_STATE gil = PyGILState_Ensure();
    PyObject *result = PyObject_CallFunction(g_dispatch, "(s)", event);
    if (!result) PyErr_Print(); else Py_DECREF(result);
    PyGILState_Release(gil);
}

void DispatchInt(const char *event, int value) {
    if (!Running() || !g_dispatch)
        return;
    PyGILState_STATE gil = PyGILState_Ensure();
    PyObject *result = PyObject_CallFunction(g_dispatch, "(si)", event, value);
    if (!result) PyErr_Print(); else Py_DECREF(result);
    PyGILState_Release(gil);
}

void DispatchPtr(const char *event, void *ptr) {
    if (!Running() || !g_dispatch)
        return;
    PyGILState_STATE gil = PyGILState_Ensure();
    PyObject *result = PyObject_CallFunction(
        g_dispatch, "(sk)", event,
        reinterpret_cast<unsigned long>(ptr));
    if (!result) PyErr_Print(); else Py_DECREF(result);
    PyGILState_Release(gil);
}

void DispatchPtrInt(const char *event, void *ptr, int value) {
    if (!Running() || !g_dispatch)
        return;
    PyGILState_STATE gil = PyGILState_Ensure();
    PyObject *arg = Py_BuildValue(
        "(ki)", reinterpret_cast<unsigned long>(ptr), value);
    PyObject *result = arg ? PyObject_CallFunction(g_dispatch, "(sO)", event, arg)
                           : nullptr;
    Py_XDECREF(arg);
    if (!result) PyErr_Print(); else Py_DECREF(result);
    PyGILState_Release(gil);
}

void Shutdown() {
    if (!Running())
        return;
    Dispatch("shutdown");
    pysa::ResetEventGates();
    if (g_savedState) {
        PyEval_RestoreThread(g_savedState);
        g_savedState = nullptr;
    }
    pysa::ShutdownHooks();
    Py_XDECREF(g_dispatch);
    g_dispatch = nullptr;
    Py_FinalizeEx();
    g_state = State::NotStarted;
    pysa::Log("PyAndreas shut down");
}

}  // namespace pysa::host
