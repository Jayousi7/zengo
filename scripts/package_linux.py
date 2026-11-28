"""Package the Linux build (``dist/zengo``, from ``scripts/build.py``) as a .deb
and, given appimagetool, an AppImage. Both land in ``dist/``.

    python scripts/package_linux.py [--appimagetool PATH]

The .deb installs to /usr/bin with a menu entry and icon. The AppImage is one
file; run, it adds its own menu entry (see ``zengo/ui/menu_entry.py``).
"""

import argparse
import os
import shutil
import stat
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
WORK = ROOT / "build" / "package"
DESKTOP = ROOT / "packaging" / "linux" / "zengo.desktop"
ICON = ROOT / "packaging" / "icons" / "zengo.png"

CONTROL = """\
Package: zengo
Version: {version}
Section: games
Priority: optional
Architecture: amd64
Depends: libxcb-cursor0
Maintainer: Zengo <https://github.com/Jayousi7/zengo>
Homepage: https://github.com/Jayousi7/zengo
Description: Zengo the desktop cockatiel
 A pixel-art cockatiel who lives on your desktop: he walks, flies, perches on
 your windows, eats, bathes, plays and keeps you company while you work.
"""

APPRUN = """\
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/zengo" "$@"
"""


def version() -> str:
    with open(ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)["project"]["version"]


def _executable(path: Path) -> None:
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _install_tree(root: Path, binary: Path) -> None:
    """The files as installed under ``root``: /usr/bin, the menu entry, the icon."""
    (root / "usr" / "bin").mkdir(parents=True)
    shutil.copy2(binary, root / "usr" / "bin" / "zengo")
    _executable(root / "usr" / "bin" / "zengo")
    apps = root / "usr" / "share" / "applications"
    icons = root / "usr" / "share" / "icons" / "hicolor" / "256x256" / "apps"
    apps.mkdir(parents=True)
    icons.mkdir(parents=True)
    shutil.copy2(DESKTOP, apps / "zengo.desktop")
    shutil.copy2(ICON, icons / "zengo.png")
    _tidy(root)


def _tidy(root: Path) -> None:
    """Plain permissions whatever the umask: folders 755, files 644, programs 755."""
    for path in [root, *root.rglob("*")]:
        executable = path.is_dir() or path.stat().st_mode & stat.S_IXUSR
        path.chmod(0o755 if executable else 0o644)


def deb(binary: Path, v: str) -> Path:
    root = WORK / f"zengo_{v}_amd64"
    _install_tree(root, binary)
    (root / "DEBIAN").mkdir()
    (root / "DEBIAN" / "control").write_text(CONTROL.format(version=v), encoding="utf-8")
    out = DIST / f"zengo_{v}_amd64.deb"
    subprocess.run(["dpkg-deb", "--build", "--root-owner-group", str(root), str(out)], check=True)
    return out


def appimage(binary: Path, v: str, tool: Path) -> Path:
    appdir = WORK / "Zengo.AppDir"
    _install_tree(appdir, binary)
    shutil.copy2(DESKTOP, appdir / "zengo.desktop")
    shutil.copy2(ICON, appdir / "zengo.png")
    (appdir / "AppRun").write_text(APPRUN, encoding="utf-8")
    _executable(appdir / "AppRun")
    out = DIST / f"Zengo-{v}-x86_64.AppImage"
    env = {**os.environ, "ARCH": "x86_64", "APPIMAGE_EXTRACT_AND_RUN": "1"}
    subprocess.run([str(tool.resolve()), str(appdir), str(out)], check=True, env=env)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--appimagetool", type=Path, help="appimagetool, to build the AppImage")
    args = parser.parse_args()
    binary = DIST / "zengo"
    if not binary.is_file():
        raise SystemExit(f"{binary} not found: run scripts/build.py first")
    shutil.rmtree(WORK, ignore_errors=True)
    v = version()
    print(f"built {deb(binary, v)}")
    if args.appimagetool:
        print(f"built {appimage(binary, v, args.appimagetool)}")


if __name__ == "__main__":
    main()
