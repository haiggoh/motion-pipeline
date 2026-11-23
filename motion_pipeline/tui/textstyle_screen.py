"""TextStyleScreen — pick the L0 base text style (0.8.0 Task 4 / user Q1).

Data-driven: the list is text_styles.STYLES itself, so a new table row appears here with no
change to this file (pinned by the monkeypatched-row test in tests/test_text_style.py).
Saved as text_style in project.json; projects saved before 0.8.0 have no key and render the
default.
"""
import json
import os

from textual.containers import Vertical
from textual.widgets import Label, ListItem, ListView, Static

from .. import project as project_mod
from .. import text_styles
from .base import SubmenuScreen


class TextStyleScreen(SubmenuScreen):
    TITLE = 'Text animation'
    ACTIONS = [('save', 'Save as project text style')]
    BODY_FILL = True
    EXPLAIN = ('How the base text enters each scene. Saved as "text_style" in project.json; '
               'projects saved before 0.8.0 have no key and render the default.')

    def compose_body(self):
        yield Static(self.EXPLAIN, id='ts-explain', classes='muted')
        with Vertical(id='stylelist'):
            yield Label('Styles')
            yield ListView(id='styles')
        yield Static('', id='status', classes='feedback')
        yield Static('', id='error', classes='feedback-error')

    def on_mount(self):
        self._seq = 0        # ever-increasing ListItem ids (index ids crashed with DuplicateIds, E2)
        self._by_seq = {}    # seq -> style name
        self._selected = None
        self.refresh_styles()

    def _current(self):
        pd = getattr(self.app, 'project_dir', None)
        pj = os.path.join(pd, 'project.json') if pd else None
        if pj and os.path.isfile(pj):
            try:
                return json.loads(open(pj).read()).get('text_style', text_styles.DEFAULT)
            except (ValueError, OSError):
                return text_styles.DEFAULT
        return text_styles.DEFAULT

    def refresh_styles(self):
        if not self.query('#styles'):
            return
        lv = self.query_one('#styles', ListView)
        lv.clear()
        self._by_seq = {}
        current = self._current()
        for name, st in text_styles.STYLES.items():
            mark = '*' if name == current else ' '
            self._by_seq[self._seq] = name
            lv.append(ListItem(Label(f'{mark} {st.label}  ({name})'), id=f'style-{self._seq}'))
            self._seq += 1

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self._selected = self._by_seq[int(event.item.id.removeprefix('style-'))]

    def on_action(self, action_id):
        if action_id != 'save':
            return
        err = self.query_one('#error', Static)
        status = self.query_one('#status', Static)
        err.update('')
        try:
            pd = self.require_project()
            if not self._selected:
                raise ValueError('select a style in the list first')
            if self._selected not in text_styles.STYLES:
                raise ValueError(f"unknown style {self._selected!r} — want one of {sorted(text_styles.STYLES)}")
            p = project_mod.load(pd)
            p['text_style'] = self._selected
            project_mod.save(pd, p)  # validate() re-checks the style name before writing
            status.update(f"saved text_style={self._selected!r} in {os.path.basename(pd)}")
            self.refresh_styles()
        except (ValueError, OSError) as e:
            err.update(f'error: {e}')
