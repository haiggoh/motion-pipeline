"""terminal_driver.py — Apple Terminal compatibility adapter for Textual (spec A1).

Textual 8.2.8's LinuxDriver._query_in_band_window_resize (linux_driver.py:157) writes
the DECRQM 2048 query `ESC[?2048$p` unconditionally; Apple Terminal does not consume it
and prints the trailing `p` visibly (stray `p` on startup). The subclass below is a
no-op for that query only when TERM_PROGRAM=Apple_Terminal; every other terminal and
every other driver feature (mouse, bracketed paste, 2026 sync, resize handling) is
inherited unchanged. Ported from free-agents' bin/session_picker_terminal.py.

Integration: pass via the App CONSTRUCTOR — `App.__init__` does
`self.driver_class = driver_class or self.get_driver_class()` (app.py:637), so a class
attribute is overwritten. MenuAppBase.__init__ does kwargs.setdefault('driver_class',
get_driver_class()).
"""
from __future__ import annotations

import os

from textual.drivers.linux_driver import LinuxDriver


class AppleTerminalSafeDriver(LinuxDriver):
    """LinuxDriver that skips the 2048 DECRQM query on Apple Terminal only."""

    def _query_in_band_window_resize(self) -> None:
        if os.environ.get('TERM_PROGRAM', '') == 'Apple_Terminal':
            return
        super()._query_in_band_window_resize()


def get_driver_class() -> type[LinuxDriver] | None:
    """The safe driver on macOS/Linux (where LinuxDriver would be selected), None elsewhere
    (Windows / custom TEXTUAL_DRIVER keep Textual's auto-detection)."""
    if os.name != 'posix':
        return None
    return AppleTerminalSafeDriver
