// Native GTA Options > PyAndreas submenu and DeveloperMode persistence.

#include "PySaMenu.h"
#include "PySaHost.h"
#include "PySaModule.h"

#include "CMenuManager.h"
#include "CText.h"
#include <safetyhook.hpp>
#include <windows.h>

#include <cstring>

namespace pysa::menu {
namespace {

std::string g_baseDir;
bool g_developerMode = false;
bool g_installed = false;
int g_settingsPage = -1;
SafetyHookInline g_textHook;
SafetyHookInline g_actionHook;
SafetyHookInline g_switchMenuHook;

void SetName(char (&destination)[8], const char *name) {
    memset(destination, 0, sizeof(destination));
    strncpy(destination, name, sizeof(destination) - 1);
}

void Save() {
    WritePrivateProfileStringA("PyAndreas", "DeveloperMode",
                               g_developerMode ? "1" : "0",
                               (g_baseDir + "\\PyAndreas.ini").c_str());
}

const char *__fastcall TextHook(CText *self, void *, const char *key) {
    if (!strcmp(key, "PYSAMNU") || !strcmp(key, "PYSATTL"))
        return "PYANDREAS";
    if (!strcmp(key, "PYSADEV"))
        return g_developerMode ? "DEVELOPER MODE: ON"
                               : "DEVELOPER MODE: OFF";
    return g_textHook.thiscall<const char *>(self, key);
}

char __fastcall ActionHook(CMenuManager *self, void *, char input, char enter) {
    if (self->m_nCurrentMenuPage == g_settingsPage &&
            self->m_nCurrentMenuEntry == 0 && enter) {
        g_developerMode = !g_developerMode;
        Save();
        host::DispatchInt("developer_mode_changed", g_developerMode ? 1 : 0);
        return 1;
    }
    return g_actionHook.thiscall<char>(self, input, enter);
}

void __fastcall SwitchMenuHook(CMenuManager *self, void *) {
    if (pysa::ConsoleBlocksFrontendToggle())
        return;
    g_switchMenuHook.thiscall<void>(self);
}

CMenuScreen *ActiveScreens() {
    CMenuScreen *screens = *reinterpret_cast<CMenuScreen **>(0x579568);
    return screens ? screens : aScreens;
}

int FindPage(CMenuScreen *screens) {
    if (screens != aScreens) {
        int lastUsed = NUM_MENU_PAGES - 1;
        for (int page = NUM_MENU_PAGES; page < 127; ++page) {
            if (!strncmp(screens[page].m_ScreenName, "PYSATTL", 8))
                return page;
            if (screens[page].m_ScreenName[0] != '\0')
                lastUsed = page;
        }
        return lastUsed + 1 < 127 ? lastUsed + 1 : -1;
    }
    CMenuScreen &empty = screens[MENUPAGE_EMPTY];
    return (empty.m_ScreenName[0] == '\0' ||
            !strncmp(empty.m_ScreenName, "PYSATTL", 8))
        ? MENUPAGE_EMPTY : -1;
}

int InsertOptionsLink(CMenuScreen &options) {
    int freeEntry = -1;
    int insertEntry = -1;
    for (int i = 0; i < NUM_ENTRIES; ++i) {
        if (!strncmp(options.m_aEntries[i].m_EntryName, "PYSAMNU", 8))
            return i;
        if (freeEntry < 0 && options.m_aEntries[i].m_EntryName[0] == '\0')
            freeEntry = i;
        if (!strncmp(options.m_aEntries[i].m_EntryName, "FEDS_TB", 8))
            insertEntry = i;
    }
    if (freeEntry < 0)
        return -1;
    if (insertEntry < 0)
        return freeEntry;
    if (freeEntry < insertEntry)
        return -1;
    memmove(&options.m_aEntries[insertEntry + 1],
            &options.m_aEntries[insertEntry],
            sizeof(CMenuScreen::CMenuEntry) * (freeEntry - insertEntry));
    return insertEntry;
}

}  // namespace

void Install(const std::string &baseDir) {
    if (g_installed)
        return;
    g_baseDir = baseDir;
    g_developerMode = GetPrivateProfileIntA(
        "PyAndreas", "DeveloperMode", 0,
        (g_baseDir + "\\PyAndreas.ini").c_str()) != 0;

    CMenuScreen *screens = ActiveScreens();
    g_settingsPage = FindPage(screens);
    int parentEntry = InsertOptionsLink(screens[MENUPAGE_OPTIONS]);
    if (g_settingsPage < 0 || parentEntry < 0) {
        pysa::Log("PyAndreas submenu disabled: no safe menu page or entry");
        return;
    }

    auto &link = screens[MENUPAGE_OPTIONS].m_aEntries[parentEntry];
    memset(&link, 0, sizeof(link));
    link.m_nAction = MENUACTION_CHANGEMENU;
    SetName(link.m_EntryName, "PYSAMNU");
    link.m_nSaveSlot = MENUENTRY_BUTTON;
    link.m_nTargetMenu = static_cast<char>(g_settingsPage);
    link.m_nAlign = 3;

    CMenuScreen &settings = screens[g_settingsPage];
    memset(&settings, 0, sizeof(settings));
    SetName(settings.m_ScreenName, "PYSATTL");
    settings.m_nPreviousPage = MENUPAGE_OPTIONS;
    settings.m_nParentEntry = static_cast<char>(parentEntry);

    auto &toggle = settings.m_aEntries[0];
    toggle.m_nAction = MENUACTION_YES;
    SetName(toggle.m_EntryName, "PYSADEV");
    toggle.m_nSaveSlot = MENUENTRY_BUTTON;
    toggle.m_nTargetMenu = MENUPAGE_NONE;
    toggle.m_nX = 60;
    toggle.m_nY = 140;
    toggle.m_nAlign = 1;

    auto &back = settings.m_aEntries[1];
    back.m_nAction = MENUACTION_BACK;
    SetName(back.m_EntryName, "FEDS_TB");
    back.m_nSaveSlot = MENUENTRY_BUTTON;
    back.m_nTargetMenu = MENUPAGE_NONE;
    back.m_nX = 490;
    back.m_nY = 380;
    back.m_nAlign = 1;

    g_textHook = safetyhook::create_inline(
        reinterpret_cast<void *>(0x6A0050), reinterpret_cast<void *>(&TextHook));
    g_actionHook = safetyhook::create_inline(
        reinterpret_cast<void *>(0x57CD50), reinterpret_cast<void *>(&ActionHook));
    g_switchMenuHook = safetyhook::create_inline(
        reinterpret_cast<void *>(0x576B70),
        reinterpret_cast<void *>(&SwitchMenuHook));
    if (!g_textHook || !g_actionHook || !g_switchMenuHook) {
        pysa::Log("PyAndreas Options submenu hooks failed");
        return;
    }
    g_installed = true;
    pysa::Log("PyAndreas Options submenu installed (page=%d, DeveloperMode=%s)",
              g_settingsPage, g_developerMode ? "on" : "off");
}

}  // namespace pysa::menu
