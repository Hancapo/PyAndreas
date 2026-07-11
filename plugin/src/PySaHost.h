#pragma once

namespace pysa::host {

void RegisterEvents();
void ProcessTick();
void Shutdown();
bool Running();

void Dispatch(const char *event);
void DispatchInt(const char *event, int value);
void DispatchPtr(const char *event, void *ptr);
void DispatchPtrInt(const char *event, void *ptr, int value);

}  // namespace pysa::host
