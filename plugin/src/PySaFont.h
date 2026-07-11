#pragma once

#include "PySaModule.h"

namespace pysa {

extern PyMethodDef pysa_font_methods[];

void FlushMonoFontQueue();
void MonoFontLost();
void MonoFontReset();
void ShutdownMonoFont();

}  // namespace pysa
