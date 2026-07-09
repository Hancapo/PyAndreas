// PyAndreas - 2D rendering (rectangles + textured sprites).
//
// Draw calls from Python are queued and flushed on the game's drawing event
// (before the text queue, so HUD text sits on top). Textures are PNG files
// loaded through plugin-sdk's SpriteLoader/CTxdStore.

#include "PySaModule.h"

#include "plugin.h"
#include "CSprite2d.h"
#include "CRect.h"
#include "SpriteLoader.h"

#include <string>
#include <unordered_map>
#include <vector>

using namespace plugin;

namespace pysa {

namespace {

struct RenderItem {
    int type;               // 0 = rect, 1 = sprite
    float x1, y1, x2, y2;
    unsigned int rgba;      // 0xRRGGBBAA
    std::string sprite;     // texture name (type 1)
};

std::vector<RenderItem> g_renderQueue;
SpriteLoader g_sprites;
bool g_spritesReady = false;

CRGBA Unpack(unsigned int rgba) {
    return CRGBA((rgba >> 24) & 0xFF, (rgba >> 16) & 0xFF, (rgba >> 8) & 0xFF, rgba & 0xFF);
}

PyObject *py_draw_rect(PyObject *, PyObject *args) {
    RenderItem it{};
    it.type = 0;
    if (!PyArg_ParseTuple(args, "ffffI", &it.x1, &it.y1, &it.x2, &it.y2, &it.rgba))
        return nullptr;
    g_renderQueue.push_back(std::move(it));
    return Py_BuildValue("");
}

PyObject *py_draw_sprite(PyObject *, PyObject *args) {
    RenderItem it{};
    it.type = 1;
    const char *name;
    if (!PyArg_ParseTuple(args, "sffffI", &name, &it.x1, &it.y1, &it.x2, &it.y2, &it.rgba))
        return nullptr;
    it.sprite = name;
    g_renderQueue.push_back(std::move(it));
    return Py_BuildValue("");
}

// load_texture(path, name) -> bool. Loads a single PNG file; `name` is the
// key used later by draw_sprite. Must be called after RW is up (game_start).
PyObject *py_load_texture(PyObject *, PyObject *args) {
    const char *path;
    const char *name = nullptr;
    if (!PyArg_ParseTuple(args, "s|s", &path, &name))
        return nullptr;
    bool ok = g_sprites.LoadSpriteFromFolder(path) != nullptr;
    g_spritesReady = g_spritesReady || ok;
    (void)name;  // SpriteLoader keys by the file's own base name
    return PyBool_FromLong(ok ? 1 : 0);
}

// load_textures(folder) -> bool. Loads every PNG in a folder.
PyObject *py_load_textures(PyObject *, PyObject *args) {
    const char *folder;
    if (!PyArg_ParseTuple(args, "s", &folder))
        return nullptr;
    bool ok = g_sprites.LoadAllSpritesFromFolder(folder);
    g_spritesReady = g_spritesReady || ok;
    return PyBool_FromLong(ok ? 1 : 0);
}

}  // namespace

PyMethodDef pysa_render_methods[] = {
    {"draw_rect", py_draw_rect, METH_VARARGS,
     "draw_rect(x1, y1, x2, y2, rgba) - queue a filled rectangle for this frame"},
    {"draw_sprite", py_draw_sprite, METH_VARARGS,
     "draw_sprite(name, x1, y1, x2, y2, rgba) - queue a textured rectangle"},
    {"load_texture", py_load_texture, METH_VARARGS,
     "load_texture(png_path) -> bool  (call from on_game_start; keyed by file name)"},
    {"load_textures", py_load_textures, METH_VARARGS,
     "load_textures(folder) -> bool  (loads every .png in the folder)"},
    {nullptr, nullptr, 0, nullptr},
};

void FlushRenderQueue() {
    if (g_renderQueue.empty())
        return;
    for (const RenderItem &it : g_renderQueue) {
        CRect rect(it.x1, it.y1, it.x2, it.y2);
        if (it.type == 0) {
            CSprite2d::DrawRect(rect, Unpack(it.rgba));
        } else if (g_spritesReady) {
            CSprite2d sprite = g_sprites.GetSprite(it.sprite);
            if (sprite.m_pTexture) {
                sprite.SetRenderState();
                sprite.Draw(rect, Unpack(it.rgba));
            }
        }
    }
    g_renderQueue.clear();
}

}  // namespace pysa
