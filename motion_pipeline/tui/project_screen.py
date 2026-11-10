"""ProjectScreen — step 0: create or load the project everything else reads and writes, and
change the remembered projects folder. app.project_dir is always the CURRENT project folder.
"""
import os

from textual.widgets import Input, Label, Static

from .. import config
from .. import project as project_mod
from .base import SubmenuScreen
from .paths import PathInput


class ProjectScreen(SubmenuScreen):
    TITLE = 'New / load project'
    ACTIONS = [('create', 'Create new project'), ('load', 'Load existing project'),
               ('root', 'Save projects folder')]

    def compose_body(self):
        yield Label('Project name')
        yield Input(id='name', placeholder='my-project')
        yield Label('Project directory (optional; drop a folder from Finder)')
        yield PathInput(id='dir', placeholder='<projects folder>/<name>')
        yield Label('Projects folder (where new projects are created)')
        yield PathInput(id='root', value=config.projects_root() or config.SUGGESTED_ROOT)
        yield Static('', id='status')
        yield Static('', id='error')

    def _target_dir(self, name):
        d = self.query_one('#dir', Input).value.strip()
        if d:
            return os.path.abspath(os.path.expanduser(d))
        root = config.projects_root()
        if not root:
            raise ValueError('no projects folder chosen yet — set one below and save it')
        if not name:
            raise ValueError('project name is empty')
        return os.path.join(root, name)

    def on_action(self, action_id):
        err = self.query_one('#error', Static)
        err.update('')
        status = self.query_one('#status', Static)
        try:
            if action_id == 'root':
                root = config.set_projects_root(self.query_one('#root', Input).value)
                status.update(f'projects folder: {root}')
                return
            name = self.query_one('#name', Input).value.strip()
            d = self._target_dir(name)
            if action_id == 'create':
                if not name:
                    name = os.path.basename(d)
                os.makedirs(d, exist_ok=True)
                if not os.path.isfile(os.path.join(d, 'project.json')):
                    project_mod.save(d, project_mod.default_project(name))
                verb = 'created'
            else:
                p = project_mod.load(d)  # raises naming the problem if invalid
                name = p['name']
                verb = 'loaded'
            self.app.project_dir = d
            config.set_last_project(d)
            status.update(f'{verb} {name} ({d})')
        except (ValueError, FileNotFoundError, OSError) as e:
            err.update(f'error: {e}')
