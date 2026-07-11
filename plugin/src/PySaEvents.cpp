// plugin-sdk event wiring and high-frequency native subscription gates.

#include "PySaEvents.h"
#include "PySaFont.h"
#include "PySaModule.h"

#include "plugin.h"

#include <cstring>

using namespace plugin;

namespace pysa {
namespace {

struct EventGates {
    bool hudDraw = false;
    bool radarDraw = false;
    bool afterFadeDraw = false;
    bool menuDraw = false;
    bool vehicleRender = false;
    bool pedRender = false;
    bool objectRender = false;
} g_gates;

}  // namespace

bool SetEventEnabled(const char *name, bool enabled) {
    if (!strcmp(name, "hud_draw")) g_gates.hudDraw = enabled;
    else if (!strcmp(name, "radar_draw")) g_gates.radarDraw = enabled;
    else if (!strcmp(name, "after_fade_draw")) g_gates.afterFadeDraw = enabled;
    else if (!strcmp(name, "menu_draw")) g_gates.menuDraw = enabled;
    else if (!strcmp(name, "vehicle_render")) g_gates.vehicleRender = enabled;
    else if (!strcmp(name, "ped_render")) g_gates.pedRender = enabled;
    else if (!strcmp(name, "object_render")) g_gates.objectRender = enabled;
    else return false;
    return true;
}

bool EventEnabled(const char *name) {
    if (!strcmp(name, "hud_draw")) return g_gates.hudDraw;
    if (!strcmp(name, "radar_draw")) return g_gates.radarDraw;
    if (!strcmp(name, "after_fade_draw")) return g_gates.afterFadeDraw;
    if (!strcmp(name, "menu_draw")) return g_gates.menuDraw;
    if (!strcmp(name, "vehicle_render")) return g_gates.vehicleRender;
    if (!strcmp(name, "ped_render")) return g_gates.pedRender;
    if (!strcmp(name, "object_render")) return g_gates.objectRender;
    return false;
}

void ResetEventGates() { g_gates = EventGates{}; }

namespace host {

void RegisterEvents() {
    Events::gameProcessEvent.before += [] { CaptureConsoleInputFrame(); };
    Events::gameProcessEvent += [] { ProcessTick(); };

    Events::drawingEvent += [] {
        Dispatch("draw");
        FlushRenderQueue();
        FlushMonoFontQueue();
        FlushDrawQueue();
    };
    Events::drawHudEvent += [] {
        if (EventEnabled("hud_draw")) Dispatch("hud_draw");
    };
    Events::drawRadarEvent += [] {
        if (EventEnabled("radar_draw")) Dispatch("radar_draw");
    };
    Events::drawAfterFadeEvent += [] {
        if (EventEnabled("after_fade_draw")) Dispatch("after_fade_draw");
        Dispatch("developer_console_draw");
        FlushRenderQueue();
        FlushMonoFontQueue();
        FlushDrawQueue();
    };
    Events::menuDrawingEvent += [] {
        Dispatch("frontend_open");
        if (EventEnabled("menu_draw")) Dispatch("menu_draw");
    };

    Events::vehicleRenderEvent += [](CVehicle *value) {
        if (EventEnabled("vehicle_render")) DispatchPtr("vehicle_render", value);
    };
    Events::pedRenderEvent += [](CPed *value) {
        if (EventEnabled("ped_render")) DispatchPtr("ped_render", value);
    };
    Events::objectRenderEvent += [](CObject *value) {
        if (EventEnabled("object_render")) DispatchPtr("object_render", value);
    };

    Events::initScriptsEvent += [] {
        if (Running()) Dispatch("game_start");
    };
    Events::restartGameEvent += [] { Dispatch("game_restart"); };
    Events::reInitGameEvent += [] { Dispatch("game_reinit"); };
    Events::initRwEvent += [] { Dispatch("render_init"); };
    Events::initPoolsEvent += [] { Dispatch("pools_init"); };
    Events::shutdownPoolsEvent += [] { Dispatch("pools_shutdown"); };
    Events::d3dLostEvent += [] {
        MonoFontLost();
        Dispatch("device_lost");
    };
    Events::d3dResetEvent += [] {
        MonoFontReset();
        Dispatch("device_reset");
    };

    Events::vehicleCtorEvent += [](CVehicle *value) {
        DispatchPtr("vehicle_created", value);
    };
    Events::vehicleDtorEvent += [](CVehicle *value) {
        DispatchPtr("vehicle_destroyed", value);
    };
    Events::pedCtorEvent += [](CPed *value) {
        DispatchPtr("ped_created", value);
    };
    Events::pedDtorEvent += [](CPed *value) {
        DispatchPtr("ped_destroyed", value);
    };
    Events::objectCtorEvent += [](CObject *value) {
        DispatchPtr("object_created", value);
    };
    Events::objectDtorEvent += [](CObject *value) {
        DispatchPtr("object_destroyed", value);
    };
    Events::vehicleSetModelEvent += [](CVehicle *value, int model) {
        DispatchPtrInt("vehicle_model_changed", value, model);
    };
    Events::pedSetModelEvent += [](CPed *value, int model) {
        DispatchPtrInt("ped_model_changed", value, model);
    };

    Events::shutdownRwEvent += [] {
        ShutdownMonoFont();
        Shutdown();
    };
}

}  // namespace host
}  // namespace pysa
