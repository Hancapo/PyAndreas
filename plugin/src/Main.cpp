// PyAndreas - Python scripting layer for GTA San Andreas.
// Plugin host: embeds CPython (32-bit, stable ABI) and forwards plugin-sdk
// events into the pure-Python 'pysa' package.
//
// Expected game-folder layout:
//   <game>\scripts\PyAndreas.SA.asi        (this plugin)
//   <game>\PyAndreas\python\               (32-bit embeddable Python: python3.dll, python3xx.dll, python3xx.zip)
//   <game>\PyAndreas\lib\pysa\             (the pysa package)
//   <game>\PyAndreas\scripts\*.py          (user scripts)
//   <game>\PyAndreas\PyAndreas.log         (created at runtime)

#include "PySaModule.h"

#include "plugin.h"
#include "CHud.h"

using namespace plugin;

namespace {

enum class State { NotStarted, Running, Failed };

State g_state = State::NotStarted;
PyObject *g_dispatch = nullptr;     // pysa._runtime.dispatch
bool g_pendingGameStart = false;
PyThreadState *g_savedState = nullptr;  // set when the GIL is released between frames

std::string GameDir() {
    char path[MAX_PATH];
    GetModuleFileNameA(nullptr, path, MAX_PATH);
    std::string s(path);
    size_t slash = s.find_last_of('\\');
    return slash == std::string::npos ? s : s.substr(0, slash);
}

bool DirExists(const std::string &dir) {
    DWORD attrs = GetFileAttributesA(dir.c_str());
    return attrs != INVALID_FILE_ATTRIBUTES && (attrs & FILE_ATTRIBUTE_DIRECTORY);
}

// Load the bundled 32-bit Python runtime (python3.dll + python3xx.dll).
// Falls back to a system-wide python3.dll if no bundled runtime exists.
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

// PyRun_SimpleString is not part of the stable ABI; this is its equivalent.
bool RunString(const char *code) {
    PyObject *main = PyImport_AddModule("__main__");  // borrowed
    if (!main)
        return false;
    PyObject *dict = PyModule_GetDict(main);  // borrowed
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
    CHud::SetHelpMessage("PyAndreas failed to start - see PyAndreas.log", true, false, false);
}

void InitPython() {
    std::string base = GameDir() + "\\PyAndreas";
    pysa::SetBaseDir(base);
    pysa::Log("PyAndreas starting (base: %s)", base.c_str());

    if (!DirExists(base)) {
        Fail("PyAndreas folder not found next to gta_sa.exe");
        return;
    }

    std::string pyHome = base + "\\python";
    bool bundled = DirExists(pyHome);
    if (!LoadPythonRuntime(pyHome, bundled)) {
        Fail(bundled ? "could not load python3.dll from PyAndreas\\python"
                     : "no PyAndreas\\python folder and no system-wide 32-bit python3.dll");
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

    // sys.path: our package dir + user scripts dir; route stdout/stderr into the log.
    char boot[1024];
    snprintf(boot, sizeof(boot),
             "import sys\n"
             "sys.path.insert(0, r'%s\\lib')\n"
             "sys.path.insert(0, r'%s\\scripts')\n"
             "sys.stdout = sys.stderr = open(r'%s\\PyAndreas.log', 'a', buffering=1, "
             "encoding='utf-8', errors='replace')\n",
             base.c_str(), base.c_str(), base.c_str());
    if (!RunString(boot)) {
        Fail("bootstrap path setup failed");
        return;
    }

    PyObject *runtime = PyImport_ImportModule("pysa._runtime");
    if (!runtime) {
        PyErr_Print();
        Fail("could not import pysa._runtime (is PyAndreas\\lib\\pysa in place?)");
        return;
    }
    g_dispatch = PyObject_GetAttrString(runtime, "dispatch");
    PyObject *r = PyObject_CallMethod(runtime, "bootstrap", "s", (base + "\\scripts").c_str());
    Py_DECREF(runtime);
    if (!r || !g_dispatch) {
        PyErr_Print();
        Fail("pysa._runtime.bootstrap() raised - see log");
        return;
    }
    Py_DECREF(r);

    g_state = State::Running;
    pysa::Log("PyAndreas ready (%s)", Py_GetVersion());

    // Release the GIL between frames so background Python threads (threading,
    // asyncio) can run. Every dispatch re-acquires it via PyGILState_Ensure.
    g_savedState = PyEval_SaveThread();
}

void Dispatch(const char *event) {
    if (g_state != State::Running || !g_dispatch)
        return;
    PyGILState_STATE gil = PyGILState_Ensure();
    PyObject *r = PyObject_CallFunction(g_dispatch, "(s)", event);
    if (!r)
        PyErr_Print();
    else
        Py_DECREF(r);
    PyGILState_Release(gil);
}

void DispatchPtr(const char *event, void *ptr) {
    if (g_state != State::Running || !g_dispatch)
        return;
    PyGILState_STATE gil = PyGILState_Ensure();
    PyObject *r = PyObject_CallFunction(g_dispatch, "(sk)", event,
                                        reinterpret_cast<unsigned long>(ptr));
    if (!r)
        PyErr_Print();
    else
        Py_DECREF(r);
    PyGILState_Release(gil);
}

class PyAndreas {
public:
    PyAndreas() {
        Events::gameProcessEvent += [] {
            if (g_state == State::NotStarted) {
                InitPython();
                if (g_state == State::Running)
                    g_pendingGameStart = true;
            }
            if (g_pendingGameStart) {
                g_pendingGameStart = false;
                Dispatch("game_start");
            }
            Dispatch("tick");
        };

        Events::drawingEvent += [] {
            Dispatch("draw");
            pysa::FlushRenderQueue();   // rects/sprites first
            pysa::FlushDrawQueue();     // text on top
        };

        Events::initScriptsEvent += [] {
            // New game / loaded save. Python may not be up yet on the very
            // first session - the tick handler covers that case.
            if (g_state == State::Running)
                Dispatch("game_start");
        };

        Events::vehicleCtorEvent += [](CVehicle *vehicle) { DispatchPtr("vehicle_created", vehicle); };
        Events::vehicleDtorEvent += [](CVehicle *vehicle) { DispatchPtr("vehicle_destroyed", vehicle); };
        Events::pedCtorEvent += [](CPed *ped) { DispatchPtr("ped_created", ped); };
        Events::pedDtorEvent += [](CPed *ped) { DispatchPtr("ped_destroyed", ped); };
        Events::objectCtorEvent += [](CObject *object) { DispatchPtr("object_created", object); };
        Events::objectDtorEvent += [](CObject *object) { DispatchPtr("object_destroyed", object); };

        Events::shutdownRwEvent += [] {
            if (g_state == State::Running) {
                Dispatch("shutdown");
                // Re-acquire the GIL we released after init, then tear down.
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
        };
    }
} g_pyAndreas;

}  // namespace
