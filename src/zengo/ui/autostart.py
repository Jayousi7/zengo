"""Starting Zengo when you log in.

- Linux: ``~/.config/autostart/zengo.desktop``, the freedesktop standard that
  Cinnamon, GNOME, KDE and others honour.
- Windows: a ``Zengo`` value under ``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run``,
  no admin rights needed.

The entry itself is the only record of whether it's on: nothing about it is kept
in his settings, so removing it by hand turns it off here too.

It points at what he's running from: the binary, or (run from source) this
Python with ``-m zengo``. If the binary it pointed at has moved, the entry is
repointed when he next starts from his new place; an entry pointing somewhere
that still exists is never touched, so trying out a copy (or the source) doesn't
take over your login.
"""

from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path
from typing import Any, Protocol

APP_NAME = "Zengo"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def own_command() -> list[str]:
    """How to start him as he's running now. From an AppImage, that's the
    AppImage file itself: what's running is a copy unpacked for the while."""
    appimage = os.environ.get("APPIMAGE")
    if appimage and Path(appimage).is_file():
        return [appimage]
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, "-m", "zengo"]


class _Entry(Protocol):
    def read(self) -> list[str] | None: ...
    def write(self, command: list[str]) -> None: ...
    def remove(self) -> None: ...


class DesktopEntry:
    """The freedesktop autostart file."""

    def __init__(self, config_home: Path | None = None) -> None:
        home = config_home or Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
        self.path = home / "autostart" / "zengo.desktop"

    def read(self) -> list[str] | None:
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except (OSError, ValueError):
            return None
        for line in lines:
            if line.startswith("Exec="):
                return _desktop_split(line.removeprefix("Exec=")) or None
        return None

    def write(self, command: list[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        exec_line = " ".join(_desktop_quote(arg) for arg in command)
        self.path.write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            f"Name={APP_NAME}\n"
            "Comment=Zengo the desktop cockatiel\n"
            f"Exec={exec_line}\n"
            "Terminal=false\n"
            "X-GNOME-Autostart-enabled=true\n",
            encoding="utf-8",
        )

    def remove(self) -> None:
        self.path.unlink(missing_ok=True)


def _desktop_split(exec_line: str) -> list[str]:
    """The arguments of an Exec line: split on spaces, except inside double
    quotes, where a backslash takes the next character as it is."""
    args: list[str] = []
    current: list[str] = []
    quoted = started = False
    chars = iter(exec_line)
    for c in chars:
        if quoted:
            if c == "\\":
                current.append(next(chars, ""))
            elif c == '"':
                quoted = False
            else:
                current.append(c)
        elif c == '"':
            quoted = started = True
        elif c in " \t":
            if started:
                args.append("".join(current))
                current, started = [], False
        else:
            current.append(c)
            started = True
    if started:
        args.append("".join(current))
    return args


def _desktop_quote(arg: str) -> str:
    """Quoted as the Desktop Entry spec wants, where it needs quoting."""
    if arg and not any(c in arg for c in " \t\n\"'\\><~|&;$*?#()`"):
        return arg
    escaped = "".join("\\" + c if c in '"`$\\' else c for c in arg)
    return f'"{escaped}"'


class RunKey:
    """The Windows registry's Run key for the current user."""

    def __init__(self, registry: Any = None) -> None:
        if registry is None:
            import winreg as registry  # type: ignore[import-not-found,no-redef]
        self._reg = registry

    def read(self) -> list[str] | None:
        reg = self._reg
        try:
            with reg.OpenKey(reg.HKEY_CURRENT_USER, RUN_KEY) as key:
                value, _ = reg.QueryValueEx(key, APP_NAME)
        except OSError:
            return None
        if not isinstance(value, str):
            return None
        return [part.strip('"') for part in shlex.split(value, posix=False)] or None

    def write(self, command: list[str]) -> None:
        reg = self._reg
        value = " ".join(f'"{arg}"' if " " in arg else arg for arg in command)
        with reg.CreateKey(reg.HKEY_CURRENT_USER, RUN_KEY) as key:
            reg.SetValueEx(key, APP_NAME, 0, reg.REG_SZ, value)

    def remove(self) -> None:
        reg = self._reg
        try:
            with reg.OpenKey(reg.HKEY_CURRENT_USER, RUN_KEY, 0, reg.KEY_SET_VALUE) as key:
                reg.DeleteValue(key, APP_NAME)
        except OSError:
            pass


class Autostart:
    """Whether he starts at login, and the switch for it."""

    def __init__(self, entry: _Entry | None, command: list[str] | None = None) -> None:
        self._entry = entry
        self._command = command or own_command()

    @classmethod
    def for_this_system(cls) -> Autostart:
        if sys.platform.startswith("linux"):
            return cls(DesktopEntry())
        if sys.platform == "win32":
            return cls(RunKey())
        return cls(None)  # elsewhere: not supported (yet)

    @property
    def supported(self) -> bool:
        return self._entry is not None

    def enabled(self) -> bool | None:
        """On or off; ``None`` where it isn't supported."""
        if self._entry is None:
            return None
        return self._entry.read() is not None

    def set(self, on: bool) -> None:
        """Turn it on or off. Failing quietly (a read-only folder) leaves it as it was."""
        if self._entry is None:
            return
        try:
            if on:
                self._entry.write(self._command)
            else:
                self._entry.remove()
        except OSError as error:
            print(f"zengo: can't change starting at login: {error}", file=sys.stderr)

    def refresh(self) -> None:
        """If it's on but points at a program that's no longer there (the binary
        was moved), point it at this one."""
        if self._entry is None:
            return
        current = self._entry.read()
        if current is None or current == self._command:
            return
        if not Path(current[0]).exists():
            self.set(True)
