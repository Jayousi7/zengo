"""The other applications' windows on the desktop, front-most first.

Only ordinary windows that are shown, on the current workspace, and neither
maximized, minimized nor full screen; never Zengo's own. On X11 this asks the
window manager, through the same standard properties taskbars use; on Windows,
``EnumWindows``. Elsewhere (Wayland without XWayland, say) there are none, and
he simply never perches on windows.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import sys
from collections.abc import Callable

from zengo.world import Window

Reader = Callable[[], list[Window]]

MIN_SIZE = (100, 60)
"""Smaller windows are left out: too small to perch on, and mostly not app windows
at all (another copy of Zengo's cloud, seeds and cage, say)."""


def _big_enough(left: int, top: int, right: int, bottom: int) -> bool:
    return right - left >= MIN_SIZE[0] and bottom - top >= MIN_SIZE[1]


def windows_reader() -> Reader:
    try:
        reader = _windows() if sys.platform == "win32" else _x11()
    except (OSError, AttributeError):
        reader = None
    return reader or (lambda: [])


def _is_zengo(wm_class: bytes) -> bool:
    """WM_CLASS holds the instance and class names; Qt sets the class to the app name."""
    return b"Zengo" in wm_class.split(b"\0")


# --- X11 -------------------------------------------------------------------------


def _x11() -> Reader | None:
    name = ctypes.util.find_library("X11")
    if not name:
        return None
    x = ctypes.CDLL(name)
    c_ulong, c_long, c_int, c_void_p = ctypes.c_ulong, ctypes.c_long, ctypes.c_int, ctypes.c_void_p
    x.XOpenDisplay.restype = c_void_p
    x.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x.XDefaultRootWindow.restype = c_ulong
    x.XDefaultRootWindow.argtypes = [c_void_p]
    x.XInternAtom.restype = c_ulong
    x.XInternAtom.argtypes = [c_void_p, ctypes.c_char_p, c_int]
    x.XGetWindowProperty.argtypes = [
        c_void_p, c_ulong, c_ulong, c_long, c_long, c_int, c_ulong,
        ctypes.POINTER(c_ulong), ctypes.POINTER(c_int), ctypes.POINTER(c_ulong),
        ctypes.POINTER(c_ulong), ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)),
    ]  # fmt: skip
    x.XGetGeometry.argtypes = [
        c_void_p, c_ulong, ctypes.POINTER(c_ulong), ctypes.POINTER(c_int), ctypes.POINTER(c_int),
        ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint),
        ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint),
    ]  # fmt: skip
    x.XTranslateCoordinates.argtypes = [
        c_void_p, c_ulong, c_ulong, c_int, c_int,
        ctypes.POINTER(c_int), ctypes.POINTER(c_int), ctypes.POINTER(c_ulong),
    ]  # fmt: skip
    x.XFree.argtypes = [c_void_p]
    x.XSync.argtypes = [c_void_p, c_int]

    display = x.XOpenDisplay(None)
    if not display:
        return None
    root = x.XDefaultRootWindow(display)

    # A window can vanish between two questions about it. Xlib's default answer to
    # the resulting error is to end the program, so errors are ignored instead.
    handler_type = ctypes.CFUNCTYPE(c_int, c_void_p, c_void_p)
    ignore = handler_type(lambda _display, _event: 0)
    x.XSetErrorHandler.argtypes = [handler_type]
    x.XSetErrorHandler(ignore)

    def atom(name: str) -> int:
        return x.XInternAtom(display, name.encode(), 0)

    names = [
        "_NET_CLIENT_LIST_STACKING",
        "_NET_WM_STATE",
        "_NET_WM_STATE_HIDDEN",
        "_NET_WM_STATE_FULLSCREEN",
        "_NET_WM_STATE_MAXIMIZED_VERT",
        "_NET_WM_STATE_MAXIMIZED_HORZ",
        "_NET_WM_WINDOW_TYPE",
        "_NET_WM_WINDOW_TYPE_NORMAL",
        "_NET_WM_WINDOW_TYPE_DIALOG",
        "_NET_WM_DESKTOP",
        "_NET_CURRENT_DESKTOP",
        "_NET_WM_PID",
        "_NET_FRAME_EXTENTS",
        "_GTK_FRAME_EXTENTS",
        "WM_CLASS",
    ]
    atoms = {n: atom(n) for n in names}
    any_type = 0
    pid = os.getpid()

    def longs(window: int, prop: str) -> list[int]:
        kind, form = c_ulong(), c_int()
        count, after = c_ulong(), c_ulong()
        data = ctypes.POINTER(ctypes.c_ubyte)()
        status = x.XGetWindowProperty(
            display, window, atoms[prop], 0, 4096, 0, any_type,
            ctypes.byref(kind), ctypes.byref(form), ctypes.byref(count),
            ctypes.byref(after), ctypes.byref(data),
        )  # fmt: skip
        if status != 0 or not data:
            return []
        try:
            if form.value != 32:
                return []
            values = ctypes.cast(data, ctypes.POINTER(c_ulong))
            return [values[i] for i in range(count.value)]
        finally:
            x.XFree(data)

    def text(window: int, prop: str) -> bytes:
        kind, form = c_ulong(), c_int()
        count, after = c_ulong(), c_ulong()
        data = ctypes.POINTER(ctypes.c_ubyte)()
        status = x.XGetWindowProperty(
            display, window, atoms[prop], 0, 1024, 0, any_type,
            ctypes.byref(kind), ctypes.byref(form), ctypes.byref(count),
            ctypes.byref(after), ctypes.byref(data),
        )  # fmt: skip
        if status != 0 or not data:
            return b""
        try:
            return bytes(data[: count.value]) if form.value == 8 else b""
        finally:
            x.XFree(data)

    def frame(window: int) -> tuple[int, int, int, int] | None:
        """Screen rectangle of the window as you see it: decorations in, shadows out."""
        root_out, gx, gy = c_ulong(), c_int(), c_int()
        width, height, border, depth = (ctypes.c_uint() for _ in range(4))
        if not x.XGetGeometry(
            display, window, ctypes.byref(root_out), ctypes.byref(gx), ctypes.byref(gy),
            ctypes.byref(width), ctypes.byref(height), ctypes.byref(border), ctypes.byref(depth),
        ):  # fmt: skip
            return None
        sx, sy, child = c_int(), c_int(), c_ulong()
        if not x.XTranslateCoordinates(
            display, window, root, 0, 0, ctypes.byref(sx), ctypes.byref(sy), ctypes.byref(child)
        ):
            return None
        left, top = sx.value, sy.value
        right, bottom = left + width.value, top + height.value
        server = longs(window, "_NET_FRAME_EXTENTS")  # title bar drawn by the window manager
        if len(server) == 4:
            left, right, top, bottom = (
                left - server[0],
                right + server[1],
                top - server[2],
                bottom + server[3],
            )
        client = longs(window, "_GTK_FRAME_EXTENTS")  # shadow drawn by the app itself
        if len(client) == 4:
            left, right, top, bottom = (
                left + client[0],
                right - client[1],
                top + client[2],
                bottom - client[3],
            )
        return left, top, right, bottom

    wanted_types = {atoms["_NET_WM_WINDOW_TYPE_NORMAL"], atoms["_NET_WM_WINDOW_TYPE_DIALOG"]}
    unwanted_states = {
        atoms["_NET_WM_STATE_HIDDEN"],
        atoms["_NET_WM_STATE_FULLSCREEN"],
    }
    maximized = {atoms["_NET_WM_STATE_MAXIMIZED_VERT"], atoms["_NET_WM_STATE_MAXIMIZED_HORZ"]}

    def read() -> list[Window]:
        stacking = longs(root, "_NET_CLIENT_LIST_STACKING")  # bottom-most first
        current = longs(root, "_NET_CURRENT_DESKTOP")
        found: list[Window] = []
        for window in reversed(stacking):
            types = set(longs(window, "_NET_WM_WINDOW_TYPE"))
            if types and not types & wanted_types:
                continue  # docks, panels, the desktop, tooltips...
            states = set(longs(window, "_NET_WM_STATE"))
            if states & unwanted_states or maximized <= states:
                continue
            desktop = longs(window, "_NET_WM_DESKTOP")
            if current and desktop and desktop[0] not in (current[0], 0xFFFFFFFF):
                continue  # on another workspace
            if longs(window, "_NET_WM_PID") == [pid] or _is_zengo(text(window, "WM_CLASS")):
                continue  # Zengo's own, or another copy of him
            rect = frame(window)
            if rect is not None and _big_enough(*rect):
                found.append(Window(window, *rect))
        x.XSync(display, 0)
        return found

    def one(window: int) -> tuple[int, int, int, int] | None:
        rect = frame(window)
        x.XSync(display, 0)
        return rect

    read.keep_alive = ignore  # type: ignore[attr-defined]  # the error handler must outlive us
    read.frame = one  # type: ignore[attr-defined]
    return read


# --- Windows ---------------------------------------------------------------------


def _windows() -> Reader | None:
    from ctypes import wintypes

    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    dwmapi = ctypes.windll.dwmapi  # type: ignore[attr-defined]
    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)  # type: ignore[attr-defined]
    gwl_exstyle, ws_ex_toolwindow = -20, 0x00000080
    dwmwa_extended_frame_bounds, dwmwa_cloaked = 9, 14
    pid = os.getpid()

    def read() -> list[Window]:
        found: list[Window] = []

        def visit(hwnd, _):  # front-most first
            if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd) or user32.IsZoomed(hwnd):
                return True
            if user32.GetWindowLongW(hwnd, gwl_exstyle) & ws_ex_toolwindow:
                return True
            if user32.GetWindowTextLengthW(hwnd) == 0:
                return True
            cloaked = wintypes.DWORD()
            dwmapi.DwmGetWindowAttribute(hwnd, dwmwa_cloaked, ctypes.byref(cloaked), 4)
            if cloaked.value:
                return True  # on another virtual desktop, or a suspended app
            owner = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
            if owner.value == pid:
                return True
            title = ctypes.create_unicode_buffer(64)
            user32.GetWindowTextW(hwnd, title, 64)
            if title.value == "Zengo" or title.value.startswith("Zengo's"):
                return True  # another copy of him
            rect = wintypes.RECT()
            if dwmapi.DwmGetWindowAttribute(
                hwnd, dwmwa_extended_frame_bounds, ctypes.byref(rect), ctypes.sizeof(rect)
            ):
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
            if _big_enough(rect.left, rect.top, rect.right, rect.bottom):
                found.append(Window(int(hwnd), rect.left, rect.top, rect.right, rect.bottom))
            return True

        user32.EnumWindows(enum_proc(visit), 0)
        return found

    def one(hwnd: int) -> tuple[int, int, int, int] | None:
        if not user32.IsWindow(hwnd):
            return None
        rect = wintypes.RECT()
        if dwmapi.DwmGetWindowAttribute(
            hwnd, dwmwa_extended_frame_bounds, ctypes.byref(rect), ctypes.sizeof(rect)
        ) and not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None
        return rect.left, rect.top, rect.right, rect.bottom

    read.frame = one  # type: ignore[attr-defined]
    return read
