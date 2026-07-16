// PyAndreas - Python scripting layer for GTA San Andreas (plugin-sdk based).
// Declarations shared between the embedded '_pysa' module and the plugin host.
#pragma once

#define PY_SSIZE_T_CLEAN
#define Py_LIMITED_API 0x03080000  // stable ABI: one binary works on any 32-bit Python >= 3.8
// Always link the release python3.lib, even in Debug builds of the plugin.
#ifdef _DEBUG
#undef _DEBUG
#include <Python.h>
#define _DEBUG
#else
#include <Python.h>
#endif

#include <string>
#include <vector>

// Registered as a builtin module before Py_Initialize().
extern "C" PyObject *PyInit__pysa(void);

namespace pysa {

// One queued 2D text draw, flushed on the game's drawing event.
struct DrawItem {
    std::string text;
    float x, y, sx, sy;
    unsigned int rgba;      // 0xRRGGBBAA
    int font;               // eFontStyle
    int align;              // 0 center, 1 left, 2 right
    int shadow;             // drop shadow offset (0 = off)
    unsigned int dropRgba;
    int proportional;
    float wrapx;
};

extern std::vector<DrawItem> g_drawQueue;

void Log(const char *fmt, ...);
void SetBaseDir(const std::string &dir);
const std::string &BaseDir();    // <game>\PyAndreas
void FlushDrawQueue();           // text; call from drawingEvent after dispatching "draw"
void FlushRenderQueue();         // rects/sprites; call before FlushDrawQueue
void ShutdownHooks();            // remove all function hooks (call before Py_Finalize)
void ResetEventGates();
bool SetEventEnabled(const char *name, bool enabled);
bool EventEnabled(const char *name);
void CaptureConsoleInputFrame(); // filter input for the active console or custom UI
bool ConsoleBlocksFrontendToggle(); // active UI owns the current menu-toggle input

// Method tables contributed by the render and hook translation units,
// concatenated into the _pysa module at init.
extern PyMethodDef pysa_render_methods[];
extern PyMethodDef pysa_font_methods[];
extern PyMethodDef pysa_hook_methods[];

}  // namespace pysa
