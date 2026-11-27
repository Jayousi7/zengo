"""Time since the last keyboard or mouse input anywhere on the desktop.

Asked of the system itself, which tracks it for screensavers: the X11 screensaver
extension on Linux, ``GetLastInputInfo`` on Windows. Only *when* there was input
is known, never what it was: no keys are read. Where neither is available it
reports nothing, and Zengo simply never notices typing.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import sys


class InputIdle:
    def __init__(self) -> None:
        self._read = _windows() if sys.platform == "win32" else _x11()

    def seconds(self) -> float | None:
        """Seconds since any input, or None if the system won't say."""
        if self._read is None:
            return None
        try:
            return self._read()
        except OSError:
            return None


def _x11():
    xlib_name, xss_name = ctypes.util.find_library("X11"), ctypes.util.find_library("Xss")
    if not xlib_name or not xss_name:
        return None
    try:
        xlib, xss = ctypes.CDLL(xlib_name), ctypes.CDLL(xss_name)
    except OSError:
        return None

    class Info(ctypes.Structure):
        _fields_ = [
            ("window", ctypes.c_ulong),
            ("state", ctypes.c_int),
            ("kind", ctypes.c_int),
            ("til_or_since", ctypes.c_ulong),
            ("idle", ctypes.c_ulong),
            ("event_mask", ctypes.c_ulong),
        ]

    xlib.XOpenDisplay.restype = ctypes.c_void_p
    xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
    xlib.XDefaultRootWindow.restype = ctypes.c_ulong
    xlib.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
    xss.XScreenSaverAllocInfo.restype = ctypes.POINTER(Info)
    xss.XScreenSaverQueryInfo.restype = ctypes.c_int
    xss.XScreenSaverQueryInfo.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(Info)]

    display = xlib.XOpenDisplay(None)
    if not display:
        return None  # not on X11 (Wayland without XWayland, say)
    root = xlib.XDefaultRootWindow(display)
    info = xss.XScreenSaverAllocInfo()

    def read() -> float | None:
        if not xss.XScreenSaverQueryInfo(display, root, info):
            return None
        return info.contents.idle / 1000

    return read


def _windows():
    class LastInput(ctypes.Structure):
        _fields_ = [("size", ctypes.c_uint), ("time", ctypes.c_uint)]

    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32  # type: ignore[attr-defined]
    last = LastInput(ctypes.sizeof(LastInput), 0)

    def read() -> float | None:
        if not user32.GetLastInputInfo(ctypes.byref(last)):
            return None
        return ((kernel32.GetTickCount() - last.time) & 0xFFFFFFFF) / 1000

    return read
