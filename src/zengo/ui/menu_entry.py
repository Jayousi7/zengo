"""Run as an AppImage, Zengo puts himself in your applications menu.

An AppImage is one file you download and run: nothing installs it, so nothing
adds it to the menu. The first time he runs from one (and whenever it's been
moved since), he writes a menu entry and his icon to your own data folder,
pointing at the AppImage. Installed from the .deb, the package has done this
already, and running from source he leaves the menu alone.
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


def ensure_menu_entry(
    icon_png: bytes, appimage: str | None = None, home: Path | None = None
) -> bool:
    """Running from an AppImage, make sure the menu has him, pointing at it.
    True if anything was written."""
    appimage = appimage if appimage is not None else os.environ.get("APPIMAGE")
    if not appimage or not Path(appimage).is_file():
        return False
    home = home or data_home()
    entry = home / "applications" / "zengo.desktop"
    icon = home / "icons" / "hicolor" / "256x256" / "apps" / f"{ICON_NAME}.png"
    wrote = False
    try:
        current = None
        if entry.exists():
            for line in entry.read_text(encoding="utf-8").splitlines():
                if line.startswith("Exec="):
                    current = _desktop_split(line.removeprefix("Exec="))
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
