"""Keeping some windows in front of Zengo's own.

The branch, the cage, his dish and the speech cloud must stay in front of him:
his tail hangs behind the branch, he sits behind the bars. Window managers don't
reliably allow that: Cinnamon, for one, ignores requests to raise windows that
never take focus, and doesn't keep a transient window above its parent when both
are "always on top". So these windows bypass the window manager altogether, as
menus and tooltips do: the X server stacks them, above the managed windows, and
raising them simply works. They still get mouse clicks and drags. On Windows the
flag means nothing and stacking works as asked.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget


def bypass_window_manager(window: QWidget) -> None:
    window.setWindowFlag(Qt.WindowType.BypassWindowManagerHint, True)
