"""Packaging: running from an AppImage, and the package build script."""

from zengo.ui.autostart import _desktop_split, own_command
from zengo.ui.menu_entry import ensure_menu_entry


def test_from_an_appimage_he_starts_the_appimage_at_login(tmp_path, monkeypatch):
    image = tmp_path / "Zengo x86_64.AppImage"
    image.write_bytes(b"")
    monkeypatch.setenv("APPIMAGE", str(image))
    assert own_command() == [str(image)]
    monkeypatch.setenv("APPIMAGE", str(tmp_path / "gone.AppImage"))
    assert own_command() != [str(tmp_path / "gone.AppImage")]


def test_an_appimage_puts_him_in_the_menu_once(tmp_path):
    image = tmp_path / "apps" / "Zengo.AppImage"
    image.parent.mkdir()
    image.write_bytes(b"")
    home = tmp_path / "share"
    assert ensure_menu_entry(b"png", str(image), home)
    entry = home / "applications" / "zengo.desktop"
    text = entry.read_text(encoding="utf-8")
    exec_line = next(line for line in text.splitlines() if line.startswith("Exec="))
    assert _desktop_split(exec_line.removeprefix("Exec=")) == [str(image)]
    assert "Icon=zengo" in text
    assert (home / "icons/hicolor/256x256/apps/zengo.png").read_bytes() == b"png"
    assert not ensure_menu_entry(b"png", str(image), home)  # nothing to do the second time
    moved = tmp_path / "Zengo.AppImage"
    image.rename(moved)
    assert ensure_menu_entry(b"png", str(moved), home)  # moved: the entry follows it


def test_not_from_an_appimage_the_menu_is_left_alone(tmp_path):
    assert not ensure_menu_entry(b"png", None, tmp_path)
    assert not ensure_menu_entry(b"png", "", tmp_path)
    assert not any(tmp_path.iterdir())


def test_the_package_layout(tmp_path):
    import importlib.util
    import stat
    from pathlib import Path

    script = Path(__file__).resolve().parent.parent / "scripts" / "package_linux.py"
    spec = importlib.util.spec_from_file_location("package_linux", script)
    package = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(package)
    binary = tmp_path / "zengo"
    binary.write_bytes(b"#!")
    root = tmp_path / "root"
    package._install_tree(root, binary)
    zengo = root / "usr/bin/zengo"
    assert zengo.stat().st_mode & 0o777 == 0o755
    entry = root / "usr/share/applications/zengo.desktop"
    assert stat.S_IMODE(entry.stat().st_mode) == 0o644
    assert "Exec=zengo" in entry.read_text(encoding="utf-8")
    assert (root / "usr/share/icons/hicolor/256x256/apps/zengo.png").stat().st_size > 100
    assert package.version().count(".") == 2
