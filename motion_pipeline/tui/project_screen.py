"""ProjectScreen — step 0: create or load the project file/directory everything is stored in."""
import os

from textual.containers import Vertical
from textual.widgets import Input, Label, Static

from .. import project as project_mod
from .base import SubmenuScreen


class ProjectScreen(SubmenuScreen):
    TITLE = 'New / load project'
    ACTIONS = [('create', 'Create new project'), ('load', 'Load existing project')]

    def compose_body(self):
        with Vertical():
            yield Label('Project name')
            yield Input(id='name', placeholder='my-project')
            yield Label('Project directory (drop a folder from Finder to paste its path, or type it)')
            yield Input(id='dir', placeholder='projects/my-project')
            yield Static('', id='status')
            yield Static('', id='error')

    def on_action(self, action_id):
        if action_id not in ('create', 'load'):
            return
        err = self.query_one('#error', Static)
        err.update('')
        try:
            name = self.query_one('#name', Input).value.strip()
            d = self.query_one('#dir', Input).value.strip() or os.path.join('projects', name or 'my-project')
            if not name:
                raise ValueError('project name is empty')
            if action_id == 'create':
                os.makedirs(d, exist_ok=True)
                pj = os.path.join(d, 'project.json')
                if not os.path.isfile(pj):
                    project_mod.save(d, project_mod.default_project(name))
                self.app.project_dir = os.path.abspath(d)
                self.query_one('#status', Static).update(f'created {self.app.project_dir}')
            else:
                p = project_mod.load(d)  # raises naming the problem if invalid
                self.app.project_dir = os.path.abspath(d)
                self.query_one('#status', Static).update(f'loaded {p["name"]} from {self.app.project_dir}')
        except (ValueError, FileNotFoundError) as e:
            err.update(f'error: {e}')
