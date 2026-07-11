// Direct TrueType monospace rendering for the developer console.
//
// The renderer loads an actual .ttf with AddFontResourceEx and creates D3DX
// font atlases on GTA's D3D9 device. It never routes console text through
// GTA's proportional bitmap-font tables.

#include "PySaFont.h"

#include "plugin.h"
#include "dxsdk/d3dx9core.h"

#include <windows.h>

#include <algorithm>
#include <cmath>
#include <map>
#include <string>
#include <vector>

namespace pysa {
namespace {

using CreateFontFn = HRESULT (WINAPI *)(
    LPDIRECT3DDEVICE9, INT, UINT, UINT, UINT, BOOL, DWORD, DWORD, DWORD,
    DWORD, LPCWSTR, LPD3DXFONT *);

struct MonoTextItem {
    std::wstring text;
    float x;
    float y;
    int height;
    unsigned int rgba;
    bool clipped;
    RECT clip;
};

std::vector<MonoTextItem> g_queue;
std::map<int, LPD3DXFONT> g_fonts;
HMODULE g_d3dx = nullptr;
CreateFontFn g_createFont = nullptr;
std::wstring g_fontPath;
std::wstring g_fontFace = L"Consolas";
bool g_fontResourceAdded = false;
bool g_configLoaded = false;

std::wstring Wide(const std::string &value) {
    if (value.empty()) return {};
    int count = MultiByteToWideChar(CP_UTF8, 0, value.c_str(), -1,
                                    nullptr, 0);
    if (count <= 0) return {};
    std::wstring result(static_cast<size_t>(count), L'\0');
    MultiByteToWideChar(CP_UTF8, 0, value.c_str(), -1, result.data(), count);
    result.pop_back();
    return result;
}

std::wstring Utf8(const char *value) {
    return Wide(value ? std::string(value) : std::string());
}

void LoadConfig() {
    if (g_configLoaded) return;
    g_configLoaded = true;

    wchar_t windows[MAX_PATH]{};
    GetWindowsDirectoryW(windows, MAX_PATH);
    g_fontPath = std::wstring(windows) + L"\\Fonts\\consola.ttf";

    std::wstring ini = Wide(BaseDir()) + L"\\PyAndreas.ini";
    wchar_t path[1024]{};
    wchar_t face[LF_FACESIZE]{};
    GetPrivateProfileStringW(L"PyAndreas", L"ConsoleFont", g_fontPath.c_str(),
                             path, 1024, ini.c_str());
    GetPrivateProfileStringW(L"PyAndreas", L"ConsoleFontFace", L"Consolas",
                             face, LF_FACESIZE, ini.c_str());
    wchar_t expanded[1024]{};
    ExpandEnvironmentStringsW(path, expanded, 1024);
    g_fontPath = expanded;
    if (!(g_fontPath.size() > 1 && g_fontPath[1] == L':') &&
            !(g_fontPath.size() > 1 && g_fontPath[0] == L'\\' &&
              g_fontPath[1] == L'\\'))
        g_fontPath = Wide(BaseDir()) + L"\\" + g_fontPath;
    g_fontFace = face;
    if (AddFontResourceExW(g_fontPath.c_str(), FR_PRIVATE, nullptr) > 0)
        g_fontResourceAdded = true;
}

bool LoadD3dx() {
    if (g_createFont) return true;
    for (int version = 43; version >= 24 && !g_d3dx; --version) {
        wchar_t name[32];
        swprintf_s(name, L"d3dx9_%d.dll", version);
        g_d3dx = LoadLibraryW(name);
    }
    if (!g_d3dx) {
        Log("Console font renderer: no D3DX9 runtime found");
        return false;
    }
    g_createFont = reinterpret_cast<CreateFontFn>(
        GetProcAddress(g_d3dx, "D3DXCreateFontW"));
    return g_createFont != nullptr;
}

LPD3DXFONT Font(int height) {
    height = std::max(8, height);
    auto found = g_fonts.find(height);
    if (found != g_fonts.end()) return found->second;
    LoadConfig();
    if (!LoadD3dx()) return nullptr;
    auto *device = static_cast<LPDIRECT3DDEVICE9>(RwD3D9GetCurrentD3DDevice());
    if (!device) return nullptr;

    LPD3DXFONT font = nullptr;
    HRESULT result = g_createFont(
        device, height, 0, FW_NORMAL, 1, FALSE, DEFAULT_CHARSET,
        OUT_TT_PRECIS, ANTIALIASED_QUALITY, FIXED_PITCH | FF_MODERN,
        g_fontFace.c_str(), &font);
    if (FAILED(result) || !font) {
        Log("Console font renderer: failed to create '%ls' at %dpx",
            g_fontFace.c_str(), height);
        return nullptr;
    }
    g_fonts.emplace(height, font);
    return font;
}

float Width(const std::wstring &text, int height) {
    LPD3DXFONT font = Font(height);
    if (!font || text.empty()) return 0.0f;
    // DrawText/DT_CALCRECT discards trailing whitespace. A real monospace
    // caret needs every codepoint—including spaces—to occupy one cell.
    TEXTMETRICW metrics{};
    if (!font->GetTextMetricsW(&metrics)) return 0.0f;
    return static_cast<float>(text.size() * metrics.tmAveCharWidth);
}

PyObject *py_draw_mono_text(PyObject *, PyObject *args) {
    const char *text;
    float x, y, height;
    unsigned int rgba;
    float clipLeft = 0.0f, clipTop = 0.0f, clipRight = 0.0f, clipBottom = 0.0f;
    if (!PyArg_ParseTuple(args, "sfffI|ffff", &text, &x, &y, &height, &rgba,
                          &clipLeft, &clipTop, &clipRight, &clipBottom))
        return nullptr;
    int pixels = std::max(8, static_cast<int>(std::lround(height)));
    if (!Font(pixels)) return PyBool_FromLong(0);
    bool clipped = PyTuple_Size(args) >= 9;
    RECT clip{static_cast<LONG>(clipLeft), static_cast<LONG>(clipTop),
              static_cast<LONG>(clipRight), static_cast<LONG>(clipBottom)};
    g_queue.push_back({Utf8(text), x, y, pixels, rgba, clipped, clip});
    return PyBool_FromLong(1);
}

PyObject *py_mono_text_width(PyObject *, PyObject *args) {
    const char *text;
    float height;
    if (!PyArg_ParseTuple(args, "sf", &text, &height))
        return nullptr;
    return PyFloat_FromDouble(Width(
        Utf8(text), std::max(8, static_cast<int>(std::lround(height)))));
}

}  // namespace

PyMethodDef pysa_font_methods[] = {
    {"draw_mono_text", py_draw_mono_text, METH_VARARGS,
     "draw_mono_text(text, x, y, pixel_height, rgba) -> bool"},
    {"mono_text_width", py_mono_text_width, METH_VARARGS,
     "mono_text_width(text, pixel_height) -> pixels"},
    {nullptr, nullptr, 0, nullptr},
};

void FlushMonoFontQueue() {
    auto *device = static_cast<LPDIRECT3DDEVICE9>(RwD3D9GetCurrentD3DDevice());
    for (const MonoTextItem &item : g_queue) {
        LPD3DXFONT font = Font(item.height);
        if (!font) continue;
        RECT rect{static_cast<LONG>(item.x), static_cast<LONG>(item.y), 0, 0};
        unsigned int color = ((item.rgba & 0xFF) << 24) | (item.rgba >> 8);
        DWORD previousScissor = FALSE;
        RECT previousRect{};
        if (item.clipped && device) {
            device->GetRenderState(D3DRS_SCISSORTESTENABLE, &previousScissor);
            device->GetScissorRect(&previousRect);
            device->SetScissorRect(&item.clip);
            device->SetRenderState(D3DRS_SCISSORTESTENABLE, TRUE);
        }
        font->DrawTextW(nullptr, item.text.c_str(), -1, &rect,
                        DT_LEFT | DT_TOP | DT_NOCLIP | DT_SINGLELINE, color);
        if (item.clipped && device) {
            device->SetScissorRect(&previousRect);
            device->SetRenderState(D3DRS_SCISSORTESTENABLE, previousScissor);
        }
    }
    g_queue.clear();
}

void MonoFontLost() {
    for (auto &[_, font] : g_fonts) font->OnLostDevice();
}

void MonoFontReset() {
    for (auto &[_, font] : g_fonts) font->OnResetDevice();
}

void ShutdownMonoFont() {
    g_queue.clear();
    for (auto &[_, font] : g_fonts) font->Release();
    g_fonts.clear();
    if (g_fontResourceAdded)
        RemoveFontResourceExW(g_fontPath.c_str(), FR_PRIVATE, nullptr);
    g_fontResourceAdded = false;
    g_configLoaded = false;
    g_fontPath.clear();
    if (g_d3dx) FreeLibrary(g_d3dx);
    g_d3dx = nullptr;
    g_createFont = nullptr;
}

}  // namespace pysa
