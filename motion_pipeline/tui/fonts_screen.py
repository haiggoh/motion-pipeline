"""FontsScreen — font family + role->weight mapping (Task 3, design G4).

Pick a bundled OFL family or a project-local client font (from the project's gitignored
fonts/ dir); map the four roles to weights; non-OFL client fonts show a licence warning
(decide-question 2). Save writes fonts config into projects/<name>/project.json.
"""
import json
import os

from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Select, Static

from .. import fonts as fonts_mod
from .colours_screen import PROJECTS


def project_json_path(project_name):
    return os.path.join(PROJECTS, project_name, 'project.json')


class FontsScreen(Screen):
    def __init__(self, extra_families=()):
        super().__init__()
        self.extra_families = list(extra_families)

    def compose(self):
        families = fonts_mod.bundled_families() + [f for f in self.extra_families
                                                    if f not in fonts_mod.bundled_families()]
        with Vertical():
            yield Label('Project name')
            yield Input(id='name', placeholder='my-project')
            yield Label('Font family')
            yield Select([(f, f) for f in families], id='family',
                         prompt='bundled OFL family…')
            for role in fonts_mod.ROLES:
                yield Label(f'{role} weight')
                yield Select([(str(w), w) for w in (400, 600, 700, 900)],
                             id=f'role-{role}', value=fonts_mod.DEFAULT_WEIGHTS[role])
            with Horizontal():
                yield Button('Save font config', id='save', variant='primary')
            yield Static('', id='licence-warning')
            yield Static('', id='status')
            yield Static('', id='error')

    def on_mount(self):
        self._refresh_warning()

    def _selected_family(self):
        sel = self.query_one('#family', Select)
        return sel.value if sel.value != Select.BLANK else None

    def _refresh_warning(self):
        fam = self._selected_family()
        warn = self.query_one('#licence-warning', Static)
        if fam and not any(fam == b for b in fonts_mod.bundled_families()):
            warn.update(f'LICENCE WARNING: {fam} is a client font (non-OFL). It lives only in the '
                        f'project\'s gitignored fonts/ and is never committed to this repo.')
        else:
            warn.update('')

    def on_select_changed(self, _event):
        self._refresh_warning()

    def on_button_pressed(self, event):
        if event.button.id != 'save':
            return
        err = self.query_one('#error', Static)
        err.update('')
        try:
            name = self.query_one('#name', Input).value.strip()
            fam = self._selected_family()
            if not name:
                raise ValueError('project name is empty')
            if not fam:
                raise ValueError('pick a font family')
            roles = {role: self.query_one(f'#role-{role}', Select).value for role in fonts_mod.ROLES}
            path = project_json_path(name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            cfg = {}
            if os.path.isfile(path):
                cfg = json.loads(open(path).read())
            cfg['fonts'] = {'family': fam, 'roles': roles}
            tmp = path + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(cfg, f, indent=2)
                f.write('\n')
            os.replace(tmp, path)
            # gate must pass for the bundled families
            fonts_mod.font_gate(os.path.dirname(path), cfg)
            self.query_one('#status', Static).update(f'saved {path}')
        except ValueError as e:
            err.update(f'error: {e}')
