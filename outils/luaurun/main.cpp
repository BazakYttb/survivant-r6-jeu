// Minimal Luau runner: luaurun [--check] file.lua [more files run in the same state]
#include "lua.h"
#include "lualib.h"
#include "luacode.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <fstream>
#include <sstream>

static std::string readFile(const char* p) {
    std::ifstream f(p, std::ios::binary);
    if (!f) { fprintf(stderr, "cannot open %s\n", p); exit(2); }
    std::stringstream ss; ss << f.rdbuf(); return ss.str();
}

static int l_readfile(lua_State* L) {
    const char* p = luaL_checkstring(L, 1);
    std::ifstream f(p, std::ios::binary);
    if (!f) { lua_pushnil(L); lua_pushfstring(L, "cannot open %s", p); return 2; }
    std::stringstream ss; ss << f.rdbuf(); std::string s = ss.str();
    lua_pushlstring(L, s.data(), s.size());
    return 1;
}

static int l_loadstring(lua_State* L) {
    size_t len = 0;
    const char* src = luaL_checklstring(L, 1, &len);
    const char* name = luaL_optstring(L, 2, "=loadstring");
    lua_CompileOptions opts = {};
    opts.optimizationLevel = 1;
    opts.debugLevel = 2;
    size_t bcSize = 0;
    char* bc = luau_compile(src, len, &opts, &bcSize);
    int r = luau_load(L, name, bc, bcSize, 0);
    free(bc);
    if (r == 0) return 1;
    lua_pushnil(L);
    lua_insert(L, -2);
    return 2;
}

int main(int argc, char** argv) {
    bool checkOnly = false;
    int first = 1;
    if (argc > 1 && strcmp(argv[1], "--check") == 0) { checkOnly = true; first = 2; }
    if (first >= argc) { fprintf(stderr, "usage: luaurun [--check] file.lua ...\n"); return 2; }
    lua_State* L = luaL_newstate();
    luaL_openlibs(L);
    lua_pushcfunction(L, l_readfile, "readfile"); lua_setglobal(L, "readfile");
    lua_pushcfunction(L, l_loadstring, "loadstring"); lua_setglobal(L, "loadstring");
    int rc = 0;
    for (int i = first; i < argc; ++i) {
        std::string src = readFile(argv[i]);
        size_t bcSize = 0;
        lua_CompileOptions opts = {};
        opts.optimizationLevel = 1;
        opts.debugLevel = 2;
        char* bc = luau_compile(src.data(), src.size(), &opts, &bcSize);
        std::string chunk = std::string("@") + argv[i];
        int lr = luau_load(L, chunk.c_str(), bc, bcSize, 0);
        free(bc);
        if (lr != 0) {
            fprintf(stderr, "COMPILE ERROR %s: %s\n", argv[i], lua_tostring(L, -1));
            lua_pop(L, 1);
            rc = 1;
            continue;
        }
        if (checkOnly) { printf("OK (syntax) %s\n", argv[i]); lua_pop(L, 1); continue; }
        // traceback via debug.traceback
        lua_getglobal(L, "debug"); lua_getfield(L, -1, "traceback"); lua_remove(L, -2);
        lua_insert(L, -2);
        int base = lua_gettop(L) - 1;
        int r = lua_pcall(L, 0, 0, base);
        if (r != 0) {
            fprintf(stderr, "RUNTIME ERROR %s: %s\n", argv[i], lua_tostring(L, -1));
            lua_pop(L, 1);
            rc = 1;
        }
        lua_pop(L, 1); // traceback fn
    }
    lua_close(L);
    return rc;
}
