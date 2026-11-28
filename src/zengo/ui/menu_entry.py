"""Run as an AppImage, Zengo puts himself in your applications menu.

An AppImage is one file you download and run: nothing installs it, so nothing
adds it to the menu. The first time he runs from one (and whenever it's been
moved since), he writes a menu entry and his icon to your own data folder,
pointing at the AppImage. Installed from the .deb, the package has done this
already, and running from source he leaves the menu alone, except to clear away
an entry he once wrote for an AppImage that's since been deleted: left there, it
would hide the .deb's own entry and the menu would start nothing.
"""

from __future__ import annotations

import os
from pathlib import Path

from zengo.ui.autostart import APP_NAME, _desktop_quote, _desktop_split

ICON_NAME = "zengo"


def data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")


def entry_text(command: list[str]) -> str:
    exec_line = " ".join(_desktop_quote(arg) for arg in command)
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={APP_NAME}\n"
        "GenericName=Desktop pet\n"
        "Comment=Zengo the desktop cockatiel\n"
        f"Exec={exec_line}\n"
        f"Icon={ICON_NAME}\n"
        "Terminal=false\n"
        "Categories=Game;Amusement;\n"
        "StartupNotify=false\n"
    )


def _entry_command(entry: Path) -> list[str] | None:
    if not entry.exists():
        return None
    for line in entry.read_text(encoding="utf-8").splitlines():
        if line.startswith("Exec="):
            return _desktop_split(line.removeprefix("Exec="))
    return None


def _points_at_a_lost_appimage(command: list[str] | None) -> bool:
    """An entry he wrote for an AppImage (just its path) that's no longer there."""
    return (
        command is not None
        and len(command) == 1
        and command[0].lower().endswith(".appimage")
        and not Path(command[0]).exists()
    )


def ensure_menu_entry(
    icon_png: bytes, appimage: str | None = None, home: Path | None = None
) -> bool:
    """Running from an AppImage, make sure the menu has him, pointing at it.
    Otherwise, clear away an entry left for an AppImage that's gone.
    True if anything was written or removed."""
    appimage = appimage if appimage is not None else os.environ.get("APPIMAGE")
    home = home or data_home()
    entry = home / "applications" / "zengo.desktop"
    icon = home / "icons" / "hicolor" / "256x256" / "apps" / f"{ICON_NAME}.png"
    if not appimage or not Path(appimage).is_file():
        try:
            if not _points_at_a_lost_appimage(_entry_command(entry)):
                return False
            entry.unlink()
            icon.unlink(missing_ok=True)
        except (OSError, ValueError):
            return False
        return True
    wrote = False
    try:
        current = _entry_command(entry)
        if current != [appimage]:
            entry.parent.mkdir(parents=True, exist_ok=True)
            entry.write_text(entry_text([appimage]), encoding="utf-8")
            wrote = True
        if not icon.exists():
            icon.parent.mkdir(parents=True, exist_ok=True)
            icon.write_bytes(icon_png)
            wrote = True
    except (OSError, ValueError):
        return False  # a menu entry is a nicety: never a reason not to start
    return wrote
