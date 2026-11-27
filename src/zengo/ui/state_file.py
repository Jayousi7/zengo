"""Where what Zengo remembers is kept between runs: a small JSON file."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QStandardPaths


class StateFile:
    """Reads and writes the state file. Never fails loudly: a missing or damaged
    file reads as nothing remembered, and a failed save is reported once on stderr."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._warned = False

    @classmethod
    def default(cls) -> StateFile:
        """In the user's app data folder: ``~/.local/share/Zengo`` on Linux,
        ``%APPDATA%\\Zengo`` on Windows (the application name must be set first)."""
        folder = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        return cls(Path(folder) / "state.json")

    def load(self) -> object:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def save(self, data: object) -> None:
        """Write ``data``, replacing the old file in one step, so a crash or power
        cut mid-save leaves the previous file whole rather than a half-written one."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, temp = tempfile.mkstemp(dir=self.path.parent, prefix=".state-", suffix=".json")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as out:
                    json.dump(data, out, indent=1)
                os.replace(temp, self.path)
            except BaseException:
                Path(temp).unlink(missing_ok=True)
                raise
        except OSError as error:
            if not self._warned:
                print(f"zengo: can't save state to {self.path}: {error}", file=sys.stderr)
                self._warned = True
