"""paths.py — Finder drag-and-drop into path fields (0.5.0 Task 5).

A drop onto a terminal window arrives as a bracketed PASTE of the item's path, delivered to
whichever widget has focus. Terminals encode it differently:
  Terminal.app   /a/My\\ Folder<space>       (backslash-escaped, trailing space)
  iTerm2         '/a/My Folder'             (single-quoted)
  some apps      file:///a/My%20Folder/      (URL)
normalize_dropped_path() turns every form into the plain path; PathInput replaces its value
with it (a drop means "this path", never "insert at the cursor") and shows ✓/✗ existence in
its frame. SubmenuScreen routes a paste that lands on a non-input widget to the screen's
first PathInput (v0.4.x: focus sat on the Back button, so drops vanished).
"""
import os
import shlex
from urllib.parse import unquote, urlparse

from textual import events
from textual.widgets import Input


def normalize_dropped_path(text: str) -> str:
    t = (text or '').strip()
    if not t:
        return ''
    if t.startswith('file://'):
        first = t.split()[0]
        p = unquote(urlparse(first).path)
        return p.rstrip('/') if len(p) > 1 else p
    try:
        parts = shlex.split(t)   # handles \-escapes, '…' and "…" quoting, multiple items
    except ValueError:
        parts = [t]
    p = parts[0] if parts else t
    return os.path.expanduser(p)


class PathInput(Input):
    """A text field for a file/folder path: drops and pastes are decoded and REPLACE the
    value; the frame's subtitle says whether the path exists (relative paths resolve against
    the current project folder)."""

    def _resolve(self, value):
        if not value or os.path.isabs(value):
            return value
        base = getattr(self.app, 'project_dir', None) or os.getcwd()
        return os.path.join(base, value)

    def update_status(self):
        v = self.value.strip()
        if not v:
            self.border_subtitle = ''
        elif os.path.exists(self._resolve(v)):
            self.border_subtitle = '✓ exists'
        else:
            self.border_subtitle = '✗ not found'

    def on_mount(self):
        self.update_status()

    def on_input_changed(self, event):
        if event.input is self:
            self.update_status()

    def _on_paste(self, event: events.Paste) -> None:
        # Textual dispatches _on_paste through the MRO: prevent_default stops Input's own
        # handler (which would INSERT the raw escaped text at the cursor) — never super().
        event.prevent_default()
        event.stop()
        path = normalize_dropped_path(event.text)
        if path:
            self.value = path
            self.cursor_position = len(path)
