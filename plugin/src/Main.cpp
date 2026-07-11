// PyAndreas ASI entry point. Native responsibilities live in focused units;
// this file only composes the plugin at load time.

#include "PySaEvents.h"

namespace {

class PyAndreasPlugin {
public:
    PyAndreasPlugin() { pysa::host::RegisterEvents(); }
} g_pyAndreasPlugin;

}  // namespace
