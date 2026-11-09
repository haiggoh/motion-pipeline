"""ColoursScreen — CI colour setup (design §2 step 1, G3).

Enter the few main colours + a name; the rest of the palette is derived (scheme.derive_palette).
"Derive & preview" shows the derived roles; "Save scheme" writes projects/<name>/scheme.json;
the list on the left loads an existing scheme back for re-editing (G3 "saved as files and
re-editable in the menu").
"""
import os

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Label, ListItem, ListView, Static

from .. import scheme as scheme_mod
from .base import MenuAppBase, SubmenuScreen

PROJECTS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'projects')


def scheme_path(project_name):
    return os.path.join(PROJECTS, project_name, 'scheme.json')


class ColoursScreen(SubmenuScreen):
    def compose_body(self):
        with Horizontal():
            with Vertical(id='scheme-list'):
                yield Label('Saved schemes (click to re-edit)')
                yield ListView(id='schemes')
            with Vertical(id='editor'):
                yield Label('Project name')
                yield Input(id='name', placeholder='my-project')
                for key, label in [('background_dark', 'Background (dark) #hex'),
                                   ('background_light', 'Background glow/light #hex'),
                                   ('accent', 'Accent #hex'),
                                   ('text', 'Text #hex')]:
                    yield Label(label)
                    yield Input(id=key, placeholder='#rrggbb')
                with Horizontal():
                    yield Button('Derive & preview', id='derive')
                    yield Button('Save scheme', id='save', variant='primary')
                yield Static('', id='preview')
                yield Static('', id='error')

    def on_mount(self) -> None:
        self.refresh_scheme_list()

    def refresh_scheme_list(self) -> None:
        if not self.query('#schemes'):
            return  # DOM not composed yet
        lv = self.query_one('#schemes', ListView)
        existing = {getattr(c, 'id', '') for c in lv.children}
        if not os.path.isdir(PROJECTS):
            return
        for name in sorted(os.listdir(PROJECTS)):
            if os.path.isfile(scheme_path(name)) and f'scheme-{name}' not in existing:
                lv.append(ListItem(Label(name), id=f'scheme-{name}'))

    def current_scheme(self):
        name = self.query_one('#name', Input).value.strip()
        vals = {k: self.query_one(f'#{k}', Input).value.strip() for k in scheme_mod.INPUT_KEYS[1:]}
        return {'name': name, **vals}

    def on_button_pressed(self, event: Button.Pressed) -> None:
        err = self.query_one('#error', Static)
        err.update('')
        try:
            s = scheme_mod.validate_scheme(self.current_scheme())
            if event.button.id == 'derive':
                p = scheme_mod.derive_palette(s)
                lines = [f'{k}: {v}' for k, v in p.items() if k != 'gradient_stops']
                lines.append('gradient_stops: ' + ' -> '.join(p['gradient_stops']))
                self.query_one('#preview', Static).update('\n'.join(lines))
            elif event.button.id == 'save':
                if not s['name']:
                    raise ValueError('project name is empty')
                scheme_mod.save_scheme(scheme_path(s['name']), s)
                self.query_one('#preview', Static).update(f'saved {scheme_path(s["name"])}')
                self.refresh_scheme_list()
        except ValueError as e:
            err.update(f'error: {e}')

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        name = event.item.id.removeprefix('scheme-')
        s = scheme_mod.load_scheme(scheme_path(name))
        self.query_one('#name', Input).value = s['name']
        for k in scheme_mod.INPUT_KEYS[1:]:
            self.query_one(f'#{k}', Input).value = s[k]


class MotionPipelineApp(MenuAppBase):
    """The project menu (Task 5 extends this with the remaining screens)."""

    def on_mount(self) -> None:
        self.push_screen(ColoursScreen())
