/* hwr2_capture.dll - in-process frame capture for GameLab (lab mode, hidden desktop).

   PrintWindow returns a blank image for HWR2's OpenGL window on a hidden desktop (no
   compositor). This DLL is injected into the GameLab copy of HWR2.exe by the launcher and
   replaces the exe's import of gdi32!SwapBuffers (bgfx's WGL backend presents with it).
   On each swap it looks for a request file in the working directory; when present it
   reads the back buffer with glReadPixels, writes a BMP to the path named in the request
   (via a .tmp + rename) and deletes the request. Nothing else is touched, and GL state
   it changes (read framebuffer, pack buffer, pack alignment, read buffer) is restored.

   Request file:  gamelab_capture.req   (one line: absolute output path ending in .bmp)
   Log lines:     gamelab_capture.log   (appended; injection, each capture, errors)

   It also replaces the exe's import of shell32!SHGetKnownFolderPath: when the launcher sets
   GAMELAB_LOCALAPPDATA, FOLDERID_LocalAppData resolves to that directory, so the game's own
   save backups (<LocalAppData>/HeroesofHammerwatch2/save_backups) land in the GameLab game
   dir instead of the user's profile. The game resolves the folder through the shell API, not
   the LOCALAPPDATA variable, so the hook must be in before the first call: the launcher
   starts HWR2.exe suspended, injects, then resumes. Every folder request is logged.

   It also hooks SDL2.dll's window-activation imports (see "focus" below): logged always,
   made non-activating in watch mode (GAMELAB_NO_ACTIVATE=1).

   With GAMELAB_SHIM_INPUT=1 (watch mode) it also hooks the exe's SDL_PollEvent and feeds it
   GameLab's keys from a mailslot (see "input" below), so they never depend on window focus.
   Those hooks also hide the user's mouse and focus changes from the game; a hand-off message
   on the same mailslot ("hand-off" below) turns that off when a scenario gives the game to
   the human, so from then on the game sees its input exactly as it would unhooked.

   Build: gcc -shared -O2 -Wall -o ../bin/hwr2_capture.dll hwr2_capture.c -lgdi32 -lopengl32 -lole32
*/
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <objbase.h>

typedef void (WINAPI *PFNGLREADPIXELS)(int, int, int, int, unsigned, unsigned, void *);
typedef void (WINAPI *PFNGLGETINTEGERV)(unsigned, int *);
typedef void (WINAPI *PFNGLPIXELSTOREI)(unsigned, int);
typedef void (WINAPI *PFNGLREADBUFFER)(unsigned);
typedef void (WINAPI *PFNGLBINDFRAMEBUFFER)(unsigned, unsigned);
typedef void (WINAPI *PFNGLBINDBUFFER)(unsigned, unsigned);
typedef PROC (WINAPI *PFNWGLGETPROCADDRESS)(LPCSTR);
typedef BOOL (WINAPI *PFNSWAPBUFFERS)(HDC);
typedef HRESULT (WINAPI *PFNSHGETKNOWNFOLDERPATH)(const GUID *, DWORD, HANDLE, PWSTR *);

#define GL_RGBA 0x1908
#define GL_BGRA 0x80E1
#define GL_UNSIGNED_BYTE 0x1401
#define GL_PACK_ALIGNMENT 0x0D05
#define GL_READ_BUFFER 0x0C02
#define GL_BACK 0x0405
#define GL_VIEWPORT 0x0BA2
#define GL_READ_FRAMEBUFFER 0x8CA8
#define GL_READ_FRAMEBUFFER_BINDING 0x8CAA
#define GL_PIXEL_PACK_BUFFER 0x88EB
#define GL_PIXEL_PACK_BUFFER_BINDING 0x88ED

static PFNSWAPBUFFERS real_swap;
static PFNSHGETKNOWNFOLDERPATH real_known_folder;
/* FOLDERID_LocalAppData {F1B32785-6FBA-4FCF-9D55-7B8E7F157091} */
static const GUID LOCAL_APPDATA = {0xF1B32785, 0x6FBA, 0x4FCF, {0x9D, 0x55, 0x7B, 0x8E, 0x7F, 0x15, 0x70, 0x91}};
static PFNGLREADPIXELS glReadPixels_;
static PFNGLGETINTEGERV glGetIntegerv_;
static PFNGLPIXELSTOREI glPixelStorei_;
static PFNGLREADBUFFER glReadBuffer_;
static PFNGLBINDFRAMEBUFFER glBindFramebuffer_;
static PFNGLBINDBUFFER glBindBuffer_;
static unsigned long frames;

static void shim_log(const char *fmt, ...)
{
    FILE *f = fopen("gamelab_capture.log", "a");
    if (!f) return;
    SYSTEMTIME t; GetLocalTime(&t);
    fprintf(f, "[%02d:%02d:%02d.%03d] ", t.wHour, t.wMinute, t.wSecond, t.wMilliseconds);
    va_list ap; va_start(ap, fmt); vfprintf(f, fmt, ap); va_end(ap);
    fputc('\n', f);
    fclose(f);
}

static int load_gl(void)
{
    if (glReadPixels_) return 1;
    HMODULE gl = GetModuleHandleA("opengl32.dll");
    if (!gl) return 0;
    PFNWGLGETPROCADDRESS wglGPA = (PFNWGLGETPROCADDRESS)GetProcAddress(gl, "wglGetProcAddress");
    glReadPixels_ = (PFNGLREADPIXELS)GetProcAddress(gl, "glReadPixels");
    glGetIntegerv_ = (PFNGLGETINTEGERV)GetProcAddress(gl, "glGetIntegerv");
    glPixelStorei_ = (PFNGLPIXELSTOREI)GetProcAddress(gl, "glPixelStorei");
    glReadBuffer_ = (PFNGLREADBUFFER)GetProcAddress(gl, "glReadBuffer");
    if (wglGPA) {
        glBindFramebuffer_ = (PFNGLBINDFRAMEBUFFER)wglGPA("glBindFramebuffer");
        glBindBuffer_ = (PFNGLBINDBUFFER)wglGPA("glBindBuffer");
    }
    return glReadPixels_ && glGetIntegerv_ && glPixelStorei_ && glReadBuffer_;
}

static void capture(const char *path)
{
    if (!load_gl()) { shim_log("ERR opengl32 functions not found"); return; }
    int vp[4] = {0}, prevRead = 0, prevPack = 0, prevAlign = 4, prevBuf = GL_BACK;
    glGetIntegerv_(GL_VIEWPORT, vp);
    HWND hwnd = WindowFromDC(wglGetCurrentDC());
    RECT rc; int w = vp[2], h = vp[3];
    if (hwnd && GetClientRect(hwnd, &rc)) { w = rc.right; h = rc.bottom; }
    if (w <= 0 || h <= 0 || w > 16384 || h > 16384) { shim_log("ERR bad size %dx%d", w, h); return; }
    glGetIntegerv_(GL_PACK_ALIGNMENT, &prevAlign);
    glGetIntegerv_(GL_READ_BUFFER, &prevBuf);
    if (glBindFramebuffer_) { glGetIntegerv_(GL_READ_FRAMEBUFFER_BINDING, &prevRead); glBindFramebuffer_(GL_READ_FRAMEBUFFER, 0); }
    if (glBindBuffer_) { glGetIntegerv_(GL_PIXEL_PACK_BUFFER_BINDING, &prevPack); glBindBuffer_(GL_PIXEL_PACK_BUFFER, 0); }
    glPixelStorei_(GL_PACK_ALIGNMENT, 4);
    glReadBuffer_(GL_BACK);
    size_t n = (size_t)w * h * 4;
    unsigned char *px = (unsigned char *)malloc(n);
    if (px) glReadPixels_(0, 0, w, h, GL_BGRA, GL_UNSIGNED_BYTE, px);
    glReadBuffer_(prevBuf);
    glPixelStorei_(GL_PACK_ALIGNMENT, prevAlign);
    if (glBindFramebuffer_) glBindFramebuffer_(GL_READ_FRAMEBUFFER, prevRead);
    if (glBindBuffer_) glBindBuffer_(GL_PIXEL_PACK_BUFFER, prevPack);
    if (!px) { shim_log("ERR out of memory"); return; }

    char tmp[MAX_PATH + 8];
    snprintf(tmp, sizeof tmp, "%s.tmp", path);
    FILE *f = fopen(tmp, "wb");
    if (!f) { shim_log("ERR cannot write %s", tmp); free(px); return; }
    BITMAPFILEHEADER fh = {0}; BITMAPINFOHEADER ih = {0};
    fh.bfType = 0x4D42; fh.bfOffBits = sizeof fh + sizeof ih; fh.bfSize = fh.bfOffBits + (DWORD)n;
    ih.biSize = sizeof ih; ih.biWidth = w; ih.biHeight = h;   /* bottom-up, as GL returns it */
    ih.biPlanes = 1; ih.biBitCount = 32; ih.biCompression = BI_RGB; ih.biSizeImage = (DWORD)n;
    fwrite(&fh, sizeof fh, 1, f); fwrite(&ih, sizeof ih, 1, f); fwrite(px, 1, n, f);
    fclose(f);
    free(px);
    DeleteFileA(path);
    if (!MoveFileA(tmp, path)) { shim_log("ERR rename to %s failed (%lu)", path, GetLastError()); return; }
    shim_log("captured frame %lu %dx%d -> %s", frames, w, h, path);
}

/* pacing: the interval between presents, as the user sees frames (the scripts' ms is a fixed
   33 ms tick and cannot show a render hitch). A line per PACE_N frames, and one per hitch. */
#define PACE_N 600
static LARGE_INTEGER pace_freq, pace_prev;
static double pace_sum, pace_max;
static unsigned pace_n, pace_over20, pace_over34, pace_over50;

static void pace(void)
{
    LARGE_INTEGER now;
    QueryPerformanceCounter(&now);
    if (!pace_freq.QuadPart) QueryPerformanceFrequency(&pace_freq);
    if (pace_prev.QuadPart) {
        double ms = (double)(now.QuadPart - pace_prev.QuadPart) * 1000.0 / (double)pace_freq.QuadPart;
        pace_n++; pace_sum += ms;
        if (ms > pace_max) pace_max = ms;
        if (ms > 20) pace_over20++;
        if (ms > 34) pace_over34++;
        if (ms > 50) { pace_over50++; shim_log("pace hitch %.1f ms at frame %lu", ms, frames); }
        if (pace_n >= PACE_N) {
            shim_log("pace n=%u mean=%.2f max=%.1f over20=%u over34=%u over50=%u",
                     pace_n, pace_sum / pace_n, pace_max, pace_over20, pace_over34, pace_over50);
            pace_n = pace_over20 = pace_over34 = pace_over50 = 0;
            pace_sum = pace_max = 0;
        }
    }
    pace_prev = now;
}

static BOOL WINAPI hooked_swap(HDC hdc)
{
    frames++;
    pace();
    if ((frames & 3) == 0) {
        FILE *req = fopen("gamelab_capture.req", "rb");
        if (req) {
            char path[MAX_PATH] = {0};
            size_t got = fread(path, 1, sizeof path - 1, req);
            fclose(req);
            while (got && (path[got - 1] == '\n' || path[got - 1] == '\r' || path[got - 1] == ' ')) path[--got] = 0;
            DeleteFileA("gamelab_capture.req");
            if (got) capture(path);
        }
    }
    return real_swap(hdc);
}

static HRESULT WINAPI hooked_known_folder(const GUID *id, DWORD flags, HANDLE token, PWSTR *out)
{
    WCHAR lab[MAX_PATH];
    DWORD n = GetEnvironmentVariableW(L"GAMELAB_LOCALAPPDATA", lab, MAX_PATH);
    int redirect = id && IsEqualGUID(id, &LOCAL_APPDATA) && n > 0 && n < MAX_PATH;
    shim_log("SHGetKnownFolderPath {%08lX-...}%s", id ? id->Data1 : 0UL, redirect ? " -> GAMELAB_LOCALAPPDATA" : " (passed through)");
    if (!redirect)
        return real_known_folder(id, flags, token, out);
    size_t bytes = (n + 1) * sizeof(WCHAR);
    *out = (PWSTR)CoTaskMemAlloc(bytes);
    if (!*out) return E_OUTOFMEMORY;
    memcpy(*out, lab, bytes);
    return S_OK;
}

/* ---- focus: SDL2.dll is the only module that imports the user32 calls that can activate a
   window (HWR2.exe imports none of them; objdump -p, docs/RE_NOTES.md 2026-10-17). Every call
   is logged with the foreground before and after it. With GAMELAB_NO_ACTIVATE=1 (watch mode)
   a call made while the foreground belongs to another process is made non-activating:
   ShowWindow gets the matching NOACTIVATE/NA command, SetWindowPos gets SWP_NOACTIVATE, and
   SetForegroundWindow / SetActiveWindow are refused. When the user has put the game in the
   foreground themselves, every call passes through unchanged. */
typedef BOOL (WINAPI *PFNSHOWWINDOW)(HWND, int);
typedef BOOL (WINAPI *PFNSETWINDOWPOS)(HWND, HWND, int, int, int, int, UINT);
typedef BOOL (WINAPI *PFNSETFOREGROUNDWINDOW)(HWND);
typedef HWND (WINAPI *PFNSETHWND)(HWND);
static PFNSHOWWINDOW real_show;
static PFNSETWINDOWPOS real_setpos;
static PFNSETFOREGROUNDWINDOW real_setfg;
static PFNSETHWND real_setactive, real_setfocus;
static int no_activate;
static HWND game_hwnd;         /* watch mode: SDL's top-level SDL_app window */
static LONG focus_lines;
#define FOCUS_LOG_CAP 200

static int fg_is_ours(void)
{
    DWORD pid = 0;
    GetWindowThreadProcessId(GetForegroundWindow(), &pid);
    return pid == GetCurrentProcessId();
}

static void focus_log(const char *call, HWND h, long arg, long arg2, HWND fg_before, const char *action)
{
    LONG n = InterlockedIncrement(&focus_lines);
    if (n > FOCUS_LOG_CAP) return;
    HWND fg_after = GetForegroundWindow();
    DWORD pid = 0;
    GetWindowThreadProcessId(fg_after, &pid);
    shim_log("focus %s(hwnd=%p, %ld, 0x%lx) %s; fg %p -> %p%s%s", call, (void *)h, arg, arg2, action,
             (void *)fg_before, (void *)fg_after,
             fg_before != fg_after && pid == GetCurrentProcessId() ? " TOOK FOREGROUND" : "",
             n == FOCUS_LOG_CAP ? " (log cap reached)" : "");
}

static BOOL WINAPI hooked_show(HWND h, int cmd)
{
    HWND before = GetForegroundWindow();
    int use = cmd;
    if (no_activate && !fg_is_ours()) {
        switch (cmd) {
        case SW_SHOWNORMAL: case SW_RESTORE: use = SW_SHOWNOACTIVATE; break;
        case SW_SHOW: case SW_SHOWDEFAULT: use = SW_SHOWNA; break;
        case SW_SHOWMINIMIZED: case SW_MINIMIZE: use = SW_SHOWMINNOACTIVE; break;
        }
    }
    BOOL r = real_show(h, use);
    focus_log("ShowWindow", h, cmd, use, before, use != cmd ? "rewritten (cmd -> 2nd arg)" : "passed");
    return r;
}

static BOOL WINAPI hooked_setpos(HWND h, HWND after, int x, int y, int cx, int cy, UINT flags)
{
    HWND before = GetForegroundWindow();
    UINT use = flags;
    if (no_activate && !fg_is_ours()) use |= SWP_NOACTIVATE;
    BOOL r = real_setpos(h, after, x, y, cx, cy, use);
    if (!(flags & SWP_NOACTIVATE) || before != GetForegroundWindow())
        focus_log("SetWindowPos", h, (long)(LONG_PTR)after, flags, before, use != flags ? "SWP_NOACTIVATE added" : "passed");
    return r;
}

static BOOL WINAPI hooked_setfg(HWND h)
{
    HWND before = GetForegroundWindow();
    if (no_activate && !fg_is_ours()) {
        focus_log("SetForegroundWindow", h, 0, 0, before, "refused");
        return FALSE;
    }
    BOOL r = real_setfg(h);
    focus_log("SetForegroundWindow", h, r, 0, before, "passed");
    return r;
}

static HWND WINAPI hooked_setactive(HWND h)
{
    HWND before = GetForegroundWindow();
    if (no_activate && !fg_is_ours()) {
        focus_log("SetActiveWindow", h, 0, 0, before, "refused");
        return NULL;
    }
    HWND r = real_setactive(h);
    focus_log("SetActiveWindow", h, 0, 0, before, "passed");
    return r;
}

/* Watch mode: SDL's top-level windows are born WS_EX_NOACTIVATE, so neither a click on them
   nor the system's hand-off when the foreground window closes can activate them while the
   game loads. Such a window also has no taskbar button, which is wanted: clicking a taskbar
   button lets explorer activate the window regardless (20261017-200812). At the first frame the
   runner clears WS_EX_NOACTIVATE and adds the button (winproc.allow_activation), after which
   the human may click it like any window. */
typedef HWND (WINAPI *PFNCREATEWINDOWEXW)(DWORD, LPCWSTR, LPCWSTR, DWORD, int, int, int, int, HWND, HMENU, HINSTANCE, LPVOID);
static PFNCREATEWINDOWEXW real_create;

static HWND WINAPI hooked_create(DWORD ex, LPCWSTR cls, LPCWSTR name, DWORD style, int x, int y, int w, int h,
                                 HWND parent, HMENU menu, HINSTANCE inst, LPVOID param)
{
    DWORD use = ex;
    if (no_activate && !parent && !(style & WS_CHILD)) use |= WS_EX_NOACTIVATE;
    HWND r = real_create(use, cls, name, style, x, y, w, h, parent, menu, inst, param);
    if (no_activate && r && !parent && !(style & WS_CHILD) && !IS_INTRESOURCE(cls) && lstrcmpW(cls, L"SDL_app") == 0)
        game_hwnd = r;
    shim_log("focus CreateWindowExW(ex=0x%lx -> 0x%lx, style=0x%lx, parent=%p) -> %p", ex, use, style, (void *)parent, (void *)r);
    return r;
}

/* Watch mode: SDL only delivers posted keys once it believes its window has keyboard focus, and
   it decides that from GetForegroundWindow (20261018-000453: three posted Enters lost at the
   main menu while the user's window was the foreground; lab mode, where the game is the hidden
   desktop's foreground, never loses one). So in SDL's import table only, GetForegroundWindow and
   GetFocus answer with the game window while another process holds the real foreground. The
   real foreground is never touched. ClipCursor from SDL is refused in that state, so a focused
   SDL cannot confine the user's real cursor. */
typedef HWND (WINAPI *PFNGETHWND)(void);
typedef BOOL (WINAPI *PFNCLIPCURSOR)(const RECT *);
static PFNGETHWND real_getfg, real_getfocus;
static PFNCLIPCURSOR real_clip;
static LONG fake_focus_logged;

/* Hand-off (watch mode, the runner's `play` step): message type GAMELAB_HANDOFF on the input
   mailslot. Until then the hooks below hide the user's mouse and focus changes so GameLab's
   scripted keys land; after it the game is the human's, and every one of them answers what
   SDL answers: real mouse motion, buttons and wheel, real SDL_GetMouseState, real focus.
   Only ClipCursor stays refused while another process owns the foreground, as unhooked SDL
   never clips then either (watch arena 20261021-061402: the user's mouse did nothing in the
   arena, the shim had dropped every motion and button event and pinned the mouse at 0,0).
   An optional second u32 with bit GAMELAB_HANDOFF_KEEP_FOCUS frees the mouse only and keeps
   SDL told it has focus, as a player who clicked into the window has it: for a scripted test
   that may not take the real foreground (devarena/watch-input). */
#define GAMELAB_HANDOFF 0x7F00
#define GAMELAB_HANDOFF_KEEP_FOCUS 1
static volatile LONG inj_handoff;     /* focus answered truthfully */
static volatile LONG inj_mouse_free;  /* real mouse events and state reach the game */

static HWND fake_focus(HWND real)
{
    if (inj_handoff || !no_activate || !game_hwnd || fg_is_ours()) return real;
    if (InterlockedExchange(&fake_focus_logged, 1) == 0)
        shim_log("focus SDL told its window %p has focus (real foreground %p)", (void *)game_hwnd, (void *)GetForegroundWindow());
    return game_hwnd;
}

static HWND WINAPI hooked_getfg(void) { return fake_focus(real_getfg()); }
static HWND WINAPI hooked_getfocus(void) { return fake_focus(real_getfocus()); }

static BOOL WINAPI hooked_clip(const RECT *rc)
{
    if (rc && no_activate && !fg_is_ours()) {
        focus_log("ClipCursor", NULL, rc->left, rc->top, GetForegroundWindow(), "refused");
        return TRUE;
    }
    return real_clip(rc);
}

static HWND WINAPI hooked_setfocus(HWND h)
{
    HWND before = GetForegroundWindow();
    HWND r = real_setfocus(h);
    focus_log("SetFocus", h, 0, 0, before, "passed");
    return r;
}

/* Watch mode input (GAMELAB_SHIM_INPUT=1): GameLab's keys go into the game's event stream, not
   through window messages. HWR2 reads every key and character through SDL_PollEvent (its only
   SDL input imports are SDL_PollEvent, SDL_GetMouseState and the joystick/controller calls), so
   the exe's import of SDL_PollEvent hands out queued GameLab events before the real ones. The
   queue is the mailslot \\.\mailslot\gamelab_input_<pid>; each message is one event:
     u32 type (0x300 SDL_KEYDOWN / 0x301 SDL_KEYUP): i32 scancode, i32 keycode, u16 mod
     u32 type (0x303 SDL_TEXTINPUT): up to 31 bytes of UTF-8
   Why: a posted WM_KEYDOWN only becomes an SDL key event while SDL believes its window has
   keyboard focus, which the focus hooks above do not guarantee while the user works in another
   window (chest-watch 20261018-163015 and -165101: every posted Enter lost at the main menu).
   The real foreground, the user's keyboard and mouse are untouched: nothing here is real input,
   and real SDL events still pass through unchanged. Layouts: SDL 2.30.7 SDL_events.h. */
typedef int (__cdecl *PFNSDLPOLLEVENT)(void *);
typedef unsigned (__cdecl *PFNSDLGETTICKS)(void);
static PFNSDLPOLLEVENT real_poll;
static PFNSDLGETTICKS sdl_ticks;
static HANDLE inj_slot = INVALID_HANDLE_VALUE;
static unsigned inj_window_id = 1;
static LONG inj_count;

#pragma pack(push, 4)
typedef struct {
    unsigned type, timestamp, windowID;
    unsigned char state, repeat, pad2, pad3;
    int scancode, sym;
    unsigned short mod;
    unsigned unused;
} SdlKeyEvent;                        /* SDL_KeyboardEvent: 32 bytes */
typedef struct {
    unsigned type, timestamp, windowID;
    char text[32];
} SdlTextEvent;                       /* SDL_TextInputEvent: 44 bytes */
#pragma pack(pop)

static int inj_build(const unsigned char *m, DWORD n, unsigned char *ev)
{
    unsigned type;
    if (n < 4) return 0;
    memcpy(&type, m, 4);
    memset(ev, 0, 56);                /* sizeof(SDL_Event) on 64-bit */
    unsigned now = sdl_ticks ? sdl_ticks() : GetTickCount();
    if ((type == 0x300 || type == 0x301) && n >= 14) {
        SdlKeyEvent *k = (SdlKeyEvent *)ev;
        k->type = type; k->timestamp = now; k->windowID = inj_window_id;
        k->state = type == 0x300 ? 1 : 0;
        memcpy(&k->scancode, m + 4, 4);
        memcpy(&k->sym, m + 8, 4);
        memcpy(&k->mod, m + 12, 2);
        return 1;
    }
    if (type == 0x303 && n > 4) {
        SdlTextEvent *t = (SdlTextEvent *)ev;
        t->type = type; t->timestamp = now; t->windowID = inj_window_id;
        DWORD len = n - 4 > 31 ? 31 : n - 4;
        memcpy(t->text, m + 4, len);
        return 1;
    }
    return 0;
}

/* The game also drops keys while it believes its window is unfocused: in chest-watch
   20261018-170133 the shim handed it the Enter (log "first GameLab event") and no session
   started. It learns focus from SDL_WINDOWEVENT_FOCUS_GAINED / _LOST and SDL_GetWindowFlags
   (both in its imports), so with shim input it is told it has focus once, never that it lost
   it, and SDL_GetWindowFlags always carries SDL_WINDOW_INPUT_FOCUS. Only the game's belief
   changes: the real foreground and the user's input are untouched. */
typedef unsigned (__cdecl *PFNSDLGETWINDOWFLAGS)(void *);
static PFNSDLGETWINDOWFLAGS real_winflags;
static LONG inj_focus_sent, inj_focus_dropped;
#define SDL_WINDOWEVENT 0x200
#define SDL_WINDOWEVENT_FOCUS_GAINED 12
#define SDL_WINDOWEVENT_FOCUS_LOST 13
#define SDL_WINDOWEVENT_LEAVE 11
#define SDL_WINDOW_INPUT_FOCUS 0x200
#define SDL_WINDOW_MOUSE_FOCUS 0x400

static unsigned __cdecl hooked_winflags(void *window)
{
    unsigned f = real_winflags(window);
    return inj_handoff ? f : f | SDL_WINDOW_INPUT_FOCUS | SDL_WINDOW_MOUSE_FOCUS;
}

/* Focus alone was not enough (chest-watch 20261018-170421: focus told, focus-lost dropped, the
   Enter handed over, still no session). The game also imports SDL_GetMouseFocus, and the one
   watch run whose first posted Enter took (-155215) is consistent with the user's pointer
   resting over the game window. So SDL_GetMouseFocus answers with the game's window when SDL
   has none, and SDL_WINDOWEVENT_LEAVE is dropped like focus-lost. The real cursor is untouched. */
typedef void *(__cdecl *PFNSDLGETMOUSEFOCUS)(void);
typedef void *(__cdecl *PFNSDLGETWINDOWFROMID)(unsigned);
static PFNSDLGETMOUSEFOCUS real_mousefocus;
static PFNSDLGETWINDOWFROMID sdl_window_from_id;
static LONG inj_mouse_logged;

static void *__cdecl hooked_mousefocus(void)
{
    void *w = real_mousefocus();
    if (w || inj_handoff || !sdl_window_from_id) return w;
    w = sdl_window_from_id(inj_window_id);
    if (w && InterlockedExchange(&inj_mouse_logged, 1) == 0)
        shim_log("input SDL_GetMouseFocus answered with window %u (SDL had none)", inj_window_id);
    return w;
}

/* The user's real mouse is kept from the game too. A pointer that passes over the window puts
   the menu in mouse mode (GUI/WindowInput.as:84-91: any change of the mouse position sets
   m_usingMouse), and there Enter clicks only what the pointer hovers (GUI/WindowObject.as:96-113),
   so nothing: chest-watch 20261018-172146 lost three Enters that way, and lab -172828 reproduced
   it by posting one WM_MOUSEMOVE. With shim input SDL's mouse events are dropped and
   SDL_GetMouseState answers a fixed (0,0), no buttons, as on the hidden desktop where lab's
   Enter always takes. GameLab's own pointer (gl pointer) writes the engine's MousePos and
   needs neither. The real cursor and the user's desktop are untouched. */
typedef unsigned (__cdecl *PFNSDLGETMOUSESTATE)(int *, int *);
static PFNSDLGETMOUSESTATE real_mousestate;
static LONG inj_mouse_dropped, inj_state_logged;

static unsigned __cdecl hooked_mousestate(int *x, int *y)
{
    int rx = 0, ry = 0;
    if (inj_mouse_free) return real_mousestate(x, y);
    unsigned b = real_mousestate(&rx, &ry);
    if (InterlockedExchange(&inj_state_logged, 1) == 0)
        shim_log("input SDL_GetMouseState frozen at 0,0 (SDL had %d,%d buttons 0x%x)", rx, ry, b);
    if (x) *x = 0;
    if (y) *y = 0;
    return 0;
}

/* Hand-off with focus kept (a scripted player): SDL arms TrackMouseEvent on the first
   WM_MOUSEMOVE, and with the real cursor elsewhere Windows answers WM_MOUSELEAVE at once, where
   SDL sends the real cursor position as motion and drops mouse focus (SDL 2.30.7,
   SDL_windowsevents.c), so a posted move never stays (lab watch-input 20261021-155630: the
   engine's MousePos never followed). Only then is the leave tracking skipped. */
typedef BOOL (WINAPI *PFNTRACKMOUSEEVENT)(void *);
static PFNTRACKMOUSEEVENT real_track;
static LONG inj_track_logged;

static BOOL WINAPI hooked_track(void *tme)
{
    if (!inj_mouse_free || inj_handoff) return real_track(tme);
    if (InterlockedExchange(&inj_track_logged, 1) == 0)
        shim_log("input TrackMouseEvent skipped (hand-off with focus kept: no mouse-leave)");
    return TRUE;
}

static int __cdecl hooked_poll(void *ev)
{
    DWORD next = 0;
    if (ev && inj_slot != INVALID_HANDLE_VALUE && InterlockedExchange(&inj_focus_sent, 1) == 0) {
        unsigned char *w = (unsigned char *)ev;          /* SDL_WindowEvent: event at +12 */
        memset(w, 0, 56);
        *(unsigned *)w = SDL_WINDOWEVENT;
        ((unsigned *)w)[1] = sdl_ticks ? sdl_ticks() : GetTickCount();
        ((unsigned *)w)[2] = inj_window_id;
        w[12] = SDL_WINDOWEVENT_FOCUS_GAINED;
        shim_log("input told the game its window has focus (window %u)", inj_window_id);
        return 1;
    }
    while (inj_slot != INVALID_HANDLE_VALUE && GetMailslotInfo(inj_slot, NULL, &next, NULL, NULL)
           && next != MAILSLOT_NO_MESSAGE) {
        if (!ev) return 1;            /* SDL_PollEvent(NULL): "is there an event" */
        unsigned char m[64];
        DWORD got = 0;
        if (next > sizeof m) {        /* not ours: drop it */
            unsigned char *junk = (unsigned char *)HeapAlloc(GetProcessHeap(), 0, next);
            if (junk) { ReadFile(inj_slot, junk, next, &got, NULL); HeapFree(GetProcessHeap(), 0, junk); }
            continue;
        }
        if (!ReadFile(inj_slot, m, next, &got, NULL)) break;
        if (got >= 4 && *(unsigned *)m == GAMELAB_HANDOFF) {
            int keep = got >= 8 && (((unsigned *)m)[1] & GAMELAB_HANDOFF_KEEP_FOCUS);
            InterlockedExchange(&inj_mouse_free, 1);
            if (keep) {
                shim_log("input handed to the player, focus kept: SDL mouse events pass through, "
                         "SDL still told its window has focus");
                continue;
            }
            InterlockedExchange(&inj_handoff, 1);
            /* SDL was told it had focus (fake_focus); have it look again now that it is
               answered truthfully, so the game hears a real focus-lost if the user is elsewhere */
            int fg = fg_is_ours();
            if (game_hwnd && !fg) PostMessageW(game_hwnd, WM_KILLFOCUS, 0, 0);
            shim_log("input handed to the player: SDL mouse, focus and window events pass through "
                     "(foreground %s)", fg ? "is the game" : "is another process");
            continue;
        }
        if (inj_build(m, got, (unsigned char *)ev)) {
            if (InterlockedIncrement(&inj_count) == 1)
                shim_log("input first GameLab event handed to SDL_PollEvent (type 0x%x, window %u)",
                         *(unsigned *)ev, inj_window_id);
            return 1;
        }
    }
    for (;;) {
        int r = real_poll(ev);
        if (!r || !ev)
            return r;
        unsigned t = *(unsigned *)ev;
        if (t == SDL_WINDOWEVENT || (t >= 0x300 && t < 0x400))   /* windowID at +8 */
            inj_window_id = ((unsigned *)ev)[2];
        if (inj_handoff)
            return r;
        if (inj_mouse_free && t >= 0x400 && t <= 0x403)
            return r;
        if (inj_slot != INVALID_HANDLE_VALUE && t == SDL_WINDOWEVENT
            && (((unsigned char *)ev)[12] == SDL_WINDOWEVENT_FOCUS_LOST
                || ((unsigned char *)ev)[12] == SDL_WINDOWEVENT_LEAVE)) {
            if (InterlockedIncrement(&inj_focus_dropped) <= 5)
                shim_log("input dropped SDL %s (window %u)",
                         ((unsigned char *)ev)[12] == SDL_WINDOWEVENT_LEAVE ? "mouse-leave" : "focus-lost", inj_window_id);
            continue;
        }
        if (inj_slot != INVALID_HANDLE_VALUE && t >= 0x400 && t <= 0x403) {   /* motion, button, wheel */
            if (InterlockedIncrement(&inj_mouse_dropped) <= 3)
                shim_log("input dropped SDL mouse event 0x%x", t);
            continue;
        }
        return r;
    }
}

/* Replace `func` imported from `dll` in `module`'s import table; returns the original or NULL. */
static void *hook_iat(HMODULE exe, const char *dll, const char *func, void *hook)
{
    if (!exe) return NULL;
    BYTE *base = (BYTE *)exe;
    IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)(base + ((IMAGE_DOS_HEADER *)base)->e_lfanew);
    IMAGE_DATA_DIRECTORY dir = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
    IMAGE_IMPORT_DESCRIPTOR *imp = (IMAGE_IMPORT_DESCRIPTOR *)(base + dir.VirtualAddress);
    for (; imp->Name; imp++) {
        if (lstrcmpiA((char *)(base + imp->Name), dll) != 0) continue;
        IMAGE_THUNK_DATA *names = (IMAGE_THUNK_DATA *)(base + imp->OriginalFirstThunk);
        IMAGE_THUNK_DATA *slots = (IMAGE_THUNK_DATA *)(base + imp->FirstThunk);
        for (; names->u1.AddressOfData; names++, slots++) {
            if (IMAGE_SNAP_BY_ORDINAL(names->u1.Ordinal)) continue;
            IMAGE_IMPORT_BY_NAME *ibn = (IMAGE_IMPORT_BY_NAME *)(base + names->u1.AddressOfData);
            if (strcmp((char *)ibn->Name, func) != 0) continue;
            DWORD old;
            VirtualProtect(&slots->u1.Function, sizeof(void *), PAGE_READWRITE, &old);
            void *orig = (void *)slots->u1.Function;
            slots->u1.Function = (ULONG_PTR)hook;
            VirtualProtect(&slots->u1.Function, sizeof(void *), old, &old);
            return orig;
        }
    }
    return NULL;
}

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID reserved)
{
    (void)inst; (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(inst);
        HMODULE exe = GetModuleHandleA(NULL);
        real_swap = (PFNSWAPBUFFERS)hook_iat(exe, "gdi32.dll", "SwapBuffers", (void *)hooked_swap);
        real_known_folder = (PFNSHGETKNOWNFOLDERPATH)hook_iat(exe, "shell32.dll", "SHGetKnownFolderPath", (void *)hooked_known_folder);
        shim_log("injected; SwapBuffers %s, SHGetKnownFolderPath %s",
                 real_swap ? "hooked" : "ERR import not found",
                 real_known_folder ? "hooked" : "ERR import not found");
        HMODULE sdl = GetModuleHandleA("SDL2.dll");
        char flag[8] = {0};
        no_activate = GetEnvironmentVariableA("GAMELAB_NO_ACTIVATE", flag, sizeof flag) > 0 && flag[0] == '1';
        real_show = (PFNSHOWWINDOW)hook_iat(sdl, "user32.dll", "ShowWindow", (void *)hooked_show);
        real_setpos = (PFNSETWINDOWPOS)hook_iat(sdl, "user32.dll", "SetWindowPos", (void *)hooked_setpos);
        real_setfg = (PFNSETFOREGROUNDWINDOW)hook_iat(sdl, "user32.dll", "SetForegroundWindow", (void *)hooked_setfg);
        real_setactive = (PFNSETHWND)hook_iat(sdl, "user32.dll", "SetActiveWindow", (void *)hooked_setactive);
        real_setfocus = (PFNSETHWND)hook_iat(sdl, "user32.dll", "SetFocus", (void *)hooked_setfocus);
        real_create = (PFNCREATEWINDOWEXW)hook_iat(sdl, "user32.dll", "CreateWindowExW", (void *)hooked_create);
        if (no_activate) {
            real_getfg = (PFNGETHWND)hook_iat(sdl, "user32.dll", "GetForegroundWindow", (void *)hooked_getfg);
            real_getfocus = (PFNGETHWND)hook_iat(sdl, "user32.dll", "GetFocus", (void *)hooked_getfocus);
            real_clip = (PFNCLIPCURSOR)hook_iat(sdl, "user32.dll", "ClipCursor", (void *)hooked_clip);
            real_track = (PFNTRACKMOUSEEVENT)hook_iat(sdl, "user32.dll", "TrackMouseEvent", (void *)hooked_track);
            shim_log("watch focus hooks in SDL2.dll: GetForegroundWindow %s, GetFocus %s, ClipCursor %s, TrackMouseEvent %s",
                     real_getfg ? "hooked" : "ERR", real_getfocus ? "hooked" : "ERR", real_clip ? "hooked" : "ERR",
                     real_track ? "hooked" : "ERR");
        }
        shim_log("focus hooks in SDL2.dll: ShowWindow %s, SetWindowPos %s, SetForegroundWindow %s, "
                 "SetActiveWindow %s, SetFocus %s, CreateWindowExW %s; no_activate=%d",
                 real_show ? "hooked" : "ERR", real_setpos ? "hooked" : "ERR", real_setfg ? "hooked" : "ERR",
                 real_setactive ? "hooked" : "ERR", real_setfocus ? "hooked" : "ERR",
                 real_create ? "hooked" : "ERR", no_activate);
        if (GetEnvironmentVariableA("GAMELAB_SHIM_INPUT", flag, sizeof flag) > 0 && flag[0] == '1') {
            char name[64];
            snprintf(name, sizeof name, "\\\\.\\mailslot\\gamelab_input_%lu", GetCurrentProcessId());
            inj_slot = CreateMailslotA(name, 0, 0, NULL);
            sdl_ticks = sdl ? (PFNSDLGETTICKS)GetProcAddress(sdl, "SDL_GetTicks") : NULL;
            real_poll = (PFNSDLPOLLEVENT)hook_iat(exe, "SDL2.dll", "SDL_PollEvent", (void *)hooked_poll);
            if (!real_poll && inj_slot != INVALID_HANDLE_VALUE) { CloseHandle(inj_slot); inj_slot = INVALID_HANDLE_VALUE; }
            if (real_poll) {
                real_winflags = (PFNSDLGETWINDOWFLAGS)hook_iat(exe, "SDL2.dll", "SDL_GetWindowFlags", (void *)hooked_winflags);
                sdl_window_from_id = sdl ? (PFNSDLGETWINDOWFROMID)GetProcAddress(sdl, "SDL_GetWindowFromID") : NULL;
                real_mousefocus = (PFNSDLGETMOUSEFOCUS)hook_iat(exe, "SDL2.dll", "SDL_GetMouseFocus", (void *)hooked_mousefocus);
                real_mousestate = (PFNSDLGETMOUSESTATE)hook_iat(exe, "SDL2.dll", "SDL_GetMouseState", (void *)hooked_mousestate);
            }
            shim_log("input SDL_PollEvent %s, SDL_GetWindowFlags %s, SDL_GetMouseFocus %s, SDL_GetMouseState %s, mailslot %s %s",
                     real_poll ? "hooked" : "ERR import not found", real_winflags ? "hooked" : "ERR",
                     real_mousefocus ? "hooked" : "ERR", real_mousestate ? "hooked" : "ERR",
                     name, inj_slot != INVALID_HANDLE_VALUE ? "open" : "ERR");
        }
    }
    return TRUE;
}
