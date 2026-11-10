"""ProjectScreen — step 0: create or load the project everything else reads and writes,
change the remembered projects folder, and set the video format (aspect / fps / UHD) for
new projects and — via Save format — for the current one. app.project_dir is always the
CURRENT project folder.
"""
import os

from textual.containers import Horizontal
from textual.widgets import Checkbox, Input, Label, Select, Static

from .. import config
from .. import project as project_mod
from .base import SubmenuScreen
from .paths import PathInput

# display order per the README's format list; values must exist in project.ASPECTS
ASPECT_OPTIONS = [(a, a) for a in ('16:9', '9:16', '1:1', '4:5')]
FPS_OPTIONS = [(str(f), f) for f in project_mod.FPS_CHOICES]


class ProjectScreen(SubmenuScreen):
    TITLE = 'New / load project'
    ACTIONS = [('create', 'Create new project'), ('load', 'Load existing project'),
               ('root', 'Save projects folder'), ('format', 'Save format')]

    def compose_body(self):
        with Horizontal(classes='path-row'):
            yield Label('Name')
            yield Input(id='name', placeholder='my-project')
        with Horizontal(classes='path-row'):
            yield Label('Directory (drop a folder from Finder)')
            yield PathInput(id='dir', placeholder='optional — <projects folder>/<name>')
        with Horizontal(classes='path-row'):
            yield Label('Projects folder')
            yield PathInput(id='root', value=config.projects_root() or config.SUGGESTED_ROOT,
                            placeholder='where new projects are created')
        with Horizontal(classes='format-row'):
            yield Label('Aspect')
            yield Select(ASPECT_OPTIONS, value='16:9', allow_blank=False, id='aspect')
            yield Label('FPS')
            yield Select(FPS_OPTIONS, value=60, allow_blank=False, id='fps')
            yield Checkbox('UHD (16:9 only)', id='uhd')

    def compose_after_actions(self):
        # below the action rows (see _RenderScreenBase): feedback never pushes the fields around
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

    def _format_values(self):
        """The three format fields, with the UHD-outside-16:9 combination refused loudly
        (set-but-invalid must abort naming it — never silently fall back)."""
        aspect = self.query_one('#aspect', Select).value
        fps = self.query_one('#fps', Select).value
        uhd = self.query_one('#uhd', Checkbox).value
        if uhd and aspect != '16:9':
            raise ValueError(f'UHD is 16:9 only — uncheck UHD or set aspect to 16:9 (got {aspect})')
        return aspect, fps, uhd

    def on_action(self, action_id):
        err = self.query_one('#error', Static)
        err.update('')
        status = self.query_one('#status', Static)
        try:
            if action_id == 'root':
                root = config.set_projects_root(self.query_one('#root', Input).value)
                status.update(f'projects folder: {root}')
                return
            if action_id == 'format':
                pd = self.require_project()
                aspect, fps, uhd = self._format_values()
                p = project_mod.load(pd)
                p['aspect'] = aspect
                p['resolution'] = project_mod.resolution_for(aspect, uhd)
                p['fps'] = fps
                project_mod.save(pd, p)
                msg = (f'format saved: {aspect} {p["resolution"][0]}x{p["resolution"][1]} '
                       f'@ {fps} fps')
                if p.get('zones'):
                    msg += (' — keep-out zones are in pixel coordinates of the previous '
                            'format — check step 3')
                status.update(msg)
                return
            name = self.query_one('#name', Input).value.strip()
            d = self._target_dir(name)
            if action_id == 'create':
                aspect, fps, uhd = self._format_values()  # BEFORE anything is written
                if not name:
                    name = os.path.basename(d)
                os.makedirs(d, exist_ok=True)
                if not os.path.isfile(os.path.join(d, 'project.json')):
                    project_mod.save(d, project_mod.default_project(name, aspect=aspect,
                                                                    fps=fps, uhd=uhd))
                verb = 'created'
            else:
                p = project_mod.load(d)  # raises naming the problem if invalid
                name = p['name']
                self.query_one('#aspect', Select).value = p['aspect']
                self.query_one('#fps', Select).value = p['fps']
                self.query_one('#uhd', Checkbox).value = p['resolution'] == list(project_mod.UHD)
                verb = 'loaded'
            self.app.project_dir = d
            config.set_last_project(d)
            status.update(f'{verb} {name} ({d})')
        except (ValueError, FileNotFoundError, OSError) as e:
            err.update(f'error: {e}')
