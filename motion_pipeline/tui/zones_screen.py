"""ZonesScreen — timed keep-out zones editable in the menu (design §8a).

Zones anchor to section names (never seconds). Rect is [x,y,w,h] in frame coordinates
of the current aspect. Saved into project.json zones[].
"""
import json
import os

from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Label, ListItem, ListView, Static

from .. import project as project_mod
from .base import SubmenuScreen
from .colours_screen import PROJECTS


def _load(name):
    path = os.path.join(PROJECTS, name, 'project.json')
    return json.loads(open(path).read()) if os.path.isfile(path) else project_mod.default_project(name)


class ZonesScreen(SubmenuScreen):
    def compose_body(self):
        with Horizontal():
            with Vertical(id='zonelist'):
                yield Label('Keep-out zones (click to edit)')
                yield ListView(id='zones')
            with Vertical(id='editor'):
                yield Label('Project name')
                yield Input(id='name', placeholder='my-project')
                yield Label('Zone section (transcript section name)')
                yield Input(id='section', placeholder='intro')
                yield Label('Rect [x,y,w,h] in frame coords of the project aspect')
                yield Input(id='rect', placeholder='520,100,880,880')
                with Horizontal():
                    yield Button('Add/update zone', id='save', variant='primary')
                yield Static('', id='status')
                yield Static('', id='error')

    def on_mount(self):
        self.refresh_zones()

    def refresh_zones(self):
        if not self.query('#zones'):
            return  # DOM not composed yet
        lv = self.query_one('#zones', ListView)
        lv.clear()
        name = self.query_one('#name', Input).value.strip()
        if not name:
            return
        try:
            p = _load(name)
        except Exception:
            return
        for i, z in enumerate(p.get('zones', [])):
            lv.append(ListItem(Label(f"{z['section']}: {z['rect']}"), id=f'zone-{i}'))

    def on_button_pressed(self, event):
        if event.button.id != 'save':
            return
        err = self.query_one('#error', Static)
        err.update('')
        try:
            name = self.query_one('#name', Input).value.strip()
            if not name:
                raise ValueError('project name is empty')
            section = self.query_one('#section', Input).value.strip()
            rect = [int(v) for v in self.query_one('#rect', Input).value.split(',')]
            if len(rect) != 4:
                raise ValueError('rect must be x,y,w,h')
            p = _load(name)
            zones = [z for z in p.get('zones', []) if z['section'] != section]
            zones.append({'section': section, 'rect': rect})
            p['zones'] = zones
            project_mod.save(os.path.join(PROJECTS, name), p)
            self.query_one('#status', Static).update(f'saved zone for {section!r} in {name}')
            self.refresh_zones()
        except (ValueError, json.JSONDecodeError) as e:
            err.update(f'error: {e}')
