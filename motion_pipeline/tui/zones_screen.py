"""ZonesScreen — timed keep-out zones editable in the menu (design §8a).

Zones anchor to section names (never seconds). Rect is [x,y,w,h] in frame coordinates
of the current aspect. Saved into project.json zones[] with the project's aspect (P1:
zones of other aspects stay on disk, listed dimmed as inactive).
"""
import json
import os

from textual.containers import Horizontal, Vertical
from textual.widgets import Input, Label, ListItem, ListView, Static

from .. import project as project_mod
from .. import transcript as transcript_mod
from .base import ActionMenu, SubmenuScreen


def _load(project_dir):
    path = os.path.join(project_dir, 'project.json')
    return json.loads(open(path).read()) if os.path.isfile(path) else \
        project_mod.default_project(os.path.basename(project_dir))


class ZonesScreen(SubmenuScreen):
    TITLE = 'Keep-out zones'
    ACTIONS = [('save', 'Add/update zone'), ('delete', 'Delete selected zone')]
    BODY_FILL = True

    def compose_body(self):
        with Horizontal():
            with Vertical(id='zonelist', classes='zone-list'):
                yield Label('Keep-out zones')
                yield Static('(no zones yet)', id='zones-empty', classes='muted')
                yield ListView(id='zones')
            with Vertical(id='zone-editor', classes='zone-editor'):
                yield Label('Section (transcript section name)')
                yield Input(id='section', placeholder='intro')
                yield Label('Rect x,y,w,h (frame pixels)')
                yield Input(id='rect', placeholder='520,100,880,880')
                yield Static('', id='status')
                yield Static('', id='error')

    def on_mount(self):
        self._seq = 0         # ever-increasing ListItem ids (index ids crashed with DuplicateIds, E2)
        self._by_seq = {}     # seq -> zone dict
        self._selected = None  # seq of the selected zone
        self.refresh_zones()

    def refresh_zones(self):
        if not self.query('#zones'):
            return  # DOM not composed yet
        lv = self.query_one('#zones', ListView)
        lv.clear()
        self._by_seq = {}
        pd = getattr(self.app, 'project_dir', None)
        if not pd:
            return
        try:
            p = _load(pd)
        except Exception:
            return
        self.query_one('#zones-empty', Static).display = not p.get('zones')
        for z in p.get('zones', []):
            active = z.get('aspect', p['aspect']) == p['aspect']
            text = f"{z['section']}: {z['rect']}"
            if not active:
                text += f" ({z.get('aspect')}, inactive)"
            self._by_seq[self._seq] = z
            lv.append(ListItem(Label(text, classes='' if active else 'muted'), id=f'zone-{self._seq}'))
            self._seq += 1
        if self.query('#actions'):
            self.query_one('#actions', ActionMenu).set_enabled('delete', self._selected is not None)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        seq = int(event.item.id.removeprefix('zone-'))
        z = self._by_seq[seq]
        self._selected = seq
        self.query_one('#section', Input).value = z['section']
        self.query_one('#rect', Input).value = ','.join(str(v) for v in z['rect'])
        self.query_one('#actions', ActionMenu).set_enabled('delete', True)

    def _check_section(self, pd, p, section):
        """(error, muted_note): a readable transcript pins the section names; without one the
        section is accepted with a muted note (the zone is anchored by name, checked at render)."""
        if not section:
            return 'section must not be empty', None
        tpath = os.path.join(pd, p.get('transcript', 'transcript.txt'))
        if not os.path.isfile(tpath):
            return None, 'transcript not readable — section not checked'
        try:
            model = transcript_mod.load(tpath)
        except (ValueError, OSError):
            return None, 'transcript not readable — section not checked'
        names = [s['name'] for s in model['sections']]
        if section not in names:
            return f"unknown section {section!r} — transcript has {names}", None
        return None, None

    def on_action(self, action_id):
        if action_id not in ('save', 'delete'):
            return
        err = self.query_one('#error', Static)
        err.update('')
        status = self.query_one('#status', Static)
        try:
            pd = self.require_project()
            p = _load(pd)
            if action_id == 'delete':
                if self._selected is None:
                    raise ValueError('select a zone in the list first')
                z = self._by_seq[self._selected]
                p['zones'] = [x for x in p.get('zones', []) if x['section'] != z['section']]
                project_mod.save(pd, p)
                status.update(f"deleted zone for {z['section']!r} in {os.path.basename(pd)}")
                self._selected = None
                self.refresh_zones()
                return
            section = self.query_one('#section', Input).value.strip()
            rect = [int(v) for v in self.query_one('#rect', Input).value.split(',')]
            if len(rect) != 4:
                raise ValueError('rect must be x,y,w,h')
            serr, note = self._check_section(pd, p, section)
            if serr:
                raise ValueError(serr)
            zones = [z for z in p.get('zones', []) if z['section'] != section]
            zones.append({'section': section, 'rect': rect, 'aspect': p['aspect']})
            p['zones'] = zones
            project_mod.save(pd, p)  # validate() raises on bad rect/aspect/frame BEFORE writing
            status.update(f'saved zone for {section!r} in {os.path.basename(pd)}'
                          + (f' — {note}' if note else ''))
            self._selected = None
            self.refresh_zones()
        except (ValueError, json.JSONDecodeError) as e:
            err.update(f'error: {e}')
