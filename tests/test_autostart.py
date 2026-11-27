"""Starting Zengo at login: the freedesktop file on Linux, the Run key on Windows."""

import sys

from zengo.ui.autostart import Autostart, DesktopEntry, RunKey


def test_the_desktop_file_is_written_and_removed(tmp_path):
    entry = DesktopEntry(tmp_path)
    auto = Autostart(entry, ["/opt/zengo/zengo"])
    assert auto.enabled() is False
    auto.set(True)
    assert auto.enabled() is True
    text = entry.path.read_text()
    assert entry.path == tmp_path / "autostart" / "zengo.desktop"
    assert "Exec=/opt/zengo/zengo\n" in text and "Type=Application" in text
    auto.set(False)
    assert auto.enabled() is False and not entry.path.exists()


def test_awkward_paths_are_quoted_and_read_back(tmp_path):
    command = ["/home/me/My Apps/py$thon", "-m", "zengo"]
    entry = DesktopEntry(tmp_path)
    entry.write(command)
    assert 'Exec="/home/me/My Apps/py\\$thon" -m zengo' in entry.path.read_text()
    assert entry.read() == command


def test_running_from_source_starts_this_python(monkeypatch):
    from zengo.ui import autostart

    monkeypatch.delattr(sys, "frozen", raising=False)
    assert autostart.own_command() == [sys.executable, "-m", "zengo"]
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert autostart.own_command() == [sys.executable]


def test_a_moved_binary_is_found_again_but_a_working_entry_is_left_alone(tmp_path):
    entry = DesktopEntry(tmp_path)
    here = tmp_path / "zengo-new"
    here.touch()
    entry.write([str(tmp_path / "old-place" / "zengo")])  # moved away: gone
    Autostart(entry, [str(here)]).refresh()
    assert entry.read() == [str(here)]

    other = tmp_path / "zengo-installed"
    other.touch()
    entry.write([str(other)])  # still there: someone else's entry, keep it
    Autostart(entry, [str(here)]).refresh()
    assert entry.read() == [str(other)]


def test_off_stays_off_on_refresh(tmp_path):
    entry = DesktopEntry(tmp_path)
    Autostart(entry, ["/x/zengo"]).refresh()
    assert not entry.path.exists()


class FakeRegistry:
    """Just enough of ``winreg`` for the Run key."""

    HKEY_CURRENT_USER, KEY_SET_VALUE, REG_SZ = "HKCU", 2, 1

    def __init__(self):
        self.values = {}

    class _Key:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def OpenKey(self, root, path, *args):
        return self._Key()

    CreateKey = OpenKey

    def QueryValueEx(self, key, name):
        if name not in self.values:
            raise FileNotFoundError(name)
        return self.values[name], self.REG_SZ

    def SetValueEx(self, key, name, reserved, kind, value):
        self.values[name] = value

    def DeleteValue(self, key, name):
        if name not in self.values:
            raise FileNotFoundError(name)
        del self.values[name]


def test_the_windows_run_key_is_set_and_cleared():
    registry = FakeRegistry()
    auto = Autostart(RunKey(registry), [r"C:\Program Files\Zengo\zengo.exe"])
    assert auto.enabled() is False
    auto.set(True)
    assert registry.values["Zengo"] == r'"C:\Program Files\Zengo\zengo.exe"'
    assert RunKey(registry).read() == [r"C:\Program Files\Zengo\zengo.exe"]
    auto.set(False)
    assert auto.enabled() is False
    auto.set(False)  # already off: nothing to remove, no complaint


def test_unsupported_systems_have_no_switch():
    auto = Autostart(None)
    assert auto.enabled() is None and not auto.supported
    auto.set(True)  # does nothing
