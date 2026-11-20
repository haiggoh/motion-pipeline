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


def normalize_dropped_paths(text: str) -> list[str]:
    """All items of a drop, decoded (Terminal.app \\-escapes, iTerm '…', file:// URLs)."""
    t = (text or '').strip()
    if not t:
        return []
    if t.startswith('file://'):
        p = unquote(urlparse(t.split()[0]).path)
        return [p.rstrip('/') if len(p) > 1 else p]
    try:
        parts = shlex.split(t)   # handles \-escapes, '…' and "…" quoting, multiple items
    except ValueError:
        parts = [t]
    return [os.path.expanduser(p) for p in parts] or [t]


def normalize_dropped_path(text: str) -> str:
    parts = normalize_dropped_paths(text)
    return parts[0] if parts else ''


# what each field accepts (spec A2): a drop goes to the single field that accepts the file
TRANSCRIPT_EXTS = ('.txt', '.md', '.rtf', '.doc', '.docx', '.pdf')
VO_EXTS = ('.wav', '.mp3', '.m4a', '.aif', '.aiff', '.flac', '.mov', '.mp4')


class PathInput(Input):
    """A text field for a file/folder path: drops and pastes are decoded and REPLACE the
    value; the frame's subtitle says whether the path exists (relative paths resolve against
    the current project folder). `accepts`/`accepts_dirs` declare what a drop may carry, so
    SubmenuScreen.route_drop can land a drop in the RIGHT field (spec A2)."""

    def __init__(self, *args, accepts: tuple[str, ...] = (), accepts_dirs: bool = False, **kw):
        self.accepts = tuple(a.lower() for a in accepts)
        self.accepts_dirs = accepts_dirs
        self._drop_note = None
        super().__init__(*args, **kw)

    def accepts_path(self, path: str) -> bool:
        """Extension match, case-insensitive; directories only when accepts_dirs;
        accepts=() without accepts_dirs accepts any file."""
        if os.path.isdir(path):
            return self.accepts_dirs
        ext = os.path.splitext(path)[1].lower()
        if self.accepts:
            return ext in self.accepts
        return not self.accepts_dirs

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
        note = self._drop_note
        if note:
            self.border_subtitle = note
            self._drop_note = None

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
        route = getattr(self.screen, 'route_drop', None)
        target = route(event.text) if route is not None else self
        if target is None:
            return
        paths = normalize_dropped_paths(event.text)
        if not paths:
            return
        if len(paths) > 1:
            target._drop_note = f'{len(paths)} items dropped — used the first'
        path = paths[0]
        target.value = path
        target.cursor_position = len(path)
        if len(paths) > 1:
            target.border_subtitle = target._drop_note
        else:
            target.update_status()
        target.focus()
