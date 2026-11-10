"""ZonesScreen — timed keep-out zones editable in the menu (design §8a).

Zones anchor to section names (never seconds). Rect is [x,y,w,h] in frame coordinates
of the current aspect. Saved into project.json zones[].
"""
import json
import os

from textual.containers import Horizontal, Vertical
from textual.widgets import Input, Label, ListItem, ListView, Static

from .. import project as project_mod
from .base import SubmenuScreen


def _load(project_dir):
    path = os.path.join(project_dir, 'project.json')
    return json.loads(open(path).read()) if os.path.isfile(path) else \
        project_mod.default_project(os.path.basename(project_dir))


class ZonesScreen(SubmenuScreen):
    TITLE = 'Keep-out zones'
    ACTIONS = [('save', 'Add/update zone')]
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
        self.refresh_zones()

    def refresh_zones(self):
        if not self.query('#zones'):
            return  # DOM not composed yet
        lv = self.query_one('#zones', ListView)
        lv.clear()
        pd = getattr(self.app, 'project_dir', None)
        if not pd:
            return
        try:
            p = _load(pd)
        except Exception:
            return
        self.query_one('#zones-empty', Static).display = not p.get('zones')
        for i, z in enumerate(p.get('zones', [])):
            lv.append(ListItem(Label(f"{z['section']}: {z['rect']}"), id=f'zone-{i}'))

    def on_action(self, action_id):
        if action_id != 'save':
            return
        err = self.query_one('#error', Static)
        err.update('')
        try:
            pd = self.require_project()
            section = self.query_one('#section', Input).value.strip()
            rect = [int(v) for v in self.query_one('#rect', Input).value.split(',')]
            if len(rect) != 4:
                raise ValueError('rect must be x,y,w,h')
            p = _load(pd)
            zones = [z for z in p.get('zones', []) if z['section'] != section]
            zones.append({'section': section, 'rect': rect})
            p['zones'] = zones
            project_mod.save(pd, p)
            self.query_one('#status', Static).update(f'saved zone for {section!r} in {os.path.basename(pd)}')
            self.refresh_zones()
        except (ValueError, json.JSONDecodeError) as e:
            err.update(f'error: {e}')
